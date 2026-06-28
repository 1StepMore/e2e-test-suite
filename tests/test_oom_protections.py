"""Verify OOM (Out-of-Memory) protections exist in the codebase.

This suite-level test checks that existing OOM protection measures
from Wave 5 are still in place:

1. Cache key uses chunked reading (not whole-file read_bytes)
   — ``opp/cliutils.py:_cache_key()`` uses 8KB chunked SHA-256
2. PDFExtractor has a page limit
   — ``opp/extractors/pdf.py:PDFExtractor.extract_text_blocks()``
     caps at ``MAX_PAGES`` (default 1000)

The actual regression tests live in the OPP test suite:
- ``Omni_Pre_Processor/tests/test_opp_cache.py::test_cache_key_chunked_reading_does_not_oom``
- ``Omni_Pre_Processor/tests/test_pdf_extractor.py::test_max_pages_limits_extraction``

This file verifies those tests still exist and are importable.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OPP_TESTS = ROOT / "Omni_Pre_Processor" / "tests"

# Expected test function names and their files
OOM_GUARDS = {
    "test_cache_key_chunked_reading_does_not_oom": "test_opp_cache.py",
    "test_max_pages_limits_extraction": "test_pdf_extractor.py",
}


def test_oom_guard_files_exist():
    """All OOM guard test files must exist."""
    for test_func, test_file in OOM_GUARDS.items():
        path = OPP_TESTS / test_file
        assert path.exists(), (
            f"Missing OOM guard test file: {path} "
            f"(expected to contain '{test_func}')"
        )


def test_oom_guard_functions_exist():
    """All OOM guard test functions must exist in their respective files."""
    for test_func, test_file in OOM_GUARDS.items():
        path = OPP_TESTS / test_file
        assert path.exists(), f"Missing file: {path}"
        content = path.read_text(encoding="utf-8")
        assert f"def {test_func}" in content, (
            f"Missing OOM guard test function '{test_func}' in {test_file}"
        )


def test_cache_key_uses_chunked_reading():
    """Verify _cache_key() in opp/cliutils.py uses chunked reading, not read_bytes()."""
    cliutils_path = ROOT / "Omni_Pre_Processor" / "src" / "opp" / "cliutils.py"
    assert cliutils_path.exists(), f"Missing cliutils.py: {cliutils_path}"
    content = cliutils_path.read_text(encoding="utf-8")

    # Should have chunked reading
    assert "read(8192)" in content or "read(8 * 1024)" in content or "chunk" in content.lower(), (
        "cliutils.py _cache_key() must use chunked reading (8KB blocks) — "
        "whole-file read_bytes() can OOM on large files"
    )

    # Should NOT use read_bytes()
    assert "read_bytes" not in content or "pytest" in content or "test" in content.lower(), (
        "cliutils.py should not use Path.read_bytes() which loads entire file into memory"
    )


def test_pdf_extractor_has_page_limit():
    """Verify PDFExtractor has a MAX_PAGES cap."""
    pdf_extractor_path = ROOT / "Omni_Pre_Processor" / "src" / "opp" / "extractors" / "pdf.py"
    assert pdf_extractor_path.exists(), f"Missing pdf.py: {pdf_extractor_path}"
    content = pdf_extractor_path.read_text(encoding="utf-8")

    assert "MAX_PAGES" in content, (
        "PDFExtractor must define MAX_PAGES to limit page extraction "
        "(prevents OOM on 50K-page PDFs)"
    )

    assert "page_limit" in content or "min(doc.page_count, max_pages)" in content, (
        "PDFExtractor.extract_text_blocks() must cap extraction at MAX_PAGES "
        "via page_limit = min(doc.page_count, max_pages)"
    )
