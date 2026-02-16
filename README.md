# VibeSim — Economic Simulation Engine

A macroeconomic sandbox for hobbyists and academics to explore how fiscal policy, monetary policy, and market dynamics interact in a simulated economy with multiple agent types.

## What Is This?

VibeSim lets you spin up a small economy — with workers, firms, a bank, and a government — and watch what happens when you pull different policy levers. Raise taxes, cut spending, trigger a technology boom, or cause an energy crisis, and see how employment, prices, output, and inequality respond.

Think of it as SimCity for macroeconomics — tune the knobs, watch the dials, and build intuition for how real economies respond to policy changes.

## Features

- **Multi-Agent Economy**: Workers, firms (food/energy/shelter), a bank, and a consolidated government
- **Policy Levers**: Tax rates, government spending, transfers, minimum wage, and more
- **Scenario Shocks**: Built-in presets for stimulus, austerity, tax reform, tech booms, energy crises
- **MMT Money Model**: Government spending creates money; taxation destroys it
- **Cobb-Douglas Production**: Standard production functions with labor and capital inputs
- **Interactive Dashboard**: Flask + Plotly web UI for parameter tuning and visualization
- **Reproducible**: Seeded RNG — same seed, same results
- **Exportable**: CSV output, YAML configs, run artifact saving

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Launch the dashboard
python run.py

# Or run a CLI demo
python run.py --demo

# Run tests
pytest -m smoke tests/
```

Open http://localhost:5000 to configure parameters, select a scenario, and run.

## How It Works

Each simulated day follows this cycle:

1. **Government** collects taxes and makes transfer payments
2. **Labor market** clears — firms hire workers and pay wages
3. **Production** — firms produce goods using labor + capital
4. **Goods market** clears — workers buy food, energy, shelter
5. **Consumption** — individuals use what they bought
6. **Profit distribution** — firms pay owners (weekly)
7. **Price/wage adjustment** — firms and wages respond to market signals

### Money Creation (MMT)

- Government spending **creates** money (credits bank deposits)
- Taxation **destroys** money (debits deposits)
- The government deficit = net money injected into the private sector

### Production

```
output = productivity × labor^0.7 × capital^0.3
```

Standard Cobb-Douglas with diminishing returns.

## Scenario Shocks

| Scenario | What Happens |
|----------|-------------|
| **stimulus** | Government spending +10k/day at day 90 |
| **austerity** | Government spending -50% at day 90 |
| **tax_reform** | Income tax cut to 10% at day 90 |
| **tech_boom** | Food productivity 2x, energy 1.5x at day 90 |
| **energy_crisis** | Energy productivity drops to 40% at day 90 |
| **stagflation** | Energy crisis + delayed stimulus |

## Configuration

Key parameters (see `engine/config.py` or `configs/baseline.yaml`):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `num_days` | 365 | Simulation length |
| `num_individuals` | 1000 | Population size |
| `num_food_firms` | 4 | Number of food producers |
| `income_tax_rate` | 0.20 | Income tax rate |
| `sales_tax_rate` | 0.05 | Sales tax rate |
| `daily_govt_spending` | 5000 | Daily public goods spending |
| `daily_govt_transfer` | 10 | Daily transfer per unemployed |
| `initial_wage` | 80 | Starting daily wage |

Load from YAML:
```python
from engine.io import load_config_yaml
config = load_config_yaml("configs/baseline.yaml")
```

## Output & Metrics

The simulation tracks: GDP, unemployment rate, average wage, money supply, government deficit, food/energy/shelter prices and quantities, Gini coefficient, income shares, and sector balances.

## Example: Policy Comparison

```python
from engine import SimConfig, Simulation
from engine.shocks import stimulus_spending

config = SimConfig(num_days=180, seed=42)

# Baseline
baseline = Simulation(config)
baseline_results = baseline.run()

# Stimulus
stim = Simulation(config, shocks=[stimulus_spending(day=90, extra_daily=10_000)])
stim_results = stim.run()

print(f"Baseline GDP: {baseline_results[-1].gdp:.0f}")
print(f"Stimulus GDP: {stim_results[-1].gdp:.0f}")
```

## Use Cases

- Explore fiscal policy effects (stimulus vs austerity)
- Study inequality dynamics (progressive taxation, UBI scenarios)
- Observe supply shocks (energy crises, productivity changes)
- Examine sectoral balance identities (MMT predictions)
- Teach macro concepts with a hands-on simulation

## Project Structure

```
engine/           # Core simulation (importable Python package)
  simulation.py   # Main loop
  config.py       # SimConfig dataclass
  ledger.py       # Transaction ledger
  actors.py       # Individual, Firm, Bank, Government
  markets.py      # Labor and goods market clearing
  policy.py       # Government operations and taxation
  production.py   # Cobb-Douglas production + price/wage rules
  shocks.py       # Scenario shocks
  metrics.py      # Daily statistics collection
  io.py           # YAML config, CSV export, run artifacts
dashboard/        # Flask web UI
tests/            # Test suite
configs/          # YAML config presets
```

## Future Directions

- Bank lending / endogenous credit creation
- Capital investment and depreciation
- Bond markets and interest rate policy
- Open economy (trade, exchange rates)
- Heterogeneous agents (skills, preferences)
- Asset markets (stocks, real estate)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Run the smoke tests before submitting a PR.

---

Built with Python, Flask, and Plotly.
