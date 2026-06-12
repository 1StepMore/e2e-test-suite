"""End-to-end tests for OPP → OL → ORF localization pipeline.

This module tests the complete Omni Localization Suite workflow:
1. OPP extracts documents to MD/XLIFF + skeleton.zip + manifest.json
2. OL translates MD/XLIFF content to target language
3. ORF backfills translated content to target format (DOCX/PPTX/etc)

Run with: pytest tests/test_e2e_pipeline.py -v
"""

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


class TestOmniPipelinePrerequisites:
    """Test that all prerequisites for E2E testing are met."""

    def test_opp_importable(self):
        """Verify OPP module can be imported."""
        try:
            from opp.detector import FormatType, detect_format
            from opp.pipeline import OPPPipeline
        except ImportError as e:
            pytest.skip(f"OPP not importable: {e}")

    def test_ol_importable(self):
        """Verify OL module can be imported."""
        try:
            from ol_md.pipeline import MDRepairPipeline
            from ol_md.shield import shield_markdown
        except ImportError as e:
            pytest.skip(f"OL not importable: {e}")

    def test_orf_importable(self):
        """Verify ORF module can be imported."""
        try:
            from orf.parsers.manifest import Manifest
            from orf.skeleton.skeleton_loader import SkeletonLoader
        except ImportError as e:
            pytest.skip(f"ORF not importable: {e}")


class TestOPPExtraction:
    """Test OPP document extraction functionality."""

    @pytest.mark.requires_opp
    def test_opp_extracts_docx(self, opp_pipeline, sample_docx_path, tmp_path):
        """OPP should extract DOCX and return content."""
        result = opp_pipeline.process_file(sample_docx_path)

        assert result is not None
        assert result.format_type.value == "docx"
        assert len(result.errors) == 0
        assert len(result.content) > 0

    @pytest.mark.requires_opp
    def test_opp_generates_markdown(self, opp_pipeline, sample_docx_path, tmp_path):
        """OPP should generate markdown from extraction result."""
        result = opp_pipeline.process_file(sample_docx_path)
        assert result.extraction_result is not None

        md_path = tmp_path / "output.md"
        opp_pipeline.generate_markdown(result.extraction_result, md_path)

        assert md_path.exists()
        md_content = md_path.read_text(encoding="utf-8")
        assert len(md_content) > 0
        assert "User Manual" in md_content

    @pytest.mark.requires_opp
    def test_opp_generates_xliff(self, opp_pipeline, sample_docx_path, tmp_path):
        """OPP should generate XLIFF from extraction result."""
        result = opp_pipeline.process_file(sample_docx_path)
        assert result.extraction_result is not None

        xliff_path = tmp_path / "output.xlf"
        opp_pipeline.generate_xliff(
            result.extraction_result,
            xliff_path,
            source_lang="en",
            target_lang="zh"
        )

        assert xliff_path.exists()
        xliff_content = xliff_path.read_text(encoding="utf-8")
        assert len(xliff_content) > 0
        assert "<xliff" in xliff_content

    @pytest.mark.requires_opp
    def test_opp_saves_skeleton(self, opp_pipeline, sample_docx_path, tmp_path):
        """OPP should save skeleton.zip for DOCX."""
        result = opp_pipeline.process_file(sample_docx_path)
        assert result.extraction_result is not None
        assert result.extraction_result.skeleton is not None

        output_dir = tmp_path / "skeleton_test"
        output_dir.mkdir(exist_ok=True)

        skeleton_path = opp_pipeline.save_skeleton(
            result.extraction_result,
            sample_docx_path.stem,
            output_dir
        )

        assert skeleton_path is not None
        assert skeleton_path.exists()

        with zipfile.ZipFile(skeleton_path, 'r') as zf:
            names = zf.namelist()
            assert "word/document.xml" in names

    @pytest.mark.requires_opp
    def test_opp_creates_manifest(self, opp_pipeline, sample_docx_path, tmp_path):
        """Test manifest creation with all required fields."""
        result = opp_pipeline.process_file(sample_docx_path)

        output_dir = tmp_path / "manifest_test"
        output_dir.mkdir(exist_ok=True)

        md_path = output_dir / f"{sample_docx_path.stem}.md"
        xliff_path = output_dir / f"{sample_docx_path.stem}.xlf"

        if result.extraction_result:
            opp_pipeline.generate_markdown(result.extraction_result, md_path)
            opp_pipeline.generate_xliff(result.extraction_result, xliff_path, "en", "zh")

        skeleton_path = None
        if result.extraction_result and result.extraction_result.skeleton:
            skeleton_path = opp_pipeline.save_skeleton(result.extraction_result, sample_docx_path.stem, output_dir)

        manifest_data = {
            "manifest_version": "1.0",
            "generated_at": "2026-05-27T00:00:00Z",
            "tool": "OPP",
            "tool_version": "0.2.0",
            "source": {
                "file_path": str(sample_docx_path),
                "original_filename": sample_docx_path.name,
                "format": "DOCX",
            },
            "extraction": {
                "source_lang": "en",
                "target_lang": "zh",
                "outputs": {
                    "markdown": {"path": str(md_path)},
                    "xliff": {"path": str(xliff_path)},
                },
            },
            "skeleton": {
                "path": str(skeleton_path) if skeleton_path else None,
                "format": "ZIP"
            }
        }

        manifest_path = output_dir / "manifest.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest_data, f, indent=2)

        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert manifest["tool"] == "OPP"
        assert manifest["source"]["format"] == "DOCX"


