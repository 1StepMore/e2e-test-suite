"""omni-mcp MCP server with translate_file, ping, and the two validation
tools (list_validation_scenarios, run_validation_scenario).

Uses ``mcp.server.Server`` + ``mcp.server.stdio.stdio_server`` (standard
mcp library, v1.27.2) — consistent with OPP, OL, and ORF MCP servers.

The validation tools dispatch to the REAL validation engine: the scenario
library comes from ``omni_mcp/validation/loader.py`` (phase 1 load) and
``run_validation_scenario`` drives ``omni_mcp/validation/engine.py``
(orchestrator, guide §3 phases 1-6) — no mock path (draft D3, D12).  The
engine is run in a worker thread (``asyncio.to_thread``) because its
in-process mcp adapter awaits async tool functions via ``asyncio.run``,
which cannot run inside the MCP server's own event loop.

SECURITY: This server calls OPP/OL/ORF CLIs directly, bypassing sub-module
MCP path security (PathValidator).  Only use in trusted environments.
"""

from __future__ import annotations

import anyio
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from omni_mcp import __version__
from omni_mcp.orchestrator import translate_file as _translate_file
from omni_mcp.validation.cli import _select_names
from omni_mcp.validation.engine import run_scenarios
from omni_mcp.validation.loader import ScenarioError, load_scenarios

#: Suite root: this module lives at <root>/omni_mcp/server.py.
SUITE_ROOT = Path(__file__).resolve().parent.parent

#: Scenario library + run records dirs (absolute — CWD-independent).
_SCENARIOS_DIR = SUITE_ROOT / "scenarios"
_RUNS_DIR = SUITE_ROOT / "validation-runs"

logger = logging.getLogger("omni_mcp.server")

# ── Error / success helpers ───────────────────────────────────────────


def _error_response(code: str, message: str, **extra: Any) -> dict[str, Any]:
    """Standardized error response (Wave 0 shape)."""
    resp: dict[str, Any] = {
        "success": False,
        "error": {"code": code, "message": message},
        "error_code": code,
        "message": message,
    }
    resp.update(extra)
    return resp


def _success_response(content: dict[str, Any]) -> dict[str, Any]:
    """Standardized success response wrapping payload under ``content``."""
    return {"success": True, "content": content}


# ── Tool implementations ─────────────────────────────────────────────


async def translate_file(
    file_path: str,
    source_lang: str,
    target_lang: str,
    output_format: str,
    pipeline: str | None = None,
) -> dict[str, Any]:
    """Orchestrate OPP→OL→ORF in one call.

    This is the in-process async wrapper around the synchronous
    orchestrator.  Tests can import and call it directly.
    """
    if not file_path:
        return _error_response("OMNI_INVALID_INPUT", "file_path is required")

    result = _translate_file(
        file_path=file_path,
        source_lang=source_lang,
        target_lang=target_lang,
        output_format=output_format,
        pipeline=pipeline,
    )
    return result


async def ping() -> dict[str, Any]:
    """Health check endpoint."""
    return _success_response({
        "module": "omni-mcp",
        "version": __version__,
    })


def _validate_tier(tier: Any) -> dict[str, Any] | None:
    """Validate the shared ``tier`` param (1|2|3, AutoInfo tier model).

    Returns an error response dict when invalid, None when valid.  A bool
    is rejected (``True`` is an int subclass that would silently mean 1 —
    same guard the loader applies).
    """
    if tier is None:
        return None
    if isinstance(tier, bool) or not isinstance(tier, int) or tier not in (1, 2, 3):
        return _error_response(
            "OMNI_INVALID_INPUT",
            "tier must be an integer in 1|2|3 "
            "(1=no keys hermetic, 2=LLM key, 3=paid/external/network)",
        )
    return None


async def list_validation_scenarios(tier: int | None = None) -> dict[str, Any]:
    """Enumerate the validation scenario library (phase 1 loader, real).

    Returns every scenario's header — name, category, tier, requires_env,
    description — from ``load_scenarios``; ``tier`` narrows to one tier.
    No execution happens.
    """
    err = _validate_tier(tier)
    if err is not None:
        return err
    try:
        loaded = load_scenarios(_SCENARIOS_DIR)
    except ScenarioError as exc:
        return _error_response("OMNI_VALIDATION_LOAD_ERROR", str(exc))
    if tier is not None:
        loaded = [s for s in loaded if s.get("tier") == tier]
    scenarios = [
        {
            "name": s["name"],
            "category": s.get("category"),
            "tier": s.get("tier"),
            "requires_env": list(s.get("requires_env") or []),
            "description": s.get("description"),
        }
        for s in loaded
    ]
    return _success_response({"scenarios": scenarios, "count": len(scenarios)})


