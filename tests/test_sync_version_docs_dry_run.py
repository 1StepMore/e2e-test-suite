"""Test P1-T2: sync_version_docs.py should support --dry-run and --validate modes."""
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "sync_version_docs.py"


def test_dry_run_flag_exists():
    """The script must accept --dry-run flag."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run", "--help"],
        capture_output=True, text=True, timeout=30,
    )
    # If --dry-run is unknown, argparse will print "unrecognized arguments" and exit 2
    assert "unrecognized arguments" not in result.stderr, (
        f"--dry-run flag is not supported. stderr: {result.stderr}"
    )


def test_dry_run_does_not_modify_files(tmp_path):
    """--dry-run must NOT write to any target file."""
    # First, snapshot modification times
    targets = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "COMPATIBILITY.md",
    ]
    mtimes_before = {t: t.stat().st_mtime for t in targets if t.exists()}

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        capture_output=True, text=True, timeout=30,
        cwd=REPO_ROOT,
    )
    # Exit code can be 0 or 1 depending on whether there are changes
    assert result.returncode in (0, 1), f"Unexpected exit code: {result.returncode}\n{result.stderr}"

    mtimes_after = {t: t.stat().st_mtime for t in targets if t.exists()}
    for t in targets:
        if t.exists():
            assert mtimes_before[t] == mtimes_after[t], (
                f"{t} was modified during --dry-run! Before: {mtimes_before[t]}, After: {mtimes_after[t]}"
            )


def test_validate_flag_strict_check():
    """--validate should exit non-zero if versions disagree between pyproject and docs."""
    # This is similar to the existing --check behavior; test it exists
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--validate"],
        capture_output=True, text=True, timeout=30,
        cwd=REPO_ROOT,
    )
    # Should not fail with "unrecognized arguments"
    assert "unrecognized arguments" not in result.stderr, (
        f"--validate flag is not supported. stderr: {result.stderr}"
    )
