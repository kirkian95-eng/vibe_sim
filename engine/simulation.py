"""
Main simulation loop.

Orchestrates the daily cycle:
  1. Apply any shocks scheduled for today
  2. Government spending / transfers
  3. Labor market clearing (hiring + wage payment)
  4. Production
  5. Goods market clearing (purchases)
  6. Consumption
  7. Taxation
  8. Firm profit distribution
  9. Price & wage adjustment
 10. Record daily statistics
"""

from __future__ import annotations

import dataclasses as dc
import random
import time
from collections.abc import Callable

from .actors import (
    Bank,
    Firm,
    Government,
    Individual,
    create_all_actors,
)
from .config import SimConfig
from .ledger import Ledger
from .markets import (
    adjust_prices_and_wages,
    clear_goods_market,
    clear_labor_market,
    consume_goods,
    run_production,
)
from .metrics import DailyStats, collect_daily_stats
from .policy import (
    firm_profit_distribution,
    government_operations,
    post_government_spending,
)
from .shocks import Shock


class Simulation:
    """
    The main simulation engine.

    Usage:
        sim = Simulation(config, shocks=[...])
        results = sim.run()
    """

    def __init__(self, config: SimConfig, shocks: list[Shock] | None = None):
        self.config = config
        self.shocks = sorted(shocks or [], key=lambda s: s.day)
        self.rng = random.Random(config.seed)
        self.ledger = Ledger()
        self.day = 0
        self.history: list[DailyStats] = []
        self.shock_log: list[str] = []
        self._profiling: dict[str, float] = {}
        self._profile_hooks: list[Callable[[str, float], None]] = []

        # Create actors
        actors = create_all_actors(
            self.ledger,
            num_individuals=config.num_individuals,
            num_food_firms=config.num_food_firms,
            num_energy_firms=config.num_energy_firms,
            num_shelter_firms=config.num_shelter_firms,
            num_owners=config.num_owners,
            initial_prices=config.initial_prices(),
            initial_wage=config.initial_wage,
        )
        self.individuals: list[Individual] = actors["individuals"]
        self.firms: list[Firm] = actors["firms"]
        self.bank: Bank = actors["bank"]
        self.govt: Government = actors["government"]

        # Initialize the economy
        self._bootstrap()

    def _bootstrap(self) -> None:
        """
        Inject initial money into the economy via government spending.
        This is the 'genesis' — money can only exist if the government
        spends it into existence (or banks lend it).
        """
        cfg = self.config

        # Government spending creates initial money for individuals
        for ind in self.individuals:
            post_government_spending(
                self.ledger, 0, self.govt, self.bank, ind.id,
                cfg.initial_individual_cash,
                f"Bootstrap: initial cash for {ind.id}",
            )

        # Government spending creates initial money for firms
        for firm in self.firms:
            post_government_spending(
                self.ledger, 0, self.govt, self.bank, firm.id,
                cfg.initial_firm_cash,
                f"Bootstrap: initial cash for {firm.id}",
            )
            # Initial capital endowment (equity injection)
            self.ledger.post(0, f"Bootstrap: capital for {firm.id}", [
                (f"{firm.id}:capital", cfg.initial_firm_capital, 0),
                (f"{firm.id}:equity", 0, cfg.initial_firm_capital),
            ])
            # Initial inventory
            self.ledger.post(0, f"Bootstrap: inventory for {firm.id}", [
                (f"{firm.id}:inventory", cfg.initial_firm_inventory, 0),
                (f"{firm.id}:equity", 0, cfg.initial_firm_inventory),
            ])

    def add_profile_hook(self, hook: Callable[[str, float], None]) -> None:
        """Register a callback invoked with (phase_name, elapsed_seconds) each step."""
        self._profile_hooks.append(hook)

    def _profile(self, name: str, elapsed: float) -> None:
        self._profiling[name] = self._profiling.get(name, 0.0) + elapsed
        for hook in self._profile_hooks:
            hook(name, elapsed)

    def step(self) -> DailyStats:
        """Advance the simulation by one day."""
        self.day += 1
        cfg = self.config

        # 1. Apply shocks
        for shock in self.shocks:
            if shock.day == self.day:
                cfg = shock.apply(cfg)
                self.config = cfg
                self.shock_log.append(f"Day {self.day}: {shock.description}")

        journal_before = self.ledger.journal_size

        # 2. Government operations (spending + tax collection)
        t0 = time.perf_counter()
        govt_stats = government_operations(
            self.ledger, self.day, cfg, self.govt, self.bank,
            self.individuals, self.firms,
        )
        self._profile("government", time.perf_counter() - t0)

        # 3. Labor market
        t0 = time.perf_counter()
        labor_stats = clear_labor_market(
            self.ledger, self.day, cfg, self.firms,
            self.individuals, self.bank, self.rng,
        )
        self._profile("labor_market", time.perf_counter() - t0)

        # 4. Production
        t0 = time.perf_counter()
        run_production(self.ledger, self.day, cfg, self.firms)
        self._profile("production", time.perf_counter() - t0)

        # 5. Goods market
        t0 = time.perf_counter()
        goods_stats = clear_goods_market(
            self.ledger, self.day, cfg, self.firms,
            self.individuals, self.bank, self.govt, self.rng,
        )
        self._profile("goods_market", time.perf_counter() - t0)

        # 6. Consumption
        t0 = time.perf_counter()
        consume_goods(self.ledger, self.day, self.individuals, cfg)
        self._profile("consumption", time.perf_counter() - t0)

        # 7. Firm profit distribution
        t0 = time.perf_counter()
        firm_profit_distribution(
            self.ledger, self.day, cfg, self.firms,
            self.individuals, self.bank,
        )
        self._profile("profit_dist", time.perf_counter() - t0)

        # 8. Price and wage adjustments
        adjust_prices_and_wages(
            cfg, self.firms, labor_stats["unemployment_rate"], ledger=self.ledger,
        )

        # 9. Collect statistics
        t0 = time.perf_counter()
        stats = collect_daily_stats(
            self.day,
            self.ledger,
            self.individuals,
            self.firms,
            self.bank.id,
            self.govt.id,
            labor_stats,
            goods_stats,
            govt_stats,
            journal_before,
        )
        self._profile("metrics", time.perf_counter() - t0)

        self.history.append(stats)
        return stats

    def run(self) -> list[DailyStats]:
        """Run the full simulation."""
        t_start = time.perf_counter()
        for _ in range(self.config.num_days):
            self.step()
        self._profile("total_wall_time", time.perf_counter() - t_start)
        return self.history

    @property
    def profiling(self) -> dict[str, float]:
        """Cumulative timing data by phase."""
        return dict(self._profiling)

    def results_summary(self) -> dict:
        """Return a summary suitable for JSON serialization."""
        return {
            "config": dc.asdict(self.config),
            "num_days": self.day,
            "seed": self.config.seed,
            "shock_log": self.shock_log,
            "daily_stats": [s.to_dict() for s in self.history],
            "final_journal_size": self.ledger.journal_size,
            "accounting_valid": (
                self.ledger.check_all_entries_balanced()
                and self.ledger.check_system_balance()
                and self.ledger.verify_running_balances()
            ),
            "profiling": self.profiling,
        }
