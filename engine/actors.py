"""
Actor types and their account structures.

Each actor (Individual, Firm, Bank, Government) is initialized with the
correct set of ledger accounts so that the simulation can post journal
entries against them.
"""

from __future__ import annotations

import dataclasses as dc
from enum import Enum
from typing import Dict, List, Optional

from .ledger import AccountType, Ledger


class ActorType(Enum):
    INDIVIDUAL = "individual"
    FIRM = "firm"
    BANK = "bank"
    GOVERNMENT = "government"  # consolidated CB + Treasury


class GoodType(Enum):
    FOOD = "food"
    ENERGY = "energy"
    SHELTER = "shelter"


GOODS = [GoodType.FOOD, GoodType.ENERGY, GoodType.SHELTER]


@dc.dataclass
class Actor:
    """Base actor with a ledger reference."""

    id: str
    actor_type: ActorType

    def acct(self, name: str) -> str:
        """Shorthand for fully-qualified account id."""
        return f"{self.id}:{name}"


@dc.dataclass
class Individual(Actor):
    """A person who works, consumes, and may own firms."""

    employed: bool = False
    employer_id: Optional[str] = None
    is_owner: bool = False
    owned_firm_id: Optional[str] = None

    @staticmethod
    def create(ledger: Ledger, idx: int, is_owner: bool = False) -> Individual:
        actor_id = f"ind_{idx:04d}"
        ind = Individual(
            id=actor_id,
            actor_type=ActorType.INDIVIDUAL,
            is_owner=is_owner,
        )
        # Balance-sheet accounts
        ledger.create_account(actor_id, "cash", AccountType.ASSET)
        for g in GOODS:
            ledger.create_account(actor_id, f"inventory:{g.value}", AccountType.ASSET)
        ledger.create_account(actor_id, "loans_payable", AccountType.LIABILITY)
        ledger.create_account(actor_id, "equity", AccountType.EQUITY)
        # Income-statement accounts
        ledger.create_account(actor_id, "labor_income", AccountType.REVENUE)
        ledger.create_account(actor_id, "transfer_income", AccountType.REVENUE)
        ledger.create_account(actor_id, "profit_income", AccountType.REVENUE)
        ledger.create_account(actor_id, "consumption_expense", AccountType.EXPENSE)
        ledger.create_account(actor_id, "tax_expense", AccountType.EXPENSE)
        return ind


@dc.dataclass
class Firm(Actor):
    """A firm that produces one type of good."""

    good_type: GoodType = GoodType.FOOD
    owner_id: Optional[str] = None
    num_workers: int = 0
    wage_offer: float = 80.0
    price: float = 5.0
    daily_production: float = 0.0
    daily_sales: float = 0.0
    daily_revenue: float = 0.0

    @staticmethod
    def create(
        ledger: Ledger,
        idx: int,
        good_type: GoodType,
        initial_price: float,
        initial_wage: float,
    ) -> Firm:
        actor_id = f"firm_{good_type.value}_{idx:02d}"
        firm = Firm(
            id=actor_id,
            actor_type=ActorType.FIRM,
            good_type=good_type,
            price=initial_price,
            wage_offer=initial_wage,
        )
        # Balance-sheet accounts
        ledger.create_account(actor_id, "cash", AccountType.ASSET)
        ledger.create_account(actor_id, "inventory", AccountType.ASSET)
        ledger.create_account(actor_id, "capital", AccountType.ASSET)
        ledger.create_account(actor_id, "loans_payable", AccountType.LIABILITY)
        ledger.create_account(actor_id, "equity", AccountType.EQUITY)
        # Income-statement accounts
        ledger.create_account(actor_id, "revenue", AccountType.REVENUE)
        ledger.create_account(actor_id, "wage_expense", AccountType.EXPENSE)
        ledger.create_account(actor_id, "input_expense", AccountType.EXPENSE)
        ledger.create_account(actor_id, "tax_expense", AccountType.EXPENSE)
        return firm


@dc.dataclass
class Bank(Actor):
    """A commercial bank — intermediates between sectors."""

    @staticmethod
    def create(ledger: Ledger, idx: int = 0) -> Bank:
        actor_id = f"bank_{idx:02d}"
        bank = Bank(id=actor_id, actor_type=ActorType.BANK)
        # Assets
        ledger.create_account(actor_id, "reserves", AccountType.ASSET)
        ledger.create_account(actor_id, "loans_receivable", AccountType.ASSET)
        ledger.create_account(actor_id, "bonds", AccountType.ASSET)
        # Liabilities
        ledger.create_account(actor_id, "deposits", AccountType.LIABILITY)
        # Equity
        ledger.create_account(actor_id, "equity", AccountType.EQUITY)
        # Income statement
        ledger.create_account(actor_id, "interest_income", AccountType.REVENUE)
        ledger.create_account(actor_id, "interest_expense", AccountType.EXPENSE)
        return bank


@dc.dataclass
class Government(Actor):
    """
    Consolidated government = Treasury + Central Bank.

    Government spending creates money (credits bank reserves / deposits).
    Taxation destroys money (debits deposits / reserves).
    """

    @staticmethod
    def create(ledger: Ledger) -> Government:
        actor_id = "govt"
        govt = Government(id=actor_id, actor_type=ActorType.GOVERNMENT)
        # Assets
        ledger.create_account(actor_id, "tax_receivable", AccountType.ASSET)
        # Liabilities (money is a govt liability)
        ledger.create_account(actor_id, "currency_issued", AccountType.LIABILITY)
        ledger.create_account(actor_id, "bonds_issued", AccountType.LIABILITY)
        # Equity
        ledger.create_account(actor_id, "equity", AccountType.EQUITY)
        # Income statement
        ledger.create_account(actor_id, "tax_revenue", AccountType.REVENUE)
        ledger.create_account(actor_id, "spending_expense", AccountType.EXPENSE)
        ledger.create_account(actor_id, "transfer_expense", AccountType.EXPENSE)
        ledger.create_account(actor_id, "interest_expense", AccountType.EXPENSE)
        return govt


def create_all_actors(
    ledger: Ledger,
    num_individuals: int,
    num_food_firms: int,
    num_energy_firms: int,
    num_shelter_firms: int,
    num_owners: int,
    initial_prices: Dict[str, float],
    initial_wage: float,
) -> dict:
    """
    Instantiate all actors and register their accounts on the ledger.
    Returns a dict with keys: individuals, firms, bank, government.
    """
    # Government (singleton)
    govt = Government.create(ledger)

    # Bank (singleton for now)
    bank = Bank.create(ledger)

    # Firms
    firms: List[Firm] = []
    firm_idx = 0
    for good, count in [
        (GoodType.FOOD, num_food_firms),
        (GoodType.ENERGY, num_energy_firms),
        (GoodType.SHELTER, num_shelter_firms),
    ]:
        for _ in range(count):
            f = Firm.create(
                ledger, firm_idx, good, initial_prices[good.value], initial_wage
            )
            firms.append(f)
            firm_idx += 1

    # Individuals
    individuals: List[Individual] = []
    for i in range(num_individuals):
        is_owner = i < num_owners
        ind = Individual.create(ledger, i, is_owner=is_owner)
        if is_owner and i < len(firms):
            ind.owned_firm_id = firms[i].id
            firms[i].owner_id = ind.id
        individuals.append(ind)

    return {
        "individuals": individuals,
        "firms": firms,
        "bank": bank,
        "government": govt,
    }