async def run_validation_scenario(
    scenario: str | None = None,
    tier: int | None = None,
    verbose: bool = False,
    module: str | None = None,
) -> dict[str, Any]:
    """Run the real validation engine (orchestrator) on matching scenarios.

    Params mirror the validation CLI: ``scenario`` is a case-insensitive
    substring of the scenario FILENAME (AutoInfo semantics), ``tier``
    restricts by tier, ``module`` restricts to one module's scenarios
    (opp/ol/orf/suite), ``verbose`` adds the full per-step trace.  The
    engine's step records already carry the per-step check text (``name``)
    and ``standard:`` citations (D12) — both are echoed into the response.
    The run is persisted to ``validation-runs/`` like a CLI run.
    """
    if scenario is not None and not isinstance(scenario, str):
        return _error_response(
            "OMNI_INVALID_INPUT",
            "scenario must be a string (case-insensitive substring of the "
            "scenario filename)",
        )
    if module is not None and not isinstance(module, str):
        return _error_response(
            "OMNI_INVALID_INPUT",
            "module must be a string (opp, ol, orf, or suite)",
        )
    err = _validate_tier(tier)
    if err is not None:
        return err
    try:
        loaded = load_scenarios(_SCENARIOS_DIR)
    except ScenarioError as exc:
        return _error_response("OMNI_VALIDATION_LOAD_ERROR", str(exc))

    names, empty_filters = _select_names(
        loaded, _SCENARIOS_DIR, scenario, tier, module=module
    )
    warnings = [f"no scenarios match {f}" for f in empty_filters]
    if not names:
        return _success_response({
            "run_id": None,
            "trace_id": None,
            "runs_dir": None,
            "scenario": scenario,
            "tier": tier,
            "module": module,
            "verbose": verbose,
            "warnings": warnings,
            "results": [],
        })

    filters = (
        None
        if (scenario is None and tier is None and module is None)
        else names
    )
    run = await asyncio.to_thread(
        run_scenarios, _SCENARIOS_DIR, filters=filters, runs_dir=_RUNS_DIR
    )
    results = []
    for s in run.scenarios:
        steps = []
        for st in s.steps:
            step = {
                "step_index": st["step_index"],
                "name": st["name"],
                "passed": st["passed"],
                "status": st["status"],
                "standard": st["standard"],
                "surface": st["surface"],
                "real_call": st["real_call"],
            }
            if verbose:
                step.update({
                    "expect": st["expect"],
                    "actual": st["actual"],
                    "duration_seconds": st["duration_seconds"],
                    "grade": st["grade"],
                })
            steps.append(step)
        results.append({
            "name": s.name,
            "status": s.status,
            "summary": s.summary,
            "missing_env": s.missing_env,
            "steps": steps,
        })
    return _success_response({
        "run_id": run.run_id,
        "trace_id": run.trace_id,
        "runs_dir": run.run_dir,
        "scenario": scenario,
        "tier": tier,
        "module": module,
        "verbose": verbose,
        "warnings": warnings,
        "results": results,
    })


# ── Tool schemas ─────────────────────────────────────────────────────

