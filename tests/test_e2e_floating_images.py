"""E2E test: Floating images (``wp:anchor``) survive OPP → OL → ORF pipeline intact.

Creates a synthetic DOCX with one floating (``wp:anchor``) and one inline
(``wp:inline``) image, runs the full pipeline, then verifies the output
DOCX preserves the ``wp:anchor`` element with correct position values.

This is the E2E counterpart of the ORF unit test in
``Omni_Re_Formatter/tests/test_xliff2docx_floating.py``, which only tests
the injection side in isolation.
"""

from __future__ import annotations

import base64
import json
import os
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from lxml import etree

# ---------------------------------------------------------------------------
# PNG constants
# ---------------------------------------------------------------------------

# 1x1 black RGB pixel (used as inline image)
TINY_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwGhQGI/UOEQAAAASUVORK5CYII="
)


def _make_png_1x1(r: int, g: int, b: int) -> bytes:
    """Create a minimal 1x1 RGB PNG with the given colour."""
    def png_chunk(ctype: bytes, data: bytes) -> bytes:
        chunk = ctype + data
        crc = struct.pack(">I", 0xFFFFFFFF & zlib.crc32(chunk))
        return struct.pack(">I", len(data)) + chunk + crc

    import zlib

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = bytes([r, g, b])
    idat = zlib.compress(raw)
    return header + png_chunk(b"IHDR", ihdr) + png_chunk(b"IDAT", idat) + png_chunk(b"IEND", b"")


# A different-colour 1x1 PNG (blue) so the hash differs from inline → no dedup
_PNG_FLOAT_BYTES = _make_png_1x1(0, 0, 255)
_PNG_INLINE_BYTES = base64.b64decode(TINY_PNG_BASE64)

# ---------------------------------------------------------------------------
# OOXML Namespaces
# ---------------------------------------------------------------------------

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SUITE_ROOT = Path(__file__).resolve().parents[1]
OPP_SRC = SUITE_ROOT / "Omni_Pre_Processor" / "src"
OL_SRC = SUITE_ROOT / "Omni_Localizer" / "src"
ORF_SRC = SUITE_ROOT / "Omni_Re_Formatter" / "src"
OL_CONFIG = SUITE_ROOT / "Omni_Localizer" / "config" / "default.yaml"
OPP_CONFIG = SUITE_ROOT / "Omni_Pre_Processor" / "config" / "default.yaml"

# Floating image position values (in EMU — English Metric Units)
FLOAT_POS_H = 2_286_000  # ~2.5 inches
FLOAT_POS_V = 914_400    # ~1.0 inch
FLOAT_REL_H = "page"
FLOAT_REL_V = "page"
IMAGE_CX = 914_400
IMAGE_CY = 914_400

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------


def _build_env() -> dict[str, str]:
    """Build subprocess environment with FAKE_LLM and proper PYTHONPATH."""
    env = os.environ.copy()
    src_dirs = [
        str(SUITE_ROOT / "tests"),
        str(OPP_SRC),
        str(OL_SRC),
        str(ORF_SRC),
    ]
    env["PYTHONPATH"] = ":".join(
        filter(None, src_dirs + [env.get("PYTHONPATH", "")])
    )
    # FAKE mode
    env["OMNI_TEST_FAKE_LLM"] = "1"
    env["OMNI_TEST_FAKE_PANDOC"] = "1"
    # Config paths
    env["OPP_CONFIG_PATH"] = str(OPP_CONFIG)
    # litellm telemetry suppression (same as conftest.py)
    env.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    env.setdefault("DISABLE_LITELLM_TELEMETRY", "True")
    env.setdefault("LITELLM_TELEMETRY", "False")
    # Dummy API keys — config validators check non-empty; FAKE_LLM bypasses calls
    for k in [
        "ZHIPU_API_KEY",
        "AGNES_API_KEY",
        "NVIDIA_NIM_API_KEY",
        "BAIDU_API_KEY",
        "BAIDU_SECRET_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "MINIMAX_API_KEY",
    ]:
        env.setdefault(k, "sk-dummy")
    env.setdefault("MINIMAX_BASE_URL", "http://localhost:8080/v1")
    # ORF path allowlist
    env.setdefault("ORF_MCP_ALLOWED_DIRS", "/tmp")
    return env


# ---------------------------------------------------------------------------
# DOCX builder
# ---------------------------------------------------------------------------


