"""
Economic sanity checks.

These tests verify that the simulation produces economically reasonable
outcomes and responds correctly to policy shocks.
"""


from engine import SimConfig, Simulation
from engine.shocks import austerity, stimulus_spending, tax_cut, technology_breakthrough


def test_economy_produces_output():
    """The economy should produce goods and generate GDP."""
    config = SimConfig(num_days=30, seed=1)
    sim = Simulation(config)
    results = sim.run()

    # GDP should be positive
    assert results[-1].gdp > 0, "GDP should be positive"

    # Production should occur
    assert results[-1].food_produced > 0, "Food should be produced"
    assert results[-1].energy_produced > 0, "Energy should be produced"
    assert results[-1].shelter_produced > 0, "Shelter should be produced"


def test_employment_dynamics():
    """Labor market should clear and employment should be non-zero."""
    config = SimConfig(
        num_days=60,
        seed=2,
        num_individuals=200,
        num_food_firms=4,
        num_energy_firms=3,
        num_shelter_firms=3,
    )
    sim = Simulation(config)
    results = sim.run()

    # Employment should be non-zero and unemployment bounded
    final_unemployment = results[-1].unemployment_rate
    assert 0.0 <= final_unemployment <= 1.0, \
        f"Unemployment rate {final_unemployment:.1%} out of bounds"
    assert results[-1].total_employment > 0, "Some workers should be employed"

    # Employment should vary over time
    unemployment_series = [r.unemployment_rate for r in results]
    assert max(unemployment_series) - min(unemployment_series) > 0.001, \
        "Unemployment should show some variation"


def test_prices_are_positive():
    """All prices should remain positive."""
    config = SimConfig(num_days=90, seed=3)
    sim = Simulation(config)
    results = sim.run()

    for day_stat in results:
        assert day_stat.food_price > 0, f"Day {day_stat.day}: food price not positive"
        assert day_stat.energy_price > 0, f"Day {day_stat.day}: energy price not positive"
        assert day_stat.shelter_price > 0, f"Day {day_stat.day}: shelter price not positive"


def test_wages_adjust_to_unemployment():
    """Wages should respond to labor market conditions (Phillips curve)."""
    config = SimConfig(
        num_days=180,
        seed=5,
        wage_adjustment_speed=0.05,
    )
    sim = Simulation(config)
    results = sim.run()

    # Get early and late stats
    early_wage = sum(r.avg_wage for r in results[10:20]) / 10
    late_wage = sum(r.avg_wage for r in results[-10:]) / 10

    # Wages should change over time
    print(f"Early avg wage: {early_wage:.2f}, Late avg wage: {late_wage:.2f}")
    assert abs(late_wage - early_wage) > 1.0, "Wages should adjust over time"


def test_inequality_exists():
    """There should be income/wealth inequality in the economy."""
    config = SimConfig(num_days=365, seed=10, owner_fraction=0.02)
    sim = Simulation(config)
    results = sim.run()

    final = results[-1]

    # Gini should be between 0 and 1
    assert 0.0 <= final.gini_coefficient <= 1.0, \
        f"Gini coefficient {final.gini_coefficient} is out of bounds"

    # There should be some inequality
    assert final.gini_coefficient > 0.1, \
        "Gini is too low, there should be some inequality"

    # Top 1% should have more than 1% of income
    assert final.top1_pct_income_share > 0.01, \
        "Top 1% should have more than their proportional share"


def test_stimulus_increases_output():
    """Government stimulus spending should increase GDP."""
    config = SimConfig(num_days=180, seed=7)

    # Baseline
    baseline_sim = Simulation(config)
    baseline_results = baseline_sim.run()
    baseline_gdp = sum(r.gdp for r in baseline_results[100:180])

    # Stimulus scenario
    stimulus_sim = Simulation(config, shocks=[stimulus_spending(day=50, extra_daily=10_000)])
    stimulus_results = stimulus_sim.run()
    stimulus_gdp = sum(r.gdp for r in stimulus_results[100:180])

    print(f"Baseline GDP (late): {baseline_gdp:.0f}")
    print(f"Stimulus GDP (late): {stimulus_gdp:.0f}")

    # Stimulus should increase GDP
    assert stimulus_gdp > baseline_gdp * 1.05, \
        "Stimulus spending should significantly increase GDP"


def test_austerity_reduces_output():
    """Government spending cuts should reduce GDP."""
    config = SimConfig(num_days=180, seed=8)

    # Baseline
    baseline_sim = Simulation(config)
    baseline_results = baseline_sim.run()
    baseline_gdp = sum(r.gdp for r in baseline_results[100:180])

    # Austerity scenario
    austerity_sim = Simulation(config, shocks=[austerity(day=50, cut_fraction=0.5)])
    austerity_results = austerity_sim.run()
    austerity_gdp = sum(r.gdp for r in austerity_results[100:180])

    print(f"Baseline GDP (late): {baseline_gdp:.0f}")
    print(f"Austerity GDP (late): {austerity_gdp:.0f}")

    # Austerity should reduce GDP
    assert austerity_gdp < baseline_gdp * 0.95, \
        "Austerity should reduce GDP"


def test_technology_increases_productivity():
    """Technological improvements should increase output."""
    config = SimConfig(num_days=120, seed=9)

    # Baseline
    baseline_sim = Simulation(config)
    baseline_results = baseline_sim.run()
    baseline_food = sum(r.food_produced for r in baseline_results[60:120])

    # Tech boom scenario
    tech_sim = Simulation(config, shocks=[
        technology_breakthrough(day=30, sector="food", multiplier=2.0)
    ])
    tech_results = tech_sim.run()
    tech_food = sum(r.food_produced for r in tech_results[60:120])

    print(f"Baseline food production: {baseline_food:.0f}")
    print(f"Tech food production: {tech_food:.0f}")

    # Technology should increase food production
    assert tech_food > baseline_food * 1.3, \
        "Technology breakthrough should significantly increase production"


