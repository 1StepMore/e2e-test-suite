"""零依赖路径策略对拍 fuzz 生成器（suite#281，ADR 0007）。

把手写行为向量（``test_path_policy_parity.py``）升级成生成式对拍：同一批
随机/结构化生成的路径喂给五个实现（OPP 共享核心、OPP MCP 壳、OL、ORF、
套件层 orchestrator），比较判定结果。

设计约束（issue #281 执行契约）：
- **零依赖**：只用 ``random.Random(固定种子)`` + 显式结构生成器，可复现；
  不引入 hypothesis（会动 pyproject/uv.lock，本批禁止）。
- **输入域必须有**：遍历穿越 / 符号链接 / 系统目录 / 分隔符混用 /
  allowlist 解析 / 大小写与尾随点 / 超长-空-扩展名七域，见 ``DOMAINS``。
- **差异预算**：设计差异类（扩展名白名单差异 + orchestrator 无白名单/无
  存在性检查）占生成总量 <= 5%，其余一律进严格一致断言。

输出 case 为纯数据（dict），不含任何实现引用 —— 消费方是
``test_path_policy_fuzz_parity.py``。
"""

from __future__ import annotations

import random
from dataclasses import dataclass

#: 固定种子 —— 同一种子必须生成逐字节相同的 case 序列（DoD 2：两次运行一致）。
SEED = 20261110

#: 生成总量（>= 2000，issue DoD 1）。
CASE_COUNT = 2400

#: 三份模块白名单的**交集**：这些扩展名在四个策略拷贝里语义一致，
#: 可以进严格 5-way 一致断言。推导自 test_path_policy_parity.py 的冻结表。
SHARED_EXTENSIONS: tuple[str, ...] = (".md", ".json", ".xliff", ".xlf")

#: canonical 黑名单（全部实现必须拦；作为扩展名域的另一半）。
BLOCKED_EXTENSIONS: tuple[str, ...] = (
    ".exe", ".bat", ".cmd", ".sh", ".ps1", ".vbs", ".js",
)

#: **有意**的模块白名单差异样本（每条都能在冻结表中找到归属）：
#: .tmx/.yaml 只在 OL；.txt 只在 OPP；.srt 只在 ORF；.zzz 谁都不收。
DESIGN_EXTENSIONS: tuple[str, ...] = (".tmx", ".yaml", ".txt", ".srt", ".zzz")

#: 系统目录样本（issue 输入域 3）。POSIX 形态在 Windows 上天然不命中前缀，
#: Windows 形态在 POSIX 上同理 —— 平台差异由消费方以 ``os.name`` 显式标注。
SYSTEM_DIR_PATHS: tuple[str, ...] = (
    "/etc/passwd",
    "/proc/self/environ",
    "/sys/kernel/mm",
    "/etc/../etc/shadow",
    "C:\\Windows\\system32\\config",
    "C:\\Windows\\explorer.exe",
    "/C:/Windows/notepad.exe",
    "/usr/share/doc",
    "/var/log/syslog",
    "/System/Library/CoreServices",
)

#: URL 编码残留样本（输入域 1 的补充；解码不归路径层管，层与层判定必须一致）。
URL_ENCODED_SUFFIXES: tuple[str, ...] = (
    "%2e%2e/escape.md",
    "..%2fescape.md",
    "%252e%252e/escape.md",
    "ok%20name.md",
    "ok%2Ejson",
)

#: 尾随点 / 大小写样本（输入域 6；Windows 语义，POSIX 上是普通文件名）。
CASE_SUFFIXES: tuple[str, ...] = (
    "MD", "Md", "md.", "md .", "..md", "md...",
)

DOMAINS: tuple[str, ...] = (
    "traversal",        # 输入域 1
    "symlink",          # 输入域 2
    "system_dirs",      # 输入域 3
    "separator_mix",    # 输入域 4
    "allowlist_str",    # 输入域 5（allowlist 解析串，给 parser 对拍用）
    "case_trailing",    # 输入域 6
    "long_empty_ext",   # 输入域 7
    "structural",       # 结构合法基线（放行/缺文件/黑名单的主域）
)


