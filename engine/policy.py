"""
Government policy operations: spending, taxation, transfers, pensions,
healthcare payments, and profit distribution.

All transactions are posted as balanced journal entries on the shared ledger.
All flows are monthly.
"""

from __future__ import annotations

from .actors import Bank, Firm, GoodType, Government, Individual, LifeStage
from .config import SimConfig
from .ledger import Ledger

# ── Transaction helpers ─────────────────────────────────────────────


def post_government_spending(
    ledger: Ledger,
    month: int,
    govt: Government,
    bank: Bank,
    recipient_id: str,
    amount: float,
    description: str,
) -> None:
    """
    Government spending creates money.
    Government: DR spending_expense, CR currency_issued
    Bank:       DR reserves,        CR deposits
    Recipient:  DR cash,            CR transfer_income / revenue
    """
    if recipient_id.startswith("ind_"):
        income_acct = f"{recipient_id}:transfer_income"
    elif recipient_id.startswith("firm_"):
        income_acct = f"{recipient_id}:revenue"
    else:
        income_acct = f"{recipient_id}:equity"

    ledger.post(month, description, [
        (f"{govt.id}:spending_expense", amount, 0),
        (f"{govt.id}:currency_issued", 0, amount),
        (f"{bank.id}:reserves", amount, 0),
        (f"{bank.id}:deposits", 0, amount),
        (f"{recipient_id}:cash", amount, 0),
        (income_acct, 0, amount),
    ])


def post_pension_payment(
    ledger: Ledger,
    month: int,
    govt: Government,
    bank: Bank,
    recipient: Individual,
    amount: float,
) -> None:
    """Government pension payment to a retiree — creates money."""
    ledger.post(month, f"Pension: {recipient.id}", [
        (f"{govt.id}:pension_expense", amount, 0),
        (f"{govt.id}:currency_issued", 0, amount),
        (f"{bank.id}:reserves", amount, 0),
        (f"{bank.id}:deposits", 0, amount),
        (f"{recipient.id}:cash", amount, 0),
        (f"{recipient.id}:pension_income", 0, amount),
    ])


def post_healthcare_govt_payment(
    ledger: Ledger,
    month: int,
    govt: Government,
    bank: Bank,
    healthcare_firm_id: str,
    amount: float,
    description: str,
) -> None:
    """Government pays healthcare firm for elder/retiree visits — creates money."""
    ledger.post(month, description, [
        (f"{govt.id}:healthcare_expense", amount, 0),
        (f"{govt.id}:currency_issued", 0, amount),
        (f"{bank.id}:reserves", amount, 0),
        (f"{bank.id}:deposits", 0, amount),
        (f"{healthcare_firm_id}:cash", amount, 0),
        (f"{healthcare_firm_id}:revenue", 0, amount),
    ])


def post_healthcare_private_payment(
    ledger: Ledger,
    month: int,
    payer: Individual,
    healthcare_firm_id: str,
    amount: float,
    description: str,
) -> None:
    """Individual pays healthcare firm (e.g. childbirth fee)."""
    if amount <= 0:
        return
    ledger.post(month, description, [
        (f"{payer.id}:cash", 0, amount),
        (f"{payer.id}:equity", amount, 0),
        (f"{healthcare_firm_id}:cash", amount, 0),
        (f"{healthcare_firm_id}:revenue", 0, amount),
    ])


def post_transfer_payment(
    ledger: Ledger,
    month: int,
    govt: Government,
    bank: Bank,
    recipient: Individual,
    amount: float,
) -> None:
    """Government transfer payment to an individual (unemployment benefit etc)."""
    ledger.post(month, f"Govt transfer to {recipient.id}", [
        (f"{govt.id}:transfer_expense", amount, 0),
        (f"{govt.id}:currency_issued", 0, amount),
        (f"{bank.id}:reserves", amount, 0),
        (f"{bank.id}:deposits", 0, amount),
        (f"{recipient.id}:cash", amount, 0),
        (f"{recipient.id}:transfer_income", 0, amount),
    ])


