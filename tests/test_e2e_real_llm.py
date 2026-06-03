"""Real LLM integration tests for the OPP→OL→ORF XLIFF path.

By default, CI runs only the fake-LLM tests (use_fake_llm seam). These
real-LLM tests run via: pytest -m "nightly" or pytest -m "requires_api_key".

Prerequisites:
- Omni_Localizer/.env contains at least one of MINIMAX_API_KEY, BAIDU_API_KEY
- Omni_Localizer/config/local.yaml contains 6 model entries (each role has 2); the test passes `-c local.yaml` to ol_cli.

What's tested:
- Test 1 (Path A / MCP): 12/12 image paragraph_index preservation via MCP tools
- Test 2 (Path B / CLI): 12/12 image paragraph_index preservation via subprocess
- Test 3 (translation quality): LQA judge 4-dim average >= 5.0

Image position assertion uses ±2 paragraph tolerance because the LLM
might shift paragraphs slightly during translation. Strict 0-tolerance
matching would be too brittle.
"""

import asyncio
import base64
import json
import os
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pytest
from lxml import etree


W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


@dataclass
class ImagePosition:
    filename: str
    paragraph_index: Optional[int]
    image_data: bytes = field(repr=False, compare=False, default=b"")


@pytest.fixture
def use_real_llm(monkeypatch):
    """Load .env, verify API key, do NOT set OMNI_TEST_FAKE_LLM.

    Inverse of use_fake_llm. If no API key is available, skip the test.

    Also points OL_CONFIG_PATH at Omni_Localizer/config/local.yaml so
    MCP translate_xliff (which falls back to OL_CONFIG_PATH then to
    config/default.yaml) uses the gitignored real-LLM config rather
    than the tracked placeholder.
    """
    env_path = Path(__file__).resolve().parents[1] / "Omni_Localizer" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                if v.strip():
                    if k.strip() not in os.environ:
                        monkeypatch.setenv(k.strip(), v.strip())

    local_yaml = (
        Path(__file__).resolve().parents[1]
        / "Omni_Localizer" / "config" / "local.yaml"
    )
    if local_yaml.exists():
        monkeypatch.setenv("OL_CONFIG_PATH", str(local_yaml))

    if not any(os.environ.get(k) for k in ["MINIMAX_API_KEY", "BAIDU_API_KEY"]):
        pytest.skip("Real LLM test skipped: no MINIMAX/BAIDU key in Omni_Localizer/.env")


def extract_image_positions(docx_path: Path) -> dict[str, ImagePosition]:
    """Extract {filename: ImagePosition} from a DOCX by reading its XML."""
    with zipfile.ZipFile(docx_path) as zf:
        doc_xml = zf.read("word/document.xml")
        rels_xml = zf.read("word/_rels/document.xml.rels")

        rels_tree = etree.fromstring(rels_xml)
        embed_to_target: dict[str, str] = {}
        for rel in rels_tree.findall(f".//{REL_NS}Relationship"):
            embed_to_target[rel.get("Id")] = rel.get("Target")

        tree = etree.fromstring(doc_xml)
        all_paragraphs = tree.findall(f".//{W_NS}p")
        para_to_idx = {p: i for i, p in enumerate(all_paragraphs)}

        positions: dict[str, ImagePosition] = {}
        for drawing in tree.findall(f".//{W_NS}drawing"):
            parent = drawing.getparent()
            while parent is not None and parent.tag != f"{W_NS}p":
                parent = parent.getparent()
            para_idx = para_to_idx.get(parent) if parent is not None else None

            for blip in drawing.iter(f"{A_NS}blip"):
                embed = blip.get(f"{R_NS}embed")
                if embed and embed in embed_to_target:
                    target = embed_to_target[embed]
                    filename = target.split("/")[-1]
                    full_path = (
                        f"word/{target}" if not target.startswith("/")
                        else target.lstrip("/")
                    )
                    try:
                        image_data = zf.read(full_path)
                    except KeyError:
                        image_data = b""
                    if filename not in positions:
                        positions[filename] = ImagePosition(
                            filename=filename,
                            paragraph_index=para_idx,
                            image_data=image_data,
                        )
                    break
    return positions


