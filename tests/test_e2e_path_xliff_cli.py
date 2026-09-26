"""Path B: OPP → ol_cli translate-xliff → orf.cli apply-xliff."""

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest


pytestmark = [pytest.mark.e2e, pytest.mark.real_chain]


@pytest.fixture
def use_fake_llm(monkeypatch):
    """Sets OMNI_TEST_FAKE_LLM=1 and OMNI_TEST_FAKE_PANDOC=1 for subprocesses."""
    monkeypatch.setenv("OMNI_TEST_FAKE_LLM", "1")
    monkeypatch.setenv("OMNI_TEST_FAKE_PANDOC", "1")
    return True


def _make_subprocess_env() -> dict:
    """Build subprocess env with PYTHONPATH including all 3 src dirs + the
    test seam env vars (which monkeypatch writes to os.environ)."""
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


class TestPathXliffCLI:
    def test_full_chain_cli_returns_zero(
        self, opp_pipeline, meridian_english_docx_path, tmp_path: Path, use_fake_llm
    ):
        """End-to-end: real OPP + real OL CLI (with fake LLM) + real ORF CLI (with fake pandoc).

        Uses the canonical en→zh English fixture (meridian_robotics.docx), not
        the 海尔 zh→en fixture: under OMNI_TEST_FAKE_LLM=1 the OL fake pool
        (ol_pool/fake.py) ECHOES the source prefixed with the target lang
        ("[zh] <source>"), and the shipped default.yaml sets
        block_on_source_script_fragment: true with target_locale en-US — so a
        Chinese source (CJK) echoed into the "target" is correctly blocked by
        quality Gate 6 (SOURCE_SCRIPT_FRAGMENT, rc=4). An English source keeps
        the hermetic chain green while still exercising the full plumbing.
        """
        output_dir = tmp_path / "xliff_cli"
        opp_out = output_dir / "opp"
        ol_out = output_dir / "ol"
        orf_out = output_dir / "orf"
        for d in (opp_out, ol_out, orf_out):
            d.mkdir(parents=True)

        result = opp_pipeline.process_file(meridian_english_docx_path)
        assert result.extraction_result is not None

        xliff_path = opp_out / f"{meridian_english_docx_path.stem}.xlf"
        opp_pipeline.generate_xliff(result.extraction_result, xliff_path, "en", "zh")
        assert xliff_path.exists()

        skeleton_path = opp_pipeline.save_skeleton(
            result.extraction_result, meridian_english_docx_path.stem, orf_out
        )
        assert skeleton_path is not None and skeleton_path.exists()

        config_path = (
            Path(__file__).resolve().parent.parent
            / "Omni_Localizer" / "config" / "default.yaml"
        )
        env = _make_subprocess_env()
        dummy_env = {
            "ZHIPU_API_KEY": "test-dummy",
            "AGNES_API_KEY": "test-dummy",
            "NVIDIA_NIM_API_KEY": "test-dummy",
        }
        env.update(dummy_env)
        ol_result = subprocess.run(
            [sys.executable, "-m", "ol_cli", "translate-xliff",
             str(xliff_path), "-o", str(ol_out),
             "-c", str(config_path), "--no-cache"],
            capture_output=True, text=True, env=env,
        )
        assert ol_result.returncode == 0, (
            f"OL CLI failed (rc={ol_result.returncode}): {ol_result.stderr}"
        )

        translated_xliff = ol_out / f"{meridian_english_docx_path.stem}.xlf"
        assert translated_xliff.exists(), f"Translated XLIFF not produced: {ol_result.stderr}"
        xlf_content = translated_xliff.read_text(encoding="utf-8")
        assert "<target>" in xlf_content, "No <target> elements in OL output"
        tree = ET.fromstring(xlf_content)
        ns = "urn:oasis:names:tc:xliff:document:1.2"
        translated_count = sum(
            1 for unit in tree.iter(f"{{{ns}}}trans-unit")
            if (s := unit.find(f"{{{ns}}}source")) is not None
            and (t := unit.find(f"{{{ns}}}target")) is not None
            and s.text and t.text and s.text != t.text
        )
        assert translated_count > 0, "No translation detected (all source==target)"

        orf_result = subprocess.run(
            [sys.executable, "-m", "orf.cli", "apply-xliff",
             str(skeleton_path), "--xliff", str(translated_xliff),
             "--output", str(orf_out / "result.docx"),
             "--format", "docx"],
            capture_output=True, text=True, env=env,
        )
        assert orf_result.returncode == 0, (
            f"ORF CLI failed (rc={orf_result.returncode}): {orf_result.stderr}"
        )

        docx_path = orf_out / "result.docx"
        assert docx_path.exists()
        with zipfile.ZipFile(docx_path) as zf:
            assert "word/document.xml" in zf.namelist()
            doc_xml = zf.read("word/document.xml").decode("utf-8")
        assert any(m in doc_xml for m in ["[zh]", "[ZH]", "你好", "世界", "用户手册", "测试", "功能"]), \
            f"No translation markers in final DOCX: {doc_xml[:500]}"
