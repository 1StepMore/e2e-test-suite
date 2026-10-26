"""Tests for omni_mcp.validation.engine (guide §3.1 phases 4-6, §4 honesty).

The engine is the orchestrator: load (loader.py) -> dispatch (dispatch.py)
-> grade (grader.py) -> aggregate -> trace -> persist.  These tests drive
it end-to-end with tiny cli/python steps (real subprocesses — the only
surface that needs no component imports) and assert the guide's verdict
semantics (passed | failed | unconfigured | recovered | partial-pass),
the per-step trace fields (step_index / duration_seconds / arguments /
trace_id), and the ``validation-runs/<ts>/scenarios.json`` + ``latest.txt``
persistence (guide §3.1 phase 6, phase-6 persistence).
"""

import json
import os
import textwrap
import uuid

import pytest

from omni_mcp.validation.dispatch import StepResult
from omni_mcp.validation.engine import (
    RunResult,
    ScenarioResult,
    _is_throttled,
    _missing_env,
    _step_status,
    persist_run,
    run_scenarios,
)
from omni_mcp.validation.loader import ScenarioError

MISSING_VAR = "DEFINITELY_MISSING_VAR"


def _write(tmp_path, name, body):
    """Write a scenario YAML file, creating parent dirs."""
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def _cli_steps(*commands):
    """YAML steps block: one cli step per command, expecting success."""
    return "\n".join(
        f'  - name: "step {i}"\n    kind: cli\n    command: "{cmd}"\n'
        f"    expect:\n      success: true"
        for i, cmd in enumerate(commands, 1)
    )


def _scenario(name, *, requires_env="", requires_env_any="", min_passing=None,
              pass_ratio=None, steps="", cleanup_steps=""):
    """Build a scenario YAML body; steps default to one passing cli step."""
    head = [f"name: {name}", f'description: "{name}"']
    if requires_env:
        head.append(f"requires_env: {requires_env}")
    if requires_env_any:
        head.append(f"requires_env_any: {requires_env_any}")
    if min_passing is not None:
        head.append(f"min_passing: {min_passing}")
    if pass_ratio is not None:
        head.append(f"pass_ratio: {pass_ratio}")
    body = "steps:\n" + (steps or _cli_steps("true"))
    if cleanup_steps:
        body += "\ncleanup_steps:\n" + cleanup_steps
    return "\n".join(head) + "\n" + body


# ---------------------------------------------------------------------------
# Aggregation: verdicts
# ---------------------------------------------------------------------------


def test_all_steps_pass_verdict_passed(tmp_path):
    _write(tmp_path, "pass.yaml", _scenario("simple", steps=_cli_steps("true", "true")))
    run = run_scenarios(tmp_path, persist=False)
    assert len(run.scenarios) == 1
    sc = run.scenarios[0]
    assert sc.status == "passed"
    assert sc.missing_env == []


def test_failed_step_verdict_failed(tmp_path):
    _write(tmp_path, "fail.yaml", _scenario("simple", steps=_cli_steps("true", "false")))
    run = run_scenarios(tmp_path, persist=False)
    assert run.scenarios[0].status == "failed"


def test_no_policy_one_fail_failed(tmp_path):
    # All-or-nothing default (guide §2.7): no min_passing/pass_ratio.
    _write(tmp_path, "mixed.yaml", _scenario("mixed", steps=_cli_steps("true", "false")))
    assert run_scenarios(tmp_path, persist=False).scenarios[0].status == "failed"


# ---------------------------------------------------------------------------
# unconfigured gate (guide §2.5, §4.2: never passes, never fails, never silent)
# ---------------------------------------------------------------------------


def test_unconfigured_when_env_missing(tmp_path, monkeypatch):
    monkeypatch.delenv(MISSING_VAR, raising=False)
    _write(tmp_path, "gated.yaml",
           _scenario("gated", requires_env=f"[{MISSING_VAR}]", steps=_cli_steps("true")))
    sc = run_scenarios(tmp_path, persist=False).scenarios[0]
    assert sc.status == "unconfigured"
    assert sc.missing_env == [MISSING_VAR]
    assert sc.steps == []  # nothing ran


def test_unconfigured_never_passes_or_fails(tmp_path, monkeypatch):
    monkeypatch.delenv(MISSING_VAR, raising=False)
    _write(tmp_path, "gated.yaml",
           _scenario("gated", requires_env=f"[{MISSING_VAR}]", steps=_cli_steps("true")))
    sc = run_scenarios(tmp_path, persist=False).scenarios[0]
    assert sc.status not in ("passed", "failed")
    assert sc.status == "unconfigured"


def test_unconfigured_steps_do_not_run(tmp_path, monkeypatch):
    monkeypatch.delenv(MISSING_VAR, raising=False)
    marker = tmp_path / "marker.txt"
    _write(tmp_path, "gated.yaml", _scenario(
        "gated", requires_env=f"[{MISSING_VAR}]",
        steps=f'  - name: "touch"\n    kind: cli\n    command: "touch {marker}"\n'
              "    expect:\n      success: true"))
    run_scenarios(tmp_path, persist=False)
    assert not marker.exists()


def test_unconfigured_empty_string_env_is_missing(tmp_path):
    # A var present but empty counts as missing (empty counts as missing).
    _write(tmp_path, "gated.yaml",
           _scenario("gated", requires_env="[OMNI_EMPTY_VAR]", steps=_cli_steps("true")))
    run = run_scenarios(tmp_path, env={"OMNI_EMPTY_VAR": ""}, persist=False)
    assert run.scenarios[0].status == "unconfigured"
    assert run.scenarios[0].missing_env == ["OMNI_EMPTY_VAR"]


