# Contributing to VibeSim

Thanks for your interest in contributing!

## Development Setup

```bash
git clone <repo-url>
cd vibe_sim
pip install -e ".[dev]"
```

## Running Tests

```bash
# Smoke tests (fast, <30s)
pytest -v -m smoke tests/

# Core tests (smoke + accounting + io)
pytest -v tests/test_smoke.py tests/test_accounting.py tests/test_io.py

# Full suite including economics and invariants
pytest -v tests/

# Property-based tests only (slow, run before committing)
pytest -v tests/test_properties.py
```

## Code Quality

```bash
ruff check engine/ tests/
ruff format engine/ tests/
mypy engine/ --ignore-missing-imports
```

## Making Changes

1. Create a feature branch from `main`.
2. Make your changes.
3. Run `pytest -m smoke` to verify basic correctness.
4. Run `ruff check` and `mypy` with no errors.
5. Open a pull request with a clear description.

## Adding a New Shock Type

1. Add a factory function in `engine/shocks.py`.
2. Register it in `SHOCK_FACTORIES`.
3. Optionally add a scenario preset in `SCENARIOS`.
4. Add a test in `tests/test_economics.py`.

## Project Structure

```
engine/          # Core simulation engine (importable package)
  simulation.py  # Main simulation loop
  config.py      # SimConfig dataclass
  ledger.py      # Transaction ledger (double-entry)
  actors.py      # Individual, Firm, Bank, Government
  accounts.py    # Account utilities and sector helpers
  markets.py     # Labor and goods market clearing
  policy.py      # Government operations and taxation
  production.py  # Production functions and price/wage rules
  shocks.py      # Scenario shocks
  metrics.py     # DailyStats and metric collection
  io.py          # YAML config, CSV export, run artifacts

dashboard/       # Flask web UI (optional dependency)
tests/           # Test suite
configs/         # YAML config presets
```
