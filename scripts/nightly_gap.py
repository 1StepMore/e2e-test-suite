#!/usr/bin/env python3
"""nightly_gap.py — 不眠计划 · Omni Suite 差距计算器（L2-a）

把「当前产出 vs 完成定义（DoD）」算成机器可读矩阵。
**冻结区**：coding agent 只跑、不改。

DoD：**195 个格子 × 2 条通道（CLI / MCP）= 390 次格子运行**全部通过。
- 195 = md 路径 11 输入 × 15 输出（165）+ xliff 路径 6 × 5（30）
- 两条通道各 195 格：CLI 走 scripts/format_matrix_verifier.py，
  MCP 走 scripts/mcp_matrix_verifier.py（同 195 格，改走 MCP 工具调用）

⚠️ 三条抗作弊规矩（都来自实测，不是推测）：

1. **跳过 ≠ 通过**。验证器对缺外部二进制的格子（pandoc / md2pptx / aspose）
   自动 skip，且 "exits 0 if all non-skipped cells pass" —— 也就是说
   **什么都不装、全靠 skip，也能拿 exit 0**。故 skip 单独计数，
   并要求 **skip 数不得超过冻结基线**（新增 skip = 退步，不是进步）。
2. **解释器必须先探活**。验证器按 `suite_root/.venv_ol/bin/python` 选解释器，
   选到缺 `opp`/`orf`/`ol_cli` 的环境时**不会报环境错**，而是让 195 格逐个 FAIL ——
   实测拿到过 128 fail / 0 pass 的**全假红**矩阵。故先探活，不通即 exit 2。
3. **拿不到数据 ≠ 通过**。第一版脚本在这里犯过错：验证器没落 `matrix.json` 时
   `total/passed/failed/skipped` 全是 0，而 `gap = failed + 超额skip = 0`
   于是**报了「390 格全过」的假绿**。现在：任一通道拿不到矩阵、或总数不等于
   预期 390，一律 **exit 2**，绝不判绿。

   （配套：CLI 验证器**只有传 `--json` 才写 `matrix.json`**，不传只写 `matrix.md`；
   MCP 验证器无条件写 json 但不认 `--parallel`。两者的开关差异按能力探测。）

用法：python3 scripts/nightly_gap.py [--out-dir DIR] [--parallel N] [--skip-run]
退出码：0 = 两通道 390 格全过且 skip 未超基线 / 1 = 仍有差距 / 2 = 环境、用法或取数错误
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
EXPECTED_TOTAL = 390          # 195 格 × 2 通道
DEFAULT_MAX_SKIP = 67         # 冻结基线：2026-09-30 实测（缺 pandoc/md2pptx/aspose 的格子）


def preflight(python: str) -> list[str]:
    """返回缺失模块列表；空 = 环境可用。这是防「全假红」的第一道闸。"""
    missing = []
    for mod in REQUIRED_MODULES:
        r = subprocess.run([python, "-c", f"import {mod}"],  # noqa: S603
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            missing.append(mod)
    return missing


def run_verifier(python: str, script: str, out_dir: Path, timeout: int,
                 parallel: int = 1) -> dict:
    """跑一个通道的验证器，读它自己落的 matrix.json。

    开关按**能力探测**传，不硬编码：
    - `--parallel`：MCP 验证器不认，硬传会直接报错退出
    - `--json`：CLI 验证器只有传它才写 matrix.json（不传只写 matrix.md）
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    script_path = REPO / "scripts" / script
    src = script_path.read_text(encoding="utf-8")
    cmd = [python, str(script_path), "--out-dir", str(out_dir)]
    if parallel > 1 and "--parallel" in src:
        cmd += ["--parallel", str(parallel)]
    if "--json" in src:
        cmd += ["--json"]

    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True,  # noqa: S603
                       cwd=REPO, timeout=timeout)
    payload: dict = {"script": script, "returncode": r.returncode,
                     "duration_s": round(time.time() - t0, 1)}

    data_path = out_dir / "matrix.json"
    if data_path.is_file():
        d = json.loads(data_path.read_text(encoding="utf-8"))
        payload.update({k: d.get(k) for k in
                        ("total", "passed", "skipped", "failed", "duration_s")})
        cells = d.get("cells") or []
        skips: dict[str, int] = {}
        fails: dict[str, int] = {}
        for c in cells:
            if c.get("status") == "skip":
                key = (c.get("skip_reason") or c.get("detail") or "unknown").strip()[:60]
                skips[key] = skips.get(key, 0) + 1
            elif c.get("status") == "fail":
                key = f"{c.get('inp')}→{c.get('outp')} ({c.get('path')})"
                fails[key] = fails.get(key, 0) + 1
        payload["skip_reasons"] = skips
        payload["failed_cells"] = fails
    else:
        payload["error"] = (f"没有产出 matrix.json；rc={r.returncode}；"
                            f"stderr={r.stderr.strip()[-400:]}")
    return payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nightly_gap.py")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--out-dir", default="/tmp/omni-nightly")
    ap.add_argument("--max-skip", type=int, default=DEFAULT_MAX_SKIP)
    ap.add_argument("--expect-total", type=int, default=EXPECTED_TOTAL,
                    help="预期格子总数（矩阵形状变了就要人来确认，不是自动放行）")
    ap.add_argument("--skip-run", action="store_true",
                    help="只算差异，不重跑验证器（读已有 matrix.json）")
    ap.add_argument("--timeout", type=int, default=7200)
    ap.add_argument("--parallel", type=int, default=1,
                    help="验证器内部并发（默认 1=顺序，判据更稳；夜间可加大提速）")
    ap.add_argument("--json-out", default="")
    ap.add_argument("--md-out", default="")
    args = ap.parse_args(argv)

    python = shutil.which(args.python) or args.python
    missing = preflight(python)
    if missing:
        print(f"解释器不可用：{python}\n"
              f"  缺模块：{', '.join(missing)}\n"
              f"  这条不是差距，是环境问题。验证器在这种环境下会把 195 格逐个\n"
              f"  判成 FAIL（实测 128 fail / 0 pass 的全假红），所以这里直接拦下。\n"
              f"  修法见 SETUP.md：用装了 OPP/OL/ORF 三件套的 .venv_ol 解释器。",
              file=sys.stderr)
        return 2

    out_root = Path(args.out_dir)
    channels: dict[str, dict] = {}
    for name, script in (("CLI", "format_matrix_verifier.py"),
                         ("MCP", "mcp_matrix_verifier.py")):
        d = out_root / name.lower()
        if args.skip_run:
            data_path = d / "matrix.json"
            if not data_path.is_file():
                channels[name] = {"script": script, "error": f"缺 {data_path}"}
                continue
            raw = json.loads(data_path.read_text(encoding="utf-8"))
            payload: dict = {"script": script, "returncode": None, "cached": True}
            payload.update({k: raw.get(k) for k in
                            ("total", "passed", "skipped", "failed", "duration_s")})
            channels[name] = payload
        else:
            channels[name] = run_verifier(python, script, d, args.timeout, args.parallel)

    # —— 抗作弊 3：拿不到数据不许判绿 ——
    no_data = [n for n, c in channels.items() if not (c.get("total") or 0)]
    if no_data:
        lines = [f"取数失败：{', '.join(no_data)} 通道没有可用矩阵。",
                 "  「拿不到数据」不等于「通过」——按环境/取数错误处理，不判绿。"]
        for n in no_data:
            if channels[n].get("error"):
                lines.append(f"  {n}: {channels[n]['error']}")
        print("\n".join(lines), file=sys.stderr)
        return 2

    total = sum(c.get("total") or 0 for c in channels.values())
    passed = sum(c.get("passed") or 0 for c in channels.values())
    failed = sum(c.get("failed") or 0 for c in channels.values())
    skipped = sum(c.get("skipped") or 0 for c in channels.values())

    if total != args.expect_total:
        print(f"矩阵形状变了：实测 {total} 格，预期 {args.expect_total} 格。\n"
              f"  这可能是**真变化**（矩阵扩展/收缩），也可能是取数出了问题。\n"
              f"  不自动放行，需人确认后调整 --expect-total。", file=sys.stderr)
        return 2

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
