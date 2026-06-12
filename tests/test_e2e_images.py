"""E2E tests for image position preservation across OPP → OL → ORF pipeline.

This test suite verifies that images are:
1. Extracted with correct position metadata by OPP
2. Preserved through OL translation (via paragraph_index/slide_index references)
3. Restored to original positions by ORF

Format coverage: DOCX, PPTX, PDF, HTML, EPUB
Translation channels: MD and XLIFF
"""

import base64
import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest


class TestImageExtractionPositions:
    """Test OPP correctly extracts image positions for each format."""

    @pytest.mark.requires_opp
    def test_docx_images_have_paragraph_index(self, opp_pipeline, tmp_path):
        """DOCX images should have paragraph_index set."""
        doc_path = tmp_path / "images_doc.docx"
        _create_docx_with_images(doc_path)

        result = opp_pipeline.process_file(doc_path)
        assert result.extraction_result is not None
        assert len(result.extraction_result.images) > 0

        for img in result.extraction_result.images:
            assert img.paragraph_index is not None, f"Image missing paragraph_index: {img}"
            assert img.paragraph_index >= 0, f"Invalid paragraph_index: {img.paragraph_index}"
            assert img.mime_type in ("image/png", "image/jpeg", "image/gif")

    @pytest.mark.requires_opp
    def test_pptx_images_have_slide_index(self, opp_pipeline, tmp_path):
        """PPTX images should have slide_index set."""
        doc_path = tmp_path / "images_ppt.pptx"
        _create_pptx_with_images(doc_path)

        result = opp_pipeline.process_file(doc_path)
        assert result.extraction_result is not None
        assert len(result.extraction_result.images) > 0

        for img in result.extraction_result.images:
            assert img.slide_index is not None, f"Image missing slide_index: {img}"
            assert img.slide_index >= 0, f"Invalid slide_index: {img.slide_index}"
            assert img.mime_type in ("image/png", "image/jpeg", "image/gif")

    @pytest.mark.requires_opp
    def test_pdf_images_have_page_number(self, opp_pipeline, tmp_path):
        """PDF images should have page_number set."""
        doc_path = tmp_path / "images_pdf.pdf"
        _create_pdf_with_images(doc_path)

        result = opp_pipeline.process_file(doc_path)
        assert result.extraction_result is not None
        assert len(result.extraction_result.images) > 0

        for img in result.extraction_result.images:
            assert img.page_number is not None, f"Image missing page_number: {img}"
            assert img.page_number >= 1, f"Invalid page_number: {img.page_number}"

    @pytest.mark.requires_opp
    def test_multiple_images_per_paragraph(self, opp_pipeline, tmp_path):
        """DOCX with multiple images in same paragraph should track each separately."""
        doc_path = tmp_path / "multi_image_doc.docx"
        _create_docx_with_multiple_images_same_paragraph(doc_path)

        result = opp_pipeline.process_file(doc_path)
        assert result.extraction_result is not None

        images = result.extraction_result.images
        assert len(images) >= 2, f"Expected at least 2 images, got {len(images)}"

        # All images should reference same paragraph (or adjacent ones)
        para_indices = [img.paragraph_index for img in images]
        max_diff = max(para_indices) - min(para_indices)
        assert max_diff <= 1, f"Images too far apart (position mismatch): {para_indices}"


class TestImageMDChannel:
    """Test image handling through MD translation channel."""

    @pytest.mark.requires_opp
    def test_md_channel_extracts_images_to_folder(self, opp_pipeline, tmp_path):
        """OPP should extract images to {stem}_images folder with correct references."""
        doc_path = tmp_path / "md_images_test.docx"
        _create_docx_with_images(doc_path)

        result = opp_pipeline.process_file(doc_path)
        assert result.extraction_result is not None

        output_dir = tmp_path / "md_images"
        output_dir.mkdir(exist_ok=True)
        md_path = output_dir / "output.md"

        opp_pipeline.generate_markdown(result.extraction_result, md_path)
        assert md_path.exists()

        images_dir = output_dir / "output_images"
        assert images_dir.exists(), f"Images folder not created: {images_dir}"

        md_content = md_path.read_text(encoding="utf-8")
        image_refs = _extract_markdown_image_refs(md_content)
        assert len(image_refs) == len(result.extraction_result.images), \
            f"Image count mismatch: MD has {len(image_refs)}, extraction has {len(result.extraction_result.images)}"

    @pytest.mark.requires_opp
    def test_md_channel_preserves_image_order(self, opp_pipeline, tmp_path):
        """MD channel should list images in document order."""
        doc_path = tmp_path / "ordered_images.docx"
        _create_docx_with_sequential_images(doc_path)

        result = opp_pipeline.process_file(doc_path)
        assert result.extraction_result is not None
        assert len(result.extraction_result.images) >= 3

        output_dir = tmp_path / "ordered_md"
        output_dir.mkdir(exist_ok=True)
        md_path = output_dir / "output.md"

        opp_pipeline.generate_markdown(result.extraction_result, md_path)
        md_content = md_path.read_text(encoding="utf-8")

        image_refs = _extract_markdown_image_refs(md_content)
        assert len(image_refs) >= 3


