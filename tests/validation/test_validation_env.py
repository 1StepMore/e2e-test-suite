"""Tests for the runner's default sandbox allowlist (issue e2e-test-suite#229).

Tier-1 is documented as "no keys hermetic"; these tests lock the other half
of that promise: no manual path-allowlist exports either.  The runner (the
caller layer) fills the module servers' fail-closed allowlist vars with a
suite-root + tempdir sandbox when unset, and never overwrites an explicit
operator value.  The dispatcher itself stays inject-free (D4).
"""

import os
import tempfile
from pathlib import Path

import pytest

import omni_mcp.validation.cli as cli
from omni_mcp.validation.cli import (
    ALLOWLIST_ENV_VARS,
    allowed_dirs_default,
    build_validation_env,
    check_allowlist_covers_sandbox,
    format_allowlist_problem,
)
from omni_mcp.validation.dispatch import SUITE_ROOT

VALID = """\
name: sample
description: "hermetic scenario that declares an allowlist need"
tier: 1
level: agent-user
requires_env: [MCP_ALLOWED_DIRECTORIES]
steps:
  - name: "one"
    kind: cli
    command: "true"
    expect:
      success: true
"""


_ALL_PRECEDENCE_VARS = tuple(
    dict.fromkeys(
        [
            *ALLOWLIST_ENV_VARS,
            "OMNI_MCP_ALLOWED_DIRS",
            "OL_ALLOWED_DIRECTORIES",
        ]
    )
)


def _clear_allowlists(monkeypatch):
    for name in _ALL_PRECEDENCE_VARS:
        monkeypatch.delenv(name, raising=False)


def test_build_validation_env_defaults_all_five_when_absent(monkeypatch):
    _clear_allowlists(monkeypatch)
    monkeypatch.delenv("OMNI_TEST_FAKE_LLM", raising=False)

    env = build_validation_env()

    for name in ALLOWLIST_ENV_VARS:
        assert env[name] == allowed_dirs_default()
    assert "OMNI_TEST_FAKE_LLM" not in env


def test_build_validation_env_neither_injects_nor_strips_fake_llm(monkeypatch):
    """CI exports OMNI_TEST_FAKE_LLM=1 for its smoke gates; the runner must
    carry it through (the engine needs it to mark human-quality runs
    invalid) and must never add it when absent (D4)."""
    _clear_allowlists(monkeypatch)
    monkeypatch.setenv("OMNI_TEST_FAKE_LLM", "1")
    assert build_validation_env()["OMNI_TEST_FAKE_LLM"] == "1"

    monkeypatch.delenv("OMNI_TEST_FAKE_LLM", raising=False)
    assert "OMNI_TEST_FAKE_LLM" not in build_validation_env()


def test_build_validation_env_preserves_explicit_value_verbatim(monkeypatch):
    _clear_allowlists(monkeypatch)
    monkeypatch.setenv(
        "MCP_ALLOWED_DIRECTORIES", "/explicit/only/path"
    )

    env = build_validation_env()

    assert env["MCP_ALLOWED_DIRECTORIES"] == "/explicit/only/path"
    for name in ALLOWLIST_ENV_VARS[1:]:
        assert env[name] == allowed_dirs_default()


def test_default_value_contains_suite_root_and_tempdir():
    value = allowed_dirs_default()

    assert value == f"{SUITE_ROOT}{os.pathsep}{tempfile.gettempdir()}"
    assert str(SUITE_ROOT) in value
    assert tempfile.gettempdir() in value


class _FakeRun:
    run_id = "run-test"
    trace_id = "trace-test"
    run_dir = None
    scenarios: list = []