def test_env_param_satisfies_gate(tmp_path, monkeypatch):
    # The gate checks the effective env (the env param when given), which
    # is exactly what dispatch will run the steps with.
    monkeypatch.delenv("OMNI_PROVIDED_VAR", raising=False)
    _write(tmp_path, "gated.yaml",
           _scenario("gated", requires_env="[OMNI_PROVIDED_VAR]", steps=_cli_steps("true")))
    # dispatch uses the explicit env as-is (build_cli_env semantics), so it
    # must carry PATH for bare command names to resolve.
    run = run_scenarios(
        tmp_path,
        env={"OMNI_PROVIDED_VAR": "1", "PATH": os.environ.get("PATH", "")},
        persist=False,
    )
    assert run.scenarios[0].status == "passed"
    assert run.scenarios[0].missing_env == []


def test_run_record_env_status(tmp_path):
    _write(tmp_path, "plain.yaml", _scenario("plain", steps=_cli_steps("true")))
    _write(tmp_path, "gated.yaml",
           _scenario("gated", requires_env=f"[{MISSING_VAR}]", steps=_cli_steps("true")))
    run = run_scenarios(tmp_path, persist=False)
    by_name = {s.name: s for s in run.scenarios}
    assert by_name["plain"].missing_env == []      # configured: empty list
    assert by_name["gated"].missing_env == [MISSING_VAR]


# ---------------------------------------------------------------------------
# requires_env_any OR group (PR-A): AND stays AND, OR overrides, OR fails closed
# ---------------------------------------------------------------------------


def test_missing_env_absent_or_group_is_byte_identical_to_and_only():
    # I1: absent/empty requires_env_any equals the AND-only result, order kept.
    assert _missing_env({"requires_env": ["A", "B"]}, {"A": "1"}) == ["B"]
    assert _missing_env(
        {"requires_env": ["A", "B"], "requires_env_any": []}, {"A": "1"}
    ) == ["B"]
    assert _missing_env({"requires_env": []}, {}) == []


def test_missing_env_or_group_satisfied_overrides_missing_and():
    # I2: one resolved OR member configures the scenario despite a missing AND var.
    assert _missing_env(
        {"requires_env": ["A"], "requires_env_any": ["B", "C"]}, {"B": "1"}
    ) == []


def test_missing_env_or_group_unsatisfied_fails_closed_without_and():
    # I3: a declared OR group with no resolving member fails closed even with
    # an empty AND list (a keyless user must never reach a real call).
    assert _missing_env(
        {"requires_env": [], "requires_env_any": ["B", "C"]}, {}
    ) == ["B", "C"]
    assert _missing_env({"requires_env_any": ["B"]}, {}) == ["B"]


def test_missing_env_or_group_unsatisfied_reports_members_and_and():
    # I4: unmet names carry the AND members plus the OR group's members.
    assert _missing_env(
        {"requires_env": ["A"], "requires_env_any": ["B", "C"]}, {}
    ) == ["A", "B", "C"]


def test_missing_env_empty_string_counts_as_missing_for_both_layers():
    # I5: a var present but empty is missing for requires_env and the OR group.
    assert _missing_env({"requires_env": ["A"]}, {"A": ""}) == ["A"]
    assert _missing_env({"requires_env_any": ["B"]}, {"B": ""}) == ["B"]


def test_unconfigured_or_group_unsatisfied_never_runs_steps(tmp_path):
    # I3 end-to-end: an unsatisfied OR group with an empty AND dispatches nothing.
    marker = tmp_path / "or-marker.txt"
    _write(tmp_path, "or-gated.yaml", _scenario(
        "or-gated", requires_env_any="[OMNI_OR_A, OMNI_OR_B]",
        steps=f'  - name: "touch"\n    kind: cli\n    command: "touch {marker}"\n'
              "    expect:\n      success: true"))
    sc = run_scenarios(
        tmp_path, env={"PATH": os.environ.get("PATH", "")}, persist=False
    ).scenarios[0]
    assert sc.status == "unconfigured"
    assert sc.steps == []
    assert sc.missing_env == ["OMNI_OR_A", "OMNI_OR_B"]
    assert not marker.exists()


def test_or_group_satisfied_runs_scenario_despite_missing_and(tmp_path):
    # I2 end-to-end: a resolved OR member configures a missing-AND scenario.
    _write(tmp_path, "or-ok.yaml", _scenario(
        "or-ok", requires_env="[OMNI_OR_AND_MISSING]",
        requires_env_any="[OMNI_OR_PROVIDED, OMNI_OR_OTHER]",
        steps=_cli_steps("true")))
    sc = run_scenarios(
        tmp_path,
        env={"OMNI_OR_PROVIDED": "1", "PATH": os.environ.get("PATH", "")},
        persist=False,
    ).scenarios[0]
    assert sc.status == "passed"
    assert sc.missing_env == []


# ---------------------------------------------------------------------------
# Recovery (guide §2.6: only a passing recovery call flips a step green)
# ---------------------------------------------------------------------------

RECOVERY_YAML = """
name: recoverable
description: "primary fails, recovery fixes it"
steps:
  - name: "fail step"
    kind: cli
    command: "false"
    expect:
      success: true
    recovery_steps:
      - name: "recover"
        kind: cli
        command: "true"
        expect:
          success: true
"""


