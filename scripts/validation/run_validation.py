#!/usr/bin/env python3
"""Console entry for the validation engine (plan todo 9).

Thin wrapper: the real logic lives in ``omni_mcp.validation.cli``
(importable and testable in-process); this script exists so
``python scripts/validation/run_validation.py`` works from a checkout
without installing the console script.  The console entry ``validation``
(root pyproject.toml [project.scripts]) points at the same ``main``.
"""

import sys

from omni_mcp.validation.cli import main

if __name__ == "__main__":
    sys.exit(main())
