"""
Government bond market — monthly issuance, clearing, and interest payments.

Bonds are financial assets for households and liabilities of government.
Each month the government issues bonds equal to its deficit. A simple
clearing mechanism finds an interest rate that equates supply and demand.
Interest is paid monthly to bondholders.
"""

from __future__ import annotations

from .actors import Bank, Government, Individual
from .config import MONTHS_PER_YEAR, SimConfig
from .ledger import Ledger


# ── Bond purchase transaction ─────────────────────────────────────


def post_bond_purchase(
    ledger: Ledger,
    month: int,
    bank: Bank,
    govt: Government,
    buyer: Individual,
    amount: float,
) -> None:
    """Individual buys government bonds with bank deposits.

    Buyer:  DR bond_asset,      CR cash          (swap deposit for bond)
    Bank:   DR deposits,        CR reserves      (deposit liability shrinks)
    Govt:   DR currency_issued, CR bonds_issued  (swap money liability for bond liability)
    """
    if amount <= 0:
        return
    ledger.post(month, f"Bond purchase: {buyer.id} buys {amount:.0f}", [
        (f"{buyer.id}:bond_asset", amount, 0),
        (f"{buyer.id}:cash", 0, amount),
        (f"{bank.id}:deposits", amount, 0),
        (f"{bank.id}:reserves", 0, amount),
        (f"{govt.id}:currency_issued", amount, 0),
        (f"{govt.id}:bonds_issued", 0, amount),
    ])


def post_bond_interest(
    ledger: Ledger,
    month: int,
    govt: Government,
    bank: Bank,
    recipient: Individual,
    amount: float,
) -> None:
    """Government pays bond interest — creates new money like any govt spending.

    Govt:      DR interest_expense, CR currency_issued
    Bank:      DR reserves,         CR deposits
    Recipient: DR cash,             CR transfer_income
    """
    if amount <= 0:
        return
    ledger.post(month, f"Bond interest: {govt.id} -> {recipient.id}", [
        (f"{govt.id}:interest_expense", amount, 0),
        (f"{govt.id}:currency_issued", 0, amount),
        (f"{bank.id}:reserves", amount, 0),
        (f"{bank.id}:deposits", 0, amount),
        (f"{recipient.id}:cash", amount, 0),
        (f"{recipient.id}:transfer_income", 0, amount),
    ])


# ── Bond market clearing ─────────────────────────────────────────


def _demand_at_rate(
    annual_rate: float,
    available_savings: float,
    sensitivity: float,
) -> float:
    """Monotonically increasing demand function of the offered yield."""
    # demand = available_savings * min(1, sensitivity * annual_rate)
    return available_savings * min(1.0, sensitivity * annual_rate)


def clear_bond_market(
    ledger: Ledger,
    month: int,
    config: SimConfig,
    govt: Government,
    bank: Bank,
    individuals: list[Individual],
    deficit: float,
) -> dict[str, float]:
    """Issue bonds to cover the monthly government deficit.

    Uses bisection to find an annual interest rate where demand ≈ supply.
    Returns stats dict with clearing rate, amount issued, and unmet issuance.
    """
    supply = max(0.0, deficit)  # only issue bonds for positive deficit
    if supply < 1.0:
        return {
            "bonds_issued": 0.0,
            "bond_rate": config.bond_rate_min,
            "unmet_issuance": 0.0,
            "total_interest_paid": 0.0,
        }

    # Compute available savings per individual (fraction of cash they'd bid)
    buyer_savings: list[tuple[Individual, float]] = []
    total_available = 0.0
    for ind in individuals:
        if not ind.alive:
            continue
        cash = ledger.account_balance(f"{ind.id}:cash")
        available = max(0.0, cash * config.bond_savings_fraction)
        if available > 1.0:
            buyer_savings.append((ind, available))
            total_available += available

    if total_available < 1.0:
        return {
            "bonds_issued": 0.0,
            "bond_rate": config.bond_rate_max,
            "unmet_issuance": supply,
            "total_interest_paid": 0.0,
        }

    # Bisection to find clearing rate
    lo = config.bond_rate_min
    hi = config.bond_rate_max
    for _ in range(30):
        mid = (lo + hi) / 2.0
        d = _demand_at_rate(mid, total_available, config.bond_demand_sensitivity)
        if d < supply:
            lo = mid
        else:
            hi = mid
    clearing_rate = (lo + hi) / 2.0

    # Allocate bonds proportionally at the clearing rate
    total_demand = _demand_at_rate(clearing_rate, total_available, config.bond_demand_sensitivity)
    issued = min(supply, total_demand)
    if issued < 1.0:
        return {
            "bonds_issued": 0.0,
            "bond_rate": clearing_rate,
            "unmet_issuance": supply,
            "total_interest_paid": 0.0,
        }

    for ind, avail in buyer_savings:
        share = avail / total_available
        purchase = issued * share
        if purchase > 0.5:
            post_bond_purchase(ledger, month, bank, govt, ind, purchase)

    return {
        "bonds_issued": issued,
        "bond_rate": clearing_rate,
        "unmet_issuance": max(0.0, supply - issued),
        "total_interest_paid": 0.0,  # filled in by pay_bond_interest below
    }


def pay_bond_interest(
    ledger: Ledger,
    month: int,
    config: SimConfig,
    govt: Government,
    bank: Bank,
    individuals: list[Individual],
    annual_rate: float,
) -> float:
    """Pay monthly interest on outstanding bonds to all holders.

    Returns total interest paid.
    """
    monthly_rate = annual_rate / MONTHS_PER_YEAR
    total_paid = 0.0
    for ind in individuals:
        if not ind.alive:
            continue
        bond_balance = ledger.account_balance(f"{ind.id}:bond_asset")
        if bond_balance < 0.01:
            continue
        interest = bond_balance * monthly_rate
        if interest > 0.01:
            post_bond_interest(ledger, month, govt, bank, ind, interest)
            total_paid += interest
    return total_paid
