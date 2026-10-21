"""Issue #204 — the MD handoff contract must describe what the code does.

OPP emits Markdown with no YAML frontmatter; frontmatter is an OL output-side
product. These tests are the gate: if someone reverses that (makes OPP emit
frontmatter), the contract text and this test must be updated together.

The artifact is produced by the serializer that actually writes the OPP->OL
handoff (``MarkdownGenerator``), not by spawning the CLI: the property is about
the serialized shape, and a subprocess test would couple it to the runner's
PATH/venv layout for no gain.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from omni_suite.contract.models import DocumentFormat
from omni_suite.contract.validator import validate_md_output

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "CONTRACT.md"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"


@pytest.fixture(scope="module")
def opp_md(tmp_path_factory) -> Path:
    pytest.importorskip("opp")
    from opp.markdown.generator import MarkdownGenerator
    from opp.utils.dataclasses import ExtractionResult, ParagraphData

    output = tmp_path_factory.mktemp("opp_md_contract") / "sample.md"
    result = ExtractionResult(
        paragraphs=[
            ParagraphData(text="Hello World", style="Heading 1"),
            ParagraphData(text="This is a translatable paragraph.", position=1),
        ],
        tables=[],
        images=[],
    )
    MarkdownGenerator().generate_to_file(result, output)
    return output


def test_opp_md_has_no_yaml_frontmatter(opp_md: Path):
    content = opp_md.read_text(encoding="utf-8")

    assert content.strip()
    assert not content.startswith("---"), (
        "OPP started emitting YAML frontmatter. That is a contract change, not a "
        "refactor: update CONTRACT.md MD Format Contract and this test, and fix "
        "OL's input-frontmatter handling first (issue #204, Omni_Localizer#146)."
    )


def test_validator_reads_bare_md_as_md(opp_md: Path):
    doc = validate_md_output(opp_md, "en", "zh")

    assert doc is not None
    assert doc.format_type == DocumentFormat.MD
    assert doc.segments


def test_contract_does_not_require_opp_frontmatter():
    text = CONTRACT.read_text(encoding="utf-8")

    assert "OPP MUST produce valid Markdown with YAML frontmatter" not in text
    assert (
        "OPP MUST produce valid Markdown **without requiring** YAML frontmatter"
        in text
    )


def test_architecture_doc_marks_opp_md_as_frontmatter_free():
    text = ARCHITECTURE.read_text(encoding="utf-8")

    assert "no** YAML frontmatter" in text
