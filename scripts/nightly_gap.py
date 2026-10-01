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
   **什么都不装、全靠 skip，也能拿 exit 0**。故 skip 单独计数，并拆成两半：
   **需清理的 skip**（环境/能力类，装上二进制或补能力才算真进展）进 `gap_units`
   —— 它是 DoD 的差距本体；**豁免的 skip**（因夹具内容缺失而必然跳过，
   `EXEMPT_SKIP_REASONS`）是夹具内容依赖、非能力缺陷，**不计入 `gap_units`**，
   要清掉它们需要补语料。豁免项**仍原样出现在通道 skipped 总数里**，不静默吞掉。
   另设**回归护栏** `regression_gap`（每通道 skip 不得超过 `--max-skip`），
   专门抓「跳过数变多」的退步。
2. **解释器必须先探活**。验证器按 `suite_root/.venv_ol/bin/python` 选解释器，
   选到缺 `opp`/`orf`/`ol_cli` 的环境时**不会报环境错**，而是让 195 格逐个 FAIL ——
   实测拿到过 128 fail / 0 pass 的**全假红**矩阵。故先探活，不通即 exit 2。
3. **拿不到数据 ≠ 通过**。第一版脚本在这里犯过错：验证器没落 `matrix.json` 时
   `total/passed/failed/skipped` 全是 0，两个口径都算出 0
   （`gap_units = 0 + 0`、`regression_gap = 0 + 0`）
   于是**报了「390 格全过」的假绿**。现在：任一通道拿不到矩阵、或总数不等于
   预期 390，一律 **exit 2**，绝不判绿。

   （配套：CLI 验证器**只有传 `--json` 才写 `matrix.json`**，不传只写 `matrix.md`；
   MCP 验证器无条件写 json 但不认 `--parallel`。两者的开关差异按能力探测。）

用法：python3 scripts/nightly_gap.py [--out-dir DIR] [--subset S] [--corpus minimal|real]
                                      [--fidelity] [--max-skip N] [--parallel N] [--skip-run]
两个口径，**别混用**（混用会重演「跳过就等于达标」的假绿）：

1. **DoD 口径（判定与退出码只用它）**
   `gap_units = fail 合计 + Σ_通道 (skipped_通道 − exempt_通道)`
   ——「还需清理的跳过格子数」，夹具内容依赖的豁免项不算差距。
   `gap_units == 0` → exit 0；否则 exit 1。
2. **回归护栏（只抓退步，不参与判定）**
   `regression_gap = fail 合计 + Σ_通道 max(0, skipped_通道 − --max-skip)`
   —— **每通道**基线（默认 67/通道），两条通道各自比、不相加。
   护栏 0 **≠ 达标**：把 `--max-skip` 调宽只会洗掉退步告警，
   洗不掉 DoD 差距（exit 仍由 `gap_units` 定）。

退出码：0 = gap_units 归零 / 1 = 仍有差距（fail 或需清理的 skip > 0）/ 2 = 环境、用法或取数错误
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
DEFAULT_MAX_SKIP = 67         # 冻结基线（**每通道**口径，2026-10-01 裁定）：2026-09-30 实测
EXEMPT_SKIP_REASONS = (
    # 因**夹具内容缺失**而必然跳过的理由子串（豁免 = 夹具内容依赖，非能力缺陷；
    # 要清掉它们需要补语料，见 docs/NIGHTLY.md）。
    # ⚠️ 只收内容依赖类：pandoc / nbformat / xliff 之类环境或能力类跳过**不在此列**，
    # 仍属「需清理的 skip」。
    "MD→SRT requires timestamped cues",
    "MD→JSON requires JSON code block",
    "XLSX→PPTX: no slide content",
    "PPTX→XLSX: no table content",
)


def is_exempt(reason: str) -> bool:
    """跳过理由是否属于「夹具内容缺失」类 → 计入 exempt_skips，与「需清理的 skip」分开看。"""
    return any(pat in reason for pat in EXEMPT_SKIP_REASONS)


def tally_cells(cells: list) -> tuple[dict, dict, dict]:
    """统计一个通道的 matrix.json cells → (skip 理由计数, fail 格子, 豁免理由计数)。

    豁免判定用**完整**理由文本（不截断），避免 60 字符截断吞掉子串。
    """
    skips: dict[str, int] = {}
    fails: dict[str, int] = {}
    exempt: dict[str, int] = {}
    for c in cells:
        if c.get("status") == "skip":
            reason = (c.get("skip_reason") or c.get("detail") or "unknown").strip()
            key = reason[:60]
            skips[key] = skips.get(key, 0) + 1
            if is_exempt(reason):
                exempt[key] = exempt.get(key, 0) + 1
        elif c.get("status") == "fail":
            key = f"{c.get('inp')}→{c.get('outp')} ({c.get('path')})"
            fails[key] = fails.get(key, 0) + 1
    return skips, fails, exempt


