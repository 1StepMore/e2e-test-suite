"""Local conftest for tests/error_scenarios/.

Overrides the parent conftest's session-scoped autouse
fixture ``_copy_latest_final_outputs`` (which walks
``test_artifacts/runs/`` and times out on WSL2) and the
per-test ``_copy_component_logs_to_artifact_dir`` (which
copies log files we don't need for hermetic CLI tests).

The parent fixture's name is preserved so pytest's
fixture-resolution picks the local override when running
tests in this directory.
"""
from __future__ import annotations

import pytest


@pytest.fixture(scope="session", autouse=True)
def _copy_latest_final_outputs():
    yield


@pytest.fixture(autouse=True)
def _copy_component_logs_to_artifact_dir(request, artifact_dir):
    yield
