#!/usr/bin/env bash
# ============================================================================
# E2E Test Runner — OPP → OL → ORF Full Pipeline
# ============================================================================
# Usage: bash run_test.sh [OPTIONS]
#   --test-name NAME     Override test name (default: auto timestamp)
#   --short             Short run: minimal artifacts (skips large files)
#   --mcp               Also test MCP paths (default: CLI only)
#   --skip-opp          Skip OPP step
#   --skip-ol           Skip OL step
#   --skip-orf          Skip ORF step
#   --module MODULE     Test only one module: opp | ol | orf
#
# Environment:
#   SUITE_DIR           Suite root (default: parent dir of this script)
#   PY312               Python 3.12 venv python
#   OL_VENV            Path to OL venv (default: ~/.hermes/venvs/omni-localizer)
#   TEST_SIZE          "mini" | "small" | "full" (default: small)
#
# Output:
#   $SUITE_DIR/test-output/{test-name}/  (structured artifacts)
#   $SUITE_DIR/reports/{test-name}-TEST-REPORT.md
# ============================================================================
set -euo pipefail

SUITE_DIR="${SUITE_DIR:-$(cd "$(dirname "$0")" && pwd)}"
PY312="$SUITE_DIR/.venv312/bin/python"
OL_VENV="${OL_VENV:-$HOME/.hermes/venvs/omni-localizer}"
TEST_SIZE="${TEST_SIZE:-small}"
TEST_NAME="${TEST_NAME:-e2e-$(date +%Y%m%d-%H%M%S)}"
OUT_DIR="$SUITE_DIR/test-output/$TEST_NAME"

# Optional flags
RUN_MCP="${RUN_MCP:-0}"
SKIP_OPP=0; SKIP_OL=0; SKIP_ORF=0
MODULE=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --test-name)  TEST_NAME="$2"; OUT_DIR="$SUITE_DIR/test-output/$TEST_NAME"; shift 2 ;;
    --short)      TEST_SIZE="mini" ; shift ;;
    --mcp)        RUN_MCP=1 ; shift ;;
    --skip-opp)   SKIP_OPP=1 ; shift ;;
    --skip-ol)    SKIP_OL=1 ; shift ;;
    --skip-orf)   SKIP_ORF=1 ; shift ;;
    --module)     MODULE="$2"; shift 2 ;;
    *)            echo "Unknown option: $1"; exit 1 ;;
  esac
done

if [[ -n "$MODULE" ]]; then
  case $MODULE in
    opp)  SKIP_OL=1; SKIP_ORF=1 ;;
    ol)   SKIP_OPP=1; SKIP_ORF=1 ;;
    orf)  SKIP_OPP=1; SKIP_OL=1 ;;
    *)    echo "Unknown module: $MODULE"; exit 1 ;;
  esac
fi

mkdir -p "$OUT_DIR"

log()  { echo "[$(date +%H:%M:%S)] $*" | tee -a "$OUT_DIR/runner.log" ; }
fail() { echo "[FAIL] $*" | tee -a "$OUT_DIR/runner.log" ; exit 1 ; }

# --------------------------------------------------------------------------
# Prepare source document
# --------------------------------------------------------------------------
prepare_doc() {
  local src_doc="$OUT_DIR/source.docx"
  if [[ "$TEST_SIZE" == "mini" ]]; then
    # Minimal 1-paragraph doc
    "$PY312" - << 'PYEOF'
from docx import Document
doc = Document()
doc.add_heading("测试文档", level=1)
doc.add_paragraph("这是一段测试中文文本，需要被翻译成英文。")
doc.save("$src_doc")
print("Created mini source:", "$src_doc")
PYEOF
  else
    # Standard multi-paragraph doc
    "$PY312" - << 'PYEOF'
from docx import Document
doc = Document()
doc.add_heading("海尔智家 2024 年报", level=1)
doc.add_paragraph(
    "海尔智家股份有限公司成立于1984年，是全球领先的家电制造商之一。"
    "公司致力于推动智慧家庭生态系统的建设，在冰箱、洗衣机、空调等领域处于领先地位。"
)
doc.add_heading("财务摘要", level=2)
doc.add_paragraph(
    "2024年度，公司实现营业收入人民币2257亿元，同比增长8.6%。"
    "其中海外市场收入占比达到53%，展现出强劲的全球化运营能力。"
)
doc.add_heading("未来展望", level=2)
doc.add_paragraph(
    "公司计划在2025年进一步拓展海外市场，特别是在欧洲和东南亚地区。"
    "通过本地化运营和数字化转型，海尔将努力提升品牌影响力和市场份额。"
)
doc.save("$src_doc")
print("Created standard source:", "$src_doc")
PYEOF
  fi
  echo "$src_doc"
}

