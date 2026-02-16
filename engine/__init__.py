"""
VibeSim -- Research-grade macroeconomic simulation engine.

Public API::

    from engine import Simulation, SimConfig, DailyStats
    from engine.shocks import stimulus_spending
    from engine.io import save_run_artifacts, load_config_yaml
"""

from .config import SimConfig
from .metrics import DailyStats, compute_gini
from .simulation import Simulation

__version__ = "0.1.0"

__all__ = [
    "SimConfig",
    "Simulation",
    "DailyStats",
    "compute_gini",
    "__version__",
]
