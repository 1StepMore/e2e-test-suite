#!/usr/bin/env python3
"""MCP Client — direct STDIO JSON-RPC communication with Omni MCP servers.
Bypasses the gateway's MCP manager for reliable tool execution.

Usage:
    python mcp_client.py opp ping
    python mcp_client.py opp extract_document --file_path=/path/to/doc.docx
    python mcp_client.py ol translate_md_text --content="Hello" --source_lang=en --target_lang=zh
    python mcp_client.py orf apply_md --input_md="# Hello" --target_format=docx --output_path=/tmp/out.docx
"""

import asyncio
import json
import os
import sys


# Load .env vars from OL project directory
def _load_env(env_path: str) -> dict:
    """Load a .env file and return a dict of variables."""
    result = {}
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'\"")
                result[key] = value
    except FileNotFoundError:
        pass
    return result


_OL_ENV = _load_env(
    "/mnt/d/Hermes-Workspace/01-Projects/e2e-test-suite/Omni_Localizer/.env"
)

# Server definitions matching the global config
SERVERS = {
    "opp": {
        "command": "/home/renanzai/.hermes/venvs/omni-localizer/bin/python",
        "args": ["-m", "opp.mcp.server"],
        "env": {
            "OPP_MCP_ALLOWED_DIRS": "/mnt/d/Hermes-Workspace:/home/renanzai",
            "OPP_MCP_MAX_FILE_SIZE": "100000000",
            "PYTHONPATH": "/mnt/d/Hermes-Workspace/01-Projects/e2e-test-suite/Omni_Pre_Processor/src",
        },
    },
    "ol": {
        "command": "/home/renanzai/.hermes/venvs/omni-localizer/bin/python",
        "args": ["-m", "ol_mcp"],
        "env": {
            "MCP_ALLOWED_DIRECTORIES": "/mnt/d/Hermes-Workspace,/tmp,/home/renanzai",
            "PYTHONPATH": "/mnt/d/Hermes-Workspace/01-Projects/e2e-test-suite/Omni_Localizer/src",
            "OL_CONFIG_PATH": "/mnt/d/Hermes-Workspace/01-Projects/e2e-test-suite/Omni_Localizer/config/default.yaml",
        },
    },
    "orf": {
        "command": "/home/renanzai/.hermes/venvs/omni-localizer/bin/python",
        "args": ["-m", "orf.mcp.server"],
        "env": {
            "PYTHONPATH": "/mnt/d/Hermes-Workspace/01-Projects/e2e-test-suite/Omni_Re_Formatter/src",
            "ORF_MCP_ALLOWED_DIRS": "/mnt/d/Hermes-Workspace:/tmp:/home/renanzai",
            "ORF_MCP_MAX_FILE_SIZE": "100",
        },
    },
}


class MCPClient:
    """Direct MCP client over STDIO JSON-RPC."""

    def __init__(self, server_name: str):
        if server_name not in SERVERS:
            raise ValueError(f"Unknown server: {server_name}. Choose from: {list(SERVERS.keys())}")
        cfg = SERVERS[server_name]
        self.server_name = server_name
        self.cfg = cfg
        self.proc = None
        self._req_id = 0

    async def _connect(self):
        env = os.environ.copy()
        env.update(self.cfg["env"])
        # For OL server, also inject .env vars (API keys)
        if self.server_name == "ol":
            for k, v in _OL_ENV.items():
                if k not in env:
                    env[k] = v
        self.proc = await asyncio.create_subprocess_exec(
            self.cfg["command"],
            *self.cfg["args"],
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        # Initialize handshake
        await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "hermes-e2e", "version": "1.0"},
        })

        # Send initialized notification
        await self._send_notification("notifications/initialized")

    async def _send_request(self, method: str, params: dict = None) -> dict:
        self._req_id += 1
        req = {
            "jsonrpc": "2.0",
            "id": self._req_id,
            "method": method,
        }
        if params is not None:
            req["params"] = params
        self.proc.stdin.write((json.dumps(req) + "\n").encode())
        await self.proc.stdin.drain()

        # Read response — increase buffer limit for large payloads (S5 scale, 68KB+)
        self.proc.stdout._limit = 4 * 1024 * 1024  # 4 MB
        line = await asyncio.wait_for(self.proc.stdout.readline(), timeout=120)
        resp = json.loads(line.decode().strip())
        if "error" in resp:
            raise RuntimeError(f"MCP error: {resp['error']}")
        return resp.get("result", {})

    async def _send_notification(self, method: str):
        notif = {"jsonrpc": "2.0", "method": method}
        self.proc.stdin.write((json.dumps(notif) + "\n").encode())
        await self.proc.stdin.drain()

    async def call_tool(self, tool_name: str, arguments: dict = None) -> dict:
        """Call an MCP tool and return the result content."""
        result = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments or {},
        })
        return result

    async def list_tools(self) -> list:
        """List available tools from the server."""
        result = await self._send_request("tools/list")
        return result.get("tools", [])

    async def close(self):
        if self.proc:
            try:
                self.proc.terminate()
                await asyncio.wait_for(self.proc.wait(), timeout=5)
            except:
                self.proc.kill()
            self.proc = None

    async def __aenter__(self):
        await self._connect()
        return self

    async def __aexit__(self, *args):
        await self.close()


def _parse_args():
    """Parse CLI arguments: <server> <tool> [--key=value ...]"""
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    server_name = sys.argv[1]
    tool_name = sys.argv[2]

    # Parse key=value arguments
    arguments = {}
    for arg in sys.argv[3:]:
        if arg.startswith("--"):
            arg = arg[2:]
        if "=" in arg:
            key, value = arg.split("=", 1)
            # Try to parse JSON values
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                pass
            arguments[key] = value

    return server_name, tool_name, arguments


async def _main():
    server_name, tool_name, arguments = _parse_args()

    if tool_name == "list_tools":
        async with MCPClient(server_name) as client:
            tools = await client.list_tools()
            print(f"\n{'─' * 60}")
            print(f"  {server_name.upper()} MCP — {len(tools)} tools")
            print(f"{'─' * 60}")
            for t in tools:
                name = t.get("name", "?")
                desc = t.get("description", "")
                if desc:
                    print(f"  • {name:<35s} {desc[:80]}")
                else:
                    print(f"  • {name}")
            return

    async with MCPClient(server_name) as client:
        # For ping, just verify connection
        if tool_name == "ping":
            tools = await client.list_tools()
            print(f"✅ {server_name} MCP connected — {len(tools)} tools available")
            return

        # Call the tool
        result = await client.call_tool(tool_name, arguments)

        # Extract text content
        content = result.get("content", [])
        text_parts = []
        for block in content:
            if block.get("type") == "text":
                text_parts.append(block["text"])
            elif block.get("type") == "resource":
                text_parts.append(str(block.get("resource", {})))

        output = "\n".join(text_parts)
        if output:
            print(output)
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
