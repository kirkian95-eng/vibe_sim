"""
Metrics collection and monthly statistics.

Gathers macro, distributional, demographic, and accounting metrics
each simulation month.
"""

from __future__ import annotations

import dataclasses as dc

from .actors import Firm, GoodType, Individual, LifeStage
from .ledger import Ledger


@dc.dataclass
class MonthlyStats:
    """Snapshot of the economy for one month."""

    month: int = 0

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

    # Kalecki profits identity components
    aggregate_profits: float = 0.0
    total_wages: float = 0.0
    worker_saving: float = 0.0
    capitalist_consumption: float = 0.0
    investment: float = 0.0
    kalecki_residual: float = 0.0

    # Demographics
    population: int = 0
    num_children: int = 0
    num_adults: int = 0
    num_retirees: int = 0
    births: int = 0
    deaths: int = 0
    dependency_ratio: float = 0.0

    # Pensions
    total_pensions: float = 0.0
    pension_per_retiree: float = 0.0

    # Healthcare
    healthcare_capacity: float = 0.0
    elder_visits_needed: float = 0.0
    elder_visits_served: float = 0.0
    healthcare_shortage: float = 0.0
    healthcare_govt_spending: float = 0.0

    # Bonds
    bonds_issued: float = 0.0
    bond_rate: float = 0.0
    total_bonds_outstanding: float = 0.0
    bond_interest_paid: float = 0.0

    # Accounting
    journal_entries_this_month: int = 0
    all_balanced: bool = True
    system_balanced: bool = True

    def to_dict(self) -> dict:
        return dc.asdict(self)


# Backward compatibility alias
DailyStats = MonthlyStats


def compute_gini(values: list[float]) -> float:
    """Compute Gini coefficient from a list of values. Capped at 1.0 (negative wealth can exceed 1)."""
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
    gini = gini_sum / (n * total)
    return min(1.0, max(0.0, gini))  # cap; negative wealth can produce > 1


def collect_monthly_stats(
    month: int,
    ledger: Ledger,
    individuals: list[Individual],
    firms: list[Firm],
    bank_id: str,
    govt_id: str,
    labor_stats: dict[str, float],
    goods_stats: dict[str, float],
    govt_stats: dict[str, float],
    pension_stats: dict[str, float],
    hc_stats: dict[str, float],
    bond_stats: dict[str, float],
    birth_result: dict,
    death_result: dict,
    journal_before: int,
) -> MonthlyStats:
    """Gather all statistics for the current month."""
    alive = [ind for ind in individuals if ind.alive]

    # Cash holdings (alive only)
    cash_values = [ledger.account_balance(f"{ind.id}:cash") for ind in alive]

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

    # Production totals (non-healthcare firms only)
    food_prod = sum(f.production for f in firms if f.good_type == GoodType.FOOD)
    energy_prod = sum(f.production for f in firms if f.good_type == GoodType.ENERGY)
    shelter_prod = sum(f.production for f in firms if f.good_type == GoodType.SHELTER)

    # GDP = total revenue from goods sales
    from .actors import GOODS
    gdp = sum(goods_stats.get(f"{g.value}_revenue", 0) for g in GOODS)

    # Average wage
    wages = [f.wage_offer for f in firms]
    avg_wage = sum(wages) / len(wages) if wages else 0

    # ── Kalecki profits identity ──────────────────────────────────
    total_wages_paid = labor_stats.get("total_wages", 0.0)
    consumer_spending = gdp
    govt_purchases = govt_stats.get("govt_spending_on_firms", 0.0)
    sales_tax = goods_stats.get("total_sales_tax", 0.0)
    income_tax = govt_stats.get("total_tax_collected", 0.0)
    transfers = govt_stats.get("transfers_to_households", 0.0)
    cap_consumption = goods_stats.get("capitalist_consumption", 0.0)
    wkr_consumption = goods_stats.get("worker_consumption", 0.0)

    aggregate_profits = (consumer_spending + govt_purchases) - (total_wages_paid + sales_tax)
    worker_saving = total_wages_paid + transfers - income_tax - wkr_consumption
    full_govt_deficit = (govt_purchases + transfers) - (income_tax + sales_tax)

    investment = 0.0
    kalecki_residual = aggregate_profits - (investment + full_govt_deficit + cap_consumption - worker_saving)

    # Money supply = total deposits
    money_supply = ledger.account_balance(f"{bank_id}:deposits")

    # Sector balances
    private_balance = sum(
        ledger.actor_net_worth(i.id) for i in individuals
    ) + sum(
        ledger.actor_net_worth(f.id) for f in firms
    )
    govt_balance = ledger.actor_net_worth(govt_id)
    bank_balance = ledger.actor_net_worth(bank_id)

    # Demographics
    num_children = sum(1 for i in alive if i.life_stage == LifeStage.CHILD)
    num_adults = sum(1 for i in alive if i.life_stage == LifeStage.ADULT)
    num_retirees = sum(1 for i in alive if i.life_stage == LifeStage.RETIRED)
    population = len(alive)
    dependency_ratio = (num_children + num_retirees) / max(1, num_adults)

    # Bonds outstanding
    total_bonds = ledger.account_balance(f"{govt_id}:bonds_issued")

    journal_this_month = ledger.journal_size - journal_before

    return MonthlyStats(
        month=month,
        gdp=gdp,
        unemployment_rate=labor_stats["unemployment_rate"],
        total_employment=int(labor_stats["total_hired"]),
        avg_wage=avg_wage,
        govt_deficit=full_govt_deficit,
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
        aggregate_profits=aggregate_profits,
        total_wages=total_wages_paid,
        worker_saving=worker_saving,
        capitalist_consumption=cap_consumption,
        investment=investment,
        kalecki_residual=kalecki_residual,
        population=population,
        num_children=num_children,
        num_adults=num_adults,
        num_retirees=num_retirees,
        births=int(birth_result.get("births", 0)),
        deaths=int(death_result.get("deaths", 0)),
        dependency_ratio=dependency_ratio,
        total_pensions=pension_stats.get("total_pensions", 0.0),
        pension_per_retiree=pension_stats.get("pension_per_retiree", 0.0),
        healthcare_capacity=hc_stats.get("healthcare_capacity", 0.0),
        elder_visits_needed=hc_stats.get("elder_visits_needed", 0.0),
        elder_visits_served=hc_stats.get("elder_visits_served", 0.0),
        healthcare_shortage=hc_stats.get("healthcare_shortage", 0.0),
        healthcare_govt_spending=hc_stats.get("healthcare_govt_spending", 0.0),
        bonds_issued=bond_stats.get("bonds_issued", 0.0),
        bond_rate=bond_stats.get("bond_rate", 0.0),
        total_bonds_outstanding=total_bonds,
        bond_interest_paid=bond_stats.get("total_interest_paid", 0.0),
        journal_entries_this_month=journal_this_month,
        all_balanced=ledger.check_entries_balanced_from(journal_before),
        system_balanced=True,  # deferred to results_summary for perf
    )


# Backward compatibility alias
collect_daily_stats = collect_monthly_stats
