# EconomySim Roadmap (plan.md)

This file is the forward-looking product and engineering plan for the ledger-first economy simulation. It is written to be handed to an AI coding agent as guidance for future versions.

## Guiding principles

- **Ledger-first:** Every economic action is a posted double-entry journal entry. If an action cannot be expressed as debits and credits across accounts, it does not exist in the model yet.
- **Monthly timebase:** A period is a month. All rates are monthly internally (with convenience views that annualize where needed).
- **Determinism:** Every run is reproducible from a seed and a parameter bundle. Run artifacts include the seed, parameters, and git commit hash when available.
- **Separation of concerns:** Engine produces state and logged data. UI reads run artifacts and provides visualization and scenario orchestration.
- **Scenario culture:** Every major feature includes at least one scenario or shock that demonstrates it, plus a baseline comparison.
- **Invariants are sacred:** Balanced journal entries, balanced balance sheets, and basic sector consistency must remain true after every month.

## Version map

- v0.2: Ages and Stages (LIVE)
- v0.21: Graphs for Nerds (LIVE, needs work)
- v0.22: Shelter Nerf (temporary patch, LIVE)
- v0.3: Shelters and Firms Overhaul
- v0.4: Fiscal vs Monetary
- v0.5: Trade Wars

---

## v0.2: Ages and Stages (LIVE)

### Intent
Introduce life-cycle dynamics that create realistic dependency ratios, pension burdens, healthcare labor demand, and demographic sensitivity to economic shocks.

### Core features
- Age tracked per individual, advancing monthly.
- Stages: child, adult, retired.
- Birth mechanics: births depend on economic conditions (fed and sheltered), cooldowns, parenting labor penalties, and child consumption obligations.
- Retirement: labor supply ends at retirement age; old-age pension begins.
- Mortality: monthly hazard from age threshold onward, calibrated to target average death age; wealth at death transfers to government.
- Healthcare institution: childbirth cost, mandatory elder monthly visits, capacity based on employed labor, wage bidding for staffing.
- Government deficit and bond issuance: monthly deficit tracked; bonds sold to convert deposits into less money-like instruments; bond market clears a rate; interest paid monthly.

### Data model notes
- Individuals need: age_months, stage, alive, parents, children, fertility cooldown, parenting labor penalty window.
- Bonds: household bond assets, government bond liabilities, bond holdings and interest flows.
- Healthcare: service demand (elder visits, childbirth events), staffing, capacity, wage, revenue sources.

### Invariants to preserve
- Every journal entry balances.
- Each actor balance sheet balances each month.
- Stage transitions follow rules (child to adult, adult to retired).
- Fertility cooldown enforced for parent pairs.
- Bond issuance and interest are internally consistent in the ledger.

### Acceptance criteria
- Run 240 months and see demographic shift and policy burden effects.
- Healthcare hires toward meeting elder service demand; unmet demand is visible.
- Deficit and bonds appear as time series; bond rate clears each month.
- Accounting tests pass.

---

## v0.21: Graphs for Nerds (LIVE, needs work)

### Intent
Make the UI useful as an economics instrument, not only a simulation viewer.

### Core features
- A dedicated **Graphs** tab that computes macro indicators from run outputs.
- Metrics include: CPI index, inflation (MoM and YoY), unemployment/employment, GDP (nominal and real), interest rates (at least bond clearing rate), median income, and distribution summaries.

### What "needs work" commonly means
- Definitions drifting from engine realities (for example, GDP accidentally double-counting intermediates).
- Missing data quality handling (missing prices due to shortages).
- Scenario comparison and run selection UX unclear.
- Labels and units inconsistent with monthly timebase.

### Plan to stabilize v0.21
1. **Lock definitions**
   - CPI uses a fixed basket with editable weights that must sum to 1.
   - GDP uses one method as the canonical definition (prefer expenditure on final goods). Intermediate purchases excluded.
   - Income definition is explicit (wages, profits distributed, transfers, interest).
2. **Add transaction classification tags in the ledger**
   - is_final, good_type, txn_type, sector_from, sector_to.
3. **Add data quality flags**
   - Price carry-forward when no transactions occur for a good in a month.
   - GDP completeness and any identified double-count risks flagged.
4. **Better scenario compare**
   - Overlay charts baseline vs scenario, and an end-of-run KPI table.

### Acceptance criteria
- Two scenarios compared on one page without manual file hacking.
- CPI, GDP, interest rate, and median income charts remain stable across refactors.
- A short deterministic test dataset validates calculations.

---

## v0.22: Shelter Nerf (LIVE, temporary patch)

