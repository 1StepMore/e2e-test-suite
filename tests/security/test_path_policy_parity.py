"""路径安全策略一致性门禁（ADR 0007 Phase 1 第 3 条）。

背景
----
路径安全（穿越 / 符号链接逃逸 / 系统目录拦截 / 扩展名白名单与黑名单 / 目录包含）
在三个子仓库里各有一份实现（OPP 是"共享底层 + 薄 MCP 包装"，OL 与 ORF 是自含
副本），第四份在套件层：``omni_mcp/orchestrator.py`` 不经过任何子模块的
``PathValidator``（它直接起 CLI 子进程），因此自带一份策略。它们不是四套**策略**，
而是同一套策略的四份拷贝 —— 已经出现真实漂移：``/proc``、``/sys`` 在 OPP 被拦、
在 OL/ORF 未被拦；``MCP_ALLOWED_EXTENSIONS`` 在 OPP/ORF 的 legacy ``validate()``
上静默失效；``omni_mcp`` 的 allowlist 曾经按 ``":"`` 切分（Windows 盘符被切开），
且只做 allowlist 包含检查、完全没有系统目录与黑名单拦截（2026-09-17 补齐）。

本文件是这件事的**唯一可引用基准**（ADR 0007）：

* 冻结 canonical 常量（改变必须同时改这里的字面集合，即"有意识地改策略"）；
* 断言四份拷贝的 ``SYSTEM_DIRS`` / ``BLOCKED_EXTENSIONS`` 与 canonical 完全相等；
* 用同一张**行为向量表**跑遍三个 validator 与套件层 orchestrator，判定必须逐条
  相同且等于表中预期值；
* 锁定 ``MCP_ALLOWED_EXTENSIONS`` 在三份实现里的解析语义与 legacy ``validate()``
  的环境变量覆盖行为；
* 锁定四份 allowlist 解析入口对同一输入的切分结果逐字相同 —— 2026-09-17 复查发现
  的同族缺陷：OPP/ORF 优先按 ``":"`` 切分，Windows 盘符被切开，文档里给出的
  ``C:\\docs;C:\\out`` 写法完全失效；``omni_mcp`` 当时是同一模式的最弱一份。

刻意不使用 ``pytest.importorskip``：三个模块不可导入时必须红，不许静默跳过
（伪绿守卫，见 scenarios/STANDARDS.md 的 fallbacks-never-evidence 精神）。

文件名带 ``test_`` 前缀且位于 ``tests/`` 下，CI 的 ``pytest tests/`` 会自动收集
（.github/workflows/e2e-tests.yml 第 127 行），无需额外接线。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from ol_mcp import security as ol_security
from ol_mcp.security import PathValidator as OlPathValidator
from ol_mcp.security import _parse_allowed_dirs as ol_parse_allowed_dirs
from opp.mcp import security as opp_mcp_security
from opp.mcp.config import _parse_allowed_dirs as opp_parse_allowed_dirs
from opp.mcp.security import PathValidationError
from opp.mcp.security import PathValidator as OppPathValidator
from opp.utils import security as opp_core
from orf.mcp import security as orf_security
from orf.mcp.config import _parse_allowed_dirs as orf_parse_allowed_dirs
from orf.mcp.security import PathValidator as OrfPathValidator

import omni_security
from omni_mcp import orchestrator as omni_orchestrator

# ---------------------------------------------------------------------------
# Canonical 冻结常量（唯一真值来源）
# ---------------------------------------------------------------------------

#: 必须被三份实现一致拦截的系统目录。
#: 加项 = 收紧策略（安全）；减项 = 放松策略（必须在 ADR 0007 里说明理由）。
CANONICAL_SYSTEM_DIRS: frozenset[str] = frozenset({
    "/etc",
    "/usr",
    "/var",
    "/proc",
    "/sys",
    "/System",
    "/Library",
    "/C:/Windows",
    "C:\\Windows",
})

#: 必须被三份实现一致拦截的可执行/脚本扩展名。
CANONICAL_BLOCKED_EXTENSIONS: frozenset[str] = frozenset({
    ".exe",
    ".bat",
    ".cmd",
    ".sh",
    ".ps1",
    ".vbs",
    ".js",
})

#: 各模块扩展名白名单**有意**不同（OPP 摄入 16 种输入格式、OL 摄入词典/TMX/XLIFF/MD
#: 7 种、ORF 产出 21 种格式），所以分别冻结；差异本身不是漂移，未经本表确认的改动才是。
OPP_ALLOWED_EXTENSIONS: frozenset[str] = frozenset({
    ".md", ".docx", ".pptx", ".pdf", ".xliff", ".xlf", ".xml",
    ".html", ".odt", ".epub", ".zip", ".txt",
    ".xlsx", ".csv", ".json", ".eml",
})
OL_ALLOWED_EXTENSIONS: frozenset[str] = frozenset({
    ".json", ".tmx", ".xlf", ".xliff", ".md", ".yaml", ".yml",
})
ORF_ALLOWED_EXTENSIONS: frozenset[str] = frozenset({
    ".md", ".docx", ".pptx", ".xliff", ".xlf", ".xml", ".html", ".odt", ".epub", ".zip",
    ".csv", ".tsv", ".xlsx", ".json", ".ipynb", ".eml", ".msg", ".srt", ".icml", ".rtf",
    ".pdf",
})


# ---------------------------------------------------------------------------
# 行为向量表（只覆盖三份实现**共享**的规则）
# ---------------------------------------------------------------------------

#: 每条向量 = ``(id, 相对 root 的路径模板, 预期判定)``。
#: 路径用 ``/`` 拼接后交给 ``Path``，在 POSIX 与 Windows 上等价；``..`` 由
#: ``Path.parts`` 检出，因此不依赖平台前缀比较（``/proc`` 这类系统目录在 Windows
#: 上前缀匹配天然失效，故不放进向量表）。
SHARED_VECTORS: tuple[tuple[str, str, bool], ...] = (
    ("file_inside_allowlist", "allowed/ok.md", True),
    ("double_dot_traversal", "allowed/../escape.md", False),
    ("traversal_to_system_dir", "allowed/../../etc/passwd", False),
    ("blocked_executable_extension", "allowed/evil.exe", False),
    ("outside_allowlist_sibling", "outside/secret.md", False),
    ("missing_file_inside_allowlist", "allowed/ghost.md", False),
)

#: 向量里需要在磁盘上真实落盘的文件（其余向量不落盘，只验证结构性拒绝）。
_VECTOR_FILES: tuple[str, ...] = (
    "allowed/ok.md",
    "allowed/evil.exe",
    "escape.md",
    "outside/secret.md",
)

#: 套件层 orchestrator 用的向量表：与 :data:`SHARED_VECTORS` 同源，但**去掉存在性
#: 向量**。``omni_mcp.orchestrator._path_denial_message`` 只判路径策略，文件是否
#: 存在由 ``translate_file()`` 之后的 ``FILE_NOT_FOUND`` 分支负责（既有 API 契约，
#: 见 ``tests/security/test_omni_mcp_path_denied.py``）；把存在性混进策略判决会把
#: 那条契约变成 ``OMNI_PATH_DENIED``，属行为回退，所以不合并进同一张表。
ORCHESTRATOR_POLICY_VECTORS: tuple[tuple[str, str, bool], ...] = tuple(
    vector for vector in SHARED_VECTORS if vector[0] != "missing_file_inside_allowlist"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _Copy:
    """一份路径安全实现的可调用包装（统一"拒绝 = False"的判定语义）。"""

    def __init__(self, name: str, factory):
        """初始化。

        Args:
            name: 实现名（``opp`` / ``ol`` / ``orf``），用于断言失败信息。
            factory: 接收 allowed 目录列表、返回 PathValidator 实例的工厂。
        """
        self.name = name
        self._factory = factory

    def validator(self, allowed_dir: Path):
        """用一个允许目录构造 validator。"""
        return self._factory([allowed_dir])

    def verdict(self, allowed_dir: Path, path: str) -> bool:
        """返回该实现对该路径的判定；``PathValidationError`` 记为拒绝。

        OPP 在 Phase 1 规则上抛 ``PathValidationError``，OL/ORF 返回
        ``ValidationResult(success=False)`` —— 两种 API 收敛成同一个 bool。

        Args:
            allowed_dir: 允许访问的目录。
            path: 待判定路径字符串。

        Returns:
            True 表示放行，False 表示拒绝。
        """
        validator = self.validator(allowed_dir)
        try:
            return bool(validator.validate_path(path).success)
        except PathValidationError:
            return False


COPIES: tuple[_Copy, ...] = (
    _Copy("opp", lambda dirs: OppPathValidator(allowed_directories=dirs)),
    _Copy("ol", lambda dirs: OlPathValidator(allowed_directories=dirs)),
    _Copy("orf", lambda dirs: OrfPathValidator(allowed_directories=dirs)),
)


@pytest.fixture
def vector_root(tmp_path: Path) -> Path:
    """造出向量表需要的目录树与文件。

    Returns:
        root 目录（内含 ``allowed/`` 与 ``outside/``）。
    """
    (tmp_path / "allowed").mkdir()
    (tmp_path / "outside").mkdir()
    for rel in _VECTOR_FILES:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix == ".exe":
            target.write_bytes(b"MZ")
        else:
            target.write_text("x")
    return tmp_path


# ---------------------------------------------------------------------------
# 1. 常量一致性
# ---------------------------------------------------------------------------


class TestCanonicalConstants:
    """canonical 常量是所有拷贝的上界，改它必须显式改本文件的字面集合。"""

    def test_opp_core_owns_canonical_system_dirs(self):
        """OPP 共享底层 = canonical（它是 canonical 的持有者）。"""
        assert set(opp_core.SYSTEM_DIRS) == set(CANONICAL_SYSTEM_DIRS)

    def test_opp_core_owns_canonical_blocked_extensions(self):
        """OPP 共享底层的黑名单 = canonical。"""
        assert set(opp_core.BLOCKED_EXTENSIONS) == set(CANONICAL_BLOCKED_EXTENSIONS)

    def test_opp_mcp_wrapper_reexports_the_same_objects(self):
        """OPP MCP 包装必须 re-export 同一对象，而不是再抄一份常量。"""
        assert opp_mcp_security.SYSTEM_DIRS is opp_core.SYSTEM_DIRS
        assert opp_mcp_security.BLOCKED_EXTENSIONS is opp_core.BLOCKED_EXTENSIONS

    def test_ol_system_dirs_match_canonical(self):
        """OL 的 SYSTEM_DIRS 必须等于 canonical（漂移修复：曾缺 /proc、/sys、/C:/Windows）。"""
        assert set(ol_security.SYSTEM_DIRS) == set(CANONICAL_SYSTEM_DIRS)

    def test_ol_blocked_extensions_match_canonical(self):
        """OL 的黑名单必须等于 canonical。"""
        assert set(ol_security.BLOCKED_EXTENSIONS) == set(CANONICAL_BLOCKED_EXTENSIONS)

    def test_orf_system_dirs_match_canonical(self):
        """ORF 的 SYSTEM_DIRS 必须等于 canonical（漂移修复：曾缺 /proc、/sys）。"""
        assert set(orf_security.SYSTEM_DIRS) == set(CANONICAL_SYSTEM_DIRS)

    def test_orf_blocked_extensions_match_canonical(self):
        """ORF 的黑名单必须等于 canonical。"""
        assert set(orf_security.BLOCKED_EXTENSIONS) == set(CANONICAL_BLOCKED_EXTENSIONS)

    def test_orchestrator_system_dirs_are_the_shared_objects(self):
        """套件层 orchestrator 直接使用 ``omni_security`` 的 SYSTEM_DIRS 对象。

        Phase 2A 删除了 orchestrator 的第四份拷贝，它不再自持常量而是 import
        canonical 包。用 identity（``is``）而不是 equality 证明"没有第二份拷贝"——
        equality 对一份值相同的新副本同样成立，identity 只有同一对象才成立。
        """
        assert omni_orchestrator.SYSTEM_DIRS is omni_security.SYSTEM_DIRS

    def test_orchestrator_blocked_extensions_are_the_shared_objects(self):
        """套件层 orchestrator 的黑名单必须与 ``omni_security`` 是同一对象。"""
        assert omni_orchestrator.BLOCKED_EXTENSIONS is omni_security.BLOCKED_EXTENSIONS

    def test_per_module_extension_whitelists_are_frozen(self):
        """三个模块各自的白名单被冻结：差异是有意的，改动必须显式。"""
        from opp.mcp.security import PathValidator as OppPv

        assert set(OppPv.ALLOWED_EXTENSIONS) == set(OPP_ALLOWED_EXTENSIONS)
        assert set(OlPathValidator.ALLOWED_EXTENSIONS) == set(OL_ALLOWED_EXTENSIONS)
        assert set(OrfPathValidator.ALLOWED_EXTENSIONS) == set(ORF_ALLOWED_EXTENSIONS)


# ---------------------------------------------------------------------------
# 2. 行为向量一致性
# ---------------------------------------------------------------------------


class TestSharedVectorParity:
    """同一张向量表跑遍三份实现，判定必须逐条相同且等于预期值。"""

    @staticmethod
    def _verdicts(root: Path, rel: str) -> dict[str, bool]:
        """在 root 上对三个实现求 (name -> 判定)。"""
        path = str(root / rel)
        return {copy.name: copy.verdict(root / "allowed", path) for copy in COPIES}

    @pytest.mark.parametrize(
        ("vector_id", "rel", "expected"),
        SHARED_VECTORS,
        ids=[v[0] for v in SHARED_VECTORS],
    )
    def test_verdict_identical_across_copies(self, vector_root, vector_id, rel, expected):
        """三份实现对该向量必须给出同一判定，且等于表中预期值。"""
        verdicts = self._verdicts(vector_root, rel)
        assert len(set(verdicts.values())) == 1, (
            f"[{vector_id}] 三份实现判定不一致：{verdicts}"
            "（共享规则必须完全一致；差异即为策略漂移）"
        )
        assert verdicts["opp"] is expected, (
            f"[{vector_id}] 预期 {expected}，实际 {verdicts} ——"
            "若这是有意的策略变更，请同步更新 SHARED_VECTORS 与 ADR 0007"
        )


class TestOrchestratorPolicyParity:
    """套件层 orchestrator 必须与三份子模块拷贝给出同一路径判决。

    2026-09-17 补齐（ADR 0007 Phase 1 的延伸）：``omni_mcp.orchestrator`` 此前只做
    allowlist 包含检查 —— 系统目录（``/etc``、``C:\\Windows``）与可执行黑名单
    （``.exe``、``.sh`` …）在这条最外层入口上完全没有拦截，即便 allowlist 被配置成
    文件系统根也一样。它是最外层入口（直接起 OPP/OL/ORF 子进程），漏检等于让三份
    子模块的拦截形同虚设。
    """

    @staticmethod
    def _verdicts(monkeypatch, allowed_dir: Path, path: str) -> dict[str, bool]:
        """求四份拷贝对同一路径的判决（True = 放行）。

        Args:
            monkeypatch: pytest fixture，用于把 allowlist 写进环境变量
                （orchestrator 从环境变量读 allowlist，不接参数）。
            allowed_dir: 允许访问的目录。
            path: 待判定路径。

        Returns:
            ``{拷贝名: 是否放行}``，键为 ``opp`` / ``ol`` / ``orf`` / ``omni_mcp``。
        """
        verdicts = {copy.name: copy.verdict(allowed_dir, path) for copy in COPIES}
        monkeypatch.setenv("MCP_ALLOWED_DIRECTORIES", str(allowed_dir))
        verdicts["omni_mcp"] = omni_orchestrator._path_denial_message(path) is None
        return verdicts

    @pytest.mark.parametrize(
        ("vector_id", "rel", "expected"),
        ORCHESTRATOR_POLICY_VECTORS,
        ids=[v[0] for v in ORCHESTRATOR_POLICY_VECTORS],
    )
    def test_verdict_identical_to_the_three_copies(
        self, vector_root, monkeypatch, vector_id, rel, expected
    ):
        """四份拷贝对该向量必须给出同一判定，且等于表中预期值。"""
        path = str(vector_root / rel)
        verdicts = self._verdicts(monkeypatch, vector_root / "allowed", path)
        assert len(set(verdicts.values())) == 1, (
            f"[{vector_id}] orchestrator 与三份子模块拷贝判定不一致：{verdicts}"
            "（同一套策略的副本不允许有差异）"
        )
        assert verdicts["omni_mcp"] is expected, (
            f"[{vector_id}] 预期 {expected}，实际 {verdicts}"
        )

    def test_system_directory_is_denied_by_every_copy(self, vector_root, monkeypatch):
        """平台对应的系统目录路径必须被四份拷贝一致拒绝。

        只断言判决与"命中的是系统目录这条分支"，不落盘：四份实现都把系统目录检查
        放在存在性检查之前，所以路径不必真实存在。POSIX 用 ``/etc``、Windows 用
        ``C:\\Windows`` —— 前缀比较的语义决定了这两类目录在对方平台上天然不命中。
        """
        target = Path("C:/Windows") / "omni-parity-probe.md" if os.name == "nt" else Path(
            "/etc/omni-parity-probe.md"
        )
        verdicts = self._verdicts(monkeypatch, vector_root / "allowed", str(target))
        assert set(verdicts.values()) == {False}, (
            f"系统目录 {target} 未被四份拷贝一致拦截：{verdicts}"
        )
        message = omni_orchestrator._path_denial_message(str(target))
        assert message is not None and "system directory" in message, (
            f"orchestrator 的拒绝理由必须点名系统目录分支，实际：{message!r}"
        )

    def test_blocked_extension_branch_names_the_extension(self, vector_root, monkeypatch):
        """黑名单分支必须明说被拒的扩展名，而不是笼统的"不在 allowlist 内"。"""
        monkeypatch.setenv("MCP_ALLOWED_DIRECTORIES", str(vector_root / "allowed"))
        message = omni_orchestrator._path_denial_message(
            str(vector_root / "allowed" / "evil.exe")
        )
        assert message is not None, "allowlist 内的 .exe 必须被黑名单拦截"
        assert ".exe" in message and "blocked" in message, f"拒绝理由不明确：{message!r}"


# ---------------------------------------------------------------------------
# 3. MCP_ALLOWED_EXTENSIONS 解析语义一致性
# ---------------------------------------------------------------------------


class TestEnvOverrideParity:
    """同一个环境变量在三份实现里必须同义（前导点可选、纯空白视为未设置）。"""

    def test_dotted_value_matches_across_copies(self, monkeypatch):
        """``MCP_ALLOWED_EXTENSIONS=.zzz`` 三份实现都解析为 ``{.zzz}``。"""
        monkeypatch.setenv("MCP_ALLOWED_EXTENSIONS", ".zzz")
        assert opp_mcp_security.resolve_allowed_extensions(OppPathValidator.ALLOWED_EXTENSIONS) == {".zzz"}
        assert ol_security.PathValidator.get_allowed_extensions() == {".zzz"}
        assert orf_security.resolve_allowed_extensions(OrfPathValidator.ALLOWED_EXTENSIONS) == {".zzz"}

    def test_undotted_value_is_normalised_by_all_copies(self, monkeypatch):
        """``=zzz``（无前导点）三份实现都必须补点 —— 曾只有 OL 不补。"""
        monkeypatch.setenv("MCP_ALLOWED_EXTENSIONS", "zzz")
        assert opp_mcp_security.resolve_allowed_extensions(OppPathValidator.ALLOWED_EXTENSIONS) == {".zzz"}
        assert ol_security.PathValidator.get_allowed_extensions() == {".zzz"}
        assert orf_security.resolve_allowed_extensions(OrfPathValidator.ALLOWED_EXTENSIONS) == {".zzz"}

    def test_whitespace_only_value_falls_back_to_default(self, monkeypatch):
        """纯空白 = 未设置（三份实现都返回各自默认集合，不得产生空集）。"""
        monkeypatch.setenv("MCP_ALLOWED_EXTENSIONS", "   ")
        assert opp_mcp_security.resolve_allowed_extensions(OppPathValidator.ALLOWED_EXTENSIONS) == set(
            OPP_ALLOWED_EXTENSIONS
        )
        assert ol_security.PathValidator.get_allowed_extensions() == set(OL_ALLOWED_EXTENSIONS)
        assert orf_security.resolve_allowed_extensions(OrfPathValidator.ALLOWED_EXTENSIONS) == set(
            ORF_ALLOWED_EXTENSIONS
        )

    def test_undotted_override_accepts_the_file_in_all_three(self, tmp_path, monkeypatch):
        """行为层收口：``=zzz`` + ``ok.zzz`` 三份实现都放行（收敛前 OL 会拒）。"""
        target = tmp_path / "ok.zzz"
        target.write_text("x")
        monkeypatch.setenv("MCP_ALLOWED_EXTENSIONS", "zzz")
        verdicts = {copy.name: copy.verdict(tmp_path, str(target)) for copy in COPIES}
        assert set(verdicts.values()) == {True}, f"环境变量覆盖未在三份实现里生效：{verdicts}"


class TestLegacyValidateHonoursEnv:
    """legacy ``validate()`` 必须与 ``validate_path()`` 读同一份生效白名单。

    修复（2026-09-17，ADR 0007）：OPP/ORF 的 ``validate()`` 原来直读类常量
    ``ALLOWED_EXTENSIONS``，``MCP_ALLOWED_EXTENSIONS`` 在 legacy 路径上静默失效。
    """

    @pytest.mark.parametrize("validator_cls", [OppPathValidator, OrfPathValidator],
                             ids=["opp", "orf"])
    def test_env_override_applies_to_legacy_validate(self, validator_cls, monkeypatch):
        """设 ``=zzz`` 后 legacy ``validate()`` 必须放行 ``.zzz`` 且拒绝 ``.md``。"""
        monkeypatch.setenv("MCP_ALLOWED_EXTENSIONS", ".zzz")
        assert validator_cls.validate("input.zzz") == (True, "")
        ok, message = validator_cls.validate("input.md")
        assert ok is False and "not in allowed set" in message

    @pytest.mark.parametrize("validator_cls", [OppPathValidator, OrfPathValidator],
                             ids=["opp", "orf"])
    def test_default_applies_when_env_unset(self, validator_cls, monkeypatch):
        """未设环境变量时 legacy ``validate()`` 用类默认集合。"""
        monkeypatch.delenv("MCP_ALLOWED_EXTENSIONS", raising=False)
        assert validator_cls.validate("input.md") == (True, "")
        ok, _ = validator_cls.validate("input.zzz")
        assert ok is False

    @pytest.mark.parametrize("validator_cls", [OppPathValidator, OrfPathValidator],
                             ids=["opp", "orf"])
    def test_whitespace_only_env_falls_back(self, validator_cls, monkeypatch):
        """纯空白环境变量不得把 legacy ``validate()`` 变成"全拒"。"""
        monkeypatch.setenv("MCP_ALLOWED_EXTENSIONS", "  ")
        assert validator_cls.validate("input.md") == (True, "")

    def test_legacy_validate_still_rejects_traversal(self, monkeypatch):
        """legacy 路径的穿越拦截不得因本次改动而放松。"""
        monkeypatch.delenv("MCP_ALLOWED_EXTENSIONS", raising=False)
        for validator_cls in (OppPathValidator, OrfPathValidator):
            ok, message = validator_cls.validate(str(Path("a") / ".." / "b.md"))
            assert ok is False and "traversal" in message.lower()


def test_split_allowlist_is_platform_correct(monkeypatch):
    """``omni_mcp`` 的 allowlist 切分不得把 Windows 盘符切开（缺陷 D-3 回归）。

    ``os.pathsep`` 在 POSIX 上是 ``:``、Windows 上是 ``;``。旧实现在两个平台上都把
    ``:`` 当分隔符，于是 ``C:\\work`` 被切成 ``C`` 与 ``\\work``，allowlist 在
    Windows 上等于完全失效。
    """
    from omni_mcp.orchestrator import _split_allowlist

    if os.name == "nt":
        assert _split_allowlist(r"C:\work;D:\data") == [r"C:\work", r"D:\data"]
    else:
        assert _split_allowlist("/work:/data") == ["/work", "/data"]
    # 逗号在所有平台都可用，且空白被去掉
    assert _split_allowlist(" /a , /b ") == ["/a", "/b"]


# ---------------------------------------------------------------------------
# allowlist 解析一致性（ADR 0007 Phase 1，2026-09-17 新增同族缺陷）
# ---------------------------------------------------------------------------


def _omni_parse_allowed_dirs(value: str) -> list[Path]:
    """``omni_mcp.orchestrator`` 的 allowlist 解析适配器（字符串 → ``Path``）。

    orchestrator 的 ``_split_allowlist`` 只负责切分，``Path`` 转换发生在
    ``_allowed_directories`` 里；这里把两步拼起来，使它可与三份
    ``_parse_allowed_dirs`` 逐字比较。

    Args:
        value: 环境变量原始值。

    Returns:
        非空分段组成的 ``Path`` 列表（与三份 ``_parse_allowed_dirs`` 同契约）。
    """
    return [Path(part) for part in omni_orchestrator._split_allowlist(value)]


#: 四份拷贝的 allowlist 解析入口。键 = 拷贝名。
#:
#: 它们都读同一个 ``MCP_ALLOWED_DIRECTORIES``（各自的模块专属变量作回退），
#: 所以切分语义必须逐字相同 —— 否则同一个环境变量在四份实现里含义不同。
ALLOWLIST_PARSERS = {
    "opp": opp_parse_allowed_dirs,
    "ol": ol_parse_allowed_dirs,
    "orf": orf_parse_allowed_dirs,
    "omni_mcp": _omni_parse_allowed_dirs,
}


class TestAllowlistParsingParity:
    """四份 allowlist 解析入口必须对同一输入给出逐字相同的结果。

    缺陷族（2026-09-17，与 ``omni_mcp.orchestrator`` 的 D-3 同一模式）：OPP 与
    ORF 的 ``_parse_allowed_dirs`` 优先按 ``":"`` 切分（``separators = [":", ";"]``），
    而 Windows 盘符本身含 ``":"``。于是：

    * ``ORF_MCP_ALLOWED_DIRS=C:\\work`` → ``["C", "\\work"]`` → 两个都不包含目标
      路径，**allowlist 在 Windows 上完全失效**，任何合法路径都被判
      ``PATH_NOT_ALLOWED``（实测复现：
      ``Omni_Re_Formatter/tests/test_orf_security_attacks.py`` 的两条 happy-path
      用例，报错里能看到被解析成 ``D:\\贯维\\Omni_Suite\\C`` 的假目录）；
    * OPP 的 Windows 文档写法 ``OPP_MCP_ALLOWED_DIRS=C:\\docs;C:\\out``
      （``docs/opencode-installation.md``、``install_opp_agents.bat``）同样被打散。

    OL 是第三个副本，此前只按逗号切分 —— 没有这个 bug，但语义与 OPP/ORF 不同，
    而 ``omni_mcp.orchestrator`` 的拒绝提示明确写着 "comma- or
    '<os.pathsep>'-separated"，OL 不认平台分隔符会让那条提示变成假话。

    统一契约为：按 ``os.pathsep``（POSIX ``":"`` / Windows ``";"``）加逗号切分，
    去空白、丢空段；不含分隔符的值就是单元素列表。
    """

    def test_separator_free_value_is_a_single_entry(self, tmp_path):
        """无分隔符的值必须原样成为单元素 —— Windows 上即"盘符不被切开"。

        Windows 本地跑这条用例时 ``str(tmp_path)`` 形如 ``C:\\Users\\...``，
        正是被旧实现切开的那种输入；POSIX 上它锁定的是单路径不返回 ``[]``
        （round 12 ORF FIX-#5 的老回归）。
        """
        target = str(tmp_path)
        for name, parse in ALLOWLIST_PARSERS.items():
            assert parse(target) == [Path(target)], (
                f"{name} 把单个目录切散了：{parse(target)!r}"
            )

    def test_all_parsers_agree_on_every_vector(self, tmp_path):
        """逐条向量：四份实现的解析结果必须完全相同且等于预期值。"""
        alpha = tmp_path / "alpha"
        beta = tmp_path / "beta"
        alpha.mkdir()
        beta.mkdir()
        vectors: dict[str, tuple[str, list[Path]]] = {
            "single_path": (str(alpha), [alpha]),
            "platform_separated": (
                os.pathsep.join([str(alpha), str(beta)]),
                [alpha, beta],
            ),
            "comma_separated": (f"{alpha},{beta}", [alpha, beta]),
            "whitespace_padded": (f"   {alpha} , {beta}   ", [alpha, beta]),
            "blank_value": ("   ", []),
            "empty_value": ("", []),
        }
        for label, (raw, expected) in vectors.items():
            verdicts = {name: parse(raw) for name, parse in ALLOWLIST_PARSERS.items()}
            assert set(map(tuple, verdicts.values())) == {tuple(expected)}, (
                f"向量 {label!r}（raw={raw!r}）四份实现不一致：{verdicts!r}"
            )

    def test_platform_separator_split_matches_os_pathsep(self, tmp_path):
        """平台分隔符必须被当作分隔符（Windows ``;`` / POSIX ``:``）。"""
        alpha = tmp_path / "alpha"
        beta = tmp_path / "beta"
        alpha.mkdir()
        beta.mkdir()
        raw = os.pathsep.join([str(alpha), str(beta)])
        for name, parse in ALLOWLIST_PARSERS.items():
            assert parse(raw) == [alpha, beta], f"{name} 未按 os.pathsep 切分"

    @pytest.mark.skipif(
        os.name != "nt",
        reason="盘符语义仅存在于 Windows；POSIX 上 ':' 就是合法分隔符，本用例无意义",
    )
    def test_drive_letter_colon_is_not_a_separator(self):
        """Windows 盘符里的 ``":"`` 不得被当作分隔符（缺陷族核心回归）。

        仅 Windows 生效：POSIX 上 ``":"`` 是 ``os.pathsep``，按它切分是**正确**
        行为，所以本用例不做成跨平台断言，也不伪装成通过。修复前的实测证据见
        类 docstring 引用的 ``test_orf_security_attacks.py`` 失败输出。
        """
        for name, parse in ALLOWLIST_PARSERS.items():
            assert parse(r"C:\work") == [Path(r"C:\work")], f"{name} 切开了盘符"
            assert parse(r"C:\docs;C:\out") == [
                Path(r"C:\docs"),
                Path(r"C:\out"),
            ], f"{name} 未按 ';' 切分 Windows 多目录"
