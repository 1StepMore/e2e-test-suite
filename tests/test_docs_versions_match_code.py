"""Verify that version tables in AGENTS.md and README.md match source code.

This test reads version numbers from:
  - AGENTS.md version table
  - README.md 环境说明 table
  - Each sub-repo's pyproject.toml (the source of truth)
  - The root VERSION file

It asserts that documented versions match the actual source versions.
"""

import re
import sys
from pathlib import Path

import pytest

# Project root
ROOT = Path(__file__).resolve().parent.parent

# Modules and their pyproject.toml paths
MODULE_PYPROJECT = {
    "OPP": ROOT / "Omni_Pre_Processor" / "pyproject.toml",
    "OL": ROOT / "Omni_Localizer" / "pyproject.toml",
    "ORF": ROOT / "Omni_Re_Formatter" / "pyproject.toml",
    "Omni_Suite": ROOT / "pyproject.toml",
}

# Table-row → component key mapping for AGENTS.md
AGENTS_TABLE_ROWS = {
    "Omni_Suite": "Omni_Suite",
    "OPP": "OPP",
    "OL": "OL",
    "ORF": "ORF",
}

# Table-row → component key mapping for README.md 环境说明
README_TABLE_ROWS = {
    "OPP": "OPP",
    "OL": "OL",
    "ORF": "ORF",
    "Omni_Suite": "Omni_Suite",
}


def _read_pyproject_version(pyproject_path: Path) -> str:
    """Extract version string from a pyproject.toml file."""
    text = pyproject_path.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise ValueError(f"Could not find version in {pyproject_path}")
    return m.group(1)


def _parse_agents_version_table(text: str) -> dict[str, str]:
    """Parse the AGENTS.md version table into {component: version}.

    Table format (markdown):
      | Component | Version | Status |
      |---|---|---|
      | Omni_Suite | v0.4.0 | ... |
      | OPP | v0.9.0 | ... |
    """
    versions: dict[str, str] = {}
    # Find the version table: starts with | Component | Version | Status |
    # then |---|---|---|, then data rows
    in_table = False
    for line in text.splitlines():
        if line.startswith("| Component | Version | Status |"):
            in_table = True
            continue
        if in_table and line.startswith("|---"):
            continue
        if in_table and line.startswith("| "):
            # End of table?
            if line.startswith("| `") or line.startswith("|**"):
                break
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4:
                component = parts[1]
                version = parts[2].lstrip("v")
                versions[component] = version
            # Check if next line is still a table row or end
        elif in_table and not line.startswith("|"):
            break
    return versions


def _parse_readme_version_table(text: str) -> dict[str, str]:
    """Parse the README.md 环境说明 table into {component: version}.

    Table format (markdown):
      | 组件 | 路径 | 版本 / SHA |
      |------|------|------|
      | OPP | `Omni_Pre_Processor/` | v0.6.6 |
    """
    versions: dict[str, str] = {}
    in_table = False
    for line in text.splitlines():
        if "| 组件 | 路径 | 版本 / SHA |" in line:
            in_table = True
            continue
        if in_table and line.startswith("|---"):
            continue
        if in_table and line.startswith("| "):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4:
                component = parts[1]
                version_cell = parts[3]
                # Remove leading v prefix
                version = version_cell.lstrip("v")
                versions[component] = version
        elif in_table and not line.startswith("|"):
            break
    return versions


# ── Tests ──────────────────────────────────────────────────────────


def test_agents_md_version_table():
    """AGENTS.md version table matches pyproject.toml versions."""
    agents_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    doc_versions = _parse_agents_version_table(agents_text)

    for component, row_key in AGENTS_TABLE_ROWS.items():
        doc_ver = doc_versions.get(row_key)
        assert doc_ver is not None, (
            f"Component '{row_key}' not found in AGENTS.md version table"
        )
        actual_ver = _read_pyproject_version(MODULE_PYPROJECT[component])
        assert doc_ver == actual_ver, (
            f"AGENTS.md lists {component} v{doc_ver} "
            f"but pyproject.toml has v{actual_ver}"
        )


def test_readme_version_table():
    """README.md 环境说明 version table matches pyproject.toml versions."""
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    doc_versions = _parse_readme_version_table(readme_text)

    for component, row_key in README_TABLE_ROWS.items():
        doc_ver = doc_versions.get(row_key)
        assert doc_ver is not None, (
            f"Component '{row_key}' not found in README.md version table"
        )
        actual_ver = _read_pyproject_version(MODULE_PYPROJECT[component])
        assert doc_ver == actual_ver, (
            f"README.md lists {component} v{doc_ver} "
            f"but pyproject.toml has v{actual_ver}"
        )


def test_agents_version_tagline():
    """AGENTS.md tagline (vX · vY · vZ) matches actual versions."""
    agents_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    doc_versions = _parse_agents_version_table(agents_text)

    # Build expected tagline pattern from pyproject toml
    suite_ver = _read_pyproject_version(MODULE_PYPROJECT["Omni_Suite"])
    opp_ver = _read_pyproject_version(MODULE_PYPROJECT["OPP"])
    ol_ver = _read_pyproject_version(MODULE_PYPROJECT["OL"])
    orf_ver = _read_pyproject_version(MODULE_PYPROJECT["ORF"])

    expected_tagline = f"v{opp_ver} · v{ol_ver} · v{orf_ver} · v{suite_ver}."

    # Find the tagline — it's the line right after the version table
    lines = agents_text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("v") and "·" in line and line.strip().endswith("."):
            actual_tagline = line.strip()
            assert actual_tagline == expected_tagline, (
                f"AGENTS.md tagline mismatch:\n"
                f"  Actual:   {actual_tagline}\n"
                f"  Expected: {expected_tagline}\n"
                f"  (from pyproject.toml: OPP v{opp_ver}, OL v{ol_ver}, "
                f"ORF v{orf_ver}, Suite v{suite_ver})"
            )
            return

    pytest.fail("Could not find version tagline in AGENTS.md")


def test_readme_version_tagline():
    """README.md version tagline matches actual versions."""
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    doc_versions = _parse_readme_version_table(readme_text)

    suite_ver = _read_pyproject_version(MODULE_PYPROJECT["Omni_Suite"])
    opp_ver = _read_pyproject_version(MODULE_PYPROJECT["OPP"])
    ol_ver = _read_pyproject_version(MODULE_PYPROJECT["OL"])
    orf_ver = _read_pyproject_version(MODULE_PYPROJECT["ORF"])

    expected_tagline = f"v{opp_ver} · v{ol_ver} · v{orf_ver} · v{suite_ver}"

    lines = readme_text.splitlines()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("v") and "·" in stripped:
            # Check if this looks like a version tagline (not a version table row)
            actual_tagline = stripped
            assert actual_tagline.startswith(expected_tagline.rstrip(".")) or \
                   actual_tagline == expected_tagline or \
                   actual_tagline == expected_tagline + "。", (
                f"README.md tagline mismatch:\n"
                f"  Actual:   {actual_tagline}\n"
                f"  Expected: {expected_tagline}\n"
            )
            return

    pytest.fail("Could not find version tagline in README.md")
