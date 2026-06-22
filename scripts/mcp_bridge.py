"""Minimal stdio JSON-RPC server for MCP tool calls.

Avoids the `mcp.server.stdio` import which blocks in this environment.
Implements just enough of the MCP stdio protocol (Content-Length framed
JSON-RPC) to serve the 5 tools needed by the matrix verifier.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SUITE_ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable
ENV_BASE = {
    "OMNI_TEST_FAKE_LLM": "1",
    "OMNI_TEST_FAKE_PANDOC": "1",
    "PATH": os.environ.get("PATH", ""),
}


def _run_cli(module: str, args: list[str], cwd: Path, env_extra: dict | None = None,
             timeout: int = 120) -> dict:
    env = {**ENV_BASE, **(env_extra or {})}
    cmd = [PYTHON, "-u", "-m", module, *args]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=env, cwd=str(cwd), timeout=timeout,
        )
        if result.returncode != 0:
            return {"error": (result.stderr or f"exit {result.returncode}")[:500]}
        stdout = result.stdout.strip()
        if stdout.startswith("{"):
            return json.loads(stdout)
        return {"output": stdout}
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def opp_extract_document(file_path: str, output_formats=None, source_lang: str = "en",
                         target_lang: str = "zh", output_dir: str = None, **kwargs) -> dict:
    if output_formats is None:
        output_formats = ["md"]
    fmt = "both" if "both" in output_formats else output_formats[0]
    if not output_dir:
        output_dir = str(Path(file_path).parent / "opp_out")
    args = [file_path, "--target-format", fmt, "--source-lang", source_lang,
            "--target-lang", target_lang, "--output-dir", output_dir]
    return _run_cli("opp.cli", args, SUITE_ROOT / "Omni_Pre_Processor",
                    {"OPP_ALLOWED_DIRECTORIES": str(Path(file_path).parent)})


def ol_translate_md(file_path: str, source_lang: str = "en", target_lang: str = "zh",
                     output_dir: str = None, **kwargs) -> dict:
    if not output_dir:
        output_dir = str(Path(file_path).parent / "ol_out")
    args = [file_path, "-s", source_lang, "-t", target_lang, "-o", output_dir, "--json"]
    return _run_cli("ol_cli", ["translate-md", *args], SUITE_ROOT / "Omni_Localizer")


def ol_translate_xliff(input_path: str, source_lang: str = "en", target_lang: str = "zh",
                       output_path: str = None, **kwargs) -> dict:
    if not output_path:
        output_path = str(Path(input_path).parent / (Path(input_path).stem + ".out.xlf"))
    args = [input_path, "-s", source_lang, "-t", target_lang,
            "-o", str(Path(output_path).parent), "--json"]
    return _run_cli("ol_cli", ["translate-xliff", *args], SUITE_ROOT / "Omni_Localizer")


def orf_apply_md(input_md: str, target_format: str, output_path: str = None, **kwargs) -> dict:
    if not output_path:
        output_path = str(Path(input_md).parent / f"result.{target_format}")
    args = [input_md, "--target-format", target_format, "--output", output_path, "--json"]
    return _run_cli("orf.cli", ["apply-md", *args], SUITE_ROOT / "Omni_Re_Formatter")


def orf_apply_xliff(input_file: str, xliff_path: str, output_path: str = None,
                    format: str = "docx", **kwargs) -> dict:
    if not output_path:
        output_path = str(Path(input_file).parent / f"result.{format}")
    args = [input_file, "--xliff", xliff_path, "--output", output_path,
            "--format", format, "--force", "--json"]
    return _run_cli("orf.cli", ["apply-xliff", *args], SUITE_ROOT / "Omni_Re_Formatter")


def ping() -> dict:
    return {"status": "ok", "transport": "stdio-raw"}


TOOLS = {
    "opp": {"extract_document": opp_extract_document, "ping": ping},
    "ol": {"translate_md_text": ol_translate_md, "translate_xliff": ol_translate_xliff, "ping": ping},
    "orf": {"apply_md": orf_apply_md, "apply_xliff": orf_apply_xliff, "ping": ping},
}

SCHEMAS = {
    "opp": [
        {"name": "extract_document", "description": "Extract document (OPP)",
         "inputSchema": {"type": "object", "required": ["file_path"],
                         "properties": {"file_path": {"type": "string"},
                                        "output_formats": {"type": "array"},
                                        "source_lang": {"type": "string"},
                                        "target_lang": {"type": "string"},
                                        "output_dir": {"type": "string"}}}},
        {"name": "ping", "description": "Health check",
         "inputSchema": {"type": "object", "properties": {}}},
    ],
    "ol": [
        {"name": "translate_md_text", "description": "Translate MD (OL)",
         "inputSchema": {"type": "object", "required": ["file_path"],
                         "properties": {"file_path": {"type": "string"},
                                        "source_lang": {"type": "string"},
                                        "target_lang": {"type": "string"},
                                        "output_dir": {"type": "string"}}}},
        {"name": "translate_xliff", "description": "Translate XLIFF (OL)",
         "inputSchema": {"type": "object", "required": ["input_path"],
                         "properties": {"input_path": {"type": "string"},
                                        "source_lang": {"type": "string"},
                                        "target_lang": {"type": "string"},
                                        "output_path": {"type": "string"}}}},
        {"name": "ping", "description": "Health check",
         "inputSchema": {"type": "object", "properties": {}}},
    ],
    "orf": [
        {"name": "apply_md", "description": "Apply MD to format (ORF)",
         "inputSchema": {"type": "object", "required": ["input_md", "target_format"],
                         "properties": {"input_md": {"type": "string"},
                                        "target_format": {"type": "string"},
                                        "output_path": {"type": "string"}}}},
        {"name": "apply_xliff", "description": "Apply XLIFF (ORF)",
         "inputSchema": {"type": "object", "required": ["input_file", "xliff_path"],
                         "properties": {"input_file": {"type": "string"},
                                        "xliff_path": {"type": "string"},
                                        "output_path": {"type": "string"},
                                        "format": {"type": "string"}}}},
        {"name": "ping", "description": "Health check",
         "inputSchema": {"type": "object", "properties": {}}},
    ],
}


def _send_response(msg_id, result):
    body = json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result}).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
    sys.stdout.buffer.flush()


def _send_error(msg_id, code, message):
    body = json.dumps({"jsonrpc": "2.0", "id": msg_id,
                        "error": {"code": code, "message": message}}).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
    sys.stdout.buffer.flush()


def _read_message() -> dict | None:
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        line = line.decode("utf-8", errors="replace").strip()
        if not line:
            break
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    cl = headers.get("content-length")
    if not cl:
        return None
    body = sys.stdin.buffer.read(int(cl))
    return json.loads(body.decode("utf-8"))


def _handle_request(msg: dict, tools: dict, schemas: list) -> None:
    method = msg.get("method")
    msg_id = msg.get("id")
    params = msg.get("params", {})

    if method == "initialize":
        _send_response(msg_id, {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "omni-bridge", "version": "1.0"},
            "capabilities": {"tools": {}},
        })
    elif method == "notifications/initialized":
        pass
    elif method == "tools/list":
        _send_response(msg_id, {"tools": schemas})
    elif method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        if name not in tools:
            _send_error(msg_id, -32601, f"unknown tool: {name}")
            return
        try:
            func = tools[name]
            result = func() if name == "ping" else func(**arguments)
            text = result if isinstance(result, str) else json.dumps(result, default=str)
            _send_response(msg_id, {"content": [{"type": "text", "text": text}]})
        except Exception as e:
            _send_error(msg_id, -32603, f"{type(e).__name__}: {e}")
    elif method == "ping":
        _send_response(msg_id, {"status": "ok"})
    else:
        _send_error(msg_id, -32601, f"unknown method: {method}")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("opp", "ol", "orf"):
        print("Usage: mcp_bridge.py {opp|ol|orf}", file=sys.stderr)
        sys.exit(1)
    which = sys.argv[1]
    tools = TOOLS[which]
    schemas = SCHEMAS[which]
    while True:
        try:
            msg = _read_message()
        except (EOFError, KeyboardInterrupt, json.JSONDecodeError):
            break
        if msg is None:
            break
        _handle_request(msg, tools, schemas)


if __name__ == "__main__":
    main()
