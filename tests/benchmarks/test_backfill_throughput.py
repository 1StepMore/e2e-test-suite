"""Throughput benchmarks for ORF backfill.

Measures backfill timing from markdown to target formats via CLI subprocess.
Marked with @pytest.mark.benchmark — run with: pytest tests/benchmarks/ -m benchmark
"""

import os
import subprocess
import time
from pathlib import Path

import pytest


pytestmark = [
    pytest.mark.benchmark,
    pytest.mark.requires_orf,
]


@pytest.fixture(scope="module", autouse=True)
def _fake_pandoc():
    """Allow tests without real pandoc."""
    os.environ.setdefault("OMNI_TEST_FAKE_PANDOC", "1")


@pytest.fixture
def sample_md_path(tmp_path: Path) -> Path:
    """Create a sample markdown file for backfill benchmarking."""
    content = """---
source_lang: en
target_lang: zh
---

# User Manual

## Introduction

This document describes the product features and usage instructions.

## Features

The product supports multiple output formats including DOCX, PDF, and HTML.
"""
    path = tmp_path / "sample.md"
    path.write_text(content, encoding="utf-8")
    return path


def _run_orf_cli(input_path: Path, output_path: Path, target_format: str) -> float:
    """Run orf apply-md via subprocess and return elapsed seconds.
    
    Uses ``python -m orf.cli`` to avoid the ``orf/logging/`` module shadowing
    the stdlib ``logging`` package when running the script file directly.
    """
    suite_root = Path(__file__).resolve().parents[2]
    orf_src = str(suite_root / "Omni_Re_Formatter" / "src")

    env = os.environ.copy()
    env["OMNI_TEST_FAKE_PANDOC"] = "1"
    env.setdefault("DISABLE_LITELLM_TELEMETRY", "True")

    pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{orf_src}:{pp}" if pp else orf_src

    start = time.perf_counter()
    result = subprocess.run(
        ["python", "-m", "orf.cli", "apply-md", str(input_path),
         "--target-format", target_format, "--output", str(output_path)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(suite_root / "Omni_Re_Formatter"),
        timeout=120,
    )
    elapsed = time.perf_counter() - start

    if result.returncode != 0:
        pytest.fail(f"ORF CLI failed (rc={result.returncode}): {result.stderr[:500]}")

    return elapsed


class TestMDBackfillThroughput:
    """ORF apply-md timing benchmarks."""

    def test_md_to_docx(self, sample_md_path, tmp_path):
        """Time backfill from MD to DOCX."""
        output_path = tmp_path / "output.docx"

        elapsed = _run_orf_cli(sample_md_path, output_path, "docx")

        assert output_path.exists(), "DOCX output not created"
        assert output_path.stat().st_size > 0

        print(f"\n  MD→DOCX backfill: {elapsed:.4f}s")
        assert elapsed < 30.0, f"MD→DOCX backfill too slow: {elapsed:.2f}s"

    def test_md_to_html(self, sample_md_path, tmp_path):
        """Time backfill from MD to HTML."""
        output_path = tmp_path / "output.html"

        elapsed = _run_orf_cli(sample_md_path, output_path, "html")

        assert output_path.exists(), "HTML output not created"
        assert output_path.stat().st_size > 0

        print(f"\n  MD→HTML backfill: {elapsed:.4f}s")
        assert elapsed < 30.0, f"MD→HTML backfill too slow: {elapsed:.2f}s"

    def test_md_backfill_consecutive_runs(self, sample_md_path, tmp_path):
        """Run MD→DOCX backfill 3 times and report min/avg/max."""
        timings = []
        for i in range(3):
            out = tmp_path / f"output_{i}.docx"
            elapsed = _run_orf_cli(sample_md_path, out, "docx")
            timings.append(elapsed)

        avg = sum(timings) / len(timings)
        print(f"\n  MD→DOCX (3 runs): min={min(timings):.4f}s  avg={avg:.4f}s  max={max(timings):.4f}s")
        assert avg < 30.0, f"Average backfill time {avg:.2f}s too high"