def supported_flags(script: str) -> dict:
    """验证器支持哪些透传参数（**能力探测**，不硬编码——MCP 验证器暂不认 --fidelity）。"""
    src = (REPO / "scripts" / script).read_text(encoding="utf-8")
    return {f: f"--{f}" in src for f in ("subset", "corpus", "fidelity")}


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
                 parallel: int = 1, run_opts: dict | None = None) -> dict:
    """跑一个通道的验证器，读它自己落的 matrix.json。

    开关按**能力探测**传，不硬编码：
    - `--parallel`：MCP 验证器不认，硬传会直接报错退出
    - `--json`：CLI 验证器只有传它才写 matrix.json（不传只写 matrix.md）
    - `--subset` / `--corpus` / `--fidelity`：口径透传，同样按验证器是否认该参数决定
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    script_path = REPO / "scripts" / script
    src = script_path.read_text(encoding="utf-8")
    opts = run_opts or {}
    cmd = [python, str(script_path), "--out-dir", str(out_dir)]
    if parallel > 1 and "--parallel" in src:
        cmd += ["--parallel", str(parallel)]
    if "--json" in src:
        cmd += ["--json"]
    applied: dict = {}
    if opts.get("subset") and "--subset" in src:
        cmd += ["--subset", opts["subset"]]
        applied["subset"] = opts["subset"]
    if opts.get("corpus") and "--corpus" in src:
        cmd += ["--corpus", opts["corpus"]]
        applied["corpus"] = opts["corpus"]
    if opts.get("fidelity") and "--fidelity" in src:
        cmd += ["--fidelity"]
        applied["fidelity"] = True

    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True,  # noqa: S603
                       cwd=REPO, timeout=timeout)
    payload: dict = {"script": script, "returncode": r.returncode,
                     "duration_s": round(time.time() - t0, 1),
                     "options_applied": applied,
                     "options_supported": supported_flags(script)}

    data_path = out_dir / "matrix.json"
    if data_path.is_file():
        d = json.loads(data_path.read_text(encoding="utf-8"))
        payload.update({k: d.get(k) for k in
                        ("total", "passed", "skipped", "failed", "duration_s")})
        skips, fails, exempt = tally_cells(d.get("cells") or [])
        payload["skip_reasons"] = skips
        payload["failed_cells"] = fails
        payload["exempt_skip_reasons"] = exempt
    else:
        payload["error"] = (f"没有产出 matrix.json；rc={r.returncode}；"
                            f"stderr={r.stderr.strip()[-400:]}")
    return payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nightly_gap.py")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--out-dir", default="/tmp/omni-nightly")
    ap.add_argument("--max-skip", type=int, default=DEFAULT_MAX_SKIP,
                    help=f"**回归护栏**的每通道跳过基线（默认 {DEFAULT_MAX_SKIP}）："
                         "每通道 max(0, skipped − 本值) 计入 regression_gap，"
                         "两通道各自比、不相加。**它不决定判定与退出码**"
                         "（判定只看 gap_units）；调宽它不会让差距消失")
    ap.add_argument("--expect-total", type=int, default=EXPECTED_TOTAL,
                    help="预期格子总数（矩阵形状变了就要人来确认，不是自动放行）")
    ap.add_argument("--subset", default="",
                    help="透传给两个验证器：只跑指定输入子集（逗号分隔，如 docx,md）；"
                         "空 = 全量（子集跑要同时调 --expect-total）")
    ap.add_argument("--corpus", choices=["minimal", "real"], default="minimal",
                    help="透传给两个验证器：矩阵夹具口径（默认 minimal = 最小夹具，"
                         "real = test_corpus/ 真实夹具）")
    ap.add_argument("--fidelity", action="store_true",
                    help="透传给两个验证器：通过的格子再算内容保真度分数"
                         "（验证器不认该参数时按能力探测跳过，不报错）")
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
    run_opts = {"subset": args.subset, "corpus": args.corpus, "fidelity": args.fidelity}
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
            payload: dict = {"script": script, "returncode": None, "cached": True,
                             "options_supported": supported_flags(script)}
            payload.update({k: raw.get(k) for k in
                            ("total", "passed", "skipped", "failed", "duration_s")})
            skips, fails, exempt = tally_cells(raw.get("cells") or [])
            payload["skip_reasons"] = skips
            payload["failed_cells"] = fails
            payload["exempt_skip_reasons"] = exempt
            channels[name] = payload
        else:
            channels[name] = run_verifier(python, script, d, args.timeout,
                                          args.parallel, run_opts)

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
        hint = ("\n  注意：--subset 子集跑的总格数会变小，需人同时给 --expect-total。"
                if args.subset else "")
        print(f"矩阵形状变了：实测 {total} 格，预期 {args.expect_total} 格。\n"
              f"  这可能是**真变化**（矩阵扩展/收缩），也可能是取数出了问题。\n"
              f"  不自动放行，需人确认后调整 --expect-total。{hint}", file=sys.stderr)
        return 2

    # —— 两个口径，物理分开 ——
    # 1) DoD 口径（判定与退出码用它）：gap = fail 合计 + Σ_通道 (skipped − exempt)
    #    即「还需清理的跳过格子数」——夹具内容依赖的豁免项不算能力差距。
    # 2) 回归护栏（只抓退步）：gap = fail 合计 + Σ_通道 max(0, skipped − max_skip)
    #    （老口径把两条通道的 skip 相加后比一次，134 恒超 67，永远收敛不到 0。）
    #
    # ⚠️ 两者不能互相顶替：护栏判 0 只说明「跳过没变多」，不说明「没有差距」。
    #    反过来，DoD 口径也不该被护栏替代——否则 44 个需清理的 skip 会被
    #    `--max-skip 200` 洗成 exit 0，又回到「跳过就等于达标」的老毛病。
    needs_cleanup: dict[str, int] = {}
    excess: dict[str, int] = {}
    exempt_reasons: dict[str, dict] = {}
    exempt_skips: dict[str, int] = {}
    per_channel: dict[str, dict] = {}
    for name, c in channels.items():
        ch_failed = c.get("failed") or 0
        ch_skipped = c.get("skipped") or 0
        exempt_reasons[name] = c.get("exempt_skip_reasons") or {}
        ch_exempt = sum(exempt_reasons[name].values())
        exempt_skips[name] = ch_exempt
        ch_needs = max(0, ch_skipped - ch_exempt)
        needs_cleanup[name] = ch_needs
        excess[name] = max(0, ch_skipped - args.max_skip)
        per_channel[name] = {
            "total": c.get("total") or 0,
            "passed": c.get("passed") or 0,
            "skipped": ch_skipped,
            "failed": ch_failed,
            "exempt": ch_exempt,
            "needs_cleanup": ch_needs,
            "regression_excess": excess[name],
        }
    needs_cleanup_total = sum(needs_cleanup.values())
    excess_total = sum(excess.values())
    gap_units = failed + needs_cleanup_total            # DoD 口径：判定与退出码
    regression_gap = failed + excess_total              # 回归护栏：只抓退步

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
        "baseline_mode": "per_channel",
        # —— 判定口径：DoD（还需清理的跳过 + fail）。exit 由它决定 ——
        "gap_units": gap_units,
        "gap_mode": "needs_cleanup_plus_failed",
        # —— 回归护栏：跳过数有没有变多（每通道比 --max-skip）。**不参与判定** ——
        "regression_gap": regression_gap,
        "regression_mode": "per_channel_max_skip",
        "needs_cleanup_total": needs_cleanup_total,
        "per_channel": per_channel,
        "exempt_skips": exempt_skips,
        "exempt_skip_reasons": exempt_reasons,
        "run_options": {"subset": args.subset, "corpus": args.corpus,
                        "fidelity": args.fidelity},
        "channels": channels,
    }

    # —— 护栏与判定是两个数，判定行必须同时给出，避免「护栏 0 = 达标」的误读 ——
    if regression_gap > 0:
        guard = (f"回归护栏 {regression_gap} > 基线 {args.max_skip}/通道："
                 f"跳过数变多 = 退步")
    else:
        guard = f"回归护栏 {regression_gap} ≤ 基线 {args.max_skip}/通道"
    split = " · ".join(f"{n} {needs_cleanup[n]} = 总 skip "
                       f"{per_channel[n]['skipped']} − 豁免 "
                       f"{per_channel[n]['exempt']}" for n in channels)
    if gap_units > 0:
        verdict = (f"- 判定：**仍有差距（fail {failed} + 需清理 skip "
                   f"{needs_cleanup_total}）**（{split}；{guard} → "
                   f"gap_units {gap_units}，exit 1）")
    elif skipped:
        verdict = (f"- 判定：**仍有差距（fail {failed} + 需清理 skip "
                   f"{needs_cleanup_total}）**（{split}；{guard} → "
                   f"gap_units {gap_units}，exit 1；剩下的 skip 全是豁免项，"
                   f"不算能力差距，但要清掉它们需要补语料）")
    else:
        verdict = (f"- 判定：**两通道 {total} 格全过，无 fail、无需清理的 skip**"
                   f"（{guard} → gap_units {gap_units}，exit 0）")
    md = ["# Omni Suite 差距矩阵", "", verdict, "",
          "- 判定口径（DoD，决定 exit）：`gap_units` = fail 合计 + "
          f"Σ_通道 (skipped − exempt) = {failed} + {needs_cleanup_total} = "
          f"**{gap_units}**（= 还需清理的跳过格子数，**豁免项不算差距**）",
          f"- 回归护栏（只抓退步，**不决定判定**）：`regression_gap` = fail 合计 + "
          f"Σ_通道 max(0, skipped − {args.max_skip}) = {failed} + {excess_total} = "
          f"**{regression_gap}**（基线 {args.max_skip}/通道；**护栏通过 ≠ 达标**，"
          "调宽 `--max-skip` 不会让差距消失）",
          f"- 解释器：`{python}`（已探活 {', '.join(REQUIRED_MODULES)}）",
          f"- 合计：**{total}** 格（CLI + MCP）· passed **{passed}** · "
          f"failed **{failed}** · skipped **{skipped}**"
          f"（豁免 {sum(exempt_skips.values())} + 需清理 {needs_cleanup_total}）",
          "- 运行口径（run_options）："
          f"subset={args.subset or '（空=全量）'} · corpus={args.corpus} · "
          f"fidelity={'开' if args.fidelity else '关'}",
          "- per_channel（判定数 needs_cleanup / 护栏数 regression_excess）："
          + " · ".join(
              f"{n} total={per_channel[n]['total']} "
              f"passed={per_channel[n]['passed']} "
              f"skipped={per_channel[n]['skipped']} "
              f"failed={per_channel[n]['failed']} "
              f"exempt={per_channel[n]['exempt']} "
              f"needs_cleanup={per_channel[n]['needs_cleanup']} "
              f"regression_excess={per_channel[n]['regression_excess']}"
              for n in channels)]
    for name, c in channels.items():
        pc = per_channel[name]
        md.append(f"  - {name} 通道：total={c.get('total')} passed={c.get('passed')} "
                  f"failed={c.get('failed')} skipped={pc['skipped']} "
                  f"rc={c.get('returncode')}")
        md.append(f"    - DoD 口径：skip {pc['skipped']} − 豁免 {pc['exempt']} = "
                  f"**需清理 {pc['needs_cleanup']}**"
                  + (f" + fail {pc['failed']} → 本通道 gap_units "
                     f"{pc['needs_cleanup'] + pc['failed']}"
                     if pc["failed"] else "（fail 0）"))
        md.append(f"    - 回归护栏：skip {pc['skipped']} vs 基线 {args.max_skip} → "
                  f"超额 {pc['regression_excess']}")
        md.append(f"    - skip 拆分：豁免 {pc['exempt']}（夹具内容依赖）+ "
                  f"需清理 {pc['needs_cleanup']}")
    md.append("")
    md.append(f"- 豁免 skip（exempt_skips）：CLI {exempt_skips.get('CLI', 0)} · "
              f"MCP {exempt_skips.get('MCP', 0)}"
              " —— **豁免 = 夹具内容依赖，非能力缺陷；"
              "要清掉它们需要补语料（见 docs/NIGHTLY.md）**")
    md.append("  - **豁免项不计入 `gap_units`，但仍原样出现在 skipped 总数里**"
              "（不静默吞掉）；单列只为与「需清理的 skip」分开；pandoc / nbformat / "
              "xliff 之类环境或能力类跳过**不豁免**，照常计入 `gap_units`。")
    for name in channels:
        er = exempt_reasons.get(name) or {}
        if er:
            detail = "、".join(f"{k} ×{v}" for k, v in
                              sorted(er.items(), key=lambda kv: -kv[1]))
            md.append(f"  - {name} 豁免明细：{detail}")
    for name, c in channels.items():
        sup = c.get("options_supported") or {}
        for opt in ("subset", "corpus", "fidelity"):
            if run_opts.get(opt) and not sup.get(opt, True):
                md.append(f"- ⚠️ `{name}` 通道的验证器不支持 `--{opt}`，"
                          "本次未透传（该通道矩阵不含此口径）")
    if args.skip_run and (args.subset or args.fidelity
                          or args.corpus != "minimal"):
        md.append("- ⚠️ `--skip-run`：run_options 只记录请求值，缓存矩阵"
                  "没有按新口径重跑（要真透传就去掉 --skip-run）")
    md_text = "\n".join(md) + "\n"

    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.md_out:
        Path(args.md_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md_out).write_text(md_text, encoding="utf-8")
    print(md_text)
    return 0 if gap_units == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"环境/用法错误：{type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(2)
