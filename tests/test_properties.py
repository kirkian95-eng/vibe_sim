"""
Property-based and randomized tests.

Uses hypothesis to verify that accounting invariants hold under
random configurations and seeds. Runs 50-200 ticks per test.
"""

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from engine import SimConfig, Simulation

# ── Strategy for valid SimConfig ─────────────────────────────────────

sim_config_strategy = st.builds(
    SimConfig,
    seed=st.integers(min_value=1, max_value=100_000),
    num_days=st.integers(min_value=30, max_value=90),
    num_individuals=st.integers(min_value=20, max_value=50),
    num_food_firms=st.integers(min_value=1, max_value=3),
    num_energy_firms=st.integers(min_value=1, max_value=3),
    num_shelter_firms=st.integers(min_value=1, max_value=3),
    income_tax_rate=st.floats(min_value=0.01, max_value=0.50),
    sales_tax_rate=st.floats(min_value=0.0, max_value=0.20),
    daily_govt_transfer=st.floats(min_value=1.0, max_value=100.0),
    daily_govt_spending=st.floats(min_value=1000.0, max_value=20000.0),
    initial_wage=st.floats(min_value=30.0, max_value=200.0),
)


# ── Property: journal entries always balance ─────────────────────────


@given(config=sim_config_strategy)
@settings(
    max_examples=15,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_journal_always_balanced(config):
    """For any valid config, every journal entry must balance."""
    sim = Simulation(config)
    sim.run()
    for entry in sim.ledger.journal:
        assert entry.is_balanced(), (
            f"Entry #{entry.entry_id} unbalanced with config seed={config.seed}"
        )


# ── Property: balance sheet equation holds for all actors ────────────


@given(config=sim_config_strategy)
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_balance_sheet_always_holds(config):
    """A == L + E + R - X must hold for every actor under any valid config."""
    sim = Simulation(config)
    sim.run()

    for ind in sim.individuals:
        assert sim.ledger.check_balance_sheet_equation(ind.id), (
            f"Balance sheet fails for {ind.id} (seed={config.seed})"
        )
    for firm in sim.firms:
        assert sim.ledger.check_balance_sheet_equation(firm.id), (
            f"Balance sheet fails for {firm.id} (seed={config.seed})"
        )
    assert sim.ledger.check_balance_sheet_equation(sim.bank.id)
    assert sim.ledger.check_balance_sheet_equation(sim.govt.id)


# ── Property: system balance (total debit-normal == total credit-normal)


@given(config=sim_config_strategy)
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_system_balance_always_holds(config):
    """System-wide debit balances must equal credit balances."""
    sim = Simulation(config)
    sim.run()
    assert sim.ledger.check_system_balance(), (
        f"System balance fails with seed={config.seed}"
    )


# ── Property: replay matches running balances ────────────────────────


@given(config=sim_config_strategy)
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_replay_matches_running(config):
    """Running balances must match a full journal replay."""
    sim = Simulation(config)
    sim.run()
    assert sim.ledger.verify_running_balances(), (
        f"Replay mismatch with seed={config.seed}"
    )


# ── Property: GDP is non-negative ────────────────────────────────────


@given(config=sim_config_strategy)
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_gdp_non_negative(config):
    """GDP should never be negative."""
    sim = Simulation(config)
    results = sim.run()
    for stat in results:
        assert stat.gdp >= 0, (
            f"Negative GDP on day {stat.day} (seed={config.seed})"
        )


# ── Property: prices always positive ────────────────────────────────


@given(config=sim_config_strategy)
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_prices_always_positive(config):
    """All prices must remain positive."""
    sim = Simulation(config)
    results = sim.run()
    for stat in results:
        assert stat.food_price > 0, f"Food price <= 0 day {stat.day}"
        assert stat.energy_price > 0, f"Energy price <= 0 day {stat.day}"
        assert stat.shelter_price > 0, f"Shelter price <= 0 day {stat.day}"


# ── Deterministic: same seed, same result ────────────────────────────


@given(seed=st.integers(min_value=1, max_value=10000))
@settings(max_examples=5, deadline=None)
def test_deterministic_with_random_seed(seed):
    """Same seed must produce identical results."""
    config = SimConfig(num_days=30, seed=seed, num_individuals=100)

    sim1 = Simulation(config)
    r1 = sim1.run()

    sim2 = Simulation(config)
    r2 = sim2.run()

    for i, (a, b) in enumerate(zip(r1, r2, strict=True)):
        assert abs(a.gdp - b.gdp) < 1e-6, f"Day {i}: GDP differs for seed={seed}"
        assert abs(a.unemployment_rate - b.unemployment_rate) < 1e-9
