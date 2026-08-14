"""Tests for omni_mcp.validation.loader (guide §2 schema, §3 load phase).

The loader is phase 1 of the engine: recursive glob over ``scenarios/**``,
PyYAML ``safe_load``, and schema validation per the guide §2 contract.
Load-time rejection is loud by design (guide §2.4): a malformed scenario
raises ``ScenarioError`` naming the file and the rule violated — never
silently skipped, never counted as coverage.
"""

import textwrap

import pytest

from omni_mcp.validation.loader import (
    ScenarioError,
    load_scenarios,
    validate_scenario,
)

# The smallest complete scenario per guide §2.8: 3 steps (cli/mcp/python),
# each with its own expect block; exercises every optional field family
# the loader must accept (partial-pass, regression, instructions, standard).
VALID_SCENARIO = """
name: sample-e2e
description: "A valid 3-step scenario exercising all schema families"
category: pipeline
requires_env: [TEST_DB_URL]
requires_http: true
min_passing: 2
pass_ratio: 0.67
regression: false
regression_issue: null
instructions: |
  Drive the CLI, call the MCP ping tool in-process, then run a python snippet.
steps:
  - name: "CLI step"
    kind: cli
    command: "opp --version"
    timeout_seconds: 30
    standard: STANDARDS.md#exit-codes
    instructions: "Check the version prints and exits 0."
    expect:
      success: true
      exit_code: 0
      stdout_has: ["opp"]
    recovery_steps:
      - name: "Recover"
        kind: cli
        command: "true"
        expect:
          success: true
    collect_artifacts:
      - path: "artifacts/version.log"
        required: true
  - name: "MCP step"
    kind: mcp
    tool: ping
    arguments: {}
    expect:
      success: true
  - name: "Python step"
    kind: python
    command: "print('ok')"
    expect:
      success: true
      stdout_has: ["ok"]
cleanup_steps:
  - name: "Cleanup"
    kind: cli
    command: "rm -f /tmp/sample-e2e.log"
    expect:
      success: true
"""


def _write(tmp_path, name, body):
    """Write a scenario YAML file, creating parent dirs."""
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_load_scenarios_returns_validated_scenarios(tmp_path):
    _write(tmp_path, "sample.yaml", VALID_SCENARIO)

    scenarios = load_scenarios(tmp_path)

    assert len(scenarios) == 1
    s = scenarios[0]
    assert s["name"] == "sample-e2e"
    assert s["description"] == "A valid 3-step scenario exercising all schema families"
    assert len(s["steps"]) == 3
    assert s["steps"][0]["kind"] == "cli"
    assert s["steps"][1]["kind"] == "mcp"
    assert s["steps"][1]["tool"] == "ping"
    assert s["steps"][2]["kind"] == "python"


def test_load_scenarios_recursive_glob_picks_up_nested_files(tmp_path):
    """Guide §3.1 phase 1: the glob is the registration mechanism."""
    _write(tmp_path, "regression/t2-pdf-guard.yaml", VALID_SCENARIO)
    _write(tmp_path, "opp/docx.yaml", VALID_SCENARIO.replace("sample-e2e", "opp-docx"))

    scenarios = load_scenarios(tmp_path)

    assert [s["name"] for s in scenarios] == ["opp-docx", "sample-e2e"]  # sorted


def test_load_scenarios_skips_dot_dirs(tmp_path):
    _write(tmp_path, ".hidden/bad.yaml", "name: hidden\n")  # invalid: no steps
    _write(tmp_path, "good.yaml", VALID_SCENARIO)

    scenarios = load_scenarios(tmp_path)

    assert len(scenarios) == 1
    assert scenarios[0]["name"] == "sample-e2e"


def test_load_scenarios_empty_library_returns_empty_list(tmp_path):
    """scenarios/ has only .gitkeep until Wave 3 — 0 scenarios, no crash."""
    assert load_scenarios(tmp_path) == []
    assert load_scenarios(tmp_path / "does-not-exist") == []


def test_defaults_applied_for_optional_fields(tmp_path):
    minimal = """
    name: minimal
    description: "Smallest possible scenario"
    steps:
      - name: "one"
        kind: cli
        command: "true"
        expect:
          success: true
      - name: "two"
        kind: mcp
        tool: ping
        expect:
          success: true
    """
    _write(tmp_path, "minimal.yaml", minimal)

    s = load_scenarios(tmp_path)[0]

    assert s["category"] == "general"
    assert s["requires_env"] == []
    assert s["requires_http"] is False
    assert s["cleanup_steps"] == []
    assert s["steps"][0]["recovery_steps"] == []
    assert s["steps"][1]["arguments"] == {}  # mcp steps default to empty arguments