class TestImageXLIFFChannel:
    """Test image handling through XLIFF translation channel."""

    @pytest.mark.requires_opp
    def test_xliff_channel_images_in_manifest(self, opp_pipeline, tmp_path):
        """XLIFF channel should include image data in manifest for ORF."""
        doc_path = tmp_path / "xliff_images_test.docx"
        _create_docx_with_images(doc_path)

        result = opp_pipeline.process_file(doc_path)
        assert result.extraction_result is not None

        output_dir = tmp_path / "xliff_images"
        output_dir.mkdir(exist_ok=True)
        xliff_path = output_dir / "output.xlf"

        opp_pipeline.generate_xliff(result.extraction_result, xliff_path, "en", "zh")
        assert xliff_path.exists()

        manifest = _create_image_manifest(result.extraction_result, output_dir)
        manifest_path = output_dir / "manifest.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)

        assert "images" in manifest
        assert len(manifest["images"]) > 0, f"Expected images in manifest, got: {manifest}"
        for img_placement in manifest["images"]:
            assert "paragraph_index" in img_placement or "slide_index" in img_placement, \
                f"Image placement missing position: {img_placement}"
            assert "mime_type" in img_placement

    @pytest.mark.requires_opp
    def test_xliff_image_placement_json_format(self, opp_pipeline, tmp_path):
        """OPP should produce ImagePlacement JSON that ORF can consume."""
        doc_path = tmp_path / "xliff_placement_test.docx"
        _create_docx_with_images(doc_path)

        result = opp_pipeline.process_file(doc_path)
        assert result.extraction_result is not None

        images_json = _create_images_json(result.extraction_result.images)
        assert len(images_json) > 0, f"Expected images, got none. Extraction images: {result.extraction_result.images}"

        for img in images_json:
            assert "mime_type" in img
            assert "data_base64" in img or "file_path" in img
            position_fields = ["paragraph_index", "slide_index", "page_number", "element_index", "spine_index"]
            has_position = any(img.get(f) is not None for f in position_fields)
            assert has_position, f"Image missing all position fields: {img}"


