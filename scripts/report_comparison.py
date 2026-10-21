#!/usr/bin/env python3
"""Generate an E2E content + structure acceptance report for a pipeline run."""

from __future__ import annotations

import argparse
import datetime as _dt
import difflib
import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

RESIDUE_MIN_RUN_CJK = 2
RESIDUE_MIN_LATIN_WORDS = 4
SKIP_SIMILARITY = 0.98
DEGENERATE_RUN = 10
MIN_TARGET_CHARS = 3

PATH_DIRS = {
    "A": "A-xliff-cli",
    "B": "B-xliff-mcp",
    "C": "C-md-cli",
    "D": "D-md-mcp",
}
MODULE_DIRS = {
    "OPP": "Omni_Pre_Processor",
    "OL": "Omni_Localizer",
    "ORF": "Omni_Re_Formatter",
}
STRUCTURE_RULES = (
    "structure_paragraphs",
    "structure_images",
    "structure_image_positions",
    "structure_document",
)
CONTENT_RULES = (
    "source_lang_residue",
    "skipped_units",
    "tag_residue",
    "llm_refusal",
)

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
CJK_RUN_RE = re.compile(rf"[\u3400-\u4dbf\u4e00-\u9fff]{{{RESIDUE_MIN_RUN_CJK},}}")
LATIN_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’\-]*")
LATIN_RUN_RE = re.compile(
    r"[A-Za-z][A-Za-z'’\-]*"
    r"(?:(?:[ \t\r\n]+|[.,;:!?'\"()\[\]{}<>/\\|&@#$%^*+=~`_\-]+)"
    rf"[A-Za-z][A-Za-z'’\-]*){{{RESIDUE_MIN_LATIN_WORDS - 1},}}"
)
DEGENERATE_RE = re.compile(rf"(.)\1{{{DEGENERATE_RUN - 1},}}")
MD_SEPARATOR_RE = re.compile(r"^\s*\|?[\s:|-]*-[\s:|-]*\|?\s*$")

TAG_PATTERNS = [
    (r"\[OL:[A-Za-z0-9:_\-]+\]", "unrestored OL placeholder"),
    (r"&lt;/?(?:bx|ex|b|i)\b", "escaped XML tag"),
    (r"<bx[^/>]*$", "truncated <bx tag"),
    (r"<ex[^/>]*$", "truncated <ex tag"),
    (r"<note\b", "leaked <note> element (E2E-69)"),
    (r"Warning:\s*Tag auto-appended", "OL fallback warning leaked into text"),
    (r"\x00TAG", "NUL sentinel leaked"),
    (r"</?w:t\b", "literal w:t markup leaked into text"),
]

REFUSAL_PATTERNS = [
    r"i'm sorry",
    r"i am sorry",
    r"i cannot",
    r"i can't",
    r"i'm unable to",
    r"i am unable to",
    r"could you (confirm|provide|clarify)",
    r"please (provide|clarify|confirm)",
    r"translation is already",
    r"already in the target",
    r"the text you provided is already",
    r"as an ai",
    r"抱歉",
    r"无法翻译",
    r"作为(一个)?AI",
]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def make_snippet(text: str, start: int, end: int, limit: int = 30) -> str:
    match = text[start:end]
    if len(match) >= limit:
        snippet = match[:limit]
    else:
        pad = (limit - len(match)) // 2
        left = min(pad, start)
        right = limit - len(match) - left
        snippet = text[start - left : end + right]
    return normalize(snippet).replace("|", "\\|")


@dataclass
class Paragraph:
    index: int
    text: str


@dataclass
class DocxContent:
    path: Path
    paragraphs: list[Paragraph]
    nested: list[Paragraph]
    image_count: int
    image_positions: list[int]
    xml_error: str | None = None
    drawing_count: int = 0
    pict_count: int = 0


@dataclass
class XliffUnit:
    id: str
    source: str
    target: str | None


@dataclass
class XliffContent:
    path: Path | None
    source_lang: str | None
    target_lang: str | None
    units: list[XliffUnit]
    raw: str
    error: str | None = None


@dataclass
class Finding:
    rule: str
    location: str
    snippet: str
    detail: str


