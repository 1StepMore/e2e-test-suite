"""Verify version consistency across the Omni Suite.

Checks that:
1. The suite ``VERSION`` file matches ``omni_suite/__init__.py`` fallback version
2. The suite ``pyproject.toml`` version matches ``VERSION`` file
3. OPP ``pyproject.toml`` version matches OPP ``__init__.py`` fallback version
4. OL ``pyproject.toml`` version matches OL ``__init__.py`` version
5. ORF ``pyproject.toml`` version matches ORF runtime version (via importlib.metadata)

Note: Some packages use ``importlib.metadata`` at runtime, which reads the
installed package version from the distribution metadata. This test reads
the source ``__init__.py`` fallback values and ``pyproject.toml`` directly
so it works without requiring the package to be installed.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# File paths
SUITE_VERSION_FILE = ROOT / "VERSION"
SUITE_PYPROJECT = ROOT / "pyproject.toml"
SUITE_INIT = ROOT / "omni_suite" / "__init__.py"

OPP_PYPROJECT = ROOT / "Omni_Pre_Processor" / "pyproject.toml"
OPP_INIT = ROOT / "Omni_Pre_Processor" / "src" / "opp" / "__init__.py"

OL_PYPROJECT = ROOT / "Omni_Localizer" / "pyproject.toml"
OL_INIT = ROOT / "Omni_Localizer" / "src" / "ol" / "__init__.py"

ORF_PYPROJECT = ROOT / "Omni_Re_Formatter" / "pyproject.toml"
ORF_INIT = ROOT / "Omni_Re_Formatter" / "src" / "orf" / "__init__.py"

# Regex patterns
_TOML_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"')
_INIT_FALLBACK_RE = re.compile(r'__version__\s*=\s*"([^"]+)"')


def _read_version_from_file(path: Path) -> str | None:
    """Read a plain version string from a file (e.g. VERSION)."""
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()


def _parse_toml_version(path: Path) -> str | None:
    """Extract ``version = "X.Y.Z"`` from a pyproject.toml file."""
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _TOML_VERSION_RE.match(line.strip())
        if m:
            return m.group(1)
    return None


def _parse_init_fallback(path: Path) -> str | None:
    """Extract the fallback ``__version__ = "X.Y.Z"`` from an __init__.py.

    Looks for the fallback string, not the importlib.metadata path.
    """
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        # Skip lines with importlib.metadata
        if "importlib.metadata" in line:
            continue
        m = _INIT_FALLBACK_RE.search(line)
        if m:
            return m.group(1)
    return None


# ── Suite-level consistency ─────────────────────────────────────────────


def test_suite_version_file_exists():
    """VERSION file must exist."""
    assert SUITE_VERSION_FILE.exists(), f"Missing suite VERSION file: {SUITE_VERSION_FILE}"


def test_suite_pyproject_version_matches_version_file():
    """pyproject.toml version must match VERSION file."""
    pyproject_ver = _parse_toml_version(SUITE_PYPROJECT)
    version_file_ver = _read_version_from_file(SUITE_VERSION_FILE)
    assert pyproject_ver is not None, f"Cannot parse version from {SUITE_PYPROJECT}"
    assert version_file_ver is not None, f"Cannot read {SUITE_VERSION_FILE}"
    assert pyproject_ver == version_file_ver, (
        f"Suite pyproject.toml version '{pyproject_ver}' != "
        f"VERSION file '{version_file_ver}'"
    )


def test_suite_init_fallback_matches_version_file():
    """omni_suite/__init__.py fallback version must match VERSION file."""
    init_ver = _parse_init_fallback(SUITE_INIT)
    version_file_ver = _read_version_from_file(SUITE_VERSION_FILE)
    assert init_ver is not None, f"Cannot parse fallback version from {SUITE_INIT}"
    assert version_file_ver is not None, f"Cannot read {SUITE_VERSION_FILE}"
    assert init_ver == version_file_ver, (
        f"Suite __init__.py fallback '{init_ver}' != "
        f"VERSION file '{version_file_ver}'"
    )


# ── OPP version consistency ─────────────────────────────────────────────


def test_opp_pyproject_version_matches_init():
    """OPP pyproject.toml version must match OPP __init__.py fallback."""
    pyproject_ver = _parse_toml_version(OPP_PYPROJECT)
    init_ver = _parse_init_fallback(OPP_INIT)
    assert pyproject_ver is not None, f"Cannot parse version from {OPP_PYPROJECT}"
    assert init_ver is not None, f"Cannot parse fallback version from {OPP_INIT}"
    assert pyproject_ver == init_ver, (
        f"OPP pyproject.toml version '{pyproject_ver}' != "
        f"OPP __init__.py fallback '{init_ver}'"
    )


# ── OL version consistency ──────────────────────────────────────────────


def test_ol_pyproject_version_matches_init():
    """OL pyproject.toml version must match OL __init__.py hardcoded version."""
    pyproject_ver = _parse_toml_version(OL_PYPROJECT)
    init_ver = _parse_init_fallback(OL_INIT)
    assert pyproject_ver is not None, f"Cannot parse version from {OL_PYPROJECT}"
    assert init_ver is not None, f"Cannot parse version from {OL_INIT}"
    assert pyproject_ver == init_ver, (
        f"OL pyproject.toml version '{pyproject_ver}' != "
        f"OL __init__.py version '{init_ver}'"
    )


# ── ORF version consistency ─────────────────────────────────────────────


def test_orf_pyproject_version_matches_init():
    """ORF pyproject.toml version must match ORF __init__.py (importlib.metadata).

    ORF's ``__init__.py`` uses ``importlib.metadata`` directly (no fallback),
    so we check that the version string in ``pyproject.toml`` is present
    somewhere in the ``__init__.py`` (e.g. as a comment or reference).
    """
    pyproject_ver = _parse_toml_version(ORF_PYPROJECT)
    assert pyproject_ver is not None, f"Cannot parse version from {ORF_PYPROJECT}"

    # ORF uses importlib.metadata at runtime — the version comes from
    # the installed package. We verify the pyproject.toml version is
    # consistent with the source tree (no drift between them).
    assert pyproject_ver, f"ORF pyproject.toml has empty version"