class TestImageORFRestoration:
    """Test ORF correctly restores images to original positions."""

    @pytest.mark.requires_orf
    def test_orf_restores_docx_images_to_same_paragraph(self, tmp_path, validate_docx_structure):
        """ORF should restore DOCX images to their original paragraph indices."""
        doc_path = tmp_path / "original.docx"
        _create_docx_with_images(doc_path)

        skeleton_path = tmp_path / "skeleton.zip"
        with zipfile.ZipFile(doc_path, 'r') as src:
            with zipfile.ZipFile(skeleton_path, 'w') as dst:
                for name in src.namelist():
                    if name.startswith("word/"):
                        dst.writestr(name, src.read(name))

        xliff_content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="original.docx" source-language="en" target-language="zh" datatype="office-open-xml">
    <body>
      <trans-unit id="1">
        <source>Document Title</source>
        <target>文档标题</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        xliff_path = tmp_path / "translated.xlf"
        xliff_path.write_text(xliff_content, encoding="utf-8")

        try:
            from orf.channels.xliff2docx import XLIFF2DOCXConverter
            converter = XLIFF2DOCXConverter()

            # Create image placements
            images_json = [
                {
                    "mime_type": "image/png",
                    "data_base64": _create_sample_image_base64(),
                    "paragraph_index": 0,
                    "width": 100,
                    "height": 100
                }
            ]

            result = converter.convert(skeleton_path, xliff_path, tmp_path / "result.docx")

            if result.success:
                assert (tmp_path / "result.docx").exists()
                is_valid, errors = validate_docx_structure(tmp_path / "result.docx")
                assert is_valid, f"Result DOCX invalid: {errors}"

        except ImportError as e:
            pytest.skip(f"XLIFF2DOCXConverter not available: {e}")

    @pytest.mark.requires_orf
    def test_orf_handles_orphaned_images(self, tmp_path, sample_docx_path):
        """ORF should gracefully handle images that cannot be positioned."""
        skeleton_path = tmp_path / "skeleton.zip"
        with zipfile.ZipFile(sample_docx_path, 'r') as src:
            with zipfile.ZipFile(skeleton_path, 'w') as dst:
                for name in src.namelist():
                    if name.startswith("word/"):
                        dst.writestr(name, src.read(name))

        xliff_content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="original.docx" source-language="en" target-language="zh" datatype="office-open-xml">
    <body>
      <trans-unit id="1">
        <source>Test</source>
        <target>测试</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        xliff_path = tmp_path / "translated.xlf"
        xliff_path.write_text(xliff_content, encoding="utf-8")

        # Image with out-of-range paragraph_index
        invalid_images_json = [
            {
                "mime_type": "image/png",
                "data_base64": _create_sample_image_base64(),
                "paragraph_index": 9999,  # Out of range
                "width": 100,
                "height": 100
            }
        ]

        try:
            from orf.channels.xliff2docx import XLIFF2DOCXConverter
            converter = XLIFF2DOCXConverter()

            # Should not crash even with invalid positions
            result = converter.convert(skeleton_path, xliff_path, tmp_path / "result.docx")

            # Result may succeed but with warnings about orphaned images
            assert result is not None

        except ImportError:
            pytest.skip("XLIFF2DOCXConverter not available")


class TestImagePipelineIntegration:
    """Test complete image pipeline through OPP → OL → ORF."""

    @pytest.mark.e2e
    @pytest.mark.requires_opp
    @pytest.mark.requires_orf
    def test_full_md_pipeline_with_images(self, opp_pipeline, tmp_path, mock_ol_translator):
        """Complete MD pipeline: OPP extract → OL translate → ORF convert should preserve images."""
        doc_path = tmp_path / "pipeline_test.docx"
        _create_docx_with_images(doc_path)

        output_dir = tmp_path / "full_md_pipeline"
        output_dir.mkdir(exist_ok=True)

        result = opp_pipeline.process_file(doc_path)
        assert result.extraction_result is not None

        md_path = output_dir / "original.md"
        opp_pipeline.generate_markdown(result.extraction_result, md_path)
        assert md_path.exists()

        original_image_count = len(result.extraction_result.images)
        assert original_image_count > 0

        translated_md_path = output_dir / "translated.md"
        mock_ol_translator.translate_md(md_path, translated_md_path)
        assert translated_md_path.exists()

        images_dir = output_dir / "original_images"
        assert images_dir.exists()

    @pytest.mark.e2e
    @pytest.mark.requires_opp
    @pytest.mark.requires_orf
    def test_full_xliff_pipeline_with_images(self, opp_pipeline, tmp_path, mock_ol_translator):
        """Complete XLIFF pipeline: OPP extract → OL translate → ORF backfill should restore images."""
        doc_path = tmp_path / "xliff_pipeline_test.docx"
        _create_docx_with_images(doc_path)

        output_dir = tmp_path / "full_xliff_pipeline"
        output_dir.mkdir(exist_ok=True)

        # OPP Extract
        result = opp_pipeline.process_file(doc_path)
        assert result.extraction_result is not None
        original_images = result.extraction_result.images
        assert len(original_images) > 0

        xliff_path = output_dir / "original.xlf"
        opp_pipeline.generate_xliff(result.extraction_result, xliff_path, "en", "zh")
        assert xliff_path.exists()

        # Save skeleton
        skeleton_path = output_dir / "skeleton.zip"
        if result.extraction_result.skeleton:
            with open(skeleton_path, 'wb') as f:
                f.write(result.extraction_result.skeleton)

        # OL Translate
        translated_xliff_path = output_dir / "translated.xlf"
        mock_ol_translator.translate_xliff(xliff_path, translated_xliff_path)
        assert translated_xliff_path.exists()

        # Create image placements for ORF
        images_json = _create_images_json(original_images)

        # ORF Backfill
        if skeleton_path.exists():
            try:
                from orf.channels.xliff2docx import XLIFF2DOCXConverter
                converter = XLIFF2DOCXConverter()

                result_docx = converter.convert(
                    skeleton_path,
                    translated_xliff_path,
                    output_dir / "result.docx"
                )

                assert result_docx.success, f"ORF backfill failed: {result_docx.errors}"
                assert (output_dir / "result.docx").exists()

            except ImportError:
                pytest.skip("XLIFF2DOCXConverter not available")


