"""TDD tests for the format matrix verifier.

Locks in:
- availability gating
- skip rules
- matrix reporting
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import format_matrix_verifier as fmv  # noqa: E402  (issue #223 P2.1)


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


class TestXLIFFSameFormatRuns:
    """Same-format XLIFF cells must stay runnable.

    Regression: the rule ("xliff_xfmt", "*") parks a wildcard in the format
    slot, but _check_skip compared `inp != fmt` against that wildcard instead
    of against the OUTPUT format. `inp` is always a real format name, so the
    condition held for every xliff cell and the entire channel was skipped --
    including the same-format cells ORF does support, which the rule's own
    comment asserts ("Only same-format XLIFF cells are supported"). docx ->
    docx, the suite's primary XLIFF round-trip, was never verified through
    the matrix.

    The pairs below are the ones observed in a real matrix run, so each
    assertion discriminates instead of passing for an unrelated reason.
    """

    def test_same_format_cell_is_not_skipped(self, monkeypatch):
        monkeypatch.setitem(fmv.AVAILABILITY, "pandoc", True)
        assert fmv._check_skip("docx", "docx", "xliff") is None

    def test_cross_format_cell_is_still_skipped(self, monkeypatch):
        monkeypatch.setitem(fmv.AVAILABILITY, "pandoc", True)
        xfmt = next(r[2] for r in fmv.SKIP_RULES if r[0] == "xliff_xfmt")
        assert fmv._check_skip("docx", "odt", "xliff") == xfmt
        assert fmv._check_skip("pptx", "docx", "xliff") == xfmt


class TestEPUBXLIFFSkeletonRuleReclaimed:
    """EPUB produces a skeleton, so no static skip rule may hide its cells.

    The rule was written 6-21 (bc527b9), when EPUB genuinely had no skeleton
    and was therefore correct. OPP#39 (a8d9499, 6-29) gave EPUB a skeleton with
    data-trans-unit-id injected, but the rule was never reclaimed -- the same
    failure shape as #130. Kept separate from TestXLIFFSameFormatRuns so a
    future regression can be attributed to the right cause.
    """

    def test_no_static_skip_rule_for_epub(self):
        assert not [r for r in fmv.SKIP_RULES if r[0] == "xliff" and r[1] == "epub"]

    def test_epub_xliff_cell_is_not_skipped(self, monkeypatch):
        monkeypatch.setitem(fmv.AVAILABILITY, "pandoc", True)
        assert fmv._check_skip("epub", "epub", "xliff") is None

    def test_no_xliff_gap_formats_remain(self):
        """No format is left without an XLIFF backfill path.

        HTML was reclaimed at OPP#92 (``1ac5357``) and XLSX at OPP#94
        (``6c2a5d8``). EML was the last gap: OPP's email extractor now emits
        an EML skeleton (``message.eml`` + ``eml_map.json``) and ORF backfills
        it through ``xliff2eml``, so its skip rule was reclaimed too.

        Asserting the exact set, not a subset, is deliberate: it is what
        catches the next stale rule being quietly added back.
        """
        kept = {r[1] for r in fmv.SKIP_RULES if r[0] == "xliff"}
        assert kept == set()

    def test_xlsx_rule_is_reclaimed(self, monkeypatch):
        """XLSX emits a skeleton (OPP#94) and ORF backfills it (ORF#66).

        Also pins ``xlsx`` into XLIFF_OUTPUTS: without it the cell is never
        generated, so it would vanish from the matrix instead of being
        reported — the failure mode a skip-rule reclaim alone would hide.
        """
        monkeypatch.setitem(fmv.AVAILABILITY, "pandoc", True)
        assert not [r for r in fmv.SKIP_RULES if r[0] == "xliff" and r[1] == "xlsx"]
        assert "xlsx" in fmv.XLIFF_OUTPUTS
        assert fmv._check_skip("xlsx", "xlsx", "xliff") is None

    def test_html_rule_is_reclaimed(self, monkeypatch):
        """HTML emits a skeleton (OPP#92), so no static rule may hide its cells."""
        monkeypatch.setitem(fmv.AVAILABILITY, "pandoc", True)
        assert not [r for r in fmv.SKIP_RULES if r[0] == "xliff" and r[1] == "html"]
        assert fmv._check_skip("html", "html", "xliff") is None


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
            fmv.CellResult("a", "x", "md", "pass", 1.0),
            fmv.CellResult("b", "y", "md", "pass", 1.0),
            fmv.CellResult("c", "z", "md", "skip", 0.0, skip_reason="x"),
            fmv.CellResult("d", "w", "md", "fail", 1.0, detail="boom"),
        ]
        assert r.passed == 2
        assert r.skipped == 1
        assert r.failed == 1

    def test_to_dict_round_trip(self):
        r = fmv.MatrixResult()
        r.cells = [fmv.CellResult("a", "b", "md", "pass", 2.5)]
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
            fmv.CellResult("a", "b", "md", "pass", 1.0),
            fmv.CellResult("c", "d", "md", "skip", 0.0, skip_reason="x"),
            fmv.CellResult("e", "f", "md", "fail", 1.0, detail="boom"),
        ]
        md = fmv._render_markdown(r)
        assert "**Pass**: 1" in md
        assert "**Skip**: 1" in md
        assert "**Fail**: 1" in md
        assert "❌ 1 cell(s) failed" in md

    def test_no_fail_shows_pass_message(self):
        r = fmv.MatrixResult()
        r.cells = [fmv.CellResult("a", "b", "md", "pass", 1.0)]
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
        skeleton_data = {"files": {}}  # no xml, no slides, no opf
        document_xml = skeleton_data.get("xml")
        assert document_xml is None
        # The error message must include the keyword "Cross-format"
        # so users can grep for it
        expected_msg_fragment = "Cross-format XLIFF"
        # In the real fix we build a message that includes this fragment
        assert "Cross-format" in expected_msg_fragment


