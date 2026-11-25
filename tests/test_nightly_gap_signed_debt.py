"""suite#374 — 结构性拒绝（58 格跨格式 XLIFF）按 owner 2026-11-19 签字移出 gap。

两条钉子：
a) 只有结构性拒绝 skip ⇒ gap_units == 0；
b) 混入一条非结构性 skip ⇒ gap_units 相应 +1（防止把真债一起误免）。
"""
import json

import pytest

import scripts.nightly_gap as ng

XFMT = "XLIFF cross-format not supported by ORF converters"


def _cell(inp, outp, path, status, reason=""):
    return {"inp": inp, "outp": outp, "path": path, "status": status,
            "skip_reason": reason, "detail": ""}


def _structural_cells():
    return [
        _cell("docx", "pptx", "xliff", "skip", XFMT),
        _cell("docx", "epub", "xliff", "skip", XFMT),
        _cell("docx", "docx", "xliff", "pass"),
    ]


def _write_matrix(out_root, channel, cells):
    d = out_root / channel
    d.mkdir(parents=True)
    (d / "matrix.json").write_text(json.dumps({
        "total": len(cells),
        "passed": sum(1 for c in cells if c["status"] == "pass"),
        "skipped": sum(1 for c in cells if c["status"] == "skip"),
        "failed": sum(1 for c in cells if c["status"] == "fail"),
        "cells": cells,
    }), encoding="utf-8")


def _run_skip(out_root, expect_total, json_out):
    return ng.main(["--skip-run", "--out-dir", str(out_root),
                    "--expect-total", str(expect_total),
                    "--json-out", str(json_out)])


@pytest.fixture()
def no_preflight(monkeypatch):
    monkeypatch.setattr(ng, "preflight", lambda python: [])


class TestSignedDebt:
    def test_only_structural_skips_yield_zero_gap(self, tmp_path, no_preflight):
        cells = _structural_cells()
        _write_matrix(tmp_path, "cli", cells)
        _write_matrix(tmp_path, "mcp", [dict(c) for c in cells])

        json_out = tmp_path / "gap.json"
        rc = _run_skip(tmp_path, expect_total=6, json_out=json_out)

        result = json.loads(json_out.read_text(encoding="utf-8"))
        assert rc == 0
        assert result["gap_units"] == 0
        assert result["needs_cleanup_total"] == 0
        assert result["signed_debt_units"] == 4
        assert result["signed_debt_mode"] == "structural_refusal_signed_off_2026-11-19"
        assert result["structural_refusals"]["total"] == 4
        assert result["structural_refusals"]["still_counted_in_gap_units"] is False
        assert result["structural_refusals"]["signed_off"] == "owner 2026-11-19 (#374)"

    def test_one_non_structural_skip_adds_one_to_gap(self, tmp_path, no_preflight):
        cells = _structural_cells()
        _write_matrix(tmp_path, "cli", cells + [_cell("docx", "pdf", "md", "skip",
                                                      "pandoc not installed")])
        _write_matrix(tmp_path, "mcp", [dict(c) for c in cells])

        json_out = tmp_path / "gap.json"
        rc = _run_skip(tmp_path, expect_total=7, json_out=json_out)

        result = json.loads(json_out.read_text(encoding="utf-8"))
        assert rc == 1
        assert result["gap_units"] == 1
        assert result["signed_debt_units"] == 4
        assert result["per_channel"]["CLI"]["needs_cleanup"] == 1
        assert result["per_channel"]["MCP"]["needs_cleanup"] == 0
        assert result["per_channel"]["CLI"]["signed_debt"] == 2


class TestSignedUnreachableB20:
    """owner 2026-11-25（B20）：内容依赖但样例语料补不出来的跳过，签字移出而非留作债。

    判据要点：**只有**「中间 MD 缺 JSON 代码块」这部分留在 exempt（补语料可清）；
    SRT/CSV/PPTX-XLSX 这类补语料也补不出来的，改记 signed_debt，且 gap_units 归零。
    """

    SRT = "MD→SRT requires timestamped cues; no timestamps in fixture"
    CSV = "MD→CSV requires a table; intermediate MD has none"
    JSON_ = "MD→JSON requires JSON code block or OPP key=value source"

    def test_reason_buckets_are_mutually_exclusive(self):
        for reason in (self.SRT, self.CSV):
            assert ng.is_signed_unreachable(reason) is True
            assert ng.is_exempt(reason) is False, f"{reason} 仍在 exempt，会重复计入"
        assert ng.is_exempt(self.JSON_) is True
        assert ng.is_signed_unreachable(self.JSON_) is False

    def test_signed_unreachable_cells_do_not_count_as_gap(self, tmp_path, no_preflight):
        cells = [
            _cell("docx", "srt", "md", "skip", self.SRT),
            _cell("docx", "csv", "md", "skip", self.CSV),
            _cell("docx", "json", "md", "skip", self.JSON_),
            _cell("docx", "txt", "md", "pass"),
        ]
        _write_matrix(tmp_path, "cli", cells)
        _write_matrix(tmp_path, "mcp", [dict(c) for c in cells])

        json_out = tmp_path / "gap.json"
        _run_skip(tmp_path, expect_total=8, json_out=json_out)
        data = json.loads(json_out.read_text(encoding="utf-8"))

        # 每通道：2 格签字移出 + 1 格 exempt（补语料可清）⇒ needs_cleanup = 0
        assert data["signed_debt_units"] == 4, data
        assert data["gap_units"] == 0, data
        assert data["per_channel"]["CLI"]["exempt"] == 1
        assert data["per_channel"]["CLI"]["signed_debt"] == 2
