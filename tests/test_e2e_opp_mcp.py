"""E2E tests for OPP MCP server tools.

Tests the OPP MCP server tools:
- extract_document tool
- batch_extract tool
- detect_format tool

Each test directly calls the MCP tool functions.
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestOPPMCP:
    """OPP MCP server tool tests."""

    @pytest.mark.requires_opp
    def test_extract_document_md_format(self, tmp_path):
        """Test extract_document tool with md output format."""
        from docx import Document

        # Create sample DOCX
        doc = Document()
        doc.add_heading("Test Document", level=1)
        doc.add_paragraph("Test paragraph content.")

        docx_path = tmp_path / "test.docx"
        doc.save(str(docx_path))

        # Mock MCP server components
        with patch("opp.mcp.server._init_server") as mock_init, \
             patch("opp.mcp.server._validator") as mock_validator, \
             patch("opp.mcp.server._config", MagicMock(output_dir=None, allowed_directories=[])), \
             patch("opp.mcp.server._pipeline") as mock_pipeline, \
             patch("opp.mcp.server._serializer") as mock_serializer:

            mock_validator.validate_path.return_value = MagicMock(success=True)
            mock_pipeline.process_file.return_value = MagicMock(
                extraction_result=MagicMock(
                    paragraphs=[MagicMock(text="Test paragraph content.")],
                    tables=[],
                    images=[],
                    skeleton_files=["word/document.xml"],
                    skeleton=b"PK...",
                    warnings=[],
                ),
                errors=[],
            )
            mock_serializer.serialize.return_value = {
                "success": True,
                "extraction_result": {"paragraphs": 1},
            }

            # Import and call the tool
            from opp.mcp.server import extract_document

            result = asyncio.run(extract_document(
                file_path=str(docx_path),
                output_formats=["md"],
                source_lang="en",
                target_lang="zh",
            ))

            assert result["success"] is True

    @pytest.mark.requires_opp
    def test_extract_document_xlf_format(self, tmp_path):
        """Test extract_document tool with xlf output format."""
        from docx import Document

        doc = Document()
        doc.add_heading("XLIFF Test", level=1)
        doc.add_paragraph("Content for translation.")

        docx_path = tmp_path / "xliff_test.docx"
        doc.save(str(docx_path))

        with patch("opp.mcp.server._validator") as mock_validator, \
             patch("opp.mcp.server._config", MagicMock(output_dir=None, allowed_directories=[str(tmp_path)])), \
             patch("opp.mcp.server._pipeline") as mock_pipeline, \
             patch("opp.mcp.server._serializer") as mock_serializer:

            mock_validator.validate_path.return_value = MagicMock(success=True)
            mock_pipeline.process_file.return_value = MagicMock(
                extraction_result=MagicMock(
                    paragraphs=[MagicMock(text="Content.")],
                    tables=[],
                    images=[],
                    skeleton_files=["word/document.xml"],
                    skeleton=b"PK...",
                    warnings=[],
                ),
                errors=[],
            )
            mock_serializer.serialize.return_value = {"success": True}

            from opp.mcp.server import extract_document

            result = asyncio.run(extract_document(
                file_path=str(docx_path),
                output_formats=["xlf"],
                source_lang="en",
                target_lang="zh",
            ))

            assert result["success"] is True

    @pytest.mark.requires_opp
    def test_batch_extract_validation_error(self, tmp_path):
        """Test batch_extract tool fails fast on invalid paths."""
        from opp.mcp.server import batch_extract

        result = asyncio.run(batch_extract(
            file_paths=["/nonexistent/path/file.docx"],
            output_formats=["md"],
        ))

        assert result["success"] is False
        assert "validation_errors" in result or "error" in result

    @pytest.mark.requires_opp
    def test_detect_format_tool(self, tmp_path):
        """Test detect_format_tool correctly identifies file format."""
        from docx import Document

        doc = Document()
        doc.add_heading("Format Detection", level=1)
        doc.add_paragraph("Content.")

        docx_path = tmp_path / "detect.docx"
        doc.save(str(docx_path))

        with patch("opp.mcp.server._validator") as mock_validator, \
             patch("opp.mcp.server._config", MagicMock(output_dir=None, allowed_directories=[])):
            mock_validator.validate_path.return_value = MagicMock(success=True)

            from opp.mcp.server import detect_format_tool

            result = asyncio.run(detect_format_tool(file_path=str(docx_path)))

            assert result["success"] is True
            assert result["format"] in ["DOCX", "docx"]
            assert "confidence" in result

    @pytest.mark.requires_opp
    def test_detect_format_tool_invalid_path(self):
        """Test detect_format_tool handles invalid paths."""
        from opp.mcp.server import detect_format_tool

        result = asyncio.run(detect_format_tool(file_path="/invalid/path/file.docx"))

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.requires_opp
    def test_extract_document_both_formats(self, tmp_path):
        """Test extract_document tool with output_formats=['both']."""
        from docx import Document

        doc = Document()
        doc.add_heading("Both Formats Test", level=1)
        doc.add_paragraph("Testing MD and XLIFF output.")

        docx_path = tmp_path / "both.docx"
        doc.save(str(docx_path))

        with patch("opp.mcp.server._validator") as mock_validator, \
             patch("opp.mcp.server._config", MagicMock(output_dir=None, allowed_directories=[])), \
             patch("opp.mcp.server._pipeline") as mock_pipeline, \
             patch("opp.mcp.server._serializer") as mock_serializer:

            mock_validator.validate_path.return_value = MagicMock(success=True)
            mock_pipeline.process_file.return_value = MagicMock(
                extraction_result=MagicMock(
                    paragraphs=[MagicMock(text="Testing.")],
                    tables=[],
                    images=[],
                    skeleton_files=["word/document.xml"],
                    skeleton=b"PK...",
                    warnings=[],
                ),
                errors=[],
            )
            mock_serializer.serialize.return_value = {"success": True}

            from opp.mcp.server import extract_document

            result = asyncio.run(extract_document(
                file_path=str(docx_path),
                output_formats=["both"],
                source_lang="en",
                target_lang="zh",
            ))

            assert result["success"] is True

    @pytest.mark.requires_opp
    def test_batch_extract_mixed_results(self, tmp_path):
        """Test batch_extract handles mixed success/failure results."""
        from docx import Document

        doc = Document()
        doc.add_heading("Mixed", level=1)
        doc.add_paragraph("Content.")

        valid_path = tmp_path / "valid.docx"
        doc.save(str(valid_path))

        invalid_path = "/invalid/path.docx"

        with patch("opp.mcp.server._validator") as mock_validator, \
             patch("opp.mcp.server._config", MagicMock(output_dir=None, allowed_directories=[])), \
             patch("opp.mcp.server._pipeline") as mock_pipeline, \
             patch("opp.mcp.server._serializer") as mock_serializer:

            def validate_side_effect(path):
                if "invalid" in path:
                    return MagicMock(success=False, error="Path not allowed")
                return MagicMock(success=True)

            mock_validator.validate_path.side_effect = validate_side_effect
            mock_pipeline.process_file.return_value = MagicMock(
                extraction_result=MagicMock(
                    paragraphs=[],
                    tables=[],
                    images=[],
                    skeleton_files=[],
                    skeleton=None,
                    warnings=[],
                ),
                errors=[],
            )
            mock_serializer.serialize.return_value = {"success": True}

            from opp.mcp.server import batch_extract

            result = asyncio.run(batch_extract(
                file_paths=[str(valid_path), invalid_path],
                output_formats=["md"],
            ))

            assert result["failed"] == 1
            assert "error" in result

    @pytest.mark.requires_opp
    def test_extract_document_with_resource_dir(self, tmp_path):
        """Test extract_document respects resource_dir parameter."""
        from docx import Document

        doc = Document()
        doc.add_heading("Resource Test", level=1)
        doc.add_paragraph("Content.")

        docx_path = tmp_path / "resource.docx"
        doc.save(str(docx_path))

        resource_dir = tmp_path / "resources"
        resource_dir.mkdir()

        with patch("opp.mcp.server._init_server") as mock_init, \
             patch("opp.mcp.server._validator") as mock_validator, \
             patch("opp.mcp.server._config", MagicMock(output_dir=None, allowed_directories=[str(tmp_path)])), \
             patch("opp.mcp.server._pipeline") as mock_pipeline, \
             patch("opp.mcp.server._serializer") as mock_serializer:

            mock_validator.validate_path.return_value = MagicMock(success=True)
            mock_pipeline.process_file.return_value = MagicMock(
                extraction_result=MagicMock(
                    paragraphs=[MagicMock(text="Content.")],
                    tables=[],
                    images=[],
                    skeleton_files=["word/document.xml"],
                    skeleton=b"PK...",
                    warnings=[],
                ),
                errors=[],
            )
            mock_serializer.serialize.return_value = {"success": True}

            from opp.mcp.server import extract_document

            result = asyncio.run(extract_document(
                file_path=str(docx_path),
                output_formats=["md"],
                resource_dir=str(resource_dir),
            ))

            assert result["success"] is True