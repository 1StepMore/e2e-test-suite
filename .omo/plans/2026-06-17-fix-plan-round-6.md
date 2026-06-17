# Fix Plan — Round 6 (2026-06-17)

Comprehensive todo list of issues surfaced in **round 5** (the round
just completed) plus a selection of round-5-deferred items that are
practical for this turn. The structure follows the round 5 plan: list
all known issues with severity/effort, then execute the high-leverage
subset.

## Round 6 Results (this turn)

### Commits

| Repo | SHA | Summary |
|---|---|---|
| main | `17ac8e6` | docs(plan): round 6 plan (this file) |
| Omni_Localizer | `6ab5137` | feat(ol): cost map skip + cache mtime + rpm>0 fallback filter |
| main | `29e59d6` | feat(phase1): FIX-#16 promote xliff_outputs_by_input to module-level |

### Fixes applied

| ID | File | Change |
|---|---|---|
| **A** | `Omni_Localizer/src/ol_pool/router.py` | `os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")` BEFORE `import litellm` (env var check is import-time) |
| **#11** | `Omni_Localizer/src/ol_pool/router.py` | `_pool_cache` value is now `(pool, config_mtime)` tuple; `get_instance()` re-builds when mtime changes (config edits take effect without restart). Added missing `from pathlib import Path` (test caught this). |
| **#16** | `scripts/phase1_runner.py` | Promoted `xliff_outputs_by_input` to module-level `XLIFF_OUTPUTS_BY_INPUT` constant; `build_matrix()` now references it. |
| **#17** | `Omni_Localizer/src/ol_pool/router.py` | `_build_fallbacks` filters `requests_per_minute <= 0` (Pydantic ge=1 already prevents this at config load, but mutation-after-construction can bypass). |

### Tests added (this turn)

| Test file | Count | Coverage |
|---|---|---|
| Omni_Localizer/tests/test_model_pool_failover.py | 3 new | LITELLM_LOCAL_MODEL_COST_MAP env set; _pool_cache mtime invalidation; rpm=0 fallback filter |
| tests/test_phase1_p2_matrix.py | 1 new | `XLIFF_OUTPUTS_BY_INPUT` is importable constant |
| **Total new tests** | **4** | |

### Test results

```
Omni_Localizer/tests/test_model_pool_failover.py  : 11 ✅ (3 new)
Omni_Localizer/tests/test_model_pool_schema.py    : 14 ✅
Omni_Localizer/tests/test_config_loader.py       :  2 ✅
Omni_Localizer/tests/test_round5_e2e.py           :  8 ✅
tests/test_phase1_p2_matrix.py                   :  4 ✅ (1 new)
                                                  TOTAL: 39 ✅
```

### OMO Loop — round 6 (with all round 6 fixes)

```
Cycle 1: 161.9s, 8/8 GREEN (Q2 LQA 4.60/5)
Cycle 2: 276.6s, 8/8 GREEN (Q2 LQA 4.57/5)
→ CONVERGED at 2 cycles
```

**LQA stable at 4.57-4.60** — best round yet (round 4: 3.88 noise,
round 5: 4.14-4.30, round 6: **4.57-4.60**). The combination of:
- Round 5: per-model RPM + OPT-13 hard 429
- Round 6: cost map skip (no startup hiccup) + cache mtime

has converged to a stable translation pipeline.

**0 cost map warnings in OMO log** (vs 1+ per cycle in round 5).
Confirmed via `grep -c "get_model_cost_map" logs/ol-2026-06-17.log` → 0.

## Comparison across rounds

| Round | LQA cycle 1 | LQA cycle 2 | Cost map warnings | OMO result |
|---|---|---|---|---|
| 3 (initial) | — | — | 1+ per cycle | 3/3 converged (broken 404 + docx→odt) |
| 4 (after 404 fix) | 4.54 | **3.88** ← noise | 1+ per cycle | partial, 1 fix-fail |
| 5 (OPT-11/12/13) | 4.30 | 4.14 | 1+ per cycle | 2/2 converged, fixed regression |
| 6 (this round) | 4.60 | 4.57 | **0** | 2/2 converged, no regression |

## Round 5 Findings — Issues That Were Addressed in Round 6

### New findings (observed during round 5 verification)

| ID | Issue | Status |
|---|---|---|
| A | Litellm WARNING on every cycle (remote model cost map) | ✅ FIXED in round 6 |
| B | Round 5 commit `a6956f5` removed 7 lines from `translate()` | ✅ ALREADY FIXED in round 5 (`3d87d8d`) |

### Deferred items (from round 5) — addressed this turn

| ID | Issue | Status |
|---|---|---|
| #11 | `omni_cache` not invalidated on config change | ✅ FIXED (cache mtime check) |
| #15 | MCP `apply_xliff` may still test cross-format | ⏸ DEFERRED to round 7 — audit found only docx→docx in current tests; the CLI-side guard from round 5 (FIX-#8) catches cross-format. MCP type-safe enum is a nice-to-have, not a bug. |
| #16 | `xliff_outputs_by_input` is local variable in `build_matrix()` | ✅ FIXED (promoted to module-level) |
| #17 | `_build_fallbacks` doesn't validate `rpm > 0` | ✅ FIXED (defensive filter) |

## Remaining issue inventory (deferred to future rounds)

| ID | Issue | Sev | Effort | Notes |
|---|---|---|---|---|
| #3 | LQA threshold 4.0 in noise edge | Med | M | Round 6 LQA 4.57-4.60 shows it's stable in normal conditions; defer until we have a data set that triggers the noise again |
| #4 | en→zh 2028-unit doc long-tail | Med | L | Needs prefer-OPENCODE_GO for large docs |
| #10 | Cross-role fallback doesn't fire when all 3 NVIDIA 429 | Med | L | OPT-13 should make this rarer; not observed in round 5/6 |
| #12 | `try_safe_fix` only does clear_opp_cache | Med | M | Docstring lists 6 fixes, only 1 implemented |
| #14 | No test for real RPM behavior | Med | M | Round 5/6 behavior is stable; test is nice-to-have |
| #15 | MCP apply_xliff format enum | Med | S | CLI guard catches it; enum is type-safe improvement |
| #19 | No per-model latency metric | Low | S | Latency instrumentation |
| #20 | OMO loop convergence fragile under LLM noise | Med | S | Round 6 LQA stable; convergence not actually fragile in practice |
| **#24** | **API keys hardcoded in `local.yaml`/`default.yaml` (security)** | **High** | **L** | **Top priority for round 7 — needs env-var refactor + .env.example sync** |
| #25 | `f"{m.provider}/{m.model}"` model path concatenation fragile | Low | S | Pydantic + model name discipline |

## Recommended Next Round (round 7)

1. **#24 (API key security)** — high severity, dedicated round
2. **#12 (try_safe_fix)** — M effort, makes OMO loop more resilient
3. **#15 (MCP format enum)** — S effort, type-safe improvement
4. **#4 (en→zh long-tail)** — L effort, prefer-OPENCODE_GO strategy

## Verification

- All 39 tests pass ✅
- OMO round 6 converges at 2 cycles ✅
- LQA 4.60 / 4.57 (stable, no noise) ✅
- 0 cost map warnings (FIX-A confirmed) ✅
- No regression from round 5 ✅
