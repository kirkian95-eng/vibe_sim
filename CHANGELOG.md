# Changelog

All notable changes to VibeSim are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

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
