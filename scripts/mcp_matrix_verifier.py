"""MCP matrix verifier — runs the same 195 cells as the CLI matrix but via
MCP tool calls instead of subprocess CLI invocations.

Flow per cell (MD path):
1. OPP MCP server: extract_document → MD file
2. OL MCP server: translate_md_text → translated MD
3. ORF MCP server: apply_md → output file

For XLIFF path: extract_document with target_format="both" + translate_xliff + apply_xliff.

Servers are started once and reused across cells (much faster than per-cell start).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, asdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SUITE_ROOT = SCRIPT_DIR.parent


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class MCPCellResult:
    inp: str
    outp: str
    path: str
    status: str  # "pass", "skip", "fail"
    duration_s: float
    detail: str = ""
    skip_reason: str = ""
    opp_tool: str = ""
    ol_tool: str = ""
    orf_tool: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MCPMatrixResult:
    cells: list[MCPCellResult] = field(default_factory=list)
    total_duration_s: float = 0.0

    @property
    def passed(self) -> int:
        return sum(1 for c in self.cells if c.status == "pass")

    @property
    def skipped(self) -> int:
        return sum(1 for c in self.cells if c.status == "skip")

    @property
    def failed(self) -> int:
        return sum(1 for c in self.cells if c.status == "fail")

    def to_dict(self) -> dict:
        return {
            "total": len(self.cells),
            "passed": self.passed,
            "skipped": self.skipped,
            "failed": self.failed,
            "duration_s": self.total_duration_s,
            "cells": [c.to_dict() for c in self.cells],
        }


# ---------------------------------------------------------------------------
# MCP client context (real mcp library; bridge removed in Phase 1).
# ---------------------------------------------------------------------------

_MCP_SERVER_PLAN = {
    "opp": (["-u", "-m", "opp.mcp.server"], "Omni_Pre_Processor"),
    "ol":  (["-u", "-m", "ol_mcp"],         "Omni_Localizer"),
    "orf": (["-u", "-m", "orf.mcp.server"],  "Omni_Re_Formatter"),
}


@asynccontextmanager
async def mcp_session(which: str, suite_root: Path, env: dict):
    from mcp import StdioServerParameters, stdio_client
    from mcp.client.session import ClientSession

    argv, subdir = _MCP_SERVER_PLAN[which]
    params = StdioServerParameters(
        command=sys.executable,
        args=argv,
        cwd=str(suite_root / "src" / subdir),
        env=env,
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield _MCPSessionAdapter(session)


class _MCPSessionAdapter:
    def __init__(self, session):
        self._session = session

    async def list_tools(self) -> list:
        result = await self._session.list_tools()
        return [
            {"name": t.name, "description": t.description}
            for t in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict) -> dict:
        result = await self._session.call_tool(name, arguments or {})
        if result.isError:
            return {
                "success": False,
                "error": getattr(result, "error", "unknown"),
                "isError": True,
            }
        text_parts = [c.text for c in result.content if hasattr(c, "text")]
        text = "\n".join(text_parts)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}


async def _call_tool(session, tool_name: str, arguments: dict) -> dict:
    """Call an MCP tool and return the parsed result."""
    return await session.call_tool(tool_name, arguments)


# ---------------------------------------------------------------------------
# Cell execution
# ---------------------------------------------------------------------------

# Mirror the skip rules from format_matrix_verifier.py
SKIP_RULES = [
    ("output", "pptx", "md2pptx CLI not installed"),
    ("output", "docx", "pandoc not installed"),
    ("output", "pdf", "pandoc/weasyprint not installed"),
    ("output", "odt", "pandoc not installed"),
    ("output", "epub", "pandoc not installed"),
    ("output", "rtf", "pandoc not installed"),
    ("output", "icml", "pandoc not installed"),
    ("output", "msg", "aspose-email-foss not installed"),
    ("input", "ipynb", "nbformat not installed"),
    ("*", "json", "MD→JSON requires JSON code block or OPP key=value source"),
    ("*", "srt", "MD→SRT requires timestamped cues; no timestamps in fixture"),
    ("pptx", "xlsx", "PPTX→XLSX: no table content in slide fixture"),
    ("xlsx", "pptx", "XLSX→PPTX: no slide content in table fixture"),
    ("*", "csv", "MD→CSV: apply_md doesn't produce CSV (use batch_convert for tabular data)"),
    ("*", "xlsx", "MD→XLSX: apply_md doesn't produce XLSX (use batch_convert for tabular data)"),
    ("*", "ipynb", "MD→IPYNB: apply_md doesn't produce IPYNB"),
    ("*", "eml", "MD→EML: apply_md doesn't produce EML"),
    ("xliff", "xlsx", "XLIFF: OPP doesn't produce skeleton for XLSX"),
    ("xliff", "html", "XLIFF: OPP doesn't produce skeleton for HTML"),
    ("xliff", "epub", "XLIFF: OPP doesn't produce skeleton for EPUB"),
    ("xliff", "eml", "XLIFF: OPP doesn't produce skeleton for EML"),
    ("xliff_xfmt", "*", "XLIFF cross-format not supported by ORF converters"),
]

XLIFF_INPUTS = {"docx", "pptx", "xlsx", "html", "epub", "eml"}
XLIFF_OUTPUTS = {"docx", "pptx", "epub", "html", "odt"}


def _should_skip(inp: str, outp: str, path: str) -> str | None:
    """Return skip reason or None. Simplified version of the CLI check."""
    for rule in SKIP_RULES:
        axis, fmt, reason = rule
        if axis == "input" and fmt == inp:
            return reason
        if axis == "output" and fmt == outp:
            return reason
        if axis == "*" and fmt == outp:
            return reason
        if axis == inp and fmt == outp:
            return reason
        if axis == "xliff" and fmt == inp and path == "xliff":
            return reason
        if axis == "xliff_xfmt" and path == "xliff" and inp != fmt:
            return reason
    return None


async def _run_one_cell_mcp(
    inp: str, outp: str, path: str,
    src: Path, cell_dir: Path,
    opp_session, ol_session, orf_session,
) -> MCPCellResult:
    """Run a single cell end-to-end via MCP tool calls."""
    t0 = time.monotonic()
    skip = _should_skip(inp, outp, path)
    if skip:
        return MCPCellResult(inp, outp, path, "skip", 0.0, skip_reason=skip)

    try:
        if path == "md":
            (cell_dir / "opp").mkdir(parents=True, exist_ok=True)
            opp_resp = await _call_tool(opp_session, "extract_document", {
                "file_path": str(src),
                "output_formats": ["md"],
                "source_lang": "en",
                "target_lang": "zh",
                "resource_dir": str(cell_dir / "opp" / "resources"),
            })
            opp_tool = "extract_document"
            md_content = opp_resp.get("md_content")
            if not md_content:
                return MCPCellResult(inp, outp, path, "fail", time.monotonic() - t0,
                                     opp_tool=opp_tool,
                                     detail=f"OPP MCP: no md_content in response: {opp_resp}")
            opp_traceparent = opp_resp.get("traceparent")

            (cell_dir / "ol").mkdir(parents=True, exist_ok=True)
            ol_args: dict = {
                "content": md_content,
                "source_lang": "en",
                "target_lang": "zh",
            }
            if opp_traceparent:
                ol_args["traceparent"] = opp_traceparent
            ol_resp = await _call_tool(ol_session, "translate_md_text", ol_args)
            ol_tool = "translate_md_text"
            translated_text = ol_resp.get("translated")
            if not translated_text:
                return MCPCellResult(inp, outp, path, "fail", time.monotonic() - t0,
                                     opp_tool=opp_tool, ol_tool=ol_tool,
                                     detail=f"OL MCP: no translated in response: {ol_resp}")
            ol_traceparent = ol_resp.get("traceparent")
            translated_md = cell_dir / "ol" / f"{Path(src).stem}.md"
            translated_md.write_text(translated_text, encoding="utf-8")

            orf_out = cell_dir / f"result.{outp}"
            orf_args: dict = {
                "input_md": str(translated_md),
                "target_format": outp,
                "output_path": str(orf_out),
            }
            if ol_traceparent:
                orf_args["traceparent"] = ol_traceparent
            orf_resp = await _call_tool(orf_session, "apply_md", orf_args)
            orf_tool = "apply_md"
            if not orf_out.exists():
                return MCPCellResult(inp, outp, path, "fail", time.monotonic() - t0,
                                     opp_tool=opp_tool, ol_tool=ol_tool, orf_tool=orf_tool,
                                     detail=f"ORF MCP: no output at {orf_out}: {orf_resp}")

            return MCPCellResult(inp, outp, path, "pass", time.monotonic() - t0,
                                 opp_tool=opp_tool, ol_tool=ol_tool, orf_tool=orf_tool)
        else:
            (cell_dir / "opp").mkdir(parents=True, exist_ok=True)
            opp_resp = await _call_tool(opp_session, "extract_document", {
                "file_path": str(src),
                "output_formats": ["xlf"],
                "source_lang": "en",
                "target_lang": "zh",
                "resource_dir": str(cell_dir / "opp" / "resources"),
            })
            opp_tool = "extract_document"
            xliff_content = opp_resp.get("xliff_content")
            if not xliff_content:
                return MCPCellResult(inp, outp, path, "fail", time.monotonic() - t0,
                                     opp_tool=opp_tool,
                                     detail=f"OPP MCP: no xliff_content: {opp_resp}")
            opp_traceparent = opp_resp.get("traceparent")
            xlf_file = cell_dir / "opp" / f"{Path(src).stem}.xlf"
            xlf_file.write_text(xliff_content, encoding="utf-8")

            (cell_dir / "ol").mkdir(parents=True, exist_ok=True)
            ol_xlf = cell_dir / "ol" / xlf_file.name
            ol_args = {
                "input_path": str(xlf_file),
                "source_lang": "en",
                "target_lang": "zh",
                "output_path": str(ol_xlf),
            }
            if opp_traceparent:
                ol_args["traceparent"] = opp_traceparent
            ol_resp = await _call_tool(ol_session, "translate_xliff", ol_args)
            ol_tool = "translate_xliff"
            if not ol_xlf.exists():
                ol_xlfs = list((cell_dir / "ol").glob("*.xlf"))
                if not ol_xlfs:
                    return MCPCellResult(inp, outp, path, "fail", time.monotonic() - t0,
                                         opp_tool=opp_tool, ol_tool=ol_tool,
                                         detail=f"OL MCP: no translated .xlf: {ol_resp}")
                ol_xlf = ol_xlfs[0]
            ol_traceparent = ol_resp.get("traceparent")

            orf_out = cell_dir / f"result.{outp}"
            orf_args = {
                "input_file": str(xlf_file),
                "xliff_path": str(ol_xlf),
                "output_path": str(orf_out),
                "format": outp,
            }
            if ol_traceparent:
                orf_args["traceparent"] = ol_traceparent
            orf_resp = await _call_tool(orf_session, "apply_xliff", orf_args)
            orf_tool = "apply_xliff"
            if not orf_out.exists():
                return MCPCellResult(inp, outp, path, "fail", time.monotonic() - t0,
                                     opp_tool=opp_tool, ol_tool=ol_tool, orf_tool=orf_tool,
                                     detail=f"ORF MCP: no output at {orf_out}: {orf_resp}")

            return MCPCellResult(inp, outp, path, "pass", time.monotonic() - t0,
                                 opp_tool=opp_tool, ol_tool=ol_tool, orf_tool=orf_tool)

    except Exception as e:
        return MCPCellResult(inp, outp, path, "fail", time.monotonic() - t0,
                             detail=f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def _run_matrix(args) -> int:
    from format_matrix_verifier import FULL_MATRIX, _resolve_fixture

    env = os.environ.copy()
    env["OMNI_TEST_FAKE_LLM"] = "1"
    env["OMNI_TEST_FAKE_PANDOC"] = "1"
    env["PYTHONPATH"] = ":".join(filter(None, [
        env.get("PYTHONPATH", ""),
        str(SUITE_ROOT / "Omni_Pre_Processor" / "src"),
        str(SUITE_ROOT / "Omni_Localizer" / "src"),
        str(SUITE_ROOT / "Omni_Re_Formatter" / "src"),
    ]))
    env["OPP_MCP_ALLOWED_DIRS"] = str(args.out_dir.resolve())
    env["ORF_MCP_ALLOWED_DIRS"] = str(args.out_dir.resolve())

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_root = out_dir / "cells"
    tmp_root.mkdir(exist_ok=True)

    cells = list(FULL_MATRIX)
    if args.path_filter == "md":
        cells = [c for c in cells if c[2] == "md"]
    elif args.path_filter == "xliff":
        cells = [c for c in cells if c[2] == "xliff"]
    if args.subset:
        wanted = {s.strip() for s in args.subset.split(",") if s.strip()}
        cells = [c for c in cells if c[0] in wanted]

    result = MCPMatrixResult()
    t0 = time.monotonic()

    async with mcp_session(
        "opp", SUITE_ROOT, env
    ) as opp_session, mcp_session(
        "ol", SUITE_ROOT, env
    ) as ol_session, mcp_session(
        "orf", SUITE_ROOT, env
    ) as orf_session:

        # Discover tools (sanity check)
        opp_tools = await opp_session.list_tools()
        ol_tools = await ol_session.list_tools()
        orf_tools = await orf_session.list_tools()
        print(f"  OPP tools: {[t['name'] for t in opp_tools][:5]}...")
        print(f"  OL  tools: {[t['name'] for t in ol_tools][:5]}...")
        print(f"  ORF tools: {[t['name'] for t in orf_tools][:5]}...", flush=True)

        for inp, outp, path in cells:
            cell_dir = tmp_root / f"mcp_{path}_{inp}_to_{outp}"
            cell_dir.mkdir(parents=True, exist_ok=True)
            src = cell_dir / f"sample.{inp}"
            if not _resolve_fixture(inp, src, args.corpus, SUITE_ROOT):
                result.cells.append(MCPCellResult(inp, outp, path, "skip", 0.0,
                                                  skip_reason=f"no fixture for {inp}"))
                continue
            c = await _run_one_cell_mcp(
                inp, outp, path, src, cell_dir,
                opp_session, ol_session, orf_session,
            )
            result.cells.append(c)
            print(f"  {c.inp} → {c.outp} ({c.path}): {c.status.upper()} ({c.duration_s:.1f}s)"
                  f"{'  ' + c.detail if c.detail else ''}"
                  f"{'  [' + c.skip_reason + ']' if c.skip_reason else ''}",
                  flush=True)

    result.total_duration_s = time.monotonic() - t0
    json_path = out_dir / "matrix.json"
    json_path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
                         encoding="utf-8")
    print(f"\nCells: {len(result.cells)} | Pass: {result.passed} | "
          f"Skip: {result.skipped} | Fail: {result.failed} | "
          f"Duration: {result.total_duration_s:.1f}s")
    print(f"JSON: {json_path}")
    return 0 if result.failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP matrix verifier")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--corpus", choices=["minimal", "real"], default="minimal")
    parser.add_argument("--path-filter", choices=["md", "xliff", "both"], default="both")
    parser.add_argument("--subset", type=str, default=None)
    args = parser.parse_args()
    return asyncio.run(_run_matrix(args))


if __name__ == "__main__":
    sys.exit(main())
