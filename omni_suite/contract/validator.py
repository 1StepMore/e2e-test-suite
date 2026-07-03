"""Validate actual pipeline outputs against the TranslationDocument contract."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from omni_suite.contract.models import DocumentFormat, TranslationDocument

# Map OPP/ORF format strings to DocumentFormat enum
FORMAT_STRING_MAP = {
    "docx": DocumentFormat.DOCX,
    "pptx": DocumentFormat.PPTX,
    "pdf": DocumentFormat.PDF,
    "epub": DocumentFormat.EPUB,
    "html": DocumentFormat.HTML,
    "md": DocumentFormat.MD,
    "markdown": DocumentFormat.MD,
    "xlf": DocumentFormat.XLIFF,
    "xliff": DocumentFormat.XLIFF,
}


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    frontmatter_text = parts[1].strip()
    body = parts[2].strip()
    # Simple key: value parsing (no YAML lib dependency)
    fm: dict[str, Any] = {}
    for line in frontmatter_text.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip().strip('"').strip("'")
    return fm, body


def _parse_segments(body: str) -> list[dict[str, Any]]:
    """Extract segments from markdown body (one segment per paragraph)."""
    segments = []
    for i, para in enumerate(body.split("\n\n")):
        para = para.strip()
        if para and not para.startswith("#"):
            segments.append({"id": str(i), "source": para})
    return segments


def validate_md_output(
    md_path: Path,
    source_lang: str,
    target_lang: str,
) -> TranslationDocument | None:
    """Validate an MD file produced by OPP.

    Returns a TranslationDocument on success, None on failure.
    """
    try:
        content = md_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    frontmatter, body = _parse_frontmatter(content)
    format_str = frontmatter.get("format", "md").lower()
    fmt = FORMAT_STRING_MAP.get(format_str)
    if fmt is None:
        return None

    segments_data = _parse_segments(body)
    segments = [{"id": s["id"], "source": s["source"]} for s in segments_data]

    try:
        return TranslationDocument(
            format_type=fmt,
            pipeline_path="md",
            source_lang=frontmatter.get("source_lang", source_lang),
            target_lang=frontmatter.get("target_lang", target_lang),
            metadata=frontmatter,
            segments=segments,
        )
    except Exception:
        return None


def validate_xliff_output(
    xliff_path: Path,
    source_lang: str,
    target_lang: str,
) -> TranslationDocument | None:
    """Validate an XLIFF file produced by OPP/OL.

    Returns a TranslationDocument on success, None on failure.
    """
    try:
        content = xliff_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    # Basic XLIFF 1.2 detection
    if "<xliff" not in content:
        return None

    # Count <trans-unit> elements
    trans_unit_count = content.count("<trans-unit")

    # Try to extract source-language and target-language from <file> tag
    src_match = re.search(r'source-language="([^"]+)"', content)
    tgt_match = re.search(r'target-language="([^"]+)"', content)

    fmt = DocumentFormat.XLIFF
    segments = [
        {"id": str(i), "source": f"<trans-unit #{i}>"}
        for i in range(trans_unit_count)
    ]

    try:
        return TranslationDocument(
            format_type=fmt,
            pipeline_path="xliff",
            source_lang=src_match.group(1) if src_match else source_lang,
            target_lang=tgt_match.group(1) if tgt_match else target_lang,
            metadata={"trans_unit_count": trans_unit_count},
            segments=segments,
        )
    except Exception:
        return None


def validate_pipeline_round_trip(
    md_path: Path,
    source_lang: str,
    target_lang: str,
) -> bool:
    """Test that an MD file from OPP can be validated by the contract."""
    doc = validate_md_output(md_path, source_lang, target_lang)
    return doc is not None