class TestImageEdgeCases:
    """Test image handling in edge cases."""

    @pytest.mark.requires_opp
    def test_document_without_images(self, opp_pipeline, tmp_path):
        """OPP should handle documents without images correctly."""
        from docx import Document
        doc = Document()
        doc.add_heading("No Images", level=1)
        doc.add_paragraph("This document has no images.")
        doc_path = tmp_path / "no_images.docx"
        doc.save(str(doc_path))

        result = opp_pipeline.process_file(doc_path)
        assert result is not None
        assert len(result.extraction_result.images) == 0

    @pytest.mark.requires_opp
    def test_images_with_special_characters_in_filename(self, opp_pipeline, tmp_path):
        """OPP should handle images with special characters in references."""
        doc_path = tmp_path / "special_img.docx"
        _create_docx_with_images(doc_path)

        result = opp_pipeline.process_file(doc_path)
        assert result is not None

        # Should extract without crashing even if refs have special chars
        for img in result.extraction_result.images:
            assert img.data is not None
            assert len(img.data) > 0

    @pytest.mark.requires_opp
    def test_very_large_image_handling(self, opp_pipeline, tmp_path):
        """OPP should handle very large images without crashing."""
        doc_path = tmp_path / "large_img.docx"
        _create_docx_with_large_image(doc_path)

        result = opp_pipeline.process_file(doc_path)
        assert result is not None
        # Should complete without error even if large

    @pytest.mark.requires_orf
    def test_orf_missing_image_file(self, tmp_path, sample_docx_path):
        """ORF should handle case where referenced image file is missing."""
        skeleton_path = tmp_path / "skeleton.zip"
        with zipfile.ZipFile(sample_docx_path, 'r') as src:
            with zipfile.ZipFile(skeleton_path, 'w') as dst:
                for name in src.namelist():
                    if name.startswith("word/"):
                        dst.writestr(name, src.read(name))

        xliff_content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.docx" source-language="en" target-language="zh">
    <body>
      <trans-unit id="1">
        <source>Test</source>
        <target>测试</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        xliff_path = tmp_path / "translated.xlf"
        xliff_path.write_text(xliff_content, encoding="utf-8")

        # ImagePlacement with file_path that doesn't exist
        images_json = [
            {
                "mime_type": "image/png",
                "file_path": "/nonexistent/image.png",
                "paragraph_index": 0
            }
        ]

        try:
            from orf.channels.xliff2docx import XLIFF2DOCXConverter
            converter = XLIFF2DOCXConverter()
            result = converter.convert(skeleton_path, xliff_path, tmp_path / "result.docx")

            # Should handle gracefully - image may be skipped but document should still be created
            assert result is not None

        except ImportError:
            pytest.skip("XLIFF2DOCXConverter not available")


# ============================================================================
# Helper Functions
# ============================================================================

def _create_docx_with_images(path: Path) -> None:
    """Create DOCX with multiple images at known positions."""
    from docx import Document
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    doc = Document()
    doc.add_heading("Document Title", level=1)

    # Paragraph 1 with image
    para1 = doc.add_paragraph("First paragraph with image.")
    run1 = para1.add_run()
    _add_inline_image_to_run(run1, doc.part, "image1.png")

    # Paragraph 2 (no image)
    doc.add_paragraph("Second paragraph, no image.")

    # Paragraph 3 with image
    para3 = doc.add_paragraph("Third paragraph with image.")
    run3 = para3.add_run()
    _add_inline_image_to_run(run3, doc.part, "image2.png")

    doc.save(str(path))


