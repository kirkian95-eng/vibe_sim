"""
Scenario shocks — policy changes, technology breakthroughs, etc.

A Shock is a callable that modifies the SimConfig on a given month.
Shocks are registered before the simulation runs.
"""

from __future__ import annotations

import dataclasses as dc
from collections.abc import Callable

from .config import SimConfig


@dc.dataclass
class Shock:
    """A discrete event that changes simulation parameters."""

    name: str
    month: int  # when the shock fires
    description: str
    apply: Callable[[SimConfig], SimConfig]  # returns modified config

    def __repr__(self):
        return f"Shock({self.name!r}, month={self.month})"


# ── Pre-built shock factories ───────────────────────────────────────


def tax_hike(month: int, new_rate: float) -> Shock:
    """Increase income tax rate."""
    def _apply(cfg: SimConfig) -> SimConfig:
        return dc.replace(cfg, income_tax_rate=new_rate)
    return Shock(
        name=f"tax_hike_{new_rate:.0%}",
        month=month,
        description=f"Income tax rate increased to {new_rate:.0%}",
        apply=_apply,
    )


def tax_cut(month: int, new_rate: float) -> Shock:
    """Decrease income tax rate."""
    def _apply(cfg: SimConfig) -> SimConfig:
        return dc.replace(cfg, income_tax_rate=new_rate)
    return Shock(
        name=f"tax_cut_{new_rate:.0%}",
        month=month,
        description=f"Income tax rate decreased to {new_rate:.0%}",
        apply=_apply,
    )


def technology_breakthrough(month: int, sector: str, multiplier: float) -> Shock:
    """Productivity boost in a sector."""
    def _apply(cfg: SimConfig) -> SimConfig:
        field = f"{sector}_productivity"
        old = getattr(cfg, field)
        return dc.replace(cfg, **{field: old * multiplier})
    return Shock(
        name=f"tech_{sector}_{multiplier:.1f}x",
        month=month,
        description=f"{sector} productivity multiplied by {multiplier:.1f}x",
        apply=_apply,
    )


def stimulus_spending(month: int, extra_per_capita: float) -> Shock:
    """Increase government monthly spending (per capita, scales with population)."""
    def _apply(cfg: SimConfig) -> SimConfig:
        extra_total = extra_per_capita * cfg.num_individuals
        return dc.replace(cfg, monthly_govt_spending=cfg.monthly_govt_spending + extra_total)
    return Shock(
        name=f"stimulus_{extra_per_capita:.0f}_pc",
        month=month,
        description=f"Government monthly spending increased by {extra_per_capita:.0f}/capita",
        apply=_apply,
    )


def austerity(month: int, cut_fraction: float) -> Shock:
    """Cut government spending and transfers."""
    def _apply(cfg: SimConfig) -> SimConfig:
        return dc.replace(
            cfg,
            monthly_govt_spending=cfg.monthly_govt_spending * (1 - cut_fraction),
            monthly_govt_transfer=cfg.monthly_govt_transfer * (1 - cut_fraction),
        )
    return Shock(
        name=f"austerity_{cut_fraction:.0%}",
        month=month,
        description=f"Government spending cut by {cut_fraction:.0%}",
        apply=_apply,
    )


def minimum_wage_increase(month: int, new_min_wage: float) -> Shock:
    """Raise the minimum wage."""
    def _apply(cfg: SimConfig) -> SimConfig:
        return dc.replace(cfg, min_wage=new_min_wage)
    return Shock(
        name=f"min_wage_{new_min_wage:.0f}",
        month=month,
        description=f"Minimum wage raised to {new_min_wage:.0f}",
        apply=_apply,
    )


def energy_crisis(month: int, productivity_drop: float = 0.5) -> Shock:
    """Energy sector productivity drops (supply shock)."""
    def _apply(cfg: SimConfig) -> SimConfig:
        return dc.replace(cfg, energy_productivity=cfg.energy_productivity * productivity_drop)
    return Shock(
        name="energy_crisis",
        month=month,
        description=f"Energy productivity dropped to {productivity_drop:.0%} of previous",
        apply=_apply,
    )


# ── Factory from dict (for API) ─────────────────────────────────────

SHOCK_FACTORIES = {
    "tax_hike": lambda d: tax_hike(d["month"], d["value"]),
    "tax_cut": lambda d: tax_cut(d["month"], d["value"]),
    "technology_breakthrough": lambda d: technology_breakthrough(d["month"], d["sector"], d["value"]),
    "stimulus_spending": lambda d: stimulus_spending(d["month"], d["value"]),
    "austerity": lambda d: austerity(d["month"], d["value"]),
    "minimum_wage_increase": lambda d: minimum_wage_increase(d["month"], d["value"]),
    "energy_crisis": lambda d: energy_crisis(d["month"], d.get("value", 0.5)),
}


def shock_from_dict(d: dict) -> Shock | None:
    """Create a Shock from a JSON-style dict: {type, month, value, ...}."""
    factory = SHOCK_FACTORIES.get(d.get("type", ""))
    if factory:
        return factory(d)
    return None


# ── Scenario presets ────────────────────────────────────────────────

SCENARIOS: dict[str, list[Shock]] = {
    "baseline": [],
    "stimulus": [
        stimulus_spending(month=6, extra_per_capita=300),
    ],
    "austerity": [
        austerity(month=6, cut_fraction=0.50),
    ],
    "tax_reform": [
        tax_cut(month=6, new_rate=0.10),
    ],
    "tech_boom": [
        technology_breakthrough(month=6, sector="food", multiplier=2.0),
        technology_breakthrough(month=6, sector="energy", multiplier=1.5),
    ],
    "energy_crisis": [
        energy_crisis(month=6, productivity_drop=0.4),
    ],
    "stagflation": [
        energy_crisis(month=6, productivity_drop=0.5),
        stimulus_spending(month=9, extra_per_capita=450),
    ],
}