@dataclass
class StructureSnapshot:
    source_paragraphs: int
    result_paragraphs: int
    source_images: int
    result_images: int
    source_positions: list[int]
    result_positions: list[int]
    paragraphs_ok: bool
    images_ok: bool
    positions_ok: bool


@dataclass
class PathReport:
    key: str
    dirname: str
    has_result: bool
    structure: StructureSnapshot | None
    structure_findings: list[Finding] = field(default_factory=list)
    content_findings: list[Finding] = field(default_factory=list)
    xliff_note: str = ""
    status: str = ""

    @property
    def findings(self) -> list[Finding]:
        return self.structure_findings + self.content_findings


def read_docx(path: Path) -> DocxContent:
    try:
        with zipfile.ZipFile(path) as archive:
            data = archive.read("word/document.xml")
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        return DocxContent(path, [], [], 0, [], xml_error=str(exc))

    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        return DocxContent(path, [], [], 0, [], xml_error=str(exc))

    body = root.find(W + "body")
    top_elements = [child for child in body if child.tag == W + "p"] if body is not None else []
    top_set = set(top_elements)
    all_paragraphs = root.findall(".//" + W + "p")
    nested_elements = [element for element in all_paragraphs if element not in top_set]

    paragraphs = [
        Paragraph(index, "".join(node.text or "" for node in element.findall(".//" + W + "t")))
        for index, element in enumerate(top_elements)
    ]
    nested = [
        Paragraph(index + 1, "".join(node.text or "" for node in element.findall(".//" + W + "t")))
        for index, element in enumerate(nested_elements)
    ]

    drawing_count = len(root.findall(".//" + W + "drawing"))
    pict_count = len(root.findall(".//" + W + "pict"))
    image_positions = [
        paragraph.index
        for paragraph, element in zip(paragraphs, top_elements, strict=False)
        if element.findall(".//" + W + "drawing") or element.findall(".//" + W + "pict")
    ]

    return DocxContent(
        path=path,
        paragraphs=paragraphs,
        nested=nested,
        image_count=drawing_count + pict_count,
        image_positions=image_positions,
        drawing_count=drawing_count,
        pict_count=pict_count,
    )


def read_xliff(path: Path | None) -> XliffContent:
    if path is None or not path.is_file():
        return XliffContent(None, None, None, [], "")
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return XliffContent(path, None, None, [], "", error=str(exc))
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        return XliffContent(path, None, None, [], raw, error=str(exc))

    file_element = next(
        (element for element in root.iter() if local_name(element.tag) == "file"), None
    )
    source_lang = file_element.get("source-language") if file_element is not None else None
    target_lang = file_element.get("target-language") if file_element is not None else None

    units: list[XliffUnit] = []
    for element in root.iter():
        if local_name(element.tag) != "trans-unit":
            continue
        unit_id = element.get("id") or ""
        source_element = next(
            (child for child in element if local_name(child.tag) == "source"), None
        )
        target_element = next(
            (child for child in element if local_name(child.tag) == "target"), None
        )
        units.append(
            XliffUnit(
                id=unit_id,
                source="".join(source_element.itertext()) if source_element is not None else "",
                target="".join(target_element.itertext()) if target_element is not None else None,
            )
        )
    return XliffContent(path, source_lang, target_lang, units, raw)


def document_texts(document: DocxContent) -> list[tuple[str, str]]:
    items = [(f"p{paragraph.index}", paragraph.text) for paragraph in document.paragraphs]
    items.extend((f"nested#{paragraph.index}", paragraph.text) for paragraph in document.nested)
    return items


def xliff_target_texts(xliff: XliffContent) -> list[tuple[str, str]]:
    return [(f"unit {unit.id}", unit.target) for unit in xliff.units if unit.target is not None]


def has_source_language_chars(text: str, target_lang: str) -> bool:
    if target_lang == "zh":
        return LATIN_WORD_RE.search(text) is not None
    return CJK_RE.search(text) is not None


def scan_source_lang_residue(items: list[tuple[str, str]], target_lang: str) -> list[Finding]:
    pattern = LATIN_RUN_RE if target_lang == "zh" else CJK_RUN_RE
    detail = "Latin-word run in zh target" if target_lang == "zh" else "CJK run in non-zh target"
    findings: list[Finding] = []
    for location, text in items:
        for match in pattern.finditer(text):
            findings.append(
                Finding(
                    "source_lang_residue",
                    location,
                    make_snippet(text, match.start(), match.end()),
                    detail,
                )
            )
    return findings


