"""Tests for Phase 0.5 — Stage-by-stage quality report.

Verifies that ``scripts/turnkey/quality_report.py`` emits a structured
``report.json`` with the 6 Q-gate keys defined in the design contract:
    q1_functional, q2_lqa, q3_glossary, q4_image, q5_punct, q6_roundtrip
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make scripts/ importable
SUITE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SUITE_ROOT / "scripts"))

from turnkey.quality_report import (  # noqa: E402
    _default_metrics,
    collect_stage_metrics,
    write_report,
)


REQUIRED_QGATE_KEYS = {
    "q1_functional",
    "q2_lqa",
    "q3_glossary",
    "q4_image",
    "q5_punct",
    "q6_roundtrip",
}


class TestStageReportContract:
    """``report.json`` has all 6 Q-gate keys with the documented shape."""

    def test_default_metrics_has_all_six_qgates(self) -> None:
        """Default metrics contain all 6 Q-gate keys."""
        metrics = _default_metrics()
        assert set(metrics.keys()) == REQUIRED_QGATE_KEYS
        for qkey, entry in metrics.items():
            assert "passed" in entry
            assert "score" in entry
            assert isinstance(entry["passed"], bool)
            assert isinstance(entry["score"], (int, float))

    def test_collect_stage_metrics_on_empty_dir(self, tmp_path: Path) -> None:
        """Empty run_dir returns default metrics (non-fatal)."""
        metrics = collect_stage_metrics(tmp_path)
        assert set(metrics.keys()) == REQUIRED_QGATE_KEYS
        # All default to False / 0.0
        for entry in metrics.values():
            assert entry["passed"] is False
            assert entry["score"] == 0.0

    def test_collect_stage_metrics_reads_red_log(self, tmp_path: Path) -> None:
        """A phase directory with a passing red.log contributes a passing gate."""
        # Simulate phase 0.1 with a passing red.log
        phase_dir = tmp_path / "phases" / "phase_0.1"
        phase_dir.mkdir(parents=True)
        (phase_dir / "red.log").write_text("1 passed in 0.5s\n")

        metrics = collect_stage_metrics(tmp_path)

        # Phase 0.1 → q3_glossary per _QGATE_MAP
        assert metrics["q3_glossary"]["passed"] is True
        assert metrics["q3_glossary"]["score"] == 1.0

    def test_write_report_produces_valid_json(self, tmp_path: Path) -> None:
        """``write_report`` writes a loadable JSON file with all 6 Q-gates."""
        metrics = {
            "q1_functional": {"passed": True, "score": 1.0},
            "q2_lqa": {"passed": True, "score": 4.5},
            "q3_glossary": {"passed": True, "score": 1.0},
            "q4_image": {"passed": True, "score": 1.0},
            "q5_punct": {"passed": True, "score": 1.0},
            "q6_roundtrip": {"passed": True, "score": 1.0},
        }

        write_report(tmp_path, metrics)

        report_path = tmp_path / "report.json"
        assert report_path.exists()

        loaded = json.loads(report_path.read_text())
        assert set(loaded.keys()) == REQUIRED_QGATE_KEYS
        assert loaded["q2_lqa"]["score"] == 4.5

    def test_write_report_skips_empty_metrics(self, tmp_path: Path) -> None:
        """``write_report`` does not write when metrics is empty."""
        write_report(tmp_path, {})
        assert not (tmp_path / "report.json").exists()
