#!/usr/bin/env bash
# ============================================================================
# sync_shallow.sh — 同步三个 submodule 到最新上游 SHA
# ============================================================================
# Usage: bash sync_shallow.sh [--force]
#
# 行为：
#   1. git fetch origin 在每个 submodule
#   2. 更新 submodule pointer 到 origin/{branch} 最新 SHA
#   3. 在套件 commit 更新（如果 SHA 变了）
#
# --force: 即使 submodule 内容没变也做 commit（用于记录同步时间戳）
# ============================================================================
set -euo pipefail

SUITE_DIR="$(cd "$(dirname "$0")" && pwd)"
FORCE="${1:-}"

log() { echo "[$(date +%H:%M:%S)] $*"; }

sync_one() {
  local name="$1"
  local path="$2"
  local workdir="$SUITE_DIR/$path"

  if [[ ! -d "$workdir/.git" ]]; then
    log "SKIP $path: not a git repo"
    return
  fi

  local old_sha short_sha
  old_sha=$(git -C "$workdir" rev-parse --short HEAD 2>/dev/null || echo "unknown")
  short_sha=$(git -C "$workdir" rev-parse --short origin/main 2>/dev/null || echo "unknown")

  log "--- $name ---"
  log "  Current: $old_sha  |  origin/main: $short_sha"

  git -C "$workdir" fetch origin main 2>/dev/null || true

  local new_sha
  new_sha=$(git -C "$workdir" rev-parse --short origin/main 2>/dev/null || echo "")

  if [[ "$old_sha" == "$new_sha" && -z "$FORCE" ]]; then
    log "  No change — skip"
    return
  fi

  log "  Updating: $old_sha → $new_sha"
  git -C "$workdir" checkout origin/main 2>/dev/null || \
  git -C "$workdir" checkout "$new_sha" 2>/dev/null || true

  # Record new SHA in suite index
  git -C "$SUITE_DIR" add "$path"
  log "  ✓ Recorded in suite index"
}

main() {
  log "Syncing submodules to origin/main..."

  sync_one "OPP" "src/Omni_Pre_Processor"
  sync_one "OL"  "src/Omni_Localizer"
  sync_one "ORF" "src/Omni_Re_Formatter"

  local status
  status=$(git -C "$SUITE_DIR" status --short)
  if [[ -z "$status" ]]; then
    log "All submodules already at origin/main — nothing to commit"
  else
    log "Changes staged:"
    echo "$status"
    log "Commit with: git commit -m 'chore: sync submodules to origin/main'"
  fi
}

main "$@"
