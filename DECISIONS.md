# Design Decisions & Tradeoffs

This document records the key design decisions made during development, the alternatives considered, and why we chose what we chose. It serves as institutional memory so future changes don't accidentally undo past reasoning.

---

## Money Creation Model (MMT Framing)

**Decision:** Government spending creates money; taxation destroys it. The government is never revenue-constrained.

**Why:** This is the simplest internally consistent monetary model for a closed economy. It avoids the chicken-and-egg problem of "where does the first dollar come from?" and lets us study fiscal policy effects without modeling a complex banking system. The bank exists to intermediate (payroll loans, deposits) but is not the primary money creator.

**Tradeoff:** The model cannot study money-multiplier effects or bank reserve constraints. That's fine for v0.2-v0.3; a richer banking model can be added in v0.4.

---

## One Firm Per Good Type (Scaling via Demand)

**Decision:** The economy has exactly 1 food firm, 1 energy firm, 1 shelter firm, and 1 healthcare firm. Scaling is achieved by adjusting demand (population), not firm count.

**Why:** Firms don't compete strategically in this model — prices adjust reactively to inventory levels. Adding more firms of the same type doesn't change economic dynamics, it just splits the same demand across more entities and slows the simulation. All parameters are rates and ratios, so results are indifferent to population size.

**Tradeoff:** No inter-firm competition, no market concentration dynamics. Acceptable for a policy sandbox; could add competitive dynamics later if needed.

---

## Housing as Durable Asset (Rental Market)

**Decision:** Shelter firms own housing units as durable assets that persist across months. Individuals rent, they don't buy. Housing units are not consumed like food/energy.

**Alternatives considered:**
1. Government provides shelter directly (v0.22 "shelter nerf") — too simple, no market dynamics
2. Individuals buy housing — requires mortgages, home equity tracking, much more complex
3. Rental market with landlord firms — middle ground with real market dynamics

**Why:** The rental model gives us vacancy rates, rent adjustment, construction feedback loops, and a revenue stream for shelter firms — all without the complexity of a mortgage market. Mortgages can be added later as an extension.

**Tradeoff:** No homeownership, no wealth effects from property values. The model cannot study housing bubbles or mortgage crises yet.

---

## Housing Construction Pipeline

**Decision:** Shelter firms start multi-month construction projects when vacancy drops below 10%. Projects cost cash (spread over months), require workers, and add units on completion.

**Why:** This creates the key feedback loop: low vacancy -> high rents -> firm revenue grows -> firm starts construction -> hires workers -> months pass -> units complete -> vacancy rises -> rents stabilize. Without this, housing stock is fixed and population growth creates a permanent shortage.

**Tradeoff:** Construction is cash-funded only (no construction loans). The vacancy threshold and cost parameters are calibrated for 1000-agent baseline but may need tuning for very small populations.

---

## Capital Investment: Maintenance + Demand-Driven

**Decision:** Firms invest in capital each month from available cash. Investment has two components:
- **Maintenance** (`firm_min_investment_rate` x K, default 2%/month) — offsets depreciation with a small growth bias
- **Demand-driven** (`firm_investment_rate` x K x shortage, default up to 10%/month) — scales with how far inventory is below target

Investment runs before loan repayment and is capped at 30% of cash.

**Alternatives considered:**
1. **Profit-based investment** (invest fraction of undistributed profit) — rejected because bootstrap government spending shows up as cumulative revenue, creating artificially high "profit" in early months that triggers massive over-investment
2. **Cash-pool with payroll buffer** (invest spare cash beyond 2 months payroll) — rejected because firms run on payroll loans and never accumulate spare cash above the buffer
3. **Bank-financed investment loans** — considered but deferred; adds complexity and the current model captures the key dynamics

**Why the current approach works:**
- Capital-proportional investment is stable (no bootstrap artifacts)
- The 30% cash cap prevents starving operations
- Running before loan repayment ensures firms have cash to invest (loan repayment takes all remaining cash)
- Maintenance rate (2%) minus depreciation (1%) = ~1% net monthly growth (~12% annual), which is reasonable
- Demand-driven component responds to inventory shortages, so firms grow capacity when needed

**Tradeoff:** Firms invest from existing cash only, not from borrowed funds. This means unprofitable firms (negative cash flow) can still invest their maintenance amount from whatever cash they have, but cannot fund expansion. A credit-financed investment mechanism would be more realistic but is deferred.

---

## Capital Depreciation

**Decision:** Capital depreciates at 1% per month (~12% annual) after production each period. Ledger entry: DR depreciation_expense, CR capital.

**Why:** Without depreciation, capital is a free lunch — bootstrapped once and used forever. Depreciation creates the need for ongoing investment and makes capital a real economic cost. The 1%/month rate implies ~8-year useful life for capital goods, which is reasonable for a mixed economy.

