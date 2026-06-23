"""omni-suite meta-package — suite version and compatibility CLI."""

__version__ = "0.2.3"

# NOTE: do NOT import from .cli here — that would preload the module and
# break `python -m omni_suite.cli --version` (RuntimeWarning + main() never runs).
