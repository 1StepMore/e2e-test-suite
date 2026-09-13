"""T-08 regression: omni_mcp.translate_file must enforce path security.

``omni_mcp`` calls the OPP/OL/ORF CLIs directly, bypassing each sub-module's
MCP ``PathValidator``. Before T-08 it did no path checking at all, so an agent
could point it at any file on the host (``../../etc/passwd``), and it also had
no shared-secret auth.

Contract locked here:
  * a path outside the configured allowlist -> ``OMNI_PATH_DENIED``
  * no allowlist configured at all -> fail CLOSED with ``OMNI_PATH_DENIED``
  * an allowed path still reaches the pipeline
  * when ``MCP_SHARED_SECRET`` is set, a wrong/missing secret -> ``AUTH_FAILED``

Red-first: the denial cases currently fall through to the CLI subprocess.
"""
from __future__ import annotations

import pytest


_ALL_ALLOWLIST_VARS = (
    "MCP_ALLOWED_DIRECTORIES",
    "OMNI_MCP_ALLOWED_DIRS",
    "OPP_MCP_ALLOWED_DIRS",
    "OL_MCP_ALLOWED_DIRS",
    "ORF_MCP_ALLOWED_DIRS",
)


@pytest.fixture
def forbid_cli(monkeypatch):
    """Fail loudly if the orchestrator reaches the CLI subprocess."""

    def _boom(*args, **kwargs):
        raise AssertionError("CLI must not be invoked for a denied/unauthorized path")

    monkeypatch.setattr("omni_mcp.orchestrator._run_cli", _boom)


@pytest.fixture
def clear_allowlist(monkeypatch):
    for var in _ALL_ALLOWLIST_VARS:
        monkeypatch.delenv(var, raising=False)


def _docx(tmp_path, name="doc.docx"):
    p = tmp_path / name
    p.write_bytes(b"PK\x03\x04")
    return p


def test_out_of_allowlist_path_denied(monkeypatch, tmp_path, forbid_cli):
    """A source file outside the allowlist must yield OMNI_PATH_DENIED."""
    from omni_mcp.orchestrator import translate_file

    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    src = _docx(outside)

    for var in _ALL_ALLOWLIST_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MCP_ALLOWED_DIRECTORIES", str(allowed))

    result = translate_file(
        file_path=str(src),
        source_lang="en",
        target_lang="zh",
        output_format="docx",
    )
    assert result["success"] is False
    assert result["error"]["code"] == "OMNI_PATH_DENIED"


def test_traversal_path_denied(monkeypatch, tmp_path, forbid_cli):
    """A ``..`` traversal that escapes the allowlist must yield OMNI_PATH_DENIED."""
    from omni_mcp.orchestrator import translate_file

    allowed = tmp_path / "allowed"
    allowed.mkdir()
    traversal = str(allowed / ".." / ".." / "etc" / "passwd")

    for var in _ALL_ALLOWLIST_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MCP_ALLOWED_DIRECTORIES", str(allowed))

    result = translate_file(
        file_path=traversal,
        source_lang="en",
        target_lang="zh",
        output_format="docx",
    )
    assert result["success"] is False
    assert result["error"]["code"] == "OMNI_PATH_DENIED"


def test_fails_closed_when_no_allowlist_configured(tmp_path, clear_allowlist, forbid_cli):
    """With no allowlist env var set, translate_file must refuse (fail CLOSED)."""
    from omni_mcp.orchestrator import translate_file

    src = _docx(tmp_path)
    result = translate_file(
        file_path=str(src),
        source_lang="en",
        target_lang="zh",
        output_format="docx",
    )
    assert result["success"] is False
    assert result["error"]["code"] == "OMNI_PATH_DENIED"


def test_allowed_path_reaches_pipeline(monkeypatch, tmp_path):
    """A path inside the allowlist must pass the security gate."""
    from omni_mcp.orchestrator import translate_file

    src = _docx(tmp_path)
    for var in _ALL_ALLOWLIST_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MCP_ALLOWED_DIRECTORIES", str(tmp_path))
    monkeypatch.setattr(
        "omni_mcp.orchestrator._run_cli",
        lambda cmd, **kwargs: {
            "success": False,
            "error": {"code": "OPP_FAILED", "message": "stubbed"},
        },
    )

    result = translate_file(
        file_path=str(src),
        source_lang="en",
        target_lang="zh",
        output_format="docx",
    )
    assert result["success"] is False
    assert result["error"]["code"] == "OPP_FAILED"


@pytest.mark.asyncio
async def test_server_rejects_wrong_shared_secret(monkeypatch, tmp_path):
    """When MCP_SHARED_SECRET is set, the server requires a matching secret."""
    from omni_mcp.server import translate_file

    src = _docx(tmp_path)
    monkeypatch.setenv("MCP_ALLOWED_DIRECTORIES", str(tmp_path))
    monkeypatch.setenv("MCP_SHARED_SECRET", "correct-horse")

    result = await translate_file(
        file_path=str(src),
        source_lang="en",
        target_lang="zh",
        output_format="docx",
        shared_secret="wrong-battery",
    )
    assert result["success"] is False
    assert result["error"]["code"] == "AUTH_FAILED"
