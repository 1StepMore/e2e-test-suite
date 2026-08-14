"""Tests for the suite-level validation MCP tools (plan todo 20).

RED-first: written BEFORE ``omni_mcp/server.py`` gained the two tools.
Both tools dispatch to the REAL validation engine — the scenario library
comes from ``omni_mcp/validation/loader.py::load_scenarios`` and the run
orchestrator is ``omni_mcp/validation/engine.py::run_scenarios`` — through
the server's in-process ``_call_tool`` handler.  No mocks, no FAKE_LLM.

Covered surfaces:

- surface: ``_TOOL_SCHEMAS`` / ``_TOOL_DISPATCH`` gain both tools (4 total)
- happy list: real loader library with the five-part header
  (name, category, tier, requires_env, description)
- list tier filter: tier=1 returns only hermetic scenarios
- error list: tier 4 (outside 1|2|3) -> structured OMNI_INVALID_INPUT
  (STANDARDS.md#error-clarity)
- happy run: real engine on the hermetic ``tool-omni_mcp-ping`` scenario
  (tier 1, no LLM keys) -> passed verdict, per-step check text and
  ``standard:`` citations in-band (draft D12)
- error run: bad params (tier 4, non-string scenario filter) -> structured
  error, never a raise
- no-match filter: mirrors the CLI — a warning and empty results, not an
  error
- verbose: adds the full expect/actual/grade trace per step
"""

from __future__ import annotations

import json

import pytest

from omni_mcp.server import _TOOL_DISPATCH, _TOOL_SCHEMAS, _call_tool

_VALIDATION_TOOLS = {"list_validation_scenarios", "run_validation_scenario"}


def _parse(blocks) -> dict:
    """The single TextContent block of a call_tool response, as JSON."""
    assert len(blocks) == 1
    return json.loads(blocks[0].text)


# ---------------------------------------------------------------------------
# Surface
# ---------------------------------------------------------------------------


def test_schemas_declare_both_validation_tools():
    """The suite surface grows to 4: translate_file, ping, and the two
    validation tools — schema and dispatch must agree exactly."""
    schema_names = {s["name"] for s in _TOOL_SCHEMAS}
    assert _VALIDATION_TOOLS <= schema_names
    assert set(_TOOL_DISPATCH) == schema_names


# ---------------------------------------------------------------------------
# list_validation_scenarios
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_validation_scenarios_returns_library():
    """Happy: the tool returns the REAL loader's library with the
    five-part header (name, category, tier, requires_env, description)."""
    payload = _parse(await _call_tool("list_validation_scenarios", {}))
    assert payload["success"] is True
    content = payload["content"]
    assert content["count"] > 0
    names = {s["name"] for s in content["scenarios"]}
    assert "tool-omni_mcp-list_validation_scenarios" in names
    assert "tool-omni_mcp-ping" in names
    for s in content["scenarios"]:
        for key in ("name", "category", "tier", "requires_env", "description"):
            assert key in s, f"scenario entry missing {key!r}: {s}"


@pytest.mark.asyncio
async def test_list_validation_scenarios_tier_filter():
    """tier=1 returns only hermetic scenarios; the full library has
    higher-tier entries that must be excluded by the filter."""
    payload = _parse(await _call_tool("list_validation_scenarios", {"tier": 1}))
    assert payload["success"] is True
    assert all(s["tier"] == 1 for s in payload["content"]["scenarios"])
    all_payload = _parse(await _call_tool("list_validation_scenarios", {}))
    assert payload["content"]["count"] < all_payload["content"]["count"]


@pytest.mark.asyncio
async def test_list_validation_scenarios_invalid_tier():
    """Error path (STANDARDS.md#error-clarity): tier 4 is outside 1|2|3 —
    the tool must return a structured OMNI_INVALID_INPUT error, never a
    raw exception."""
    payload = _parse(await _call_tool("list_validation_scenarios", {"tier": 4}))
    assert payload["success"] is False
    assert payload["error"]["code"] == "OMNI_INVALID_INPUT"
    assert "tier" in payload["error"]["message"]


