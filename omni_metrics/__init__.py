"""Shared Prometheus metrics for the Omni Suite (Phase B5)."""

from omni_metrics.metrics import TOOL_CALLS, TOOL_LATENCY, record_tool_call

__all__ = ["TOOL_CALLS", "TOOL_LATENCY", "record_tool_call"]
