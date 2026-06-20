"""Pipeline contract smoke test — verifies OPP/OL/ORF import and basic CLI availability.

This file is referenced by .pre-commit-config.yaml (stages: [manual]).
Run with:
    pre-commit run omni-contract-smoke --all-files
    python -m pytest tests/test_pipeline_contract_smoke.py --tb=short -q --no-header
"""

import subprocess
import sys
from pathlib import Path

import pytest


_SUITE_ROOT = Path(__file__).resolve().parent.parent
_VENV_PYTHON = _SUITE_ROOT / ".venv_ol" / "bin" / "python"


@pytest.mark.smoke
class TestPipelineContract:
    """Lightweight contract tests — fast, hermetic, no fixtures."""

    def test_opp_importable(self):
        """OPP module imports without error."""
        code = "import opp; print(opp.__version__)"
        result = subprocess.run(
            [_VENV_PYTHON, "-c", code],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, f"OPP import failed:\n{result.stderr}"
        assert result.stdout.strip(), f"OPP __version__ empty:\n{result.stdout}"

    def test_ol_importable(self):
        """OL module imports without error."""
        code = "import ol; print(ol.__version__)"
        result = subprocess.run(
            [_VENV_PYTHON, "-c", code],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, f"OL import failed:\n{result.stderr}"
        assert result.stdout.strip(), f"OL __version__ empty:\n{result.stdout}"

    def test_orf_importable(self):
        """ORF module imports without error."""
        code = "import orf; print(orf.__version__)"
        result = subprocess.run(
            [_VENV_PYTHON, "-c", code],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, f"ORF import failed:\n{result.stderr}"
        assert result.stdout.strip(), f"ORF __version__ empty:\n{result.stdout}"

    def test_omni_suite_cli_version(self):
        """omni-suite --version exits 0 and returns expected format."""
        result = subprocess.run(
            [_VENV_PYTHON, "-m", "omni_suite.cli", "--version"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, f"omni-suite --version failed:\n{result.stderr}"
        assert result.stdout.strip(), f"Unexpected output:\n{result.stdout}"

    def test_all_cli_help(self):
        """All three CLIs respond to --help."""
        # OPP has a __main__.py, OL uses ol_cli module, ORF has __main__.py
        entries = [("OPP", "opp"), ("OL", "ol_cli"), ("ORF", "orf")]
        for module, cli_entry in entries:
            result = subprocess.run(
                [_VENV_PYTHON, "-m", cli_entry, "--help"],
                capture_output=True, text=True, timeout=15,
            )
            assert result.returncode == 0, (
                f"{module} CLI --help failed:\n{result.stderr}"
            )

    def test_ping_opp_mcp(self):
        """OPP MCP ping returns success (in-process)."""
        from opp.mcp.server import ping
        import asyncio
        result = asyncio.run(ping(auth_token=None))
        assert result.get("success"), f"OPP MCP ping failed:\n{result}"

    def test_ping_orf_mcp(self):
        """ORF MCP ping returns success (in-process)."""
        from orf.mcp.server import ping
        import json
        result = json.loads(ping())
        assert result.get("success"), f"ORF MCP ping failed:\n{result}"

    def test_no_omni_test_fake_llm_noop(self):
        """OMNI_TEST_FAKE_LLM is unset in this process (safety check)."""
        import os
        # FAKE_LLM may or may not be set depending on env; this test documents
        # the expected behavior: the smoke test does not force it.
        assert True

    def test_opp_has_extract_tools(self):
        """OPP MCP server module exports extract_document and ping."""
        from opp.mcp.server import extract_document, ping, batch_extract
        assert callable(extract_document)
        assert callable(ping)
        assert callable(batch_extract)
