# Model Assumptions

This document describes the modelling choices, economic framework,
and known limitations of VibeSim v0.2.

---

## 1. Purpose and Scope

VibeSim is a sandbox for exploring how fiscal and monetary policy
affect a simulated economy. It models a closed economy with:

- **Individuals** who are born, age, work, retire, and die
- **Firms** — one per good type (food, energy, healthcare) plus landlord firms (shelter). Firms use labor and capital; they do not compete strategically — prices adjust reactively to inventory/vacancy.
- **A bank** that intermediates financial flows and extends loans to firms (and individuals) short on deposits
- **A government** that spends money into existence, collects taxes, pays pensions, funds healthcare, and issues bonds

The simulation is designed for experimentation, not forecasting. Default
parameters are starting points — users should tune them for their
research questions.

### Money Model (MMT / Chartalist)

VibeSim follows a Modern Monetary Theory framework:

- Government spending **creates** money (credited to bank deposits)
- Taxation **destroys** money (debited from deposits)
- Government deficit = net money injected into the private sector
- The government cannot "run out of money" — it is the currency issuer
- Taxation manages aggregate demand, not "funding"
- Government bonds allow deposit holders to swap cash for interest-bearing assets

### Bank Lending

Firms and individuals hold deposits at the bank. When short on cash (e.g. payroll),
the bank extends loans: Bank DR loans_receivable, CR deposits; Firm DR cash, CR loans_payable.
Loan creation expands bank credit (deposits). Firms repay from excess cash each month.

### What Is NOT Modelled

- **Interest on bank loans**: Loan principal is tracked but interest is not charged yet.
- **Interest on reserves / deposits**: The rate parameter exists but isn't applied yet.
- **Capital accumulation**: Firms cannot invest in new capital; capital stock is fixed at startup.
- **Depreciation**: Capital doesn't decay over time.

---

## 2. Government (Consolidated Treasury + Central Bank)

The Government actor combines Treasury and Central Bank into a single
entity. This simplification:

- Makes money creation/destruction explicit
- Avoids intra-government bond operations
- Aligns with stock-flow consistent (SFC) modelling

**Sector classification:**

| Sector | Actors |
|--------|--------|
| Private | All Individuals + all Firms |
| Banking | Bank (single commercial bank) |
| Government | Consolidated Treasury + CB |

---

## 3. Demographics

### Life Stages

Each individual has an age (in months) and a life stage:

| Stage | Age Range | Behavior |
|-------|-----------|----------|
| CHILD | 0–17 years (< 216 months) | Does not work. Consumes 50% of adult food, paid by guardian. |
| ADULT | 18–64 years (216–779 months) | Works, consumes, may have children. |
| RETIRED | 65+ years (≥ 780 months) | Receives pension, consumes, faces mortality risk from age 72. |

### Initial Population

At startup, ages are distributed uniformly across 1–72 years. This produces
a mix of children, working-age adults, and retirees from month 1.

### Fertility

- Eligible adults (18–64, alive, no cooldown) are randomly paired each month
- Each pair has a chance of producing a child based on `fertility_rate_annual`
- After birth: 12-month fertility cooldown and a parenting labor penalty (0.5× wage) for a configurable number of months
- Births incur a healthcare fee paid to a healthcare firm

### Mortality

- Mortality hazard begins at `mortality_start_age` (default: 72 years)
- Constant monthly hazard calibrated so expected death age = `target_death_age` (default: 80)
- On death: individual marked as not alive, estate (cash) transferred to a random living adult

### Aging and Transitions

Each month, `advance_ages()` increments every living individual's age by 1 month.
When an individual crosses a life-stage boundary (18 years, retirement age),
their stage transitions automatically. New retirees leave the labor force.

---

## 4. Production and Pricing

### Production Function

Firms use a **Cobb-Douglas** production function:

    output = A × L^α × K^β

- `A` = sector-specific productivity
- `L` = workers hired that month
- `K` = firm capital stock
- `α` = labor share (default 0.7), `β` = capital share (default 0.3)

If either L or K is zero, output is zero.

### Capital

Capital is endowed at startup and does not depreciate. There is no
investment decision — the capital stock is fixed.

### Inventory and Pricing

Firms target `avg_monthly_sales × target_inventory_months` units of inventory.
Prices adjust monthly based on the inventory-to-target ratio:

    ratio = current_inventory / target_inventory
    new_price = old_price × (1 + (1 - ratio) × adjustment_speed)

