"""Tests for Phase 4.5 OTel tracing across the 3 MCP servers.

Verifies:

- ``OMNI_TRACING_ENABLED=0`` (default) makes the tracer a no-op
  (no span files written, ``start_call_tool_span`` yields None).
- With ``OMNI_TRACING_ENABLED=1``, calling a tool emits a JSONL
  span file to ``OMNI_TRACES_DIR/<module>.jsonl`` with the
  expected shape (span name ``<module>.call_tool``, attributes
  ``tool.name`` + ``tool.status`` + ``module.version``).
- Errors and ``unknown_tool`` produce a span with status=error.
- The MCP stdio stream is not corrupted by tracing (the JSONL
  exporter writes to a file, not stdout/stderr).
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import pytest

SUITE_ROOT = Path(__file__).resolve().parents[3]


def _reset_otel_tracer_provider() -> None:
    """Reset the global OTel TracerProvider so each test can
    install its own.  OTel disallows overriding the provider
    once set, so we flip its internal ``_done`` flag.

    This is a private API; we accept the coupling because the
    OTel test pattern is well-established and the alternative
    (per-test TracerProvider) would require restructuring
    production code.
    """
    from opentelemetry import trace
    once = trace._TRACER_PROVIDER_SET_ONCE
    if once is not None:
        once._done = False
    trace._TRACER_PROVIDER = None


def _load_tracing_module(name: str, path: Path):
    """Load a tracing module fresh (per-test) and reset its
    setup state plus the OTel provider.
    """
    _reset_otel_tracer_provider()
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._setup_done = False
    return mod


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


class TestOPPSpanEmission:
    def test_tracing_disabled_by_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OMNI_TRACING_ENABLED", raising=False)
        monkeypatch.setenv("OMNI_TRACES_DIR", str(tmp_path))
        mod = _load_tracing_module(
            "opp_mcp_tracing_under_test",
            SUITE_ROOT / "Omni_Pre_Processor" / "src" / "opp" / "mcp" / "tracing.py",
        )
        assert mod.is_enabled() is False
        with mod.start_call_tool_span("extract_document", {}) as span:
            assert span is None
        assert not (tmp_path / "opp.jsonl").exists()

    def test_tracing_enabled_emits_span(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OMNI_TRACING_ENABLED", "1")
        monkeypatch.setenv("OMNI_TRACES_DIR", str(tmp_path))
        mod = _load_tracing_module(
            "opp_mcp_tracing_under_test",
            SUITE_ROOT / "Omni_Pre_Processor" / "src" / "opp" / "mcp" / "tracing.py",
        )
        assert mod.is_enabled() is True
        with mod.start_call_tool_span("extract_document", {"file_path": "/x.docx"}) as span:
            assert span is not None
            mod.set_span_status(span, "success", duration_ms=12.5)
        time.sleep(0.3)
        spans = _read_jsonl(tmp_path / "opp.jsonl")
        assert len(spans) >= 1
        last = spans[-1]
        assert last["name"] == "opp.call_tool"
        assert last["attributes"]["tool.name"] == "extract_document"
        assert last["attributes"]["tool.status"] == "success"
        assert last["attributes"]["module"] == "opp"
        assert "module.version" in last["attributes"]
        assert last["status"]["status_code"] == "OK"

    def test_tracing_error_status(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OMNI_TRACING_ENABLED", "1")
        monkeypatch.setenv("OMNI_TRACES_DIR", str(tmp_path))
        mod = _load_tracing_module(
            "opp_mcp_tracing_under_test",
            SUITE_ROOT / "Omni_Pre_Processor" / "src" / "opp" / "mcp" / "tracing.py",
        )
        with mod.start_call_tool_span("nope", {}) as span:
            mod.set_span_status(span, "error", error_code="OPP_UNKNOWN_TOOL")
        time.sleep(0.3)
        spans = _read_jsonl(tmp_path / "opp.jsonl")
        assert any(
            s["attributes"].get("tool.status") == "error"
            and s["attributes"].get("tool.error_code") == "OPP_UNKNOWN_TOOL"
            for s in spans
        )


class TestOLSpanEmission:
    def test_tracing_disabled_by_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OMNI_TRACING_ENABLED", raising=False)
        monkeypatch.setenv("OMNI_TRACES_DIR", str(tmp_path))
        monkeypatch.setenv("OMNI_TEST_FAKE_LLM", "1")
        mod = _load_tracing_module(
            "ol_mcp_tracing_under_test",
            SUITE_ROOT / "Omni_Localizer" / "src" / "ol_mcp" / "tracing.py",
        )
        assert mod.is_enabled() is False
        with mod.start_call_tool_span("translate_md_text", {}) as span:
            assert span is None

    def test_tracing_enabled_emits_span(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OMNI_TRACING_ENABLED", "1")
        monkeypatch.setenv("OMNI_TRACES_DIR", str(tmp_path))
        monkeypatch.setenv("OMNI_TEST_FAKE_LLM", "1")
        mod = _load_tracing_module(
            "ol_mcp_tracing_under_test",
            SUITE_ROOT / "Omni_Localizer" / "src" / "ol_mcp" / "tracing.py",
        )
        with mod.start_call_tool_span("translate_md_text", {"content": "hi"}) as span:
            mod.set_span_status(span, "success", duration_ms=8.0)
        time.sleep(0.3)
        spans = _read_jsonl(tmp_path / "ol.jsonl")
        assert len(spans) >= 1
        last = spans[-1]
        assert last["name"] == "ol.call_tool"
        assert last["attributes"]["tool.name"] == "translate_md_text"
        assert last["attributes"]["tool.status"] == "success"
        assert last["attributes"]["module"] == "ol"


class TestORFSpanEmission:
    def test_tracing_disabled_by_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OMNI_TRACING_ENABLED", raising=False)
        monkeypatch.setenv("OMNI_TRACES_DIR", str(tmp_path))
        mod = _load_tracing_module(
            "orf_mcp_tracing_under_test",
            SUITE_ROOT / "Omni_Re_Formatter" / "src" / "orf" / "mcp" / "tracing.py",
        )
        assert mod.is_enabled() is False
        with mod.start_call_tool_span("apply_md", {}) as span:
            assert span is None

    def test_tracing_enabled_emits_span(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OMNI_TRACING_ENABLED", "1")
        monkeypatch.setenv("OMNI_TRACES_DIR", str(tmp_path))
        mod = _load_tracing_module(
            "orf_mcp_tracing_under_test",
            SUITE_ROOT / "Omni_Re_Formatter" / "src" / "orf" / "mcp" / "tracing.py",
        )
        with mod.start_call_tool_span("apply_md", {"input_md": "/x.md"}) as span:
            mod.set_span_status(span, "success", duration_ms=4.0)
        time.sleep(0.3)
        spans = _read_jsonl(tmp_path / "orf.jsonl")
        assert len(spans) >= 1
        last = spans[-1]
        assert last["name"] == "orf.call_tool"
        assert last["attributes"]["tool.name"] == "apply_md"
        assert last["attributes"]["tool.status"] == "success"
        assert last["attributes"]["module"] == "orf"


class TestTraceDoesNotCorruptStdIO:
    """Sanity check: the JSONL exporter writes to a file, not
    stdout/stderr.  The MCP stdio transport must remain clean.
    """

    def test_opp_tracing_does_not_print(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("OMNI_TRACING_ENABLED", "1")
        monkeypatch.setenv("OMNI_TRACES_DIR", str(tmp_path))
        mod = _load_tracing_module(
            "opp_mcp_tracing_under_test",
            SUITE_ROOT / "Omni_Pre_Processor" / "src" / "opp" / "mcp" / "tracing.py",
        )
        with mod.start_call_tool_span("extract_document", {}) as span:
            mod.set_span_status(span, "success", duration_ms=1.0)
        time.sleep(0.2)
        out = capsys.readouterr()
        assert out.out == ""
        assert out.err == ""
