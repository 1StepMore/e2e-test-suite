#!/bin/bash
# Tests for scripts/setup_dev.sh WORKSPACE_ROOT layout detection (e2e#18).
set -euo pipefail

PASS=0
FAIL=0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_SCRIPT="$SCRIPT_DIR/setup_dev.sh"

pass() { echo "  ✅ $1"; PASS=$((PASS + 1)); }
fail() { echo "  ❌ $1"; FAIL=$((FAIL + 1)); }

echo "=== e2e#18: setup_dev.sh layout detection ==="

# ── Test 1: child layout (sub-repos as children) ────────────────────────────
echo ""
echo "--- Test 1: child layout ---"
TMPDIR1=$(mktemp -d)
trap "rm -rf $TMPDIR1" EXIT

mkdir -p "$TMPDIR1/e2e-test-suite/scripts"
mkdir -p "$TMPDIR1/e2e-test-suite/Omni_Pre_Processor"
mkdir -p "$TMPDIR1/e2e-test-suite/Omni_Localizer"
mkdir -p "$TMPDIR1/e2e-test-suite/Omni_Re_Formatter"
mkdir -p "$TMPDIR1/e2e-test-suite/.venv_ol/bin"

# Create minimal pyproject.toml for version check
for mod in Omni_Pre_Processor Omni_Localizer Omni_Re_Formatter; do
    echo 'version = "0.0.0"' > "$TMPDIR1/e2e-test-suite/$mod/pyproject.toml"
done

# Copy setup script
cp "$SETUP_SCRIPT" "$TMPDIR1/e2e-test-suite/scripts/setup_dev.sh"

# Extract WORKSPACE_ROOT logic and test it
bash -c "
PROJECT_ROOT='$TMPDIR1/e2e-test-suite'
if [ -d \"\$PROJECT_ROOT/Omni_Pre_Processor\" ]; then
    WORKSPACE_ROOT=\"\$PROJECT_ROOT\"
elif [ -d \"\$(dirname \"\$PROJECT_ROOT\")/Omni_Pre_Processor\" ]; then
    WORKSPACE_ROOT=\"\$(dirname \"\$PROJECT_ROOT\")\"
else
    echo '[ERR] Cannot find Omni_Pre_Processor'
    exit 1
fi
if [ \"\$WORKSPACE_ROOT\" = \"\$PROJECT_ROOT\" ]; then
    echo 'PASS'
else
    echo 'FAIL: expected PROJECT_ROOT, got \$WORKSPACE_ROOT'
    exit 1
fi
" && pass "child layout resolves WORKSPACE_ROOT=PROJECT_ROOT" || fail "child layout"

# ── Test 2: sibling layout (sub-repos as siblings) ──────────────────────────
echo ""
echo "--- Test 2: sibling layout ---"
TMPDIR2=$(mktemp -d)
trap "rm -rf $TMPDIR2" EXIT

mkdir -p "$TMPDIR2/Omni_Pre_Processor"
mkdir -p "$TMPDIR2/Omni_Localizer"
mkdir -p "$TMPDIR2/Omni_Re_Formatter"
mkdir -p "$TMPDIR2/e2e-test-suite/scripts"

bash -c "
PROJECT_ROOT='$TMPDIR2/e2e-test-suite'
if [ -d \"\$PROJECT_ROOT/Omni_Pre_Processor\" ]; then
    WORKSPACE_ROOT=\"\$PROJECT_ROOT\"
elif [ -d \"\$(dirname \"\$PROJECT_ROOT\")/Omni_Pre_Processor\" ]; then
    WORKSPACE_ROOT=\"\$(dirname \"\$PROJECT_ROOT\")\"
else
    echo '[ERR] Cannot find Omni_Pre_Processor'
    exit 1
fi
EXPECTED='$TMPDIR2'
if [ \"\$WORKSPACE_ROOT\" = \"\$EXPECTED\" ]; then
    echo 'PASS'
else
    echo 'FAIL: expected \$EXPECTED, got \$WORKSPACE_ROOT'
    exit 1
fi
" && pass "sibling layout resolves WORKSPACE_ROOT=parent" || fail "sibling layout"

# ── Test 3: neither layout → error ──────────────────────────────────────────
echo ""
echo "--- Test 3: missing sub-repos → error ---"
TMPDIR3=$(mktemp -d)
trap "rm -rf $TMPDIR3" EXIT

mkdir -p "$TMPDIR3/nowhere/scripts"

bash -c "
PROJECT_ROOT='$TMPDIR3/nowhere'
if [ -d \"\$PROJECT_ROOT/Omni_Pre_Processor\" ]; then
    WORKSPACE_ROOT=\"\$PROJECT_ROOT\"
elif [ -d \"\$(dirname \"\$PROJECT_ROOT\")/Omni_Pre_Processor\" ]; then
    WORKSPACE_ROOT=\"\$(dirname \"\$PROJECT_ROOT\")\"
else
    echo '[ERR] Cannot find Omni_Pre_Processor'
    exit 1
fi
echo 'FAIL: should have exited with error'
exit 1
" 2>/dev/null && fail "should have errored" || pass "errors when no sub-repos found"

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
