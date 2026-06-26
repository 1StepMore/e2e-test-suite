"""MCP I/O response shape contract tests (Wave 0.0 of 9-issue plan).

Per the cross-repo MCP response standard (docs/ERROR_CODES.md:15-29,
docs/API_STABILITY.md:197), every MCP tool response MUST conform to:

    Success: {success: true, content: {dict}, metadata?: {dict}}
    Error:   {success: false, error: {code: str, message: str}}

This test validates structural conformance across 21 MCP tools
(7 OPP + 8 OL + 6 ORF). It is expected to FAIL against the current
codebase — it serves as the test-first (RED) gate for Waves 0.1-0.3
standardization PRs.

Transport: real ``mcp.client.stdio.stdio_client`` + ``ClientSession``
(not raw JSON-RPC, not mock). Server spawned as subprocess with
``OMNI_TEST_FAKE_LLM=1``.

Run::

    pytest tests/contract/test_mcp_io_contract.py -v
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import anyio
import pytest
from mcp import StdioServerParameters, stdio_client
from mcp.client.session import ClientSession

SUITE_ROOT = Path(__file__).resolve().parent.parent.parent
VENV_PYTHON = SUITE_ROOT / ".venv_ol" / "bin" / "python"
PYTHONPATH_SEP = ";" if sys.platform == "win32" else ":"

OPP_SRC = SUITE_ROOT / "Omni_Pre_Processor" / "src"
OL_SRC = SUITE_ROOT / "Omni_Localizer" / "src"
ORF_SRC = SUITE_ROOT / "Omni_Re_Formatter" / "src"

_SHARED_ENV = {
    "OMNI_TEST_FAKE_LLM": "1",
    "OMNI_TEST_FAKE_PANDOC": "1",
    "OPP_MCP_ALLOWED_DIRS": "/tmp",
    "ORF_MCP_ALLOWED_DIRS": "/tmp",
}


def _server_params(module: str) -> StdioServerParameters:
    src_map = {"opp": OPP_SRC, "orf": ORF_SRC, "ol": OL_SRC}
    args_map = {
        "opp": ["-u", "-m", "opp.mcp.server"],
        "orf": ["-u", "-m", "orf.mcp.server"],
        "ol": ["-u", "-m", "ol_mcp"],
    }
    env = os.environ.copy()
    env.update(_SHARED_ENV)
    src = str(src_map[module])
    env["PYTHONPATH"] = PYTHONPATH_SEP.join(
        filter(None, [env.get("PYTHONPATH", ""), src])
    )
    return StdioServerParameters(
        command=str(VENV_PYTHON), args=args_map[module], env=env
    )


async def _call_tool(module: str, tool_name: str, args: dict) -> dict:
    """Start an MCP server, call one tool, return the parsed JSON response."""
    params = _server_params(module)
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=args)
            text = result.content[0].text if result.content else ""
            return json.loads(text)


# ── Success shape: every tool must return {success: true, content: {dict}} ──


SUCCESS_TOOLS = {
    "opp": ("ping", {}),
    "orf": ("ping", {}),
    "ol": ("ping", {}),
}

ALLOWED_TOP_LEVEL = frozenset({"success", "content", "metadata"})


@pytest.mark.asyncio
@pytest.mark.parametrize("module", ["opp", "orf", "ol"])
async def test_success_response_wraps_content(module: str):
    """Success responses MUST have ``content`` dict at top level (no top-level data fields)."""
    tool_name, tool_args = SUCCESS_TOOLS[module]
    resp = await _call_tool(module, tool_name, tool_args)

    assert resp.get("success") is True, f"{module}.{tool_name}: success != True"

    # Content MUST be present and be a dict
    assert "content" in resp, (
        f"{module}.{tool_name}: missing 'content' field. "
        f"Top-level keys: {list(resp.keys())}"
    )
    assert isinstance(resp["content"], dict), (
        f"{module}.{tool_name}: content must be a dict, got {type(resp['content'])}"
    )

    # No top-level fields outside the allowed set
    for key in resp:
        assert key in ALLOWED_TOP_LEVEL, (
            f"{module}.{tool_name}: unexpected top-level field '{key}'. "
            f"All data must be wrapped in 'content'. "
            f"Allowed: {sorted(ALLOWED_TOP_LEVEL)}"
        )


# ── Error shape: every tool must return {success: false, error: {code, message}} ──


# Error-triggering calls per module: tool_name → arguments that should produce an error
ERROR_INPUTS = {
    "opp": {
        "tool": "extract_document",
        "args": {
            "file_path": "/nonexistent/nope.docx",
            "output_formats": ["md"],
        },
    },
    "orf": {
        "tool": "batch_convert",
        "args": {
            "input_dir": "/tmp/nonexistent",  # passes schema validation, fails tool-level path check
            "target_format": "docx",
        },
    },
    "ol": {
        "tool": "judge_text",
        "args": {
            "source": "hello",
            "target": "你好",
            "source_lang": "en",
            "target_lang": "en",  # same language — OL should reject or produce 0-score
        },
    },
}


@pytest.mark.asyncio
@pytest.mark.parametrize("module", ["opp", "orf", "ol"])
async def test_error_response_has_error_code(module: str):
    """On failure, response MUST have ``error: {code: str, message: str}``."""
    info = ERROR_INPUTS[module]
    resp = await _call_tool(module, info["tool"], info["args"])

    assert resp.get("success") is False, (
        f"{module}.{info['tool']}: expected success=False, "
        f"got {resp.get('success')}"
    )

    # Must have error field — a dict with code and message
    assert "error" in resp, (
        f"{module}.{info['tool']}: missing 'error' field. "
        f"Response keys: {list(resp.keys())}"
    )
    err = resp["error"]
    assert isinstance(err, dict), (
        f"{module}.{info['tool']}: error must be a dict, got {type(err)}"
    )
    assert "code" in err and isinstance(err["code"], str) and err["code"], (
        f"{module}.{info['tool']}: error.code must be non-empty string, "
        f"got {err.get('code')!r}"
    )
    assert "message" in err and isinstance(err["message"], str) and err["message"], (
        f"{module}.{info['tool']}: error.message must be non-empty string, "
        f"got {err.get('message')!r}"
    )


# ── Parametrized cross-module structure check (stretch goal for later waves) ──
# All 21 tools will be added here in future. For now, the success + error
# shape tests above establish the gate. Adding 21 full call tests would
# require test files per tool type and is deferred to Wave 0.1-0.3 PRs.
