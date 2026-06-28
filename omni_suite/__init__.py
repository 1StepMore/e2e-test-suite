"""omni-suite meta-package — suite version and compatibility CLI."""

try:
    from importlib.metadata import version as _v
    __version__ = _v("omni-suite")
except Exception:
    __version__ = "0.4.0"  # fallback

# NOTE: do NOT import from .cli here — that would preload the module and
# break `python -m omni_suite.cli --version` (RuntimeWarning + main() never runs).