def extract_xliff_units(xliff_path: Path) -> list[dict]:
    """Extract (unit_id, source, target) from an XLIFF 1.2 file."""
    tree = etree.parse(str(xliff_path))
    NS = "{urn:oasis:names:tc:xliff:document:1.2}"
    units = []
    for tu in tree.iter(f"{NS}trans-unit"):
        units.append({
            "id": tu.get("id"),
            "source": "".join(t.text or "" for t in tu.iter(f"{NS}source")),
            "target": "".join(t.text or "" for t in tu.iter(f"{NS}target")),
        })
    return units


def _build_subprocess_env() -> dict[str, str]:
    """Build env for ol_cli / orf.cli subprocess: src dirs on PYTHONPATH, no FAKE env vars."""
    env = os.environ.copy()
    suite_root = Path(__file__).resolve().parents[1]
    src_dirs = [
        str(suite_root / "tests"),
        str(suite_root / "Omni_Pre_Processor" / "src"),
        str(suite_root / "Omni_Localizer" / "src"),
        str(suite_root / "Omni_Re_Formatter" / "src"),
    ]
    env["PYTHONPATH"] = ":".join(filter(None, src_dirs + [env.get("PYTHONPATH", "")]))
    env.pop("OMNI_TEST_FAKE_LLM", None)
    env.pop("OMNI_TEST_FAKE_PANDOC", None)
    return env


def _run_opp_extraction(haier_docx: Path, tmp_path: Path) -> tuple[Path, list[ImagePosition], Path]:
    """Run OPP on the Haier DOCX. Returns (xliff_path, opp_images, skeleton_path)."""
    from opp.pipeline import OPPPipeline

    pipeline = OPPPipeline(resource_storage_dir=tmp_path / "resources")
    result = pipeline.process_file(haier_docx)
    xliff_path = pipeline.generate_xliff(
        result.extraction_result, tmp_path / "haier.xlf", "en", "zh"
    )
    skeleton_path = pipeline.save_skeleton(
        result.extraction_result, "haier", tmp_path
    )

    opp_images = [
        ImagePosition(
            filename=f"img_{i}.{img.mime_type.split('/')[-1] if img.mime_type else 'png'}",
            paragraph_index=img.paragraph_index,
            image_data=img.data or b"",
        )
        for i, img in enumerate(result.extraction_result.images)
    ]
    seen_hashes: set[int] = set()
    deduped: list[ImagePosition] = []
    for img in opp_images:
        h = hash(img.image_data)
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        deduped.append(img)
    return xliff_path, deduped, skeleton_path


def _write_images_json(opp_images: list[ImagePosition], json_path: Path) -> None:
    """Write images.json for ORF --images-json from OPP images."""
    data = {
        "images": [
            {
                "paragraph_index": img.paragraph_index,
                "mime_type": "image/png",
                "data_base64": base64.b64encode(img.image_data).decode("ascii"),
            }
            for img in opp_images
        ]
    }
    json_path.write_text(json.dumps(data), encoding="utf-8")