def test_recovery_turns_failed_step_recovered(tmp_path):
    _write(tmp_path, "recover.yaml", RECOVERY_YAML)
    sc = run_scenarios(tmp_path, persist=False).scenarios[0]
    assert sc.status == "recovered"
    rec = sc.steps[0]
    assert rec["status"] == "recovered"
    assert rec["passed"] is True
    assert rec["recovery_status"] == "passed"
    assert len(rec["recovery"]) == 1
    assert rec["recovery"][0]["passed"] is True


def test_recovery_records_preserve_red(tmp_path):
    # RED is never erased (guide §4.5): the primary grade still shows the
    # failure even though the step is treated green for the verdict.
    _write(tmp_path, "recover.yaml", RECOVERY_YAML)
    rec = run_scenarios(tmp_path, persist=False).scenarios[0].steps[0]
    assert rec["grade"]["passed"] is False
    assert rec["actual"]["success"] is False
    assert rec["actual"]["exit_code"] == 1


def test_recovery_failure_stays_failed(tmp_path):
    _write(tmp_path, "recover.yaml",
           RECOVERY_YAML.replace('command: "true"', 'command: "false"'))
    sc = run_scenarios(tmp_path, persist=False).scenarios[0]
    assert sc.status == "failed"
    rec = sc.steps[0]
    assert rec["status"] == "failed"
    assert rec["passed"] is False
    assert rec["recovery_status"] == "failed"


def test_no_recovery_attempted_on_pass(tmp_path):
    _write(tmp_path, "recover.yaml",
           RECOVERY_YAML.replace('command: "false"', 'command: "true"'))
    rec = run_scenarios(tmp_path, persist=False).scenarios[0].steps[0]
    assert rec["passed"] is True
    assert rec["recovery"] == []
    assert rec["recovery_status"] is None


def test_recovered_counts_as_succeeded_for_partial_pass(tmp_path):
    _write(tmp_path, "mixed.yaml", """
name: mixed
description: "recovered step counts toward the partial-pass bar"
min_passing: 2
steps:
  - name: "ok"
    kind: cli
    command: "true"
    expect:
      success: true
  - name: "fail then recover"
    kind: cli
    command: "false"
    expect:
      success: true
    recovery_steps:
      - name: "recover"
        kind: cli
        command: "true"
        expect:
          success: true
  - name: "boom"
    kind: cli
    command: "false"
    expect:
      success: true
""")
    sc = run_scenarios(tmp_path, persist=False).scenarios[0]
    assert sc.status == "partial-pass"
    assert [s["status"] for s in sc.steps] == ["passed", "recovered", "failed"]


# ---------------------------------------------------------------------------
# Partial-pass policy (guide §2.7)
# ---------------------------------------------------------------------------


def test_min_passing_met_partial_pass(tmp_path):
    _write(tmp_path, "mixed.yaml",
           _scenario("mixed", min_passing=2, steps=_cli_steps("true", "true", "false")))
    assert run_scenarios(tmp_path, persist=False).scenarios[0].status == "partial-pass"


def test_min_passing_not_met_failed(tmp_path):
    _write(tmp_path, "mixed.yaml",
           _scenario("mixed", min_passing=3, steps=_cli_steps("true", "true", "false")))
    assert run_scenarios(tmp_path, persist=False).scenarios[0].status == "failed"


def test_pass_ratio_met_partial_pass(tmp_path):
    _write(tmp_path, "mixed.yaml",
           _scenario("mixed", pass_ratio=0.5, steps=_cli_steps("true", "true", "false")))
    assert run_scenarios(tmp_path, persist=False).scenarios[0].status == "partial-pass"


def test_pass_ratio_not_met_failed(tmp_path):
    _write(tmp_path, "mixed.yaml",
           _scenario("mixed", pass_ratio=0.75, steps=_cli_steps("true", "true", "false")))
    assert run_scenarios(tmp_path, persist=False).scenarios[0].status == "failed"


def test_all_pass_ignores_policy_returns_passed(tmp_path):
    _write(tmp_path, "mixed.yaml",
           _scenario("mixed", min_passing=2, steps=_cli_steps("true", "true")))
    assert run_scenarios(tmp_path, persist=False).scenarios[0].status == "passed"


# ---------------------------------------------------------------------------
# Cleanup (guide §2.6: best-effort, never affects the verdict)
# ---------------------------------------------------------------------------


def test_cleanup_runs_and_does_not_affect_verdict(tmp_path):
    marker = tmp_path / "cleaned.txt"
    cleanup = (f'  - name: "cleanup"\n    kind: cli\n    command: "touch {marker}"\n'
               "    expect:\n      success: true")
    _write(tmp_path, "c.yaml", _scenario("c", steps=_cli_steps("true"), cleanup_steps=cleanup))
    sc = run_scenarios(tmp_path, persist=False).scenarios[0]
    assert sc.status == "passed"
    assert marker.exists()
    assert len(sc.cleanup) == 1
    assert sc.cleanup[0]["passed"] is True


def test_cleanup_failure_does_not_fail_scenario(tmp_path):
    cleanup = ('  - name: "cleanup"\n    kind: cli\n    command: "false"\n'
               "    expect:\n      success: true")
    _write(tmp_path, "c.yaml", _scenario("c", steps=_cli_steps("true"), cleanup_steps=cleanup))
    sc = run_scenarios(tmp_path, persist=False).scenarios[0]
    assert sc.status == "passed"
    assert sc.cleanup[0]["passed"] is False


