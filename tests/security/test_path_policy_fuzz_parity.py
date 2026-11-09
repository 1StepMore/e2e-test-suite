"""路径策略五实现对拍 fuzz（suite#281，ADR 0007）。

把手写行为向量（``test_path_policy_parity.py``，解决"已知的"漂移）升级成
生成式对拍：:mod:`tests.security._path_fuzz_gen` 按固定种子生成 2400 个
case，同一 case 同时喂给五个实现，逐 case 与**文档化策略模型**对拍，并
在模型判"共享"的维度上额外断言跨实现一致：

1. **OPP 共享核心**  ``opp.utils.security.validate_path``（抛 ``PathValidationError``）
2. **OPP MCP 壳**    ``opp.mcp.security.PathValidator.validate_path``
3. **OL**            ``ol_mcp.security.PathValidator.validate_path``
4. **ORF**           ``orf.mcp.security.PathValidator.validate_path``
5. **orchestrator**  ``omni_mcp.orchestrator._path_denial_message``

差异三分类（issue #281 契约；每类都有归因，不许"全塞进 allowlist"）：

* **已知设计差异**（模型显式编码 + ADR 条款）：
  - 分层：OPP 共享核心是路径安全内核，只持 canonical 黑名单
    （``test_path_policy_parity.py`` 冻结断言它 owns SYSTEM_DIRS/BLOCKED_EXTENSIONS），
    **不含**模块扩展名白名单 —— 白名单是 MCP 壳/各模块策略层的事；
  - 模块白名单有意不同（OPP 20 / OL 7 / ORF 21，冻结表）→ design 扩展按
    "各实现按自己的白名单收放"逐实现断言；
  - orchestrator 无扩展名白名单、无存在性检查（ADR 0007 Step 3b；suite 的
    ``FILE_NOT_FOUND`` 是它下游的独立分支契约）→ 结构合法但缺失的路径：
    四子模块一致拒绝（缺文件），orchestrator 策略放行 —— 断言差异本身。
* **平台差异** → ``pytest.skip`` 显式标注（Windows 无符号链接特权；Win32
  尾点别名）。尾随点/大小写在 POSIX 上是普通文件语义，五层共享同一路径
  层，判定仍须一致，不跳过。
* **真漂移** → 本文件直接红（case id + 五判定全打印）；修复需另行授权
  （不改生产代码）。

复现性（DoD 2）：``generate_cases`` 纯函数 + 固定种子，库内自检"生成两次
逐项相等"；CI 侧同一命令跑两次输出一致。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _path_fuzz_gen import BLOCKED_EXTENSIONS, SEED, SHARED_EXTENSIONS, FuzzCase, generate_cases
from ol_mcp.security import PathValidator as OlPathValidator
from opp.mcp.security import PathValidationError
from opp.mcp.security import PathValidator as OppPathValidator
from opp.utils import security as opp_core
from orf.mcp.security import PathValidator as OrfPathValidator

import omni_security
from omni_mcp import orchestrator as omni_orchestrator

# ---------------------------------------------------------------------------
# 五个实现的归一化适配层（统一"放行 = True"）
# ---------------------------------------------------------------------------


def _v_opp_core(path: str, allowed_dir: Path) -> bool:
    try:
        opp_core.validate_path(path, [allowed_dir])
        return True
    except opp_core.PathValidationError:
        return False


def _v_opp_mcp(path: str, allowed_dir: Path) -> bool:
    try:
        return bool(OppPathValidator(allowed_directories=[allowed_dir]).validate_path(path).success)
    except PathValidationError:
        return False


def _v_ol(path: str, allowed_dir: Path) -> bool:
    return bool(OlPathValidator(allowed_directories=[allowed_dir]).validate_path(path).success)


def _v_orf(path: str, allowed_dir: Path) -> bool:
    return bool(OrfPathValidator(allowed_directories=[allowed_dir]).validate_path(path).success)


IMPLEMENTATIONS = ("opp_core", "opp_mcp", "ol", "orf", "omni_mcp")
SUBMODULES = ("opp_core", "opp_mcp", "ol", "orf")

#: 各实现的模块白名单（design 扩展 case 的逐实现断言依据）。核心无白名单。
MODULE_WHITELISTS: dict[str, frozenset[str]] = {
    "opp_mcp": frozenset(OppPathValidator.ALLOWED_EXTENSIONS),
    "ol": frozenset(OlPathValidator.ALLOWED_EXTENSIONS),
    "orf": frozenset(OrfPathValidator.ALLOWED_EXTENSIONS),
}


def _run_case(impl: str, case: FuzzCase, root: Path, monkeypatch) -> bool:
    """对一个实现求判定。"""
    path = str(root / case.rel) if case.rel else str(root)
    if impl == "opp_core":
        return _v_opp_core(path, root / "allowed")
    if impl == "opp_mcp":
        return _v_opp_mcp(path, root / "allowed")
    if impl == "ol":
        return _v_ol(path, root / "allowed")
    if impl == "orf":
        return _v_orf(path, root / "allowed")
    if impl == "omni_mcp":
        monkeypatch.setenv("MCP_ALLOWED_DIRECTORIES", str(root / "allowed"))
        return omni_orchestrator._path_denial_message(path) is None
    raise AssertionError(f"unknown impl {impl}")


# ---------------------------------------------------------------------------
# 盘面构造（模块级一次：全部 case 共享同一棵树）
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fuzz_root(tmp_path_factory):
    """构造整棵 case 树；返回 (root, symlink_unsupported, creation_failed)。

    symlink 在 Windows 无特权环境下创建失败 → case 级显式 ``pytest.skip``
    （平台差异类，不许静默）。``creation_failed`` 记录 Windows 尾点别名等
    创建期平台语义，供模型归因。
    """
    root = tmp_path_factory.mktemp("path_fuzz")
    (root / "allowed").mkdir()
    (root / "outside").mkdir()
    unsupported: set[str] = set()
    creation_failed: set[str] = set()
    for case in generate_cases():
        if case.domain == "symlink":
            link = root / "allowed" / Path(case.rel).name
            if case.allowlist_raw.startswith(".."):
                target = root / "outside" / f"target_{case.case_id}.md"
            else:
                target = root / "allowed" / case.allowlist_raw
            target.parent.mkdir(parents=True, exist_ok=True)
            if not case.allowlist_raw.startswith(".."):
                target.write_text("x", encoding="utf-8")  # inside 目标必须真实存在
            try:
                os.symlink(target, link)
            except (OSError, NotImplementedError):
                unsupported.add(case.case_id)
            continue
        if case.domain == "allowlist_str" or not case.rel or not case.exists:
            continue
        target = root / case.rel
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x", encoding="utf-8")
        except OSError:
            creation_failed.add(case.case_id)  # 如 Windows 尾点别名
    return root, unsupported, creation_failed


ALL_CASES = generate_cases()


# ---------------------------------------------------------------------------
# DoD 2：固定种子可复现（生成两次逐项相等）
# ---------------------------------------------------------------------------


def test_generator_is_seed_deterministic():
    """同种子两次生成必须逐项相等（DoD 2 的库内自检；CI 另贴两次 pytest 输出）。"""
    assert generate_cases() == generate_cases()
    assert generate_cases(seed=SEED) == generate_cases(seed=SEED)
    assert len(generate_cases()) >= 2000


def test_seed_change_changes_cases():
    """换个种子必须产生不同序列 —— 证明种子真的进了随机源。"""
    assert generate_cases(seed=SEED) != generate_cases(seed=SEED + 1)


# ---------------------------------------------------------------------------
# 文档化策略模型（差异归因落点）
# ---------------------------------------------------------------------------

_POSIX_SYSTEM_PREFIXES = ("/etc", "/proc", "/sys", "/usr", "/var", "/System", "/C:/Windows")


def _suffix_of(case: FuzzCase) -> str:
    return Path(case.rel).suffix if case.rel else ""


def _symlink_mode(case: FuzzCase) -> str:
    if case.allowlist_raw.startswith(".."):
        return "outside"
    # inside 目标由 fixture 落盘；broken 目标从不落盘
    return "broken" if case.allowlist_raw.startswith("missing_") else "inside"


def _structurally_rejected(case: FuzzCase) -> bool:
    """生成器保证的三类结构性拒绝：穿越 / 系统目录 / canonical 黑名单。"""
    if case.domain == "traversal" or ".." in Path(case.rel).parts:
        return True
    if _suffix_of(case) in BLOCKED_EXTENSIONS:
        return True
    rel = case.rel
    if rel.startswith(_POSIX_SYSTEM_PREFIXES):
        return True
    if rel.replace("/", "\\").startswith("C:\\Windows"):
        return True
    return False


def _expected(impl: str, case: FuzzCase, exists: bool) -> bool:
    """文档化策略模型：该实现对该 case 的**应然**判定。

    归因（ADR 0007 + 冻结表）：
    - 结构性拒绝（穿越/系统目录/黑名单）：五方一致 False（共享规则）。
    - orchestrator：无白名单、无存在性检查 → 结构合法即 True。
    - OPP 共享核心：内核无 allowlist 白名单（黑名单归它）→ 结构合法且
      存在即 True，缺失 False。
    - 三个壳：白名单 ∩ 存在。
    - symlink：inside → True；outside/broken → False（解析后包含性，五方共享）。
    """
    if case.domain == "symlink":
        mode = _symlink_mode(case)
        if mode == "inside":
            return True
        if mode == "outside":
            return False
        # broken：orchestrator 只做解析后包含性（无存在性检查）→ 指向
        # allowlist 内缺失文件的断链仍放行；四个子模块的存在性检查 → 拒绝。
        # 这是文档化设计差异（ADR 0007 Step 3b / FILE_NOT_FOUND 契约）。
        return impl == "omni_mcp"
    if _structurally_rejected(case):
        return False
    if impl == "omni_mcp":
        return True
    if impl == "opp_core":
        return exists
    return exists and _suffix_of(case) in MODULE_WHITELISTS[impl]


# ---------------------------------------------------------------------------
# 主对拍
# ---------------------------------------------------------------------------


class TestFuzzParity:
    """2400 case × 5 实现：逐 case 对文档化模型对拍 + 共享维度一致断言。"""

    @pytest.mark.parametrize("case", ALL_CASES, ids=[c.case_id for c in ALL_CASES])
    def test_case(self, case: FuzzCase, fuzz_root, monkeypatch):
        root, unsupported, creation_failed = fuzz_root
        if case.case_id in unsupported:
            pytest.skip("symlink creation unsupported on this platform (no privilege/dev mode)")
        if case.case_id in creation_failed:
            pytest.skip("path creation rejected by the platform (Win32 trailing-dot alias)")

        verdicts = {impl: _run_case(impl, case, root, monkeypatch) for impl in IMPLEMENTATIONS}

        if case.domain == "allowlist_str":
            self._assert_allowlist_parsers(case)
            return

        # 1) 模型对拍（每实现必须等于文档化应然判定）。
        exists = case.exists or case.rel == "allowed"
        for impl in IMPLEMENTATIONS:
            expected = _expected(impl, case, exists)
            assert verdicts[impl] is expected, (
                f"[{case.case_id}/{case.domain}] {impl} 判定漂移："
                f"应然={expected} 实然={verdicts[impl]}\n"
                f"rel={case.rel!r} exists={exists} suffix={_suffix_of(case)!r}\n"
                f"五方实然：{verdicts}"
            )

        # 2) 共享维度上额外断言跨实现一致：
        #    - 结构性拒绝：五方全 False（模型已保证，这里显式再断一次）；
        #    - 结构合法且存在、扩展名属三方交集或 canonical 黑名单：五方一致；
        #    - 结构合法但缺失：四子模块一致 False（orchestrator 的差异已由模型断言）。
        if _structurally_rejected(case):
            assert set(verdicts.values()) == {False}, f"[{case.case_id}] 五方未一致拦截：{verdicts}"
        elif exists and _suffix_of(case) in SHARED_EXTENSIONS:
            assert len(set(verdicts.values())) == 1, (
                f"[{case.case_id}] 共享扩展名判定漂移：{verdicts}"
            )
        elif not exists:
            sub = {k: verdicts[k] for k in SUBMODULES}
            assert len(set(sub.values())) == 1, (
                f"[{case.case_id}] 缺失路径上四子模块判定不一致：{sub}"
            )

    # ------------------------------------------------------------------

    @staticmethod
    def _assert_allowlist_parsers(case: FuzzCase) -> None:
        """输入域 5：四个 allowlist 解析入口对同一原始串切分一致。"""
        from ol_mcp.security import _parse_allowed_dirs as ol_parse
        from opp.mcp.config import _parse_allowed_dirs as opp_parse
        from orf.mcp.config import _parse_allowed_dirs as orf_parse

        from omni_mcp.orchestrator import _split_allowlist as omni_split

        raw = case.allowlist_raw
        results = {
            "opp": tuple(opp_parse(raw)),
            "ol": tuple(ol_parse(raw)),
            "orf": tuple(orf_parse(raw)),
            "omni_mcp": tuple(Path(p) for p in omni_split(raw)),
        }
        assert len(set(results.values())) == 1, (
            f"[{case.case_id}] allowlist 解析漂移：raw={raw!r} → {results}"
        )


# ---------------------------------------------------------------------------
# canonical 常量兜底锚（防生成器口径写歪）
# ---------------------------------------------------------------------------


def test_canonical_constants_unchanged():
    """fuzz 的黑名单样本必须是 canonical 的子集（口径锚定）。"""
    assert set(BLOCKED_EXTENSIONS) <= set(omni_security.BLOCKED_EXTENSIONS)
