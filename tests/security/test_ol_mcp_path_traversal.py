"""Tests for OL MCP PathValidator (round 16 Phase A1).

Validates that the OL MCP tools reject path-traversal attacks and
out-of-allowlist paths. Closes the gap identified in the round-15
security audit where ``load_glossary``, ``search_tm``, and
``translate_xliff`` accepted file paths with zero validation.
"""

import os
from pathlib import Path

import pytest

from ol_mcp.security import (
    BLOCKED_EXTENSIONS,
    SYSTEM_DIRS,
    PathValidator,
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


def _assert_path_denied(parsed: dict) -> None:
    """断言工具层返回了统一的路径拒绝错误码。

    2026-09-17 校正：fail-closed 改造（suite commit 5a93c66）把拒绝形态从
    ``warnings: ["OL_PATH_NOT_ALLOWED"]`` 改成结构化 ``error_code``
    （``OL_PATH_DENIED``，见 docs/ERROR_CODES.md）。本文件此前仍断言旧形态，
    7 个用例恒红 —— 断言的是历史实现，而不是当前契约。

    Args:
        parsed: MCP 工具返回的 JSON 解析结果。
    """
    assert parsed["success"] is False, parsed
    assert parsed["error_code"] == "OL_PATH_DENIED", parsed


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
        """系统目录必须在 containment 之前被拦。

        2026-09-17（ADR 0007）：原用例硬编码 ``/etc/passwd``，在 Windows 上
        ``Path("/etc/passwd")`` 解析到当前盘符下的 ``\\etc\\passwd``，既不落在
        allowlist 也不命中系统目录前缀，报的是 "not within allowed directories" ——
        断言的是平台而不是策略。现在按平台选取真实系统目录，allowlist 取该路径的
        锚点（POSIX ``/``、Windows ``C:\\``），使拒绝原因必然来自系统目录检查。
        """
        if os.name == "nt":
            probe = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
        else:
            probe = Path("/etc")
        v = PathValidator(allowed_directories=[Path(probe.anchor)])
        result = v.validate_path(str(probe / "passwd"))
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
        """OL 白名单冻结为 7 项（2026-09-17 校正：``.yaml``/``.yml`` 早已加入）。

        该集合同时被 ``tests/security/test_path_policy_parity.py`` 的
        ``OL_ALLOWED_EXTENSIONS`` 冻结，改动必须显式改两处。
        """
        expected = {".json", ".tmx", ".xlf", ".xliff", ".md", ".yaml", ".yml"}
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

    def test_empty_env_fails_closed(self, monkeypatch):
        """未配置 allowlist 时必须 fail-CLOSED（不得回退到 cwd）。

        2026-09-17 校正：``get_default_validator()`` 已改为 fail-CLOSED —— 三个
        allowlist 环境变量全未设置时抛 ``ValueError``，而不是默默把 cwd 当白名单。
        原用例断言的是旧行为（``allowed_directories == [cwd]``），即"未配置 =
        允许当前目录"，那正是要消除的不安全默认。
        """
        for var in ("MCP_ALLOWED_DIRECTORIES", "OL_MCP_ALLOWED_DIRS", "OL_ALLOWED_DIRECTORIES"):
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(ValueError, match="fail-CLOSED"):
            get_default_validator()

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
        _assert_path_denied(parsed)

    @pytest.mark.asyncio
    async def test_outside_allowlist_rejected(self, env_allowed, outside_dir):
        from ol_mcp.tools import LoadGlossaryInput, load_glossary
        params = LoadGlossaryInput(path=str(outside_dir / "secret.json"))
        result = await load_glossary(params)
        import json
        parsed = json.loads(result)
        _assert_path_denied(parsed)


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
        _assert_path_denied(parsed)

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
        _assert_path_denied(parsed)


class TestTranslateXliffPathValidation:
    """translate_xliff must reject paths outside the allowlist."""

    @pytest.mark.asyncio
    async def test_traversal_input_path_rejected(self, env_allowed, allowed_dir):
        """输出路径也放在 allowlist 内，使唯一违规点是 input_path（断言更精确）。"""
        from ol_mcp.tools import TranslateXliffInput, translate_xliff
        evil = str(allowed_dir / ".." / ".." / "etc" / "passwd.xlf")
        out = str(allowed_dir / "out.xlf")
        params = TranslateXliffInput(
            input_path=evil,
            output_path=out,
            source_lang="en",
            target_lang="zh",
        )
        result = await translate_xliff(params)
        import json
        parsed = json.loads(result)
        _assert_path_denied(parsed)

    @pytest.mark.asyncio
    async def test_outside_allowlist_input_rejected(self, env_allowed, allowed_dir, outside_dir):
        """同上传入路径越界：输出仍在 allowlist 内。"""
        from ol_mcp.tools import TranslateXliffInput, translate_xliff
        out = str(allowed_dir / "out.xlf")
        params = TranslateXliffInput(
            input_path=str(outside_dir / "secret.xlf"),
            output_path=out,
            source_lang="en",
            target_lang="zh",
        )
        result = await translate_xliff(params)
        import json
        parsed = json.loads(result)
        _assert_path_denied(parsed)

    @pytest.mark.asyncio
    async def test_glossary_path_outside_allowlist_warns_not_denies(
        self, env_allowed, allowed_dir, outside_dir
    ):
        """越界的**可选** glossary 只降级为 warning，不得让整次调用被拒。

        2026-09-17 校正（ADR 0007 相邻发现）：原用例断言
        ``"OL_PATH_NOT_ALLOWED" in warnings``，而当前实现写的是
        ``f"{OL_PATH_DENIED}: {error}"``（``ol_mcp/translate_xliff.py:282``），
        字符串早已改名 —— 用例断言的是历史实现。这里按当前契约重写：

        * 必填参数（input/output）越界 → 整次拒绝（见本类其他用例）；
        * 可选参数（glossary）越界 → 记 warning、glossary 置空、流程继续。

        输入/输出都放在 allowlist 内，使 glossary_path 成为唯一违规点。glossary
        分支在解析出 trans-unit 之后才执行，故这里给一个最小合法 XLIFF；翻译阶段
        是否成功取决于环境（CI 用 FAKE_LLM），所以"未被拒"在所有环境都断言，
        warning 只在调用成功时可观察。
        """
        from ol_mcp.tools import TranslateXliffInput, translate_xliff
        in_path = allowed_dir / "doc.xlf"
        in_path.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">'
            '<file source-language="en" target-language="zh" original="doc.md">'
            '<body><trans-unit id="1"><source>Hello</source></trans-unit></body>'
            "</file></xliff>",
            encoding="utf-8",
        )
        params = TranslateXliffInput(
            input_path=str(in_path),
            output_path=str(allowed_dir / "out.xlf"),
            glossary_path=str(outside_dir / "secret.json"),
            source_lang="en",
            target_lang="zh",
        )
        result = await translate_xliff(params)
        import json
        parsed = json.loads(result)
        assert parsed.get("error_code") != "OL_PATH_DENIED", (
            f"可选 glossary 越界不得导致整次调用被拒：{parsed}"
        )
        if parsed.get("success"):
            # 成功响应把 warning 放在 content.warnings（不在顶层）。
            warnings = (parsed.get("content") or {}).get("warnings", [])
            assert any("OL_PATH_DENIED" in w for w in warnings), (
                f"glossary 越界必须留下 warning：{parsed}"
            )