def scan_tag_residue(
    items: list[tuple[str, str]], patterns: list[tuple[str, str]] | None = None
) -> list[Finding]:
    active = TAG_PATTERNS if patterns is None else patterns
    findings: list[Finding] = []
    for location, text in items:
        for pattern, detail in active:
            for match in re.finditer(pattern, text):
                findings.append(
                    Finding(
                        "tag_residue",
                        location,
                        make_snippet(text, match.start(), match.end()),
                        detail,
                    )
                )
    return findings


def scan_llm_refusal(items: list[tuple[str, str]]) -> list[Finding]:
    findings: list[Finding] = []
    for location, text in items:
        for pattern in REFUSAL_PATTERNS:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match is not None:
                findings.append(
                    Finding(
                        "llm_refusal",
                        location,
                        make_snippet(text, match.start(), match.end()),
                        f"refusal/clarification phrase: {match.group(0)}",
                    )
                )
    return findings


def strip_markdown_tables(text: str) -> str:
    kept = [line for line in text.splitlines() if not MD_SEPARATOR_RE.match(line)]
    return "\n".join(kept)


def scan_degenerate(items: list[tuple[str, str]]) -> list[Finding]:
    findings: list[Finding] = []
    for location, text in items:
        cleaned = strip_markdown_tables(text)
        match = DEGENERATE_RE.search(cleaned)
        if match is not None:
            findings.append(
                Finding(
                    "llm_refusal",
                    location,
                    make_snippet(cleaned, match.start(), match.end()),
                    "degenerate output",
                )
            )
    return findings


def scan_empty_xliff_targets(xliff: XliffContent) -> list[Finding]:
    findings: list[Finding] = []
    for unit in xliff.units:
        if unit.target is None or not unit.target.strip():
            findings.append(
                Finding(
                    "llm_refusal",
                    f"unit {unit.id}",
                    "",
                    "empty target (LLM 未产出)",
                )
            )
    return findings


def _tail_alignment(source: DocxContent, result: DocxContent) -> list[Finding]:
    findings: list[Finding] = []
    source_texts = [normalize(paragraph.text) for paragraph in source.paragraphs]
    result_texts = [normalize(paragraph.text) for paragraph in result.paragraphs]
    for index in range(max(len(source_texts), len(result_texts))):
        if index >= len(result_texts):
            findings.append(
                Finding(
                    "skipped_units",
                    f"p{index}",
                    make_snippet(source_texts[index], 0, len(source_texts[index])),
                    "missing in result",
                )
            )
        elif index >= len(source_texts):
            findings.append(
                Finding(
                    "skipped_units",
                    f"p{index}",
                    make_snippet(result_texts[index], 0, len(result_texts[index])),
                    "extra in result",
                )
            )
    return findings


def _xliff_alignment(
    source: DocxContent, result: DocxContent, xliff: XliffContent
) -> list[Finding] | None:
    if not xliff.units:
        return None

    source_texts = [normalize(paragraph.text) for paragraph in source.paragraphs]
    result_texts = [normalize(paragraph.text) for paragraph in result.paragraphs]

    unit_to_source: dict[str, int] = {}
    used_sources: set[int] = set()
    for unit in xliff.units:
        unit_source = normalize(unit.source)
        if not unit_source:
            continue
        for index, text in enumerate(source_texts):
            if index in used_sources:
                continue
            if text == unit_source:
                unit_to_source[unit.id] = index
                used_sources.add(index)
                break

    target_to_units: dict[str, list[str]] = {}
    for unit in xliff.units:
        if unit.target is not None:
            target_to_units.setdefault(normalize(unit.target), []).append(unit.id)

    source_present: set[int] = set()
    result_mapped: set[int] = set()
    for result_index, text in enumerate(result_texts):
        for unit_id in target_to_units.get(text, []):
            source_index = unit_to_source.get(unit_id)
            if source_index is not None:
                source_present.add(source_index)
                result_mapped.add(result_index)
                break

    empty_sources = [
        index for index, text in enumerate(source_texts) if not text and index not in source_present
    ]
    empty_results = [
        index for index, text in enumerate(result_texts) if not text and index not in result_mapped
    ]
    for source_index, result_index in zip(empty_sources, empty_results, strict=False):
        source_present.add(source_index)
        result_mapped.add(result_index)

    if not source_present and not result_mapped:
        return None

    findings: list[Finding] = []
    for index, text in enumerate(source_texts):
        if index not in source_present:
            findings.append(
                Finding(
                    "skipped_units",
                    f"p{index}",
                    make_snippet(text, 0, len(text)),
                    "missing in result",
                )
            )
    for index, text in enumerate(result_texts):
        if index not in result_mapped:
            findings.append(
                Finding(
                    "skipped_units",
                    f"p{index}",
                    make_snippet(text, 0, len(text)),
                    "extra in result",
                )
            )
    return findings


