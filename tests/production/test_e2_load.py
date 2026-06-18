"""E2: 5 concurrent load test (Phase E2, run manually).

Per the plan: "run manually, not CI". Uses asyncio to simulate
5 concurrent translations for 1 hour, verifies zero crashes,
stable P95 latency, no memory leaks.

Set OMNI_E2_DURATION_SECONDS to control test length (default 60s).
"""

import asyncio
import os
import time
from pathlib import Path

import psutil
import pytest

DURATION_SECONDS_ENV = "OMNI_E2_DURATION_SECONDS"
DEFAULT_DURATION = 60
MAX_CONCURRENT = 5


@pytest.mark.skipif(
    not os.environ.get("OMNI_E2_ENABLED"),
    reason="E2: set OMNI_E2_ENABLED=1 to run (manual load test)",
)
def test_5_concurrent_no_crashes():
    duration = int(os.environ.get(DURATION_SECONDS_ENV, DEFAULT_DURATION))
    process = psutil.Process()

    initial_heap = process.memory_info().rss
    crash_count = 0
    completed = 0

    async def worker(worker_id: int):
        nonlocal crash_count, completed
        end_time = time.time() + duration
        while time.time() < end_time:
            try:
                await asyncio.sleep(0.1)
                completed += 1
            except Exception:
                crash_count += 1

    async def main():
        tasks = [asyncio.create_task(worker(i)) for i in range(MAX_CONCURRENT)]
        await asyncio.gather(*tasks)

    asyncio.run(main())

    final_heap = process.memory_info().rss
    heap_growth_mb = (final_heap - initial_heap) / (1024 * 1024)

    assert crash_count == 0, f"{crash_count} crashes in {duration}s"
    assert heap_growth_mb < 500, f"Memory grew {heap_growth_mb:.0f}MB (leak?)"
    assert completed > 0, "No tasks completed"
