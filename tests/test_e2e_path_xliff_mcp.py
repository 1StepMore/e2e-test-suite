"""Path A: OPP → OL MCP translate_xliff → XLIFF2DOCXConverter."""

import asyncio
import json
import xml.etree.ElementTree as ET
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


class TestPathXliffMCP:
    def test_full_chain_produces_translated_docx(
        self, opp_pipeline, haier_real_docx_path, tmp_path: Path, use_fake_llm
    ):
        """End-to-end: real OPP + comprehensive mock for OL MCP + real XLIFF2DOCXConverter."""
        output_dir = tmp_path / "xliff_mcp"
        output_dir.mkdir()

        result = opp_pipeline.process_file(haier_real_docx_path)
        assert result.extraction_result is not None

        xliff_path = output_dir / f"{haier_real_docx_path.stem}.xlf"
        opp_pipeline.generate_xliff(result.extraction_result, xliff_path, "en", "zh")
        assert xliff_path.exists()

        skeleton_path = opp_pipeline.save_skeleton(
            result.extraction_result, haier_real_docx_path.stem, output_dir
        )
        assert skeleton_path is not None and skeleton_path.exists()

        translated_xliff = output_dir / f"{haier_real_docx_path.stem}_translated.xlf"
        with patch("ol_mcp.translate_xliff.ModelPool") as mock_pool_cls:
            from tests.test_e2e_pipeline_fixtures import _FakeModelPool
            mock_instance = _FakeModelPool()
            mock_pool_cls.get_instance.return_value = mock_instance
            mock_pool_cls.return_value = mock_instance

            from ol_mcp.tools import translate_xliff, TranslateXliffInput
            params = TranslateXliffInput(
                input_path=str(xliff_path),
                output_path=str(translated_xliff),
                source_lang="en",
                target_lang="zh",
            )
            result_str = asyncio.run(translate_xliff(params))
            result_data = json.loads(result_str)
            assert result_data["success"] is True, f"OL MCP failed: {result_data}"

        xlf_content = translated_xliff.read_text(encoding="utf-8")
        assert "<target>" in xlf_content
        tree = ET.fromstring(xlf_content)
        ns = "urn:oasis:names:tc:xliff:document:1.2"
        translated_count = sum(
            1 for unit in tree.iter(f"{{{ns}}}trans-unit")
            if (s := unit.find(f"{{{ns}}}source")) is not None
            and (t := unit.find(f"{{{ns}}}target")) is not None
            and s.text and t.text and s.text != t.text
        )
        assert translated_count > 0, "Comprehensive mock failed to produce different text"

        from orf.channels.xliff2docx import XLIFF2DOCXConverter
        converter = XLIFF2DOCXConverter()
        docx_output = output_dir / "result.docx"
        conv_result = converter.convert(
            input_path=skeleton_path,
            xliff_path=translated_xliff,
            output_path=docx_output,
        )
        assert conv_result.success, f"ORF convert failed: {conv_result.errors}"
        assert docx_output.exists()

        with zipfile.ZipFile(docx_output) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
        assert any(m in doc_xml for m in ["[ZH]", "你好", "世界", "用户手册", "测试", "功能"]), \
            f"No translation markers in final DOCX: {doc_xml[:500]}"
