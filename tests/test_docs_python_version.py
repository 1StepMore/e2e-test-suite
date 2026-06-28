"""Verify no stale Python 3.10 / py310 references in CONTRIBUTING.md files.

Checks all CONTRIBUTING.md files in the repo (suite + sub-repos) for
stale version references that should have been updated to 3.13 / py313.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Stale patterns that should NOT appear
STALE_PATTERNS = [
    'python_version = "3.10"',
    'target-version = "py310"',
    "Python 3.10",
    "Python 3.9",
    "Python 3.8",
]


def _all_contributing_files() -> list[Path]:
    """Collect all CONTRIBUTING.md files from explicit module dirs."""
    candidates = [
        ROOT / "CONTRIBUTING.md",
        ROOT / "Omni_Pre_Processor" / "CONTRIBUTING.md",
        ROOT / "Omni_Re_Formatter" / "CONTRIBUTING.md",
        ROOT / "Omni_Localizer" / "CONTRIBUTING.md",
    ]
    return sorted(p for p in candidates if p.exists())


def test_no_stale_python_version_in_contributing():
    """CONTRIBUTING.md must not reference Python < 3.13."""
    files = _all_contributing_files()
    assert files, "No CONTRIBUTING.md files found"

    for path in files:
        text = path.read_text(encoding="utf-8")
        for pattern in STALE_PATTERNS:
            assert pattern not in text, (
                f"Stale pattern '{pattern}' found in {path}"
            )


def test_current_python_version_referenced():
    """CONTRIBUTING.md files with explicit version info should reference Python 3.13/py313."""
    files = _all_contributing_files()
    for path in files:
        text = path.read_text(encoding="utf-8")
        # Check for explicit Python version or ruff target-version references only
        has_explicit_version_ref = any(
            pat in text for pat in [
                "Python 3.", "python_version", "target-version",
                "py310", "py311", "py312",
            ]
        )
        if not has_explicit_version_ref:
            continue  # skip files without version-pin content
        has_current = ("3.13" in text) or ("py313" in text)
        assert has_current, (
            f"{path} has an explicit version reference but does not use 3.13 or py313"
        )