def test_cleanup_runs_after_failed_scenario(tmp_path):
    marker = tmp_path / "cleaned.txt"
    cleanup = (f'  - name: "cleanup"\n    kind: cli\n    command: "touch {marker}"\n'
               "    expect:\n      success: true")
    _write(tmp_path, "c.yaml", _scenario("c", steps=_cli_steps("false"), cleanup_steps=cleanup))
    sc = run_scenarios(tmp_path, persist=False).scenarios[0]
    assert sc.status == "failed"
    assert marker.exists()


# ---------------------------------------------------------------------------
# Trace (guide §3.1 phase 5: step_index / duration / arguments / trace_id)
# ---------------------------------------------------------------------------


def test_step_trace_fields(tmp_path):
    _write(tmp_path, "t.yaml", _scenario("t", steps=_cli_steps("true")))
    run = run_scenarios(tmp_path, persist=False)
    rec = run.scenarios[0].steps[0]
    assert rec["step_index"] == 1
    assert isinstance(rec["duration_seconds"], float) and rec["duration_seconds"] >= 0
    assert rec["arguments"] == {"command": "true"}
    assert rec["trace_id"] == run.trace_id
    assert rec["surface"] == "cli: true"
    assert rec["real_call"] == "true"
    assert rec["expect"] == {"success": True}
    assert rec["actual"]["success"] is True
    assert rec["passed"] is True
    assert rec["status"] == "passed"
    grade = rec["grade"]
    assert grade["passed"] is True
    assert grade["checks"][0]["name"] == "success"
    assert grade["reason"]


def test_same_trace_id_all_steps_one_run(tmp_path):
    # One UUID per run, threaded into every step (guide §3.1 phase 5).
    _write(tmp_path, "t.yaml", _scenario("t", steps=_cli_steps("true", "true")))
    run = run_scenarios(tmp_path, persist=False)
    recs = run.scenarios[0].steps
    assert len({r["trace_id"] for r in recs}) == 1
    assert run.trace_id == recs[0]["trace_id"]
    assert uuid.UUID(run.trace_id)  # valid uuid4


def test_trace_id_differs_between_runs(tmp_path):
    _write(tmp_path, "t.yaml", _scenario("t", steps=_cli_steps("true")))
    r1 = run_scenarios(tmp_path, persist=False)
    r2 = run_scenarios(tmp_path, persist=False)
    assert r1.trace_id != r2.trace_id


def test_step_index_1_based(tmp_path):
    _write(tmp_path, "t.yaml", _scenario("t", steps=_cli_steps("true", "true", "true")))
    recs = run_scenarios(tmp_path, persist=False).scenarios[0].steps
    assert [r["step_index"] for r in recs] == [1, 2, 3]


def test_arguments_echo_mcp(tmp_path):
    # mcp steps echo their arguments dict; the call goes through the real
    # in-process dispatcher (os.getenv — stdlib, no component imports).
    _write(tmp_path, "m.yaml", """
name: mcp-echo
description: "mcp step arguments echo"
steps:
  - name: "getenv"
    kind: mcp
    tool: os.getenv
    arguments: {key: PATH}
    expect:
      success: true
""")
    rec = run_scenarios(tmp_path, persist=False).scenarios[0].steps[0]
    assert rec["arguments"] == {"key": "PATH"}
    assert rec["passed"] is True


def test_arguments_echo_cli(tmp_path):
    _write(tmp_path, "t.yaml", _scenario("t", steps=_cli_steps("true")))
    rec = run_scenarios(tmp_path, persist=False).scenarios[0].steps[0]
    assert rec["arguments"] == {"command": "true"}


def test_cli_stderr_lands_in_scenario_record(tmp_path):
    """e2e-test-suite#174: a CLI step's stderr is persisted in the scenario
    record — OL writes its ``WARNING: N of M unit(s) ... untranslated`` to
    stderr, and the harness must keep it visible (never stdout-only).  Both
    the in-memory step record and the persisted scenarios.json carry it."""
    runs = tmp_path / "runs"
    _write(tmp_path, "warn.yaml", """
name: warn
description: "cli stderr is persisted in the scenario record"
steps:
  - name: "warn"
    kind: cli
    command: |-
      sh -c "echo OL-WARNING 2-of-6-untranslated 1>&2"
    expect:
      exit_code: 0
      stderr_has: ["OL-WARNING"]
""")
    run = run_scenarios(tmp_path, runs_dir=runs, persist=True)
    rec = run.scenarios[0].steps[0]
    assert run.scenarios[0].status == "passed"
    assert "OL-WARNING" in rec["actual"]["stderr"]
    payload = json.loads((runs / run.run_id / "scenarios.json").read_text(encoding="utf-8"))
    persisted = payload["scenarios"][0]["steps"][0]["actual"]
    assert "OL-WARNING" in persisted["stderr"]


def test_timeout_step_failed_with_timeout_flag(tmp_path):
    # Dispatch already records timeouts as failed steps (timeout: True in
    # the actual block) — the engine propagates that, no extra work.  The
    # step status is the distinct "timeout" (issue #176); the scenario
    # verdict stays "failed".
    _write(tmp_path, "slow.yaml", """
name: slow
description: "step exceeds its timeout"
steps:
  - name: "sleepy"
    kind: cli
    command: "sleep 5"
    timeout_seconds: 1
    expect:
      success: true
""")
    sc = run_scenarios(tmp_path, persist=False).scenarios[0]
    rec = sc.steps[0]
    assert rec["passed"] is False
    assert rec["status"] == "timeout"
    assert rec["timed_out"] is True
    assert sc.status == "failed"
    assert rec["actual"].get("timeout") is True
    assert "timed out" in rec["actual"].get("error", "")


