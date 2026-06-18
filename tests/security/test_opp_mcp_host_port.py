"""Tests for OPP MCP host/port config (round 16 Phase A3).

The MCP server must NOT default to FastMCP's 0.0.0.0:8000 (binds
to all interfaces, no auth). After Phase A3, the default is
127.0.0.1:8766, overridable via OPP_MCP_HOST / OPP_MCP_PORT env
vars. This test guards against accidental regression to the
insecure default.
"""

import logging
from pathlib import Path

import pytest

from opp.mcp.config import MCPConfig, load_config


@pytest.fixture
def allowed_dir(tmp_path):
    """A valid allowed dir (required by load_config)."""
    d = tmp_path / "allowed"
    d.mkdir()
    return d


@pytest.fixture
def env_setup(monkeypatch, allowed_dir):
    """Set OPP_MCP_ALLOWED_DIRS and clear other env vars for clean tests."""
    monkeypatch.setenv("OPP_MCP_ALLOWED_DIRS", str(allowed_dir))
    # Clear host/port env vars so we test defaults
    monkeypatch.delenv("OPP_MCP_HOST", raising=False)
    monkeypatch.delenv("OPP_MCP_PORT", raising=False)


class TestMCPConfigDefaults:
    """Default host/port must be loopback, not 0.0.0.0."""

    def test_default_host_is_loopback(self, env_setup):
        cfg = load_config()
        assert cfg.host == "127.0.0.1", (
            f"Default host must be 127.0.0.1 (loopback), got {cfg.host!r}. "
            f"0.0.0.0 binds to all interfaces with no auth — see round-15 audit."
        )

    def test_default_port_is_8766(self, env_setup):
        cfg = load_config()
        assert cfg.port == 8766, (
            f"Default port must be 8766, got {cfg.port}. "
            f"(ORF uses 8765; different port so both can run simultaneously.)"
        )

    def test_dataclass_default_host_is_loopback(self):
        """MCPConfig dataclass default for host is 127.0.0.1."""
        cfg = MCPConfig(allowed_directories=[Path("/tmp")])
        assert cfg.host == "127.0.0.1"

    def test_dataclass_default_port_is_8766(self):
        """MCPConfig dataclass default for port is 8766."""
        cfg = MCPConfig(allowed_directories=[Path("/tmp")])
        assert cfg.port == 8766


class TestMCPConfigEnvOverride:
    """OPP_MCP_HOST and OPP_MCP_PORT env vars override defaults."""

    def test_env_host_overrides_default(self, monkeypatch, allowed_dir):
        monkeypatch.setenv("OPP_MCP_ALLOWED_DIRS", str(allowed_dir))
        monkeypatch.setenv("OPP_MCP_HOST", "0.0.0.0")  # explicit opt-in
        monkeypatch.delenv("OPP_MCP_PORT", raising=False)
        cfg = load_config()
        assert cfg.host == "0.0.0.0"

    def test_env_port_overrides_default(self, monkeypatch, allowed_dir):
        monkeypatch.setenv("OPP_MCP_ALLOWED_DIRS", str(allowed_dir))
        monkeypatch.setenv("OPP_MCP_PORT", "9999")
        monkeypatch.delenv("OPP_MCP_HOST", raising=False)
        cfg = load_config()
        assert cfg.port == 9999

    def test_invalid_env_port_falls_back_to_default(
        self, monkeypatch, allowed_dir, caplog
    ):
        """Non-integer OPP_MCP_PORT logs warning, falls back to 8766."""
        monkeypatch.setenv("OPP_MCP_ALLOWED_DIRS", str(allowed_dir))
        monkeypatch.setenv("OPP_MCP_PORT", "not-a-number")
        monkeypatch.delenv("OPP_MCP_HOST", raising=False)
        with caplog.at_level(logging.WARNING):
            cfg = load_config()
        assert cfg.port == 8766
        assert any("OPP_MCP_PORT" in r.message for r in caplog.records)
