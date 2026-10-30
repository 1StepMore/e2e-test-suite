"""Extended filename special character handling tests.

Covers S10.6 from the integrated test plan. Supplements the basic filename
tests in test_e2e_edge_cases.py with more thorough per-module testing
via CLI subprocesses (where path escaping matters).

Tests that each module handles: spaces, Unicode, parentheses, ampersands,
plus signs in file paths without crashing with encoding errors.

Run with:
    OMNI_TEST_FAKE_LLM=1 OMNI_TEST_FAKE_PANDOC=1 pytest tests/test_e2e_edge_filenames.py -v
"""

import os
import subprocess
import sys
import zipfile
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


# Test filenames that should work
SPECIAL_FILENAMES = [
    "my document.docx",      # spaces
    "我的文档.docx",         # Unicode (Chinese)
    "doc(v1).docx",         # parentheses
    "doc+test.docx",        # plus sign
    "doc & report.docx",    # ampersand
    "doc(v1.2_final).docx",  # mixed special chars
    "a_b_c.docx",           # underscores
    "doc - copy.docx",      # dash
    "100% complete.docx",   # percent
    "doc#1.docx",           # hash
]

# Fixtures on the suite root for OPP/ORF CLI access
SUITE_ROOT_REAL = Path(__file__).resolve().parent.parent


def _create_minimal_docx(path: Path) -> None:
    """Create a minimal valid DOCX at the given path."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml",
            '<?xml version="1.0"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>Test</w:t></w:r></w:p></w:body>'
            '</w:document>')
        zf.writestr("[Content_Types].xml",
            '<?xml version="1.0"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '</Types>')
        zf.writestr("word/_rels/document.xml.rels",
            '<?xml version="1.0"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>')


class TestSpecialFilenamesOPP:
    """OPP should handle special characters in filenames."""

    @pytest.mark.parametrize("filename", SPECIAL_FILENAMES)
    def test_opp_extract_special_filename(self, filename, tmp_path):
        """OPP extract on files with special filename characters should not crash."""
        docx = tmp_path / filename
        _create_minimal_docx(docx)
        out = tmp_path / "out"
        out.mkdir()

        env = _make_env(OPP_MCP_ALLOWED_DIRS=str(tmp_path))
        try:
            cli = subprocess.run(
                [sys.executable, "-m", "opp", str(docx),
                 "--target-format", "md", "--output-dir", str(out)],
                capture_output=True, text=True,
                env=env,
                timeout=30,
            )
        except (subprocess.CalledProcessError, OSError) as e:
            # Some filenames may cause OS-level errors on specific filesystems
            # We only care about UnicodeEncodeError or similar encoding crashes
            if "UnicodeEncodeError" in str(e) or "encoding" in str(e).lower():
                pytest.fail(f"Encoding error with filename '{filename}': {e}")
            pytest.skip(f"OS error with filename '{filename}': {e}")

        # Should not crash with encoding error
        assert "UnicodeEncodeError" not in cli.stderr
        assert "UnicodeDecodeError" not in cli.stderr


class TestSpecialFilenamesORF:
    """ORF should handle special characters in filenames."""

    @pytest.mark.parametrize("filename", ["my file.md", "测试.md", "doc(v1).md",
                                            "doc+test.md", "doc & report.md"])
    def test_orf_detect_format_special_filename(self, filename, tmp_path):
        """ORF detect_format on files with special chars should not crash."""
        md_file = tmp_path / filename
        md_file.write_text("# Test")

        import json

        from orf.mcp.server import detect_format

        result = json.loads(detect_format(str(md_file)))
        # May fail (file not a real format) but should not crash with encoding error
        assert isinstance(result, dict)
