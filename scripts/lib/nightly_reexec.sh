#!/usr/bin/env bash
# nightly_reexec.sh — re-enter an entrypoint whose file was replaced mid-run.
#
# issue #212 (e2e-test-suite): `nightly_batch.sh` starts on whatever branch the
# work tree happens to be on, then `preflight()` runs
# `nightly_sync.py --switch-branch`, which may `git checkout main`. Bash reads
# a script incrementally from the fd it opened at startup; a checkout replaces
# the file (new inode), so the process keeps executing the OLD copy for the rest
# of the run. Steps added to the script on main are then silently skipped —
# exactly what happened on 2026-10-22 (`ai-process` never ran, 0 error, exit 0).
#
# The fix is not "copy the script at startup" (that would still copy the old
# branch's copy). It is: note the entrypoint hash BEFORE the sync, and if the
# file's content changed afterwards, `exec` the on-disk version with the
# original argv. The child then executes the post-sync (main) copy.
#
# Sourced by `scripts/nightly_batch.sh`. Behaviour is covered by
# `tests/test_nightly_batch_reexec.py`, which builds real git repos and
# reproduces the branch switch.

# Print a content hash for a readable file (empty + rc1 when unreadable).
nightly_file_hash() {
  local file="$1"
  [ -f "$file" ] || return 1
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$file" | awk '{print $1}'
  else
    cksum "$file" | awk '{print $1 "-" $2}'
  fi
}

# nightly_reexec_if_changed <entrypoint> <hash-before> [argv...]
#
# Re-exec <entrypoint> with [argv...] when its content no longer matches
# <hash-before>. No-op when:
#   - the call is already a re-entry (OMNI_NIGHTLY_REEXECED is set), or
#   - <entrypoint> is not a readable file / <hash-before> is empty, or
#   - the content is unchanged.
# The guard env var makes a pathological "file changes on every read" loop
# terminate after exactly one re-exec.
nightly_reexec_if_changed() {
  local entrypoint="$1" hash_before="${2:-}"
  shift 2

  [ -n "${OMNI_NIGHTLY_REEXECED:-}" ] && return 0
  [ -f "$entrypoint" ] || return 0
  [ -n "$hash_before" ] || return 0

  local hash_now
  hash_now="$(nightly_file_hash "$entrypoint")" || return 0
  [ "$hash_now" = "$hash_before" ] && return 0

  export OMNI_NIGHTLY_REEXECED=1
  printf '[nightly] entrypoint replaced during preflight -> re-exec %s (issue #212)\n' \
    "$entrypoint" >&2
  exec bash "$entrypoint" "$@"
}
