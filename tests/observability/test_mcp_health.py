"""Tests for Phase B4: health check endpoints.

Verifies the ping() tool returns success with module name and version
for both OL and ORF MCP servers. Auth is checked (per Phase A4).
"""

import asyncio
import json



class TestOLHealthEndpoint:
    def test_ping_returns_success_no_auth_env(self, monkeypatch):
        monkeypatch.delenv("MCP_SHARED_SECRET", raising=False)
        from ol_mcp.tools import ping
        result = json.loads(asyncio.run(ping()))
        assert result["success"] is True
        assert result["content"]["module"] == "ol"
        assert "version" in result["content"]
        assert isinstance(result["content"]["version"], str)

    def test_ping_with_correct_auth(self, monkeypatch):
        monkeypatch.setenv("MCP_SHARED_SECRET", "test-secret")
        from ol_mcp.tools import ping
        result = json.loads(asyncio.run(ping(auth_token="test-secret")))
        assert result["success"] is True
        assert result["content"]["module"] == "ol"

    def test_ping_with_wrong_auth(self, monkeypatch):
        monkeypatch.setenv("MCP_SHARED_SECRET", "test-secret")
        from ol_mcp.tools import ping
        result = json.loads(asyncio.run(ping(auth_token="wrong")))
        assert result["success"] is False
        assert result["error_code"] == "AUTH_FAILED"


class TestORFHealthEndpoint:
    def test_ping_returns_success_no_auth_env(self, monkeypatch):
        monkeypatch.delenv("MCP_SHARED_SECRET", raising=False)
        from orf.mcp.server import ping
        result = json.loads(ping())
        assert result["success"] is True
        assert result["content"]["module"] == "orf"
        assert "version" in result["content"]
        assert isinstance(result["content"]["version"], str)

    def test_ping_with_correct_auth(self, monkeypatch):
        monkeypatch.setenv("MCP_SHARED_SECRET", "test-secret")
        from orf.mcp.server import ping
        result = json.loads(ping(auth_token="test-secret"))
        assert result["success"] is True
        assert result["content"]["module"] == "orf"

    def test_ping_with_wrong_auth(self, monkeypatch):
        monkeypatch.setenv("MCP_SHARED_SECRET", "test-secret")
        from orf.mcp.server import ping
        result = json.loads(ping(auth_token="wrong"))
        assert result["success"] is False
        assert result["error_code"] == "AUTH_FAILED"
