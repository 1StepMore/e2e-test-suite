"""Tests for Phase B3: structured JSON logging.

Verifies all 3 modules' loggers emit valid JSON with the plan's
field names (timestamp, level, module, message, request_id) when
OMNI_LOG_FORMAT=json, and continue to emit human-readable text
when OMNI_LOG_FORMAT=console (default).
"""

import io
import json
import logging



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


# Phase 4.1 — structlog primary path. All 3 modules must emit identical
# JSON shape (timestamp, level, module, request_id, event) under
# OMNI_LOG_FORMAT=json. The structlog call site is
# ``structlog.get_logger("opp.<sub>").info(event, k=v)``; the kwargs
# become JSON fields. The event is captured from the log file that
# ``setup_logger`` / ``init_logger`` opens for ``PrintLoggerFactory``.
STRUCTLOG_EXPECTED_FIELDS = {"timestamp", "level", "module", "request_id", "event"}


def _read_last_log_line(log_path) -> dict:
    """Read the last non-empty line of ``log_path`` and parse as JSON."""
    with open(log_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    assert lines, f"no log lines in {log_path}"
    return json.loads(lines[-1])


class TestStructlogJsonPath:
    """Phase 4.1: all 3 modules emit identical JSON via structlog."""

    def test_opp_structlog_emits_standard_shape(self, monkeypatch):
        monkeypatch.setenv("OMNI_LOG_FORMAT", "json")
        from opp.logger import _build_processors, _build_final_renderer, _NamedPrintLoggerFactory
        import structlog
        import io

        sink = io.StringIO()
        structlog.configure(
            processors=_build_processors() + [_build_final_renderer()],
            wrapper_class=structlog.make_filtering_bound_logger(20),
            context_class=dict,
            logger_factory=_NamedPrintLoggerFactory(file=sink),
            cache_logger_on_first_use=True,
        )
        structlog.contextvars.bind_contextvars(request_id="opp-struct-rid")
        structlog.get_logger("opp.cli").info("extraction_complete", file="/tmp/doc.md", paragraph_count=42)

        lines = [ln for ln in sink.getvalue().splitlines() if ln.strip()]
        assert lines, "no structlog output captured"
        record = json.loads(lines[-1])
        assert STRUCTLOG_EXPECTED_FIELDS <= set(record.keys())
        assert record["level"] == "INFO"
        assert record["module"] == "opp.cli"
        assert record["request_id"] == "opp-struct-rid"
        assert record["event"] == "extraction_complete"
        assert record["file"] == "/tmp/doc.md"
        assert record["paragraph_count"] == 42

    def test_ol_structlog_emits_standard_shape(self, monkeypatch):
        monkeypatch.setenv("OMNI_LOG_FORMAT", "json")
        from ol_logging.formatters import _build_processors, _build_final_renderer
        from ol_logging.core import _NamedPrintLoggerFactory
        import structlog
        import io

        sink = io.StringIO()
        structlog.configure(
            processors=_build_processors() + [_build_final_renderer()],
            wrapper_class=structlog.make_filtering_bound_logger(20),
            context_class=dict,
            logger_factory=_NamedPrintLoggerFactory(file=sink),
            cache_logger_on_first_use=True,
        )
        structlog.contextvars.bind_contextvars(request_id="ol-struct-rid")
        structlog.get_logger("ol.cli").info("translated", count=5, source="en", target="zh")

        lines = [ln for ln in sink.getvalue().splitlines() if ln.strip()]
        assert lines, "no structlog output captured"
        record = json.loads(lines[-1])
        assert STRUCTLOG_EXPECTED_FIELDS <= set(record.keys())
        assert record["level"] == "INFO"
        assert record["module"] == "ol.cli"
        assert record["request_id"] == "ol-struct-rid"
        assert record["event"] == "translated"
        assert record["count"] == 5
        assert record["source"] == "en"
        assert record["target"] == "zh"

    def test_orf_structlog_emits_standard_shape(self, monkeypatch):
        monkeypatch.setenv("OMNI_LOG_FORMAT", "json")
        from orf.logging import _build_processors, _build_final_renderer, _NamedPrintLoggerFactory
        import structlog
        import io

        sink = io.StringIO()
        structlog.configure(
            processors=_build_processors() + [_build_final_renderer()],
            wrapper_class=structlog.make_filtering_bound_logger(20),
            context_class=dict,
            logger_factory=_NamedPrintLoggerFactory(file=sink),
            cache_logger_on_first_use=True,
        )
        structlog.contextvars.bind_contextvars(request_id="orf-struct-rid")
        structlog.get_logger("orf.cli").info("converted", target="docx", file="/tmp/out.docx")

        lines = [ln for ln in sink.getvalue().splitlines() if ln.strip()]
        assert lines, "no structlog output captured"
        record = json.loads(lines[-1])
        assert STRUCTLOG_EXPECTED_FIELDS <= set(record.keys())
        assert record["level"] == "INFO"
        assert record["module"] == "orf.cli"
        assert record["request_id"] == "orf-struct-rid"
        assert record["event"] == "converted"
        assert record["target"] == "docx"
        assert record["file"] == "/tmp/out.docx"

    def test_all_three_modules_emit_identical_shape(self, monkeypatch):
        """Cross-module invariant: same event on OPP/OL/ORF produces the same JSON key set."""
        monkeypatch.setenv("OMNI_LOG_FORMAT", "json")
        import io
        captured = {}

        from opp.logger import _build_processor_formatter
        fmt = _build_processor_formatter()
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(fmt)
        logger = logging.getLogger("opp.cross")
        logger.setLevel(logging.INFO)
        logger.handlers = [handler]
        logger.info("cross_module_event", extra={"request_id": "cross-rid", "k": "v"})
        captured["opp"] = set(json.loads(stream.getvalue().strip()).keys())

        from ol_logging.formatters import get_structlog_formatter
        fmt = get_structlog_formatter()
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(fmt)
        logger = logging.getLogger("ol.cross")
        logger.setLevel(logging.INFO)
        logger.handlers = [handler]
        logger.info("cross_module_event", extra={"request_id": "cross-rid", "k": "v"})
        captured["ol"] = set(json.loads(stream.getvalue().strip()).keys())

        from orf.logging import _get_stdlib_handler_formatter
        fmt = _get_stdlib_handler_formatter(json_mode=True)
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(fmt)
        logger = logging.getLogger("orf.cross")
        logger.setLevel(logging.INFO)
        logger.handlers = [handler]
        logger.info("cross_module_event", extra={"request_id": "cross-rid", "k": "v"})
        captured["orf"] = set(json.loads(stream.getvalue().strip()).keys())

        assert captured["opp"] == captured["ol"] == captured["orf"], (
            f"field sets diverge: {captured}"
        )
        for module, fields in captured.items():
            assert STRUCTLOG_EXPECTED_FIELDS <= fields, (
                f"{module} missing standard fields: have {fields}"
            )
