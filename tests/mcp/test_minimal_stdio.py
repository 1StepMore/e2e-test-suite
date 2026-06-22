#!/usr/bin/env python3
"""
Phase 1.1 — Critical MCP stdio validation.

Tests whether the standard `mcp` library's `stdio_server()` transport works
correctly in this environment.

Background:
  fastmcp 3.4.2 has a known stdio transport bug: the server starts and reads
  stdin but never writes responses to JSON-RPC requests. We plan to replace
  fastmcp with the standard `mcp` library (mcp 1.27.2).

This test validates the stdio transport at TWO levels:
  1. RAW JSON-RPC over subprocess stdin/stdout (wire-level validation)
  2. Full ClientSession via stdio_client (library-level validation)
"""

import sys
import json
import subprocess
import time
import os
import threading
import queue
import select
import textwrap


# ─── Minimal MCP Server Code (spawned as subprocess) ───────────────────

SERVER_CODE = textwrap.dedent("""\
    import sys
    import anyio
    from mcp.server import Server
    from mcp import stdio_server
    from mcp.types import Tool, TextContent

    server = Server("test-server")

    @server.list_tools()
    async def list_tools():
        return [
            Tool(
                name="ping",
                description="Simple ping tool",
                inputSchema={"type": "object", "properties": {}},
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        if name == "ping":
            return [TextContent(type="text", text="pong")]
        raise ValueError(f"Unknown tool: {name}")

    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
                raise_exceptions=False,
            )

    if __name__ == "__main__":
        anyio.run(main)
""")


# ─── Helper Functions ──────────────────────────────────────────────────

def send_jsonrpc(stdin, request: dict) -> None:
    """Send a JSON-RPC message as a single line to the server's stdin."""
    line = json.dumps(request, ensure_ascii=False, separators=(",", ":")) + "\n"
    stdin.write(line)
    stdin.flush()


def read_line_with_timeout(stream, timeout: float = 10.0) -> str:
    """
    Read a line from a text stream with a timeout.

    Uses a background thread because select.select() on TextIOWrapper
    with bufsize=0 has known issues (threading is more reliable).
    """
    result_queue = queue.Queue()

    def reader():
        try:
            line = stream.readline()
            result_queue.put(line)
        except Exception as e:
            result_queue.put(e)

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    try:
        result = result_queue.get(timeout=timeout)
        if isinstance(result, Exception):
            raise IOError(f"Error reading from stream: {result}") from result
        return result
    except queue.Empty:
        raise TimeoutError(
            f"Timed out waiting for response after {timeout}s"
        )


def read_jsonrpc(stdout, timeout: float = 10.0) -> dict:
    """Read a JSON-RPC response line with timeout."""
    line = read_line_with_timeout(stdout, timeout=timeout)
    if not line:
        raise ConnectionError("Server closed stdout (process may have crashed)")
    return json.loads(line)


def spawn_server() -> subprocess.Popen:
    """Start the minimal MCP server as a subprocess."""
    proc = subprocess.Popen(
        [sys.executable, "-u", "-c", SERVER_CODE],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0,  # unbuffered — critical for stdio_server
    )
    return proc


def drain_stderr(proc: subprocess.Popen, timeout: float = 1.0) -> str:
    """Read any remaining stderr output from the process."""
    result = ""
    r = threading.Thread(target=lambda: result + proc.stderr.read(), daemon=True)
    # Simple approach: just try to read with timeout
    try:
        r, w, x = select.select([proc.stderr], [], [], timeout)
        if r:
            return proc.stderr.read()
    except Exception:
        pass
    return ""


# ─── Test 1: Raw JSON-RPC over stdio ──────────────────────────────────

