"""Tests for scripts/check_governance_paths.py (Omni Suite issue #260).

Every test writes a synthetic ``.github/CODEOWNERS`` under ``tmp_path`` and
runs the real CLI as a subprocess, so the assertions cover exit codes and the
human-readable gate messages exactly as CI sees them.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_governance_paths.py"

CODEOWNERS = """\
# Owner-gated surfaces (fixture).
/.agents/expectations/  @owner
/.agents/roles/         @owner
/scenarios/             @owner
/docs/dev/              @owner
"""


def _tree(tmp_path: Path, codeowners: str | None = CODEOWNERS) -> Path:
    if codeowners is not None:
        target = tmp_path / ".github" / "CODEOWNERS"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(codeowners, encoding="utf-8")
    return tmp_path


def _run(
    cwd: Path,
    *args: str,
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin,
        text=True,
        capture_output=True,
        cwd=cwd,
        check=False,
    )


def test_no_protected_paths_exit_zero(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    result = _run(root, "--files", "-", "--labels", "", stdin="README.md\n")
    assert result.returncode == 0
    assert "OK: no unprotected governance changes" in result.stdout


def test_protected_without_label_fails(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    result = _run(
        root,
        "--files",
        "-",
        "--labels",
        "",
        stdin="scenarios/foo.yaml\ndocs/dev/gate.md\n",
    )
    assert result.returncode == 1
    assert "PROTECTED: scenarios/foo.yaml (matched /scenarios/)" in result.stdout
    assert "PROTECTED: docs/dev/gate.md (matched /docs/dev/)" in result.stdout
    assert "governance-approved" in result.stdout
    assert "Ask the owner to add it." in result.stdout


def test_protected_with_label_passes(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    result = _run(
        root,
        "--files",
        "-",
        "--labels",
        "bug,governance-approved",
        stdin="scenarios/foo.yaml\n",
    )
    assert result.returncode == 0
    assert "OK: 1 governance file(s) allowed by 'governance-approved'" in result.stdout


def test_codeowners_file_itself_is_protected(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    result = _run(
        root,
        "--files",
        "-",
        "--labels",
        "",
        stdin=".github/CODEOWNERS\n",
    )
    assert result.returncode == 1
    assert "PROTECTED: .github/CODEOWNERS" in result.stdout
    assert "FAIL: 1 governance path(s)" in result.stdout


def test_custom_label_name(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    allowed = _run(
        root,
        "--files",
        "-",
        "--labels",
        "owner-ok",
        "--label-name",
        "owner-ok",
        stdin="scenarios/foo.yaml\n",
    )
    assert allowed.returncode == 0
    assert "allowed by 'owner-ok'" in allowed.stdout

    wrong_label = _run(
        root,
        "--files",
        "-",
        "--labels",
        "governance-approved",
        "--label-name",
        "owner-ok",
        stdin="scenarios/foo.yaml\n",
    )
    assert wrong_label.returncode == 1
    assert "'owner-ok' label" in wrong_label.stdout


def test_removing_codeowners_line_unprotects_path(tmp_path: Path) -> None:
    reduced = "".join(
        line + "\n" for line in CODEOWNERS.splitlines() if "scenarios" not in line
    )
    root = _tree(tmp_path, reduced)
    result = _run(root, "--files", "-", "--labels", "", stdin="scenarios/foo.yaml\n")
    assert result.returncode == 0
    assert "OK: no unprotected governance changes" in result.stdout


def test_missing_codeowners_skips(tmp_path: Path) -> None:
    root = _tree(tmp_path, codeowners=None)
    result = _run(root, "--files", "-", "--labels", "", stdin="scenarios/foo.yaml\n")
    assert result.returncode == 0
    assert "SKIP: no CODEOWNERS file" in result.stdout


def test_files_argument_reads_path(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    changed = root / "changed.txt"
    changed.write_text("docs/dev/gate.md\n", encoding="utf-8")
    result = _run(root, "--files", str(changed), "--labels", "")
    assert result.returncode == 1
    assert "PROTECTED: docs/dev/gate.md" in result.stdout