def gate_skipped_units(
    source: DocxContent,
    result: DocxContent,
    target_lang: str,
    ol_xliff: XliffContent,
    opp_xliff: XliffContent,
) -> list[Finding]:
    findings: list[Finding] = []

    if len(source.paragraphs) != len(result.paragraphs):
        aligned = _xliff_alignment(source, result, ol_xliff)
        findings.extend(aligned if aligned is not None else _tail_alignment(source, result))

    for index in range(min(len(source.paragraphs), len(result.paragraphs))):
        source_text = source.paragraphs[index].text
        result_text = result.paragraphs[index].text
        source_norm = normalize(source_text)
        result_norm = normalize(result_text)

        if source_norm and has_source_language_chars(source_text, target_lang):
            ratio = difflib.SequenceMatcher(None, source_norm, result_norm).ratio()
            if result_norm == source_norm or ratio >= SKIP_SIMILARITY:
                findings.append(
                    Finding(
                        "skipped_units",
                        f"p{index}",
                        make_snippet(source_text, 0, len(source_text)),
                        "untranslated (source text unchanged)",
                    )
                )

        if source_norm and len(result_text.strip()) < MIN_TARGET_CHARS:
            findings.append(
                Finding(
                    "skipped_units",
                    f"p{index}",
                    make_snippet(source_text, 0, len(source_text)),
                    "empty target",
                )
            )

    if ol_xliff.path is not None and opp_xliff.path is not None:
        opp_ids = {unit.id for unit in opp_xliff.units}
        ol_ids = {unit.id for unit in ol_xliff.units}
        for unit_id in sorted(opp_ids - ol_ids):
            findings.append(
                Finding(
                    "skipped_units",
                    f"unit {unit_id}",
                    "",
                    "missing in translated xliff",
                )
            )
        for unit_id in sorted(ol_ids - opp_ids):
            findings.append(
                Finding(
                    "skipped_units",
                    f"unit {unit_id}",
                    "",
                    "extra in translated xliff",
                )
            )
        if len(ol_xliff.units) != len(opp_xliff.units) and ol_ids == opp_ids:
            findings.append(
                Finding(
                    "skipped_units",
                    "xliff",
                    "",
                    f"unit count {len(ol_xliff.units)} != {len(opp_xliff.units)}",
                )
            )

    return findings


def dedupe(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, str, str, str]] = set()
    unique: list[Finding] = []
    for finding in findings:
        key = (finding.rule, finding.location, finding.snippet, finding.detail)
        if key not in seen:
            seen.add(key)
            unique.append(finding)
    return unique


def content_findings_for_path(
    source: DocxContent,
    result: DocxContent | None,
    target_lang: str,
    ol_xliff: XliffContent,
    opp_xliff: XliffContent,
) -> list[Finding]:
    findings: list[Finding] = []

    if result is not None:
        doc_items = document_texts(result)
        findings.extend(scan_source_lang_residue(doc_items, target_lang))
        findings.extend(scan_tag_residue(doc_items))
        findings.extend(scan_llm_refusal(doc_items))
        findings.extend(scan_degenerate(doc_items))
        findings.extend(gate_skipped_units(source, result, target_lang, ol_xliff, opp_xliff))

    if ol_xliff.path is not None:
        target_items = xliff_target_texts(ol_xliff)
        findings.extend(scan_source_lang_residue(target_items, target_lang))
        findings.extend(scan_tag_residue(target_items))
        findings.extend(
            scan_tag_residue(
                [("xliff raw", ol_xliff.raw)],
                patterns=[pattern for pattern in TAG_PATTERNS if pattern[0] != r"</?w:t\b"],
            )
        )
        findings.extend(scan_llm_refusal(target_items))
        findings.extend(scan_empty_xliff_targets(ol_xliff))
        findings.extend(scan_degenerate(target_items))

    return dedupe(findings)


