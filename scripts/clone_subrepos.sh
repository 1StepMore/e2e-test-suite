#!/usr/bin/env bash
# =============================================================================
# Clone 3 sub-repos (Omni_Pre_Processor, Omni_Localizer, Omni_Re_Formatter)
# for CI environments where the sub-repos are not present.
#
# Each sub-repo is a full git repo (not a git submodule). The parent suite's
# .gitignore excludes them, so `actions/checkout@v4` does NOT bring them
# into the CI working tree. CI workflows must run this script before
# `uv sync` or any test that imports `opp` / `ol_mcp` / `orf`.
#
# URLs can be overridden via env vars:
#   OMNI_OPP_URL, OMNI_OL_URL, OMNI_ORF_URL
#
# Versions can be pinned via env vars (default: branch=main):
#   OMNI_OPP_REF, OMNI_OL_REF, OMNI_ORF_REF
#   (any git ref: branch, tag, or SHA)
#
# Usage: bash scripts/clone_subrepos.sh
# =============================================================================
set -euo pipefail

ws="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

declare -a subs=(
    "Omni_Pre_Processor|${OMNI_OPP_URL:-https://github.com/1StepMore/Omni_Pre_Processor.git}|${OMNI_OPP_REF:-main}"
    "Omni_Localizer|${OMNI_OL_URL:-https://github.com/1StepMore/Omni_Localizer.git}|${OMNI_OL_REF:-main}"
    "Omni_Re_Formatter|${OMNI_ORF_URL:-https://github.com/1StepMore/Omni_Re_Formatter.git}|${OMNI_ORF_REF:-main}"
)

for entry in "${subs[@]}"; do
    IFS='|' read -r name url ref <<< "$entry"
    target="$ws/$name"
    if [[ -d "$target/.git" ]]; then
        echo "[OK]    $name already cloned at $target"
        continue
    fi
    # Remove the (gitignored) directory if it's an empty stub from checkout
    if [[ -d "$target" ]]; then
        rm -rf "$target"
    fi
    echo "[INFO]  Cloning $name from $url (ref=$ref)"
    if ! git clone --depth 1 --branch "$ref" "$url" "$target"; then
        echo "[ERR]   Failed to clone $name. Run manually:"
        echo "        git clone --depth 1 --branch $ref $url $target"
        exit 1
    fi
    echo "[OK]    $name cloned"
done
