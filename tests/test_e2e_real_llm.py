"""Real LLM integration tests — full E2E matrix coverage.

Replaces the previous 3-test design with a 14-test 4-tier suite that exercises
every (component × transport × format) cell. The user's core pursuit: make sure
every feature works.

Test layout (see .omo/plans/e2e-test-suite-redesign.md for full design):

- Tier 1 — Per-component × per-transport smoke (6 parametrized tests)
    OPP × {CLI, MCP} + OL × {CLI, MCP} + ORF × {CLI, MCP}
    Each exercises all relevant format paths for its component.
    Verifies every transport can drive its component to a valid output.
    Runtime: ~8-12 min total.

- Tier 2 — Sparse homogeneous E2E (4 tests)
    xliff/md intermediate × all-CLI/all-MCP transport combos.
    Full OPP→OL→ORF pipeline to final DOCX.
    Asserts 7/7 unique images preserved (paragraph_index within tolerance).
    Runtime: ~12-16 min total.
    Tier 2.2 / 2.4 (all-MCP) blocked on Phase 0.5 (OPP MCP save_skeleton tool).

- Tier 3 — LQA on final DOCX text (2 tests)
    Full OPP→OL→ORF pipeline, then extract text from final DOCX.
    JudgeService 4-dim avg (adequacy, fluency, terminology, format) ≥ 5.0.
    Runtime: ~6-8 min total.

- Tier 4 — ORF format coverage (2 tests)
    Full pipeline ending in MD→EPUB and MD→HTML.
    Verifies ORF's other output formats work end-to-end.
    Runtime: ~6-8 min total.

Direction: zh -> en. The Haier test DOCX is in Chinese, so OPP XLIFF is
generated as source-language="zh" target-language="en", and OL is called with
source_lang="zh", target_lang="en". Switching to en -> zh would cause the LLM
to refuse to translate (it sees Chinese source text and returns meta-commentary
instead of translation), making LQA a no-op.

Test fixture: 爱上海尔_第二章_全球创牌 - E2E测试专用.docx (real, no synthetic).
Per the user, this is the canonical test DOCX and is non-negotiable for all tiers.

Prerequisites:
- Omni_Localizer/.env contains at least one of MINIMAX_API_KEY, BAIDU_API_KEY
- Omni_Localizer/config/local.yaml contains 6 model entries (each role has 2)
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
from typing import Literal, Optional

import pytest
from lxml import etree


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ImagePosition:
    filename: str
    paragraph_index: Optional[int]
    image_data: bytes = field(repr=False, compare=False, default=b"")


@dataclass
class OppOutputs:
    """Outputs from one OPP run on a single DOCX.

    - skeleton_path: required by ORF.apply_xliff as the `input_file` arg.
    - xliff_path / md_path: the two intermediate formats OPP can produce.
      Consumed by OL.
    - images_json_path: required by ORF when injecting images back into the
      translated DOCX. Format: {images: [{paragraph_index, mime_type,
      data_base64}, ...]}.
    """
    skeleton_path: Path
    xliff_path: Path
    md_path: Path
    images_json_path: Path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
        pytest.fail(
            "Tier 3 LQA test requires a real LLM API key. "
            "Set MINIMAX_API_KEY or BAIDU_API_KEY in Omni_Localizer/.env, "
            "or in the test environment. Silent skip is removed — a missing key "
            "now ERRORs so pipeline regressions are visible instead of hidden."
        )


@pytest.fixture
def use_opp_mcp(monkeypatch):
    """Initialize the OPP MCP server in-process so its tools are callable.

    Sets OPP_MCP_ALLOWED_DIRS to /tmp and the project root (if not already
    set), then loads MCPConfig and calls opp.mcp.server._init_server(config).
    Mirrors what main() does in production but in-process, without needing
    the FastMCP stdio server. Re-initializes per test (cheap; just sets
    module globals).
    """
    from opp.mcp import server as _opp_mcp_server
    from opp.mcp.config import load_config as _load_opp_mcp_config

    if not os.environ.get("OPP_MCP_ALLOWED_DIRS"):
        allowed = ["/tmp", str(Path(__file__).resolve().parents[1])]
        monkeypatch.setenv("OPP_MCP_ALLOWED_DIRS", ":".join(allowed))

    _opp_mcp_server._init_server(_load_opp_mcp_config())


# ---------------------------------------------------------------------------
# Helpers — subprocess env (unchanged)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helpers — DOCX / XLIFF inspection (unchanged)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helpers — per-component runners (Phase 2-4 stubs)
# ---------------------------------------------------------------------------

async def _run_opp(
    transport: Literal["cli", "mcp"],
    docx_path: Path,
    out_dir: Path,
    source_lang: str = "zh",
    target_lang: str = "en",
) -> OppOutputs:
    """Run OPP on docx_path via the chosen transport.

    The OPP "transport" choice covers the XLIFF/MD generation step:
    - transport="cli": subprocess `python -m opp.cli <file> --target-format both
      --output-dir <dir> --source-lang zh --target-lang en` writes
      {base_name}.xlf and {base_name}.md to out_dir.
    - transport="mcp": in-process call to opp.mcp.server.generate_xliff and
      opp.mcp.server.generate_markdown (async, return dict with success +
      output_path).

    Skeleton and images.json always come from OPPPipeline Python API, because
    OPP CLI and OPP MCP do not expose them. The skeleton is required by
    ORF.apply_xliff, and images.json is required by ORF when injecting images
    back into the translated DOCX.

    Phase 0.5 will add save_skeleton to OPP MCP, after which the MCP path can
    produce the skeleton without falling back to the Python API. The CLI path
    is unlikely to ever expose skeleton (out of CLI's scope).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    base_name = docx_path.stem
    xliff_path = out_dir / f"{base_name}.xlf"
    md_path = out_dir / f"{base_name}.md"

    if transport == "cli":
        result = subprocess.run(
            [
                sys.executable, "-m", "opp.cli", str(docx_path),
                "--output-dir", str(out_dir),
                "--target-format", "both",
                "--source-lang", source_lang,
                "--target-lang", target_lang,
            ],
            capture_output=True, text=True, env=_build_subprocess_env(),
        )
        assert result.returncode == 0, (
            f"opp.cli failed (rc={result.returncode}): {result.stderr}"
        )
    elif transport == "mcp":
        from opp.mcp.server import generate_xliff, generate_markdown

        xliff_result = await generate_xliff(
            str(docx_path), source_lang, target_lang,
            output_path=str(xliff_path),
        )
        assert xliff_result.get("success"), (
            f"OPP MCP generate_xliff failed: {xliff_result}"
        )
        md_result = await generate_markdown(
            str(docx_path), output_path=str(md_path),
        )
        assert md_result.get("success"), (
            f"OPP MCP generate_markdown failed: {md_result}"
        )
        xliff_path = Path(xliff_result["output_path"])
        md_path = Path(md_result["output_path"])
    else:
        raise ValueError(f"Unknown transport: {transport!r}")

    _assert_non_empty_file(xliff_path)
    _assert_non_empty_file(md_path)

    from opp.pipeline import OPPPipeline

    pipeline = OPPPipeline(resource_storage_dir=out_dir / "resources")
    proc_result = pipeline.process_file(docx_path)
    assert proc_result.extraction_result is not None, (
        "OPPPipeline.process_file returned no extraction_result"
    )

    skeleton_path = pipeline.save_skeleton(
        proc_result.extraction_result, base_name, out_dir,
    )
    assert skeleton_path is not None, (
        f"OPPPipeline.save_skeleton returned None for {docx_path}"
    )
    _assert_non_empty_file(skeleton_path)

    images_json_path = out_dir / "images.json"
    pipeline.generate_images_json(proc_result.extraction_result, images_json_path)
    _assert_non_empty_file(images_json_path)

    return OppOutputs(
        skeleton_path=skeleton_path,
        xliff_path=xliff_path,
        md_path=md_path,
        images_json_path=images_json_path,
    )


async def _run_ol(
    transport: Literal["cli", "mcp"],
    intermediate: Path,
    out_dir: Path,
    source_lang: str = "zh",
    target_lang: str = "en",
) -> Path:
    """Translate the intermediate file (.xlf or .md) via the chosen transport.

    Returns the path to the translated file. OL writes its output to
    `out_dir / intermediate.name` in all paths, so callers can rely on
    that location for downstream ORF consumption.

    The MCP path has an asymmetry: `translate_xliff` is file-based (takes
    `input_path` and `output_path`), but `translate_md_text` is text-in/text-out
    (takes `content: str` and returns `translated: str`). The MD MCP path
    therefore needs a read-file → call → write-file dance.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    config_path = (
        Path(__file__).resolve().parents[1]
        / "Omni_Localizer" / "config" / "local.yaml"
    )
    is_xliff = intermediate.suffix == ".xlf"
    output_path = out_dir / intermediate.name

    if transport == "cli":
        if is_xliff:
            cmd = [
                sys.executable, "-m", "ol_cli", "translate-xliff",
                str(intermediate), "-o", str(out_dir), "-c", str(config_path),
                "-s", source_lang, "-t", target_lang,
            ]
        else:
            cmd = [
                sys.executable, "-m", "ol_cli", "translate-md",
                str(intermediate), "-o", str(out_dir), "-c", str(config_path),
                "-s", source_lang, "-t", target_lang,
            ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=_build_subprocess_env(),
        )
        assert result.returncode == 0, (
            f"ol_cli translate failed (rc={result.returncode}): {result.stderr}"
        )
        _assert_non_empty_file(output_path)
        return output_path

    if transport == "mcp":
        from ol_mcp.tools import (
            TranslateInput, TranslateXliffInput,
            translate_md_text, translate_xliff,
        )

        if is_xliff:
            result_str = await translate_xliff(TranslateXliffInput(
                input_path=str(intermediate),
                output_path=str(output_path),
                source_lang=source_lang,
                target_lang=target_lang,
                config_path=str(config_path),
            ))
            result = json.loads(result_str)
            assert result.get("success"), (
                f"OL MCP translate_xliff failed: {result}"
            )
            return Path(result["output_path"])

        md_text = intermediate.read_text(encoding="utf-8")
        result_str = await translate_md_text(TranslateInput(
            content=md_text,
            source_lang=source_lang,
            target_lang=target_lang,
            config_path=str(config_path),
        ))
        result = json.loads(result_str)
        assert result.get("success"), (
            f"OL MCP translate_md_text failed: {result}"
        )
        output_path.write_text(result["translated"], encoding="utf-8")
        return output_path

    raise ValueError(f"Unknown transport: {transport!r}")


def _run_orf(
    transport: Literal["cli", "mcp"],
    skeleton_path: Path,
    translated_intermediate: Path,
    output_path: Path,
    intermediate_format: Literal["xliff", "md"],
    target_format: Literal["docx", "epub", "html"] = "docx",
    images_json: Optional[Path] = None,
) -> Path:
    """Apply translated intermediate to skeleton via the chosen transport.

    For XLIFF intermediate, `skeleton_path` is passed as the `input_file` arg
    to ORF's `apply-xliff` (per ORF's docstring, this is the "Original document
    file path (skeleton)"). For MD intermediate, skeleton is not used by ORF
    `apply-md` (MD is converted to target format directly via pandoc).

    ORF CLI's `apply-md` does NOT support `--images-json` (per cli.py:122
    "image injection not supported for MD pipeline; use XLIFF pipeline for
    precise image placement"). The MCP `apply_md` similarly has no images
    param. So the MD path cannot inject images back into the output — this
    is a known ORF limitation, not a test bug.

    The MCP `apply_xliff` takes `images` as a list of dicts (not a file
    path), so for the MCP XLIFF path we read the images.json and pass its
    `images` list directly.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if transport == "cli":
        if intermediate_format == "xliff":
            cmd = [
                sys.executable, "-m", "orf.cli", "apply-xliff",
                str(skeleton_path), "--xliff", str(translated_intermediate),
                "--output", str(output_path), "--format", target_format,
            ]
            if images_json is not None:
                cmd.extend(["--images-json", str(images_json)])
        else:
            cmd = [
                sys.executable, "-m", "orf.cli", "apply-md",
                str(translated_intermediate), "--target-format", target_format,
                "--output", str(output_path),
            ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=_build_subprocess_env(),
        )
        assert result.returncode == 0, (
            f"orf.cli apply failed (rc={result.returncode}): {result.stderr}"
        )
        _assert_non_empty_file(output_path)
        return output_path

    if transport == "mcp":
        from orf.mcp.server import apply_md, apply_xliff

        if intermediate_format == "xliff":
            images_list: Optional[list[dict]] = None
            if images_json is not None:
                images_payload = json.loads(images_json.read_text(encoding="utf-8"))
                images_list = images_payload.get("images")
            result_str = apply_xliff(
                input_file=str(skeleton_path),
                xliff_path=str(translated_intermediate),
                output_path=str(output_path),
                format=target_format,
                images=images_list,
            )
        else:
            result_str = apply_md(
                input_md=str(translated_intermediate),
                target_format=target_format,
                output_path=str(output_path),
            )
        result = json.loads(result_str)
        assert result.get("success"), f"ORF MCP apply failed: {result}"
        return Path(result["output_path"])

    raise ValueError(f"Unknown transport: {transport!r}")


# ---------------------------------------------------------------------------
# Helpers — text extraction (Phase 7-8 stubs)
# ---------------------------------------------------------------------------

def _extract_docx_text(docx_path: Path) -> list[tuple[int, str]]:
    """Extract [(paragraph_index, text), ...] from a DOCX, in order."""
    with zipfile.ZipFile(docx_path) as zf:
        doc_xml = zf.read("word/document.xml")
    tree = etree.fromstring(doc_xml)
    return [
        (i, "".join(t.text or "" for t in p.iter(f"{W_NS}t")))
        for i, p in enumerate(tree.findall(f".//{W_NS}p"))
    ]


def _extract_epub_text(epub_path: Path) -> str:
    """Extract concatenated text from all XHTML/HTML files inside the EPUB.

    EPUBs are ZIP archives whose body content lives in `OEBPS/*.xhtml` (or
    `EPUB/*.xhtml` depending on producer). We concatenate text from every
    `.xhtml` / `.html` / `.htm` entry and strip XML/HTML tags. Order is
    determined by ZIP entry order, which is sufficient for LQA — judges
    compare against the source DOCX text, not a specific chapter mapping.
    """
    import re as _re

    parts: list[str] = []
    with zipfile.ZipFile(epub_path) as zf:
        for name in zf.namelist():
            if not name.lower().endswith((".xhtml", ".html", ".htm")):
                continue
            try:
                content = zf.read(name).decode("utf-8", errors="replace")
            except Exception:
                continue
            text = _re.sub(r"<[^>]+>", " ", content)
            text = _re.sub(r"\s+", " ", text).strip()
            if text:
                parts.append(text)
    return " ".join(parts)


def _extract_html_text(html_path: Path) -> str:
    """Extract text from an HTML file (pandoc MD→HTML output)."""
    import re as _re

    content = html_path.read_text(encoding="utf-8", errors="replace")
    text = _re.sub(r"<script\b.*?</script>", " ", content, flags=_re.DOTALL | _re.IGNORECASE)
    text = _re.sub(r"<style\b.*?</style>", " ", text, flags=_re.DOTALL | _re.IGNORECASE)
    text = _re.sub(r"<[^>]+>", " ", text)
    text = _re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Helpers — LQA judge runner
# ---------------------------------------------------------------------------

async def _judge_docx_text(
    target_docx: Path,
    source_docx: Path,
    src_lang: str = "zh",
    tgt_lang: str = "en",
) -> dict:
    """Run JudgeService over (source, target) paragraph pairs aligned by paragraph_index.

    Returns a dict with avg_adequacy, avg_fluency, avg_terminology, avg_format
    (the 4 JudgeService dimensions) plus the raw judgments list. Pairs with
    empty source or target are skipped (untranslatable paragraphs).
    """
    from ol_lqa.judge import JudgeService
    from ol_pool.router import ModelPool

    target_paras = _extract_docx_text(target_docx)
    source_paras = _extract_docx_text(source_docx)
    source_by_idx = {idx: text for idx, text in source_paras}

    config_path = os.environ.get("OL_CONFIG_PATH", "config/default.yaml")
    model_pool = ModelPool.get_instance(config_path)
    judge = JudgeService(pass_threshold=5.0, model_pool=model_pool)
    pairs = [
        (source_by_idx[idx], text, idx)
        for idx, text in target_paras
        if idx in source_by_idx and source_by_idx[idx].strip() and text.strip()
    ]
    if not pairs:
        return {
            "avg_adequacy": 0.0, "avg_fluency": 0.0,
            "avg_terminology": 0.0, "avg_format": 0.0,
            "judgments": [],
        }

    judgments = await asyncio.gather(*[
        judge.judge(src, tgt, unit_id) for src, tgt, unit_id in pairs
    ])
    n = len(judgments)
    return {
        "avg_adequacy": sum(j.judge_scores["adequacy"] for j in judgments) / n,
        "avg_fluency": sum(j.judge_scores["fluency"] for j in judgments) / n,
        "avg_terminology": sum(
            j.judge_scores["terminology_consistency"] for j in judgments
        ) / n,
        "avg_format": sum(
            j.judge_scores["format_preservation"] for j in judgments
        ) / n,
        "judgments": judgments,
    }


# ---------------------------------------------------------------------------
# Helpers — E2E chain + image positioning assertion
# ---------------------------------------------------------------------------

async def _run_e2e_chain(
    transport: Literal["cli", "mcp"],
    haier_docx: Path,
    tmp_path: Path,
    intermediate: Literal["xliff", "md"] = "xliff",
    target: Literal["docx", "epub", "html"] = "docx",
    src_lang: str = "zh",
    tgt_lang: str = "en",
) -> tuple[Path, OppOutputs]:
    """Run the full OPP -> OL -> ORF chain. Returns (output_path, opp_outputs)."""
    opp_out = tmp_path / "opp"
    ol_out = tmp_path / "ol"
    orf_out = tmp_path / "orf"
    orf_out.mkdir(parents=True, exist_ok=True)

    opp = await _run_opp(transport, haier_docx, opp_out, src_lang, tgt_lang)
    intermediate_path = opp.xliff_path if intermediate == "xliff" else opp.md_path
    translated = await _run_ol(transport, intermediate_path, ol_out, src_lang, tgt_lang)
    output = orf_out / f"haier_final.{target}"
    images_json = opp.images_json_path if intermediate == "xliff" else None
    _run_orf(
        transport, opp.skeleton_path, translated, output,
        intermediate, target, images_json,
    )
    return output, opp


async def _run_e2e_chain_mixed(
    opp_transport: Literal["cli", "mcp"],
    ol_transport: Literal["cli", "mcp"],
    orf_transport: Literal["cli", "mcp"],
    haier_docx: Path,
    tmp_path: Path,
    intermediate: Literal["xliff", "md"] = "xliff",
    target: Literal["docx", "epub", "html"] = "docx",
    src_lang: str = "zh",
    tgt_lang: str = "en",
) -> tuple[Path, OppOutputs]:
    """Run the full OPP -> OL -> ORF chain with per-component transport selection.

    Closes the gap where the entire pipeline was forced onto a single transport.
    A mixed chain (e.g. OPP CLI + OL MCP + ORF CLI) catches transport-specific
    bugs that only appear when the same data crosses transport boundaries.
    """
    opp_out = tmp_path / "opp"
    ol_out = tmp_path / "ol"
    orf_out = tmp_path / "orf"
    orf_out.mkdir(parents=True, exist_ok=True)

    opp = await _run_opp(opp_transport, haier_docx, opp_out, src_lang, tgt_lang)
    intermediate_path = opp.xliff_path if intermediate == "xliff" else opp.md_path
    translated = await _run_ol(ol_transport, intermediate_path, ol_out, src_lang, tgt_lang)
    output = orf_out / f"haier_final.{target}"
    images_json = opp.images_json_path if intermediate == "xliff" else None
    _run_orf(
        orf_transport, opp.skeleton_path, translated, output,
        intermediate, target, images_json,
    )
    return output, opp


def _assert_image_positioning(
    output_docx: Path,
    images_json: Path,
    tolerance: int = 2,
) -> None:
    """Assert that all OPP images appear in output_docx with paragraph_index within tolerance.

    Reads OPP-side image data + paragraph_index from images.json, output-side
    from extract_image_positions(output_docx), matches by image_data hash,
    and asserts |output_idx - opp_idx| <= tolerance for each pair.
    """
    payload = json.loads(images_json.read_text(encoding="utf-8"))
    opp_images = [
        ImagePosition(
            filename=f"img_{i}",
            paragraph_index=img["paragraph_index"],
            image_data=base64.b64decode(img["data_base64"]),
        )
        for i, img in enumerate(payload["images"])
    ]
    seen: set[int] = set()
    deduped: list[ImagePosition] = []
    for img in opp_images:
        h = hash(img.image_data)
        if h in seen:
            continue
        seen.add(h)
        deduped.append(img)

    actual = extract_image_positions(output_docx)
    assert len(actual) == len(deduped), (
        f"Expected {len(deduped)} unique OPP images, got {len(actual)} in output"
    )
    for opp_img in deduped:
        opp_hash = hash(opp_img.image_data)
        matched = next(
            (a for a in actual.values() if hash(a.image_data) == opp_hash),
            None,
        )
        assert matched is not None, (
            f"OPP image not found in output. "
            f"Output images: {list(actual.keys())}"
        )
        assert abs(matched.paragraph_index - opp_img.paragraph_index) <= tolerance, (
            f"Image paragraph_index mismatch: "
            f"expected {opp_img.paragraph_index}, got {matched.paragraph_index}, "
            f"tolerance {tolerance}"
        )


def _assert_non_empty_file(path: Path, min_size: int = 1) -> None:
    """Assert a file exists and has content (Audit 7.1)."""
    if not path.exists():
        raise AssertionError(f"File not found: {path}")
    size = path.stat().st_size
    if size < min_size:
        raise AssertionError(
            f"File exists but is empty or too small ({size} bytes): {path}"
        )


_CJK_RANGES = (
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0x3400, 0x4DBF),   # CJK Extension A
    (0x3040, 0x309F),   # Hiragana
    (0x30A0, 0x30FF),   # Katakana
    (0xAC00, 0xD7AF),   # Hangul Syllables
)


