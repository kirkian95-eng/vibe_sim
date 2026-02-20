"""
Market clearing mechanisms for labor and goods.

Markets operate each simulation month.  All transactions are posted as
balanced journal entries on the shared ledger.
"""

from __future__ import annotations

import random as _random

from .actors import GOODS, Bank, ConstructionProject, Firm, GoodType, Government, Individual, LifeStage
from .config import SimConfig
from .ledger import Ledger
from .policy import post_sales_tax
from .production import cobb_douglas, desired_labor, firm_target_output

# ── Transaction helpers ─────────────────────────────────────────────


def post_payroll_loan(
    ledger: Ledger,
    month: int,
    bank: Bank,
    firm: Firm,
    amount: float,
) -> None:
    """
    Bank extends a loan to a firm short on deposits. Creates new bank credit.
    Bank: DR loans_receivable, CR deposits
    Firm: DR cash (deposits), CR loans_payable
    """
    if amount <= 0:
        return
    ledger.post(month, f"Payroll loan: {bank.id} -> {firm.id}", [
        (f"{bank.id}:loans_receivable", amount, 0),
        (f"{bank.id}:deposits", 0, amount),
        (f"{firm.id}:cash", amount, 0),
        (f"{firm.id}:loans_payable", 0, amount),
    ])


def post_wage_payment(
    ledger: Ledger,
    month: int,
    bank: Bank,
    firm: Firm,
    worker: Individual,
    amount: float,
) -> None:
    """
    Firm pays worker from its deposits. If firm is short, bank extends a
    payroll loan first. Money moves within the banking system.
    """
    cash = ledger.account_balance(f"{firm.id}:cash")
    shortfall = amount - cash
    if shortfall > 0.01:
        post_payroll_loan(ledger, month, bank, firm, shortfall)
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


