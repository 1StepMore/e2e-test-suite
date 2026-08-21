"""Artifact-assertion engine for the Omni Suite validation framework (e2e-test-suite#44).

Formalized P0/P1 assertion set that runs DETERMINISTIC checks on ACTUAL
PRODUCED FILES — the artifacts of the OPP → OL → ORF pipeline (extracted
markdown, manifests, translated docs, backfilled html/json/srt/xml/csv).

Modeled on AutoInfo's ``validation_matrix.py`` (#331/#351): one readable
function per assertion, each carrying its source issue + severity; a
``run_assertions`` entrypoint that scans an artifacts directory and returns
per-artifact results.

Design rules:

* Deterministic — no LLM, no network, no subprocess. Stdlib everywhere;
  PyYAML is imported lazily inside ``_load_frontmatter`` only, so importing
  this module never requires PyYAML.
* Every text artifact runs the always-on hard-security group
  (``_no_placeholder_leak``, ``_no_secret_leak``, ``_no_broken_reference``,
  ``_no_external_error_text``).
* Module-specific structure assertions run only when ``module`` matches.
* Results are returned sorted by ``(artifact, name)`` — deterministic order.

The public contract (imported by other modules) is ``AssertionResult`` and
``run_assertions`` — match their signatures EXACTLY.
"""

from __future__ import annotations

import csv
import dataclasses
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class AssertionResult:
    """Outcome of a single formalized artifact assertion."""

    name: str  # assertion id, e.g. "_no_placeholder_leak"
    passed: bool
    issue: str  # source reference, e.g. "e2e#44"
    severity: str  # "P0" (hard/security) | "P1" (quality/structure)
    module: str  # "opp" | "ol" | "orf" | "suite"
    artifact: str  # file name (basename) the assertion ran on
    detail: str  # human-readable one-liner (what failed / clean)

    def to_dict(self) -> dict[str, Any]:
        """dataclasses.asdict shape — the shape report/engine modules read."""
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# Regexes shared across assertions
# ---------------------------------------------------------------------------

# _No ..._ empty-state markers (AutoInfo's _PLACEHOLDER shape: "_No <text>_").
_PLACEHOLDER_EMPTY = re.compile(r"_No [^_]+_")

# Standalone filler tokens as a whole table cell or list item.
_PLACEHOLDER_TOKEN = re.compile(
    r"^(?:n/?a|tbd|tba|tbc|none|not available|not provided|not specified|"
    r"not disclosed|no data(?: available)?|no content(?: provided)?|"
    r"to be determined|to be announced|to be confirmed)[.,;:]*$",
    re.IGNORECASE,
)
_LIST_MARKER = re.compile(r"^[-*•]?\s*(?:\[\s*[ xX]\s*\])?\s*")

# Mustache template braces.
_MUSTACHE = re.compile(r"\{\{[^}]*\}\}")

# Skeleton echoes like <finding 1> / <translation of ...>.
_SKELETON_ECHO = re.compile(r"<[a-z][a-z0-9 _-]+>", re.IGNORECASE)

# Unresolved OL shield markers: [OL:TYPE:NNNN] (e.g. [OL:CODE:0000]).
_SHIELD_MARKER = re.compile(r"\[OL:[A-Z]+:\d{4}\]")

# Credential shapes: sk- (OpenAI), AIza (Google), AKIA (AWS key id),
# ghp_/gho_/github_pat_ (GitHub), PEM private-key headers, api_key=... values.
_KEY_SHAPES = re.compile(
    r"\bsk-[A-Za-z0-9]{16,}|"
    r"\bAIza[0-9A-Za-z_-]{20,}|"
    r"\bAKIA[0-9A-Z]{16}|"
    r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|"
    r"\bghp_[A-Za-z0-9]{30,}|"
    r"\bapi[_-]?key[=:][\"']?[A-Za-z0-9_\-]{16,}"
)
# Unresolved env refs as VALUES: ${OPENAI_API_KEY}-style. Flagged anywhere in
# the body except a YAML frontmatter key-definition line (``api_key: ${X}``).
_ENV_REF = re.compile(r"\$\{[A-Z][A-Z0-9_]{2,}\}")