def _cjk_ratio(text: str) -> float:
    """Return fraction of alphabetic characters that are CJK / Hangul / Kana."""
    if not text:
        return 0.0
    cjk = 0
    alpha = 0
    for ch in text:
        if not ch.isalpha():
            continue
        alpha += 1
        cp = ord(ch)
        if any(lo <= cp <= hi for lo, hi in _CJK_RANGES):
            cjk += 1
    return cjk / alpha if alpha else 0.0


def _assert_translated_to_target_lang(text: str, target_lang: str) -> None:
    """Assert the text is in the target language (Audit 7.2).

    For target_lang='en', the CJK ratio must be below 0.5 (allowing
    some proper nouns / names). For target_lang='zh', the CJK ratio
    must be at or above 0.5. Other target languages are not checked.
    """
    if not text or not text.strip():
        raise AssertionError(
            f"Translated text is empty — LLM produced no output. Sample: {text[:100]!r}"
        )
    if target_lang not in ("en", "zh"):
        return
    ratio = _cjk_ratio(text)
    if target_lang == "en" and ratio >= 0.5:
        raise AssertionError(
            f"Translated text is {ratio:.0%} CJK — LLM likely returned the "
            f"source language instead of English. Sample: {text[:200]!r}"
        )
    if target_lang == "zh" and ratio < 0.5:
        raise AssertionError(
            f"Translated text is only {ratio:.0%} CJK — LLM likely returned "
            f"the wrong language for target=zh. Sample: {text[:200]!r}"
        )


