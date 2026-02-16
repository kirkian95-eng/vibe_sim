"""
Simulation configuration -- all tuneable parameters in one place.

A SimConfig is a frozen snapshot; shocks produce a new config for
the affected period range.  Configs can be loaded from YAML via
``engine.io.load_config_yaml``.

All quantities are monthly unless stated otherwise.
"""

from __future__ import annotations

import dataclasses as dc


MONTHS_PER_YEAR: int = 12


@dc.dataclass
class SimConfig:
    """All parameters that define a simulation run."""

    # ── General ─────────────────────────────────────────────────────
    seed: int = 42
    num_months: int = 120  # 10 years
    name: str = "baseline"

    # ── Population ──────────────────────────────────────────────────
    num_individuals: int = 1000
    owner_fraction: float = 0.01  # top 1% own firms

    # ── Firms ───────────────────────────────────────────────────────
    num_food_firms: int = 4
    num_energy_firms: int = 3
    num_shelter_firms: int = 3
    num_healthcare_firms: int = 2

    # ── Production (Cobb-Douglas) ─────────────────────────────────
    food_productivity: float = 2.0
    energy_productivity: float = 1.5
    shelter_productivity: float = 0.8
    healthcare_productivity: float = 5.0  # visits per worker per month
    labor_share: float = 0.7
    capital_share: float = 0.3

    # ── Initial endowments ──────────────────────────────────────────
    initial_firm_cash: float = 50_000.0
    initial_firm_capital: float = 100.0
    initial_firm_inventory: float = 50.0
    initial_individual_cash: float = 500.0
    initial_bank_reserves: float = 500_000.0

    # ── Consumption (units per adult per month) ─────────────────────
    food_need: float = 1.0
    energy_need: float = 1.0
    shelter_need: float = 1.0
    child_food_fraction: float = 0.5  # children consume 50% of adult food

    # ── Prices (initial, per unit) ──────────────────────────────────
    initial_food_price: float = 150.0
    initial_energy_price: float = 120.0
    initial_shelter_price: float = 600.0

    # ── Wages (monthly) ─────────────────────────────────────────────
    initial_wage: float = 2400.0
    min_wage: float = 600.0
    wage_adjustment_speed: float = 0.06  # fraction per month

    # ── Price adjustment ────────────────────────────────────────────
    price_adjustment_speed: float = 0.10  # fraction per month
    target_inventory_months: float = 2.0  # months of sales to keep

    # ── Government / fiscal ─────────────────────────────────────────
    income_tax_rate: float = 0.20
    sales_tax_rate: float = 0.05
    monthly_govt_transfer: float = 300.0  # per unemployed person per month
    monthly_govt_spending: float = 150_000.0  # public goods spending per month

    # ── Banking ─────────────────────────────────────────────────────
    interest_rate: float = 0.05  # annual
    reserve_requirement: float = 0.10

    # ── Firm profit distribution ────────────────────────────────────
    profit_distribution_rate: float = 0.50

    # ── Demographics ────────────────────────────────────────────────
    retirement_age: int = 65  # years
    mortality_start_age: int = 72  # years
    target_death_age: int = 80  # average death age
    fertility_rate_annual: float = 0.01  # ~1% annual growth target

    # ── Pensions ────────────────────────────────────────────────────
    pension_replacement_rate: float = 0.50  # fraction of trailing avg wage

    # ── Healthcare ──────────────────────────────────────────────────
    childbirth_healthcare_fee: float = 5000.0
    elder_healthcare_monthly_cost: float = 500.0

    # ── Bonds ───────────────────────────────────────────────────────
    bond_duration_months: int = 120  # 10 year maturity
    bond_rate_min: float = 0.005  # annual floor
    bond_rate_max: float = 0.15  # annual ceiling
    bond_demand_sensitivity: float = 5.0
    bond_savings_fraction: float = 0.3  # max share of savings bid for bonds

    @property
    def num_firms(self) -> int:
        return (
            self.num_food_firms
            + self.num_energy_firms
            + self.num_shelter_firms
            + self.num_healthcare_firms
        )

    @property
    def num_owners(self) -> int:
        return max(1, int(self.num_individuals * self.owner_fraction))

    @property
    def monthly_interest_rate(self) -> float:
        return self.interest_rate / MONTHS_PER_YEAR

    @property
    def monthly_mortality_hazard(self) -> float:
        """Constant hazard so E[remaining life | age>=72] ≈ 8 years (96 months).

        Geometric distribution: E[X] = 1/λ  →  λ = 1/96 ≈ 0.0104.
        """
        remaining = (self.target_death_age - self.mortality_start_age) * MONTHS_PER_YEAR
        if remaining <= 0:
            return 1.0
        return 1.0 / remaining

    @property
    def monthly_fertility_hazard(self) -> float:
        """Per-eligible-couple monthly birth probability.

        Calibrated so realised births ≈ fertility_rate_annual × population / year
        when all adults are fed and sheltered.
        """
        if self.fertility_rate_annual <= 0:
            return 0.0
        return self.fertility_rate_annual / 3.9

    def initial_prices(self) -> dict[str, float]:
        return {
            "food": self.initial_food_price,
            "energy": self.initial_energy_price,
            "shelter": self.initial_shelter_price,
        }

    def productivity(self) -> dict[str, float]:
        return {
            "food": self.food_productivity,
            "energy": self.energy_productivity,
            "shelter": self.shelter_productivity,
        }

    def consumption_needs(self) -> dict[str, float]:
        return {
            "food": self.food_need,
            "energy": self.energy_need,
            "shelter": self.shelter_need,
        }
