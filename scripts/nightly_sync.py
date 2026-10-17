#!/usr/bin/env python3
"""nightly_sync.py — 不眠计划 · 开工前同步（L1 总纲 §7）

每晚开工**先同步到最新 main，再算差距**（差距必须基于当下代码）。此前
`nightly_batch.sh` 的 `preflight()` 只探活代理 / ComfyUI / hyperframes / Chrome /
whisper / 磁盘，**没有任何 git fetch / merge 步骤** ⇒ 一晚的差距矩阵测的其实是
「本地 clone 恰好停在哪」。issue #166 的实证：夜跑工作树停在旧判据上，
矩阵报「三轨全达标」，同步 main 后重跑立刻 exit 1。

本脚本只做**同步记账**（不是把关）：对每个仓
`before -> fetch origin main -> merge --ff-only origin/main -> after`，
把结果落成机器可读 JSON，供跑批事后回答「这份矩阵测的是哪个 commit」。

三条硬规矩：
  1) **单仓失败不中断其它仓、不非零退出**——这一步是记账；失败的仓记进 `stale`。
  2) `mode` 语义：
       ff           —— before != after，已快进到 main（同步成功）
       current      —— fetch 成功且 before == after，本就最新
       FETCH_FAILED —— fetch 失败（超时 / 非零 / 仓不可达）
       NO_FF        —— fetch 成功但 `merge --ff-only` 失败（分叉等）
       WRONG_BRANCH —— 工作树停在非 main 分支（`branch != "main"`，含取不到
                       分支名的 null）；必须计入 stale——它根本没停到 main，
                       矩阵测的不是 main 代码。此类只记账、不做 fetch/merge，
                       避免把 origin/main 快进到功能分支上。
  3) `stale` = 未能停到 main 的仓（FETCH_FAILED / NO_FF / WRONG_BRANCH）；
     `ff` 与 `current` 都算同步到位，**不进** stale。

用法：
  python3 scripts/nightly_sync.py --sync-only          # 同步 + 打印 + 落 JSON
  python3 scripts/nightly_sync.py --dirs A B           # 覆盖默认仓列表（测试用）
  python3 scripts/nightly_sync.py --json-out X.json --timeout 60

退出码：恒为 0（除非 argparse 用法错）——「把关」由 `nightly_gap.py` 负责。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

WS = Path("/mnt/d/Hermes-Workspace/01-Projects")
E2E = WS / "e2e-test-suite"

# 需要同步的 6 个仓：前 3 个是被测项目，后 3 个是矩阵经 .venv_ol editable 安装
# import 的兄弟目录（它们各自是独立 git 仓，不在 e2e-test-suite 版本控制内）。
DEFAULT_REPOS: list[str] = [
    str(WS / "AutoInfo"),
    str(WS / "AutoMedia-repo"),
    str(E2E),
    str(E2E / "Omni_Pre_Processor"),
    str(E2E / "Omni_Localizer"),
    str(E2E / "Omni_Re_Formatter"),
]

DEFAULT_JSON_OUT = "test_artifacts/nightly/base.json"

# 同步到位的 mode 集合：不落进 stale。
SYNCED_MODES = ("ff", "current")


def _git(path: str, *args: str, timeout: int) -> tuple[int, str, str]:
    """跑一条 `git -C <path> ...`；返回 (returncode, stdout, stderr)。

    超时返回 (-1, "", ...)，git 不可用返回 (-2, "", ...)——都**不抛异常**，
    保证单仓失败不会打断整轮同步。
    """
    cmd = ["git", "-C", path, *args]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", f"timeout after {timeout}s"
    except OSError as exc:  # git 不在 PATH 等
        return -2, "", str(exc)


def _rev(path: str, timeout: int) -> str | None:
    """取 `<path>` 当前 HEAD 的完整 SHA；失败返回 None。"""
    code, out, _ = _git(path, "rev-parse", "HEAD", timeout=timeout)
    return out if code == 0 and out else None


def _branch(path: str, timeout: int) -> str | None:
    """取 `<path>` 当前分支名（`git rev-parse --abbrev-ref HEAD`）；失败返回 None。

    detached HEAD 会返回 "HEAD"，同样应视为非 main（计 WRONG_BRANCH）。
    """
    code, out, _ = _git(path, "rev-parse", "--abbrev-ref", "HEAD", timeout=timeout)
    return out if code == 0 and out else None


def sync_repo(path: str, timeout: int) -> dict[str, str | None]:
    """同步单个仓：fetch origin main → merge --ff-only origin/main。

    返回 `{name, path, branch, before, after, mode}`；任何一步失败都落到对应
    mode，不抛异常、不产生非零退出。

    工作树不在 main 时（`branch != "main"`，含取不到分支名的 null）只记账为
    `WRONG_BRANCH`，不做 fetch/merge——否则 `merge --ff-only origin/main` 会把
    origin/main 快进到功能分支上，矩阵也就测错了树。
    """
    name = os.path.basename(path.rstrip("/")) or path
    branch = _branch(path, timeout)
    before = _rev(path, timeout)

    if branch != "main":
        shown = branch if branch is not None else "<unknown>"
        print(
            f"[sync] {name}: 未同步 (mode=WRONG_BRANCH): 工作树停在 {shown}，"
            f"非 main；已跳过 fetch/merge",
            file=sys.stderr,
        )
        return {
            "name": name,
            "path": path,
            "branch": branch,
            "before": before,
            "after": before,
            "mode": "WRONG_BRANCH",
        }

    fetch_code, _, fetch_err = _git(path, "fetch", "origin", "main", timeout=timeout)
    fetch_ok = fetch_code == 0

    merge_ok = False
    merge_err = ""  # 提前定值：任何路径（含 after 读不到 HEAD）都不会未定义引用
    if fetch_ok:
        merge_code, _, merge_err = _git(
            path, "merge", "--ff-only", "origin/main", timeout=timeout
        )
        merge_ok = merge_code == 0
    else:
        merge_err = fetch_err

    after = _rev(path, timeout)

    if not fetch_ok:
        mode = "FETCH_FAILED"
    elif after is None:
        mode = "FETCH_FAILED"  # fetch 成功却读不到 HEAD，按取数失败记账
    elif before != after:
        mode = "ff"
    elif merge_ok:
        mode = "current"
    else:
        mode = "NO_FF"

    if mode not in SYNCED_MODES:
        print(f"[sync] {name}: 未同步 (mode={mode}): {merge_err}", file=sys.stderr)

    return {
        "name": name,
        "path": path,
        "branch": branch,
        "before": before,
        "after": after,
        "mode": mode,
    }


def build_report(repos: list[str], timeout: int) -> dict:
    """对每个仓跑同步，汇总成 base.json 的形状。"""
    results = [sync_repo(p, timeout) for p in repos]
    stale = [r["name"] for r in results if r["mode"] not in SYNCED_MODES]
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "repos": results,
        "stale": stale,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="开工前把每个被测仓同步到最新 main（L1 总纲 §7）。"
    )
    parser.add_argument(
        "--dirs",
        nargs="+",
        default=None,
        metavar="DIR",
        help="覆盖默认仓列表（测试用；默认 6 个仓见 DEFAULT_REPOS）",
    )
    parser.add_argument(
        "--json-out",
        default=DEFAULT_JSON_OUT,
        help=f"记账 JSON 落盘路径（默认 {DEFAULT_JSON_OUT}）",
    )
    parser.add_argument(
        "--sync-only",
        action="store_true",
        help="只同步、打印、落 JSON 然后退出 0（本脚本本就只做同步，"
        "该开关用于把「同步这一步」单独重跑/验收）",
    )
    parser.add_argument(
        "--timeout", type=int, default=120, help="单条 git 命令超时秒数（默认 120）"
    )
    args = parser.parse_args(argv)

    repos = args.dirs if args.dirs else DEFAULT_REPOS
    report = build_report(repos, args.timeout)

    for r in report["repos"]:
        before = r["before"] if r["before"] is not None else "<unknown>"
        after = r["after"] if r["after"] is not None else "<unknown>"
        print(
            f"[sync] {r['name']}: {before} -> {after} ({r['mode']}) "
            f"branch={r['branch']}"
        )

    out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    return 0  # 「记账」不是「把关」：恒 0，把关交给 nightly_gap.py


if __name__ == "__main__":
    raise SystemExit(main())
