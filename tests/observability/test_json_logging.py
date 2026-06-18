"""Tests for Phase B3: structured JSON logging.

Verifies all 3 modules' loggers emit valid JSON with the plan's
field names (timestamp, level, module, message, request_id) when
OMNI_LOG_FORMAT=json, and continue to emit human-readable text
when OMNI_LOG_FORMAT=console (default).
"""

import io
import json
import logging
import os

import pytest


# Expected field names per the plan.
EXPECTED_FIELDS = {"timestamp", "level", "module", "message"}
REQUEST_ID_FIELD = "request_id"


def _capture_log(formatter: logging.Formatter) -> tuple[io.StringIO, logging.Logger]:
    """Return (stream, logger) wired to an in-memory handler with the given formatter."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)
    logger = logging.getLogger(f"test.{id(formatter)}")
    logger.setLevel(logging.INFO)
    logger.handlers = [handler]
    return stream, logger


class TestOLJsonFormatter:
    def test_json_mode_emits_valid_json(self, monkeypatch):
        monkeypatch.setenv("OMNI_LOG_FORMAT", "json")
        from ol_logging.formatters import get_formatter
        fmt = get_formatter()
        assert fmt.__class__.__name__ == "JsonFormatter"

    def test_json_output_has_plan_fields(self, monkeypatch):
        monkeypatch.setenv("OMNI_LOG_FORMAT", "json")
        from ol_logging.formatters import get_formatter
        fmt = get_formatter()
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(fmt)
        logger = logging.getLogger("test.ol_json")
        logger.setLevel(logging.INFO)
        logger.handlers = [handler]
        logger.info("Translated 5 files", extra={"request_id": "abc-123"})
        record = json.loads(stream.getvalue().strip())
        assert set(record.keys()) >= EXPECTED_FIELDS
        assert record[REQUEST_ID_FIELD] == "abc-123"
        assert record["level"] == "INFO"
        assert record["module"] == "test.ol_json"
        assert record["message"] == "Translated 5 files"

    def test_console_mode_unchanged(self, monkeypatch):
        monkeypatch.delenv("OMNI_LOG_FORMAT", raising=False)
        from ol_logging.formatters import get_formatter
        fmt = get_formatter()
        assert fmt.__class__.__name__ == "Formatter"
        assert not fmt.__class__.__name__.startswith("Json")


class TestOPPJsonFormatter:
    def test_json_mode_emits_valid_json(self, monkeypatch):
        monkeypatch.setenv("OMNI_LOG_FORMAT", "json")
        from opp.logger import _build_formatter
        fmt = _build_formatter(json_mode=True)
        assert fmt.__class__.__name__ == "JsonFormatter"

    def test_json_output_has_plan_fields(self, monkeypatch):
        monkeypatch.setenv("OMNI_LOG_FORMAT", "json")
        from opp.logger import _build_formatter
        fmt = _build_formatter(json_mode=True)
        stream, logger = _capture_log(fmt)
        logger.info("Extracted 42 paragraphs", extra={"request_id": "opp-123"})
        record = json.loads(stream.getvalue().strip())
        assert set(record.keys()) >= EXPECTED_FIELDS
        assert record[REQUEST_ID_FIELD] == "opp-123"
        assert record["level"] == "INFO"
        assert record["message"] == "Extracted 42 paragraphs"

    def test_console_mode_unchanged(self, monkeypatch):
        monkeypatch.delenv("OMNI_LOG_FORMAT", raising=False)
        from opp.logger import _build_formatter
        fmt = _build_formatter(json_mode=False)
        assert fmt.__class__.__name__ == "Formatter"


class TestORFJsonFormatter:
    def test_json_mode_emits_valid_json(self, monkeypatch):
        monkeypatch.setenv("OMNI_LOG_FORMAT", "json")
        from orf.logging import _build_formatter
        fmt = _build_formatter(json_mode=True)
        assert fmt.__class__.__name__ == "JsonFormatter"

    def test_json_output_has_plan_fields(self, monkeypatch):
        monkeypatch.setenv("OMNI_LOG_FORMAT", "json")
        from orf.logging import _build_formatter
        fmt = _build_formatter(json_mode=True)
        stream, logger = _capture_log(fmt)
        logger.info("Converted to DOCX", extra={"request_id": "orf-789"})
        record = json.loads(stream.getvalue().strip())
        assert set(record.keys()) >= EXPECTED_FIELDS
        assert record[REQUEST_ID_FIELD] == "orf-789"
        assert record["level"] == "INFO"
        assert record["message"] == "Converted to DOCX"

    def test_console_mode_unchanged(self, monkeypatch):
        monkeypatch.delenv("OMNI_LOG_FORMAT", raising=False)
        from orf.logging import _build_formatter
        fmt = _build_formatter(json_mode=False)
        assert fmt.__class__.__name__ == "Formatter"


class TestRequestIdOptional:
    def test_request_id_absent_when_not_provided(self, monkeypatch):
        """request_id is optional; logs without it should not have the field."""
        monkeypatch.setenv("OMNI_LOG_FORMAT", "json")
        from ol_logging.formatters import get_formatter
        fmt = get_formatter()
        stream, logger = _capture_log(fmt)
        logger.info("No request ID here")
        record = json.loads(stream.getvalue().strip())
        assert REQUEST_ID_FIELD not in record or record.get(REQUEST_ID_FIELD) is None