def _create_docx_with_floating_image(path: Path) -> None:
    """Build a valid DOCX with one floating (``wp:anchor``) and one inline image.

    The floating image uses known position offsets (``FLOAT_POS_H/V``) and the
    inline image serves as a control — OPP should produce two distinct
    ``ImageData`` entries in ``images.json``.
    """
    # --- document.xml --------------------------------------------------------
    doc = etree.Element(
        f"{{{W}}}document",
        nsmap={"w": W, "wp": WP, "a": A, "pic": PIC, "r": R},
    )
    body = etree.SubElement(doc, f"{{{W}}}body")

    # Helper: add a paragraph with optional drawing child
    def _add_para(
        parent: etree._Element,
        text: str,
        drawing_children: list[etree._Element] | None = None,
    ) -> None:
        p = etree.SubElement(parent, f"{{{W}}}p")
        r = etree.SubElement(p, f"{{{W}}}r")
        t = etree.SubElement(r, f"{{{W}}}t")
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        t.text = text
        if drawing_children:
            for dw in drawing_children:
                dwrapper = etree.SubElement(r, f"{{{W}}}drawing")
                dwrapper.append(dw)

    # P1 — text only
    _add_para(body, "Text paragraph before images.")

    # P2 — text + floating (wp:anchor) drawing
    anchor = _build_floating_anchor()
    _add_para(body, "Paragraph with floating image.", drawing_children=[anchor])

    # P3 — text + inline (wp:inline) drawing
    inline = _build_inline()
    _add_para(body, "Paragraph with inline image.", drawing_children=[inline])

    doc_xml = etree.tostring(
        doc, xml_declaration=True, encoding="UTF-8", standalone=True
    )

    # --- word/_rels/document.xml.rels ----------------------------------------
    rels = etree.Element(f"{{{REL}}}Relationships", nsmap={None: REL})
    for rid, target in [("rIdFloat", "media/image1.png"), ("rIdInline", "media/image2.png")]:
        rel = etree.SubElement(rels, f"{{{REL}}}Relationship")
        rel.set("Id", rid)
        rel.set(
            "Type",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
        )
        rel.set("Target", target)
    rels_xml = etree.tostring(
        rels, xml_declaration=True, encoding="UTF-8", standalone=True
    )

    # --- [Content_Types].xml -------------------------------------------------
    ct = etree.Element(f"{{{CT}}}Types", nsmap={None: CT})
    for ext, ct_val in [
        ("png", "image/png"),
        ("xml", "application/xml"),
        ("rels", "application/vnd.openxmlformats-package.relationships+xml"),
    ]:
        d = etree.SubElement(ct, f"{{{CT}}}Default")
        d.set("Extension", ext)
        d.set("ContentType", ct_val)
    ov = etree.SubElement(ct, f"{{{CT}}}Override")
    ov.set("PartName", "/word/document.xml")
    ov.set(
        "ContentType",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
    )
    ct_xml = etree.tostring(
        ct, xml_declaration=True, encoding="UTF-8", standalone=True
    )

    # --- _rels/.rels ---------------------------------------------------------
    root_rels = etree.Element(f"{{{REL}}}Relationships", nsmap={None: REL})
    rr = etree.SubElement(root_rels, f"{{{REL}}}Relationship")
    rr.set("Id", "rId1")
    rr.set(
        "Type",
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
    )
    rr.set("Target", "word/document.xml")
    root_rels_xml = etree.tostring(
        root_rels, xml_declaration=True, encoding="UTF-8", standalone=True
    )

    # --- Write ZIP -----------------------------------------------------------
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", ct_xml)
        zf.writestr("_rels/.rels", root_rels_xml)
        zf.writestr("word/_rels/document.xml.rels", rels_xml)
        zf.writestr("word/document.xml", doc_xml)
        zf.writestr("word/media/image1.png", _PNG_FLOAT_BYTES)
        zf.writestr("word/media/image2.png", _PNG_INLINE_BYTES)


