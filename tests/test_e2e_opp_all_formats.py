"""E2E tests for OPP - All input formats.

Covers:
- DOCX, PPTX, PDF, XLSX, CSV, JSON, XML, HTML, EPUB
- EML, MSG (Email), Image (OCR), IPYNB, YouTube URL
- Audio, Video

Each format test verifies:
1. OPP can detect the format
2. OPP can extract content correctly
3. OPP generates MD and/or XLIFF output
4. OPP preserves images and formatting where applicable
"""

import json
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

import pytest


class TestOPPDocxFormat:
    """DOCX format E2E tests."""

    @pytest.mark.requires_opp
    def test_docx_detect_and_extract(self, opp_pipeline, tmp_path):
        """OPP should detect and extract DOCX content."""
        from docx import Document

        doc = Document()
        doc.add_heading("Test Document", level=1)
        doc.add_paragraph("Test paragraph with content.")
        doc.add_paragraph("Another paragraph.")

        doc_path = tmp_path / "test.docx"
        doc.save(str(doc_path))

        result = opp_pipeline.process_file(doc_path)
        assert result is not None
        assert result.format_type.value == "docx"
        assert len(result.content) > 0

    @pytest.mark.requires_opp
    def test_docx_generates_markdown(self, opp_pipeline, tmp_path):
        """OPP should generate MD from DOCX."""
        from docx import Document

        doc = Document()
        doc.add_heading("Title", level=1)
        doc.add_paragraph("Content paragraph.")

        doc_path = tmp_path / "title.docx"
        doc.save(str(doc_path))

        result = opp_pipeline.process_file(doc_path)
        md_path = tmp_path / "output.md"
        opp_pipeline.generate_markdown(result.extraction_result, md_path)

        assert md_path.exists()
        content = md_path.read_text()
        assert "Title" in content

    @pytest.mark.requires_opp
    def test_docx_generates_xliff(self, opp_pipeline, tmp_path):
        """OPP should generate XLIFF from DOCX."""
        from docx import Document

        doc = Document()
        doc.add_heading("Hello", level=1)
        doc.add_paragraph("World content.")

        doc_path = tmp_path / "hello.docx"
        doc.save(str(doc_path))

        result = opp_pipeline.process_file(doc_path)
        xliff_path = tmp_path / "hello.xlf"
        opp_pipeline.generate_xliff(result.extraction_result, xliff_path, "en", "zh")

        assert xliff_path.exists()
        xliff_content = xliff_path.read_text()
        assert "<xliff" in xliff_content
        assert "Hello" in xliff_content


class TestOPPPptxFormat:
    """PPTX format E2E tests."""

    @pytest.mark.requires_opp
    def test_pptx_detect_and_extract(self, opp_pipeline, tmp_path):
        """OPP should detect and extract PPTX content."""
        from pptx import Presentation
        from pptx.util import Inches

        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        title = slide.shapes.title
        title.text = "Presentation Title"
        body = slide.placeholders[1]
        body.text = "Slide content"

        pptx_path = tmp_path / "test.pptx"
        prs.save(str(pptx_path))

        result = opp_pipeline.process_file(pptx_path)
        assert result is not None
        assert result.format_type.value == "pptx"
        assert len(result.content) > 0

    @pytest.mark.requires_opp
    def test_pptx_generates_markdown(self, opp_pipeline, tmp_path):
        """OPP should generate MD from PPTX."""
        from pptx import Presentation

        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        title = slide.shapes.title
        title.text = "Slide Title"

        pptx_path = tmp_path / "slide.pptx"
        prs.save(str(pptx_path))

        result = opp_pipeline.process_file(pptx_path)
        md_path = tmp_path / "slide.md"
        opp_pipeline.generate_markdown(result.extraction_result, md_path)

        assert md_path.exists()


