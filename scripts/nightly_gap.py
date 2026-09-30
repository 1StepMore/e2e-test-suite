#!/usr/bin/env python3
"""nightly_gap.py — 不眠计划 · Omni Suite 差距计算器（L2-a）

把「当前产出 vs 完成定义（DoD）」算成机器可读矩阵。
**冻结区**：coding agent 只跑、不改。

DoD：**195 个格子 × 2 条通道（CLI / MCP）= 390 次格子运行**全部通过。
- 195 = md 路径 11 输入 × 15 输出（165）+ xliff 路径 6 × 5（30）
- 两条通道各 195 格：CLI 走 scripts/format_matrix_verifier.py，
  MCP 走 scripts/mcp_matrix_verifier.py（同 195 格，改走 MCP 工具调用）

⚠️ 两条抗作弊规矩（都来自实测，不是推测）：

1. **跳过 ≠ 通过**。验证器对缺外部二进制的格子（pandoc / md2pptx / aspose）
   自动 skip，且 "exits 0 if all non-skipped cells pass" —— 也就是说
   **什么都不装、全靠 skip，也能拿 exit 0**。故本计算器把 skip 单独计数，
   并要求 **skip 数不得超过冻结基线**（新增 skip = 退步，不是进步）。
2. **解释器必须先探活**。验证器按 `suite_root/.venv_ol/bin/python` 选解释器，
   选到缺 `opp`/`orf` 的环境时**不会报环境错**，而是让 195 格逐个 FAIL ——
   实测拿到过 128 fail / 0 pass 的**全假红**矩阵。故本计算器先探活
   （能否 import opp.cli / orf / ol_pool），不通就 exit 2 大声报错，
   **绝不产出假矩阵**。

用法：python3 scripts/nightly_gap.py [--out-dir DIR] [--max-skip N] [--skip-run]
退出码：0 = 两通道 390 格全过且 skip 未超基线 / 1 = 仍有差距 / 2 = 环境或用法错误
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REQUIRED_MODULES = ("opp.cli", "orf", "ol_pool")
DEFAULT_MAX_SKIP = 67  # 冻结基线：2026-09-30 实测（缺 pandoc/md2pptx/aspose 的格子）


def preflight(python: str) -> list[str]:
    """返回缺失模块列表；空 = 环境可用。这是防「全假红」的第一道闸。"""
    missing = []
    for mod in REQUIRED_MODULES:
        r = subprocess.run([python, "-c", f"import {mod}"],  # noqa: S603
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            missing.append(mod)
    return missing


def run_verifier(python: str, script: str, out_dir: Path, timeout: int) -> dict:
    """跑一个通道的验证器，读它自己的 matrix.json（不解析 stdout，借鉴输出格式）。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [python, str(REPO / "scripts" / script), "--out-dir", str(out_dir)]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True,  # noqa: S603
                       cwd=REPO, timeout=timeout)
    data_path = out_dir / "matrix.json"
    payload: dict = {"script": script, "returncode": r.returncode,
                     "duration_s": round(time.time() - t0, 1)}
    if data_path.is_file():
        d = json.loads(data_path.read_text(encoding="utf-8"))
        payload.update({k: d.get(k) for k in
                        ("total", "passed", "skipped", "failed", "duration_s")})
        cells = d.get("cells") or []
        skips: dict[str, int] = {}
        fails: dict[str, int] = {}
        for c in cells:
            if c.get("status") == "skip":
                key = (c.get("detail") or "unknown").strip()[:60]
                skips[key] = skips.get(key, 0) + 1
            elif c.get("status") == "fail":
                key = f"{c.get('inp')}→{c.get('outp')} ({c.get('path')})"
                fails[key] = fails.get(key, 0) + 1
        payload["skip_reasons"] = skips
        payload["failed_cells"] = fails
    else:
        payload["error"] = f"没有产出 matrix.json；stderr={r.stderr[-300:]}"
    return payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nightly_gap.py")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--out-dir", default="/tmp/omni-nightly")
    ap.add_argument("--max-skip", type=int, default=DEFAULT_MAX_SKIP)
    ap.add_argument("--skip-run", action="store_true",
                    help="只跑差异计算，不重跑验证器（用已有 matrix.json）")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--json-out", default="")
    ap.add_argument("--md-out", default="")
    args = ap.parse_args(argv)

    python = shutil.which(args.python) or args.python
    missing = preflight(python)
    if missing:
        msg = (f"解释器不可用：{python}\n"
               f"  缺模块：{', '.join(missing)}\n"
               f"  这条不是差距，是环境问题。验证器在这种环境下会把 195 格逐个\n"
               f"  判成 FAIL（实测 128 fail / 0 pass 的全假红），所以这里直接拦下。\n"
               f"  修法见 SETUP.md：用装了 OPP/OL/ORF 三件套的 .venv_ol 解释器。")
        print(msg, file=sys.stderr)
        return 2

    out_root = Path(args.out_dir)
    channels = {}
    for name, script in (("CLI", "format_matrix_verifier.py"),
                         ("MCP", "mcp_matrix_verifier.py")):
        d = out_root / name.lower()
        if args.skip_run and (d / "matrix.json").is_file():
            payload = {"script": script, "returncode": None, "cached": True}
            raw = json.loads((d / "matrix.json").read_text(encoding="utf-8"))
            payload.update({k: raw.get(k) for k in
                            ("total", "passed", "skipped", "failed", "duration_s")})
        else:
            payload = run_verifier(python, script, d, args.timeout)
        channels[name] = payload

    total = sum(c.get("total") or 0 for c in channels.values())
    passed = sum(c.get("passed") or 0 for c in channels.values())
    failed = sum(c.get("failed") or 0 for c in channels.values())
    skipped = sum(c.get("skipped") or 0 for c in channels.values())
    gap = failed + max(0, skipped - args.max_skip)

    result = {
        "schema": "nightly-gap/1",
        "project": "Omni Suite",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "interpreter": python,
        "total_units": total,
        "passing_units": passed,
        "failed": failed,
        "skipped": skipped,
        "max_skip": args.max_skip,
        "gap_units": gap,
        "channels": channels,
    }

    verdict = ("- 判定：**两通道 390 格全过，skip 未超基线**" if gap == 0
               else f"- 判定：**仍有差距（fail {failed} + 超额 skip "
                    f"{max(0, skipped - args.max_skip)}）**")
    md = ["# Omni Suite 差距矩阵", "", verdict, "",
          f"- 解释器：`{python}`（已探活 {', '.join(REQUIRED_MODULES)}）",
          f"- 合计：**{total}** 格（CLI + MCP）· passed **{passed}** · "
          f"failed **{failed}** · skipped **{skipped}**（基线 ≤{args.max_skip}）"]
    for name, c in channels.items():
        md.append(f"  - {name} 通道：total={c.get('total')} passed={c.get('passed')} "
                  f"failed={c.get('failed')} skipped={c.get('skipped')} "
                  f"rc={c.get('returncode')}")
    md_text = "\n".join(md) + "\n"

    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.md_out:
        Path(args.md_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md_out).write_text(md_text, encoding="utf-8")
    print(md_text)
    return 0 if gap == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"环境/用法错误：{type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(2)
