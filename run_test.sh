#!/usr/bin/env bash
# ============================================================================
# E2E Test Runner — OPP → OL → ORF Full Pipeline
# ============================================================================
set -euo pipefail

SUITE_DIR="${SUITE_DIR:-$(cd "$(dirname "$0")" && pwd)}"
PY312="$SUITE_DIR/.venv312/bin/python"
OL_VENV="${OL_VENV:-$HOME/.hermes/venvs/omni-localizer}"
TEST_SIZE="${TEST_SIZE:-small}"
TEST_NAME="${TEST_NAME:-e2e-$(date +%Y%m%d-%H%M%S)}"
OUT_DIR="$SUITE_DIR/test-output/$TEST_NAME"
mkdir -p "$OUT_DIR"

log()  { echo "[$(date +%H:%M:%S)] $*" | tee -a "$OUT_DIR/runner.log" ; }
fail() { echo "[FAIL] $*" | tee -a "$OUT_DIR/runner.log" ; exit 1 ; }

# --------------------------------------------------------------------------
# Prepare source document (writes to fixed path OUT_DIR/haier.docx)
# --------------------------------------------------------------------------
prepare_doc() {
  local src_doc="$OUT_DIR/haier.docx"
  local tmp_script
  tmp_script=$(mktemp /tmp/prepare_doc_XXXXX.py)

  cat > "$tmp_script" << 'PYEOF'
import sys
from docx import Document

src_doc = sys.argv[1]
test_size = sys.argv[2]

doc = Document()

if test_size == "mini":
    doc.add_heading("测试文档", level=1)
    doc.add_paragraph("这是一段测试中文文本，需要被翻译成英文。")
else:
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

doc.save(src_doc)
print(src_doc)
PYEOF

  "$PY312" "$tmp_script" "$src_doc" "$TEST_SIZE" >> "$OUT_DIR/runner.log" 2>&1
  rm -f "$tmp_script"

  if [[ ! -f "$src_doc" ]]; then
    fail "prepare_doc: file not created at $src_doc"
  fi
  log "prepare_doc OK: $src_doc"
}

# --------------------------------------------------------------------------
# STEP 1: OPP — generate XLIFF
# --------------------------------------------------------------------------
run_opp() {
  log "=== STEP 1: OPP generate XLIFF ==="

  local src_doc="$OUT_DIR/haier.docx"
  if [[ ! -f "$src_doc" ]]; then
    fail "OPP: source doc not found: $src_doc"
  fi

  local xliff_in="$OUT_DIR/opp_out/haier.xlf"
  mkdir -p "$OUT_DIR/opp_out"

  PYTHONPATH="$SUITE_DIR/src/Omni_Pre_Processor/src" \
    "$PY312" -m opp \
    --target-format xlf \
    --source-lang zh --target-lang en \
    --output-dir "$OUT_DIR/opp_out" \
    "$src_doc" >> "$OUT_DIR/runner.log" 2>&1

  if [[ ! -f "$xliff_in" ]]; then
    fail "OPP output not found: $xliff_in"
  fi

  local unit_count
  unit_count=$(grep -c '<trans-unit' "$xliff_in" || echo 0)
  log "OPP OK: $unit_count units, output=$xliff_in"
}

# --------------------------------------------------------------------------
# STEP 2: OL — translate XLIFF (CLI)
# --------------------------------------------------------------------------
run_ol_cli() {
  log "=== STEP 2: OL CLI translate-xliff ==="

  local xliff_in="$OUT_DIR/opp_out/haier.xlf"
  if [[ ! -f "$xliff_in" ]]; then
    fail "OL CLI: input XLIFF not found: $xliff_in"
  fi

  local xliff_out="$OUT_DIR/ol_out/haier.xlf"
  mkdir -p "$OUT_DIR/ol_out"

  "$OL_VENV/bin/ol" translate-xliff \
    "$xliff_in" \
    --source-lang zh --target-lang en \
    --json \
    -o "$OUT_DIR/ol_out" >> "$OUT_DIR/runner.log" 2>&1

  if [[ ! -f "$xliff_out" ]]; then
    fail "OL CLI output not found: $xliff_out"
  fi

  local target_count
  target_count=$(grep -c '<target>' "$xliff_out" || echo 0)
  log "OL CLI OK: $target_count targets in output"
}

# --------------------------------------------------------------------------
# STEP 3: ORF — apply XLIFF
# --------------------------------------------------------------------------
run_orf() {
  log "=== STEP 3: ORF apply-xliff ==="

  local src_doc="$OUT_DIR/haier.docx"
  local xliff_in="$OUT_DIR/ol_out/haier.xlf"
  if [[ ! -f "$src_doc" ]]; then
    fail "ORF: source doc not found: $src_doc"
  fi
  if [[ ! -f "$xliff_in" ]]; then
    fail "ORF: XLIFF not found: $xliff_in"
  fi

  local result_doc="$OUT_DIR/orf_out/result.docx"
  mkdir -p "$OUT_DIR/orf_out"

  PYTHONPATH="$SUITE_DIR/src/Omni_Re_Formatter/src" \
    "$PY312" -m orf.cli apply-xliff \
    "$src_doc" \
    --xliff "$xliff_in" \
    --output "$result_doc" \
    --format docx >> "$OUT_DIR/runner.log" 2>&1

  if [[ ! -f "$result_doc" ]]; then
    fail "ORF output not found: $result_doc"
  fi

  log "ORF OK: output=$result_doc"
}

# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
main() {
  local skip_opp=0 skip_ol=0 skip_orf=0 module=""

  while [[ $# -gt 0 ]]; do
    case $1 in
      --test-name)  TEST_NAME="$2"; OUT_DIR="$SUITE_DIR/test-output/$TEST_NAME"; mkdir -p "$OUT_DIR"; shift 2 ;;
      --short)      TEST_SIZE="mini" ; shift ;;
      --skip-opp)   skip_opp=1 ; shift ;;
      --skip-ol)    skip_ol=1 ; shift ;;
      --skip-orf)   skip_orf=1 ; shift ;;
      --module)
        module="$2"
        case $module in
          opp) skip_ol=1; skip_orf=1 ;;
          ol)  skip_opp=1; skip_orf=1 ;;
          orf) skip_opp=1; skip_ol=1 ;;
          *) echo "Unknown module: $module"; exit 1 ;;
        esac
        shift 2 ;;
      *) echo "Unknown option: $1"; exit 1 ;;
    esac
  done

  log "Starting E2E run: TEST_NAME=$TEST_NAME TEST_SIZE=$TEST_SIZE"
  log "Suite: $SUITE_DIR"
  log "PY312: $PY312"
  log "OL_VENV: $OL_VENV"

  if [[ "$skip_opp" == "0" ]]; then
    prepare_doc
    run_opp
  else
    log "OPP skipped"
  fi

  if [[ "$skip_ol" == "0" ]]; then
    run_ol_cli
  else
    log "OL skipped"
  fi

  if [[ "$skip_orf" == "0" ]]; then
    run_orf
  else
    log "ORF skipped"
  fi

  log "E2E run complete: $TEST_NAME"
}

main "$@"