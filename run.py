#!/usr/bin/env python3
"""
VibeSim — Economic and Monetary Simulation Engine

Usage:
    python run.py                      # Run the dashboard
    python run.py --demo               # Run a demo simulation (CLI)
    python run.py --test               # Run tests
"""

import argparse
import sys


def run_dashboard():
    """Start the Flask dashboard."""
    from dashboard.app import main
    print("Starting VibeSim dashboard on http://localhost:5001")
    print("Press Ctrl+C to stop")
    main()


def run_demo():
    """Run a demo simulation and print results."""
    from engine import SimConfig, Simulation
    from engine.shocks import SCENARIOS

    print("=" * 70)
    print("VibeSim v0.2 Demo — Baseline vs Stimulus Comparison")
    print("=" * 70)

    config = SimConfig(
        num_months=24,
        seed=42,
        num_individuals=50,
        num_food_firms=2,
        num_energy_firms=2,
        num_shelter_firms=0,  # govt provides shelter
    )

    # Baseline
    print("\n[1/2] Running baseline scenario (24 months)...")
    baseline = Simulation(config)
    baseline_results = baseline.run()
    baseline_final = baseline_results[-1]

    print(f"  Complete: {baseline.ledger.journal_size} journal entries")
    print(f"  Final GDP: ${baseline_final.gdp:,.0f}")
    print(f"  Unemployment: {baseline_final.unemployment_rate:.1%}")
    print(f"  Population: {baseline_final.population}")
    print(f"  Gini coefficient: {baseline_final.gini_coefficient:.3f}")
    print(f"  Accounting valid: {baseline.results_summary()['accounting_valid']}")

    # Stimulus
    print("\n[2/2] Running stimulus scenario...")
    stimulus = Simulation(config, shocks=SCENARIOS["stimulus"])
    stimulus_results = stimulus.run()
    stimulus_final = stimulus_results[-1]

    print(f"  Complete: {stimulus.ledger.journal_size} journal entries")
    print(f"  Shocks applied: {', '.join(stimulus.shock_log)}")
    print(f"  Final GDP: ${stimulus_final.gdp:,.0f}")
    print(f"  Unemployment: {stimulus_final.unemployment_rate:.1%}")
    print(f"  Gini coefficient: {stimulus_final.gini_coefficient:.3f}")
    print(f"  Accounting valid: {stimulus.results_summary()['accounting_valid']}")

    # Comparison
    print("\n" + "=" * 70)
    print("Comparison (Stimulus vs Baseline)")
    print("=" * 70)
    if baseline_final.gdp > 0:
        gdp_change = (stimulus_final.gdp - baseline_final.gdp) / baseline_final.gdp * 100
    else:
        gdp_change = 0.0
    unemp_change = stimulus_final.unemployment_rate - baseline_final.unemployment_rate
    gini_change = stimulus_final.gini_coefficient - baseline_final.gini_coefficient

    print(f"  GDP change: {gdp_change:+.1f}%")
    print(f"  Unemployment change: {unemp_change:+.1%} percentage points")
    print(f"  Gini change: {gini_change:+.3f}")
    print()

    print("\n" + "=" * 70)
    print("Demo complete! Run 'python run.py' to launch the dashboard.")
    print("=" * 70)


def run_tests():
    """Run the test suite."""
    import pytest
    print("Running test suite...")
    exit_code = pytest.main(["-v", "tests/"])
    sys.exit(exit_code)


def main():
    parser = argparse.ArgumentParser(description="VibeSim Economic Simulation Engine")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run a demo simulation (CLI output)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run the test suite",
    )

    args = parser.parse_args()

    if args.demo:
        run_demo()
    elif args.test:
        run_tests()
    else:
        run_dashboard()


if __name__ == "__main__":
    main()