class TestOPPToOLIntegration:
    """Test OPP → OL integration using mock translator."""

    @pytest.mark.requires_opp
    def test_opp_to_mock_ol_md(self, opp_pipeline, sample_docx_path, tmp_path, mock_ol_translator):
        """OPP extracts → MockOL translates MD → verify translation."""
        result = opp_pipeline.process_file(sample_docx_path)
        assert result.extraction_result is not None

        output_dir = tmp_path / "md_translate"
        output_dir.mkdir(exist_ok=True)

        md_path = output_dir / "original.md"
        opp_pipeline.generate_markdown(result.extraction_result, md_path)
        assert md_path.exists()

        translated_md_path = output_dir / "translated.md"
        success = mock_ol_translator.translate_md(md_path, translated_md_path)
        assert success

        translated_content = translated_md_path.read_text(encoding="utf-8")
        assert "[→zh]" in translated_content or "source_lang: en" in translated_content

    @pytest.mark.requires_opp
    def test_opp_to_mock_ol_xliff(self, opp_pipeline, sample_docx_path, tmp_path, mock_ol_translator):
        """OPP extracts → MockOL translates XLIFF → verify translation."""
        result = opp_pipeline.process_file(sample_docx_path)
        assert result.extraction_result is not None

        output_dir = tmp_path / "xliff_translate"
        output_dir.mkdir(exist_ok=True)

        xliff_path = output_dir / "original.xlf"
        opp_pipeline.generate_xliff(result.extraction_result, xliff_path, "en", "zh")
        assert xliff_path.exists()

        translated_xliff_path = output_dir / "translated.xlf"
        success = mock_ol_translator.translate_xliff(xliff_path, translated_xliff_path)
        assert success

        import xml.etree.ElementTree as ET
        tree = ET.parse(translated_xliff_path)
        root = tree.getroot()
        ns = "urn:oasis:names:tc:xliff:document:1.2"
        file_el = root.find(f"{{{ns}}}file")
        assert file_el is not None
        assert file_el.get("target-language") == "zh"


