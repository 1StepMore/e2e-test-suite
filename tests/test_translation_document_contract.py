"""Test P3-T1: TranslationDocument Pydantic model contract."""
import pytest
from omni_suite.contract.models import TranslationDocument, DocumentFormat, TranslationSegment


def test_translation_document_basic_construction():
    """TranslationDocument can be constructed with required fields."""
    doc = TranslationDocument(
        format_type=DocumentFormat.DOCX,
        pipeline_path="md",
        source_lang="en",
        target_lang="zh",
    )
    assert doc.format_type == DocumentFormat.DOCX
    assert doc.pipeline_path == "md"
    assert doc.source_lang == "en"
    assert doc.target_lang == "zh"
    assert doc.segments == []
    assert doc.metadata == {}
    assert doc.version == "1.0"


def test_translation_document_json_schema_generation():
    """P3-T1 verify: model can generate valid JSON Schema."""
    schema = TranslationDocument.model_json_schema()
    assert "format_type" in schema["properties"]
    assert "pipeline_path" in schema["properties"]
    assert "source_lang" in schema["properties"]
    assert "target_lang" in schema["properties"]
    assert "segments" in schema["properties"]


def test_translation_document_extra_ignore_compatibility():
    """P3-T1 design decision: extra='ignore' allows existing pipeline outputs without breaking."""
    doc = TranslationDocument(
        format_type=DocumentFormat.PDF,
        pipeline_path="xliff",
        source_lang="en",
        target_lang="zh",
        unknown_field="ignored",  # Should not raise
    )
    assert doc.unknown_field == "ignored"  # extra='ignore' keeps the field


def test_translation_document_invalid_lang_code_rejected():
    """TranslationDocument validates ISO 639-1 language codes."""
    with pytest.raises(ValueError):
        TranslationDocument(
            format_type=DocumentFormat.DOCX,
            pipeline_path="md",
            source_lang="x",  # Too short
            target_lang="zh",
        )


def test_translation_document_invalid_pipeline_rejected():
    """TranslationDocument only accepts 'md' or 'xliff' pipeline paths."""
    with pytest.raises(ValueError):
        TranslationDocument(
            format_type=DocumentFormat.DOCX,
            pipeline_path="invalid",
            source_lang="en",
            target_lang="zh",
        )


def test_translation_document_segments():
    """TranslationDocument can hold a list of TranslationSegment."""
    seg = TranslationSegment(id="1", source="Hello", target="你好")
    doc = TranslationDocument(
        format_type=DocumentFormat.DOCX,
        pipeline_path="md",
        source_lang="en",
        target_lang="zh",
        segments=[seg],
    )
    assert len(doc.segments) == 1
    assert doc.segments[0].source == "Hello"
    assert doc.segments[0].target == "你好"


def test_validator_module_loadable():
    """P3-T2: validator module is importable."""
    from omni_suite.contract import validator
    assert hasattr(validator, "validate_md_output")
    assert hasattr(validator, "validate_xliff_output")
    assert hasattr(validator, "validate_pipeline_round_trip")
