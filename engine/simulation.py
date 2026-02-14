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
from typing import Dict, List, Optional

from .actors import (
    Actor,
    Bank,
    Firm,
    GoodType,
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
    firm_profit_distribution,
    government_operations,
    post_government_spending,
    run_production,
)
from .shocks import Shock


@dc.dataclass
class DailyStats:
    """Snapshot of the economy for one day."""

    day: int = 0

    # Macro
    gdp: float = 0.0  # total output value
    unemployment_rate: float = 0.0
    total_employment: int = 0
    avg_wage: float = 0.0
    govt_deficit: float = 0.0
    total_money_supply: float = 0.0

    # Prices
    food_price: float = 0.0
    energy_price: float = 0.0
    shelter_price: float = 0.0

    # Quantities
    food_produced: float = 0.0
    energy_produced: float = 0.0
    shelter_produced: float = 0.0
    food_sold: float = 0.0
    energy_sold: float = 0.0
    shelter_sold: float = 0.0

    # Distribution
    gini_coefficient: float = 0.0
    median_cash: float = 0.0
    mean_cash: float = 0.0
    top1_pct_income_share: float = 0.0
    bottom50_pct_income_share: float = 0.0

    # Sector balances
    private_sector_balance: float = 0.0
    govt_sector_balance: float = 0.0
    bank_sector_balance: float = 0.0

    # Accounting
    journal_entries_today: int = 0
    all_balanced: bool = True
    system_balanced: bool = True

    def to_dict(self) -> dict:
        return dc.asdict(self)


def compute_gini(values: List[float]) -> float:
    """Compute Gini coefficient from a list of values."""
    if not values or len(values) < 2:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    total = sum(sorted_vals)
    if total <= 0:
        return 0.0
    cumulative = 0.0
    gini_sum = 0.0
    for i, v in enumerate(sorted_vals):
        cumulative += v
        gini_sum += (2 * (i + 1) - n - 1) * v
    return gini_sum / (n * total)