def post_tax_payment(
    ledger: Ledger,
    month: int,
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
    ledger.post(month, description, [
        (f"{payer_id}:tax_expense", amount, 0),
        (f"{payer_id}:cash", 0, amount),
        (f"{bank.id}:deposits", amount, 0),
        (f"{bank.id}:reserves", 0, amount),
        (f"{govt.id}:currency_issued", amount, 0),
        (f"{govt.id}:tax_revenue", 0, amount),
    ])


def post_sales_tax(
    ledger: Ledger,
    month: int,
    govt: Government,
    bank: Bank,
    firm: Firm,
    amount: float,
) -> None:
    """Firm remits sales tax to government."""
    if amount <= 0:
        return
    post_tax_payment(ledger, month, govt, bank, firm.id, amount, f"Sales tax: {firm.id}")


def post_profit_distribution(
    ledger: Ledger,
    month: int,
    bank: Bank,
    firm: Firm,
    owner: Individual,
    amount: float,
) -> None:
    """Firm distributes profits to owner."""
    ledger.post(month, f"Profit dist: {firm.id} -> {owner.id}", [
        (f"{firm.id}:equity", amount, 0),
        (f"{firm.id}:cash", 0, amount),
        (f"{owner.id}:cash", amount, 0),
        (f"{owner.id}:profit_income", 0, amount),
    ])


# ── Aggregate policy operations ─────────────────────────────────────


def government_operations(
    ledger: Ledger,
    month: int,
    config: SimConfig,
    govt: Government,
    bank: Bank,
    individuals: list[Individual],
    firms: list[Firm],
    avg_wage: float = 0.0,
) -> dict[str, float]:
    """
    Government collects income tax, pays transfers, and purchases from firms.
    Taxes destroy money; spending creates money.
    Transfers and spending are indexed to average wage so they stay in "real dollars".
    """
    stats: dict[str, float] = {}
    total_tax = 0.0
    total_transfers = 0.0
    transfers_to_households = 0.0
    govt_spending_on_firms = 0.0

    firm_by_id = {f.id: f for f in firms}

    # Income tax on wages (employed adults only)
    for ind in individuals:
        if not ind.alive:
            continue
        if ind.employed and ind.employer_id:
            employer = firm_by_id.get(ind.employer_id)
            if employer:
                tax = employer.wage_offer * config.income_tax_rate
                ind_cash = ledger.account_balance(f"{ind.id}:cash")
                tax = min(tax, ind_cash)
                if tax > 0.01:
                    post_tax_payment(
                        ledger, month, govt, bank, ind.id, tax,
                        f"Income tax: {ind.id}",
                    )
                    total_tax += tax

    # Transfer payments to unemployed adults (not children, not owners, not retired)
    unemployed = [
        ind for ind in individuals
        if ind.alive
        and ind.life_stage == LifeStage.ADULT
        and not ind.employed
        and not ind.is_owner
    ]
    # Transfer amount indexed to average wage to maintain real value.
    # Config value is calibrated to initial_wage; scale proportionally.
    wage_scale = avg_wage / config.initial_wage if avg_wage > 0 and config.initial_wage > 0 else 1.0
    transfer_amount = config.monthly_govt_transfer * wage_scale

    for ind in unemployed:
        post_transfer_payment(ledger, month, govt, bank, ind, transfer_amount)
        total_transfers += transfer_amount
        transfers_to_households += transfer_amount

    # General government spending (purchases from non-healthcare firms)
    # Indexed to average wage to maintain real value.
    govt_spending = config.monthly_govt_spending * wage_scale
    non_hc_firms = [f for f in firms if not f.is_healthcare]
    if govt_spending > 0 and non_hc_firms:
        per_firm = govt_spending / len(non_hc_firms)
        for firm in non_hc_firms:
            post_government_spending(
                ledger, month, govt, bank, firm.id, per_firm,
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


def pension_operations(
    ledger: Ledger,
    month: int,
    config: SimConfig,
    govt: Government,
    bank: Bank,
    individuals: list[Individual],
    avg_wage: float,
) -> dict[str, float]:
    """Pay monthly pensions to all living retirees."""
    pension_amount = max(1.0, avg_wage * config.pension_replacement_rate)
    total_pensions = 0.0
    num_paid = 0

    for ind in individuals:
        if ind.alive and ind.life_stage == LifeStage.RETIRED:
            post_pension_payment(ledger, month, govt, bank, ind, pension_amount)
            total_pensions += pension_amount
            num_paid += 1

    return {
        "total_pensions": total_pensions,
        "num_retirees_paid": num_paid,
        "pension_per_retiree": pension_amount,
    }


def healthcare_operations(
    ledger: Ledger,
    month: int,
    config: SimConfig,
    govt: Government,
    bank: Bank,
    individuals: list[Individual],
    healthcare_firms: list[Firm],
) -> dict[str, float]:
    """Government pays healthcare firms for elder visits.

    Healthcare capacity = sum of workers × healthcare_productivity.
    Retirees are served first. Unmet visits are recorded as a shortage.
    """
    if not healthcare_firms:
        return {
            "healthcare_capacity": 0.0,
            "elder_visits_needed": 0.0,
            "elder_visits_served": 0.0,
            "healthcare_shortage": 0.0,
            "healthcare_govt_spending": 0.0,
        }

    total_capacity = sum(
        f.num_workers * config.healthcare_productivity for f in healthcare_firms
    )

    retirees = [i for i in individuals if i.alive and i.life_stage == LifeStage.RETIRED]
    visits_needed = len(retirees)
    visits_served = min(visits_needed, int(total_capacity))
    shortage = max(0, visits_needed - visits_served)

    total_payment = visits_served * config.elder_healthcare_monthly_cost
    if total_payment > 0 and healthcare_firms:
        per_firm = total_payment / len(healthcare_firms)
        for firm in healthcare_firms:
            post_healthcare_govt_payment(
                ledger, month, govt, bank, firm.id, per_firm,
                f"Elder healthcare: {firm.id}",
            )

    return {
        "healthcare_capacity": total_capacity,
        "elder_visits_needed": float(visits_needed),
        "elder_visits_served": float(visits_served),
        "healthcare_shortage": float(shortage),
        "healthcare_govt_spending": total_payment,
    }


def repay_firm_loans(
    ledger: Ledger,
    month: int,
    firms: list[Firm],
    bank: Bank,
) -> float:
    """
    Firms repay bank loans from excess deposits. Reduces loans_payable and cash.
    Returns total repaid.
    """
    total_repaid = 0.0
    for firm in firms:
        cash = ledger.account_balance(f"{firm.id}:cash")
        loans = ledger.account_balance(f"{firm.id}:loans_payable")
        repay = min(max(0, cash), max(0, loans))
        if repay > 0.01:
            ledger.post(month, f"Loan repayment: {firm.id} -> {bank.id}", [
                (f"{firm.id}:cash", 0, repay),
                (f"{firm.id}:loans_payable", repay, 0),
                (f"{bank.id}:loans_receivable", 0, repay),
                (f"{bank.id}:deposits", repay, 0),
            ])
            total_repaid += repay
    return total_repaid


def firm_profit_distribution(
    ledger: Ledger,
    month: int,
    config: SimConfig,
    firms: list[Firm],
    individuals: list[Individual],
    bank: Bank,
) -> float:
    """
    Firms distribute a fraction of profits to owners (monthly).
    Returns total distributed.
    """
    total_distributed = 0.0
    ind_by_id = {i.id: i for i in individuals}
    for firm in firms:
        if not firm.owner_id:
            continue
        owner = ind_by_id.get(firm.owner_id)
        if not owner or not owner.alive:
            continue

        revenue = ledger.account_balance(f"{firm.id}:revenue")
        expenses = (
            ledger.account_balance(f"{firm.id}:wage_expense")
            + ledger.account_balance(f"{firm.id}:input_expense")
            + ledger.account_balance(f"{firm.id}:tax_expense")
        )
        cumulative_profit = revenue - expenses
        # Only distribute from undistributed profit so that distributions
        # don't grow unboundedly as cumulative revenue accumulates.
        undistributed = cumulative_profit - firm.cumulative_distributions
        if undistributed <= 0:
            continue

        dist = undistributed * config.profit_distribution_rate
        firm_cash = ledger.account_balance(f"{firm.id}:cash")
        dist = min(dist, firm_cash * 0.5)
        if dist > 0.01:
            post_profit_distribution(ledger, month, bank, firm, owner, dist)
            firm.cumulative_distributions += dist
            total_distributed += dist

    return total_distributed
