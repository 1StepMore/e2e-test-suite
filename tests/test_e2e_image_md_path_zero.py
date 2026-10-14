"""Q13.3: MD pipeline produces 0 images in final DOCX.

Master Validation Plan Q13.3:
"MD path produces 0 images — The MD path (OPP → MD → OL → ORF) does
 NOT inject images into output."

This verifies that the MD pipeline path results in an output DOCX with
zero `<w:drawing>` elements, as distinct from the XLIFF path which
preserves images.

Uses the real Haier DOCX fixture which has known image content.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.real_chain]

SUITE_ROOT = Path(__file__).resolve().parent.parent
OL_CONFIG = SUITE_ROOT / "Omni_Localizer" / "config" / "default.yaml"

# Use the real Haier DOCX which contains images
HAIER_DOCX = SUITE_ROOT / "爱上海尔_第二章_全球创牌 - E2E测试专用.docx"


def _make_env(**extra) -> dict:
    env = os.environ.copy()
    env["OMNI_TEST_FAKE_LLM"] = "1"
    env["OMNI_TEST_FAKE_PANDOC"] = "1"
    for d in ["Omni_Pre_Processor", "Omni_Localizer", "Omni_Re_Formatter"]:
        src = SUITE_ROOT / d / "src"
        if src.exists():
            pp = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = f"{src}:" + pp if pp else str(src)
    env["OL_CONFIG_PATH"] = str(OL_CONFIG)
    env.setdefault("ZHIPU_API_KEY", "sk-dummy")
    env.setdefault("AGNES_API_KEY", "sk-dummy")
    env.setdefault("NVIDIA_NIM_API_KEY", "nvapi-dummy")
    env.update(extra)
    return env


def _cli(cmd: list[str], **extra_env) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m"] + cmd,
        capture_output=True, text=True,
        env=_make_env(**extra_env),
        cwd=str(SUITE_ROOT),
        timeout=120,
    )


def _count_drawings(docx_path: Path) -> int:
    """Count <w:drawing> elements in a DOCX."""
    import zipfile
    from lxml import etree
    with zipfile.ZipFile(docx_path) as zf:
        doc_xml = zf.read("word/document.xml")
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    tree = etree.fromstring(doc_xml)
    return len(tree.findall(f".//{ns}drawing"))


class TestMDPathZeroImages:
    """MD pipeline output DOCX must have 0 drawings."""

    def test_md_pipeline_produces_zero_drawings(self, tmp_path):
        """Full OPP→MD→OL→ORF pipeline → DOCX with 0 <w:drawing>."""
        if not HAIER_DOCX.exists():
            pytest.skip(f"Haier DOCX not found at {HAIER_DOCX}")

        # Verify source has drawings
        src_count = _count_drawings(HAIER_DOCX)
        assert src_count >= 1, "Haier DOCX should have at least 1 drawing"

        # Step 1: OPP extract to MD
        opp_dir = tmp_path / "opp"; opp_dir.mkdir()
        r = _cli(["opp", "--target-format", "md",
                   "--source-lang", "zh", "--target-lang", "en",
                   "--output-dir", str(opp_dir), str(HAIER_DOCX)])
        assert r.returncode == 0, f"OPP failed: stderr={r.stderr}"
        md_files = list(opp_dir.glob("*.md"))
        assert len(md_files) >= 1, f"No MD files in {opp_dir}"

        # Step 2: OL translate MD
        ol_dir = tmp_path / "ol"; ol_dir.mkdir()
        r = _cli(["ol_cli", "translate-md", str(md_files[0]),
                   "-o", str(ol_dir), "-c", str(OL_CONFIG),
                   "-s", "zh", "-t", "en", "--no-cache"])
        assert r.returncode == 0, f"OL failed: {r.stderr}"
        translated = ol_dir / md_files[0].name
        assert translated.exists()

        # Step 3: ORF apply MD → DOCX
        orf_dir = tmp_path / "orf"; orf_dir.mkdir()
        result_docx = orf_dir / "result.docx"
        r = _cli(["orf", "apply-md", str(translated),
                   "--target-format", "docx", "--output", str(result_docx)])
        assert r.returncode == 0, f"ORF failed: {r.stderr}"
        assert result_docx.exists()

        # Verify: 0 drawings in MD pipeline output
        final_count = _count_drawings(result_docx)
        assert final_count == 0, (
            f"MD pipeline DOCX should have 0 drawings, got {final_count}. "
            f"Source had {src_count}. MD path does NOT preserve images."
        )
