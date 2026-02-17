"""
Smoke tests -- minimal sanity checks designed to run fast in CI.
"""

import pytest

from engine import SimConfig, Simulation
from engine.actors import create_all_actors
from engine.ledger import Ledger


@pytest.mark.smoke
def test_smoke_simulation():
    """Quick end-to-end: 3 months, 50 agents, all invariants hold."""
    config = SimConfig(
        seed=1,
        num_months=3,
        num_individuals=50,
        num_food_firms=1,
        num_energy_firms=1,
        num_shelter_firms=1,
    )
    sim = Simulation(config)
    results = sim.run()

    assert len(results) == 3
    assert results[-1].gdp > 0
    assert sim.ledger.check_all_entries_balanced()
    assert sim.ledger.check_system_balance()
    assert sim.ledger.verify_running_balances()

    summary = sim.results_summary()
    assert summary["accounting_valid"]


@pytest.mark.smoke
def test_smoke_profiling():
    """Profiling hooks should produce timing data."""
    config = SimConfig(seed=1, num_months=3, num_individuals=50)
    sim = Simulation(config)
    sim.run()

    prof = sim.profiling
    assert "total_wall_time" in prof
    assert prof["total_wall_time"] > 0
    assert "labor_market" in prof
    assert "goods_market" in prof


@pytest.mark.smoke
def test_smoke_import():
    """Core public API should be importable."""
    from engine import __version__

    assert __version__ == "0.2.0"


@pytest.mark.smoke
def test_initial_age_distribution_roughly_uniform():
    """Initial population ages should be spread roughly evenly from 0 to 72 years.

    This is a standalone data-structure check (no simulation run), so we use
    700 individuals for statistical accuracy.
    """
    ledger = Ledger()
    actors = create_all_actors(
        ledger=ledger,
        num_individuals=700,
        num_food_firms=2,
        num_energy_firms=2,
        num_shelter_firms=2,
        num_owners=6,
        initial_prices={"food": 10.0, "energy": 8.0, "shelter": 15.0, "healthcare": 20.0},
        initial_wage=2400.0,
        num_healthcare_firms=1,
    )
    individuals = actors["individuals"]
    assert len(individuals) == 700

    # Bucket into 6 age bands of 12 years each.
    band_size_years = 12
    num_bands = 6
    bands = [0] * num_bands

    for ind in individuals:
        age_years = ind.age_months / 12
        band_idx = min(int(age_years // band_size_years), num_bands - 1)
        bands[band_idx] += 1

    expected_per_band = 700 / num_bands  # ~116.7
    for i, count in enumerate(bands):
        lo = i * band_size_years
        hi = (i + 1) * band_size_years
        assert abs(count - expected_per_band) <= 15, (
            f"Age band {lo}-{hi}y: expected ~{expected_per_band:.0f}, got {count}"
        )
