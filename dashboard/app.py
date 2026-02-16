"""
Flask dashboard for the economic simulation.

Provides:
  - GET  /           → main dashboard page
  - POST /api/run    → run a simulation with given config, return JSON results
  - GET  /api/scenarios → list available scenario presets
"""

from __future__ import annotations

import dataclasses as dc
import json
import os
from typing import List

from flask import Flask, jsonify, render_template, request

from engine import SimConfig, Simulation
from engine.shocks import SCENARIOS, Shock, shock_from_dict

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "static"),
)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/scenarios")
def list_scenarios():
    result = {}
    for name, shocks in SCENARIOS.items():
        result[name] = [
            {"name": s.name, "month": s.month, "description": s.description}
            for s in shocks
        ]
    return jsonify(result)


@app.route("/api/run", methods=["POST"])
def run_simulation():
    data = request.get_json(force=True) if request.data else {}

    # Build config from defaults + overrides
    config_overrides = data.get("config", {})
    cfg = SimConfig(**{
        k: v for k, v in config_overrides.items()
        if hasattr(SimConfig, k)
    })

    # Load shocks
    scenario_name = data.get("scenario", "baseline")
    shocks: List[Shock] = []
    if scenario_name in SCENARIOS:
        shocks = list(SCENARIOS[scenario_name])

    # Add custom shocks
    for s in data.get("custom_shocks", []):
        shock = shock_from_dict(s)
        if shock:
            shocks.append(shock)

    # Run simulation
    sim = Simulation(cfg, shocks=shocks)
    sim.run()

    return jsonify(sim.results_summary())


def main():
    app.run(host="0.0.0.0", port=5001, debug=True)


if __name__ == "__main__":
    main()
