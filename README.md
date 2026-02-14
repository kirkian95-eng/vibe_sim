# VibeSim — Economic Simulation Engine

A research-grade macroeconomic/microeconomic simulation engine grounded in **double-entry bookkeeping**. Every economic transaction is a balanced journal entry, ensuring accounting integrity at all times.

## Features

- 🧮 **Rigorous Accounting**: Append-only journal, double-entry bookkeeping, full audit trail
- 🏦 **Modern Monetary Theory**: "Taxes destroy money; government spending creates money"
- 👥 **Multi-Agent Economy**: Individuals, firms, banks, consolidated government
- 📊 **Production Economy**: Food, energy, shelter produced via Cobb-Douglas functions
- 💼 **Labor & Goods Markets**: Daily market clearing with wage/price adjustment
- 📈 **Scenario Analysis**: Built-in policy shocks (stimulus, austerity, tax changes, technology)
- 🎨 **Interactive Dashboard**: Flask + Plotly web UI for parameter tuning and visualization
- ✅ **Tested**: Accounting invariants + economic sanity checks

## Quick Start

### Installation

```bash
# Clone the repo
git clone <repo-url>
cd vibe_sim

# Install dependencies
pip install -r requirements.txt
```

### Run the Dashboard

```bash
python run.py
```

Open http://localhost:5000 in your browser. Configure parameters, select a scenario shock, and run the simulation.

### Run a Demo (CLI)

```bash
python run.py --demo
```

This runs a baseline vs stimulus comparison and prints results to the console.

### Run Tests

```bash
python run.py --test
# or
pytest -v tests/
```

## Architecture

### Core Components

```
engine/
├── ledger.py       # Double-entry bookkeeping journal and accounts
├── actors.py       # Individual, Firm, Bank, Government actor types
├── config.py       # Simulation parameters (tuneable)
├── production.py   # Cobb-Douglas production functions
├── markets.py      # Labor and goods market clearing + transactions
├── simulation.py   # Main daily simulation loop
└── shocks.py       # Scenario shocks (policy changes, tech breakthroughs)

dashboard/
├── app.py          # Flask API server
└── templates/
    └── index.html  # Interactive dashboard UI

tests/
├── test_accounting.py  # Accounting invariants
└── test_economics.py   # Economic sanity checks
```

### Accounting Model

Every transaction is a **balanced journal entry** with debits and credits:

- **Asset** and **Expense** accounts increase with debits
- **Liability**, **Equity**, and **Revenue** accounts increase with credits
- Each entry must balance: `total_debits = total_credits`

The ledger maintains:
- Append-only journal (authoritative source of truth)
- Running account balances (incrementally updated)
- Invariant checks: balance sheet equation, system balance, sector balance

### Economic Model

**Actors:**
- **Individuals**: Work, consume, pay taxes, may own firms
- **Firms**: Produce goods (food/energy/shelter), hire labor, set prices
- **Bank**: Intermediates deposits and loans
- **Government** (consolidated CB + Treasury): Spends money into existence, taxes destroy money

**Daily Cycle:**
1. Government spending (transfers to unemployed + public goods)
2. Labor market clearing (firms hire workers, pay wages)
3. Production (firms produce output using labor + capital)
4. Goods market clearing (individuals buy goods from firms)
5. Consumption (individuals consume from inventory)
6. Taxation (income tax + sales tax)
7. Profit distribution (weekly)
8. Price & wage adjustment (respond to inventory levels and unemployment)

**Production Function:**
```
output = productivity * labor^α * capital^β
```
where α = labor_share (default 0.7), β = capital_share (default 0.3).

**Money Creation/Destruction (MMT):**
- Government spending **creates** money (credits bank reserves/deposits)
- Taxation **destroys** money (debits deposits/reserves)
- Private sector net financial assets = cumulative government deficit

## Scenario Shocks

Built-in scenarios:
- **baseline**: No shocks
- **stimulus**: Government spending +10k/day at day 90
- **austerity**: Government spending -50% at day 90
- **tax_reform**: Income tax cut to 10% at day 90
- **tech_boom**: Food productivity 2x, energy 1.5x at day 90
- **energy_crisis**: Energy productivity drops to 40% at day 90
- **stagflation**: Energy crisis + delayed stimulus

## Configuration