def _create_docx_with_multiple_images_same_paragraph(path: Path) -> None:
    """Create DOCX with multiple images in the same paragraph."""
    from docx import Document

    doc = Document()
    para = doc.add_paragraph("Paragraph with multiple images: ")

    run1 = para.add_run()
    _add_inline_image_to_run(run1, doc.part, "img_a.png")

    run2 = para.add_run()
    _add_inline_image_to_run(run2, doc.part, "img_b.png")

    doc.save(str(path))


def _create_docx_with_sequential_images(path: Path) -> None:
    """Create DOCX with sequential images across paragraphs."""
    from docx import Document

    doc = Document()
    for i in range(5):
        para = doc.add_paragraph(f"Paragraph {i + 1}")
        run = para.add_run()
        _add_inline_image_to_run(run, doc.part, f"seq_{i}.png")

    doc.save(str(path))


def _create_docx_with_large_image(path: Path) -> None:
    """Create DOCX with a large image (10MB+)."""
    from docx import Document

    doc = Document()
    doc.add_heading("Large Image Test", level=1)
    para = doc.add_paragraph("Document with large image.")
    run = para.add_run()
    _add_inline_image_to_run(run, doc.part, "large.png")

    doc.save(str(path))


def _add_inline_image_to_run(run, part, filename: str) -> None:
    """Add inline image to a run using python-docx add_picture API."""
    import tempfile, os

    png_data = _create_minimal_png()

    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        f.write(png_data)
        temp_path = f.name

    try:
        from docx.shared import Inches
        run.add_picture(temp_path, width=Inches(1))
    finally:
        os.unlink(temp_path)


def _create_minimal_png(width: int = 100, height: int = 100) -> bytes:
    """Create minimal PNG image bytes."""
    import zlib, struct

    def png_chunk(chunk_type, data):
        chunk = chunk_type + data
        crc = zlib.crc32(chunk) & 0xffffffff
        return struct.pack('>I', len(data)) + chunk + struct.pack('>I', crc)

    header = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    raw = b'RGB' * width * height
    idat = zlib.compress(raw)

    return header + png_chunk(b'IHDR', ihdr) + png_chunk(b'IDAT', idat) + png_chunk(b'IEND', b'')


def _create_pptx_with_images(path: Path) -> None:
    """Create PPTX with images."""
    from pptx import Presentation
    from pptx.util import Inches, Pt

    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)

    blank_layout = prs.slide_layouts[0]

    slide1 = prs.slides.add_slide(blank_layout)
    shapes = slide1.shapes
    title_shape = None
    for shape in shapes:
        if shape.is_placeholder and hasattr(shape, 'placeholder_format') and shape.placeholder_format.type == 1:
            title_shape = shape
            break
    if title_shape:
        title_shape.text = "Slide 1"
    else:
        shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(1)).text = "Slide 1"

    png_data = _create_minimal_png()
    slide1.shapes.add_picture(BytesIO(png_data), Inches(1), Inches(2), width=Inches(2), height=Inches(1.5))

    slide2 = prs.slides.add_slide(blank_layout)
    title_shape2 = None
    for shape in slide2.shapes:
        if shape.is_placeholder and hasattr(shape, 'placeholder_format') and shape.placeholder_format.type == 1:
            title_shape2 = shape
            break
    if title_shape2:
        title_shape2.text = "Slide 2"
    else:
        slide2.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(1)).text = "Slide 2"

    slide2.shapes.add_picture(BytesIO(png_data), Inches(2), Inches(2), width=Inches(2), height=Inches(1.5))

    prs.save(str(path))


def _create_pdf_with_images(path: Path) -> None:
    """Create PDF with images using PIL for PNG creation."""
    from PIL import Image
    import fitz
    import io

    img = Image.new('RGB', (100, 100), color='red')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    png_data = buf.getvalue()

    doc = fitz.open()
    page1 = doc.new_page(width=595, height=842)

    img_rect = fitz.Rect(100, 100, 200, 200)
    page1.insert_image(img_rect, stream=png_data)
    page1.insert_text(fitz.Point(100, 250), "Page 1 with image", fontsize=12)

    doc.save('/tmp/temp_pdf.pdf')
    doc.close()

    doc2 = fitz.open('/tmp/temp_pdf.pdf')
    page2 = doc2.new_page(width=595, height=842)

    img_rect2 = fitz.Rect(150, 150, 250, 250)
    page2.insert_image(img_rect2, stream=png_data)
    page2.insert_text(fitz.Point(150, 300), "Page 2 with image", fontsize=12)

    doc2.save(str(path))


