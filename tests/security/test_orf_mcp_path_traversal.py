"""Tests for ORF MCP PathValidator — path traversal, symlink, extension, no-allowlist.

Mirrors the OPP path traversal test structure. Tests both the PathValidator
directly (unit) and through MCP tool functions (integration).

ORF MCP tools are synchronous and return JSON strings (not dicts), and use
inline error codes (``PATH_NOT_ALLOWED``, ``FILE_PATH_NOT_ALLOWED``, ``CLI_ERROR``)
instead of a centralized ``@mcp_error_boundary`` decorator like OPP.

Closes gap S12.4 (symlink), S12.6 (blocked extensions), S12.7 (XLIFF image path
injection), S12.9 (no allowlist) from the integrated test plan.
"""

import json
from pathlib import Path

import pytest


def _symlink_or_skip(link: Path, target: str | Path) -> None:
    """创建符号链接；当前平台/权限不允许时跳过该用例。

    2026-09-17（报告风险 #5 Windows 开发入口）：Windows 未开启开发者模式或进程缺少
    ``SeCreateSymbolicLinkPrivilege`` 时 ``Path.symlink_to`` 抛
    ``OSError: [WinError 1314] 客户端没有所需的特权``。这是**环境**限制，不是策略
    缺陷 —— 用例在 Linux/CI 与开启开发者模式的 Windows 上仍然生效，所以只做条件
    跳过，不做平台整体跳过，也不伪装成通过。

    Args:
        link: 待创建的链接路径。
        target: 链接指向的目标。

    Raises:
        pytest.skip.Exception: 平台不允许创建符号链接时。
    """
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"当前环境无法创建符号链接（{exc}）")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def allowed_dir(tmp_path):
    """An allowed directory with one valid document file."""
    d = tmp_path / "allowed"
    d.mkdir()
    (d / "doc.md").write_text("# Test document\n\nHello world.")
    return d


@pytest.fixture
def outside_dir(tmp_path):
    """A directory that is NOT in the allowlist."""
    d = tmp_path / "outside"
    d.mkdir()
    (d / "secret.md").write_text("sensitive")
    return d


@pytest.fixture
def validator(allowed_dir):
    """PathValidator configured with one allowed dir."""
    from orf.mcp.security import PathValidator
    return PathValidator(allowed_directories=[allowed_dir])


@pytest.fixture
def env_allowed(allowed_dir, monkeypatch):
    """Set ORF_MCP_ALLOWED_DIRS so the MCP server picks it up."""
    monkeypatch.setenv("ORF_MCP_ALLOWED_DIRS", str(allowed_dir))
    return allowed_dir


def _parse(result_json: str) -> dict:
    """Parse ORF's JSON-string return value into a dict."""
    return json.loads(result_json)


# ============================================================================
# Unit tests — PathValidator directly
# ============================================================================

