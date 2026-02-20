"""
Main simulation loop.

Orchestrates the monthly cycle:
  1. Apply any shocks scheduled for this month
  2. Advance ages / life-stage transitions
  3. Births
  4. Deaths (mortality, estate settlement)
  5. Government operations (spending + tax collection)
  6. Pension payments
  6.5 Housing development (construction pipeline)
  7. Labor market clearing (hiring + wage payment)
  8. Production
  9. Healthcare operations (elder visits)
 10. Goods market clearing (purchases)
 11. Consumption
 12. Firm profit distribution
 13. Bond market clearing
 14. Bond interest payments
 15. Price & wage adjustment
 16. Record monthly statistics
"""

from __future__ import annotations

import dataclasses as dc
import math
import random
import time
from collections.abc import Callable

from .actors import (
    Bank,
    Firm,
    GoodType,
    Government,
    Individual,
    create_all_actors,
)
from .bonds import clear_bond_market, pay_bond_interest
from .config import SimConfig
from .demographics import advance_ages, run_births, run_deaths
from .ledger import Ledger
from .markets import (
    adjust_prices_and_wages,
    clear_goods_market,
    clear_labor_market,
    consume_goods,
    run_housing_development,
    run_production,
)
from .metrics import MonthlyStats, collect_monthly_stats
from .policy import (
    firm_investment,
    firm_profit_distribution,
    government_operations,
    healthcare_operations,
    pension_operations,
    post_government_spending,
    repay_firm_loans,
)
from .scaling import compute_all_scaled
from .shocks import Shock


def _initial_cash_for_age(age_months: int, target_at_65: float) -> float:
    """
    Age-proportional initial savings: ~$1 at 18, logarithmic growth to target at 65.

    Retirees need prior savings; otherwise they start with $0 and run out of money.
    years_since_18 = max(0, (age_months - 216) / 12)
    amount = 1 + (target_at_65 - 1) * ln(1 + years_since_18) / ln(48)
    """
    if age_months < 216:  # Under 18
        return 1.0
    years_since_18 = (age_months - 216) / 12.0
    # ln(48) ≈ 3.87 is the value at 65 (47 years of accumulation)
    scale = (target_at_65 - 1.0) / math.log(48)
    return 1.0 + scale * math.log(1.0 + years_since_18)


