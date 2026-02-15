# Model Assumptions

This document describes the key modelling choices, accounting framework,
and known limitations of VibeSim v0.1.

---

## 1. Accounting Consolidation

### Double-Entry Bookkeeping

Every economic transaction is a balanced journal entry with
`sum(debits) == sum(credits)`. The ledger is append-only; running
balances are maintained incrementally but can be verified by replaying
the full journal.

### Account Types

| Type      | Normal Side | Examples                |
|-----------|-------------|-------------------------|
| Asset     | Debit       | cash, inventory, capital |
| Liability | Credit      | loans_payable, deposits  |
| Equity    | Credit      | equity                  |
| Revenue   | Credit      | labor_income, revenue    |
| Expense   | Debit       | wage_expense, tax_expense |

**Balance sheet equation** (per actor):

    Assets = Liabilities + Equity + Revenue - Expense

This is checked every simulation day for every actor.

### Consolidated Government

The Government actor consolidates the Treasury and Central Bank into
a single entity. This is a deliberate simplification that:

- Avoids modelling intra-government bond operations
- Makes money creation/destruction explicit and auditable
- Aligns with a stock-flow consistent (SFC) / MMT accounting framework

**Consequence**: There is no separate central bank balance sheet or
inter-governmental bond market. Government spending directly credits
bank reserves and deposits; taxation directly debits them.

### Sector Classification

| Sector   | Actors                             |
|----------|------------------------------------|
| Private  | All Individuals + all Firms        |
| Banking  | Bank (single commercial bank)      |
| Government | Consolidated Treasury + CB       |

In a closed economy with no foreign sector:

    Private net worth + Government net worth + Bank net worth
        = Total equity from production (non-financial wealth)

Financial assets net to zero across all sectors; real wealth comes
from production (inventory, capital).

---

## 2. Money Creation and Destruction

VibeSim follows a **chartalist / MMT** money model:

### Creation (Government Spending)

When the government spends:

    Government: DR spending_expense, CR currency_issued
    Bank:       DR reserves,        CR deposits
    Recipient:  DR cash,            CR income

Money is created as a government liability (`currency_issued`) and
simultaneously appears as a bank asset (reserves) and depositor's
asset (cash). No prior "funding" is needed.

### Destruction (Taxation)

When taxes are collected:

    Taxpayer:   DR tax_expense, CR cash
    Bank:       DR deposits,    CR reserves
    Government: DR currency_issued, CR tax_revenue

The process reverses: deposits and reserves shrink, and the government's
outstanding currency liability decreases.

### Implications

- Government deficit = net money creation for the private sector
- Government surplus = net money destruction
- The government does not "run out of money" — it is the currency issuer
- Taxation serves to manage aggregate demand, not to "fund" spending

### What Is NOT Modelled (v0.1)

- **Bank lending / credit creation**: The single bank is a pure
  intermediary; it does not create money through lending.
- **Interest on reserves / deposits**: The interest rate parameter exists
  but is not yet applied to balances.
- **Bond issuance**: Government bonds exist in the ledger schema but are
  not traded.

---

## 3. Production Functions and Pricing

### Production Function

Firms use a **Cobb-Douglas** production function:

    output = A × L^α × K^β

Where:
- `A` = sector-specific productivity parameter
- `L` = number of workers hired that day
- `K` = firm capital stock (ledger balance)
- `α` = labor share (default 0.7)
- `β` = capital share (default 0.3)

If either L or K is zero, output is zero.

**Note**: α + β = 1.0 (constant returns to scale). This is a standard
assumption but means there are no economies of scale.

### Capital

Capital is endowed at simulation start and does not depreciate in v0.1.
There is no investment decision — firms cannot purchase new capital.
This means the capital stock is fixed throughout the simulation.

### Inventory Management

Firms target `avg_daily_sales × target_inventory_days` units of inventory.
If inventory falls below target, they increase production (hire more).
Production creates inventory at a nominal value of $1/unit in the ledger.

### Pricing Rule

Firms adjust prices daily based on an inventory-ratio rule:

    ratio = current_inventory / target_inventory
    new_price = old_price × (1 + (1 - ratio) × adjustment_speed)

- If `ratio > 1` (excess inventory) → price falls
- If `ratio < 1` (shortage) → price rises
- Prices have a minimum floor (default $0.50)

This is a simple adaptive rule, **not** a marginal-cost-based price.

### Wage Adjustment (Phillips Curve)

Wages adjust based on the gap between actual and target unemployment:

    gap = target_unemployment - actual_unemployment
    new_wage = old_wage × (1 - gap × adjustment_speed)

- Low unemployment → wages rise
- High unemployment → wages fall
- Wages have a minimum floor (min_wage parameter)

---

## 4. Market Clearing

### Labor Market

1. Each firm computes desired labor from its production target.
2. Demand is constrained by firm cash (can't hire if can't pay).
3. Workers (excluding firm owners) are shuffled randomly.
4. Firms are sorted by wage offer (highest first).
5. Workers are allocated to firms greedily until demand is met.
6. Wage payment is posted as a journal entry immediately.

**Limitations**:
- Workers don't choose between firms; assignment is random + greedy.
- No skill heterogeneity or search frictions.
- Employment resets daily (no contracts or sticky employment).

### Goods Market

1. Individuals are shuffled for fairness.
2. Goods are purchased in priority order: food > energy > shelter.
3. For each good, the individual buys from the cheapest firm with stock.
4. Purchase quantity is min(need, inventory, affordable).
5. Sales tax is collected from the firm on each transaction.

**Limitations**:
- No saving/consumption optimization — individuals buy up to their
  daily need if they can afford it.
- No credit purchases; individuals can only spend available cash.

---

## 5. Known Limitations

### Structural

1. **No bank lending**: Money supply is determined entirely by government
   fiscal policy. Endogenous money creation through credit is absent.
2. **No capital accumulation**: Firms cannot invest in new capital.
   The economy cannot grow its productive capacity endogenously.
3. **No depreciation**: Capital does not decay, which is unrealistic for
   long-run simulations.
4. **Single bank**: No interbank market, no bank competition.
5. **Closed economy**: No imports, exports, or exchange rates.

### Behavioral

6. **No expectations**: Agents use simple adaptive rules, not
   forward-looking optimization or rational expectations.
7. **No saving behavior**: Individuals spend up to their daily need
   each day; there is no intertemporal consumption smoothing.
8. **Homogeneous labor**: All workers are identical in productivity.
9. **Daily reset**: Employment is re-matched every day with no
   hiring/firing costs.

### Numerical

10. **Floating-point**: The ledger uses `float64`. Over very long runs
    (10,000+ days) with many agents, accumulated rounding may cause
    balance-check tolerances to be approached. The EPSILON is 1e-6.
11. **Inventory valuation**: Inventory is tracked at $1/unit nominal
    regardless of market price. This creates an equity adjustment
    on every sale (the difference between market price and nominal).

---

## 6. What Is Next

Planned for future versions:

- **Bank lending and credit creation**: Endogenous money supply via
  commercial bank loans.
- **Capital investment**: Firms purchase capital, creating an
  accelerator mechanism.
- **Depreciation**: Capital decays over time, requiring reinvestment.
- **Bond market**: Government bonds traded between bank and agents.
- **Interest rate policy**: Central bank sets rate; deposits/loans accrue.
- **Open economy**: Foreign sector with trade and exchange rates.
- **Heterogeneous agents**: Different skill levels, preferences, sectors.
- **Expectation formation**: Adaptive or model-consistent expectations.

---

*Document version: 0.1.0 — February 2026*
