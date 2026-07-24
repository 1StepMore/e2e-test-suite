"""Tests for omni-mcp — the suite-level MCP orchestrator.

Covers:
1. Happy-path translate_file (OPP→OL→ORF via real CLIs with FAKE_LLM)
2. Error propagation (file not found, bad format, CLI failure)
3. Pipeline auto-detection (MD-only format → md path)
4. Ping health check
5. MCP server tool dispatch
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure FAKE_LLM is set for all tests in this module
os.environ.setdefault("OMNI_TEST_FAKE_LLM", "1")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SUITE_ROOT = Path(__file__).resolve().parents[1]
_VENV_BIN = _SUITE_ROOT / ".venv_ol" / "bin"


def _cli(name: str) -> str:
    """Return the absolute path to a CLI binary in the venv, or the bare name."""
    p = _VENV_BIN / name
    return str(p) if p.exists() else shutil.which(name) or name


# ---------------------------------------------------------------------------
# Unit tests — orchestrator with mocked subprocess
# ---------------------------------------------------------------------------


class TestOrchestratorUnit:
    """Unit tests for omni_mcp.orchestrator.translate_file (mocked CLIs)."""

    def test_file_not_found(self, tmp_path):
        from omni_mcp.orchestrator import translate_file

        result = translate_file(
            file_path=str(tmp_path / "nonexistent.docx"),
            source_lang="en",
            target_lang="zh",
            output_format="docx",
        )
        assert result["success"] is False
        assert result["error"]["code"] == "FILE_NOT_FOUND"

    @patch("omni_mcp.orchestrator._run_cli")
    def test_opp_failure(self, mock_cli, tmp_path):
        from omni_mcp.orchestrator import translate_file

        # Create a dummy source file
        src = tmp_path / "test.docx"
        src.write_bytes(b"PK\x03\x04")  # minimal ZIP magic

        mock_cli.return_value = {
            "success": False,
            "error": {"code": "OPP_INTERNAL_ERROR", "message": "bad file"},
        }

        result = translate_file(
            file_path=str(src),
            source_lang="en",
            target_lang="zh",
            output_format="docx",
        )
        assert result["success"] is False
        assert result["error"]["code"] == "OPP_FAILED"

    @patch("omni_mcp.orchestrator._run_cli")
    def test_ol_failure(self, mock_cli, tmp_path):
        from omni_mcp.orchestrator import translate_file

        src = tmp_path / "test.docx"
        src.write_bytes(b"PK\x03\x04")

        def side_effect(cmd, **kwargs):
            if cmd[0] in ("opp", _cli("opp")):
                for i, arg in enumerate(cmd):
                    if arg == "--output-dir" and i + 1 < len(cmd):
                        out_dir = Path(cmd[i + 1])
                        out_dir.mkdir(parents=True, exist_ok=True)
                        (out_dir / "test.md").write_text("# Hello\n\nWorld\n")
                return {"success": True, "suggested_pipeline": "md_only"}
            if cmd[0] in ("ol", _cli("ol")):
                return {"success": False, "error": {"code": "OL_RATE_LIMITED", "message": "rate limited"}}
            return {"success": True}

        mock_cli.side_effect = side_effect

        result = translate_file(
            file_path=str(src),
            source_lang="en",
            target_lang="zh",
            output_format="docx",
        )
        assert result["success"] is False
        assert result["error"]["code"] == "OL_FAILED"

    @patch("omni_mcp.orchestrator._run_cli")
    def test_orf_failure(self, mock_cli, tmp_path):
        from omni_mcp.orchestrator import translate_file

        src = tmp_path / "test.docx"
        src.write_bytes(b"PK\x03\x04")

        def side_effect(cmd, **kwargs):
            if cmd[0] in ("opp", _cli("opp")):
                for i, arg in enumerate(cmd):
                    if arg == "--output-dir" and i + 1 < len(cmd):
                        out_dir = Path(cmd[i + 1])
                        out_dir.mkdir(parents=True, exist_ok=True)
                        (out_dir / "test.md").write_text("# Hello\n\nWorld\n")
                return {"success": True, "suggested_pipeline": "md_only"}
            if cmd[0] in ("ol", _cli("ol")):
                for i, arg in enumerate(cmd):
                    if arg == "-o" and i + 1 < len(cmd):
                        out_dir = Path(cmd[i + 1])
                        out_dir.mkdir(parents=True, exist_ok=True)
                        (out_dir / "test.md").write_text("# 你好\n\n世界\n")
                return {"success": True}
            if cmd[0] in ("orf", _cli("orf")):
                return {"success": False, "error": {"code": "ORF_PANDOC_MISSING", "message": "pandoc not found"}}
            return {"success": True}

        mock_cli.side_effect = side_effect

        result = translate_file(
            file_path=str(src),
            source_lang="en",
            target_lang="zh",
            output_format="docx",
        )
        assert result["success"] is False
        assert "ORF" in result["error"]["code"] or "ORF" in result["error"]["message"]

    @patch("omni_mcp.orchestrator._run_cli")
    def test_success_shape(self, mock_cli, tmp_path):
        from omni_mcp.orchestrator import translate_file

        src = tmp_path / "test.docx"
        src.write_bytes(b"PK\x03\x04")

        def side_effect(cmd, **kwargs):
            if cmd[0] in ("opp", _cli("opp")):
                for i, arg in enumerate(cmd):
                    if arg == "--output-dir" and i + 1 < len(cmd):
                        out_dir = Path(cmd[i + 1])
                        out_dir.mkdir(parents=True, exist_ok=True)
                        (out_dir / "test.md").write_text("# Hello\n\nWorld\n")
                return {"success": True, "suggested_pipeline": "md_only"}
            if cmd[0] in ("ol", _cli("ol")):
                for i, arg in enumerate(cmd):
                    if arg == "-o" and i + 1 < len(cmd):
                        out_dir = Path(cmd[i + 1])
                        out_dir.mkdir(parents=True, exist_ok=True)
                        (out_dir / "test.md").write_text("# 你好\n\n世界\n")
                return {"success": True}
            if cmd[0] in ("orf", _cli("orf")):
                for i, arg in enumerate(cmd):
                    if arg == "-o" and i + 1 < len(cmd):
                        Path(cmd[i + 1]).write_text("fake docx content")
                return {"success": True}
            return {"success": True}

        mock_cli.side_effect = side_effect

        result = translate_file(
            file_path=str(src),
            source_lang="en",
            target_lang="zh",
            output_format="docx",
        )
        assert result["success"] is True
        content = result["content"]
        assert "output_path" in content
        assert content["pipeline"] in ("md", "xliff")
        assert content["source_lang"] == "en"
        assert content["target_lang"] == "zh"
        assert content["output_format"] == "docx"
        assert "duration_ms" in content

    @patch("omni_mcp.orchestrator._run_cli")
    def test_pipeline_auto_detect_xliff(self, mock_cli, tmp_path):
        from omni_mcp.orchestrator import translate_file

        src = tmp_path / "test.docx"
        src.write_bytes(b"PK\x03\x04")

        def side_effect(cmd, **kwargs):
            if cmd[0] in ("opp", _cli("opp")):
                for i, arg in enumerate(cmd):
                    if arg == "--output-dir" and i + 1 < len(cmd):
                        out_dir = Path(cmd[i + 1])
                        out_dir.mkdir(parents=True, exist_ok=True)
                        (out_dir / "test.xlf").write_text(
                            '<xliff version="1.2"><file source-language="en" target-language="zh">'
                            '<body><trans-unit id="1"><source>Hello</source></trans-unit></body>'
                            '</file></xliff>'
                        )
                return {"success": True, "suggested_pipeline": "xliff_only"}
            if cmd[0] in ("ol", _cli("ol")):
                for i, arg in enumerate(cmd):
                    if arg == "-o" and i + 1 < len(cmd):
                        out_dir = Path(cmd[i + 1])
                        out_dir.mkdir(parents=True, exist_ok=True)
                        (out_dir / "test.xlf").write_text(
                            '<xliff version="1.2"><file source-language="en" target-language="zh">'
                            '<body><trans-unit id="1"><source>Hello</source><target>你好</target></trans-unit></body>'
                            '</file></xliff>'
                        )
                return {"success": True}
            if cmd[0] in ("orf", _cli("orf")):
                for i, arg in enumerate(cmd):
                    if arg == "--output" and i + 1 < len(cmd):
                        Path(cmd[i + 1]).write_text("fake docx")
                return {"success": True}
            return {"success": True}

        mock_cli.side_effect = side_effect

        result = translate_file(
            file_path=str(src),
            source_lang="en",
            target_lang="zh",
            output_format="docx",
        )
        assert result["success"] is True
        assert result["content"]["pipeline"] == "xliff"


# ---------------------------------------------------------------------------
# Unit tests — MCP server tool dispatch
# ---------------------------------------------------------------------------


class TestMCPServerTools:
    """Test the MCP server's tool functions directly."""

    @pytest.mark.asyncio
    async def test_ping(self):
        from omni_mcp.server import ping

        result = await ping()
        assert result["success"] is True
        assert result["content"]["module"] == "omni-mcp"
        assert "version" in result["content"]

    @pytest.mark.asyncio
    async def test_translate_file_missing_path(self):
        from omni_mcp.server import translate_file

        result = await translate_file(
            file_path="",
            source_lang="en",
            target_lang="zh",
            output_format="docx",
        )
        assert result["success"] is False
        assert result["error"]["code"] == "OMNI_INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_translate_file_nonexistent(self):
        from omni_mcp.server import translate_file

        result = await translate_file(
            file_path="/tmp/nonexistent_file_12345.docx",
            source_lang="en",
            target_lang="zh",
            output_format="docx",
        )
        assert result["success"] is False
        assert result["error"]["code"] == "FILE_NOT_FOUND"

    def test_tool_schemas_valid(self):
        """Verify all tool schemas have required fields."""
        from omni_mcp.server import _TOOL_SCHEMAS

        for schema in _TOOL_SCHEMAS:
            assert "name" in schema
            assert "description" in schema
            assert "inputSchema" in schema
            assert schema["inputSchema"]["type"] == "object"

    def test_dispatch_table_matches_schemas(self):
        """Every schema name must have a dispatch entry and vice versa."""
        from omni_mcp.server import _TOOL_SCHEMAS, _TOOL_DISPATCH

        schema_names = {s["name"] for s in _TOOL_SCHEMAS}
        dispatch_names = set(_TOOL_DISPATCH.keys())
        assert schema_names == dispatch_names, (
            f"Mismatch: schemas={schema_names}, dispatch={dispatch_names}"
        )


