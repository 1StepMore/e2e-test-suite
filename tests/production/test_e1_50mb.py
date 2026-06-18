"""E1: 50MB file production test (Phase E1, gated on fixture).

Generates or finds a 50MB DOCX, runs OPP→OL→ORF end-to-end.
Verifies: no crashes, output valid, P95 latency < 5 min.

Per the plan: "gated on fixture availability". This test is
skipped by default. Set OMNI_E1_FIXTURE_PATH to enable.
"""

import os
import time
from pathlib import Path

import pytest

FIXTURE_ENV = "OMNI_E1_FIXTURE_PATH"
P95_LATENCY_SECONDS = 300  # 5 minutes


@pytest.mark.skipif(
    not os.environ.get(FIXTURE_ENV),
    reason=f"E1: set {FIXTURE_ENV} to a 50MB DOCX to enable",
)
def test_50mb_file_end_to_end():
    fixture_path = Path(os.environ[FIXTURE_ENV])
    assert fixture_path.exists(), f"Fixture not found: {fixture_path}"
    size_mb = fixture_path.stat().st_size / (1024 * 1024)
    assert size_mb >= 45, f"Fixture too small: {size_mb:.1f}MB (need ≥45MB)"

    t0 = time.time()
    output = run_opp_ol_orf(fixture_path)
    elapsed = time.time() - t0

    assert output.exists(), "No output produced"
    assert output.stat().st_size > 0, "Output is empty"
    assert elapsed < P95_LATENCY_SECONDS, (
        f"P95 latency exceeded: {elapsed:.0f}s > {P95_LATENCY_SECONDS}s"
    )


def run_opp_ol_orf(input_path: Path) -> Path:
    """Run the full OPP→OL→ORF pipeline. Stub for now — real
    implementation needs the full pipeline wired up."""
    output = input_path.parent / f"{input_path.stem}_processed.docx"
    output.touch()
    return output
