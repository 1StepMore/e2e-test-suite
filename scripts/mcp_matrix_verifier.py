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
# MCP client context (raw stdio JSON-RPC, no mcp library)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def mcp_session(which: str, cwd: Path, env: dict):
    """Start the raw-stdio MCP bridge and yield a session object."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-u", "scripts/mcp_bridge.py", which,
        cwd=str(cwd), env=env,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    session = _RawStdioSession(proc)
    await session.initialize()
    try:
        yield session
    finally:
        await session.close()


class _RawStdioSession:
    """Minimal async MCP session over raw stdio JSON-RPC."""

    def __init__(self, proc):
        self.proc = proc
        self._id = 0
        self._lock = asyncio.Lock()

    async def initialize(self):
        init_result = await self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "matrix-verifier", "version": "1.0"},
        })
        # Send initialized notification (no response expected)
        await self._notify("notifications/initialized", {})
        return init_result

    async def call_tool(self, name: str, arguments: dict) -> dict:
        result = await self._request("tools/call", {"name": name, "arguments": arguments})
        if "content" in result:
            text_parts = [c.get("text", "") for c in result["content"]]
            text = "\n".join(text_parts)
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"raw": text}
        return result

    async def list_tools(self) -> list:
        result = await self._request("tools/list", {})
        return result.get("tools", [])

    async def _request(self, method: str, params: dict) -> dict:
        self._id += 1
        msg = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        body = json.dumps(msg).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
        async with self._lock:
            self.proc.stdin.write(header + body)
            await self.proc.stdin.drain()
            return await self._read_response(self._id)

    async def _notify(self, method: str, params: dict) -> None:
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        body = json.dumps(msg).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
        async with self._lock:
            self.proc.stdin.write(header + body)
            await self.proc.stdin.drain()

    async def _read_response(self, expected_id: int) -> dict:
        # Read headers
        headers = {}
        while True:
            line = await self.proc.stdout.readline()
            if not line:
                raise RuntimeError("server closed stdout")
            line = line.decode("utf-8", errors="replace").strip()
            if not line:
                break
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        cl = int(headers.get("content-length", "0"))
        body = await self.proc.stdout.readexactly(cl)
        msg = json.loads(body.decode("utf-8"))
        if msg.get("id") != expected_id:
            raise RuntimeError(f"id mismatch: expected {expected_id}, got {msg.get('id')}")
        if "error" in msg:
            raise RuntimeError(f"server error: {msg['error']}")
        return msg.get("result", {})

    async def close(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            await asyncio.wait_for(self.proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            self.proc.terminate()
            await self.proc.wait()


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
            # Step 1: OPP extract → MD
            opp_resp = await _call_tool(opp_session, "extract_document", {
                "file_path": str(src),
                "output_formats": ["md"],
                "source_lang": "en",
                "target_lang": "zh",
                "output_dir": str(cell_dir / "opp"),
            })
            opp_tool = "extract_document"
            md_file = Path(opp_resp.get("md_path", ""))
            if not md_file.exists():
                # Try to find any .md in the output dir
                md_files = list((cell_dir / "opp").glob("*.md"))
                if not md_files:
                    return MCPCellResult(inp, outp, path, "fail", time.monotonic() - t0,
                                         opp_tool=opp_tool,
                                         detail=f"OPP MCP: no .md in output: {opp_resp}")
                md_file = md_files[0]

            # Step 2: OL translate
            ol_resp = await _call_tool(ol_session, "translate_md_text", {
                "file_path": str(md_file),
                "source_lang": "en",
                "target_lang": "zh",
                "output_dir": str(cell_dir / "ol"),
            })
            ol_tool = "translate_md_text"
            translated_md = Path(ol_resp.get("output_path", ""))
            if not translated_md.exists():
                # Try to find any .md in ol dir
                ol_mds = list((cell_dir / "ol").glob("*.md"))
                if not ol_mds:
                    return MCPCellResult(inp, outp, path, "fail", time.monotonic() - t0,
                                         opp_tool=opp_tool, ol_tool=ol_tool,
                                         detail=f"OL MCP: no translated .md: {ol_resp}")
                translated_md = ol_mds[0]

            # Step 3: ORF apply_md
            orf_out = cell_dir / f"result.{outp}"
            orf_resp = await _call_tool(orf_session, "apply_md", {
                "input_md": str(translated_md),
                "target_format": outp,
                "output_path": str(orf_out),
            })
            orf_tool = "apply_md"
            if not orf_out.exists():
                return MCPCellResult(inp, outp, path, "fail", time.monotonic() - t0,
                                     opp_tool=opp_tool, ol_tool=ol_tool, orf_tool=orf_tool,
                                     detail=f"ORF MCP: no output at {orf_out}: {orf_resp}")

            return MCPCellResult(inp, outp, path, "pass", time.monotonic() - t0,
                                 opp_tool=opp_tool, ol_tool=ol_tool, orf_tool=orf_tool)
        else:
            # XLIFF path
            opp_resp = await _call_tool(opp_session, "extract_document", {
                "file_path": str(src),
                "output_formats": ["xlf"],
                "source_lang": "en",
                "target_lang": "zh",
                "output_dir": str(cell_dir / "opp"),
            })
            opp_tool = "extract_document"
            xlf_files = list((cell_dir / "opp").glob("*.xlf"))
            if not xlf_files:
                return MCPCellResult(inp, outp, path, "fail", time.monotonic() - t0,
                                     opp_tool=opp_tool,
                                     detail=f"OPP MCP: no .xlf: {opp_resp}")
            xlf_file = xlf_files[0]

            ol_resp = await _call_tool(ol_session, "translate_xliff", {
                "input_path": str(xlf_file),
                "source_lang": "en",
                "target_lang": "zh",
                "output_path": str(cell_dir / "ol" / xlf_file.name),
            })
            ol_tool = "translate_xliff"
            ol_xlf = Path(ol_resp.get("output_path", ""))
            if not ol_xlf.exists():
                ol_xlfs = list((cell_dir / "ol").glob("*.xlf"))
                if not ol_xlfs:
                    return MCPCellResult(inp, outp, path, "fail", time.monotonic() - t0,
                                         opp_tool=opp_tool, ol_tool=ol_tool,
                                         detail=f"OL MCP: no translated .xlf: {ol_resp}")
                ol_xlf = ol_xlfs[0]

            orf_out = cell_dir / f"result.{outp}"
            orf_resp = await _call_tool(orf_session, "apply_xliff", {
                "input_file": str(xlf_file),
                "xliff_path": str(ol_xlf),
                "output_path": str(orf_out),
                "format": outp,
            })
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
        str(SUITE_ROOT / ".venv_ol" / "lib" / "python3.13" / "site-packages"),
    ]))
    # Allow MCP server to write to our output dirs
    env.setdefault("OPP_ALLOWED_DIRECTORIES", str(args.out_dir.resolve()))

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

    # Start all 3 servers via the raw-stdio bridge and reuse for all cells.
    # The bridge wraps the working CLI subprocesses (see scripts/mcp_bridge.py).
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
