"""Tests for scripts/report_comparison.py (E2E content gates).

Fixtures are built from scratch (stdlib only) so the suite never depends on
gitignored run artifacts.
"""

from __future__ import annotations

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1]
SCRIPT = SUITE / "scripts" / "report_comparison.py"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
XML_NS = "http://www.w3.org/XML/1998/namespace"

SOURCE_TEXTS = [
    "标题一",
    "第二章 海尔的全球创牌",
    "",
    "创出一个全球化企业、世界级品牌",
    "改革开放以来，中国企业出海已走过数十年历程。",
    "历经40年创业发展，海尔持续聚焦科技自主创新。",
    "海尔已经连续6年蝉联全球品牌百强。",
    "  #46",
    "海尔全球创牌的成果：35个工业园、143个工厂。",
    "服务10亿用户家庭。",
]

TARGET_TEXTS = [
    "Title One",
    "Chapter Two Haier's Global Brand Building",
    "",
    "Create a global enterprise, world-class brand",
    "Since reform and opening up, Chinese enterprises have gone global for decades.",
    "After 40 years of development, Haier keeps focusing on technological innovation.",
    "Haier has been in the global top 100 brands for six consecutive years.",
    "#46",
    "Haier's global brand results: 35 industrial parks and 143 factories.",
    "Serving 1 billion households.",
]

IMAGE_PARAGRAPHS = (7, 8)
UNIT_PARAGRAPHS = (0, 1, 3, 4, 5, 6, 7, 8, 9)

CONTENT_TYPES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""

ROOT_RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""


def _qualified(tag: str) -> str:
    return W + tag


def _document_xml(paragraphs: list[str], image_paragraphs: tuple[int, ...]) -> bytes:
    ET.register_namespace("w", W[1:-1])
    document = ET.Element(_qualified("document"))
    body = ET.SubElement(document, _qualified("body"))
    for index, text in enumerate(paragraphs):
        paragraph = ET.SubElement(body, _qualified("p"))
        if text:
            run = ET.SubElement(paragraph, _qualified("r"))
            node = ET.SubElement(run, _qualified("t"))
            node.text = text
            if text != text.strip():
                node.set("{" + XML_NS + "}space", "preserve")
        if index in image_paragraphs:
            run = ET.SubElement(paragraph, _qualified("r"))
            ET.SubElement(run, _qualified("drawing"))
    return ET.tostring(document, encoding="utf-8", xml_declaration=True)


