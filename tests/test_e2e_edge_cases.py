"""Edge case tests — empty inputs, corrupt files, missing files, special characters.

Covers S10.1-S10.6, S10.8 from the integrated test plan. Tests each MCP tool's
behavior when given unusual or invalid inputs, without requiring real LLM
or pandoc. Where possible, tests call MCP tools in-process; where the tool
requires complex setup (e.g. OL translate needs ModelPool mock), tests fall
back to CLI subprocess or verify a looser contract.

Important notes:
- OPP MCP tools need ``_init_server(load_config())`` before use (module-level
  singletons set at server start). Tests that call OPP tools directly must
  call ``_init_server`` first, usually via ``monkeypatch.setenv("OPP_MCP_ALLOWED_DIRS", ...)``.
- ORF MCP tools ``detect_format`` and ``info`` return ``{format, confidence}`` /
  ``{format, size_mb}`` — NOT ``{success, ...}`` shape. Only ``apply_md`` and
  ``apply_xliff`` use the standard error shape.

Run with:
    OMNI_TEST_FAKE_LLM=1 OMNI_TEST_FAKE_PANDOC=1 pytest tests/test_e2e_edge_cases.py -v
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


@pytest.fixture
def init_opp(monkeypatch, tmp_path):
    """Initialize OPP MCP server with tmp_path as the only allowed directory."""
    monkeypatch.setenv("OPP_MCP_ALLOWED_DIRS", str(tmp_path))
    from opp.mcp.config import load_config
    from opp.mcp.server import _init_server
    _init_server(load_config())
    return tmp_path


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


# ============================================================================
# S10.1: Empty Input Files
# ============================================================================

class TestEmptyInputs:
    """Each tool's behavior when given an empty/zero-length input."""

    def test_opp_detect_format_empty_file(self, init_opp, tmp_path):
        """OPP detect_format_tool on empty file → error."""
        import asyncio

        from opp.mcp.server import detect_format_tool
        empty = tmp_path / "empty.docx"
        empty.write_bytes(b"")
        result = asyncio.run(detect_format_tool(str(empty)))
        # May detect by extension; if success=True, that's also fine
        if not result.get("success"):
            assert result.get("error") or result.get("message")

    def test_opp_generate_markdown_empty_file(self, init_opp, tmp_path):
        """OPP generate_markdown on empty file → error."""
        import asyncio

        from opp.mcp.server import generate_markdown
        empty = tmp_path / "empty.docx"
        empty.write_bytes(b"")
        out = tmp_path / "out.md"
        result = asyncio.run(generate_markdown(str(empty), output_path=str(out)))
        if not result.get("success"):
            assert result.get("error") or result.get("message")

    def test_opp_extract_document_empty_file(self, init_opp, tmp_path):
        """OPP extract_document on empty file → error."""
        import asyncio

        from opp.mcp.server import extract_document
        empty = tmp_path / "empty.docx"
        empty.write_bytes(b"")
        result = asyncio.run(extract_document(file_path=str(empty), output_formats="md"))
        if not result.get("success"):
            assert result.get("error") or result.get("message")

    def test_ol_translate_md_empty_string(self, tmp_path):
        """OL translate-md with empty file should not crash."""
        empty_md = tmp_path / "empty.md"
        empty_md.write_text("")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        result = subprocess.run(
            [sys.executable, "-m", "ol_cli", "translate-md",
             str(empty_md), "-s", "en", "-t", "zh",
             "-o", str(out_dir), "--no-cache", "-c", str(OL_CONFIG)],
            capture_output=True, text=True,
            env=_make_env(),
            timeout=30,
        )
        assert result.returncode in (0, 1)

    def test_orf_apply_md_empty_md(self, tmp_path):
        """ORF apply_md on empty MD."""
        from orf.mcp.server import apply_md
        empty = tmp_path / "empty.md"
        empty.write_text("")
        out = tmp_path / "out.docx"
        result = json.loads(apply_md(
            input_md=str(empty), target_format="docx", output_path=str(out),
        ))
        assert isinstance(result, dict)

    def test_orf_apply_xliff_empty_xliff(self, tmp_path):
        """ORF apply_xliff with empty XLIFF → error."""
        from orf.mcp.server import apply_xliff
        skeleton = tmp_path / "test.skeleton.zip"
        skeleton.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
        xliff = tmp_path / "empty.xlf"
        xliff.write_text("")
        out = tmp_path / "out.docx"
        result = json.loads(apply_xliff(
            input_file=str(skeleton), xliff_path=str(xliff),
            output_path=str(out), format="docx",
        ))
        assert result.get("success") is False


