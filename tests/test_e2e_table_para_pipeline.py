"""OPP#80 Wave 3: the REAL 3-stage pipeline for per-paragraph table-cell units.

This is the first test anywhere that takes a ``table_{t}_r{r}_c{c}_para{p}``
resname through the **real** OPP → OL → ORF chain end to end. OL has no
``resname`` awareness at all: it preserves the attribute only because
``ol_buses/xliff_bus.py:write_target_back`` regex-substitutes the ``<target>``
content keyed by ``trans-unit`` id — exactly the kind of implicit coupling that
silently breaks. This test locks it.

The chain, per the suite's existing real-chain convention
(``tests/test_e2e_path_xliff_cli.py``):

1. **OPP** (in-process ``OPPPipeline``) extracts a table cell with three real
   paragraphs, with ``OPP_TABLE_PARAGRAPH_UNITS=1``, and emits one
   ``_para{p}`` trans-unit per paragraph plus a ``skeleton.zip``.
2. **OL** (shipped CLI, subprocess) translates the XLIFF through the
   ``OMNI_TEST_FAKE_LLM`` seam. The fake pool returns ``[<tgt>] <source>``
   per trans-unit, so every unit really does get its OWN target — the test is
   hermetic and deterministic AND exercises per-unit translation.
3. **ORF** (shipped CLI, subprocess) backfills the translated XLIFF into the
   skeleton.

Core assertion: every ``resname`` is byte-identical before and after OL. Then
the output document must hold three SEPARATE paragraphs with three SEPARATE
targets (not one joined blob).

Hermetic: no network, no real keys, ``tmp_path`` only. Marked ``e2e`` +
``real_chain`` (not ``nightly``) so it runs in the normal suite.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.real_chain]

_SUITE_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIRS = (
    _SUITE_ROOT / "Omni_Pre_Processor" / "src",
    _SUITE_ROOT / "Omni_Localizer" / "src",
    _SUITE_ROOT / "Omni_Re_Formatter" / "src",
)
_OL_CONFIG = _SUITE_ROOT / "Omni_Localizer" / "config" / "default.yaml"

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"

# The three raw paragraph texts every fixture cell carries. Distinctive so a
# misplaced target cannot accidentally satisfy the assertions.
PARA_TEXTS = ("Alpha-cell-0", "Beta-cell-1", "Gamma-cell-2")
RESNAME_PREFIX = "table_0_r0_c0"


def _paragraphs_env() -> dict:
    """Subprocess env: PYTHONPATH for all 3 modules + the fake seams.

    ``OS_TABLE...`` is copied from the parent (monkeypatched by the test), and
    the dummy API keys come from ``tests/conftest.py``'s ``setdefault`` — OL's
    CLI precheck only requires a non-empty provider key, and the fake pool
    never dials out.
    """
    env = os.environ.copy()
    parts = [str(d) for d in _SRC_DIRS if d.exists()]
    existing = env.get("PYTHONPATH", "")
    if existing:
        parts.append(existing)
    env["PYTHONPATH"] = ":".join(parts)
    env["OMNI_TEST_FAKE_LLM"] = "1"
    env["OMNI_TEST_FAKE_PANDOC"] = "1"
    return env


def _resname_tokens(xliff_path: Path) -> list[bytes]:
    """The raw ``resname="..."`` values, in document order, as bytes."""
    return re.findall(rb'resname="([^"]+)"', xliff_path.read_bytes())


def _build_docx_cell(path: Path) -> None:
    from docx import Document

    doc = Document()
    table = doc.add_table(rows=1, cols=1)
    cell = table.rows[0].cells[0]
    cell.text = PARA_TEXTS[0]
    for text in PARA_TEXTS[1:]:
        cell.add_paragraph(text)
    doc.save(str(path))


def _build_pptx_cell(path: Path) -> None:
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank layout
    frame = slide.shapes.add_table(1, 1, Inches(1), Inches(1), Inches(4), Inches(2))
    text_frame = frame.table.cell(0, 0).text_frame
    text_frame.text = PARA_TEXTS[0]
    for text in PARA_TEXTS[1:]:
        text_frame.add_paragraph().text = text
    prs.save(str(path))


def _run_ol(xliff_path: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            sys.executable, "-m", "ol_cli", "translate-xliff",
            str(xliff_path), "-o", str(out_dir),
            "-c", str(_OL_CONFIG), "--no-cache", "-s", "en", "-t", "zh",
        ],
        capture_output=True, text=True, env=_paragraphs_env(), timeout=180,
    )
    assert result.returncode == 0, (
        f"OL CLI failed (rc={result.returncode})\n"
        f"stdout tail: {result.stdout[-2000:]}\n"
        f"stderr tail: {result.stderr[-2000:]}"
    )
    translated = out_dir / xliff_path.name
    assert translated.exists(), f"OL did not produce {translated}"
    return translated


def _run_orf(skeleton_path: Path, xliff_path: Path, output_path: Path, fmt: str) -> None:
    result = subprocess.run(
        [
            sys.executable, "-m", "orf.cli", "apply-xliff", str(skeleton_path),
            "--xliff", str(xliff_path), "--output", str(output_path),
            "--format", fmt,
        ],
        capture_output=True, text=True, env=_paragraphs_env(), timeout=180,
    )
    assert result.returncode == 0, (
        f"ORF CLI failed (rc={result.returncode})\n"
        f"stdout tail: {result.stdout[-2000:]}\n"
        f"stderr tail: {result.stderr[-2000:]}"
    )
    assert output_path.exists(), f"ORF did not produce {output_path}"


def _docx_cell_paragraphs(path: Path) -> list[str]:
    """Direct ``w:p`` texts of the first table cell, read from the raw XML."""
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    cell = next(root.iter(f"{W_NS}tc"))
    return [
        "".join(t.text or "" for t in p.iter(f"{W_NS}t"))
        for p in cell.findall(f"{W_NS}p")
    ]


def _pptx_cell_paragraphs(path: Path) -> list[str]:
    """Direct ``a:p`` texts of the first table cell, read from the raw slide XML."""
    with zipfile.ZipFile(path) as zf:
        slides = sorted(
            name for name in zf.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        )
        assert slides, "output PPTX has no slide parts"
        for name in slides:
            root = ET.fromstring(zf.read(name))
            table = next(root.iter(f"{A_NS}tbl"), None)
            if table is None:
                continue
            cell = next(table.iter(f"{A_NS}tc"))
            return [
                "".join(t.text or "" for t in p.iter(f"{A_NS}t"))
                for p in cell.iter(f"{A_NS}p")
            ]
    raise AssertionError("output PPTX has no table")


def _run_pipeline(opp_pipeline, source_path: Path, tmp_path: Path, fmt: str) -> dict:
    """Run OPP → OL → ORF for one table-cell fixture and assert the contract.

    Returns the observed evidence (resnames before/after, final paragraph
    texts) so the caller can surface it.
    """
    stem = source_path.stem
    opp_out = tmp_path / "opp"
    opp_out.mkdir(parents=True, exist_ok=True)

    result = opp_pipeline.process_file(source_path)
    assert result.extraction_result is not None, result.errors
    xliff_path = opp_out / f"{stem}.xlf"
    opp_pipeline.generate_xliff(
        result.extraction_result, xliff_path, source_lang="en", target_lang="zh"
    )
    skeleton_path = opp_pipeline.save_skeleton(result.extraction_result, stem, opp_out)
    assert skeleton_path is not None and skeleton_path.exists(), "no skeleton.zip"

    # (1) OPP emitted one _para{p} unit per raw paragraph, indices 0..2.
    before = _resname_tokens(xliff_path)
    expected = [f"{RESNAME_PREFIX}_para{i}".encode() for i in range(len(PARA_TEXTS))]
    assert before == expected, f"OPP resnames: {[b.decode() for b in before]}"

    # (2) REAL OL translation over the XLIFF.
    translated_xliff = _run_ol(xliff_path, tmp_path / "ol")

    # (3) CORE: resnames byte-identical across OL.
    after = _resname_tokens(translated_xliff)
    assert after == before, (
        "OL mutated the table-cell resnames\n"
        f"before: {[b.decode() for b in before]}\n"
        f"after:  {[b.decode() for b in after]}"
    )

    # OL really produced a distinct target per paragraph (otherwise the final
    # document assertion below could pass for the wrong reason).
    targets = re.findall(rb"<target[^>]*>([^<]*)</target>", translated_xliff.read_bytes())
    trans_targets = [t for t in targets if b"[zh]" in t]
    assert len(trans_targets) == len(PARA_TEXTS), (
        f"expected one fake target per paragraph, got {trans_targets!r}"
    )

    # (4) REAL ORF backfill into the skeleton.
    output_path = tmp_path / "orf" / f"result.{fmt}"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _run_orf(skeleton_path, translated_xliff, output_path, fmt)

    paragraphs = (
        _docx_cell_paragraphs(output_path)
        if fmt == "docx"
        else _pptx_cell_paragraphs(output_path)
    )
    evidence = {
        "resnames_before": [b.decode() for b in before],
        "resnames_after": [b.decode() for b in after],
        "targets": [t.decode() for t in trans_targets],
        "paragraphs": paragraphs,
    }
    # Surfaced under `pytest -rA` / `-s` as the resname-before/after evidence.
    print(
        f"\n[table-para/{fmt}] resnames BEFORE OL: {evidence['resnames_before']}\n"
        f"[table-para/{fmt}] resnames AFTER  OL: {evidence['resnames_after']}\n"
        f"[table-para/{fmt}] per-unit targets:   {evidence['targets']}\n"
        f"[table-para/{fmt}] final paragraphs:   {evidence['paragraphs']}"
    )
    return evidence


class TestTableParagraphUnitsPipeline:
    def test_docx_three_paragraph_cell_survives_real_pipeline(
        self, opp_pipeline, tmp_path: Path, monkeypatch
    ):
        monkeypatch.setenv("OPP_TABLE_PARAGRAPH_UNITS", "1")
        source = tmp_path / "docx_cell.docx"
        _build_docx_cell(source)

        evidence = _run_pipeline(opp_pipeline, source, tmp_path, "docx")

        assert evidence["paragraphs"] == [f"[zh] {t}" for t in PARA_TEXTS], evidence

    def test_pptx_three_paragraph_cell_survives_real_pipeline(
        self, opp_pipeline, tmp_path: Path, monkeypatch
    ):
        monkeypatch.setenv("OPP_TABLE_PARAGRAPH_UNITS", "1")
        source = tmp_path / "pptx_cell.pptx"
        _build_pptx_cell(source)

        evidence = _run_pipeline(opp_pipeline, source, tmp_path, "pptx")

        assert evidence["paragraphs"] == [f"[zh] {t}" for t in PARA_TEXTS], evidence
