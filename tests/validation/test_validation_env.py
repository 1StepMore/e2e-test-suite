"""Tests for the runner's default sandbox allowlist (issue e2e-test-suite#229).

Tier-1 is documented as "no keys hermetic"; these tests lock the other half
of that promise: no manual path-allowlist exports either.  The runner (the
caller layer) fills the module servers' fail-closed allowlist vars with a
suite-root + tempdir sandbox when unset, and never overwrites an explicit
operator value.  The dispatcher itself stays inject-free (D4).
"""

import os
import tempfile

import pytest

import omni_mcp.validation.cli as cli
from omni_mcp.validation.cli import (
    ALLOWLIST_ENV_VARS,
    allowed_dirs_default,
    build_validation_env,
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


def _clear_allowlists(monkeypatch):
    for name in ALLOWLIST_ENV_VARS:
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
    monkeypatch.setenv("ORF_MCP_ALLOWED_DIRS", "/operator/value")
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
    assert captured["env"]["ORF_MCP_ALLOWED_DIRS"] == "/operator/value"
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
