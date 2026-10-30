"""Tests for the nightly gap report's per-cell divergence guard (issue #234).

The regression guard used to compare only per-channel skip *totals*, so a
CLI-skip / MCP-pass split on the same cell (10 MD→CSV cells, 2026-10-30
nightly) hid inside matching totals. The guard now also compares the two
channels cell by cell: any ``(inp, outp, path)`` whose status differs — or
that exists on one side only — counts into ``regression_gap``.
"""
import json

import pytest

import scripts.nightly_gap as ng


def _cell(inp, outp, path, status, reason=""):
    return {"inp": inp, "outp": outp, "path": path, "status": status,
            "skip_reason": reason, "detail": ""}


class TestFindDivergentCells:
    def test_identical_channels_yield_no_divergence(self):
        cells = [_cell("docx", "csv", "md", "skip", "MD→CSV requires a table"),
                 _cell("docx", "md", "md", "pass")]
        assert ng.find_divergent_cells(cells, [dict(c) for c in cells]) == []

    def test_status_mismatch_is_reported_with_both_sides(self):
        cli = [_cell("docx", "csv", "md", "skip", "MD→CSV requires a table; intermediate MD has none")]
        mcp = [_cell("docx", "csv", "md", "pass")]
        divergent = ng.find_divergent_cells(cli, mcp)
        assert len(divergent) == 1
        assert divergent[0]["cell"] == {"inp": "docx", "outp": "csv", "path": "md"}
        assert divergent[0]["CLI"] == {"status": "skip",
                                       "reason": "MD→CSV requires a table; intermediate MD has none"}
        assert divergent[0]["MCP"] == {"status": "pass", "reason": ""}

    def test_missing_cell_on_one_side_counts(self):
        cli = [_cell("docx", "csv", "md", "skip", "x"), _cell("eml", "csv", "md", "skip", "y")]
        mcp = [_cell("docx", "csv", "md", "skip", "x")]
        divergent = ng.find_divergent_cells(cli, mcp)
        assert len(divergent) == 1
        assert divergent[0]["cell"]["inp"] == "eml"
        assert divergent[0]["CLI"]["status"] == "skip"
        assert divergent[0]["MCP"]["status"] == "missing"


class TestMdCsvExemption:
    def test_md_csv_reason_is_exempt(self):
        assert ng.is_exempt("MD→CSV requires a table; intermediate MD has none")

    def test_capability_reasons_stay_non_exempt(self):
        assert not ng.is_exempt("pandoc not installed")
        assert not ng.is_exempt("XLIFF cross-format not supported by ORF converters")


def _write_matrix(out_root, channel, cells, total=None):
    d = out_root / channel
    d.mkdir(parents=True)
    (d / "matrix.json").write_text(json.dumps({
        "total": total if total is not None else len(cells),
        "passed": sum(1 for c in cells if c["status"] == "pass"),
        "skipped": sum(1 for c in cells if c["status"] == "skip"),
        "failed": sum(1 for c in cells if c["status"] == "fail"),
        "cells": cells,
    }), encoding="utf-8")


def _skip_run(out_root, expect_total, json_out):
    return ng.main(["--skip-run", "--out-dir", str(out_root),
                    "--expect-total", str(expect_total),
                    "--json-out", str(json_out)])


@pytest.fixture()
def no_preflight(monkeypatch):
    """--skip-run needs no modules; keep the hermetic path free of preflight."""
    monkeypatch.setattr(ng, "preflight", lambda python: [])


class TestMainDivergenceGuard:
    def test_skip_pass_split_is_counted_in_regression_gap(self, tmp_path, no_preflight):
        exempt_reason = "MD→CSV requires a table; intermediate MD has none"
        cells = [
            _cell("docx", "csv", "md", "skip", exempt_reason),   # divergent below
            _cell("docx", "md", "md", "pass"),
            _cell("docx", "srt", "md", "skip", "MD→SRT requires timestamped cues; no timestamps in fixture"),
        ]
        _write_matrix(tmp_path, "cli", cells)
        mcp_cells = [dict(c) for c in cells]
        mcp_cells[0]["status"] = "pass"          # the exact #234 split: CLI skip / MCP pass
        mcp_cells[0]["skip_reason"] = ""
        _write_matrix(tmp_path, "mcp", mcp_cells)

        json_out = tmp_path / "gap.json"
        rc = _skip_run(tmp_path, expect_total=6, json_out=json_out)

        result = json.loads(json_out.read_text(encoding="utf-8"))
        # DoD verdict stays clean (the split cells are exempt skips on the CLI side,
        # passes on the MCP side) — but the guard must flag the divergence.
        assert result["gap_units"] == 0
        assert rc == 0
        assert result["channel_divergence"] == 1
        assert result["regression_gap"] == 1
        assert result["regression_mode"] == "per_cell_divergence_plus_max_skip"
        assert result["divergent_cells"][0]["cell"]["outp"] == "csv"
        assert "_cells" not in result["channels"]["CLI"]
        assert "_cells" not in result["channels"]["MCP"]

    def test_identical_channels_keep_regression_gap_zero(self, tmp_path, no_preflight):
        cells = [
            _cell("docx", "csv", "md", "skip", "MD→CSV requires a table; intermediate MD has none"),
            _cell("docx", "md", "md", "pass"),
        ]
        _write_matrix(tmp_path, "cli", cells)
        _write_matrix(tmp_path, "mcp", [dict(c) for c in cells])

        json_out = tmp_path / "gap.json"
        rc = _skip_run(tmp_path, expect_total=4, json_out=json_out)

        result = json.loads(json_out.read_text(encoding="utf-8"))
        assert rc == 0
        assert result["channel_divergence"] == 0
        assert result["regression_gap"] == 0

    def test_missing_cell_on_one_side_is_counted(self, tmp_path, no_preflight):
        cells = [
            _cell("docx", "csv", "md", "pass"),
            _cell("eml", "csv", "md", "pass"),
        ]
        _write_matrix(tmp_path, "cli", cells)
        _write_matrix(tmp_path, "mcp", cells[:1])   # MCP "lost" the eml→csv cell

        json_out = tmp_path / "gap.json"
        _skip_run(tmp_path, expect_total=3, json_out=json_out)

        result = json.loads(json_out.read_text(encoding="utf-8"))
        assert result["channel_divergence"] == 1
        assert result["divergent_cells"][0]["MCP"]["status"] == "missing"
        assert result["regression_gap"] == 1
