"""
Market clearing mechanisms for labor and goods.

Markets operate each simulation day.  All transactions are posted as
balanced journal entries on the shared ledger.
"""

from __future__ import annotations

import random as _random

from .actors import Bank, Firm, GoodType, Government, Individual
from .config import SimConfig
from .ledger import Ledger
from .policy import (
    post_sales_tax,
)
from .production import cobb_douglas, desired_labor, firm_target_output

# ── Transaction helpers ─────────────────────────────────────────────
# These encapsulate the double-entry for common economic transactions.


def post_wage_payment(
    ledger: Ledger,
    day: int,
    bank: Bank,
    firm: Firm,
    worker: Individual,
    amount: float,
) -> None:
    """
    Firm pays worker.  Money moves within the banking system.
    Firm:   DR wage_expense, CR cash
    Worker: DR cash,         CR labor_income
    (Bank deposits net out — one depositor to another.)
    """
    ledger.post(day, f"Wage: {firm.id} -> {worker.id}", [
        (f"{firm.id}:wage_expense", amount, 0),
        (f"{firm.id}:cash", 0, amount),
        (f"{worker.id}:cash", amount, 0),
        (f"{worker.id}:labor_income", 0, amount),
    ])


def post_goods_sale(
    ledger: Ledger,
    day: int,
    bank: Bank,
    firm: Firm,
    buyer: Individual,
    good: GoodType,
    quantity: float,
    price_per_unit: float,
) -> None:
    """
    Sale transaction using a hybrid model:
    - Money flows at market prices
    - Inventory is tracked in physical units (at $1/unit nominal value in ledger)
    - Firm records revenue and COGS
    """
    total_price = quantity * price_per_unit

    # Buyer's transaction: acquire inventory (at nominal $1/unit), pay cash (at market price)
    # Shortfall goes to equity (immediate consumption value)
    ledger.post(day, f"Purchase: {buyer.id} buys {quantity:.1f} {good.value}", [
        (f"{buyer.id}:inventory:{good.value}", quantity, 0),  # nominal value
        (f"{buyer.id}:cash", 0, total_price),  # actual payment
        (f"{buyer.id}:equity", total_price - quantity, 0),  # difference (consumption surplus/deficit)
    ])

    # Firm's transaction: receive cash, record revenue, reduce inventory, record COGS
    ledger.post(day, f"Sale: {firm.id} sells {quantity:.1f} {good.value}", [
        (f"{firm.id}:cash", total_price, 0),
        (f"{firm.id}:revenue", 0, total_price),
        (f"{firm.id}:inventory", 0, quantity),  # nominal value
        (f"{firm.id}:equity", quantity, 0),  # COGS (cost of inventory sold)
    ])


def post_goods_consumption(
    ledger: Ledger,
    day: int,
    individual: Individual,
    good: GoodType,
    quantity: float,
) -> None:
    """
    Individual consumes goods from their inventory.
    DR consumption_expense (record the expense of consuming)
    CR inventory:good (reduce inventory asset)
    """
    ledger.post(day, f"Consume: {individual.id} {quantity:.2f} {good.value}", [
        (f"{individual.id}:consumption_expense", quantity, 0),
        (f"{individual.id}:inventory:{good.value}", 0, quantity),
    ])


def post_production(
    ledger: Ledger,
    day: int,
    firm: Firm,
    quantity: float,
) -> None:
    """
    Firm produces goods: capital is 'used' (not consumed, but
    creates inventory).  DR inventory, CR equity (value creation
    through production).
    """
    if quantity <= 0:
        return
    ledger.post(day, f"Production: {firm.id} {quantity:.1f} {firm.good_type.value}", [
        (f"{firm.id}:inventory", quantity, 0),
        (f"{firm.id}:equity", 0, quantity),
    ])


# ── Market clearing ─────────────────────────────────────────────────


def clear_labor_market(
    ledger: Ledger,
    day: int,
    config: SimConfig,
    firms: list[Firm],
    individuals: list[Individual],
    bank: Bank,
    rng: _random.Random,
) -> dict[str, float]:
    """
    Simple labor market: firms demand labor based on production targets,
    workers supply labor.  Matching is random.

    Returns stats dict with employment info.
    """
    # Reset employment
    for ind in individuals:
        ind.employed = False
        ind.employer_id = None
    for f in firms:
        f.num_workers = 0

    # Compute labor demand per firm
    productivities = config.productivity()
    labor_demands: list[tuple[Firm, int]] = []
    for firm in firms:
        inventory = ledger.account_balance(f"{firm.id}:inventory")
        avg_sales = max(1.0, firm.daily_sales if firm.daily_sales > 0 else 10.0)
        target = firm_target_output(inventory, avg_sales, config.target_inventory_days)
        labor_needed = desired_labor(
            target,
            productivities[firm.good_type.value],
            ledger.account_balance(f"{firm.id}:capital"),
            config.labor_share,
            config.capital_share,
        )
        # Constrained by cash: can the firm afford this many workers?
        cash = ledger.account_balance(f"{firm.id}:cash")
        max_affordable = int(cash / max(firm.wage_offer, 1.0))
        wanted = max(1, min(int(labor_needed) + 1, max_affordable))
        labor_demands.append((firm, wanted))

    # Shuffle workers for random matching
    workers = [ind for ind in individuals if not ind.is_owner]
    rng.shuffle(workers)

    # Sort firms by wage offer (higher wages attract first)
    labor_demands.sort(key=lambda x: x[0].wage_offer, reverse=True)

    worker_idx = 0
    total_hired = 0
    for firm, demand in labor_demands:
        hired = 0
        while hired < demand and worker_idx < len(workers):
            w = workers[worker_idx]
            worker_idx += 1
            w.employed = True
            w.employer_id = firm.id
            firm.num_workers += 1
            hired += 1
            total_hired += 1
            # Post wage payment
            post_wage_payment(ledger, day, bank, firm, w, firm.wage_offer)

    total_workers = len(workers)
    unemployment_rate = 1.0 - (total_hired / max(total_workers, 1))

    return {
        "total_hired": total_hired,
        "total_workers": total_workers,
        "unemployment_rate": unemployment_rate,
    }


