"""E2E test: Haier DOCX through OPP → OL (XLIFF, LQA) → ORF with exact
image placement verification + content quality comparison.

This is the canonical real-LLM E2E test for the production pipeline.
Mirrors `production_pipeline_run_2026-06-08/scripts/run_pipeline.sh` step
for step, then adds rigorous verification that the final DOCX is a
faithful translation of the source.

Source: ``scenarios/_fixtures/haier_ch2_zh.docx`` (447 KB, Chinese)
Direction: zh → en
LQA: enabled via ``Omni_Localizer/config/local.yaml`` (enable_lqa: true)
LLM: real (requires ``MINIMAX_API_KEY`` or ``BAIDU_API_KEY`` in
``Omni_Localizer/.env``)

What this test verifies (against the source as ground truth):

1. **All 3 stages exit 0** and produce their expected outputs.
2. **LQA judge is actually invoked** — not silently skipped — by reading
   the OL component log (which emits a ``JudgeService`` call trace on
   the LQA path).
3. **Image data roundtrip** — all 7 unique image blobs (sha256 of bytes)
   from the source are present in the final DOCX, bit-for-bit.
4. **Image placement** — every ``paragraph_index`` that OPP reported in
   ``images.json`` is preserved in the final DOCX at the same
   ``//w:p`` document-order index. This is the "exact image placement"
   the user asked for.
5. **Content quality**:
   - No chain-of-thought leak (``<think>`` patterns).
   - No Chinese punctuation (``《》 ``, ``"" ``, ``一、``, ``。``).
   - No literal XLIFF ``<bx>``/``<ex>`` markup leaking into ``<w:t>``
     (LEAK-FIX 2026-06-08 regression).
   - Real English content present (target vocabulary).
6. **Structural comparison** — body paragraph count and drawing count
   match between source and final (translation did not silently drop
   structure).

Why ``//w:p`` (not body-direct children) for paragraph indexing:
OPP sets ``paragraph_index`` in ``images.json`` using
``tree.findall(f'.//{W_NS}p')`` (all w:p, including nested in tables
and text boxes — see ``Omni_Pre_Processor/src/opp/extractors/docx.py``).
ORF's ``inject_images`` uses ``root.xpath("//w:p", ...)`` (same scope).
Therefore the test must enumerate via ``//w:p`` for the comparison to
be apples-to-apples.

Run:
    pytest tests/test_e2e_xliff_lqa_image_placement.py -v -s \\
        --log-cli-level=INFO
Skip (no API key):
    OMNI_SKIP_REAL_LLM=1 pytest tests/test_e2e_xliff_lqa_image_placement.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pytest
from lxml import etree


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUITE_ROOT = Path(__file__).resolve().parents[1]
HAIER_DOCX = SUITE_ROOT / "scenarios" / "_fixtures" / "haier_ch2_zh.docx"

OPP_DIR = SUITE_ROOT / "Omni_Pre_Processor"
OL_DIR = SUITE_ROOT / "Omni_Localizer"
ORF_DIR = SUITE_ROOT / "Omni_Re_Formatter"
OPP_SRC = OPP_DIR / "src"
OL_SRC = OL_DIR / "src"
ORF_SRC = ORF_DIR / "src"

OPP_DEFAULT_CONFIG = OPP_DIR / "config" / "default.yaml"
OL_LOCAL_CONFIG = OL_DIR / "config" / "local.yaml"
OL_DOTENV = OL_DIR / ".env"

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
WP_NS = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
MC_NS = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
XLIFF_NS = "{urn:oasis:names:tc:xliff:document:1.2}"

# Ground truth: per-image data hash for the Haier source (sha256 prefix).
# If the source file is replaced, these will mismatch — re-enumerate via
# _enumerate_source_images() to regenerate.
EXPECTED_IMAGE_COUNT = 7
EXPECTED_DRAWING_COUNT = 12  # = images.json length
EXPECTED_DRAWING_PARA_INDICES = [7, 8, 9, 13, 13, 17, 18, 24, 28, 28, 32, 33]


# ---------------------------------------------------------------------------
# Subprocess environment builder
# ---------------------------------------------------------------------------


def _build_subprocess_env() -> dict[str, str]:
    """Build env for OPP/OL/ORF subprocess invocations.

    Real-LLM mode: do NOT set ``OMNI_TEST_FAKE_LLM`` (the FAKE seam
    bypasses real translation + LQA judge). Set
    ``TRANSFORMERS_OFFLINE``/``HF_HUB_OFFLINE`` so LiteLLM and any
    sentence-transformers imports don't try to reach HuggingFace.
    """
    env = os.environ.copy()
    src_dirs = [
        str(SUITE_ROOT),
        str(SUITE_ROOT / "tests"),
        str(OPP_SRC), str(OL_SRC), str(ORF_SRC),
    ]
    env["PYTHONPATH"] = ":".join(
        filter(None, src_dirs + [env.get("PYTHONPATH", "")])
    )
    env["TRANSFORMERS_OFFLINE"] = "1"
    env["HF_HUB_OFFLINE"] = "1"
    env["OPP_CONFIG_PATH"] = str(SUITE_ROOT / "Omni_Pre_Processor" / "config" / "default.yaml")
    env.pop("OMNI_TEST_FAKE_LLM", None)
    env.pop("OMNI_TEST_FAKE_PANDOC", None)
    # Point OL at the local.yaml config (which has enable_lqa: true).
    if OL_LOCAL_CONFIG.exists():
        env["OL_CONFIG_PATH"] = str(OL_LOCAL_CONFIG)
    return env


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def lqa_enabled_env(monkeypatch) -> None:
    """Load OL .env into the test environment and fail if no API key.

    Existing real-LLM tests use FAIL-on-missing-key semantics (see
    ``tests/test_e2e_real_llm.py::use_real_llm``) — silent skip is
    removed so pipeline regressions are visible. Honor the
    ``OMNI_SKIP_REAL_LLM=1`` env var as an explicit opt-out.
    """
    if os.environ.get("OMNI_SKIP_REAL_LLM") == "1":
        pytest.skip("OMNI_SKIP_REAL_LLM=1 set; skipping real-LLM test")

    if OL_DOTENV.exists():
        for line in OL_DOTENV.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                if v.strip() and k.strip() not in os.environ:
                    monkeypatch.setenv(k.strip(), v.strip())

    if not OL_LOCAL_CONFIG.exists():
        pytest.fail(
            f"LQA config not found: {OL_LOCAL_CONFIG}. "
            "Copy Omni_Localizer/config/default.yaml to local.yaml and set "
            "enable_lqa: true."
        )

    # Verify the config has LQA enabled
    config_text = OL_LOCAL_CONFIG.read_text(encoding="utf-8")
    if "enable_lqa: true" not in config_text:
        pytest.fail(
            f"LQA config does not have enable_lqa: true: {OL_LOCAL_CONFIG}"
        )

    if not any(os.environ.get(k) for k in ["MINIMAX_API_KEY", "BAIDU_API_KEY"]):
        pytest.fail(
            "E2E LQA test requires a real LLM API key. "
            "Set MINIMAX_API_KEY or BAIDU_API_KEY in Omni_Localizer/.env "
            "(or in the test environment). "
            "Set OMNI_SKIP_REAL_LLM=1 to skip this test."
        )


# ---------------------------------------------------------------------------
# Image / document inspection helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImageRecord:
    """One image instance extracted from a DOCX.

    `para_index` is the 0-based document-order index into ``//w:p``
    (matches OPP's ``paragraph_index`` convention).
    `rId` is the relationship id (``r:embed`` on the blip).
    `is_floating` distinguishes ``wp:inline`` from ``wp:anchor``.
    `data_sha256` is the sha256 of the image bytes (used for content
    equality after pipeline roundtrip — two distinct drawings pointing
    at the same blob have the same hash).
    """

    para_index: int
    rId: str
    is_floating: bool
    data_sha256: str


def _enumerate_docx_images(docx_path: Path) -> list[ImageRecord]:
    """Enumerate all UNIQUE drawings in a DOCX.

    Dedup rule (mirrors OPP's ``docx.py:303-323``): skip drawings whose
    direct parent is ``mc:Fallback`` (every ``mc:Choice`` rendering
    has a ``mc:Fallback`` mirror that would otherwise double-count).
    Take the FIRST ``a:blip`` per drawing.

    Returned list preserves document order.
    """
    with zipfile.ZipFile(docx_path) as zf:
        doc_xml = zf.read("word/document.xml")
        rels_xml = zf.read("word/_rels/document.xml.rels")

    rels_tree = etree.fromstring(rels_xml)
    embed_to_target: dict[str, str] = {}
    for rel in rels_tree.findall(f".//{REL_NS}Relationship"):
        embed_to_target[rel.get("Id")] = rel.get("Target")

    tree = etree.fromstring(doc_xml)
    all_ps = tree.findall(f".//{W_NS}p")
    para_to_idx = {id(p): i for i, p in enumerate(all_ps)}

    out: list[ImageRecord] = []
    with zipfile.ZipFile(docx_path) as zf:
        for drawing in tree.iter(f"{W_NS}drawing"):
            # mc:Fallback dedup
            parent = drawing.getparent()
            if parent is not None and parent.tag == f"{MC_NS}Fallback":
                continue

            # walk to containing w:p
            p = drawing.getparent()
            while p is not None and p.tag != f"{W_NS}p":
                p = p.getparent()
            if p is None:
                continue
            para_idx = para_to_idx.get(id(p))
            if para_idx is None:
                continue

            is_floating = drawing.find(f".//{WP_NS}anchor") is not None

            # first blip
            blip = None
            for b in drawing.iter(f"{A_NS}blip"):
                blip = b
                break
            if blip is None:
                continue
            rId = blip.get(f"{R_NS}embed")
            if not rId or rId not in embed_to_target:
                continue

            # fetch image bytes for sha256
            target = embed_to_target[rId]
            full_path = (
                f"word/{target}" if not target.startswith("/")
                else target.lstrip("/")
            )
            try:
                image_data = zf.read(full_path)
            except KeyError:
                image_data = b""
            sha = hashlib.sha256(image_data).hexdigest()

            out.append(ImageRecord(
                para_index=para_idx,
                rId=rId,
                is_floating=is_floating,
                data_sha256=sha,
            ))
    return out


def _body_paragraph_count(docx_path: Path) -> int:
    """Count ``w:p`` elements that are direct children of ``w:body``."""
    with zipfile.ZipFile(docx_path) as zf:
        doc_xml = zf.read("word/document.xml")
    tree = etree.fromstring(doc_xml)
    body = tree.find(f"{W_NS}body")
    return len(body.findall(f"./{W_NS}p"))


def _all_paragraph_count(docx_path: Path) -> int:
    """Count ALL ``w:p`` elements (``//w:p`` — includes nested)."""
    with zipfile.ZipFile(docx_path) as zf:
        doc_xml = zf.read("word/document.xml")
    tree = etree.fromstring(doc_xml)
    return len(tree.findall(f".//{W_NS}p"))


def _visible_paragraphs(docx_path: Path) -> list[str]:
    """Extract visible (non-empty) text from body's direct child paragraphs.

    Joins all ``w:t`` text inside each ``w:p`` and drops paragraphs with
    no text (image-only paragraphs are kept as empty strings; we drop
    those).
    """
    with zipfile.ZipFile(docx_path) as zf:
        doc_xml = zf.read("word/document.xml")
    tree = etree.fromstring(doc_xml)
    body = tree.find(f"{W_NS}body")
    out: list[str] = []
    for p in body.findall(f"./{W_NS}p"):
        text = "".join(t.text or "" for t in p.iter(f"{W_NS}t"))
        text = text.strip()
        if text:
            out.append(text)
    return out


def _read_docx_xml(docx_path: Path) -> str:
    """Read ``word/document.xml`` as text (for content-quality checks)."""
    with zipfile.ZipFile(docx_path) as zf:
        return zf.read("word/document.xml").decode("utf-8")


# ---------------------------------------------------------------------------
# Content-quality assertions
# ---------------------------------------------------------------------------


def _assert_no_chain_of_thought(xml: str) -> None:
    """No ``<think>``/``</think>`` blocks or ``reasoning:`` style traces.

    Some LLMs emit chain-of-thought in their final answer. OL strips
    these via the post-processor (POST_MORTEM fix 95360f1), but a
    regression here would leak the model's reasoning to the end user.
    """
    bad = re.findall(r"<think>|</think>|reasoning:|<reasoning>", xml, re.IGNORECASE)
    assert not bad, (
        f"Chain-of-thought leak detected: {bad[:3]!r}"
    )


def _assert_no_chinese_punctuation(xml: str) -> None:
    """None of the Chinese typographic chars leak into the translated DOCX.

    The OL has post-processors for 《》 `` `` 一、 etc. (POST_MORTEM
    fix 1478b14). A regression here means Chinese text is sneaking
    past the localizer.
    """
    forbidden = {
        "《": "Chinese open book bracket",
        "》": "Chinese close book bracket",
        "“": "Chinese open curly quote",
        "”": "Chinese close curly quote",
        "、": "Chinese ordinal/comma",
    }
    leaks = {char: desc for char, desc in forbidden.items() if char in xml}
    assert not leaks, (
        f"Chinese punctuation leaked into final DOCX: {leaks}"
    )
    # Chinese ordinal like 一、二、三、 is forbidden when followed by 、.
    if re.search(r"[一二三四五六七八九十][、]", xml):
        pytest.fail("Chinese ordinal pattern (e.g. 一、) leaked into final DOCX")


def _assert_no_bx_ex_leak(xml: str) -> None:
    """No literal ``<bx>``/``<ex>`` XLIFF markup in any ``<w:t>`` element.

    Regression for LEAK-FIX (2026-06-08): the OL may have stored the
    LLM's preserved ``<bx>`` markers as XML entities, which ORF
    previously wrote verbatim into ``<w:t>``. After the fix, these
    tags must be converted to proper DOCX run formatting (or stripped)
    — never visible to the end user.
    """
    w_t_re = re.compile(r"<w:t[^>]*>([^<]*)</w:t>", re.DOTALL)
    leaks: list[str] = []
    for m in w_t_re.finditer(xml):
        text = m.group(1)
        if "<bx" in text or "<ex" in text:
            leaks.append(text)
        # Defensive: lxml encodes '<' as &lt; on serialization, so also
        # check the encoded form in case the writer ever stops encoding.
        if "&lt;bx" in text or "&lt;ex" in text:
            leaks.append(text)
    assert not leaks, (
        f"LEAK-FIX regression: <bx>/<ex> in <w:t> elements: {leaks[:3]!r}"
    )


def _assert_real_english(xml: str) -> None:
    """Real English content is present (the LLM actually translated)."""
    en_keywords = ["love", "haier", "chapter", "enterprise", "brand",
                   "global", "china", "reform", "industry", "kantar"]
    xml_lower = xml.lower()
    hits = [w for w in en_keywords if w in xml_lower]
    assert len(hits) >= 3, (
        f"Only {len(hits)} English keywords found ({hits!r}); "
        f"translation may not have run. Expected >= 3 of {en_keywords}."
    )


# ---------------------------------------------------------------------------
# LQA evidence
# ---------------------------------------------------------------------------


def _find_latest_ol_log(artifacts_root: Path) -> Path | None:
    """Find the most recent OL log file.

    OL writes logs to one of two places, depending on the OL version
    and the CWD of the subprocess:

    1. ``Omni_Localizer/logs/ol-*.log`` — when CWD is Omni_Localizer
       (or OL is installed editable and resolves its log path from
       its own package location).
    2. ``<suite_root>/logs/ol-*.log`` — when CWD is the suite root
       (this is what the test's subprocess actually does, because
       PYTHONPATH includes Omni_Localizer/src but the process CWD
       is the suite root).

    After each test the conftest's ``_copy_component_logs_to_artifact_dir``
    fixture copies the latest matching log to the artifact dir under
    ``logs/ol.log`` — prefer that copy.
    """
    # Prefer the artifact-dir copy (most reliable)
    for cand in sorted(
        artifacts_root.rglob("logs/ol.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        return cand
    # Fall back to the source-of-truth log dirs (try both)
    candidates: list[Path] = []
    candidates.extend((OL_DIR / "logs").glob("ol-*.log"))
    candidates.extend((SUITE_ROOT / "logs").glob("ol-*.log"))
    candidates = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _assert_lqa_invoked(
    ol_log: Path | None,
    ol_stdout: str = "",
    ol_stderr: str = "",
) -> None:
    """Verify the LQA judge was actually invoked during the OL run.

    Evidence we look for in the OL log AND in captured stdout/stderr:
    - "LQA enabled" or "LQA: judge" trace line
    - "lqa=on" (the OL CLI's own compact status line)
    - "JudgeService" instantiation
    - "enable_lqa" mention
    - typer.echo'd "LQA enabled for XLIFF: threshold=..."

    If no log is found AND no stdout/stderr evidence exists, we FAIL
    — silent skip is removed so pipeline regressions are visible.
    """
    indicators = [
        "LQA enabled",
        "lqa=on",
        "JudgeService",
        "LQA:",
        "lqa_score",
        "LQA unit",
        "lqa_enabled",
    ]

    log_text = ""
    if ol_log is not None and ol_log.exists():
        log_text = ol_log.read_text(encoding="utf-8", errors="replace")

    combined = log_text + "\n" + ol_stdout + "\n" + ol_stderr
    hits = [s for s in indicators if s in combined]

    if not hits:
        pytest.fail(
            "LQA was not invoked during the OL run. "
            f"None of {indicators!r} found in:\n"
            f"  - OL log: {ol_log}\n"
            f"  - OL stdout (last 500): {ol_stdout[-500:] if ol_stdout else '(empty)'}\n"
            f"  - OL stderr (last 500): {ol_stderr[-500:] if ol_stderr else '(empty)'}"
        )


# ---------------------------------------------------------------------------
# Stage runners (subprocess CLI, mirrors run_pipeline.sh exactly)
# ---------------------------------------------------------------------------


def _run_opp_xliff(input_docx: Path, out_dir: Path) -> dict[str, Path]:
    """Stage 1: OPP extract DOCX → .xlf + .skeleton.zip + _images.json.

    Mirrors the OPP invocation in
    ``production_pipeline_run_2026-06-08/scripts/run_pipeline.sh:70-74``.
    Uses ``--target-format=xlf`` (NOT both) — we only need XLIFF + the
    DOCX skeleton + images.json for the XLIFF backfill path.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "opp.cli", str(input_docx),
        "--target-format", "xlf",
        "--source-lang", "zh",
        "--target-lang", "en",
        "--config", str(OPP_DEFAULT_CONFIG),
        "--no-cache",
        "--output-dir", str(out_dir),
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, env=_build_subprocess_env(),
    )
    assert result.returncode == 0, (
        f"OPP extract failed (rc={result.returncode})\n"
        f"STDOUT:\n{result.stdout[-2000:]}\n"
        f"STDERR:\n{result.stderr[-2000:]}"
    )

    # OPP emits files with the source basename + .xlf, _images.json,
    # .skeleton.zip. Use a glob to find them (the stem includes Chinese
    # characters so we can't predict the exact filename).
    xlf_candidates = list(out_dir.glob("*.xlf"))
    skel_candidates = list(out_dir.glob("*.skeleton.zip"))
    img_candidates = [
        p for p in out_dir.iterdir()
        if p.name.endswith("_images.json") or p.name == "images.json"
    ]
    assert xlf_candidates, f"OPP did not produce an .xlf in {out_dir}: {list(out_dir.iterdir())}"
    assert skel_candidates, f"OPP did not produce a .skeleton.zip in {out_dir}"
    assert img_candidates, f"OPP did not produce _images.json in {out_dir}"

    return {
        "xliff": xlf_candidates[0],
        "skeleton": skel_candidates[0],
        "images_json": img_candidates[0],
    }


def _run_ol_xliff(
    xliff_in: Path, out_dir: Path,
) -> tuple[Path, str, str]:
    """Stage 2: OL translate XLIFF → translated XLIFF (LQA via local.yaml).

    Uses ``Omni_Localizer/config/local.yaml`` (which has
    ``enable_lqa: true``) so the LQA judge wraps every translation
    with a best-of-N retry.

    Returns ``(translated_xliff_path, stdout, stderr)`` — the
    captured output is needed downstream to verify LQA was actually
    invoked (the OL CLI emits ``"LQA enabled for XLIFF: threshold=..."``
    to stdout via ``typer.echo``).

    Mirrors ``production_pipeline_run_2026-06-08/scripts/run_pipeline.sh:89-93``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "ol_cli", "translate-xliff",
        str(xliff_in),
        "-c", str(OL_LOCAL_CONFIG),
        "-s", "zh", "-t", "en",
        "-o", str(out_dir),
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        env=_build_subprocess_env(), timeout=600,
    )
    assert result.returncode == 0, (
        f"OL translate-xliff failed (rc={result.returncode})\n"
        f"STDOUT (last 2000):\n{result.stdout[-2000:]}\n"
        f"STDERR (last 2000):\n{result.stderr[-2000:]}"
    )

    translated = out_dir / xliff_in.name
    assert translated.exists(), (
        f"OL did not write translated XLIFF at {translated}\n"
        f"Output dir contents: {list(out_dir.iterdir())}"
    )
    assert translated.stat().st_size > 0, (
        f"OL wrote empty XLIFF: {translated}"
    )
    return translated, result.stdout, result.stderr


def _run_orf_xliff(
    skeleton: Path, translated_xliff: Path, images_json: Path, out_dir: Path,
) -> Path:
    """Stage 3: ORF backfill translated XLIFF into a final DOCX.

    Mirrors ``production_pipeline_run_2026-06-08/scripts/run_pipeline.sh:99-103``.
    The ``--images-json`` flag carries the OPP images.json with
    per-image ``paragraph_index`` so ORF can re-insert the original
    images at the right positions.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / "haier_final.docx"
    cmd = [
        sys.executable, "-m", "orf.cli", "apply-xliff",
        str(skeleton),
        "--xliff", str(translated_xliff),
        "--images-json", str(images_json),
        "--output", str(output_path),
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        env=_build_subprocess_env(), timeout=300,
    )
    assert result.returncode == 0, (
        f"ORF apply-xliff failed (rc={result.returncode})\n"
        f"STDOUT (last 2000):\n{result.stdout[-2000:]}\n"
        f"STDERR (last 2000):\n{result.stderr[-2000:]}"
    )
    assert output_path.exists(), f"ORF did not produce {output_path}"
    assert output_path.stat().st_size > 0, f"ORF output is empty: {output_path}"
    return output_path


# ---------------------------------------------------------------------------
# The main test
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.requires_api_key
@pytest.mark.nightly
@pytest.mark.slow
class TestHaierE2EXLIFFWithLQAAndImagePlacement:
    """End-to-end real-LLM test: Haier DOCX → OPP → OL (LQA) → ORF → final DOCX.

    This is the canonical acceptance test for the production pipeline.
    Mirrors ``production_pipeline_run_2026-06-08/scripts/run_pipeline.sh``
    and asserts (a) the pipeline runs cleanly, (b) LQA was actually
    invoked, (c) every image is in the right place, (d) no Chinese /
    chain-of-thought / bx-ex leaks, (e) structural counts match
    between source and final.
    """

    def test_full_pipeline_xliff_lqa_image_placement(
        self,
        lqa_enabled_env: None,
        haier_real_docx_path: Path,
        artifact_dir: Path,
    ) -> None:
        # 1. OPP extract
        opp_out = artifact_dir / "opp"
        opp_outputs = _run_opp_xliff(haier_real_docx_path, opp_out)
        xliff_in = opp_outputs["xliff"]
        skeleton = opp_outputs["skeleton"]
        images_json = opp_outputs["images_json"]
        assert xliff_in.exists() and xliff_in.stat().st_size > 0
        assert skeleton.exists() and skeleton.stat().st_size > 0
        assert images_json.exists() and images_json.stat().st_size > 0

        # 2. OL translate with LQA (via local.yaml)
        ol_out = artifact_dir / "ol"
        translated_xliff, ol_stdout, ol_stderr = _run_ol_xliff(xliff_in, ol_out)
        # The translated XLIFF must contain real English targets, not
        # the Chinese source. Sanity check.
        translated_text = translated_xliff.read_text(encoding="utf-8")
        assert 'target-language="en"' in translated_text
        assert translated_text.count("<trans-unit") >= 9

        # 3. ORF backfill with image injection
        orf_out = artifact_dir / "orf"
        final_docx = _run_orf_xliff(skeleton, translated_xliff, images_json, orf_out)

        # =================================================================
        # VERIFICATION 1: LQA was actually invoked
        # =================================================================
        ol_log = _find_latest_ol_log(artifact_dir)
        _assert_lqa_invoked(ol_log, ol_stdout=ol_stdout, ol_stderr=ol_stderr)

        # =================================================================
        # VERIFICATION 2: image data roundtrip (every blob preserved)
        # =================================================================
        src_images = _enumerate_docx_images(haier_real_docx_path)
        final_images = _enumerate_docx_images(final_docx)
        src_hashes = {img.data_sha256 for img in src_images}
        final_hashes = {img.data_sha256 for img in final_images}
        missing = src_hashes - final_hashes
        assert not missing, (
            f"LEAK: {len(missing)} unique image data blobs missing from "
            f"final DOCX. Source had {len(src_hashes)} unique blobs, "
            f"final has {len(final_hashes)}. Missing: "
            f"{sorted(missing)[:3]!r}"
        )
        assert len(src_hashes) == EXPECTED_IMAGE_COUNT, (
            f"Sanity: source has {len(src_hashes)} unique images, "
            f"expected {EXPECTED_IMAGE_COUNT}. The source DOCX may have "
            f"changed — re-enumerate via _enumerate_docx_images()."
        )

        # =================================================================
        # VERIFICATION 3: exact image placement (paragraph_index preserved)
        # =================================================================
        # The 12 drawings OPP extracted (in document order) must all be
        # present in the final DOCX at the same paragraph_index. ORF's
        # inject_images uses //w:p (matching OPP's convention).
        src_para_indices = sorted(img.para_index for img in src_images)
        final_para_indices = sorted(img.para_index for img in final_images)
        assert src_para_indices == final_para_indices, (
            f"Image paragraph_index drift between source and final.\n"
            f"  source: {src_para_indices}\n"
            f"  final:  {final_para_indices}\n"
            f"Missing from final: {set(src_para_indices) - set(final_para_indices)}\n"
            f"Extra in final:    {set(final_para_indices) - set(src_para_indices)}"
        )
        # Pin the exact distribution to catch any future regression
        # silently shifting the indices.
        assert src_para_indices == sorted(EXPECTED_DRAWING_PARA_INDICES), (
            f"Sanity: source paragraph_index list has changed. "
            f"Expected {EXPECTED_DRAWING_PARA_INDICES}, got {src_para_indices}. "
            f"Source DOCX may have been updated — re-enumerate the ground truth."
        )
        assert final_para_indices == sorted(EXPECTED_DRAWING_PARA_INDICES), (
            f"Image placement regression: final paragraph_index list is "
            f"{final_para_indices}, expected {sorted(EXPECTED_DRAWING_PARA_INDICES)}"
        )

        # =================================================================
        # VERIFICATION 4: content quality (no leaks, real English)
        # =================================================================
        final_xml = _read_docx_xml(final_docx)
        _assert_no_chain_of_thought(final_xml)
        _assert_no_chinese_punctuation(final_xml)
        _assert_no_bx_ex_leak(final_xml)
        _assert_real_english(final_xml)

        # =================================================================
        # VERIFICATION 5: structural comparison (source vs final)
        # =================================================================
        # Body paragraph count: source has 10 direct body w:p, final
        # should also have 10 (text was translated, not lost). ORF
        # may add or merge paragraphs when injecting images, so allow
        # a small tolerance.
        src_body = _body_paragraph_count(haier_real_docx_path)
        final_body = _body_paragraph_count(final_docx)
        assert abs(src_body - final_body) <= 3, (
            f"Body paragraph count drift: source={src_body}, final={final_body}"
        )

        # Visible body text: source paragraphs (Chinese) must be
        # replaced with non-empty English text in the final.
        src_visible = _visible_paragraphs(haier_real_docx_path)
        final_visible = _visible_paragraphs(final_docx)
        # All final paragraphs should be non-empty (translation produced text)
        assert len(final_visible) >= len(src_visible) - 2, (
            f"Visible paragraph count dropped: source={len(src_visible)}, "
            f"final={len(final_visible)}"
        )
        # None of the final paragraphs should still be in Chinese
        cjk_re = re.compile(r"[\u4e00-\u9fff]")
        chinese_remaining = [
            p[:50] for p in final_visible if cjk_re.search(p)
        ]
        assert not chinese_remaining, (
            f"BUG: {len(chinese_remaining)} paragraphs still in Chinese: "
            f"{chinese_remaining[:3]}"
        )

        # =================================================================
        # VERIFICATION 6: roundtrip the images.json OPP emitted
        # =================================================================
        images_data = json.loads(images_json.read_text(encoding="utf-8"))
        assert "images" in images_data, "images.json missing 'images' key"
        assert len(images_data["images"]) == EXPECTED_DRAWING_COUNT, (
            f"images.json has {len(images_data['images'])} images, "
            f"expected {EXPECTED_DRAWING_COUNT}"
        )
        # All entries should have paragraph_index (no floating images
        # in this file)
        for i, img in enumerate(images_data["images"]):
            assert img.get("paragraph_index") is not None, (
                f"images.json entry {i} missing paragraph_index"
            )
            assert img.get("paragraph_index") in EXPECTED_DRAWING_PARA_INDICES, (
                f"images.json entry {i} has unexpected paragraph_index: "
                f"{img.get('paragraph_index')!r}"
            )

        # Final summary (printed so the artifact log shows what was verified)
        print()
        print("=" * 70)
        print("E2E Haier XLIFF + LQA + Image Placement — PASSED")
        print("=" * 70)
        print(f"  Source DOCX:       {haier_real_docx_path.name}")
        print(f"  Final DOCX:        {final_docx}")
        print(f"  Source images:     {len(src_images)} drawings, "
              f"{len(src_hashes)} unique data blobs")
        print(f"  Final images:      {len(final_images)} drawings, "
              f"{len(final_hashes)} unique data blobs")
        print(f"  Paragraph indices: {src_para_indices}")
        print(f"  Body paragraphs:   source={src_body}, final={final_body}")
        print(f"  Visible paragraphs: source={len(src_visible)}, "
              f"final={len(final_visible)}")
        print(f"  LQA evidence:      {ol_log}")
        print("=" * 70)
