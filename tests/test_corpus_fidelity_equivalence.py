"""TDD tests for corpus generator, fidelity checker, and equivalence checker.

Locks in:
- Corpus generator produces 5 valid complex documents
- Fidelity checker correctly measures text/table/image preservation
- Equivalence checker correctly identifies matching/divergent cells
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import corpus_generator  # noqa: E402
import equivalence_checker  # noqa: E402
import fidelity_checker  # noqa: E402


@pytest.fixture
def generated_docx(tmp_path) -> Path:
    """A real DOCX built by the shipped corpus generator, inside ``tmp_path``.

    The equivalence checker feeds each cell's ``sample``/``result`` to the
    fidelity checker, which parses DOCX as a real OOXML package. A text file
    merely named ``.docx`` raises ``docx.opc.exceptions.PackageNotFoundError``,
    so cells must hold a genuine generated document — never a committed binary.
    """
    dest = tmp_path / "generated_sample.docx"
    corpus_generator.generate_docx(dest)
    return dest


# ---------------------------------------------------------------------------
# Corpus generator
# ---------------------------------------------------------------------------

class TestCorpusGenerator:
    def test_corpus_dir_is_under_suite_root(self):
        assert corpus_generator.CORPUS_DIR.parent.name == "Omni_Suite"

    def test_png_bytes_returns_valid_png(self):
        import io

        from PIL import Image
        data = corpus_generator._png_bytes()
        img = Image.open(io.BytesIO(data))
        assert img.format == "PNG"
        assert img.size == (10, 10)

    def test_png_custom_dimensions(self):
        import io

        from PIL import Image
        data = corpus_generator._png_bytes(width=50, height=30, color="blue")
        img = Image.open(io.BytesIO(data))
        assert img.size == (50, 30)

    def test_generate_docx_creates_file(self, tmp_path):
        dest = tmp_path / "test.docx"
        corpus_generator.generate_docx(dest)
        assert dest.exists()
        assert dest.stat().st_size > 5000  # should be substantial

    def test_generate_pptx_creates_file(self, tmp_path):
        dest = tmp_path / "test.pptx"
        corpus_generator.generate_pptx(dest)
        assert dest.exists()
        assert dest.stat().st_size > 5000

    @pytest.mark.timeout(180)
    def test_generate_pdf_creates_file(self, tmp_path):
        pytest.importorskip(
            "weasyprint",
            reason="optional PDF engine (weasyprint) not installed",
        )
        dest = tmp_path / "test.pdf"
        corpus_generator.generate_pdf(dest)
        assert dest.exists()
        data = dest.read_bytes()
        assert data.startswith(b"%PDF-")
        assert data.rstrip().endswith(b"%%EOF")

    def test_generate_xlsx_creates_file(self, tmp_path):
        dest = tmp_path / "test.xlsx"
        corpus_generator.generate_xlsx(dest)
        assert dest.exists()
        assert dest.stat().st_size > 1000

    def test_generate_html_creates_file(self, tmp_path):
        dest = tmp_path / "test.html"
        corpus_generator.generate_html(dest)
        assert dest.exists()
        text = dest.read_text()
        assert "<h1>" in text
        assert "<table" in text
        assert "<img" in text

    def test_generate_all_is_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(corpus_generator, "CORPUS_DIR", tmp_path)
        first = corpus_generator.generate_all()
        assert len(first) == 5
        # Second call should generate nothing (files exist)
        second = corpus_generator.generate_all()
        assert second == []


# ---------------------------------------------------------------------------
# Fidelity checker
# ---------------------------------------------------------------------------

class TestFidelityChecker:
    def test_self_fidelity_is_perfect(self, tmp_path):
        src = tmp_path / "self.docx"
        corpus_generator.generate_docx(src)
        r = fidelity_checker.compute_fidelity(src, src, "docx")
        assert r.overall == 1.0
        assert r.text_score == 1.0
        assert r.passes()

    def test_missing_output_has_zero_overall(self, tmp_path):
        src = tmp_path / "src.docx"
        corpus_generator.generate_docx(src)
        r = fidelity_checker.compute_fidelity(src, tmp_path / "missing.docx", "docx")
        assert r.overall < 0.5
        assert not r.passes()
        assert "output file missing" in r.notes

    def test_extracts_text_from_docx(self, tmp_path):
        src = tmp_path / "src.docx"
        corpus_generator.generate_docx(src)
        text = fidelity_checker._extract_text(src)
        assert "Annual Report" in text
        assert "Executive Summary" in text
        assert "Financial Highlights" in text

    def test_extracts_text_from_html(self, tmp_path):
        src = tmp_path / "src.html"
        corpus_generator.generate_html(src)
        text = fidelity_checker._extract_text(src)
        assert "Product Catalog" in text
        assert "Smartphones" in text

    def test_extracts_text_from_xlsx(self, tmp_path):
        src = tmp_path / "src.xlsx"
        corpus_generator.generate_xlsx(src)
        text = fidelity_checker._extract_text(src)
        assert "Americas" in text
        assert "Widget" in text

    def test_counts_tables_in_docx(self, tmp_path):
        src = tmp_path / "src.docx"
        corpus_generator.generate_docx(src)
        count = fidelity_checker._count_tables(src)
        assert count == 2  # 2 tables in the complex docx

    def test_counts_images_in_docx(self, tmp_path):
        src = tmp_path / "src.docx"
        corpus_generator.generate_docx(src)
        count = fidelity_checker._count_images(src)
        assert count >= 1

    def test_to_dict_is_json_serializable(self, tmp_path):
        import json
        src = tmp_path / "src.docx"
        corpus_generator.generate_docx(src)
        r = fidelity_checker.compute_fidelity(src, src, "docx")
        d = r.to_dict()
        json.dumps(d)  # must not raise

    def test_normalize_text_strips_punctuation(self):
        words = fidelity_checker._normalize_text("Hello, world! Foo-bar.")
        assert "hello" in words
        assert "world" in words
        assert "foo" in words
        assert "bar" in words


# ---------------------------------------------------------------------------
# Equivalence checker
# ---------------------------------------------------------------------------

class TestEquivalenceChecker:
    def _make_run(self, base, cells_data, label="test", docx_src=None):
        """Create a run dir. Each entry is ``(inp, outp, path, has_result, content)``."""
        run_dir = base / f"run_{label}"
        cells_dir = run_dir / "cells"
        cells_dir.mkdir(parents=True)
        for inp, outp, path, has_result, content in cells_data:
            cell_dir = cells_dir / f"{path}_{inp}_to_{outp}"
            cell_dir.mkdir()
            if inp == "docx":
                assert docx_src is not None, "docx cells require the generated_docx fixture"
                shutil.copy(docx_src, cell_dir / f"sample.{inp}")
                if has_result:
                    shutil.copy(docx_src, cell_dir / f"result.{outp}")
            else:
                (cell_dir / f"sample.{inp}").write_text("source", encoding="utf-8")
                if has_result:
                    (cell_dir / f"result.{outp}").write_text(content, encoding="utf-8")
        return run_dir

    def test_identical_runs_are_equivalent(self, tmp_path, generated_docx):
        cells = [("docx", "docx", "md", True, None)]
        a = self._make_run(tmp_path, cells, label="a", docx_src=generated_docx)
        b = self._make_run(tmp_path, cells, label="b", docx_src=generated_docx)
        report = equivalence_checker.compare_runs(a, b)
        assert report.divergent == 0
        assert report.equivalent == 1

    def test_missing_in_a_is_divergent(self, tmp_path, generated_docx):
        a = self._make_run(
            tmp_path, [("docx", "docx", "md", False, None)],
            label="a", docx_src=generated_docx,
        )
        b = self._make_run(
            tmp_path, [("docx", "docx", "md", True, None)],
            label="b", docx_src=generated_docx,
        )
        report = equivalence_checker.compare_runs(a, b)
        assert report.missing_in_a == 1
        assert report.divergent == 1

    def test_missing_in_b_is_divergent(self, tmp_path, generated_docx):
        a = self._make_run(
            tmp_path, [("docx", "docx", "md", True, None)],
            label="a", docx_src=generated_docx,
        )
        b = self._make_run(
            tmp_path, [("docx", "docx", "md", False, None)],
            label="b", docx_src=generated_docx,
        )
        report = equivalence_checker.compare_runs(a, b)
        assert report.missing_in_b == 1
        assert report.divergent == 1

    def test_both_missing_is_not_divergent(self, tmp_path):
        a = self._make_run(tmp_path, [], label="a")
        b = self._make_run(tmp_path, [], label="b")
        report = equivalence_checker.compare_runs(a, b)
        assert report.divergent == 0
        assert report.equivalent == 0

    def test_size_difference_detected(self, tmp_path):
        a = self._make_run(
            tmp_path, [("md", "md", "md", True, "x" * 100)], label="a",
        )
        b = self._make_run(
            tmp_path, [("md", "md", "md", True, "x" * 1000)], label="b",
        )
        report = equivalence_checker.compare_runs(a, b, size_tolerance=0.05)
        assert report.divergent == 1

    def test_to_dict_is_json_serializable(self, tmp_path, generated_docx):
        import json
        cells = [("docx", "docx", "md", True, None)]
        a = self._make_run(tmp_path, cells, label="a", docx_src=generated_docx)
        b = self._make_run(tmp_path, cells, label="b", docx_src=generated_docx)
        report = equivalence_checker.compare_runs(a, b)
        d = report.to_dict()
        json.dumps(d)
