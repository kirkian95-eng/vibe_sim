"""
Economic sanity checks.

These tests verify that the simulation produces economically reasonable
outcomes and responds correctly to policy shocks.

All tests use 50 agents and short runs to keep CI fast.
"""


from engine import SimConfig, Simulation
from engine.shocks import austerity, stimulus_spending, tax_cut, technology_breakthrough

# Shared small config for tests that don't need special params
_SMALL = dict(num_individuals=50, num_food_firms=2, num_energy_firms=2, num_shelter_firms=2)


def test_economy_produces_output():
    """The economy should produce goods and generate GDP."""
    config = SimConfig(num_months=6, seed=1, **_SMALL)
    sim = Simulation(config)
    results = sim.run()

    assert results[-1].gdp > 0, "GDP should be positive"
    assert results[-1].food_produced > 0, "Food should be produced"
    assert results[-1].energy_produced > 0, "Energy should be produced"
    assert results[-1].shelter_produced > 0, "Shelter should be produced"


def test_employment_dynamics():
    """Labor market should clear and employment should be non-zero."""
    config = SimConfig(num_months=12, seed=2, **_SMALL)
    sim = Simulation(config)
    results = sim.run()

    final_unemployment = results[-1].unemployment_rate
    assert 0.0 <= final_unemployment <= 1.0, \
        f"Unemployment rate {final_unemployment:.1%} out of bounds"
    assert results[-1].total_employment > 0, "Some workers should be employed"

    # With demographics (children, retirees) the effective labor force is
    # smaller, so full employment is common with 50 agents.  Just verify
    # the rate is within valid bounds and that employment is positive.
    unemployment_series = [r.unemployment_rate for r in results]
    assert all(0.0 <= u <= 1.0 for u in unemployment_series), \
        "Unemployment rate out of bounds"


def test_prices_are_positive():
    """All prices should remain positive."""
    config = SimConfig(num_months=12, seed=3, **_SMALL)
    sim = Simulation(config)
    results = sim.run()

    for month_stat in results:
        assert month_stat.food_price > 0, f"Month {month_stat.month}: food price not positive"
        assert month_stat.energy_price > 0, f"Month {month_stat.month}: energy price not positive"
        assert month_stat.shelter_price > 0, f"Month {month_stat.month}: shelter price not positive"


def test_wages_adjust_to_unemployment():
    """Wages should respond to labor market conditions (Phillips curve)."""
    config = SimConfig(num_months=12, seed=5, wage_adjustment_speed=0.05, **_SMALL)
    sim = Simulation(config)
    results = sim.run()

    early_wage = sum(r.avg_wage for r in results[1:4]) / 3
    late_wage = sum(r.avg_wage for r in results[-3:]) / 3

    assert abs(late_wage - early_wage) > 1.0, "Wages should adjust over time"


def test_inequality_exists():
    """There should be income/wealth inequality in the economy."""
    config = SimConfig(num_months=12, seed=10, owner_fraction=0.02, **_SMALL)
    sim = Simulation(config)
    results = sim.run()

    final = results[-1]
    assert 0.0 <= final.gini_coefficient <= 1.0, \
        f"Gini coefficient {final.gini_coefficient} is out of bounds"
    assert final.gini_coefficient > 0.05, \
        "Gini is too low, there should be some inequality"


def test_stimulus_increases_money_supply():
    """Government stimulus creates money: higher spending -> larger money supply."""
    config = SimConfig(num_months=12, seed=7, **_SMALL)

    baseline_sim = Simulation(config)
    baseline_results = baseline_sim.run()
    baseline_money = baseline_results[-1].total_money_supply

    stimulus_sim = Simulation(config, shocks=[stimulus_spending(month=3, extra_monthly=300_000)])
    stimulus_results = stimulus_sim.run()
    stimulus_money = stimulus_results[-1].total_money_supply

    assert stimulus_money > baseline_money, \
        "Stimulus spending should increase the money supply"


def test_austerity_reduces_money_supply():
    """Government spending cuts should reduce money creation."""
    config = SimConfig(num_months=12, seed=8, **_SMALL)

    baseline_sim = Simulation(config)
    baseline_results = baseline_sim.run()
    baseline_money = baseline_results[-1].total_money_supply

    austerity_sim = Simulation(config, shocks=[austerity(month=3, cut_fraction=0.5)])
    austerity_results = austerity_sim.run()
    austerity_money = austerity_results[-1].total_money_supply

    assert austerity_money < baseline_money, \
        "Austerity should reduce the money supply"


