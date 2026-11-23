"""Per-format paragraph counting for translated_fidelity.

Why not text heuristics
-----------------------
Splitting extracted text on newlines inflates counts for any format that wraps
lines (odt 36 -> 233, pdf 36 -> 885), and splitting on blank lines collapses
documents whose extractor emits no blank lines (docx 36 -> 3). Neither is
usable, because the structure score divides output by source: a wrong
denominator makes every ratio meaningless in both directions.

Each format exposes paragraph structure natively. Use that:

| format | source of truth |
|---|---|
| docx | python-docx `doc.paragraphs` |
| odt / epub | XHTML `<p>` elements |
| html | `<p>` elements |
| pdf | pymupdf text blocks |
| md | physical lines (this IS the structure for md) |
| rtf | `\\par` delimited |
| other | None (unmeasurable — caller must not score it) |
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

# Namespace-agnostic: ODT serialises paragraphs as <text:p>, EPUB as <p>,
# both must match. A bare r"<p\b" silently misses every ODT paragraph.
_P_TAG = re.compile(r"<(?:\w+:)?p\b[^>]*>(.*?)</(?:\w+:)?p>", re.DOTALL | re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_TABLE_ROW_START = "|"


def _clean(text: str) -> str:
    """Strip tags/entities and collapse whitespace."""
    text = _TAG.sub(" ", text or "")
    text = (
        text.replace("&nbsp;", " ").replace("&amp;", "&")
        .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    )
    return re.sub(r"\s+", " ", text).strip()


def _from_docx(path: Path) -> list[str] | None:
    try:
        import docx  # python-docx
    except ImportError:
        return None
    try:
        doc = docx.Document(str(path))
    except Exception:  # noqa: BLE001 - corrupt/foreign docx: unmeasurable
        return None
    out = []
    for para in doc.paragraphs:
        text = (para.text or "").strip()
        if text:
            out.append(text)
    return out


def _from_xhtml(path: Path, member_suffixes: tuple[str, ...], member: str | None) -> list[str] | None:
    try:
        with zipfile.ZipFile(path) as z:
            names = [member] if member else [
                n for n in z.namelist() if n.lower().endswith(member_suffixes)
            ]
            out = []
            for name in names:
                html = z.read(name).decode("utf-8", "replace")
                for raw in _P_TAG.findall(html):
                    text = _clean(raw)
                    if text:
                        out.append(text)
            return out
    except (zipfile.BadZipFile, OSError, KeyError):
        return None


def _from_html(path: Path) -> list[str] | None:
    try:
        html = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    out = []
    for raw in _P_TAG.findall(html):
        text = _clean(raw)
        if text:
            out.append(text)
    return out or None


def _from_pdf(path: Path) -> list[str] | None:
    try:
        import pymupdf  # 1.24+
    except ImportError:
        try:
            import fitz as pymupdf  # older name
        except ImportError:
            return None
    try:
        doc = pymupdf.open(str(path))
    except Exception:  # noqa: BLE001 - unreadable pdf: unmeasurable
        return None
    out = []
    for page in doc:
        for block in page.get_text("blocks"):
            # blocks: (x0, y0, x1, y1, text, block_no, block_type)
            text = (block[4] or "").strip() if len(block) > 4 else ""
            if text and not text.startswith(_TABLE_ROW_START):
                out.append(re.sub(r"\s+", " ", text))
    doc.close()
    return out


def _from_rtf(path: Path) -> list[str] | None:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    # \par ends a paragraph; drop control words and braces.
    raw = re.sub(r"\\[a-z]+-?\d*\s?", " ", raw)
    raw = raw.replace("{", " ").replace("}", " ")
    out = [p.strip() for p in re.split(r"\\par|\\\n", raw) if p.strip()]
    out = [re.sub(r"\s+", " ", p) for p in out]
    return [p for p in out if p] or None


def _from_markdown(text: str) -> list[str]:
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(_TABLE_ROW_START) or line.startswith("#"):
            continue
        line = re.sub(r"^[-*+]\s+", "", line).strip()
        if line:
            out.append(line)
    return out


def paragraphs_for(path: Path, fallback_text: str = "") -> list[str] | None:
    """Paragraph-level blocks for ``path``, or None when unmeasurable.

    None means "this format's paragraph structure is not obtainable here" and
    the caller MUST exclude the dimension rather than score it as 0.
    """
    if not path.exists():
        return []
    suffix = path.suffix.lower().lstrip(".")
    if suffix == "docx":
        return _from_docx(path)
    if suffix == "odt":
        return _from_xhtml(path, (".xml",), "content.xml")
    if suffix == "epub":
        return _from_xhtml(path, (".xhtml", ".html", ".htm"), None)
    if suffix in ("html", "htm"):
        return _from_html(path)
    if suffix == "pdf":
        return _from_pdf(path)
    if suffix == "rtf":
        return _from_rtf(path)
    if suffix in ("md", "markdown", "txt"):
        return _from_markdown(path.read_text(encoding="utf-8", errors="replace"))
    if fallback_text:
        return _from_markdown(fallback_text)
    return None
