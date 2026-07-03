"""Test P3-T3 + P3-T4: CONTRACT.md exists, is well-formed, and is CI-covered.

P3-T3: Document the OPP→OL→ORF handoff contract in CONTRACT.md.
P3-T4: Ensure a CI workflow runs the contract tests.

These tests are the RED gate — they will FAIL until CONTRACT.md exists
and the CI workflow references it.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONTRACT = REPO_ROOT / "CONTRACT.md"


def test_contract_md_exists():
    """CONTRACT.md must exist at the repo root."""
    assert CONTRACT.exists(), (
        f"CONTRACT.md not found at {CONTRACT}. The OPP→OL→ORF handoff contract "
        f"is undocumented, leading to silent breakage."
    )


def test_contract_md_documents_three_stages():
    """CONTRACT.md must document all 3 pipeline stages."""
    content = CONTRACT.read_text(encoding="utf-8")
    assert "OPP" in content, "CONTRACT.md must mention OPP"
    assert "OL" in content or "Omni Localizer" in content, "CONTRACT.md must mention OL"
    assert "ORF" in content or "Omni Re-Formatter" in content, "CONTRACT.md must mention ORF"


def test_contract_md_documents_md_format():
    """CONTRACT.md must document the MD handoff format."""
    content = CONTRACT.read_text(encoding="utf-8")
    has_md_section = bool(re.search(r"(?i)(md|markdown).*(format|handoff|contract)", content))
    assert has_md_section, (
        "CONTRACT.md must document the MD handoff format (what OPP outputs → OL consumes)"
    )


def test_contract_md_documents_xliff_format():
    """CONTRACT.md must document the XLIFF handoff format."""
    content = CONTRACT.read_text(encoding="utf-8")
    has_xliff_section = bool(re.search(r"(?i)(xliff|xlf).*(format|handoff|contract)", content))
    assert has_xliff_section, "CONTRACT.md must document the XLIFF handoff format"


def test_contract_md_includes_json_schema():
    """CONTRACT.md should include or link to the JSON schema of TranslationDocument."""
    content = CONTRACT.read_text(encoding="utf-8")
    has_schema = (
        "format_type" in content
        or "TranslationDocument" in content
        or "model_json_schema" in content
        or "JSON Schema" in content
    )
    assert has_schema, (
        "CONTRACT.md should embed or reference the TranslationDocument JSON schema"
    )


def test_contract_md_versioned():
    """CONTRACT.md must declare a version (so changes are tracked)."""
    content = CONTRACT.read_text(encoding="utf-8")
    has_version = bool(re.search(r"(?i)\**version\**[:\s]+v?\d+\.\d+", content))
    assert has_version, "CONTRACT.md must declare a contract version (e.g., 'Version: 1.0')"


def test_ci_workflow_runs_contract_tests():
    """P3-T4: A CI workflow must run the contract tests."""
    workflow_dir = REPO_ROOT / ".github" / "workflows"
    assert workflow_dir.exists(), "No .github/workflows/ directory"
    found = False
    for wf in workflow_dir.iterdir():
        if not wf.name.endswith(".yml") and not wf.name.endswith(".yaml"):
            continue
        try:
            content = wf.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "contract" in content.lower() or "TranslationDocument" in content:
            found = True
            break
    assert found, (
        f"No CI workflow in {workflow_dir} references the contract tests. "
        f"Add 'pytest tests/test_contract_documentation.py -v' to a workflow."
    )
