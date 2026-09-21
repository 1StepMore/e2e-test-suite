"""Tests for Phase 4.5 health check / readiness probe endpoints.

Verifies the in-process ``check()`` returns the expected JSON
shape, and that starting the HTTP server on ``OMNI_HEALTH_PORT``
(when ``OMNI_HEALTH_ENABLED=1``) returns 200 OK on ``/health``
with the same shape.  The HTTP server is NEVER started by
default — these tests enable it explicitly with the env var.
"""
from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

SUITE_ROOT = Path(__file__).resolve().parents[3]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _free_port() -> int:
    """Find a free localhost port."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _http_get(url: str, timeout: float = 2.0):
    req = urllib.request.Request(url)
    return urllib.request.urlopen(req, timeout=timeout)  # nosec B310 - localhost health probe only


class TestOPPCheck:
    @pytest.fixture
    def health_mod(self, monkeypatch):
        monkeypatch.delenv("OMNI_HEALTH_ENABLED", raising=False)
        return _load_module(
            "opp_health_under_test",
            SUITE_ROOT / "Omni_Pre_Processor" / "src" / "opp" / "mcp" / "health.py",
        )

    def test_check_returns_required_keys(self, health_mod):
        result = health_mod.check()
        assert result["status"] == "ok"
        assert result["module"] == "opp"
        assert "version" in result
        assert isinstance(result["version"], str)
        assert "uptime_s" in result
        assert isinstance(result["uptime_s"], int)
        assert result["uptime_s"] >= 0

    def test_health_server_off_by_default(self, health_mod, monkeypatch):
        monkeypatch.delenv("OMNI_HEALTH_ENABLED", raising=False)
        monkeypatch.setenv("OMNI_HEALTH_PORT", str(_free_port()))
        srv = health_mod.start_health_server()
        assert srv is None

    def test_health_server_serves_ok(self, health_mod, monkeypatch):
        port = _free_port()
        monkeypatch.setenv("OMNI_HEALTH_ENABLED", "1")
        monkeypatch.setenv("OMNI_HEALTH_PORT", str(port))
        try:
            srv = health_mod.start_health_server()
            assert srv is not None
            time.sleep(0.2)
            resp = _http_get(f"http://127.0.0.1:{port}/health")
            assert resp.status == 200
            body = json.loads(resp.read().decode("utf-8"))
            assert body["status"] == "ok"
            assert body["module"] == "opp"
        finally:
            health_mod.stop_health_server()

    def test_health_server_root_path(self, health_mod, monkeypatch):
        port = _free_port()
        monkeypatch.setenv("OMNI_HEALTH_ENABLED", "1")
        monkeypatch.setenv("OMNI_HEALTH_PORT", str(port))
        try:
            health_mod.start_health_server()
            time.sleep(0.2)
            resp = _http_get(f"http://127.0.0.1:{port}/")
            assert resp.status == 200
        finally:
            health_mod.stop_health_server()

    def test_health_server_unknown_path_404(self, health_mod, monkeypatch):
        port = _free_port()
        monkeypatch.setenv("OMNI_HEALTH_ENABLED", "1")
        monkeypatch.setenv("OMNI_HEALTH_PORT", str(port))
        try:
            health_mod.start_health_server()
            time.sleep(0.2)
            try:
                _http_get(f"http://127.0.0.1:{port}/nope")
                assert False, "expected 404"
            except urllib.error.HTTPError as e:
                assert e.code == 404
        finally:
            health_mod.stop_health_server()

    def test_default_health_port(self, health_mod):
        assert health_mod.DEFAULT_HEALTH_PORT == 8767


class TestOLCheck:
    @pytest.fixture
    def health_mod(self, monkeypatch):
        monkeypatch.delenv("OMNI_HEALTH_ENABLED", raising=False)
        monkeypatch.setenv("OMNI_TEST_FAKE_LLM", "1")
        return _load_module(
            "ol_health_under_test",
            SUITE_ROOT / "Omni_Localizer" / "src" / "ol_mcp" / "health.py",
        )

    def test_check_returns_required_keys(self, health_mod):
        result = health_mod.check()
        assert result["status"] == "ok"
        assert result["module"] == "ol"
        assert "version" in result
        assert "uptime_s" in result

    def test_health_server_serves_ok(self, health_mod, monkeypatch):
        port = _free_port()
        monkeypatch.setenv("OMNI_HEALTH_ENABLED", "1")
        monkeypatch.setenv("OMNI_HEALTH_PORT", str(port))
        try:
            srv = health_mod.start_health_server()
            assert srv is not None
            time.sleep(0.2)
            resp = _http_get(f"http://127.0.0.1:{port}/health")
            assert resp.status == 200
            body = json.loads(resp.read().decode("utf-8"))
            assert body["module"] == "ol"
        finally:
            health_mod.stop_health_server()


class TestORFCheck:
    @pytest.fixture
    def health_mod(self, monkeypatch):
        monkeypatch.delenv("OMNI_HEALTH_ENABLED", raising=False)
        return _load_module(
            "orf_health_under_test",
            SUITE_ROOT / "Omni_Re_Formatter" / "src" / "orf" / "mcp" / "health.py",
        )

    def test_check_returns_required_keys(self, health_mod):
        result = health_mod.check()
        assert result["status"] == "ok"
        assert result["module"] == "orf"
        assert "version" in result
        assert "uptime_s" in result

    def test_health_server_serves_ok(self, health_mod, monkeypatch):
        port = _free_port()
        monkeypatch.setenv("OMNI_HEALTH_ENABLED", "1")
        monkeypatch.setenv("OMNI_HEALTH_PORT", str(port))
        try:
            srv = health_mod.start_health_server()
            assert srv is not None
            time.sleep(0.2)
            resp = _http_get(f"http://127.0.0.1:{port}/health")
            assert resp.status == 200
            body = json.loads(resp.read().decode("utf-8"))
            assert body["module"] == "orf"
        finally:
            health_mod.stop_health_server()


class TestHealthPortIsSeparateFromStdio:
    """The health server must NEVER bind to a stdio fd — it is
    an HTTP server on a separate port.  This test guards
    against an accidental regression where someone wires the
    health handler into the MCP ``stdio_server()`` transport.
    """

    def test_opp_health_handler_uses_http_server(self):
        from http.server import BaseHTTPRequestHandler
        health_mod = _load_module(
            "opp_health_under_test",
            SUITE_ROOT / "Omni_Pre_Processor" / "src" / "opp" / "mcp" / "health.py",
        )
        assert issubclass(health_mod.HealthHandler, BaseHTTPRequestHandler)
        assert hasattr(health_mod.HealthHandler, "do_GET")


class TestMCPServerExposesHealthEndpoint:
    """Spawn an MCP server subprocess with the health endpoint
    enabled, then hit ``/health`` on the configured port and
    assert 200 OK.  This is the make-test-health scenario: the
    MCP stdio transport and the health HTTP server must coexist
    in the same process.
    """

    def _spawn_mcp(
        self,
        module: str,
        src_dir: Path,
        health_port: int,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.Popen:
        env = os.environ.copy()
        env["OMNI_HEALTH_ENABLED"] = "1"
        env["OMNI_HEALTH_PORT"] = str(health_port)
        env["PATH"] = str(SUITE_ROOT / ".venv_ol" / "bin") + ":" + env.get("PATH", "")
        env["OMNI_TEST_FAKE_LLM"] = "1"
        env["OMNI_TEST_FAKE_PANDOC"] = "1"
        env["OMNI_LOG_FORMAT"] = "json"
        env["PYTHONPATH"] = str(src_dir) + os.pathsep + env.get("PYTHONPATH", "")
        if extra_env:
            env.update(extra_env)
        return subprocess.Popen(
            [sys.executable, "-u", "-m", module],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

    def test_opp_mcp_with_health_endpoint(self):
        port = _free_port()
        proc = self._spawn_mcp(
            "opp.mcp.server",
            SUITE_ROOT / "Omni_Pre_Processor" / "src",
            port,
            extra_env={"OPP_MCP_ALLOWED_DIRS": str(SUITE_ROOT)},
        )
        try:
            for _ in range(40):
                time.sleep(0.5)
                try:
                    resp = _http_get(f"http://127.0.0.1:{port}/health", timeout=1)
                    break
                except (urllib.error.URLError, ConnectionError):
                    continue
            else:
                pytest.fail("OPP MCP server did not start serving /health within 20s")
            assert resp.status == 200
            body = json.loads(resp.read().decode("utf-8"))
            assert body["status"] == "ok"
            assert body["module"] == "opp"
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    def test_ol_mcp_with_health_endpoint(self):
        port = _free_port()
        proc = self._spawn_mcp(
            "ol_mcp",
            SUITE_ROOT / "Omni_Localizer" / "src",
            port,
        )
        try:
            for _ in range(60):
                time.sleep(0.5)
                try:
                    resp = _http_get(f"http://127.0.0.1:{port}/health", timeout=1)
                    break
                except (urllib.error.URLError, ConnectionError):
                    continue
            else:
                pytest.fail("OL MCP server did not start serving /health within 30s")
            assert resp.status == 200
            body = json.loads(resp.read().decode("utf-8"))
            assert body["status"] == "ok"
            assert body["module"] == "ol"
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    def test_orf_mcp_with_health_endpoint(self):
        port = _free_port()
        proc = self._spawn_mcp(
            "orf.mcp.server",
            SUITE_ROOT / "Omni_Re_Formatter" / "src",
            port,
            extra_env={"ORF_MCP_ALLOWED_DIRS": str(SUITE_ROOT)},
        )
        try:
            for _ in range(20):
                time.sleep(0.5)
                try:
                    resp = _http_get(f"http://127.0.0.1:{port}/health", timeout=1)
                    break
                except (urllib.error.URLError, ConnectionError):
                    continue
            else:
                pytest.fail("ORF MCP server did not start serving /health within 10s")
            assert resp.status == 200
            body = json.loads(resp.read().decode("utf-8"))
            assert body["status"] == "ok"
            assert body["module"] == "orf"
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
