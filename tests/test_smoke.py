"""
Smoke tests -- minimal sanity checks designed to run fast in CI.
"""

import pytest

from engine import SimConfig, Simulation


@pytest.mark.smoke
def test_smoke_simulation():
    """Quick end-to-end: 10 days, 50 agents, all invariants hold."""
    config = SimConfig(
        seed=1,
        num_days=10,
        num_individuals=50,
        num_food_firms=1,
        num_energy_firms=1,
        num_shelter_firms=1,
    )
    sim = Simulation(config)
    results = sim.run()

    assert len(results) == 10
    assert results[-1].gdp > 0
    assert sim.ledger.check_all_entries_balanced()
    assert sim.ledger.check_system_balance()
    assert sim.ledger.verify_running_balances()

    summary = sim.results_summary()
    assert summary["accounting_valid"]


@pytest.mark.smoke
def test_smoke_profiling():
    """Profiling hooks should produce timing data."""
    config = SimConfig(seed=1, num_days=5, num_individuals=50)
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

    assert __version__ == "0.1.0"
