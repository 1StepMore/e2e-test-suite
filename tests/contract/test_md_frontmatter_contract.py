"""Issue #204 — the MD handoff contract must describe what the code does.

OPP emits Markdown with no YAML frontmatter; frontmatter is an OL output-side
product. These tests are the gate: if someone reverses that (makes OPP emit
frontmatter), the contract text and this test must be updated together.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from omni_suite.contract.models import DocumentFormat
from omni_suite.contract.validator import validate_md_output

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "CONTRACT.md"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"
SAMPLE_DOCX = REPO_ROOT / "tests" / "fixtures" / "sample.docx"


@pytest.fixture(scope="module")
def opp_md(tmp_path_factory) -> Path:
    pytest.importorskip("opp")
    out_dir = tmp_path_factory.mktemp("opp_md_contract")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "opp",
            "--target-format",
            "md",
            "--source-lang",
            "en",
            "--target-lang",
            "zh",
            "--output-dir",
            str(out_dir),
            str(SAMPLE_DOCX),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stderr[-800:]
    produced = list(out_dir.glob("*.md"))
    assert produced, f"OPP produced no .md in {out_dir}"
    return produced[0]


def test_opp_md_has_no_yaml_frontmatter(opp_md: Path):
    content = opp_md.read_text(encoding="utf-8")
    assert not content.startswith("---"), (
        "OPP started emitting YAML frontmatter. That is a contract change, not a "
        "refactor: update CONTRACT.md § MD Format Contract and this test, and fix "
        "OL's input-frontmatter handling first (issue #204)."
    )


def test_validator_reads_bare_md_as_md(opp_md: Path):
    doc = validate_md_output(opp_md, "en", "zh")

    assert doc is not None
    assert doc.format_type == DocumentFormat.MD


def test_contract_does_not_require_opp_frontmatter():
    text = CONTRACT.read_text(encoding="utf-8")

    assert "OPP MUST produce valid Markdown with YAML frontmatter" not in text
    assert "OPP MUST produce valid Markdown **without requiring** YAML frontmatter" in text


def test_architecture_doc_marks_opp_md_as_frontmatter_free():
    text = ARCHITECTURE.read_text(encoding="utf-8")

    assert "no** YAML frontmatter" in text
