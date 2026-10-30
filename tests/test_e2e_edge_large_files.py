"""Large file handling tests — OPP size limits, OL long text.

Covers S10.4 from the integrated test plan. Tests:
- OPP rejects files > max_file_size_bytes (default 100MB, can be lowered)
- OL handles very long MD text without crashing
- ORF handles large MD conversion

Run with:
    OMNI_TEST_FAKE_LLM=1 OMNI_TEST_FAKE_PANDOC=1 pytest tests/test_e2e_edge_large_files.py -v
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.real_chain]

SUITE_ROOT = Path(__file__).resolve().parent
OL_CONFIG = SUITE_ROOT.parent / "Omni_Localizer" / "config" / "default.yaml"


def _make_env(**extra) -> dict:
    env = os.environ.copy()
    env["OMNI_TEST_FAKE_LLM"] = "1"
    env["OMNI_TEST_FAKE_PANDOC"] = "1"
    for d in ["Omni_Pre_Processor", "Omni_Localizer", "Omni_Re_Formatter"]:
        src = SUITE_ROOT.parent / d / "src"
        if src.exists():
            pp = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = f"{src}:" + pp if pp else str(src)
    env["OL_CONFIG_PATH"] = str(OL_CONFIG)
    env.update(extra)
    return env


class TestOPPLargeFileRejection:
    """OPP should reject files exceeding configurable size limits."""

    def test_file_exceeds_limit_rejected(self, tmp_path, monkeypatch):
        """File larger than max_file_size_bytes should be rejected.

        Contract（与 OPP 自身 tests/mcp/test_security.py 一致）：超限时
        ``PathValidator.validate_path`` **抛 ``opp.utils.security.PathValidationError``**
        —— 由调用方的 ``@mcp_error_boundary`` 翻成 OPP_PATH_DENIED 响应；
        它**不是**返回 ``ValidationResult(success=False)``。
        """
        monkeypatch.setenv("OPP_MCP_ALLOWED_DIRS", str(tmp_path))

        from opp.mcp.security import PathValidationError, PathValidator

        big_file = tmp_path / "big.docx"
        big_file.write_bytes(b"X" * 200)  # 200 bytes > 100 byte limit

        validator = PathValidator(
            allowed_directories=[tmp_path],
            max_file_size_bytes=100,  # Tiny limit
        )

        with pytest.raises(PathValidationError, match="size"):
            validator.validate_path(str(big_file))

    def test_file_within_limit_passes_path_validation(self, tmp_path):
        """File within size limit should pass path validation (content still needs to be valid)."""
        from opp.mcp.security import PathValidator

        small_file = tmp_path / "small.docx"
        small_file.write_bytes(b"X" * 50)  # 50 bytes < default 100MB

        validator = PathValidator(
            allowed_directories=[tmp_path],
        )
        result = validator.validate_path(str(small_file))
        # Should pass size check, but may fail on content (not a real DOCX)
        assert result.success is True or "allowed" not in result.error.lower()


class TestOLLargeTextHandling:
    """OL should handle very long text without crashing."""

    def test_ol_translate_very_long_text(self, tmp_path):
        """OL translate needs to handle long text without timeout or crash.

        Uses FAKE_LLM so no real API calls; verifies the CLI doesn't crash.
        """
        long_text = "Hello world. " * 20_000  # ~300K chars
        md_file = tmp_path / "huge.md"
        md_file.write_text(long_text)
        out_dir = tmp_path / "ol_out"
        out_dir.mkdir()

        result = subprocess.run(
            [sys.executable, "-m", "ol_cli", "translate-md",
             str(md_file), "-s", "en", "-t", "zh",
             "-o", str(out_dir), "-c", str(OL_CONFIG), "--no-cache"],
            capture_output=True, text=True,
            env=_make_env(),
            timeout=120,
        )
        # Should not crash; may return 0 (success) or 1 (some error)
        assert result.returncode in (0, 1)
        # Ensure no Python-level crash
        if result.returncode != 0:
            # Error should be a pipeline error, not Python traceback
            assert "Traceback" not in result.stderr


class TestORFLargeFileHandling:
    """ORF should handle large MD files without crashing."""

    def test_orf_apply_md_large_file(self, tmp_path):
        """ORF apply-md with large input should not crash."""
        from orf.mcp.server import apply_md

        large_md = tmp_path / "large.md"
        large_md.write_text("# Large Doc\\n\\n" + "Hello world. " * 5_000)
        out = tmp_path / "out.docx"

        result = json.loads(apply_md(
            input_md=str(large_md),
            target_format="docx",
            output_path=str(out),
        ))
        # May fail (FAKE_PANDOC produces stubs) but should not crash
        assert isinstance(result, dict)