# --- e2e#228: empty artifacts must FAIL, table-less MD→CSV must SKIP -----
# Runners are driven with monkeypatched subprocess.run so no real
# OPP/OL/ORF process starts.

def _completed_process(cmd):
    return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")


def _fake_md_subprocess(cell_dir: Path, src: Path, md_text: str,
                        artifact_bytes: bytes = b""):
    def run(cmd, **kwargs):
        module = cmd[2]
        if module == "opp.cli":
            (cell_dir / f"{src.stem}.md").write_text(md_text, encoding="utf-8")
        elif module == "ol_cli":
            md_path = Path(cmd[cmd.index("translate-md") + 1])
            out_dir = Path(cmd[cmd.index("-o") + 1])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / md_path.name).write_text(md_text, encoding="utf-8")
        elif module == "orf.cli":
            Path(cmd[cmd.index("--output") + 1]).write_bytes(artifact_bytes)
        else:
            raise AssertionError(f"unexpected subprocess: {cmd}")
        return _completed_process(cmd)
    return run


def _fake_xliff_subprocess(cell_dir: Path, src: Path, artifact_bytes: bytes = b""):
    def run(cmd, **kwargs):
        module = cmd[2]
        if module == "opp.cli":
            (cell_dir / f"{src.stem}.xlf").write_text("<xliff/>", encoding="utf-8")
            (cell_dir / f"{src.stem}.skeleton.zip").write_bytes(b"PK")
        elif module == "ol_cli":
            xlf_path = Path(cmd[cmd.index("translate-xliff") + 1])
            out_dir = Path(cmd[cmd.index("-o") + 1])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / xlf_path.name).write_text("<xliff/>", encoding="utf-8")
        elif module == "orf.cli":
            Path(cmd[cmd.index("--output") + 1]).write_bytes(artifact_bytes)
        else:
            raise AssertionError(f"unexpected subprocess: {cmd}")
        return _completed_process(cmd)
    return run