**Tradeoff:** Depreciation is a straight-line fraction of current capital, not based on usage or age of specific assets. Simpler than vintage capital models but sufficient for macro dynamics.

---

## Frictional Unemployment (Job Separation Rate)

**Decision:** Each month, a fraction of the labor force (`job_separation_rate`, default 3%) is removed from the hiring pool before matching. These workers are "between jobs" and unavailable this period.

**Why:** Without frictional unemployment, the model shows 0% unemployment whenever labor demand exceeds supply, which is unrealistic. Real economies always have some workers transitioning between jobs. The separation approach is simpler than modeling individual job search with matching frictions.

**Tradeoff:** Workers are randomly separated, not based on firm performance or individual characteristics. All separated workers return to the pool next month. No long-term unemployment or hysteresis effects.

---

## Wage-Indexed Fiscal Policy (Real Dollars)

**Decision:** Government transfers and spending are multiplied by `avg_wage / initial_wage` each month. This keeps fiscal policy in "real dollars" as the economy evolves.

**Why:** Without indexing, fixed-dollar transfers ($300/month) become meaningless as wages grow. A $300 transfer matters when wages are $2400 but is trivial when wages reach $5000. Similarly, government spending of $150k/month doesn't scale with the economy. Indexing to average wages ensures fiscal policy maintains constant real purchasing power.

**Alternatives considered:**
1. CPI indexing — we don't have a clean CPI yet; wages are a simpler proxy
2. GDP indexing — GDP is noisier than wages
3. Manual adjustment — defeats the purpose of automatic stabilization

**Tradeoff:** If wages diverge from prices (e.g., during a productivity boom), fiscal policy may over- or under-compensate. But for a first pass, wage indexing is simple and directionally correct.

---

## Simulation Loop Ordering

**Decision:** The monthly step runs in this order: demographics -> government -> pensions -> housing dev -> labor -> production -> healthcare -> goods market -> consumption -> investment -> loan repayment -> profit distribution -> bonds -> prices.

**Key ordering decisions:**
- **Investment before loan repayment:** Firms allocate cash to capital before repaying bank loans. This ensures firms can invest even when carrying loan balances. Without this, loan repayment takes all available cash and investment never happens.
- **Housing development before labor market:** Construction projects set their worker demand before hiring, so shelter firms include construction workers in their labor requests.
- **Government before labor:** Transfers and spending inject cash into the economy before wages are paid, giving firms and individuals purchasing power.

**Tradeoff:** Ordering creates implicit priority (who gets paid first matters when cash is scarce). The current order prioritizes government operations and capital investment over debt repayment, which aligns with the MMT framing.

---

## Dashboard: Policy Levers vs Advanced Parameters

**Decision:** The dashboard sidebar is split into "Policy Levers" (always visible) and "Advanced / Model Assumptions" (collapsed by default with a warning).

**Policy levers** (~15 params): things a policymaker would actually control — tax rates, spending, retirement age, minimum wage, etc.

**Advanced** (~20 params): model calibration — productivity, price adjustment speed, Cobb-Douglas shares, etc. Changing these in isolation can create unstable or unrealistic results.

**Why:** Users were confused by having 39 inputs of mixed importance. Policy levers are the product; calibration params are implementation details. The warning banner ("These parameters are co-calibrated. Changing one in isolation can produce unstable or unrealistic results.") manages expectations.

**Tradeoff:** Some users may want to explore calibration changes. The toggle makes them accessible but not prominent.

---

## Payroll Loans (Bank Credit Creation)

**Decision:** When firms can't cover payroll from cash on hand, the bank extends a payroll loan (creates new bank credit). This means firms never fail to pay wages due to cash shortfalls.

**Why:** In a simplified model with government as the primary money creator, firms often have negative cash flow (wages exceed revenue) especially at small population sizes. Without payroll loans, firms would default on wages every month, creating unrealistic mass unemployment. The bank's willingness to lend ensures the labor market clears.

**Tradeoff:** Firms can accumulate unbounded loan balances. There's no credit limit, interest on loans, or insolvency trigger yet. This is a known gap that Phase 4 (firm insolvency) will address.

---

## Scale Invariance

**Decision:** All simulation parameters are rates and ratios. Results (unemployment rate, price levels, GDP per capita) should be the same whether you run 50 or 1000 agents.

**Why:** This lets us test with 50 agents (fast) and run production with 1000+ agents (realistic). It also means parameter tuning generalizes across population sizes.

**Implementation:** The `scaling.py` module computes all bootstrap endowments from per-capita ratios and demand estimates. Firm cash, capital, inventory, government spending, and healthcare fees all scale linearly with population.

**Tradeoff:** Small populations (50 agents) have discrete rounding effects that don't appear at scale. Some dynamics (e.g., frictional unemployment at exactly 3%) may vary by +/-1% at small scale due to integer rounding.