class TestE2ERealLLMImagePositioning:
    """Real LLM XLIFF path tests: 7/7 unique image paragraph_index preservation.

    Haier DOCX ground truth: 12 w:drawing elements, but only 7 unique image
    files referenced (drawings 3-12 reference image8-image12, with drawings
    8-12 being duplicates of 3-7). The v3 plan assumed 12 unique images —
    that was wrong. See .omo/plans/real-llm-integration-tests.md Section 0.

    Tolerance is ±2 paragraphs because the LLM may shift paragraphs
    slightly during translation. Strict 0-tolerance matching would be
    too brittle given LLM stochasticity.
    """

    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_path_a_mcp_image_positioning_7_of_7(
        self, haier_real_docx_path: Path, use_real_llm, tmp_path: Path
    ):
        """Path A (MCP): 7/7 unique images preserve paragraph_index ±2.

        OL step goes through MCP (ol_mcp.tools.translate_xliff); ORF step
        goes through CLI (orf.cli apply-xliff) since orf.mcp.tools module
        does not exist in this codebase — only orf.mcp.server (FastMCP
        server with apply_xliff registered as a tool closure).
        """
        from ol_mcp import tools as ol_mcp_tools
        from ol_mcp.tools import TranslateXliffInput

        env = _build_subprocess_env()

        xliff_path, opp_images, skeleton_path = _run_opp_extraction(
            haier_real_docx_path, tmp_path
        )
        assert len(opp_images) == 7, (
            f"Expected 7 unique OPP images (after dedup), got {len(opp_images)}. "
            f"See plan Section 0 for ground truth (12 drawings, 5 are duplicates)."
        )

        ol_result_str = asyncio.run(ol_mcp_tools.translate_xliff(TranslateXliffInput(
            input_path=str(xliff_path),
            output_path=str(tmp_path / "haier_translated.xlf"),
            source_lang="en",
            target_lang="zh",
        )))
        ol_result = json.loads(ol_result_str)
        assert ol_result["success"], f"OL translate_xliff failed: {ol_result}"

        translated_xliff = Path(ol_result["output_path"])
        assert translated_xliff.exists()

        images_json_path = tmp_path / "images.json"
        _write_images_json(opp_images, images_json_path)

        output_docx = tmp_path / "haier_final.docx"
        orf_result = subprocess.run(
            [
                sys.executable, "-m", "orf.cli", "apply-xliff",
                str(skeleton_path), "--xliff", str(translated_xliff),
                "--output", str(output_docx), "--format", "docx",
                "--images-json", str(images_json_path),
            ],
            capture_output=True, text=True, env=env,
        )
        assert orf_result.returncode == 0, (
            f"ORF apply-xliff failed (rc={orf_result.returncode}): {orf_result.stderr}"
        )
        assert output_docx.exists()

        actual_positions = extract_image_positions(output_docx)
        assert len(actual_positions) == 7, (
            f"Expected 7 unique image files in output, got {len(actual_positions)}. "
            f"See .omo/plans/real-llm-integration-tests.md Section 0 for ground truth."
        )

        for opp_img in opp_images:
            opp_hash = hash(opp_img.image_data)
            matched = None
            for actual in actual_positions.values():
                if hash(actual.image_data) == opp_hash:
                    matched = actual
                    break
            assert matched is not None, (
                f"OPP image not found in output. "
                f"Output images: {list(actual_positions.keys())}"
            )
            assert abs(matched.paragraph_index - opp_img.paragraph_index) <= 2, (
                f"Image paragraph_index mismatch: "
                f"expected {opp_img.paragraph_index}, got {matched.paragraph_index}"
            )

    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_path_b_cli_image_positioning_7_of_7(
        self, haier_real_docx_path: Path, use_real_llm, tmp_path: Path
    ):
        """Path B (CLI): 7/7 unique images preserve paragraph_index ±2."""
        config_path = (
            Path(__file__).resolve().parents[1] / "Omni_Localizer" / "config" / "local.yaml"
        )
        env = _build_subprocess_env()

        xliff_path, opp_images, skeleton_path = _run_opp_extraction(
            haier_real_docx_path, tmp_path
        )
        assert len(opp_images) == 7, (
            f"Expected 7 unique OPP images (after dedup), got {len(opp_images)}. "
            f"See plan Section 0 for ground truth (12 drawings, 5 are duplicates)."
        )

        ol_out_dir = tmp_path / "ol_out"
        ol_out_dir.mkdir()
        ol_result = subprocess.run(
            [
                sys.executable, "-m", "ol_cli", "translate-xliff",
                str(xliff_path), "-o", str(ol_out_dir), "-c", str(config_path),
            ],
            capture_output=True, text=True, env=env,
        )
        assert ol_result.returncode == 0, (
            f"OL translate-xliff failed (rc={ol_result.returncode}): {ol_result.stderr}"
        )
        translated_xliff = ol_out_dir / xliff_path.name
        assert translated_xliff.exists()

        images_json_path = tmp_path / "images.json"
        _write_images_json(opp_images, images_json_path)

        output_docx = tmp_path / "haier_final.docx"
        orf_result = subprocess.run(
            [
                sys.executable, "-m", "orf.cli", "apply-xliff",
                str(skeleton_path), "--xliff", str(translated_xliff),
                "--output", str(output_docx), "--format", "docx",
                "--images-json", str(images_json_path),
            ],
            capture_output=True, text=True, env=env,
        )
        assert orf_result.returncode == 0, (
            f"ORF apply-xliff failed (rc={orf_result.returncode}): {orf_result.stderr}"
        )
        assert output_docx.exists()

        actual_positions = extract_image_positions(output_docx)
        assert len(actual_positions) == 7, (
            f"Expected 7 unique image files in output, got {len(actual_positions)}. "
            f"See .omo/plans/real-llm-integration-tests.md Section 0 for ground truth."
        )

        for opp_img in opp_images:
            opp_hash = hash(opp_img.image_data)
            matched = None
            for actual in actual_positions.values():
                if hash(actual.image_data) == opp_hash:
                    matched = actual
                    break
            assert matched is not None
            assert abs(matched.paragraph_index - opp_img.paragraph_index) <= 2


