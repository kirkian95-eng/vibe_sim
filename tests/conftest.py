"""
Shared test fixtures for VibeSim.
"""

import pytest

from engine import SimConfig, Simulation


@pytest.fixture
def small_sim():
    """A quick 30-day sim for unit tests."""
    config = SimConfig(
        seed=42,
        num_days=30,
        num_individuals=100,
        num_food_firms=2,
        num_energy_firms=2,
        num_shelter_firms=2,
    )
    sim = Simulation(config)
    sim.run()
    return sim


@pytest.fixture
def medium_sim():
    """A 90-day sim with default population."""
    config = SimConfig(seed=42, num_days=90)
    sim = Simulation(config)
    sim.run()
    return sim


@pytest.fixture
def ledger_only():
    """A bare ledger for unit-level account tests."""
    from engine.ledger import Ledger

    return Ledger()
