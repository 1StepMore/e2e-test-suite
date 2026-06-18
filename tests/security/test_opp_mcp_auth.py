"""Tests for OPP MCP shared-secret auth (round 16 Phase A4).

Mirrors the OL auth test structure. OPP tools take individual
parameters (not Pydantic models), so auth_token is a keyword
parameter, not a field on an input model.
"""

import pytest

from opp.mcp.auth import auth_failure_response, check_auth


class TestCheckAuthDisabled:
    def test_no_env_var_returns_pass(self, monkeypatch):
        monkeypatch.delenv("MCP_SHARED_SECRET", raising=False)
        ok, err = check_auth(None)
        assert ok is True
        assert err is None

    def test_no_env_var_with_secret_returns_pass(self, monkeypatch):
        monkeypatch.delenv("MCP_SHARED_SECRET", raising=False)
        ok, err = check_auth("any")
        assert ok is True


class TestCheckAuthEnabled:
    def test_correct_secret_returns_pass(self, monkeypatch):
        monkeypatch.setenv("MCP_SHARED_SECRET", "s3cr3t")
        ok, err = check_auth("s3cr3t")
        assert ok is True

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


class TestAuthFailureResponse:
    def test_response_shape(self):
        resp = auth_failure_response()
        assert resp["success"] is False
        assert resp["error_code"] == "AUTH_FAILED"
        assert "auth_token" in resp["message"]


class TestToolsRejectBadAuth:
    @pytest.fixture(autouse=True)
    def enable_auth(self, monkeypatch):
        monkeypatch.setenv("MCP_SHARED_SECRET", "test-secret-123")

    @pytest.mark.asyncio
    async def test_detect_format_rejects_wrong_secret(self):
        from opp.mcp.server import detect_format_tool
        result = await detect_format_tool("/tmp/x.docx", auth_token="wrong")
        assert result["success"] is False
        assert result["error_code"] == "AUTH_FAILED"

    @pytest.mark.asyncio
    async def test_ping_rejects_wrong_secret(self):
        from opp.mcp.server import ping
        result = await ping(auth_token="wrong")
        assert result["success"] is False
        assert result["error_code"] == "AUTH_FAILED"
