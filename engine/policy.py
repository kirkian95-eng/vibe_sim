"""
Government policy operations: spending, taxation, transfers, profit distribution.

All transactions are posted as balanced journal entries on the shared ledger.
"""

from __future__ import annotations

from .actors import Bank, Firm, Government, Individual
from .config import SimConfig
from .ledger import Ledger

# ── Transaction helpers ─────────────────────────────────────────────


def post_government_spending(
    ledger: Ledger,
    day: int,
    govt: Government,
    bank: Bank,
    recipient_id: str,
    amount: float,
    description: str,
) -> None:
    """
    Government spending creates money.
    Government: DR spending_expense, CR currency_issued  (money creation)
    Bank:       DR reserves,        CR deposits          (intermediation)
    Recipient:  DR cash,            CR transfer_income / revenue
    """
    if recipient_id.startswith("ind_"):
        income_acct = f"{recipient_id}:transfer_income"
    elif recipient_id.startswith("firm_"):
        income_acct = f"{recipient_id}:revenue"
    else:
        income_acct = f"{recipient_id}:equity"

    ledger.post(day, description, [
        (f"{govt.id}:spending_expense", amount, 0),
        (f"{govt.id}:currency_issued", 0, amount),
        (f"{bank.id}:reserves", amount, 0),
        (f"{bank.id}:deposits", 0, amount),
        (f"{recipient_id}:cash", amount, 0),
        (income_acct, 0, amount),
    ])


def post_transfer_payment(
    ledger: Ledger,
    day: int,
    govt: Government,
    bank: Bank,
    recipient: Individual,
    amount: float,
) -> None:
    """Government transfer payment to an individual (unemployment benefit etc)."""
    ledger.post(day, f"Govt transfer to {recipient.id}", [
        (f"{govt.id}:transfer_expense", amount, 0),
        (f"{govt.id}:currency_issued", 0, amount),
        (f"{bank.id}:reserves", amount, 0),
        (f"{bank.id}:deposits", 0, amount),
        (f"{recipient.id}:cash", amount, 0),
        (f"{recipient.id}:transfer_income", 0, amount),
    ])


def post_tax_payment(
    ledger: Ledger,
    day: int,
    govt: Government,
    bank: Bank,
    payer_id: str,
    amount: float,
    description: str,
) -> None:
    """
    Taxation destroys money.
    Payer:      DR tax_expense,     CR cash
    Bank:       DR deposits,        CR reserves
    Government: DR currency_issued, CR tax_revenue
    """
    ledger.post(day, description, [
        (f"{payer_id}:tax_expense", amount, 0),
        (f"{payer_id}:cash", 0, amount),
        (f"{bank.id}:deposits", amount, 0),
        (f"{bank.id}:reserves", 0, amount),
        (f"{govt.id}:currency_issued", amount, 0),
        (f"{govt.id}:tax_revenue", 0, amount),
    ])


def post_sales_tax(
    ledger: Ledger,
    day: int,
    govt: Government,
    bank: Bank,
    firm: Firm,
    amount: float,
) -> None:
    """Firm remits sales tax to government."""
    if amount <= 0:
        return
    post_tax_payment(ledger, day, govt, bank, firm.id, amount, f"Sales tax: {firm.id}")


def post_profit_distribution(
    ledger: Ledger,
    day: int,
    bank: Bank,
    firm: Firm,
    owner: Individual,
    amount: float,
) -> None:
    """Firm distributes profits to owner."""
    ledger.post(day, f"Profit dist: {firm.id} -> {owner.id}", [
        (f"{firm.id}:equity", amount, 0),
        (f"{firm.id}:cash", 0, amount),
        (f"{owner.id}:cash", amount, 0),
        (f"{owner.id}:profit_income", 0, amount),
    ])


# ── Aggregate policy operations ─────────────────────────────────────


def government_operations(
    ledger: Ledger,
    day: int,
    config: SimConfig,
    govt: Government,
    bank: Bank,
    individuals: list[Individual],
    firms: list[Firm],
) -> dict[str, float]:
    """
    Government collects income tax and makes transfer payments.
    Taxes destroy money; spending creates money.
    """
    stats: dict[str, float] = {}
    total_tax = 0.0
    total_transfers = 0.0
    transfers_to_households = 0.0
    govt_spending_on_firms = 0.0

    # Build a lookup for firms by id (avoid O(n) search per individual)
    firm_by_id = {f.id: f for f in firms}

    # Income tax on wages
    for ind in individuals:
        if ind.employed and ind.employer_id:
            employer = firm_by_id.get(ind.employer_id)
            if employer:
                tax = employer.wage_offer * config.income_tax_rate
                ind_cash = ledger.account_balance(f"{ind.id}:cash")
                tax = min(tax, ind_cash)
                if tax > 0.01:
                    post_tax_payment(
                        ledger, day, govt, bank, ind.id, tax,
                        f"Income tax: {ind.id}",
                    )
                    total_tax += tax

    # Transfer payments to unemployed
    unemployed = [ind for ind in individuals if not ind.employed and not ind.is_owner]
    for ind in unemployed:
        amount = config.daily_govt_transfer
        post_transfer_payment(ledger, day, govt, bank, ind, amount)
        total_transfers += amount
        transfers_to_households += amount

    # General government spending (purchases from firms)
    if config.daily_govt_spending > 0 and firms:
        per_firm = config.daily_govt_spending / len(firms)
        for firm in firms:
            post_government_spending(
                ledger, day, govt, bank, firm.id, per_firm,
                f"Govt spending: {firm.id}",
            )
            total_transfers += per_firm
            govt_spending_on_firms += per_firm

    stats["total_tax_collected"] = total_tax
    stats["total_govt_transfers"] = total_transfers
    stats["transfers_to_households"] = transfers_to_households
    stats["govt_spending_on_firms"] = govt_spending_on_firms
    stats["govt_deficit"] = total_transfers - total_tax
    return stats


def firm_profit_distribution(
    ledger: Ledger,
    day: int,
    config: SimConfig,
    firms: list[Firm],
    individuals: list[Individual],
    bank: Bank,
) -> float:
    """
    Firms distribute a fraction of profits to owners (weekly).
    Returns total distributed.
    """
    if day % 7 != 0:
        return 0.0

    total_distributed = 0.0
    ind_by_id = {i.id: i for i in individuals}
    for firm in firms:
        if not firm.owner_id:
            continue
        owner = ind_by_id.get(firm.owner_id)
        if not owner:
            continue

        revenue = ledger.account_balance(f"{firm.id}:revenue")
        expenses = (
            ledger.account_balance(f"{firm.id}:wage_expense")
            + ledger.account_balance(f"{firm.id}:input_expense")
            + ledger.account_balance(f"{firm.id}:tax_expense")
        )
        profit = revenue - expenses
        if profit <= 0:
            continue

        dist = profit * config.profit_distribution_rate * (1.0 / 52.0)
        firm_cash = ledger.account_balance(f"{firm.id}:cash")
        dist = min(dist, firm_cash * 0.5)
        if dist > 1.0:
            post_profit_distribution(ledger, day, bank, firm, owner, dist)
            total_distributed += dist

    return total_distributed