def test_timeout_and_assertion_failure_are_distinct(tmp_path):
    """A timeout and an assertion failure share the failed scenario verdict
    but are distinguishable per step: ``timeout`` vs ``failed``, with the
    timeout count called out in the scenario summary (issue #176)."""
    _write(tmp_path, "mixed.yaml", """
name: mixed
description: "one assertion failure, one timeout"
steps:
  - name: "assert-fail"
    kind: cli
    command: "false"
    expect:
      success: true
  - name: "slow"
    kind: cli
    command: "sleep 5"
    timeout_seconds: 1
    expect:
      success: true
""")
    sc = run_scenarios(tmp_path, persist=False).scenarios[0]
    assert sc.status == "failed"
    assert [s["status"] for s in sc.steps] == ["failed", "timeout"]
    assert [s["timed_out"] for s in sc.steps] == [False, True]
    assert "1 timed out" in sc.summary


def test_step_timeout_env_override_applied(tmp_path, monkeypatch):
    """OMNI_VALIDATION_STEP_TIMEOUT_S lets a slow step finish without
    editing the scenario: a 2s command capped at 1s passes once the env var
    raises the cap (issue #176)."""
    monkeypatch.setenv("OMNI_VALIDATION_STEP_TIMEOUT_S", "5")
    _write(tmp_path, "slow.yaml", """
name: slow-ok
description: "env override raises the step cap"
steps:
  - name: "sleepy"
    kind: cli
    command: "sleep 2"
    timeout_seconds: 1
    expect:
      success: true
""")
    sc = run_scenarios(tmp_path, persist=False).scenarios[0]
    assert sc.status == "passed"
    assert sc.steps[0]["status"] == "passed"


def test_run_scenarios_step_timeout_argument_applied(tmp_path):
    """The explicit step_timeout argument (the --step-timeout plumbing)
    overrides a step's too-small cap."""
    _write(tmp_path, "slow.yaml", """
name: slow-opt
description: "explicit step_timeout raises the cap"
steps:
  - name: "sleepy"
    kind: cli
    command: "sleep 2"
    timeout_seconds: 1
    expect:
      success: true
""")
    sc = run_scenarios(
        tmp_path, persist=False, step_timeout=5
    ).scenarios[0]
    assert sc.status == "passed"


# ---------------------------------------------------------------------------
# Throttled / stalled cause statuses (issue #194)
# ---------------------------------------------------------------------------


def test_rate_limited_cli_step_status_throttled(tmp_path):
    """A failed cli step whose stderr names a 429/RateLimitError is
    ``throttled``, not a bare assertion failure — and the scenario still
    fails (throttling is never a pass)."""
    _write(tmp_path, "throttled.yaml", """
name: throttled
description: "router exhausted the rate-limit retry chain"
steps:
  - name: "translate under rate limit"
    kind: cli
    command: |-
      sh -c "echo 'litellm.RateLimitError: Error code: 429 - rate limited' 1>&2; exit 1"
    expect:
      success: true
""")
    sc = run_scenarios(tmp_path, persist=False).scenarios[0]
    rec = sc.steps[0]
    assert rec["status"] == "throttled"
    assert rec["throttled"] is True
    assert rec["passed"] is False
    assert sc.status == "failed"
    assert "1 throttled" in sc.summary


def test_rate_limited_mcp_record_status_throttled(tmp_path, monkeypatch):
    """An in-process mcp step carries the exception text in ``error`` — a
    429 there is throttled too."""
    import omni_mcp.validation.engine as engine

    _write(tmp_path, "throttled-mcp.yaml", """
name: throttled-mcp
description: "mcp tool raised a rate limit"
steps:
  - name: "call a tool"
    kind: mcp
    tool: ping
    arguments: {}
    expect:
      success: true
""")

    def fake_dispatch(step, env=None, step_timeout=None):
        return StepResult(
            surface="mcp: ping",
            real_call="ping({})",
            expect=dict(step.get("expect") or {}),
            actual={
                "success": False,
                "error": "litellm.RateLimitError: Error code: 429",
            },
            artifact_to_show=None,
            standard=step.get("standard"),
            duration_seconds=0.01,
        )

    monkeypatch.setattr(engine, "dispatch_step", fake_dispatch)
    sc = engine.run_scenarios(tmp_path, persist=False).scenarios[0]
    assert sc.steps[0]["status"] == "throttled"
    assert sc.steps[0]["throttled"] is True
    assert sc.status == "failed"


def test_passed_step_never_reclassified_as_throttled(tmp_path):
    """A passing step that merely mentions 429 in its output is still
    ``passed`` — the cause statuses never override success."""
    _write(tmp_path, "passing.yaml", """
name: passing-with-429
description: "a retry log line on a successful step"
steps:
  - name: "retried then succeeded"
    kind: cli
    command: |-
      sh -c "echo 'retrying after 429' 1>&2; exit 0"
    expect:
      success: true
""")
    sc = run_scenarios(tmp_path, persist=False).scenarios[0]
    rec = sc.steps[0]
    assert rec["status"] == "passed"
    assert rec["passed"] is True
    assert rec["throttled"] is False


def test_throttled_wins_over_timeout(tmp_path):
    """A step that both timed out and carried a rate-limit signature is
    reported as throttled — the actionable cause wins."""
    _write(tmp_path, "both.yaml", """
name: both
description: "rate limited and slow"
steps:
  - name: "slow and throttled"
    kind: cli
    command: |-
      sh -c "echo 'litellm.RateLimitError: 429' 1>&2; sleep 5"
    timeout_seconds: 1
    expect:
      success: true
""")
    sc = run_scenarios(tmp_path, persist=False).scenarios[0]
    rec = sc.steps[0]
    assert rec["timed_out"] is True
    assert rec["status"] == "throttled"
    assert sc.status == "failed"


