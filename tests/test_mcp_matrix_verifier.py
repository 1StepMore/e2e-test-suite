"""Tests for the MCP verifier's MD→CSV runtime guard (issue #234).

The CLI verifier skips MD→CSV cells whose intermediate Markdown carries no
table (``format_matrix_verifier._run_md_path``). The MCP verifier never ran
that guard — it only consulted the static ``_check_skip`` rule table — so the
same fixture scored skip (CLI) vs pass (MCP) and the divergence hid inside
identical skip *totals*. These tests lock in the shared guard.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import format_matrix_verifier as fmv  # noqa: E402
import mcp_matrix_verifier as mmv  # noqa: E402


class _FakeSession:
    """Records tool calls; returns canned responses keyed by tool name.

    With ``touch_outputs`` an ``apply_md`` call writes a stub artifact at
    ``output_path`` so the full-path cell reaches its PASS return.
    """

    def __init__(self, responses: dict | None = None, touch_outputs: bool = False):
        self.responses = responses or {}
        self.touch_outputs = touch_outputs
        self.calls: list[str] = []

    async def call_tool(self, name, arguments):
        self.calls.append(name)
        if self.touch_outputs and name == "apply_md":
            out = Path(arguments["output_path"])
            out.write_text("artifact", encoding="utf-8")
        return self.responses.get(name, {})


def _md_path_cells(cell_dir: Path) -> tuple[_FakeSession, _FakeSession, _FakeSession]:
    """Fresh fake sessions wired for an OPP→OL→ORF MD-path cell."""
    opp = _FakeSession({"extract_document": {
        "success": True,
        "content": {"md_content": "# Sample\n\nProse without any table.\n"},
    }})
    ol = _FakeSession({"translate_md_text": {"translated": "翻译后无表格散文"}})
    orf = _FakeSession(touch_outputs=True)
    return opp, ol, orf


class TestMdCsvGuardUnit:
    def test_guard_reuses_cli_reason_constant(self):
        assert mmv._md_csv_skip("csv", "prose, no table") == fmv.MD_CSV_TABLE_SKIP_REASON

    def test_guard_skips_without_table(self):
        assert mmv._md_csv_skip("csv", "# Sample\n\nProse.\n") == \
            "MD→CSV requires a table; intermediate MD has none"

    def test_guard_passes_pipe_table(self):
        md = "| a | b |\n|---|---|\n| 1 | 2 |\n"
        assert mmv._md_csv_skip("csv", md) is None

    def test_guard_passes_html_table(self):
        assert mmv._md_csv_skip("csv", "<table><tr><td>a</td></tr></table>") is None

    def test_guard_ignores_other_outputs(self):
        assert mmv._md_csv_skip("md", "prose, no table") is None
        assert mmv._md_csv_skip("docx", "prose, no table") is None


class TestMdCsvGuardWiring:
    """The guard must fire inside the MD-path cell run, before OL/ORF are called."""

    def _run(self, tmp_path, outp):
        opp, ol, orf = _md_path_cells(tmp_path)
        cell_dir = tmp_path / "cell"
        cell_dir.mkdir()
        result = asyncio.run(mmv._run_one_cell_mcp(
            "docx", outp, "md", cell_dir / "sample.docx", cell_dir,
            opp, ol, orf))
        return result, opp, ol, orf

    def test_no_table_csv_is_skip_and_never_reaches_ol_orf(self, tmp_path):
        result, opp, ol, orf = self._run(tmp_path, "csv")
        assert result.status == "skip"
        assert result.skip_reason == fmv.MD_CSV_TABLE_SKIP_REASON
        assert opp.calls == ["extract_document"]
        assert ol.calls == [] and orf.calls == []

    def test_no_table_md_output_still_runs_full_path(self, tmp_path):
        result, _opp, ol, orf = self._run(tmp_path, "md")
        assert result.status == "pass"
        assert ol.calls == ["translate_md_text"]
        assert orf.calls == ["apply_md"]

    def test_table_bearing_csv_still_runs_full_path(self, tmp_path):
        opp, ol, orf = _md_path_cells(tmp_path)
        opp.responses["extract_document"]["content"]["md_content"] = (
            "| a | b |\n|---|---|\n| 1 | 2 |\n")
        cell_dir = tmp_path / "cell2"
        cell_dir.mkdir()
        result = asyncio.run(mmv._run_one_cell_mcp(
            "docx", "csv", "md", cell_dir / "sample.docx", cell_dir,
            opp, ol, orf))
        assert result.status == "pass"
        assert ol.calls == ["translate_md_text"]
        assert orf.calls == ["apply_md"]
