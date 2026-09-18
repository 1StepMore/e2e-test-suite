"""路径安全策略的**行为特征化测试**（ADR 0007 Phase 2，Task 2）。

背景
----
ADR 0007 Phase 2 要把四份路径策略拷贝（OPP 共享底层 + OPP MCP 包装、OL 自含、
ORF 自含、套件层 ``omni_mcp.orchestrator`` 的部分拷贝）收敛到一个共享
``omni_security`` 包。收敛前先布下这张"行为锁"网：本文件在**当前未改动的树上
必须全绿**，收敛后也必须全绿 —— 任何一条失败都说明重构改变了可观察行为。

与 ``test_path_policy_parity.py`` 的分工
----------------------------------------
parity 文件锁定四份拷贝**应该一致**的规则（canonical 常量、共享向量、env 语义、
allowlist 切分一致性）。本文件锁定 parity 的 ``SHARED_VECTORS`` 之外、且**已知
存在有意差异**的行为，逐份拷贝钉死：

* 每条拒绝/放行的**判定**（四份拷贝都跑同一张更宽的向量表：穿越、系统目录
  ``/proc``、黑名单扩展名 ``.exe``、allowlist 外、缺失文件、目录路径、符号链接
  逃逸、超大文件）；
* 各自**当前的消息措辞**（OPP "not in allowed directories" vs OL/ORF
  "not within allowed directories" vs orchestrator "not within the allowed
  directories"）；
* **检查顺序**差异（OPP 的扩展名白名单在共享层存在性检查**之后**，OL/ORF 在
  **之前**）；
* **目录处理**差异（ORF 的 ``validate_path`` 接受一个扩展名不在白名单里的目录，
  OPP/OL 拒绝）；
* 版本遗留的 ``PathValidator.validate()`` 静态方法对 ``.exe`` 的**精确元组**
  ``(False, "Extension '.exe' not in allowed set")``，以及它是否受
  ``MCP_ALLOWED_EXTENSIONS`` 影响；
* 四份 allowlist 解析器对 Windows 盘符字面量 ``C:\\docs;C:\\out`` 与
  ``os.pathsep``/逗号混用的**逐字一致切分**。

这些值全部由**实际运行**确认（2026-09-18 在当前树 + ``.venv_ol`` 上执行），
不是从代码"看起来应该是"推断的。刻意不使用 ``pytest.importorskip``：任一模块
不可导入时本文件必须红，不许伪绿（见 scenarios/STANDARDS.md 的
fallbacks-never-evidence 精神）。

文件名带 ``test_`` 前缀且位于 ``tests/`` 下，CI 的 ``pytest tests/`` 自动收集。
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from omni_mcp import orchestrator as omni_orchestrator
from opp.mcp.config import _parse_allowed_dirs as opp_parse_allowed_dirs
from opp.mcp.security import PathValidationError
from opp.mcp.security import PathValidator as OppPathValidator
from ol_mcp.security import PathValidator as OlPathValidator
from ol_mcp.security import _parse_allowed_dirs as ol_parse_allowed_dirs
from orf.mcp.config import _parse_allowed_dirs as orf_parse_allowed_dirs
from orf.mcp.security import PathValidator as OrfPathValidator


# ---------------------------------------------------------------------------
# 冻结的预期消息 / 元组（改动策略必须显式改这些字面量）
# ---------------------------------------------------------------------------

#: 各拷贝对"allowlist 之外"路径的拒绝消息片段。措辞不同是**有意保留**的当前
#: 行为（收敛时按 ADR 0007 决策 3 逐模块保留消息，本表是其可执行证据）。
OPP_OUTSIDE_ALLOWLIST_FRAGMENT = "not in allowed directories"
OL_OUTSIDE_ALLOWLIST_FRAGMENT = "not within allowed directories"
ORF_OUTSIDE_ALLOWLIST_FRAGMENT = "not within allowed directories"
ORCHESTRATOR_OUTSIDE_ALLOWLIST_FRAGMENT = "not within the allowed directories"

#: 黑名单扩展名的拒绝消息 —— 四份拷贝当前**逐字相同**。
BLOCKED_EXTENSION_MESSAGE = "File extension '.exe' is blocked"

#: ORF legacy 静态 ``validate()`` 对黑名单扩展名的精确元组（见
#: Omni_Re_Formatter/tests/test_security_extensions.py:44 与 :62）。
ORF_LEGACY_EXE_TUPLE: tuple[bool, str] = (
    False,
    "Extension '.exe' not in allowed set",
)
ORF_LEGACY_SH_TUPLE: tuple[bool, str] = (
    False,
    "Extension '.sh' not in allowed set",
)

DEFAULT_MAX_FILE_SIZE_BYTES = 100_000_000
OVERSIZE_LIMIT_BYTES = 16


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _ModuleCopy:
    """一份子模块路径策略的可调用包装（统一"拒绝 = False"的判定语义）。

    与 parity 文件的同名辅助类不同：这里同时保留**失败消息**，因为本文件的重点
    是特征化各拷贝当前不同的措辞与检查顺序，而不只是布尔判定。
    """

    def __init__(self, name: str, factory: Callable[[list[Path], int], object]) -> None:
        """初始化。

        Args:
            name: 实现名（``opp`` / ``ol`` / ``orf``），用于断言失败信息。
            factory: 接收 ``(allowed_dirs, max_file_size_bytes)``、返回 validator
                实例的工厂。
        """
        self.name = name
        self._factory = factory

    def verdict(
        self,
        allowed_dir: Path,
        path: str,
        max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
    ) -> tuple[bool, str | None]:
        """返回 ``(是否放行, 失败消息)``。

        OPP 在共享规则上抛 ``PathValidationError``，OL/ORF 返回
        ``ValidationResult(success=False)`` —— 两种 API 在这里收敛成同一种元组。
        """
        validator = self._factory([allowed_dir], max_file_size_bytes)
        try:
            result = validator.validate_path(path)  # type: ignore[attr-defined]
        except PathValidationError as exc:
            return False, str(exc)
        return bool(result.success), result.error


MODULE_COPIES: dict[str, _ModuleCopy] = {
    "opp": _ModuleCopy(
        "opp",
        lambda dirs, max_bytes: OppPathValidator(
            allowed_directories=dirs, max_file_size_bytes=max_bytes
        ),
    ),
    "ol": _ModuleCopy(
        "ol",
        lambda dirs, max_bytes: OlPathValidator(
            allowed_directories=dirs, max_file_size_bytes=max_bytes
        ),
    ),
    "orf": _ModuleCopy(
        "orf",
        lambda dirs, max_bytes: OrfPathValidator(
            allowed_directories=dirs, max_file_size_bytes=max_bytes
        ),
    ),
}


def _orchestrator_verdict(
    monkeypatch: pytest.MonkeyPatch, allowed_dir: Path, path: str
) -> tuple[bool, str | None]:
    """套件层 orchestrator 的判定（从环境变量读 allowlist）。"""
    monkeypatch.setenv("MCP_ALLOWED_DIRECTORIES", str(allowed_dir))
    message = omni_orchestrator._path_denial_message(path)
    return message is None, message


def _orchestrator_parse(value: str) -> list[Path]:
    """``omni_mcp`` allowlist 解析适配器（切分 + ``Path`` 转换，与三份同契约）。"""
    return [Path(part) for part in omni_orchestrator._split_allowlist(value)]


#:：四份拷贝的 allowlist 解析入口。键 = 拷贝名。
ALLOWLIST_PARSERS: dict[str, Callable[[str], list[Path]]] = {
    "opp": opp_parse_allowed_dirs,
    "ol": ol_parse_allowed_dirs,
    "orf": orf_parse_allowed_dirs,
    "orchestrator": _orchestrator_parse,
}


@pytest.fixture
def policy_tree(tmp_path: Path) -> SimpleNamespace:
    """造出向量表需要的目录树、文件、目录与逃逸符号链接。

    Returns:
        ``SimpleNamespace``，含 ``root`` / ``allowed`` / ``outside`` / ``link``
        与 ``link_created``（符号链接在无权限平台创建失败时为 False）。
    """
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()

    (allowed / "ok.md").write_text("ok")
    (allowed / "ok.zzz").write_text("zzz")  # 存在但不在任何白名单
    (allowed / "evil.exe").write_bytes(b"MZ")
    (allowed / "big.md").write_text("x" * 4096)
    (allowed / "subdir").mkdir()
    (outside / "secret.md").write_text("secret")

    link = allowed / "escape_link.md"
    link_created = True
    try:
        link.symlink_to(outside / "secret.md")
    except (OSError, NotImplementedError):
        link_created = False

    return SimpleNamespace(
        root=tmp_path,
        allowed=allowed,
        outside=outside,
        link=link,
        link_created=link_created,
    )


# ---------------------------------------------------------------------------
# 1. 更宽的向量表：每条向量的判定（四份拷贝）
# ---------------------------------------------------------------------------


class TestRejectionVectorSet:
    """parity ``SHARED_VECTORS`` 之外 / 已知分歧的向量，逐条锁定当前判定。"""

    def test_traversal_is_denied_by_all_four(self, policy_tree, monkeypatch):
        """``..`` 穿越：四份拷贝全部拒绝（OPP/OL/ORF 走穿越分支，orchestrator 走 allowlist）。"""
        path = str(policy_tree.allowed / ".." / "escape.md")
        verdicts = {
            name: copy.verdict(policy_tree.allowed, path)
            for name, copy in MODULE_COPIES.items()
        }
        verdicts["orchestrator"] = _orchestrator_verdict(monkeypatch, policy_tree.allowed, path)
        assert {allowed for allowed, _ in verdicts.values()} == {False}, (
            f"穿越未被四份拷贝一致拒绝：{verdicts}"
        )
        # OPP/OL/ORF 有显式 ``..`` 分支；orchestrator 只 resolve + allowlist 包含。
        assert "traversal" in (verdicts["opp"][1] or "").lower()
        assert "Path traversal detected" in (verdicts["ol"][1] or "")
        assert "Path traversal detected" in (verdicts["orf"][1] or "")
        assert (verdicts["orchestrator"][1] or "").startswith(
            "Path is not within the allowed directories:"
        )

    def test_system_directory_is_denied_by_all_four(self, policy_tree, monkeypatch):
        """系统目录（POSIX ``/proc``、Windows ``C:\\Windows``）：四份拷贝全部拒绝。"""
        target = (
            r"C:\Windows\omni-characterization-probe.md"
            if os.name == "nt"
            else "/proc/omni-characterization-probe.md"
        )
        verdicts = {
            name: copy.verdict(policy_tree.allowed, target)
            for name, copy in MODULE_COPIES.items()
        }
        verdicts["orchestrator"] = _orchestrator_verdict(monkeypatch, policy_tree.allowed, target)
        assert {allowed for allowed, _ in verdicts.values()} == {False}, (
            f"系统目录未被四份拷贝一致拒绝：{verdicts}"
        )
        for name, (_, message) in verdicts.items():
            assert "system directory not allowed" in (message or ""), (
                f"{name} 的拒绝理由未点名系统目录分支：{message!r}"
            )

    @pytest.mark.skipif(os.name == "nt", reason="/proc 语义仅存在于 POSIX")
    def test_proc_specifically_is_a_system_directory(self, policy_tree, monkeypatch):
        """POSIX 上 ``/proc`` 必须命中系统目录分支（任务点名的具体目录）。"""
        target = "/proc/omni-characterization-probe.md"
        for name, copy in MODULE_COPIES.items():
            allowed, message = copy.verdict(policy_tree.allowed, target)
            assert allowed is False and "/proc" in (message or ""), (
                f"{name} 未拦截 /proc：{(allowed, message)!r}"
            )
        allowed, message = _orchestrator_verdict(monkeypatch, policy_tree.allowed, target)
        assert allowed is False and "/proc" in (message or "")

    def test_blocked_extension_is_denied_by_all_four(self, policy_tree, monkeypatch):
        """黑名单扩展名 ``.exe``：四份拷贝全部拒绝，且消息逐字相同。"""
        path = str(policy_tree.allowed / "evil.exe")
        verdicts = {
            name: copy.verdict(policy_tree.allowed, path)
            for name, copy in MODULE_COPIES.items()
        }
        verdicts["orchestrator"] = _orchestrator_verdict(monkeypatch, policy_tree.allowed, path)
        for name, (allowed, message) in verdicts.items():
            assert (allowed, message) == (False, BLOCKED_EXTENSION_MESSAGE), (
                f"{name} 对 .exe 的判定/消息不符：{(allowed, message)!r}"
            )

    def test_outside_allowlist_is_denied_by_all_four(self, policy_tree, monkeypatch):
        """allowlist 外的兄弟目录：四份拷贝全部拒绝（消息措辞各自不同）。"""
        path = str(policy_tree.outside / "secret.md")
        verdicts = {
            name: copy.verdict(policy_tree.allowed, path)
            for name, copy in MODULE_COPIES.items()
        }
        verdicts["orchestrator"] = _orchestrator_verdict(monkeypatch, policy_tree.allowed, path)
        assert {allowed for allowed, _ in verdicts.values()} == {False}, (
            f"allowlist 外路径未被一致拒绝：{verdicts}"
        )

    def test_missing_file_rejected_by_modules_allowed_by_orchestrator(
        self, policy_tree, monkeypatch
    ):
        """缺失文件：三份模块校验器拒绝；orchestrator **放行**（它不做存在性检查）。

        这是既有 API 契约（``translate_file()`` 在策略门之后单独报
        ``FILE_NOT_FOUND``），不是 bug。
        """
        path = str(policy_tree.allowed / "ghost.md")
        for name in ("opp", "ol", "orf"):
            allowed, message = MODULE_COPIES[name].verdict(policy_tree.allowed, path)
            assert (allowed, message) == (False, "File does not exist"), (
                f"{name} 对缺失文件判定不符：{(allowed, message)!r}"
            )
        allowed, message = _orchestrator_verdict(monkeypatch, policy_tree.allowed, path)
        assert allowed is True and message is None, (
            "orchestrator 的存在性检查语义变了（应放行，交给 FILE_NOT_FOUND 分支）"
        )

    def test_directory_path_rejected_by_opp_ol_accepted_by_orf_orchestrator(
        self, policy_tree, monkeypatch
    ):
        """目录路径：OPP/OL 拒绝，ORF/orchestrator 放行（当前有意差异）。"""
        path = str(policy_tree.allowed / "subdir")
        assert MODULE_COPIES["opp"].verdict(policy_tree.allowed, path) == (
            False,
            "Path must be a file, not a directory",
        )
        assert MODULE_COPIES["ol"].verdict(policy_tree.allowed, path) == (
            False,
            "Extension '' not in allowed set",
        )
        assert MODULE_COPIES["orf"].verdict(policy_tree.allowed, path) == (True, None), (
            "ORF 当前接受扩展名不在白名单里的目录；此断言锁定该行为"
        )
        allowed, message = _orchestrator_verdict(monkeypatch, policy_tree.allowed, path)
        assert allowed is True and message is None

    def test_symlink_escape_is_denied_by_all_four(self, policy_tree, monkeypatch):
        """符号链接指向 allowlist 外：四份拷贝全部拒绝（resolve 后的包含检查）。"""
        if not policy_tree.link_created:
            pytest.skip("当前平台/权限无法创建符号链接")
        path = str(policy_tree.link)
        verdicts = {
            name: copy.verdict(policy_tree.allowed, path)
            for name, copy in MODULE_COPIES.items()
        }
        verdicts["orchestrator"] = _orchestrator_verdict(monkeypatch, policy_tree.allowed, path)
        assert {allowed for allowed, _ in verdicts.values()} == {False}, (
            f"符号链接逃逸未被四份拷贝一致拒绝：{verdicts}"
        )
        assert OPP_OUTSIDE_ALLOWLIST_FRAGMENT in (verdicts["opp"][1] or "")
        assert OL_OUTSIDE_ALLOWLIST_FRAGMENT in (verdicts["ol"][1] or "")

    def test_oversized_file_rejected_by_modules_allowed_by_orchestrator(
        self, policy_tree, monkeypatch
    ):
        """超大文件：三份模块校验器按 ``max_file_size_bytes`` 拒绝；orchestrator 无尺寸上限。"""
        path = str(policy_tree.allowed / "big.md")
        for name in ("opp", "ol", "orf"):
            allowed, message = MODULE_COPIES[name].verdict(
                policy_tree.allowed, path, max_file_size_bytes=OVERSIZE_LIMIT_BYTES
            )
            assert allowed is False and "exceeds limit" in (message or ""), (
                f"{name} 未按尺寸上限拒绝：{(allowed, message)!r}"
            )
            assert f"of {OVERSIZE_LIMIT_BYTES} bytes" in (message or "")
        allowed, message = _orchestrator_verdict(monkeypatch, policy_tree.allowed, path)
        assert allowed is True and message is None, (
            "orchestrator 无尺寸检查（当前有意行为）"
        )


# ---------------------------------------------------------------------------
# 2. 已知消息 / API 形状分歧（逐条精确锁定）
# ---------------------------------------------------------------------------


class TestMessageAndApiDivergences:
    """锁定 OPP/OL/ORF 当前各不相同的 API 形状与拒绝措辞。"""

    def test_opp_raises_path_validation_error_for_outside_allowlist(self, policy_tree):
        """OPP 在 allowlist 外时**抛** ``PathValidationError``，消息含指定片段。"""
        path = str(policy_tree.outside / "secret.md")
        validator = OppPathValidator(allowed_directories=[policy_tree.allowed])
        with pytest.raises(PathValidationError) as excinfo:
            validator.validate_path(path)
        assert OPP_OUTSIDE_ALLOWLIST_FRAGMENT in str(excinfo.value), (
            f"OPP 消息措辞变了：{str(excinfo.value)!r}"
        )
        assert str(excinfo.value) == f"Path not in allowed directories: {path}"

    def test_ol_returns_validation_result_failure_for_outside_allowlist(self, policy_tree):
        """OL **不抛**，返回 ``ValidationResult(success=False)``，消息含指定片段。"""
        path = str(policy_tree.outside / "secret.md")
        result = OlPathValidator(allowed_directories=[policy_tree.allowed]).validate_path(path)
        assert result.success is False and result.resolved_path is None
        assert OL_OUTSIDE_ALLOWLIST_FRAGMENT in (result.error or ""), (
            f"OL 消息措辞变了：{result.error!r}"
        )
        assert (result.error or "").startswith("Path is not within allowed directories:")

    def test_orf_returns_validation_result_failure_for_outside_allowlist(self, policy_tree):
        """ORF 与 OL 同形（``ValidationResult(success=False)``），消息片段一致。"""
        path = str(policy_tree.outside / "secret.md")
        result = OrfPathValidator(allowed_directories=[policy_tree.allowed]).validate_path(path)
        assert result.success is False and result.resolved_path is None
        assert ORF_OUTSIDE_ALLOWLIST_FRAGMENT in (result.error or "")

    def test_orchestrator_message_has_the_extra_word_the(self, policy_tree, monkeypatch):
        """orchestrator 的措辞比 OL/ORF 多一个 ``the``（当前有意差异）。"""
        path = str(policy_tree.outside / "secret.md")
        allowed, message = _orchestrator_verdict(monkeypatch, policy_tree.allowed, path)
        assert allowed is False
        assert (message or "").startswith("Path is not within the allowed directories:")
        assert ORCHESTRATOR_OUTSIDE_ALLOWLIST_FRAGMENT in (message or "")

    def test_orf_legacy_validate_exact_tuple_for_blocked_extension(self, tmp_path):
        """ORF legacy 静态 ``validate()`` 对 ``.exe`` / ``.sh`` 返回精确元组。"""
        assert (
            OrfPathValidator.validate(str(tmp_path / "malware.exe"), base_dir=tmp_path)
            == ORF_LEGACY_EXE_TUPLE
        )
        assert (
            OrfPathValidator.validate(str(tmp_path / "script.sh"), base_dir=tmp_path)
            == ORF_LEGACY_SH_TUPLE
        )

    def test_opp_legacy_validate_exact_tuple_for_blocked_extension(self, tmp_path):
        """OPP legacy ``validate()`` 与 ORF 返回同一精确元组（未单独验证过的一致性）。"""
        assert (
            OppPathValidator.validate(str(tmp_path / "malware.exe"))
            == ORF_LEGACY_EXE_TUPLE
        )


# ---------------------------------------------------------------------------
# 3. 扩展名白名单与存在性检查的顺序分歧
# ---------------------------------------------------------------------------


class TestExtensionCheckOrdering:
    """OPP 白名单在共享层存在性检查**之后**；OL/ORF 在**之前**。"""

    def test_missing_non_whitelisted_extension_reveals_the_order(self, policy_tree):
        """缺失 + 白名单外：OPP 报"不存在"，OL/ORF 报"扩展名不在白名单"。"""
        path = str(policy_tree.allowed / "ghost.zzz")
        assert MODULE_COPIES["opp"].verdict(policy_tree.allowed, path) == (
            False,
            "File does not exist",
        ), "OPP 的共享层存在性检查应在白名单检查之前"
        expected = (False, "Extension '.zzz' not in allowed set")
        assert MODULE_COPIES["ol"].verdict(policy_tree.allowed, path) == expected
        assert MODULE_COPIES["orf"].verdict(policy_tree.allowed, path) == expected

    def test_existing_non_whitelisted_extension_all_modules_reject_on_whitelist(
        self, policy_tree
    ):
        """存在 + 白名单外：三份模块都走白名单分支（OPP 的白名单仍然生效）。"""
        path = str(policy_tree.allowed / "ok.zzz")
        expected = (False, "Extension '.zzz' not in allowed set")
        for name in ("opp", "ol", "orf"):
            assert MODULE_COPIES[name].verdict(policy_tree.allowed, path) == expected, (
                f"{name} 未对白名单外扩展名给出预期判定"
            )

    def test_orf_validate_path_accepts_directory_without_allowed_extension(self, policy_tree):
        """ORF 明确接受"无扩展名目录"（``resolved.is_dir()`` 短路）。"""
        allowed, message = MODULE_COPIES["orf"].verdict(
            policy_tree.allowed, str(policy_tree.allowed / "subdir")
        )
        assert (allowed, message) == (True, None)


# ---------------------------------------------------------------------------
# 4. legacy validate() 的环境变量覆盖
# ---------------------------------------------------------------------------


class TestLegacyEnvOverride:
    """legacy ``validate()`` 与实例路径读同一份 ``MCP_ALLOWED_EXTENSIONS``。"""

    @pytest.mark.parametrize(
        "validator_cls", [OppPathValidator, OrfPathValidator], ids=["opp", "orf"]
    )
    def test_legacy_env_override_can_whitelist_a_blacklisted_extension(
        self, validator_cls, monkeypatch
    ):
        """``MCP_ALLOWED_EXTENSIONS=.exe`` 时 legacy 路径放行 ``.exe``。

        legacy ``validate()`` 只查白名单、不查黑名单 —— 白名单被覆盖后黑名单即失效；
        这是当前可观察行为，收敛时必须保持或显式决策。
        """
        monkeypatch.setenv("MCP_ALLOWED_EXTENSIONS", ".exe")
        assert validator_cls.validate("payload.exe") == (True, "")

    @pytest.mark.parametrize(
        "validator_cls", [OppPathValidator, OrfPathValidator], ids=["opp", "orf"]
    )
    def test_legacy_env_override_exact_tuple_removes_default_extension(
        self, validator_cls, monkeypatch
    ):
        """``MCP_ALLOWED_EXTENSIONS=.zzz`` 时 legacy 对 ``.md`` 返回精确元组。"""
        monkeypatch.setenv("MCP_ALLOWED_EXTENSIONS", ".zzz")
        assert validator_cls.validate("input.md") == (
            False,
            "Extension '.md' not in allowed set",
        )


# ---------------------------------------------------------------------------
# 5. 四份 allowlist 解析器逐字一致
# ---------------------------------------------------------------------------


class TestAllowlistParserAgreement:
    """四份 allowlist 解析入口对同一输入必须给出**逐字一致**的切分。

    parity 文件只在 Windows 上锁定 ``C:\\docs;C:\\out`` 的盘符语义；本类在所有
    平台上锁定"四份实现彼此一致"，把同族缺陷的另一半（跨拷贝漂移）也钉住。
    """

    @staticmethod
    def _agreement(raw: str) -> dict[str, list[Path]]:
        return {name: parse(raw) for name, parse in ALLOWLIST_PARSERS.items()}

    def test_windows_drive_literal_splits_identically_across_parsers(self):
        """``C:\\docs;C:\\out``：四份解析器结果逐字一致（平台无关的一致性）。"""
        raw = r"C:\docs;C:\out"
        results = self._agreement(raw)
        distinct = {tuple(paths) for paths in results.values()}
        assert len(distinct) == 1, f"四份解析器对该输入不一致：{results!r}"

    def test_platform_separator_and_comma_mix_splits_identically(self, tmp_path):
        """``<a><pathsep><b>,<c>``：平台分隔符与逗号混用时四份一致。"""
        alpha, beta, gamma = tmp_path / "alpha", tmp_path / "beta", tmp_path / "gamma"
        raw = f"{alpha}{os.pathsep}{beta},{gamma}"
        results = self._agreement(raw)
        distinct = {tuple(paths) for paths in results.values()}
        assert len(distinct) == 1, f"四份解析器对混用分隔符不一致：{results!r}"
        assert list(results.values())[0] == [alpha, beta, gamma]

    def test_whitespace_and_empty_segments_splits_identically(self, tmp_path):
        """空白填充 + 连续/空分段：四份都去空白、丢空段，结果一致。"""
        alpha, beta = tmp_path / "alpha", tmp_path / "beta"
        raw = f"  {alpha} {os.pathsep},,{beta},  "
        results = self._agreement(raw)
        distinct = {tuple(paths) for paths in results.values()}
        assert len(distinct) == 1, f"四份解析器对空白/空段不一致：{results!r}"
        assert list(results.values())[0] == [alpha, beta]

    @pytest.mark.skipif(
        os.name != "nt", reason="盘符语义仅存在于 Windows"
    )
    def test_windows_drive_literal_exact_value_on_windows(self):
        """Windows 上四份解析器都必须把 ``C:\\docs;C:\\out`` 切成两个盘符目录。"""
        expected = [Path(r"C:\docs"), Path(r"C:\out")]
        for name, parse in ALLOWLIST_PARSERS.items():
            assert parse(r"C:\docs;C:\out") == expected, f"{name} 切分错误"