def _write_docx(path: Path, paragraphs: list[str], image_paragraphs: tuple[int, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES_XML)
        archive.writestr("_rels/.rels", ROOT_RELS_XML)
        archive.writestr("word/document.xml", _document_xml(paragraphs, image_paragraphs))


def _write_xliff(path: Path, units: list[tuple[str, str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    xliff = ET.Element("xliff", {"version": "1.2"})
    file_element = ET.SubElement(
        xliff,
        "file",
        {
            "source-language": "zh",
            "target-language": "en",
            "original": "source.docx",
            "datatype": "plaintext",
        },
    )
    body = ET.SubElement(file_element, "body")
    for unit_id, source, target in units:
        trans_unit = ET.SubElement(body, "trans-unit", {"id": unit_id})
        source_element = ET.SubElement(trans_unit, "source")
        source_element.text = source
        target_element = ET.SubElement(trans_unit, "target")
        target_element.text = target
    path.write_text(ET.tostring(xliff, encoding="unicode") + "\n", encoding="utf-8")


def build_fixture_run(root: Path) -> Path:
    """在 root 下造一个最小但完整的 run 目录，四向用例都基于它。"""
    run_dir = root
    run_dir.mkdir(parents=True, exist_ok=True)

    _write_docx(run_dir / "source.docx", SOURCE_TEXTS, IMAGE_PARAGRAPHS)
    _write_docx(
        run_dir / "A-xliff-cli" / "orf_out" / "result.docx",
        TARGET_TEXTS,
        IMAGE_PARAGRAPHS,
    )

    units = [
        (str(unit_id), SOURCE_TEXTS[source_index], TARGET_TEXTS[source_index])
        for unit_id, source_index in enumerate(UNIT_PARAGRAPHS, start=1)
    ]
    _write_xliff(run_dir / "A-xliff-cli" / "opp_out" / "source.xlf", units)
    _write_xliff(run_dir / "A-xliff-cli" / "ol_out" / "source.xlf", units)

    metadata = {
        "shas": {"OPP": "aaaaaaa", "OL": "bbbbbbb", "ORF": "ccccccc"},
        "canonical_source": {"file": "fixture.docx"},
        "source_lang": "zh",
        "target_lang": "en",
    }
    (run_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return run_dir


def _run_report(run_dir: Path, *, as_json: bool = False) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(SCRIPT),
        str(run_dir),
        "--suite",
        str(SUITE),
        "--path",
        "A",
    ]
    if as_json:
        command.append("--json")
    return subprocess.run(command, capture_output=True, text=True)


def _json_findings(completed: subprocess.CompletedProcess[str]) -> list[dict[str, str]]:
    payload = json.loads(completed.stdout)
    return payload["paths"]["A"]["findings"]


def _locations(findings: list[dict[str, str]], rule: str) -> set[str]:
    return {finding["location"] for finding in findings if finding["rule"] == rule}


def _rule_counts(findings: list[dict[str, str]]) -> dict[str, int]:
    counts = {
        "source_lang_residue": 0,
        "skipped_units": 0,
        "tag_residue": 0,
        "llm_refusal": 0,
    }
    for finding in findings:
        counts[finding["rule"]] = counts.get(finding["rule"], 0) + 1
    return counts


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
    run_dir = build_fixture_run(tmp_path / "run")
    completed = _run_report(run_dir, as_json=True)
    report = (run_dir / "Comparison-Report-Detailed.md").read_text(encoding="utf-8")

    assert completed.returncode == 0, completed.stdout + completed.stderr
    findings = _json_findings(completed)
    assert _rule_counts(findings) == {
        "source_lang_residue": 0,
        "skipped_units": 0,
        "tag_residue": 0,
        "llm_refusal": 0,
    }
    assert "✅ 本次测试未发现新 Bug" in report
    assert "内容 4 项" in report


def test_source_lang_residue_fails(tmp_path: Path) -> None:
    run_dir = build_fixture_run(tmp_path / "run")
    result_path = run_dir / "A-xliff-cli" / "orf_out" / "result.docx"

    def mutate(data: bytes) -> bytes:
        root = ET.fromstring(data)
        top = _top_paragraphs(root)
        for index in (3, 4, 5):
            targets = _definition(top[index])
            if not targets:
                continue
            targets[0].text = SOURCE_TEXTS[index]
            for node in targets[1:]:
                node.text = ""
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    edit_docx(result_path, mutate)
    completed = _run_report(run_dir, as_json=True)
    report = (run_dir / "Comparison-Report-Detailed.md").read_text(encoding="utf-8")

    assert completed.returncode == 1, completed.stdout + completed.stderr
    findings = _json_findings(completed)
    assert _locations(findings, "source_lang_residue") == {"p3", "p4", "p5"}
    assert _locations(findings, "skipped_units") <= {"p3", "p4", "p5"}
    assert "✅ 本次测试未发现新 Bug" not in report


def test_skipped_units_fails(tmp_path: Path) -> None:
    run_dir = build_fixture_run(tmp_path / "run")
    result_path = run_dir / "A-xliff-cli" / "orf_out" / "result.docx"

    def mutate(data: bytes) -> bytes:
        root = ET.fromstring(data)
        body = root.find(W + "body")
        top = _top_paragraphs(root)
        for paragraph in (top[4], top[5]):
            body.remove(paragraph)
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    edit_docx(result_path, mutate)
    completed = _run_report(run_dir, as_json=True)
    report = (run_dir / "Comparison-Report-Detailed.md").read_text(encoding="utf-8")

    assert completed.returncode == 1, completed.stdout + completed.stderr
    findings = _json_findings(completed)
    assert _locations(findings, "skipped_units") == {"p4", "p5"}
    assert "missing in result" in report
    assert "✅ 本次测试未发现新 Bug" not in report


def test_tag_residue_fails(tmp_path: Path) -> None:
    run_dir = build_fixture_run(tmp_path / "run")
    result_path = run_dir / "A-xliff-cli" / "orf_out" / "result.docx"

    def mutate(data: bytes) -> bytes:
        root = ET.fromstring(data)
        top = _top_paragraphs(root)
        targets = _definition(top[4])
        assert targets
        targets[-1].text = (targets[-1].text or "") + " [OL:CODE:0001]"
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    edit_docx(result_path, mutate)
    completed = _run_report(run_dir, as_json=True)
    report = (run_dir / "Comparison-Report-Detailed.md").read_text(encoding="utf-8")

    assert completed.returncode == 1, completed.stdout + completed.stderr
    findings = _json_findings(completed)
    counts = _rule_counts(findings)
    assert _locations(findings, "tag_residue") == {"p4"}
    assert counts["source_lang_residue"] == 0
    assert counts["skipped_units"] == 0
    assert counts["llm_refusal"] == 0
    assert "✅ 本次测试未发现新 Bug" not in report


def test_no_dependency_on_test_output() -> None:
    """fixture 必须纯自造：测试文件不得引用 gitignored 产物或任何 run 目录常量。"""
    text = Path(__file__).read_text(encoding="utf-8")
    assert "test" + "-output" not in text
    assert "Full" + "-Standard-" not in text
