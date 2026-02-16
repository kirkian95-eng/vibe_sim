# VibeSim — Economic Simulation Engine

A macroeconomic sandbox for hobbyists and academics to explore how fiscal policy, monetary policy, and market dynamics interact in a simulated economy with demographics, government bonds, and a healthcare sector.

## What Is This?

VibeSim lets you spin up a small economy — with workers, firms, a bank, and a government — and watch what happens when you pull different policy levers. Raise taxes, cut spending, trigger a technology boom, or cause an energy crisis, and see how employment, prices, output, and inequality respond.

Agents are born, grow up, work, retire, and die. The government pays pensions, funds healthcare, and issues bonds. The economy evolves month by month.

Think of it as SimCity for macroeconomics — tune the knobs, watch the dials, and build intuition for how real economies respond to policy changes.

## Features

- **Multi-Agent Economy**: Workers, firms (food/energy/shelter/healthcare), a bank, and a consolidated government
- **Demographics**: Individual lifecycle — children, working-age adults, retirees. Births, deaths, aging, and life-stage transitions
- **Policy Levers**: Tax rates, government spending, transfers, minimum wage, pension replacement rate, retirement age
- **Government Bonds**: Monthly bond market with interest rate clearing and coupon payments
- **Healthcare Sector**: Capacity-constrained healthcare funded by government (elder care) and private payments (childbirth)
- **Pensions**: Government-funded retirement income indexed to average wages
- **Scenario Shocks**: Built-in presets for stimulus, austerity, tax reform, tech booms, energy crises
- **MMT Money Model**: Government spending creates money; taxation destroys it
- **Cobb-Douglas Production**: Standard production functions with labor and capital inputs
- **Interactive Dashboard**: Flask + Plotly web UI with tabs for macro, prices, distribution, production, demographics, healthcare, bonds, and a city view animation
- **Reproducible**: Seeded RNG — same seed, same results
- **Exportable**: CSV output, YAML configs, run artifact saving

## Getting Started (< 2 Minutes)

### Prerequisites

You need **Python 3.10 or newer** installed. If you don't have it, download it from [python.org/downloads](https://www.python.org/downloads/) and follow the installer.

You also need a **terminal** (command line):
- **macOS**: Open the "Terminal" app (search for it in Spotlight)
- **Windows**: Open "Command Prompt" or "PowerShell" from the Start menu
- **Linux**: Open your terminal emulator (usually Ctrl+Alt+T)

### Step 1: Download the project

In your terminal, run:

```bash
git clone <repo-url>
cd vibe_sim
```

Replace `<repo-url>` with the actual repository URL.

### Step 2: Install dependencies

This one command installs everything VibeSim needs:

```bash
pip install -r requirements.txt
```

### Step 3: Launch the dashboard

```bash
python run.py
```

You'll see output like `Running on http://0.0.0.0:5001`. That means the server is running.

### Step 4: Open in your browser

Go to: **http://localhost:5001**

"Localhost" just means "this computer" — the simulation server is running on your own machine, and your browser connects to it.

### Step 5: Run your first simulation

1. You'll see a dashboard with parameter sliders on the left
2. Click **"Run Simulation"** at the top
3. Wait a few seconds — interactive charts will appear in tabs (Macro, Prices, Distribution, Demographics, and more)
4. Try selecting a scenario like "stimulus" or "energy_crisis" and running again to see how the economy responds

### Alternative: Quick CLI Demo

If you just want to verify things work without opening a browser:

```bash
python run.py --demo
```

This runs a 24-month baseline vs. stimulus comparison and prints results to your terminal.

## How It Works

Each simulated month follows this cycle:

1. **Demographics** — advance ages, life-stage transitions (child→adult→retired)
2. **Births** — eligible adult pairs may produce children (with healthcare fee)
3. **Deaths** — mortality hazard for the elderly; estate settlement
4. **Government** — collects taxes and makes transfer payments
5. **Pensions** — monthly pension payments to all retirees
6. **Labor market** — firms hire workers and pay wages (healthcare firms included)
7. **Production** — firms produce goods using labor + capital
8. **Healthcare** — government pays for elder visits; capacity tracking
9. **Goods market** — individuals buy food, energy, shelter (guardians pay for children)
10. **Consumption** — individuals use what they bought
11. **Profit distribution** — firms pay owners (monthly)
12. **Bond market** — government issues bonds to cover deficit; bisection clearing
13. **Bond interest** — monthly coupon payments to bondholders
14. **Price/wage adjustment** — firms and wages respond to market signals
15. **Metrics** — collect monthly statistics

### Money Creation (MMT)

