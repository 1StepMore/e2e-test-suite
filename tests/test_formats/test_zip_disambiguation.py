"""Tests for ZIP format disambiguation in magic bytes detection.

All ZIP-based formats (DOCX, PPTX, ODT, EPUB, XLSX) share the same
PK\x03\x04 magic bytes. The _disambiguate_zip_format function inspects
internal ZIP entry names to distinguish them.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from orf.detection.format_detector import FormatDetector
from orf.detection.magic_bytes import _disambiguate_zip_format
from opp.detector import detect_format, FormatType


def _make_zip(path: Path, entries: dict[str, bytes]) -> Path:
    """Create a minimal ZIP file with the given entries."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return path


class TestZipDisambiguationDirect:
    """Direct tests of _disambiguate_zip_format()."""

    def test_docx(self, tmp_path: Path):
        z = _make_zip(tmp_path / "test.zip", {"word/document.xml": b"<document/>"})
        assert _disambiguate_zip_format(z) == "docx"

    def test_pptx(self, tmp_path: Path):
        z = _make_zip(tmp_path / "test.zip", {"ppt/presentation.xml": b"<presentation/>"})
        assert _disambiguate_zip_format(z) == "pptx"

    def test_xlsx(self, tmp_path: Path):
        z = _make_zip(tmp_path / "test.zip", {"xl/workbook.xml": b"<workbook/>"})
        assert _disambiguate_zip_format(z) == "xlsx"

    def test_epub(self, tmp_path: Path):
        z = _make_zip(
            tmp_path / "test.zip",
            {
                "META-INF/container.xml": b"<container/>",
                "OEBPS/content.opf": b"<opf/>",
            },
        )
        assert _disambiguate_zip_format(z) == "epub"

    def test_odt_via_container_xml(self, tmp_path: Path):
        z = _make_zip(
            tmp_path / "test.zip",
            {"META-INF/container.xml": b"<container/>", "content.xml": b"<content/>"},
        )
        # ODT has META-INF/container.xml without OEBPS/ prefix
        assert _disambiguate_zip_format(z) == "odt"

    def test_odt_via_content_xml(self, tmp_path: Path):
        z = _make_zip(tmp_path / "test.zip", {"content.xml": b"<content/>"})
        assert _disambiguate_zip_format(z) == "odt"

    def test_empty_zip_returns_unknown(self, tmp_path: Path):
        z = _make_zip(tmp_path / "empty.zip", {})
        assert _disambiguate_zip_format(z) == "zip/unknown"

    def test_nonexistent_file_returns_unknown(self, tmp_path: Path):
        assert _disambiguate_zip_format(tmp_path / "nope.zip") == "zip/unknown"

    def test_non_zip_file_returns_unknown(self, tmp_path: Path):
        p = tmp_path / "not_a_zip.txt"
        p.write_text("hello")
        assert _disambiguate_zip_format(p) == "zip/unknown"


class TestORFFormatDetector:
    """Test that FormatDetector.detect_from_file uses disambiguation."""

    @pytest.fixture
    def detector(self) -> FormatDetector:
        return FormatDetector()

    def test_docx_detected(self, detector: FormatDetector, tmp_path: Path):
        z = _make_zip(tmp_path / "test.docx", {"word/document.xml": b"<document/>"})
        assert detector.detect_from_file(z) == "DOCX"

    def test_pptx_detected(self, detector: FormatDetector, tmp_path: Path):
        z = _make_zip(tmp_path / "test.pptx", {"ppt/presentation.xml": b"<presentation/>"})
        assert detector.detect_from_file(z) == "PPTX"

    def test_xlsx_detected(self, detector: FormatDetector, tmp_path: Path):
        z = _make_zip(tmp_path / "test.xlsx", {"xl/workbook.xml": b"<workbook/>"})
        assert detector.detect_from_file(z) == "XLSX"

    def test_epub_detected(self, detector: FormatDetector, tmp_path: Path):
        z = _make_zip(
            tmp_path / "test.epub",
            {"META-INF/container.xml": b"", "OEBPS/content.opf": b""},
        )
        assert detector.detect_from_file(z) == "EPUB"

    def test_odt_detected(self, detector: FormatDetector, tmp_path: Path):
        z = _make_zip(tmp_path / "test.odt", {"content.xml": b"<content/>"})
        assert detector.detect_from_file(z) == "ODT"

    def test_unknown_zip(self, detector: FormatDetector, tmp_path: Path):
        z = _make_zip(tmp_path / "test.zip", {"random.txt": b"hello"})
        from orf.error_handlers.conversion_error import FormatDetectionError

        with pytest.raises(FormatDetectionError):
            detector.detect_from_file(z)


class TestOPPDetector:
    """Test that OPP detect_format uses disambiguation for ZIP files."""

    def test_docx_detected(self, tmp_path: Path):
        z = _make_zip(tmp_path / "test.zip", {"word/document.xml": b"<document/>"})
        fmt, conf = detect_format(z)
        assert fmt == FormatType.DOCX
        assert conf > 0.0

    def test_pptx_detected(self, tmp_path: Path):
        z = _make_zip(tmp_path / "test.zip", {"ppt/presentation.xml": b"<presentation/>"})
        fmt, conf = detect_format(z)
        assert fmt == FormatType.PPTX
        assert conf > 0.0

    def test_xlsx_detected(self, tmp_path: Path):
        z = _make_zip(tmp_path / "test.zip", {"xl/workbook.xml": b"<workbook/>"})
        fmt, conf = detect_format(z)
        assert fmt == FormatType.XLSX
        assert conf > 0.0

    def test_epub_detected(self, tmp_path: Path):
        z = _make_zip(
            tmp_path / "test.zip",
            {"META-INF/container.xml": b"", "OEBPS/content.opf": b""},
        )
        fmt, conf = detect_format(z)
        assert fmt == FormatType.EPUB
        assert conf > 0.0

    def test_odt_detected(self, tmp_path: Path):
        z = _make_zip(tmp_path / "test.zip", {"content.xml": b"<content/>"})
        fmt, conf = detect_format(z)
        assert fmt == FormatType.ODT
        assert conf > 0.0

    def test_unknown_zip_returns_unknown(self, tmp_path: Path):
        z = _make_zip(tmp_path / "test.zip", {"random.txt": b"hello"})
        fmt, conf = detect_format(z)
        assert fmt == FormatType.UNKNOWN