- Excess inventory → price falls
- Shortage → price rises
- Minimum price floor of $0.50

### Wage Adjustment (Phillips Curve)

Wages respond to the gap between actual and target unemployment:

    gap = target_unemployment - actual_unemployment
    new_wage = old_wage × (1 + gap × adjustment_speed)

- Low unemployment → wages rise
- High unemployment → wages fall
- Minimum wage floor applies

---

## 5. Government Bonds

Each month, the government issues bonds to cover its deficit:

1. **Bond supply** = max(0, government deficit for the month)
2. **Bond demand** = individuals offer a fraction of their deposits
3. **Clearing**: A bisection algorithm finds the market-clearing interest rate within `[rate_min, rate_max]`
4. **Settlement**: Buyers swap deposits for bond assets; government records bonds issued
5. **Interest**: Monthly coupon = annual_rate / 12 × bond_holdings, paid to each bondholder via money creation

Bonds are a financial portfolio choice — they convert liquid deposits into
interest-bearing government liabilities.

---

## 6. Healthcare

Healthcare firms produce capacity using labor (Cobb-Douglas, same as other firms).

- **Elder care**: The government pays for monthly healthcare visits for retirees, subject to capacity constraints
- **Childbirth**: Each birth incurs a healthcare fee paid from the parent's deposits
- **Shortage tracking**: If healthcare demand exceeds capacity, the shortfall is recorded in monthly metrics

---

## 7. Pensions

All retired individuals receive a monthly pension:

    pension = pension_replacement_rate × average_wage

- Default replacement rate: 50%
- Pensions are funded by government money creation (consistent with MMT)
- Pension payments are recorded as government transfers in the ledger

---

## 8. Market Clearing

### Labor Market

1. Firms compute desired labor from their production target
2. Demand is constrained by firm cash (can't hire without funds)
3. Workers are shuffled randomly; firms sorted by wage (highest first)
4. Workers allocated greedily until each firm's demand is met
5. Wages paid immediately via ledger entry
6. Only living adults are eligible for employment

**Limitations**: No skill heterogeneity, no search frictions, employment
resets monthly (no contracts).

### Goods Market

1. Individuals shuffled for fairness
2. Goods purchased in priority: food > energy > shelter
3. Buy from cheapest firm with stock (food/energy) or lowest rent (shelter)
4. Quantity = min(need, available inventory or housing capacity, affordable)
5. Sales tax collected per transaction
6. Guardians pay for their children's food (at 50% of adult quantity) and shelter

**Shelter (Rental Market)**: Shelter firms own durable housing stock. Individuals
pay monthly rent; housing units stay with the firm (not consumed). Rent prices
adjust based on vacancy rate rather than inventory. Shelter firms hire
maintenance workers proportional to housing stock.

**Limitations**: Fixed monthly needs (no demand elasticity), no consumer
credit for purchases, no saving/investment optimization. No home ownership
or mortgages yet.

---

## 9. Known Limitations

### Structural
1. **Capital accumulation** — firms cannot invest in new capital; stock is fixed
2. **No depreciation** — capital doesn't decay
3. **Single bank** — no interbank market
4. **Closed economy** — no trade or exchange rates

### Behavioral
5. **No expectations** — agents use simple adaptive rules
6. **Fixed consumption needs** — no demand elasticity or luxury goods
7. **Homogeneous labor** — all workers identical
8. **Monthly employment reset** — no hiring/firing costs

### Numerical
9. **Float64 precision** — over very long runs (1,000+ months) with many
    agents, accumulated rounding may approach tolerance thresholds
10. **Inventory at $1/unit** — creates equity adjustments on every sale
    when market price differs from nominal

---

## 10. Planned Extensions (v0.3 in progress)

- Housing development — shelter firms build new units with labor and capital
- Firm equity — shareholders, stock market, profit distribution overhaul
- Firm insolvency — liquidation, restructuring, bailouts
- Manager job type — credential-gated, 1:5 ratio to workers
- College — institution that produces credentials, govt-funded
- Childcare and schools — affects parental labor supply

### Future (v0.4+)

- Fiscal and monetary policy stabilizers
- Central bank with dual mandate
- Open economy with trade and exchange rates
- Heterogeneous agents (skills, preferences)
- Demand elasticity (luxury consumption, savings)
- Immigration and emigration

---

*Document version: 0.3.0-dev — February 2026*