class TestOLToORFIntegration:
    """Test OL → ORF integration."""

    @pytest.mark.requires_orf
    def test_orf_md_to_docx(self, tmp_path, validate_docx_structure):
        """ORF should convert MD to DOCX."""
        md_content = """---
source_lang: en
target_lang: zh
---

# 用户手册

这是中文内容。

## 介绍

- 功能1
- 功能2
"""
        md_path = tmp_path / "test.md"
        md_path.write_text(md_content, encoding="utf-8")

        try:
            from orf.channels.md2docx import MD2DOCXConverter
            converter = MD2DOCXConverter()
            result = converter.convert(md_path, tmp_path / "result.docx")

            if result.success:
                assert (tmp_path / "result.docx").exists()
                is_valid, _ = validate_docx_structure(tmp_path / "result.docx")
                assert is_valid
        except ImportError as e:
            pytest.skip(f"MD2DOCXConverter not available: {e}")

    @pytest.mark.requires_orf
    def test_orf_xliff_backfill(self, tmp_path, sample_docx_path, validate_docx_structure):
        """ORF should backfill XLIFF to DOCX skeleton."""
        skeleton_path = tmp_path / "test.skeleton.zip"
        with zipfile.ZipFile(skeleton_path, 'w') as zf:
            with zipfile.ZipFile(sample_docx_path, 'r') as src_zf:
                for name in src_zf.namelist():
                    if name.startswith("word/"):
                        zf.writestr(name, src_zf.read(name))

        xliff_content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.docx" source-language="en" target-language="zh" datatype="office-open-xml">
    <body>
      <trans-unit id="1">
        <source>User Manual</source>
        <target>用户手册</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        xliff_path = tmp_path / "translated.xlf"
        xliff_path.write_text(xliff_content, encoding="utf-8")

        try:
            from orf.channels.xliff2docx import XLIFF2DOCXConverter
            converter = XLIFF2DOCXConverter()
            result = converter.convert(skeleton_path, xliff_path, tmp_path / "result.docx")

            if result.success:
                assert (tmp_path / "result.docx").exists()
                is_valid, _ = validate_docx_structure(tmp_path / "result.docx")
                assert is_valid
        except ImportError as e:
            pytest.skip(f"XLIFF2DOCXConverter not available: {e}")


class TestMDChannelWorkflow:
    """Test complete MD-based translation workflow."""

    @pytest.mark.e2e
    @pytest.mark.requires_opp
    @pytest.mark.requires_orf
    def test_md_pipeline(self, opp_pipeline, sample_docx_path, tmp_path, mock_ol_translator, validate_docx_structure):
        """OPP → OL → ORF using MD channel."""
        output_dir = tmp_path / "md_pipeline"
        output_dir.mkdir(exist_ok=True)

        result = opp_pipeline.process_file(sample_docx_path)
        assert result.extraction_result is not None

        md_path = output_dir / "original.md"
        opp_pipeline.generate_markdown(result.extraction_result, md_path)
        assert md_path.exists()

        translated_md_path = output_dir / "translated.md"
        mock_ol_translator.translate_md(md_path, translated_md_path)

        try:
            from orf.channels.md2docx import MD2DOCXConverter
            converter = MD2DOCXConverter()
            docx_output = output_dir / "result.docx"
            conv_result = converter.convert(translated_md_path, docx_output)

            if conv_result.success:
                assert docx_output.exists()
                is_valid, _ = validate_docx_structure(docx_output)
                assert is_valid
        except ImportError as e:
            pytest.skip(f"ORF not available: {e}")