def _build_floating_anchor() -> etree._Element:
    """Build a ``wp:anchor`` element matching the ORF injection contract."""
    anchor = etree.Element(
        f"{{{WP}}}anchor",
        attrib={
            "distT": "0",
            "distB": "0",
            "distL": "114300",
            "distR": "114300",
            "simplePos": "0",
            "relativeHeight": "251659264",
            "behindDoc": "0",
            "locked": "0",
            "layoutInCell": "1",
            "allowOverlap": "1",
        },
    )
    etree.SubElement(anchor, f"{{{WP}}}simplePos", x="0", y="0")
    pos_h = etree.SubElement(anchor, f"{{{WP}}}positionH", relativeFrom=FLOAT_REL_H)
    etree.SubElement(pos_h, f"{{{WP}}}posOffset").text = str(FLOAT_POS_H)
    pos_v = etree.SubElement(anchor, f"{{{WP}}}positionV", relativeFrom=FLOAT_REL_V)
    etree.SubElement(pos_v, f"{{{WP}}}posOffset").text = str(FLOAT_POS_V)
    etree.SubElement(anchor, f"{{{WP}}}extent", cx=str(IMAGE_CX), cy=str(IMAGE_CY))
    etree.SubElement(anchor, f"{{{WP}}}effectExtent", l="0", t="0", r="0", b="0")
    etree.SubElement(anchor, f"{{{WP}}}wrapNone")
    etree.SubElement(anchor, f"{{{WP}}}docPr", id="1", name="Floating")
    cngf = etree.SubElement(anchor, f"{{{WP}}}cNvGraphicFramePr")
    etree.SubElement(cngf, f"{{{A}}}graphicFrameLocks", noChangeAspect="1")
    graphic = etree.SubElement(anchor, f"{{{A}}}graphic")
    gd = etree.SubElement(
        graphic,
        f"{{{A}}}graphicData",
        uri="http://schemas.openxmlformats.org/drawingml/2006/picture",
    )
    pic = etree.SubElement(gd, f"{{{PIC}}}pic")
    nv = etree.SubElement(pic, f"{{{PIC}}}nvPicPr")
    etree.SubElement(nv, f"{{{PIC}}}cNvPr", id="1", name="image")
    etree.SubElement(nv, f"{{{PIC}}}cNvPicPr")
    blipFill = etree.SubElement(pic, f"{{{PIC}}}blipFill")
    etree.SubElement(
        blipFill,
        f"{{{A}}}blip",
        attrib={
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed": "rIdFloat",  # noqa: E501
        },
    )
    stretch = etree.SubElement(blipFill, f"{{{A}}}stretch")
    etree.SubElement(stretch, f"{{{A}}}fillRect")
    sppr = etree.SubElement(pic, f"{{{PIC}}}spPr")
    xfrm = etree.SubElement(sppr, f"{{{A}}}xfrm")
    etree.SubElement(xfrm, f"{{{A}}}off", x="0", y="0")
    etree.SubElement(xfrm, f"{{{A}}}ext", cx=str(IMAGE_CX), cy=str(IMAGE_CY))
    prst = etree.SubElement(sppr, f"{{{A}}}prstGeom", prst="rect")
    etree.SubElement(prst, f"{{{A}}}avLst")
    return anchor


def _build_inline() -> etree._Element:
    """Build a ``wp:inline`` element as a control image."""
    inline = etree.Element(
        f"{{{WP}}}inline",
        attrib={"distT": "0", "distB": "0", "distL": "0", "distR": "0"},
    )
    etree.SubElement(inline, f"{{{WP}}}extent", cx=str(IMAGE_CX), cy=str(IMAGE_CY))
    etree.SubElement(inline, f"{{{WP}}}effectExtent", l="0", t="0", r="0", b="0")
    etree.SubElement(inline, f"{{{WP}}}docPr", id="2", name="Inline")
    etree.SubElement(inline, f"{{{WP}}}cNvGraphicFramePr")
    graphic = etree.SubElement(inline, f"{{{A}}}graphic")
    gd = etree.SubElement(
        graphic,
        f"{{{A}}}graphicData",
        uri="http://schemas.openxmlformats.org/drawingml/2006/picture",
    )
    pic = etree.SubElement(gd, f"{{{PIC}}}pic")
    nv = etree.SubElement(pic, f"{{{PIC}}}nvPicPr")
    etree.SubElement(nv, f"{{{PIC}}}cNvPr", id="2", name="image")
    etree.SubElement(nv, f"{{{PIC}}}cNvPicPr")
    blipFill = etree.SubElement(pic, f"{{{PIC}}}blipFill")
    etree.SubElement(
        blipFill,
        f"{{{A}}}blip",
        attrib={
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed": "rIdInline",  # noqa: E501
        },
    )
    stretch = etree.SubElement(blipFill, f"{{{A}}}stretch")
    etree.SubElement(stretch, f"{{{A}}}fillRect")
    sppr = etree.SubElement(pic, f"{{{PIC}}}spPr")
    xfrm = etree.SubElement(sppr, f"{{{A}}}xfrm")
    etree.SubElement(xfrm, f"{{{A}}}off", x="0", y="0")
    etree.SubElement(xfrm, f"{{{A}}}ext", cx=str(IMAGE_CX), cy=str(IMAGE_CY))
    prst = etree.SubElement(sppr, f"{{{A}}}prstGeom", prst="rect")
    etree.SubElement(prst, f"{{{A}}}avLst")
    return inline


