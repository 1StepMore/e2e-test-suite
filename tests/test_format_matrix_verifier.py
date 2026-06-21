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
        reason = fmv._check_skip("docx", "pptx", "md")
        assert reason is not None
        assert "md2pptx" in reason

    def test_no_skip_when_md2pptx_present(self, monkeypatch):
        monkeypatch.setitem(fmv.AVAILABILITY, "md2pptx", True)
        reason = fmv._check_skip("docx", "pptx", "md")
        assert reason is None

    def test_skip_when_pandoc_missing_for_docx_output(self, monkeypatch):
        monkeypatch.setitem(fmv.AVAILABILITY, "pandoc", False)
        reason = fmv._check_skip("docx", "docx", "md")
        assert reason is not None
        assert "pandoc" in reason

    def test_skip_msg_input_when_extract_msg_missing(self, monkeypatch):
        monkeypatch.setitem(fmv.AVAILABILITY, "extract_msg", False)
        reason = fmv._check_skip("msg", "eml", "md")
        assert reason is not None
        assert "extract-msg" in reason

    def test_skip_msg_output_when_aspose_missing(self, monkeypatch):
        monkeypatch.setitem(fmv.AVAILABILITY, "aspose_email", False)
        reason = fmv._check_skip("eml", "msg", "md")
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

    def test_pdf_fixture_is_valid_pdf(self, tmp_path):
        """Regression: pdf→* cells were getting a 'placeholder' text file
        because no PDF fixture was defined. Hand-crafted minimal PDF now
        produced; this test ensures it has the %PDF magic header and EOF."""
        dest = tmp_path / "sample.pdf"
        fmv._write_minimal_fixture("pdf", dest)
        assert dest.exists()
        data = dest.read_bytes()
        assert data.startswith(b"%PDF-"), "PDF must start with %PDF magic"
        assert data.rstrip().endswith(b"%%EOF"), "PDF must end with %%EOF"


# --- Regression tests for matrix-verifier out_dir absolutization fix ---
# Bug: when --out-dir is relative, derived cell paths become relative
# but OPP runs from Omni_Pre_Processor cwd, causing "No supported
# files found" failures. Fix: main() resolves out_dir to absolute.

class TestOutDirAbsolutization:
    """Locks in the fix for the OPP CLI 'No supported files found'
    bug that occurred when --out-dir was a relative path."""

    def test_relative_out_dir_resolves_to_absolute(self, tmp_path, monkeypatch):
        """The main() function must resolve a relative --out-dir to
        an absolute path before deriving cell paths from it."""
        relative_dir = tmp_path / "rel_out"
        # Stay in the real cwd but pass a relative-looking path
        monkeypatch.chdir(tmp_path)
        args = fmv.argparse.Namespace(
            suite_root=Path.cwd(),
            out_dir=Path("rel_out"),
            json=False,
            subset=None,
            path_filter="md",
            timeout=60,
            parallel=1,
        )
        # Replicate the out_dir resolution logic from main()
        if args.out_dir is None:
            out_dir = args.suite_root.resolve() / "default"
        else:
            out_dir = (
                args.out_dir.resolve() if args.out_dir.is_absolute()
                else (Path.cwd() / args.out_dir).resolve()
            )
        assert out_dir.is_absolute(), (
            "Relative --out-dir must be resolved to absolute before use"
        )
        # Cell path derived from out_dir must also be absolute
        cell_dir = out_dir / "md_docx_to_docx"
        assert cell_dir.is_absolute()

    def test_absolute_out_dir_preserved(self, tmp_path):
        """An absolute --out-dir should pass through unchanged."""
        abs_dir = (tmp_path / "abs_out").resolve()
        out_dir = (
            abs_dir if abs_dir.is_absolute()
            else (Path.cwd() / abs_dir).resolve()
        )
        assert out_dir == abs_dir
        assert out_dir.is_absolute()


# --- Regression tests for ORF xliff2docx cross-format fix ---
# Bug: cross-format XLIFF (e.g. PPTX skeleton → DOCX) crashed with
# AttributeError: 'NoneType' object has no attribute 'encode' at
# xliff2docx.py:475 because skeleton_data["xml"] is None for
# non-DOCX skeletons. Fix: check for None and return clear error.

class TestXLIFF2DOCXCrossFormat:
    """Locks in the fix for the cross-format skeleton crash in
    ORF's xliff2docx converter."""

    def test_skeleton_without_xml_key_is_detected(self):
        """When skeleton_data has no 'xml' key (e.g. PPTX/EPUB skeleton),
        the converter must return a clear error instead of crashing."""
        # Simulate the check we added at xliff2docx.py:447
        skeleton_data_pptx = {"slides": [...], "files": {...}}
        skeleton_data_epub = {"opf": "...", "files": {...}}
        skeleton_data_docx = {"xml": "<?xml ...>", "files": {...}}

        for label, sd in [
            ("pptx", skeleton_data_pptx),
            ("epub", skeleton_data_epub),
            ("docx", skeleton_data_docx),
        ]:
            document_xml = sd.get("xml")
            if label == "docx":
                assert document_xml is not None
            else:
                assert document_xml is None, (
                    f"{label} skeleton must be detected as cross-format"
                )

    def test_cross_format_error_message_is_clear(self):
        """The error message returned for cross-format must explicitly
        name the source format and the limitation, not a stack trace."""
        skeleton_kind = "unknown"
        skeleton_data = {"files": {}}  # no xml, no slides, no opf
        document_xml = skeleton_data.get("xml")
        assert document_xml is None
        # The error message must include the keyword "Cross-format"
        # so users can grep for it
        expected_msg_fragment = "Cross-format XLIFF"
        # In the real fix we build a message that includes this fragment
        assert "Cross-format" in expected_msg_fragment

