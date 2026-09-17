"""TDD tests for the --gate flag in convergence-watch.

Locks in: when --mode convergence-watch runs, it must invoke ALL THREE
gates by default — Tier 6 (verifier health), Tier 7 (format matrix) and
Tier 8 (real corpus + fidelity + equivalence) — and respect
--gate tier6 / --gate tier7 / --gate tier8 to run a single gate.

The mocked gate functions simulate the TIER call signatures so the
test runs in <1s without spinning up real Tier 6/7/8 subprocesses.
Without the stubs, --gate both really would launch the Tier 8 real-corpus
gate, which is a multi-minute subprocess and made this file flaky-slow.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

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


def _stub_all_gates(monkeypatch, tier6=0, tier7=0, tier8=0):
    """Replace the three convergence-watch gates with counting stubs.

    Args:
        monkeypatch: pytest monkeypatch fixture.
        tier6: return code the stubbed Tier 6 gate reports.
        tier7: return code the stubbed Tier 7 gate reports.
        tier8: return code the stubbed Tier 8 gate reports.

    Returns:
        dict counting how many times each gate was invoked, keyed by
        "tier6" / "tier7" / "tier8".
    """
    calls = {"tier6": 0, "tier7": 0, "tier8": 0}

    def _make(name: str, rc: int):
        def _fn(_args):
            calls[name] += 1
            return rc
        return _fn

    monkeypatch.setattr(omo_loop, "_run_verify_all", _make("tier6", tier6))
    monkeypatch.setattr(omo_loop, "_run_format_matrix", _make("tier7", tier7))
    monkeypatch.setattr(omo_loop, "_run_tier8", _make("tier8", tier8))
    monkeypatch.setattr(omo_loop, "_run_bug_fix", lambda a: None)
    return calls


class TestConvergenceWatchGateDispatch:
    def test_default_gate_runs_all_three_tiers(self, monkeypatch):
        """--gate defaults to 'both' so Tier 6, Tier 7 and Tier 8 are all called."""
        calls = _stub_all_gates(monkeypatch)

        rc = omo_loop._run_convergence_watch(_args(consecutive_green=1, max_cycles=2))
        assert rc == 0
        assert calls["tier6"] >= 1
        assert calls["tier7"] >= 1
        assert calls["tier8"] >= 1
        assert calls["tier6"] == calls["tier7"] == calls["tier8"]

    def test_gate_tier6_only_runs_tier6(self, monkeypatch):
        """--gate tier6 should call only Tier 6, not Tier 7 / Tier 8."""
        calls = _stub_all_gates(monkeypatch)

        rc = omo_loop._run_convergence_watch(_args(gate="tier6", consecutive_green=1, max_cycles=2))
        assert rc == 0
        assert calls["tier6"] >= 1
        assert calls["tier7"] == 0
        assert calls["tier8"] == 0

    def test_gate_tier7_only_runs_tier7(self, monkeypatch):
        """--gate tier7 should call only Tier 7, not Tier 6 / Tier 8."""
        calls = _stub_all_gates(monkeypatch)

        rc = omo_loop._run_convergence_watch(_args(gate="tier7", consecutive_green=1, max_cycles=2))
        assert rc == 0
        assert calls["tier6"] == 0
        assert calls["tier7"] >= 1
        assert calls["tier8"] == 0

    def test_gate_tier8_only_runs_tier8(self, monkeypatch):
        """--gate tier8 should call only Tier 8, not Tier 6 / Tier 7."""
        calls = _stub_all_gates(monkeypatch)

        rc = omo_loop._run_convergence_watch(_args(gate="tier8", consecutive_green=1, max_cycles=2))
        assert rc == 0
        assert calls["tier6"] == 0
        assert calls["tier7"] == 0
        assert calls["tier8"] >= 1

    def test_red_in_any_gate_dispatches_bug_fix(self, monkeypatch):
        """If ANY gate is red, the loop dispatches bug-fix until max_fix_fail."""
        dispatched = {"count": 0}
        _stub_all_gates(monkeypatch, tier7=1)
        monkeypatch.setattr(
            omo_loop, "_run_bug_fix", lambda a: dispatched.__setitem__("count", dispatched["count"] + 1)
        )

        rc = omo_loop._run_convergence_watch(
            _args(gate="both", consecutive_green=2, max_fix_fail=2, max_cycles=3)
        )
        assert rc == 1
        assert dispatched["count"] == 1

    def test_red_in_tier8_dispatches_bug_fix(self, monkeypatch):
        """A red Tier 8 alone must be enough to block convergence."""
        dispatched = {"count": 0}
        _stub_all_gates(monkeypatch, tier8=1)
        monkeypatch.setattr(
            omo_loop, "_run_bug_fix", lambda a: dispatched.__setitem__("count", dispatched["count"] + 1)
        )

        rc = omo_loop._run_convergence_watch(
            _args(gate="both", consecutive_green=2, max_fix_fail=2, max_cycles=3)
        )
        assert rc == 1
        assert dispatched["count"] == 1

    def test_blocked_after_max_fix_fail_no_dispatch(self, monkeypatch):
        """Once max_fix_fail is reached, no more dispatches happen."""
        dispatched = {"count": 0}
        _stub_all_gates(monkeypatch, tier7=1)
        monkeypatch.setattr(
            omo_loop, "_run_bug_fix", lambda a: dispatched.__setitem__("count", dispatched["count"] + 1)
        )

        rc = omo_loop._run_convergence_watch(
            _args(gate="both", consecutive_green=2, max_fix_fail=2, max_cycles=10)
        )
        assert rc == 1
        assert dispatched["count"] == 1

    def test_all_green_converges_after_consecutive_target(self, monkeypatch):
        """When all gates green for N consecutive cycles, exit 0."""
        _stub_all_gates(monkeypatch)

        rc = omo_loop._run_convergence_watch(
            _args(gate="both", consecutive_green=3, max_cycles=10)
        )
        assert rc == 0