class Simulation:
    """
    The main simulation engine.

    Usage:
        sim = Simulation(config, shocks=[...])
        results = sim.run()
    """

    def __init__(self, config: SimConfig, shocks: Optional[List[Shock]] = None):
        self.config = config
        self.shocks = sorted(shocks or [], key=lambda s: s.day)
        self.rng = random.Random(config.seed)
        self.ledger = Ledger()
        self.day = 0
        self.history: List[DailyStats] = []
        self.shock_log: List[str] = []

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
        self.individuals: List[Individual] = actors["individuals"]
        self.firms: List[Firm] = actors["firms"]
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
        govt_stats = government_operations(
            self.ledger, self.day, cfg, self.govt, self.bank,
            self.individuals, self.firms, self.rng,
        )

        # 3. Labor market
        labor_stats = clear_labor_market(
            self.ledger, self.day, cfg, self.firms,
            self.individuals, self.bank, self.rng,
        )

        # 4. Production
        run_production(self.ledger, self.day, cfg, self.firms)

        # 5. Goods market
        goods_stats = clear_goods_market(
            self.ledger, self.day, cfg, self.firms,
            self.individuals, self.bank, self.govt, self.rng,
        )

        # 6. Consumption
        consume_goods(self.ledger, self.day, self.individuals, cfg)

        # 7. Firm profit distribution
        total_distributed = firm_profit_distribution(
            self.ledger, self.day, cfg, self.firms,
            self.individuals, self.bank,
        )

        # 8. Price and wage adjustments
        adjust_prices_and_wages(cfg, self.firms, labor_stats["unemployment_rate"])

        # 9. Collect statistics
        stats = self._collect_stats(
            labor_stats, goods_stats, govt_stats, journal_before
        )
        self.history.append(stats)
        return stats

    def run(self) -> List[DailyStats]:
        """Run the full simulation."""
        for _ in range(self.config.num_days):
            self.step()
        return self.history

    def _collect_stats(
        self,
        labor_stats: dict,
        goods_stats: dict,
        govt_stats: dict,
        journal_before: int,
    ) -> DailyStats:
        """Gather all statistics for the current day."""
        # Cash holdings
        cash_values = []
        for ind in self.individuals:
            cash_values.append(self.ledger.account_balance(f"{ind.id}:cash"))

        sorted_cash = sorted(cash_values)
        n = len(sorted_cash)
        median_cash = sorted_cash[n // 2] if n > 0 else 0
        mean_cash = sum(sorted_cash) / n if n > 0 else 0

        # Income shares (use cash as proxy for accumulated income)
        total_cash = sum(sorted_cash)
        if total_cash > 0:
            top1_count = max(1, n // 100)
            top1_share = sum(sorted_cash[-top1_count:]) / total_cash
            bottom50_count = n // 2
            bottom50_share = sum(sorted_cash[:bottom50_count]) / total_cash
        else:
            top1_share = 0.0
            bottom50_share = 0.0

        # Production totals
        food_prod = sum(f.daily_production for f in self.firms if f.good_type == GoodType.FOOD)
        energy_prod = sum(f.daily_production for f in self.firms if f.good_type == GoodType.ENERGY)
        shelter_prod = sum(f.daily_production for f in self.firms if f.good_type == GoodType.SHELTER)

        # GDP = total revenue from goods sales
        gdp = sum(goods_stats.get(f"{g.value}_revenue", 0) for g in GoodType)

        # Average wage
        wages = [f.wage_offer for f in self.firms]
        avg_wage = sum(wages) / len(wages) if wages else 0

        # Money supply = total deposits
        money_supply = self.ledger.account_balance(f"{self.bank.id}:deposits")

        # Sector balances
        private_ids = [i.id for i in self.individuals] + [f.id for f in self.firms]
        private_balance = self.ledger.check_sector_balance(private_ids)
        govt_balance = self.ledger.actor_net_worth(self.govt.id)
        bank_balance = self.ledger.actor_net_worth(self.bank.id)

        journal_today = self.ledger.journal_size - journal_before

        return DailyStats(
            day=self.day,
            gdp=gdp,
            unemployment_rate=labor_stats["unemployment_rate"],
            total_employment=int(labor_stats["total_hired"]),
            avg_wage=avg_wage,
            govt_deficit=govt_stats["govt_deficit"],
            total_money_supply=money_supply,
            food_price=goods_stats.get("food_avg_price", 0),
            energy_price=goods_stats.get("energy_avg_price", 0),
            shelter_price=goods_stats.get("shelter_avg_price", 0),
            food_produced=food_prod,
            energy_produced=energy_prod,
            shelter_produced=shelter_prod,
            food_sold=goods_stats.get("food_quantity_sold", 0),
            energy_sold=goods_stats.get("energy_quantity_sold", 0),
            shelter_sold=goods_stats.get("shelter_quantity_sold", 0),
            gini_coefficient=compute_gini(cash_values),
            median_cash=median_cash,
            mean_cash=mean_cash,
            top1_pct_income_share=top1_share,
            bottom50_pct_income_share=bottom50_share,
            private_sector_balance=private_balance,
            govt_sector_balance=govt_balance,
            bank_sector_balance=bank_balance,
            journal_entries_today=journal_today,
            all_balanced=self.ledger.check_all_entries_balanced(),
            system_balanced=self.ledger.check_system_balance(),
        )

    def results_summary(self) -> dict:
        """Return a summary suitable for JSON serialization."""
        return {
            "config": dc.asdict(self.config),
            "num_days": self.day,
            "shock_log": self.shock_log,
            "daily_stats": [s.to_dict() for s in self.history],
            "final_journal_size": self.ledger.journal_size,
            "accounting_valid": (
                self.ledger.check_all_entries_balanced()
                and self.ledger.check_system_balance()
                and self.ledger.verify_running_balances()
            ),
        }
