"""Tests for OL MCP shared-secret auth (round 16 Phase A4).

When ``MCP_SHARED_SECRET`` env var is set, every tool call must
include a ``shared_secret`` field matching that value. If the
env var is not set, auth is disabled (dev / stdio mode).
"""

import json

import pytest

from ol_mcp.auth import auth_failure_response, check_auth


@pytest.fixture
def allowed_dir(tmp_path):
    """An allowed directory with one valid JSON file.

    Duplicated from test_ol_mcp_path_traversal.py to keep this
    test file self-contained (pytest fixtures don't cross files
    unless defined in conftest.py).
    """
    d = tmp_path / "allowed"
    d.mkdir()
    (d / "glossary.json").write_text('{"hello": {"translation": "你好"}}')
    (d / "tm.tmx").write_text("<tmx>empty</tmx>")
    return d


# ---------------------------------------------------------------------------
# Unit tests: check_auth()
# ---------------------------------------------------------------------------

class TestCheckAuthDisabled:
    """When MCP_SHARED_SECRET is not set, auth is disabled."""

    def test_no_env_var_returns_pass(self, monkeypatch):
        monkeypatch.delenv("MCP_SHARED_SECRET", raising=False)
        ok, err = check_auth(None)
        assert ok is True
        assert err is None

    def test_no_env_var_with_secret_returns_pass(self, monkeypatch):
        """Auth is disabled, so any provided secret is accepted."""
        monkeypatch.delenv("MCP_SHARED_SECRET", raising=False)
        ok, err = check_auth("any-secret")
        assert ok is True
        assert err is None


class TestCheckAuthEnabled:
    """When MCP_SHARED_SECRET is set, provided secret must match."""

    def test_correct_secret_returns_pass(self, monkeypatch):
        monkeypatch.setenv("MCP_SHARED_SECRET", "s3cr3t")
        ok, err = check_auth("s3cr3t")
        assert ok is True
        assert err is None

    def test_wrong_secret_returns_fail(self, monkeypatch):
        monkeypatch.setenv("MCP_SHARED_SECRET", "s3cr3t")
        ok, err = check_auth("wrong")
        assert ok is False
        assert err == "AUTH_FAILED"

    def test_missing_secret_returns_fail(self, monkeypatch):
        monkeypatch.setenv("MCP_SHARED_SECRET", "s3cr3t")
        ok, err = check_auth(None)
        assert ok is False
        assert err == "AUTH_FAILED"

    def test_empty_secret_returns_fail(self, monkeypatch):
        monkeypatch.setenv("MCP_SHARED_SECRET", "s3cr3t")
        ok, err = check_auth("")
        assert ok is False
        assert err == "AUTH_FAILED"


class TestAuthFailureResponse:
    """auth_failure_response returns the standard error dict."""

    def test_response_shape(self):
        resp = auth_failure_response()
        assert resp["success"] is False
        assert resp["error_code"] == "AUTH_FAILED"
        assert "shared_secret" in resp["message"].lower()


# ---------------------------------------------------------------------------
# Integration tests: tools reject bad auth, accept good auth
# ---------------------------------------------------------------------------

class TestToolsRejectBadAuth:
    """Tool functions return AUTH_FAILED when secret is wrong/missing."""

    @pytest.fixture(autouse=True)
    def enable_auth(self, monkeypatch):
        """Enable auth for each test in this class."""
        monkeypatch.setenv("MCP_SHARED_SECRET", "test-secret-123")

    @pytest.mark.asyncio
    async def test_translate_md_text_rejects_wrong_secret(self):
        from ol_mcp.tools import TranslateInput, translate_md_text
        params = TranslateInput(
            content="Hello",
            source_lang="en",
            target_lang="zh",
            shared_secret="wrong-secret",
        )
        result = await translate_md_text(params)
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert parsed["error_code"] == "AUTH_FAILED"

    @pytest.mark.asyncio
    async def test_judge_text_rejects_missing_secret(self):
        from ol_mcp.tools import JudgeInput, judge_text
        params = JudgeInput(source="Hello", target="你好", shared_secret=None)
        result = await judge_text(params)
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert parsed["error_code"] == "AUTH_FAILED"

    @pytest.mark.asyncio
    async def test_load_glossary_rejects_wrong_secret(self, allowed_dir):
        from ol_mcp.tools import LoadGlossaryInput, load_glossary
        params = LoadGlossaryInput(
            path=str(allowed_dir / "glossary.json"),
            shared_secret="wrong",
        )
        result = await load_glossary(params)
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert parsed["error_code"] == "AUTH_FAILED"

    @pytest.mark.asyncio
    async def test_search_tm_rejects_wrong_secret(self, allowed_dir):
        from ol_mcp.tools import SearchTMInput, search_tm
        params = SearchTMInput(
            source_text="hello",
            tmx_path=str(allowed_dir / "tm.tmx"),
            shared_secret="wrong",
        )
        result = await search_tm(params)
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert parsed["error_code"] == "AUTH_FAILED"


class TestToolsAcceptGoodAuth:
    """When the right secret is provided, auth passes (subsequent
    errors are about the actual content, not auth)."""

    @pytest.fixture(autouse=True)
    def enable_auth(self, monkeypatch):
        monkeypatch.setenv("MCP_SHARED_SECRET", "test-secret-123")

    @pytest.mark.asyncio
    async def test_judge_text_with_correct_secret_runs(self):
        """The judge call should proceed past the auth check and fail
        on something else (e.g., the LLM isn't available in tests),
        but NOT with AUTH_FAILED."""
        from ol_mcp.tools import JudgeInput, judge_text
        params = JudgeInput(
            source="Hello",
            target="你好",
            shared_secret="test-secret-123",
        )
        result = await judge_text(params)
        parsed = json.loads(result)
        # If auth passed, the error_code should NOT be AUTH_FAILED.
        if not parsed["success"]:
            assert parsed.get("error_code") != "AUTH_FAILED", (
                f"Auth should have passed but got: {parsed}"
            )