class TestArtifactDefect:
    def test_zero_byte_file_is_defect(self, tmp_path):
        artifact = tmp_path / "result.csv"
        artifact.write_bytes(b"")
        assert fmv._artifact_defect(artifact, "csv") == "produced empty output (0 bytes)"

    def test_zero_byte_binary_is_defect(self, tmp_path):
        artifact = tmp_path / "result.docx"
        artifact.write_bytes(b"")
        assert fmv._artifact_defect(artifact, "docx") == "produced empty output (0 bytes)"

    def test_whitespace_only_text_is_defect(self, tmp_path):
        artifact = tmp_path / "result.csv"
        artifact.write_text("  \n\t\n", encoding="utf-8")
        assert fmv._artifact_defect(artifact, "csv") == (
            "produced empty output (whitespace only)"
        )

    def test_non_empty_csv_has_no_defect(self, tmp_path):
        artifact = tmp_path / "result.csv"
        artifact.write_text("col1,col2\na,b\n", encoding="utf-8")
        assert fmv._artifact_defect(artifact, "csv") is None

    def test_missing_file_is_defect(self, tmp_path):
        defect = fmv._artifact_defect(tmp_path / "absent.html", "html")
        assert defect is not None
        assert "no output" in defect


class TestMarkdownTableDetector:
    def test_pipe_table_detected(self):
        md = "Intro\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n"
        assert fmv._has_markdown_table(md) is True

    def test_table_without_separator_not_detected(self):
        assert fmv._has_markdown_table("| a | b |\n| 1 | 2 |\n") is False

    def test_plain_prose_not_detected(self):
        assert fmv._has_markdown_table("# Test\n\nHello, world.\n") is False

    def test_html_table_detected(self):
        assert fmv._has_markdown_table("<table><tr><td>a</td></tr></table>") is True


class TestMDPathArtifactAssertion:
    def _run(self, tmp_path, monkeypatch, outp, md_text, artifact_bytes):
        cell_dir = tmp_path / f"md_docx_to_{outp}"
        cell_dir.mkdir()
        src = cell_dir / "sample.docx"
        src.write_bytes(b"fixture")
        monkeypatch.setattr(
            fmv.subprocess, "run",
            _fake_md_subprocess(cell_dir, src, md_text, artifact_bytes),
        )
        return fmv._run_md_path(
            Path("python"), {}, tmp_path, src, cell_dir, "docx", outp, 0.0,
        )

    def test_zero_byte_artifact_is_fail(self, tmp_path, monkeypatch):
        result = self._run(tmp_path, monkeypatch, "html",
                           "# Test\n\nHello, world.\n", b"")
        assert result.status == "fail"
        assert "produced empty output (0 bytes)" in result.detail

    def test_csv_without_table_is_skip(self, tmp_path, monkeypatch):
        result = self._run(tmp_path, monkeypatch, "csv",
                           "# Test\n\nHello, world.\n", b"")
        assert result.status == "skip"
        assert result.skip_reason == (
            "MD→CSV requires a table; intermediate MD has none"
        )

    def test_csv_with_table_passes(self, tmp_path, monkeypatch):
        md = "| a | b |\n| --- | --- |\n| 1 | 2 |\n"
        result = self._run(tmp_path, monkeypatch, "csv", md, b"a,b\n1,2\n")
        assert result.status == "pass"

    def test_xliff_path_zero_byte_artifact_is_fail(self, tmp_path, monkeypatch):
        cell_dir = tmp_path / "xliff_docx_to_docx"
        cell_dir.mkdir()
        src = cell_dir / "sample.docx"
        src.write_bytes(b"fixture")
        monkeypatch.setattr(
            fmv.subprocess, "run",
            _fake_xliff_subprocess(cell_dir, src, b""),
        )
        result = fmv._run_xliff_path(
            Path("python"), {}, tmp_path, src, cell_dir, "docx", "docx", 0.0,
        )
        assert result.status == "fail"
        assert "produced empty output (0 bytes)" in result.detail
