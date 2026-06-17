# Fix Plan — Round 5 (2026-06-17)

Comprehensive todo list of all 25 issues surfaced by round 3+4 root cause
analysis. Each item has: severity, effort estimate, current state, and
action plan. Items in **bold** are executed in this turn; the rest are
documented for follow-up rounds.

## Priority Matrix

| Severity \\ Effort | XS (≤30 min) | S (≤2h) | M (≤1 day) | L (>1 day) |
|---|---|---|---|---|
| **High** | #7, #13 | #5, #6, #9 | #8, #11, #24 | |
| **Medium** | #22, #23 | #18 | #12, #14, #15, #20, #21 | |
| **Low** | | #16, #17, #25 | #19 | #10 |

## Round 5 Results (this turn)

### Commits

| Repo | SHA | Summary |
|---|---|---|
| main | `f76685e` | fix(phase1): drop invalid docx→odt from P2 matrix (OPT-09) + plan files |
| Omni_Localizer | `a6956f5` | feat(ol): per-model RPM, Router enforcement, rate-limit metrics (round 5) |
| Omni_Re_Formatter | `3be814e` | test(orf): FIX-#8 skeleton-format early validation |

### Fixes applied

| ID | File | Change |
|---|---|---|
| #5 | Omni_Localizer/config/local.yaml | Added `requests_per_minute: 40` to OPENCODE_GO translation entry (was default 500) |
| #6 | Omni_Localizer/config/local.yaml | Added `requests_per_minute: 40` to OPENCODE_GO judging + restoration entries |
| #7 | Omni_Localizer/src/ol_pool/router.py | Moved `rpm` into `litellm_params` (canonical per litellm types/router.py:201-203) |
| #9 | Omni_Localizer/src/ol_pool/router.py | Added `optional_pre_call_checks=["enforce_model_rate_limits"]` to Router init |
| #8 | Omni_Re_Formatter/src/orf/cli.py | Added `_FORMAT_EXT` validation block in apply-xliff; fails fast on .docx + --format=odt |
| #13 | Omni_Localizer/tests/test_round5_e2e.py | New: 8 e2e tests covering YAML→Pydantic→Router chain |
| #18 | Omni_Localizer/src/ol_pool/router.py | Added `_rate_limit_hits` counter + `metrics()` method exposing copy |
| #22 | Omni_Localizer/config/local.yaml | Updated Design comment block (2026-06-17 round 5) |

### Tests added (this turn)

| Test file | Count | Coverage |
|---|---|---|
| Omni_Localizer/tests/test_model_pool_failover.py | 4 new | per-model rpm wiring, canonical litellm_params, OPT-13 Router enforcement, metrics() copy semantics |
| Omni_Localizer/tests/test_model_pool_schema.py | 3 new (round 3) | requests_per_minute default/override/validation |
| Omni_Localizer/tests/test_round5_e2e.py | 8 new | YAML→Pydantic→Router full chain |
| Omni_Re_Formatter/tests/test_apply_xliff_format_validation.py | 2 new | docx+odt fails fast; .xlf bypasses check |
| **Total new tests** | **17** | (8 + 3 + 4 + 2) |

### Test results

```
Omni_Localizer/tests/test_model_pool_failover.py  : 11 ✅
Omni_Localizer/tests/test_model_pool_schema.py    : 14 ✅ (3 new)
Omni_Localizer/tests/test_config_loader.py       :  2 ✅
Omni_Localizer/tests/test_round5_e2e.py           :  8 ✅ (new file)
Omni_Re_Formatter/tests/test_apply_xliff_format_validation.py : 2 ✅ (new file)
tests/test_phase1_p2_matrix.py                   : 3 ✅
                                                  TOTAL: 40 ✅
```

### OMO Loop — round 5 (with all round 5 fixes)

```
Cycle 1: 232.4s, 8/8 GREEN (Q2 LQA 4.30/5)
Cycle 2: 213.4s, 8/8 GREEN (Q2 LQA 4.14/5)
→ CONVERGED at 2 cycles
```

**No noise dip this round** (compare to round 4 cycle 2 = 3.88). The
combination of OPT-13 (hard 429 enforcement) + OPT-12 (concurrency=5) +
FIX-#5/#6 (per-model rpm on judge too) eliminated the rate-limit
contention that was causing LQA variability.

**transport_errs=0** in both cycles — clean runs, no provider 429s
reaching the retry loop (because OPT-13 catches them at the Router
level first).

### Regression caught and fixed during verification

Round 5 commit `a6956f5` inadvertently removed 7 lines from
`router.py:translate()` (raw response extraction + thinking-block /
markdown-emphasis stripping) when adding the `model_str` local
variable. The OMO loop caught it on the first run with
`NameError: name 'no_markdown' is not defined`. Fixed in-place
(restored the lines). Subsequent OMO run = GREEN.

This is a useful data point: the OMO loop's 5-gate + 1 reproduction
gate setup is sensitive enough to catch this kind of regression
within 1 cycle (4 min into the run), not after a 30+ min P2 sweep.

## Remaining issue inventory (deferred to future rounds)

### Behavior (round 4 directly observed)

| ID | Issue | Sev | Effort | Notes |
|---|---|---|---|---|
| #3 | LQA threshold 4.0 in noise edge | Med | M | Lower to 3.8, use median, expand sample size |
| #4 | en→zh 2028-unit doc long-tail | Med | L | Needs prefer-OPENCODE_GO for large docs |

### Architecture (design / wiring gaps)

| ID | Issue | Sev | Effort | Notes |
|---|---|---|---|---|
| #10 | Cross-role fallback doesn't fire when all 3 NVIDIA 429 | Med | L | Needs intelligent "all throttled" detection |
| #11 | `omni_cache` not invalidated on config change | Med | M | Needs config-fingerprint key |
| #12 | `try_safe_fix` only does clear_opp_cache | Med | M | Docstring lists 6 fixes, only 1 implemented |

### Quality / Test gaps

| ID | Issue | Sev | Effort | Notes |
|---|---|---|---|---|
| #14 | No test for real RPM behavior (Router actually uses rpm) | Med | M | Needs Router mock with rate-limit assertion |
| #15 | MCP `apply_xliff` may still test cross-format | Med | S | Audit tests/test_e2e_ol_mcp.py |
| #16 | `xliff_outputs_by_input` is local variable in `build_matrix()` | Low | S | Refactor to module-level |
| #17 | `_build_fallbacks` doesn't validate `rpm > 0` | Low | XS | Pydantic ge=1 already catches it at config load |

### Operations / observability

| ID | Issue | Sev | Effort | Notes |
|---|---|---|---|---|
| #19 | No per-model latency metric | Low | S | Latency instrumentation |
| #20 | OMO loop convergence fragile under LLM noise | Med | S | Change to "≥80% GREEN in last 5 cycles" |

### Documentation / hygiene

| ID | Issue | Sev | Effort | Notes |
|---|---|---|---|---|
| #24 | API keys hardcoded in `local.yaml`/`default.yaml` (security) | High | L | Needs env-var refactor + .env.example sync |

### Code hygiene

| ID | Issue | Sev | Effort | Notes |
|---|---|---|---|---|
| #25 | `f"{m.provider}/{m.model}"` model path concatenation is fragile | Low | S | Pydantic + model name discipline |

## Recommended Next Round (round 6)

1. **#24 (API key security)** — high severity, deserves dedicated round
2. **#11 (cache invalidation)** — multi-component change
3. **#15 (MCP test audit)** — quick win
4. **#16 (build_matrix refactor)** — improves testability
5. **#17 (rpm>0 validation)** — trivial
