"""
Shared test fixtures for VibeSim.
"""

import pytest

from engine import SimConfig, Simulation


@pytest.fixture
def small_sim():
    """A quick 6-month sim for unit tests."""
    config = SimConfig(
        seed=42,
        num_months=6,
        num_individuals=50,
        num_food_firms=2,
        num_energy_firms=2,
        num_shelter_firms=2,
    )
    sim = Simulation(config)
    sim.run()
    return sim


@pytest.fixture
def medium_sim():
    """A 12-month sim with moderate population."""
    config = SimConfig(seed=42, num_months=12, num_individuals=50)
    sim = Simulation(config)
    sim.run()
    return sim


@pytest.fixture
def ledger_only():
    """A bare ledger for unit-level account tests."""
    from engine.ledger import Ledger

    return Ledger()
