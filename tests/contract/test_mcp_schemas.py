"""MCP schema contract tests (Phase 4.7).

Per API_STABILITY.md the 21 MCP tool schemas (7 OPP + 6 ORF + 8 OL) are
frozen public surface. Any change to a tool's name, description, or
inputSchema requires a major version bump. The fixtures in
``tests/contract/fixtures/{opp,orf,ol}_mcp_schemas.json`` are the
current baseline. If a test fails, the MCP surface has changed and
either:

  1. The change is intentional — regenerate fixtures and document it
  2. The change is accidental — revert the change

The transport is the real ``mcp.client.stdio.stdio_client`` +
``ClientSession`` (not raw JSON-RPC, not the deleted mcp_bridge.py). The
server is spawned as a subprocess with the required env vars:
``OMNI_TEST_FAKE_LLM=1``, ``OMNI_TEST_FAKE_PANDOC=1``,
``OPP_MCP_ALLOWED_DIRS=/tmp``, ``ORF_MCP_ALLOWED_DIRS=/tmp``.

Run with::

    .venv_ol/bin/python -m pytest tests/contract/test_mcp_schemas.py -v
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import anyio
import pytest
from mcp import StdioServerParameters, stdio_client
from mcp.client.session import ClientSession

SUITE_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
VENV_PYTHON = SUITE_ROOT / ".venv_ol" / "bin" / "python"
PYTHONPATH_SEP = ";" if sys.platform == "win32" else ":"

OPP_SRC = SUITE_ROOT / "Omni_Pre_Processor" / "src"
OL_SRC = SUITE_ROOT / "Omni_Localizer" / "src"
ORF_SRC = SUITE_ROOT / "Omni_Re_Formatter" / "src"

OPP_FIXTURE = FIXTURES_DIR / "opp_mcp_schemas.json"
ORF_FIXTURE = FIXTURES_DIR / "orf_mcp_schemas.json"
OL_FIXTURE = FIXTURES_DIR / "ol_mcp_schemas.json"

EXPECTED_COUNTS = {"opp": 7, "orf": 6, "ol": 8}

EXPECTED_TOOLS = {
    "opp": frozenset({
        "extract_document",
        "batch_extract",
        "detect_format_tool",
        "generate_xliff",
        "generate_markdown",
        "save_skeleton",
        "ping",
    }),
    "orf": frozenset({
        "apply_md",
        "apply_xliff",
        "batch_convert",
        "detect_format",
        "info",
        "ping",
    }),
    "ol": frozenset({
        "translate_md_text",
        "judge_text",
        "load_glossary",
        "get_relevant_terms",
        "search_tm",
        "batch_translate_texts",
        "translate_xliff",
        "ping",
    }),
}

# Common log noise from the OPP/ORF CLI that pollutes stdout/stderr.
# We strip these before comparison because they include timestamps.
_LOG_NOISE_PATTERNS = [
    re.compile(r"^\[INFO\] Log file: .+$", re.MULTILINE),
    re.compile(r"^\[DEBUG\] .+$", re.MULTILINE),
    re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} .+$", re.MULTILINE),
]


def _strip_log_noise(text: str) -> str:
    for pattern in _LOG_NOISE_PATTERNS:
        text = pattern.sub("", text)
    return text


def _server_env(module: str) -> dict[str, str]:
    env = os.environ.copy()
    env["OMNI_TEST_FAKE_LLM"] = "1"
    env["OMNI_TEST_FAKE_PANDOC"] = "1"
    env["OPP_MCP_ALLOWED_DIRS"] = "/tmp"
    env["ORF_MCP_ALLOWED_DIRS"] = "/tmp"
    src = {"opp": OPP_SRC, "orf": ORF_SRC, "ol": OL_SRC}[module]
    env["PYTHONPATH"] = PYTHONPATH_SEP.join(
        filter(None, [env.get("PYTHONPATH", ""), str(src)])
    )
    return env


def _server_params(module: str) -> StdioServerParameters:
    args = {
        "opp": ["-u", "-m", "opp.mcp.server"],
        "orf": ["-u", "-m", "orf.mcp.server"],
        "ol": ["-u", "-m", "ol_mcp"],
    }[module]
    return StdioServerParameters(
        command=str(VENV_PYTHON),
        args=args,
        env=_server_env(module),
    )


async def _fetch_schemas(module: str) -> list[dict]:
    async with stdio_client(_server_params(module)) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.list_tools()
            tools = []
            for tool in result.tools:
                tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": (
                        dict(tool.inputSchema)
                        if isinstance(tool.inputSchema, dict)
                        else tool.inputSchema
                    ),
                })
            tools.sort(key=lambda x: x["name"])
            return tools


def _normalize(schemas: list[dict]) -> str:
    return _strip_log_noise(
        json.dumps(schemas, indent=2, sort_keys=True, ensure_ascii=False)
    )


def _check(module: str, fixture_path: Path) -> None:
    assert fixture_path.exists(), (
        f"Missing fixture: {fixture_path}. "
        f"Regenerate via the capture helper in tests/contract/test_mcp_schemas.py."
    )
    expected_raw = _strip_log_noise(fixture_path.read_text(encoding="utf-8"))
    actual = anyio.run(_fetch_schemas, module)
    names = {s["name"] for s in actual}
    expected_names = EXPECTED_TOOLS[module]
    assert names == expected_names, (
        f"{module.upper()} MCP tool name set mismatch: "
        f"missing={sorted(expected_names - names)}, extra={sorted(names - expected_names)}"
    )
    assert len(actual) == EXPECTED_COUNTS[module], (
        f"{module.upper()} MCP tool count: expected {EXPECTED_COUNTS[module]}, "
        f"got {len(actual)}"
    )
    actual_text = _normalize(actual)
    if actual_text != expected_raw:
        actual_path = fixture_path.with_suffix(".actual.json")
        actual_path.write_text(actual_text, encoding="utf-8")
        pytest.fail(
            f"{module.upper()} MCP schemas changed. "
            f"Diff saved to {actual_path}.\n"
            f"If intentional: cp {actual_path} {fixture_path}"
        )


def test_opp_mcp_schemas_frozen():
    """OPP MCP must expose exactly 7 tools whose schemas match the frozen baseline."""
    _check("opp", OPP_FIXTURE)


def test_orf_mcp_schemas_frozen():
    """ORF MCP must expose exactly 6 tools whose schemas match the frozen baseline."""
    _check("orf", ORF_FIXTURE)


def test_ol_mcp_schemas_frozen():
    """OL MCP must expose exactly 8 tools whose schemas match the frozen baseline."""
    _check("ol", OL_FIXTURE)


def test_total_mcp_tool_count_is_21():
    """Sanity: 7 OPP + 6 ORF + 8 OL = 21 MCP tools. Sum is part of the contract."""
    assert sum(EXPECTED_COUNTS.values()) == 21
    actual_total = sum(
        len(EXPECTED_TOOLS[m]) for m in ("opp", "orf", "ol")
    )
    assert actual_total == 21
