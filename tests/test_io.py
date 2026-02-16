"""
Tests for I/O utilities: YAML config, CSV export, run artifacts.
"""

import json

from engine import SimConfig
from engine.io import (
    actor_history,
    load_config_yaml,
    market_history,
    save_config_yaml,
    save_run_artifacts,
    write_ledger_csv,
    write_results_csv,
)


class TestYAMLConfig:
    def test_round_trip(self, tmp_path):
        cfg = SimConfig(seed=123, num_days=90, income_tax_rate=0.15)
        path = tmp_path / "config.yaml"
        save_config_yaml(cfg, path)
        loaded = load_config_yaml(path)
        assert loaded.seed == 123
        assert loaded.num_days == 90
        assert abs(loaded.income_tax_rate - 0.15) < 1e-9

    def test_unknown_keys_ignored(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text("seed: 999\nnum_days: 10\nbogus_key: hello\n")
        cfg = load_config_yaml(path)
        assert cfg.seed == 999
        assert cfg.num_days == 10


class TestCSVExport:
    def test_write_results_csv(self, tmp_path, small_sim):
        path = tmp_path / "results.csv"
        write_results_csv(small_sim.history, path)
        assert path.exists()
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 31  # header + 30 days
        assert "gdp" in lines[0]

    def test_write_ledger_csv(self, tmp_path, small_sim):
        path = tmp_path / "journal.csv"
        write_ledger_csv(small_sim.ledger.journal, path)
        assert path.exists()
        lines = path.read_text().strip().split("\n")
        assert len(lines) > 100  # header + many entries
        assert "entry_id" in lines[0]


class TestRunArtifacts:
    def test_save_creates_folder(self, tmp_path, small_sim):
        run_dir = save_run_artifacts(
            small_sim.config,
            small_sim.history,
            small_sim.ledger.journal,
            output_dir=tmp_path,
        )
        assert run_dir.exists()
        assert (run_dir / "config.yaml").exists()
        assert (run_dir / "daily_stats.csv").exists()
        assert (run_dir / "journal.csv").exists()
        assert (run_dir / "metadata.json").exists()

        meta = json.loads((run_dir / "metadata.json").read_text())
        assert meta["seed"] == small_sim.config.seed
        assert meta["vibe_sim_version"] == "0.1.0"


class TestLedgerQueries:
    def test_actor_history(self, small_sim):
        rows = actor_history(small_sim.ledger.journal, small_sim.govt.id)
        assert len(rows) > 0
        for row in rows:
            assert row["account_id"].startswith("govt:")

    def test_market_history(self, small_sim):
        hist = market_history(small_sim.history, "food")
        assert len(hist) == 30
        assert all(h["price"] > 0 for h in hist)
