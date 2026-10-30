"""Tests for Phase 2 root-level env var documentation and references."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_env_example_documents_unified_var():
    """.env.example must document MCP_ALLOWED_DIRECTORIES as preferred."""
    content = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "MCP_ALLOWED_DIRECTORIES" in content, (
        ".env.example does not document MCP_ALLOWED_DIRECTORIES. "
        "This is the unified env var for OPP/OL/ORF MCP servers."
    )


def test_env_example_keeps_per_module_overrides():
    """.env.example should still document per-module vars as overrides."""
    content = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "OPP_MCP_ALLOWED_DIRS" in content, "Per-module override OPP_MCP_ALLOWED_DIRS missing"
    assert "ORF_MCP_ALLOWED_DIRS" in content, "Per-module override ORF_MCP_ALLOWED_DIRS missing"
    assert "OL_ALLOWED_DIRECTORIES" in content, "Per-module override OL_ALLOWED_DIRECTORIES missing"


def test_cursorrules_documents_unified_var():
    """.cursorrules is a thin pointer; env-var truth lives in its authority.

    Since the 2026-10-30 adapter convergence (.cursorrules / CLAUDE.md → thin
    pointers, claims kept only in gate-enforced sources), .cursorrules carries
    no env-var claims itself — it must point at AGENTS.md, which documents the
    unified var. This test pins the pointer contract, not a copied claim.
    """
    content = (REPO_ROOT / ".cursorrules").read_text(encoding="utf-8")
    assert "AGENTS.md" in content, (
        ".cursorrules must point at AGENTS.md as its authoritative context"
    )
    agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "MCP_ALLOWED_DIRECTORIES" in agents, (
        "AGENTS.md (the .cursorrules authority) does not document "
        "MCP_ALLOWED_DIRECTORIES"
    )


def test_skill_md_documents_unified_var():
    """SKILL.md must document MCP_ALLOWED_DIRECTORIES."""
    content = (REPO_ROOT / ".opencode" / "skills" / "omni-suite" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "MCP_ALLOWED_DIRECTORIES" in content, (
        "SKILL.md does not document MCP_ALLOWED_DIRECTORIES"
    )


def test_omni_suite_cli_has_unified_var():
    """omni_suite/cli.py must include MCP_ALLOWED_DIRECTORIES in _OPTIONAL_VARS."""
    content = (REPO_ROOT / "omni_suite" / "cli.py").read_text(encoding="utf-8")
    assert "MCP_ALLOWED_DIRECTORIES" in content, (
        "omni_suite/cli.py does not reference MCP_ALLOWED_DIRECTORIES"
    )


def test_omni_suite_cli_does_not_reference_nonexistent_ol_mcp_allowed_dirs():
    """omni_suite/cli.py must NOT reference the nonexistent OL_MCP_ALLOWED_DIRS."""
    content = (REPO_ROOT / "omni_suite" / "cli.py").read_text(encoding="utf-8")
    # Check that "OL_MCP_ALLOWED_DIRS" is not used as a real var name
    # (with the OL_ prefix, not OPP_/ORF_)
    lines_with_ol_mcp = [
        line
        for line in content.splitlines()
        if "OL_MCP_ALLOWED_DIRS" in line
        and "OPP_MCP" not in line
        and "ORF_MCP" not in line
    ]
    assert not lines_with_ol_mcp, (
        f"omni_suite/cli.py references nonexistent 'OL_MCP_ALLOWED_DIRS'. "
        f"The correct var name is 'OL_ALLOWED_DIRECTORIES'.\n"
        f"Lines: {lines_with_ol_mcp}"
    )
