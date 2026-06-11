"""Tests for SkeletonLoader.load_skeleton() with the real 14MB slim DOCX.

Verifies that the skeleton loader can correctly load and parse a production-scale
DOCX file with 7,681 paragraphs, measuring memory usage with tracemalloc.
"""

import tracemalloc
from pathlib import Path

import pytest
from lxml import etree

# Ensure ORF is on sys.path (same pattern as test_e2e_performance.py)
from conftest import setup_component_paths

setup_component_paths()

# Path to the real 14MB slim DOCX in the repo root
SLIM_DOCX_PATH = Path(__file__).parent.parent / "（slim）爱上海尔.docx"


@pytest.mark.slow
@pytest.mark.requires_orf
class TestSkeletonLoaderLargeFile:
    """Tests for SkeletonLoader.load_skeleton() with the real 14MB slim DOCX.

    Each test loads the skeleton from the large DOCX file and verifies
    different aspects: memory usage, paragraph count, and XML validity.
    """

    @pytest.mark.skipif(
        not hasattr(tracemalloc, "start"),
        reason="tracemalloc not available on this Python version",
    )
    def test_load_skeleton_memory(self):
        """Load skeleton from 14MB slim DOCX and measure memory usage.

        Asserts that word/document.xml is loaded (not None),
        the skeleton files dict contains the document, and peak
        memory stays under 200MB.
        """
        from orf.skeleton.skeleton_loader import SkeletonLoader

        if not SLIM_DOCX_PATH.exists():
            pytest.skip("（slim）爱上海尔.docx not found — place it in the repo root")

        loader = SkeletonLoader()
        tracemalloc.start()
        try:
            skeleton = loader.load_skeleton(str(SLIM_DOCX_PATH))
            current, peak = tracemalloc.get_traced_memory()

            # Core assertions
            assert skeleton is not None
            assert skeleton["xml"] is not None, "word/document.xml was not loaded"
            assert "word/document.xml" in skeleton["files"], (
                "word/document.xml not found in skeleton files"
            )
            assert peak < 200 * 1024 * 1024, (
                f"Peak memory {peak / 1024 / 1024:.1f}MB exceeds 200MB limit"
            )

            print(
                f"\n  Memory: current={current / 1024 / 1024:.1f}MB, "
                f"peak={peak / 1024 / 1024:.1f}MB"
            )
        finally:
            tracemalloc.stop()

    def test_find_paragraphs(self):
        """Load skeleton and verify the paragraph count.

        The slim Haier DOCX contains 8,608 <w:p> elements across the
        entire document tree (body, tables, headers, footers, text boxes).
        This pins the known count to detect regressions.
        """
        from orf.skeleton.skeleton_loader import SkeletonLoader

        if not SLIM_DOCX_PATH.exists():
            pytest.skip("（slim）爱上海尔.docx not found — place it in the repo root")

        loader = SkeletonLoader()
        skeleton = loader.load_skeleton(str(SLIM_DOCX_PATH))
        assert skeleton["xml"] is not None, "word/document.xml was not loaded"

        paragraphs = loader.find_paragraphs()
        assert len(paragraphs) == 8608, (
            f"Expected 8608 paragraphs, got {len(paragraphs)}"
        )
        print(f"  Found {len(paragraphs)} paragraphs")

    def test_document_xml_is_valid(self):
        """Verify that word/document.xml is valid XML parsable by lxml.

        Also confirms the root element tag ends with 'document' as
        expected for OOXML documents.
        """
        from orf.skeleton.skeleton_loader import SkeletonLoader

        if not SLIM_DOCX_PATH.exists():
            pytest.skip("（slim）爱上海尔.docx not found — place it in the repo root")

        loader = SkeletonLoader()
        skeleton = loader.load_skeleton(str(SLIM_DOCX_PATH))

        xml_bytes = skeleton["files"]["word/document.xml"]
        root = etree.fromstring(xml_bytes)
        assert root is not None
        assert root.tag.endswith("document"), (
            f"Root tag '{root.tag}' does not end with 'document'"
        )

    def test_all_key_skeleton_files_present(self):
        """Verify that all essential OOXML skeleton files are present.

        A valid skeleton should include at minimum the content types,
        relationships, and the main document parts.
        """
        from orf.skeleton.skeleton_loader import SkeletonLoader

        if not SLIM_DOCX_PATH.exists():
            pytest.skip("（slim）爱上海尔.docx not found — place it in the repo root")

        loader = SkeletonLoader()
        skeleton = loader.load_skeleton(str(SLIM_DOCX_PATH))

        required_prefixes = [
            "word/document.xml",
            "[Content_Types].xml",
            "word/_rels/",
            "_rels/",
        ]
        for prefix in required_prefixes:
            matching = [k for k in skeleton["files"] if k.startswith(prefix)]
            assert matching, f"No file matching prefix '{prefix}' found in skeleton"

        print(
            f"  Total files in skeleton: {len(skeleton['files'])}"
        )
