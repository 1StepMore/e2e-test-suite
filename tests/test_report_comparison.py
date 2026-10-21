"""Tests for scripts/report_comparison.py (E2E content gates)."""

from __future__ import annotations

import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

SUITE = Path(__file__).resolve().parents[1]
SCRIPT = SUITE / "scripts" / "report_comparison.py"
BASE_RUN = SUITE / "test-output" / "Full-Standard-20260601-230852"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

pytestmark = pytest.mark.skipif(not (BASE_RUN / "source.docx").exists(), reason="base run 缺失")


def _copy_run(tmp_path: Path) -> Path:
    destination = tmp_path / BASE_RUN.name
    shutil.copytree(BASE_RUN, destination)
    return destination


def _run_report(run_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(run_dir),
            "--suite",
            str(SUITE),
            "--path",
            "A",
        ],
        capture_output=True,
        text=True,
    )


def _definition(top: ET.Element) -> list[ET.Element]:
    return top.findall(".//" + W + "t")


def _paragraph_text(paragraph: ET.Element) -> str:
    return "".join(node.text or "" for node in _definition(paragraph))


def _top_paragraphs(root: ET.Element) -> list[ET.Element]:
    body = root.find(W + "body")
    if body is None:
        return []
    return [child for child in body if child.tag == W + "p"]


def _docx_xml(path: Path) -> ET.Element:
    with zipfile.ZipFile(path) as archive:
        return ET.fromstring(archive.read("word/document.xml"))


def edit_docx(path: Path, mutate_fn) -> None:
    with zipfile.ZipFile(path) as archive:
        items = [(info, archive.read(info.filename)) for info in archive.infolist()]

    with zipfile.ZipFile(path, "w") as archive:
        for info, data in items:
            if info.filename == "word/document.xml":
                data = mutate_fn(data)
            archive.writestr(info, data)


def test_clean_sample_passes(tmp_path: Path) -> None:
    run_dir = _copy_run(tmp_path)
    completed = _run_report(run_dir)
    report = (run_dir / "Comparison-Report-Detailed.md").read_text(encoding="utf-8")

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "✅ 本次测试未发现新 Bug" in report
    assert "内容 4 项" in report


def test_source_lang_residue_fails(tmp_path: Path) -> None:
    run_dir = _copy_run(tmp_path)
    result_path = run_dir / "A-xliff-cli" / "orf_out" / "result.docx"
    source_paragraphs = _top_paragraphs(_docx_xml(BASE_RUN / "source.docx"))
    source_texts = [_paragraph_text(paragraph) for paragraph in source_paragraphs]

    def mutate(data: bytes) -> bytes:
        root = ET.fromstring(data)
        top = _top_paragraphs(root)
        for index in (3, 4, 5):
            targets = _definition(top[index])
            if not targets:
                continue
            targets[0].text = source_texts[index]
            for node in targets[1:]:
                node.text = ""
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    edit_docx(result_path, mutate)
    completed = _run_report(run_dir)
    report = (run_dir / "Comparison-Report-Detailed.md").read_text(encoding="utf-8")

    assert completed.returncode == 1
    assert "source_lang_residue" in report
    for location in ("p3", "p4", "p5"):
        assert location in report
    assert "✅ 本次测试未发现新 Bug" not in report


def test_skipped_units_fails(tmp_path: Path) -> None:
    run_dir = _copy_run(tmp_path)
    result_path = run_dir / "A-xliff-cli" / "orf_out" / "result.docx"

    def mutate(data: bytes) -> bytes:
        root = ET.fromstring(data)
        body = root.find(W + "body")
        top = _top_paragraphs(root)
        for paragraph in (top[4], top[5]):
            body.remove(paragraph)
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    edit_docx(result_path, mutate)
    completed = _run_report(run_dir)
    report = (run_dir / "Comparison-Report-Detailed.md").read_text(encoding="utf-8")

    assert completed.returncode == 1
    assert "skipped_units" in report
    assert "p4" in report
    assert "p5" in report
    assert "missing in result" in report
    assert "✅ 本次测试未发现新 Bug" not in report


def test_tag_residue_fails(tmp_path: Path) -> None:
    run_dir = _copy_run(tmp_path)
    result_path = run_dir / "A-xliff-cli" / "orf_out" / "result.docx"

    def mutate(data: bytes) -> bytes:
        root = ET.fromstring(data)
        top = _top_paragraphs(root)
        targets = _definition(top[4])
        assert targets
        targets[-1].text = (targets[-1].text or "") + " [OL:CODE:0001]"
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    edit_docx(result_path, mutate)
    completed = _run_report(run_dir)
    report = (run_dir / "Comparison-Report-Detailed.md").read_text(encoding="utf-8")

    assert completed.returncode == 1
    assert "tag_residue" in report
    assert "[OL:CODE:0001]" in report or "p4" in report
    assert "✅ 本次测试未发现新 Bug" not in report