class Simulation:
    """
    The main simulation engine.

    Usage:
        sim = Simulation(config, shocks=[...])
        results = sim.run()
    """

    def __init__(self, config: SimConfig, shocks: list[Shock] | None = None):
        # Scale-invariant: compute all population-scaled values
        scaled = compute_all_scaled(config)
        self.config = dc.replace(
            config,
            num_food_firms=scaled["firm_counts"]["food"],
            num_energy_firms=scaled["firm_counts"]["energy"],
            num_healthcare_firms=scaled["firm_counts"]["healthcare"],
            monthly_govt_spending=scaled["monthly_govt_spending"],
            initial_savings_at_retirement=scaled["savings_at_retirement"],
            childbirth_healthcare_fee=scaled["healthcare_fees"]["childbirth"],
            elder_healthcare_monthly_cost=scaled["healthcare_fees"]["elder_per_visit"],
            initial_individual_cash=scaled["newborn_bootstrap"] / 0.1,
        )
        self._scaled = scaled
        self.shocks = sorted(shocks or [], key=lambda s: s.month)
        self.rng = random.Random(config.seed)
        self.ledger = Ledger()
        self.month = 0
        self.history: list[MonthlyStats] = []
        self.shock_log: list[str] = []
        self._profiling: dict[str, float] = {}
        self._profile_hooks: list[Callable[[str, float], None]] = []
        self._next_individual_idx: int = 0
        self._bond_rate: float = config.bond_rate_min

        # Create actors (using scaled firm counts from self.config)
        cfg = self.config
        actors = create_all_actors(
            self.ledger,
            num_individuals=cfg.num_individuals,
            num_food_firms=cfg.num_food_firms,
            num_energy_firms=cfg.num_energy_firms,
            num_shelter_firms=cfg.num_shelter_firms,
            num_owners=cfg.num_owners,
            initial_prices=cfg.initial_prices(),
            initial_wage=cfg.initial_wage,
            num_healthcare_firms=cfg.num_healthcare_firms,
            rng=self.rng,
        )
        self.individuals: list[Individual] = actors["individuals"]
        self.firms: list[Firm] = actors["firms"]
        self.bank: Bank = actors["bank"]
        self.govt: Government = actors["government"]
        self._next_individual_idx = len(self.individuals)

        # Initialize the economy
        self._bootstrap()

    def _bootstrap(self) -> None:
        """
        Inject initial money into the economy via government spending.
        Money can only exist if the government spends it into existence.

        Individuals receive age-proportional initial savings: ~$1 at age 18,
        growing logarithmically to initial_savings_at_retirement at age 65.
        This funds retirees who would otherwise start with $0 and run out of money.

        All endowments are scale-invariant (from scaling.compute_all_scaled).
        """
        cfg = self.config
        endowments = self._scaled["firm_endowments"]

        # Government spending creates initial money for individuals (age-proportional)
        for ind in self.individuals:
            if ind.alive:
                amount = _initial_cash_for_age(
                    ind.age_months,
                    cfg.initial_savings_at_retirement,
                )
                post_government_spending(
                    self.ledger, 0, self.govt, self.bank, ind.id,
                    amount,
                    f"Bootstrap: initial cash for {ind.id}",
                )

        # Government spending creates initial money for firms (per-good scaled endowments)
        for firm in self.firms:
            e = endowments.get(firm.good_type.value, endowments.get("healthcare"))
            cash = e["cash"]
            post_government_spending(
                self.ledger, 0, self.govt, self.bank, firm.id,
                cash,
                f"Bootstrap: initial cash for {firm.id}",
            )
            # Initial capital endowment (equity injection) - goods firms only
            if not firm.is_healthcare and e["capital"] > 0:
                self.ledger.post(0, f"Bootstrap: capital for {firm.id}", [
                    (f"{firm.id}:capital", e["capital"], 0),
                    (f"{firm.id}:equity", 0, e["capital"]),
                ])
            # Initial inventory - goods firms only
            if not firm.is_healthcare and e["inventory"] > 0:
                self.ledger.post(0, f"Bootstrap: inventory for {firm.id}", [
                    (f"{firm.id}:inventory", e["inventory"], 0),
                    (f"{firm.id}:equity", 0, e["inventory"]),
                ])
            # Initial housing stock - shelter firms only
            if firm.good_type == GoodType.SHELTER:
                housing = e.get("housing_units", 0.0)
                if housing > 0:
                    firm.housing_units = housing
                    self.ledger.post(0, f"Bootstrap: housing for {firm.id}", [
                        (f"{firm.id}:housing_asset", housing, 0),
                        (f"{firm.id}:equity", 0, housing),
                    ])

        # Warm-start the sales EMA so firms estimate demand correctly from month 1.
        # Without this, firm.sales starts at 0 and the EMA only reaches 30% of actual
        # sales after the first month, causing firms to slash production and hiring.
        demand_est = self._scaled.get("demand_estimates", {})
        firm_counts = self._scaled["firm_counts"]
        for firm in self.firms:
            if firm.is_healthcare:
                continue
            good = firm.good_type.value
            count = firm_counts.get(good, 1)
            d = demand_est.get(good, 0)
            if d > 0 and count > 0:
                firm.sales = d / count
                firm.revenue_ema = firm.sales * firm.price

    def add_profile_hook(self, hook: Callable[[str, float], None]) -> None:
        """Register a callback invoked with (phase_name, elapsed_seconds) each step."""
        self._profile_hooks.append(hook)

    def _profile(self, name: str, elapsed: float) -> None:
        self._profiling[name] = self._profiling.get(name, 0.0) + elapsed
        for hook in self._profile_hooks:
            hook(name, elapsed)

    def step(self) -> MonthlyStats:
        """Advance the simulation by one month."""
        self.month += 1
        cfg = self.config

        # 1. Apply shocks
        for shock in self.shocks:
            if shock.month == self.month:
                cfg = shock.apply(cfg)
                self.config = cfg
                self.shock_log.append(f"Month {self.month}: {shock.description}")

        journal_before = self.ledger.journal_size

        # 2. Advance ages / life-stage transitions
        t0 = time.perf_counter()
        advance_ages(self.individuals, cfg)
        self._profile("demographics_aging", time.perf_counter() - t0)

        # 3. Births
        t0 = time.perf_counter()
        birth_result = run_births(
            self.ledger, self.month, cfg, self.individuals,
            self.firms, self.bank, self.govt, self.rng,
            next_individual_idx=self._next_individual_idx,
        )
        new_borns: list[Individual] = birth_result["new_individuals"]  # type: ignore[assignment]
        if new_borns:
            self.individuals.extend(new_borns)
            self._next_individual_idx += len(new_borns)
        self._profile("demographics_births", time.perf_counter() - t0)

        # 4. Deaths
        t0 = time.perf_counter()
        death_result = run_deaths(
            self.ledger, self.month, cfg, self.individuals,
            self.govt, self.bank, self.rng,
        )
        self._profile("demographics_deaths", time.perf_counter() - t0)

        # 5. Government operations (spending + tax collection)
        t0 = time.perf_counter()
        avg_wage = sum(f.wage_offer for f in self.firms) / max(1, len(self.firms))
        govt_stats = government_operations(
            self.ledger, self.month, cfg, self.govt, self.bank,
            self.individuals, self.firms, avg_wage,
        )
        self._profile("government", time.perf_counter() - t0)

        # 6. Pension payments
        t0 = time.perf_counter()
        pension_stats = pension_operations(
            self.ledger, self.month, cfg, self.govt, self.bank,
            self.individuals, avg_wage,
        )
        self._profile("pensions", time.perf_counter() - t0)

        # 6.5 Housing development (construction pipeline)
        t0 = time.perf_counter()
        housing_stats = run_housing_development(
            self.ledger, self.month, cfg, self.firms,
        )
        self._profile("housing_development", time.perf_counter() - t0)

        # 7. Labor market
        t0 = time.perf_counter()
        labor_stats = clear_labor_market(
            self.ledger, self.month, cfg, self.firms,
            self.individuals, self.bank, self.rng,
        )
        self._profile("labor_market", time.perf_counter() - t0)

        # 8. Production
        t0 = time.perf_counter()
        run_production(self.ledger, self.month, cfg, self.firms)
        self._profile("production", time.perf_counter() - t0)

        # 9. Healthcare operations
        t0 = time.perf_counter()
        healthcare_firms = [f for f in self.firms if f.is_healthcare]
        hc_stats = healthcare_operations(
            self.ledger, self.month, cfg, self.govt, self.bank,
            self.individuals, healthcare_firms,
        )
        self._profile("healthcare", time.perf_counter() - t0)

        # 10. Goods market
        t0 = time.perf_counter()
        goods_stats = clear_goods_market(
            self.ledger, self.month, cfg, self.firms,
            self.individuals, self.bank, self.govt, self.rng,
        )
        self._profile("goods_market", time.perf_counter() - t0)

        # 11. Consumption
        t0 = time.perf_counter()
        consume_goods(self.ledger, self.month, self.individuals, cfg)
        self._profile("consumption", time.perf_counter() - t0)

        # 12. Firm investment, then loan repayment, then profit distribution
        # Investment first: firms allocate cash to capital before repaying loans.
        t0 = time.perf_counter()
        investment_total = firm_investment(
            self.ledger, self.month, cfg, self.firms,
        )
        repay_firm_loans(self.ledger, self.month, self.firms, self.bank)
        firm_profit_distribution(
            self.ledger, self.month, cfg, self.firms,
            self.individuals, self.bank,
        )
        self._profile("profit_dist", time.perf_counter() - t0)

        # 13. Bond market clearing
        t0 = time.perf_counter()
        deficit_for_bonds = govt_stats.get("govt_deficit", 0.0) + pension_stats.get("total_pensions", 0.0) + hc_stats.get("healthcare_govt_spending", 0.0)
        bond_stats = clear_bond_market(
            self.ledger, self.month, cfg, self.govt, self.bank,
            self.individuals, deficit_for_bonds,
        )
        self._bond_rate = bond_stats.get("bond_rate", self._bond_rate)
        self._profile("bonds", time.perf_counter() - t0)

        # 14. Bond interest payments
        t0 = time.perf_counter()
        bond_interest = pay_bond_interest(
            self.ledger, self.month, cfg, self.govt, self.bank,
            self.individuals, self._bond_rate,
        )
        bond_stats["total_interest_paid"] = bond_interest
        self._profile("bond_interest", time.perf_counter() - t0)

        # 15. Price and wage adjustments
        adjust_prices_and_wages(
            cfg, self.firms, labor_stats["unemployment_rate"], ledger=self.ledger,
        )

        # 16. Collect statistics
        t0 = time.perf_counter()
        stats = collect_monthly_stats(
            self.month,
            self.ledger,
            self.individuals,
            self.firms,
            self.bank.id,
            self.govt.id,
            labor_stats,
            goods_stats,
            govt_stats,
            pension_stats,
            hc_stats,
            bond_stats,
            birth_result,
            death_result,
            journal_before,
            housing_stats,
            investment_total=investment_total,
        )
        self._profile("metrics", time.perf_counter() - t0)

        self.history.append(stats)
        return stats

    def run(self) -> list[MonthlyStats]:
        """Run the full simulation."""
        t_start = time.perf_counter()
        for _ in range(self.config.num_months):
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
            "num_months": self.month,
            "seed": self.config.seed,
            "shock_log": self.shock_log,
            "monthly_stats": [s.to_dict() for s in self.history],
            "final_journal_size": self.ledger.journal_size,
            "accounting_valid": (
                self.ledger.check_all_entries_balanced()
                and self.ledger.check_system_balance()
                and self.ledger.verify_running_balances()
            ),
            "profiling": self.profiling,
        }
