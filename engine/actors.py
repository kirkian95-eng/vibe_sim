"""
Actor types and their account structures.

Each actor (Individual, Firm, Bank, Government) is initialized with the
correct set of ledger accounts so that the simulation can post journal
entries against them.
"""

from __future__ import annotations

import dataclasses as dc
from enum import Enum
from random import Random

from .ledger import AccountType, Ledger


class ActorType(Enum):
    INDIVIDUAL = "individual"
    FIRM = "firm"
    BANK = "bank"
    GOVERNMENT = "government"  # consolidated CB + Treasury


class LifeStage(Enum):
    CHILD = "child"
    ADULT = "adult"
    RETIRED = "retired"


class GoodType(Enum):
    FOOD = "food"
    ENERGY = "energy"
    SHELTER = "shelter"
    HEALTHCARE = "healthcare"


# Goods traded on the regular goods market (healthcare is separate).
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
    employer_id: str | None = None
    is_owner: bool = False
    owned_firm_id: str | None = None

    # Demographics (v0.2)
    age_months: int = 0
    life_stage: LifeStage = LifeStage.ADULT
    alive: bool = True
    parent_ids: list[str] = dc.field(default_factory=list)
    children_ids: list[str] = dc.field(default_factory=list)
    fertility_cooldown_months: int = 0
    reduced_labor_months_remaining: int = 0

    @staticmethod
    def create(
        ledger: Ledger,
        idx: int,
        is_owner: bool = False,
        age_months: int = 360,
        life_stage: LifeStage | None = None,
    ) -> Individual:
        actor_id = f"ind_{idx:04d}"

        # Infer life stage from age if not explicitly given.
        if life_stage is None:
            if age_months < 216:  # < 18 years
                life_stage = LifeStage.CHILD
            elif age_months < 780:  # < 65 years
                life_stage = LifeStage.ADULT
            else:
                life_stage = LifeStage.RETIRED

        ind = Individual(
            id=actor_id,
            actor_type=ActorType.INDIVIDUAL,
            is_owner=is_owner,
            age_months=age_months,
            life_stage=life_stage,
        )

        # Balance-sheet accounts
        ledger.create_account(actor_id, "cash", AccountType.ASSET)
        for g in GOODS:
            ledger.create_account(actor_id, f"inventory:{g.value}", AccountType.ASSET)
        ledger.create_account(actor_id, "bond_asset", AccountType.ASSET)
        ledger.create_account(actor_id, "loans_payable", AccountType.LIABILITY)
        ledger.create_account(actor_id, "equity", AccountType.EQUITY)

        # Income-statement accounts
        ledger.create_account(actor_id, "labor_income", AccountType.REVENUE)
        ledger.create_account(actor_id, "transfer_income", AccountType.REVENUE)
        ledger.create_account(actor_id, "profit_income", AccountType.REVENUE)
        ledger.create_account(actor_id, "pension_income", AccountType.REVENUE)
        ledger.create_account(actor_id, "consumption_expense", AccountType.EXPENSE)
        ledger.create_account(actor_id, "tax_expense", AccountType.EXPENSE)
        return ind


@dc.dataclass
class Firm(Actor):
    """A firm that produces one type of good."""

    good_type: GoodType = GoodType.FOOD
    owner_id: str | None = None
    num_workers: int = 0
    wage_offer: float = 80.0
    price: float = 5.0
    production: float = 0.0
    sales: float = 0.0
    revenue_ema: float = 0.0

    @property
    def is_healthcare(self) -> bool:
        """True if this firm produces healthcare services."""
        return self.good_type == GoodType.HEALTHCARE

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
    """A commercial bank -- intermediates between sectors."""

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
        ledger.create_account(actor_id, "shelter_revenue", AccountType.REVENUE)
        ledger.create_account(actor_id, "spending_expense", AccountType.EXPENSE)
        ledger.create_account(actor_id, "transfer_expense", AccountType.EXPENSE)
        ledger.create_account(actor_id, "interest_expense", AccountType.EXPENSE)
        ledger.create_account(actor_id, "pension_expense", AccountType.EXPENSE)
        ledger.create_account(actor_id, "healthcare_expense", AccountType.EXPENSE)
        return govt