# ---------------------------------------------------------------------------
# Pipeline stage runners
# ---------------------------------------------------------------------------


def _run_opp(docx_path: Path, out_dir: Path) -> dict[str, Path]:
    """Stage 1: OPP extract DOCX → .xlf + .skeleton.zip + *_images.json."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "opp.cli",
        str(docx_path),
        "--target-format",
        "xlf",
        "--source-lang",
        "en",
        "--target-lang",
        "zh",
        "--output-dir",
        str(out_dir),
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, env=_build_env()
    )
    assert result.returncode == 0, (
        f"OPP extract failed (rc={result.returncode})\n"
        f"STDOUT:\n{result.stdout[-2000:]}\n"
        f"STDERR:\n{result.stderr[-2000:]}"
    )

    xlf = list(out_dir.glob("*.xlf"))
    skel = list(out_dir.glob("*.skeleton.zip"))
    img = [
        p
        for p in out_dir.iterdir()
        if p.name.endswith("_images.json") or p.name == "images.json"
    ]
    assert xlf, f"OPP did not produce .xlf in {out_dir}"
    assert skel, f"OPP did not produce .skeleton.zip in {out_dir}"
    assert img, f"OPP did not produce _images.json in {out_dir}"
    return {"xliff": xlf[0], "skeleton": skel[0], "images_json": img[0]}


def _run_ol(xliff_in: Path, out_dir: Path) -> Path:
    """Stage 2: OL translate XLIFF (FAKE_LLM — mock translation)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "ol_cli",
        "translate-xliff",
        str(xliff_in),
        "-c",
        str(OL_CONFIG),
        "-s",
        "en",
        "-t",
        "zh",
        "-o",
        str(out_dir),
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, env=_build_env(), timeout=120
    )
    assert result.returncode == 0, (
        f"OL translate-xliff failed (rc={result.returncode})\n"
        f"STDOUT (last 2000):\n{result.stdout[-2000:]}\n"
        f"STDERR (last 2000):\n{result.stderr[-2000:]}"
    )
    translated = out_dir / xliff_in.name
    assert translated.exists(), f"OL did not write output at {translated}"
    return translated


def _run_orf(
    skeleton: Path, translated_xliff: Path, images_json: Path, out_dir: Path
) -> Path:
    """Stage 3: ORF backfill translated XLIFF into final DOCX."""
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / "final.docx"
    cmd = [
        sys.executable,
        "-m",
        "orf.cli",
        "apply-xliff",
        str(skeleton),
        "--xliff",
        str(translated_xliff),
        "--images-json",
        str(images_json),
        "--output",
        str(output_path),
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, env=_build_env(), timeout=120
    )
    assert result.returncode == 0, (
        f"ORF apply-xliff failed (rc={result.returncode})\n"
        f"STDOUT (last 2000):\n{result.stdout[-2000:]}\n"
        f"STDERR (last 2000):\n{result.stderr[-2000:]}"
    )
    assert output_path.exists(), f"ORF did not produce {output_path}"
    return output_path


# ---------------------------------------------------------------------------
# Verification helpers
# ---------------------------------------------------------------------------


def _read_images_json(path: Path) -> list[dict]:
    """Parse an OPP ``*_images.json`` into a list of image entries."""
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("images", data if isinstance(data, list) else [])
    return raw


def _find_floating_in_images(images: list[dict]) -> dict | None:
    """Return the first image entry with ``is_floating: true``, or ``None``."""
    for img in images:
        if img.get("is_floating"):
            return img
    return None


def _find_inline_in_images(images: list[dict]) -> dict | None:
    """Return the first image entry without ``is_floating``, or ``None``."""
    for img in images:
        if not img.get("is_floating", False):
            return img
    return None


