# Model Assumptions

This document describes the modelling choices, economic framework,
and known limitations of VibeSim v0.1.

---

## 1. Purpose and Scope

VibeSim is a sandbox for exploring how fiscal and monetary policy
affect a simulated economy. It models a closed economy with:

- **Workers** who earn wages and consume goods
- **Firms** that produce food, energy, and shelter using labor and capital
- **A bank** that intermediates financial flows
- **A government** that spends money into existence, collects taxes, and makes transfers

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

### What Is NOT Modelled (v0.1)

- **Bank lending / credit creation**: The bank is a pure intermediary.
- **Interest on reserves / deposits**: The rate parameter exists but isn't applied yet.
- **Bond trading**: Government bonds exist in the schema but are not traded.

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

## 3. Production and Pricing

### Production Function

Firms use a **Cobb-Douglas** production function:

    output = A × L^α × K^β

- `A` = sector-specific productivity
- `L` = workers hired that day
- `K` = firm capital stock
- `α` = labor share (default 0.7), `β` = capital share (default 0.3)

If either L or K is zero, output is zero.

### Capital

Capital is endowed at startup and does not depreciate. There is no
investment decision — the capital stock is fixed.

### Inventory and Pricing

Firms target `avg_daily_sales × target_inventory_days` units of inventory.
Prices adjust daily based on the inventory-to-target ratio:

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

## 4. Market Clearing

### Labor Market

1. Firms compute desired labor from their production target
2. Demand is constrained by firm cash (can't hire without funds)
3. Workers are shuffled randomly; firms sorted by wage (highest first)
4. Workers allocated greedily until each firm's demand is met
5. Wages paid immediately via ledger entry

**Limitations**: No skill heterogeneity, no search frictions, employment
resets daily (no contracts).

### Goods Market

1. Individuals shuffled for fairness
2. Goods purchased in priority: food > energy > shelter
3. Buy from cheapest firm with stock
4. Quantity = min(need, available inventory, affordable)
5. Sales tax collected per transaction

**Limitations**: Fixed daily needs (no demand elasticity), no credit
purchases, no saving/investment optimization.

---

## 5. Known Limitations

### Structural
1. **No bank lending** — money supply determined entirely by fiscal policy
2. **No capital accumulation** — firms cannot invest in new capital
3. **No depreciation** — capital doesn't decay
4. **Single bank** — no interbank market
5. **Closed economy** — no trade or exchange rates

### Behavioral
6. **No expectations** — agents use simple adaptive rules
7. **Fixed consumption needs** — no demand elasticity or luxury goods
8. **Homogeneous labor** — all workers identical
9. **Daily employment reset** — no hiring/firing costs

### Numerical
10. **Float64 precision** — over very long runs (10,000+ days) with many
    agents, accumulated rounding may approach tolerance thresholds
11. **Inventory at $1/unit** — creates equity adjustments on every sale
    when market price differs from nominal

---

## 6. Planned Extensions

- Bank lending and endogenous credit creation
- Capital investment with an accelerator mechanism
- Depreciation requiring reinvestment
- Bond market between government, bank, and agents
- Interest rate policy
- Open economy with trade and exchange rates
- Heterogeneous agents (skills, preferences)
- Demand elasticity (luxury consumption, savings)

---

*Document version: 0.1.0 — February 2026*