def test_stalled_step_status(tmp_path, monkeypatch):
    """``actual.stalled: true`` classifies a failed step as ``stalled``."""
    import omni_mcp.validation.engine as engine

    _write(tmp_path, "stalled.yaml", """
name: stalled
description: "a subprocess went silent"
steps:
  - name: "silent subprocess"
    kind: cli
    command: "true"
    expect:
      success: true
""")

    def fake_dispatch(step, env=None, step_timeout=None):
        return StepResult(
            surface="cli: true",
            real_call="true",
            expect=dict(step.get("expect") or {}),
            actual={
                "success": False,
                "exit_code": 1,
                "stdout": "",
                "stderr": "",
                "stalled": True,
                "error": "no output for 180s (stall cap)",
            },
            artifact_to_show=None,
            standard=step.get("standard"),
            duration_seconds=180.0,
        )

    monkeypatch.setattr(engine, "dispatch_step", fake_dispatch)
    sc = engine.run_scenarios(tmp_path, persist=False).scenarios[0]
    assert sc.steps[0]["status"] == "stalled"
    assert sc.steps[0]["stalled"] is True
    assert sc.status == "failed"


def test_step_status_precedence_unit():
    """The status precedence: passed > known-gap > throttled > stalled >
    timeout > failed."""
    assert _step_status(False, True, True, True, True) == "passed"
    assert _step_status(True, False, True, True, True) == "known-gap"
    assert _step_status(False, False, True, True, True) == "throttled"
    assert _step_status(False, False, True, False, True) == "stalled"
    assert _step_status(False, False, True) == "timeout"
    assert _step_status(False, False) == "failed"


def test_is_throttled_matches_stderr_error_stdout():
    assert _is_throttled({"stderr": "litellm.RateLimitError: 429"}) is True
    assert _is_throttled({"error": "Error code: 429"}) is True
    assert _is_throttled({"stdout": "ratelimiterror raised"}) is True
    assert _is_throttled({"throttled": True}) is True
    assert _is_throttled({"stderr": "error code 14290"}) is False
    assert _is_throttled({"stderr": "assertion mismatch"}) is False


def test_summary_counts_throttled_and_stalled(tmp_path, monkeypatch):
    """A mixed failing scenario calls out both new cause counts without
    disturbing the existing timed-out / known-gap suffix order."""
    import omni_mcp.validation.engine as engine

    _write(tmp_path, "mixed-causes.yaml", """
name: mixed-causes
description: "throttled + stalled + assertion failure"
steps:
  - name: "throttled"
    kind: cli
    command: "true"
    expect:
      success: true
  - name: "stalled"
    kind: cli
    command: "true"
    expect:
      success: true
  - name: "assert-fail"
    kind: cli
    command: "false"
    expect:
      success: true
""")

    actuals = {
        "throttled": {"success": False, "stderr": "litellm.RateLimitError: Error code: 429"},
        "stalled": {"success": False, "error": "no output for 180s", "stalled": True},
        "assert-fail": {"success": False, "exit_code": 1, "stderr": "", "error": "exit 1"},
    }

    def fake_dispatch(step, env=None, step_timeout=None):
        return StepResult(
            surface=f"cli: {step['name']}",
            real_call="x",
            expect=dict(step.get("expect") or {}),
            actual=actuals[step["name"]],
            artifact_to_show=None,
            standard=step.get("standard"),
            duration_seconds=0.01,
        )

    monkeypatch.setattr(engine, "dispatch_step", fake_dispatch)
    sc = engine.run_scenarios(tmp_path, persist=False).scenarios[0]
    assert sc.status == "failed"
    assert "1 throttled" in sc.summary
    assert "1 stalled" in sc.summary


# ---------------------------------------------------------------------------
# Persistence (phase 6)
# ---------------------------------------------------------------------------


def test_persist_writes_run_dir_and_latest(tmp_path):
    runs = tmp_path / "validation-runs"
    _write(tmp_path, "p.yaml", _scenario("p", steps=_cli_steps("true")))
    run = run_scenarios(tmp_path, runs_dir=runs, persist=True)
    assert run.run_id
    run_dir = runs / run.run_id
    assert run_dir.is_dir()
    payload = json.loads((run_dir / "scenarios.json").read_text(encoding="utf-8"))
    assert payload["trace_id"] == run.trace_id
    assert payload["run_id"] == run.run_id
    assert payload["scenarios"][0]["status"] == "passed"
    assert (runs / "latest.txt").read_text(encoding="utf-8").strip() == run.run_id


def test_persist_creates_runs_dir(tmp_path):
    runs = tmp_path / "does" / "not" / "exist"
    _write(tmp_path, "p.yaml", _scenario("p", steps=_cli_steps("true")))
    run = run_scenarios(tmp_path, runs_dir=runs, persist=True)
    assert (runs / run.run_id / "scenarios.json").is_file()