def test_main_passes_defaulted_env_and_records_it(tmp_path, monkeypatch, capsys):
    _clear_allowlists(monkeypatch)
    (tmp_path / "sample.yaml").write_text(VALID, encoding="utf-8")
    captured: dict = {}

    def fake_run_scenarios(dirs, **kwargs):
        captured["dirs"] = dirs
        captured.update(kwargs)
        return _FakeRun()

    monkeypatch.setattr(cli, "run_scenarios", fake_run_scenarios)
    monkeypatch.setattr(
        cli, "collect_run_meta", lambda repos: {"suite_version": "test-meta"}
    )

    rc = cli.main([
        "--scenario", "sample",
        "--scenarios-dir", str(tmp_path),
        "--runs-dir", str(tmp_path / "runs"),
    ])

    assert rc == 0
    for name in ALLOWLIST_ENV_VARS:
        assert captured["env"][name] == allowed_dirs_default()
    recorded = captured["run_meta"]["validation_env"]
    assert recorded["allowed_dirs_defaulted"] == list(ALLOWLIST_ENV_VARS)
    assert recorded["allowed_dirs_value"] == allowed_dirs_default()
    assert captured["run_meta"]["suite_version"] == "test-meta"


def test_main_explicit_value_wins_and_is_not_recorded_as_defaulted(
    tmp_path, monkeypatch, capsys
):
    _clear_allowlists(monkeypatch)
    explicit = f"/operator/value{os.pathsep}{allowed_dirs_default()}"
    monkeypatch.setenv("ORF_MCP_ALLOWED_DIRS", explicit)
    (tmp_path / "sample.yaml").write_text(VALID, encoding="utf-8")
    captured: dict = {}

    def fake_run_scenarios(dirs, **kwargs):
        captured.update(kwargs)
        return _FakeRun()

    monkeypatch.setattr(cli, "run_scenarios", fake_run_scenarios)
    monkeypatch.setattr(cli, "collect_run_meta", lambda repos: {})

    rc = cli.main([
        "--scenario", "sample",
        "--scenarios-dir", str(tmp_path),
        "--runs-dir", str(tmp_path / "runs"),
    ])

    assert rc == 0
    assert captured["env"]["ORF_MCP_ALLOWED_DIRS"] == explicit
    defaulted = captured["run_meta"]["validation_env"]["allowed_dirs_defaulted"]
    assert "ORF_MCP_ALLOWED_DIRS" not in defaulted
    assert set(defaulted) == set(ALLOWLIST_ENV_VARS) - {"ORF_MCP_ALLOWED_DIRS"}


@pytest.mark.parametrize("name", ALLOWLIST_ENV_VARS)
def test_existing_value_never_overwritten(name, monkeypatch):
    _clear_allowlists(monkeypatch)
    monkeypatch.setenv(name, "/kept")

    assert build_validation_env()[name] == "/kept"


@pytest.mark.parametrize("name", ALLOWLIST_ENV_VARS)
def test_empty_value_defaults_like_unset(name, monkeypatch):
    """Empty counts as missing, matching the engine's env gate."""
    _clear_allowlists(monkeypatch)
    monkeypatch.setenv(name, "")

    assert build_validation_env()[name] == allowed_dirs_default()


def test_requires_env_gate_passes_with_defaulted_env(tmp_path, monkeypatch):
    """A scenario declaring the allowlist need runs instead of unconfigured."""
    from omni_mcp.validation.engine import run_scenarios

    _clear_allowlists(monkeypatch)
    (tmp_path / "sample.yaml").write_text(VALID, encoding="utf-8")

    run = run_scenarios(
        tmp_path,
        env=build_validation_env(),
        runs_dir=tmp_path / "runs",
        persist=False,
    )

    assert run.scenarios[0].status == "passed"
    assert run.scenarios[0].missing_env == []