- Government spending **creates** money (credits bank deposits)
- Taxation **destroys** money (debits deposits)
- The government deficit = net money injected into the private sector
- Bonds convert deposits into bond assets (financial portfolio rebalancing)

### Production

```
output = productivity × labor^0.7 × capital^0.3
```

Standard Cobb-Douglas with diminishing returns.

### Demographics

- **Children** (< 18 years): Don't work, consume 50% of adult food (paid by guardian)
- **Adults** (18–64): Work, consume, may have children
- **Retirees** (65+): Receive pensions, consume, face mortality risk from age 72
- **Fertility**: ~1% annual growth rate, 12-month cooldown, parenting labor penalty
- **Mortality**: Constant hazard from age 72, calibrated for average death at 80

## Scenario Shocks

| Scenario | What Happens |
|----------|-------------|
| **stimulus** | Government spending +300k/month at month 6 |
| **austerity** | Government spending -50% at month 6 |
| **tax_reform** | Income tax cut to 10% at month 6 |
| **tech_boom** | Food productivity 2x, energy 1.5x at month 6 |
| **energy_crisis** | Energy productivity drops to 40% at month 6 |
| **stagflation** | Energy crisis + delayed stimulus |

## Configuration

Key parameters (see `engine/config.py` or `configs/baseline.yaml`):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `num_months` | 120 | Simulation length (months) |
| `num_individuals` | 1000 | Population size |
| `num_food_firms` | 1 | Fixed at 1 per good; scaling overrides |
| `num_healthcare_firms` | 1 | 1 healthcare firm; scaling overrides |
| `income_tax_rate` | 0.20 | Income tax rate |
| `sales_tax_rate` | 0.05 | Sales tax rate |
| `monthly_govt_spending` | 150000 | Monthly public goods spending |
| `monthly_govt_transfer` | 300 | Monthly transfer per unemployed |
| `initial_wage` | 2400 | Starting monthly wage |
| `retirement_age` | 65 | Age of retirement (years) |
| `pension_replacement_rate` | 0.50 | Pension as fraction of avg wage |
| `fertility_rate_annual` | 0.01 | Target annual population growth |

Load from YAML:
```python
from engine.io import load_config_yaml
config = load_config_yaml("configs/baseline.yaml")
```

## Output & Metrics

The simulation tracks: GDP, unemployment rate, average wage, money supply, government deficit, food/energy/shelter prices and quantities, Gini coefficient, income shares, sector balances, population by life stage, births, deaths, dependency ratio, pension totals, healthcare capacity and shortage, bond rate, bonds outstanding, and bond interest.

## Example: Policy Comparison

```python
from engine import SimConfig, Simulation
from engine.shocks import stimulus_spending

config = SimConfig(num_months=24, seed=42)

# Baseline
baseline = Simulation(config)
baseline_results = baseline.run()

# Stimulus
stim = Simulation(config, shocks=[stimulus_spending(month=6, extra_per_capita=300)])
stim_results = stim.run()

print(f"Baseline GDP: {baseline_results[-1].gdp:.0f}")
print(f"Stimulus GDP: {stim_results[-1].gdp:.0f}")
print(f"Population:   {stim_results[-1].population}")
```

## Use Cases

- Explore fiscal policy effects (stimulus vs austerity)
- Study inequality dynamics (progressive taxation, UBI scenarios)
- Observe supply shocks (energy crises, productivity changes)
- Examine sectoral balance identities (MMT predictions)
- Model demographic transitions (aging populations, pension sustainability)
- Analyze bond market dynamics and government debt
- Study healthcare capacity constraints
- Teach macro concepts with a hands-on simulation

## Project Structure

```
engine/              # Core simulation (importable Python package)
  simulation.py      # Main monthly loop (16 phases)
  config.py          # SimConfig dataclass
  ledger.py          # Double-entry transaction ledger
  actors.py          # Individual, Firm, Bank, Government
  markets.py         # Labor and goods market clearing
  policy.py          # Government operations, pensions, healthcare
  production.py      # Cobb-Douglas production + price/wage rules
  demographics.py    # Aging, births, deaths, life-stage transitions
  bonds.py           # Government bond market + interest
  shocks.py          # Scenario shocks
  metrics.py         # Monthly statistics collection
  io.py              # YAML config, CSV export, run artifacts
dashboard/           # Flask web UI
tests/               # Test suite (48 tests)
configs/             # YAML config presets
```

## Future Directions

- Bank lending / endogenous credit creation
- Capital investment and depreciation
- Open economy (trade, exchange rates)
- Heterogeneous agents (skills, preferences)
- Asset markets (stocks, real estate)
- Immigration and emigration
- Education and human capital accumulation

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Run the smoke tests before submitting a PR.

---

Built with Python, Flask, and Plotly.
