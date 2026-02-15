# Contributing to VibeSim

Thanks for your interest in contributing! This document covers the basics.

## Development Setup

```bash
# Clone and install in editable mode with dev dependencies
git clone <repo-url>
cd vibe_sim
pip install -e ".[dev]"
```

## Running Tests

```bash
# All tests
pytest -v tests/

# Fast tests only (skip slow, long-running tests)
pytest -v -m "not slow" tests/

# Smoke tests only
pytest -v -m smoke tests/
```

## Code Quality

```bash
# Lint
ruff check engine/ tests/

# Format
ruff format engine/ tests/

# Type check
mypy engine/ --ignore-missing-imports
```

## Making Changes

1. Create a feature branch from `main`.
2. Make your changes. Preserve accounting invariants.
3. Run the test suite and ensure all tests pass.
4. Run `ruff check` and `mypy` with no errors.
5. Open a pull request with a clear description.

## Key Invariants

These must **always** hold -- CI enforces them:

- Every journal entry balances: `sum(debits) == sum(credits)`
- Balance sheet equation holds for every actor: `A == L + E + R - X`
- System-wide balance: total debit-normal balances == total credit-normal balances
- Replay from journal matches running balances

If your change breaks any of these, it will be caught by the property-based tests.

## Adding a New Shock Type

1. Add a factory function in `engine/shocks.py`.
2. Register it in `SHOCK_FACTORIES`.
3. Optionally add a scenario preset in `SCENARIOS`.
4. Add a test in `tests/test_economics.py`.

## Project Structure

```
engine/          # Core simulation engine (importable package)
  config.py      # SimConfig dataclass
  ledger.py      # Double-entry bookkeeping
  actors.py      # Individual, Firm, Bank, Government
  accounts.py    # Account utilities and sector helpers
  markets.py     # Labor and goods market clearing
  policy.py      # Government operations and taxation
  production.py  # Cobb-Douglas production functions
  shocks.py      # Scenario shocks
  metrics.py     # DailyStats and metric collection
  io.py          # YAML config, CSV export, run artifacts
  simulation.py  # Main simulation loop

dashboard/       # Flask web UI (optional dependency)
tests/           # Test suite
```
