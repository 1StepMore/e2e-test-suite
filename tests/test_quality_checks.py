"""Unit tests for tests/quality_checks.check_translation_quality.

Pins the contract for the three false-positive fixes documented in
issue 1StepMore/e2e-test-suite#4:

  1. Markdown table separator lines must NOT be flagged as
     DEGENERATE_OUTPUT (the original `(.)1{9,}` regex matched
     `|--------|` — 10+ consecutive dashes).
  2. Translation-existence must use a target/source length ratio,
     not an absolute character threshold (PDF/PPTX/XLSX/CSV with
     short content were rejected by `cn_chars > 20` even when the
     translation was correct).
  3. Source that is entirely fenced code blocks must auto-PASS
     (JSON/HTML files with only `<img>` metadata or `{}` JSON
     extract to code blocks; after v0.4.7 #5 fence preservation,
     the translation is correctly the same code block, not
     "missing translation").

Also pins the negative cases (real degenerate outputs, empty
targets, no translation produced) so future refactors don't
regress the original bug fixes.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add tests/ to sys.path so we can import the module being tested
# (it's not under src/ — it's a suite-level utility).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_checks import (  # noqa: E402  (sys.path mutation must come first)
    MIN_TARGET_CHARS,
    MIN_TARGET_RATIO,
    QualityResult,
    _FORMAT_RATIO_OVERRIDES,
    _is_entirely_fenced_code,
    check_translation_quality,
)


# ════════════════════════════════════════════════════════════════════════
# Fix #1: table separator excluded from degenerate detection
# ════════════════════════════════════════════════════════════════════════


class TestTableSeparatorNotDegenerate:
    """Markdown table separator/alignment rows must not trip the
    `(.)1{9,}` regex. Validates the original Issue #4 Symptom A
    (10格 false positive: 8 DOCX + 2 CSV)."""

    def test_simple_dash_separator_does_not_flag_degenerate(self):
        src = "| Name | Age |\n|----|----|\n| Alice | 30 |"
        tgt = "| 姓名 | 年龄 |\n|----|----|\n| 爱丽丝 | 30 |"
        r = check_translation_quality(src, tgt, "docx")
        assert r.is_complete is True
        assert r.is_degenerate is False
        assert any("table separator" in n for n in r.notes)

    def test_alignment_colon_separator_does_not_flag_degenerate(self):
        """`:---:` style alignment markers (8+ chars of `-` and `:`)."""
        src = "| L | C | R |\n|:---|:---:|---:|\n| a | b | c |"
        tgt = "| 左 | 中 | 右 |\n|:---|:---:|---:|\n| 甲 | 乙 | 丙 |"
        r = check_translation_quality(src, tgt, "docx")
        assert r.is_complete is True
        assert r.is_degenerate is False

    def test_csv_with_table_separator_passes(self):
        """Issue #4 Symptom A: 2格 CSV false positive."""
        src = "name,age\n----,----\nAlice,30\nBob,25"
        tgt = "姓名,年龄\n----,----\n爱丽丝,30\n鲍勃,25"
        r = check_translation_quality(src, tgt, "csv")
        assert r.is_complete is True
        assert r.is_degenerate is False

    def test_real_10_dashes_in_text_still_flags_degenerate(self):
        """Sanity: a row that's NOT a table separator (mixed chars)
        with 10+ repeated dashes is still flagged."""
        src = "Some prose"
        # 10+ dashes NOT in a table (no pipes) — should still flag
        # because the regex would match the run of dashes
        tgt = "This text contains 10+ consecutive dashes: --------------------"
        r = check_translation_quality(src, tgt, "docx")
        # 10+ dashes in non-table context IS a degenerate signal
        # (the 20+ dashes in this string matches the 9+ repeat)
        assert r.is_degenerate is True
        assert r.is_complete is False

    def test_11_dots_in_a_row_still_flags_degenerate(self):
        """Real degenerate case: 11 dots."""
        src = "Hello world"
        tgt = "..........."  # 11 dots
        r = check_translation_quality(src, tgt, "docx")
        assert r.is_degenerate is True
        assert r.is_complete is False
        assert "DEGENERATE_OUTPUT" in r.reason


# ════════════════════════════════════════════════════════════════════════
# Fix #2: ratio-based translation existence (not absolute threshold)
# ════════════════════════════════════════════════════════════════════════