def test_persist_record_content_deep(tmp_path):
    marker = tmp_path / "cleaned.txt"
    cleanup = (f'  - name: "cleanup"\n    kind: cli\n    command: "touch {marker}"\n'
               "    expect:\n      success: true")
    runs = tmp_path / "runs"
    _write(tmp_path, "gated.yaml",
           _scenario("gated", requires_env=f"[{MISSING_VAR}]", steps=_cli_steps("true")))
    _write(tmp_path, "plain.yaml",
           _scenario("plain", steps=_cli_steps("true"), cleanup_steps=cleanup))
    run = run_scenarios(tmp_path, runs_dir=runs, persist=True)
    payload = json.loads((runs / run.run_id / "scenarios.json").read_text(encoding="utf-8"))
    by_name = {s["name"]: s for s in payload["scenarios"]}
    assert by_name["gated"]["status"] == "unconfigured"
    assert by_name["gated"]["missing_env"] == [MISSING_VAR]
    assert by_name["plain"]["missing_env"] == []
    rec = by_name["plain"]["steps"][0]
    assert rec["trace_id"] == payload["trace_id"]
    assert rec["grade"]["passed"] is True
    assert rec["grade"]["checks"][0]["name"] == "success"
    assert rec["duration_seconds"] >= 0
    assert by_name["plain"]["cleanup"][0]["step_index"] == 0


def test_latest_points_to_newest_run(tmp_path):
    runs = tmp_path / "runs"
    _write(tmp_path, "a.yaml", _scenario("a", steps=_cli_steps("true")))
    r1 = run_scenarios(tmp_path, runs_dir=runs, persist=True)
    r2 = run_scenarios(tmp_path, runs_dir=runs, persist=True)
    assert (runs / "latest.txt").read_text(encoding="utf-8").strip() == r2.run_id
    assert r1.run_id != r2.run_id


def test_persist_default_runs_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, "a.yaml", _scenario("a", steps=_cli_steps("true")))
    run = run_scenarios(tmp_path, persist=True)  # default runs_dir=validation-runs
    assert (tmp_path / "validation-runs" / run.run_id / "scenarios.json").is_file()


def test_same_second_runs_get_distinct_dirs(tmp_path, monkeypatch):
    # Runs are immutable — a same-second collision gets a suffix instead of
    # overwriting (guide §3.1 phase 6 "immutable, written once").
    import omni_mcp.validation.engine as engine

    runs = tmp_path / "runs"
    _write(tmp_path, "a.yaml", _scenario("a", steps=_cli_steps("true")))
    monkeypatch.setattr(engine.time, "strftime", lambda fmt: "20260814-120000")
    r1 = persist_run(run_scenarios(tmp_path, persist=False), runs_dir=runs)
    r2 = persist_run(run_scenarios(tmp_path, persist=False), runs_dir=runs)
    assert r1.name != r2.name
    assert r1.is_dir() and r2.is_dir()
    assert (runs / "latest.txt").read_text(encoding="utf-8").strip() == r2.name


def test_run_result_to_dict_json_serializable(tmp_path):
    _write(tmp_path, "a.yaml", _scenario("a", steps=_cli_steps("true")))
    run = run_scenarios(tmp_path, persist=False)
    json.dumps(run.to_dict())  # must not raise


def test_run_scenarios_returns_run_result(tmp_path):
    _write(tmp_path, "a.yaml", _scenario("a", steps=_cli_steps("true")))
    run = run_scenarios(tmp_path, persist=False)
    assert isinstance(run, RunResult)
    assert isinstance(run.scenarios[0], ScenarioResult)
    assert run.timestamp


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


def test_filters_subset_by_name(tmp_path):
    _write(tmp_path, "a.yaml", _scenario("alpha", steps=_cli_steps("true")))
    _write(tmp_path, "b.yaml", _scenario("beta", steps=_cli_steps("false")))
    run = run_scenarios(tmp_path, filters=["alpha"], persist=False)
    assert [s.name for s in run.scenarios] == ["alpha"]
    assert run.scenarios[0].status == "passed"


def test_filters_none_runs_all(tmp_path):
    _write(tmp_path, "a.yaml", _scenario("alpha", steps=_cli_steps("true")))
    _write(tmp_path, "b.yaml", _scenario("beta", steps=_cli_steps("true")))
    run = run_scenarios(tmp_path, persist=False)
    assert {s.name for s in run.scenarios} == {"alpha", "beta"}


def test_filters_accepts_single_string(tmp_path):
    _write(tmp_path, "a.yaml", _scenario("alpha", steps=_cli_steps("true")))
    _write(tmp_path, "b.yaml", _scenario("beta", steps=_cli_steps("true")))
    run = run_scenarios(tmp_path, filters="beta", persist=False)
    assert [s.name for s in run.scenarios] == ["beta"]


# ---------------------------------------------------------------------------
# Load-time rejection is loud (guide §2.4) — the engine propagates it
# ---------------------------------------------------------------------------


def test_malformed_scenario_raises_scenario_error(tmp_path):
    _write(tmp_path, "bad.yaml", "name: nope\nsteps: []\n")
    with pytest.raises(ScenarioError):
        run_scenarios(tmp_path, persist=False)


# ---------------------------------------------------------------------------
# run_meta — component versions + git SHAs (OPP#58 per-repo delivery)
# ---------------------------------------------------------------------------


def test_collect_run_meta_has_suite_keys_and_repo_entries():
    """collect_run_meta(['suite','opp','ol','orf']) returns the suite
    version/sha, a per-component {version, sha} entry for every repo, and
    the ``repos`` list — the block the diff/report tools consume."""
    from omni_mcp.validation.engine import collect_run_meta

    meta = collect_run_meta(["suite", "opp", "ol", "orf"])

    assert "suite_version" in meta and meta["suite_version"] != "unknown"
    assert "suite_sha" in meta and meta["suite_sha"] != "unknown"
    for repo in ("opp", "ol", "orf"):
        assert repo in meta
        assert meta[repo]["version"] != "unknown"
        assert meta[repo]["sha"] != "unknown"
    assert meta["repos"] == ["opp", "ol", "orf"]  # suite is not re-listed


