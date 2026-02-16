# Changelog

All notable changes to VibeSim are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [0.2.0] - 2026-02-16 — Ages and Stages

### Added
- **Monthly timebase**: Entire simulation converted from daily to monthly.
  All parameters, variables, labels, and outputs now use monthly units.
- **Individual lifecycle**: Agents now have `age_months`, `life_stage`
  (CHILD / ADULT / RETIRED), and an `alive` flag. Initial population is
  distributed evenly across ages 1–72 years.
- **Fertility and births**: Paired adults can produce children with a
  monthly fertility hazard (~1% annual population growth). Both parents
  get a 12-month fertility cooldown and a 12-month labor penalty (half
  effective wage). Childbirth incurs a healthcare fee split between parents.
- **Mortality and inheritance**: Individuals face a constant mortality
  hazard starting at age 72, calibrated for an average death age of 80.
  Estates are settled as a 100% inheritance tax (money destruction).
- **Retirement and pensions**: Adults retire at 65 and receive a
  government-funded pension equal to `pension_replacement_rate × avg_wage`
  each month (money creation).
- **Government bonds**: Monthly bond market with bisection-based clearing.
  Households swap deposits for bonds at the market-clearing interest rate.
  Government pays monthly interest to bondholders (money creation).
- **Healthcare sector**: Healthcare firms compete for labor alongside
  goods firms. Government funds elder healthcare visits monthly.
  Capacity is constrained by healthcare employment. Childbirth fees
  flow to healthcare firms.
- **New dashboard tabs**: Demographics (population pyramid, births/deaths,
  dependency ratio), Healthcare (capacity vs demand, shortage, spending),
  Bonds (rate, outstanding, interest, issuance).
- **New KPIs**: Population count and bond rate added to the dashboard.
- **New config parameters**: `retirement_age`, `mortality_start_age`,
  `target_death_age`, `fertility_rate_annual`, `pension_replacement_rate`,
  `num_healthcare_firms`, `healthcare_productivity`,
  `childbirth_healthcare_fee`, `elder_healthcare_monthly_cost`,
  `bond_duration_months`, `bond_rate_min`, `bond_rate_max`,
  `bond_demand_sensitivity`, `bond_savings_fraction`, `child_food_fraction`.
- **New modules**: `engine/bonds.py`, `engine/demographics.py`.
- **Backward compatibility**: `DailyStats` alias for `MonthlyStats`,
  `collect_daily_stats` alias for `collect_monthly_stats`.

### Changed
- **Timebase**: `num_days` → `num_months`, `daily_govt_transfer` →
  `monthly_govt_transfer`, `daily_govt_spending` → `monthly_govt_spending`,
  `target_inventory_days` → `target_inventory_months`.
- **Default values scaled for monthly**: wages 80→2400, transfers 10→300,
  govt spending 5000→150000, prices scaled proportionally.
- **Simulation loop**: Now runs 16 phases per month (demographics, govt,
  pensions, labor, production, healthcare, goods, consumption, profits,
  bonds, interest, price/wage adjustment, metrics).
- **Labor market**: Only alive adults (not children, not retirees) participate.
  Parents with `reduced_labor_months_remaining > 0` earn half wages.
- **Goods market**: Children consume 0.5× food (paid by guardian).
  Healthcare firms excluded from goods market.
- **Firm profit distribution**: Now monthly (1/12 instead of 1/52).
- **EMA smoothing**: 0.7/0.3 monthly blend (was 0.9/0.1 daily).
- **Shock timing**: All scenario presets fire at month 6 (was day 90).
- **Dashboard**: All labels, chart titles, and city view converted to months.
- **Version**: 0.1.0 → 0.2.0.

### Fixed
- Government deficit calculation now includes sales tax (was income tax only).
- Sector balance invariant test accounts for bonds_issued liability.

## [0.1.0] - 2026-02-16

### Added
- **Core engine**: Multi-agent economic simulation with daily market clearing.
- **Actors**: Individuals (workers/consumers), Firms (food/energy/shelter),
  Bank, consolidated Government (Treasury + Central Bank).
- **Production**: Cobb-Douglas production functions with labor and capital.
- **Markets**: Labor market with Phillips-curve wage adjustment;
  goods market with inventory-based price adjustment.
- **Policy**: Government spending (money creation), taxation (money destruction),
  unemployment transfers, firm profit distribution.
- **Shocks**: Stimulus, austerity, tax reform, tech boom, energy crisis,
  stagflation scenario presets.
- **Config system**: `SimConfig` dataclass with YAML load/save support.
- **Metrics**: Daily stats (GDP, unemployment, Gini, sector balances, prices).
- **I/O**: CSV export for results and journal; run artifact saving with metadata.
- **Profiling**: Per-phase timing hooks on the simulation loop.
- **Dashboard**: Flask + Plotly interactive web UI for running scenarios.
- **Tests**: Smoke tests, ledger invariants, property-based tests (hypothesis),
  economic sanity checks.
- **CI**: GitHub Actions workflow (lint, test, smoke).
- **Docs**: README, CONTRIBUTING, Model Assumptions, CHANGELOG.

### Fixed
- Phillips-curve wage adjustment was inverted (high unemployment raised wages).
- Firms could hire with negative cash balance (forced minimum of 1 worker).
- Price spiral from passing zero inventory to adjustment function.
- EMA of daily sales updated per-transaction instead of per-day.
- Negative debit in goods sale when unit price < $1.

### Architecture
- Clean module separation: ledger, actors, markets, policy, production,
  shocks, metrics, io, simulation.
- Engine is an importable Python package (`from engine import Simulation`).
- Deterministic seeded RNG for reproducible runs.
