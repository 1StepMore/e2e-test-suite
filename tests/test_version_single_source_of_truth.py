"""Test P1-T3: Version SSOT and P1-T4: COMPATIBILITY.md unification.

Ensures:
- VERSION_COMPATIBILITY.md is removed (it duplicated COMPATIBILITY.md and was stale)
- COMPATIBILITY.md reflects actual sub-repo versions from pyproject.toml
- sync_version_docs.py does not reference the deleted file
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _read_pyproject_version(pyproject_path: Path) -> str:
    """Read the version = 'X.Y.Z' line from a pyproject.toml."""
    for line in pyproject_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("version"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise ValueError(f"version not found in {pyproject_path}")


class TestP1T4VersionCompatRemoved:
    """P1-T4: VERSION_COMPATIBILITY.md should be removed."""

    def test_version_compatibility_md_does_not_exist(self):
        """VERSION_COMPATIBILITY.md duplicates COMPATIBILITY.md and was out of date."""
        vc = REPO_ROOT / "VERSION_COMPATIBILITY.md"
        assert not vc.exists(), (
            f"VERSION_COMPATIBILITY.md still exists at {vc}. "
            f"It duplicates COMPATIBILITY.md and was last updated 2026-06-22. "
            f"Delete it to avoid conflicting version info."
        )

    def test_sync_version_docs_does_not_reference_version_compatibility(self):
        """sync_version_docs.py should not reference the deleted VERSION_COMPATIBILITY.md."""
        sync = REPO_ROOT / "scripts" / "sync_version_docs.py"
        content = sync.read_text(encoding="utf-8")
        assert "VERSION_COMPATIBILITY" not in content, (
            "sync_version_docs.py still references VERSION_COMPATIBILITY.md. "
            "Remove these references since the file is deleted."
        )


class TestP1T3VersionSSOT:
    """P1-T3: COMPATIBILITY.md should reflect actual pyproject.toml versions."""

    def test_compatibility_md_ol_version_matches_pyproject(self):
        """COMPATIBILITY.md latest row should show current OL version (0.7.0)."""
        ol_version = _read_pyproject_version(
            REPO_ROOT / "Omni_Localizer" / "pyproject.toml"
        )
        compat = REPO_ROOT / "COMPATIBILITY.md"
        content = compat.read_text(encoding="utf-8")
        # The latest Suite row in the compatibility matrix should have the current OL version
        # Check that OL version appears somewhere in the matrix (not just in example commands)
        matrix_lines = [
            line for line in content.splitlines()
            if line.startswith("|") and ol_version in line
        ]
        assert matrix_lines, (
            f"OL version {ol_version} not found in any row of COMPATIBILITY.md matrix. "
            f"Latest row still shows old version. Update COMPATIBILITY.md."
        )

    def test_compatibility_md_opp_version_matches_pyproject(self):
        """COMPATIBILITY.md latest row should show current OPP version (0.9.1)."""
        opp_version = _read_pyproject_version(
            REPO_ROOT / "Omni_Pre_Processor" / "pyproject.toml"
        )
        compat = REPO_ROOT / "COMPATIBILITY.md"
        content = compat.read_text(encoding="utf-8")
        matrix_lines = [
            line for line in content.splitlines()
            if line.startswith("|") and opp_version in line
        ]
        assert matrix_lines, (
            f"OPP version {opp_version} not found in any row of COMPATIBILITY.md matrix. "
            f"Update COMPATIBILITY.md."
        )

    def test_compatibility_md_orf_version_matches_pyproject(self):
        """COMPATIBILITY.md latest row should show current ORF version (0.4.16)."""
        orf_version = _read_pyproject_version(
            REPO_ROOT / "Omni_Re_Formatter" / "pyproject.toml"
        )
        compat = REPO_ROOT / "COMPATIBILITY.md"
        content = compat.read_text(encoding="utf-8")
        matrix_lines = [
            line for line in content.splitlines()
            if line.startswith("|") and orf_version in line
        ]
        assert matrix_lines, (
            f"ORF version {orf_version} not found in any row of COMPATIBILITY.md matrix. "
            f"Update COMPATIBILITY.md."
        )