# External-lib error / LLM leakage.
_TRACEBACK = re.compile(r"Traceback \(most recent call last\)")
_LITELLM = re.compile(r"litellm|BerriAI|Give Feedback", re.IGNORECASE)
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_EXT_ERROR = re.compile(
    r"Internal Server Error|TimeoutError|openai\.|"
    r"zhipu|bigmodel\.cn|HTTP 5\d\d|"
    r"\b(?:429|500|502|503)\b",
    re.IGNORECASE,
)

# SRT cue timecode line: 00:00:01,000 --> 00:00:04,000
_SRT_TIMECODE = re.compile(
    r"^\s*\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}\s*$",
    re.MULTILINE,
)

# Plausible markdown link / image / html href targets.
_LINK_PLAUSIBLE = re.compile(
    r"^(?:https?://|/|#|\./|\.\./|mailto:)", re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Hard-security group — runs for EVERY module, always
# ---------------------------------------------------------------------------


def _iter_cells(line: str) -> list[str]:
    """Split one stripped line into table cells (markdown row) or itself."""
    if line.startswith("|"):
        return [c.strip() for c in line.strip("|").split("|")]
    return [line]


def _no_placeholder_leak(
    path: Path, text: str, artifact: str, module: str
) -> AssertionResult:
    """e2e#44 (P0) — no unresolved placeholders in the artifact body:
    ``_No ..._`` empty-state markers, ``{{...}}`` mustache, skeleton echoes
    (``<finding 1>``), standalone TODO/TBD/N-A/Not available/To be
    determined as a whole table cell or list item, or leftover
    ``[OL:TYPE:NNNN]`` shield markers.  Skeleton-echo ``<tag>`` detection is
    skipped for ``.html``/``.htm``/``.xml``/``.xlf`` artifacts — there
    ``<head>``, ``<body>``, ``<source>``, ``<target>``, ``<document>`` are
    legitimate markup, not echoes."""
    found: list[str] = []
    for m in _PLACEHOLDER_EMPTY.finditer(text):
        found.append(m.group(0))
    for m in _MUSTACHE.finditer(text):
        found.append(m.group(0))
    if artifact.lower().endswith((".html", ".htm", ".xml", ".xlf")):
        pass  # real markup, not skeleton echoes
    else:
        for m in _SKELETON_ECHO.finditer(text):
            found.append(m.group(0))
    for m in _SHIELD_MARKER.finditer(text):
        found.append(m.group(0))
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        for cell in _iter_cells(line):
            cell = _LIST_MARKER.sub("", cell).strip()
            if cell and _PLACEHOLDER_TOKEN.match(cell):
                found.append(cell)
    seen = list(dict.fromkeys(found))
    return AssertionResult(
        "_no_placeholder_leak", not seen, "e2e#44", "P0", module, artifact,
        "placeholders=" + ", ".join(seen) if seen else "clean",
    )


def _no_secret_leak(
    path: Path, text: str, artifact: str, module: str
) -> AssertionResult:
    """e2e#44 (P0) — the artifact leaks credential shapes: ``sk-``/``AIza``/
    ``AKIA``/``ghp_`` API-key prefixes, PEM private-key headers,
    ``api_key=...`` values, or unresolved ``${OPENAI_API_KEY}``-style env
    refs appearing as values (lenient: a YAML frontmatter key-definition
    line such as ``api_key: ${X}`` is excluded)."""
    bad: list[str] = []
    for m in _KEY_SHAPES.finditer(text):
        bad.append(m.group(0)[:24] + "...")
    for m in _ENV_REF.finditer(text):
        line = text[: m.start()].rsplit("\n", 1)[-1]
        stripped = line.strip()
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:\s*", stripped):
            continue  # YAML frontmatter key def, not a value leak
        bad.append(m.group(0))
    seen = list(dict.fromkeys(bad))
    return AssertionResult(
        "_no_secret_leak", not seen, "e2e#44", "P0", module, artifact,
        "leak=" + ", ".join(seen) if seen else "clean",
    )


def _no_broken_reference(
    path: Path, text: str, artifact: str, module: str
) -> AssertionResult:
    """e2e#44 (P1) — no malformed markdown/image/html references: empty or
    whitespace-only targets (``[text]()``, ``![alt]()``, ``[View Source]()``,
    ``<img src=\"\">``, ``<a href=\"\">``), space-only ``]( )``, or a
    markdown link whose target is not a plausible URL/path. Relative repo
    paths like ``images/foo.png`` are NOT flagged."""
    bad: list[str] = []
    for m in re.finditer(r"!?\[[^\]]*\]\(\s*\)", text):
        bad.append("empty link target " + repr(m.group(0)[:30]))
    for m in re.finditer(r"\]\(\s+\)", text):
        bad.append("whitespace-only link target " + repr(m.group(0)[:30]))
    for m in re.finditer(r"\[View Source\]\(\s*\)", text):
        bad.append("empty [View Source]()")
    for m in re.finditer(r'<img\s+src\s*=\s*["\']\s*["\']', text, re.IGNORECASE):
        bad.append("empty <img src>")
    for m in re.finditer(r'<a\s+href\s*=\s*["\']\s*["\']', text, re.IGNORECASE):
        bad.append("empty <a href>")
    for m in re.finditer(r"!?\[[^\]]*\]\(([^)]*)\)", text):
        target = m.group(1).strip()
        if target and not _LINK_PLAUSIBLE.match(target):
            bad.append(f"implausible link target {target[:40]!r}")
    seen = list(dict.fromkeys(bad))
    return AssertionResult(
        "_no_broken_reference", not seen, "e2e#44", "P1", module, artifact,
        "broken=" + "; ".join(seen) if seen else "clean",
    )


def _no_external_error_text(
    path: Path, text: str, artifact: str, module: str
) -> AssertionResult:
    """e2e#44 (P0) — the artifact body carries no external-lib error / LLM
    leakage: Python tracebacks, litellm/BerriAI/'Give Feedback' markers,
    ANSI escape sequences, 'Internal Server Error', 'TimeoutError',
    openai./zhipu/bigmodel.cn error text, or HTTP 5xx / 429/500/502/503
    status lines in the first 2000 chars (lenient)."""
    bad: list[str] = []
    head = text[:2000]
    if _TRACEBACK.search(text):
        bad.append("traceback")
    if _LITELLM.search(text):
        bad.append("litellm/BerriAI marker")
    if _ANSI.search(head):
        bad.append("ANSI escape")
    if _EXT_ERROR.search(head):
        bad.append("external error text")
    return AssertionResult(
        "_no_external_error_text", not bad, "e2e#44", "P0", module, artifact,
        "; ".join(bad) if bad else "clean",
    )


# ---------------------------------------------------------------------------
# opp — OPP extraction structure assertions
# ---------------------------------------------------------------------------


def _md_nonempty(path: Path, text: str, artifact: str, module: str) -> AssertionResult:
    """opp (P1) — a ``.md`` artifact has >= 1 non-blank line and >= 1
    non-marker line (not only ``<!-- ... -->`` comments / frontmatter)."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return AssertionResult(
            "_md_nonempty", False, "opp", "P1", module, artifact,
            "empty markdown (no non-blank lines)",
        )
    marker_only = all(
        ln.strip().startswith("<!--") or ln.strip() == "---"
        for ln in lines
    )
    return AssertionResult(
        "_md_nonempty", not marker_only, "opp", "P1", module, artifact,
        f"{len(lines)} non-blank lines"
        + (" (all markers/comments)" if marker_only else ""),
    )


def _manifest_json_parseable(
    path: Path, text: str, artifact: str, module: str
) -> AssertionResult:
    """opp (P1) — ``*_manifest.json`` / ``.json`` parses with json.loads; a
    manifest carrying ``source.file_path``/``source.format``/``extraction.
    outputs`` keys must have them present and non-empty (structure check).
    A non-manifest ``.json`` must still parse."""
    try:
        data = json.loads(text)
    except ValueError as exc:
        return AssertionResult(
            "_manifest_json_parseable", False, "opp", "P1", module, artifact,
            f"invalid JSON: {exc}",
        )
    if not isinstance(data, dict) or "_manifest" not in artifact:
        return AssertionResult(
            "_manifest_json_parseable", True, "opp", "P1", module, artifact,
            "valid JSON",
        )
    missing = []
    for key in ("file_path", "format"):
        if not data.get("source", {}).get(key):
            missing.append(f"source.{key}")
    if not data.get("extraction", {}).get("outputs"):
        missing.append("extraction.outputs")
    return AssertionResult(
        "_manifest_json_parseable", not missing, "opp", "P1", module, artifact,
        "manifest structure ok" if not missing else "missing: " + ", ".join(missing),
    )


def _csv_structure(path: Path, text: str, artifact: str, module: str) -> AssertionResult:
    """opp (P1) — ``.csv`` parses with csv.reader, has >= 1 header row and
    >= 1 data row, and rows have consistent column counts."""
    try:
        rows = list(csv.reader(text.splitlines()))
    except csv.Error as exc:
        return AssertionResult(
            "_csv_structure", False, "opp", "P1", module, artifact,
            f"csv parse error: {exc}",
        )
    if not rows:
        return AssertionResult(
            "_csv_structure", False, "opp", "P1", module, artifact,
            "empty csv",
        )
    widths = {len(r) for r in rows if r}
    ok = len(rows) >= 2 and len(widths) == 1 and 0 not in widths
    return AssertionResult(
        "_csv_structure", ok, "opp", "P1", module, artifact,
        f"{len(rows)} rows x {sorted(widths)} cols" if ok
        else f"bad structure: {len(rows)} rows, widths={sorted(widths)}",
    )


def _html_no_tag_leak(path: Path, text: str, artifact: str, module: str) -> AssertionResult:
    """OPP#36 (P1) — an OPP-produced ``.md`` derived from html must not leak
    raw ``<html``/``<body`` tags into the markdown body (html→md extraction
    should convert, not leak raw tags)."""
    if artifact.endswith(".md") and re.search(r"<(?:html|body)\b", text, re.IGNORECASE):
        return AssertionResult(
            "_html_no_tag_leak", False, "OPP#36", "P1", module, artifact,
            "raw <html>/<body> tag leaked into markdown",
        )
    return AssertionResult(
        "_html_no_tag_leak", True, "OPP#36", "P1", module, artifact,
        "no html/body tag leak" if artifact.endswith(".md") else "not a .md artifact",
    )


# ---------------------------------------------------------------------------
# ol — OL translation structure assertions
# ---------------------------------------------------------------------------


def _load_frontmatter(text: str) -> dict[str, Any]:
    """Parse leading YAML frontmatter (``---\\n...\\n---``) lazily (PyYAML);
    returns {} when absent or unparseable. No PyYAML at import time."""
    if not (text.startswith("---\n") or text.startswith("---\r\n")):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    try:
        import yaml  # local import: PyYAML is a soft runtime dep only

        data = yaml.safe_load(text[4:end])
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _target_complete(path: Path, text: str, artifact: str, module: str) -> AssertionResult:
    """ol (P1) — a translated artifact is non-empty AND (if it has YAML
    frontmatter) ``target_lang`` is declared; an ``.xlf`` must have every
    ``<trans-unit>`` with a non-empty ``<target>`` (or no trans-units)."""
    if artifact.endswith(".xlf"):
        units = re.findall(
            r"<trans-unit\b[^>]*>(.*?)</trans-unit>", text, re.DOTALL
        )
        if not units:
            return AssertionResult(
                "_target_complete", True, "ol", "P1", module, artifact,
                "no <trans-unit> elements",
            )
        empty = [
            i for i, u in enumerate(units, 1)
            if not re.search(r"<target(?:\s[^>]*)?>\s*[^<\s]", u, re.DOTALL)
        ]
        return AssertionResult(
            "_target_complete", not empty, "ol", "P1", module, artifact,
            f"all {len(units)} trans-units have targets" if not empty
            else f"{len(empty)}/{len(units)} trans-units have empty targets",
        )
    if not text.strip():
        return AssertionResult(
            "_target_complete", False, "ol", "P1", module, artifact,
            "empty translated artifact",
        )
    fm = _load_frontmatter(text)
    if not fm:
        return AssertionResult(
            "_target_complete", True, "ol", "P1", module, artifact,
            "non-empty, no frontmatter",
        )
    declared = bool(fm.get("target_lang"))
    return AssertionResult(
        "_target_complete", declared, "ol", "P1", module, artifact,
        f"target_lang={fm.get('target_lang')!r}" if declared
        else "frontmatter present but target_lang missing",
    )


def _no_source_echo(path: Path, text: str, artifact: str, module: str) -> AssertionResult:
    """ol (P1) — a translated artifact does not dump the source verbatim as
    the target: an ``.xlf`` with ``<target>`` == ``<source>`` for more than
    half its trans-units, OR an ``.md`` whose frontmatter declares identical
    ``source_lang``/``target_lang`` (self-translation)."""
    if artifact.endswith(".xlf"):
        pairs = re.findall(
            r"<source(?:\s[^>]*)?>(.*?)</source>.*?<target(?:\s[^>]*)?>(.*?)</target>",
            text, re.DOTALL,
        )
        if not pairs:
            return AssertionResult(
                "_no_source_echo", True, "ol", "P1", module, artifact,
                "no source/target pairs",
            )
        echoed = sum(1 for s, t in pairs if s.strip() == t.strip())
        ok = echoed <= len(pairs) / 2
        return AssertionResult(
            "_no_source_echo", ok, "ol", "P1", module, artifact,
            f"{echoed}/{len(pairs)} units echo source",
        )
    fm = _load_frontmatter(text)
    if fm and fm.get("source_lang") and fm.get("source_lang") == fm.get("target_lang"):
        return AssertionResult(
            "_no_source_echo", False, "ol", "P1", module, artifact,
            f"self-translation: source_lang == target_lang == {fm['source_lang']!r}",
        )
    return AssertionResult(
        "_no_source_echo", True, "ol", "P1", module, artifact,
        "no source echo",
    )


def _shield_roundtrip(path: Path, text: str, artifact: str, module: str) -> AssertionResult:
    """E2E-77/78 (P1) — an OL ``.md`` output contains NO leftover
    ``[OL:TYPE:NNNN]`` shield markers (module-specific stricter check on top
    of the P0 placeholder leak)."""
    markers = _SHIELD_MARKER.findall(text)
    return AssertionResult(
        "_shield_roundtrip", not markers, "E2E-77/78", "P1", module, artifact,
        f"leftover shield markers: {markers[:5]}" if markers else "no [OL:...] markers",
    )


# ---------------------------------------------------------------------------
# orf — ORF backfill structure assertions
# ---------------------------------------------------------------------------


def _srt_timecodes(path: Path, text: str, artifact: str, module: str) -> AssertionResult:
    """orf (P1) — an ``.srt`` with cues has >= 1 cue carrying a valid
    ``HH:MM:SS,mmm --> HH:MM:SS,mmm`` timecode line. An SRT passthrough with
    no timecode arrows at all (STANDARDS.md#srt-structure: non-empty MD
    passthrough when the input has no timing blocks) is NOT a failure — only
    a cue WITH an arrow must be well-formed."""
    cues = re.split(r"\n\s*\n", text.strip())
    timed_cues = [c for c in cues if "-->" in c]
    if not timed_cues:
        return AssertionResult(
            "_srt_timecodes", True, "orf", "P1", module, artifact,
            "no timecode cues (non-empty passthrough)",
        )
    ok = any(_SRT_TIMECODE.search(c) for c in timed_cues)
    return AssertionResult(
        "_srt_timecodes", ok, "orf", "P1", module, artifact,
        f"{len(timed_cues)} cue(s), {'valid' if ok else 'malformed'} timecodes",
    )


def _html_has_structure(path: Path, text: str, artifact: str, module: str) -> AssertionResult:
    """orf (P1) — an ``.html`` is non-empty and contains ``<html`` + ``<body``
    (or ``<DOCTYPE`` plus a top-level element)."""
    if not text.strip():
        return AssertionResult(
            "_html_has_structure", False, "orf", "P1", module, artifact,
            "empty html",
        )
    has_doctype = bool(re.search(r"<!DOCTYPE\b", text[:500], re.IGNORECASE))
    ok = (
        re.search(r"<html\b", text, re.IGNORECASE)
        and re.search(r"<body\b", text, re.IGNORECASE)
    ) or (
        has_doctype
        and re.search(r"<[a-z][a-z0-9]*\b[^>]*>", text[500:], re.IGNORECASE)
    )
    return AssertionResult(
        "_html_has_structure", ok, "orf", "P1", module, artifact,
        "html structure ok" if ok else "missing <html>/<body> or DOCTYPE+element",
    )


def _json_parseable(path: Path, text: str, artifact: str, module: str) -> AssertionResult:
    """orf (P1) — ``.json`` parses with json.loads."""
    try:
        json.loads(text)
    except ValueError as exc:
        return AssertionResult(
            "_json_parseable", False, "orf", "P1", module, artifact,
            f"invalid JSON: {exc}",
        )
    return AssertionResult(
        "_json_parseable", True, "orf", "P1", module, artifact, "valid JSON",
    )


def _xml_parseable(path: Path, text: str, artifact: str, module: str) -> AssertionResult:
    """orf (P1) — ``.xml`` parses with xml.etree.ElementTree."""
    try:
        ET.fromstring(text)
    except ET.ParseError as exc:
        return AssertionResult(
            "_xml_parseable", False, "orf", "P1", module, artifact,
            f"invalid XML: {exc}",
        )
    return AssertionResult(
        "_xml_parseable", True, "orf", "P1", module, artifact, "valid XML",
    )


def _docx_pptx_zip_ok(path: Path, text: str, artifact: str, module: str) -> AssertionResult:
    """orf (P1) — ``.docx``/``.pptx`` open as zipfile.ZipFile without error
    (OOXML structure integrity). ``text`` carries the raw bytes for binary
    artifacts (``run_assertions`` passes bytes when the file is not
    text-decodable)."""
    raw = text.encode("utf-8", errors="surrogateescape") if isinstance(text, str) else text
    try:
        with zipfile.ZipFile(Path(path)) as zf:
            names = zf.namelist()
    except (zipfile.BadZipFile, OSError) as exc:
        return AssertionResult(
            "_docx_pptx_zip_ok", False, "orf", "P1", module, artifact,
            f"not a valid zip: {exc}",
        )
    ok = bool(names)
    return AssertionResult(
        "_docx_pptx_zip_ok", ok, "orf", "P1", module, artifact,
        f"valid zip, {len(names)} entries" if ok else "empty zip",
    )


# ---------------------------------------------------------------------------
# Assertion tables + dispatch
# ---------------------------------------------------------------------------

AssertionFn = Callable[[Path, str, str, str], AssertionResult]

HARD_SECURITY: tuple[AssertionFn, ...] = (
    _no_placeholder_leak,
    _no_secret_leak,
    _no_broken_reference,
    _no_external_error_text,
)

# opp structure assertions, keyed by artifact extension.
OPP_STRUCTURE: dict[str, tuple[AssertionFn, ...]] = {
    ".md": (_md_nonempty, _html_no_tag_leak),
    ".json": (_manifest_json_parseable,),
    ".csv": (_csv_structure,),
}

# ol structure assertions: apply to translated md/xlf artifacts.
OL_STRUCTURE: tuple[AssertionFn, ...] = (
    _target_complete,
    _no_source_echo,
    _shield_roundtrip,
)

# orf structure assertions, keyed by artifact extension.
ORF_STRUCTURE: dict[str, tuple[AssertionFn, ...]] = {
    ".html": (_html_has_structure,),
    ".htm": (_html_has_structure,),
    ".srt": (_srt_timecodes,),
    ".json": (_json_parseable,),
    ".xml": (_xml_parseable,),
    ".docx": (_docx_pptx_zip_ok,),
    ".pptx": (_docx_pptx_zip_ok,),
}

# Noise files / dirs excluded from the artifact scan.
_NOISE_NAMES = {".DS_Store", "Thumbs.db", ".gitkeep"}
_NOISE_SUFFIXES = {".pyc", ".pyo"}
_NOISE_DIR_PARTS = {"__pycache__", ".git", ".venv", ".venv_ol", ".mypy_cache"}

# Extensions read as text (utf-8, errors="replace"); everything else is read
# as bytes (binary docx/pptx for the zip check).
_TEXT_EXTS = {
    ".md", ".txt", ".json", ".csv", ".html", ".htm", ".xml", ".xlf",
    ".srt", ".yaml", ".yml", ".eml",
}


def _read_artifact(path: Path) -> str | bytes:
    """Read an artifact: utf-8 text with errors='replace' for text formats,
    raw bytes for binary formats."""
    if path.suffix.lower() in _TEXT_EXTS:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
    try:
        return path.read_bytes()
    except OSError:
        return b""


def _structure_groups(module: str, artifact: str) -> list[tuple[AssertionFn, ...]]:
    """Which structure groups apply to ``artifact`` under ``module``.

    * ``module == "suite"`` → [] (hard-security only).
    * ``module`` in {"opp", "orf"} → that module's per-extension set.
    * ``module == "ol"`` → the OL set for translated md/xlf artifacts.
    * ``module == "all"`` → every group whose extension the artifact matches
      (a ``.json`` gets the opp manifest/json check AND the orf json check;
      an ``.md`` gets the opp md checks AND the ol checks).
    """
    lower = artifact.lower()
    ext = Path(lower).suffix
    if module == "opp":
        return [OPP_STRUCTURE[ext]] if ext in OPP_STRUCTURE else []
    if module == "orf":
        return [ORF_STRUCTURE[ext]] if ext in ORF_STRUCTURE else []
    if module == "ol":
        if ext in (".md", ".xlf"):
            return [OL_STRUCTURE]
        return []
    if module == "all":
        groups: list[tuple[AssertionFn, ...]] = []
        if ext in OPP_STRUCTURE:
            groups.append(OPP_STRUCTURE[ext])
        if ext in (".md", ".xlf"):
            groups.append(OL_STRUCTURE)
        if ext in ORF_STRUCTURE:
            groups.append(ORF_STRUCTURE[ext])
        return groups
    return []  # unknown module → hard-security only (like "suite")


def run_assertions(
    artifacts_dir: str | Path, module: str = "suite"
) -> list[AssertionResult]:
    """Scan ``artifacts_dir`` for produced files and run the assertion groups:
    the module's structure assertions + the always-on hard-security group.

    Deterministic, no LLM, no network, no subprocess. Returns every result
    (pass AND fail) in deterministic order (sorted by artifact then name).

    Dispatch rules:
      * glob ``**/*.*`` (recursive), excluding dot-dirs and common noise
        (``.DS_Store``, ``__pycache__``, ``*.pyc``);
      * the hard-security group runs on every TEXT artifact (every module);
      * the module's structure assertions run only when ``module`` matches
        that module's prefix (opp→opp set, ol→ol set, orf→orf set,
        suite→hard-security only);
      * ``module="all"`` runs all three structure sets, each artifact going
        through the groups whose extension it matches.
    """
    root = Path(artifacts_dir)
    results: list[AssertionResult] = []
    if not root.is_dir():
        return results

    files: list[Path] = []
    for p in root.rglob("*.*"):
        if p.is_dir():
            continue
        rel = p.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if any(part in _NOISE_DIR_PARTS for part in rel.parts):
            continue
        if p.name in _NOISE_NAMES or p.suffix.lower() in _NOISE_SUFFIXES:
            continue
        files.append(p)
    files.sort(key=lambda p: str(p.relative_to(root)))

    for p in files:
        artifact = p.name
        ext = p.suffix.lower()
        raw = _read_artifact(p)

        # Hard-security group on every text artifact (binary docx/pptx carry
        # no readable text body for these checks).
        if isinstance(raw, str) and ext in _TEXT_EXTS:
            for fn in HARD_SECURITY:
                results.append(fn(p, raw, artifact, module))

        # Module structure assertions.
        for group in _structure_groups(module, artifact):
            for fn in group:
                results.append(fn(p, raw, artifact, module))

    # Deterministic order: (artifact, name).
    results.sort(key=lambda r: (r.artifact, r.name))
    return results