# --------------------------------------------------------------------------
# STEP 1: OPP — generate XLIFF
# --------------------------------------------------------------------------
run_opp() {
  log "=== STEP 1: OPP generate XLIFF ==="

  local src_doc="${1:-}"
  [[ -z "$src_doc" || ! -f "$src_doc" ]] && fail "OPP: source doc not found: $src_doc"

  local xliff_in="$OUT_DIR/opp_out/haier.xlf"
  mkdir -p "$OUT_DIR/opp_out"

  PYTHONPATH="$SUITE_DIR/src/Omni_Pre_Processor/src" \
    "$PY312" -m opp \
    --target-format xlf \
    --source-lang zh --target-lang en \
    --output-dir "$OUT_DIR/opp_out" \
    "$src_doc" 2>&1 | tee -a "$OUT_DIR/runner.log"

  local manifest="$OUT_DIR/opp_out/haier_manifest.json"
  local skeleton="$OUT_DIR/opp_out/haier.skeleton.zip"

  if [[ ! -f "$xliff_in" ]]; then
    fail "OPP output not found: $xliff_in"
  fi

  local unit_count
  unit_count=$(grep -c '<trans-unit' "$xliff_in" || echo 0)

  log "OPP OK: $unit_count units, output=$xliff_in"
  echo "$xliff_in"
}

# --------------------------------------------------------------------------
# STEP 2: OL — translate XLIFF (CLI)
# --------------------------------------------------------------------------
run_ol_cli() {
  log "=== STEP 2: OL CLI translate-xliff ==="

  local xliff_in="${1:-}"
  [[ -z "$xliff_in" || ! -f "$xliff_in" ]] && fail "OL CLI: input XLIFF not found: $xliff_in"

  local xliff_out="$OUT_DIR/ol_out/haier.xlf"
  mkdir -p "$OUT_DIR/ol_out"

  "$OL_VENV/bin/ol" translate-xliff \
    "$xliff_in" \
    --source-lang zh --target-lang en \
    --json \
    -o "$OUT_DIR/ol_out" 2>&1 | tee -a "$OUT_DIR/runner.log"

  if [[ ! -f "$xliff_out" ]]; then
    fail "OL CLI output not found: $xliff_out"
  fi

  local target_count
  target_count=$(grep -c '<target>' "$xliff_out" || echo 0)
  log "OL CLI OK: $target_count targets in output"
  echo "$xliff_out"
}

# --------------------------------------------------------------------------
# STEP 3: OL — translate XLIFF (MCP)
# --------------------------------------------------------------------------
run_ol_mcp() {
  log "=== STEP 2b: OL MCP translate-xliff ==="

  local xliff_in="${1:-}"
  [[ -z "$xliff_in" || ! -f "$xliff_in" ]] && fail "OL MCP: input XLIFF not found: $xliff_in"

  # MCP call via Hermes mcp_ol_translate_xliff tool — skip if RUN_MCP=0
  # For now, stub: call the MCP server directly via stdio JSON-RPC
  local xliff_out="$OUT_DIR/ol_mcp_out/haier.xlf"
  mkdir -p "$OUT_DIR/ol_mcp_out"
  cp "$xliff_in" "$xliff_out.orig"

  # TODO: implement MCP stdio call
  log "OL MCP: (stub — not yet implemented, use CLI result)"
  echo "$xliff_out"
}

