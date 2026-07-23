"""Pipeline path selection tests — validates decision tree from README.md §Pipeline Selection Strategy.

References:
    - README.md "Pipeline Selection Strategy" section for the decision tree
      (MD Path vs XLIFF Path vs --target-format both)
    - AGENTS.md "Format Support Matrix" for skeleton.zip support table
    - docs/ARCHITECTURE.md §3.4 for skeleton.zip contract details

The Omni Suite supports two pipeline paths:
    XLIFF Path: layout-faithful backfill using skeleton.zip (requires OOXML skeleton)
    MD Path:    text-first conversion, supports 16 output formats via ORF apply-md

PDF → XLIFF is intentionally blocked (no skeleton.zip for PDF).

Run with:
    pytest tests/test_pipeline_path_selection.py -v --tb=short
"""

import pytest

# ── Helper: pipeline selection logic ────────────────────────────────────────

# Formats that produce skeleton.zip (from README.md "Format Support by Path")
_SKELETON_FORMATS = {"docx", "pptx", "epub"}

# Output format ↔ skeleton support lookup (XLIFF path needs skeleton.zip)
_FORMAT_XLIFF_SUPPORTED = {
    "docx": True,
    "pptx": True,
    "epub": True,
    "xlsx": False,  # no skeleton serializer for xlsx
    "pdf": False,   # PDF→XLIFF intentionally blocked
    "html": False,  # no skeleton.zip
    "csv": False,   # data format, no layout
    "json": False,  # data format, no layout
    "xml": False,   # data format, no layout
    "eml": False,   # email format, no skeleton
    "msg": False,   # email format, no skeleton
    "image": False,  # OCR text extraction only
    "youtube": False,  # transcription only
}


def select_pipeline_path(format: str, requirement: str) -> str:
    """Select the appropriate pipeline path based on format and user requirement.

    Implements the decision tree from README.md:

        Do you need to preserve the ORIGINAL DOCUMENT LAYOUT?
          YES → XLIFF Path (needs skeleton.zip from OPP)
          NO  → MD Path (text-first, 16 output formats)

        When unsure → use --target-format both

        PDF → XLIFF is INTENTIONALLY BLOCKED

    Args:
        format: Input document format (e.g. 'docx', 'pdf', 'html', 'csv').
        requirement: User requirement — one of 'layout_critical',
                     'cross_format', or 'unsure'.

    Returns:
        'xliff' for XLIFF path, 'md' for MD path, 'both' for both.

    Raises:
        ValueError: If format or requirement is unrecognized.
    """
    fmt = format.lower()
    req = requirement.lower()

    valid_formats = _FORMAT_XLIFF_SUPPORTED.keys()
    if fmt not in valid_formats:
        raise ValueError(f"Unknown format '{format}'. Valid: {sorted(valid_formats)}")

    valid_reqs = {"layout_critical", "cross_format", "unsure"}
    if req not in valid_reqs:
        raise ValueError(
            f"Unknown requirement '{requirement}'. Valid: {sorted(valid_reqs)}"
        )

    # Formats without skeleton.zip support → MD only, regardless of requirement
    if not _FORMAT_XLIFF_SUPPORTED[fmt]:
        return "md"

    # Decision tree for skeleton-supporting formats
    if req == "layout_critical":
        return "xliff"
    if req == "cross_format":
        return "md"
    if req == "unsure":
        return "both"

    # Safe fallback
    return "both"


# ── Tests ───────────────────────────────────────────────────────────────────

