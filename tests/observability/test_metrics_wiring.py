"""Tests for Phase B5: verify record_tool_call is wired into
OPP log_mcp_audit and OL mcp_error_boundary.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from prometheus_client import REGISTRY


def _get_counter(module: str, tool: str, success: str) -> float:
    val = REGISTRY.get_sample_value(
        "omni_mcp_tool_calls_total",
        {"module": module, "tool": tool, "success": success},
    )
    return val or 0.0


class TestOPPAuditWiring:
    def test_log_mcp_audit_increments_metrics(self):
        from opp.utils.mcp_errors import log_mcp_audit
        before = _get_counter("opp", "test_opp_tool", "True")
        log_mcp_audit("test_opp_tool", 100.0, True)
        after = _get_counter("opp", "test_opp_tool", "True")
        assert after == before + 1

    def test_log_mcp_audit_failure_increments(self):
        from opp.utils.mcp_errors import log_mcp_audit
        before = _get_counter("opp", "test_opp_fail", "False")
        log_mcp_audit("test_opp_fail", 200.0, False)
        after = _get_counter("opp", "test_opp_fail", "False")
        assert after == before + 1


class TestOLBoundaryWiring:
    def test_async_wrapper_success_increments_metrics(self):
        from ol_mcp._errors import mcp_error_boundary

        @mcp_error_boundary
        async def test_tool(x: int) -> int:
            return x * 2

        before = _get_counter("ol", "test_tool", "True")
        result = asyncio.run(test_tool(21))
        after = _get_counter("ol", "test_tool", "True")
        assert result == 42
        assert after == before + 1

    def test_async_wrapper_failure_increments_metrics(self):
        from ol_mcp._errors import mcp_error_boundary

        @mcp_error_boundary
        async def failing_tool():
            raise ValueError("boom")

        before = _get_counter("ol", "failing_tool", "False")
        result = asyncio.run(failing_tool())
        after = _get_counter("ol", "failing_tool", "False")
        assert after == before + 1
        assert '"error_code"' in result
