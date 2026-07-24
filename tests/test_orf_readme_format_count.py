"""Verify ORF README has correct format counts and version.

- Check MD backfill claims 16 formats
- Check XLIFF backfill says ODT (not ODF)
- Check Project Status version matches v0.4.16
"""

from pathlib import Path

README = Path(__file__).resolve().parents[1] / "Omni_Re_Formatter" / "README.md"


def test_md_backfill_16_formats():
    """MD backfill section must list exactly 16 formats."""
    text = README.read_text(encoding="utf-8")
    assert "MD backfill: 16 formats" in text, (
        "Expected 'MD backfill: 16 formats' in ORF README"
    )

    # Verify all 16 format names appear somewhere in the file
    expected_formats = [
        "DOCX", "ODT", "EPUB", "HTML", "RTF", "PDF", "PPTX",
        "ICML", "SRT", "XLSX", "CSV", "JSON", "XML", "IPYNB",
        "EML", "MSG",
    ]
    for fmt in expected_formats:
        assert fmt in text, f"Format {fmt} not found in ORF README"


def test_xliff_backfill_odt_not_odf():
    """XLIFF backfill should use ODT, not the typo ODF."""
    text = README.read_text(encoding="utf-8")
    assert "ODF" not in text, (
        "ORF README still contains stale 'ODF' typo (should be 'ODT')"
    )
    assert "ODT" in text, "ORF README missing 'ODT' in format lists"


def test_project_status_version():
    """Project Status section must reflect current ORF version."""
    text = README.read_text(encoding="utf-8")
    assert "Project Status (v0.4.17)" in text, (
        "Expected 'Project Status (v0.4.17)' in ORF README"
    )
