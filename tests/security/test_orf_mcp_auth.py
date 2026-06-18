"""Tests for ORF MCP shared-secret auth (round 16 Phase A4).

ORF tools are sync (not async) and take auth_token as a keyword
parameter. Mirrors the OL/OPP auth test structure.
"""

import json

import pytest

from orf.mcp.auth import auth_failure_response, check_auth


class TestCheckAuthDisabled:
    def test_no_env_var_returns_pass(self, monkeypatch):
        monkeypatch.delenv("MCP_SHARED_SECRET", raising=False)
        ok, err = check_auth(None)
        assert ok is True
        assert err is None


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

    def test_detect_format_rejects_wrong_secret(self):
        from orf.mcp.server import detect_format
        result = detect_format("/tmp/x.docx", auth_token="wrong")
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert parsed["error_code"] == "AUTH_FAILED"

    def test_info_rejects_wrong_secret(self):
        from orf.mcp.server import info
        result = info("/tmp/x.docx", auth_token="wrong")
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert parsed["error_code"] == "AUTH_FAILED"
