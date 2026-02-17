"""
Demographics: aging, births, deaths, inheritance, and pensions.

This module runs once per simulation month and handles:
  - Aging all alive individuals by one month
  - Life-stage transitions (child -> adult, adult -> retired)
  - Births (paired fertility, healthcare fee, newborn bootstrap)
  - Deaths (mortality hazard, estate settlement via taxation)
  - Pension payments to retirees
"""

from __future__ import annotations

import random

from .actors import Bank, Firm, Government, Individual, LifeStage
from .config import MONTHS_PER_YEAR, SimConfig
from .ledger import Ledger
from .policy import post_government_spending, post_tax_payment, post_transfer_payment

# ---------------------------------------------------------------------------
# Aging
# ---------------------------------------------------------------------------

def advance_ages(
    individuals: list[Individual],
    config: SimConfig,
) -> dict[str, list]:
    """Increment age_months for every alive individual and handle transitions.

    Also ticks down fertility_cooldown_months and
    reduced_labor_months_remaining for individuals that have those
    counters set above zero.

    Returns ``{"new_adults": [...], "new_retirees": [...]}`` for logging.
    """
    retirement_threshold = config.retirement_age * MONTHS_PER_YEAR  # e.g. 780
    adult_threshold = 18 * MONTHS_PER_YEAR  # 216

    new_adults: list[Individual] = []
    new_retirees: list[Individual] = []

    for ind in individuals:
        if not ind.alive:
            continue

        ind.age_months += 1

        # Tick down cooldowns
        if ind.fertility_cooldown_months > 0:
            ind.fertility_cooldown_months -= 1
        if ind.reduced_labor_months_remaining > 0:
            ind.reduced_labor_months_remaining -= 1

        # Life-stage transitions
        if ind.life_stage == LifeStage.CHILD and ind.age_months >= adult_threshold:
            ind.life_stage = LifeStage.ADULT
            new_adults.append(ind)

        elif ind.life_stage == LifeStage.ADULT and ind.age_months >= retirement_threshold:
            ind.life_stage = LifeStage.RETIRED
            # Retirees leave the labour force
            ind.employed = False
            ind.employer_id = None
            new_retirees.append(ind)

    return {"new_adults": new_adults, "new_retirees": new_retirees}


# ---------------------------------------------------------------------------
# Births
# ---------------------------------------------------------------------------

def _is_eligible_parent(ind: Individual) -> bool:
    """An individual can be a parent if they are an alive adult with no
    active fertility cooldown."""
    return (
        ind.alive
        and ind.life_stage == LifeStage.ADULT
        and ind.fertility_cooldown_months == 0
    )


def _fed_fraction(
    individuals: list[Individual],
    ledger: Ledger,
) -> float:
    """Fraction of alive adults that are 'fed' (cash > 0 heuristic)."""
    adults = [i for i in individuals if i.alive and i.life_stage == LifeStage.ADULT]
    if not adults:
        return 0.0
    fed = sum(
        1
        for ind in adults
        if ledger.account_balance(f"{ind.id}:cash") > 0
    )
    return fed / len(adults)


def run_births(
    ledger: Ledger,
    month: int,
    config: SimConfig,
    individuals: list[Individual],
    firms: list[Firm],
    bank: Bank,
    govt: Government,
    rng: random.Random,
    *,
    next_individual_idx: int | None = None,
) -> dict[str, object]:
    """Pair eligible adults, roll fertility, and create newborns.

    Parameters
    ----------
    next_individual_idx:
        The integer index to use for the *first* newborn's id
        (``ind_{idx:04d}``).  If ``None`` the function falls back to
        ``len(individuals)`` which is safe as long as no individuals have
        been removed from the list.

    Returns
    -------
    dict with keys:
        ``"births"`` (int), ``"new_individuals"`` (list[Individual]).
    """
    if next_individual_idx is None:
        next_individual_idx = len(individuals)

    eligible = [i for i in individuals if _is_eligible_parent(i)]

    # Shuffle deterministically so pairing is reproducible but not biased.
    rng.shuffle(eligible)

    # Pair up: take consecutive pairs (0,1), (2,3), ...
    pairs: list[tuple[Individual, Individual]] = []
    for i in range(0, len(eligible) - 1, 2):
        pairs.append((eligible[i], eligible[i + 1]))

    # Wellbeing scalar: birth probability scales with economic conditions.
    wellbeing = _fed_fraction(individuals, ledger)
    base_prob = config.monthly_fertility_hazard

    new_borns: list[Individual] = []
    idx = next_individual_idx

    for parent_a, parent_b in pairs:
        effective_prob = base_prob * wellbeing
        if rng.random() >= effective_prob:
            continue

        # --- Birth event ------------------------------------------------

        # Create new Individual
        child = Individual.create(ledger, idx, is_owner=False)
        child.age_months = 0
        child.life_stage = LifeStage.CHILD
        child.alive = True
        child.parent_ids = [parent_a.id, parent_b.id]
        child.children_ids = []
        child.fertility_cooldown_months = 0
        child.reduced_labor_months_remaining = 0
        idx += 1

        # Link parents to child
        parent_a.children_ids.append(child.id)
        parent_b.children_ids.append(child.id)

        # Cooldown on both parents
        parent_a.fertility_cooldown_months = 12
        parent_b.fertility_cooldown_months = 12

        # Reduced labour productivity for both parents
        parent_a.reduced_labor_months_remaining = 12
        parent_b.reduced_labor_months_remaining = 12

        # --- Healthcare fee (split 50/50 between parents) ---------------
        fee = config.childbirth_healthcare_fee
        half_fee = fee / 2.0

        for parent in (parent_a, parent_b):
            parent_cash = ledger.account_balance(f"{parent.id}:cash")
            payable = min(half_fee, parent_cash)
            if payable > 0:
                # Parent pays: DR consumption_expense, CR cash
                # (Money leaves parent; in a fuller model it would flow to
                # a healthcare firm.  Here we destroy it via taxation
                # mechanics so the ledger stays balanced.)
                post_tax_payment(
                    ledger,
                    month,
                    govt,
                    bank,
                    parent.id,
                    payable,
                    f"Childbirth healthcare: {parent.id} for {child.id}",
                )

        # --- Bootstrap child with a small government transfer -----------
        bootstrap_amount = config.initial_individual_cash * 0.1
        if bootstrap_amount > 0:
            post_government_spending(
                ledger,
                month,
                govt,
                bank,
                child.id,
                bootstrap_amount,
                f"Bootstrap: newborn {child.id}",
            )

        new_borns.append(child)

    return {
        "births": len(new_borns),
        "new_individuals": new_borns,
    }


