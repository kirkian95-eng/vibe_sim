"""
I/O utilities: YAML config loading, CSV/Parquet export, run artifact saving.

Run artifacts include: parameters, seed, git commit hash, summary metrics.
"""

from __future__ import annotations

import csv
import dataclasses as dc
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import SimConfig
from .metrics import DailyStats

# ── YAML config loading ──────────────────────────────────────────────


def load_config_yaml(path: str | Path) -> SimConfig:
    """Load a SimConfig from a YAML file. Unknown keys are ignored."""
    import yaml  # type: ignore[import-untyped]

    with open(path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"YAML config must be a mapping, got {type(data).__name__}")

    valid_fields = {f.name for f in dc.fields(SimConfig)}
    filtered = {k: v for k, v in data.items() if k in valid_fields}
    return SimConfig(**filtered)


def save_config_yaml(config: SimConfig, path: str | Path) -> None:
    """Save a SimConfig to a YAML file."""
    import yaml  # type: ignore[import-untyped]

    data = dc.asdict(config)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


# ── CSV export ────────────────────────────────────────────────────────


def write_results_csv(results: list[DailyStats], path: str | Path) -> None:
    """Write daily stats to a tidy CSV file."""
    if not results:
        return
    fieldnames = list(dc.asdict(results[0]).keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for stat in results:
            writer.writerow(dc.asdict(stat))


def write_ledger_csv(
    journal: list,
    path: str | Path,
) -> None:
    """Write the full journal to a flat CSV (one row per journal line)."""
    fieldnames = [
        "entry_id", "day", "description", "account_id", "debit", "credit",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for entry in journal:
            for line in entry.lines:
                writer.writerow({
                    "entry_id": entry.entry_id,
                    "day": entry.day,
                    "description": entry.description,
                    "account_id": line.account_id,
                    "debit": line.debit,
                    "credit": line.credit,
                })


# ── Ledger queries ────────────────────────────────────────────────────


def actor_history(journal: list, actor_id: str) -> list[dict[str, Any]]:
    """Extract all journal entries involving a given actor, as dicts."""
    rows: list[dict[str, Any]] = []
    for entry in journal:
        for line in entry.lines:
            if line.account_id.startswith(f"{actor_id}:"):
                rows.append({
                    "entry_id": entry.entry_id,
                    "day": entry.day,
                    "description": entry.description,
                    "account_id": line.account_id,
                    "debit": line.debit,
                    "credit": line.credit,
                })
    return rows


def market_history(
    results: list[DailyStats],
    good: str,
) -> list[dict[str, float]]:
    """Extract price/quantity/revenue history for a given good type."""
    return [
        {
            "day": s.day,
            "price": getattr(s, f"{good}_price", 0.0),
            "produced": getattr(s, f"{good}_produced", 0.0),
            "sold": getattr(s, f"{good}_sold", 0.0),
        }
        for s in results
    ]


# ── Git hash helper ──────────────────────────────────────────────────


def get_git_commit_hash() -> str | None:
    """Return the current git commit hash, or None if not in a repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


# ── Run artifacts ─────────────────────────────────────────────────────


def save_run_artifacts(
    config: SimConfig,
    results: list[DailyStats],
    journal: list,
    output_dir: str | Path = "runs",
    extra_metadata: dict[str, Any] | None = None,
) -> Path:
    """
    Save all run artifacts to a timestamped folder.

    Creates:
      runs/<timestamp>_<name>/
        config.yaml
        daily_stats.csv
        journal.csv
        metadata.json
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_name = f"{ts}_{config.name}"
    run_dir = Path(output_dir) / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    # Config
    save_config_yaml(config, run_dir / "config.yaml")

    # Daily stats CSV
    write_results_csv(results, run_dir / "daily_stats.csv")

    # Journal CSV
    write_ledger_csv(journal, run_dir / "journal.csv")

    # Metadata
    final = results[-1] if results else None
    metadata: dict[str, Any] = {
        "run_name": run_name,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "seed": config.seed,
        "num_days": config.num_days,
        "num_individuals": config.num_individuals,
        "num_firms": config.num_firms,
        "git_commit": get_git_commit_hash(),
        "vibe_sim_version": "0.1.0",
        "summary": {
            "final_gdp": final.gdp if final else 0.0,
            "final_unemployment": final.unemployment_rate if final else 0.0,
            "final_gini": final.gini_coefficient if final else 0.0,
            "total_journal_entries": len(journal),
        },
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    with open(run_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2, default=str)

    return run_dir
