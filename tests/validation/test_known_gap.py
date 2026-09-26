"""T-17 known-gap isolation.

A scenario (or a single step) marked ``known_gap: true`` asserts a bar the
pipeline cannot yet meet.  The marker is meaningful, not decorative:

- the scenario verdict is ``known-gap`` (never GREEN, never a failure), so
  it never drives a nonzero exit and never lands in the blockers;
- a step-level ``known_gap`` failure is excluded from its scenario's
  verdict (the strict gate still runs and is recorded, but the scenario
  stays green);
- the contract lint enforces the location invariant: ``known_gap: true``
  lives ONLY under a ``known-gaps/`` directory, and every file under
  ``known-gaps/`` declares the flag — a weakened bar can never be silently
  left in the pass-bar library.
"""

import textwrap

from omni_mcp.validation.cli import lint_scenarios, main
from omni_mcp.validation.engine import run_scenarios
from omni_mcp.validation.loader import ScenarioError, load_scenarios

import pytest


def _write(tmp_path, name, body):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


_KNOWN_GAP = """
name: pipeline-sample-known-gap
description: "known gap — published bar not met"
known_gap: true
level: human-quality
tier: 2
steps:
  - name: "strict bar (expected to fail)"
    kind: cli
    command: "false"
    expect:
      success: true
"""

_PASSING = """
name: sample
description: "passing"
level: agent-user
steps:
  - name: "one"
    kind: cli
    command: "true"
    expect:
      success: true
"""


def test_loader_accepts_known_gap_scenario_field(tmp_path):
    _write(tmp_path, "known-gaps/gap.yaml", _KNOWN_GAP)
    loaded = load_scenarios(tmp_path)
    assert loaded[0]["known_gap"] is True


def test_loader_defaults_known_gap_false(tmp_path):
    _write(tmp_path, "pass.yaml", _PASSING)
    assert load_scenarios(tmp_path)[0]["known_gap"] is False


def test_loader_rejects_non_bool_scenario_known_gap(tmp_path):
    _write(
        tmp_path,
        "known-gaps/bad.yaml",
        "name: bad\ndescription: bad\nknown_gap: yes-please\nsteps:\n"
        '  - name: "one"\n    kind: cli\n    command: "true"\n'
        "    expect:\n      success: true\n",
    )
    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "known_gap" in str(ei.value)


def test_loader_accepts_step_known_gap_and_rejects_non_bool(tmp_path):
    body = _write(
        tmp_path,
        "step-gap.yaml",
        "name: step-gap\ndescription: step gap\nsteps:\n"
        '  - name: "strict"\n    kind: cli\n    command: "false"\n'
        "    known_gap: true\n    expect:\n      success: true\n",
    )
    assert load_scenarios(tmp_path)[0]["steps"][0]["known_gap"] is True

    body.write_text(
        'name: step-gap\ndescription: step gap\nsteps:\n'
        '  - name: "strict"\n    kind: cli\n    command: "false"\n'
        '    known_gap: "maybe"\n    expect:\n      success: true\n',
        encoding="utf-8",
    )
    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "known_gap" in str(ei.value)


def test_scenario_known_gap_status_is_known_gap(tmp_path, monkeypatch):
    """A known-gap scenario is ``known-gap`` when it really runs.

    The verdict is also gated by the R-07 fake guard, so pin the environment
    instead of inheriting it: with no fake active the declared non-verdict is
    ``known-gap``; with ``OMNI_TEST_FAKE_LLM=1`` the same human-quality
    scenario is fallback output, which STANDARDS.md D4 makes ``invalid`` — a
    fake-active run is never admissible evidence, not even for a known gap.

    Both halves are asserted so neither rule can start silently overriding the
    other (this test previously inherited the caller's env, so it passed on a
    developer shell and failed under the hermetic CI job).
    """
    _write(tmp_path, "known-gaps/gap.yaml", _KNOWN_GAP)

    monkeypatch.delenv("OMNI_TEST_FAKE_LLM", raising=False)
    sc = run_scenarios(tmp_path, persist=False).scenarios[0]
    assert sc.status == "known-gap", sc.summary
    assert sc.known_gap is True

    monkeypatch.setenv("OMNI_TEST_FAKE_LLM", "1")
    fake_sc = run_scenarios(tmp_path, persist=False).scenarios[0]
    assert fake_sc.status == "invalid", fake_sc.summary
    assert "OMNI_TEST_FAKE_LLM=1" in fake_sc.summary


def test_step_known_gap_failure_does_not_fail_scenario(tmp_path):
    _write(
        tmp_path,
        "step-gap.yaml",
        "name: step-gap\ndescription: step gap\nsteps:\n"
        '  - name: "strict (published bar)"\n    kind: cli\n    command: "false"\n'
        "    known_gap: true\n    expect:\n      success: true\n"
        '  - name: "meetable"\n    kind: cli\n    command: "true"\n'
        "    expect:\n      success: true\n",
    )
    run = run_scenarios(tmp_path, persist=False)
    sc = run.scenarios[0]
    assert sc.status == "passed"
    assert sc.known_gap is False
    assert sc.steps[0]["known_gap"] is True
    assert sc.steps[0]["status"] == "known-gap"


def test_cli_known_gap_only_failure_exits_zero(tmp_path, capsys):
    _write(tmp_path, "known-gaps/gap.yaml", _KNOWN_GAP)
    code = main(
        ["--scenarios-dir", str(tmp_path), "--runs-dir", str(tmp_path / "runs")]
    )
    assert code == 0
    assert "known-gap" in capsys.readouterr().out


def test_cli_plain_failure_still_exits_one(tmp_path, capsys):
    _write(
        tmp_path,
        "fail.yaml",
        "name: fail\ndescription: fail\nsteps:\n"
        '  - name: "one"\n    kind: cli\n    command: "false"\n'
        "    expect:\n      success: true\n",
    )
    code = main(
        ["--scenarios-dir", str(tmp_path), "--runs-dir", str(tmp_path / "runs")]
    )
    assert code == 1


def test_lint_rejects_known_gap_outside_known_gaps_dir(tmp_path):
    _write(tmp_path, "gap.yaml", _KNOWN_GAP)
    findings = lint_scenarios(tmp_path)
    assert any(f.rule == "known-gap-location" for f in findings)


def test_lint_rejects_known_gaps_dir_without_marker(tmp_path):
    _write(tmp_path, "known-gaps/not-marked.yaml", _PASSING)
    findings = lint_scenarios(tmp_path)
    assert any(f.rule == "known-gap-location" for f in findings)


def test_lint_accepts_marked_known_gap_in_known_gaps_dir(tmp_path):
    _write(tmp_path, "known-gaps/gap.yaml", _KNOWN_GAP)
    assert lint_scenarios(tmp_path) == []