_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "translate_file",
        "description": (
            "Orchestrate OPP→OL→ORF to translate a document in one step. "
            "Extracts the source document (OPP), translates it (OL), and "
            "produces the output in the requested format (ORF)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the source document.",
                },
                "source_lang": {
                    "type": "string",
                    "description": "Source language code (e.g. 'en').",
                },
                "target_lang": {
                    "type": "string",
                    "description": "Target language code (e.g. 'zh').",
                },
                "output_format": {
                    "type": "string",
                    "description": (
                        "Target output format (e.g. 'docx', 'html', 'epub', 'md'). "
                        "See ORF apply-md for the full list of 16 supported formats."
                    ),
                },
                "pipeline": {
                    "type": "string",
                    "enum": ["md", "xliff"],
                    "description": (
                        "Force pipeline type. 'md' uses MD path (text-first), "
                        "'xliff' uses XLIFF path (layout-faithful). "
                        "Omit for auto-detection based on OPP's suggested_pipeline."
                    ),
                },
            },
            "required": ["file_path", "source_lang", "target_lang", "output_format"],
        },
    },
    {
        "name": "ping",
        "description": "Health check endpoint. Returns module name and version.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "list_validation_scenarios",
        "description": (
            "Enumerate the validation scenario library: name, category, "
            "tier, requires_env, and description for every scenario (or "
            "only those at a given tier). Loads through the real "
            "validation loader — no execution."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tier": {
                    "type": "integer",
                    "enum": [1, 2, 3],
                    "description": (
                        "Only scenarios at this tier "
                        "(1=no keys hermetic, 2=LLM key, "
                        "3=paid/external/network). Omit for all."
                    ),
                },
            },
        },
    },
    {
        "name": "run_validation_scenario",
        "description": (
            "Run the real validation engine (load -> dispatch -> grade -> "
            "aggregate -> persist) on matching scenarios. 'scenario' is a "
            "case-insensitive substring of the scenario filename; 'tier' "
            "restricts by tier; 'module' restricts to one module's "
            "scenarios (opp/ol/orf/suite); 'verbose' adds the full "
            "per-step trace. Results carry per-step check text and "
            "STANDARDS.md citations in-band."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "scenario": {
                    "type": "string",
                    "description": (
                        "Case-insensitive substring of the scenario "
                        "filename to run (e.g. 'tool-omni_mcp-ping'). "
                        "Omit to run all scenarios (respecting 'tier'/'module')."
                    ),
                },
                "tier": {
                    "type": "integer",
                    "enum": [1, 2, 3],
                    "description": (
                        "Only scenarios at this tier "
                        "(1=no keys hermetic, 2=LLM key, "
                        "3=paid/external/network). Omit for all."
                    ),
                },
                "module": {
                    "type": "string",
                    "enum": ["opp", "ol", "orf", "suite"],
                    "description": (
                        "Per-module validation: run only this module's "
                        "scenarios (its categories plus its "
                        "tool-<module>-* agent-surface scenarios). "
                        "Omit for all modules."
                    ),
                },
                "verbose": {
                    "type": "boolean",
                    "description": (
                        "Include the full per-step expect/actual/grade "
                        "trace in the response (default false)."
                    ),
                },
            },
        },
    },
]

# ── Dispatch table ────────────────────────────────────────────────────

_TOOL_DISPATCH: dict[str, Any] = {
    "translate_file": translate_file,
    "ping": ping,
    "list_validation_scenarios": list_validation_scenarios,
    "run_validation_scenario": run_validation_scenario,
}

# ── MCP Server instance ──────────────────────────────────────────────

server: Server = Server("omni-mcp")


@server.list_tools()
async def _list_tools() -> list[types.Tool]:
    """Advertise tools to the MCP client."""
    return [types.Tool(**schema) for schema in _TOOL_SCHEMAS]


@server.call_tool()
async def _call_tool(
    name: str, arguments: dict[str, Any],
) -> list[types.ContentBlock]:
    """Dispatch a tool call to the matching function.

    Returns a single ``TextContent`` block with the JSON-serialized result.
    Any uncaught exception is logged and returned as a safe error payload.
    """
    fn = _TOOL_DISPATCH.get(name)
    if fn is None:
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    _error_response("OMNI_UNKNOWN_TOOL", f"Unknown tool: {name!r}"),
                    ensure_ascii=False,
                ),
            )
        ]

    try:
        result = await fn(**(arguments or {}))
    except Exception:
        logger.exception("Unhandled error in tool %s", name)
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    _error_response(
                        "OMNI_INTERNAL_ERROR",
                        "An internal error occurred. Check server logs.",
                    ),
                    ensure_ascii=False,
                ),
            )
        ]

    if not isinstance(result, dict):
        result = _success_response({"data": result})

    return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


# ── Entry point ───────────────────────────────────────────────────────


async def _run() -> None:
    """Async entry point: drive the stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
            raise_exceptions=False,
        )


def main() -> None:
    """Synchronous entry point invoked by ``python -m omni_mcp``.

    WARNING
    -------
    This server calls OPP/OL/ORF CLIs directly, bypassing sub-module MCP
    path security (PathValidator).  Pass ``--danger-disable-security`` to
    acknowledge this risk — the flag is required for documentation purposes;
    without it a startup warning is emitted.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="omni-mcp — suite-level MCP orchestrator",
    )
    parser.add_argument(
        "--danger-disable-security",
        action="store_true",
        help=(
            "Acknowledge that this server bypasses OPP/OL/ORF MCP path security "
            "(PathValidator).  Only use in trusted environments."
        ),
    )
    args = parser.parse_args()

    if not args.danger_disable_security:
        logger.warning(
            "SECURITY: omni-mcp server started without --danger-disable-security flag. "
            "This server calls OPP/OL/ORF CLIs directly, bypassing sub-module MCP "
            "path security (PathValidator).  Only use in trusted environments."
        )

    anyio.run(_run)


if __name__ == "__main__":
    main()
