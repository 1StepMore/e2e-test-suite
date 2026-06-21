"""Content fidelity checker for the format matrix.

Compares source and output documents by extracting text, tables, and image
counts, then computing preservation scores. Used by the matrix verifier
to distinguish "output exists" from "output preserves content".
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FidelityReport:
    """Fidelity comparison between a source and its processed output."""
    text_score: float = 0.0      # 0-1: fraction of source words present in output
    table_score: float = 0.0     # 0-1: table count and dimension similarity
    image_score: float = 0.0     # 0-1: image count similarity
    source_words: int = 0
    output_words: int = 0
    source_tables: int = 0
    output_tables: int = 0
    source_images: int = 0
    output_images: int = 0
    overall: float = 0.0         # weighted average
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text_score": round(self.text_score, 3),
            "table_score": round(self.table_score, 3),
            "image_score": round(self.image_score, 3),
            "overall": round(self.overall, 3),
            "source_words": self.source_words,
            "output_words": self.output_words,
            "source_tables": self.source_tables,
            "output_tables": self.output_tables,
            "source_images": self.source_images,
            "output_images": self.output_images,
            "notes": self.notes,
        }

    def passes(self, threshold: float = 0.70) -> bool:
        """A cell passes fidelity if overall score >= threshold."""
        return self.overall >= threshold


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _normalize_text(text: str) -> list[str]:
    """Lowercase, strip punctuation, split on whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return [t for t in text.split() if t]


def _extract_text(path: Path) -> str:
    """Extract plain text from DOCX, PPTX, XLSX, PDF, HTML, or MD."""
    if not path.exists():
        return ""
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _extract_docx_text(path)
    if suffix == ".pptx":
        return _extract_pptx_text(path)
    if suffix == ".xlsx":
        return _extract_xlsx_text(path)
    if suffix == ".pdf":
        return _extract_pdf_text(path)
    if suffix in (".html", ".htm"):
        return _extract_html_text(path)
    if suffix in (".md", ".markdown"):
        return _extract_md_text(path)
    return path.read_text(encoding="utf-8", errors="ignore")


def _extract_docx_text(path: Path) -> str:
    from docx import Document
    d = Document(str(path))
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)


def _extract_pptx_text(path: Path) -> str:
    from pptx import Presentation
    p = Presentation(str(path))
    parts = []
    for slide in p.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    parts.append(para.text)
            if shape.has_table:
                for row in shape.table.rows:
                    for cell in row.cells:
                        parts.append(cell.text)
    return "\n".join(parts)


def _extract_xlsx_text(path: Path) -> str:
    from openpyxl import load_workbook
    wb = load_workbook(str(path), data_only=True, read_only=True)
    parts = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            for v in row:
                if v is not None:
                    parts.append(str(v))
    wb.close()
    return "\n".join(parts)


def _extract_pdf_text(path: Path) -> str:
    """Best-effort PDF text extraction. Tries pypdf, then pdfplumber, then raw."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except ImportError:
        pass
    try:
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages)
    except ImportError:
        pass
    # Fallback: read raw (will be binary garbage but gives us SOMETHING)
    return path.read_bytes().decode("utf-8", errors="ignore")


def _extract_html_text(path: Path) -> str:
    """Strip HTML tags to get plain text."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL)
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return text


def _extract_md_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"!?\[.*?\]\(.*?\)", " ", text)
    text = re.sub(r"[#*_>`]", " ", text)
    return text


# ---------------------------------------------------------------------------
# Structure counters
# ---------------------------------------------------------------------------

def _count_docx_tables(path: Path) -> int:
    from docx import Document
    return len(Document(str(path)).tables)


def _count_pptx_tables(path: Path) -> int:
    from pptx import Presentation
    p = Presentation(str(path))
    return sum(1 for s in p.slides for sh in s.shapes if sh.has_table)


def _count_xlsx_sheets(path: Path) -> int:
    from openpyxl import load_workbook
    return len(load_workbook(str(path), read_only=True).sheetnames)


def _count_pdf_tables(path: Path) -> int:
    try:
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            return sum(len(p.find_tables()) for p in pdf.pages)
    except ImportError:
        return 0


def _count_html_tables(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return len(re.findall(r"<table[\s>]", text, re.IGNORECASE))


def _count_md_tables(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    return sum(
        1 for i, line in enumerate(lines)
        if line.strip().startswith("|") and i + 1 < len(lines)
        and re.match(r"^\s*\|[\s\-:|]+\|", lines[i + 1])
    )


def _count_tables(path: Path) -> int:
    if not path.exists():
        return 0
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _count_docx_tables(path)
    if suffix == ".pptx":
        return _count_pptx_tables(path)
    if suffix == ".xlsx":
        return _count_xlsx_sheets(path)
    if suffix == ".pdf":
        return _count_pdf_tables(path)
    if suffix in (".html", ".htm"):
        return _count_html_tables(path)
    if suffix in (".md", ".markdown"):
        return _count_md_tables(path)
    return 0


def _count_images(path: Path) -> int:
    """Count embedded images by inspecting the file (ZIP-based for Office formats)."""
    if not path.exists():
        return 0
    suffix = path.suffix.lower()
    if suffix in (".docx", ".pptx", ".xlsx"):
        try:
            with zipfile.ZipFile(path) as zf:
                return sum(
                    1 for n in zf.namelist()
                    if n.startswith("word/media/") or n.startswith("ppt/media/")
                    or n.startswith("xl/media/")
                )
        except (zipfile.BadZipFile, OSError):
            return 0
    if suffix in (".html", ".htm"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        return len(re.findall(r"<img[\s>]", text, re.IGNORECASE))
    return 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_fidelity(
    source: Path,
    output: Path,
    output_format: str,
) -> FidelityReport:
    """Compare source and output for text/table/image preservation."""
    r = FidelityReport()

    src_text = _extract_text(source)
    out_text = _extract_text(output) if output.exists() else ""

    src_words = _normalize_text(src_text)
    out_words = _normalize_text(out_text)
    r.source_words = len(src_words)
    r.output_words = len(out_words)

    if src_words:
        out_set = set(out_words)
        matched = sum(1 for w in src_words if w in out_set)
        r.text_score = matched / len(src_words)
    else:
        r.text_score = 1.0

    r.source_tables = _count_tables(source)
    r.output_tables = _count_tables(output) if output.exists() else 0
    if r.source_tables:
        r.table_score = min(r.output_tables, r.source_tables) / r.source_tables
    else:
        r.table_score = 1.0

    r.source_images = _count_images(source)
    r.output_images = _count_images(output) if output.exists() else 0
    if r.source_images:
        r.image_score = min(r.output_images, r.source_images) / r.source_images
    else:
        r.image_score = 1.0

    r.overall = 0.6 * r.text_score + 0.25 * r.table_score + 0.15 * r.image_score

    if not output.exists():
        r.notes.append("output file missing")
    if r.source_words > 0 and r.output_words == 0:
        r.notes.append("output has no extractable text")
    if r.source_tables > 0 and r.output_tables == 0:
        r.notes.append("output has no tables")
    if r.source_images > 0 and r.output_images == 0:
        r.notes.append("output has no images")

    return r