def _read_output_document_xml(docx_path: Path) -> etree._Element:
    """Read and parse ``word/document.xml`` from a DOCX."""
    with zipfile.ZipFile(docx_path, "r") as zf:
        xml_bytes = zf.read("word/document.xml")
    return etree.fromstring(xml_bytes)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestFloatingImageE2E:
    """Floating images (``wp:anchor``) survive the full OPP → OL → ORF pipeline."""

    def test_floating_image_survives_pipeline(self, tmp_path: Path) -> None:
        """Full end-to-end: create DOCX → OPP → OL → ORF → verify.

        Test flow:
        1. Create synthetic DOCX with one floating (wp:anchor) + one inline image
        2. OPP extract → verify images.json has ``is_floating: true``
        3. OL translate (FAKE_LLM) — verifies images survive translation
        4. ORF backfill → verify output DOCX has ``wp:anchor`` with correct position
        """
        # ------------------------------------------------------------------
        # 1. Create synthetic DOCX
        # ------------------------------------------------------------------
        docx_path = tmp_path / "source.docx"
        _create_docx_with_floating_image(docx_path)
        assert docx_path.exists(), "Synthetic DOCX was not created"
        assert docx_path.stat().st_size > 0, "Synthetic DOCX is empty"

        # ------------------------------------------------------------------
        # 2. OPP extraction
        # ------------------------------------------------------------------
        opp_out = tmp_path / "opp"
        opp_outputs = _run_opp(docx_path, opp_out)

        # Parse images.json
        images = _read_images_json(opp_outputs["images_json"])
        assert len(images) == 2, (
            f"Expected 2 images in images.json (1 floating + 1 inline), "
            f"got {len(images)} — content hash dedup may have collapsed them."
        )

        # Find floating image
        floating = _find_floating_in_images(images)
        assert floating is not None, (
            f"images.json has no entry with is_floating=true. "
            f"All entries: {json.dumps(images, indent=2)}"
        )
        # Verify floating image properties
        assert floating.get("paragraph_index") is None, (
            f"Floating image should have paragraph_index=null, "
            f"got {floating.get('paragraph_index')!r}"
        )
        assert floating.get("wp_anchor_h") == FLOAT_POS_H, (
            f"Floating wp_anchor_h: expected {FLOAT_POS_H}, "
            f"got {floating.get('wp_anchor_h')}"
        )
        assert floating.get("wp_anchor_v") == FLOAT_POS_V, (
            f"Floating wp_anchor_v: expected {FLOAT_POS_V}, "
            f"got {floating.get('wp_anchor_v')}"
        )

        # Find inline image control
        inline = _find_inline_in_images(images)
        assert inline is not None, "images.json has no inline (non-floating) entry"
        assert inline.get("paragraph_index") is not None, (
            "Inline image should have a paragraph_index, got None"
        )
        assert "is_floating" not in inline or inline["is_floating"] is False, (
            "Inline image should NOT have is_floating set to true"
        )

        # ------------------------------------------------------------------
        # 3. OL translation (FAKE_LLM — mock translation)
        # ------------------------------------------------------------------
        ol_out = tmp_path / "ol"
        _run_ol(opp_outputs["xliff"], ol_out)
        translated = ol_out / opp_outputs["xliff"].name
        assert translated.exists(), "Translated XLIFF was not created"

        # ------------------------------------------------------------------
        # 4. ORF backfill
        # ------------------------------------------------------------------
        orf_out = tmp_path / "orf"
        final_docx = _run_orf(
            opp_outputs["skeleton"],
            translated,
            opp_outputs["images_json"],
            orf_out,
        )

        # ------------------------------------------------------------------
        # 5. Verify output DOCX structure
        # ------------------------------------------------------------------
        root = _read_output_document_xml(final_docx)

        # Namespace map for XPath queries
        NSMAP = {
            "w": W,
            "wp": WP,
            "a": A,
            "pic": PIC,
            "r": R,
        }

        # Count wp:anchor elements.
        # The skeleton preserves the source DOCX's 2 drawings (1 floating anchor
        # in P2 + 1 inline in P3). ORF injects the floating image from
        # images.json into the FIRST paragraph (P1). The inline image is
        # deduped via cx/cy extent matching (E2E-07). So expected structure:
        #   P1: ORF-injected wp:anchor  (from images.json — correct position)
        #   P2: skeleton-preserved wp:anchor (original source position)
        #   P3: skeleton-preserved wp:inline
        anchors = root.xpath("//wp:anchor", namespaces=NSMAP)
        assert len(anchors) >= 1, (
            f"Expected at least 1 wp:anchor in output DOCX, "
            f"found {len(anchors)}"
        )

        injected_anchor = anchors[0]
        pos_h_off = injected_anchor.find(f"{{{WP}}}positionH/{{{WP}}}posOffset")
        pos_v_off = injected_anchor.find(f"{{{WP}}}positionV/{{{WP}}}posOffset")

        assert pos_h_off is not None, "Missing positionH/posOffset"
        assert pos_v_off is not None, "Missing positionV/posOffset"
        assert pos_h_off.text == str(FLOAT_POS_H), (
            f"positionH mismatch: expected {FLOAT_POS_H}, "
            f"got {pos_h_off.text}"
        )
        assert pos_v_off.text == str(FLOAT_POS_V), (
            f"positionV mismatch: expected {FLOAT_POS_V}, "
            f"got {pos_v_off.text}"
        )

        # Verify relativeFrom attributes on injected anchor
        pos_h = injected_anchor.find(f"{{{WP}}}positionH")
        pos_v = injected_anchor.find(f"{{{WP}}}positionV")
        assert pos_h.get("relativeFrom") == FLOAT_REL_H, (
            f"positionH@relativeFrom expected {FLOAT_REL_H}, "
            f"got {pos_h.get('relativeFrom')}"
        )
        assert pos_v.get("relativeFrom") == FLOAT_REL_V, (
            f"positionV@relativeFrom expected {FLOAT_REL_V}, "
            f"got {pos_v.get('relativeFrom')}"
        )

        # Verify the anchor has a blip with r:embed
        blip = injected_anchor.find(f".//{{{A}}}blip")
        assert blip is not None, "wp:anchor must contain a:blip"
        embed = blip.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
        )
        assert embed, "a:blip must have r:embed attribute"

        # Verify wp:inline elements also exist (the control inline image
        # preserved in the skeleton)
        inlines = root.xpath("//wp:inline", namespaces=NSMAP)
        assert len(inlines) >= 1, (
            f"Expected at least 1 wp:inline (control image), found {len(inlines)}"
        )

    def test_floating_image_json_fields(self, tmp_path: Path) -> None:
        """Verify OPP writes correct fields to images.json for floating images.

        This test only runs OPP extraction (no OL/ORF) to validate the
        OPP-side contract with fine-grained assertions.
        """
        docx_path = tmp_path / "source_fields.docx"
        _create_docx_with_floating_image(docx_path)
        opp_out = tmp_path / "opp_fields"
        opp_outputs = _run_opp(docx_path, opp_out)

        images = _read_images_json(opp_outputs["images_json"])
        assert len(images) == 2, f"Expected 2 images, got {len(images)}"

        # Floating image contract
        floating = _find_floating_in_images(images)
        assert floating is not None, "No floating image found"
        assert floating["is_floating"] is True
        assert floating["paragraph_index"] is None
        assert isinstance(floating["wp_anchor_h"], int)
        assert isinstance(floating["wp_anchor_v"], int)
        assert floating["wp_anchor_h"] == FLOAT_POS_H
        assert floating["wp_anchor_v"] == FLOAT_POS_V

        # Inline image contract
        inline = _find_inline_in_images(images)
        assert inline is not None, "No inline image found"
        assert not inline.get("is_floating", False)
        assert inline["paragraph_index"] is not None
        # Inline should not have anchor offset fields
        assert "wp_anchor_h" not in inline or inline["wp_anchor_h"] == 0
        assert "wp_anchor_v" not in inline or inline["wp_anchor_v"] == 0

    def test_floating_image_no_orphans(self, tmp_path: Path) -> None:
        """Floating images should NOT be orphaned by ORF backfill.

        This runs the full pipeline and checks that the ORF output
        has the correct number of drawings.
        """
        docx_path = tmp_path / "source_no_orphan.docx"
        _create_docx_with_floating_image(docx_path)
        opp_out = tmp_path / "opp_no_orphan"
        opp_outputs = _run_opp(docx_path, opp_out)

        ol_out = tmp_path / "ol_no_orphan"
        translated = _run_ol(opp_outputs["xliff"], ol_out)

        orf_out = tmp_path / "orf_no_orphan"
        final = _run_orf(
            opp_outputs["skeleton"],
            translated,
            opp_outputs["images_json"],
            orf_out,
        )

        root = _read_output_document_xml(final)
        NSMAP = {"w": W, "wp": WP, "a": A}
        drawings = root.xpath("//w:drawing", namespaces=NSMAP)
        # The skeleton preserves the source's 2 drawings (1 floating + 1
        # inline). ORF injects the floating image from images.json (inline
        # is deduped via cx/cy extent). So: 2 skeleton + 1 injected = 3.
        assert len(drawings) == 3, (
            f"Expected 3 drawings in final DOCX (2 skeleton + 1 injected), "
            f"found {len(drawings)}. ORF may have orphaned some images."
        )
