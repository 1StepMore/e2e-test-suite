"""Path C: OPP → OL MCP translate_md_text → MD2DOCXConverter."""

import asyncio
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest


pytestmark = [pytest.mark.e2e, pytest.mark.real_chain]


@pytest.fixture
def use_fake_llm(monkeypatch):
    """Sets OMNI_TEST_FAKE_LLM=1 and OMNI_TEST_FAKE_PANDOC=1 for the chain."""
    monkeypatch.setenv("OMNI_TEST_FAKE_LLM", "1")
    monkeypatch.setenv("OMNI_TEST_FAKE_PANDOC", "1")
    return True


class TestPathMdMCP:
    def test_full_chain_produces_translated_docx(
        self, opp_pipeline, haier_real_docx_path, tmp_path: Path, use_fake_llm
    ):
        """End-to-end: real OPP + comprehensive mock for OL MCP + real MD2DOCXConverter."""
        output_dir = tmp_path / "md_mcp"
        output_dir.mkdir()

        result = opp_pipeline.process_file(haier_real_docx_path)
        assert result.extraction_result is not None

        md_path = output_dir / f"{haier_real_docx_path.stem}.md"
        opp_pipeline.generate_markdown(result.extraction_result, md_path)
        assert md_path.exists()
        original_md_content = md_path.read_text(encoding="utf-8")

        translated_md = output_dir / f"{haier_real_docx_path.stem}_translated.md"
        with patch("ol_mcp.tools.ModelPool") as mock_pool_cls:
            from tests.test_e2e_pipeline_fixtures import _FakeModelPool
            mock_instance = _FakeModelPool()
            mock_pool_cls.get_instance.return_value = mock_instance
            mock_pool_cls.return_value = mock_instance

            from ol_mcp.tools import translate_md_text, TranslateInput
            params = TranslateInput(
                content=original_md_content,
                source_lang="en",
                target_lang="zh",
            )
            result_str = asyncio.run(translate_md_text(params))
            result_data = json.loads(result_str)
            assert result_data["success"] is True, f"OL MCP failed: {result_data}"
            translated_md_content = result_data["translated"]
            translated_md.write_text(translated_md_content, encoding="utf-8")

        assert original_md_content != translated_md_content, "MD content unchanged after MCP translate"
        assert any(m in translated_md_content for m in ["[ZH]", "你好", "世界", "用户手册", "测试", "功能"]), \
            f"No translation markers in OL MCP output: {translated_md_content[:500]}"

        from tests.test_e2e_pipeline_fixtures import _FakePandocRunner
        with patch("subprocess.run", side_effect=_FakePandocRunner()):
            from orf.channels.md2docx import MD2DOCXConverter
            converter = MD2DOCXConverter()
            docx_output = output_dir / "result.docx"
            conv_result = converter.convert(translated_md, docx_output)
        assert conv_result.success, f"ORF convert failed: {conv_result.errors}"
        assert docx_output.exists()

        with zipfile.ZipFile(docx_output) as zf:
            assert "word/document.xml" in zf.namelist()
            doc_xml = zf.read("word/document.xml").decode("utf-8")
        assert any(m in doc_xml for m in ["用户手册", "欢迎使用"]), \
            f"No translation markers in final DOCX: {doc_xml[:500]}"