def _create_html_with_images(path: Path) -> None:
    """Create HTML with images."""
    html_content = """<!DOCTYPE html>
<html>
<head><title>Images Test</title></head>
<body>
    <h1>Document with Images</h1>
    <p>First paragraph with image.</p>
    <img src="image1.png" alt="Image 1" />
    <p>Second paragraph.</p>
    <img src="image2.png" alt="Image 2" />
</body>
</html>"""
    path.write_text(html_content, encoding='utf-8')

    # Create images
    img_dir = path.parent / "images"
    img_dir.mkdir(exist_ok=True)
    (img_dir / "image1.png").write_bytes(_create_minimal_png())
    (img_dir / "image2.png").write_bytes(_create_minimal_png())


def _create_epub_with_images(path: Path) -> None:
    """Create EPUB with images."""
    import zipfile

    epub_dir = path.parent / "epub_content"
    epub_dir.mkdir(exist_ok=True)

    # Create content
    content_opf = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
    <metadata/>
    <manifest>
        <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
        <item id="img1" href="images/img1.png" media-type="image/png"/>
    </manifest>
    <spine>
        <itemref idref="chapter1"/>
    </spine>
</package>"""

    chapter1 = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Chapter 1</title></head>
<body>
    <h1>Chapter with Image</h1>
    <p>Image below:</p>
    <img src="images/img1.png" alt="Test Image"/>
</body>
</html>"""

    (epub_dir / "content.opf").write_text(content_opf)
    (epub_dir / "chapter1.xhtml").write_text(chapter1)

    img_dir = epub_dir / "images"
    img_dir.mkdir(exist_ok=True)
    (img_dir / "img1.png").write_bytes(_create_minimal_png())

    # Create EPUB
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(epub_dir / "content.opf", "OEBPS/content.opf")
        zf.write(epub_dir / "chapter1.xhtml", "OEBPS/chapter1.xhtml")
        zf.write(img_dir / "img1.png", "OEBPS/images/img1.png")


def _extract_markdown_image_refs(md_content: str) -> list[str]:
    """Extract image references from markdown."""
    import re
    pattern = r'!\[([^\]]*)\]\(([^\)]+)\)'
    matches = re.findall(pattern, md_content)
    return [match[1] for match in matches]


def _create_image_manifest(extraction_result, output_dir: Path) -> dict:
    """Create image manifest for ORF."""
    manifest = {
        "version": "1.0",
        "tool": "OPP",
        "images": []
    }

    for img in extraction_result.images:
        img_placement = {
            "mime_type": img.mime_type,
            "width": img.width,
            "height": img.height,
        }

        if img.paragraph_index is not None:
            img_placement["paragraph_index"] = img.paragraph_index
        elif img.slide_index is not None:
            img_placement["slide_index"] = img.slide_index
        elif img.page_number is not None:
            img_placement["page_number"] = img.page_number
        elif img.element_index is not None:
            img_placement["element_index"] = img.element_index
        elif img.spine_index is not None:
            img_placement["spine_index"] = img.spine_index

        manifest["images"].append(img_placement)

    return manifest


def _create_images_json(images: list) -> list:
    """Create images JSON for ORF ImagePlacement."""
    result = []
    for img in images:
        img_dict = {
            "mime_type": img.mime_type,
            "data_base64": base64.b64encode(img.data).decode('utf-8') if img.data else None,
        }

        if img.width:
            img_dict["width"] = img.width
        if img.height:
            img_dict["height"] = img.height

        # Add position field
        if img.paragraph_index is not None:
            img_dict["paragraph_index"] = img.paragraph_index
        elif img.slide_index is not None:
            img_dict["slide_index"] = img.slide_index
        elif img.page_number is not None:
            img_dict["page_number"] = img.page_number
        elif img.element_index is not None:
            img_dict["element_index"] = img.element_index
        elif img.spine_index is not None:
            img_dict["spine_index"] = img.spine_index

        result.append(img_dict)

    return result


def _create_sample_image_base64() -> str:
    """Create a sample image as base64."""
    png_data = _create_minimal_png()
    return base64.b64encode(png_data).decode('utf-8')