def test_validate_scenario_standalone(tmp_path):
    """Expose validate_scenario(scenario, path) for reuse by contract lint."""
    data = {
        "name": "standalone",
        "description": "validated directly, not via glob",
        "steps": [{"kind": "cli", "command": "true", "expect": {"success": True}}],
    }

    out = validate_scenario(data, tmp_path / "standalone.yaml")

    assert out["name"] == "standalone"
    assert out["category"] == "general"


# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("missing", ["name", "description", "steps"])
def test_missing_required_field_rejected(tmp_path, missing):
    body = VALID_SCENARIO
    if missing == "name":
        body = body.replace("name: sample-e2e\n", "")
    elif missing == "description":
        body = body.replace(
            'description: "A valid 3-step scenario exercising all schema families"\n', ""
        )
    else:
        body = body.split("steps:", 1)[0]  # drop the steps block entirely
    path = _write(tmp_path, "bad.yaml", body)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)

    assert str(path) in str(ei.value)  # error names the FILE
    assert f"'{missing}'" in str(ei.value)  # and the RULE


def test_steps_must_be_non_empty_list(tmp_path):
    _write(tmp_path, "empty-steps.yaml", """
    name: empty
    description: "no steps"
    steps: []
    """)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "steps" in str(ei.value) and "non-empty" in str(ei.value)


def test_scenario_must_be_a_mapping(tmp_path):
    _write(tmp_path, "list.yaml", "- just\n- a list\n")

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "mapping" in str(ei.value)


def test_malformed_yaml_rejected(tmp_path):
    _write(tmp_path, "broken.yaml", "name: [unclosed\n")

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "parse" in str(ei.value).lower()


# ---------------------------------------------------------------------------
# Step validation — expect is the mandatory heart (guide §2.2/§2.4)
# ---------------------------------------------------------------------------


def test_step_without_expect_rejected(tmp_path):
    """A step without an expect block cannot be graded (guide §2.4)."""
    body = VALID_SCENARIO.replace(
        "    expect:\n      success: true\n      stdout_has: [\"ok\"]\n",
        "    command: \"echo hi\"\n",
    )
    _write(tmp_path, "no-expect.yaml", body)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    # "scenarios/...: step 3 missing 'expect'"
    assert "step 3" in str(ei.value) and "expect" in str(ei.value)


def test_step_with_empty_expect_rejected(tmp_path):
    """An empty expect block is not falsifiable — rejected at load time."""
    _write(tmp_path, "empty-expect.yaml", """
    name: empty-expect
    description: "expect block must be non-empty"
    steps:
      - name: "one"
        kind: cli
        command: "true"
        expect: {}
    """)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "expect" in str(ei.value)


def test_step_missing_kind_rejected(tmp_path):
    _write(tmp_path, "no-kind.yaml", """
    name: no-kind
    description: "kind is required per step (guide §2.4)"
    steps:
      - name: "one"
        command: "true"
        expect:
          success: true
    """)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "kind" in str(ei.value)


@pytest.mark.parametrize("bad_kind", ["http", "rest", "tool", "SOAP", 42])
def test_kind_must_be_mcp_cli_python(tmp_path, bad_kind):
    _write(tmp_path, "bad-kind.yaml", f"""
    name: bad-kind
    description: "kind must be one of mcp|cli|python"
    steps:
      - name: "one"
        kind: {bad_kind!r}
        command: "true"
        expect:
          success: true
    """)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "mcp" in str(ei.value) and "cli" in str(ei.value)


def test_mcp_step_requires_tool(tmp_path):
    _write(tmp_path, "mcp-no-tool.yaml", """
    name: mcp-no-tool
    description: "mcp-kind steps must name their tool"
    steps:
      - name: "one"
        kind: mcp
        expect:
          success: true
    """)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "tool" in str(ei.value)


def test_cli_step_requires_command(tmp_path):
    _write(tmp_path, "cli-no-command.yaml", """
    name: cli-no-command
    description: "cli-kind steps must carry a command"
    steps:
      - name: "one"
        kind: cli
        expect:
          success: true
    """)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "command" in str(ei.value)


def test_python_step_requires_command(tmp_path):
    _write(tmp_path, "py-no-command.yaml", """
    name: py-no-command
    description: "python-kind steps must carry a command"
    steps:
      - name: "one"
        kind: python
        expect:
          success: true
    """)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "command" in str(ei.value)


