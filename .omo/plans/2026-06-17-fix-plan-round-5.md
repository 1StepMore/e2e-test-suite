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

## Issue Inventory

### Behavior (round 4 directly observed)

| ID | Issue | Sev | Effort | Action this turn |
|---|---|---|---|---|
| #3 | LQA threshold 4.0 in noise edge (cycle 2 hit 3.88) | Med | M | Defer — needs design discussion (lower to 3.8, use median, expand sample) |
| #4 | en→zh 2028-unit doc long-tail (always slow) | Med | L | Defer — needs prefer-OPENCODE_GO for large docs or chunked translation |
| **#5** | **OPENCODE_GO models missing `requests_per_minute`** | **High** | **XS** | **FIX: set rpm=40 on OPENCODE_GO entries** |
| **#6** | **LQA judge / restoration models missing `requests_per_minute`** | **High** | **XS** | **FIX: set rpm=40 on judging/restoration entries (judge calls also consume quota)** |

### Architecture (design / wiring gaps)

| ID | Issue | Sev | Effort | Action this turn |
|---|---|---|---|---|
| **#7** | **rpm written at deployment top-level, not `litellm_params`** | **Low** | **XS** | **FIX: move to `litellm_params["rpm"]` (canonical per litellm types/router.py)** |
| **#8** | **ORF XLIFF→ODT silent failure on non-ODF skeleton** | **Med** | **M** | **FIX: add early format validation in `apply-xliff` (skeleton.ext must match `--format`)** |
| **#9** | **Router not using `enforce_model_rate_limits` (OPT-13)** | **High** | **XS** | **FIX: enable in Router init** |
| #10 | Cross-role fallback doesn't fire when all 3 NVIDIA models 429 | Med | L | Defer — needs intelligent "all throttled" detection |
| #11 | `omni_cache` not invalidated on config change | Med | M | Defer — needs config-fingerprint key |
| #12 | `try_safe_fix` only does clear_opp_cache; docstring lists 6 fixes | Med | M | Defer — needs max_xliff, model-switch, timeout-bump implementations |

### Quality / Test gaps

| **#13** | **No e2e test for `max_xliff_concurrent` config flow** | **High** | **S** | **FIX: add test loading local.yaml → assert `ConcurrencyLimiter._xliff_sem._value == 5`** |
| #14 | No test for real RPM behavior (Router actually uses rpm) | Med | M | Defer — needs Router mock with rate-limit assertion |
| #15 | MCP `apply_xliff` may still test cross-format | Med | S | Defer — audit tests/test_e2e_ol_mcp.py |
| #16 | `xliff_outputs_by_input` is local variable in `build_matrix()` | Low | S | Defer — refactor to module-level |
| #17 | `_build_fallbacks` doesn't validate `rpm > 0` | Low | XS | Defer — pydantic ge=1 already catches it at config load |

### Operations / observability

| **#18** | **No metric on rate-limit hits (only WARN log)** | **Med** | **S** | **FIX: add `Counter("ol_rate_limit_hits", labels=[model])` in router.py retry loop** |
| #19 | No per-model latency metric | Low | S | Defer — needs timing instrumentation |
| #20 | OMO loop convergence fragile under LLM noise | Med | S | Defer — change to "≥80% GREEN in last 5 cycles" |

### Documentation / hygiene

| **#22** | **`local.yaml:22-30` Design comment is stale (mentions 06-16 rationale, doesn't mention RPM)** | **Med** | **XS** | **FIX: append round 5 design notes (RPM, ODT removal)** |
| **#23** | **plan file "round-3" actually contains round 3 + 4** | **Low** | **XS** | **FIX: leave existing file as-is (don't break history); reference from round-5 plan** |
| #24 | API keys hardcoded in `local.yaml`/`default.yaml` (security) | High | L | Defer — needs env-var refactor + .env.example sync; security review needed |

### Code hygiene

| #25 | `f"{m.provider}/{m.model}"` model path concatenation is fragile | Low | S | Defer — pydantic + model name discipline |

## Round 5 Execution Plan

1. **Plan file (this file)** — done.
2. **Commit round 3+4 changes** — `phase1_runner.py`, `test_phase1_p2_matrix.py`, plan file.
3. **Apply fixes** (high-leverage quick wins):
   - #5, #6: `requests_per_minute` on OPENCODE_GO + judge/restoration in `local.yaml`
   - #7: `rpm` → `litellm_params["rpm"]` in `router.py`
   - #9: `enforce_model_rate_limits=True` in Router init
   - #22: refresh Design comment in `local.yaml`
   - #13: e2e test for max_xliff_concurrent flow
   - #18: rate-limit hit counter
   - #8: ORF skeleton-format early validation
4. **Tests** — extend existing test files; verify all pass.
5. **Commit round 5** as separate commit.
6. **Run new round**:
   - OMO loop (1-2 cycles, fast regression check)
   - P2 sweep (validates XLIFF path with RPM + matrix changes)
7. **Update plan** with results + deferred items.

## Deferred Items (Backlog for future rounds)

These were intentionally not addressed this turn. Each is a meaningful
piece of work that deserves its own round:

| ID | Suggested next-round | Why deferred |
|---|---|---|
| #3 | Round 6 or design discussion | Threshold change has wider implications (OMO convergence signal, LQA gate semantics) |
| #4 | Round 6+ | Needs architectural change (prefer OPENCODE_GO for large docs) |
| #10 | Round 6+ | Cross-role fallback redesign |
| #11 | Round 7+ | Cache fingerprinting is a multi-component change |
| #12 | Round 6+ | `try_safe_fix` needs wider discussion on what "safe" means |
| #14 | Round 6+ | RPM behavior test needs Router mocking strategy |
| #15 | Round 6 | Audit + fix MCP tests |
| #16 | Round 7+ | Refactor + test refactor |
| #17 | Round 6+ | Trivial but pydantic-level fix |
| #19 | Round 7+ | Latency instrumentation |
| #20 | Round 6 | OMO convergence criteria — needs behavioral validation |
| #21 | Same as #12 | |
| #24 | Round 6+ | Security refactor — needs .env.example update + key rotation discussion |
| #25 | Round 7+ | Path syntax discipline |
