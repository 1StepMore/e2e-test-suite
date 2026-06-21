"""TDD tests for the --gate flag in convergence-watch.

Locks in: when --mode convergence-watch runs, it must invoke BOTH
Tier 6 (verifier health) and Tier 7 (format matrix) by default,
and respect --gate tier6 / --gate tier7 to run a single gate.

The mocked gate functions simulate the TIER call signatures so the
test runs in <1s without spinning up real Tier 6/7 subprocesses.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import omo_loop  # noqa: E402


def _args(max_cycles=10, consecutive_green=2, max_fix_fail=5, gate="both"):
    return argparse.Namespace(
        max_cycles=max_cycles,
        consecutive_green=consecutive_green,
        max_fix_fail=max_fix_fail,
        source_lang="en",
        target_lang="zh",
        gate=gate,
    )


class TestConvergenceWatchGateDispatch:
    def test_default_gate_runs_both_tier6_and_tier7(self, monkeypatch):
        """--gate defaults to 'both' so both Tier 6 and Tier 7 are called."""
        calls = {"tier6": 0, "tier7": 0}

        def fake_t6(_args):
            calls["tier6"] += 1
            return 0

        def fake_t7(_args):
            calls["tier7"] += 1
            return 0

        monkeypatch.setattr(omo_loop, "_run_verify_all", fake_t6)
        monkeypatch.setattr(omo_loop, "_run_format_matrix", fake_t7)
        monkeypatch.setattr(omo_loop, "_run_bug_fix", lambda a: None)

        rc = omo_loop._run_convergence_watch(_args(consecutive_green=1, max_cycles=2))
        assert rc == 0
        assert calls["tier6"] >= 1
        assert calls["tier7"] >= 1
        assert calls["tier6"] == calls["tier7"]

    def test_gate_tier6_only_runs_tier6(self, monkeypatch):
        """--gate tier6 should call only Tier 6, not Tier 7."""
        calls = {"tier6": 0, "tier7": 0}

        def fake_t6(_args):
            calls["tier6"] += 1
            return 0

        monkeypatch.setattr(omo_loop, "_run_verify_all", fake_t6)
        monkeypatch.setattr(omo_loop, "_run_format_matrix", lambda a: calls.__setitem__("tier7", calls["tier7"]+1) or 0)
        monkeypatch.setattr(omo_loop, "_run_bug_fix", lambda a: None)

        rc = omo_loop._run_convergence_watch(_args(gate="tier6", consecutive_green=1, max_cycles=2))
        assert rc == 0
        assert calls["tier6"] >= 1
        assert calls["tier7"] == 0

    def test_gate_tier7_only_runs_tier7(self, monkeypatch):
        """--gate tier7 should call only Tier 7, not Tier 6."""
        calls = {"tier6": 0, "tier7": 0}

        def fake_t7(_args):
            calls["tier7"] += 1
            return 0

        monkeypatch.setattr(omo_loop, "_run_verify_all", lambda a: calls.__setitem__("tier6", calls["tier6"]+1) or 0)
        monkeypatch.setattr(omo_loop, "_run_format_matrix", fake_t7)
        monkeypatch.setattr(omo_loop, "_run_bug_fix", lambda a: None)

        rc = omo_loop._run_convergence_watch(_args(gate="tier7", consecutive_green=1, max_cycles=2))
        assert rc == 0
        assert calls["tier6"] == 0
        assert calls["tier7"] >= 1

    def test_red_in_any_gate_dispatches_bug_fix(self, monkeypatch):
        """If EITHER gate is red, the loop dispatches bug-fix until max_fix_fail."""
        dispatched = {"count": 0}

        monkeypatch.setattr(omo_loop, "_run_verify_all", lambda a: 0)
        monkeypatch.setattr(omo_loop, "_run_format_matrix", lambda a: 1)

        def fake_bug_fix(_a):
            dispatched["count"] += 1

        monkeypatch.setattr(omo_loop, "_run_bug_fix", fake_bug_fix)

        rc = omo_loop._run_convergence_watch(
            _args(gate="both", consecutive_green=2, max_fix_fail=2, max_cycles=3)
        )
        assert rc == 1
        assert dispatched["count"] == 1

    def test_blocked_after_max_fix_fail_no_dispatch(self, monkeypatch):
        """Once max_fix_fail is reached, no more dispatches happen."""
        dispatched = {"count": 0}

        monkeypatch.setattr(omo_loop, "_run_verify_all", lambda a: 0)
        monkeypatch.setattr(omo_loop, "_run_format_matrix", lambda a: 1)
        monkeypatch.setattr(
            omo_loop, "_run_bug_fix", lambda a: dispatched.__setitem__("count", dispatched["count"]+1)
        )

        rc = omo_loop._run_convergence_watch(
            _args(gate="both", consecutive_green=2, max_fix_fail=2, max_cycles=10)
        )
        assert rc == 1
        assert dispatched["count"] == 1

    def test_all_green_converges_after_consecutive_target(self, monkeypatch):
        """When all gates green for N consecutive cycles, exit 0."""
        monkeypatch.setattr(omo_loop, "_run_verify_all", lambda a: 0)
        monkeypatch.setattr(omo_loop, "_run_format_matrix", lambda a: 0)
        monkeypatch.setattr(omo_loop, "_run_bug_fix", lambda a: None)

        rc = omo_loop._run_convergence_watch(
            _args(gate="both", consecutive_green=3, max_cycles=10)
        )
        assert rc == 0