# ---------------------------------------------------------------------------
# Deaths
# ---------------------------------------------------------------------------

def run_deaths(
    ledger: Ledger,
    month: int,
    config: SimConfig,
    individuals: list[Individual],
    govt: Government,
    bank: Bank,
    rng: random.Random,
) -> dict[str, object]:
    """Apply mortality hazard to eligible individuals.

    For each individual who dies:
      1. Mark ``alive = False``.
      2. Transfer remaining cash balance to government using the same
         accounting path as a tax payment (money is destroyed — deposits
         and reserves shrink symmetrically).

    Returns ``{"deaths": int, "deceased_ids": list[str]}``.
    """
    mortality_threshold = config.mortality_start_age * MONTHS_PER_YEAR
    hazard = config.monthly_mortality_hazard

    deceased_ids: list[str] = []

    for ind in individuals:
        if not ind.alive:
            continue
        if ind.age_months < mortality_threshold:
            continue

        if rng.random() >= hazard:
            continue

        # --- Death event ------------------------------------------------
        ind.alive = False
        ind.employed = False
        ind.employer_id = None

        cash_balance = ledger.account_balance(f"{ind.id}:cash")

        if cash_balance > 0:
            # Settle estate: treat the entire cash balance as a 100%
            # inheritance tax.  This uses the standard tax-payment path
            # which correctly destroys money:
            #   Deceased: DR tax_expense, CR cash
            #   Bank:     DR deposits,    CR reserves
            #   Govt:     DR currency_issued, CR tax_revenue
            post_tax_payment(
                ledger,
                month,
                govt,
                bank,
                ind.id,
                cash_balance,
                f"Estate settlement: {ind.id}",
            )

        # Zero out any remaining equity so the balance sheet is clean.
        equity_balance = ledger.account_balance(f"{ind.id}:equity")
        if abs(equity_balance) > 1e-6:
            # Equity is a credit-normal account.
            # To zero it: DR equity (reduces it), CR ... we need a
            # contra-account.  The individual has no liabilities left
            # (cash is gone), so the residual equity reflects accumulated
            # income minus expenses.  We close it against income/expense
            # via a single balancing entry that debits equity and credits
            # a revenue offset (or vice-versa).
            #
            # If equity > 0 (credit balance): DR equity, CR transfer_income
            #   (mirrors the accounting identity: assets already zeroed,
            #    so equity + revenue - expense must also zero)
            # If equity < 0 (debit balance):  DR transfer_income, CR equity
            #
            # In practice these entries only matter for balance-sheet
            # tidiness; the money has already been destroyed above.
            if equity_balance > 0:
                ledger.post(month, f"Close equity: {ind.id}", [
                    (f"{ind.id}:equity", equity_balance, 0),
                    (f"{ind.id}:transfer_income", 0, equity_balance),
                ])
            else:
                abs_eq = abs(equity_balance)
                ledger.post(month, f"Close equity: {ind.id}", [
                    (f"{ind.id}:transfer_income", abs_eq, 0),
                    (f"{ind.id}:equity", 0, abs_eq),
                ])

        deceased_ids.append(ind.id)

    return {
        "deaths": len(deceased_ids),
        "deceased_ids": deceased_ids,
    }


# ---------------------------------------------------------------------------
# Pensions
# ---------------------------------------------------------------------------

def pay_pensions(
    ledger: Ledger,
    month: int,
    config: SimConfig,
    individuals: list[Individual],
    govt: Government,
    bank: Bank,
    avg_wage: float,
) -> dict[str, float]:
    """Pay a monthly pension to every alive retiree.

    The pension is ``avg_wage * config.pension_replacement_rate`` and is
    funded by government money creation (identical accounting to transfer
    payments).

    Returns ``{"total_pensions": float, "num_retirees_paid": int}``.
    """
    pension = avg_wage * config.pension_replacement_rate
    if pension <= 0:
        return {"total_pensions": 0.0, "num_retirees_paid": 0}

    total = 0.0
    count = 0

    for ind in individuals:
        if not ind.alive:
            continue
        if ind.life_stage != LifeStage.RETIRED:
            continue

        post_transfer_payment(
            ledger,
            month,
            govt,
            bank,
            ind,
            pension,
        )
        total += pension
        count += 1

    return {"total_pensions": total, "num_retirees_paid": count}
