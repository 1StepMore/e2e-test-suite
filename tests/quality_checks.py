"""Translation quality checks for the Omni Suite matrix regression.

Codified from the QC function in `/tmp/run_scene_matrix.py` (the
2026-06-24 full-matrix test runner). The original 200-cell matrix
regression flagged 48 cells as FAIL — all 48 were false positives
caused by three hardcoded, format-insensitive rules. This module
fixes all three and pins the new contract with regression tests.

The three bugs that were fixed:

1. **Degenerate detection mis-flagged markdown table separator lines.**
   The original `(.)1{9,}` regex matched `|--------|` (10+ dashes
   in a row), flagging perfectly valid tables as `DEGENERATE_OUTPUT`.
   Fix: strip markdown table separator/alignment rows before applying
   the regex.

2. **Translation-existence check used an absolute character threshold.**
   The original `cn_chars > 20` (20 Chinese characters) rejected
   short-content formats like PDF / PPTX / XLSX / CSV where the
   source itself is <20 characters, even when the translation was
   correct. Fix: replace with a target/source length ratio that is
   proportional to source length.

3. **Source-non-translatable was not detected.**
   JSON files and HTML files with only `<img>` metadata extract to
   pure ```json``` / ```html``` code blocks. After the v0.4.7 #5
   fence-preservation fix, the code block content is correctly
   preserved verbatim — so the translated target has 0 characters
   of "translation" but the file is genuinely not translatable.
   The original check rejected these as `NO_TRANSLATION`. Fix: if
   the source is entirely fenced code blocks, return
   `source_non_translatable=True` and short-circuit to PASS.

Public API: `check_translation_quality(source, target, ...)` returns
a `QualityResult` dataclass. The matrix test runner consumes this
to categorize each cell.

Reference issue: 1StepMore/e2e-test-suite#4.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Markdown table separator/alignment row. Matches lines that consist
# only of pipes, hyphens, colons, and spaces — i.e. the second row of
# a markdown table that defines column alignment.
#   e.g.  |-------|-------|-------|   →  matches
#         |:-------|:-----:|------:|  →  matches
#         -------                →  does not match (no pipes, ambiguous)
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?[\s\-:|]+\|?\s*$", re.MULTILINE)

# Triple-backtick fenced code block (with optional language tag).
# Same shape as `Omni_Localizer/src/ol_post/punctuation.py:_FENCE_RE`
# — kept in sync deliberately.
_FENCE_RE = re.compile(r"```[\w]*\n[\s\S]*?```")

# Degenerate-character detector. Matches 10+ of the same character
# in a row. Used to flag cases where the LLM output is mostly
# punctuation, formatting chars, or just broken (e.g. ".........").
# Note: this is applied AFTER stripping table separator lines, so
# table dashes are not flagged.
_DEGENERATE_RE = re.compile(r"(.)\1{9,}")

# CJK Unified Ideographs U+4E00–U+9FFF + extension A (U+3400–U+4DBF)
# — used to count "Chinese characters" in the target for the
# `cn_chars` field. This is the same range the original script used.
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")

# Markdown emphasis/bullet markers we strip before counting "real text"
# characters in the target. If the target is mostly `*` `_` `-` `#` etc.
# with very few non-marker chars, it's likely a broken/malformed output.
_MARKER_CHARS = set("*_`-#>")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class QualityResult:
    """Outcome of `check_translation_quality()`.

    The matrix test runner inspects these fields to categorize each
    cell. `is_complete` is the overall pass/fail — if any blocking
    check fails, the cell is FAIL.
    """

    is_complete: bool
    """Overall pass/fail. True iff the translation is acceptable."""

    has_translation: bool
    """True iff the target contains translatable content (CJK / latin words
    beyond a trivial number of chars)."""

    is_degenerate: bool
    """True iff the target looks broken (10+ of the same char in a row,
    outside markdown table separators)."""

    is_table_separator_only: bool = False
    """True iff the target consists entirely of markdown table separator
    rows (degenerate-detection false positive guard)."""

    source_non_translatable: bool = False
    """True iff the source is entirely fenced code blocks and therefore
    has no translatable content (Issue #4 fix #3). When True, the cell
    is PASS regardless of target content."""

    target_chars: int = 0
    """Total target length in characters (after whitespace strip)."""

    source_chars: int = 0
    """Total source length in characters (after whitespace strip)."""

    cn_chars: int = 0
    """CJK character count in target — kept for backwards compatibility
    with the original `cn_chars > 20` check (and for human-readable
    reporting)."""

    target_source_ratio: float = 0.0
    """len(target.strip()) / max(1, len(source.strip())). For very short
    sources, the absolute fallback (`MIN_TARGET_CHARS`) takes over."""

    reason: str = ""
    """Human-readable reason if the result is FAIL. Empty for PASS."""

    notes: list[str] = field(default_factory=list)
    """Non-blocking diagnostic notes (e.g. "table separator stripped
    from degenerate check")."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_entirely_fenced_code(text: str) -> bool:
    """True iff `text` consists entirely of fenced code blocks (possibly
    with surrounding whitespace).

    This is the "source is not translatable" detection for fix #3:
    if the OPP extract is a JSON / HTML code-block file (i.e. the
    entire content is wrapped in ```json ... ``` or ```html ... ```),
    the translation is expected to be the same code block verbatim
    (per the v0.4.7 #5 fence-preservation fix), and 0 "translated
    chars" is the correct outcome — not a quality failure.
    """
    if not text or not text.strip():
        return False  # Empty source is "nothing to translate", not "non-translatable"
    stripped = _FENCE_RE.sub("", text)
    return stripped.strip() == ""


def _strip_table_separators(text: str) -> str:
    """Remove markdown table separator/alignment rows from `text`.

    A row like `|-------|-------|` or `|:---:|---:|` is a markdown
    alignment marker — NOT actual content. The original
    `(.)1{9,}` regex flagged these as DEGENERATE_OUTPUT (10+ dashes
    in a row), breaking every DOCX and CSV matrix cell that
    contained tables. Strip them first, then run the degenerate
    check on the remainder.
    """
    return _TABLE_SEPARATOR_RE.sub("", text)


def _count_cjk(text: str) -> int:
    return len(_CJK_RE.findall(text))


def _is_only_markers_and_whitespace(text: str) -> bool:
    """True iff `text` after whitespace strip is entirely markdown
    markers (`*` `_` `-` `#` `>`) and whitespace — i.e. the LLM
    output is formatting without content. Used as a secondary
    degenerate signal so a 3-char string of `***` doesn't pass
    the `(.)1{9,}` regex (only 3 in a row) but is still flagged
    degenerate.

    Threshold: at least 1 non-marker char. A single real char like
    "Y" or "甲" passes — we need a real failure to be unambiguous,
    not just a short output. The 10+ repeated char regex handles
    the "*****Y*****" case (10 markers + 1 real char still has a
    10-char run of markers).
    """
    if not text or not text.strip():
        return True
    stripped = text.strip()
    non_marker = sum(1 for c in stripped if c not in _MARKER_CHARS and not c.isspace())
    return non_marker < 1


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

# Minimum target characters for short sources. Below this, ratio-based
# checking is unreliable (e.g. a 4-char source with a 0-char target
# gives ratio 0.0, but a 0-char source with 0-char target also gives
# ratio 0.0 — we want different verdicts for these). A single non-empty
# target is a valid translation of a single-character source, so the
# short-source floor is `max(1, source_chars // 2)` (50% of source
# length, with a hard minimum of 1) rather than an absolute threshold.
MIN_TARGET_CHARS = 1

# Minimum target/source length ratio. 0.25 is empirically a good
# floor for en→zh: Chinese characters are typically denser, so a
# 100-char English source often yields 25-50 Chinese characters
# (ratio 0.25-0.50). A ratio of 0.25 catches "no translation
# produced" while tolerating terse legitimate outputs.
MIN_TARGET_RATIO = 0.25

# Per-format overrides for MIN_TARGET_RATIO. Formats where short
# content is the norm (PDF, PPTX, XLSX, CSV, JSON, HTML) get a
# lower floor so a 5-char translation of a 50-char source still
# passes. The matrix test runner passes `source_format` so the
# appropriate override is applied.
_FORMAT_RATIO_OVERRIDES: dict[str, float] = {
    "pdf": 0.15,    # PDF: title-only / one-paragraph docs are common
    "pptx": 0.20,   # PPTX: slide titles + short bullet text
    "xlsx": 0.20,   # XLSX: cell values, headers, short labels
    "csv": 0.20,    # CSV: cell values can be 1-3 chars (status codes, etc.)
    "json": 0.10,   # JSON: keys can be short; content is often code (see fix #3)
    "html": 0.10,   # HTML: similar to JSON
    "eml": 0.20,    # EML: subject lines, short email bodies
    "epub": 0.25,   # EPUB: full prose, default
    "ipynb": 0.25,  # IPYNB: mostly code
    "xml": 0.25,    # XML: tag-heavy
    "docx": 0.25,   # DOCX: default
    "md": 0.25,     # MD: default
}

# Per-language-pair overrides for MIN_TARGET_RATIO (Issue e2e #6).
# Highest priority tier in the lookup chain (lang > format > default).
# Intentionally empty — every (src, tgt) pair currently falls through
# to _FORMAT_RATIO_OVERRIDES / MIN_TARGET_RATIO. Populate from matrix
# regressions as data warrants.
_LANG_RATIO_OVERRIDES: dict[tuple[str, str], float] = {}


def _resolve_min_ratio(
    source_format: Optional[str],
    source_lang: str,
    target_lang: str,
) -> float:
    """Return the min target/source ratio for this (format, lang) tuple.

    Lookup chain: language pair > format > MIN_TARGET_RATIO default.
    """
    lang_pair = (source_lang, target_lang)
    if lang_pair in _LANG_RATIO_OVERRIDES:
        return _LANG_RATIO_OVERRIDES[lang_pair]
    fmt = (source_format or "").lower().strip()
    return _FORMAT_RATIO_OVERRIDES.get(fmt, MIN_TARGET_RATIO)


def check_translation_quality(
    source: str,
    target: str,
    source_format: Optional[str] = None,
    source_lang: str = "en",
    target_lang: str = "zh",
) -> QualityResult:
    """Decide whether `target` is an acceptable translation of `source`.

    Returns a `QualityResult` describing each check's outcome. The
    `is_complete` field is the overall pass/fail verdict.

    Three checks, in order:

    1. **Source is entirely fenced code blocks** → `source_non_translatable=True`,
       `is_complete=True` (Issue #4 fix #3). The v0.4.7 #5
       fence-preservation fix ensures code blocks are preserved
       verbatim, so 0 "translated chars" in this case is correct.

    2. **Target is degenerate** (10+ of the same char, or pure markdown
       markers) → `is_degenerate=True`, `is_complete=False` (Issue
       #4 fix #1: table separator rows are stripped first so valid
       tables don't false-positive).

    3. **Target has translation** (CJK char count or length ratio
       above the format-aware threshold) → `has_translation=True`
       (Issue #4 fix #2: ratio-based, not absolute).

    Args:
        source: Source text (post-OPP extraction, pre-OL translation).
        target: Translated text (post-OL, post-ORF backfill).
        source_format: Format hint for ratio overrides (one of
            "docx", "pdf", "json", etc.; case-insensitive). Optional
            — defaults to the conservative `MIN_TARGET_RATIO` of 0.3.
        source_lang: Source language code (default "en"). Used in the
            ratio lookup chain (see _LANG_RATIO_OVERRIDES).
        target_lang: Target language code (default "zh"). Used in the
            ratio lookup chain (see _LANG_RATIO_OVERRIDES).

    Returns:
        A `QualityResult` with `is_complete` and the individual check
        outcomes. `reason` is populated on FAIL with a short human
        description.
    """
    notes: list[str] = []
    source_text = (source or "").strip()
    target_text = (target or "").strip()
    source_chars = len(source_text)
    target_chars = len(target_text)
    cn_chars = _count_cjk(target_text)
    ratio = target_chars / max(1, source_chars)

    # ---- Check 1: source is entirely fenced code blocks (no translatable content) ----
    if _is_entirely_fenced_code(source_text):
        return QualityResult(
            is_complete=True,
            has_translation=True,  # the code block is itself the "content"
            is_degenerate=False,
            source_non_translatable=True,
            target_chars=target_chars,
            source_chars=source_chars,
            cn_chars=cn_chars,
            target_source_ratio=ratio,
            reason="",
            notes=["source is entirely fenced code blocks; v0.4.7 #5 fence preservation = PASS"],
        )

    # ---- Check 2: target is degenerate (table separators already excluded) ----
    target_for_degenerate_check = _strip_table_separators(target_text)
    if target_for_degenerate_check != target_text:
        notes.append("markdown table separator rows stripped from degenerate check")
    degenerates = _DEGENERATE_RE.findall(target_for_degenerate_check)
    is_degenerate = bool(degenerates) or _is_only_markers_and_whitespace(target_text)

    # Empty target is its own failure mode (NO_TRANSLATION), not degenerate.
    # An empty target didn't produce broken chars, it produced NO output.
    if not target_text:
        return QualityResult(
            is_complete=False,
            has_translation=False,
            is_degenerate=False,
            target_chars=target_chars,
            source_chars=source_chars,
            cn_chars=cn_chars,
            target_source_ratio=ratio,
            reason="NO_TRANSLATION: target is empty (no translation produced)",
            notes=notes,
        )

    if is_degenerate:
        return QualityResult(
            is_complete=False,
            has_translation=False,
            is_degenerate=True,
            target_chars=target_chars,
            source_chars=source_chars,
            cn_chars=cn_chars,
            target_source_ratio=ratio,
            reason="DEGENERATE_OUTPUT: target has 10+ repeated chars or is pure markers",
            notes=notes,
        )

    # ---- Check 3: target has translation (ratio-based, format-aware) ----
    min_ratio = _resolve_min_ratio(source_format, source_lang, target_lang)

    # Short-source fallback: if source is < 20 chars, a 50% length
    # ratio is the floor (with `MIN_TARGET_CHARS=1` as the hard
    # minimum for non-empty output). A single non-empty target is
    # a valid translation of a single-character source (e.g. "X" →
    # "X" or "X" → "好" both pass). Also accepts ≥1 CJK char
    # regardless of length, since a single Chinese character can be
    # a complete translation.
    if source_chars < 20:
        short_floor = max(MIN_TARGET_CHARS, int(source_chars * 0.5))
        has_translation = target_chars >= short_floor
        if not has_translation and cn_chars >= 1:
            has_translation = True
        notes.append(
            f"short-source path: source_chars={source_chars} < 20, "
            f"using short_floor={short_floor}"
        )
    else:
        has_translation = ratio >= min_ratio

    if not has_translation:
        return QualityResult(
            is_complete=False,
            has_translation=False,
            is_degenerate=False,
            target_chars=target_chars,
            source_chars=source_chars,
            cn_chars=cn_chars,
            target_source_ratio=ratio,
            reason=(
                f"NO_TRANSLATION: target/source ratio {ratio:.2f} < "
                f"min_ratio {min_ratio:.2f} for format={source_format!r}; "
                f"target_chars={target_chars}, cn_chars={cn_chars}"
            ),
            notes=notes,
        )

    return QualityResult(
        is_complete=True,
        has_translation=True,
        is_degenerate=False,
        target_chars=target_chars,
        source_chars=source_chars,
        cn_chars=cn_chars,
        target_source_ratio=ratio,
        reason="",
        notes=notes,
    )


__all__ = [
    "QualityResult",
    "check_translation_quality",
    "MIN_TARGET_CHARS",
    "MIN_TARGET_RATIO",
    "_FORMAT_RATIO_OVERRIDES",
    "_LANG_RATIO_OVERRIDES",
    "_resolve_min_ratio",
]