def test_raw_jsonrpc_stdio() -> dict:
    """
    Test 1: Wire-level validation.

    Spawn the server as a subprocess, send raw JSON-RPC messages, and
    validate responses.
    """
    print("=" * 70)
    print("TEST 1: Raw JSON-RPC over subprocess stdin/stdout")
    print("=" * 70)

    proc = spawn_server()
    results = {"steps": {}}

    try:
        # ── Step 1: Initialize ──
        print("\n[Step 1] Sending initialize request...")
        send_jsonrpc(proc.stdin, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        })

        resp = read_jsonrpc(proc.stdout, timeout=12.0)
        assert resp.get("id") == 1, f"Expected id=1, got id={resp.get('id')}"
        assert "result" in resp, f"Expected 'result' in response: {resp}"
        server_info = resp["result"].get("serverInfo", {})
        assert server_info.get("name") == "test-server", \
            f"Expected server name 'test-server', got {server_info}"
        print(f"  OK: name={server_info['name']}, "
              f"version={server_info.get('version', '(none)')}")
        results["steps"]["initialize"] = {"status": "pass", "server_info": server_info}

        # ── Step 2: Initialized notification ──
        print("\n[Step 2] Sending initialized notification...")
        send_jsonrpc(proc.stdin, {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        })
        # Notifications don't get responses; wait briefly
        time.sleep(0.3)
        print(f"  OK: notification sent (no response expected)")
        results["steps"]["initialized"] = {"status": "pass"}

        # ── Step 3: List Tools ──
        print("\n[Step 3] Sending tools/list request...")
        send_jsonrpc(proc.stdin, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
        })

        resp = read_jsonrpc(proc.stdout, timeout=10.0)
        assert resp.get("id") == 2, f"Expected id=2, got id={resp.get('id')}"
        assert "result" in resp, f"Expected 'result' in response: {resp}"
        tools = resp["result"].get("tools", [])
        tool_names = [t["name"] for t in tools]
        assert "ping" in tool_names, \
            f"Expected 'ping' tool, got: {tool_names}"
        print(f"  OK: tools={tool_names}")
        results["steps"]["list_tools"] = {"status": "pass", "tools": tool_names}

        # ── Step 4: Call ping tool ──
        print("\n[Step 4] Calling tools/call for 'ping'...")
        send_jsonrpc(proc.stdin, {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "ping",
                "arguments": {},
            },
        })

        resp = read_jsonrpc(proc.stdout, timeout=10.0)
        assert resp.get("id") == 3, f"Expected id=3, got id={resp.get('id')}"
        assert "result" in resp, f"Expected 'result' in response: {resp}"
        content = resp["result"].get("content", [])
        text = content[0].get("text", "") if content else ""
        assert "pong" in text, f"Expected text containing 'pong', got: {text}"
        assert resp["result"].get("isError") is False, \
            f"Expected isError=false, got: {resp['result']}"
        print(f"  OK: {text}")
        results["steps"]["call_tool"] = {"status": "pass", "response": text}

        print("\n" + "-" * 50)
        print("TEST 1 RESULT: PASS - All 4 JSON-RPC steps succeeded")
        print("-" * 50)
        results["overall"] = "pass"

    except (AssertionError, TimeoutError, ConnectionError, json.JSONDecodeError,
            IOError) as e:
        stderr_output = ""
        try:
            r, w, x = select.select([proc.stderr], [], [], 1.0)
            if r:
                stderr_output = proc.stderr.read()
        except Exception:
            pass
        print(f"\n  FAILED: {e}")
        if stderr_output:
            print(f"\n  [Server stderr]:\n{stderr_output[:2000]}")
        results["overall"] = "fail"
        results["error"] = str(e)
        results["stderr"] = stderr_output

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

        stderr_output = proc.stderr.read()
        if stderr_output and not results.get("stderr"):
            results["stderr"] = stderr_output[:2000]

    return results


# ─── Test 2: Full ClientSession via stdio_client ──────────────────────

async def _client_session_stdio() -> dict:
    """Library-level validation using mcp's stdio_client + ClientSession."""
    import anyio
    from mcp import StdioServerParameters, stdio_client
    from mcp.client.session import ClientSession

    print("\n" + "=" * 70)
    print("TEST 2: Full ClientSession via stdio_client")
    print("=" * 70)

    results = {"steps": {}}

    import tempfile
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(SERVER_CODE)
        server_path = f.name

    try:
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-u", server_path],
        )

        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                # ── Step 1: Initialize ──
                print("\n[Step 1] session.initialize()...")
                init_result = await session.initialize()
                print(f"  OK: serverInfo={init_result.serverInfo!r}")
                results["steps"]["initialize"] = {
                    "status": "pass",
                    "server_info": {
                        "name": init_result.serverInfo.name,
                        "version": init_result.serverInfo.version,
                    },
                }

                # ── Step 2: List Tools ──
                print("\n[Step 2] session.list_tools()...")
                tools_result = await session.list_tools()
                tool_names = [t.name for t in tools_result.tools]
                assert "ping" in tool_names, \
                    f"Expected 'ping' tool, got: {tool_names}"
                print(f"  OK: tools={tool_names}")
                results["steps"]["list_tools"] = {
                    "status": "pass",
                    "tools": tool_names,
                }

                # ── Step 3: Call ping tool ──
                print("\n[Step 3] session.call_tool('ping')...")
                call_result = await session.call_tool("ping", {})
                text = ""
                for c in call_result.content:
                    if hasattr(c, "text"):
                        text += c.text
                assert "pong" in text, \
                    f"Expected 'pong', got: {text!r}"
                assert call_result.isError is False
                print(f"  OK: {text}")
                results["steps"]["call_tool"] = {
                    "status": "pass",
                    "response": text,
                }

        print("\n" + "-" * 50)
        print("TEST 2 RESULT: PASS - All 3 ClientSession steps succeeded")
        print("-" * 50)
        results["overall"] = "pass"

    except Exception as e:
        import traceback
        print(f"\n  FAILED: {e}")
        traceback.print_exc()
        results["overall"] = "fail"
        results["error"] = str(e)
        results["traceback"] = traceback.format_exc()

    finally:
        try:
            os.unlink(server_path)
        except OSError:
            pass

    return results