# ---------------------------------------------------------------------------
# run_validation_scenario
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_validation_scenario_happy_hermetic():
    """Happy: run the REAL engine on the hermetic ``tool-omni_mcp-ping``
    scenario (tier 1 — no LLM keys) via call_tool; the run record must
    carry a passed verdict, per-step check text, and in-band standard
    citations (D12)."""
    payload = _parse(
        await _call_tool("run_validation_scenario", {"scenario": "tool-omni_mcp-ping"})
    )
    assert payload["success"] is True
    content = payload["content"]
    assert content["run_id"]  # a real persisted run
    results = content["results"]
    assert len(results) == 1
    result = results[0]
    assert result["name"] == "tool-omni_mcp-ping"
    assert result["status"] == "passed"
    assert len(result["steps"]) == 2
    for step in result["steps"]:
        assert step["name"]  # per-step check text
        assert step["standard"].startswith("STANDARDS.md#")  # citation in-band
    # Real-surface evidence: the steps hit the actual suite tool function
    # (dispatch.py ToolAdapter resolves omni_mcp.server.ping in-process).
    assert result["steps"][0]["surface"] == "mcp: omni_mcp.server.ping"


@pytest.mark.asyncio
async def test_run_validation_scenario_module_filter():
    """Per-module validation (extend-don't-multiply): ``module: ol`` runs
    only OL scenarios — the result set must not include opp/orf tools and
    must carry the module param in the response."""
    payload = _parse(
        await _call_tool("run_validation_scenario", {"module": "ol", "scenario": "tool-ol-ping"})
    )
    assert payload["success"] is True
    content = payload["content"]
    assert content["module"] == "ol"
    results = content["results"]
    assert len(results) == 1
    assert results[0]["name"] == "tool-ol-ping"


@pytest.mark.asyncio
async def test_run_validation_scenario_module_invalid():
    """Error path: a non-string module is rejected with a structured error."""
    payload = _parse(await _call_tool("run_validation_scenario", {"module": 42}))
    assert payload["success"] is False
    assert payload.get("error_code") == "OMNI_INVALID_INPUT"


@pytest.mark.asyncio
async def test_run_validation_scenario_module_no_match_warns():
    """Unknown module value: no scenarios match -> warning, no failure."""
    payload = _parse(
        await _call_tool("run_validation_scenario", {"module": "nope"})
    )
    assert payload["success"] is True
    assert payload["content"]["warnings"]
    assert payload["content"]["results"] == []


@pytest.mark.asyncio
async def test_run_validation_scenario_invalid_tier():
    """Error path (#error-clarity): bad params return a structured error."""
    payload = _parse(await _call_tool("run_validation_scenario", {"tier": 4}))
    assert payload["success"] is False
    assert payload["error"]["code"] == "OMNI_INVALID_INPUT"


@pytest.mark.asyncio
async def test_run_validation_scenario_invalid_filter_type():
    """Error path (#error-clarity): a non-string scenario filter is a
    structured error, not a crash."""
    payload = _parse(await _call_tool("run_validation_scenario", {"scenario": 42}))
    assert payload["success"] is False
    assert payload["error"]["code"] == "OMNI_INVALID_INPUT"


@pytest.mark.asyncio
async def test_run_validation_scenario_no_match_warns():
    """A valid filter matching nothing mirrors the CLI: a warning and an
    empty result list, not an error."""
    payload = _parse(
        await _call_tool(
            "run_validation_scenario", {"scenario": "definitely-no-such-scenario"}
        )
    )
    assert payload["success"] is True
    assert payload["content"]["results"] == []
    assert payload["content"]["warnings"]


@pytest.mark.asyncio
async def test_run_validation_scenario_verbose_adds_detail():
    """verbose: true adds the full expect/actual/grade trace per step."""
    quiet = _parse(
        await _call_tool("run_validation_scenario", {"scenario": "tool-omni_mcp-ping"})
    )
    loud = _parse(
        await _call_tool(
            "run_validation_scenario",
            {"scenario": "tool-omni_mcp-ping", "verbose": True},
        )
    )
    quiet_step = quiet["content"]["results"][0]["steps"][0]
    loud_step = loud["content"]["results"][0]["steps"][0]
    assert "actual" not in quiet_step
    assert loud_step["actual"]["success"] is True
    assert "expect" in loud_step
    assert "grade" in loud_step