### Intent
Stabilize the economy while housing is under redesign by simplifying shelter flows.

### Current patch behavior
- Shelter prices are temporarily fixed or removed from price adjustment.
- All shelter rents flow to the government as a placeholder mechanism.

### Technical debt created by the patch
- Shelter no longer behaves like a market or firm sector.
- Government revenue is artificially inflated and may distort bonds, taxes, and CPI.
- Individual welfare and inequality dynamics are dampened or distorted.

### Exit plan
- Remove or disable the patch as part of v0.3 housing market overhaul.
- Provide a migration step for runs and dashboards, including a clear changelog note that shelter series are not comparable across versions.

---

## v0.3: Shelters and Firms Overhaul

### Intent
Turn shelter into a real asset market and firms into entities that can fail, recapitalize, and interact with capital markets. Add the missing social institutions that make labor supply and credentials matter.

### Major themes
1. **Housing market and property development**
2. **Firm behaviors: stock market, insolvency, and financing**
3. **Labor structure: managers**
4. **Human capital: college**
5. **Childcare and education as institutions and goods**

### 1) Housing market and property development

#### Features
- Rent versus own distinction for individuals.
- Housing as a durable asset with a stock (units) and a flow (new development).
- Developers build new housing using labor, energy, and capital goods; project timelines are multi-month.
- Rent is paid to property owners (individual owners, firms, or a housing sector). Government may subsidize housing in specific scenarios.
- Optional mortgage concept: households can borrow from banks to purchase a home. This can be staged, starting with cash-only purchases and later adding mortgages.

#### Accounting
- Housing units appear as assets on owner balance sheets.
- Rent is income to owners, expense to renters.
- Development is investment spending, not consumption.
- Mortgages create loans (bank asset) and deposits (household asset), with loan amortization and interest.

#### Metrics
- Homeownership rate, rent burden, housing price index, vacancy rate.
- Housing starts and completions.
- Shelter CPI component should be coherent (rent index and or imputed rent if implemented later).

#### Acceptance criteria
- Shelter dynamics respond to shocks: population growth, interest rate changes, construction productivity.
- Rents no longer flow to government by default.
- Housing units and any mortgage flows are fully journaled and balance.

### 2) Firm overhaul: stock market, insolvency, and financing

#### Features
- Firms have equity that is owned by individuals (starting with the top 1 percent owners but extendable).
- Firms can become insolvent and either:
  - Default and liquidate, or
  - Restructure (debt haircut, equity dilution), or
  - Receive a bailout under a government policy scenario.
- Stock market mechanism for equity valuations and optional issuance of new equity.
- Firm reinvestment: retained earnings can fund capital expansion with diminishing returns.

#### Accounting
- Equity is a claim on firm net assets.
- Profits can be retained (increase equity) or distributed (income to owners, reduce firm equity or cash).
- Default and restructuring must be handled via explicit ledger events.

#### Metrics
- Default rates, firm leverage, equity concentration, dividend share.
- Profit shares by sector and over time.

#### Acceptance criteria
- At least one scenario causes firm stress and a visible insolvency event with accounting intact.
- Equity ownership evolves and impacts inequality in a visible way.

### 3) Managers: labor hierarchy

#### Features
- For every 5 employees a firm must employ 1 manager (rule-based staffing requirement).
- Managers have higher wages, and firms compete for them.
- Managers require a credential (college). Non-credentialed adults cannot fill manager roles.

#### Design notes
- This is easiest if labor market matching supports job types: worker versus manager.
- The ratio rule can be implemented as:
  - Required_managers = ceil(total_employees / 5) for each firm.
- Managers can become a bottleneck that reduces firm capacity even when non-manager labor is abundant.

#### Acceptance criteria
- Firms reduce output when manager roles cannot be filled.
- Wage premium emerges for managers, affecting inequality.

### 4) College: credentials and financing

#### Features
- College is an institution that produces credentials, consumes labor, and may charge tuition.
- Credential acquisition takes time (multi-year in months).
- Financing options to brainstorm and stage:
  1. Student debt provided by banks, repaid over time.
  2. Parents pay tuition from income and savings.
  3. Government funding, treated as public spending.
  4. Random scholarships or ability-based selection (optional).

#### Minimal first implementation
- Make college enrollment a probability for eligible young adults, bounded by household affordability and or loans.
- Completion yields credential.
- Tuition flows to the college institution; college hires educators as labor demand.

#### Acceptance criteria
- Manager labor supply becomes sensitive to college throughput.
- Tuition and debt dynamics appear in household balance sheets if loans are enabled.

### 5) Childcare and education as a good and institutions

