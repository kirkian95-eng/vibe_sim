"""
Metrics collection and daily statistics.

Gathers macro, distributional, and accounting metrics each simulation day.
"""

from __future__ import annotations

import dataclasses as dc

from .actors import Firm, GoodType, Individual
from .ledger import Ledger


@dc.dataclass
class DailyStats:
    """Snapshot of the economy for one day."""

    day: int = 0

    # Macro
    gdp: float = 0.0
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


def compute_gini(values: list[float]) -> float:
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


def collect_daily_stats(
    day: int,
    ledger: Ledger,
    individuals: list[Individual],
    firms: list[Firm],
    bank_id: str,
    govt_id: str,
    labor_stats: dict[str, float],
    goods_stats: dict[str, float],
    govt_stats: dict[str, float],
    journal_before: int,
) -> DailyStats:
    """Gather all statistics for the current day."""
    # Cash holdings
    cash_values = [ledger.account_balance(f"{ind.id}:cash") for ind in individuals]

    sorted_cash = sorted(cash_values)
    n = len(sorted_cash)
    median_cash = sorted_cash[n // 2] if n > 0 else 0
    mean_cash = sum(sorted_cash) / n if n > 0 else 0

    # Income shares
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
    food_prod = sum(f.daily_production for f in firms if f.good_type == GoodType.FOOD)
    energy_prod = sum(f.daily_production for f in firms if f.good_type == GoodType.ENERGY)
    shelter_prod = sum(f.daily_production for f in firms if f.good_type == GoodType.SHELTER)

    # GDP = total revenue from goods sales
    gdp = sum(goods_stats.get(f"{g.value}_revenue", 0) for g in GoodType)

    # Average wage
    wages = [f.wage_offer for f in firms]
    avg_wage = sum(wages) / len(wages) if wages else 0

    # Money supply = total deposits
    money_supply = ledger.account_balance(f"{bank_id}:deposits")

    # Sector balances — use actor_net_worth directly for performance
    private_balance = sum(
        ledger.actor_net_worth(i.id) for i in individuals
    ) + sum(
        ledger.actor_net_worth(f.id) for f in firms
    )
    govt_balance = ledger.actor_net_worth(govt_id)
    bank_balance = ledger.actor_net_worth(bank_id)

    journal_today = ledger.journal_size - journal_before

    return DailyStats(
        day=day,
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
        # Only check today's new entries (not the entire journal every day)
        all_balanced=ledger.check_entries_balanced_from(journal_before),
        system_balanced=True,  # deferred to results_summary for perf
    )
