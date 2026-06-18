#!/bin/bash
# =============================================================================
# Omni Suite — Dev Environment Setup
# =============================================================================
# Detects OS + Python version, creates/activates a shared venv, installs all
# three modules in editable mode, copies .env.example → .env, verifies pandoc,
# and runs the C-3 contract smoke test.
#
# Usage:
#   bash scripts/setup_dev.sh             # full setup (create venv, install, smoke)
#   bash scripts/setup_dev.sh --check-only  # verify without installing
# =============================================================================

set -euo pipefail

# ── Colour helpers ───────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Colour

info()  { printf "${CYAN}[INFO]${NC}  %s\n" "$*"; }
ok()    { printf "${GREEN}[OK]${NC}    %s\n" "$*"; }
warn()  { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
err()   { printf "${RED}[ERR]${NC}   %s\n" "$*"; }

# ── Resolve project root ─────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── CLI flags ────────────────────────────────────────────────────────────────
CHECK_ONLY=false
for arg in "$@"; do
    case "$arg" in
        --check-only) CHECK_ONLY=true ;;
        *) err "Unknown argument: $arg"; exit 2 ;;
    esac
done

# ═══════════════════════════════════════════════════════════════════════════════
# Step 1 — Detect OS
# ═══════════════════════════════════════════════════════════════════════════════
info "Detecting OS …"
OS_NAME="$(uname -s)"
case "$OS_NAME" in
    Linux*)  OS_FAMILY="linux"   ;;
    Darwin*) OS_FAMILY="macos"   ;;
    MINGW*|MSYS*|CYGWIN*) OS_FAMILY="windows" ;;
    *)       OS_FAMILY="unknown" ;;
esac
ok "OS detected: $OS_NAME ($OS_FAMILY)"

# ═══════════════════════════════════════════════════════════════════════════════
# Step 2 — Verify Python >= 3.12
# ═══════════════════════════════════════════════════════════════════════════════
info "Checking Python version …"
PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" &>/dev/null; then
    err "python3 not found. Please install Python >= 3.12."
    exit 1
fi

PY_MAJOR="$("$PYTHON_BIN" -c 'import sys; print(sys.version_info.major)')"
PY_MINOR="$("$PYTHON_BIN" -c 'import sys; print(sys.version_info.minor)')"
PY_VERSION="${PY_MAJOR}.${PY_MINOR}"

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 12 ]; }; then
    err "Python >= 3.12 required, found $PY_VERSION"
    exit 1
fi
ok "Python $PY_VERSION detected"

# ═══════════════════════════════════════════════════════════════════════════════
# Step 3 — Create / activate venv
# ═══════════════════════════════════════════════════════════════════════════════
VENV_DIR="$PROJECT_ROOT/.venv_ol"

if [ "$CHECK_ONLY" = false ]; then
    if [ ! -d "$VENV_DIR" ]; then
        info "Creating virtual environment at $VENV_DIR …"
        "$PYTHON_BIN" -m venv "$VENV_DIR"
        ok "Virtual environment created"
    else
        info "Virtual environment already exists at $VENV_DIR"
    fi
fi

# Check that venv exists for activation
if [ ! -f "$VENV_DIR/bin/python" ]; then
    err "Virtual environment not found at $VENV_DIR/bin/python"
    err "Re-run without --check-only to create it."
    exit 1
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
ok "Virtual environment activated ($(.venv_ol/bin/python --version))"

# ═══════════════════════════════════════════════════════════════════════════════
# Step 4 — Install via uv sync (Phase C1: root workspace)
# ═══════════════════════════════════════════════════════════════════════════════
if [ "$CHECK_ONLY" = false ]; then
    if command -v uv &>/dev/null; then
        info "Installing via uv sync (root workspace) …"
        cd "$PROJECT_ROOT"
        uv sync
        ok "uv sync complete — all 3 submodules + omni_metrics installed"
    else
        warn "uv not found — falling back to pip install -e for each submodule"
        warn "Install uv for the recommended workflow: https://docs.astral.sh/uv/"
        pip install --upgrade pip setuptools wheel -q
        pip install -e "$PROJECT_ROOT/Omni_Pre_Processor" -e "$PROJECT_ROOT/Omni_Localizer" -e "$PROJECT_ROOT/Omni_Re_Formatter"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Step 4b — Version assertion (Phase C5)
