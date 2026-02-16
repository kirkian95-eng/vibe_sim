"""
Market clearing mechanisms for labor and goods.

Markets operate each simulation month.  All transactions are posted as
balanced journal entries on the shared ledger.
"""

from __future__ import annotations

import random as _random

from .actors import Bank, Firm, GoodType, Government, Individual, LifeStage, GOODS
from .config import SimConfig
from .ledger import Ledger
from .policy import (
    post_sales_tax,
    post_shelter_purchase_from_govt,
)
from .production import cobb_douglas, desired_labor, firm_target_output

# ── Transaction helpers ─────────────────────────────────────────────


def post_wage_payment(
    ledger: Ledger,
    month: int,
    bank: Bank,
    firm: Firm,
    worker: Individual,
    amount: float,
) -> None:
    """
    Firm pays worker.  Money moves within the banking system.
    Firm:   DR wage_expense, CR cash
    Worker: DR cash,         CR labor_income
    """
    ledger.post(month, f"Wage: {firm.id} -> {worker.id}", [
        (f"{firm.id}:wage_expense", amount, 0),
        (f"{firm.id}:cash", 0, amount),
        (f"{worker.id}:cash", amount, 0),
        (f"{worker.id}:labor_income", 0, amount),
    ])


def post_goods_sale(
    ledger: Ledger,
    month: int,
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

    diff = total_price - quantity
    if diff >= 0:
        buyer_lines = [
            (f"{buyer.id}:inventory:{good.value}", quantity, 0),
            (f"{buyer.id}:cash", 0, total_price),
            (f"{buyer.id}:equity", diff, 0),
        ]
    else:
        buyer_lines = [
            (f"{buyer.id}:inventory:{good.value}", quantity, 0),
            (f"{buyer.id}:cash", 0, total_price),
            (f"{buyer.id}:equity", 0, -diff),
        ]
    ledger.post(month, f"Purchase: {buyer.id} buys {quantity:.1f} {good.value}", buyer_lines)

    ledger.post(month, f"Sale: {firm.id} sells {quantity:.1f} {good.value}", [
        (f"{firm.id}:cash", total_price, 0),
        (f"{firm.id}:revenue", 0, total_price),
        (f"{firm.id}:inventory", 0, quantity),
        (f"{firm.id}:equity", quantity, 0),
    ])


def post_goods_consumption(
    ledger: Ledger,
    month: int,
    individual: Individual,
    good: GoodType,
    quantity: float,
) -> None:
    """Individual consumes goods from their inventory."""
    ledger.post(month, f"Consume: {individual.id} {quantity:.2f} {good.value}", [
        (f"{individual.id}:consumption_expense", quantity, 0),
        (f"{individual.id}:inventory:{good.value}", 0, quantity),
    ])


def post_production(
    ledger: Ledger,
    month: int,
    firm: Firm,
    quantity: float,
) -> None:
    """Firm produces goods: inventory created, equity credited."""
    if quantity <= 0:
        return
    ledger.post(month, f"Production: {firm.id} {quantity:.1f} {firm.good_type.value}", [
        (f"{firm.id}:inventory", quantity, 0),
        (f"{firm.id}:equity", 0, quantity),
    ])


# ── Market clearing ─────────────────────────────────────────────────


def clear_labor_market(
    ledger: Ledger,
    month: int,
    config: SimConfig,
    firms: list[Firm],
    individuals: list[Individual],
    bank: Bank,
    rng: _random.Random,
) -> dict[str, float]:
    """
    Monthly labor market: firms demand labor based on production targets,
    workers supply labor.  Matching is random.
    Only alive adults who are not owners participate in the worker pool.
    Parents with reduced_labor_months_remaining > 0 supply at 50% effectiveness
    (modeled as being available for hiring but at reduced productivity —
    here we simply let them be hired but the firm gets half a worker).
    """
    # Reset employment
    for ind in individuals:
        if ind.alive:
            ind.employed = False
            ind.employer_id = None
    for f in firms:
        f.num_workers = 0

    # Compute labor demand per firm
    productivities = config.productivity()
    labor_demands: list[tuple[Firm, int]] = []
    for firm in firms:
        if firm.is_healthcare:
            # Healthcare firms bid for workers to build capacity;
            # their demand is proportional to their cash (like other firms)
            cash = ledger.account_balance(f"{firm.id}:cash")
            wanted = max(0, int(cash / max(firm.wage_offer, 1.0)))
            wanted = min(wanted, 50)  # cap healthcare firm hiring
        else:
            inventory = ledger.account_balance(f"{firm.id}:inventory")
            avg_sales = max(1.0, firm.sales if firm.sales > 0 else 10.0)
            target = firm_target_output(inventory, avg_sales, config.target_inventory_months)
            labor_needed = desired_labor(
                target,
                productivities[firm.good_type.value],
                ledger.account_balance(f"{firm.id}:capital"),
                config.labor_share,
                config.capital_share,
            )
            cash = ledger.account_balance(f"{firm.id}:cash")
            max_affordable = max(0, int(cash / max(firm.wage_offer, 1.0)))
            wanted = min(int(labor_needed) + 1, max_affordable)

        if wanted > 0:
            labor_demands.append((firm, wanted))

    # Workers: alive adults who are not owners
    workers = [
        ind for ind in individuals
        if ind.alive
        and ind.life_stage == LifeStage.ADULT
        and not ind.is_owner
    ]
    rng.shuffle(workers)

    # Sort firms by wage offer (higher wages attract first)
    labor_demands.sort(key=lambda x: x[0].wage_offer, reverse=True)

    worker_idx = 0
    total_hired = 0
    total_wages = 0.0
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

            # Parenting penalty: new parents supply half labor → half wage
            effective_wage = firm.wage_offer
            if w.reduced_labor_months_remaining > 0:
                effective_wage = firm.wage_offer * 0.5

            total_wages += effective_wage
            post_wage_payment(ledger, month, bank, firm, w, effective_wage)

    total_workers = len(workers)
    unemployment_rate = 1.0 - (total_hired / max(total_workers, 1))

    return {
        "total_hired": total_hired,
        "total_workers": total_workers,
        "unemployment_rate": unemployment_rate,
        "total_wages": total_wages,
    }


def run_production(
    ledger: Ledger,
    month: int,
    config: SimConfig,
    firms: list[Firm],
) -> None:
    """Each non-healthcare firm produces output based on its labor and capital."""
    productivities = config.productivity()
    for firm in firms:
        if firm.is_healthcare:
            firm.production = 0.0
            continue
        capital = ledger.account_balance(f"{firm.id}:capital")
        labor = float(firm.num_workers)
        output = cobb_douglas(
            productivities[firm.good_type.value],
            labor,
            capital,
            config.labor_share,
            config.capital_share,
        )
        firm.production = output
        if output > 0:
            post_production(ledger, month, firm, output)


def clear_goods_market(
    ledger: Ledger,
    month: int,
    config: SimConfig,
    firms: list[Firm],
    individuals: list[Individual],
    bank: Bank,
    govt: Government,
    rng: _random.Random,
) -> dict[str, float]:
    """
    Individuals buy goods from firms.  Priority: food > energy > shelter.
    Children's food consumption (paid by guardians) is handled here.
    Returns stats with prices and quantities.
    """
    needs = config.consumption_needs()
    stats: dict[str, float] = {}

    # Only non-healthcare firms sell in the goods market
    goods_firms = [f for f in firms if not f.is_healthcare]

    firms_by_good: dict[GoodType, list[Firm]] = {g: [] for g in GOODS}
    for f in goods_firms:
        if f.good_type in firms_by_good:
            firms_by_good[f.good_type].append(f)

    total_sales: dict[str, float] = {g.value: 0.0 for g in GOODS}
    total_revenue: dict[str, float] = {g.value: 0.0 for g in GOODS}
    worker_consumption = 0.0
    capitalist_consumption = 0.0
    total_sales_tax = 0.0

    firm_month_sales: dict[str, float] = {f.id: 0.0 for f in goods_firms}
    firm_month_revenue: dict[str, float] = {f.id: 0.0 for f in goods_firms}

    # Build parent lookup for child food purchasing
    ind_by_id = {i.id: i for i in individuals}

    # Determine consumption needs per individual
    # Children: 0.5x food, 1.0x energy, 1.0x shelter (paid by guardian)
    # Retirees and adults: full consumption
    alive_individuals = [i for i in individuals if i.alive]

    # Shuffle for fairness
    order = list(alive_individuals)
    rng.shuffle(order)

    # TRADEOFF: Shelter is temporarily an infinitely-available good at fixed price.
    # Individuals buy from government; money is destroyed like tax. To revert to
    # market-based shelter with supply-constrained firms, restore the shelter firm
    # loop below and remove the shelter govt branch. See policy.post_shelter_purchase_from_govt.
    shelter_fixed_price = config.shelter_fixed_price

    for good_type in [GoodType.FOOD, GoodType.ENERGY, GoodType.SHELTER]:
        need_base = needs[good_type.value]
        available_firms = firms_by_good[good_type]

        # Shelter: bypass firms, use govt provision (infinite supply, fixed price)
        if good_type == GoodType.SHELTER:
            for ind in order:
                need = need_base if ind.life_stage != LifeStage.CHILD else need_base
                payer = None
                for pid in ind.parent_ids:
                    p = ind_by_id.get(pid)
                    if p and p.alive:
                        payer = p
                        break
                if ind.life_stage != LifeStage.CHILD:
                    payer = ind
                if payer is None:
                    continue
                payer_cash_acct = f"{payer.id}:cash"
                cash = ledger.account_balance(payer_cash_acct)
                if cash <= 0:
                    continue
                qty = min(need, cash / shelter_fixed_price)
                if qty <= 0.001:
                    continue
                cost = qty * shelter_fixed_price
                # Guardian pays for child: transfer from guardian to child (balance sheet neutral)
                if payer.id != ind.id and cost > 0:
                    ledger.post(month, f"Guardian shelter transfer: {payer.id} -> {ind.id}", [
                        (f"{payer.id}:cash", 0, cost),
                        (f"{payer.id}:equity", cost, 0),
                        (f"{ind.id}:cash", cost, 0),
                        (f"{ind.id}:transfer_income", 0, cost),
                    ])
                post_shelter_purchase_from_govt(
                    ledger, month, ind, bank, govt, qty, shelter_fixed_price
                )
                total_sales[good_type.value] += qty
                total_revenue[good_type.value] += cost
                if ind.is_owner:
                    capitalist_consumption += cost
                else:
                    worker_consumption += cost
            continue

        if not available_firms:
            continue

        for ind in order:
            # Determine this individual's need and who pays
            if ind.life_stage == LifeStage.CHILD:
                if good_type == GoodType.FOOD:
                    need = need_base * config.child_food_fraction
                else:
                    need = need_base
                # Guardian pays — find first living parent
                payer = None
                for pid in ind.parent_ids:
                    p = ind_by_id.get(pid)
                    if p and p.alive:
                        payer = p
                        break
                if payer is None:
                    continue  # orphan with no guardian — skip
                payer_cash_acct = f"{payer.id}:cash"
            else:
                need = need_base
                payer = ind
                payer_cash_acct = f"{ind.id}:cash"

            cash = ledger.account_balance(payer_cash_acct)
            if cash <= 0:
                continue

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

                post_goods_sale(ledger, month, bank, firm, ind, good_type, qty, firm.price)

                if ind.life_stage == LifeStage.CHILD and payer is not None and payer.id != ind.id:
                    pass  # We'll handle this below

                # Sales tax
                tax = cost * config.sales_tax_rate
                if tax > 0.01:
                    firm_cash = ledger.account_balance(f"{firm.id}:cash")
                    tax = min(tax, firm_cash)
                    if tax > 0.01:
                        post_sales_tax(ledger, month, govt, bank, firm, tax)
                        total_sales_tax += tax

                remaining_need -= qty
                cash -= cost
                total_sales[good_type.value] += qty
                total_revenue[good_type.value] += cost
                firm_month_sales[firm.id] = firm_month_sales.get(firm.id, 0.0) + qty
                firm_month_revenue[firm.id] = firm_month_revenue.get(firm.id, 0.0) + cost
                if ind.is_owner:
                    capitalist_consumption += cost
                else:
                    worker_consumption += cost

    # Update firm EMAs with monthly totals
    for firm in goods_firms:
        ms = firm_month_sales.get(firm.id, 0.0)
        mr = firm_month_revenue.get(firm.id, 0.0)
        firm.sales = (firm.sales * 0.7) + ms * 0.3
        firm.revenue_ema = (firm.revenue_ema * 0.7) + mr * 0.3

    for g in GOODS:
        stats[f"{g.value}_quantity_sold"] = total_sales[g.value]
        stats[f"{g.value}_revenue"] = total_revenue[g.value]
        if g == GoodType.SHELTER:
            # Shelter is govt-provided at fixed price (see TRADEOFF above)
            stats[f"{g.value}_avg_price"] = shelter_fixed_price
        else:
            gfirms = firms_by_good.get(g, [])
            if gfirms:
                stats[f"{g.value}_avg_price"] = sum(f.price for f in gfirms) / len(gfirms)
            else:
                stats[f"{g.value}_avg_price"] = 0.0

    stats["worker_consumption"] = worker_consumption
    stats["capitalist_consumption"] = capitalist_consumption
    stats["total_sales_tax"] = total_sales_tax

    return stats


def consume_goods(
    ledger: Ledger,
    month: int,
    individuals: list[Individual],
    config: SimConfig,
) -> None:
    """Individuals consume goods from their inventory."""
    needs = config.consumption_needs()
    for ind in individuals:
        if not ind.alive:
            continue
        for good_type in GOODS:
            if ind.life_stage == LifeStage.CHILD and good_type == GoodType.FOOD:
                need = needs[good_type.value] * config.child_food_fraction
            else:
                need = needs[good_type.value]
            inv = ledger.account_balance(f"{ind.id}:inventory:{good_type.value}")
            consumed = min(need, inv)
            if consumed > 0.001:
                post_goods_consumption(ledger, month, ind, good_type, consumed)


def adjust_prices_and_wages(
    config: SimConfig,
    firms: list[Firm],
    unemployment_rate: float,
    ledger: Ledger | None = None,
) -> None:
    """End-of-month price and wage adjustments based on inventory levels."""
    from .production import adjust_price, adjust_wage

    for firm in firms:
        if firm.is_healthcare:
            # Healthcare firms adjust wages but don't have inventory-based pricing
            firm.wage_offer = adjust_wage(
                firm.wage_offer,
                unemployment_rate,
                config.wage_adjustment_speed,
                min_wage=config.min_wage,
            )
            continue

        inventory = 0.0
        if ledger is not None:
            inventory = ledger.account_balance(f"{firm.id}:inventory")
        firm.price = adjust_price(
            firm.price,
            inventory,
            max(1.0, firm.sales),
            config.target_inventory_months,
            config.price_adjustment_speed,
        )
        firm.wage_offer = adjust_wage(
            firm.wage_offer,
            unemployment_rate,
            config.wage_adjustment_speed,
            min_wage=config.min_wage,
        )