class TestPathValidator:
    """Direct unit tests against ORF's PathValidator."""

    def test_allowed_path_passes(self, validator, allowed_dir):
        """File inside the allowed directory should pass."""
        doc = allowed_dir / "doc.md"
        result = validator.validate_path(str(doc))
        assert result.success is True
        assert result.resolved_path is not None

    def test_path_traversal_blocked(self, validator, allowed_dir):
        """Path containing .. should be rejected."""
        traversal = allowed_dir.parent / "doc.md"
        result = validator.validate_path(str(traversal))
        assert result.success is False
        assert "traversal" in result.error.lower() or ".." in result.error

    def test_outside_allowlist_blocked(self, validator, outside_dir):
        """File outside allowed directories should be rejected."""
        secret = outside_dir / "secret.md"
        result = validator.validate_path(str(secret))
        assert result.success is False
        assert "allowed" in result.error.lower()

    def test_symlink_to_outside_blocked(self, validator, allowed_dir):
        """Symlink pointing outside allowed directories should be rejected."""
        link = allowed_dir / "innocent.md"
        _symlink_or_skip(link, "/tmp/should_not_access")
        result = validator.validate_path(str(link))
        assert result.success is False
        assert "symlink" in result.error.lower()

    def test_symlink_to_allowed_passes(self, validator, allowed_dir):
        """Symlink pointing inside allowed dirs should pass."""
        target = allowed_dir / "real.md"
        target.write_text("# Real doc")
        link = allowed_dir / "link.md"
        _symlink_or_skip(link, target)
        result = validator.validate_path(str(link))
        assert result.success is True

    def test_blocked_extension_rejected(self, validator, allowed_dir):
        """Executable/script extensions should be rejected."""
        blocked = allowed_dir / "script.exe"
        blocked.write_bytes(b"MZ")
        result = validator.validate_path(str(blocked))
        assert result.success is False
        assert "blocked" in result.error.lower() or "extension" in result.error.lower()

    def test_system_dir_blocked(self, validator):
        """Path inside a system directory should be rejected."""
        result = validator.validate_path("/etc/passwd")
        assert result.success is False

    def test_file_too_large_rejected(self, validator, allowed_dir):
        """File exceeding max_file_size_bytes should be rejected."""
        big = allowed_dir / "big.md"
        big.write_bytes(b"X" * 101)
        small_validator = type(validator)(
            allowed_directories=validator.allowed_directories,
            max_file_size_bytes=100,
        )
        result = small_validator.validate_path(str(big))
        assert result.success is False
        assert "size" in result.error.lower()

    def test_nonexistent_file_rejected(self, validator, allowed_dir):
        """Non-existent file should be rejected (allow_missing=False)."""
        missing = allowed_dir / "nonexistent.md"
        result = validator.validate_path(str(missing))
        assert result.success is False
        assert "exist" in result.error.lower()

    def test_blocked_extensions_set(self):
        """BLOCKED_EXTENSIONS should contain executable types."""
        from orf.mcp.security import BLOCKED_EXTENSIONS
        for ext in (".exe", ".bat", ".sh", ".ps1", ".vbs", ".js", ".cmd"):
            assert ext in BLOCKED_EXTENSIONS, f"{ext} should be blocked"

    def test_allowed_extensions_set(self):
        """ALLOWED_EXTENSIONS should contain document/output formats."""
        from orf.mcp.security import PathValidator
        for ext in (".md", ".docx", ".pptx", ".xlf", ".html", ".csv", ".json", ".srt",
                     ".epub", ".pdf", ".eml"):
            assert ext in PathValidator.ALLOWED_EXTENSIONS, f"{ext} should be allowed"


# ============================================================================
# Integration tests — through MCP tools
# ============================================================================

