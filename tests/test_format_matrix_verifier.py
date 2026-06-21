"""TDD tests for the format matrix verifier.

Locks in:
- availability gating
- skip rules
- matrix reporting
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import format_matrix_verifier as fmv  # noqa: E402


class TestAvailability:
    def test_availability_is_dict_of_bools(self):
        assert isinstance(fmv.AVAILABILITY, dict)
        for key, val in fmv.AVAILABILITY.items():
            assert isinstance(val, bool), f"{key} = {val!r} not bool"

    def test_known_keys_present(self):
        for key in ("pandoc", "md2pptx", "weasyprint", "aspose_email", "extract_msg", "nbformat"):
            assert key in fmv.AVAILABILITY


class TestSkipRules:
    def test_skip_when_md2pptx_missing(self, monkeypatch):
        monkeypatch.setitem(fmv.AVAILABILITY, "md2pptx", False)
        reason = fmv._check_skip("docx", "pptx")
        assert reason is not None
        assert "md2pptx" in reason

    def test_no_skip_when_md2pptx_present(self, monkeypatch):
        monkeypatch.setitem(fmv.AVAILABILITY, "md2pptx", True)
        reason = fmv._check_skip("docx", "pptx")
        assert reason is None

    def test_skip_when_pandoc_missing_for_docx_output(self, monkeypatch):
        monkeypatch.setitem(fmv.AVAILABILITY, "pandoc", False)
        reason = fmv._check_skip("docx", "docx")
        assert reason is not None
        assert "pandoc" in reason

    def test_skip_msg_input_when_extract_msg_missing(self, monkeypatch):
        monkeypatch.setitem(fmv.AVAILABILITY, "extract_msg", False)
        reason = fmv._check_skip("msg", "eml")
        assert reason is not None
        assert "extract-msg" in reason

    def test_skip_msg_output_when_aspose_missing(self, monkeypatch):
        monkeypatch.setitem(fmv.AVAILABILITY, "aspose_email", False)
        reason = fmv._check_skip("eml", "msg")
        assert reason is not None
        assert "aspose" in reason.lower()


class TestMatrixDefinition:
    def test_matrix_has_docx_inputs(self):
        docx_cells = [c for c in fmv.MD_PATH_MATRIX if c[0] == "docx"]
        assert len(docx_cells) >= 5

    def test_matrix_is_unique(self):
        # No duplicate (input, output) pairs
        pairs = set(fmv.MD_PATH_MATRIX)
        assert len(pairs) == len(fmv.MD_PATH_MATRIX)


class TestMatrixResult:
    def test_passed_skipped_failed_counts(self):
        r = fmv.MatrixResult()
        r.cells = [
            fmv.CellResult("a", "x", "pass", 1.0),
            fmv.CellResult("b", "y", "pass", 1.0),
            fmv.CellResult("c", "z", "skip", 0.0, skip_reason="x"),
            fmv.CellResult("d", "w", "fail", 1.0, detail="boom"),
        ]
        assert r.passed == 2
        assert r.skipped == 1
        assert r.failed == 1

    def test_to_dict_round_trip(self):
        r = fmv.MatrixResult()
        r.cells = [fmv.CellResult("a", "b", "pass", 2.5)]
        d = r.to_dict()
        assert d["total"] == 1
        assert d["passed"] == 1
        assert d["cells"][0]["inp"] == "a"
        # Should be JSON-serializable
        json.dumps(d)


class TestRenderMarkdown:
    def test_includes_pass_skip_fail_counts(self):
        r = fmv.MatrixResult()
        r.cells = [
            fmv.CellResult("a", "b", "pass", 1.0),
            fmv.CellResult("c", "d", "skip", 0.0, skip_reason="x"),
            fmv.CellResult("e", "f", "fail", 1.0, detail="boom"),
        ]
        md = fmv._render_markdown(r)
        assert "**Pass**: 1" in md
        assert "**Skip**: 1" in md
        assert "**Fail**: 1" in md
        assert "❌ 1 cell(s) failed" in md

    def test_no_fail_shows_pass_message(self):
        r = fmv.MatrixResult()
        r.cells = [fmv.CellResult("a", "b", "pass", 1.0)]
        md = fmv._render_markdown(r)
        assert "✅" in md


class TestWriteFixture:
    @pytest.mark.parametrize("fmt,expected_ext", [
        ("html", ".html"),
        ("csv", ".csv"),
        ("json", ".json"),
        ("xml", ".xml"),
        ("eml", ".eml"),
    ])
    def test_text_fixtures(self, tmp_path, fmt, expected_ext):
        dest = tmp_path / f"sample.{fmt}"
        fmv._write_minimal_fixture(fmt, dest)
        assert dest.exists()
        assert dest.stat().st_size > 0