def compare_structure(
    source: DocxContent, result: DocxContent
) -> tuple[StructureSnapshot, list[Finding]]:
    snapshot = StructureSnapshot(
        source_paragraphs=len(source.paragraphs),
        result_paragraphs=len(result.paragraphs),
        source_images=source.image_count,
        result_images=result.image_count,
        source_positions=list(source.image_positions),
        result_positions=list(result.image_positions),
        paragraphs_ok=len(source.paragraphs) == len(result.paragraphs),
        images_ok=source.image_count == result.image_count,
        positions_ok=source.image_positions == result.image_positions,
    )
    findings: list[Finding] = []
    if not snapshot.paragraphs_ok:
        findings.append(
            Finding(
                "structure_paragraphs",
                "paragraph count",
                "",
                f"source {snapshot.source_paragraphs} != result {snapshot.result_paragraphs}",
            )
        )
    if not snapshot.images_ok:
        findings.append(
            Finding(
                "structure_images",
                "image count",
                "",
                f"source {snapshot.source_images} != result {snapshot.result_images}",
            )
        )
    if not snapshot.positions_ok:
        findings.append(
            Finding(
                "structure_image_positions",
                "image positions",
                "",
                f"source {snapshot.source_positions} != result {snapshot.result_positions}",
            )
        )
    return snapshot, findings


def analyze_path(
    key: str, run_dir: Path, source_content: DocxContent, target_lang: str
) -> PathReport:
    dirname = PATH_DIRS[key]
    path_dir = run_dir / dirname
    result_path = path_dir / "orf_out" / "result.docx"
    has_result = result_path.is_file()

    ol_xliff = read_xliff(path_dir / "ol_out" / "source.xlf")
    opp_xliff = read_xliff(path_dir / "opp_out" / "source.xlf")

    structure: StructureSnapshot | None = None
    structure_findings: list[Finding] = []
    result_content: DocxContent | None = None

    if has_result:
        result_content = read_docx(result_path)
        if result_content.xml_error:
            structure = StructureSnapshot(
                len(source_content.paragraphs),
                0,
                source_content.image_count,
                0,
                list(source_content.image_positions),
                [],
                False,
                False,
                False,
            )
            structure_findings.append(
                Finding(
                    "structure_document",
                    "document.xml",
                    "",
                    f"XML unparsable: {result_content.xml_error}",
                )
            )
        else:
            structure, structure_findings = compare_structure(source_content, result_content)

    content_findings = content_findings_for_path(
        source_content, result_content, target_lang, ol_xliff, opp_xliff
    )

    if result_content is not None and result_content.xml_error:
        content_findings = dedupe(
            content_findings
            + [
                Finding(
                    "tag_residue",
                    "document.xml",
                    "",
                    "XML unparsable",
                )
            ]
        )

    xliff_note = ""
    if ol_xliff.path is None:
        xliff_note = "XLIFF 层跳过（无 ol_out/source.xlf）"

    report = PathReport(
        key=key,
        dirname=dirname,
        has_result=has_result,
        structure=structure,
        structure_findings=structure_findings,
        content_findings=content_findings,
        xliff_note=xliff_note,
    )
    if report.structure_findings or report.content_findings:
        report.status = "FAIL"
    elif not report.has_result:
        report.status = "INCOMPLETE"
    else:
        report.status = "PASS"
    return report


def resolve_run_dir(run_id: str, runs_base: Path) -> Path:
    candidate = Path(run_id)
    if not candidate.is_absolute():
        candidate = runs_base / candidate
    return candidate


def resolve_source(run_dir: Path, suite: Path, metadata: dict) -> tuple[Path | None, list[Path]]:
    tried: list[Path] = []
    local = run_dir / "source.docx"
    tried.append(local)
    if local.is_file():
        return local, tried

    canonical = metadata.get("canonical_source")
    if isinstance(canonical, dict) and canonical.get("file"):
        fallback = suite / "test-artifacts" / str(canonical["file"])
        tried.append(fallback)
        if fallback.is_file():
            return fallback, tried
    return None, tried


