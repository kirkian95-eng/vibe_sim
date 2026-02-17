"""
Scale-invariant initialization.

All start-of-simulation values are computed from RATES and RATIOS so that
results are indifferent to num_individuals (50 vs 1000 give same unemployment
rate, GDP per capita, etc.) other than rounding.
"""

from __future__ import annotations

from .config import SimConfig

REFERENCE_POPULATION = 1000

# One firm per good type. Firms don't compete strategically (no profit-maximizing logic);
# prices adjust reactively to inventory. Scaling is via demand, not firm count.
GOVT_SPENDING_PER_CAPITA = 150.0
SAVINGS_MONTHS_OF_WAGE_AT_65 = 17.0
BANK_RESERVES_PER_CAPITA = 500.0
CHILDBIRTH_FEE_MONTHS_OF_WAGE = 2.08
ELDER_HEALTHCARE_FRACTION_OF_WAGE = 0.21
NEWBORN_BOOTSTRAP_FRACTION_OF_WAGE = 0.02


def scaled_firm_counts(config: SimConfig) -> dict[str, int]:
    """One firm per good type. Demand scales with population; firm count does not."""
    return {
        "food": 1,
        "energy": 1,
        "shelter": config.num_shelter_firms,
        "healthcare": 1,
    }


def _est_demand(config: SimConfig, counts: dict[str, int]) -> dict[str, float]:
    """Estimate consumption demand by good (before individuals exist). Ages 1-72 → ~33% child."""
    n = config.num_individuals
    needs = config.consumption_needs()
    # Approx: 1/3 children, 2/3 adults+retirees
    adult_eq = n * 0.67 + n * 0.33 * config.child_food_fraction  # food-equivalent
    return {
        "food": adult_eq * needs["food"],
        "energy": n * needs["energy"],
    }


def scaled_firm_endowments(
    config: SimConfig,
    counts: dict[str, int],
    demand: dict[str, float],
) -> dict[str, dict[str, float]]:
    """
    Per-firm cash, capital, inventory. All scale with demand so ratios stay constant.

    - firm_cash: months_of_payroll * (workers_per_firm) * wage
      Use ALL firms (including healthcare) in workers_per_firm so each firm
      can afford to hire its share; otherwise goods firms exhaust the pool.
    - firm_capital: demand_per_firm * capital_per_unit (Cobb-Douglas intensity)
    - firm_inventory: demand_per_firm * target_inventory_months
    """
    n = config.num_individuals
    wage = config.initial_wage
    # Workers ≈ 64% of population (adults - owners)
    labor_force = n * 0.64
    num_goods_firms = counts["food"] + counts["energy"] + counts["shelter"]
    num_all_firms = num_goods_firms + counts["healthcare"]
    workers_per_firm = labor_force / max(1, num_all_firms)

    # Per-firm cash: enough for 2.5 months of payroll (cold start)
    months_payroll = 2.5
    firm_cash = months_payroll * workers_per_firm * wage

    result: dict[str, dict[str, float]] = {}
    for good, count in [("food", counts["food"]), ("energy", counts["energy"])]:
        if count <= 0:
            continue
        d = demand.get(good, n)
        demand_per_firm = d / count
        capital_per_unit = 0.4  # K/demand ratio for Cobb-Douglas
        result[good] = {
            "cash": firm_cash,
            "capital": demand_per_firm * capital_per_unit,
            "inventory": demand_per_firm * config.target_inventory_months,
        }

    # Healthcare firms (no inventory/capital in same way)
    result["healthcare"] = {
        "cash": firm_cash,  # same payroll buffer
        "capital": 0.0,
        "inventory": 0.0,
    }

    return result


def scaled_govt_spending(config: SimConfig) -> float:
    """Per-capita * population."""
    per_capita = config.govt_spending_per_capita if config.govt_spending_per_capita is not None else GOVT_SPENDING_PER_CAPITA
    return per_capita * config.num_individuals


def scaled_savings_at_retirement(config: SimConfig) -> float:
    """Months of wage at retirement."""
    return config.initial_wage * SAVINGS_MONTHS_OF_WAGE_AT_65


def scaled_bank_reserves(config: SimConfig) -> float:
    """Per-capita * population."""
    return BANK_RESERVES_PER_CAPITA * config.num_individuals


def scaled_healthcare_fees(config: SimConfig) -> dict[str, float]:
    """Healthcare fees as fraction of monthly wage."""
    wage = config.initial_wage
    return {
        "childbirth": wage * CHILDBIRTH_FEE_MONTHS_OF_WAGE,
        "elder_per_visit": wage * ELDER_HEALTHCARE_FRACTION_OF_WAGE,
    }


def scaled_newborn_bootstrap(config: SimConfig) -> float:
    """Small initial cash for newborns."""
    return config.initial_wage * NEWBORN_BOOTSTRAP_FRACTION_OF_WAGE


def compute_all_scaled(config: SimConfig) -> dict:
    """
    Compute all scale-invariant values for bootstrap and runtime.
    Returns dict with: firm_counts, firm_endowments, monthly_govt_spending,
    savings_at_retirement, bank_reserves, healthcare_fees, newborn_bootstrap.
    """
    counts = scaled_firm_counts(config)
    demand = _est_demand(config, counts)
    endowments = scaled_firm_endowments(config, counts, demand)
    return {
        "firm_counts": counts,
        "firm_endowments": endowments,
        "demand_estimates": demand,
        "monthly_govt_spending": scaled_govt_spending(config),
        "savings_at_retirement": scaled_savings_at_retirement(config),
        "bank_reserves": scaled_bank_reserves(config),
        "healthcare_fees": scaled_healthcare_fees(config),
        "newborn_bootstrap": scaled_newborn_bootstrap(config),
    }
