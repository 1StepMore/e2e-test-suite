"""Tests for the MCP verifier's corpus-content runtime guards (issue #234,
extended 2026-11-20 to srt/json/pptx→xlsx).

The CLI verifier runs ``_runtime_md_skip`` on the extracted Markdown so cells
whose intermediate MD lacks the structure their target format needs skip with
frozen corpus reasons. The MCP verifier delegates to the same CLI-side guard —
it only consulted the static ``_check_skip`` rule table before #234, so the
same fixture scored skip (CLI) vs pass (MCP) and the divergence hid inside
identical skip *totals*. These tests lock in the shared guard.
"""
from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path

from scripts import format_matrix_verifier as fmv  # noqa: E402  (issue #223 P2.1)
from scripts import mcp_matrix_verifier as mmv  # noqa: E402


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


def _md_path_cells(cell_dir: Path, md_content: str | None = None) -> tuple[_FakeSession, _FakeSession, _FakeSession]:
    """Fresh fake sessions wired for an OPP→OL→ORF MD-path cell."""
    opp = _FakeSession({"extract_document": {
        "success": True,
        "content": {"md_content": md_content or "# Sample\n\nProse without any table.\n"},
    }})
    ol = _FakeSession({"translate_md_text": {"translated": "翻译后无表格散文"}})
    orf = _FakeSession(touch_outputs=True)
    return opp, ol, orf


class TestRuntimeMdGuardUnit:
    """Unit: the MCP-side guard delegates to the CLI guard verbatim."""

    def test_guard_reuses_cli_reason_constant(self):
        assert mmv._runtime_md_skip("csv", "prose, no table") == fmv.MD_CSV_TABLE_SKIP_REASON

    def test_guard_skips_without_table(self):
        assert mmv._runtime_md_skip("csv", "# Sample\n\nProse.\n") == \
            "MD→CSV requires a table; intermediate MD has none"

    def test_guard_passes_pipe_table(self):
        md = "| a | b |\n|---|---|\n| 1 | 2 |\n"
        assert mmv._runtime_md_skip("csv", md) is None

    def test_guard_passes_html_table(self):
        assert mmv._runtime_md_skip("csv", "<table><tr><td>a</td></tr></table>") is None

    def test_guard_ignores_other_outputs(self):
        assert mmv._runtime_md_skip("md", "prose, no table") is None
        assert mmv._runtime_md_skip("docx", "prose, no table") is None

    def test_srt_guard_matches_cli(self):
        assert mmv._runtime_md_skip("srt", "# Sample\n\nProse.\n") == fmv.MD_SRT_SKIP_REASON
        cues = "1\n00:00:01,000 --> 00:00:02,000\nHello there.\n"
        assert mmv._runtime_md_skip("srt", cues) is None

    def test_json_guard_matches_cli(self):
        assert mmv._runtime_md_skip("json", "# Sample\n\nProse.\n") == fmv.MD_JSON_SKIP_REASON
        assert mmv._runtime_md_skip("json", '```json {"a": 1}```') is None
        assert mmv._runtime_md_skip("json", "json_field:greeting = Hello") is None

    def test_pptx_to_xlsx_guard_matches_cli(self):
        assert mmv._runtime_md_skip("xlsx", "# Slide\n\nProse.\n", "pptx") == \
            fmv.MD_PPTX_XLSX_SKIP_REASON
        assert mmv._runtime_md_skip("xlsx", fmv.FIXTURE_GFM_TABLE, "pptx") is None


class TestRuntimeMdGuardWiring:
    """The guard must fire inside the MD-path cell run, before OL/ORF are called."""

    def _run(self, tmp_path, outp, md_content=None, inp="docx"):
        opp, ol, orf = _md_path_cells(tmp_path, md_content)
        cell_dir = tmp_path / f"cell_{inp}_{outp}"
        cell_dir.mkdir()
        result = asyncio.run(mmv._run_one_cell_mcp(
            inp, outp, "md", cell_dir / f"sample.{inp}", cell_dir,
            opp, ol, orf))
        return result, opp, ol, orf

    def test_no_table_csv_is_skip_and_never_reaches_ol_orf(self, tmp_path):
        result, opp, ol, orf = self._run(tmp_path, "csv")
        assert result.status == "skip"
        assert result.skip_reason == fmv.MD_CSV_TABLE_SKIP_REASON
        assert opp.calls == ["extract_document"]
        assert ol.calls == [] and orf.calls == []

    def test_no_cues_srt_is_skip_and_never_reaches_ol_orf(self, tmp_path):
        result, opp, ol, orf = self._run(tmp_path, "srt")
        assert result.status == "skip"
        assert result.skip_reason == fmv.MD_SRT_SKIP_REASON
        assert opp.calls == ["extract_document"]
        assert ol.calls == [] and orf.calls == []

    def test_no_payload_json_is_skip_and_never_reaches_ol_orf(self, tmp_path):
        result, opp, ol, orf = self._run(tmp_path, "json")
        assert result.status == "skip"
        assert result.skip_reason == fmv.MD_JSON_SKIP_REASON
        assert opp.calls == ["extract_document"]
        assert ol.calls == [] and orf.calls == []

    def test_tableless_pptx_to_xlsx_is_skip(self, tmp_path):
        result, opp, ol, orf = self._run(tmp_path, "xlsx", inp="pptx")
        assert result.status == "skip"
        assert result.skip_reason == fmv.MD_PPTX_XLSX_SKIP_REASON
        assert ol.calls == [] and orf.calls == []

    def test_no_table_md_output_still_runs_full_path(self, tmp_path):
        result, _opp, ol, orf = self._run(tmp_path, "md")
        assert result.status == "pass"
        assert ol.calls == ["translate_md_text"]
        assert orf.calls == ["apply_md"]

    def test_table_bearing_csv_still_runs_full_path(self, tmp_path):
        result, _opp, ol, orf = self._run(
            tmp_path, "csv", "| a | b |\n|---|---|\n| 1 | 2 |\n")
        assert result.status == "pass"
        assert ol.calls == ["translate_md_text"]
        assert orf.calls == ["apply_md"]


