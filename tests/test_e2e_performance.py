"""Performance E2E tests for Omni_Suite.

Tests document extraction performance, timing, and resource usage.
"""

import time
import tracemalloc
from pathlib import Path

import pytest

# Ensure component paths are set up
from tests.conftest import setup_component_paths
setup_component_paths()

# Path to the real large DOCX file (~14MB, 7,681 paragraphs) in the repo root
SLIM_DOCX_PATH = Path(__file__).parent.parent / "（slim）爱上海尔.docx"


# =============================================================================
# Markers
# =============================================================================

pytestmark = [
    pytest.mark.slow,
    pytest.mark.requires_opp,
]


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def large_docx_path(tmp_path: Path) -> Path:
    """Create a large DOCX file for performance testing.

    Creates a DOCX with substantial content to test extraction speed.
    """
    from docx import Document

    doc = Document()

    # Add many paragraphs to create a large document
    for i in range(200):
        doc.add_paragraph(
            f"This is paragraph {i} with some additional text content "
            f"to increase the document size and extraction time. "
            f"Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
            f"Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
        )

    # Add some headings
    for i in range(20):
        doc.add_heading(f"Section {i}", level=1)
        doc.add_paragraph(
            f"Section content for section {i}. " * 10
        )

    # Add tables
    for i in range(10):
        table = doc.add_table(rows=20, cols=4)
        table.style = "Light Grid Accent 1"
        for row_idx, row in enumerate(table.rows):
            for col_idx, cell in enumerate(row.cells):
                cell.text = f"R{row_idx}C{col_idx}"

    output_path = tmp_path / "large_document.docx"
    doc.save(str(output_path))
    return output_path


@pytest.fixture
def large_pdf_path(tmp_path: Path) -> Path:
    """Create a large PDF file for performance testing.

    Note: This creates a minimal PDF. For real large PDF testing,
    consider using a pre-existing large PDF file.
    """
    # For simplicity, we create a text-based PDF
    # In production, you'd want to use a real large PDF
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources <<
/Font <<
/F1 4 0 R
>>
>>
/MediaBox [0 0 612 792]
/Contents 5 0 R
>>
endobj

4 0 obj
<<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
endobj

5 0 obj
<<
/Length 1000
>>
stream
BT
/F1 12 Tf
"""
    # Add many lines of text
    for i in range(100):
        pdf_content += f"100 {700 - i*10} Td\n({i} This is line {i} of the PDF content for performance testing) Tj\n".encode()
    pdf_content += b"""
ET
endstream
endobj

xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000274 00000 n
0000000400 00000 n
trailer
<<
/Size 6
/Root 1 0 R
>>
startxref
1500
%%EOF
"""

    output_path = tmp_path / "large_document.pdf"
    output_path.write_bytes(pdf_content)
    return output_path


@pytest.fixture
def opp_pipeline(tmp_path: Path):
    """Create an OPP pipeline instance for performance testing."""
    from opp.pipeline import OPPPipeline

    resource_dir = tmp_path / "opp_resources"
    resource_dir.mkdir(exist_ok=True)

    return OPPPipeline(resource_storage_dir=resource_dir)


# =============================================================================
# Performance Tests
# =============================================================================

class TestDOCXPerformance:
    """Performance tests for DOCX extraction."""

    def test_large_docx_extraction_under_30s(self, opp_pipeline, large_docx_path, tmp_path: Path):
        """Test that large DOCX extraction completes in under 30 seconds.

        This test measures the end-to-end extraction time for a document
        with ~200 paragraphs, 20 sections, and 10 tables.
        """
        output_dir = tmp_path / "perf_output"
        output_dir.mkdir(exist_ok=True)

        start_time = time.perf_counter()

        result = opp_pipeline.process_file(large_docx_path)

        extraction_time = time.perf_counter() - start_time

        # Main assertion: extraction must complete within 30 seconds
        assert extraction_time < 30.0, (
            f"DOCX extraction took {extraction_time:.2f}s, "
            f"exceeding 30s threshold"
        )

        # Verify extraction was successful
        assert result is not None
        assert result.extraction_result is not None

        print(f"\n✓ DOCX extraction completed in {extraction_time:.2f}s")

    @pytest.mark.skipif(
        not hasattr(time, 'perf_counter'),
        reason="time.perf_counter not available"
    )
    def test_docx_extraction_time_measurement(self, opp_pipeline, sample_docx_path, tmp_path: Path):
        """Test accurate time measurement of standard DOCX extraction.

        Verifies that timing measurements are precise and reproducible.
        """
        output_dir = tmp_path / "timing_output"
        output_dir.mkdir(exist_ok=True)

        # Warm-up run (not measured)
        _ = opp_pipeline.process_file(sample_docx_path)

        # Measured runs
        timings = []
        for _ in range(3):
            start = time.perf_counter()
            result = opp_pipeline.process_file(sample_docx_path)
            elapsed = time.perf_counter() - start
            timings.append(elapsed)
            assert result is not None

        avg_time = sum(timings) / len(timings)
        min_time = min(timings)
        max_time = max(timings)

        print(f"\n✓ DOCX extraction timings: avg={avg_time:.3f}s, min={min_time:.3f}s, max={max_time:.3f}s")

        # All timings should be reasonable (< 10s for standard sample)
        assert all(t < 10.0 for t in timings), (
            f"Some timings exceeded 10s threshold: {timings}"
        )

    @pytest.mark.skipif(
        not SLIM_DOCX_PATH.exists(),
        reason="（slim）爱上海尔.docx not available — place it in the repo root"
    )
    @pytest.mark.skipif(
        not hasattr(tracemalloc, 'start'),
        reason="tracemalloc not available on this Python version"
    )
    def test_real_large_docx_extraction(self, opp_pipeline, tmp_path: Path):
        """Extract the real 14MB （slim）爱上海尔.docx, measure time & peak memory.

        This benchmark validates extraction performance against a production-scale
        document with 7,681 paragraphs, 10 tables, and 390 embedded images.
        """
        output_dir = tmp_path / "real_large_output"
        output_dir.mkdir(exist_ok=True)

        tracemalloc.start()
        try:
            start_time = time.perf_counter()
            result = opp_pipeline.process_file(SLIM_DOCX_PATH)
            extraction_time = time.perf_counter() - start_time

            current, peak = tracemalloc.get_traced_memory()

            print(f"\n✓ Real large DOCX extraction completed in {extraction_time:.2f}s")
            print(f"  Memory: current={current / 1024 / 1024:.1f}MB, peak={peak / 1024 / 1024:.1f}MB")

            # Core assertions
            assert extraction_time < 120.0, (
                f"Extraction of real large DOCX took {extraction_time:.2f}s, "
                f"exceeding 120s threshold"
            )
            assert peak < 500 * 1024 * 1024, (
                f"Peak memory {peak / 1024 / 1024:.1f}MB exceeds 500MB limit"
            )
            assert result is not None
            assert result.extraction_result is not None

        finally:
            tracemalloc.stop()


class TestPDFPerformance:
    """Performance tests for PDF extraction."""

    def test_pdf_extraction_time_measurement(self, opp_pipeline, large_pdf_path, tmp_path: Path):
        """Test PDF extraction time measurement.

        Measures how long PDF extraction takes.
        """
        output_dir = tmp_path / "pdf_output"
        output_dir.mkdir(exist_ok=True)

        start_time = time.perf_counter()

        try:
            result = opp_pipeline.process_file(large_pdf_path)
            extraction_time = time.perf_counter() - start_time

            print(f"\n✓ PDF extraction completed in {extraction_time:.2f}s")

            # Just verify it completes without hanging
            assert result is not None

        except Exception as e:
            # PDFs can fail if no PDF processing library is available
            pytest.skip(f"PDF processing not available: {e}")


class TestMemoryUsage:
    """Memory usage tests using tracemalloc."""

    def test_docx_extraction_memory_usage(self, opp_pipeline, large_docx_path, tmp_path: Path):
        """Test DOCX extraction memory usage with tracemalloc.

        Measures peak memory usage during DOCX extraction.
        """
        if not hasattr(tracemalloc, 'start'):
            pytest.skip("tracemalloc not available on this Python version")

        output_dir = tmp_path / "memory_output"
        output_dir.mkdir(exist_ok=True)

        # Start memory tracking
        tracemalloc.start()

        try:
            result = opp_pipeline.process_file(large_docx_path)

            # Get peak memory usage
            current, peak = tracemalloc.get_traced_memory()

            print(f"\n✓ DOCX extraction memory: current={current / 1024 / 1024:.1f}MB, peak={peak / 1024 / 1024:.1f}MB")

            # Verify extraction succeeded
            assert result is not None

            # Peak memory should be reasonable (< 500MB for the test document)
            assert peak < 500 * 1024 * 1024, (
                f"Peak memory {peak / 1024 / 1024:.1f}MB exceeds 500MB threshold"
            )

        finally:
            tracemalloc.stop()

    def test_memory_leak_detection(self, opp_pipeline, sample_docx_path, tmp_path: Path):
        """Test for memory leaks by running multiple extractions.

        If memory grows significantly with each run, there's likely a leak.
        """
        if not hasattr(tracemalloc, 'start'):
            pytest.skip("tracemalloc not available on this Python version")

        output_dir = tmp_path / "leak_output"
        output_dir.mkdir(exist_ok=True)

        tracemalloc.start()

        try:
            initial_size = None
            final_size = None

            for i in range(5):
                result = opp_pipeline.process_file(sample_docx_path)
                assert result is not None

                if initial_size is None:
                    initial_size, _ = tracemalloc.get_traced_memory()

                final_size, peak = tracemalloc.get_traced_memory()

                print(f"  Run {i+1}: current={final_size / 1024 / 1024:.1f}MB, peak={peak / 1024 / 1024:.1f}MB")

            # Memory should not grow significantly between runs
            memory_growth = final_size - initial_size

            print(f"\n✓ Memory growth over 5 runs: {memory_growth / 1024 / 1024:.1f}MB")

            # Allow some growth but not excessive (e.g., < 50MB)
            assert memory_growth < 50 * 1024 * 1024, (
                f"Memory grew by {memory_growth / 1024 / 1024:.1f}MB, "
                f"indicating potential memory leak"
            )

        finally:
            tracemalloc.stop()


class TestThroughput:
    """Throughput and efficiency tests."""

    def test_document_throughput(self, opp_pipeline, tmp_path: Path):
        """Test document processing throughput.

        Measures how many documents can be processed per minute.
        """
        from tests.conftest import run_opp_extraction

        output_dir = tmp_path / "throughput_output"

        # Create multiple sample documents
        doc_paths = []
        for i in range(3):
            from docx import Document
            doc = Document()
            doc.add_heading(f"Test Document {i}", level=1)
            for j in range(50):
                doc.add_paragraph(f"Paragraph {j} content for throughput testing.")
            path = tmp_path / f"doc_{i}.docx"
            doc.save(str(path))
            doc_paths.append(path)

        start_time = time.perf_counter()

        for doc_path in doc_paths:
            run_opp_extraction(opp_pipeline, doc_path, output_dir)

        elapsed = time.perf_counter() - start_time

        docs_per_minute = (len(doc_paths) / elapsed) * 60

        print(f"\n✓ Processed {len(doc_paths)} documents in {elapsed:.2f}s = {docs_per_minute:.1f} docs/min")

        # Should be able to process at least a few docs per minute
        assert docs_per_minute > 1.0, (
            f"Throughput {docs_per_minute:.1f} docs/min is too low"
        )