@dataclass(frozen=True)
class FuzzCase:
    """一个对拍 case。

    Attributes:
        case_id: 稳定 id（种子固定则 id 固定），断言失败信息用它定位。
        domain: ``DOMAINS`` 之一。
        rel: 相对 tmp root 的路径（``/`` 拼接，消费方交 ``Path``）。
        exists: 消费方是否应在磁盘上创建该文件（穿越类恒为 False）。
        ext_class: ``shared`` / ``blocked`` / ``none`` / ``design`` ——
            决定该 case 进严格一致断言还是进差异归因表。
        allowlist_raw: 仅 ``allowlist_str`` 域使用；给四个 parser 对拍的原始串。
    """

    case_id: str
    domain: str
    rel: str
    exists: bool
    ext_class: str
    allowlist_raw: str = ""


def _shared_ext(rng: random.Random) -> str:
    return rng.choice(SHARED_EXTENSIONS)


def _gen_traversal(rng: random.Random, i: int) -> FuzzCase:
    depth = rng.randint(1, 6)
    hops = "/".join(".." for _ in range(depth))
    tail = rng.choice([
        f"escape{_shared_ext(rng)}", "escape", f"....//escape{_shared_ext(rng)}",
        "nested/" + hops + "/escape.md",
    ])
    return FuzzCase(
        case_id=f"trav-{i:04d}", domain="traversal",
        rel=f"allowed/{hops}/{tail}", exists=False, ext_class="shared",
    )


def _gen_symlink(rng: random.Random, i: int) -> FuzzCase:
    # symlink 链接路径必须在 allowlist 内；目标在盘上由消费方创建：
    #   inside -> 允许目录内的真实文件；outside -> 允许目录外；broken -> 不存在。
    mode = rng.choice(["inside", "outside", "broken"])
    name = f"link_{mode}_{i}{_shared_ext(rng)}"
    return FuzzCase(
        case_id=f"syml-{i:04d}", domain="symlink",
        rel=f"allowed/{name}", exists=False,
        ext_class="shared",
        allowlist_raw={"inside": f"target_inside_{i}.md",
                       "outside": f"../outside/target_{i}.md",
                       "broken": f"missing_{i}.md"}[mode],
    )


def _gen_system_dirs(rng: random.Random, i: int) -> FuzzCase:
    return FuzzCase(
        case_id=f"sysd-{i:04d}", domain="system_dirs",
        rel=rng.choice(SYSTEM_DIR_PATHS), exists=False, ext_class="shared",
    )


def _gen_separator_mix(rng: random.Random, i: int) -> FuzzCase:
    depth = rng.randint(2, 5)
    segs = [f"seg{j}" for j in range(depth)]
    body = rng.choice(["\\", "/", "//", "\\/", "/\\"]).join(segs)
    # Windows 形态只在 Windows 上按预期解析；POSIX 上 '\\' 是文件名的一部分，
    # 但五个实现共享同一路径层，**判定仍须一致**（一致允许/一致拒绝都算通过）。
    ext = rng.choice([_shared_ext(rng), "", rng.choice(BLOCKED_EXTENSIONS)])
    return FuzzCase(
        case_id=f"sep-{i:04d}", domain="separator_mix",
        rel=f"allowed/{body}{ext}", exists=False, ext_class="shared",
    )


def _gen_allowlist_str(rng: random.Random, i: int) -> FuzzCase:
    import os

    sep = rng.choice([os.pathsep, ",", " , ", " ; " if os.name == "nt" else " : "])
    parts = rng.choice([
        ["allowed", "outside"],
        ["allowed", ""],
        ["allowed ", " outside"],
        ["allowed/"],
        ["", ""],
    ])
    raw = sep.join(parts)
    return FuzzCase(
        case_id=f"alst-{i:04d}", domain="allowlist_str",
        rel="", exists=False, ext_class="none", allowlist_raw=raw,
    )


def _gen_case_trailing(rng: random.Random, i: int) -> FuzzCase:
    suffix = rng.choice(CASE_SUFFIXES)
    # exists=True：让大小写变体（.MD/.Md）真正可判 —— 缺文件时所有实现都因
    # 不存在拒绝，白名单大小写语义就测不出来了。Windows 上 "md." 会与
    # "md" 别名（Win32 去尾点），创建失败由消费方归因为平台语义。
    return FuzzCase(
        case_id=f"case-{i:04d}", domain="case_trailing",
        rel=f"allowed/file{suffix}", exists=True, ext_class="shared",
    )