# ═══════════════════════════════════════════════════════════════════════════════
COMPAT_FILE="$PROJECT_ROOT/COMPATIBILITY.md"
if [ -f "$COMPAT_FILE" ]; then
    # Extract expected versions from the first table row
    EXPECTED_LINE=$(grep -E '^\| 0\.' "$COMPAT_FILE" | head -1)
    if [ -n "$EXPECTED_LINE" ]; then
        EXPECTED_OL=$(echo "$EXPECTED_LINE" | awk -F'|' '{print $3}' | tr -d ' ')
        EXPECTED_OPP=$(echo "$EXPECTED_LINE" | awk -F'|' '{print $4}' | tr -d ' ')
        EXPECTED_ORF=$(echo "$EXPECTED_LINE" | awk -F'|' '{print $5}' | tr -d ' ')

        ACTUAL_OL=$(grep -m1 "^version" "$PROJECT_ROOT/Omni_Localizer/pyproject.toml" | sed 's/.*"\(.*\)".*/\1/')
        ACTUAL_OPP=$(grep -m1 "^version" "$PROJECT_ROOT/Omni_Pre_Processor/pyproject.toml" | sed 's/.*"\(.*\)".*/\1/')
        ACTUAL_ORF=$(grep -m1 "^version" "$PROJECT_ROOT/Omni_Re_Formatter/pyproject.toml" | sed 's/.*"\(.*\)".*/\1/')

        info "Version check (from COMPATIBILITY.md):"
        info "  OL:  expected=$EXPECTED_OL actual=$ACTUAL_OL"
        info "  OPP: expected=$EXPECTED_OPP actual=$ACTUAL_OPP"
        info "  ORF: expected=$EXPECTED_ORF actual=$ACTUAL_ORF"

        MISMATCH=0
        [ "$EXPECTED_OL" != "$ACTUAL_OL" ] && warn "OL version mismatch" && MISMATCH=1
        [ "$EXPECTED_OPP" != "$ACTUAL_OPP" ] && warn "OPP version mismatch" && MISMATCH=1
        [ "$EXPECTED_ORF" != "$ACTUAL_ORF" ] && warn "ORF version mismatch" && MISMATCH=1

        if [ "$MISMATCH" = 1 ]; then
            warn "Submodule versions don't match COMPATIBILITY.md."
            warn "This is OK for dev work, but release builds must match."
        else
            ok "All submodule versions match COMPATIBILITY.md"
        fi
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Step 5 — Copy .env.example → .env (if not already present)
# ═══════════════════════════════════════════════════════════════════════════════
ENV_EXAMPLE="$PROJECT_ROOT/.env.example"
ENV_TARGET="$PROJECT_ROOT/.env"

if [ -f "$ENV_EXAMPLE" ]; then
    if [ ! -f "$ENV_TARGET" ]; then
        info "Copying .env.example → .env …"
        cp "$ENV_EXAMPLE" "$ENV_TARGET"
        ok ".env created from .env.example"
        warn "Edit .env to set your API keys before running real-LLM tests."
    else
        info ".env already exists — skipped copy"
    fi
else
    warn ".env.example not found at $ENV_EXAMPLE — skipping .env creation"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Step 6 — Verify pandoc
# ═══════════════════════════════════════════════════════════════════════════════
info "Checking pandoc …"
if command -v pandoc &>/dev/null; then
    PANDOC_VER="$(pandoc --version 2>/dev/null | head -1 || true)"
    ok "pandoc found: $PANDOC_VER"
else
    warn "pandoc is NOT installed"
    warn ""
    warn "  Install pandoc:"
    warn "    Ubuntu/Debian:  sudo apt-get install pandoc"
    warn "    macOS (Homebrew): brew install pandoc"
    warn "    Windows:          https://pandoc.org/installing.html"
    warn ""
    warn "  ORF apply-md requires pandoc for DOCX/ODT/EPUB generation."
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Step 7 — Run C-3 contract smoke test
# ═══════════════════════════════════════════════════════════════════════════════
SMOKE_TEST="tests/test_pipeline_contract_smoke.py"
SMOKE_PATH="$PROJECT_ROOT/$SMOKE_TEST"

if [ -f "$SMOKE_PATH" ]; then
    info "Running C-3 contract smoke test …"
    echo ""

    # Use fake LLM / offline seams so no API keys are needed
    export OMNI_TEST_FAKE_LLM=1
    export OMNI_TEST_FAKE_PANDOC=1
    export TRANSFORMERS_OFFLINE=1
    export HF_HUB_OFFLINE=1

    if python -m pytest "$SMOKE_PATH" -v --tb=short 2>&1; then
        echo ""
        ok "C-3 contract smoke test PASSED"
    else
        RC=$?
        echo ""
        err "C-3 contract smoke test FAILED (exit code $RC)"
        warn "This may be due to missing system dependencies or configuration."
        warn "Review the output above for details."
        exit $RC
    fi
else
    warn "Smoke test not found at $SMOKE_PATH — skipping"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════════
echo ""
echo "==========================================================================="
info "Setup complete. Quick-start:"
echo ""
echo "  source .venv_ol/bin/activate"
echo "  opp --target-format=md document.docx          # extract"
echo "  ol translate-md document.md -s en -t zh -o out/ # translate"
echo "  orf apply-md out/document.md --target-format docx -o result.docx # convert"
echo "==========================================================================="
