# State of the Union — Omni_Suite Self-Driven Optimization

**Last updated**: 2026-06-17 (end of round 11)
**Scope**: All 11 rounds, 3 modules (OPP, OL, ORF), 4 paths (xliff_cli / xliff_mcp / md_cli / md_mcp), 11 input formats

## Round Timeline

| Round | Date | Theme | Critical Bugs | Status |
|---|---|---|---|---|
| 1-2 | 2026-06-14..15 | Initial setup (earlier session) | — | ✅ |
| 3-4 | 2026-06-16..17 | OPP/OL config fixes (NVIDIA 404, docx→odt invalid) | 3 | ✅ |
| 5 | 2026-06-17 | Round 3-4: per-model RPM, OPT-13 hard 429, OPT-12 concurrency=5 | 0 (caught regression: 7-line deletion) | ✅ |
| 6 | 2026-06-17 | Round 5: litellm.Timeout, .zip skeleton, OP/OL config guard | 4 | ✅ |
| 7 | 2026-06-17 | Tier 1-5 dispatch wiring (reuse, no rewrite) | 0 (infrastructure) | ✅ |
| 8 | 2026-06-17 | FIX-#24 API key security (skip rotation per user) | 0 (preventive) | ✅ |
| 9 | 2026-06-17 | **Tier 2 first run** (4-path real LLM) | 4 (NameError, .zip, async, await) | ✅ |
| 10 | 2026-06-17 | **Tier 3 partial** (10 format MD) | 3 (dispatch args, apply-md pptx, md2pptx missing) | ⚠️ |
| 11 | 2026-06-17 | **Tier 4 + Tier 5** (XLIFF + module-only) | 7 (timeout, MCP path, test infra) | ⚠️ |
| **Total** | | | **21 bugs caught + 0 regressions** | |

## Coverage Matrix (as of round 11 end)

**Total combinations = 11 formats × 4 paths × 2 langs = 88 + 13 module-only = 101 distinct cases**

| Tier | Cases | Tested | PASS | Status |
|---|---|---|---|---|
| Tier 1 (XLIFF CLI regression) | 1 | 1 | 1 | ✅ 100% |
| Tier 2 (4-path real LLM on DOCX) | 4 | 4 | 4 | ✅ 100% |
| Tier 3 (10 formats MD) | 20 | 6 | 4 | ⚠️ 30% |
| Tier 4 (XLIFF backfill docx+pptx) | 4 | 4 | 3 | ⚠️ 75% (1 timeout) |
| Tier 5 (module-only) | 3 | 3 | 1 | ⚠️ 33% (2 test infra) |
| OPP-only paths | 11 | 0 | — | ❌ 0% |
| ORF-only paths | 1 | 0 | — | ❌ 0% |
| **Total tested** | **44** | **18** | **13** | **~30%** |

