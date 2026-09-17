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

# ── Auto-clone sub-repos if missing ──────────────────────────────────────────
# Clones the 3 sub-repos (OPP, OL, ORF) when they are missing from a fresh
# git clone of the suite.  URLs can be overridden via env vars:
#   OMNI_OPP_URL, OMNI_OL_URL, OMNI_ORF_URL
clone_submodules_if_needed() {
    local ws
    ws="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    local -a subs=(
        "Omni_Pre_Processor|${OMNI_OPP_URL:-https://github.com/renanzai40/OPP_BackUp.git}"
        "Omni_Localizer|${OMNI_OL_URL:-https://github.com/renanzai40/OL_BackUp.git}"
        "Omni_Re_Formatter|${OMNI_ORF_URL:-https://github.com/renanzai40/ORF_BackUp.git}"
    )
    for entry in "${subs[@]}"; do
        local name="${entry%%|*}"
        local url="${entry##*|}"
        local target="$ws/$name"
        if [[ -d "$target/.git" ]]; then
            ok "$name already cloned"
        else
            info "Cloning $name from $url"
            if ! git clone --depth 1 "$url" "$target"; then
                err "Failed to clone $name. Run manually: git clone --depth 1 $url $target"
                exit 1
            fi
            ok "$name cloned"
        fi
    done
}

# ── Resolve project root ─────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Detect workspace root (child vs sibling layout) ─────────────────────────
if [ -d "$PROJECT_ROOT/Omni_Pre_Processor" ]; then
    WORKSPACE_ROOT="$PROJECT_ROOT"
elif [ -d "$(dirname "$PROJECT_ROOT")/Omni_Pre_Processor" ]; then
    WORKSPACE_ROOT="$(dirname "$PROJECT_ROOT")"
else
    echo "[ERR] Cannot find Omni_Pre_Processor relative to PROJECT_ROOT=$PROJECT_ROOT"
    exit 1
fi

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

# Native Windows (Git Bash / MSYS / Cygwin) cannot use this script: the shared
# .venv_ol/ is a Linux venv (pyvenv.cfg -> .../cpython-3.13-linux-*), so
# `source .venv_ol/bin/activate` and the `bin/` layout both fail. Windows users
# have a dedicated entry point instead — see scripts/setup_dev.ps1.
if [ "$OS_FAMILY" = "windows" ]; then
    err "Native Windows detected ($OS_NAME)."
    err "  .venv_ol/ is a Linux venv shared with WSL/CI and cannot be activated here."
    err "  Use the PowerShell entry point instead:"
    err "    powershell -ExecutionPolicy Bypass -File scripts/setup_dev.ps1"
    err "  Or run this script inside WSL (uname -s reports Linux* there)."
    exit 1
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Step 1.5 — Auto-clone sub-repos (if missing from a fresh git clone)
# ═══════════════════════════════════════════════════════════════════════════════
info "Checking sub-repo clones …"
clone_submodules_if_needed

# ═══════════════════════════════════════════════════════════════════════════════
# Step 2 — Verify Python >= 3.13
# ═══════════════════════════════════════════════════════════════════════════════
info "Checking Python version …"
PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" &>/dev/null; then
    err "python3 not found. Please install Python >= 3.13."
    exit 1
fi

PY_MAJOR="$("$PYTHON_BIN" -c 'import sys; print(sys.version_info.major)')"
PY_MINOR="$("$PYTHON_BIN" -c 'import sys; print(sys.version_info.minor)')"
PY_VERSION="${PY_MAJOR}.${PY_MINOR}"

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 13 ]; }; then
    err "Python >= 3.13 required, found $PY_VERSION"
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
# Step 3b — Warn about deprecated .venv/ (Issue #9)
# ═══════════════════════════════════════════════════════════════════════════════
if [ -d "$PROJECT_ROOT/.venv" ]; then
    warn "Deprecated .venv/ detected (Python 3.12-era, superseded by .venv_ol/)."
    warn "You can safely remove it: rm -rf $PROJECT_ROOT/.venv"
    warn "All components now use .venv_ol/ exclusively."
fi

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
        pip install -e "$WORKSPACE_ROOT/Omni_Pre_Processor" -e "$WORKSPACE_ROOT/Omni_Localizer" -e "$WORKSPACE_ROOT/Omni_Re_Formatter"
    fi

    # Ensure pandoc is on PATH for ORF MD→{docx,odt,epub,rtf,icml,pdf}
    if [ -x "$PROJECT_ROOT/.venv_ol/bin/pandoc" ]; then
        mkdir -p "$HOME/.local/bin"
        if [ ! -e "$HOME/.local/bin/pandoc" ]; then
            ln -sf "$PROJECT_ROOT/.venv_ol/bin/pandoc" "$HOME/.local/bin/pandoc"
            ok "Created pandoc symlink at $HOME/.local/bin/pandoc"
        fi
    else
        warn "pandoc not found at $PROJECT_ROOT/.venv_ol/bin/pandoc — install pypandoc-binary to enable ORF MD→{docx,odt,epub,rtf,icml,pdf}"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Step 4b — Version assertion (Phase C5)
# ═══════════════════════════════════════════════════════════════════════════════
COMPAT_FILE="$PROJECT_ROOT/COMPATIBILITY.md"
if [ -f "$COMPAT_FILE" ]; then
    # Extract the row matching the CURRENT suite version. COMPATIBILITY.md lists
    # historical versions first and may repeat the same suite version on several
    # rows (patch rows), so `head -1` used to match an OLD row (0.2.0) and made
    # this check report a mismatch on every run. Take the LAST matching row.
    SUITE_VERSION="$(
        grep -v '^[[:space:]]*#' "$PROJECT_ROOT/VERSION" 2>/dev/null \
            | grep -v '^[[:space:]]*$' | tail -1 | tr -d '[:space:]'
    )"
    EXPECTED_LINE=""
    if [ -n "$SUITE_VERSION" ]; then
        EXPECTED_LINE=$(grep -E "^\| ${SUITE_VERSION} \|" "$COMPAT_FILE" | tail -1)
    fi
    if [ -n "$EXPECTED_LINE" ]; then
        EXPECTED_OL=$(echo "$EXPECTED_LINE" | awk -F'|' '{print $3}' | tr -d ' ')
        EXPECTED_OPP=$(echo "$EXPECTED_LINE" | awk -F'|' '{print $4}' | tr -d ' ')
        EXPECTED_ORF=$(echo "$EXPECTED_LINE" | awk -F'|' '{print $5}' | tr -d ' ')

        ACTUAL_OL=$(grep -m1 "^version" "$WORKSPACE_ROOT/Omni_Localizer/pyproject.toml" | sed 's/.*"\(.*\)".*/\1/')
        ACTUAL_OPP=$(grep -m1 "^version" "$WORKSPACE_ROOT/Omni_Pre_Processor/pyproject.toml" | sed 's/.*"\(.*\)".*/\1/')
        ACTUAL_ORF=$(grep -m1 "^version" "$WORKSPACE_ROOT/Omni_Re_Formatter/pyproject.toml" | sed 's/.*"\(.*\)".*/\1/')

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
        chmod 600 "$ENV_TARGET"
        ok ".env created from .env.example with chmod 600"
        warn "Edit .env to set your API keys before running real-LLM tests."
    else
        # Enforce secure permissions on existing .env
        chmod 600 "$ENV_TARGET" 2>/dev/null || true
        ok ".env permissions locked to 600"
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
