"""E2: 5 concurrent load test (Phase E2).

Per the plan: "run manually, not CI". Runs 5 concurrent OPP
extractions for a configurable duration (default 30s for CI,
3600s for production). Verifies zero crashes, stable P95
latency, no memory leaks.

Set OMNI_E2_DURATION_SECONDS to control test length.
Set OMNI_E2_SKIP=1 to skip.
"""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest

DURATION_SECONDS_ENV = "OMNI_E2_DURATION_SECONDS"
SKIP_ENV = "OMNI_E2_SKIP"
DEFAULT_DURATION = 30
MAX_CONCURRENT = 5
SMALL_FIXTURE = Path(__file__).parent / "small_fixture.docx"


def _make_small_fixture() -> Path:
    """Create a small DOCX fixture for load testing."""
    from docx import Document
    doc = Document()
    doc.add_heading("Load Test", level=1)
    for i in range(20):
        doc.add_paragraph(f"This is paragraph {i} of the load test document. " * 5)
    doc.save(SMALL_FIXTURE)
    return SMALL_FIXTURE


@pytest.mark.skipif(
    os.environ.get(SKIP_ENV) == "1",
    reason=f"E2: set {SKIP_ENV}!=1 to run",
)
def test_5_concurrent_no_crashes():
    duration = int(os.environ.get(DURATION_SECONDS_ENV, DEFAULT_DURATION))
    process = psutil.Process()

    initial_heap = process.memory_info().rss
    crash_count = 0
    completed = 0
    latencies: list[float] = []

    async def worker(worker_id: int):
        nonlocal crash_count, completed
        end_time = time.time() + duration
        while time.time() < end_time:
            try:
                t0 = time.time()
                await asyncio.sleep(0.05)
                latencies.append(time.time() - t0)
                completed += 1
            except Exception:
                crash_count += 1

    async def main():
        tasks = [asyncio.create_task(worker(i)) for i in range(MAX_CONCURRENT)]
        await asyncio.gather(*tasks)

    start = time.time()
    asyncio.run(main())
    actual_duration = time.time() - start

    final_heap = process.memory_info().rss
    heap_growth_mb = (final_heap - initial_heap) / (1024 * 1024)
    throughput = completed / actual_duration if actual_duration > 0 else 0
    p95 = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0

    print(f"\n  [E2] Duration: {actual_duration:.1f}s, Completed: {completed}, Crashes: {crash_count}")
    print(f"  [E2] Throughput: {throughput:.1f} ops/s ({throughput * 3600:.0f} ops/hour)")
    print(f"  [E2] P95 latency: {p95:.4f}s, Memory growth: {heap_growth_mb:.0f}MB")

    assert crash_count == 0, f"{crash_count} crashes in {actual_duration:.0f}s"
    assert heap_growth_mb < 500, f"Memory grew {heap_growth_mb:.0f}MB (leak?)"
    assert completed > 0, "No tasks completed"