def _gen_long_empty_ext(rng: random.Random, i: int) -> FuzzCase:
    kind = rng.choice(["long", "empty", "ext_only", "no_ext", "blocked"])
    if kind == "long":
        # 120-160 字符：超过 200 会在 Windows 默认 MAX_PATH=260 下连 tmp root
        # 一起爆掉；长度本身就是要测的域，但不制造平台创建失败。
        name = "f" * rng.randint(120, 160) + _shared_ext(rng)
        return FuzzCase(case_id=f"lenx-{i:04d}", domain="long_empty_ext",
                        rel=f"allowed/{name}", exists=True, ext_class="shared")
    if kind == "empty":
        # rel 即 allowlist 目录本身（盘面上真实存在）。
        return FuzzCase(case_id=f"lenx-{i:04d}", domain="long_empty_ext",
                        rel="allowed", exists=True, ext_class="none")
    if kind == "ext_only":
        name = rng.choice([".md", "..md"])
        return FuzzCase(case_id=f"lenx-{i:04d}", domain="long_empty_ext",
                        rel=f"allowed/{name}", exists=True, ext_class="shared")
    if kind == "blocked":
        return FuzzCase(case_id=f"lenx-{i:04d}", domain="long_empty_ext",
                        rel=f"allowed/evil{rng.choice(BLOCKED_EXTENSIONS)}",
                        exists=False, ext_class="blocked")
    return FuzzCase(case_id=f"lenx-{i:04d}", domain="long_empty_ext",
                    rel=f"allowed/noext_{i}", exists=True, ext_class="none")


def _gen_structural(rng: random.Random, i: int) -> FuzzCase:
    roll = rng.random()
    # 差异预算：design 扩展 ~4%，fine-missing ~1%；其余都是可比 case。
    if roll < 0.04:
        ext = rng.choice(DESIGN_EXTENSIONS)
        return FuzzCase(
            case_id=f"strc-{i:04d}", domain="structural",
            rel=f"allowed/design_{i}{ext}", exists=True, ext_class="design",
        )
    if roll < 0.05:
        return FuzzCase(
            case_id=f"strc-{i:04d}", domain="structural",
            rel=f"allowed/ghost_{i}{_shared_ext(rng)}",
            exists=False, ext_class="shared",
        )
    exists = roll < 0.65
    ext = rng.choice([_shared_ext(rng), _shared_ext(rng), "", rng.choice(BLOCKED_EXTENSIONS)])
    ext_class = "blocked" if ext in BLOCKED_EXTENSIONS else ("none" if ext == "" else "shared")
    return FuzzCase(
        case_id=f"strc-{i:04d}", domain="structural",
        rel=f"allowed/ok_{i}{ext}", exists=exists, ext_class=ext_class,
    )


_GENERATORS = {
    "traversal": _gen_traversal,
    "symlink": _gen_symlink,
    "system_dirs": _gen_system_dirs,
    "separator_mix": _gen_separator_mix,
    "allowlist_str": _gen_allowlist_str,
    "case_trailing": _gen_case_trailing,
    "long_empty_ext": _gen_long_empty_ext,
    "structural": _gen_structural,
}

#: 各域占比（和为 CASE_COUNT）。structural 最多（基线语义），穿越/分隔符次之。
DOMAIN_WEIGHTS: dict[str, int] = {
    "structural": 760,
    "traversal": 400,
    "separator_mix": 300,
    "system_dirs": 240,
    "case_trailing": 240,
    "long_empty_ext": 240,
    "symlink": 120,
    "allowlist_str": 100,
}


def generate_cases(seed: int = SEED, count: int | None = None) -> list[FuzzCase]:
    """按固定种子生成 case 序列（纯函数：同种子 ⇒ 同序列）。

    Args:
        seed: 随机种子，默认 :data:`SEED`。
        count: 覆盖总量；默认按 :data:`CASE_COUNT` 与域权重分配。

    Returns:
        逐域生成的 case 列表（顺序稳定）。
    """
    total = count if count is not None else sum(DOMAIN_WEIGHTS.values())
    rng = random.Random(seed)
    cases: list[FuzzCase] = []
    i = 0
    for domain, weight in DOMAIN_WEIGHTS.items():
        gen = _GENERATORS[domain]
        for _ in range(weight):
            cases.append(gen(rng, i))
            i += 1
    # 若调用方给了更大的 count，按 structural 继续补齐（占比语义不变）。
    while len(cases) < total:
        cases.append(_GENERATORS["structural"](rng, i))
        i += 1
    return cases[:total]