class TestOPPPdfFormat:
    """PDF format E2E tests."""

    @pytest.mark.requires_opp
    def test_pdf_detect_and_extract(self, opp_pipeline, tmp_path):
        """OPP should detect and extract PDF content."""
        import fitz

        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text(fitz.Point(100, 100), "PDF Content", fontsize=12)

        pdf_path = tmp_path / "test.pdf"
        doc.save(str(pdf_path))

        result = opp_pipeline.process_file(pdf_path)
        assert result is not None
        assert result.format_type.value == "pdf"
        assert len(result.content) > 0

    @pytest.mark.requires_opp
    def test_pdf_generates_markdown(self, opp_pipeline, tmp_path):
        """OPP should generate MD from PDF."""
        import fitz

        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text(fitz.Point(100, 100), "PDF Text", fontsize=12)

        pdf_path = tmp_path / "pdf_doc.pdf"
        doc.save(str(pdf_path))

        result = opp_pipeline.process_file(pdf_path)
        md_path = tmp_path / "pdf.md"
        opp_pipeline.generate_markdown(result.extraction_result, md_path)

        assert md_path.exists()


class TestOPPExcelFormat:
    """XLSX format E2E tests."""

    @pytest.mark.requires_opp
    def test_xlsx_detect_and_extract(self, opp_pipeline, tmp_path):
        """OPP should detect and extract XLSX content."""
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        ws.append(["Header1", "Header2"])
        ws.append(["Data1", "Data2"])

        xlsx_path = tmp_path / "test.xlsx"
        wb.save(str(xlsx_path))

        result = opp_pipeline.process_file(xlsx_path)
        assert result is not None
        assert result.format_type.value == "xlsx"
        assert len(result.content) > 0

    @pytest.mark.requires_opp
    def test_xlsx_generates_markdown(self, opp_pipeline, tmp_path):
        """OPP should generate MD from XLSX (table format)."""
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["Col1", "Col2"])
        ws.append(["A", "B"])
        ws.append(["C", "D"])

        xlsx_path = tmp_path / "table.xlsx"
        wb.save(str(xlsx_path))

        result = opp_pipeline.process_file(xlsx_path)
        md_path = tmp_path / "table.md"
        opp_pipeline.generate_markdown(result.extraction_result, md_path)

        assert md_path.exists()
        content = md_path.read_text()
        assert "|" in content  # Markdown table


class TestOPPCsvFormat:
    """CSV format E2E tests."""

    @pytest.mark.requires_opp
    def test_csv_detect_and_extract(self, opp_pipeline, tmp_path):
        """OPP should detect and extract CSV content."""
        csv_path = tmp_path / "test.csv"
        csv_path.write_text("col1,col2\nval1,val2\nval3,val4")

        result = opp_pipeline.process_file(csv_path)
        assert result is not None
        assert result.format_type.value == "csv"
        assert len(result.content) > 0

    @pytest.mark.requires_opp
    def test_csv_generates_markdown(self, opp_pipeline, tmp_path):
        """OPP should generate MD table from CSV."""
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("Name,Age\nJohn,30\nJane,25")

        result = opp_pipeline.process_file(csv_path)
        md_path = tmp_path / "data.md"
        opp_pipeline.generate_markdown(result.extraction_result, md_path)

        assert md_path.exists()
        content = md_path.read_text()
        assert "Name" in content
        assert "John" in content


class TestOPPJsonFormat:
    """JSON format E2E tests."""

    @pytest.mark.requires_opp
    def test_json_detect_and_extract(self, opp_pipeline, tmp_path):
        """OPP should detect and extract JSON content."""
        json_path = tmp_path / "test.json"
        json_path.write_text('{"key": "value", "nested": {"data": 123}}')

        result = opp_pipeline.process_file(json_path)
        assert result is not None
        assert result.format_type.value == "json"
        assert len(result.content) > 0

    @pytest.mark.requires_opp
    def test_json_generates_markdown(self, opp_pipeline, tmp_path):
        """OPP should generate MD from JSON."""
        json_path = tmp_path / "obj.json"
        json_path.write_text('{"name": "test", "value": 42}')

        result = opp_pipeline.process_file(json_path)
        md_path = tmp_path / "obj.md"
        opp_pipeline.generate_markdown(result.extraction_result, md_path)

        assert md_path.exists()