class TestPandocRuntimeGate:
    """MCP channel: pandoc-backed outputs need a REAL pandoc binary (#426).

    The CLI channel fakes pandoc via OMNI_TEST_FAKE_PANDOC, but the MCP
    channel's ORF server scrubs that seam before spawning CLI subprocesses.
    On a machine without pandoc on PATH these cells used to run to
    CLI_TIMEOUT / EMPTY_OUTPUT and score fail — an environment-class false
    red. The gate must fire before any MCP call.
    """

    def _run(self, tmp_path, outp, inp="docx"):
        opp, ol, orf = _md_path_cells(tmp_path)
        cell_dir = tmp_path / f"cell_{inp}_{outp}"
        cell_dir.mkdir()
        return asyncio.run(mmv._run_one_cell_mcp(
            inp, outp, "md", cell_dir / f"sample.{inp}", cell_dir,
            opp, ol, orf)), opp, ol, orf

    def test_missing_pandoc_skips_every_pandoc_output(self, tmp_path, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        for outp in ("docx", "odt", "epub", "rtf", "icml"):
            result, _opp, _ol, _orf = self._run(tmp_path, outp)
            assert result.status == "skip"
            assert result.skip_reason == mmv.PANDOC_SKIP_REASON

    def test_skip_reason_is_frozen_exact_string(self, tmp_path, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        result, _opp, _ol, _orf = self._run(tmp_path, "docx")
        assert result.skip_reason == \
            "missing: pandoc (MCP scrubs OMNI_TEST_FAKE_PANDOC; real binary required)"

    def test_missing_pandoc_fires_before_any_mcp_call(self, tmp_path, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        result, opp, ol, orf = self._run(tmp_path, "docx")
        assert result.status == "skip"
        assert opp.calls == [] and ol.calls == [] and orf.calls == []

    def test_present_pandoc_lets_pandoc_outputs_run(self, tmp_path, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pandoc")
        for outp in ("docx", "odt", "epub", "rtf", "icml"):
            result, _opp, ol, orf = self._run(tmp_path, outp)
            assert result.status == "pass"
            assert ol.calls == ["translate_md_text"]
            assert orf.calls == ["apply_md"]

    def test_non_pandoc_outputs_not_gated(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        for outp in ("md", "pdf", "txt", "html", "srt", "csv", "json"):
            assert mmv._pandoc_runtime_skip(outp) is None

    def test_gate_probes_only_pandoc_binary_name(self, monkeypatch):
        probed: list[str] = []
        monkeypatch.setattr(shutil, "which",
                            lambda name: probed.append(name) or "/usr/bin/pandoc")
        assert mmv._pandoc_runtime_skip("docx") is None
        assert probed == ["pandoc"]


class TestCellEnvParity:
    """MCP and CLI cells must resolve modules through the same env (suite#372).

    Regression: the MCP channel's PYTHONPATH omitted the venv site-packages
    segment that the CLI channel's _cell_env carries, so shebang-launched
    conversion tools (md2pptx) hit ModuleNotFoundError only in MCP — an
    environment-class false red, not a real matrix failure. These tests lock
    the two channels to one construction with no EVA-01-specific literal.
    """

    def test_mcp_pythonpath_matches_cli_cell_env(self, tmp_path):
        cli_env = fmv._cell_env(fmv._SUITE_ROOT)
        mcp_env = mmv._mcp_cell_env(tmp_path)
        assert mcp_env["PYTHONPATH"] == cli_env["PYTHONPATH"]

    def test_shared_env_carries_venv_site_packages(self, tmp_path):
        # The PYTHONPATH's site-packages segment follows the same platform split
        # as scripts/format_matrix_verifier._venv_site_packages: .venv_win/Lib on
        # Windows, .venv_ol/lib on POSIX. Assert the platform-correct venv name +
        # site-packages (never one hardcoded platform name) so this stays a real
        # check, not a "non-empty" tautology (suite#372 contract). The path
        # separator differs per platform, so compare name/suffix as substrings
        # rather than splitting on ":".
        pp = mmv._mcp_cell_env(tmp_path)["PYTHONPATH"]
        expected_venv = ".venv_win" if os.name == "nt" else ".venv_ol"
        assert expected_venv in pp and "site-packages" in pp

    def test_all_three_module_src_dirs_present(self, tmp_path):
        pp = mmv._mcp_cell_env(tmp_path)["PYTHONPATH"]
        for mod in ("Omni_Pre_Processor", "Omni_Localizer", "Omni_Re_Formatter"):
            assert mod in pp

    def test_mcp_only_settings_are_layered_on_top(self, tmp_path):
        env = mmv._mcp_cell_env(tmp_path)
        assert env["OPP_MCP_ALLOWED_DIRS"] == str(tmp_path.resolve())
        assert env["OL_MCP_ALLOWED_DIRS"] == str(tmp_path.resolve())
        assert env["ORF_MCP_ALLOWED_DIRS"] == str(tmp_path.resolve())
        assert env["OMNI_RATE_LIMIT_RPM"] == "0"
        assert env["OMNI_RATE_LIMIT_BURST"] == "0"
        # shared base still present
        assert env["OMNI_TEST_FAKE_LLM"] == "1"
        assert env["OMNI_TEST_FAKE_PANDOC"] == "1"
