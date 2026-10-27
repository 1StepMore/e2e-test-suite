#!/bin/bash
# =============================================================================
# md2pptx install script (Phase C2)
# =============================================================================
# md2pptx (https://github.com/MartinPacker/md2pptx) is a single Python 3
# script — not a compiled CLI, not a package-manager tool, not a pip
# package. It imports its helper
# modules (funnel.py, paragraph.py, …) from the directory it lives in, so
# the clone is kept intact and only the pinned entry point is linked.
#
# This script clones the repo to a stable path, pins the entry point to
# "$INSTALL_DIR/md2pptx" (never a helper module, never the md2pptx.py
# shim), symlinks it into a bin dir, and proves the install with a REAL
# small conversion (a ZIP containing ppt/presentation.xml).
#
# Requirements: Python 3 with python-pptx >= 1.0
#   pip install 'python-pptx>=1.0'
# Optional inline-math support: latex2mathml + lxml
#
# Usage:
#   bash scripts/install_md2pptx.sh          # install (idempotent)
#   bash scripts/install_md2pptx.sh --check  # verify an existing install
#
# Env overrides (defaults shown):
#   MD2PPTX_INSTALL_DIR  $HOME/.local/share/omni-suite/md2pptx
#   MD2PPTX_BIN_DIR      $HOME/.local/bin
#
# Example — exercise the installer without touching $HOME:
#   MD2PPTX_INSTALL_DIR=/tmp/md2p/install MD2PPTX_BIN_DIR=/tmp/md2p/bin \
#       bash scripts/install_md2pptx.sh
# =============================================================================

set -euo pipefail

# ── Config ───────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SUITE_ROOT="$(dirname -- "$SCRIPT_DIR")"

MD2PPTX_REPO="${MD2PPTX_REPO:-https://github.com/MartinPacker/md2pptx.git}"
INSTALL_DIR="${MD2PPTX_INSTALL_DIR:-${HOME}/.local/share/omni-suite/md2pptx}"
BIN_DIR="${MD2PPTX_BIN_DIR:-${HOME}/.local/bin}"
BIN_NAME="md2pptx"
PYTHON="python3"

# The ONE entry point. Pinned on purpose: `find … -name "md2pptx*" | head -1`
# can pick a 7-byte md2pptx.py shim or a helper module.
ENTRY="${INSTALL_DIR}/${BIN_NAME}"

