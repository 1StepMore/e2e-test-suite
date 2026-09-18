"""The canonical constants must match the in-tree copies exactly, and the
package must stay a dependency-free leaf."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import omni_security

EXPECTED_SYSTEM_DIRS = frozenset(
    {
        "/etc",
        "/usr",
        "/var",
        "/proc",
        "/sys",
        "/System",
        "/Library",
        "/C:/Windows",
        "C:\\Windows",
    }
)
EXPECTED_BLOCKED_EXTENSIONS = frozenset(
    {".exe", ".bat", ".cmd", ".sh", ".ps1", ".vbs", ".js"}
)
EXPECTED_REASONS = frozenset(
    {
        "REASON_INVALID_PATH_FORMAT",
        "REASON_PATH_TRAVERSAL",
        "REASON_CANNOT_RESOLVE",
        "REASON_SYSTEM_DIR",
        "REASON_OUTSIDE_ALLOWLIST",
        "REASON_SYMLINK_ESCAPE",
        "REASON_SYMLINK_INACCESSIBLE",
        "REASON_BLOCKED_EXTENSION",
        "REASON_DISALLOWED_EXTENSION",
        "REASON_FILE_MISSING",
        "REASON_NOT_A_FILE",
        "REASON_FILE_TOO_LARGE",
        "REASON_STAT_FAILED",
    }
)
FORBIDDEN_MODULES = ("opp", "ol_mcp", "orf", "omni_mcp", "omni_suite")


def test_system_dirs_match_the_canonical_set():
    assert set(omni_security.SYSTEM_DIRS) == set(EXPECTED_SYSTEM_DIRS)


def test_blocked_extensions_match_the_canonical_set():
    assert set(omni_security.BLOCKED_EXTENSIONS) == set(EXPECTED_BLOCKED_EXTENSIONS)


def test_public_surface_is_exported():
    expected = {
        "SYSTEM_DIRS",
        "BLOCKED_EXTENSIONS",
        "OmniSecurityError",
        "PathValidationError",
        "ValidationResult",
        "validate_path",
        "validate_path_result",
        "system_dir_denial",
        "parse_allowed_dirs",
        "resolve_allowed_extensions",
    } | set(EXPECTED_REASONS)

    assert expected <= set(omni_security.__all__)
    for name in omni_security.__all__:
        assert hasattr(omni_security, name), f"__all__ names a missing symbol: {name}"


def test_package_is_a_leaf():
    """Importing ``omni_security`` in a fresh interpreter loads no Omni module."""
    src = Path(__file__).resolve().parents[1] / "src"
    script = (
        "import sys\n"
        "import omni_security\n"
        f"forbidden = {FORBIDDEN_MODULES!r}\n"
        "leaked = sorted(name for name in forbidden if name in sys.modules)\n"
        "if leaked:\n"
        "    print(','.join(leaked))\n"
        "    raise SystemExit(1)\n"
        "raise SystemExit(0)\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(src)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, (
        "omni_security imported a forbidden module: "
        f"{result.stdout.strip() or result.stderr.strip()}"
    )
