"""Minimal CLI entry point for vibe-sim."""

from __future__ import annotations

import argparse
import sys

from .config import SimConfig
from .simulation import Simulation


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="vibe-sim",
        description="Run a VibeSim macroeconomic simulation.",
    )
    parser.add_argument("--months", type=int, default=60, help="Number of months to simulate")
    parser.add_argument("--agents", type=int, default=200, help="Number of individuals")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--config", type=str, default=None, help="Path to a YAML config file"
    )
    args = parser.parse_args(argv)

    if args.config:
        from .io import load_config_yaml

        config = load_config_yaml(args.config)
    else:
        config = SimConfig(
            num_months=args.months,
            num_individuals=args.agents,
            seed=args.seed,
        )

    sim = Simulation(config)
    results = sim.run()

    final = results[-1]
    print(f"Completed {config.num_months} months with {config.num_individuals} agents (seed={config.seed})")
    print(f"  GDP:           {final.gdp:>12,.0f}")
    print(f"  Unemployment:  {final.unemployment_rate:>11.1%}")
    print(f"  Population:    {final.population:>12,}")
    print(f"  Gini:          {final.gini_coefficient:>12.3f}")

    if not sim.ledger.check_all_entries_balanced():
        print("WARNING: ledger has unbalanced entries", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