def _require_pandoc() -> None:
    """Skip the test if pandoc is not in PATH. Required for ORF apply-md (MD->DOCX/EPUB/HTML)."""
    import shutil
    if shutil.which("pandoc") is None:
        pytest.skip(
            "pandoc not in PATH; required for ORF apply-md (MD->DOCX/EPUB/HTML). "
            "Install via `apt-get install pandoc` or `pip install pypandoc-binary`."
        )


# ---------------------------------------------------------------------------
# Tier 1 — Per-component × per-transport smoke (6 parametrized tests)
# ---------------------------------------------------------------------------

class TestE2ERealLLMSmoke:
    """Per-component × per-transport smoke: 6 parametrized tests.

    Each test exercises all relevant format paths for its component:
    - OPP test: extracts both XLIFF and MD from Haier DOCX; asserts both
      are well-formed, 9 units / 9 paragraphs, source-language="zh".
    - OL test: translates both XLIFF and MD intermediates; asserts exit 0,
      target-language="en", 9 units / paragraphs preserved.
    - ORF test: produces all 4 output formats from the OPP/OL outputs
      (XLIFF→DOCX, MD→{DOCX, EPUB, HTML}); asserts each output file is
      valid for its type, DOCX cases have 7 unique images.

    Verifies every transport can drive its component to a valid output.
    Real Haier DOCX throughout.
    """

    @pytest.mark.parametrize("component,transport", [
        ("opp", "cli"),
        ("opp", "mcp"),
        ("ol", "cli"),
        ("ol", "mcp"),
        ("orf", "cli"),
        ("orf", "mcp"),
    ])
    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_component_transport_smoke(
        self, component, transport, haier_real_docx_path, use_real_llm, use_opp_mcp, artifact_dir,
    ):
        if component == "opp":
            outputs = asyncio.run(
                _run_opp(transport, haier_real_docx_path, artifact_dir, "zh", "en")
            )
            assert outputs.xliff_path.exists() and outputs.xliff_path.stat().st_size > 0
            assert outputs.md_path.exists() and outputs.md_path.stat().st_size > 0
            assert outputs.skeleton_path.exists() and outputs.skeleton_path.stat().st_size > 0
            assert outputs.images_json_path.exists() and outputs.images_json_path.stat().st_size > 0
            xliff_text = outputs.xliff_path.read_text(encoding="utf-8")
            assert 'source-language="zh"' in xliff_text
            assert 'target-language="en"' in xliff_text
            assert xliff_text.count("<trans-unit") == 9
        elif component == "ol":
            opp = asyncio.run(
                _run_opp("cli", haier_real_docx_path, artifact_dir, "zh", "en")
            )
            ol_out = artifact_dir / "ol"
            translated_xliff = asyncio.run(
                _run_ol(transport, opp.xliff_path, ol_out, "zh", "en")
            )
            translated_md = asyncio.run(
                _run_ol(transport, opp.md_path, ol_out, "zh", "en")
            )
            assert translated_xliff.exists() and translated_xliff.stat().st_size > 0
            assert translated_md.exists() and translated_md.stat().st_size > 0
            xliff_text = translated_xliff.read_text(encoding="utf-8")
            assert 'target-language="en"' in xliff_text
            assert xliff_text.count("<trans-unit") == 9
        elif component == "orf":
            _require_pandoc()
            opp = asyncio.run(
                _run_opp("cli", haier_real_docx_path, artifact_dir, "zh", "en")
            )
            ol_out = artifact_dir / "ol"
            orf_out = artifact_dir / "orf"
            orf_out.mkdir(parents=True, exist_ok=True)
            translated_xliff = asyncio.run(
                _run_ol("cli", opp.xliff_path, ol_out, "zh", "en")
            )
            translated_md = asyncio.run(
                _run_ol("cli", opp.md_path, ol_out, "zh", "en")
            )
            out_xliff_docx = orf_out / "out_xliff.docx"
            out_md_docx = orf_out / "out_md.docx"
            out_md_epub = orf_out / "out_md.epub"
            out_md_html = orf_out / "out_md.html"
            _run_orf(transport, opp.skeleton_path, translated_xliff, out_xliff_docx,
                     "xliff", "docx", opp.images_json_path)
            _run_orf(transport, opp.skeleton_path, translated_md, out_md_docx,
                     "md", "docx")
            _run_orf(transport, opp.skeleton_path, translated_md, out_md_epub,
                     "md", "epub")
            _run_orf(transport, opp.skeleton_path, translated_md, out_md_html,
                     "md", "html")
            assert out_xliff_docx.exists() and out_xliff_docx.stat().st_size > 0
            assert out_md_docx.exists() and out_md_docx.stat().st_size > 0
            assert out_md_epub.exists() and out_md_epub.stat().st_size > 0
            assert out_md_html.exists() and out_md_html.stat().st_size > 0
            assert len(extract_image_positions(out_xliff_docx)) == 7
            assert out_md_docx.stat().st_size > 0
        else:
            pytest.fail(f"Unknown component: {component}")

    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_orf_xliff_pptx_cli(
        self, meridian_english_pptx_path, use_real_llm, artifact_dir,
    ):
        """Tier-1 ORF xliff→pptx smoke (CLI).

        Uses a real PPTX source fixture (Meridian_Q1_Update_E2E.pptx, 3 slides)
        because XLIFF2PPTXConverter needs a PPTX skeleton to populate the
        slide structure. The Haier DOCX fixture is unsuitable here — a
        DOCX passed to XLIFF2PPTXConverter produces a malformed PPTX
        with word/document.xml (DOCX structure) instead of
        ppt/presentation.xml.
        """
        opp = asyncio.run(
            _run_opp("cli", meridian_english_pptx_path, artifact_dir, "en", "zh")
        )
        ol_out = artifact_dir / "ol"
        orf_out = artifact_dir / "orf"
        orf_out.mkdir(parents=True, exist_ok=True)
        translated_xliff = asyncio.run(
            _run_ol("cli", opp.xliff_path, ol_out, "en", "zh")
        )
        out_pptx = orf_out / "out_pptx.pptx"
        _run_orf("cli", opp.skeleton_path, translated_xliff, out_pptx,
                 "xliff", "pptx")
        _assert_non_empty_file(out_pptx)
        with zipfile.ZipFile(out_pptx) as zf:
            names = zf.namelist()
            assert "ppt/presentation.xml" in names, (
                f"PPTX missing presentation.xml. Contents: {names[:10]}"
            )
            assert "ppt/slides/slide1.xml" in names, (
                f"PPTX missing slide1.xml. Contents: {names[:10]}"
            )