@pytest.mark.smoke
class TestPipelinePathSelection:
    """Validate pipeline path selection decision tree from README.md."""

    # ── Layout-critical scenarios ──────────────────────────────────────────

    def test_layout_critical_chooses_xliff(self):
        """DOCX with layout_critical → XLIFF path.

        Rationale (README.md): "The output must look exactly like the source
        (contracts, branded docs)". DOCX supports skeleton.zip, so XLIFF
        path is the correct choice for pixel-perfect layout preservation.
        """
        result = select_pipeline_path(format="docx", requirement="layout_critical")
        assert result == "xliff", (
            f"Expected 'xliff' for docx+layout_critical, got '{result}'. "
            "DOCX supports skeleton.zip → XLIFF layout-faithful path."
        )

    def test_pptx_layout_critical_chooses_xliff(self):
        """PPTX with layout_critical → XLIFF path.

        PPTX XLIFF preserves slide masters and exact element positions.
        """
        result = select_pipeline_path(format="pptx", requirement="layout_critical")
        assert result == "xliff"

    def test_epub_layout_critical_chooses_xliff(self):
        """EPUB with layout_critical → XLIFF path.

        EPUB skeleton preserves CSS layout via skeleton.zip.
        """
        result = select_pipeline_path(format="epub", requirement="layout_critical")
        assert result == "xliff"

    # ── Cross-format scenarios ─────────────────────────────────────────────

    def test_cross_format_chooses_md(self):
        """DOCX with cross_format requirement → MD path.

        Rationale (README.md): "You want to convert to a different format
        than the source (e.g. DOCX → EPUB)". ORF apply-md supports 16
        output formats; apply-xliff requires same-format.
        """
        result = select_pipeline_path(format="docx", requirement="cross_format")
        assert result == "md", (
            f"Expected 'md' for docx+cross_format, got '{result}'. "
            "Cross-format conversion requires MD path (16 output formats)."
        )

    def test_cross_format_pptx_to_html(self):
        """PPTX → HTML cross-format → MD path."""
        result = select_pipeline_path(format="pptx", requirement="cross_format")
        assert result == "md"

    def test_cross_format_epub_to_docx(self):
        """EPUB → DOCX cross-format → MD path."""
        result = select_pipeline_path(format="epub", requirement="cross_format")
        assert result == "md"

    # ── Unsure / safe-default scenarios ────────────────────────────────────

    def test_unsure_chooses_both(self):
        """DOCX with unsure requirement → both paths.

        Rationale (README.md): "If you're unsure, extract both. The extra
        disk space is negligible, and having both paths available means
        you can switch without re-extracting."
        """
        result = select_pipeline_path(format="docx", requirement="unsure")
        assert result == "both", (
            f"Expected 'both' for docx+unsure, got '{result}'. "
            "'--target-format both' is the safe default per README.md."
        )

    def test_unsure_pptx_both(self):
        """PPTX with unsure requirement → both."""
        result = select_pipeline_path(format="pptx", requirement="unsure")
        assert result == "both"

    def test_unsure_epub_both(self):
        """EPUB with unsure requirement → both."""
        result = select_pipeline_path(format="epub", requirement="unsure")
        assert result == "both"

    # ── PDF blocks XLIFF (intentionally blocked) ───────────────────────────

    def test_pdf_blocks_xliff(self):
        """PDF with layout_critical → MD path (fallback).

        Rationale (README.md): "PDF → XLIFF is intentionally blocked."
        Per OPP_VALIDATION_MASTER_PLAN.md Q10.3: PDF produces no skeleton.zip.
        The decision tree must fall back to MD path for any PDF input.
        """
        result = select_pipeline_path(format="pdf", requirement="layout_critical")
        assert result == "md", (
            f"Expected 'md' for pdf+layout_critical, got '{result}'. "
            "PDF→XLIFF is intentionally blocked — always fall back to MD."
        )

    def test_pdf_cross_format_md(self):
        """PDF with cross_format → MD path."""
        result = select_pipeline_path(format="pdf", requirement="cross_format")
        assert result == "md"

    def test_pdf_unsure_md(self):
        """PDF with unsure → MD path (never both, no skeleton)."""
        result = select_pipeline_path(format="pdf", requirement="unsure")
        assert result == "md"

    # ── Non-skeleton formats always return MD ───────────────────────────────

    @pytest.mark.parametrize(
        "fmt",
        ["html", "csv", "json", "xml", "eml", "msg", "image", "youtube"],
    )
    def test_non_skeleton_format_always_md(self, fmt):
        """Formats without skeleton.zip support always return 'md'.

        These formats (HTML, CSV, JSON, XML, EML, MSG, image, youtube) do
        not produce skeleton.zip and therefore cannot use the XLIFF path.
        Even layout_critical requests must fall back to MD.
        """
        result = select_pipeline_path(format=fmt, requirement="layout_critical")
        assert result == "md", (
            f"Expected 'md' for {fmt}+layout_critical, got '{result}'. "
            f"{fmt.upper()} has no skeleton.zip support → MD only."
        )

    # ── Edge cases ──────────────────────────────────────────────────────────

    def test_unknown_format_raises(self):
        """Unknown format raises ValueError."""
        with pytest.raises(ValueError, match="Unknown format"):
            select_pipeline_path(format="unknown", requirement="layout_critical")

    def test_unknown_requirement_raises(self):
        """Unknown requirement raises ValueError."""
        with pytest.raises(ValueError, match="Unknown requirement"):
            select_pipeline_path(format="docx", requirement="unknown")

    def test_case_insensitivity(self):
        """Format and requirement are case-insensitive."""
        assert select_pipeline_path(format="DOCX", requirement="LAYOUT_CRITICAL") == "xliff"
        assert select_pipeline_path(format="PDF", requirement="Layout_Critical") == "md"
        assert select_pipeline_path(format="Docx", requirement="UnSuRe") == "both"

    def test_xlsx_no_skeleton(self):
        """XLSX does not produce skeleton.zip → MD only."""
        result = select_pipeline_path(format="xlsx", requirement="layout_critical")
        assert result == "md", (
            f"Expected 'md' for xlsx+layout_critical, got '{result}'. "
            "XLSX has no skeleton serializer."
        )