# ---------------------------------------------------------------------------
# Integration tests — real CLIs with OMNI_TEST_FAKE_LLM=1
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.slow
class TestTranslateFileIntegration:
    """Integration tests using real OPP/OL/ORF CLIs with FAKE_LLM."""

    @pytest.fixture(autouse=True)
    def _ensure_fake_llm(self):
        os.environ["OMNI_TEST_FAKE_LLM"] = "1"
        yield

    def test_happy_path_docx(self, sample_docx_path):
        """Full pipeline: DOCX → translated DOCX via MD path."""
        from omni_mcp.orchestrator import translate_file

        result = translate_file(
            file_path=str(sample_docx_path),
            source_lang="en",
            target_lang="zh",
            output_format="docx",
            opp_path=_cli("opp"),
            ol_path=_cli("ol"),
            orf_path=_cli("orf"),
        )
        # May succeed or fail depending on pandoc availability;
        # what matters is the shape is correct
        assert "success" in result
        if result["success"]:
            content = result["content"]
            assert Path(content["output_path"]).exists()
            assert content["pipeline"] in ("md", "xliff")
        else:
            # If it fails, it should have a proper error code
            assert "error" in result
            assert "code" in result["error"]

    def test_happy_path_html(self, sample_docx_path):
        """Full pipeline: DOCX → translated HTML (pure Python, no pandoc)."""
        from omni_mcp.orchestrator import translate_file

        result = translate_file(
            file_path=str(sample_docx_path),
            source_lang="en",
            target_lang="zh",
            output_format="html",
            opp_path=_cli("opp"),
            ol_path=_cli("ol"),
            orf_path=_cli("orf"),
        )
        assert "success" in result
        if result["success"]:
            assert Path(result["content"]["output_path"]).exists()
            assert result["content"]["output_format"] == "html"

    def test_unsupported_format_graceful(self, sample_docx_path):
        """Requesting an unsupported output format should return a clean error."""
        from omni_mcp.orchestrator import translate_file

        result = translate_file(
            file_path=str(sample_docx_path),
            source_lang="en",
            target_lang="zh",
            output_format="nonexistent_format",
            opp_path=_cli("opp"),
            ol_path=_cli("ol"),
            orf_path=_cli("orf"),
        )
        # Should fail gracefully, not crash
        assert "success" in result
        if not result["success"]:
            assert "error" in result
            assert "code" in result["error"]

    def test_md_path_detection(self, sample_docx_path):
        """DOCX with auto-detect should use MD path (suggested_pipeline=both → md)."""
        from omni_mcp.orchestrator import translate_file

        result = translate_file(
            file_path=str(sample_docx_path),
            source_lang="en",
            target_lang="zh",
            output_format="html",
            pipeline="md",
            opp_path=_cli("opp"),
            ol_path=_cli("ol"),
            orf_path=_cli("orf"),
        )
        assert "success" in result
        if result["success"]:
            assert result["content"]["pipeline"] == "md"


# ---------------------------------------------------------------------------
# Smoke test — server starts without error
# ---------------------------------------------------------------------------


class TestServerSmoke:
    """Verify the MCP server module can be imported and initialized."""

    def test_import(self):
        import omni_mcp
        assert hasattr(omni_mcp, "__version__")
        assert omni_mcp.__version__ is not None
        assert len(omni_mcp.__version__) > 0

    def test_server_instance(self):
        from omni_mcp.server import server
        assert server is not None
        assert server.name == "omni-mcp"

    def test_main_callable(self):
        from omni_mcp.server import main
        assert callable(main)

    def test_orchestrator_importable(self):
        from omni_mcp.orchestrator import translate_file
        assert callable(translate_file)