def run_production(
    ledger: Ledger,
    day: int,
    config: SimConfig,
    firms: list[Firm],
) -> None:
    """Each firm produces output based on its labor and capital."""
    productivities = config.productivity()
    for firm in firms:
        capital = ledger.account_balance(f"{firm.id}:capital")
        labor = float(firm.num_workers)
        output = cobb_douglas(
            productivities[firm.good_type.value],
            labor,
            capital,
            config.labor_share,
            config.capital_share,
        )
        firm.daily_production = output
        if output > 0:
            post_production(ledger, day, firm, output)


def clear_goods_market(
    ledger: Ledger,
    day: int,
    config: SimConfig,
    firms: list[Firm],
    individuals: list[Individual],
    bank: Bank,
    govt: Government,
    rng: _random.Random,
) -> dict[str, float]:
    """
    Individuals buy goods from firms.  Priority: food > energy > shelter.
    Returns stats with prices and quantities.
    """
    needs = config.consumption_needs()
    stats: dict[str, float] = {}

    # Group firms by good type
    firms_by_good: dict[GoodType, list[Firm]] = {g: [] for g in GoodType}
    for f in firms:
        firms_by_good[f.good_type].append(f)

    total_sales: dict[str, float] = {g.value: 0.0 for g in GoodType}
    total_revenue: dict[str, float] = {g.value: 0.0 for g in GoodType}

    # Shuffle individuals for fairness
    order = list(individuals)
    rng.shuffle(order)

    for good_type in [GoodType.FOOD, GoodType.ENERGY, GoodType.SHELTER]:
        need = needs[good_type.value]
        available_firms = firms_by_good[good_type]
        if not available_firms:
            continue

        for ind in order:
            cash = ledger.account_balance(f"{ind.id}:cash")
            if cash <= 0:
                continue

            # Find cheapest firm with inventory
            available_firms.sort(key=lambda f: f.price)
            remaining_need = need

            for firm in available_firms:
                if remaining_need <= 0:
                    break
                inv = ledger.account_balance(f"{firm.id}:inventory")
                if inv <= 0:
                    continue

                qty = min(remaining_need, inv)
                cost = qty * firm.price
                if cost > cash:
                    qty = cash / firm.price
                    cost = qty * firm.price
                if qty <= 0.001:
                    continue

                # Post the sale
                post_goods_sale(ledger, day, bank, firm, ind, good_type, qty, firm.price)

                # Sales tax
                tax = cost * config.sales_tax_rate
                if tax > 0.01:
                    firm_cash = ledger.account_balance(f"{firm.id}:cash")
                    tax = min(tax, firm_cash)
                    if tax > 0.01:
                        post_sales_tax(ledger, day, govt, bank, firm, tax)

                remaining_need -= qty
                cash -= cost
                total_sales[good_type.value] += qty
                total_revenue[good_type.value] += cost
                firm.daily_sales = (firm.daily_sales * 0.9) + qty * 0.1  # EMA
                firm.daily_revenue = (firm.daily_revenue * 0.9) + cost * 0.1

    for g in GoodType:
        stats[f"{g.value}_quantity_sold"] = total_sales[g.value]
        stats[f"{g.value}_revenue"] = total_revenue[g.value]
        gfirms = firms_by_good[g]
        if gfirms:
            stats[f"{g.value}_avg_price"] = sum(f.price for f in gfirms) / len(gfirms)
        else:
            stats[f"{g.value}_avg_price"] = 0.0

    return stats


def consume_goods(
    ledger: Ledger,
    day: int,
    individuals: list[Individual],
    config: SimConfig,
) -> None:
    """Individuals consume goods from their inventory."""
    needs = config.consumption_needs()
    for ind in individuals:
        for good_type in GoodType:
            need = needs[good_type.value]
            inv = ledger.account_balance(f"{ind.id}:inventory:{good_type.value}")
            consumed = min(need, inv)
            if consumed > 0.001:
                post_goods_consumption(ledger, day, ind, good_type, consumed)


def adjust_prices_and_wages(
    config: SimConfig,
    firms: list[Firm],
    unemployment_rate: float,
) -> None:
    """End-of-day price and wage adjustments."""
    from .production import adjust_price, adjust_wage

    for firm in firms:
        firm.price = adjust_price(
            firm.price,
            0,  # we'll use daily_sales as proxy
            max(1.0, firm.daily_sales),
            config.target_inventory_days,
            config.price_adjustment_speed,
        )
        firm.wage_offer = adjust_wage(
            firm.wage_offer,
            unemployment_rate,
            config.wage_adjustment_speed,
            min_wage=config.min_wage,
        )
