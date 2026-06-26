"""omni-mcp MCP server with translate_file and ping tools.

Uses ``mcp.server.Server`` + ``mcp.server.stdio.stdio_server`` (standard
mcp library, v1.27.2) — consistent with OPP, OL, and ORF MCP servers.
"""

from __future__ import annotations

import anyio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from omni_mcp import __version__
from omni_mcp.orchestrator import translate_file as _translate_file

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
]

# ── Dispatch table ────────────────────────────────────────────────────

_TOOL_DISPATCH: dict[str, Any] = {
    "translate_file": translate_file,
    "ping": ping,
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
    """Synchronous entry point invoked by ``python -m omni_mcp``."""
    anyio.run(_run)


if __name__ == "__main__":
    main()
