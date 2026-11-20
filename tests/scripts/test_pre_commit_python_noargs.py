"""suite#350: ``scripts/pre_commit_python.sh`` must fail closed on zero args.

Before the guard, ``exec "$interpreter" "$@"`` with an empty argument list
started an interactive Python REPL: with stdin at EOF it exited 0 without
running anything (skip-as-pass = false green), and with a live pipe it blocked
forever while a foreground timeout killed only the leader, orphaning python.

Both cases must now return rc=2 immediately and must not execute an interpreter.
"""

import shutil
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "pre_commit_python.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="bash is required to exercise the wrapper"
)

EXPECTED_MSG = "no python files given"


def _run_noargs(stdin_spec: str, timeout: float = 5.0) -> tuple[subprocess.CompletedProcess, float]:
    """Run the wrapper with zero args; ``stdin_spec`` is the bash redirection.

    The wrapper is invoked through an outer bash so ``< <(sleep 30)`` gives it a
    live, never-closing stdin exactly like the reported hang. ``sleep`` gets its
    own stdout/stderr so the helper does not wait 30s for the inherited capture
    pipes to close after the wrapper has already exited.
    """
    cmd = ["bash", "-c", f"bash {SCRIPT} {stdin_spec}"]
    started = time.monotonic()
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc, time.monotonic() - started


def test_zero_args_with_eof_stdin_exits_2():
    """① stdin EOF: rc=2 (not 0), no interpreter started."""
    proc, elapsed = _run_noargs("< /dev/null")

    assert proc.returncode == 2, (
        f"expected rc=2, got {proc.returncode}; stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    assert EXPECTED_MSG in proc.stderr
    assert elapsed < 5.0, f"took {elapsed:.2f}s, expected an immediate failure"


def test_zero_args_with_live_stdin_does_not_block():
    """② live pipe: rc=2 immediately (not a timeout / not 124)."""
    proc, elapsed = _run_noargs("< <(sleep 30 >/dev/null 2>&1)")

    assert proc.returncode == 2, (
        f"expected rc=2, got {proc.returncode}; stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    assert EXPECTED_MSG in proc.stderr
    assert elapsed < 5.0, f"took {elapsed:.2f}s, wrapper blocked on open stdin"