#### Features
- Childcare is a demanded good by households with children.
- Supply sources:
  - Firms provide childcare for profit.
  - Government provides education via schools funded by taxes.
  - Individuals can provide childcare by foregoing wages (opportunity cost).
- Primary supply should be government schools by default.
- Childcare affects parents' effective labor supply:
  - With adequate childcare, parents can supply normal labor.
  - Without childcare, parents may supply reduced labor or exit labor temporarily.

#### Accounting and metrics
- Government spending on schools and wages for educators.
- Household childcare expenses and subsidies.
- Childcare coverage rate, parental labor force participation, impacts on output and inequality.

#### Acceptance criteria
- Childcare availability measurably affects labor supply and GDP.
- A policy shock to childcare funding produces visible outcomes.

### v0.3 implementation order (recommended)
1. Replace shelter nerf with a simple rental market and landlord ownership.
2. Add development and housing stock dynamics.
3. Add firm equity and profit distribution cleanup.
4. Add insolvency and a simple bankruptcy process.
5. Add manager job type and staffing constraint.
6. Add college institution and credential pipeline.
7. Add childcare and school institution.
8. Update Graphs tab definitions to incorporate the new shelter and investment concepts cleanly.

---

## v0.4: Fiscal vs Monetary

### Intent
Introduce automated stabilizers and a central bank with a dual mandate, separating fiscal and monetary roles while maintaining MMT framing.

### Fiscal policy block
- Automated stabilizers:
  - Transfers that rise with unemployment.
  - Taxes that respond to income levels.
  - Discretionary stimulus triggered by a misery index threshold.
- Misery index:
  - Constructed from unemployment and inflation, plus optional real wage growth decline.
  - Fiscal rules respond to it, adjusting transfers, public hiring, or targeted subsidies.

### Monetary policy block
- Independent central bank with dual mandate:
  - Employment and inflation targets.
- Policy rate setting rule:
  - Taylor-like rule in monthly form, or a simpler reaction function.
- Policy rate influences:
  - Government bond clearing range and demand.
  - Bank deposit and lending rates if banking is extended.
  - Cost of capital and housing market dynamics if mortgages exist.

### Implementation constraints
- Do not break the accounting semantics:
  - Government can always spend, but bonds and interest rates affect portfolio composition and demand.
- Keep the rule system explicit, inspectable, and togglable per scenario.

### Acceptance criteria
- A recession shock triggers stabilizers and visible deficit response.
- A supply shock triggers inflation and central bank rate response.
- Outcomes differ between regimes: policy on versus policy off.

---

## v0.5: Trade Wars

### Intent
Introduce international trade dynamics: comparative advantage, transport costs, tariffs, and second-country policy interactions.

### Big design choice: currency regime
Pick one for v0.5 and document it clearly.
1. Two sovereign currencies with an exchange rate (floating or managed).
2. A single shared currency zone.
3. A fixed peg.

A two-currency model is richer but adds complexity. A shared currency model is simpler but changes policy interpretation. Decide explicitly and keep the first implementation minimal.

### Core features
- Add Country B with its own households, firms, government, and optionally central bank.
- Trade in energy and food across countries.
- Comparative advantages:
  - Different productivities by sector and country.
- Trade frictions:
  - Transportation costs per unit.
  - Tariffs and quotas as policy tools.
- Trade balance tracking:
  - Imports, exports, current account proxy, and cross-border asset positions.

### Accounting
- Cross-border payment settlement rules consistent with chosen currency regime.
- If two currencies:
  - FX market mechanism and FX reserves or private FX holdings.
  - Trade invoices and settlement entries must balance across sectors and countries.

### Acceptance criteria
- A tariff shock changes relative prices, output composition, and employment.
- Comparative advantage produces persistent trade flows in baseline.
- Graphs tab can show trade balance and imported inflation effects.

---

## Cross-version engineering checklist

### Ledger and classification
- Add and maintain transaction tags so macro calculations remain correct as features grow:
  - final consumption vs intermediate
  - transfer vs purchase
  - investment vs consumption
  - domestic vs foreign
  - loan principal vs interest

### Output schema stability
- Version output files explicitly with a schema version in the run artifact.
- Provide migration notes when dashboards change definitions.

### Performance targets (soft)
- Keep a mode that runs many agents for long horizons by toggling off expensive per-agent UI queries.
- Maintain a "research mode" where detailed ledgers are retained and a "fast mode" with aggregated ledger rollups.

### Documentation
- Maintain MODEL_ASSUMPTIONS.md as the living explanation of definitions and design decisions.
- Maintain CHANGELOG.md with version-to-version metric comparability notes.

