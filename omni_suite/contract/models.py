"""Shared contract models for OPP→OL→ORF handoff."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class DocumentFormat(str, Enum):
    """Supported document formats across the pipeline."""

    DOCX = "docx"
    PPTX = "pptx"
    PDF = "pdf"
    EPUB = "epub"
    HTML = "html"
    MD = "md"
    XLIFF = "xliff"
    # ... more as needed


class TranslationSegment(BaseModel):
    """A single translatable unit in the document."""

    id: str
    source: str
    target: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TranslationDocument(BaseModel):
    """The contract between OPP (output) → OL (input) → ORF (input).

    Used to validate handoffs at each pipeline boundary.
    """

    # Backward compat: don't reject unknown fields.
    # Using "allow" (not "ignore") so extra fields are preserved
    # on round-trip — callers can inspect them.
    model_config = {"extra": "allow"}

    format_type: DocumentFormat
    pipeline_path: Literal["md", "xliff"]
    source_lang: str = Field(min_length=2, max_length=10)
    target_lang: str = Field(min_length=2, max_length=10)
    metadata: dict[str, Any] = Field(default_factory=dict)
    segments: list[TranslationSegment] = Field(default_factory=list)
    version: str = "1.0"  # contract version
