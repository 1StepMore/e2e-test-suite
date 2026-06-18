"""Tests for OL MCP PathValidator (round 16 Phase A1).

Validates that the OL MCP tools reject path-traversal attacks and
out-of-allowlist paths. Closes the gap identified in the round-15
security audit where ``load_glossary``, ``search_tm``, and
``translate_xliff`` accepted file paths with zero validation.
"""

import os
import tempfile
from pathlib import Path

import pytest

from ol_mcp.security import (
    BLOCKED_EXTENSIONS,
    SYSTEM_DIRS,
    PathValidator,
    ValidationResult,
    get_default_validator,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def allowed_dir(tmp_path):
    """An allowed directory with one valid JSON file."""
    d = tmp_path / "allowed"
    d.mkdir()
    (d / "glossary.json").write_text('{"hello": {"translation": "你好"}}')
    (d / "tm.tmx").write_text("<tmx>empty</tmx>")
    (d / "doc.xlf").write_text("<xliff/>")
    return d


@pytest.fixture
def outside_dir(tmp_path):
    """A directory that is NOT in the allowlist."""
    d = tmp_path / "outside"
    d.mkdir()
    (d / "secret.json").write_text("{}")
    return d


@pytest.fixture
def validator(allowed_dir):
    """PathValidator configured with one allowed dir."""
    return PathValidator(allowed_directories=[allowed_dir])


@pytest.fixture
def env_allowed(allowed_dir, monkeypatch):
    """Set OL_ALLOWED_DIRECTORIES so get_default_validator() picks it up.

    The MCP tools call get_default_validator() which reads the env var,
    not the `validator` fixture. This fixture wires the env so integration
    tests can exercise the actual code path.
    """
    monkeypatch.setenv("OL_ALLOWED_DIRECTORIES", str(allowed_dir))
    return allowed_dir


# ---------------------------------------------------------------------------
# Unit tests: PathValidator
# ---------------------------------------------------------------------------

class TestPathValidatorUnit:
    """Core validation logic of PathValidator."""

    def test_valid_file_in_allowed_dir(self, validator, allowed_dir):
        f = allowed_dir / "glossary.json"
        result = validator.validate_path(str(f))
        assert result.success is True
        assert result.resolved_path == f.resolve()
        assert result.error is None

    def test_path_traversal_rejected(self, validator, allowed_dir):
        # ../../etc/passwd
        evil = str(allowed_dir / ".." / ".." / "etc" / "passwd")
        result = validator.validate_path(evil)
        assert result.success is False
        assert "traversal" in result.error.lower()

    def test_path_outside_allowed_dir_rejected(self, validator, outside_dir):
        result = validator.validate_path(str(outside_dir / "secret.json"))
        assert result.success is False
        assert "not within allowed directories" in result.error.lower()

    def test_system_directory_rejected(self, tmp_path):
        v = PathValidator(allowed_directories=[Path("/")])
        result = v.validate_path("/etc/passwd")
        assert result.success is False
        assert "system directory" in result.error.lower()

    def test_blocked_extension_rejected(self, validator, allowed_dir):
        blocked = allowed_dir / "script.sh"
        blocked.write_text("#!/bin/sh\nrm -rf /")
        result = validator.validate_path(str(blocked))
        assert result.success is False
        assert "blocked" in result.error.lower()

    def test_disallowed_extension_rejected(self, validator, allowed_dir):
        # .exe is blocked, .txt is just not allowed
        bad = allowed_dir / "doc.txt"
        bad.write_text("hello")
        result = validator.validate_path(str(bad))
        assert result.success is False
        assert "not in allowed set" in result.error.lower()

    def test_nonexistent_file_rejected(self, validator, allowed_dir):
        ghost = allowed_dir / "does_not_exist.json"
        result = validator.validate_path(str(ghost))
        assert result.success is False
        assert "does not exist" in result.error.lower()

    def test_nonexistent_with_allow_missing_succeeds(self, validator, allowed_dir):
        ghost = allowed_dir / "future_output.xlf"
        result = validator.validate_path(str(ghost), allow_missing=True)
        assert result.success is True
        assert result.resolved_path == ghost.resolve()

    def test_directory_not_file_rejected(self, validator, allowed_dir):
        # Directory has no extension, so the allowed-extension check
        # fires first ("not in allowed set"). Both this and the
        # "is file" check reject the path; the assertion just
        # confirms the directory is rejected.
        result = validator.validate_path(str(allowed_dir))
        assert result.success is False
        assert result.error is not None

    def test_file_size_limit_enforced(self, tmp_path):
        d = tmp_path / "small"
        d.mkdir()
        big = d / "big.json"
        big.write_text("x" * 200)  # 200 bytes
        # Set limit to 100 bytes
        v = PathValidator(allowed_directories=[d], max_file_size_bytes=100)
        result = v.validate_path(str(big))
        assert result.success is False
        assert "exceeds limit" in result.error.lower()

    def test_allowed_extensions_defined(self):
        expected = {".json", ".tmx", ".xlf", ".xliff", ".md"}
        assert PathValidator.ALLOWED_EXTENSIONS == expected

    def test_blocked_extensions_defined(self):
        assert ".exe" in BLOCKED_EXTENSIONS
        assert ".sh" in BLOCKED_EXTENSIONS
        assert ".bat" in BLOCKED_EXTENSIONS

    def test_system_dirs_defined(self):
        assert "/etc" in SYSTEM_DIRS
        assert "/usr" in SYSTEM_DIRS
        assert "/var" in SYSTEM_DIRS

    def test_resolve_failure_handled(self, validator):
        # Path with null byte raises ValueError on some platforms
        # (on Linux, Path() doesn't validate; resolve() will)
        result = validator.validate_path("/nonexistent_dir_12345/also_missing.json")
        # This will fail at "does not exist" or "not within allowed"
        # depending on platform. The key is it doesn't crash.
        assert result.success is False


# ---------------------------------------------------------------------------
# Unit tests: get_default_validator
# ---------------------------------------------------------------------------

class TestGetDefaultValidator:
    """Env-var-driven default validator construction."""

    def test_empty_env_uses_cwd(self, monkeypatch):
        monkeypatch.delenv("OL_ALLOWED_DIRECTORIES", raising=False)
        v = get_default_validator()
        assert len(v.allowed_directories) == 1
        assert v.allowed_directories[0] == Path.cwd().resolve()

    def test_single_dir(self, monkeypatch, tmp_path):
        monkeypatch.setenv("OL_ALLOWED_DIRECTORIES", str(tmp_path))
        v = get_default_validator()
        assert len(v.allowed_directories) == 1
        assert v.allowed_directories[0] == tmp_path.resolve()

    def test_multiple_dirs_comma_separated(self, monkeypatch, tmp_path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir()
        b.mkdir()
        monkeypatch.setenv("OL_ALLOWED_DIRECTORIES", f"{a},{b}")
        v = get_default_validator()
        assert len(v.allowed_directories) == 2
        assert v.allowed_directories[0] == a.resolve()
        assert v.allowed_directories[1] == b.resolve()

    def test_trailing_comma_ignored(self, monkeypatch, tmp_path):
        monkeypatch.setenv("OL_ALLOWED_DIRECTORIES", f"{tmp_path},")
        v = get_default_validator()
        assert len(v.allowed_directories) == 1


# ---------------------------------------------------------------------------
# Integration tests: MCP tools reject malicious paths
# ---------------------------------------------------------------------------

class TestLoadGlossaryPathValidation:
    """load_glossary must reject paths outside the allowlist."""

    @pytest.mark.asyncio
    async def test_traversal_path_rejected(self, env_allowed, allowed_dir, outside_dir):
        from ol_mcp.tools import LoadGlossaryInput, load_glossary
        evil = str(allowed_dir / ".." / ".." / "etc" / "passwd.json")
        params = LoadGlossaryInput(path=evil)
        result = await load_glossary(params)
        import json
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "OL_PATH_NOT_ALLOWED" in str(parsed.get("warnings", []))

    @pytest.mark.asyncio
    async def test_outside_allowlist_rejected(self, env_allowed, outside_dir):
        from ol_mcp.tools import LoadGlossaryInput, load_glossary
        params = LoadGlossaryInput(path=str(outside_dir / "secret.json"))
        result = await load_glossary(params)
        import json
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "OL_PATH_NOT_ALLOWED" in str(parsed.get("warnings", []))


class TestSearchTMPathValidation:
    """search_tm must reject paths outside the allowlist."""

    @pytest.mark.asyncio
    async def test_traversal_path_rejected(self, env_allowed, allowed_dir):
        from ol_mcp.tools import SearchTMInput, search_tm
        evil = str(allowed_dir / ".." / ".." / "etc" / "passwd.tmx")
        params = SearchTMInput(tmx_path=evil, source_text="hello")
        result = await search_tm(params)
        import json
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "OL_PATH_NOT_ALLOWED" in str(parsed.get("warnings", []))

    @pytest.mark.asyncio
    async def test_outside_allowlist_rejected(self, env_allowed, outside_dir):
        from ol_mcp.tools import SearchTMInput, search_tm
        params = SearchTMInput(
            tmx_path=str(outside_dir / "secret.tmx"),
            source_text="hello",
        )
        result = await search_tm(params)
        import json
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "OL_PATH_NOT_ALLOWED" in str(parsed.get("warnings", []))


class TestTranslateXliffPathValidation:
    """translate_xliff must reject paths outside the allowlist."""

    @pytest.mark.asyncio
    async def test_traversal_input_path_rejected(self, env_allowed, allowed_dir, tmp_path):
        from ol_mcp.tools import TranslateXliffInput, translate_xliff
        evil = str(allowed_dir / ".." / ".." / "etc" / "passwd.xlf")
        out = str(tmp_path / "out.xlf")
        params = TranslateXliffInput(
            input_path=evil,
            output_path=out,
            source_lang="en",
            target_lang="zh",
        )
        result = await translate_xliff(params)
        import json
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "OL_PATH_NOT_ALLOWED" in str(parsed.get("warnings", []))

    @pytest.mark.asyncio
    async def test_outside_allowlist_input_rejected(self, env_allowed, outside_dir, tmp_path):
        from ol_mcp.tools import TranslateXliffInput, translate_xliff
        out = str(tmp_path / "out.xlf")
        params = TranslateXliffInput(
            input_path=str(outside_dir / "secret.xlf"),
            output_path=out,
            source_lang="en",
            target_lang="zh",
        )
        result = await translate_xliff(params)
        import json
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "OL_PATH_NOT_ALLOWED" in str(parsed.get("warnings", []))

    @pytest.mark.asyncio
    async def test_glossary_path_outside_allowlist_warns_not_crashes(
        self, env_allowed, allowed_dir, outside_dir, tmp_path
    ):
        """If glossary_path is outside allowlist, warn but don't crash
        (glossary is optional, translation still proceeds)."""
        from ol_mcp.tools import TranslateXliffInput, translate_xliff
        in_path = allowed_dir / "doc.xlf"
        in_path.write_text("<xliff/>")
        out = str(tmp_path / "out.xlf")
        params = TranslateXliffInput(
            input_path=str(in_path),
            output_path=out,
            glossary_path=str(outside_dir / "secret.json"),
            source_lang="en",
            target_lang="zh",
        )
        result = await translate_xliff(params)
        import json
        parsed = json.loads(result)
        # Glossary was rejected (warning), but translation may still
        # proceed. The key is no crash.
        assert "OL_PATH_NOT_ALLOWED" in str(parsed.get("warnings", []))