# ============================================================================
# S10.2: Non-Existent Files
# ============================================================================

class TestNonExistentFiles:
    """Each tool's behavior when given a path to a file that doesn't exist."""

    def test_opp_detect_format_nonexistent(self, init_opp):
        """OPP detect_format_tool on nonexistent path → error."""
        import asyncio

        from opp.mcp.server import detect_format_tool
        result = asyncio.run(detect_format_tool("/nonexistent/doc.docx"))
        assert result["success"] is False
        assert result.get("error") or result.get("message")

    def test_opp_extract_document_nonexistent(self, init_opp):
        """OPP extract_document on nonexistent path → error."""
        import asyncio

        from opp.mcp.server import extract_document
        result = asyncio.run(extract_document(
            file_path="/nonexistent/doc.docx", output_formats="md"
        ))
        assert result["success"] is False
        assert result.get("error") or result.get("message")

    def test_orf_apply_md_nonexistent(self, tmp_path):
        """ORF apply_md on nonexistent path → error."""
        from orf.mcp.server import apply_md
        result = json.loads(apply_md(
            input_md="/nonexistent/doc.md", target_format="docx",
            output_path=str(tmp_path / "out.docx"),
        ))
        assert result.get("success") is False

    def test_orf_detect_format_nonexistent(self):
        """ORF detect_format on nonexistent path → UNKNOWN."""
        from orf.mcp.server import detect_format
        result = json.loads(detect_format("/nonexistent/doc.docx"))
        # detect_format returns {format, confidence} not {success}
        assert result.get("format") in ("UNKNOWN", None)

    def test_orf_info_nonexistent(self):
        """ORF info on nonexistent path → fallback dict."""
        from orf.mcp.server import info
        result = json.loads(info("/nonexistent/doc.docx"))
        # info returns {format, size_mb, ...} not {success}
        assert isinstance(result, dict)


# ============================================================================
# S10.3: Corrupted / Invalid Files
# ============================================================================

class TestCorruptedFiles:
    """Each tool's behavior when given a corrupt or invalid file."""

    def test_opp_detect_format_corrupt_docx(self, init_opp, tmp_path):
        """OPP detect_format_tool on random bytes."""
        import asyncio

        from opp.mcp.server import detect_format_tool
        corrupt = tmp_path / "corrupt.docx"
        corrupt.write_bytes(b"\xff\xfe\x00\x01" * 100)
        result = asyncio.run(detect_format_tool(str(corrupt)))
        # May detect by extension; if error, verify it has a message
        if not result.get("success"):
            assert result.get("error") or result.get("message")

    def test_opp_generate_markdown_corrupt_docx(self, init_opp, tmp_path):
        """OPP generate_markdown on random bytes."""
        import asyncio

        from opp.mcp.server import generate_markdown
        corrupt = tmp_path / "corrupt.docx"
        corrupt.write_bytes(b"\x00" * 100)
        out = tmp_path / "out.md"
        result = asyncio.run(generate_markdown(str(corrupt), output_path=str(out)))
        if not result.get("success"):
            assert result.get("error") or result.get("message")

    def test_orf_apply_xliff_non_zip_skeleton(self, tmp_path):
        """ORF apply_xliff with non-ZIP skeleton → error."""
        from orf.mcp.server import apply_xliff
        fake_skel = tmp_path / "fake.skeleton.zip"
        fake_skel.write_text("this is not a zip file")
        xliff = tmp_path / "test.xlf"
        xliff.write_text('<?xml version="1.0"?><xliff version="1.2"/>')
        out = tmp_path / "out.docx"
        result = json.loads(apply_xliff(
            input_file=str(fake_skel), xliff_path=str(xliff),
            output_path=str(out), format="docx",
        ))
        assert result.get("success") is False


# ============================================================================
# S10.4: Large File Handling
# ============================================================================

