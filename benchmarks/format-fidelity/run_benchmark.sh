#!/usr/bin/env bash
# =============================================================================
# format-fidelity benchmark: Omni (OPP→OL→ORF, MD path) vs pandoc direct
# =============================================================================
# Compares how well each path preserves the STRUCTURE of a source .docx
# (paragraph / table / image counts). Measures FORMAT fidelity only — the
# translation step runs under OMNI_TEST_FAKE_LLM=1 (placeholder, no API keys).
#
# Usage:  bash run_benchmark.sh [input.docx]
#         (default: fixtures/plain.docx relative to this script)
#
# Output: results/<ts>/metrics.json + console summary
# =============================================================================
set -u

# ---- Resolve suite root + benchmark dir (independent of CWD) ---------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCH_DIR="$SCRIPT_DIR"
SUITE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ---- Environment (FAKE_LLM placeholder + OL config required by ol CLI) -----
export OMNI_TEST_FAKE_LLM=1
export OL_CONFIG_PATH="/mnt/d/贯维/Omni_Suite/Omni_Localizer/config/test_universal.yaml"

VENV_BIN="$SUITE_ROOT/.venv_ol/bin"
PY="$VENV_BIN/python"

# ---- Console helpers --------------------------------------------------------
info()  { printf '%s\n' "[bench] $*"; }
error() { printf '%s\n' "[bench] ERROR: $*" >&2; }

# ---- Input validation -------------------------------------------------------
INPUT="${1:-$BENCH_DIR/fixtures/plain.docx}"
if [ ! -f "$INPUT" ]; then
    error "input file not found: $INPUT"
    exit 2
fi
INPUT="$(cd "$(dirname "$INPUT")" && pwd)/$(basename "$INPUT")"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
RESULTS_DIR="$BENCH_DIR/../results/$TIMESTAMP"
mkdir -p "$RESULTS_DIR/omni"

# =============================================================================
# Metric: count structural elements inside a .docx (zipfile + document.xml).
#   paragraphs = regex count of "<w:p>" / "<w:p ...>" block open tags
#   tables     = regex count of "<w:tbl>" / "<w:tbl ...>"
#   images     = number of files under word/media/ (embedded media objects)
# One consistent method per metric, applied identically to source + outputs.
# =============================================================================
count_docx() {
    "$PY" - "$1" <<'PYEOF'
import re
import sys
import zipfile

path = sys.argv[1]
try:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
        paragraphs = len(re.findall(r"<w:p[ >/]", xml))
        tables = len(re.findall(r"<w:tbl[ >/]", xml))
        images = sum(1 for n in z.namelist() if n.startswith("word/media/") and not n.endswith("/"))
    print(f"{paragraphs} {tables} {images}")
except Exception as exc:  # noqa: BLE001 - report and fail the metric, not the shell
    print(f"ERROR: {exc}", file=sys.stderr)
    sys.exit(3)
PYEOF
}

# =============================================================================
# Path (a): Omni MD path — OPP extract → OL translate (FAKE_LLM) → ORF docx
# =============================================================================
run_omni_md_path() {
    local opp_dir="$RESULTS_DIR/omni/opp"
    local ol_dir="$RESULTS_DIR/omni/ol"

    info "Omni MD path [1/3]: OPP extract"
    "$VENV_BIN/opp" "$INPUT" --target-format md --output-dir "$opp_dir" --no-cache \
        || return 1
    local md_file
    md_file="$(find "$opp_dir" -maxdepth 1 -name '*.md' | head -n 1)"
    if [ -z "$md_file" ]; then
        error "OPP produced no .md file in $opp_dir"
        return 1
    fi

    info "Omni MD path [2/3]: OL translate (FAKE_LLM placeholder)"
    "$VENV_BIN/ol" translate-md "$md_file" -s en -t zh -o "$ol_dir" --no-cache \
        || return 1
    local md_translated
    md_translated="$(find "$ol_dir" -maxdepth 1 -name '*.md' | head -n 1)"
    if [ -z "$md_translated" ]; then
        error "OL produced no .md file in $ol_dir"
        return 1
    fi

    info "Omni MD path [3/3]: ORF apply-md → docx"
    "$VENV_BIN/orf" apply-md "$md_translated" --target-format docx \
        -o "$RESULTS_DIR/omni_output.docx" --no-cache \
        || return 1
    [ -f "$RESULTS_DIR/omni_output.docx" ]
}

# =============================================================================
# Path (b): pandoc direct docx→docx
# =============================================================================
run_pandoc_path() {
    if ! command -v pandoc >/dev/null 2>&1; then
        error "pandoc not found on PATH — skipping pandoc path (Omni path continues)"
        PANDOC_STATUS="skipped"
        return 0
    fi
    if ! pandoc "$INPUT" -o "$RESULTS_DIR/pandoc_output.docx"; then
        error "pandoc conversion failed — skipping pandoc path (Omni path continues)"
        PANDOC_STATUS="error"
        return 0
    fi
    PANDOC_STATUS="ok"
    return 0
}

# =============================================================================
# Main
# =============================================================================
info "input       : $INPUT"
info "results dir : $RESULTS_DIR"

# --- Source baseline ---------------------------------------------------------
SRC_COUNTS="$(count_docx "$INPUT")" || { error "failed to count source docx"; exit 3; }

