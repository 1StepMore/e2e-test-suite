#!/usr/bin/env bash
# ============================================================================
# sync_shallow.sh — DEPRECATED stub (submodules were removed in 2026-06-24)
# ============================================================================
# The src/Omni_Pre_Processor, src/Omni_Localizer, src/Omni_Re_Formatter
# git submodules no longer exist. OPP/OL/ORF are now regular top-level
# directories (Omni_Pre_Processor/, Omni_Localizer/, Omni_Re_Formatter/),
# committed directly in this repo's tree.
#
# To "sync" any of them, just `git pull` inside the directory — no submodule
# pointer dance needed:
#   cd Omni_Pre_Processor && git pull origin main
#
# This stub is kept so any cron job or doc that still runs
# `bash scripts/sync_shallow.sh` gets a clear error instead of a confusing
# partial run.
# ============================================================================
set -euo pipefail

echo "ERROR: scripts/sync_shallow.sh is deprecated." >&2
echo "       The src/Omni_*/ submodules were removed; OPP/OL/ORF now live" >&2
echo "       as top-level directories in this repo. To update any of them:" >&2
echo "         cd Omni_<Name> && git pull origin main" >&2
echo "       Then commit the updated files in this repo as usual." >&2
exit 1
