"""Shared Prometheus metrics for the Omni Suite (Phase B5).

Exposes counters and histograms for MCP tool calls across
OPP, OL, and ORF. Metrics are module-scoped (not per-server)
so all three MCP servers contribute to the same metric
namespace.

Usage:
    from omni_metrics.metrics import record_tool_call

    record_tool_call("opp.extract_document", duration_ms=123, success=True)
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

TOOL_CALLS = Counter(
    "omni_mcp_tool_calls_total",
    "Total MCP tool calls across OPP, OL, ORF.",
    ["module", "tool", "success"],
)

TOOL_LATENCY = Histogram(
    "omni_mcp_tool_latency_ms",
    "MCP tool call latency in milliseconds.",
    ["module", "tool"],
    buckets=(1, 5, 10, 50, 100, 500, 1000, 5000, 30000),
)


def record_tool_call(module: str, tool: str, duration_ms: float, success: bool) -> None:
    """Record a single MCP tool call: increment counter and observe latency."""
    TOOL_CALLS.labels(module=module, tool=tool, success=str(success)).inc()
    TOOL_LATENCY.labels(module=module, tool=tool).observe(duration_ms)