def _life_stage_for_age(age_months: int) -> LifeStage:
    """Return the life stage for a given age in months."""
    if age_months < 216:  # < 18 years
        return LifeStage.CHILD
    if age_months < 780:  # < 65 years
        return LifeStage.ADULT
    return LifeStage.RETIRED


def create_all_actors(
    ledger: Ledger,
    num_individuals: int,
    num_food_firms: int,
    num_energy_firms: int,
    num_shelter_firms: int,
    num_owners: int,
    initial_prices: dict[str, float],
    initial_wage: float,
    num_healthcare_firms: int = 2,
    rng: Random | None = None,
) -> dict:
    """
    Instantiate all actors and register their accounts on the ledger.

    Ages are distributed evenly across 1-72 years (12-864 months).
    Children (< 18 y) are each assigned a random adult as guardian.
    Firm owners are selected from the adult population only.
    Healthcare firms produce GoodType.HEALTHCARE.

    Returns a dict with keys: individuals, firms, bank, government.
    """
    if rng is None:
        rng = Random(42)

    # Government (singleton)
    govt = Government.create(ledger)

    # Bank (singleton for now)
    bank = Bank.create(ledger)

    # Firms -- regular goods
    firms: list[Firm] = []
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

    # Healthcare firms
    healthcare_price = initial_prices.get("healthcare", 500.0)
    for _ in range(num_healthcare_firms):
        f = Firm.create(
            ledger, firm_idx, GoodType.HEALTHCARE, healthcare_price, initial_wage
        )
        firms.append(f)
        firm_idx += 1

    # Distribute ages evenly across 1-72 years (12-864 months).
    # Each individual i gets an age that tiles the range uniformly.
    age_range_months = 72 * 12  # 864
    min_age_months = 12  # 1 year

    ages: list[int] = []
    for i in range(num_individuals):
        # Spread evenly: map index to [12, 864] inclusive.
        age = min_age_months + (i * (age_range_months - min_age_months)) // max(1, num_individuals - 1)
        ages.append(age)

    # Identify which indices will be adults (eligible for ownership).
    adult_indices = [
        i for i, a in enumerate(ages) if _life_stage_for_age(a) == LifeStage.ADULT
    ]

    # Assign owners from adults. Owners are the first num_owners adults.
    owner_set: set[int] = set()
    for j in range(min(num_owners, len(adult_indices))):
        owner_set.add(adult_indices[j])

    # Create individuals
    individuals: list[Individual] = []
    for i in range(num_individuals):
        age = ages[i]
        stage = _life_stage_for_age(age)
        is_owner = i in owner_set
        ind = Individual.create(
            ledger, i, is_owner=is_owner, age_months=age, life_stage=stage
        )
        individuals.append(ind)

    # Assign owners to firms (only non-healthcare goods firms first, then
    # healthcare if owners remain). Owner ordering matches adult_indices order.
    owner_individuals = [individuals[i] for i in sorted(owner_set)]
    for oi, owner_ind in enumerate(owner_individuals):
        if oi < len(firms):
            owner_ind.owned_firm_id = firms[oi].id
            firms[oi].owner_id = owner_ind.id

    # Assign children to adult guardians deterministically using the RNG.
    adult_ids = [
        ind.id
        for ind in individuals
        if ind.life_stage == LifeStage.ADULT and not ind.is_owner
    ]
    # Fall back to all adults if every adult is an owner.
    if not adult_ids:
        adult_ids = [
            ind.id for ind in individuals if ind.life_stage == LifeStage.ADULT
        ]

    if adult_ids:
        for ind in individuals:
            if ind.life_stage == LifeStage.CHILD:
                guardian_id = rng.choice(adult_ids)
                ind.parent_ids.append(guardian_id)
                # Record the child on the guardian.
                for other in individuals:
                    if other.id == guardian_id:
                        other.children_ids.append(ind.id)
                        break

    return {
        "individuals": individuals,
        "firms": firms,
        "bank": bank,
        "government": govt,
    }