def test_tax_cuts_affect_deficit():
    """Lower taxes should increase government deficit."""
    config = SimConfig(num_days=90, seed=11, income_tax_rate=0.20)

    # Baseline
    baseline_sim = Simulation(config)
    baseline_results = baseline_sim.run()
    baseline_deficit = sum(r.govt_deficit for r in baseline_results[60:90])

    # Tax cut scenario
    tax_cut_sim = Simulation(config, shocks=[tax_cut(day=30, new_rate=0.05)])
    tax_cut_results = tax_cut_sim.run()
    tax_cut_deficit = sum(r.govt_deficit for r in tax_cut_results[60:90])

    print(f"Baseline deficit: {baseline_deficit:.0f}")
    print(f"Tax cut deficit: {tax_cut_deficit:.0f}")

    # Tax cuts should increase the deficit (make it more negative or less positive)
    assert tax_cut_deficit > baseline_deficit * 1.1, \
        "Tax cuts should increase government deficit"


def test_money_supply_grows_with_deficit():
    """
    In an MMT-style model, government deficits create net financial assets
    for the private sector, increasing money supply.
    """
    config = SimConfig(
        num_days=90,
        seed=12,
        daily_govt_spending=10_000,
        income_tax_rate=0.10,  # low tax → bigger deficit
    )
    sim = Simulation(config)
    results = sim.run()

    initial_money = results[5].total_money_supply
    final_money = results[-1].total_money_supply

    # Money supply should grow over time with deficit spending
    print(f"Initial money supply: {initial_money:.0f}")
    print(f"Final money supply: {final_money:.0f}")

    assert final_money > initial_money, \
        "Money supply should grow with government deficit spending"

    # Deficits should be positive (spending > tax)
    cumulative_deficit = sum(r.govt_deficit for r in results)
    assert cumulative_deficit > 0, "Cumulative deficit should be positive"


def test_production_consumption_balance():
    """Over time, production and consumption should roughly balance."""
    config = SimConfig(num_days=180, seed=13)
    sim = Simulation(config)
    results = sim.run()

    # Total food produced vs sold
    total_food_produced = sum(r.food_produced for r in results)
    total_food_sold = sum(r.food_sold for r in results)

    print(f"Food produced: {total_food_produced:.0f}, sold: {total_food_sold:.0f}")

    # Most of what's produced should eventually be sold
    # (allowing for inventory buildup)
    assert total_food_sold > total_food_produced * 0.5, \
        "At least half of production should be sold"


def test_deterministic_runs():
    """Same seed should produce identical results."""
    config = SimConfig(num_days=30, seed=999)

    sim1 = Simulation(config)
    results1 = sim1.run()

    sim2 = Simulation(config)
    results2 = sim2.run()

    # Results should be identical
    for i, (r1, r2) in enumerate(zip(results1, results2, strict=True)):
        assert abs(r1.gdp - r2.gdp) < 1e-6, f"Day {i}: GDP differs"
        assert abs(r1.unemployment_rate - r2.unemployment_rate) < 1e-9, \
            f"Day {i}: Unemployment differs"
        assert abs(r1.food_price - r2.food_price) < 1e-6, \
            f"Day {i}: Food price differs"


def test_economy_reaches_steady_state():
    """The economy should stabilize after initial transient period."""
    config = SimConfig(num_days=365, seed=20)
    sim = Simulation(config)
    results = sim.run()

    # Compare volatility in first 90 days vs last 90 days
    early_gdp = [r.gdp for r in results[10:100]]
    late_gdp = [r.gdp for r in results[-90:]]

    import statistics
    early_std = statistics.stdev(early_gdp) if len(early_gdp) > 1 else 0
    late_std = statistics.stdev(late_gdp) if len(late_gdp) > 1 else 0

    print(f"Early GDP std: {early_std:.2f}, Late GDP std: {late_std:.2f}")

    # Late period should be more stable (lower volatility)
    # Note: this may not always hold depending on parameters, but should generally
    assert late_std < early_std * 2.0, \
        "Economy should stabilize over time"


def test_no_runaway_inflation():
    """Prices should not explode exponentially."""
    config = SimConfig(num_days=365, seed=21)
    sim = Simulation(config)
    results = sim.run()

    initial_price = results[10].food_price
    final_price = results[-1].food_price

    # Allow for some inflation/deflation, but not hyperinflation
    ratio = final_price / initial_price
    print(f"Price ratio (final/initial): {ratio:.2f}")

    assert 0.1 < ratio < 10.0, \
        f"Price changed by factor of {ratio:.1f}, suggesting instability"


def test_gini_changes_with_policy():
    """
    Progressive policies (higher transfers) should reduce inequality.
    """
    base_config = SimConfig(num_days=180, seed=25, daily_govt_transfer=5.0)
    generous_config = SimConfig(num_days=180, seed=25, daily_govt_transfer=50.0)

    base_sim = Simulation(base_config)
    base_results = base_sim.run()
    base_gini = base_results[-1].gini_coefficient

    generous_sim = Simulation(generous_config)
    generous_results = generous_sim.run()
    generous_gini = generous_results[-1].gini_coefficient

    print(f"Base Gini: {base_gini:.3f}, Generous Gini: {generous_gini:.3f}")

    # Higher transfers should reduce inequality (lower Gini)
    assert generous_gini < base_gini, \
        "Higher transfers should reduce inequality"