# ---------------------------------------------------------------------------
# Tier 2 — Sparse homogeneous E2E (4 tests)
# ---------------------------------------------------------------------------

class TestE2ERealLLME2E:
    """Sparse homogeneous E2E: 4 tests.

    Each runs the full OPP→OL→ORF pipeline via homogeneous transport
    (all-CLI or all-MCP) to produce a final DOCX, then asserts 7/7 unique
    images are preserved with paragraph_index within tolerance.

    Mixed-transport E2E (e.g., CLI×MCP×CLI) is not tested; each transport
    is a thin I/O adapter, and component isolation is covered by Tier 1.
    """

    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_e2e_xliff_all_cli(
        self, haier_real_docx_path, use_real_llm, artifact_dir,
    ):
        output, opp = asyncio.run(
            _run_e2e_chain("cli", haier_real_docx_path, artifact_dir, "xliff", "docx")
        )
        assert output.exists()
        _assert_image_positioning(output, opp.images_json_path, tolerance=2)

    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_e2e_xliff_all_mcp(
        self, haier_real_docx_path, use_real_llm, use_opp_mcp, artifact_dir,
    ):
        output, opp = asyncio.run(
            _run_e2e_chain("mcp", haier_real_docx_path, artifact_dir, "xliff", "docx")
        )
        assert output.exists()
        _assert_image_positioning(output, opp.images_json_path, tolerance=2)

    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_e2e_md_docx_all_cli(
        self, haier_real_docx_path, use_real_llm, use_opp_mcp, artifact_dir,
    ):
        _require_pandoc()
        output, _opp = asyncio.run(
            _run_e2e_chain("cli", haier_real_docx_path, artifact_dir, "md", "docx")
        )
        assert output.exists()
        assert output.stat().st_size > 0

    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_e2e_md_docx_all_mcp(
        self, haier_real_docx_path, use_real_llm, use_opp_mcp, artifact_dir,
    ):
        _require_pandoc()
        output, _opp = asyncio.run(
            _run_e2e_chain("mcp", haier_real_docx_path, artifact_dir, "md", "docx")
        )
        assert output.exists()
        assert output.stat().st_size > 0