def test_timeout_seconds_must_be_positive_number(tmp_path):
    _write(tmp_path, "bad-timeout.yaml", """
    name: bad-timeout
    description: "timeout_seconds must be a positive number"
    steps:
      - name: "one"
        kind: cli
        command: "true"
        timeout_seconds: -5
        expect:
          success: true
    """)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "timeout_seconds" in str(ei.value)


# ---------------------------------------------------------------------------
# Nested steps: recovery_steps / cleanup_steps are steps too (guide §2.2)
# ---------------------------------------------------------------------------


def test_recovery_steps_validated_like_steps(tmp_path):
    _write(tmp_path, "bad-recovery.yaml", """
    name: bad-recovery
    description: "recovery steps must be falsifiable too"
    steps:
      - name: "one"
        kind: cli
        command: "false"
        expect:
          success: true
        recovery_steps:
          - name: "recover"
            kind: cli
            command: "true"
    """)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "recovery" in str(ei.value) and "expect" in str(ei.value)


def test_cleanup_steps_validated_like_steps(tmp_path):
    _write(tmp_path, "bad-cleanup.yaml", """
    name: bad-cleanup
    description: "cleanup steps must be falsifiable too"
    steps:
      - name: "one"
        kind: cli
        command: "true"
        expect:
          success: true
    cleanup_steps:
      - name: "cleanup"
        kind: cli
        command: "rm -f x"
    """)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "cleanup" in str(ei.value) and "expect" in str(ei.value)


# ---------------------------------------------------------------------------
# Header field types (guide §2.4 closed field set)
# ---------------------------------------------------------------------------


def test_requires_env_must_be_list_of_str(tmp_path):
    _write(tmp_path, "bad-env.yaml", """
    name: bad-env
    description: "requires_env must be a list of strings"
    requires_env: "TEST_DB_URL"
    steps:
      - name: "one"
        kind: cli
        command: "true"
        expect:
          success: true
    """)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "requires_env" in str(ei.value)


def test_requires_env_members_must_be_str(tmp_path):
    _write(tmp_path, "bad-env-member.yaml", """
    name: bad-env-member
    description: "requires_env members must be strings"
    requires_env: [42]
    steps:
      - name: "one"
        kind: cli
        command: "true"
        expect:
          success: true
    """)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "requires_env" in str(ei.value)


def test_requires_http_must_be_bool(tmp_path):
    _write(tmp_path, "bad-http.yaml", """
    name: bad-http
    description: "requires_http is a flag"
    requires_http: "yes"
    steps:
      - name: "one"
        kind: cli
        command: "true"
        expect:
          success: true
    """)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "requires_http" in str(ei.value)


def test_min_passing_must_be_positive_int(tmp_path):
    _write(tmp_path, "bad-min.yaml", """
    name: bad-min
    description: "min_passing must be a positive int"
    min_passing: 0
    steps:
      - name: "one"
        kind: cli
        command: "true"
        expect:
          success: true
    """)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "min_passing" in str(ei.value)


def test_pass_ratio_must_be_float_in_open_unit(tmp_path):
    _write(tmp_path, "bad-ratio.yaml", """
    name: bad-ratio
    description: "pass_ratio must be a float in (0, 1]"
    pass_ratio: 1.5
    steps:
      - name: "one"
        kind: cli
        command: "true"
        expect:
          success: true
    """)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "pass_ratio" in str(ei.value)


def test_regression_true_requires_regression_issue(tmp_path):
    """Guide §2.1: ``regression: true`` + ``regression_issue`` pin a bug."""
    _write(tmp_path, "bad-regression.yaml", """
    name: bad-regression
    description: "regression scenarios must pin a bug reference"
    regression: true
    steps:
      - name: "one"
        kind: cli
        command: "true"
        expect:
          success: true
    """)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "regression_issue" in str(ei.value)


def test_regression_pair_accepted(tmp_path):
    _write(tmp_path, "regression.yaml", """
    name: regression-collect-int-id
    description: "regression #104: int item ids survive"
    regression: true
    regression_issue: "#104"
    steps:
      - name: "one"
        kind: cli
        command: "true"
        expect:
          success: true
    """)

    s = load_scenarios(tmp_path)[0]
    assert s["regression"] is True
    assert s["regression_issue"] == "#104"


def test_unknown_top_level_field_rejected(tmp_path):
    """Guide §2.4: an unrecognized key is a typo in waiting — reject it."""
    _write(tmp_path, "typo.yaml", """
    name: typo
    description: "typo field"
    stepz: []
    """)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "stepz" in str(ei.value)


