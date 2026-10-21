#!/usr/bin/env bash
# 不眠计划 · 夜跑跑批（systemd oneshot 入口）
#
# 为什么是这个形态（2026-10-12 事故教训）：
#   跑批进程原来是**网关的子孙进程** ⇒ 网关一重启就被 tree-kill（180s drain 只够它跑 3 分钟），
#   而整批要 85–115 分钟 ⇒ 三份 gap.json 零产出、执行被记成 unknown（不报警）。
#   本脚本由 systemd user unit 拉起 ⇒ 跑批在**自己的 cgroup** 里，与任何 gateway 无关。
#
# 三条硬规矩（写死在实现里）：
#   1) 顺序 **AutoInfo（collect → process → gap）→ AutoMedia → Omni**（快产优先：慢的一挂不至于饿死快的）
#   2) **逐通道落账**：每步完成即更新 state.json（中断也能查「跑到哪」）
#   3) 产物与断点缓存落**仓内持久目录**（test_artifacts/、nightly/ 都是 gitignored），不用 /tmp
#
# 用法：
#   nightly_batch.sh                                   # 全量三项目（timer 的正常入口）
#   nightly_batch.sh --only ai                         # 只跑一个（验收小样本；ai|am|omni）
#   nightly_batch.sh --only ai --collect-limit 2       # 前置采集每源条数上限（默认 20）
#   nightly_batch.sh --only ai --process-min-backlog 10 # 处理积压阈值（默认 20）
#   nightly_batch.sh --only omni --omni-subset docx,md --omni-expect-total 40
# 参数：
#   --only ai|am|omni        只跑一个项目（默认全量）
#   --collect-limit N        ai 采集步骤每源上限（默认 20；只在 ai 步骤生效）
#   --process-min-backlog N  ai 处理步骤的缓存积压阈值（默认 20；只在 ai 步骤生效）
#   --omni-subset ...        omni 输入子集
#   --omni-expect-total N    omni 预期总格数
#   --omni-json-out P        omni gap.json 输出路径
#   --omni-md-out P          omni gap.md 输出路径
set -uo pipefail

H=/home/renanzai
WS=/mnt/d/Hermes-Workspace/01-Projects
E2E="$WS/e2e-test-suite"
NIGHTLY_DIR="$E2E/test_artifacts/nightly"
TS="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="$NIGHTLY_DIR/batch-$TS"
STATE="$NIGHTLY_DIR/state.json"

# systemd 的环境是干净的 ⇒ PATH / OL_CONFIG_PATH / 代理必须显式给
export HOME="$H"
export PATH="$H/.hermes/node/bin:$H/.local/bin:$H/bin:$H/mamba/envs/whisper/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export OL_CONFIG_PATH="$WS/Omni_Localizer/config/local.yaml"
export HTTPS_PROXY="${HTTPS_PROXY:-http://127.0.0.1:7892}"
export HTTP_PROXY="${HTTP_PROXY:-http://127.0.0.1:7892}"
export NO_PROXY="127.0.0.1,localhost,::1"

only=""; omni_subset=""; omni_total=""; collect_limit=20; process_min_backlog=20
while [ $# -gt 0 ]; do
  case "$1" in
    --only) only="${2:-}"; shift 2;;
    --collect-limit) collect_limit="${2:-}"; shift 2;;
    --process-min-backlog) process_min_backlog="${2:-}"; shift 2;;
    --omni-subset) omni_subset="${2:-}"; shift 2;;
    --omni-expect-total) omni_total="${2:-}"; shift 2;;
    --omni-json-out) omni_json="${2:-}"; shift 2;;
    --omni-md-out) omni_md="${2:-}"; shift 2;;
    *) echo "未知参数: $1" >&2; exit 2;;
  esac
done

mkdir -p "$RUN_DIR" "$NIGHTLY_DIR"
LOG="$RUN_DIR/batch.log"
STEP_CODE=0; STEP_DUR=0

# 差距脚本的退出码语义（冻结区口径）：0=达标 / 1=仍有差距（**正常**）/ ≥2=环境或用法错（需人介入）
step_status() {  # $1=exit_code
  case "$1" in
    0) echo ok;;      # 差距归零
    1) echo gap;;     # 仍有差距，正常（不是失败）
    *) echo error;;   # 环境/用法错 → 需人介入
  esac
}

