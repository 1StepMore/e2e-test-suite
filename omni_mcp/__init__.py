"""omni-mcp: Suite-level MCP server that orchestrates OPP→OL→ORF in one call."""

try:
    from importlib.metadata import version as _v
    __version__ = _v("omni-suite")
except Exception:
    __version__ = "0.4.0"  # fallback