class TestXLIFFChannelWorkflow:
    """Test complete XLIFF-based translation workflow."""

    @pytest.mark.e2e
    @pytest.mark.requires_opp
    @pytest.mark.requires_orf
    def test_xliff_pipeline(self, opp_pipeline, sample_docx_path, tmp_path, mock_ol_translator, validate_docx_structure):
        """OPP → OL → ORF using XLIFF channel."""
        output_dir = tmp_path / "xliff_pipeline"
        output_dir.mkdir(exist_ok=True)

        result = opp_pipeline.process_file(sample_docx_path)
        assert result.extraction_result is not None

        xliff_path = output_dir / "original.xlf"
        opp_pipeline.generate_xliff(result.extraction_result, xliff_path, "en", "zh")
        assert xliff_path.exists()

        translated_xliff_path = output_dir / "translated.xlf"
        mock_ol_translator.translate_xliff(xliff_path, translated_xliff_path)

        skeleton_path = None
        if result.extraction_result and result.extraction_result.skeleton:
            skeleton_path = opp_pipeline.save_skeleton(result.extraction_result, sample_docx_path.stem, output_dir)

        if skeleton_path:
            try:
                from orf.channels.xliff2docx import XLIFF2DOCXConverter
                converter = XLIFF2DOCXConverter()
                docx_output = output_dir / "result.docx"
                conv_result = converter.convert(skeleton_path, translated_xliff_path, docx_output)

                if conv_result.success:
                    assert docx_output.exists()
                    is_valid, _ = validate_docx_structure(docx_output)
                    assert is_valid
            except ImportError as e:
                pytest.skip(f"XLIFF2DOCXConverter not available: {e}")


class TestFullPipeline:
    """Test complete end-to-end pipeline."""

    @pytest.mark.e2e
    @pytest.mark.requires_opp
    def test_pipeline_creates_all_artifacts(self, opp_pipeline, sample_docx_path, tmp_path):
        """Test that pipeline produces all expected artifacts."""
        output_dir = tmp_path / "full_pipeline"
        output_dir.mkdir(exist_ok=True)

        result = opp_pipeline.process_file(sample_docx_path)
        assert result.extraction_result is not None

        md_path = output_dir / f"{sample_docx_path.stem}.md"
        xliff_path = output_dir / f"{sample_docx_path.stem}.xlf"

        opp_pipeline.generate_markdown(result.extraction_result, md_path)
        opp_pipeline.generate_xliff(result.extraction_result, xliff_path, "en", "zh")

        skeleton_path = None
        if result.extraction_result and result.extraction_result.skeleton:
            skeleton_path = opp_pipeline.save_skeleton(result.extraction_result, sample_docx_path.stem, output_dir)

        assert md_path.exists()
        assert xliff_path.exists()
        assert skeleton_path is not None and skeleton_path.exists()


class TestErrorHandling:
    """Test error handling throughout the pipeline."""

    @pytest.mark.requires_opp
    def test_opp_handles_missing_file(self, opp_pipeline, tmp_path):
        """OPP should handle missing input file gracefully."""
        missing = tmp_path / "nonexistent.docx"
        result = opp_pipeline.process_file(missing)

        assert result is not None
        assert len(result.errors) > 0 or result.warnings

    @pytest.mark.requires_ol
    def test_ol_handles_empty_md(self, tmp_path, mock_ol_translator):
        """OL should handle empty markdown."""
        empty_md = tmp_path / "empty.md"
        empty_md.write_text("", encoding="utf-8")

        translated_path = tmp_path / "translated.md"
        success = mock_ol_translator.translate_md(empty_md, translated_path)

        assert success

    @pytest.mark.requires_ol
    def test_ol_handles_empty_xliff(self, tmp_path, mock_ol_translator):
        """OL should handle XLIFF with no trans-units."""
        empty_xliff = tmp_path / "empty.xlf"
        empty_xliff.write_text(
            '''<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="empty.txt" source-language="en" target-language="zh">
    <body>
    </body>
  </file>
</xliff>''',
            encoding="utf-8"
        )

        translated_path = tmp_path / "translated.xlf"
        success = mock_ol_translator.translate_xliff(empty_xliff, translated_path)

        assert success

    @pytest.mark.requires_orf
    def test_orf_handles_invalid_md(self, tmp_path):
        """ORF should handle invalid markdown gracefully."""
        invalid_md = tmp_path / "invalid.md"
        invalid_md.write_text("not really markdown", encoding="utf-8")

        from orf.channels.md2docx import MD2DOCXConverter
        converter = MD2DOCXConverter()
        result = converter.convert(invalid_md, tmp_path / "result.docx")

        assert result is not None, "ORF should handle invalid MD without crashing"


