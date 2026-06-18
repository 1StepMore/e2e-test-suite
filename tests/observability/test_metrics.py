"""Tests for Phase B5: shared Prometheus metrics."""

import pytest
from prometheus_client import REGISTRY


class TestRecordToolCall:
    def test_increments_counter(self):
        from omni_metrics import record_tool_call
        before = REGISTRY.get_sample_value(
            "omni_mcp_tool_calls_total",
            {"module": "test_mod", "tool": "test_tool", "success": "True"},
        ) or 0.0
        record_tool_call("test_mod", "test_tool", 100.0, True)
        after = REGISTRY.get_sample_value(
            "omni_mcp_tool_calls_total",
            {"module": "test_mod", "tool": "test_tool", "success": "True"},
        )
        assert after == before + 1

    def test_success_false_label(self):
        from omni_metrics import record_tool_call
        before = REGISTRY.get_sample_value(
            "omni_mcp_tool_calls_total",
            {"module": "test_mod2", "tool": "test_tool2", "success": "False"},
        ) or 0.0
        record_tool_call("test_mod2", "test_tool2", 200.0, False)
        after = REGISTRY.get_sample_value(
            "omni_mcp_tool_calls_total",
            {"module": "test_mod2", "tool": "test_tool2", "success": "False"},
        )
        assert after == before + 1

    def test_latency_histogram(self):
        from omni_metrics import record_tool_call
        record_tool_call("test_mod3", "test_tool3", 42.0, True)
        count = REGISTRY.get_sample_value(
            "omni_mcp_tool_latency_ms_count",
            {"module": "test_mod3", "tool": "test_tool3"},
        )
        assert count >= 1


class TestModuleExports:
    def test_public_api(self):
        from omni_metrics import TOOL_CALLS, TOOL_LATENCY, record_tool_call
        assert TOOL_CALLS is not None
        assert TOOL_LATENCY is not None
        assert callable(record_tool_call)