def resolve_language(run_dir: Path, paths: list[str], metadata: dict) -> tuple[str, str, str]:
    ordered_paths = list(paths) + [key for key in PATH_DIRS if key not in paths]
    for key in ordered_paths:
        path_dir = run_dir / PATH_DIRS[key]
        for relative in ("ol_out/source.xlf", "opp_out/source.xlf"):
            xliff = read_xliff(path_dir / relative)
            if xliff.source_lang and xliff.target_lang:
                return xliff.source_lang, xliff.target_lang, f"XLIFF 产物（{key} / {relative}）"

    source_lang = metadata.get("source_lang")
    target_lang = metadata.get("target_lang")
    if source_lang and target_lang:
        return str(source_lang), str(target_lang), "metadata.json"
    return "zh", "en", "默认值（未在产物中找到）"


def _git_short_head(directory: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = completed.stdout.strip()
    if completed.returncode == 0 and value:
        return value
    return None


def resolve_shas(suite: Path, metadata: dict) -> tuple[dict[str, str], dict[str, str]]:
    shas: dict[str, str] = {}
    sources: dict[str, str] = {}
    metadata_shas = metadata.get("shas")
    if not isinstance(metadata_shas, dict):
        metadata_shas = {}

    for module in ("OPP", "OL", "ORF"):
        value = metadata_shas.get(module) or metadata_shas.get(module.lower())
        if value:
            shas[module] = str(value)
            sources[module] = "metadata.json"
            continue

        value = None
        for base in (suite / "src", suite):
            directory = base / MODULE_DIRS[module]
            if directory.is_dir():
                value = _git_short_head(directory)
                if value:
                    break
        if value:
            shas[module] = value
            sources[module] = "git"
        else:
            shas[module] = "unknown"
            sources[module] = "未取到"
    return shas, sources


def file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def status_icon(ok: bool) -> str:
    return "✅" if ok else "❌"


def render_report(
    run_id: str,
    run_dir: Path,
    source_path: Path,
    source_md5: str,
    source_content: DocxContent,
    language: tuple[str, str, str],
    shas: dict[str, str],
    sha_sources: dict[str, str],
    paths: list[PathReport],
    conclusion: str,
) -> str:
    source_lang, target_lang, language_source = language
    lines: list[str] = []
    lines.append("# E2E 内容 + 结构验收报告")
    lines.append("")
    lines.append(f"**Run ID**: `{run_id}`")
    lines.append(f"**生成时间**: {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    lines.append("## 数据来源")
    lines.append("")
    lines.append("| 项 | 值 |")
    lines.append("|:--|:--|")
    lines.append(f"| 源文档 | `{source_path}` |")
    lines.append(f"| 源文件 MD5 | `{source_md5}` |")
    lines.append(
        f"| 源文档结构 | {len(source_content.paragraphs)} 段 / {source_content.image_count} 图 / "
        f"位置 {source_content.image_positions} |"
    )
    lines.append(f"| 语向 | `{source_lang} → {target_lang}`（来源：{language_source}） |")
    for module in ("OPP", "OL", "ORF"):
        shas_note = ""
        if sha_sources[module] == "未取到":
            shas_note = "（SHA来源=未取到）"
        else:
            shas_note = f"（来源：{sha_sources[module]}）"
        lines.append(f"| {module} SHA | `{shas[module]}`{shas_note} |")
    if source_content.xml_error:
        lines.append(f"| 源文档 XML | ❌ {source_content.xml_error} |")
    lines.append("")

    lines.append("## 结论")
    lines.append("")
    lines.append(conclusion)
    lines.append("")

    lines.append("## 门控总表")
    lines.append("")
    lines.append(
        "| 路径 | 结构 段数 | 结构 图数 | 结构 图片位置 | source_lang_residue | "
        "skipped_units | tag_residue | llm_refusal | 状态 |"
    )
    lines.append("|:--|:--|:--|:--|:--|:--|:--|:--|:--|")
    for path in paths:
        counts = {rule: 0 for rule in CONTENT_RULES}
        for finding in path.content_findings:
            counts[finding.rule] = counts.get(finding.rule, 0) + 1
        if path.structure is None:
            para_cell = "—"
            image_cell = "—"
            position_cell = "—"
        else:
            snapshot = path.structure
            para_cell = (
                f"{status_icon(snapshot.paragraphs_ok)} "
                f"{snapshot.result_paragraphs}/{snapshot.source_paragraphs}"
            )
            image_cell = (
                f"{status_icon(snapshot.images_ok)} "
                f"{snapshot.result_images}/{snapshot.source_images}"
            )
            position_cell = (
                f"{status_icon(snapshot.positions_ok)} "
                f"{snapshot.result_positions}/{snapshot.source_positions}"
            )
        lines.append(
            f"| {path.key} | {para_cell} | {image_cell} | {position_cell} | "
            f"{counts['source_lang_residue']} | {counts['skipped_units']} | "
            f"{counts['tag_residue']} | {counts['llm_refusal']} | {path.status} |"
        )
    lines.append("")

    lines.append("## 失败明细")
    lines.append("")
    ordered_rules = list(CONTENT_RULES) + list(STRUCTURE_RULES)
    grouped = {
        rule: [
            (path.key, finding)
            for path in paths
            for finding in path.findings
            if finding.rule == rule
        ]
        for rule in ordered_rules
    }
    any_findings = any(grouped.values())
    if not any_findings:
        lines.append("无（全部通过）")
        lines.append("")
    for rule in ordered_rules:
        entries = grouped[rule]
        if not entries:
            continue
        lines.append(f"### {rule}（{len(entries)}）")
        lines.append("")
        lines.append("| 路径 | 位置 | 片段 | 说明 |")
        lines.append("|:--|:--|:--|:--|")
        for path_key, finding in entries:
            snippet = finding.snippet or "—"
            detail = finding.detail.replace("|", "\\|")
            lines.append(f"| {path_key} | {finding.location} | `{snippet}` | {detail} |")
        lines.append("")

    lines.append("## 结构维度明细")
    lines.append("")
    lines.append(
        "| 路径 | 源段数 | 结果段数 | 源图数 | 结果图数 | 源图片位置 | 结果图片位置 | 状态 |"
    )
    lines.append("|:--|:--|:--|:--|:--|:--|:--|:--|")
    for path in paths:
        if path.structure is None:
            lines.append(f"| {path.key} | — | — | — | — | — | — | {path.status} |")
            continue
        snapshot = path.structure
        lines.append(
            f"| {path.key} | {snapshot.source_paragraphs} | {snapshot.result_paragraphs} | "
            f"{snapshot.source_images} | {snapshot.result_images} | "
            f"{snapshot.source_positions} | {snapshot.result_positions} | {path.status} |"
        )
    lines.append("")
    notes = [f"- {path.key}: {path.xliff_note}" for path in paths if path.xliff_note]
    if notes:
        lines.append("XLIFF 层：")
        lines.append("")
        lines.extend(notes)
        lines.append("")

    lines.append("## 未产出路径")
    lines.append("")
    missing = [path for path in paths if not path.has_result]
    if missing:
        for path in missing:
            lines.append(f"- {path.key}（{path.dirname}）：无 `orf_out/result.docx`")
    else:
        lines.append("无")
    lines.append("")

    return "\n".join(lines)


def build_json_payload(
    run_id: str,
    source_path: Path,
    source_md5: str,
    source_content: DocxContent,
    language: tuple[str, str, str],
    shas: dict[str, str],
    sha_sources: dict[str, str],
    paths: list[PathReport],
    conclusion: str,
) -> dict:
    return {
        "run_id": run_id,
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "source": {
            "path": str(source_path),
            "md5": source_md5,
            "paragraphs": len(source_content.paragraphs),
            "images": source_content.image_count,
            "image_positions": source_content.image_positions,
            "xml_error": source_content.xml_error,
        },
        "language": {
            "source": language[0],
            "target": language[1],
            "source_of_truth": language[2],
        },
        "shas": {module: {"value": shas[module], "source": sha_sources[module]} for module in shas},
        "conclusion": conclusion,
        "paths": {
            path.key: {
                "dir": path.dirname,
                "status": path.status,
                "has_result": path.has_result,
                "structure": (
                    {
                        "source_paragraphs": path.structure.source_paragraphs,
                        "result_paragraphs": path.structure.result_paragraphs,
                        "source_images": path.structure.source_images,
                        "result_images": path.structure.result_images,
                        "source_positions": path.structure.source_positions,
                        "result_positions": path.structure.result_positions,
                        "paragraphs_ok": path.structure.paragraphs_ok,
                        "images_ok": path.structure.images_ok,
                        "positions_ok": path.structure.positions_ok,
                    }
                    if path.structure is not None
                    else None
                ),
                "findings": [
                    {
                        "rule": finding.rule,
                        "location": finding.location,
                        "snippet": finding.snippet,
                        "detail": finding.detail,
                    }
                    for finding in path.findings
                ],
            }
            for path in paths
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="E2E content + structure acceptance report for OPP→OL→ORF runs"
    )
    parser.add_argument("run_id", help="Run directory name under --runs-base, or an absolute path")
    parser.add_argument(
        "--runs-base",
        default=None,
        help="Base directory containing run directories (default: <suite>/test-output)",
    )
    parser.add_argument(
        "--suite",
        default=None,
        help="Omni Suite root (default: parent of scripts/)",
    )
    parser.add_argument(
        "--path",
        action="append",
        choices=sorted(PATH_DIRS),
        default=None,
        help="Path(s) to verify; repeatable. Default: A B C D",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    suite = Path(args.suite).resolve() if args.suite else Path(__file__).resolve().parents[1]
    runs_base = Path(args.runs_base).resolve() if args.runs_base else suite / "test-output"
    paths = args.path or list(PATH_DIRS)

    run_dir = resolve_run_dir(args.run_id, runs_base)
    if not run_dir.is_dir():
        print(f"ERROR: run directory not found: {run_dir}", file=sys.stderr)
        print(f"  --runs-base: {runs_base}", file=sys.stderr)
        return 2

    metadata: dict = {}
    metadata_path = run_dir / "metadata.json"
    if metadata_path.is_file():
        try:
            loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                metadata = loaded
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            metadata = {}

    source_path, tried_paths = resolve_source(run_dir, suite, metadata)
    if source_path is None:
        print("ERROR: source document not found. Tried:", file=sys.stderr)
        for candidate in tried_paths:
            print(f"  - {candidate}", file=sys.stderr)
        return 2

    source_content = read_docx(source_path)
    if source_content.xml_error:
        print(
            f"ERROR: source document XML unparsable: {source_path}: {source_content.xml_error}",
            file=sys.stderr,
        )
        return 2

    source_md5 = file_md5(source_path)
    language = resolve_language(run_dir, paths, metadata)
    shas, sha_sources = resolve_shas(suite, metadata)

    path_reports = [analyze_path(key, run_dir, source_content, language[1]) for key in paths]

    content_total = sum(len(path.content_findings) for path in path_reports)
    structure_total = sum(len(path.structure_findings) for path in path_reports)
    missing_paths = [path for path in path_reports if not path.has_result]

    if content_total or structure_total:
        total = content_total + structure_total
        conclusion = (
            f"❌ FAIL — 发现 {total} 项阻断问题"
            f"（内容 {content_total} 项 / 结构 {structure_total} 项）"
        )
        exit_code = 1
    elif missing_paths:
        conclusion = f'⚠️ INCOMPLETE — {len(missing_paths)} 条路径未产出结果，不能声明"未发现新 Bug"'
        exit_code = 1
    else:
        conclusion = (
            f"✅ 本次测试未发现新 Bug（结构 3 项 + 内容 4 项全部 PASS，路径 {'/'.join(paths)}）"
        )
        exit_code = 0

    report = render_report(
        run_id=args.run_id,
        run_dir=run_dir,
        source_path=source_path,
        source_md5=source_md5,
        source_content=source_content,
        language=language,
        shas=shas,
        sha_sources=sha_sources,
        paths=path_reports,
        conclusion=conclusion,
    )
    report_path = run_dir / "Comparison-Report-Detailed.md"
    report_path.write_text(report, encoding="utf-8")

    if args.json:
        payload = build_json_payload(
            args.run_id,
            source_path,
            source_md5,
            source_content,
            language,
            shas,
            sha_sources,
            path_reports,
            conclusion,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print(f"\nREPORT: {report_path}", file=sys.stderr)
        print(conclusion, file=sys.stderr)
    else:
        print(report)
        print(f"\nREPORT: {report_path}")
        print(conclusion)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