def test_unknown_step_field_rejected(tmp_path):
    _write(tmp_path, "step-typo.yaml", """
    name: step-typo
    description: "typo in step field"
    steps:
      - name: "one"
        kind: cli
        command: "true"
        expct:
          success: true
    """)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "expct" in str(ei.value)


# ---------------------------------------------------------------------------
# D12 fields: instructions + standard citations ride alongside the schema
# ---------------------------------------------------------------------------


def test_instructions_and_standard_accepted(tmp_path):
    """D12: per-scenario instructions + per-step standard citations."""
    _write(tmp_path, "d12.yaml", VALID_SCENARIO)

    s = load_scenarios(tmp_path)[0]

    assert "Drive the CLI" in s["instructions"]
    assert s["steps"][0]["standard"] == "STANDARDS.md#exit-codes"
    assert s["steps"][0]["instructions"] == "Check the version prints and exits 0."


def test_standard_must_be_string(tmp_path):
    _write(tmp_path, "bad-standard.yaml", """
    name: bad-standard
    description: "standard citations are opaque strings (resolved by lint)"
    steps:
      - name: "one"
        kind: cli
        command: "true"
        standard: ["STANDARDS.md#exit-codes"]
        expect:
          success: true
    """)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "standard" in str(ei.value)


def test_collect_artifacts_entries_need_path(tmp_path):
    _write(tmp_path, "bad-artifact.yaml", """
    name: bad-artifact
    description: "collect_artifacts entries carry a path"
    steps:
      - name: "one"
        kind: cli
        command: "true"
        expect:
          success: true
        collect_artifacts:
          - required: true
    """)

    with pytest.raises(ScenarioError) as ei:
        load_scenarios(tmp_path)
    assert "path" in str(ei.value)


# ---------------------------------------------------------------------------
# Error object contract
# ---------------------------------------------------------------------------


def test_scenario_error_carries_file_and_rule():
    err = ScenarioError("scenarios/opp/bad.yaml", "step 2 missing 'expect'")

    assert err.path == "scenarios/opp/bad.yaml"
    assert err.rule == "step 2 missing 'expect'"
    assert str(err) == "scenarios/opp/bad.yaml: step 2 missing 'expect'"
    assert isinstance(err, ValueError)


def test_load_scenarios_is_deterministic_order(tmp_path):
    for i, name in enumerate(["a.yaml", "b.yaml", "c.yaml"]):
        _write(tmp_path, name, VALID_SCENARIO.replace("sample-e2e", f"scen-{i}"))

    names = [s["name"] for s in load_scenarios(tmp_path)]

    assert names == ["scen-0", "scen-1", "scen-2"]  # sorted by file path


def test_smoke_valid_three_step_scenario_loads_at_least_one(tmp_path):
    """Task acceptance: a temp-dir valid 3-step scenario loads ≥ 1."""
    _write(tmp_path, "smoke.yaml", VALID_SCENARIO)

    assert len(load_scenarios(tmp_path)) >= 1


# ---------------------------------------------------------------------------
# Tier model (plan todo 9): optional scenario-level 1|2|3, default 1
# ---------------------------------------------------------------------------


def test_tier_field_accepted_with_default_1(tmp_path):
    """AutoInfo tier model: 1 = no keys hermetic, 2 = LLM key,
    3 = paid/external/network; the field is optional, default 1."""
    _write(tmp_path, "tiered.yaml", """
    name: tiered
    description: "tier 2 scenario"
    tier: 2
    steps:
      - name: "one"
        kind: cli
        command: "true"
        expect:
          success: true
    """)
    _write(tmp_path, "plain.yaml", VALID_SCENARIO.replace("sample-e2e", "plain-tier"))

    by_name = {s["name"]: s for s in load_scenarios(tmp_path)}

    assert by_name["tiered"]["tier"] == 2
    assert by_name["plain-tier"]["tier"] == 1  # default when omitted


def test_tier_field_must_be_an_integer_in_1_2_3(tmp_path):
    """Reject strings, out-of-range ints, floats, and bools (bool is an
    int subclass — ``tier: true`` must not silently mean 1)."""
    bad_values = [
        ("string", '"2"'),
        ("zero", 0),
        ("four", 4),
        ("float", 2.5),
        ("bool", True),
    ]
    for case, bad in bad_values:
        case_dir = tmp_path / f"case-{case}"
        _write(case_dir, "bad.yaml", f"""
        name: bad-tier
        description: "tier must be an integer in 1|2|3"
        tier: {bad}
        steps:
          - name: "one"
            kind: cli
            command: "true"
            expect:
              success: true
        """)
        with pytest.raises(ScenarioError) as ei:
            load_scenarios(case_dir)
        assert "tier" in str(ei.value)