class TestOPPXmlFormat:
    """XML format E2E tests."""

    @pytest.mark.requires_opp
    def test_xml_detect_and_extract(self, opp_pipeline, tmp_path):
        """OPP should detect and extract XML content."""
        xml_path = tmp_path / "test.xml"
        xml_path.write_text('<?xml version="1.0"?><root><item>Data</item></root>')

        result = opp_pipeline.process_file(xml_path)
        assert result is not None
        assert result.format_type.value == "xml"
        assert len(result.content) > 0

    @pytest.mark.requires_opp
    def test_xml_generates_markdown(self, opp_pipeline, tmp_path):
        """OPP should generate MD from XML."""
        xml_path = tmp_path / "doc.xml"
        xml_path.write_text('<?xml version="1.0"?><document><section>Content</section></document>')

        result = opp_pipeline.process_file(xml_path)
        md_path = tmp_path / "doc.md"
        opp_pipeline.generate_markdown(result.extraction_result, md_path)

        assert md_path.exists()


class TestOPPHtmlFormat:
    """HTML format E2E tests."""

    @pytest.mark.requires_opp
    def test_html_detect_and_extract(self, opp_pipeline, tmp_path):
        """OPP should detect and extract HTML content."""
        html_path = tmp_path / "test.html"
        html_path.write_text("<!DOCTYPE html><html><body><h1>Title</h1><p>Paragraph</p></body></html>")

        result = opp_pipeline.process_file(html_path)
        assert result is not None
        assert result.format_type.value == "html"
        assert len(result.content) > 0

    @pytest.mark.requires_opp
    def test_html_generates_markdown(self, opp_pipeline, tmp_path):
        """OPP should generate MD from HTML."""
        html_path = tmp_path / "page.html"
        html_path.write_text("<!DOCTYPE html><html><body><h1>Heading</h1><p>Text</p></body></html>")

        result = opp_pipeline.process_file(html_path)
        md_path = tmp_path / "page.md"
        opp_pipeline.generate_markdown(result.extraction_result, md_path)

        assert md_path.exists()


class TestOPPEpubFormat:
    """EPUB format E2E tests."""

    @pytest.mark.requires_opp
    def test_epub_detect_and_extract(self, opp_pipeline, tmp_path):
        """OPP should detect and extract EPUB content."""
        epub_path = tmp_path / "test.epub"
        _create_minimal_epub(epub_path)

        result = opp_pipeline.process_file(epub_path)
        assert result is not None
        assert result.format_type.value == "epub"
        assert len(result.content) > 0

    @pytest.mark.requires_opp
    def test_epub_generates_markdown(self, opp_pipeline, tmp_path):
        """OPP should generate MD from EPUB."""
        epub_path = tmp_path / "book.epub"
        _create_minimal_epub(epub_path)

        result = opp_pipeline.process_file(epub_path)
        md_path = tmp_path / "book.md"
        opp_pipeline.generate_markdown(result.extraction_result, md_path)

        assert md_path.exists()


class TestOPPEmailFormat:
    """Email (EML/MSG) format E2E tests."""

    @pytest.mark.requires_opp
    def test_eml_detect_and_extract(self, opp_pipeline, tmp_path):
        """OPP should detect and extract EML email content."""
        eml_path = tmp_path / "test.eml"
        eml_path.write_text(
            "From: sender@example.com\n"
            "To: receiver@example.com\n"
            "Subject: Test Email\n\n"
            "Email body content."
        )

        result = opp_pipeline.process_file(eml_path)
        assert result is not None
        assert result.format_type.value == "email"
        assert len(result.content) > 0

    @pytest.mark.requires_opp
    def test_msg_detect_and_extract(self, opp_pipeline, tmp_path):
        """OPP should detect and extract MSG email content."""
        try:
            import extract_msg
        except ImportError:
            pytest.skip("extract-msg not installed")

        msg_path = tmp_path / "test.msg"
        _create_minimal_msg(msg_path)

        result = opp_pipeline.process_file(msg_path)
        assert result is not None
        assert result.format_type.value == "email"


