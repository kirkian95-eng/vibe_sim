"""
Scenario shocks — policy changes, technology breakthroughs, etc.

A Shock is a callable that modifies the SimConfig (or actors/ledger)
on a given day.  Shocks are registered before the simulation runs.
"""

from __future__ import annotations

import dataclasses as dc
from collections.abc import Callable

from .config import SimConfig


@dc.dataclass
class Shock:
    """A discrete event that changes simulation parameters."""

    name: str
    day: int  # when the shock fires
    description: str
    apply: Callable[[SimConfig], SimConfig]  # returns modified config

    def __repr__(self):
        return f"Shock({self.name!r}, day={self.day})"


# ── Pre-built shock factories ───────────────────────────────────────


def tax_hike(day: int, new_rate: float) -> Shock:
    """Increase income tax rate."""
    def _apply(cfg: SimConfig) -> SimConfig:
        return dc.replace(cfg, income_tax_rate=new_rate)
    return Shock(
        name=f"tax_hike_{new_rate:.0%}",
        day=day,
        description=f"Income tax rate increased to {new_rate:.0%}",
        apply=_apply,
    )


def tax_cut(day: int, new_rate: float) -> Shock:
    """Decrease income tax rate."""
    def _apply(cfg: SimConfig) -> SimConfig:
        return dc.replace(cfg, income_tax_rate=new_rate)
    return Shock(
        name=f"tax_cut_{new_rate:.0%}",
        day=day,
        description=f"Income tax rate decreased to {new_rate:.0%}",
        apply=_apply,
    )


def technology_breakthrough(day: int, sector: str, multiplier: float) -> Shock:
    """Productivity boost in a sector."""
    def _apply(cfg: SimConfig) -> SimConfig:
        field = f"{sector}_productivity"
        old = getattr(cfg, field)
        return dc.replace(cfg, **{field: old * multiplier})
    return Shock(
        name=f"tech_{sector}_{multiplier:.1f}x",
        day=day,
        description=f"{sector} productivity multiplied by {multiplier:.1f}x",
        apply=_apply,
    )


def stimulus_spending(day: int, extra_daily: float) -> Shock:
    """Increase government daily spending."""
    def _apply(cfg: SimConfig) -> SimConfig:
        return dc.replace(cfg, daily_govt_spending=cfg.daily_govt_spending + extra_daily)
    return Shock(
        name=f"stimulus_{extra_daily:.0f}",
        day=day,
        description=f"Government daily spending increased by {extra_daily:.0f}",
        apply=_apply,
    )


def austerity(day: int, cut_fraction: float) -> Shock:
    """Cut government spending and transfers."""
    def _apply(cfg: SimConfig) -> SimConfig:
        return dc.replace(
            cfg,
            daily_govt_spending=cfg.daily_govt_spending * (1 - cut_fraction),
            daily_govt_transfer=cfg.daily_govt_transfer * (1 - cut_fraction),
        )
    return Shock(
        name=f"austerity_{cut_fraction:.0%}",
        day=day,
        description=f"Government spending cut by {cut_fraction:.0%}",
        apply=_apply,
    )


def minimum_wage_increase(day: int, new_min_wage: float) -> Shock:
    """Raise the minimum wage."""
    def _apply(cfg: SimConfig) -> SimConfig:
        return dc.replace(cfg, min_wage=new_min_wage)
    return Shock(
        name=f"min_wage_{new_min_wage:.0f}",
        day=day,
        description=f"Minimum wage raised to {new_min_wage:.0f}",
        apply=_apply,
    )


def energy_crisis(day: int, productivity_drop: float = 0.5) -> Shock:
    """Energy sector productivity drops (supply shock)."""
    def _apply(cfg: SimConfig) -> SimConfig:
        return dc.replace(cfg, energy_productivity=cfg.energy_productivity * productivity_drop)
    return Shock(
        name="energy_crisis",
        day=day,
        description=f"Energy productivity dropped to {productivity_drop:.0%} of previous",
        apply=_apply,
    )


# ── Factory from dict (for API) ─────────────────────────────────────

SHOCK_FACTORIES = {
    "tax_hike": lambda d: tax_hike(d["day"], d["value"]),
    "tax_cut": lambda d: tax_cut(d["day"], d["value"]),
    "technology_breakthrough": lambda d: technology_breakthrough(d["day"], d["sector"], d["value"]),
    "stimulus_spending": lambda d: stimulus_spending(d["day"], d["value"]),
    "austerity": lambda d: austerity(d["day"], d["value"]),
    "minimum_wage_increase": lambda d: minimum_wage_increase(d["day"], d["value"]),
    "energy_crisis": lambda d: energy_crisis(d["day"], d.get("value", 0.5)),
}


def shock_from_dict(d: dict) -> Shock | None:
    """Create a Shock from a JSON-style dict: {type, day, value, ...}."""
    factory = SHOCK_FACTORIES.get(d.get("type", ""))
    if factory:
        return factory(d)
    return None


# ── Scenario presets ────────────────────────────────────────────────

SCENARIOS: dict[str, list[Shock]] = {
    "baseline": [],
    "stimulus": [
        stimulus_spending(day=90, extra_daily=10_000),
    ],
    "austerity": [
        austerity(day=90, cut_fraction=0.50),
    ],
    "tax_reform": [
        tax_cut(day=90, new_rate=0.10),
    ],
    "tech_boom": [
        technology_breakthrough(day=90, sector="food", multiplier=2.0),
        technology_breakthrough(day=90, sector="energy", multiplier=1.5),
    ],
    "energy_crisis": [
        energy_crisis(day=90, productivity_drop=0.4),
    ],
    "stagflation": [
        energy_crisis(day=90, productivity_drop=0.5),
        stimulus_spending(day=120, extra_daily=15_000),
    ],
}
