# Fix Plan — Round 6 (2026-06-17)

Comprehensive todo list of issues surfaced in **round 5** (the round
just completed) plus a selection of round-5-deferred items that are
practical for this turn. The structure follows the round 5 plan: list
all known issues with severity/effort, then execute the high-leverage
subset.

## Round 5 Findings — Issues to Address in Round 6

### New findings (observed during round 5 verification)

| ID | Issue | Sev | Effort | Source |
|---|---|---|---|---|
| **A** | **Litellm WARNING on every cycle: "Failed to fetch remote model cost map from https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"** | **Med** | **XS** | OMO log spam (non-fatal, falls back to local). Needs env var / config to disable. |
| B | Round 5 commit `a6956f5` inadvertently removed 7 lines from `translate()` (raw/translated/no_markdown extraction). Caught and fixed in `3d87d8d`. | High | — | Already resolved. Documented for future regression baseline. |

### Deferred items (from round 5) — picking practical ones for round 6

| ID | Issue | Sev | Effort | Action this turn |
|---|---|---|---|---|
| **#11** | **`omni_cache` not invalidated on config change** (model pool / max_xliff change) | Med | M | Fix — add config-fingerprint to cache key |
| **#15** | **MCP `apply_xliff` may still test cross-format** | Med | S | Fix — audit + fix |
| **#16** | **`xliff_outputs_by_input` is local variable in `build_matrix()`** (hard to test) | Low | S | Fix — refactor to module-level |
| **#17** | **`_build_fallbacks` doesn't validate `rpm > 0`** (but Pydantic ge=1 catches at config load) | Low | XS | Fix — defensive check |

### Deferred items NOT addressed this turn (still backlog)

| ID | Issue | Why deferred |
|---|---|---|
| #3 | LQA threshold 4.0 in noise edge | Needs design discussion (lower to 3.8, use median, expand sample) |
| #4 | en→zh 2028-unit doc long-tail | Needs prefer-OPENCODE_GO for large docs (architectural) |
| #10 | Cross-role fallback doesn't fire when all 3 NVIDIA 429 | Needs intelligent "all throttled" detection (L effort) |
| #12 | `try_safe_fix` only does clear_opp_cache | Docstring lists 6 fixes, only 1 implemented (M) |
| #14 | No test for real RPM behavior | Needs Router mock with rate-limit assertion (M) |
| #19 | No per-model latency metric | Needs timing instrumentation (S) |
| #20 | OMO loop convergence fragile under LLM noise | Needs ≥80% GREEN in last 5 cycles (S, design) |
| #24 | API keys hardcoded in `local.yaml`/`default.yaml` | Needs env-var refactor + .env.example + key rotation (L, security review) |
| #25 | `f"{m.provider}/{m.model}"` model path concatenation fragile | Needs pydantic + model name discipline (S) |

## Round 6 Execution Plan

1. **Plan file (this file)** — done.
2. **Commit** — `2026-06-17-fix-plan-round-6.md` to main repo.
3. **Apply fixes** (this turn's high-leverage subset):
   - **A**: Disable litellm remote cost map fetch (env var or config).
   - **#16**: Promote `xliff_outputs_by_input` to module-level constant
     in `phase1_runner.py`. Improves testability and matches the pattern
     of `XLIFF_PATH_OUTPUTS`.
   - **#15**: Audit MCP `apply_xliff` tests for cross-format usage; fix
     any that pass a DOCX skeleton with `--format=odt`.
   - **#17**: Add defensive check in `_build_fallbacks` (skips models
     with `requests_per_minute=0`).
4. **Tests** — extend existing test files; verify all pass.
5. **Commit round 6** as separate commits.
6. **Run new loop**:
   - OMO loop (1-2 cycles, regression check + cost map warning gone).
   - Document any new findings.
7. **Update plan** with results.

## Verification Targets

- All existing tests pass.
- New round 6 tests pass.
- OMO loop converges within 2 cycles.
- LQA scores in 4.0-4.7 range (no noise dip).
- No `LiteLLM:WARNING: get_model_cost_map` in OMO log.

## Risk

- The litellm cost map change is the riskiest — disabling the fetch
  must not break cost calculation for other code paths. Mitigation: use
  the documented env var (per librarian's research), not a code hack.
- MCP test audit (#15) is a search-and-fix task; if many tests need
  fixing, defer to round 7.