Key parameters (see `engine/config.py`):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `num_days` | 365 | Simulation length |
| `num_individuals` | 1000 | Population size |
| `num_food_firms` | 4 | Number of food producers |
| `income_tax_rate` | 0.20 | Income tax rate |
| `sales_tax_rate` | 0.05 | Sales tax rate |
| `daily_govt_spending` | 5000 | Daily public goods spending |
| `daily_govt_transfer` | 10 | Daily transfer per unemployed |
| `initial_wage` | 80 | Starting wage |
| `min_wage` | 20 | Wage floor |

## Output & Metrics

The simulation tracks:

**Macro:**
- GDP (daily aggregate output value)
- Unemployment rate
- Average wage
- Money supply (bank deposits)
- Government deficit

**Prices:**
- Food, energy, shelter prices (market-determined)

**Distribution:**
- Gini coefficient
- Top 1% income share
- Bottom 50% income share

**Sector Balances:**
- Private sector net worth
- Government net worth
- Banking sector net worth

**Production:**
- Quantity produced/sold by good type
- Firm-level inventory, revenue, employment

## Testing

### Accounting Invariants

Every test run verifies:
- All journal entries are balanced
- Balance sheet equation holds for every actor: `Assets = Liabilities + Equity + Revenue - Expense`
- System-wide balance: total debits = total credits
- Running balances match journal replay
- Sector balances sum correctly (closed economy)

### Economic Sanity

Tests verify:
- GDP and production are positive
- Prices remain stable (no hyperinflation)
- Employment responds to market conditions
- Stimulus increases output
- Austerity reduces output
- Technology boosts productivity
- Inequality exists and responds to policy
- Deterministic runs (same seed → same results)

## Example: Policy Comparison

```python
from engine.config import SimConfig
from engine.simulation import Simulation
from engine.shocks import stimulus_spending

config = SimConfig(num_days=180, seed=42)

# Baseline
baseline = Simulation(config)
baseline_results = baseline.run()

# Stimulus
stim = Simulation(config, shocks=[stimulus_spending(day=90, extra_daily=10_000)])
stim_results = stim.run()

# Compare GDP
print(f"Baseline GDP: {baseline_results[-1].gdp:.0f}")
print(f"Stimulus GDP: {stim_results[-1].gdp:.0f}")
```

## Research Applications

This engine can be used to study:
- Fiscal policy effectiveness (stimulus vs austerity)
- Monetary policy transmission (interest rates, reserve requirements)
- Inequality dynamics (progressive taxation, UBI, wealth taxes)
- Supply shocks (energy crises, productivity changes)
- Sectoral balances (MMT predictions, private-public flows)
- Labor market dynamics (minimum wage, Phillips curve)

All results are reproducible (seeded RNG) and auditable (full journal available).

## License

See [LICENSE](LICENSE) file.

## Architecture Decisions

**Why double-entry bookkeeping?**
- Ensures consistency: every dollar is tracked, no leaks
- Audit trail: full replay from journal
- Sectoral balances: private, government, banking sectors must balance
- Realistic monetary operations: money is created/destroyed correctly

**Why consolidated government (CB + Treasury)?**
- Simplifies money creation: government spending = money creation
- MMT-friendly: taxes destroy money, spending creates it
- Avoids intra-government accounting complexity

**Why daily timesteps?**
- Fast enough for year-long simulations
- Granular enough for policy shock analysis
- Market clearing happens at reasonable frequency

**Why Cobb-Douglas production?**
- Standard in macro models
- Diminishing returns to labor and capital
- Easy to calibrate and interpret

## Future Enhancements

Potential extensions:
- Investment decisions (endogenous capital accumulation)
- Bank lending (endogenous money creation)
- Multiple goods sectors (intermediate inputs)
- International trade (open economy)
- Expectation formation (adaptive/rational)
- Heterogeneous agents (different preferences, skills)
- Asset markets (stocks, bonds, real estate)
- Climate/resource constraints

## Contributing

This is a research prototype. Contributions welcome:
- Additional scenario shocks
- New policy levers
- Performance optimizations
- Visualization improvements
- Documentation enhancements

Ensure all changes preserve accounting invariants (tests must pass).

---

Built with Python, Flask, and Plotly. Accounting rigor meets economic simulation.
