# Changelog

All notable changes to VibeSim are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] - 2026-02-15

### Added
- **Core engine**: Double-entry bookkeeping ledger with append-only journal.
- **Actors**: Individual, Firm, Bank, consolidated Government.
- **Production**: Cobb-Douglas production functions for food, energy, shelter.
- **Markets**: Labor market clearing with Phillips-curve wage adjustment;
  goods market clearing with inventory-based price adjustment.
- **Policy**: Government spending (money creation), taxation (money destruction),
  unemployment transfers, firm profit distribution.
- **Shocks**: Stimulus, austerity, tax reform, tech boom, energy crisis,
  stagflation scenario presets.
- **Config system**: `SimConfig` dataclass with YAML load/save support.
- **Metrics**: Daily stats collection (GDP, unemployment, Gini, sector balances).
- **I/O**: CSV export for results and journal; run artifact saving with metadata.
- **Profiling**: Per-phase timing hooks on the simulation loop.
- **Dashboard**: Flask + Plotly interactive web UI for running scenarios.
- **Tests**: Accounting invariants, economic sanity checks, property-based tests
  (hypothesis), smoke tests.
- **CI**: GitHub Actions workflow (lint, test, smoke).
- **Docs**: README, CONTRIBUTING, Model Assumptions, CHANGELOG.

### Architecture
- Clean module separation: ledger, accounts, actors, markets, policy,
  shocks, metrics, io, simulation.
- Engine is an importable Python package (`from engine import Simulation`).
- Deterministic seeded RNG for reproducible runs.
