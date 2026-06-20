"""Benchmark test configuration — sets up component import paths."""

import os
import sys
from pathlib import Path

# Ensure all three component src directories are on sys.path
_SUITE_ROOT = Path(__file__).resolve().parents[1]
for _name in ("Omni_Pre_Processor", "Omni_Localizer", "Omni_Re_Formatter"):
    _src = _SUITE_ROOT / _name / "src"
    if _src.exists() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

# Fake LLM seam default for benchmarks
os.environ.setdefault("OMNI_TEST_FAKE_LLM", "1")