# --- Path (a): Omni MD -------------------------------------------------------
PANDOC_STATUS="skipped"
OMNI_STATUS="ok"
if ! run_omni_md_path; then
    error "Omni MD path failed (see tool output above)"
    OMNI_STATUS="error"
fi

# --- Path (b): pandoc --------------------------------------------------------
PANDOC_STATUS="skipped"
run_pandoc_path

# --- Collect output metrics --------------------------------------------------
OMNI_JSON_COUNTS="none"
OMNI_PARAS="-" ; OMNI_TBLS="-" ; OMNI_IMGS="-"
if [ "$OMNI_STATUS" = "ok" ]; then
    OMNI_COUNTS="$(count_docx "$RESULTS_DIR/omni_output.docx")" || OMNI_STATUS="error"
    if [ "$OMNI_STATUS" = "ok" ]; then
        read -r OMNI_PARAS OMNI_TBLS OMNI_IMGS <<<"$OMNI_COUNTS"
    fi
fi

PANDOC_PARAS="-" ; PANDOC_TBLS="-" ; PANDOC_IMGS="-"
if [ "$PANDOC_STATUS" = "ok" ]; then
    PANDOC_COUNTS="$(count_docx "$RESULTS_DIR/pandoc_output.docx")" || PANDOC_STATUS="error"
    if [ "$PANDOC_STATUS" = "ok" ]; then
        read -r PANDOC_PARAS PANDOC_TBLS PANDOC_IMGS <<<"$PANDOC_COUNTS"
    fi
fi
read -r SRC_PARAS SRC_TBLS SRC_IMGS <<<"$SRC_COUNTS"

# --- metrics.json ------------------------------------------------------------
"$PY" - "$RESULTS_DIR/metrics.json" \
      "$TIMESTAMP" "$INPUT" \
      "$SRC_PARAS" "$SRC_TBLS" "$SRC_IMGS" \
      "$OMNI_PARAS" "$OMNI_TBLS" "$OMNI_IMGS" "$OMNI_STATUS" \
      "$PANDOC_PARAS" "$PANDOC_TBLS" "$PANDOC_IMGS" "$PANDOC_STATUS" \
      "$RESULTS_DIR/omni_output.docx" "$RESULTS_DIR/pandoc_output.docx" <<'PYEOF'
import json
import sys

out_path = sys.argv[1]
(timestamp, input_path,
 src_p, src_t, src_i,
 omni_p, omni_t, omni_i, omni_status,
 pandoc_p, pandoc_t, pandoc_i, pandoc_status,
 omni_out, pandoc_out) = sys.argv[2:]


def axis(p, t, i, status, output):
    counts = {"paragraphs": int(p), "tables": int(t), "images": int(i)}
    entry = {"paragraphs": counts["paragraphs"], "tables": counts["tables"],
             "images": counts["images"]}
    if status == "ok":
        entry["output"] = output
    else:
        entry["output"] = None
        entry["reason"] = f"path {status}"
    return entry


src_entry = {"paragraphs": int(src_p), "tables": int(src_t), "images": int(src_i)}

style_axis = (
    "N/A — MD path does not carry source styles through pandoc (by construction); "
    "XLIFF path is the fidelity path (extensible, not in this run)"
)
note = (
    "translation step uses OMNI_TEST_FAKE_LLM=1 placeholder; this benchmark "
    "measures FORMAT fidelity (structure preservation), not translation quality"
)

metrics = {
    "timestamp": timestamp,
    "input": input_path,
    "source": src_entry,
    "omni_md_path": axis(omni_p, omni_t, omni_i, omni_status, omni_out),
    "pandoc_path": axis(pandoc_p, pandoc_t, pandoc_i, pandoc_status, pandoc_out),
}
metrics["omni_md_path"]["status"] = omni_status
metrics["pandoc_path"]["status"] = pandoc_status
metrics["style_axis"] = style_axis
metrics["note"] = note

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(metrics, f, indent=2, ensure_ascii=False)
    f.write("\n")
PYEOF

# --- Console summary ---------------------------------------------------------
echo ""
info "=== format-fidelity summary ==="
info "input: $INPUT"
printf '%-14s %12s %8s %8s\n' "path" "paragraphs" "tables" "images"
printf '%-14s %12s %8s %8s\n' "source" "$SRC_PARAS" "$SRC_TBLS" "$SRC_IMGS"
printf '%-14s %12s %8s %8s   (%s)\n' "omni-md" "$OMNI_PARAS" "$OMNI_TBLS" "$OMNI_IMGS" "$OMNI_STATUS"
printf '%-14s %12s %8s %8s   (%s)\n' "pandoc" "$PANDOC_PARAS" "$PANDOC_TBLS" "$PANDOC_IMGS" "$PANDOC_STATUS"
info "metrics.json : $RESULTS_DIR/metrics.json"

# --- Exit code contract ------------------------------------------------------
# Omni path failure is fatal; pandoc failure is recorded but non-fatal.
if [ "$OMNI_STATUS" != "ok" ]; then
    error "benchmark finished WITH ERRORS (Omni MD path failed)"
    exit 4
fi
info "DONE (omni=ok, pandoc=$PANDOC_STATUS)"
exit 0
