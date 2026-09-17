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


# ---------------------------------------------------------------------------
# Suite ↔ Module in-process import surface (CONTRACT.md §"Suite ↔ Module
# In-Process Import Surface").  These two tests lock the doc and the code
# together: the doc cannot describe a surface that does not resolve, and a
# renamed registry cannot pass silently — it fails here, naming the contract.
# ---------------------------------------------------------------------------

#: (module label, dotted import path, expected shape kind) for every name the
#: suite imports from inside a module. Mirrors the CONTRACT.md table.
DECLARED_IMPORT_SURFACE = (
    ("OPP", "opp.mcp.server._TOOL_SCHEMAS", "list-of-dicts-with-name"),
    ("OL", "ol_mcp.tools.TOOL_REGISTRY", "mapping"),
    ("ORF", "orf.mcp.server._TOOL_DISPATCH", "mapping"),
    ("suite", "omni_mcp.server._TOOL_SCHEMAS", "list-of-dicts-with-name"),
    ("suite", "omni_mcp.server._TOOL_DISPATCH", "mapping"),
)


def _resolve(dotted: str):
    """Import and return the attribute named by *dotted* (``mod.attr``)."""
    import importlib

    module_path, _, attr = dotted.rpartition(".")
    module = importlib.import_module(module_path)
    return getattr(module, attr)


def test_contract_declares_in_process_import_surface():
    """The declared surface must be written down in CONTRACT.md.

    An undocumented load-bearing name is exactly the failure mode this section
    exists to prevent — the suite would break on a module refactor and nothing
    would tell the maintainer that the name was ever promised.
    """
    content = CONTRACT.read_text(encoding="utf-8")
    assert "Suite ↔ Module In-Process Import Surface" in content, (
        "CONTRACT.md lost its 'Suite ↔ Module In-Process Import Surface' section. "
        "The suite imports module registries in-process; that interface must stay "
        "documented (see this test file for the asserted list)."
    )
    missing = [dotted for _, dotted, _ in DECLARED_IMPORT_SURFACE if dotted not in content]
    assert not missing, (
        "CONTRACT.md no longer documents these load-bearing import paths: "
        f"{missing}. Add them back to the 'Suite ↔ Module In-Process Import "
        "Surface' table, or update DECLARED_IMPORT_SURFACE here if the interface "
        "genuinely changed."
    )


def test_declared_in_process_import_surface_resolves():
    """Every declared path must resolve, with the shape the contract promises.

    This is the loud half of the contract: a module that renames or moves one of
    these registries fails here with a message naming CONTRACT.md, instead of
    surfacing as a puzzling ImportError inside an unrelated coverage/doc test.
    """
    import os

    # ORF's MCP config is fail-CLOSED at import; the audit reads only the
    # registry, so any allowlist value is fine (mirrors coverage_audit.py).
    os.environ.setdefault("MCP_ALLOWED_DIRECTORIES", "/tmp")

    for label, dotted, shape in DECLARED_IMPORT_SURFACE:
        try:
            obj = _resolve(dotted)
        except Exception as exc:  # noqa: BLE001 - report the contract breach verbatim
            raise AssertionError(
                f"{label}: the suite cannot import {dotted} ({type(exc).__name__}: {exc}). "
                "That name is a declared interface — CONTRACT.md §'Suite ↔ Module "
                "In-Process Import Surface'. If the module renamed or moved it, update "
                "the suite (coverage_audit, dispatch, doc_inventory counters, the "
                "contract tests) and CONTRACT.md in the same change."
            ) from exc

        if shape == "list-of-dicts-with-name":
            assert isinstance(obj, list), f"{dotted} must be a list, got {type(obj).__name__}"
            assert obj, f"{dotted} is empty — an empty registry would make every coverage check vacuous"
            bad = [e for e in obj if not (isinstance(e, dict) and "name" in e)]
            assert not bad, (
                f"{dotted}: every entry must be a dict carrying a 'name' key; "
                f"offending entries: {bad[:3]}"
            )
            names = {e["name"] for e in obj}
        else:
            assert hasattr(obj, "keys"), (
                f"{dotted} must be a mapping (name -> entry), got {type(obj).__name__}"
            )
            names = set(obj.keys())

        assert names, f"{dotted} declares no tool names"
        assert all(isinstance(n, str) and n for n in names), (
            f"{dotted} has a non-string or empty tool name: {names!r}"
        )
