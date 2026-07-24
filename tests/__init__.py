"""Omni_Suite E2E Test Suite

This module provides end-to-end tests for the complete OPP → OL → ORF localization pipeline.
"""

try:
    from importlib.metadata import version as _v
    __version__ = _v("omni-suite")
except Exception:
    __version__ = "0.4.0"  # fallback — matches suite pyproject.toml
