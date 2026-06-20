"""Throughput benchmarks for OL translation (FAKE_LLM mode).

Measures translation timing on sample markdown content using the CLI via subprocess.
Marked with @pytest.mark.benchmark — run with: pytest tests/benchmarks/ -m benchmark
"""

import os
import subprocess
import time
from pathlib import Path

import pytest


pytestmark = [
    pytest.mark.benchmark,
    pytest.mark.requires_ol,
]


OL_CLI = str(
    Path(__file__).resolve().parents[2] / "Omni_Localizer" / "src" / "ol_cli.py"
)


@pytest.fixture(scope="module", autouse=True)
def _fake_llm():
    """Enable FAKE_LLM for all tests in this module."""
    os.environ.setdefault("OMNI_TEST_FAKE_LLM", "1")


@pytest.fixture
def sample_md_path(tmp_path: Path) -> Path:
    """Create a sample markdown file for translation benchmarking."""
    content = """---
source_lang: en
target_lang: zh
---

# User Manual

## Introduction

This document describes the product features and usage instructions.

## Features

The product supports multiple output formats including DOCX, PDF, and HTML.

### Performance

- Fast extraction: processes documents in real-time
- High accuracy: preserves inline formatting
- Scalable: handles large documents efficiently

## Specifications

| Feature | Description |
|---------|-------------|
| Format  | DOCX, PPTX, PDF |
| Speed   | < 1s per page |
| Memory  | < 500MB peak |

## Support

For technical support, please contact the support team.
"""
    path = tmp_path / "sample.md"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def sample_md_large_path(tmp_path: Path) -> Path:
    """Create a larger markdown file for heavier translation benchmarking."""
    lines = ["# Large Document\n", "\n", "## Section 1\n", "\n"]
    for i in range(100):
        lines.append(f"Paragraph {i} with some content to translate. " * 5 + "\n")
    content = "".join(lines)
    path = tmp_path / "sample_large.md"
    path.write_text(content, encoding="utf-8")
    return path


def _run_ol_cli(input_path: Path, output_dir: Path, src: str = "en", tgt: str = "zh") -> float:
    """Run ol translate-md via subprocess and return elapsed seconds."""
    suite_root = Path(__file__).resolve().parents[2]
    ol_src = str(suite_root / "Omni_Localizer" / "src")
    ol_config = str(suite_root / "Omni_Localizer" / "config" / "slim-test.yaml")

    env = os.environ.copy()
    env["OMNI_TEST_FAKE_LLM"] = "1"
    env["OL_CONFIG_PATH"] = ol_config
    # Dummy API keys for config validation (FAKE_LLM ignores actual values)
    env.setdefault("OPENCODE_GO_KEY", "dummy-benchmark-key")
    env.setdefault("OPENCODE_GO_BASE_URL", "https://dummy.example.com")
    env.setdefault("BAIDU_API_KEY", "dummy-benchmark-key")
    env.setdefault("BAIDU_BASE_URL", "https://dummy.example.com")
    # Hide litellm telemetry
    env.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    env.setdefault("DISABLE_LITELLM_TELEMETRY", "True")

    pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{ol_src}:{pp}" if pp else ol_src

    start = time.perf_counter()
    result = subprocess.run(
        ["python", OL_CLI, "translate-md", str(input_path),
         "-s", src, "-t", tgt, "-o", str(output_dir)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(suite_root / "Omni_Localizer"),
        timeout=120,
    )
    elapsed = time.perf_counter() - start

    if result.returncode != 0:
        pytest.fail(f"OL CLI failed (rc={result.returncode}): {result.stderr[:500]}")

    return elapsed


class TestMDTranslationThroughput:
    """OL markdown translation timing benchmarks."""

    def test_translate_small_md(self, sample_md_path, tmp_path):
        """Time translation of a small markdown file (FAKE_LLM)."""
        output_dir = tmp_path / "ol_out"
        output_dir.mkdir(exist_ok=True)

        elapsed = _run_ol_cli(sample_md_path, output_dir)

        # Check output exists
        out_file = output_dir / sample_md_path.name
        assert out_file.exists(), f"Output not found: {out_file}"
        assert out_file.stat().st_size > 0

        print(f"\n  Translate small MD: {elapsed:.4f}s")
        assert elapsed < 60.0, f"Translation too slow: {elapsed:.2f}s"

    def test_translate_large_md(self, sample_md_large_path, tmp_path):
        """Time translation of a larger markdown file (FAKE_LLM)."""
        output_dir = tmp_path / "ol_out_large"
        output_dir.mkdir(exist_ok=True)

        elapsed = _run_ol_cli(sample_md_large_path, output_dir)

        out_file = output_dir / sample_md_large_path.name
        assert out_file.exists()
        assert out_file.stat().st_size > 0

        print(f"\n  Translate large MD: {elapsed:.4f}s")
        assert elapsed < 120.0, f"Translation too slow: {elapsed:.2f}s"

    def test_translate_consecutive_runs(self, sample_md_path, tmp_path):
        """Run translation 3 times and report min/avg/max."""
        timings = []
        for i in range(3):
            out_dir = tmp_path / f"run_{i}"
            out_dir.mkdir(exist_ok=True)
            elapsed = _run_ol_cli(sample_md_path, out_dir)
            timings.append(elapsed)

        avg = sum(timings) / len(timings)
        print(f"\n  Translate MD (3 runs): min={min(timings):.4f}s  avg={avg:.4f}s  max={max(timings):.4f}s")
        assert avg < 60.0, f"Average translation time {avg:.2f}s too high"