log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*" | tee -a "$LOG"; }
event() { printf '%s\n' "$1" >> "$RUN_DIR/progress.jsonl"; }

state_set() {  # $1=project $2=status $3=exit_code $4=duration_s $5=json_out $6=md_out
  python3 - "$STATE" "$RUN_DIR" "$1" "$2" "$3" "$4" "$5" "$6" <<'PY'
import json, os, sys, time
state, run_dir, proj, status, code, dur, json_out, md_out = sys.argv[1:9]
d = {}
if os.path.exists(state):
    try: d = json.load(open(state, encoding="utf-8"))
    except Exception: d = {}
d["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
d["run_dir"] = run_dir
d["schema"] = "nightly-batch-state/1"
# issue #166：把「这份矩阵测的是哪个 commit」记进顶层 base（形状同 base.json）。
base_path = os.path.join(os.path.dirname(state), "base.json")
if os.path.exists(base_path):
    try: d["base"] = json.load(open(base_path, encoding="utf-8"))
    except Exception: pass
steps = d.setdefault("steps", {})
steps[proj] = {
    "status": status, "exit_code": int(code), "duration_s": round(float(dur), 1),
    "json_out": json_out, "md_out": md_out,
    "json_mtime": (time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(os.path.getmtime(json_out)))
                   if json_out and os.path.exists(json_out) else None),
    "at": d["updated_at"],
}
json.dump(d, open(state, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
PY
}

run_step() {  # $1=proj  $2=cwd  其余=命令；结果写进全局 STEP_CODE / STEP_DUR
  local proj="$1" cwd="$2"; shift 2
  log "== [$proj] 开始（cwd=$cwd）"
  event "{\"at\":\"$(date -Is)\",\"event\":\"step_start\",\"project\":\"$proj\",\"cwd\":\"$cwd\"}"
  local t0 t1
  t0=$(date +%s)
  ( cd "$cwd" && "$@" ) >> "$LOG" 2>&1
  STEP_CODE=$?
  t1=$(date +%s); STEP_DUR=$((t1 - t0))
  log "== [$proj] 结束 exit=$STEP_CODE 用时 ${STEP_DUR}s"
  event "{\"at\":\"$(date -Is)\",\"event\":\"step_done\",\"project\":\"$proj\",\"exit_code\":$STEP_CODE,\"duration_s\":$STEP_DUR}"
}

preflight() {
  log "== 前置探活 =="

  # LLM 代理（项目池第 2/3 顺位走它；首选 AMD 是直连，不依赖它）
  if curl -s -m 5 http://127.0.0.1:8787/ | grep -q "zen_proxy ok"; then
    log "代理 8787: OK"
  else
    log "代理 8787: 未就绪 → 后台拉起"
    setsid python3 "$H/.hermes/profiles/code/scripts/zen_proxy.py" --port 8787 >> "$H/.cache/zen_proxy.log" 2>&1 &
    for _ in $(seq 1 15); do sleep 2; curl -s -m 3 http://127.0.0.1:8787/ | grep -q "zen_proxy ok" && break; done
    if curl -s -m 3 http://127.0.0.1:8787/ | grep -q "zen_proxy ok"; then
      log "代理 8787: 已拉起 OK"
    else
      log "代理 8787: 拉起失败（不致命：项目池首选 AMD 直连可兜，第 2/3 顺位会降级）"
    fi
  fi

  # 图像引擎（AutoMedia 图文轨依赖）
  if curl -s -m 5 http://127.0.0.1:8188/system_stats >/dev/null; then
    log "ComfyUI 8188: OK"
  else
    log "ComfyUI 8188: 未就绪 → restart comfyui"
    systemctl --user restart comfyui >> "$LOG" 2>&1 || log "comfyui restart 返回非零"
    sleep 10
    if curl -s -m 5 http://127.0.0.1:8188/system_stats >/dev/null; then log "ComfyUI 8188: 已恢复"
    else log "ComfyUI 8188: 仍不可用（图文轨可能判红 → 报告里标「需人介入」）"; fi
  fi

  # 视频引擎 / Chrome / whisper（只记证据，不阻断）
  if command -v hyperframes >/dev/null 2>&1; then log "hyperframes: $(hyperframes --version 2>&1 | head -1)"; else log "hyperframes: 不在 PATH"; fi
  if [ -x "$H/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome" ]; then log "Linux Chrome: OK"; else log "Linux Chrome: 未找到"; fi
  if command -v whisper >/dev/null 2>&1; then log "whisper: $(command -v whisper)"; else log "whisper: 不在 PATH"; fi
  log "磁盘: $(df -h /mnt/d 2>/dev/null | tail -1)"

  # L1 总纲 §7：开工先同步到最新 main，再算差距（差距必须基于当下代码）。
  # 记账不是把关：nightly_sync.py 单仓失败不非零退出；即便整体失败也绝不中断跑批。
  # issue #186：默认工作树可能停在前一晚的 drift-audit / fix 分支上，矩阵测的
  # 就不是 main。带 --switch-branch 先切回 main（脏树不切，见 base.json 的 mode）。
  python3 "$E2E/scripts/nightly_sync.py" --switch-branch --json-out "$NIGHTLY_DIR/base.json" >> "$LOG" 2>&1 \
    || log "nightly_sync 返回非零（不致命：矩阵可能测到过期代码，见 base.json）"
}

preflight

if [ -z "$only" ] || [ "$only" = "ai" ]; then
  # issue #172：先产语料再算差距。此前只测差距不采集 ⇒ 补新鲜度判据后必然常红。
  # 采集退出码语义与 gap 不同：非零 = 采集失败（不是「有差距」）⇒ 记 error，
  # 但**不中断整批**，与 nightly_sync.py 的「记账不把关」一致，后面的 ai gap 步骤照跑。
  run_step ai-collect "$WS/AutoInfo" .venv/bin/autoinfo collect --all --limit "$collect_limit"
  if [ "$STEP_CODE" -eq 0 ]; then cst=ok; else cst=error; fi
  state_set ai-collect "$cst" "$STEP_CODE" "$STEP_DUR" "" ""

  run_step ai-process "$WS/AutoInfo" .venv/bin/python scripts/nightly_process.py \
    --min-backlog "$process_min_backlog" \
    --json-out nightly/process.json --md-out nightly/process.md
  if [ "$STEP_CODE" -eq 0 ]; then pst=ok; else pst=error; fi
  state_set ai-process "$pst" "$STEP_CODE" "$STEP_DUR" \
    "$WS/AutoInfo/nightly/process.json" "$WS/AutoInfo/nightly/process.md"

  run_step ai "$WS/AutoInfo" .venv/bin/python scripts/nightly_gap.py \
    --json-out nightly/gap.json --md-out nightly/gap.md
  st=$(step_status "$STEP_CODE")
  state_set ai "$st" "$STEP_CODE" "$STEP_DUR" "$WS/AutoInfo/nightly/gap.json" "$WS/AutoInfo/nightly/gap.md"
fi

if [ -z "$only" ] || [ "$only" = "am" ]; then
  run_step am "$WS/AutoMedia-repo" .venv/bin/python scripts/nightly_gap.py \
    --json-out nightly/gap.json --md-out nightly/gap.md
  st=$(step_status "$STEP_CODE")
  state_set am "$st" "$STEP_CODE" "$STEP_DUR" "$WS/AutoMedia-repo/nightly/gap.json" "$WS/AutoMedia-repo/nightly/gap.md"
fi

if [ -z "$only" ] || [ "$only" = "omni" ]; then
  omni_json="${omni_json:-test_artifacts/nightly/gap.json}"
  omni_md="${omni_md:-test_artifacts/nightly/gap.md}"
  omni_args=(--json-out "$omni_json" --md-out "$omni_md"
             --out-dir test_artifacts/nightly/omni-run)
  [ -n "$omni_subset" ] && omni_args+=(--subset "$omni_subset")
  [ -n "$omni_total" ] && omni_args+=(--expect-total "$omni_total")
  run_step omni "$E2E" .venv_ol/bin/python scripts/nightly_gap.py "${omni_args[@]}"
  st=$(step_status "$STEP_CODE")
  state_set omni "$st" "$STEP_CODE" "$STEP_DUR" \
    "$E2E/$omni_json" "$E2E/$omni_md"
fi

log "== 跑批结束（日志：$LOG）=="
event "{\"at\":\"$(date -Is)\",\"event\":\"batch_done\",\"run_dir\":\"$RUN_DIR\"}"
