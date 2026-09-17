"""Tests verifying image fidelity between OPP source and ORF output.

Empirically verified (2026-06-14, post-TURNKEY-IMG-01):
    - Source DOCX:  11 <w:drawing> blocks (12 via lenient regex)
    - ORF output:   11 <w:drawing> blocks (12 via lenient regex) — MATCH

Bug history:
    2026-06-14: Found ORF was re-injecting 2 inline duplicates of the
    first 2 source images (IM 16, 组合 116). Root cause was a missing
    dedup in the inline-image path. Fixed at
    `Omni_Re_Formatter/src/orf/channels/xliff2docx.py:1326-1366` via
    `_paragraph_already_has_drawing()` helper. The dedup must be
    document-wide (not paragraph-local) because OPP's paragraph_index
    is off-by-one vs. ORF's `//w:p` enumeration (Haier DOCX: OPP
    says 6, skeleton places IM 16 at paragraph 7).
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pytest

# =============================================================================
# Fixture paths
# =============================================================================

SOURCE = (
    Path(__file__).resolve().parents[2]
    / "scenarios" / "_fixtures" / "haier_ch2_zh.docx"
)
ORF_OUTPUT = Path("/tmp/turnkey_image_check/orf/output.docx")


# =============================================================================
# Helpers
# =============================================================================


def _count_drawings(docx_path: Path) -> int:
    """Count ``<w:drawing>`` elements inside ``word/document.xml``.

    Uses a simple regex count on the raw XML text — fast and avoids
    pulling in an XML parser just for one tag.
    """
    with zipfile.ZipFile(str(docx_path), "r") as zf:
        xml_content = zf.read("word/document.xml").decode("utf-8")
    return len(re.findall(r"<w:drawing[>\s]", xml_content))


def _count_media_files(docx_path: Path) -> int:
    """Count entries inside ``word/media/`` in the DOCX archive."""
    with zipfile.ZipFile(str(docx_path), "r") as zf:
        return sum(1 for name in zf.namelist() if name.startswith("word/media/"))


# =============================================================================
# Skip-if guards
# =============================================================================

skipif_no_source = pytest.mark.skipif(
    not SOURCE.exists(),
    reason=f"Source fixture not found: {SOURCE}",
)

skipif_no_output = pytest.mark.skipif(
    not ORF_OUTPUT.exists(),
    reason=f"ORF output fixture not found: {ORF_OUTPUT}",
)


# =============================================================================
# Tests
# =============================================================================


class TestImageFidelity:
    """Image drawing count and media file count match between source and ORF output."""

    # ------------------------------------------------------------------
    # Drawing count
    # ------------------------------------------------------------------

    @skipif_no_source
    @skipif_no_output
    def test_drawing_count_equals_source(self) -> None:
        """``<w:drawing>`` count in ORF output matches the source DOCX.

        Source 12 (lenient regex) / 11 (block count), output 12 / 11.
        Regression test for TURNKEY-IMG-01 (ORF inline image dedup fix).
        """
        src_count = _count_drawings(SOURCE)
        out_count = _count_drawings(ORF_OUTPUT)
        assert src_count == out_count, (
            f"<w:drawing> count mismatch: "
            f"source has {src_count}, output has {out_count}"
        )

    # ------------------------------------------------------------------
    # Media file count
    # ------------------------------------------------------------------

    @skipif_no_source
    @skipif_no_output
    def test_media_file_count_equals_source(self) -> None:
        """``word/media/`` file count in ORF output matches the source DOCX."""
        src_count = _count_media_files(SOURCE)
        out_count = _count_media_files(ORF_OUTPUT)
        assert src_count == out_count, (
            f"word/media/ file count mismatch: "
            f"source has {src_count}, output has {out_count}"
        )
