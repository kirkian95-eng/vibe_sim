"""
Simulation configuration — all tuneable parameters in one place.

A SimConfig is a frozen snapshot; shocks produce a new config for
the affected day range.
"""

from __future__ import annotations

import dataclasses as dc
from typing import Dict


@dc.dataclass
class SimConfig:
    """All parameters that define a simulation run."""

    # ── General ─────────────────────────────────────────────────────
    seed: int = 42
    num_days: int = 365
    name: str = "baseline"

    # ── Population ──────────────────────────────────────────────────
    num_individuals: int = 1000
    owner_fraction: float = 0.01  # top 1% own firms

    # ── Firms ───────────────────────────────────────────────────────
    num_food_firms: int = 4
    num_energy_firms: int = 3
    num_shelter_firms: int = 3

    # ── Production (Cobb-Douglas-ish) ───────────────────────────────
    # output = productivity * labor^labor_share * capital^capital_share
    food_productivity: float = 2.0
    energy_productivity: float = 1.5
    shelter_productivity: float = 0.8
    labor_share: float = 0.7
    capital_share: float = 0.3

    # ── Initial endowments ──────────────────────────────────────────
    initial_firm_cash: float = 50_000.0
    initial_firm_capital: float = 100.0
    initial_firm_inventory: float = 500.0
    initial_individual_cash: float = 500.0
    initial_bank_reserves: float = 500_000.0

    # ── Consumption (units per person per day) ──────────────────────
    food_need: float = 1.0
    energy_need: float = 0.5
    shelter_need: float = 0.033  # ~1 unit per month

    # ── Prices (initial) ────────────────────────────────────────────
    initial_food_price: float = 5.0
    initial_energy_price: float = 8.0
    initial_shelter_price: float = 30.0

    # ── Wages ───────────────────────────────────────────────────────
    initial_wage: float = 80.0  # per day
    min_wage: float = 20.0
    wage_adjustment_speed: float = 0.02  # fraction per day

    # ── Price adjustment ────────────────────────────────────────────
    price_adjustment_speed: float = 0.03
    target_inventory_days: float = 10.0  # days of sales to keep

    # ── Government / fiscal ─────────────────────────────────────────
    income_tax_rate: float = 0.20
    sales_tax_rate: float = 0.05
    daily_govt_transfer: float = 10.0  # per unemployed person
    daily_govt_spending: float = 5000.0  # public goods spending

    # ── Banking ─────────────────────────────────────────────────────
    interest_rate: float = 0.05  # annual
    reserve_requirement: float = 0.10

    # ── Firm profit distribution ────────────────────────────────────
    profit_distribution_rate: float = 0.50  # fraction of profits distributed

    @property
    def num_firms(self) -> int:
        return self.num_food_firms + self.num_energy_firms + self.num_shelter_firms

    @property
    def num_owners(self) -> int:
        return max(1, int(self.num_individuals * self.owner_fraction))

    @property
    def daily_interest_rate(self) -> float:
        return self.interest_rate / 365.0

    def initial_prices(self) -> Dict[str, float]:
        return {
            "food": self.initial_food_price,
            "energy": self.initial_energy_price,
            "shelter": self.initial_shelter_price,
        }

    def productivity(self) -> Dict[str, float]:
        return {
            "food": self.food_productivity,
            "energy": self.energy_productivity,
            "shelter": self.shelter_productivity,
        }

    def consumption_needs(self) -> Dict[str, float]:
        return {
            "food": self.food_need,
            "energy": self.energy_need,
            "shelter": self.shelter_need,
        }
