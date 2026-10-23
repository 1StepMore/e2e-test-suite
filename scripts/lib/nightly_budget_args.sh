#!/usr/bin/env bash
# nightly_budget_args.sh — capability-probed budget flags for the ai-process step.
#
# The nightly process stage used to have no total budget: `--timeout` is
# per-domain and defaults to 7200s, so 21 domains could run for ~42h inside a
# service whose TimeoutStartSec is 10800. AutoInfo#596 adds a total budget,
# per-domain batch derivation and newest-first selection. The suite must adopt
# those flags WITHOUT breaking when the checked-out AutoInfo predates them, so
# the flags are emitted only when `nightly_process.py --help` advertises them.
#
# Sourced by `scripts/nightly_batch.sh`; covered by
# `tests/test_nightly_batch_process_budget.py`.

# nightly_budget_args <help-text> <max-seconds> <batch-size> <seconds-per-item>
#
# Prints one argument per line, or nothing when the flags are unsupported.
# An empty batch size (0) leaves the per-domain batch to AutoInfo's own
# fair-share derivation from <max-seconds> / <seconds-per-item>.
nightly_budget_args() {
  local help_text="$1" max_seconds="${2:-0}" batch_size="${3:-0}" per_item="${4:-40}"

  printf '%s\n' "$help_text" | grep -q -- '--max-seconds' || return 0
  printf '%s\n' "$help_text" | grep -q -- '--newest-first' || return 0

  printf '%s\n' "--max-seconds" "$max_seconds" "--newest-first"
  if [ "$batch_size" != "0" ]; then
    printf '%s\n' "--batch-size" "$batch_size"
  fi
  if printf '%s\n' "$help_text" | grep -q -- '--seconds-per-item'; then
    printf '%s\n' "--seconds-per-item" "$per_item"
  fi
}
