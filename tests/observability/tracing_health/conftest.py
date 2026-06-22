"""Local conftest for tests/observability/tracing_health/.

Overrides the parent conftest's session-scoped autouse
fixture ``_copy_latest_final_outputs`` (which walks
``test_artifacts/runs/`` and times out on WSL2) and the
per-test ``_copy_component_logs_to_artifact_dir``.

The tracing + health tests don't write test artifacts and
don't need log snapshots — they only assert span JSONL
files in ``OMNI_TRACES_DIR`` and HTTP responses on a
local port.
"""
from __future__ import annotations

import pytest


@pytest.fixture(scope="session", autouse=True)
def _copy_latest_final_outputs():
    yield


@pytest.fixture(autouse=True)
def _copy_component_logs_to_artifact_dir(request, artifact_dir):
    yield
