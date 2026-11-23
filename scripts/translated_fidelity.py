"""Content fidelity for a *translated* pipeline.

Why this exists
---------------
``fidelity_checker.compute_fidelity`` scores ``text_score`` as "fraction of
source WORDS that appear in the output". That is the right question for a
same-language round-trip (XLIFF backfill) and the wrong question for a
translation: OL turns English into Chinese, so the English tokens are
*expected* to disappear. Measured on real output (e2e#430 era) the old
scorer gave ``docx→docx = 0.50`` for an artifact that had all 2 tables, 18
paragraphs and correct Chinese headings — and ``docx→odt = 0.06`` for an
artifact that was equally fine. The number was measuring the language, not
the pipeline.

This module answers the two questions that actually matter for a translated
artifact:

1. **Structure preserved?** Paragraph / table / image counts survive the trip.
   A lost table or a dropped paragraph is a real defect regardless of language.
2. **Content translated?** Is prose actually rendered in the target script, or
   is it still the source language (silent no-op translation)?

Deliberately NOT scored: translation *quality* (accuracy, fluency). That needs
a judge model; this module stays deterministic so it can run in CI without keys.

Requires nothing beyond the extractors already used by ``fidelity_checker``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.fidelity_checker import (
    _count_images,
    _count_tables,
    _extract_text,
)

# Formats whose container we can count tables in directly. Anything not listed
# here is *unknown*, not zero — conflating the two is how "odt lost its tables"
# got reported for an artifact that had 37 of them (e2e#430 era).
_TABLE_COUNTABLE = {
    "docx", "pptx", "xlsx", "pdf", "html", "htm", "md", "markdown",
    "odt", "epub", "doc",
}


def _count_tables_any(path: Path) -> int | None:
    """Table count, or None when this format's tables can't be counted here.

    None propagates as "dimension unmeasurable" so it is excluded from the
    score instead of scoring 0.0 (which reads as "every table was lost").
    """
    if not path.exists():
        return 0
    suffix = path.suffix.lower().lstrip(".")
    if suffix == "odt":
        # ODT is a zip; tables are <table:table> in content.xml.
        import zipfile
        try:
            with zipfile.ZipFile(path) as z:
                return z.read("content.xml").decode("utf-8", "replace").count("<table:table")
        except (KeyError, zipfile.BadZipFile, OSError):
            return None
    if suffix == "epub":
        # EPUB is a zip; Count across every XHTML document in the spine order.
        import zipfile
        try:
            with zipfile.ZipFile(path) as z:
                total = 0
                for name in z.namelist():
                    if name.lower().endswith((".xhtml", ".html", ".htm")):
                        total += z.read(name).decode("utf-8", "replace").count("<table")
                return total
        except (zipfile.BadZipFile, OSError):
            return None
    if suffix in _TABLE_COUNTABLE:
        return _count_tables(path)
    return None

# Scripts that indicate "this text is in the target language" for the zh
# direction. Kept as a range rather than a dictionary check: any CJK ideograph
# counts, which is what we want — we are not grading the translation.
_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
# Latin words long enough to be prose rather than an acronym/unit. "ORF",
# "PDF", "DOCX", "IPYNB" are legitimately left untranslated and must not count
# as untranslated prose (that was the reason 5 of 11 paragraphs scored as
# "mixed" on an artifact whose translation was fine).
_LATIN_WORD = re.compile(r"\b[A-Za-z]{5,}\b")


@dataclass
class TranslatedFidelityReport:
    """Fidelity of a translated artifact, split into structure vs translation."""

    structure_score: float = 0.0     # 0-1: paragraph/table/image preservation
    translation_score: float = 0.0   # 0-1: fraction of prose actually translated
    overall: float = 0.0

    source_paragraphs: int = 0
    output_paragraphs: int = 0
    source_tables: int = 0
    output_tables: int = 0
    source_images: int = 0
    output_images: int = 0

    prose_units: int = 0             # prose paragraphs examined
    translated_units: int = 0        # ...of which carry target-script text
    untranslated_samples: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "structure_score": round(self.structure_score, 3),
            "translation_score": round(self.translation_score, 3),
            "overall": round(self.overall, 3),
            "source_paragraphs": self.source_paragraphs,
            "output_paragraphs": self.output_paragraphs,
            "source_tables": self.source_tables,
            "output_tables": self.output_tables,
            "source_images": self.source_images,
            "output_images": self.output_images,
            "prose_units": self.prose_units,
            "translated_units": self.translated_units,
            "untranslated_samples": self.untranslated_samples[:3],
            "notes": self.notes,
        }

    def passes(self, threshold: float = 0.70) -> bool:
        return self.overall >= threshold


def _paragraphs(text: str) -> list[str]:
    """Block-level prose paragraphs, minus table rows and headings.

    Headings are prose too, but a heading that stayed English is a much weaker
    signal than a body paragraph, and they are short enough that the CJK test
    is noisy on them. Counting body prose keeps the metric honest.

    KNOWN LIMITATION — paragraph counts are format-dependent and not
    comparable across formats yet:

    | extractor | shape | consequence |
    |---|---|---|
    | docx (python-docx) | one paragraph per line, no blank lines | accurate |
    | xhtml (odt/epub) | wrapped lines, blank lines between blocks | inflated |
    | pdf (pymupdf) | one text block per line | heavily inflated |

    Measured on one 36-paragraph document: docx 36, odt 233, epub 175, pdf 885.
    Blank-line blocking does NOT fix it — docx text has no blank lines, so the
    whole document collapsed to 3 blocks. The correct fix is per-format native
    paragraph APIs (python-docx `doc.paragraphs`, xhtml `<p>`, pymupdf blocks),
    not text heuristics. Until then, treat the structure score as a *lower
    bound* and read the paragraph counts as diagnostics, not as a ratio.
    """
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("|") or line.startswith("#"):
            continue
        # Drop list bullets / emphasis markers so the length test is fair.
        line = re.sub(r"^[-*+]\s+", "", line).strip()
        if line:
            out.append(line)
    return out


def _is_translated(paragraph: str) -> bool:
    """True when the paragraph is in the target script.

    A paragraph containing any CJK is treated as translated: mixed
    "这是一个……document localization" paragraphs are the normal shape of a
    correct translation that kept product names. A paragraph with no CJK at all
    and multiple Latin prose words is the failure case (silent no-op).
    """
    if _CJK.search(paragraph):
        return True
    return len(_LATIN_WORD.findall(paragraph)) == 0


def compute_translated_fidelity(
    source: Path,
    output: Path,
    output_format: str,
    threshold: float = 0.70,
) -> TranslatedFidelityReport:
    """Score a translated artifact on structure preservation + translation coverage."""
    r = TranslatedFidelityReport()

    src_text = _extract_text(source)
    out_text = _extract_text(output) if output.exists() else ""

    # --- structure -------------------------------------------------------
    src_paras = _paragraphs(src_text)
    out_paras = _paragraphs(out_text)
    r.source_paragraphs = len(src_paras)
    r.output_paragraphs = len(out_paras)

    src_tables = _count_tables_any(source)
    out_tables = _count_tables_any(output) if output.exists() else 0
    r.source_tables = src_tables or 0
    r.output_tables = out_tables or 0
    r.source_images = _count_images(source)
    r.output_images = _count_images(output) if output.exists() else 0

    # Each dimension that the source actually has contributes equally. A
    # dimension the source lacks never contributes — the old scorer handed out
    # a free 1.0 for "no source tables", which inflated every cell.
    dims: list[float] = []
    if r.source_paragraphs:
        dims.append(min(r.output_paragraphs, r.source_paragraphs) / r.source_paragraphs)
    # Only score the table dimension when BOTH sides are measurable. An
    # unmeasurable output (None) is "unknown", never "lost".
    if src_tables and out_tables is not None:
        dims.append(min(out_tables, src_tables) / src_tables)
    elif src_tables and out_tables is None:
        r.notes.append(f"tables not countable for .{output.suffix.lstrip('.')} (skipped)")
    if r.source_images:
        dims.append(min(r.output_images, r.source_images) / r.source_images)
    r.structure_score = sum(dims) / len(dims) if dims else 0.0

    # --- translation -----------------------------------------------------
    prose = out_paras
    r.prose_units = len(prose)
    if prose:
        translated = [p for p in prose if _is_translated(p)]
        r.translated_units = len(translated)
        r.translation_score = len(translated) / len(prose)
        r.untranslated_samples = [p[:70] for p in prose if not _is_translated(p)]
    else:
        r.translation_score = 0.0
        r.notes.append("output has no extractable prose")

    # Structure first: losing a table is worse than leaving a sentence in English.
    r.overall = 0.65 * r.structure_score + 0.35 * r.translation_score

    if not output.exists():
        r.notes.append("output file missing")
    if src_tables and out_tables == 0:
        r.notes.append(f"tables lost: {src_tables} -> 0")
    if r.untranslated_samples:
        r.notes.append(f"{len(r.untranslated_samples)} paragraph(s) not translated")

    return r
