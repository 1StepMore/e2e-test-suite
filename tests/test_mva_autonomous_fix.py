"""MVA demo test: verifies the autonomous fix cycle works end-to-end.

This test exercises a real bug (NEW-1) in scripts/omo_loop.py:
_run_verify_all only catches subprocess.TimeoutExpired, but if the
verifier script is missing or sys.executable is invalid, subprocess.run
raises FileNotFoundError or OSError. The aggregator crashes uncaught
instead of marking the missing verifier as failed.

The test injects a fake broken verifier (path that does not exist)
and asserts the function returns non-zero instead of raising.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_OMO_LOOP_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_OMO_LOOP_DIR))

from omo_loop import _run_verify_all  # noqa: E402


class TestAutonomousFix:
    def test_verify_all_handles_missing_verifier_script(self, tmp_path):
        """A verifier script that does not exist must be reported as
        failed (not crash the whole aggregator).

        RED: function raises FileNotFoundError.
        GREEN: function returns 1 with the missing verifier in failed list.
        """
        # Fake verifiers: one valid (always-true), one with a missing script.
        sentinel = tmp_path / "always_pass.py"
        sentinel.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        missing = tmp_path / "this_does_not_exist.py"
        assert not missing.exists()  # sanity

        verifiers = [
            ("always_pass", sentinel, []),
            ("missing_verifier", missing, []),
        ]

        args = type("Args", (), {})()  # bare args namespace
        try:
            rc = _run_verify_all(args, verifiers=verifiers, out_dir=tmp_path)
        except (FileNotFoundError, OSError) as e:
            pytest.fail(
                f"_run_verify_all crashed with uncaught {type(e).__name__} "
                f"instead of returning 1: {e}"
            )
        assert rc == 1, f"expected rc=1 (one verifier failed), got {rc}"
