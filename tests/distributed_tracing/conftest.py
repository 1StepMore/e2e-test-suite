"""Local conftest for tests/distributed_tracing/.

Overrides the parent conftest's session-scoped autouse
fixture ``_copy_latest_final_outputs`` (which walks
``test_artifacts/runs/`` and times out on WSL2) and the
per-test ``_copy_component_logs_to_artifact_dir``.

The distributed tracing tests write only span JSONL
files to ``OMNI_TRACES_DIR``; they don't produce test
artifacts or need log snapshots.
"""
from __future__ import annotations

import pytest


@pytest.fixture(scope="session", autouse=True)
def _copy_latest_final_outputs():
    yield


@pytest.fixture(autouse=True)
def _copy_component_logs_to_artifact_dir(request, artifact_dir):
    yield
