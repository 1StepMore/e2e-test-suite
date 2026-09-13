"""Tests for the X-04 transport-parity path in omni_mcp.validation.dispatch.

X-04 (P0): the in-process ``_run_mcp_step`` adapter never exercised the real
MCP transport (stdio/schema/auth), so every agent-surface "MCP pass" was
unproven.  ``run_transport_parity`` starts each module's REAL MCP server over
stdio (fastmcp Client + StdioTransport against the shipped ``mcp``-library
servers) and compares every tool's protocol response against the in-process
call of the same function.  Divergence fails.

TDD RED-first: every test here drives the parity path; the all-41 test is the
F2 acceptance ("parity suite covers all 41 live tools and fails on
divergence") and is marked ``slow`` because it boots all four servers
(OL's import chain alone is ~30-40s).

Parity semantics (documented in dispatch.py):
- ``success`` must agree between in-process and protocol.
- both success -> payloads compared (volatile keys ignored:
  run_id/trace_id/durations/timestamps).
- both error -> any observable error on each side counts as agreement
  (the server envelope differs from the in-process str(exc) by design).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from omni_mcp.validation.dispatch import (
    call_tool_in_process,
    run_transport_parity,
)

SUITE_ROOT = Path(__file__).resolve().parent.parent.parent

_AUDIT_PATH = SUITE_ROOT / "scripts" / "validation" / "coverage_audit.py"


def _load_audit():
    """Import scripts/validation/coverage_audit.py from its file path."""
    spec = importlib.util.spec_from_file_location("coverage_audit", _AUDIT_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["coverage_audit"] = mod
    spec.loader.exec_module(mod)
    return mod


audit = _load_audit()


# ---------------------------------------------------------------------------
# In-process reference call — OL Pydantic-model tools included
# ---------------------------------------------------------------------------


def test_call_tool_in_process_ol_ping():
    """call_tool_in_process resolves OL tools through TOOL_REGISTRY (including
    the no-model ``ping``) and returns the normalized success envelope."""
    result = call_tool_in_process("ol", "ping", {})
    assert result["success"] is True
    data = result.get("data")
    assert isinstance(data, dict)
    assert data.get("success") is True
    assert data["content"].get("module") == "ol"


def test_call_tool_in_process_ol_model_tool_accepts_flat_args():
    """OL model-taking tools (e.g. inspect_config — no required fields) accept
    a flat arguments dict in-process: the model is constructed, not kwargs."""
    result = call_tool_in_process("ol", "inspect_config", {})
    assert "success" in result  # either clean success or clean error — never a raise
    if result["success"]:
        assert "data" in result


def test_call_tool_in_process_unknown_tool_is_clean_error():
    result = call_tool_in_process("ol", "definitely_not_a_tool", {})
    assert result["success"] is False
    assert "definitely_not_a_tool" in result["error"]


# ---------------------------------------------------------------------------
# Divergence detection (X-04: "divergence fails")
# ---------------------------------------------------------------------------


def test_parity_fails_on_divergence(monkeypatch):
    """A deliberately broken tool (in-process function diverges from the real
    server subprocess) yields equal=False / lands in diverged()."""
    import opp.mcp.server as opp_server

    def broken_ping(**kwargs):  # returns a DIFFERENT payload than the real tool
        return {"success": True, "content": {"status": "broken", "version": "0.0"}}

    monkeypatch.setattr(opp_server, "ping", broken_ping)

    report = run_transport_parity(
        {"opp": {"ping": {}}}, server_timeout=90, call_timeout=30
    )
    assert report.server_errors == {}
    (result,) = report.results
    assert result.tool == "ping"
    assert result.equal is False
    assert [r.tool for r in report.diverged()] == ["ping"]
    assert report.passed() == 0


# ---------------------------------------------------------------------------
# F2 acceptance — the parity suite covers ALL 41 live tools and passes
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_parity_covers_all_41_live_tools_and_passes():
    """The transport-parity suite covers every declared live tool (opp 9 /
    ol 21 / orf 7 / omni_mcp 4 = 41) over the REAL MCP protocol, using each
    tool's per-tool scenario arguments when the scenario declares a
    ``kind: mcp`` step, else {} — and parity holds for all 41."""
    surface = audit.load_live_surface()
    module_tools: dict[str, dict[str, dict]] = {}
    for module, tools in surface.items():
        module_tools[module] = {
            tool: audit.load_tool_arguments(SUITE_ROOT / "scenarios", module, tool)
            for tool in tools
        }

    report = run_transport_parity(module_tools, server_timeout=240, call_timeout=90)

    assert report.server_errors == {}, f"server startup failures: {report.server_errors}"
    checked = {(r.module, r.tool) for r in report.results}
    declared = {
        (module, tool) for module, tools in surface.items() for tool in tools
    }
    assert checked == declared, (
        f"parity covered {len(checked)} tools, expected all {len(declared)}"
    )
    diverged = report.diverged()
    assert diverged == [], "\n".join(
        f"  {d.module}.{d.tool}: {d.detail}" for d in diverged
    )
    assert report.passed() == 41