class TestE2ERealLLMTranslationQuality:
    """Real LLM translation quality: LQA judge 4-dim average >= 5.0.

    The 5.0 threshold is the LOOSE gate (fail only if translation is
    clearly bad). 4-dim avg 5.0-7.0 is a soft warning.
    """

    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_lqa_judge_4_dim_average_above_threshold(
        self, haier_real_docx_path: Path, use_real_llm, tmp_path: Path
    ):
        from ol_lqa.judge import JudgeService
        from ol_mcp import tools as ol_mcp_tools
        from ol_mcp.tools import TranslateXliffInput

        xliff_path, opp_images, skeleton_path = _run_opp_extraction(
            haier_real_docx_path, tmp_path
        )

        ol_result_str = asyncio.run(ol_mcp_tools.translate_xliff(TranslateXliffInput(
            input_path=str(xliff_path),
            output_path=str(tmp_path / "haier_translated.xlf"),
            source_lang="en",
            target_lang="zh",
        )))
        ol_result = json.loads(ol_result_str)
        assert ol_result["success"]

        translated_xliff = Path(ol_result["output_path"])
        units = extract_xliff_units(translated_xliff)
        assert len(units) > 0

        judge = JudgeService(pass_threshold=5.0)

        async def _judge_all() -> list:
            return await asyncio.gather(*[
                judge.judge(u["source"], u["target"], u["id"])
                for u in units if u["source"] and u["target"]
            ])

        judgments = asyncio.run(_judge_all())
        assert len(judgments) > 0

        avg_adequacy = sum(j.judge_scores["adequacy"] for j in judgments) / len(judgments)
        avg_fluency = sum(j.judge_scores["fluency"] for j in judgments) / len(judgments)
        avg_terminology = sum(
            j.judge_scores["terminology_consistency"] for j in judgments
        ) / len(judgments)
        avg_format = sum(
            j.judge_scores["format_preservation"] for j in judgments
        ) / len(judgments)

        threshold = 5.0
        if any(d < threshold for d in [avg_adequacy, avg_fluency, avg_terminology, avg_format]):
            pytest.fail(
                f"Translation quality below 5.0: "
                f"adequacy={avg_adequacy:.2f}, fluency={avg_fluency:.2f}, "
                f"terminology={avg_terminology:.2f}, format={avg_format:.2f}"
            )
