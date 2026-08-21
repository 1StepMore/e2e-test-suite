"""Tests for omni_mcp.validation.engine (guide §3.1 phases 4-6, §4 honesty).

The engine is the orchestrator: load (loader.py) -> dispatch (dispatch.py)
-> grade (grader.py) -> aggregate -> trace -> persist.  These tests drive
it end-to-end with tiny cli/python steps (real subprocesses — the only
surface that needs no component imports) and assert the guide's verdict
semantics (passed | failed | unconfigured | recovered | partial-pass),
the per-step trace fields (step_index / duration_seconds / arguments /
trace_id), and the ``validation-runs/<ts>/scenarios.json`` + ``latest.txt``
persistence (guide §3.1 phase 6, AutoInfo reference :54-89).
"""

import json
import os
import textwrap
import uuid

import pytest

from omni_mcp.validation.engine import RunResult, ScenarioResult, persist_run, run_scenarios
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


def _scenario(name, *, requires_env="", min_passing=None, pass_ratio=None,
              steps="", cleanup_steps=""):
    """Build a scenario YAML body; steps default to one passing cli step."""
    head = [f"name: {name}", f'description: "{name}"']
    if requires_env:
        head.append(f"requires_env: {requires_env}")
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
    # A var present but empty counts as missing (AutoInfo :1356-1367).
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


def test_timeout_step_failed_with_timeout_flag(tmp_path):
    # Dispatch already records timeouts as failed steps (timeout: True in
    # the actual block) — the engine propagates that, no extra work.
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
    rec = run_scenarios(tmp_path, persist=False).scenarios[0].steps[0]
    assert rec["passed"] is False
    assert rec["status"] == "failed"
    assert rec["actual"].get("timeout") is True
    assert "timed out" in rec["actual"].get("error", "")


# ---------------------------------------------------------------------------
# Persistence (guide §3.1 phase 6, AutoInfo :54-89)
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
