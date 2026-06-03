"""Test OPP drawing extraction fix: dedup + real paragraph positions.

The OPP fix in docx.py:_extract_inline_drawings:
- Skips mc:Fallback duplicates (12 → 12, not 12 → 24)
- Gets real paragraph positions from w:p parent (not para_count proxy)
- Detects wp:anchor as floating (None for paragraph_index)
- Takes only first blip per drawing (deduplicates Choice+Fallback blips)

The Haier DOCX (chinese business chapter, 447KB) has:
- 12 unique drawings (all wp:inline, 0 wp:anchor)
- 9 paragraphs (indices 0-8)
- 2 images enclosed in w:p (paragraph_index = 7, 8)
- 10 images NOT enclosed in any w:p (paragraph_index = None, structurally floating)
"""

from pathlib import Path

import pytest

from opp.utils.dataclasses import ImageData


pytestmark = [pytest.mark.e2e, pytest.mark.real_chain]


class TestOPPDrawingExtraction:
    def test_haier_docx_extracts_12_unique_images_not_24(
        self, haier_real_docx_path: Path
    ):
        """Haier DOCX has 12 unique drawings. Without dedup fix, OPP extracts 24
        (mc:Choice + mc:Fallback blips per drawing). With fix, extracts 12."""
        from opp.pipeline import OPPPipeline

        pipeline = OPPPipeline(resource_storage_dir=Path("/tmp/opp_test_resources"))
        result = pipeline.process_file(haier_real_docx_path)

        assert len(result.extraction_result.images) == 12, (
            f"Expected 12 unique images (after dedup), got "
            f"{len(result.extraction_result.images)}. OPP may be extracting "
            f"both mc:Choice and mc:Fallback blips per drawing."
        )

    def test_all_haier_images_are_inline_not_floating(
        self, haier_real_docx_path: Path
    ):
        """Haier uses wp:inline for all 12 drawings (no wp:anchor)."""
        from opp.pipeline import OPPPipeline

        pipeline = OPPPipeline(resource_storage_dir=Path("/tmp/opp_test_resources"))
        result = pipeline.process_file(haier_real_docx_path)

        floating_count = sum(
            1 for img in result.extraction_result.images
            if getattr(img, "is_floating", False)
        )
        assert floating_count == 0, (
            f"Haier has 0 wp:anchor drawings, but OPP found {floating_count} floating"
        )

    def test_haier_paragraph_index_values_in_real_range(
        self, haier_real_docx_path: Path
    ):
        """With the fix, paragraph_index reflects the real w:p parent for in-paragraph
        drawings. Haier has 34 w:p elements total (including nested in tables/textboxes),
        so values for all 12 images should be in [0, 33]."""
        from opp.pipeline import OPPPipeline

        pipeline = OPPPipeline(resource_storage_dir=Path("/tmp/opp_test_resources"))
        result = pipeline.process_file(haier_real_docx_path)

        in_para_images = [
            img for img in result.extraction_result.images
            if img.paragraph_index is not None
        ]
        assert len(in_para_images) == 12, (
            f"Expected all 12 images to have paragraph_index with the fix, "
            f"got {len(in_para_images)}"
        )

        para_indices = sorted(img.paragraph_index for img in in_para_images)
        for i, img in enumerate(in_para_images):
            assert 0 <= img.paragraph_index <= 33, (
                f"In-paragraph image {i}: paragraph_index={img.paragraph_index} "
                f"out of range [0, 33]"
            )

    def test_haier_image_data_has_is_floating_field(
        self, haier_real_docx_path: Path
    ):
        """ImageData has the new is_floating field, default False, settable."""
        img = ImageData(data=b"test", mime_type="image/png")
        assert hasattr(img, "is_floating")
        assert img.is_floating is False
        assert img.paragraph_index is None

        img_floating = ImageData(
            data=b"test", mime_type="image/png", is_floating=True
        )
        assert img_floating.is_floating is True

    def test_haier_all_12_images_have_paragraph_index(
        self, haier_real_docx_path: Path
    ):
        """With the recursive w:p search fix, all 12 images are correctly placed
        in paragraphs (including those nested in tables/textboxes/AlternateContent)."""
        from opp.pipeline import OPPPipeline

        pipeline = OPPPipeline(resource_storage_dir=Path("/tmp/opp_test_resources"))
        result = pipeline.process_file(haier_real_docx_path)

        in_para = [
            img for img in result.extraction_result.images
            if img.paragraph_index is not None
        ]
        orphan = [
            img for img in result.extraction_result.images
            if img.paragraph_index is None
        ]

        assert len(in_para) == 12, (
            f"Expected all 12 images to be in-paragraph (with the recursive w:p fix), "
            f"got {len(in_para)} in-paragraph"
        )
        assert len(orphan) == 0, (
            f"Expected 0 orphan images with the recursive w:p fix, "
            f"got {len(orphan)} orphan"
        )

    def test_images_json_carries_is_floating_field(
        self, haier_real_docx_path: Path, tmp_path: Path
    ):
        """images_json.py writes is_floating=True for floating images (none in Haier,
        but verify the field is plumbed through)."""
        import json
        from opp.pipeline import OPPPipeline
        from opp.utils.images_json import generate_images_json

        pipeline = OPPPipeline(resource_storage_dir=tmp_path / "resources")
        result = pipeline.process_file(haier_real_docx_path)

        json_path = tmp_path / "images.json"
        generate_images_json(result.extraction_result, json_path)
        data = json.loads(json_path.read_text())

        assert "images" in data
        assert len(data["images"]) == 12
        for entry in data["images"]:
            assert "is_floating" not in entry, (
                "Haier has 0 floating images; is_floating should be absent"
            )
            assert "paragraph_index" in entry

    def test_image_data_has_wp_anchor_fields(self):
        """Phase 3 compat: ImageData carries wp_anchor_h and wp_anchor_v (EMU offsets).
        Defaults are 0 for inline images. Setable for floating images."""
        img_inline = ImageData(data=b"x", mime_type="image/png")
        assert hasattr(img_inline, "wp_anchor_h")
        assert hasattr(img_inline, "wp_anchor_v")
        assert img_inline.wp_anchor_h == 0
        assert img_inline.wp_anchor_v == 0

        img_float = ImageData(
            data=b"x", mime_type="image/png", is_floating=True,
            wp_anchor_h=123456, wp_anchor_v=789012,
        )
        assert img_float.wp_anchor_h == 123456
        assert img_float.wp_anchor_v == 789012

    def test_haier_inline_images_have_zero_anchor_offsets(
        self, haier_real_docx_path: Path
    ):
        """Haier has 0 wp:anchor drawings, so all 12 images get wp_anchor_h=wp_anchor_v=0."""
        from opp.pipeline import OPPPipeline

        pipeline = OPPPipeline(resource_storage_dir=Path("/tmp/opp_test_resources"))
        result = pipeline.process_file(haier_real_docx_path)

        for i, img in enumerate(result.extraction_result.images):
            assert img.wp_anchor_h == 0, (
                f"Image {i}: expected wp_anchor_h=0 (inline), got {img.wp_anchor_h}"
            )
            assert img.wp_anchor_v == 0, (
                f"Image {i}: expected wp_anchor_v=0 (inline), got {img.wp_anchor_v}"
            )

    def test_anchor_offset_extraction_from_synthetic_anchor(self, tmp_path: Path):
        """Build a synthetic DOCX with a wp:anchor drawing, extract, verify the
        EMU offsets are captured into ImageData.wp_anchor_h/wp_anchor_v.
        This is the Phase 3 compatibility contract: ORF will read these fields
        to rebuild <wp:positionH>/<wp:positionV> on the regenerated DOCX."""
        from lxml import etree
        from opp.extractors.docx import _extract_anchor_offsets

        # Test the helper directly rather than the full pipeline — synthesizing a
        # complete DOCX with a valid rId pointing to a real image part is complex
        # and the helper is the unit under test.
        anchor_xml = """
        <w:drawing xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                   xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
                   xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                   xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
          <wp:anchor distT="0" distB="0" distL="114300" distR="114300"
                     simplePos="0" relativeHeight="251660288" behindDoc="0"
                     locked="0" layoutInCell="1" allowOverlap="1">
            <wp:simplePos x="0" y="0"/>
            <wp:positionH relativeFrom="page">
              <wp:posOffset>111111</wp:posOffset>
            </wp:positionH>
            <wp:positionV relativeFrom="page">
              <wp:posOffset>222222</wp:posOffset>
            </wp:positionV>
            <wp:extent cx="914400" cy="914400"/>
            <wp:effectExtent l="0" t="0" r="0" b="0"/>
            <wp:wrapNone/>
            <wp:docPr id="1" name="Floating 1"/>
            <wp:cNvGraphicFramePr/>
            <a:graphic>
              <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
                <pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
                  <pic:nvPicPr>
                    <pic:cNvPr id="1" name="img.png"/>
                    <pic:cNvPicPr/>
                  </pic:nvPicPr>
                  <pic:blipFill>
                    <a:blip r:embed="rId99"/>
                    <a:stretch><a:fillRect/></a:stretch>
                  </pic:blipFill>
                </pic:pic>
              </a:graphicData>
            </a:graphic>
          </wp:anchor>
        </w:drawing>
        """
        anchor_elem = etree.fromstring(anchor_xml)
        WP_NS = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
        ns_map = {"wp": WP_NS}
        h, v = _extract_anchor_offsets(anchor_elem, WP_NS, ns_map)
        assert h == 111111, f"Expected wp_anchor_h=111111, got {h}"
        assert v == 222222, f"Expected wp_anchor_v=222222, got {v}"

        inline_xml = """
        <w:drawing xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
          <wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
                     distT="0" distB="0" distL="0" distR="0">
            <wp:extent cx="914400" cy="914400"/>
          </wp:inline>
        </w:drawing>
        """
        inline_elem = etree.fromstring(inline_xml)
        h2, v2 = _extract_anchor_offsets(inline_elem, WP_NS, ns_map)
        assert h2 == 0
        assert v2 == 0

    def test_images_json_includes_anchor_offsets_for_floating(
        self, tmp_path: Path
    ):
        """images_json.py writes wp_anchor_h and wp_anchor_v when is_floating=True."""
        import json
        from opp.utils.dataclasses import ExtractionResult
        from opp.utils.images_json import generate_images_json

        result = ExtractionResult(
            paragraphs=[],
            tables=[],
            images=[
                ImageData(
                    data=b"\x89PNG\r\n", mime_type="image/png",
                    is_floating=True, paragraph_index=None,
                    wp_anchor_h=111111, wp_anchor_v=222222,
                ),
                ImageData(
                    data=b"\x89PNG\r\n", mime_type="image/png",
                    is_floating=False, paragraph_index=5,
                ),
            ],
        )
        json_path = tmp_path / "images.json"
        generate_images_json(result, json_path)
        data = json.loads(json_path.read_text())

        assert len(data["images"]) == 2
        floating_entry = data["images"][0]
        assert floating_entry["is_floating"] is True
        assert floating_entry["paragraph_index"] is None
        assert floating_entry["wp_anchor_h"] == 111111
        assert floating_entry["wp_anchor_v"] == 222222

        inline_entry = data["images"][1]
        assert "is_floating" not in inline_entry
        assert "wp_anchor_h" not in inline_entry
        assert "wp_anchor_v" not in inline_entry
        assert inline_entry["paragraph_index"] == 5