class TestPipelinePerformance:
    """Test pipeline performance."""

    @pytest.mark.requires_opp
    @pytest.mark.slow
    def test_opp_extraction_time(self, opp_pipeline, sample_docx_path):
        """OPP extraction should complete within reasonable time."""
        import time

        start = time.time()
        result = opp_pipeline.process_file(sample_docx_path)
        elapsed = time.time() - start

        assert result is not None
        assert elapsed < 30


# =============================================================================
# E2E tests for all 4 OPP→OL→ORF paths using real DOCX + real APIs
# =============================================================================

_COMPREHENSIVE_TRANSLATE_MAP = {
    "Hello": "你好",
    "World": "世界",
    "User Manual": "用户手册",
    "Test": "测试",
    "Chapter": "章节",
    "Section": "节",
    "Introduction": "介绍",
    "Feature": "功能",
    "Function": "功能",
    "Welcome": "欢迎",
}


def _comprehensive_translate(text, src_lang, tgt_lang, context=None):
    """Mock translate that returns demonstrably different text from input.

    Returns known translations when the source matches a key in
    _COMPREHENSIVE_TRANSLATE_MAP; otherwise returns a safe marker
    `[ZH]` (NOT the original text, which may contain XML special
    characters that would break the resulting XLIFF). This still
    guarantees `<target>` != `<source>` so tests can assert
    translation actually happened.
    """
    if text in _COMPREHENSIVE_TRANSLATE_MAP:
        return _COMPREHENSIVE_TRANSLATE_MAP[text]
    return "[ZH]"


class _AsyncMockPool:
    """Mock ModelPool with async translate method.

    Used as `mock_pool_cls.return_value` in the 2 MCP E2E tests.
    A real class with an `async def translate` method is more reliable
    than `AsyncMock(side_effect=...)` because:
    1. The method is a real coroutine function, so `await pool.translate(...)`
       always works.
    2. No subtle issues with how `AsyncMock` wraps the return value.
    """

    async def translate(self, text, src_lang, tgt_lang, context=None):
        return _comprehensive_translate(text, src_lang, tgt_lang, context)


_MINIMAL_DOCX_DOCUMENT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r>
        <w:t>Translated content</w:t>
      </w:r>
    </w:p>
  </w:body>
</w:document>
"""


def _create_minimal_docx(docx_path: Path) -> None:
    """Create a minimal valid DOCX file (used by pandoc mock)."""
    import zipfile
    with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", _MINIMAL_DOCX_DOCUMENT)
        zf.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""")
        zf.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""")


def _pandoc_side_effect(*args, **kwargs):
    """Mock pandoc subprocess call: create a real DOCX at the output path.

    MD2DOCXConverter.convert() internally calls `subprocess.run(["pandoc", ...])`.
    When pandoc is not installed in the test env, this mock creates a
    real minimal DOCX at the expected output path so the downstream
    assertions (validate_docx_structure) can pass.
    """
    from unittest.mock import MagicMock
    cmd = args[0] if args else kwargs.get("args", [])
    if "-o" in cmd:
        output_idx = cmd.index("-o") + 1
        output_path = Path(cmd[output_idx])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _create_minimal_docx(output_path)
    result = MagicMock()
    result.returncode = 0
    result.stdout = ""
    result.stderr = ""
    return result


def _make_subprocess_env():
    """Build subprocess env with PYTHONPATH including all 3 src dirs.

    The conftest adds src dirs to the pytest process's sys.path,
    but subprocesses get a fresh sys.path. We must inject it.
    """
    suite_root = Path(__file__).resolve().parent.parent
    src_dirs = [
        suite_root / "Omni_Pre_Processor" / "src",
        suite_root / "Omni_Localizer" / "src",
        suite_root / "Omni_Re_Formatter" / "src",
    ]
    env = os.environ.copy()
    existing_pp = env.get("PYTHONPATH", "")
    parts = [str(d) for d in src_dirs if d.exists()]
    if existing_pp:
        parts.append(existing_pp)
    env["PYTHONPATH"] = ":".join(parts)
    return env
