"""Tests for Phase 0.4 — Hard LQA quality gate.

Verifies that ``scripts/turnkey.py::lqa_gate`` returns the documented
contract: ``{passed: bool, avg_score: float, dimensional_scores: dict}``.

These are non-failing structural tests. The hermetic LLM seam
(``OMNI_TEST_FAKE_LLM=1``) and the missing JudgeService are both
handled gracefully by ``lqa_gate`` (returns ``skipped: True``), so
this test passes in CI without real LLM access.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# Load scripts/turnkey.py (the FILE, not the package) to access lqa_gate.
# There is also a scripts/turnkey/ PACKAGE with the same stem; ``import turnkey``
# would resolve to the package (which is empty), so we load the file directly.
SUITE_ROOT = Path(__file__).resolve().parents[2]
TURNKEY_FILE = SUITE_ROOT / "scripts" / "turnkey.py"
_spec = importlib.util.spec_from_file_location("turnkey_main", TURNKEY_FILE)
turnkey = importlib.util.module_from_spec(_spec)
sys.modules["turnkey_main"] = turnkey
_spec.loader.exec_module(turnkey)


SOURCE_DOCX = SUITE_ROOT / "爱上海尔_第二章_全球创牌 - E2E测试专用.docx"
OUTPUT_DOCX = Path("/tmp/turnkey_image_check/orf/output.docx")


class TestLQAGateContract:
    """``lqa_gate()`` returns the documented dict structure."""

    def test_lqa_gate_returns_dict_with_required_keys(self) -> None:
        """Returns dict with at least ``passed`` (bool) and ``avg_score`` (float)."""
        if not SOURCE_DOCX.exists() or not OUTPUT_DOCX.exists():
            pytest.skip("Source or output DOCX fixture missing")

        result = turnkey.lqa_gate(OUTPUT_DOCX, SOURCE_DOCX)

        assert isinstance(result, dict)
        assert "passed" in result
        assert "avg_score" in result
        assert isinstance(result["passed"], bool)
        assert isinstance(result["avg_score"], (int, float))

    def test_lqa_gate_handles_missing_judge_service(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns ``skipped: True`` when JudgeService is unavailable."""
        # Simulate missing JudgeService
        monkeypatch.setitem(sys.modules, "ol_lqa.judge", None)

        result = turnkey.lqa_gate(OUTPUT_DOCX, SOURCE_DOCX)

        assert result.get("skipped") is True
        assert result["passed"] is True  # skip → pass

    def test_lqa_gate_handles_missing_python_docx(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns ``skipped: True`` when python-docx is unavailable."""
        # Simulate missing python-docx by patching the import
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "docx":
                raise ImportError("simulated missing docx")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        result = turnkey.lqa_gate(OUTPUT_DOCX, SOURCE_DOCX)

        assert result.get("skipped") is True
        assert result["passed"] is True