class TestRatioBasedTranslationCheck:
    """Translation existence uses target/source length ratio,
    format-aware. Validates the original Issue #4 Symptom B
    (22格 false positive: 12 PDF + 6 PPTX + 3 XLSX + 1 CSV)."""

    def test_pdf_short_source_passes(self):
        """Issue #4 Symptom B: 12格 PDF. Source 9 chars, target 6 chars."""
        src = "Hello PDF"
        tgt = "你好 PDF"
        r = check_translation_quality(src, tgt, "pdf")
        assert r.is_complete is True
        assert r.has_translation is True
        assert r.target_source_ratio == 6 / 9  # 0.667

    def test_pptx_short_source_passes(self):
        """Issue #4 Symptom B: 6格 PPTX."""
        src = "Slide 1"
        tgt = "幻灯片 1"
        r = check_translation_quality(src, tgt, "pptx")
        assert r.is_complete is True

    def test_xlsx_short_source_passes(self):
        """Issue #4 Symptom B: 3格 XLSX."""
        src = "A,B,C"
        tgt = "甲,乙,丙"
        r = check_translation_quality(src, tgt, "xlsx")
        assert r.is_complete is True

    def test_docx_long_translation_passes_with_low_ratio(self):
        """Real en→zh: 100 chars English → 38 chars Chinese (ratio 0.28).
        Should pass even though ratio is below the 0.30 default."""
        src = "This is a test source string that has plenty of content to translate" * 2
        tgt = "这是一个测试源字符串有大量的内容来翻译" * 2
        r = check_translation_quality(src, tgt, "docx")
        assert r.is_complete is True
        assert r.target_source_ratio >= 0.25  # the new default

    def test_real_no_translation_fails_with_ratio_reason(self):
        """Target < min_ratio should fail with NO_TRANSLATION, not DEGENERATE."""
        src = "This is a long source string with plenty of content for the translator to process and translate"
        tgt = "短"  # 1 char vs 87 char source = ratio 0.01
        r = check_translation_quality(src, tgt, "docx")
        assert r.is_complete is False
        assert r.has_translation is False
        assert r.is_degenerate is False
        assert "NO_TRANSLATION" in r.reason
        assert "ratio" in r.reason

    def test_format_overrides_applied(self):
        """JSON has 0.10 override (not 0.25 default)."""
        # Use realistic varied content (not repeated chars — those would
        # trip the (.)1{9,} degenerate check before the ratio check).
        src = "a structured JSON file containing keys like name age and city to be translated"
        tgt = "JSON 文件 翻译"  # ratio ≈ 0.13 — straddles json 0.10 vs docx 0.25
        ratio = len(tgt) / len(src)
        # Sanity: this ratio must straddle the JSON/docx thresholds
        # (0.10 vs 0.25) for the test to discriminate between formats.
        assert 0.10 < ratio < 0.25, (
            f"test inputs must produce 0.10 < ratio < 0.25 to "
            f"discriminate format overrides; got ratio={ratio:.3f}"
        )

        r = check_translation_quality(src, tgt, "json")
        assert r.is_complete is True
        assert r.target_source_ratio == ratio

        r2 = check_translation_quality(src, tgt, "docx")
        assert r2.is_complete is False
        assert r2.target_source_ratio == ratio

    def test_short_source_one_char_each_passes(self):
        """1-char source, 1-char target — legitimate translation."""
        r = check_translation_quality("X", "Y", "pdf")
        assert r.is_complete is True
        assert r.target_source_ratio == 1.0

    def test_short_source_one_char_cjk_passes(self):
        """1-char source 'A' → 1-char CJK '甲' — legitimate."""
        r = check_translation_quality("A", "甲", "pdf")
        assert r.is_complete is True

    def test_empty_target_fails_with_no_translation_reason(self):
        """Empty target should fail with NO_TRANSLATION, not DEGENERATE."""
        src = "Hello world this is a longer source text for testing"
        tgt = ""
        r = check_translation_quality(src, tgt, "docx")
        assert r.is_complete is False
        assert r.is_degenerate is False  # NOT degenerate
        assert "NO_TRANSLATION" in r.reason
        assert "empty" in r.reason.lower()


# ════════════════════════════════════════════════════════════════════════
# Fix #3: source is entirely fenced code blocks → auto-PASS
# ════════════════════════════════════════════════════════════════════════