# ─── Main: Run Tests ───────────────────────────────────────────────────

def main():
    """Run both tests and report results clearly."""
    print()
    print("=" * 70)
    print("  Phase 1.1 - Critical MCP stdio validation")
    print("  Testing: mcp library v1.27.2 - stdio_server() transport")
    print("=" * 70)
    print()

    result1 = test_raw_jsonrpc_stdio()

    result2 = {"overall": "skipped"}
    if result1["overall"] == "pass":
        import anyio
        result2 = anyio.run(_client_session_stdio)
    else:
        print("\n" + "-" * 50)
        print("TEST 2: SKIPPED (Test 1 must pass first)")
        print("-" * 50)

    # ── Final Report ──
    print()
    print("=" * 70)
    print("  F I N A L   V E R D I C T")
    print("=" * 70)
    print()

    test1_status = "PASS" if result1["overall"] == "pass" else "FAIL"
    test2_status = "PASS" if result2["overall"] == "pass" else \
                   "SKIPPED" if result2["overall"] == "skipped" else "FAIL"

    print(f"  Test 1 (Raw JSON-RPC stdio):     {test1_status}")
    print(f"  Test 2 (ClientSession stdio):     {test2_status}")

    if result1["overall"] == "fail":
        print()
        print("  THE STANDARD MCP LIBRARY STDIO TRANSPORT DOES NOT WORK.")
        print()
        print("  Error details:")
        print(f"    {result1.get('error', 'unknown error')}")
        if result1.get("stderr"):
            print(f"    Server stderr: {result1['stderr'][:500]}")
        print()
        print("  Recommendation: Implement raw stdio JSON-RPC fallback")
        print("  (estimated 4h cost as documented).")
    else:
        print()
        print("  THE STANDARD MCP LIBRARY STDIO TRANSPORT WORKS!")
        print()
        print("  The server-side stdio transport (stdio_server + Server.run)")
        print("  correctly handles all JSON-RPC messages over stdin/stdout.")
        print()
        if result2["overall"] == "pass":
            print("  The FULL client-server stdio stack (stdio_client +")
            print("  ClientSession) also works correctly.")
        print()
        print("  IMPORTANT NOTES:")
        print("  - Subprocess must use `-u` (unbuffered Python) + `bufsize=0`")
        print("  - Response timeout should be >10s for cold starts")
        print("  - threading-based read timeout is recommended over select.select")
        print()
        print("  This means fastmcp 3.4.2 can be safely replaced with the")
        print("  standard mcp library (mcp 1.27.2) for OPP/OL/ORF MCP servers.")

    print()
    print("=" * 70)
    print()

    return 0 if result1["overall"] == "pass" else 1


# ─── Client Code Templates ────────────────────────────────────────────

SERVER_SIDE_TEMPLATE = """
# ======================================================================
#  SERVER-SIDE TEMPLATE - Standard MCP Library (mcp 1.27.2)
#
#  Replace existing fastmcp-based server with this pattern.
#
#  CRITICAL: Must use python -u (unbuffered) or bufsize=0 when spawning.
# ======================================================================

import anyio
from mcp.server import Server
from mcp import stdio_server
from mcp.types import Tool, TextContent

server = Server(
    "my-server-name",
    version="1.0.0",
    instructions="My MCP server",
)

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="my_tool",
            description="What this tool does",
            inputSchema={
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "Parameter description",
                    },
                },
                "required": ["param1"],
            },
        ),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "my_tool":
        result = f"Processed: {arguments.get('param1')}"
        return [TextContent(type="text", text=result)]
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
            raise_exceptions=False,
        )

if __name__ == "__main__":
    anyio.run(main)
"""

CLIENT_SIDE_TEMPLATE = """
# ======================================================================
#  CLIENT-SIDE TEMPLATE - via stdio_client + ClientSession
# ======================================================================

import anyio
from mcp import StdioServerParameters, stdio_client
from mcp.client.session import ClientSession

async def call_mcp_tool(
    server_command: str,
    server_args: list[str],
    tool_name: str,
    tool_args: dict,
) -> str:
    server_params = StdioServerParameters(
        command=server_command,
        args=server_args,
    )
    async with stdio_client(server_params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, tool_args)
            text = ""
            for c in result.content:
                if hasattr(c, "text"):
                    text += c.text
            return text
"""


if __name__ == "__main__":
    exit_code = main()
    if exit_code == 0:
        print()
        print("=" * 70)
        print("  TEMPLATES FOR OPP/OL/ORF REWRITE")
        print("=" * 70)
        print(SERVER_SIDE_TEMPLATE)
        print(CLIENT_SIDE_TEMPLATE)
    sys.exit(exit_code)