def test_preflight_narrow_unified_allowlist_reports_failure_and_hint(
    tmp_path, monkeypatch
):
    _clear_allowlists(monkeypatch)
    narrow = str(tmp_path)
    monkeypatch.setenv("MCP_ALLOWED_DIRECTORIES", narrow)

    problems = check_allowlist_covers_sandbox()

    assert [p["variable"] for p in problems] == ["MCP_ALLOWED_DIRECTORIES"]
    problem = problems[0]
    missing = {str(p) for p in problem["missing"]}
    assert missing == {str(Path(tempfile.gettempdir()).resolve())}
    hint = format_allowlist_problem(problem)
    assert "offending variable: MCP_ALLOWED_DIRECTORIES" in hint
    assert f"current value:      {narrow}" in hint
    assert f"fix: export MCP_ALLOWED_DIRECTORIES=\"{narrow}{os.pathsep}" in hint
    assert "PATH_DENIED" in hint


def test_preflight_unified_allowlist_with_tempdir_alone_passes(
    tmp_path, monkeypatch
):
    """The shipped CI config: ``MCP_ALLOWED_DIRECTORIES=/tmp`` must not abort."""
    _clear_allowlists(monkeypatch)
    monkeypatch.setenv("MCP_ALLOWED_DIRECTORIES", tempfile.gettempdir())

    assert check_allowlist_covers_sandbox() == []


def test_preflight_unset_allowlists_pass(monkeypatch):
    _clear_allowlists(monkeypatch)

    assert check_allowlist_covers_sandbox() == []


def test_preflight_module_specific_narrow_allowlist_fails(tmp_path, monkeypatch):
    _clear_allowlists(monkeypatch)
    monkeypatch.setenv("ORF_MCP_ALLOWED_DIRS", str(tmp_path))

    problems = check_allowlist_covers_sandbox()

    assert [p["variable"] for p in problems] == ["ORF_MCP_ALLOWED_DIRS"]
    assert "fix: export ORF_MCP_ALLOWED_DIRS=" in format_allowlist_problem(
        problems[0]
    )


def test_preflight_unified_value_overrides_narrow_module_var(
    tmp_path, monkeypatch
):
    _clear_allowlists(monkeypatch)
    monkeypatch.setenv("MCP_ALLOWED_DIRECTORIES", allowed_dirs_default())
    monkeypatch.setenv("ORF_MCP_ALLOWED_DIRS", str(tmp_path))

    assert check_allowlist_covers_sandbox() == []


def test_preflight_does_not_abort_list_check_dry_run(tmp_path, monkeypatch):
    _clear_allowlists(monkeypatch)
    monkeypatch.setenv("MCP_ALLOWED_DIRECTORIES", str(tmp_path))
    (tmp_path / "sample.yaml").write_text(VALID, encoding="utf-8")

    assert cli.main(["--list", "--scenarios-dir", str(tmp_path)]) == 0
    assert cli.main(["--check", "--scenarios-dir", str(tmp_path)]) == 0
    assert (
        cli.main(
            [
                "--dry-run",
                "--scenarios-dir",
                str(tmp_path),
                "--runs-dir",
                str(tmp_path / "runs"),
            ]
        )
        == 0
    )


def test_main_narrow_allowlist_fails_fast_without_dispatching(
    tmp_path, monkeypatch, capsys
):
    _clear_allowlists(monkeypatch)
    narrow = str(tmp_path)
    monkeypatch.setenv("MCP_ALLOWED_DIRECTORIES", narrow)
    (tmp_path / "sample.yaml").write_text(VALID, encoding="utf-8")
    calls = {"n": 0}

    def fake_run_scenarios(dirs, **kwargs):
        calls["n"] += 1
        return _FakeRun()

    monkeypatch.setattr(cli, "run_scenarios", fake_run_scenarios)

    rc = cli.main(
        [
            "--scenario",
            "sample",
            "--scenarios-dir",
            str(tmp_path),
            "--runs-dir",
            str(tmp_path / "runs"),
        ]
    )

    assert rc == 1
    assert calls["n"] == 0
    err = capsys.readouterr().err
    assert err.count("validation preflight failed") == 1
    assert "offending variable: MCP_ALLOWED_DIRECTORIES" in err
    assert f"fix: export MCP_ALLOWED_DIRECTORIES=\"{narrow}{os.pathsep}" in err
