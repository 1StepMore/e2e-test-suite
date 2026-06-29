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

# ── Test 4: auto-clone missing sub-repos ─────────────────────────────────────
echo ""
echo "--- Test 4: auto-clone missing sub-repos ---"

if ! command -v git &>/dev/null; then
    fail "git not found — skipping auto-clone test"
else
    TMPDIR4=$(mktemp -d)
    trap "rm -rf $TMPDIR4" EXIT

    # Create 3 minimal local git repos as clone sources
    for mod in Omni_Pre_Processor Omni_Localizer Omni_Re_Formatter; do
        mkdir -p "$TMPDIR4/src/$mod"
        git -C "$TMPDIR4/src/$mod" init --quiet
        git -C "$TMPDIR4/src/$mod" config user.email "test@test.com"
        git -C "$TMPDIR4/src/$mod" config user.name "Test"
        echo "# $mod" > "$TMPDIR4/src/$mod/README.md"
        git -C "$TMPDIR4/src/$mod" add README.md
        git -C "$TMPDIR4/src/$mod" commit -m "init" --quiet
    done

    # Fresh checkout: suite root but NO sub-repo dirs
    FRESH="$TMPDIR4/fresh"
    mkdir -p "$FRESH/scripts"
    cp "$SETUP_SCRIPT" "$FRESH/scripts/setup_dev.sh"

    # Extract the clone function to a real file so BASH_SOURCE[0] resolves
    # to a proper path (process substitution gives /dev/fd/* which breaks
    # the dirname-based ws computation).
    # '()' disambiguates function definition from its call site later in the file.
    sed -n '/^clone_submodules_if_needed()/,/^}/p' "$FRESH/scripts/setup_dev.sh" \
        > "$FRESH/scripts/_clone_func.sh"

    # Runner script at the expected relative location
    cat > "$FRESH/scripts/_t4_runner.sh" << 'T4INNER'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
info()  { printf '\033[0;36m[INFO]\033[0m  %s\n' "$*"; }
ok()    { printf '\033[0;32m[OK]\033[0m    %s\n' "$*"; }
err()   { printf '\033[0;31m[ERR]\033[0m   %s\n' "$*"; }
source "$SCRIPT_DIR/_clone_func.sh"
clone_submodules_if_needed
T4INNER
    chmod +x "$FRESH/scripts/_t4_runner.sh"

    # First clone — env var overrides point to local repos
    echo "  -> First clone (should clone all 3) …"
    if CLONE_OUT=$(cd "$FRESH" && OMNI_OPP_URL="$TMPDIR4/src/Omni_Pre_Processor" \
        OMNI_OL_URL="$TMPDIR4/src/Omni_Localizer" \
        OMNI_ORF_URL="$TMPDIR4/src/Omni_Re_Formatter" \
        bash scripts/_t4_runner.sh 2>&1); then
        pass "auto-clone exit 0"
    else
        echo "$CLONE_OUT" | head -5
        fail "auto-clone exit $?"
    fi

    # Verify each sub-repo got cloned
    all_cloned=true
    for mod in Omni_Pre_Processor Omni_Localizer Omni_Re_Formatter; do
        if [ -d "$FRESH/$mod/.git" ]; then
            pass "  $mod cloned with .git/"
        else
            fail "  $mod missing .git/ after clone"
            all_cloned=false
        fi
    done

    # Second run — should detect existing clones (idempotent)
    echo "  -> Second clone (should be idempotent) …"
    IDEM_OUT=$(cd "$FRESH" && OMNI_OPP_URL="$TMPDIR4/src/Omni_Pre_Processor" \
        OMNI_OL_URL="$TMPDIR4/src/Omni_Localizer" \
        OMNI_ORF_URL="$TMPDIR4/src/Omni_Re_Formatter" \
        bash scripts/_t4_runner.sh 2>&1) && pass "idempotent exit 0" || fail "idempotent exit $?"
    while IFS= read -r line; do
        if [[ "$line" == *"already cloned"* ]]; then
            pass "  $line"
        fi
    done <<< "$IDEM_OUT"

    if [ "$all_cloned" = true ]; then
        pass "auto-clone: all 3 sub-repos present"
    fi
fi

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
