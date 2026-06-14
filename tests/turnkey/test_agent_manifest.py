"""Tests for Phase 0.6 — Agent manifest (production contract).

Verifies that ``scripts/turnkey/agent_manifest.py`` writes a
machine-readable ``agent_manifest.json`` with the 6 required keys
documented in the design contract:
    inputs, outputs, config, retry_policy, quality_gate, supported_languages
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make scripts/ importable
SUITE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SUITE_ROOT / "scripts"))

from turnkey.agent_manifest import MANIFEST_TEMPLATE, write_manifest  # noqa: E402


REQUIRED_KEYS = {
    "inputs",
    "outputs",
    "config",
    "retry_policy",
    "quality_gate",
    "supported_languages",
}


class TestAgentManifestContract:
    """``agent_manifest.json`` has all 6 required top-level keys."""

    def test_manifest_template_has_all_required_keys(self) -> None:
        """Template dict has all 6 required keys."""
        assert set(MANIFEST_TEMPLATE.keys()) == REQUIRED_KEYS

    def test_manifest_includes_supported_languages(self) -> None:
        """Template declares supported_languages (zh, en)."""
        assert "supported_languages" in MANIFEST_TEMPLATE
        assert set(MANIFEST_TEMPLATE["supported_languages"]) >= {"zh", "en"}

    def test_write_manifest_produces_valid_json(self, tmp_path: Path) -> None:
        """``write_manifest`` writes a loadable JSON with all 6 keys."""
        write_manifest(tmp_path)

        manifest_path = tmp_path / "agent_manifest.json"
        assert manifest_path.exists()

        loaded = json.loads(manifest_path.read_text())
        assert set(loaded.keys()) == REQUIRED_KEYS

    def test_write_manifest_handles_missing_run_dir(self, tmp_path: Path) -> None:
        """Does not crash when run_dir is invalid."""
        nonexistent = tmp_path / "does_not_exist"
        # Should not raise
        write_manifest(nonexistent)
        # And should not create the directory
        assert not nonexistent.exists()