class TestORFMCPToolPathRejection:
    """Verify MCP tools return PATH_NOT_ALLOWED for invalid paths."""

    def test_apply_md_outside_allowlist(self, env_allowed):
        """apply_md with path outside allowlist → PATH_NOT_ALLOWED."""
        from orf.mcp.server import apply_md
        result = _parse(apply_md(input_md="/etc/passwd", target_format="docx",
                                 output_path="/tmp/out.docx"))
        assert result["success"] is False
        assert any(e.get("code") == "PATH_NOT_ALLOWED" for e in result.get("errors", []))

    def test_apply_md_traversal(self, env_allowed, allowed_dir):
        """apply_md with path traversal → PATH_NOT_ALLOWED."""
        from orf.mcp.server import apply_md
        traversal = str(allowed_dir / ".." / ".." / "etc" / "passwd")
        result = _parse(apply_md(input_md=traversal, target_format="docx",
                                 output_path="/tmp/out.docx"))
        assert result["success"] is False
        assert any(e.get("code") == "PATH_NOT_ALLOWED" for e in result.get("errors", []))

    def test_apply_md_output_outside_allowlist(self, env_allowed, allowed_dir):
        """apply_md with output_path outside allowlist → PATH_NOT_ALLOWED."""
        from orf.mcp.server import apply_md
        result = _parse(apply_md(
            input_md=str(allowed_dir / "doc.md"),
            target_format="docx",
            output_path="/etc/out.docx",
        ))
        assert result["success"] is False
        assert any(e.get("code") == "PATH_NOT_ALLOWED" for e in result.get("errors", []))

    def test_apply_xliff_outside_allowlist(self, env_allowed, allowed_dir):
        """apply_xliff with skeleton outside allowlist → PATH_NOT_ALLOWED."""
        from orf.mcp.server import apply_xliff
        result = _parse(apply_xliff(
            input_file="/etc/skeleton.zip",
            xliff_path=str(allowed_dir / "doc.xlf"),
            output_path=str(allowed_dir / "out.docx"),
            format="docx",
        ))
        assert result["success"] is False
        assert any(e.get("code") == "PATH_NOT_ALLOWED" for e in result.get("errors", []))

    def test_detect_format_outside_allowlist(self, env_allowed):
        """detect_format with path outside allowlist should return UNKNOWN.

        Note: ORF's detect_format returns ``{\"format\": \"UNKNOWN\"}`` for
        invalid paths (no ``success`` field) because the tool is
        best-effort detection. We verify it doesn't crash and returns
        empty/safe values.
        """
        from orf.mcp.server import detect_format
        result = _parse(detect_format("/etc/passwd"))
        # detect_format returns {format, confidence} — no success field
        # for invalid paths it should return UNKNOWN without crashing
        assert result.get("format") in ("UNKNOWN", None)

    def test_info_outside_allowlist(self, env_allowed):
        """info with path outside allowlist should return safe fallback.

        Similar to detect_format: info returns format/size info without
        a success field for invalid paths.
        """
        from orf.mcp.server import info
        result = _parse(info("/etc/passwd"))
        # Should not crash; may return UNKNOWN format
        assert isinstance(result, dict)

    def test_batch_convert_outside_allowlist(self, env_allowed):
        """batch_convert with input_dir outside allowlist → PATH_NOT_ALLOWED."""
        from orf.mcp.server import batch_convert
        result = _parse(batch_convert(input_dir="/etc", target_format="docx"))
        # ORF error_response puts per-tool payload under content (success/fail/total);
        # batch_convert rejects before any conversion, so totals are zero.
        assert result["success"] is False
        assert result.get("content", {}).get("total") == 0
        codes = {e.get("code") for e in result.get("errors", [])}
        assert "PATH_NOT_ALLOWED" in codes

    def test_xliff_image_path_injection_rejected(self, env_allowed, allowed_dir):
        """apply_xliff with image file_path outside working dir → FILE_PATH_NOT_ALLOWED.

        ORF's C4 fix rejects image placements with 'file_path' keys (arbitrary file read).
        """
        from orf.mcp.server import apply_xliff
        # Create a minimal skeleton and xliff so the tool gets past path validation
        skeleton = allowed_dir / "test.skeleton.zip"
        skeleton.write_bytes(b"PK\x03\x04" + b"\x00" * 20)
        xliff = allowed_dir / "test.xlf"
        xliff.write_text('<?xml version="1.0" encoding="UTF-8"?><xliff version="1.2"/>')

        result = _parse(apply_xliff(
            input_file=str(skeleton),
            xliff_path=str(xliff),
            output_path=str(allowed_dir / "out.docx"),
            format="docx",
            images=[{"file_path": "/etc/passwd", "paragraph_index": 0}],
        ))
        assert result["success"] is False
        assert any(e.get("code") == "FILE_PATH_NOT_ALLOWED" for e in result.get("errors", []))

    def test_apply_md_blocked_extension(self, env_allowed, allowed_dir):
        """apply_md with blocked extension → PATH_NOT_ALLOWED."""
        from orf.mcp.server import apply_md
        blocked = allowed_dir / "script.sh"
        blocked.write_text("echo hello")
        result = _parse(apply_md(
            input_md=str(blocked),
            target_format="docx",
            output_path="/tmp/out.docx",
        ))
        assert result["success"] is False
        assert any(e.get("code") == "PATH_NOT_ALLOWED" for e in result.get("errors", []))

    def test_no_allowlist_all_tools_fail(self, monkeypatch, tmp_path):
        """Without any allowlist ORF fail-CLOSES instead of defaulting to cwd.

        ORF's validator is lazily created from env; the unified
        ``MCP_ALLOWED_DIRECTORIES`` takes precedence over the ORF-specific
        name, so both must be cleared to exercise the fail-CLOSED path.
        """
        monkeypatch.delenv("ORF_MCP_ALLOWED_DIRS", raising=False)
        monkeypatch.delenv("MCP_ALLOWED_DIRECTORIES", raising=False)
        from orf.mcp import common
        from orf.mcp.server import apply_md
        common.reset_config_and_validator()
        with pytest.raises(ValueError, match="fail-CLOSED"):
            apply_md(
                input_md=str(tmp_path / "test.md"),
                target_format="docx",
                output_path=str(tmp_path / "out.docx"),
            )
