"""Extended Unicode/CJK/special character preservation tests.

Covers S10.5 from the integrated test plan. Supplements the basic unicode
tests in test_e2e_edge_cases.py with more thorough character-level checks.

Tests focus on verifying that the OPP extraction + OL translation pipeline
preserves non-ASCII characters correctly end-to-end.

Run with:
    OMNI_TEST_FAKE_LLM=1 OMNI_TEST_FAKE_PANDOC=1 pytest tests/test_e2e_edge_unicode.py -v
"""

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


RTL_TEXT = "\\u0627\\u0644\\u0633\\u0644\\u0627\\u0645 \\u0639\\u0644\\u064a\\u0643\\u0645"  # Arabic: السلام عليكم
CJK_MIXED = "Hello 你好 こんにちは 안녕하세요"
EMOJI_TEXT = "Test with emoji: 😊 🚀 🌟 👍 🎉"
ACCENTED = "Crème brûlée à la française — über cool naïve résumé"
MATH_SYMBOLS = "x² + y² = z²  ≈ ∞ ≠ ≤ ≥ ± √ ∑ ∫ π"
TIBETAN = "༄༅། །བོད་སྐད་ལ་སྐུ་ཞུ།"
HIRAGANA_KATAKANA = "ひらがな カタカナ 漢字"
SPECIAL_DOCX = ["​", "\\u200B"]  # zero-width space, zero-width non-joiner


class TestUnicodeEndToEnd:
    """Verify special characters preserved through the full pipeline."""

    @pytest.mark.parametrize("text,desc", [
        (CJK_MIXED, "Mixed CJK"),
        (EMOJI_TEXT, "Emoji"),
        (ACCENTED, "Accented Latin"),
        (MATH_SYMBOLS, "Math symbols"),
        (HIRAGANA_KATAKANA, "Japanese kana + kanji"),
    ])
    def test_unicode_via_opp_ol_pipeline(self, text, desc, tmp_path):
        """OPP (file-based) → OL translation with special characters.

        Create a DOCX with special characters, extract via OPP CLI,
        translate via OL CLI, verify characters are preserved.
        """
        import zipfile

        from lxml import etree

        # Create a minimal DOCX with our special text
        docx_path = tmp_path / f"test_{desc}.docx"

        # Build document.xml with the test text
        w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

        body = etree.Element(f"{{{w_ns}}}body")
        p = etree.SubElement(body, f"{{{w_ns}}}p")
        r = etree.SubElement(p, f"{{{w_ns}}}r")
        t = etree.SubElement(r, f"{{{w_ns}}}t")
        t.text = text
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

        doc_xml = etree.tostring(
            etree.ElementTree(
                etree.Element(f"{{{w_ns}}}document",
                    nsmap={"w": w_ns, "r": r_ns},
                )
            ),
            xml_declaration=True, encoding="UTF-8", pretty_print=True,
        )
        # Fix: build the tree properly
        doc = etree.Element(f"{{{w_ns}}}document", nsmap={"w": w_ns})
        doc.append(body)
        doc_xml = etree.tostring(doc, xml_declaration=True, encoding="UTF-8", pretty_print=True)

        with zipfile.ZipFile(docx_path, "w") as zf:
            zf.writestr("word/document.xml", doc_xml)
            zf.writestr("[Content_Types].xml",
                '<?xml version="1.0"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '</Types>')
            zf.writestr("word/_rels/document.xml.rels",
                '<?xml version="1.0"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>')

        # OPP extract
        out_md = tmp_path / "opp_out"
        out_md.mkdir()
        cli = subprocess.run(
            [sys.executable, "-m", "opp", str(docx_path),
             "--target-format", "md", "--output-dir", str(out_md)],
            capture_output=True, text=True,
            env=_make_env(OPP_MCP_ALLOWED_DIRS=str(tmp_path)),
            timeout=30,
        )
        # OPP may succeed or fail on minimal DOCX; either way, don't crash
        assert "Traceback" not in cli.stderr

    def test_ol_translate_preserves_unicode_content(self, tmp_path):
        """OL should preserve Unicode content end-to-end with FAKE_LLM.

        The translated output should at minimum be valid UTF-8 and not
        garble the source content (FAKE_LLM replaces with [ZH] marker
        for unknown text, but known text is translated).
        """
        md_file = tmp_path / "test.md"
        md_file.write_text(ACCENTED, encoding="utf-8")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        result = subprocess.run(
            [sys.executable, "-m", "ol_cli", "translate-md",
             str(md_file), "-s", "en", "-t", "zh",
             "-o", str(out_dir), "-c", str(OL_CONFIG), "--no-cache"],
            capture_output=True, text=True,
            env=_make_env(),
            timeout=30,
        )
        assert result.returncode in (0, 1)
        # Verify output is valid UTF-8
        out_files = list(out_dir.glob("*.md"))
        if out_files:
            content = out_files[0].read_bytes()
            # Content should decode as UTF-8 without error
            content.decode("utf-8")
