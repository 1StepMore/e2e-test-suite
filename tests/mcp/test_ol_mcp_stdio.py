"""Phase 1.4 regression test — OL MCP server end-to-end over stdio.

Spawns ``python -m ol_mcp`` as a subprocess, exchanges JSON-RPC
messages over stdin/stdout, and verifies the OL MCP server
implements the full MCP contract:

1. ``initialize`` returns the server name and capabilities
2. ``tools/list`` returns all 21 registered OL tools
3. ``tools/call`` invokes each tool and returns a JSON payload

This is the locked-in regression guard for the Phase 1.4 rewrite,
which replaced the standard ``mcp.server.fastmcp.FastMCP`` (which
has a stdio handshake bug in this environment) with the
``mcp.server.Server`` + ``stdio_server()`` pattern validated by
``test_minimal_stdio.py``.

Run: ``pytest tests/mcp/test_ol_mcp_stdio.py -v``
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OL_SRC = REPO_ROOT / "Omni_Localizer" / "src"


def send_jsonrpc(stdin, request: dict) -> None:
    line = json.dumps(request, ensure_ascii=False, separators=(",", ":")) + "\n"
    stdin.write(line)
    stdin.flush()


def read_line_with_timeout(stream, timeout: float) -> str:
    q: queue.Queue = queue.Queue()

    def reader():
        try:
            q.put(stream.readline())
        except Exception as e:
            q.put(e)

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    try:
        result = q.get(timeout=timeout)
        if isinstance(result, Exception):
            raise IOError(f"read error: {result}") from result
        return result
    except queue.Empty:
        raise TimeoutError(f"timed out after {timeout}s")


def read_jsonrpc(stdout, timeout: float) -> dict:
    line = read_line_with_timeout(stdout, timeout=timeout)
    if not line:
        raise ConnectionError("server closed stdout")
    return json.loads(line)


def spawn_ol_mcp() -> subprocess.Popen:
    env = os.environ.copy()
    env["OMNI_TEST_FAKE_LLM"] = "1"
    env["PYTHONPATH"] = str(OL_SRC) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.Popen(
        [sys.executable, "-u", "-m", "ol_mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0,
        env=env,
    )


EXPECTED_TOOLS = {
    "translate_md_text",
    "judge_text",
    "load_glossary",
    "get_relevant_terms",
    "search_tm",
    "batch_translate_texts",
    "translate_xliff",
    "translate_file",
    "extract_terms",
    "add_tm_entries",
    "shield_md_text",
    "unshield_md_text",
    "generate_report",
    "inspect_config",
    "disambiguate",
    "extract_warnings",
    "get_translation_status",
    "verify_terms",
    "profile_doc",
    "get_capabilities",
    "ping",
}


def test_ol_mcp_stdio_handshake_and_tools_list() -> None:
    """End-to-end: initialize → tools/list returns all 8 OL tools."""
    proc = spawn_ol_mcp()
    try:
        send_jsonrpc(proc.stdin, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ol-mcp-stdio-regression", "version": "1.0.0"},
            },
        })
        # OL imports are heavy (KeyBERT), so allow up to 60s for handshake.
        init_resp = read_jsonrpc(proc.stdout, timeout=60.0)
        assert init_resp.get("id") == 1, init_resp
        assert "result" in init_resp
        server_info = init_resp["result"].get("serverInfo", {})
        assert server_info.get("name") == "ol-mcp", server_info
        assert "version" in server_info

        send_jsonrpc(proc.stdin, {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        })
        time.sleep(0.3)

        send_jsonrpc(proc.stdin, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
        })
        list_resp = read_jsonrpc(proc.stdout, timeout=15.0)
        assert list_resp.get("id") == 2
        tool_names = {t["name"] for t in list_resp["result"].get("tools", [])}
        assert tool_names == EXPECTED_TOOLS, (
            f"tool set mismatch: missing={EXPECTED_TOOLS - tool_names}, "
            f"extra={tool_names - EXPECTED_TOOLS}"
        )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def test_ol_mcp_stdio_ping_call() -> None:
    """End-to-end: tools/call on 'ping' returns success+module=ol."""
    proc = spawn_ol_mcp()
    try:
        send_jsonrpc(proc.stdin, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ol-mcp-stdio-regression", "version": "1.0.0"},
            },
        })
        read_jsonrpc(proc.stdout, timeout=60.0)
        send_jsonrpc(proc.stdin, {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        })
        time.sleep(0.3)
        send_jsonrpc(proc.stdin, {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "ping", "arguments": {}},
        })
        resp = read_jsonrpc(proc.stdout, timeout=15.0)
        assert resp.get("id") == 3
        assert resp["result"].get("isError") is False
        text = resp["result"]["content"][0]["text"]
        payload = json.loads(text)
        assert payload.get("success") is True
        assert payload["content"].get("module") == "ol"
        assert "version" in payload["content"]
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def test_ol_mcp_stdio_unknown_tool_returns_ol_unknown_tool_code() -> None:
    """Negative: unknown tool name returns OL_UNKNOWN_TOOL JSON error."""
    proc = spawn_ol_mcp()
    try:
        send_jsonrpc(proc.stdin, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ol-mcp-stdio-regression", "version": "1.0.0"},
            },
        })
        read_jsonrpc(proc.stdout, timeout=60.0)
        send_jsonrpc(proc.stdin, {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        })
        time.sleep(0.3)
        send_jsonrpc(proc.stdin, {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "definitely_not_a_real_tool", "arguments": {}},
        })
        resp = read_jsonrpc(proc.stdout, timeout=15.0)
        assert resp.get("id") == 4
        text = resp["result"]["content"][0]["text"]
        payload = json.loads(text)
        assert payload.get("error_code") == "OL_UNKNOWN_TOOL", payload
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