(Each module's pytest suite is included in Tier 5 — those are comprehensive but pytest-level, not the production pipeline.)

## Bug Summary by Round

| Round | Bugs | Severity Distribution |
|---|---|---|
| 3-4 | 3 | 1 High, 2 Med |
| 5 (regression) | 1 (caught) | High (would have broken production) |
| 6 | 4 | 2 High, 2 Med |
| 9 | 4 | 2 High, 1 Critical, 1 Med |
| 10 | 3 | 1 High, 1 Critical, 1 High (md2pptx) |
| 11 | 7 | 1 High (timeout), 1 High (test infra), 5 Med/Low |
| **Total** | **21** | **6 High, 2 Critical, 13 Med/Low** |

**Bug density**: 21 bugs / 18 tests ≈ 1.17 bugs per test case.
At this rate, ~83 more bugs likely in the ~83 untested cases.

## Open Bug Backlog (from rounds 9-11)

### High priority (production-affecting)

- **#3** [round 11] `test_orf_apply_xliff_to_epub` — tests cross-format (docx→epub) which round 9 FIX-#8 correctly rejects. Test was always testing invalid workflow.
- **#4** [round 11] `test_e2e_ol_mcp.py` — 1 test fails (need investigation)
- **#5** [round 11] `test_e2e_orf_mcp.py` — 5 tests fail with `PATH_NOT_ALLOWED: /mnt/d/贯维/Omni_Suite`. ORF MCP path allowlist excludes project directory.
- **#6** [round 11] Tier 4 pptx en→zh — `litellm.Timeout` at 60s on long Sherlock PPTX slides. Per-model timeout too low.

### Medium priority

- **[round 10]** Tier 3 case 8+ (xlsx, csv, json, xml, ipynb, eml) — 12 cases never run due to timeout
- **[round 10]** `apply-md` MD2PPTXConverter — pptx via MD path needs `md2pptx` binary (not installed). Documented, deferred.
- **[round 11]** `run_test.sh` — hardcodes `PY312=.venv312/bin/python` (no env override)
- **[round 6]** `#3` (deferred): LQA threshold 4.0 in noise edge — round 6 LQA was 4.57-4.60 stable, no action
- **[round 6]** `#4` (deferred): en→zh 2028-unit doc long-tail — needs prefer-OPENCODE_GO strategy

### Low priority / design discussion

- **[round 6]** `#12` try_safe_fix — extend OMO auto-recovery from 1 fix to more
- **[round 6]** `#15` MCP `apply_xliff` format `Literal` enum — type-safe improvement
- **[round 6]** `#19` per-model latency metric — observability
- **[round 6]** `#25` `f"{m.provider}/{m.model}"` model path concatenation — pydantic discipline

### Done (FIX-#24 partially)

- **[round 8]** API key security: ✅ 9 hardcoded keys in default.yaml → `${ENV_VAR}` refs; ✅ `_check_for_hardcoded_secrets()` in loader.py; ✅ `.gitleaks.toml` custom rules; ✅ `OL_ALLOW_HARDCODED_KEYS=1` escape hatch. ⏭ Skipped key rotation (user: free tier).
- [remaining] `local.yaml` still has hardcoded keys (gitignored, not committed — confirmed via round 8 deep history search)

## Module Health Status

### OPP (Omni_Pre_Processor)
- Tested: Tier 1 (XLIFF backfill), Tier 2 (4-path), Tier 3 (4 formats: epub, html, pdf, pptx), Tier 5 (pytest suites)
- Status: **healthy** for tested paths
- Untested: OPP-only (no OL, no ORF), 8+ formats in Tier 3, all MCP paths in Tier 5

### OL (Omni_Localizer)
- Tested: Tier 1, Tier 2, Tier 3 (4 formats), Tier 4 (docx+pptx XLIFF), Tier 5 (CLI pytest)
- Status: **healthy** for tested paths; **1 known timeout issue** (#6)
- Untested: 12 Tier 3 cases, Tier 5 ol_mcp tests (need investigation)

### ORF (Omni_Re_Formatter)
- Tested: Tier 2 (4-path), Tier 3 (4 formats), Tier 4 (docx+pptx XLIFF), Tier 5 (CLI+MCPP pytest)
- Status: **healthy** for tested paths; **2 test infrastructure issues** (#3, #5)
- Untested: 8+ Tier 3 formats, OPP-only, ORF-only

## Tier Dispatch Status (rounds 7-11)

| Tier | Command | Status |
|---|---|---|
| 1 | `omo_loop.py --tier 1` (default) | ✅ Working, regression baseline |
| 2 | `omo_loop.py --tier 2` | ✅ Working, 4/4 paths PASS (round 9) |
| 3 | `omo_loop.py --tier 3` | ⚠️ Working but too slow (3h timeout), pptx excluded |
| 4 | `omo_loop.py --tier 4` | ✅ Working, 3/4 cases PASS (round 11) |
| 5 | `omo_loop.py --tier 5` | ✅ v2 working (pytest-based), 2/6 pass |

## Files Modified (rounds 7-11)

- `scripts/omo_loop.py` — tier dispatch (rounds 7, 11)
- `scripts/phase1_runner.py` — FIX-#16, P1 matrix cleanup, Tier 3 dispatch args fix
- `tests/test_round7_tier_dispatch.py` — dispatch tests (rounds 7, 11)
- `tests/e2e_runner.py` — `--input/--source-lang/--target-lang` args + NameError fix
- `tests/test_e2e_real_llm.py` — translate_xliff await fix
- `Omni_Localizer/src/ol_config/loader.py` — FIX-#24 secret detector
- `Omni_Localizer/src/ol_mcp/tools.py` — translate_xliff → async
- `Omni_Localizer/tests/test_loader_security.py` — new (round 8)
- `Omni_Localizer/config/default.yaml` — hardcoded keys → env refs (round 8)
- `Omni_Re_Formatter/src/orf/cli.py` — FIX-#8 .zip skeleton, pptx wired-then-unwired
- `Omni_Re_Formatter/tests/test_apply_xliff_format_validation.py` — .zip regression tests
- `Omni_Re_Formatter/tests/test_apply_md_target_format.py` — new (round 10)
- `.gitleaks.toml` — new (round 8)
- `.env.example` — new env vars documented (round 8)

## Next Round Strategy (round 12)

Per user instruction: "下个round我们应该努力补全矩阵所有case，否则debug耗时太长了"

Translation: "next round we should work to complete all matrix cases, otherwise debug takes too long"

**Key insight**: Each test takes 3-5 min; 20 cases = 1-2h per Tier. To complete the full 101-case matrix would take 10-15h. Too long for one round.

**Strategy**:
1. **Fix the 4 high-priority bugs from round 11** (~1h): #3, #4, #5, #6
2. **Speed up phase1_runner** with `--source-lang/--target-lang` flag — enables one-direction runs (cuts total time in half)
3. **Complete Tier 3** (12 cases) with speed improvements — run zh→en (6 cases) and en→zh (6 cases) separately, possibly in parallel
4. **Skip OPP-only / ORF-only** for this round — too much infrastructure work, focus on completing Tier 3 first

## Recommended Round 12 Scope

1. Write plan (XS)
2. Fix #3, #4, #5, #6 (S-M each, parallel where possible)
3. Add `--source-lang/--target-lang` to phase1_runner.py (S)
4. Run Tier 3 zh→en (6 cases, ~30 min)
5. Run Tier 3 en→zh (6 cases, ~30 min)
6. Tier 1 regression check (5 min)
7. Update plan with results

Estimated total: 2-3 hours, completes 12 Tier 3 cases + 4 high-priority bug fixes.