def test_persist_run_payload_includes_run_meta(tmp_path):
    """persist_run writes the run_meta block into scenarios.json — the
    per-repo delivery and the version base-selector read it from there."""
    runs = tmp_path / "runs"
    _write(tmp_path, "p.yaml", _scenario("p", steps=_cli_steps("true")))
    run = run_scenarios(tmp_path, runs_dir=runs, persist=True)
    payload = json.loads((runs / run.run_id / "scenarios.json").read_text(encoding="utf-8"))
    assert "run_meta" in payload
    assert payload["run_meta"]["suite_version"] != "unknown"
    assert "repos" in payload["run_meta"]


def test_run_scenarios_run_meta_auto_collected_single_dir(tmp_path):
    """run_scenarios('scenarios') auto-populates run_meta — the suite
    version/sha are present without any explicit run_meta argument."""
    _write(tmp_path, "a.yaml", _scenario("a", steps=_cli_steps("true")))
    run = run_scenarios(str(tmp_path), persist=False)
    assert run.run_meta["suite_version"] != "unknown"
    assert run.run_meta["suite_sha"] != "unknown"
    assert run.run_meta["repos"] == []


def test_run_scenarios_run_meta_auto_collected_component_dir(tmp_path):
    """With a component scenario dir, run_meta carries the repo key —
    ``_dirs_to_repo_keys`` maps the path shape to the component."""
    scn = tmp_path / "Omni_Pre_Processor" / "scenarios"
    scn.mkdir(parents=True)
    _write(scn, "opp-a.yaml", _scenario("opp-a", steps=_cli_steps("true")))
    run = run_scenarios(str(scn), persist=False)
    assert "opp" in run.run_meta
    assert run.run_meta["opp"]["version"] != "unknown"
    assert run.run_meta["repos"] == ["opp"]


def test_collect_run_meta_never_raises_on_missing_repo_dir(monkeypatch):
    """A component dir that does not exist must never raise — the version
    falls back to 'unknown' (guarded never-raises contract, OPP#58)."""
    from omni_mcp.validation import engine

    monkeypatch.setattr(engine, "_COMPONENT_DIRS", {"opp": engine._SUITE_ROOT / "Definitely_Missing_Component"})
    meta = engine.collect_run_meta(["opp"])
    assert meta["opp"] == {"version": "unknown", "sha": "unknown"}
    assert meta["suite_version"] != "unknown"  # suite part still collected


def test_run_scenarios_accepts_list_of_dirs(tmp_path):
    """A list of scenario dirs concatenates the loaded scenarios in order
    — dir1's scenarios before dir2's (per-repo merge, OPP#58)."""
    d1 = tmp_path / "one"
    d2 = tmp_path / "two"
    d1.mkdir()
    d2.mkdir()
    _write(d1, "a.yaml", _scenario("alpha", steps=_cli_steps("true")))
    _write(d2, "b.yaml", _scenario("beta", steps=_cli_steps("true")))
    run = run_scenarios([str(d1), str(d2)], persist=False)
    assert [s.name for s in run.scenarios] == ["alpha", "beta"]


# ---------------------------------------------------------------------------
# persist_run bytes-safety backstop (e2e-test-suite#184)
# ---------------------------------------------------------------------------


def _run_with_actual(actual):
    """A one-scenario RunResult whose only step carries *actual*."""
    step = {
        "step_index": 1,
        "surface": "cli: opp",
        "real_call": {"command": "opp x"},
        "expect": {"success": True},
        "actual": actual,
        "artifact_to_show": None,
    }
    scn = ScenarioResult(
        name="s",
        status="failed",
        summary="timed out",
        missing_env=[],
        steps=[step],
        cleanup=[],
        trace_id="trace",
    )
    return RunResult(
        trace_id="trace",
        timestamp="2026-01-01T00:00:00",
        scenarios=[scn],
    )


def test_persist_run_sanitizes_bytes_in_actual(tmp_path):
    """A step whose ``actual`` carries raw ``bytes`` (the post-timeout shape
    of issue #184) must still persist — bytes degrade to a decoded string so
    an entire run is never lost to one non-serialisable field."""
    runs = tmp_path / "runs"
    run = _run_with_actual({"success": False, "timeout": True, "stdout": b"partial"})
    run_dir = persist_run(run, runs_dir=runs)

    payload = json.loads((run_dir / "scenarios.json").read_text(encoding="utf-8"))
    stdout = payload["scenarios"][0]["steps"][0]["actual"]["stdout"]
    assert isinstance(stdout, str)
    assert stdout == "partial"
    assert (runs / "latest.txt").read_text(encoding="utf-8").strip() == run_dir.name


def test_sanitize_for_json_recurses_and_reports_paths():
    """The sanitizer recurses through dict/list, decodes bytes, stringifies
    unknown objects, and records the degraded field's path."""
    from omni_mcp.validation.engine import _sanitize_for_json

    problems = []
    out = _sanitize_for_json(
        {"scenarios": [{"steps": [{"actual": {"stdout": b"\xffpartial"}}]}]},
        "",
        problems,
    )
    assert out["scenarios"][0]["steps"][0]["actual"]["stdout"] == "\ufffdpartial"
    json.dumps(out)  # must not raise
    assert any("stdout" in p for p in problems)