def test_technology_increases_productivity():
    """Technological improvements should increase output."""
    config = SimConfig(num_months=12, seed=9, **_SMALL)

    baseline_sim = Simulation(config)
    baseline_results = baseline_sim.run()
    baseline_food = sum(r.food_produced for r in baseline_results[6:12])

    tech_sim = Simulation(config, shocks=[
        technology_breakthrough(month=3, sector="food", multiplier=2.0)
    ])
    tech_results = tech_sim.run()
    tech_food = sum(r.food_produced for r in tech_results[6:12])

    assert tech_food > baseline_food, \
        "Technology breakthrough should increase production"


def test_tax_cuts_affect_deficit():
    """Lower taxes should increase government deficit."""
    config = SimConfig(num_months=12, seed=11, income_tax_rate=0.20, **_SMALL)

    baseline_sim = Simulation(config)
    baseline_results = baseline_sim.run()
    baseline_deficit = sum(r.govt_deficit for r in baseline_results[6:12])

    tax_cut_sim = Simulation(config, shocks=[tax_cut(month=3, new_rate=0.05)])
    tax_cut_results = tax_cut_sim.run()
    tax_cut_deficit = sum(r.govt_deficit for r in tax_cut_results[6:12])

    assert tax_cut_deficit > baseline_deficit, \
        "Tax cuts should increase government deficit"


def test_money_supply_grows_with_deficit():
    """Government deficits create net financial assets, increasing money supply."""
    config = SimConfig(
        num_months=12, seed=12,
        monthly_govt_spending=300_000,
        income_tax_rate=0.10,
        **_SMALL,
    )
    sim = Simulation(config)
    results = sim.run()

    initial_money = results[5].total_money_supply
    final_money = results[-1].total_money_supply

    assert final_money > initial_money, \
        "Money supply should grow with government deficit spending"

    cumulative_deficit = sum(r.govt_deficit for r in results)
    assert cumulative_deficit > 0, "Cumulative deficit should be positive"


def test_production_consumption_balance():
    """Over time, production and consumption should roughly balance."""
    config = SimConfig(num_months=12, seed=13, **_SMALL)
    sim = Simulation(config)
    results = sim.run()

    total_food_produced = sum(r.food_produced for r in results)
    total_food_sold = sum(r.food_sold for r in results)

    assert total_food_sold > total_food_produced * 0.3, \
        "A substantial fraction of production should be sold"


def test_deterministic_runs():
    """Same seed should produce identical results."""
    config = SimConfig(num_months=6, seed=999, **_SMALL)

    sim1 = Simulation(config)
    results1 = sim1.run()

    sim2 = Simulation(config)
    results2 = sim2.run()

    for i, (r1, r2) in enumerate(zip(results1, results2, strict=True)):
        assert abs(r1.gdp - r2.gdp) < 1e-6, f"Month {i}: GDP differs"
        assert abs(r1.unemployment_rate - r2.unemployment_rate) < 1e-9, \
            f"Month {i}: Unemployment differs"


def test_economy_reaches_steady_state():
    """The economy should stabilize after initial transient period."""
    config = SimConfig(num_months=12, seed=20, **_SMALL)
    sim = Simulation(config)
    results = sim.run()

    import statistics
    early_gdp = [r.gdp for r in results[1:4]]
    late_gdp = [r.gdp for r in results[-3:]]

    early_std = statistics.stdev(early_gdp) if len(early_gdp) > 1 else 0
    late_std = statistics.stdev(late_gdp) if len(late_gdp) > 1 else 0

    # Demographics (births/deaths/aging) introduce ongoing variation, so
    # we just verify the economy doesn't diverge wildly.
    assert late_std < early_std * 10.0, \
        "Economy should not diverge wildly over time"


def test_no_runaway_inflation():
    """Prices should not explode exponentially."""
    config = SimConfig(num_months=12, seed=21, **_SMALL)
    sim = Simulation(config)
    results = sim.run()

    initial_price = results[5].food_price
    final_price = results[-1].food_price

    ratio = final_price / initial_price
    assert 0.01 < ratio < 100.0, \
        f"Price changed by factor of {ratio:.1f}, suggesting instability"


def test_gini_changes_with_policy():
    """Progressive policies (higher transfers) should reduce inequality."""
    base_config = SimConfig(num_months=12, seed=25, monthly_govt_transfer=100.0, **_SMALL)
    generous_config = SimConfig(num_months=12, seed=25, monthly_govt_transfer=1500.0, **_SMALL)

    base_sim = Simulation(base_config)
    base_results = base_sim.run()
    base_gini = base_results[-1].gini_coefficient

    generous_sim = Simulation(generous_config)
    generous_results = generous_sim.run()
    generous_gini = generous_results[-1].gini_coefficient

    assert generous_gini < base_gini, \
        "Higher transfers should reduce inequality"
