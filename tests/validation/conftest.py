"""Conftest for tests/validation.

Shadows the suite-wide autouse log-copying fixtures from ``tests/conftest.py``
(:272 ``_copy_component_logs_to_artifact_dir``, :302
``_copy_latest_final_outputs``) with no-ops.  Those fixtures copy component
logs into ``test_artifacts/`` after every test; on the WSL /mnt/d mount the
``Path.stat()`` / ``glob()`` calls inside them block for minutes (observed
2026-08-14: any test file under the suite root hangs at teardown).  The
validation-engine unit tests produce no component logs, so the copies add
nothing here — the no-op shadow keeps the suite convention intact for the
other test directories while making ``tests/validation/`` runnable.
"""

import pytest


@pytest.fixture(autouse=True)
def _copy_component_logs_to_artifact_dir():
    """No-op shadow: loader tests produce no component logs to copy."""
    yield


@pytest.fixture(scope="session", autouse=True)
def _copy_latest_final_outputs():
    """No-op shadow: loader tests produce no artifacts for final/."""
    yield
