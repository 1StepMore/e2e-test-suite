"""Tests for omni_mcp.validation.dispatch (guide §3.2 adapter strategy, §3.1
phase 2 dispatch).

The dispatch phase turns one step into one REAL call on a surface — never a
mock (guide §4.1).  Three adapters:

- ``kind: cli``    -> subprocess against the real module CLIs (``opp``,
                      ``ol``, ``orf``, ``omni-mcp`` console scripts in
                      ``.venv_ol/bin/``)
- ``kind: mcp``    -> in-process call of the REAL module tool functions
                      (``opp.mcp.server.*``, ``ol_mcp.tools.*``,
                      ``orf.mcp.server.*`` — the same functions the MCP
                      servers expose; AGENTS.md in-process pattern, D13)
- ``kind: python`` -> subprocess python snippet via the suite venv

Every StepResult carries the five-part evidence contract (guide §1, D12):
surface / real call / expect / actual / artifact-to-show, plus the
``standard`` citation and wall-clock ``duration_seconds``.

Strict no-mocks hygiene (D4): the cli/python adapters MUST NOT inject
``OMNI_TEST_FAKE_LLM`` (or any other var) into the subprocess env — the env
is inherited from the parent.  The happy-path tests therefore call the REAL
binaries (e.g. ``opp --help``, ``orf --version``); only error paths may mock
at the subprocess boundary.
"""

import json

import pytest