# ---------------------------------------------------------------------------
# Tier 3 — LQA on final DOCX text (2 tests)
# ---------------------------------------------------------------------------

class TestE2ERealLLMLQA:
    """LQA on final DOCX text: 2 tests.

    Runs the full OPP→OL→ORF pipeline, then extracts text from the final
    DOCX and runs JudgeService. Asserts the 4-dim average (adequacy, fluency,
    terminology_consistency, format_preservation) is >= 5.0.

    Quality is judged on the FINAL DOCX text (the user-visible artifact),
    not on the intermediate XLIFF/MD — the previous Test 3 judged the
    XLIFF, which is a no-op for translation quality signal.
    """

    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_lqa_xliff_final_docx(
        self, haier_real_docx_path, use_real_llm, artifact_dir,
    ):
        output, _opp = asyncio.run(
            _run_e2e_chain("cli", haier_real_docx_path, artifact_dir, "xliff", "docx")
        )
        _assert_non_empty_file(output)
        judgment = asyncio.run(
            _judge_docx_text(output, haier_real_docx_path, "zh", "en")
        )
        translated_text = " ".join(
            text for _idx, text in _extract_docx_text(output) if text.strip()
        )
        _assert_translated_to_target_lang(translated_text, "en")
        threshold = 5.0
        assert judgment["avg_adequacy"] >= threshold, (
            f"adequacy={judgment['avg_adequacy']:.2f}"
        )
        assert judgment["avg_fluency"] >= threshold, (
            f"fluency={judgment['avg_fluency']:.2f}"
        )
        assert judgment["avg_terminology"] >= threshold, (
            f"terminology={judgment['avg_terminology']:.2f}"
        )
        assert judgment["avg_format"] >= threshold, (
            f"format={judgment['avg_format']:.2f}"
        )

    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_lqa_md_final_docx(
        self, haier_real_docx_path, use_real_llm, artifact_dir,
    ):
        output, _opp = asyncio.run(
            _run_e2e_chain("cli", haier_real_docx_path, artifact_dir, "md", "docx")
        )
        _assert_non_empty_file(output)
        judgment = asyncio.run(
            _judge_docx_text(output, haier_real_docx_path, "zh", "en")
        )
        translated_text = " ".join(
            text for _idx, text in _extract_docx_text(output) if text.strip()
        )
        _assert_translated_to_target_lang(translated_text, "en")
        threshold = 5.0
        assert judgment["avg_adequacy"] >= threshold, (
            f"adequacy={judgment['avg_adequacy']:.2f}"
        )
        assert judgment["avg_fluency"] >= threshold, (
            f"fluency={judgment['avg_fluency']:.2f}"
        )
        assert judgment["avg_terminology"] >= threshold, (
            f"terminology={judgment['avg_terminology']:.2f}"
        )
        assert judgment["avg_format"] >= threshold, (
            f"format={judgment['avg_format']:.2f}"
        )

    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_lqa_xliff_final_docx_mcp(
        self, haier_real_docx_path, use_real_llm, artifact_dir,
    ):
        output, _opp = asyncio.run(
            _run_e2e_chain("mcp", haier_real_docx_path, artifact_dir, "xliff", "docx")
        )
        _assert_non_empty_file(output)
        judgment = asyncio.run(
            _judge_docx_text(output, haier_real_docx_path, "zh", "en")
        )
        translated_text = " ".join(
            text for _idx, text in _extract_docx_text(output) if text.strip()
        )
        _assert_translated_to_target_lang(translated_text, "en")
        threshold = 5.0
        for dim in ("avg_adequacy", "avg_fluency", "avg_terminology", "avg_format"):
            assert judgment[dim] >= threshold, (
                f"MCP xliff→docx: {dim}={judgment[dim]:.2f} below {threshold}"
            )

    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_lqa_md_final_docx_mcp(
        self, haier_real_docx_path, use_real_llm, artifact_dir,
    ):
        output, _opp = asyncio.run(
            _run_e2e_chain("mcp", haier_real_docx_path, artifact_dir, "md", "docx")
        )
        _assert_non_empty_file(output)
        judgment = asyncio.run(
            _judge_docx_text(output, haier_real_docx_path, "zh", "en")
        )
        translated_text = " ".join(
            text for _idx, text in _extract_docx_text(output) if text.strip()
        )
        _assert_translated_to_target_lang(translated_text, "en")
        threshold = 5.0
        for dim in ("avg_adequacy", "avg_fluency", "avg_terminology", "avg_format"):
            assert judgment[dim] >= threshold, (
                f"MCP md→docx: {dim}={judgment[dim]:.2f} below {threshold}"
            )

    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_lqa_xliff_final_epub(
        self, haier_real_docx_path, use_real_llm, artifact_dir,
    ):
        _require_pandoc()
        output, _opp = asyncio.run(
            _run_e2e_chain("cli", haier_real_docx_path, artifact_dir, "xliff", "epub")
        )
        _assert_non_empty_file(output)
        translated_text = _extract_epub_text(output)
        _assert_translated_to_target_lang(translated_text, "en")
        threshold_chars = 200
        assert len(translated_text) >= threshold_chars, (
            f"EPUB body too short ({len(translated_text)} chars) — "
            f"translation likely failed silently. Sample: {translated_text[:200]!r}"
        )
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            assert "mimetype" in names, f"EPUB missing mimetype. Contents: {names[:10]}"
            assert any(n.endswith("content.opf") for n in names), (
                f"EPUB missing content.opf. Contents: {names[:10]}"
            )

    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_lqa_md_final_html(
        self, haier_real_docx_path, use_real_llm, artifact_dir,
    ):
        _require_pandoc()
        output, _opp = asyncio.run(
            _run_e2e_chain("cli", haier_real_docx_path, artifact_dir, "md", "html")
        )
        _assert_non_empty_file(output)
        translated_text = _extract_html_text(output)
        _assert_translated_to_target_lang(translated_text, "en")
        threshold_chars = 200
        assert len(translated_text) >= threshold_chars, (
            f"HTML body too short ({len(translated_text)} chars) — "
            f"translation likely failed silently. Sample: {translated_text[:200]!r}"
        )
        assert "<h1" in translated_text.lower() or "<h2" in translated_text.lower(), (
            "HTML output missing heading structure"
        )

    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_lqa_en_zh_xliff_final_docx(
        self, meridian_english_docx_path, use_real_llm, artifact_dir,
    ):
        """Tier-3 en→zh direction: OPP→OL→ORF CLI with xliff intermediate, docx target."""
        output, _opp = asyncio.run(
            _run_e2e_chain(
                "cli", meridian_english_docx_path, artifact_dir,
                "xliff", "docx", src_lang="en", tgt_lang="zh",
            )
        )
        _assert_non_empty_file(output)
        judgment = asyncio.run(
            _judge_docx_text(output, meridian_english_docx_path, "en", "zh")
        )
        translated_text = " ".join(
            text for _idx, text in _extract_docx_text(output) if text.strip()
        )
        _assert_translated_to_target_lang(translated_text, "zh")
        threshold = 5.0
        for dim in ("avg_adequacy", "avg_fluency", "avg_terminology", "avg_format"):
            assert judgment[dim] >= threshold, (
                f"en→zh xliff→docx: {dim}={judgment[dim]:.2f} below {threshold}"
            )

    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_lqa_en_zh_md_final_docx(
        self, meridian_english_docx_path, use_real_llm, artifact_dir,
    ):
        """Tier-3 en→zh direction: OPP→OL→ORF CLI with md intermediate, docx target."""
        output, _opp = asyncio.run(
            _run_e2e_chain(
                "cli", meridian_english_docx_path, artifact_dir,
                "md", "docx", src_lang="en", tgt_lang="zh",
            )
        )
        _assert_non_empty_file(output)
        judgment = asyncio.run(
            _judge_docx_text(output, meridian_english_docx_path, "en", "zh")
        )
        translated_text = " ".join(
            text for _idx, text in _extract_docx_text(output) if text.strip()
        )
        _assert_translated_to_target_lang(translated_text, "zh")
        threshold = 5.0
        for dim in ("avg_adequacy", "avg_fluency", "avg_terminology", "avg_format"):
            assert judgment[dim] >= threshold, (
                f"en→zh md→docx: {dim}={judgment[dim]:.2f} below {threshold}"
            )

    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_lqa_mixed_transport_cli_mcp_cli(
        self, haier_real_docx_path, use_real_llm, artifact_dir,
    ):
        """Tier-3 mixed transport: OPP CLI → OL MCP → ORF CLI with xliff, docx."""
        output, _opp = asyncio.run(
            _run_e2e_chain_mixed(
                "cli", "mcp", "cli",
                haier_real_docx_path, artifact_dir,
                "xliff", "docx", src_lang="zh", tgt_lang="en",
            )
        )
        _assert_non_empty_file(output)
        judgment = asyncio.run(
            _judge_docx_text(output, haier_real_docx_path, "zh", "en")
        )
        translated_text = " ".join(
            text for _idx, text in _extract_docx_text(output) if text.strip()
        )
        _assert_translated_to_target_lang(translated_text, "en")
        threshold = 5.0
        for dim in ("avg_adequacy", "avg_fluency", "avg_terminology", "avg_format"):
            assert judgment[dim] >= threshold, (
                f"mixed cli/mcp/cli: {dim}={judgment[dim]:.2f} below {threshold}"
            )

    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_lqa_mixed_transport_mcp_cli_mcp(
        self, haier_real_docx_path, use_real_llm, artifact_dir,
    ):
        """Tier-3 mixed transport: OPP MCP → OL CLI → ORF MCP with md, docx."""
        output, _opp = asyncio.run(
            _run_e2e_chain_mixed(
                "mcp", "cli", "mcp",
                haier_real_docx_path, artifact_dir,
                "md", "docx", src_lang="zh", tgt_lang="en",
            )
        )
        _assert_non_empty_file(output)
        judgment = asyncio.run(
            _judge_docx_text(output, haier_real_docx_path, "zh", "en")
        )
        translated_text = " ".join(
            text for _idx, text in _extract_docx_text(output) if text.strip()
        )
        _assert_translated_to_target_lang(translated_text, "en")
        threshold = 5.0
        for dim in ("avg_adequacy", "avg_fluency", "avg_terminology", "avg_format"):
            assert judgment[dim] >= threshold, (
                f"mixed mcp/cli/mcp: {dim}={judgment[dim]:.2f} below {threshold}"
            )

    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_lqa_en_zh_xliff_final_epub(
        self, meridian_english_docx_path, use_real_llm, artifact_dir,
    ):
        """Tier-3 en→zh direction: OPP→OL→ORF CLI with xliff intermediate, epub target."""
        _require_pandoc()
        output, _opp = asyncio.run(
            _run_e2e_chain(
                "cli", meridian_english_docx_path, artifact_dir,
                "xliff", "epub", src_lang="en", tgt_lang="zh",
            )
        )
        _assert_non_empty_file(output)
        translated_text = _extract_epub_text(output)
        _assert_translated_to_target_lang(translated_text, "zh")
        threshold_chars = 200
        assert len(translated_text) >= threshold_chars, (
            f"EPUB body too short ({len(translated_text)} chars) — "
            f"en→zh translation likely failed silently. Sample: {translated_text[:200]!r}"
        )
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            assert "mimetype" in names, f"EPUB missing mimetype. Contents: {names[:10]}"
            assert any(n.endswith("content.opf") for n in names), (
                f"EPUB missing content.opf. Contents: {names[:10]}"
            )


