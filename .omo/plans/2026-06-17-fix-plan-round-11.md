# Fix Plan — Round 11 (2026-06-17) — Tier 4 + Tier 5

## Goal

Run the two **never-tested** tiers:
- **Tier 4**: XLIFF backfill matrix (4 cases: docx+pptx × 2 langs)
- **Tier 5**: Module-only via `run_test.sh --module {opp,ol,orf}` (3 cases)

## Why This Round

Coverage analysis (round 10):
- Tier 1: 1/1 (100%)
- Tier 2: 4/4 (100%)
- Tier 3: 6/20 (30% — 4 PASS, 2 RED, 12 not run)
- **Tier 4: 0/4 (0% — never run)**
- **Tier 5: 0/3 (0% — never run)**
- Total: 11/101 = 10.9% tested

Round 9 caught 4 bugs in Tier 2. Round 10 caught 3 bugs in partial Tier 3.
**Bug density ~0.64 bugs/case** → ~57 more bugs likely in 90 untested cases.

The two untested tiers are highest-risk (never validated). Round 11
fixes that.

## Tier 4 (4 cases, ~20-30 min real LLM)

```
[P2] docx XLIFF→docx zh→en
[P2] docx XLIFF→docx en→zh
[P2] pptx XLIFF→pptx zh→en   ← uses apply-xliff + XLIFF2PPTXConverter (no md2pptx binary needed)
[P2] pptx XLIFF→pptx en→zh
```

Verifies the **round 9 FIX-#8** (.zip skeleton accepted) still works
and the XLIFF backfill path is healthy across both formats.

## Tier 5 (3 cases, ~15-30 min shell-driven)

```
run_test.sh --module opp   # OPP extraction only
run_test.sh --module ol    # OL translation only (skips opp, orf)
run_test.sh --module orf   # ORF backfill only (skips opp, ol)
```

Verifies each module can run **independently** in production-like
shell flow. This is the user's "3个模块都没有bug" verification path.

## Pre-flight (done)

- Tier 4 dispatch: `omo_loop.py _run_tier_4` correctly invokes
  `phase1_runner.py --tier P2 --run-id ...` (round 10 fix)
- Tier 5 dispatch: `omo_loop.py _run_tier_5` calls
  `run_test.sh --module {opp,ol,orf}` correctly
- **Pre-existing issue found**: `run_test.sh` hardcodes
  `PY312=$SUITE_DIR/.venv312/bin/python` but only `.venv_ol` exists.
  **Fix**: pass `PY312=$SUITE_DIR/.venv_ol/bin/python` in env when
  invoking run_test.sh. (Or update run_test.sh to default to .venv_ol.)

## Scope

### Step 1 — Plan + commit (XS)

### Step 2 — Pre-flight fixes (S)
- Update `omo_loop.py _run_tier_5` to pass `PY312=.venv_ol/bin/python`
- Add regression test for tier dispatch args

### Step 3 — Run Tier 4 (20-30 min)
```
OL_ALLOW_HARDCODED_KEYS=1 .venv_ol/bin/python scripts/omo_loop.py \
    --tier 4 --source-lang zh --target-lang en
```

### Step 4 — Run Tier 5 (15-30 min)
```
OL_ALLOW_HARDCODED_KEYS=1 .venv_ol/bin/python scripts/omo_loop.py \
    --tier 5 --source-lang zh --target-lang en
```

### Step 5 — Analyze + fix critical bugs

### Step 6 — Update plan + commit

## Expected Bugs to Find

Based on density (0.64 bugs/case), 7 untested cases likely surface
4-5 bugs. Most likely categories:
- **Tier 4**: XLIFF backfill path edge cases (round 9 FIX-#8 might
  have edge cases in en→zh direction, pptx might have converter
  issues that DOCX doesn't)
- **Tier 5**: Each module's standalone invocation may have different
  env / PYTHONPATH / config issues vs the in-loop integration

## Risk

- Tier 4 may have slow pptx en→zh (~50 min observed in Tier 3)
- Tier 5 with broken PY312: if override doesn't work, fall back
  to in-process tests

## Verification

- All 7 cases (Tier 4: 4, Tier 5: 3) execute
- Tier 1 still GREEN
- Tier 2 still GREEN
- Existing tests pass

## What This Round is NOT

- Not running Tier 3 (12 unfinished cases) — Round 12
- Not running OPP-only / ORF-only — Round 12-13
- Not modifying any OPP/OL/ORF code unless a bug is found

## Recommended Next Round (round 12)

1. **Complete Tier 3** (12 cases for xlsx, csv, json, xml, ipynb, eml
   × 2 langs). May need to add `--source-lang/--target-lang` to
   phase1_runner for one-direction parallel runs.
2. **Speed up phase1_runner** for batch regression.
3. **#24 API key security** (still pending from round 8).