# --------------------------------------------------------------------------
# STEP 4: ORF — apply XLIFF
# --------------------------------------------------------------------------
run_orf() {
  log "=== STEP 3: ORF apply-xliff ==="

  local src_doc="${1:-}"
  local xliff_in="${2:-}"
  [[ ! -f "$src_doc" ]] && fail "ORF: source doc not found: $src_doc"
  [[ ! -f "$xliff_in" ]] && fail "ORF: XLIFF not found: $xliff_in"

  local result_doc="$OUT_DIR/orf_out/result.docx"
  mkdir -p "$OUT_DIR/orf_out"

  PYTHONPATH="$SUITE_DIR/src/Omni_Re_Formatter/src" \
    "$PY312" -m orf.cli apply-xliff \
    "$src_doc" \
    --xliff "$xliff_in" \
    --output "$result_doc" \
    --format docx 2>&1 | tee -a "$OUT_DIR/runner.log"

  if [[ ! -f "$result_doc" ]]; then
    fail "ORF output not found: $result_doc"
  fi

  log "ORF OK: output=$result_doc"
  echo "$result_doc"
}

# --------------------------------------------------------------------------
# Analyze results
# --------------------------------------------------------------------------
analyze() {
  log "=== ANALYSIS ==="

  local xliff_cli="$OUT_DIR/ol_out/haier.xlf"
  local xliff_mcp="${OUT_DIR}/ol_mcp_out/haier.xlf"
  local result="$OUT_DIR/result.txt"

  {
    echo "# E2E Test Report: $TEST_NAME"
    echo "Test time: $(date -Iseconds)"
    echo "Suite: $SUITE_DIR"
    echo "OPP SHA: $(git -C "$SUITE_DIR/src/Omni_Pre_Processor" rev-parse --short HEAD)"
    echo "OL SHA:  $(git -C "$SUITE_DIR/src/Omni_Localizer" rev-parse --short HEAD)"
    echo "ORF SHA: $(git -C "$SUITE_DIR/src/Omni_Re_Formatter" rev-parse --short HEAD)"
    echo ""
    echo "## Pipeline"
    echo "| Step | Status | Details |"
    echo "|------|--------|--------|"
    echo "| OPP  | $([ -f "${OUT_DIR}/opp_out/haier.xlf" ] && echo 'OK' || echo 'FAIL') | ${OUT_DIR}/opp_out/ |"
    echo "| OL CLI | $([ -f "$xliff_cli" ] && echo 'OK' || echo 'FAIL') | $(grep -c '<target>' "$xliff_cli" 2>/dev/null || echo 0) targets |"
    echo "| OL MCP | $([ -f "$xliff_mcp" ] && echo 'OK' || echo 'SKIP') | MCP path |"
    echo "| ORF  | $([ -f "${OUT_DIR}/orf_out/result.docx" ] && echo 'OK' || echo 'FAIL') | ${OUT_DIR}/orf_out/ |"
    echo ""
    echo "## Bug Findings"
    echo "TBD — fill after Hermes review"
  } > "$result"

  echo "$result"
}

# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
main() {
  log "Starting E2E run: TEST_NAME=$TEST_NAME TEST_SIZE=$TEST_SIZE"
  log "Suite: $SUITE_DIR"
  log "PY312: $PY312"
  log "OL_VENV: $OL_VENV"

  if [[ "$SKIP_OPP" == "0" ]]; then
    local src_doc
    src_doc=$(prepare_doc)
    local xliff_in
    xliff_in=$(run_opp "$src_doc")
  else
    log "OPP skipped"
    local xliff_in="${OUT_DIR}/opp_out/haier.xlf"
  fi

  if [[ "$SKIP_OL" == "0" ]]; then
    local xliff_out
    if [[ "$RUN_MCP" == "1" ]]; then
      run_ol_mcp "$xliff_in"
    fi
    xliff_out=$(run_ol_cli "$xliff_in")
  else
    log "OL skipped"
    local xliff_out="${OUT_DIR}/ol_out/haier.xlf"
  fi

  if [[ "$SKIP_ORF" == "0" ]]; then
    local src_doc="${OUT_DIR}/source.docx"
    run_orf "$src_doc" "$xliff_out"
  else
    log "ORF skipped"
  fi

  local report
  report=$(analyze)
  log "Analysis complete: $report"
  log "E2E run complete: $TEST_NAME"
}

main "$@"