# ---------------------------------------------------------------------------
# Tier 4 — ORF format coverage (2 tests)
# ---------------------------------------------------------------------------

class TestE2ERealLLMFormats:
    """ORF format coverage: 2 tests.

    Runs the full pipeline ending in MD→EPUB and MD→HTML output formats.
    Verifies ORF's other output formats work end-to-end with real LLM
    translation. CLI transport only (MCP variants deferred to avoid
    doubling runtime; can be added if a mixed bug shows up).
    """

    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_e2e_md_epub_cli(
        self, haier_real_docx_path, use_real_llm, artifact_dir,
    ):
        _require_pandoc()
        output, _opp = asyncio.run(
            _run_e2e_chain("cli", haier_real_docx_path, artifact_dir, "md", "epub")
        )
        assert output.exists()
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            assert "mimetype" in names, (
                f"EPUB missing mimetype file. Contents: {names[:10]}"
            )
            assert zf.read("mimetype").decode("ascii") == "application/epub+zip", (
                f"EPUB mimetype must be application/epub+zip, "
                f"got {zf.read('mimetype').decode('ascii')!r}"
            )
            assert any(n.endswith("content.opf") for n in names), (
                f"EPUB missing content.opf. Contents: {names[:10]}"
            )

    @pytest.mark.requires_api_key
    @pytest.mark.nightly
    def test_e2e_md_html_cli(
        self, haier_real_docx_path, use_real_llm, artifact_dir,
    ):
        _require_pandoc()
        output, _opp = asyncio.run(
            _run_e2e_chain("cli", haier_real_docx_path, artifact_dir, "md", "html")
        )
        assert output.exists()
        html_text = output.read_text(encoding="utf-8", errors="replace")
        assert "<h1" in html_text.lower() or "<h2" in html_text.lower(), (
            "HTML output missing heading tags"
        )
        assert "loving haier" in html_text.lower(), (
            "HTML output missing expected translated content"
        )
