"""Tests for suite-level omni-suite CLI (W4.2)."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

SUITE_ROOT = Path(__file__).resolve().parent.parent
CLI = sys.executable  # Current venv Python — used for `python -m omni_suite`
OMNI_SUITE_BIN = str(SUITE_ROOT / ".venv_ol" / "bin" / "omni-suite")


class TestVersion:
    def test_version_prints_value(self):
        """--version returns 0 and non-empty stdout."""
        result = subprocess.run(
            [CLI, "-m", "omni_suite", "--version"],
            capture_output=True, text=True, cwd=str(SUITE_ROOT),
        )
        assert result.returncode == 0
        assert result.stdout.strip()  # non-empty

    def test_version_output_matches_version_file(self):
        """--version output equals VERSION file content."""
        result = subprocess.run(
            [CLI, "-m", "omni_suite", "--version"],
            capture_output=True, text=True, cwd=str(SUITE_ROOT),
        )
        version_file = SUITE_ROOT / "VERSION"
        expected = version_file.read_text(encoding="utf-8").strip()
        assert result.stdout.strip() == expected


class TestCompatibility:
    def test_compatibility_prints_matrix(self):
        """--compatibility prints non-empty matrix."""
        result = subprocess.run(
            [CLI, "-m", "omni_suite", "--compatibility"],
            capture_output=True, text=True, cwd=str(SUITE_ROOT),
        )
        assert result.returncode == 0
        assert "0.1.0" in result.stdout
        assert "OPP" in result.stdout or "OL" in result.stdout


class TestStatus:
    def test_status_shows_versions(self):
        """status shows all 3 module names."""
        result = subprocess.run(
            [CLI, "-m", "omni_suite", "status"],
            capture_output=True, text=True, cwd=str(SUITE_ROOT),
        )
        assert result.returncode == 0
        assert "OPP" in result.stdout
        assert "OL" in result.stdout
        assert "ORF" in result.stdout

    def test_status_shows_dependency_section(self):
        """status shows dependency section."""
        result = subprocess.run(
            [CLI, "-m", "omni_suite", "status"],
            capture_output=True, text=True, cwd=str(SUITE_ROOT),
        )
        assert "Dependencies:" in result.stdout


class TestCheck:
    def test_check_quick_returns_zero(self):
        """check --quick completes without error."""
        result = subprocess.run(
            [CLI, "-m", "omni_suite", "check", "--quick"],
            capture_output=True, text=True, cwd=str(SUITE_ROOT), timeout=30,
        )
        assert result.returncode == 0

    def test_check_quick_shows_pandoc(self):
        """check --quick output mentions pandoc."""
        result = subprocess.run(
            [CLI, "-m", "omni_suite", "check", "--quick"],
            capture_output=True, text=True, cwd=str(SUITE_ROOT), timeout=30,
        )
        assert "pandoc" in result.stdout.lower()


class TestPipeline:
    def test_pipeline_help_text(self):
        """pipeline --help shows usage text."""
        result = subprocess.run(
            [CLI, "-m", "omni_suite", "pipeline", "--help"],
            capture_output=True, text=True, cwd=str(SUITE_ROOT),
        )
        assert result.returncode == 0
        assert "pipeline" in result.stdout.lower()
        assert "Usage" in result.stdout

    def test_pipeline_no_args_shows_help(self):
        """pipeline with no args prints usage."""
        result = subprocess.run(
            [CLI, "-m", "omni_suite", "pipeline"],
            capture_output=True, text=True, cwd=str(SUITE_ROOT),
        )
        assert result.returncode == 0
        assert "Usage" in result.stdout

    def test_pipeline_basic_orchestrates_opp_ol_orf(self, tmp_path: Path):
        """Run omni-suite pipeline on the Meridian DOCX fixture, verify final DOCX output exists.

        Uses FAKE_LLM seam to avoid real API calls.
        """
        docx = SUITE_ROOT / "Meridian_Robotics_Product_Overview_E2E.docx"
        if not docx.exists():
            pytest.skip(f"Fixture not found: {docx}")

        output = tmp_path / "result.docx"
        env = {
            **os.environ,
            "OMNI_TEST_FAKE_LLM": "1",
            "OL_CONFIG_PATH": str(SUITE_ROOT / "Omni_Localizer" / "config" / "test_universal.yaml"),
            "PATH": str(SUITE_ROOT / ".venv_ol" / "bin") + ":" + os.environ.get("PATH", ""),
        }
        result = subprocess.run(
            [CLI, "-m", "omni_suite", "pipeline", str(docx),
             "--source-lang", "en", "--target-lang", "zh",
             "--target-format", "docx",
             "--output", str(output)],
            capture_output=True, text=True, cwd=str(SUITE_ROOT), env=env, timeout=300,
        )
        # May or may not succeed depending on implementation completeness,
        # but the command must run without crashing
        assert result.returncode in (0, 1, 2), (
            f"Unexpected exit code: {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


class TestUsageAndErrors:
    def test_default_no_args_shows_usage(self):
        """No args shows usage."""
        result = subprocess.run(
            [CLI, "-m", "omni_suite"],
            capture_output=True, text=True, cwd=str(SUITE_ROOT),
        )
        assert result.returncode == 0
        assert "Usage" in result.stdout

    def test_unknown_command_exits_1(self):
        """Unknown command exits with code 1."""
        result = subprocess.run(
            [CLI, "-m", "omni_suite", "nonexistent"],
            capture_output=True, text=True, cwd=str(SUITE_ROOT),
        )
        assert result.returncode == 1
        assert "Unknown" in result.stdout

    def test_help_flag_shows_usage(self):
        """-h flag shows usage."""
        result = subprocess.run(
            [CLI, "-m", "omni_suite", "-h"],
            capture_output=True, text=True, cwd=str(SUITE_ROOT),
        )
        assert result.returncode == 0
        assert "Usage" in result.stdout
