"""suite#293 — structural_refusals 呈现口径的三条钉子。

硬要求（issue #293）：①XLIFF 跨格式 58 格被归入 structural_refusals；
②gap_units 与改动前逐位相同（分类不回写判定）；③真债不得被误归入。
"""
import scripts.nightly_gap as ng

XFMT = "XLIFF cross-format not supported by ORF converters"


def _cell(inp, outp, path, status, reason=""):
    return {"inp": inp, "outp": outp, "path": path, "status": status,
            "skip_reason": reason, "detail": ""}


def _synthetic_channel_cells():
    """一个通道 201 格的最小形状：29 个跨格式 skip（结构性桶）+ 夹具豁免
    skip + pandoc 环境类 skip（真债）+ pass。"""
    cells = [_cell("docx", "srt", "md", "skip",
                   "MD→SRT requires timestamped cues"),
             _cell("docx", "pdf", "md", "skip", "pandoc not installed"),
             _cell("md", "docx", "md", "pass")]
    for outp in ("docx", "pptx", "epub", "html", "eml", "json"):
        if outp == "docx":
            continue  # 同格式保留 pass
        cells.append(_cell("docx", outp, "xliff", "skip", XFMT))
    return cells


class TestStructuralRefusalsClassification:
    def test_58_cross_format_cells_are_classified(self):
        """①两条通道各 29 格跨格式 skip → 全部落入 structural_refusals，共 58。"""
        cli = _synthetic_channel_cells()
        mcp = _synthetic_channel_cells()
        per_ch = [ng.collect_structural_refusals(c) for c in (cli, mcp)]
        # 2026-11-25（B20）：collect 现在同时收「签字移出」桶，故每通道 = 5 XLIFF + 1 SRT。
        # XLIFF 的钉子是 5 格/通道，按下标过滤后仍需成立。
        xfmt_per_ch = [len([r for r in x if r["reason"].startswith("XLIFF cross-format")])
                       for x in per_ch]
        assert xfmt_per_ch == [5, 5]
        assert [len(x) for x in per_ch] == [6, 6]
        total = sum(len(x) for x in per_ch)
        # 夹具缩小版：XLIFF 5×2 = 10，外加各通道 1 格签字移出（B20）= 12
        assert total == 12
        assert len([r for r in per_ch[0] + per_ch[1]
                    if r["reason"].startswith("XLIFF cross-format")]) == 10
        for ref in per_ch[0]:
            if not ref["reason"].startswith("XLIFF cross-format"):
                continue  # 签字移出桶的钉子见 test_real_debt_is_not_misclassified
            assert ref["citation"], "每格必须附 ACCEPTED_GAPS 依据"
            assert "orf apply-md" in ref["correct_path"], "每格必须附正确路径指引"
        # 全量形状（29×2）走同一条判据
        full = [_cell("a", "b", "xliff", "skip", XFMT) for _ in range(58)]
        assert len(ng.collect_structural_refusals(full)) == 58

    def test_classification_does_not_touch_gap_math(self):
        """②结构性格子原样留在 needs_cleanup（不豁免、不消失）→ gap_units 不变。

        main() 的算式：gap_units = failed + Σ_通道 (skipped − exempt)。
        分类唯一的合法作用是呈现 —— 这里逐条钉死它不回流判定：
        结构性理由不得命中豁免表；tally 统计里它仍是要清理的 skip。
        """
        cells = _synthetic_channel_cells()
        skips, fails, exempt = ng.tally_cells(cells)
        xf_key = XFMT[:60]
        assert skips.get(xf_key) == 5, "结构性 skip 必须仍出现在 skip 计数里"
        assert xf_key not in exempt, "结构性格子不得被豁免（挪豁免=掩盖真债）"
        assert ng.is_structural_refusal(XFMT) and not ng.is_exempt(XFMT)
        # 判定算式：needs_cleanup = skipped − exempt − signed_unreachable。
        # 2026-11-25（B20）把「SRT 缺时间码」这类从 exempt 挪到 signed 桶，
        # 结果 needs_cleanup 仍为 6（结构性 5 + 真债 1）—— 挪桶不等于放水。
        ch_skipped = sum(skips.values())
        ch_exempt = sum(exempt.values())
        ch_signed = len([r for r in ng.collect_structural_refusals(cells)
                         if r["citation"] == ng.SIGNED_UNREACHABLE_CITATION])
        assert ch_skipped == 7          # 5 xfmt + 1 pandoc + 1 SRT
        assert ch_exempt == 0           # 无可清豁免格
        assert ch_signed == 1           # SRT 进签字桶
        assert ch_skipped - ch_exempt - ch_signed == 6  # 与改动前逐位相同
        assert fails == {}

    def test_real_debt_is_not_misclassified(self):
        """③真债（环境类/缺生产者）与夹具豁免类都不得进结构性桶；两表无交集。"""
        # 真债：三桶都不该收
        for reason in ("pandoc not installed",
                       "md2pptx CLI not installed",
                       "nbformat not installed",
                       "some new producer gap",
                       ""):
            assert not ng.is_structural_refusal(reason), reason
            assert not ng.is_signed_unreachable(reason), reason
            cells = [_cell("docx", "pdf", "md", "skip", reason)]
            assert ng.collect_structural_refusals(cells) == []

        # 内容依赖但补语料补不出来的：进**签字桶**，且必须与结构性桶理由互斥
        for reason in ("MD→SRT requires timestamped cues",
                       "XLSX→PPTX: no slide content"):
            assert not ng.is_structural_refusal(reason), reason
            assert ng.is_signed_unreachable(reason), reason
            rows = ng.collect_structural_refusals(
                [_cell("docx", "pdf", "md", "skip", reason)])
            assert [r["citation"] for r in rows] == [ng.SIGNED_UNREACHABLE_CITATION]
        for pat in ng.EXEMPT_SKIP_REASONS:
            assert not ng.is_structural_refusal(pat), pat
