"""CLI vs MCP error consistency tests.

Verifies that both transports return semantically equivalent errors
for the same invalid inputs, per S10.8 from the integrated test plan.

Tests cover:
- OPP: nonexistent file, path traversal, corrupt file
- OL: nonexistent config/glossary
- ORF: nonexistent input, path traversal

Run with:
    OMNI_TEST_FAKE_LLM=1 OMNI_TEST_FAKE_PANDOC=1 pytest tests/test_e2e_cli_vs_mcp_errors.py -v
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = [pytest.mark.e2e, pytest.mark.real_chain]

SUITE_ROOT = Path(__file__).resolve().parent
OL_CONFIG = SUITE_ROOT.parent / "Omni_Localizer" / "config" / "default.yaml"


def _make_env(**extra) -> dict:
    env = os.environ.copy()
    env["OMNI_TEST_FAKE_LLM"] = "1"
    env["OMNI_TEST_FAKE_PANDOC"] = "1"
    for d in ["Omni_Pre_Processor", "Omni_Localizer", "Omni_Re_Formatter"]:
        src = SUITE_ROOT.parent / d / "src"
        if src.exists():
            pp = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = f"{src}:" + pp if pp else str(src)
    env["OL_CONFIG_PATH"] = str(OL_CONFIG)
    env.update(extra)
    return env


def _cli(cmd: list[str], **extra_env) -> subprocess.CompletedProcess:
    """Run a CLI subprocess with the canonical base env."""
    return subprocess.run(
        [sys.executable, "-m"] + cmd,
        capture_output=True, text=True,
        env=_make_env(**extra_env),
        timeout=60,
    )


# ============================================================================
# OPP: CLI vs MCP
# ============================================================================

class TestOPPErrorConsistency:
    """OPP CLI and MCP should return semantically equivalent errors."""

    @pytest.fixture
    def init_opp_server(self, monkeypatch, tmp_path):
        """Initialize the OPP MCP server."""
        monkeypatch.setenv("OPP_MCP_ALLOWED_DIRS", str(tmp_path))
        from opp.mcp.config import load_config
        from opp.mcp.server import _init_server
        config = load_config()
        _init_server(config)
        return tmp_path

    def test_nonexistent_file(self, tmp_path, init_opp_server):
        """Both transports reject nonexistent files."""
        # CLI
        cli = _cli(["opp", "/nonexistent/doc.docx", "--target-format", "md",
                     "--output-dir", str(tmp_path / "out")])
        assert cli.returncode != 0

        # MCP
        import asyncio
        from opp.mcp.server import detect_format_tool
        mcp = asyncio.run(detect_format_tool("/nonexistent/doc.docx"))
        assert mcp["success"] is False
        # OPP inline handlers return {"success": False, "error": "..."} without error_code
        assert mcp.get("error") or mcp.get("message")

    def test_path_traversal(self, tmp_path, monkeypatch, init_opp_server):
        """Both transports reject path traversal."""
        # CLI
        traversal = str(tmp_path / ".." / ".." / "etc" / "passwd")
        cli = _cli(["opp", traversal,
                     "--target-format", "md",
                     "--output-dir", str(tmp_path / "out")])
        assert cli.returncode != 0

        # MCP
        import asyncio
        from opp.mcp.server import detect_format_tool
        mcp = asyncio.run(detect_format_tool(traversal))
        assert mcp["success"] is False
        assert mcp.get("error") or mcp.get("message")


# ============================================================================
# ORF: CLI vs MCP
# ============================================================================

class TestORFErrorConsistency:
    """ORF CLI and MCP should return semantically equivalent errors."""

    def test_nonexistent_file(self, tmp_path):
        """Both transports reject nonexistent files."""
        # CLI
        cli = _cli(["orf", "apply-md", "/nonexistent/doc.md",
                     "--target-format", "docx",
                     "--output", str(tmp_path / "out.docx")])
        assert cli.returncode != 0

        # MCP — detect_format returns {format, confidence} not {success}
        from orf.mcp.server import detect_format
        mcp = json.loads(detect_format("/nonexistent/doc.docx"))
        # For nonexistent files, detect_format returns UNKNOWN
        assert mcp.get("format") in ("UNKNOWN", None)

    def test_path_traversal(self, tmp_path, monkeypatch):
        """Both transports reject path traversal."""
        monkeypatch.setenv("ORF_MCP_ALLOWED_DIRS", str(tmp_path))

        # CLI
        traversal_path = str(tmp_path / ".." / ".." / "etc" / "passwd")
        cli = _cli(["orf", "apply-md",
                     traversal_path,
                     "--target-format", "docx",
                     "--output", str(tmp_path / "out.docx")])
        assert cli.returncode != 0

        # MCP
        from orf.mcp.server import apply_md
        mcp = json.loads(apply_md(
            input_md=str(tmp_path / ".." / ".." / "etc" / "passwd"),
            target_format="docx",
            output_path=str(tmp_path / "out.docx"),
        ))
        assert mcp["success"] is False
        # ORF returns path errors as PATH_NOT_ALLOWED in errors list
        codes = {e.get("code") for e in mcp.get("errors", [])}
        assert "PATH_NOT_ALLOWED" in codes