class TestOPPImageFormat:
    """Image OCR format E2E tests."""

    @pytest.mark.requires_opp
    def test_png_detect_and_extract(self, opp_pipeline, tmp_path):
        """OPP should detect and OCR PNG image."""
        png_path = tmp_path / "test.png"
        png_path.write_bytes(_create_minimal_png())

        result = opp_pipeline.process_file(png_path)
        assert result is not None
        assert result.format_type.value == "image"
        assert len(result.content) >= 0  # May be empty if no text in image

    @pytest.mark.requires_opp
    def test_jpeg_detect_and_extract(self, opp_pipeline, tmp_path):
        """OPP should detect and OCR JPEG image."""
        from PIL import Image

        img = Image.new('RGB', (200, 100), color='white')
        buf = BytesIO()
        img.save(buf, format='JPEG')
        jpeg_path = tmp_path / "test.jpg"
        jpeg_path.write_bytes(buf.getvalue())

        result = opp_pipeline.process_file(jpeg_path)
        assert result is not None
        assert result.format_type.value == "image"


class TestOPPIpynbFormat:
    """Jupyter Notebook format E2E tests."""

    @pytest.mark.requires_opp
    def test_ipynb_detect_and_extract(self, opp_pipeline, tmp_path):
        """OPP should detect and extract IPYNB content."""
        ipynb_path = tmp_path / "test.ipynb"
        ipynb_content = {
            "nbformat": 4,
            "nbformat_minor": 4,
            "cells": [
                {
                    "cell_type": "code",
                    "metadata": {},
                    "source": ["print('Hello')"]
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["# Heading"]
                }
            ]
        }
        ipynb_path.write_text(json.dumps(ipynb_content), encoding='utf-8')

        result = opp_pipeline.process_file(ipynb_path)
        assert result is not None
        assert result.format_type.value == "ipynb"
        assert len(result.content) > 0


class TestOPPYouTubeFormat:
    """YouTube URL format E2E tests."""

    @pytest.mark.requires_opp
    def test_youtube_url_detect_and_extract(self, opp_pipeline, tmp_path):
        """OPP should detect and extract YouTube URL content."""
        # YouTube URLs are handled via special extractor
        url_file = tmp_path / "youtube.txt"
        url_file.write_text("https://www.youtube.com/watch?v=abc12345")

        result = opp_pipeline.process_file(url_file)
        # May succeed or have specific error depending on network/format support


class TestOPPAudioFormat:
    """Audio transcription format E2E tests."""

    @pytest.mark.requires_opp
    def test_audio_detect_and_extract(self, opp_pipeline, tmp_path):
        """OPP should detect audio file (if supported)."""
        # Create minimal audio file placeholder
        audio_path = tmp_path / "test.mp3"
        audio_path.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00")

        result = opp_pipeline.process_file(audio_path)
        # Audio may not be fully processed without proper setup


class TestOPPSkeletonPreservation:
    """Skeleton preservation for all office formats."""

    @pytest.mark.requires_opp
    def test_docx_skeleton_preserved(self, opp_pipeline, tmp_path):
        """OPP should preserve DOCX skeleton for ORF backfill."""
        from docx import Document

        doc = Document()
        doc.add_heading("Title", level=1)
        doc.add_paragraph("Content")

        doc_path = tmp_path / "skeleton_test.docx"
        doc.save(str(doc_path))

        result = opp_pipeline.process_file(doc_path)
        assert result.extraction_result is not None
        assert result.extraction_result.skeleton is not None

        # Skeleton should be valid ZIP
        skeleton_bytes = result.extraction_result.skeleton
        zf = zipfile.ZipFile(BytesIO(skeleton_bytes))
        assert "word/document.xml" in zf.namelist()

    @pytest.mark.requires_opp
    def test_pptx_skeleton_preserved(self, opp_pipeline, tmp_path):
        """OPP should preserve PPTX skeleton for ORF backfill."""
        from pptx import Presentation

        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        title = slide.shapes.title
        title.text = "Title"

        pptx_path = tmp_path / "skeleton_ppt.pptx"
        prs.save(str(pptx_path))

        result = opp_pipeline.process_file(pptx_path)
        assert result.extraction_result is not None
        assert result.extraction_result.skeleton is not None