# Make overrides absolute so the symlink target is stable.
case "$INSTALL_DIR" in /*) ;; *) INSTALL_DIR="${PWD}/${INSTALL_DIR}" ;; esac
case "$BIN_DIR" in /*) ;; *) BIN_DIR="${PWD}/${BIN_DIR}" ;; esac
ENTRY="${INSTALL_DIR}/${BIN_NAME}"

# ── Colour helpers ───────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { printf "${GREEN}[INFO]${NC}  %s\n" "$*"; }
warn()  { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
err()   { printf "${RED}[ERR]${NC}   %s\n" "$*"; }

# ── Arg parsing ──────────────────────────────────────────────────────────────
CHECK_ONLY=false
for arg in "$@"; do
    case "$arg" in
        --check) CHECK_ONLY=true ;;
        -h|--help)
            sed -n '2,36p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) err "Unknown argument: $arg"; exit 2 ;;
    esac
done

# ── Preflight: Python 3 + python-pptx ───────────────────────────────────────
# md2pptx's shebang is `#!/usr/bin/env python3`, so the interpreter that
# matters is the one PATH resolves. Check it up front instead of letting the
# smoke conversion fail with a bare ModuleNotFoundError.
if ! command -v "$PYTHON" >/dev/null 2>&1; then
    err "python3 not found on PATH — md2pptx is a Python 3 script."
    exit 1
fi
if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info[0] >= 3 else 1)' 2>/dev/null; then
    err "md2pptx requires Python 3 (found: $("$PYTHON" --version 2>&1))."
    exit 1
fi
if ! "$PYTHON" -c 'import pptx' 2>/dev/null; then
    err "md2pptx requires python-pptx (>=1.0), but '$PYTHON' cannot 'import pptx'."
    err "Install it:  $PYTHON -m pip install 'python-pptx>=1.0'"
    if [ -x "$SUITE_ROOT/.venv_ol/bin/pip" ]; then
        err "Or use the suite venv:  $SUITE_ROOT/.venv_ol/bin/pip install 'python-pptx>=1.0'"
        err "then put $SUITE_ROOT/.venv_ol/bin before the system python3 on PATH."
    fi
    err "(Optional, inline math only: pip install latex2mathml lxml)"
    exit 1
fi
info "Python preflight OK: $("$PYTHON" -c 'import sys, pptx; print("Python", sys.version.split()[0], "/ python-pptx", pptx.__version__)')"

# ── Real smoke conversion ────────────────────────────────────────────────────
# Upstream accepts the positional INPUT OUTPUT form:
#   `if len(sys.argv) > 2: input_filename = sys.argv[1]; output_filename = sys.argv[2]`
# A successful run must leave a PPTX, i.e. a ZIP with ppt/presentation.xml.
smoke_test() {
    local tmp rc=0
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/md2pptx-smoke.XXXXXX")"
    printf '# Smoke\n\nHello from the md2pptx installer.\n' > "$tmp/smoke.md"

    set +e
    env -u PYTHONPATH "$BIN_DIR/$BIN_NAME" "$tmp/smoke.md" "$tmp/smoke.pptx" \
        >"$tmp/stdout.log" 2>"$tmp/stderr.log"
    rc=$?
    set -e

    if [ "$rc" -ne 0 ]; then
        err "Smoke conversion FAILED (exit $rc): $BIN_DIR/$BIN_NAME $tmp/smoke.md $tmp/smoke.pptx"
        err "--- stdout ---"
        sed 's/^/    /' "$tmp/stdout.log" >&2 || true
        err "--- stderr ---"
        sed 's/^/    /' "$tmp/stderr.log" >&2 || true
        rm -rf "$tmp"
        return 1
    fi

    if [ ! -f "$tmp/smoke.pptx" ]; then
        err "Smoke conversion exited 0 but produced no file at $tmp/smoke.pptx"
        err "--- stdout ---"
        sed 's/^/    /' "$tmp/stdout.log" >&2 || true
        err "--- stderr ---"
        sed 's/^/    /' "$tmp/stderr.log" >&2 || true
        rm -rf "$tmp"
        return 1
    fi

    if ! "$PYTHON" -c \
        'import sys, zipfile
sys.exit(0 if "ppt/presentation.xml" in zipfile.ZipFile(sys.argv[1]).namelist() else 1)' \
        "$tmp/smoke.pptx" 2>"$tmp/zipcheck.log"; then
        err "Smoke output $tmp/smoke.pptx is not a valid PPTX (no ppt/presentation.xml)."
        err "--- stdout ---"
        sed 's/^/    /' "$tmp/stdout.log" >&2 || true
        err "--- stderr ---"
        sed 's/^/    /' "$tmp/stderr.log" >&2 || true
        err "--- zip check ---"
        sed 's/^/    /' "$tmp/zipcheck.log" >&2 || true
        rm -rf "$tmp"
        return 1
    fi

    info "Smoke conversion OK: $(wc -c < "$tmp/smoke.pptx" | tr -d ' ') bytes, contains ppt/presentation.xml"
    rm -rf "$tmp"
    return 0
}

# ── Check-only mode ──────────────────────────────────────────────────────────
if [ "$CHECK_ONLY" = true ]; then
    if [ ! -f "$ENTRY" ]; then
        err "md2pptx is not installed at $ENTRY — run without --check first."
        exit 1
    fi
    if [ ! -e "$BIN_DIR/$BIN_NAME" ]; then
        err "$BIN_DIR/$BIN_NAME is missing — run without --check to repair it."
        exit 1
    fi
    info "Verifying existing install with a real smoke conversion …"
    smoke_test || { err "md2pptx check failed."; exit 1; }
    info "md2pptx check passed."
    exit 0
fi

# ── Ensure ~/.local/bin is in PATH (warn if not) ────────────────────────────
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "$BIN_DIR is not in your PATH."
    warn "Add this to your ~/.bashrc or ~/.zshrc:"
    warn "  export PATH=\"$BIN_DIR:\$PATH\""
fi

# ── Clone the repo (only when the pinned entry is absent) ───────────────────
if [ -f "$ENTRY" ]; then
    info "md2pptx sources already present at $INSTALL_DIR (reusing)."
else
    if [ -e "$INSTALL_DIR" ]; then
        warn "$INSTALL_DIR exists but $ENTRY is missing. Removing and re-cloning."
        rm -rf "$INSTALL_DIR"
    fi
    mkdir -p "$(dirname "$INSTALL_DIR")"
    info "Installing md2pptx to $INSTALL_DIR …"

    attempt=1
    while :; do
        set +e
        git clone --depth 1 "$MD2PPTX_REPO" "$INSTALL_DIR"
        rc=$?
        set -e
        if [ "$rc" -eq 0 ]; then
            break
        fi
        rm -rf "$INSTALL_DIR"
        if [ "$attempt" -ge 3 ]; then
            err "git clone failed after $attempt attempts (exit $rc)."
            err "If Git transport is flaky, fetch a tarball instead:"
            err "  gh api repos/MartinPacker/md2pptx/tarball > /tmp/md2pptx.tar.gz"
            err "  mkdir -p \"$INSTALL_DIR\" && tar xzf /tmp/md2pptx.tar.gz -C \"$INSTALL_DIR\" --strip-components=1"
            err "then re-run this installer."
            exit 1
        fi
        warn "git clone failed (exit $rc); retrying ($((attempt + 1))/3) …"
        attempt=$((attempt + 1))
        sleep 2
    done
fi

# ── Pin + validate the entry point ──────────────────────────────────────────
if [ ! -f "$ENTRY" ]; then
    err "Pinned entry point missing: $ENTRY"
    err "Upstream layout changed? Expected the Python script at the repo root."
    exit 1
fi

first_line="$(head -n 1 "$ENTRY" 2>/dev/null || true)"
case "$first_line" in
    '#!'*python*) : ;;
    *)
        err "$ENTRY does not look like the md2pptx Python 3 script (shebang: ${first_line:-<empty>})."
        exit 1
        ;;
esac

chmod +x "$ENTRY"
info "Pinned entry point: $ENTRY ($(wc -c < "$ENTRY" | tr -d ' ') bytes)"

# ── Symlink into BIN_DIR (repair a wrong/stale link) ────────────────────────
mkdir -p "$BIN_DIR"
LINK="$BIN_DIR/$BIN_NAME"
if [ -L "$LINK" ]; then
    current="$(readlink "$LINK")"
    if [ "$current" != "$ENTRY" ]; then
        warn "Repairing $LINK: $current -> $ENTRY"
        rm -f "$LINK"
    fi
elif [ -e "$LINK" ]; then
    warn "$LINK is a regular file, replacing it with a symlink -> $ENTRY"
    rm -f "$LINK"
fi
if [ ! -e "$LINK" ]; then
    ln -s "$ENTRY" "$LINK"
    info "Symlinked: $LINK -> $ENTRY"
else
    info "Symlink already correct: $LINK -> $ENTRY"
fi

# ── Verify with a real conversion (not --version) ───────────────────────────
info "Verifying install with a real smoke conversion …"
if ! smoke_test; then
    err "md2pptx install failed its smoke conversion — see output above."
    exit 1
fi

info "md2pptx installed successfully at $LINK"