def post_rent_payment(
    ledger: Ledger,
    month: int,
    bank: Bank,
    firm: Firm,
    payer: Individual,
    tenant: Individual,
    quantity: float,
    price_per_unit: float,
) -> None:
    """
    Rent payment: tenant pays landlord firm for housing.
    Housing units stay with the firm (durable asset). No inventory transfer.
    If payer != tenant (guardian paying for child), the guardian transfer is
    handled first, then the tenant pays the firm.
    """
    total = quantity * price_per_unit
    if total <= 0:
        return

    # If guardian is paying for a child, transfer money first
    if payer.id != tenant.id:
        ledger.post(month, f"Guardian rent transfer: {payer.id} -> {tenant.id}", [
            (f"{payer.id}:cash", 0, total),
            (f"{payer.id}:equity", total, 0),
            (f"{tenant.id}:cash", total, 0),
            (f"{tenant.id}:transfer_income", 0, total),
        ])

    # Tenant pays rent to firm. Shelter inventory goes to tenant for consumption
    # tracking, but housing_asset stays with firm (durable). Same pattern as goods sale.
    diff = total - quantity
    if diff >= 0:
        tenant_lines = [
            (f"{tenant.id}:inventory:shelter", quantity, 0),
            (f"{tenant.id}:cash", 0, total),
            (f"{tenant.id}:equity", diff, 0),
        ]
    else:
        tenant_lines = [
            (f"{tenant.id}:inventory:shelter", quantity, 0),
            (f"{tenant.id}:cash", 0, total),
            (f"{tenant.id}:equity", 0, -diff),
        ]
    ledger.post(month, f"Rent: {tenant.id} pays {firm.id} {quantity:.1f} shelter", tenant_lines)

    # Firm receives rent revenue (no inventory deduction — housing is durable)
    ledger.post(month, f"Rent revenue: {firm.id} from {tenant.id}", [
        (f"{firm.id}:cash", total, 0),
        (f"{firm.id}:revenue", 0, total),
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


# ── Housing development ────────────────────────────────────────────


def run_housing_development(
    ledger: Ledger,
    month: int,
    config: SimConfig,
    firms: list[Firm],
) -> dict[str, float]:
    """
    Monthly housing construction cycle for shelter firms.

    1. Complete finished projects (add units to housing stock)
    2. Tick active projects (pay monthly cost, decrement timer)
    3. Start new projects if vacancy is low and firm can afford it

    Returns dict with housing_starts, housing_completions.
    """
    shelter_firms = [f for f in firms if f.good_type == GoodType.SHELTER]
    total_starts = 0
    total_completions = 0

    for firm in shelter_firms:
        # --- Phase 1: Complete finished projects ---
        remaining = []
        for project in firm.construction_projects:
            if project.months_remaining <= 0:
                firm.housing_units += project.units
                ledger.post(month, f"Construction complete: {firm.id} +{project.units} units", [
                    (f"{firm.id}:housing_asset", project.units, 0),
                    (f"{firm.id}:equity", 0, project.units),
                ])
                total_completions += project.units
            else:
                remaining.append(project)
        firm.construction_projects = remaining

        # --- Phase 2: Tick active projects (pay costs, decrement timer) ---
        for project in firm.construction_projects:
            firm_cash = ledger.account_balance(f"{firm.id}:cash")
            if firm_cash >= project.monthly_cost:
                ledger.post(month, f"Construction cost: {firm.id}", [
                    (f"{firm.id}:input_expense", project.monthly_cost, 0),
                    (f"{firm.id}:cash", 0, project.monthly_cost),
                ])
                project.months_remaining -= 1
            # else: paused — insufficient funds

        # --- Phase 3: Start new projects if vacancy is low ---
        demand_proxy = max(1.0, firm.sales)
        vacancy = firm.housing_units - demand_proxy
        vacancy_rate = vacancy / max(1.0, firm.housing_units)

        if vacancy_rate < config.housing_construction_vacancy_threshold:
            target_vacancy = config.housing_construction_vacancy_threshold
            target_units = demand_proxy / (1.0 - target_vacancy)
            units_under_construction = sum(p.units for p in firm.construction_projects)
            gap = target_units - (firm.housing_units + units_under_construction)
            max_starts = max(1, int(firm.housing_units * config.housing_construction_max_starts_fraction))
            starts = min(max(0, int(gap)), max_starts)

            if starts > 0:
                cost_per_unit = config.housing_construction_cost_per_unit
                total_cost = starts * cost_per_unit
                monthly_cost = total_cost / max(1, config.housing_construction_months)

                firm_cash = ledger.account_balance(f"{firm.id}:cash")
                if firm_cash >= monthly_cost:
                    project = ConstructionProject(
                        units=starts,
                        months_remaining=config.housing_construction_months,
                        total_cost=total_cost,
                        monthly_cost=monthly_cost,
                        workers_needed=config.housing_construction_workers_per_project,
                    )
                    firm.construction_projects.append(project)
                    total_starts += starts

    return {
        "housing_starts": total_starts,
        "housing_completions": total_completions,
    }


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

    # Compute labor demand per firm.
    # Shelter firms excluded when govt provides shelter (see TRADEOFF in clear_goods_market)
    productivities = config.productivity()
    labor_demands: list[tuple[Firm, int]] = []
    hc_firms = [f for f in firms if f.is_healthcare]
    num_hc = len(hc_firms)

    for firm in firms:
        if firm.is_healthcare:
            # Healthcare hiring scaled to retiree demand (elder visits).
            retirees = sum(1 for i in individuals if i.alive and i.life_stage == LifeStage.RETIRED)
            workers_needed = int((retirees + config.healthcare_productivity - 1) // config.healthcare_productivity)
            per_firm = int((workers_needed + num_hc - 1) // num_hc) if num_hc else 0
            wanted = per_firm
        elif firm.good_type == GoodType.SHELTER:
            # Shelter firms need maintenance + construction workers.
            units = firm.housing_units
            maintenance = max(1, int(units / 20) + 1)
            construction = sum(
                p.workers_needed
                for p in firm.construction_projects
                if p.months_remaining > 0
            )
            wanted = maintenance + construction
        else:
            inventory = ledger.account_balance(f"{firm.id}:inventory")
            # Demand-driven target: expected sales = consumption demand / firms producing this good
            alive = [i for i in individuals if i.alive]
            needs = config.consumption_needs()
            num_children = sum(1 for i in alive if i.life_stage == LifeStage.CHILD)
            num_adults_retired = len(alive) - num_children

            if firm.good_type == GoodType.FOOD:
                demand = num_adults_retired * needs["food"] + num_children * needs["food"] * config.child_food_fraction
                num_firms = len([f for f in firms if f.good_type == GoodType.FOOD])
            elif firm.good_type == GoodType.ENERGY:
                demand = len(alive) * needs["energy"]
                num_firms = len([f for f in firms if f.good_type == GoodType.ENERGY])
            else:
                demand = len(alive) * needs.get(firm.good_type.value, 1.0)
                num_firms = len([f for f in firms if f.good_type == firm.good_type])

            expected_sales = max(1.0, demand / max(1, num_firms))
            avg_sales = max(1.0, firm.sales if firm.sales > 0 else expected_sales)
            target = firm_target_output(inventory, avg_sales, config.target_inventory_months)
            labor_needed = desired_labor(
                target,
                productivities[firm.good_type.value],
                ledger.account_balance(f"{firm.id}:capital"),
                config.labor_share,
                config.capital_share,
            )
            wanted = max(int(labor_needed) + 1, 1)

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
    total_labor_force = len(workers)

    # Frictional unemployment: remove a fraction of workers from the hiring pool.
    # These workers are "between jobs" — separated and searching, unavailable this month.
    sep_rate = config.job_separation_rate
    if sep_rate > 0 and total_labor_force > 0:
        num_separated = max(0, round(total_labor_force * sep_rate))
        if num_separated > 0:
            workers = workers[:-num_separated]

    # Hiring order:
    #   1. Healthcare (priority — elder care demand)
    #   2. Shelter maintenance (small, fixed)
    #   3. Goods firms (food, energy) — proportional to demand so no sector is starved
    priority_demands = []
    goods_demands = []
    for f, d in labor_demands:
        if f.is_healthcare or f.good_type == GoodType.SHELTER:
            priority_demands.append((f, d))
        else:
            goods_demands.append((f, d))
    # Healthcare first, then shelter, sorted by wage within each group
    priority_demands.sort(key=lambda x: (0 if x[0].is_healthcare else 1, -x[0].wage_offer))

    worker_idx = 0
    total_hired = 0
    total_wages = 0.0

    def _hire_workers(firm: Firm, target: int) -> None:
        nonlocal worker_idx, total_hired, total_wages
        hired = 0
        while hired < target and worker_idx < len(workers):
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

    # Phase 1: Priority hiring (healthcare, shelter)
    for firm, demand in priority_demands:
        _hire_workers(firm, demand)

    # Phase 2: Goods firms get proportional share of remaining workers
    available = len(workers) - worker_idx
    total_goods_demand = sum(d for _, d in goods_demands)
    if total_goods_demand > 0 and available > 0:
        # Sort by wage for consistent ordering
        goods_demands.sort(key=lambda x: -x[0].wage_offer)
        allocated_so_far = 0
        for i, (firm, demand) in enumerate(goods_demands):
            if total_goods_demand <= available:
                alloc = demand
            elif i == len(goods_demands) - 1:
                alloc = available - allocated_so_far
            else:
                alloc = max(1, round(demand * available / total_goods_demand))
                alloc = min(alloc, available - allocated_so_far)
            _hire_workers(firm, alloc)
            allocated_so_far += alloc

    unemployment_rate = 1.0 - (total_hired / max(total_labor_force, 1))

    return {
        "total_hired": total_hired,
        "total_workers": total_labor_force,
        "unemployment_rate": unemployment_rate,
        "total_wages": total_wages,
    }


def run_production(
    ledger: Ledger,
    month: int,
    config: SimConfig,
    firms: list[Firm],
) -> None:
    """Each non-healthcare firm produces output based on its labor and capital.

    After production, capital depreciates for goods-producing firms.
    """
    productivities = config.productivity()
    for firm in firms:
        if firm.is_healthcare:
            firm.production = 0.0
            continue
        if firm.good_type == GoodType.SHELTER:
            firm.production = 0.0
            continue  # housing is a durable asset; no monthly production
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

        # Capital depreciation
        if config.capital_depreciation_rate > 0 and capital > 0:
            depreciation = capital * config.capital_depreciation_rate
            if depreciation > 0.01:
                ledger.post(month, f"Depreciation: {firm.id}", [
                    (f"{firm.id}:depreciation_expense", depreciation, 0),
                    (f"{firm.id}:capital", 0, depreciation),
                ])


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
    Shelter is a rental market: individuals pay rent to shelter firms, but
    housing units stay with the firm (durable asset, not consumed).
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

    alive_individuals = [i for i in individuals if i.alive]

    # Shuffle for fairness
    order = list(alive_individuals)
    rng.shuffle(order)

    for good_type in [GoodType.FOOD, GoodType.ENERGY, GoodType.SHELTER]:
        need_base = needs[good_type.value]
        available_firms = firms_by_good[good_type]

        if not available_firms:
            continue

        # Shelter: rental market — capacity is housing_units, not inventory
        if good_type == GoodType.SHELTER:
            # Track how many units have been rented this month per firm
            units_rented: dict[str, float] = {f.id: 0.0 for f in available_firms}
            for ind in order:
                need = need_base
                # Determine payer (guardian for children)
                if ind.life_stage == LifeStage.CHILD:
                    payer = None
                    for pid in ind.parent_ids:
                        p = ind_by_id.get(pid)
                        if p and p.alive:
                            payer = p
                            break
                    if payer is None:
                        continue
                else:
                    payer = ind

                cash = ledger.account_balance(f"{payer.id}:cash")
                if cash <= 0:
                    continue

                available_firms.sort(key=lambda f: f.price)
                remaining_need = need

                for firm in available_firms:
                    if remaining_need <= 0:
                        break
                    capacity = firm.housing_units - units_rented[firm.id]
                    if capacity <= 0:
                        continue

                    qty = min(remaining_need, capacity)
                    cost = qty * firm.price
                    if cost > cash:
                        qty = cash / firm.price
                        cost = qty * firm.price
                    if qty <= 0.001:
                        continue

                    # Rent payment: money flows, but no inventory transfer.
                    # Payer pays, firm receives revenue. Shelter inventory stays.
                    post_rent_payment(ledger, month, bank, firm, payer, ind, qty, firm.price)

                    # Sales tax on rent
                    tax = cost * config.sales_tax_rate
                    if tax > 0.01:
                        firm_cash = ledger.account_balance(f"{firm.id}:cash")
                        tax = min(tax, firm_cash)
                        if tax > 0.01:
                            post_sales_tax(ledger, month, govt, bank, firm, tax)
                            total_sales_tax += tax

                    units_rented[firm.id] += qty
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
            continue

        # Food and energy: standard goods market with inventory
        for ind in order:
            if ind.life_stage == LifeStage.CHILD:
                if good_type == GoodType.FOOD:
                    need = need_base * config.child_food_fraction
                else:
                    need = need_base
                payer = None
                for pid in ind.parent_ids:
                    p = ind_by_id.get(pid)
                    if p and p.alive:
                        payer = p
                        break
                if payer is None:
                    continue
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
            firm.wage_offer = adjust_wage(
                firm.wage_offer,
                unemployment_rate,
                config.wage_adjustment_speed,
                min_wage=config.min_wage,
            )
            continue

        if firm.good_type == GoodType.SHELTER:
            # Shelter firms adjust rent based on vacancy rate.
            # High vacancy (units > demand) → lower rent. Low vacancy → raise rent.
            # Use sales EMA as proxy for demand; housing_units as supply.
            demand_proxy = max(1.0, firm.sales)
            vacancy = firm.housing_units - demand_proxy
            vacancy_rate = vacancy / max(1.0, firm.housing_units)
            # If vacancy > 0, excess supply → lower price. If < 0, shortage → raise.
            adj = -vacancy_rate * config.price_adjustment_speed
            adj = max(-config.price_adjustment_speed, min(adj, config.price_adjustment_speed))
            firm.price = max(10.0, firm.price * (1.0 + adj))
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