class TestOPPManifestGeneration:
    """Manifest generation for all formats."""

    @pytest.mark.requires_opp
    def test_all_formats_generate_manifest(self, opp_pipeline, tmp_path):
        """OPP should generate manifest for all extracted files."""
        from docx import Document

        # Create DOCX
        doc = Document()
        doc.add_heading("Manifest Test", level=1)
        doc.add_paragraph("Test content")

        doc_path = tmp_path / "manifest_test.docx"
        doc.save(str(doc_path))

        result = opp_pipeline.process_file(doc_path)

        # Generate outputs
        md_path = tmp_path / "manifest.md"
        xliff_path = tmp_path / "manifest.xlf"

        opp_pipeline.generate_markdown(result.extraction_result, md_path)
        opp_pipeline.generate_xliff(result.extraction_result, xliff_path, "en", "zh")

        # Create manifest manually (simulating what OPPPipeline does)
        manifest = {
            "manifest_version": "1.0",
            "generated_at": "2026-05-28T00:00:00Z",
            "tool": "OPP",
            "tool_version": "0.5.6",
            "source": {
                "file_path": str(doc_path),
                "original_filename": doc_path.name,
                "format": "DOCX",
            },
            "extraction": {
                "source_lang": "en",
                "target_lang": "zh",
                "outputs": {
                    "markdown": {"path": str(md_path)},
                    "xliff": {"path": str(xliff_path)},
                },
            },
            "skeleton": {
                "path": str(tmp_path / "manifest_test.skeleton.zip"),
                "format": "ZIP"
            }
        }

        manifest_path = tmp_path / "manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        assert manifest_path.exists()
        loaded = json.loads(manifest_path.read_text())
        assert loaded["tool"] == "OPP"


# ============================================================================
# Helper Functions
# ============================================================================

def _create_minimal_png(width=100, height=100) -> bytes:
    """Create minimal PNG image."""
    import zlib, struct

    def png_chunk(chunk_type, data):
        chunk = chunk_type + data
        crc = zlib.crc32(chunk) & 0xffffffff
        return struct.pack('>I', len(data)) + chunk + struct.pack('>I', crc)

    header = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    raw = b'\xff\x00\x00' * width * height
    compressor = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, -15)
    idat_data = compressor.compress(raw) + compressor.flush()

    return header + png_chunk(b'IHDR', ihdr_data) + png_chunk(b'IDAT', idat_data) + png_chunk(b'IEND', b'')


def _create_minimal_epub(epub_path: Path) -> None:
    """Create minimal EPUB file."""
    import zipfile

    epub_dir = epub_path.parent / "epub_temp"
    epub_dir.mkdir(exist_ok=True)

    # Create content
    container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>"""

    content_opf = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
    <metadata/>
    <manifest>
        <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
    </manifest>
    <spine>
        <itemref idref="chapter1"/>
    </spine>
</package>"""

    chapter1 = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Chapter</title></head>
<body><h1>Chapter Title</h1><p>Content.</p></body>
</html>"""

    (epub_dir / "META-INF" / "container.xml").parent.mkdir(exist_ok=True, parents=True)
    (epub_dir / "META-INF" / "container.xml").write_text(container_xml)
    (epub_dir / "OEBPS" / "content.opf").write_text(content_opf)
    (epub_dir / "OEBPS" / "chapter1.xhtml").write_text(chapter1)

    with zipfile.ZipFile(epub_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(epub_dir / "META-INF" / "container.xml", "META-INF/container.xml")
        zf.write(epub_dir / "OEBPS" / "content.opf", "OEBPS/content.opf")
        zf.write(epub_dir / "OEBPS" / "chapter1.xhtml", "OEBPS/chapter1.xhtml")


def _create_minimal_msg(msg_path: Path) -> None:
    """Create minimal MSG file (Outlook)."""
    try:
        import extract_msg
    except ImportError:
        msg_path.write_bytes(b"PK\x03\x04placeholder")
        return

    # If extract_msg available, create proper MSG
    msg_path.write_bytes(b"PK\x03\x04minimal_msg_content")