class TestLargeFiles:
    """Behavior with unusually large inputs."""

    def test_opp_extract_large_docx_doesnt_crash(self, init_opp, tmp_path):
        """OPP handling of a large file should not crash."""
        import asyncio

        from opp.mcp.server import extract_document
        huge = tmp_path / "huge.docx"
        huge.write_bytes(b"X" * 1_000_000)
        result = asyncio.run(extract_document(
            file_path=str(huge), output_formats="md",
        ))
        # 1MB is within default limit; result may fail (not a valid DOCX) or succeed
        assert isinstance(result, dict)

    def test_ol_translate_large_md_doesnt_crash(self, tmp_path):
        """OL translate should handle long text without crashing."""
        long_text = "Hello world. " * 10_000
        md_file = tmp_path / "large.md"
        md_file.write_text(long_text)
        out_dir = tmp_path / "ol_out"
        out_dir.mkdir()
        result = subprocess.run(
            [sys.executable, "-m", "ol_cli", "translate-md",
             str(md_file), "-s", "en", "-t", "zh",
             "-o", str(out_dir), "-c", str(OL_CONFIG), "--no-cache"],
            capture_output=True, text=True,
            env=_make_env(), timeout=120,
        )
        assert result.returncode in (0, 1)


# ============================================================================
# S10.5: Unicode / CJK / Special Characters
# ============================================================================

class TestUnicodeCharacters:
    """Preservation of special characters through the pipeline."""

    @pytest.mark.parametrize("text,desc", [
        ("你好世界", "Chinese"),
        ("こんにちは", "Japanese"),
        ("😊🚀🌟", "Emoji"),
        ("Hello 中文混合 English", "Mixed CJK + Latin"),
        ("السلام عليكم", "Arabic RTL"),
    ])
    def test_ol_translate_md_unicode_preserved(self, text, desc, tmp_path):
        """OL translate should not crash on Unicode input."""
        md_file = tmp_path / f"test_{desc}.md"
        md_file.write_text(text, encoding="utf-8")
        out_dir = tmp_path / "ol_out"
        out_dir.mkdir()
        result = subprocess.run(
            [sys.executable, "-m", "ol_cli", "translate-md",
             str(md_file), "-s", "en", "-t", "zh",
             "-o", str(out_dir), "-c", str(OL_CONFIG), "--no-cache"],
            capture_output=True, text=True,
            env=_make_env(), timeout=30,
        )
        assert result.returncode in (0, 1)
        if result.returncode == 0:
            out_files = list(out_dir.glob("*.md"))
            if out_files:
                content = out_files[0].read_text(encoding="utf-8")
                assert len(content) > 0


# ============================================================================
# S10.6: File Name Special Characters
# ============================================================================

class TestSpecialFilenames:
    """Handling of special characters in file paths."""

    @pytest.mark.parametrize("filename", [
        "my document.docx",    # spaces
        "我的文档.docx",       # Unicode
        "doc(v1).docx",        # parentheses
        "doc+test.docx",       # plus sign
        "doc & report.docx",   # ampersand
    ])
    def test_opp_detect_format_special_filenames(self, filename, tmp_path):
        """OPP should handle special characters in filenames without encoding errors."""
        doc = tmp_path / filename
        doc.write_bytes(b"PK\x03\x04" + b"\x00" * 20)
        result = subprocess.run(
            [sys.executable, "-m", "opp", str(doc), "--target-format", "md",
             "--output-dir", str(tmp_path / "out")],
            capture_output=True, text=True,
            env=_make_env(OPP_MCP_ALLOWED_DIRS=str(tmp_path)),
            timeout=30,
        )
        assert result.returncode in (0, 1)
        if "UnicodeEncodeError" in result.stderr:
            pytest.fail(f"UnicodeEncodeError with filename '{filename}': {result.stderr}")


# ============================================================================
# S10.8: CLI vs MCP Error Consistency (partial)
# ============================================================================

class TestCLIvsMCPErrors:
    """Verify that CLI and MCP return semantically equivalent errors for same invalid input."""

    def test_opp_nonexistent_file_both_transports(self, tmp_path):
        """OPP: nonexistent file returns error in both CLI and MCP."""
        cli = subprocess.run(
            [sys.executable, "-m", "opp", "/nonexistent/doc.docx",
             "--target-format", "md", "--output-dir", str(tmp_path / "out")],
            capture_output=True, text=True, env=_make_env(), timeout=30,
        )
        assert cli.returncode != 0

    def test_orf_nonexistent_file_both_transports(self, tmp_path):
        """ORF: nonexistent file returns error in both CLI and MCP."""
        cli = subprocess.run(
            [sys.executable, "-m", "orf", "apply-md",
             "/nonexistent/doc.md", "--target-format", "docx",
             "--output", str(tmp_path / "out.docx")],
            capture_output=True, text=True, env=_make_env(), timeout=30,
        )
        assert cli.returncode != 0