from omni_mcp.validation.dispatch import (
    DEFAULT_TIMEOUT_SECONDS,
    DispatchError,
    StepResult,
    build_cli_env,
    dispatch_step,
    suite_python,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cli_step(command, **extra):
    """A minimal cli-kind step dict (loader-shape, defaults applied)."""
    step = {"kind": "cli", "command": command, "expect": {"success": True}}
    step.update(extra)
    step.setdefault("timeout_seconds", 30)
    step.setdefault("arguments", {})
    step.setdefault("recovery_steps", [])
    step.setdefault("standard", None)
    return step


def _mcp_step(tool, arguments=None, **extra):
    step = {
        "kind": "mcp",
        "tool": tool,
        "arguments": arguments or {},
        "expect": {"success": True},
    }
    step.update(extra)
    step.setdefault("timeout_seconds", 30)
    step.setdefault("recovery_steps", [])
    step.setdefault("standard", None)
    return step


def _python_step(command, **extra):
    step = {"kind": "python", "command": command, "expect": {"success": True}}
    step.update(extra)
    step.setdefault("timeout_seconds", 30)
    step.setdefault("arguments", {})
    step.setdefault("recovery_steps", [])
    step.setdefault("standard", None)
    return step


# ---------------------------------------------------------------------------
# StepResult shape — five-part evidence contract (guide §1, D12)
# ---------------------------------------------------------------------------


def test_step_result_carries_five_part_evidence():
    """Every StepResult must carry surface / real_call / expect / actual /
    artifact_to_show, plus standard citation and duration_seconds."""
    result = StepResult(
        surface="cli: opp --help",
        real_call="opp --help",
        expect={"success": True, "exit_code": 0},
        actual={"success": True, "exit_code": 0, "stdout": "usage: opp", "stderr": ""},
        artifact_to_show=None,
        standard="STANDARDS.md#exit-codes",
        duration_seconds=0.25,
    )

    assert result.surface == "cli: opp --help"
    assert result.real_call == "opp --help"
    assert result.expect == {"success": True, "exit_code": 0}
    assert result.actual["exit_code"] == 0
    assert result.artifact_to_show is None
    assert result.standard == "STANDARDS.md#exit-codes"
    assert result.duration_seconds >= 0


def test_step_result_to_dict_roundtrip():
    """The result must be JSON-serializable for the run record (phase 6)."""
    result = StepResult(
        surface="mcp: ol_mcp.tools.ping",
        real_call="ol_mcp.tools.ping()",
        expect={"success": True},
        actual={"success": True, "data": {"module": "ol"}},
        artifact_to_show=None,
        standard=None,
        duration_seconds=0.1,
    )

    payload = json.loads(json.dumps(result.to_dict()))

    assert payload["surface"] == "mcp: ol_mcp.tools.ping"
    assert payload["actual"]["data"]["module"] == "ol"
    assert "duration_seconds" in payload


# ---------------------------------------------------------------------------
# cli adapter — real binaries, env hygiene (D4)
# ---------------------------------------------------------------------------


def test_cli_opp_help_exit_zero_real_output():
    """Happy path: a cli step running the real ``opp`` CLI exits 0 and its
    stdout carries real output.  ``opp --version`` is not a real OPP flag
    (argparse rejects it, exit 2 — see test_cli_honest_exit_code_for_unknown_flag),
    so the version-equivalent help surface is used, mirroring the plan's
    QA scenario (``opp --help`` exit 0)."""
    result = dispatch_step(_cli_step("opp --help", standard="STANDARDS.md#exit-codes"))

    assert result.actual["success"] is True
    assert result.actual["exit_code"] == 0
    assert result.actual["stdout"] != ""
    assert "opp" in result.actual["stdout"].lower()
    assert result.surface == "cli: opp --help"
    assert result.real_call == "opp --help"
    assert result.standard == "STANDARDS.md#exit-codes"
    assert result.duration_seconds >= 0


def test_cli_orf_version_real_output():
    """``orf --version`` exits 0 and prints a real version string."""
    result = dispatch_step(_cli_step("orf --version"))

    assert result.actual["exit_code"] == 0
    assert "orf" in result.actual["stdout"].lower()


def test_cli_ol_version_real_output():
    """``ol --version`` exits 0 and prints a real version string.

    The OL CLI (typer) boots slowly (~30s import chain), so the step
    declares a generous timeout — the call is still the real binary."""
    result = dispatch_step(
        _cli_step("ol --version", timeout_seconds=180)
    )

    assert result.actual["exit_code"] == 0
    assert "ol" in result.actual["stdout"].lower()


def test_cli_env_never_injects_fake_llm():
    """D4 strict no-mocks: the dispatch env must NOT contain
    OMNI_TEST_FAKE_LLM (or OPP_ALLOWED_DIRECTORIES) unless the parent
    process set them.  The adapter inherits the parent env and adds
    nothing."""
    env = build_cli_env()

    assert "OMNI_TEST_FAKE_LLM" not in env
    assert "OPP_ALLOWED_DIRECTORIES" not in env
    # sanity: the venv bin dir is on PATH so bare console names resolve
    assert ".venv_ol/bin" in env.get("PATH", "")


def test_cli_honest_exit_code_for_unknown_flag():
    """`opp --version` is not a real OPP flag; the real binary exits 2 with
    an argparse error.  Dispatch must record that honestly — never fabricate
    exit 0 (guide §4.1 no-mocks: what the surface says is what we record)."""
    result = dispatch_step(_cli_step("opp --version"))

    assert result.actual["success"] is False
    assert result.actual["exit_code"] == 2
    assert "unrecognized arguments" in result.actual["stderr"]


def test_cli_failing_command_records_exit_code():
    """A failing command records its real exit code in the actual block."""
    result = dispatch_step(_cli_step("sh -c 'exit 3'"))

    assert result.actual["success"] is False
    assert result.actual["exit_code"] == 3


def test_cli_timeout_records_failure_and_timeout():
    """A step exceeding timeout_seconds is a failed step with the timeout
    recorded in actual (guide §3.1 phase 2 / §2.2 timeout_seconds)."""
    result = dispatch_step(
        _cli_step(".venv_ol/bin/python -c \"import time; time.sleep(30)\"",
                  timeout_seconds=1)
    )

    assert result.actual["success"] is False
    assert result.actual.get("timeout") is True
    assert "timed out" in result.actual.get("error", "").lower()
    assert result.duration_seconds < 10


def test_cli_unknown_binary_clear_error():
    """A step naming a binary that does not exist fails with a clear error
    naming the command (guide §3.2: 'no such surface' must fail with a clear
    reason, not fabricate a result)."""
    result = dispatch_step(_cli_step("definitely-not-a-real-binary-xyz --help"))

    assert result.actual["success"] is False
    assert "definitely-not-a-real-binary-xyz" in result.actual.get("error", "")


def test_cli_artifact_to_show_from_collect_artifacts():
    """collect_artifacts[0].path becomes the artifact_to_show field."""
    result = dispatch_step(
        _cli_step("opp --help", collect_artifacts=[{"path": "artifacts/version.log", "required": True}])
    )

    assert result.artifact_to_show == "artifacts/version.log"


# ---------------------------------------------------------------------------
# mcp adapter — in-process REAL module tool functions (D13, AGENTS.md pattern)
# ---------------------------------------------------------------------------


def test_mcp_ol_ping_in_process():
    """A kind: mcp step calling ``ol_mcp.tools.ping`` runs the REAL OL tool
    function in-process and returns its success JSON."""
    result = dispatch_step(_mcp_step("ol_mcp.tools.ping"))

    assert result.actual["success"] is True
    data = result.actual.get("data")
    assert isinstance(data, dict)
    assert data.get("success") is True  # real OL envelope (parsed from JSON)
    assert data["content"].get("module") == "ol"
    assert "version" in data["content"]
    assert result.surface == "mcp: ol_mcp.tools.ping"
    assert result.real_call == "ol_mcp.tools.ping()"


def test_mcp_opp_ping_in_process():
    """``opp.mcp.server.ping`` (async) is awaited in-process and returns the
    real OPP health envelope."""
    result = dispatch_step(_mcp_step("opp.mcp.server.ping"))

    assert result.actual["success"] is True
    content = result.actual.get("data", {}).get("content", {})
    assert content.get("status") == "ok"
    assert "version" in content


def test_mcp_orf_ping_in_process():
    """``orf.mcp.server.ping`` (sync) returns the real ORF health envelope.

    ORF's MCP tools are fail-CLOSED on ``MCP_ALLOWED_DIRECTORIES``
    (ORF_AGENTS.md env table); with the allowlist set (as any ORF MCP server
    run requires) the real tool answers."""
    env = build_cli_env()
    env["MCP_ALLOWED_DIRECTORIES"] = "/tmp"
    result = dispatch_step(_mcp_step("orf.mcp.server.ping"), env=env)

    assert result.actual["success"] is True
    data = result.actual.get("data")
    assert isinstance(data, dict)
    assert data["content"].get("module") == "orf"


def test_mcp_nonexistent_tool_raises_clear_error():
    """A tool that does not exist raises a clear DispatchError NAMING the
    tool (feeds the #error-clarity standard)."""
    with pytest.raises(DispatchError) as ei:
        dispatch_step(_mcp_step("ol_mcp.tools.definitely_not_a_tool"))

    assert "ol_mcp.tools.definitely_not_a_tool" in str(ei.value)


def test_mcp_nonexistent_module_raises_clear_error():
    """A tool whose module does not resolve raises a clear DispatchError
    naming the tool reference."""
    with pytest.raises(DispatchError) as ei:
        dispatch_step(_mcp_step("ol_mcp.no_such_module.ping"))

    assert "ol_mcp.no_such_module.ping" in str(ei.value)


def test_mcp_tool_exception_is_captured_not_raised():
    """A real tool that fails (bad arguments / uninitialized server) returns
    a failed result with the error captured — the dispatch envelope is still
    structured (guide §3.3: ``except Exception -> {"success": False,
    "error": ...}`` or the tool's own error envelope)."""
    env = build_cli_env()
    env["MCP_ALLOWED_DIRECTORIES"] = "/tmp"
    result = dispatch_step(
        _mcp_step(
            "opp.mcp.server.extract_document",
            {"file_path": "/nonexistent/does-not-exist.docx", "output_formats": ["md"]},
        ),
        env=env,
    )

    assert result.actual["success"] is False
    # the real tool's error envelope surfaces somewhere in actual
    assert "error" in result.actual.get("data", {}) or result.actual.get("error")
    assert json.dumps(result.actual) != ""


# ---------------------------------------------------------------------------
# python adapter — subprocess snippet in the suite venv
# ---------------------------------------------------------------------------


def test_python_snippet_runs_in_suite_venv():
    """A kind: python step runs the snippet as a subprocess and captures
    stdout; the interpreter is the suite venv python (.venv_ol/bin/python)."""
    result = dispatch_step(
        _python_step("import sys; print('python-ok', sys.version.split()[0])")
    )

    assert result.actual["exit_code"] == 0
    assert "python-ok" in result.actual["stdout"]
    assert result.surface == "python: import sys; print('python-ok', sys.version.split()[0])"
    assert result.actual["python"].endswith(".venv_ol/bin/python")


def test_python_failing_snippet_records_exit_code():
    """A snippet that exits non-zero records its real exit code."""
    result = dispatch_step(_python_step("raise SystemExit(7)"))

    assert result.actual["success"] is False
    assert result.actual["exit_code"] == 7


def test_python_timeout_records_failure():
    """timeout_seconds applies to python-kind steps too."""
    result = dispatch_step(
        _python_step("import time; time.sleep(30)", timeout_seconds=1)
    )

    assert result.actual["success"] is False
    assert result.actual.get("timeout") is True


# ---------------------------------------------------------------------------
# Dispatch table + defaults
# ---------------------------------------------------------------------------


def test_dispatch_unknown_kind_raises():
    """A step naming an undeclared surface fails loudly (guide §3.2) —
    dispatch defends its own boundary even though the loader already
    restricts kind to mcp|cli|python."""
    with pytest.raises(DispatchError) as ei:
        dispatch_step({"kind": "http", "command": "GET /", "expect": {}})

    assert "http" in str(ei.value)


def test_default_timeout_is_a_positive_number():
    assert isinstance(DEFAULT_TIMEOUT_SECONDS, (int, float))
    assert DEFAULT_TIMEOUT_SECONDS > 0


def test_suite_python_resolves_to_venv():
    """suite_python() points at the suite venv interpreter used for
    python-kind snippets (the task requirement)."""
    p = suite_python()
    assert p.endswith(".venv_ol/bin/python")
