#!/bin/bash
# =============================================================================
# md2pptx install script (Phase C2)
# =============================================================================
# Clones MartinPacker/md2pptx to a stable path, makes it executable,
# and symlinks it to ~/.local/bin. Idempotent: re-running is a no-op.
#
# Usage:
#   bash scripts/install_md2pptx.sh         # install
#   bash scripts/install_md2pptx.sh --check  # verify install
# =============================================================================

set -euo pipefail

# ── Config ───────────────────────────────────────────────────────────────────
MD2PPTX_REPO="https://github.com/MartinPacker/md2pptx.git"
INSTALL_DIR="${HOME}/.local/share/omni-suite/md2pptx"
BIN_DIR="${HOME}/.local/bin"
BIN_NAME="md2pptx"

# ── Colour helpers ───────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { printf "${GREEN}[INFO]${NC}  %s\n" "$*"; }
warn()  { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
err()   { printf "${RED}[ERR]${NC}   %s\n" "$*"; }

# ── Check-only mode ──────────────────────────────────────────────────────────
CHECK_ONLY=false
for arg in "$@"; do
    case "$arg" in
        --check) CHECK_ONLY=true ;;
        *) err "Unknown argument: $arg"; exit 2 ;;
    esac
done

# ── Ensure ~/.local/bin is in PATH (warn if not) ────────────────────────────
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "$BIN_DIR is not in your PATH."
    warn "Add this to your ~/.bashrc or ~/.zshrc:"
    warn "  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# ── Check if already installed ──────────────────────────────────────────────
if [ -x "$BIN_DIR/$BIN_NAME" ] && [ -d "$INSTALL_DIR" ]; then
    info "md2pptx already installed at $BIN_DIR/$BIN_NAME"
    if [ "$CHECK_ONLY" = true ]; then
        "$BIN_DIR/$BIN_NAME" --version 2>&1 || true
        exit 0
    fi
    info "Re-running is a no-op (idempotent)."
    exit 0
fi

# ── Clone the repo ──────────────────────────────────────────────────────────
info "Installing md2pptx to $INSTALL_DIR …"
mkdir -p "$(dirname "$INSTALL_DIR")"

if [ -d "$INSTALL_DIR" ]; then
    warn "$INSTALL_DIR already exists but binary missing. Removing and re-cloning."
    rm -rf "$INSTALL_DIR"
fi

git clone --depth 1 "$MD2PPTX_REPO" "$INSTALL_DIR" 2>&1 | tail -3

# ── Make executable ─────────────────────────────────────────────────────────
# md2pptx is a Perl script — find the main entry point
MAIN_SCRIPT=$(find "$INSTALL_DIR" -name "md2pptx*" -type f | head -1)
if [ -z "$MAIN_SCRIPT" ]; then
    err "Could not find md2pptx entry script in $INSTALL_DIR"
    exit 1
fi
chmod +x "$MAIN_SCRIPT"
info "Made $MAIN_SCRIPT executable"

# ── Symlink to ~/.local/bin ─────────────────────────────────────────────────
mkdir -p "$BIN_DIR"
ln -sf "$MAIN_SCRIPT" "$BIN_DIR/$BIN_NAME"
info "Symlinked: $BIN_DIR/$BIN_NAME -> $MAIN_SCRIPT"

# ── Verify ──────────────────────────────────────────────────────────────────
if command -v "$BIN_NAME" &>/dev/null || [ -x "$BIN_DIR/$BIN_NAME" ]; then
    info "md2pptx installed successfully."
    "$BIN_DIR/$BIN_NAME" --version 2>&1 || warn "Could not run --version (may require Perl deps)"
else
    err "md2pptx install failed — binary not found at $BIN_DIR/$BIN_NAME"
    exit 1
fi