class TestNonTranslatableSourcePasses:
    """Source that is entirely fenced code blocks (JSON, HTML with only
    image metadata, etc.) must short-circuit to PASS. Validates the
    original Issue #4 Symptom C (16格 false positive: 10 JSON + 6 HTML).
    """

    def test_json_code_block_passes(self):
        """Issue #4 Symptom C: 10格 JSON."""
        src = '```json\n{"key": "value", "items": [1, 2, 3]}\n```'
        tgt = '```json\n{"key": "value", "items": [1, 2, 3]}\n```'
        r = check_translation_quality(src, tgt, "json")
        assert r.is_complete is True
        assert r.source_non_translatable is True
        assert "v0.4.7 #5" in r.notes[0]

    def test_html_with_only_image_metadata_passes(self):
        """Issue #4 Symptom C: 6格 HTML (only `<img>` metadata)."""
        src = "```html\n<img src=\"foo.png\" alt=\"bar\"/>\n```"
        tgt = "```html\n<img src=\"foo.png\" alt=\"bar\"/>\n```"
        r = check_translation_quality(src, tgt, "html")
        assert r.is_complete is True
        assert r.source_non_translatable is True

    def test_multiple_code_blocks_pass(self):
        """Multiple code blocks with whitespace between them."""
        src = (
            "```json\n{}\n```\n\n"
            "```python\nprint('hi')\n```\n"
        )
        tgt = src  # verbatim
        r = check_translation_quality(src, tgt, "json")
        assert r.is_complete is True
        assert r.source_non_translatable is True

    def test_prose_with_code_block_does_not_trigger(self):
        """If there's ANY prose around the code blocks, normal
        translation check applies (not the non-translatable path)."""
        src = "Here is the JSON:\n\n```json\n{\"k\": \"v\"}\n```\n\nDone."
        tgt = "这是 JSON:\n\n```json\n{\"k\": \"v\"}\n```\n\n完成。"
        r = check_translation_quality(src, tgt, "json")
        assert r.is_complete is True
        assert r.source_non_translatable is False  # NOT triggered

    def test_internal_helper_is_entirely_fenced_code(self):
        """Direct unit test of the helper function."""
        assert _is_entirely_fenced_code('```json\n{}\n```') is True
        assert _is_entirely_fenced_code("```\nfoo\n```") is True
        assert _is_entirely_fenced_code("```\n```") is True
        assert _is_entirely_fenced_code("```json\n{}\n```\n```\nfoo\n```") is True
        # NOT entirely code:
        assert _is_entirely_fenced_code("Some prose") is False
        assert _is_entirely_fenced_code("```json\n{}\n```\nProse") is False
        assert _is_entirely_fenced_code("") is False
        assert _is_entirely_fenced_code("   \n  ") is False


# ════════════════════════════════════════════════════════════════════════
# Module-level constants
# ════════════════════════════════════════════════════════════════════════


class TestModuleConstants:
    """Pin the calibrated threshold values so refactors don't drift."""

    def test_min_target_chars_is_one(self):
        """A 1-char source can have at most a 1-char translation.
        Higher floor would falsely reject 1-char cases."""
        assert MIN_TARGET_CHARS == 1

    def test_min_target_ratio_is_calibrated_for_en_zh(self):
        """0.25 is calibrated for en→zh density (Chinese chars are
        typically denser than English). Do not change without
        re-running the 200-cell matrix regression."""
        assert MIN_TARGET_RATIO == 0.25

    def test_format_overrides_cover_all_target_formats(self):
        """All 11 OPP input formats have a calibrated override."""
        expected_formats = {"pdf", "pptx", "xlsx", "csv", "json", "html",
                            "eml", "epub", "ipynb", "xml", "docx", "md"}
        assert expected_formats.issubset(_FORMAT_RATIO_OVERRIDES.keys())

    def test_pdf_has_lowest_threshold(self):
        """PDF extracts the least text on average; lowest threshold."""
        # Sorted by threshold: pdf=0.15, then pptx/xlsx/csv/eml=0.20,
        # then json/html=0.10 (but these also have fix #3 auto-pass).
        # The lowest non-trivial threshold should be PDF.
        non_trivial = {k: v for k, v in _FORMAT_RATIO_OVERRIDES.items()
                       if k not in ("json", "html")}
        assert non_trivial["pdf"] == min(non_trivial.values())


# ════════════════════════════════════════════════════════════════════════
# QualityResult dataclass
# ════════════════════════════════════════════════════════════════════════


class TestQualityResultDataclass:
    """Pin the dataclass shape so matrix consumers can rely on the fields."""

    def test_default_is_complete_for_passing(self):
        r = QualityResult(
            is_complete=True,
            has_translation=True,
            is_degenerate=False,
        )
        assert r.is_complete is True
        assert r.source_non_translatable is False
        assert r.reason == ""
        assert r.notes == []

    def test_can_be_constructed_with_all_fields(self):
        r = QualityResult(
            is_complete=False,
            has_translation=False,
            is_degenerate=True,
            target_chars=11,
            source_chars=11,
            cn_chars=0,
            target_source_ratio=1.0,
            reason="DEGENERATE_OUTPUT: target has 11 repeated chars",
            notes=["test note"],
        )
        assert r.is_degenerate is True
        assert r.reason.startswith("DEGENERATE_OUTPUT")
        assert r.notes == ["test note"]
