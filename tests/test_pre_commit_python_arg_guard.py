"""Tests for the zero-arg fail-closed guard in ``scripts/pre_commit_python.sh``.

The guard must reject an empty argument list before any interpreter is resolved:
handing ``"$@"`` (empty) to a Python interpreter starts an interactive REPL,
which silently exits 0 on EOF (fake green) or blocks forever on an active
pipe. Every test runs the real script as a subprocess -- no mocks.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "pre_commit_python.sh"


def _bash() -> str:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is not available on this host")
    return bash


def test_zero_args_with_eof_stdin_exits_2(tmp_path: Path) -> None:
    # tmp_path as cwd: the guard fires before venv probing, so the isolation
    # only keeps any venv lookup noise out of this assertion.
    result = subprocess.run(
        [_bash(), str(SCRIPT)],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )
    assert result.returncode == 2
    assert "FAIL:" in result.stderr


def test_zero_args_with_active_stdin_fails_fast(tmp_path: Path) -> None:
    # Parent keeps the pipe open (never writes, never closes) to reproduce the
    # blocking-stdin case; the guard must still return within 5 seconds.
    proc = subprocess.Popen(
        [_bash(), str(SCRIPT)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=tmp_path,
    )
    try:
        try:
            returncode = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pytest.fail("zero-arg invocation hung on active stdin for >5s")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()

    stderr = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
    assert returncode == 2
    assert "FAIL:" in stderr


def test_normal_path_still_runs_code() -> None:
    # Repo root as cwd on purpose: this is the only case that must reach
    # interpreter resolution, so a project venv (if built) can be picked up.
    result = subprocess.run(
        [_bash(), str(SCRIPT), "-c", "print(1)"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0
    assert "1" in result.stdout
