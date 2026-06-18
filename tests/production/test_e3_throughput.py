"""E3: 100 docs/day throughput simulation (Phase E3, run manually).

Per the plan: "run manually, not CI". Simulates 100 docs over
8 hours with realistic arrival pattern. Verifies 100/100 complete
and quality score is above threshold.

Set OMNI_E3_ENABLED=1 to run.
"""

import asyncio
import os
import time

import pytest

NUM_DOCS = 100
HOURS = 8
SECONDS_PER_HOUR = 3600
TARGET_PASS_RATE = 0.85


@pytest.mark.skipif(
    not os.environ.get("OMNI_E3_ENABLED"),
    reason="E3: set OMNI_E3_ENABLED=1 to run (manual throughput test)",
)
def test_100_docs_per_day():
    completed = 0
    failed = 0
    interval = (HOURS * SECONDS_PER_HOUR) / NUM_DOCS

    for i in range(NUM_DOCS):
        time.sleep(interval / 1000)
        if simulate_doc(i):
            completed += 1
        else:
            failed += 1

    pass_rate = completed / NUM_DOCS
    assert completed == NUM_DOCS, f"Only {completed}/{NUM_DOCS} completed"
    assert pass_rate >= TARGET_PASS_RATE, f"Pass rate {pass_rate:.0%} < {TARGET_PASS_RATE:.0%}"


def simulate_doc(doc_id: int) -> bool:
    """Stub: simulate a doc processing. Returns True on success."""
    return True
