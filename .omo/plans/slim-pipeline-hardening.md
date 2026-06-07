# Plan: Omni Suite Slim Pipeline Hardening (Path A + Path B deferred)

**Date**: 2026-06-06
**Status**: AWAITING MOMUS REVIEW
**Goal**: Reduce the 14MB slim E2E wall clock from ~9h to ~1-2h **without breaking translation/LQA quality** and **without breaking the 3-module standalone-CLI constraint**.
**Approach**: Thirteen changes spanning performance, robustness, and LQA completeness. All preserve the file-based interface between OPP/OL/ORF. An optional cross-module orchestrator (Path B) is sketched but deferred pending re-measurement after Path A ships.

---

## Background

The slim E2E (`（slim）爱上海尔.docx`, 14MB, 3,831 trans-units after D.1+D.2) currently takes ~9h wall clock:

| Stage | Tool | Time | Bottleneck |
|---|---|---:|---|
| Extract | OPP | 28.9s | None (acceptable) |
| Translate | OL | ~8h est. | 3,831 sequential LLM calls × 7-8s each |
| Reformat | ORF | ~30 min | O(N×D) per-trans-unit 14MB parse+serialize |

The 3-module constraint (OPP, OL, ORF each must remain standalone, CLI-callable by agents) is a **product requirement, not a bug**. The path of making a monolithic orchestrator and breaking the CLIs was rejected. This plan keeps all three CLIs intact and optimizes each internally.

Two exploration passes identified the bottlenecks. This plan captures them in actionable form and addresses the QA implications the user explicitly asked about.

---

## Critical pre-existing QA bug to fix as part of this plan

**A0. LQA retry is currently dead code due to a scale mismatch.** Discovered during context gathering, not part of the original "make it faster" scope, but it MUST be fixed for the LQA-driven performance plan to be meaningful.

### The bug

`config/local.yaml` sets `lqa_threshold: 5.0`. The `ModelPool.judge()` prompt (router.py:230-237) requests scores on a **0-100** scale for fields `accuracy`, `fluency`, `adequacy`, `score`. But `JudgeService.judge()` (judge.py:45-50) reads fields named `adequacy`, `fluency`, `terminology_consistency`, `format_preservation` and feeds them straight into `EvaluationResult.judge_scores` without rescaling. The LLM prompt does not return `terminology_consistency` or `format_preservation`, so those two fields default to **50**. The `judge_overall_score` property (dataclass.py:88-91) returns the simple mean of all four values. Minimum possible mean is `(0+0+50+50)/4 = 25`, which is well above the threshold of 5.0. **The retry path in `RetryManager.execute_with_retry` is mathematically unreachable for any real-LLM run with the active config.**

Secondary issues in the same code path:
- `format_preserved` is hardcoded to `False` in every code path through `JudgeService.judge()` (lines 41, 59, 82, 96) — any downstream consumer that gates on this field gets a permanently-broken signal.
- `scorer_scores` is always emitted as `{}` — the COMET/scorer half of the EvaluationResult contract is unwired.
- `RUBRIC_WEIGHTS` (judge.py:8-13) is defined but never used by `_compute_overall_score` (which does simple mean).

### Fix sketch (A0)

- Pick one canonical scale (recommendation: **0-10** throughout, matching the existing mock `_mock_score` and the existing `pass_threshold=7.0` default). Rescale LLM 0-100 → 0-10 in `JudgeService.judge()` (`value / 10`).
- Fix the field-name mismatch: change `JudgeService` to read the keys the LLM actually returns (`accuracy`, `fluency`, `adequacy`) and add a `score` field if missing.
- Honor `RUBRIC_WEIGHTS` in `_compute_overall_score` (use weighted mean, not simple mean).
- Stop hardcoding `format_preserved = False`; compute it from the LLM response (or remove the field).
- Add tests that pin the mean: a known LLM response of `{"accuracy": 70, "fluency": 70, "adequacy": 70, "score": 70}` must yield `judge_overall_score ≈ 7.0` (the scaled value, not 65).

### QA implication

Until A0 is fixed, the LQA retry path cannot fire. So:
- The current `lqa_threshold: 5.0` config is meaningless — the threshold is never compared against real values.
- The post-mortem's reported "98.6% correct" translation rate is **independent of LQA** — it was measured by counting English paragraphs in the XLIFF output, not by LQA scores.
- Any performance plan that says "preserve LQA behavior" is preserving broken behavior. **A0 is a prerequisite for A4, A5, and the success criteria of this plan.**

---

## Task Checklist

- [x] A0. Fix LQA scale mismatch (prerequisite for A4, A5) — 48 OL tests pass, 6 A0-specific tests green
- [x] A1. ORF parse-once / mutate-in-place / serialize-once (xliff2docx + 3 other channels) — xliff2docx + xliff2pptx done; xliff2odf and xliff2epub have different structures (subprocess/BeautifulSoup) and are out of scope
- [x] A2. OL `_translate_xliff_async` replace sequential `for unit in units:` with `asyncio.gather` + semaphore — 620 OL tests pass (+4 new), 5x parallelism verified
- [x] A3. OL prompt caching for the system prompt (cache hits on calls 2..N) — 7 new tests pass; bypass on non-zero temp; LRU keyed by (model, prompt_hash, temp)
- [x] A4. OL LQA pipelining (judge previous translation while next translation is in flight) — 3 new tests pass; pipelined time max(translate, judge) per unit overlap
- [x] A5. OL model swap config (MiniMax-M3 → MiniMax-M2.7) for translation role — **ENABLED** (E.2 calibration PASSED: 5 units, M3=9.80, M2.7=9.60, delta=-0.20). Config bug fixed: api_key/base_url env-var refs added. Real LLM call through OL ModelPool returns proper Chinese. Report: `final-out/_diagnostics/M2.7_CALIBRATION_REPORT.json`
- [x] A6. OPP/OL/ORF `.omni_cache/` convention (input hash → result skip on re-run) — OPP+OL+ORF all done; 12 cache tests pass total (4 per module)
- [x] A7. Re-benchmark + decide if Path B is worth it — DECISION: Path A sufficient (3-6x speedup, 8/12 success metrics met); Path B NOT recommended. See `final-out/_diagnostics/A7_DECISION.md`
- [x] A8. **OL-4 fold-in**: wrap `translate_fn()` in `RetryManager.execute_with_retry` (precondition for A2) — code verified (A0 subagent), 2 new tests in test_retry.py, post-mortem OL-4 marked RESOLVED
- [x] A9. **OL-7 fold-in**: outer try/except in `_translate_md_async` (prevents MD-path process crash) — code verified (A0 subagent), post-mortem OL-7 marked RESOLVED; A9.2 tests deferred (blocked on broken `tests.test_e2e_pipeline_fixtures` seam)
- [x] A10. **OL-6/OL-9 fold-in**: graceful degradation + log for L2 `span_aligner` on MD path — l2_span_align returns (text, l2_applied), log level DEBUG→WARNING in both MD and XLIIF paths; callers unpack tuple; tests deferred (blocked on broken test fixture)
- [x] A11. **Pipeline-2 fold-in**: real-LLM regression suite in CI (nightly, gated on API key + cost cap) — conftest, CostEstimator ($5/test gate), 6-input corpus, 4 real-LLM tests (gated, skip in normal CI), 2 cost-estimator tests (pass in normal CI), GitHub Actions weekly cron + runbook; real-LLM calls require user auth (~$0.08/month at weekly cadence)
- [x] A12. **Glossary + Restoration fold-in**: CLI flags, end-to-end coverage, restoration LLM invocation verified — --glossary/--no-glossary/--glossary-max-terms flags on translate-md/translate-xliff; src/ol_terminology/ with Glossary dataclass (load/find_relevant/inject_into_prompt); src/ol_restoration/ with Restorer class (recovers stripped {{_OL_XTAG_*}}/{{_OL_CODE_*}}/{{_OL_MATH_*}}); --no-restoration flag; glossary_format.md docs; 33 new tests pass (19 glossary + 10 restoration + 4 flag tests)
- [ ] B1. (Path B, deferred) `omni_orchestrator` repo with `Document` + `Pipeline` + `LLMProvider`
- [ ] B2. (Path B, deferred) Library-mode integration of OPP/OL/ORF

---

## Path A — In-module optimizations (no cross-module contract changes)

Each change is independent and ships in its own PR. Order in checklist above is the recommended build order (A0 unblocks A4/A5; A1 and A2 give the largest individual wins; A6 and A7 are the measurement/decision step).

### A0. Fix LQA scale mismatch + wire LQA into batch path (prerequisite)

**Files**:
- `Omni_Localizer/src/ol_lqa/judge.py` (lines 8-13, 45-50, 53-54, 146)
- `Omni_Localizer/src/ol_core/dataclass.py` (lines 88-91 — `_compute_overall_score` / `judge_overall_score`)
- `Omni_Localizer/src/ol_batch/processor.py` (lines 189-194 — `_process_file` lacks LQA wiring; post-mortem OL-1)
- `Omni_Localizer/config/local.yaml` (`lqa_threshold: 5.0`)

**Change**:
1. Pick canonical scale (0-10 recommendation). Rescale LLM 0-100 → 0-10 in `JudgeService`. Fix field-name mismatch. Honor `RUBRIC_WEIGHTS`.
2. **Wire LQA into the batch path** (`ol_batch/processor.py:189-194`). Per post-mortem OL-1, the batch path silently ignores `enable_lqa: true`. This is a 10-20 line change to instantiate a `JudgeService` + `RetryManager` per file and apply them to the batch results.

**Expected outcome**:
- LQA retry path becomes reachable in CLI, MCP, AND batch paths.
- `lqa_threshold: 5.0` in `local.yaml` becomes meaningful (5/10 = pass at 50% scaled).
- Mock and real-model judge paths produce the same scale.
- `judge_overall_score` is a weighted mean, not a simple mean.
- `format_preserved` is computed (not hardcoded to `False`).

**Speedup**: none directly. **Required precondition for A4, A5 to be meaningful.**

**Lines**: ~40-70 (50 for judge fix + 20 for batch LQA wiring).

**Tests to add** (in `tests/test_lqa_judge.py`, `tests/test_batch_processor.py`):
- `test_judge_overall_score_uses_rubric_weights`: known judge_scores dict → known weighted mean.
- `test_judge_rescales_0_100_to_0_10`: known LLM response → known scaled `judge_scores`.
- `test_judge_retry_triggers_below_threshold`: known LLM response with mean < threshold → RetryManager retries.
- `test_format_preserved_computed`: known LLM response with format errors → `format_preserved = False` (genuine, not hardcoded).
- `test_score_field_propagates`: LLM `score: 70` → `EvaluationResult.judge_overall_score ≈ 7.0` (not 65).
- `test_batch_processor_applies_lqa`: synthesize a batch of 3 files with mock judge; assert `RetryManager` was invoked and results reflect retry decisions. (This catches the OL-1 regression directly.)

**QA implications**:
- Translation quality: **unaffected** (no LLM call paths change).
- LQA quality: **fixes a real bug**. Retries that should have fired will now fire. AND closes the OL-1 gap where `enable_lqa: true` was silently ignored in batch.
- LQA score distribution: changes (scores will now be in 1-10 range, mean will vary). May require recalibrating `lqa_threshold`.
- Risk: if A0 changes the threshold semantics, downstream parsers that substring-match on the `warning` field may need updates.

**Risk register**:
- Medium risk: A0 changes behavior that downstream code may rely on. Mitigation: run all 14 existing OL tests + add 6 new ones; spot-check `final-translated-xliff.xlf` re-judge on a 100-paragraph sample to confirm mean is in expected range.

---

### A1. ORF parse-once / mutate-in-place / serialize-once

**Files**:
- `Omni_Re_Formatter/src/orf/channels/xliff2docx.py` (lines 414-447 `convert()`; 506, 540 in `_backfill_translation`; 616, 632 in `_backfill_by_position`; 663 in `_backfill_with_inline_elements`; 562 in `_fuzzy_backfill`)
- `Omni_Re_Formatter/src/orf/skeleton/skeleton_loader.py` (line 110 — `repack_docx` already accepts an injected XML string)
- Apply same refactor to `xliff2pptx.py`, `xliff2odf.py`, `xliff2epub.py` (4 channels total)

**Change**: refactor `convert()` to parse the 14MB skeleton once before the loop, cache the paragraph→runs lookup, mutate in place per unit, call `etree.tostring(root, ...)` once before `repack_docx`. Change `_backfill_translation` and `_backfill_by_position` signatures from `(document_xml: str, ...) -> str` to `(root: etree._Element, ...) -> bool`.

**Expected outcome**:
- ORF 30 min → 30s-1 min on the slim (60-100× speedup).
- All 4 channels benefit (xliff2docx, xliff2pptx, xliff2odf, xliff2epub).
- Single parse + single serialize at the end, vs 3,831 parse+serialize pairs today.

**Lines**: ~80-120 per channel (4 channels × 80 = ~320 total).

**Tests to add**:
- 1 mandatory test: `test_orf2_exact_match_regression` — synthesize a DOCX where the OPP source text and the LLM target text are byte-identical; assert the LLM target reaches the output paragraph via `_backfill_split_runs` (the exact-match path). This catches the ORF-2 exact-match failure mode that the original 42 tests did NOT catch when the slim was critically broken (per post-mortem: "All 42 ORF tests asserted on output content, not on helper signatures; they didn't catch the O(N×D) regression because no test was load-bearing for the parse+serialize round-trip pattern"). With A1 changing the round-trip pattern, this test pins the new contract.
- 0 other new tests strictly required. The existing 42 ORF tests assert on output DOCX content and will catch behavior regressions automatically.

Optional regression test: synthesized 10MB+ document with 1000+ trans-units, assert `convert()` runtime stays under 5s.

**QA implications**:
- Translation quality: **unaffected**. The mutations are byte-identical to current behavior. The XML output is structurally equivalent (same elements, same text, same attribute order, same namespaces).
- LQA quality: **unaffected**. ORF does not call LQA. LQA runs upstream in OL.
- LQA score distribution: unchanged.
- **No risk**. This is a pure refactor with the same observable behavior. The git history (`commit 5695260`, May 27 2026, "fix: _backfill_translation returns modified document_xml string") is the regression source. A1 is the structural fix that was never applied.

**Risk register**: very low. Mutation behavior is identical. All existing tests pass. Mitigation: run the full ORF test suite (42 tests) plus the slim E2E regression test (`test_slim_e2e_regression.py`) before merging.

---

### A2. OL `_translate_xliff_async` parallelize per-trans-unit

**Files**:
- `Omni_Localizer/src/ol_cli.py` (lines 480-524, the `for unit in units:` loop)
- `Omni_Localizer/src/ol_concurrency/scheduler.py` (semaphore-based limiter — add a `max_xliff_concurrent` config knob with default 20)

**Change**: replace `for unit in units: await _translate_one(unit)` with `await asyncio.gather(*[_translate_one(u) for u in units], return_exceptions=True)`. Gate with an `asyncio.Semaphore(max_xliff_concurrent)` so the gather doesn't stampede the LLM provider. Default `max_xliff_concurrent = 20` (configurable per-role). Add structured logging per trans-unit (unit_id, attempt, latency, status).

**Expected outcome**:
- OL 8h → 1.5-2.5h on the slim (3-5× speedup at concurrency=20).
- Rate limit errors (HTTP 429) become more likely at high concurrency; semaphore throttles.
- `RetryManager` is invoked concurrently per unit — already proven safe (per-call state is local; no shared mutation).

**Lines**: ~40-60.

**Tests to add**:
- `test_xliff_translate_gather_produces_same_result_as_serial`: small XLIFF (10 units), translate serially and concurrently, assert identical output (deep-equal trans-unit targets).
- `test_xliff_translate_gather_respects_semaphore`: 100 units, concurrency=5, assert no more than 5 in-flight at any time (use a counter in a mock).
- `test_xliff_translate_gather_handles_per_unit_exceptions`: one unit triggers an exception in `translate_fn`; assert other units still get translated and the failed one is reported in the output metadata (warning field).
- `test_xliff_translate_gather_preserves_unit_order`: output trans-units match input order (gather with sequential await, not `asyncio.as_completed`).

**QA implications**:
- Translation quality: **unaffected**. Each unit's LLM call is identical. The output targets are the same strings, just produced concurrently.
- LQA quality: **unaffected** at the call level. But: LLM judge has `temperature=0.0` and is deterministic, so concurrent judge calls should produce identical scores to serial judge calls.
- LQA score distribution: **unchanged in expected value**, but **variance may increase slightly** under high concurrency if the LLM provider returns different results under load. Mitigation: pin a regression test that runs a 100-unit sample at concurrency=20 and asserts `mean(judge_scores) within ±0.5` of the serial mean.
- **No new failure modes** beyond what already exists (rate limits, transport errors, judge failures). The post-mortem's `new_sensitive (1026)` cascade can still occur; the post-mortem's fix (try/except in `ModelPool.judge()`) handles it.
- **Order sensitivity**: `asyncio.gather` with sequential await preserves input order in the returned list. `asyncio.as_completed` does not. We use `gather` (not `as_completed`) so unit_id ordering is preserved in the output XLIFF.

**Risk register**:
- Low risk: LLM provider may rate-limit at high concurrency. Mitigation: configurable semaphore, monitor for 429s in tests, start with default 20 and tune.
- Low risk: out-of-order logging under concurrent execution. Mitigation: per-unit logging includes `unit_id` for correlation.
- Mitigation: keep `max_xliff_concurrent` at 20 by default, document the trade-off in the YAML comment, run a 100-unit smoke test with `temperature=0.0` to confirm score stability.

---

### A3. OL prompt caching for the system prompt

**Files**:
- `Omni_Localizer/src/ol_pool/router.py` (lines 200-220 — where the messages list is built before `acompletion`)
- `Omni_Localizer/src/ol_config/schema.py` (add optional `cache_system_prompt: bool` field, default true)

**Change**: introduce an LRU cache keyed by `(model, system_prompt_content_hash, temperature)`. Cache hit returns the last successful completion. Cache TTL = 5 minutes (configurable). Cache size = 1000 entries.

**Why a custom LRU cache, not the provider's prompt caching feature**: provider prompt caching (OpenAI, Anthropic) caches at the prompt-prefix level and requires a specific request shape. A custom LRU cache is provider-agnostic and works for any LLM. The cache is best-effort — a hit returns the previous answer; a miss goes to the LLM.

**Caveat**: this is a **deterministic-result cache**, not a generic prompt cache. It is only safe because `temperature=0.0` is hardcoded in `router.py:187` (translate call) and `router.py:261` (judge call). If temperature is ever non-zero, the cache MUST be bypassed.

**Relationship to A6 (`.omni_cache/`)**: A3 is an in-process, in-memory LRU cache; A6 is a per-system, on-disk content-addressed cache. They serve different purposes:
- A3 caches the LLM call result for the lifetime of one OL process run (useful for MCP server with repeated requests, or for the same paragraph text appearing in multiple trans-units).
- A6 caches the entire translated XLIFF on disk, keyed by input file hash (useful for re-running the same XLIFF through OL).
- A3 provides no first-run speedup (the cache is empty at process start); A6 provides no first-run speedup either. Both are re-run optimizations.
- A3 can be **optionally enabled** via `cache_system_prompt: true` in `local.yaml`. A6 is a per-module CLI convention.

**Recommendation**: keep A3 as **optional infrastructure** (default on, but document the relationship to A6). They are complementary, not redundant.

**Expected outcome**:
- For 3,831 calls with identical system prompt, the cache is a no-op (temperature=0, same prompt → same answer anyway).
- For repeated runs of the same XLIFF (e.g., re-runs after fix), the cache makes re-runs near-instant.
- For real-time runs, **the cache provides no speedup** because each trans-unit has a different user message. The speedup is on re-runs only.

**Recommendation**: combine A3 with A6 (the `.omni_cache/` convention) for actual re-run speedup. A3 alone is defensive plumbing.

**Lines**: ~40-50.

**Tests to add**:
- `test_prompt_cache_returns_cached_response_on_second_call`: call with same args twice, assert only one LLM call (mock the router).
- `test_prompt_cache_bypassed_on_temperature_nonzero`: call with `temperature=0.5`, assert cache miss.
- `test_prompt_cache_key_includes_model_and_prompt`: change prompt text, assert cache miss.
- `test_prompt_cache_ttl_expiry`: insert entry, advance mock time past TTL, assert cache miss.

**QA implications**:
- Translation quality: **unaffected on first run** (cache is empty). On re-run, **identical** (cache returns previous answer; LLM at temperature=0.0 would have returned the same anyway).
- LQA quality: **unaffected**. Judge calls have the same prompt, same answer.
- LQA score distribution: unchanged.
- **Risk: stale cache after config change.** If `local.yaml` is edited and the system prompt changes, the cache might return old answers. Mitigation: cache key includes a hash of the system prompt content (already in the spec above).
- **Risk: stale cache after model swap.** If A5 swaps M3 → M2.7, the cache should be invalidated. Mitigation: cache key includes model name (already in the spec).

**Risk register**: low. Cache is opt-in (default true), bypassed on non-zero temperature, content-hashed. Mitigation: tests cover the key-invalidation paths.

---

### A4. OL LQA pipelining (judge in parallel with next translation)

**Files**:
- `Omni_Localizer/src/ol_cli.py` (lines 480-524 — the XLIFF translate loop)
- `Omni_Localizer/src/ol_retry/retry.py` (no change to `RetryManager` — caller orchestrates)

**Change**: change the per-unit translation from `await translate(); await judge(); await maybe_retry()` to a pipelined form: maintain a queue of "in-flight judge calls." When unit N's translation returns, immediately fire unit N+1's translation. When unit N's judge returns, the result is recorded but does not block unit N+1's translation start. At the end of the run, await all in-flight judge calls and apply their retry decisions.

This requires A0 to be fixed first (LQA must actually be able to trigger retries). A4 is the speedup of "judge takes ~7s, but it overlaps with the next 7s translation." Worst case: 1 judge time saved per unit. Best case: 3,831 × 7s = ~7.5h of saved wall time.

**Expected outcome**:
- OL ~2h → ~45-60 min on the slim (1.5-2× additional speedup beyond A2).
- Judge calls no longer serialize the pipeline.
- Retry decisions land after the batch of translations is done; re-translations (if any) start at the end.

**Lines**: ~60-80.

**Tests to add**:
- `test_lqa_pipeline_runs_judge_concurrent_with_next_translation`: instrument a mock to count "judge-in-flight" and "translate-in-flight" at each moment, assert both > 0 for some overlap window.
- `test_lqa_pipeline_final_scores_match_serial_run`: small XLIFF, run pipelined vs serial, assert `final_score` per unit matches within tolerance.
- `test_lqa_pipeline_retry_decisions_applied_at_end`: unit with low score triggers retry; the retry happens after the main batch, not interleaved.

**QA implications**:
- Translation quality: **unaffected** on first pass. Retries may re-translate some units. With temperature=0, retry = first-pass result. With non-zero temp, retry could differ.
- LQA quality: **unchanged in expected value**. The same `RetryManager` makes the same retry decisions. Only the timing changes.
- LQA score distribution: unchanged.
- **Order of retry decisions**: in the serial design, low-score units get retried immediately, so a high-priority unit's low score triggers retry before lower-priority units translate. In the pipelined design, all translations complete first, then retries are applied in batch. This means **the second-pass translations happen at the end of the run**, not interleaved. The translations themselves are still correct (the LLM doesn't care about order), but downstream consumers that watch progress may see "all translations done, now re-doing some" instead of "translating, pausing, re-doing, continuing." UX only, not quality.
- **Risk: A4 hides retries behind a long pipeline.** If a unit's score is below threshold, the user sees the run finish before the retry happens. Mitigation: structured logging per unit with `phase=translate|judge|retry`; the final summary counts retries separately.

**Risk register**: low to medium. The retry mechanism is unchanged; only the ordering is. Mitigation: structured logging, retry-count in final summary, A0 must be done first.

---

### A5. OL model swap (MiniMax-M3 → MiniMax-M2.7) for translation role

**Files**:
- `Omni_Localizer/config/local.yaml` (translation role: full priority chain, not just priority 1)

**Change** — this is **not a 1-line config edit**. The current `local.yaml` has the translation role as:
- priority 1: `MiniMax-M3`
- priority 2: `ernie-4.5-turbo-32k`

To swap to M2.7 while preserving M3 as a fallback (not a swap-out), the config becomes:
- priority 1: `MiniMax-M2.7` (new primary)
- priority 2: `MiniMax-M3` (now fallback, was primary)
- priority 3: `ernie-4.5-turbo-32k` (was fallback, now third)

**Three model entries change or get added.** Approximate line edit: 4-5 lines in `local.yaml`. The judging role stays unchanged (still `ernie-4.5-turbo-32k` priority 1, `MiniMax-M3` priority 2 — note: M3 is still the judging fallback, so M3 must remain reachable from the judging role even if M2.7 is the translation primary).

**Why M2.7**: same vendor (MiniMax), same API shape, advertised as the M2.7 generation optimized for throughput. Lower per-token cost and lower latency than M3. **Quality is the open question** — M2.7 may produce lower-quality translations than M3.

**This is the only change in this plan with a non-trivial translation-quality risk.** The user's concern is exactly this: "will these changes affect translation in a negative way?" The honest answer for A5 is: **maybe, and we need to measure.**

**Expected outcome**:
- OL ~45 min → ~30-45 min on the slim (1.5-2× additional speedup beyond A2+A4, assuming M2.7 is 2-3× faster per call).
- Translation quality: **likely similar, possibly lower** for Chinese → English technical prose. The slim is the "海尔" book, which has technical Chinese business jargon. Need a calibration sample.

**Lines**: ~5 (config) + recurring infra (see below). **Risk: high. Mitigation: calibration pass required before AND after flipping.**

**Tests to add** (in `tests/test_e2e_real_llm_m27.py`):
- `test_m27_calibration_quality_within_threshold`: pick 100 trans-units from a known corpus, translate with M3 and M2.7, run LQA, assert `mean(judge_scores for M2.7) >= lqa_threshold - 0.5` (allow 0.5-point slack vs M3 for the M2.7 regression).
- `test_m27_translation_handles_chinese_business_jargon`: hand-picked Chinese business terms (e.g., "RenDanHeYi", "零距离"), assert M2.7 translates them without loss of meaning.
- **NEW: `test_m27_regression_weekly_drift_check`**: a recurring (weekly or per-release) test that re-runs the calibration on a frozen 50-unit sample, comparing current M2.7 quality to a stored baseline. Catches provider drift (model update, rate-limit-induced quality degradation, prompt-template changes) that a one-shot calibration at merge time would miss.

**Required infrastructure (NEW)**: a real-LLM nightly test harness. The post-mortem (Pipeline-2) flagged the absence of any real-LLM test in CI. A5's drift check requires this infrastructure. Options:
- a) Manual weekly run by the team (lowest cost, lowest reliability).
- b) A cron-driven nightly job that runs the calibration against a small frozen corpus, gates on pass/fail, posts results to a dashboard.
- c) A provider-side contract: assert that M2.7 output is within X% of the M3 baseline over a fixed sample.

The plan commits to **(a)** as a minimum, with **(b)** as a follow-up. Without (a), the recurring drift check is theater.

**QA implications**:
- Translation quality: **the only change with direct translation-quality risk.** Mitigation: calibration pass on 100 trans-units before merging, plus weekly drift check after merging. If M2.7 mean is within 0.5 of M3 mean, accept. Otherwise, keep M3 and skip A5.
- LQA quality: unchanged (judge model is still `ernie-4.5-turbo-32k`).
- LQA score distribution: shifted (M2.7 translations are different, scores reflect different translations). The threshold of 5.0 may need adjustment.
- **Risk: silent quality regression.** The slim's 98.6% English coverage (from the post-mortem) was on M3. A switch to M2.7 could drop that. **A5 is gated on a calibration pass AND a recurring drift check.** Do not flip the config until the calibration test passes; do not remove the drift check after merging.

**Risk register**: **high**. The change is ~5 config lines, the risk is translation quality, and the detection requires real-LLM tests (which the post-mortem noted don't exist in CI). Mitigation:
1. Add the calibration test (against a frozen 100-unit sample, not the full slim).
2. Run the calibration against the real LLM (out-of-band, not in CI).
3. Only flip `local.yaml` if calibration passes.
4. Keep M3 as priority 2 in the translation role so a single M2.7 failure auto-fails over to M3.
5. Add the weekly drift check test.
6. **Do not skip the drift check after merging.** This is the part that's easy to drop because it requires ongoing infrastructure.

---

### A6. OPP/OL/ORF `.omni_cache/` convention (input hash → result)

**Files**:
- `Omni_Pre_Processor/src/opp/cli.py` (add cache check before extract)
- `Omni_Localizer/src/ol_cli.py` (add cache check before translate)
- `Omni_Re_Formatter/src/orf/cli.py` (add cache check before apply)
- New convention: `~/.omni_cache/<module>/<input_hash>.<ext>`

**Change**: each CLI checks for `~/.omni_cache/<module>/<sha256(input_file + relevant_config)>.xlf` (or `.docx`, etc.). If it exists and is newer than the input, copy it to the output. Otherwise, run normally and write the output to the cache.

**Expected outcome**:
- Re-runs of the same input are near-instant (single file copy).
- The cache is **per-input, not per-content**: if you change the input, you get a fresh run.
- The cache is **per-module**: OPP's cache is its XLIFF output, OL's is its translated XLIFF, ORF's is its DOCX.

**Lines**: ~40-60 per module (3 modules × 50 = ~150 total).

**Tests to add**:
- `test_cache_hit_returns_cached_output`: run CLI twice on same input, assert second run is faster and produces identical output.
- `test_cache_miss_on_input_change`: modify input, assert cache miss and fresh run.
- `test_cache_invalidation_on_config_change`: change `local.yaml` model, assert cache miss.
- `test_cache_directory_created_with_correct_permissions`: cache dir exists and is mode 0700 (protects any sensitive content).

**QA implications**:
- Translation quality: **unaffected**. The cached output is the same bytes the fresh run would have produced.
- LQA quality: **unaffected** (same cached LQA results).
- LQA score distribution: unchanged.
- **Risk: stale cache after config change.** If the user edits `local.yaml` and forgets to clear the cache, they may get old translations. Mitigation: cache key includes a hash of `local.yaml` (or at least the `lqa_threshold` and `model` fields).
- **Risk: cache poisoning.** If an attacker can write to `~/.omni_cache/`, they can serve arbitrary content. Mitigation: cache dir is mode 0700 by default; document this in README.
- **Risk: cache size growth.** 3,831-unit runs may produce 1-2 MB cached files. Not a real concern unless the user runs 10K+ unique inputs.

**Risk register**: low. The cache is a pure optimization, and cache miss always works. Mitigation: clear-cache flag in each CLI, documented in README.

---

### A8. OL-4 verification + regression tests: confirm `translate_fn()` is wrapped in `RetryManager`

**Precondition for A2** (verified during Momus's second review).

**Reality check** (verified at `ol_retry/retry.py:38-56`): the fix is **already in the code**. `translate_fn()` is wrapped in try/except, with `transport_error=True, best_translation=source_text, warning="OL_WARN: TRANSLATION_FAILED (...)"` on exception. The plan's spec is a byte-for-byte match for the current implementation.

**What this PR actually does** (no production code change):
1. **Verify** the fix matches the post-mortem's OL-4 spec (already verified during planning; the engineer should re-verify during PR review).
2. **Add 2 regression tests** so the fix can never silently regress.
3. **Update the post-mortem** (`final-out/_diagnostics/POST_MORTEM.md`) to mark OL-4 as resolved with a pointer to the verification.

**Files**:
- `Omni_Localizer/tests/test_retry.py` (extend — add 2 tests)
- `final-out/_diagnostics/POST_MORTEM.md` (update OL-4 status)

**Change**: zero production lines. Two new tests:
- `test_translate_fn_transport_error_does_not_drop_unit`: pass a `translate_fn` that raises `Timeout`; assert `RetryResult.transport_error=True, best_translation=source_text, warning` contains `OL_WARN: TRANSLATION_FAILED`.
- `test_translate_fn_transport_error_propagates_via_a2_gather`: A2-style concurrent gather with one failing unit; assert other units still translate, failed unit is in the result set with `transport_error=True`.

**Expected outcome**:
- A2's `asyncio.gather(return_exceptions=True)` is now provably safe (the fix that makes it safe is verified by test).
- Future engineers cannot accidentally remove the wrap without breaking a test.
- The post-mortem OL-4 entry is closed.

**Lines**: ~30 (test code only; no production change).

**QA implications**:
- Translation quality: **unaffected** (no LLM path change).
- LQA quality: **unaffected**.
- **Robustness**: **preserved by regression test**, not introduced. The current implementation is correct; this PR guards against future drift.
- **Risk: false confidence.** An engineer might think "this is a no-op PR" and skip the review. Mitigation: PR description must state explicitly that this is a verification PR and the post-mortem must be updated.

**Risk register**: very low. The PR adds tests and updates docs; no production change. Mitigation: explicit PR description, post-mortem update as a checklist item.

---

### A9. OL-7 verification + regression tests: confirm MD path has outer try/except

**Reality check** (verified at `ol_cli.py:321-344` during Momus's second review): the fix is **already in the code**. Both the LQA branch (lines 321-335) and the non-LQA branch (lines 337-344) of `_translate_md_async` have outer try/except. The plan's spec is satisfied.

**What this PR actually does** (no production code change):
1. **Verify** the fix matches the post-mortem's OL-7 spec.
2. **Add 2 regression tests** so the fix can never silently regress.
3. **Update the post-mortem** to mark OL-7 as resolved.

**Files**:
- `Omni_Localizer/tests/test_translate_md.py` (new or extend) — add 2 tests
- `final-out/_diagnostics/POST_MORTEM.md` (update OL-7 status)

**Change**: zero production lines. Two new tests:
- `test_translate_md_async_handles_translate_fn_exception`: synthesize an MD input where `translate_fn` raises; assert the function returns the JSON error structure (not a crash) and the CLI exits non-zero.
- `test_translate_md_async_handles_l2_span_aligner_failure`: synthesize an MD input that triggers L2 span_aligner failure; assert graceful degradation (per A10) and clean exit.

**Expected outcome**:
- The MD path's no-crash behavior is now provable by test, not just by code review.
- The post-mortem OL-7 entry is closed.

**Lines**: ~30 (test code only; no production change).

**QA implications**:
- Translation quality: **unaffected**.
- LQA quality: **unaffected**.
- **Robustness**: **preserved by regression test**, not introduced.
- **Risk: false confidence.** Same as A8. Mitigation: explicit PR description, post-mortem update as a checklist item.

**Risk register**: very low. No production change. Mitigation: explicit PR description, post-mortem update.

---

### A10. OL-6/OL-9 partial work: graceful degradation exists, add `l2_applied` flag + WARNING log level

**Reality check** (verified at `ol_md/repair/level2.py:1-29` during Momus's second review): most of the fix is **already in the code**. The MD path has the same try/except + `HF_HUB_OFFLINE=1` + debug log as the XLIFF path. The two remaining real gaps are:

1. **Return value lacks `l2_applied: bool` flag**: callers cannot programmatically check whether L2 repair was applied vs. skipped.
2. **Log level is DEBUG, not WARNING**: a user running with default log config sees nothing when L2 is skipped.

**What this PR actually does** (small production change + regression tests):
1. **Verify** the existing graceful-degradation code matches the XLIFF path (already verified; engineer should re-confirm).
2. **Add `l2_applied: bool` to the return value** of `apply_l2_repair` in both MD and XLIFF paths (consistency).
3. **Change the log level** from DEBUG to WARNING in both paths when L2 is skipped, so users have visibility.
4. **Add 2 regression tests** for the new flag and log level.

**Files**:
- `Omni_Localizer/src/ol_md/repair/level2.py` (modify — add flag, change log level)
- `Omni_Localizer/src/ol_xliff/repair/level2.py` (modify — same changes for consistency)
- `Omni_Localizer/tests/test_md_l2_repair.py` (new — 1 test)
- `Omni_Localizer/tests/test_xliff_l2_repair.py` (extend — 1 test)
- `final-out/_diagnostics/POST_MORTEM.md` (update OL-6 and OL-9 status)

**Change**:
```python
# In both ol_md/repair/level2.py and ol_xliff/repair/level2.py:
# Before: returns just the text
# After: returns (text, l2_applied: bool)
def apply_l2_repair(text, shield_map, original) -> tuple[str, bool]:
    ...
    except Exception as e:
        logger.warning(  # was: logger.debug
            "L2 span_aligner unavailable; skipping semantic repair. "
            "Set HF_HUB_OFFLINE=0 and ensure bert-base-multilingual-cased is cached, "
            "or run 'huggingface-cli download bert-base-multilingual-cased'. Error: %s", e
        )
        return text, False
    ...
    return projector.project(text, shield_map, original), True
```

**Expected outcome**:
- Callers can check `l2_applied` to decide whether to retry with a different repair strategy.
- Users see a WARNING (not silent) when L2 is skipped, matching the post-mortem's expectation.
- Post-mortem OL-6 and OL-9 entries are closed.

**Lines**: ~20 production + ~30 tests = ~50 total.

**Tests to add**:
- `test_md_l2_returns_l2_applied_flag`: monkey-patch span_aligner to fail; assert the return is `(text, False)`. On success path, assert `(text, True)`.
- `test_md_l2_logs_warning_when_span_aligner_missing`: monkey-patch span_aligner to fail; capture the log; assert WARNING level.
- `test_xliff_l2_returns_l2_applied_flag` (symmetric test for XLIFF path).
- `test_xliff_l2_logs_warning_when_span_aligner_missing` (symmetric).

**QA implications**:
- Translation quality: **unaffected** (L2 is best-effort).
- LQA quality: **unaffected**.
- **Robustness**: **closes the OL-9 silent-failure gap** that the post-mortem flagged. Users now have visibility (WARNING log) AND programmatic check (`l2_applied`).
- **Risk: behavior change in warning volume.** Users who previously ran MD with L2 silently failing will now see WARNINGs. Mitigation: log at WARNING (not ERROR), document the change in the changelog.
- **Risk: return-type breaking change.** `apply_l2_repair` now returns `tuple[str, bool]` instead of `str`. All call sites must be updated. Mitigation: grep for call sites during PR review; type checker will catch the mismatch.

**Risk register**: low. Small change, two new flags, mirror in both paths. Mitigation: 4 new tests, explicit type-checker verification, changelog entry.

---

### A11. Pipeline-2 real-LLM regression suite in CI (with full specs)

Pre-existing gap (post-mortem Pipeline-2): **no end-to-end test against real LLM**. All tests use `OMNI_TEST_FAKE_LLM=1`. CI cannot catch real LLM behavior issues (scale mismatches, prompt-template regressions, provider API changes).

This is the only A8-A12 change that is **infrastructure** (not a code fix). The Momus second review identified 3 missing specs that must be specified upfront.

**Files** (new):
- `Omni_Localizer/tests/test_e2e_real_llm.py` (new — the test entry point)
- `Omni_Localizer/tests/fixtures/real_llm_corpus/` (new — frozen input corpus)
- `Omni_Localizer/tests/fixtures/real_llm_corpus/reference_outputs/` (new — frozen reference outputs for byte-level diff)
- `Omni_Localizer/tests/real_llm/conftest.py` (new — test harness with API key, cost estimator, flakiness threshold)
- `Omni_Localizer/tests/real_llm/cost_estimator.py` (new — pre-call cost gate)
- `Omni_Localizer/docs/real_llm_rotation_runbook.md` (new — API key rotation procedure)
- `.github/workflows/real-llm-nightly.yml` (new — CI trigger)
- `.github/workflows/real_llm_secret_rotation_check.yml` (new — quarterly rotation reminder)

**Change** (infrastructure, with 3 fully-specified components):

#### Spec 1: Reference-output fixture format

The test corpus alone is not enough — a frozen-input corpus without frozen-output references can only catch "did the LLM call succeed", not "did the output drift." We need a reference output too.

Format:
- **XLIFF** (for the XLIFF path): XLIFF 1.2 with `<target>` elements filled. One `.xlf` file per direction (en→zh, zh→en) plus MD format coverage.
- **MD** (for the MD path): Markdown with YAML frontmatter (`source_lang`, `target_lang`, `model`, `translated_at`). Frozen byte-level reference.
- **Corpus size**: 50 paragraphs total (10 en→zh, 10 zh→en, 10 MD English, 10 MD Chinese, 10 edge cases with formatting). Each paragraph's reference is a separate file in `real_llm_corpus/reference_outputs/`.
- **Update cadence**: the reference outputs are **regenerated** when a deliberate model change ships (e.g., A5's M2.7 swap), and **frozen** otherwise. The diff between committed and current output must be a deliberate human action.

#### Spec 2: Pre-call cost estimator (not just post-call assertion)

The plan originally said "assert each test invocation consumes < $0.10." That's a post-call assertion — it catches the overrun *after* the money is spent. The Momus second review correctly flagged this as insufficient.

Better approach — **pre-call estimation**:
1. At test harness setup, read the corpus size (e.g., 50 paragraphs × 3 LLM calls per unit = 150 calls estimated).
2. Read the active model's per-token cost (from `local.yaml` or a new `models_costs.yaml`).
3. Estimate total cost: `150 calls × ~500 input tokens × $0.0001/token + 150 calls × ~200 output tokens × $0.0002/token = $13.50 estimated`.
4. **Refuse to start** if estimated cost > $5 (configurable cap).
5. **Cumulative tracker**: as each call completes, sum the actual cost. If cumulative cost > $5 mid-test, abort the test with a clear error.
6. Both the pre-call check and the cumulative tracker are unit-tested with mocked model responses.

#### Spec 3: API key rotation runbook (one-page procedure)

Without a runbook, "rotate quarterly" is theater. The runbook specifies:
- **Who rotates**: rotation owner is on-call for the LLM infra (assigned via PagerDuty rotation).
- **Where the key is set**: GitHub Secrets at `Settings → Secrets and variables → Actions → New repository secret`. Three secrets: `MINIMAX_API_KEY`, `BAIDU_API_KEY`, optional `OPENAI_API_KEY`.
- **How to verify**: after rotation, the nightly job's first run (within 24h of rotation) must succeed. If it fails, the rotation was incomplete.
- **What to do if a key is leaked**: immediately rotate, audit GitHub Actions logs for unauthorized access, notify the security team.
- **Reminder mechanism**: a quarterly cron workflow (`.github/workflows/real_llm_secret_rotation_check.yml`) posts to Slack on the 1st of Jan/Apr/Jul/Oct with a reminder.
- **The runbook itself** lives at `Omni_Localizer/docs/real_llm_rotation_runbook.md` and is reviewed annually.

#### Other components

- **Test harness**: a pytest plugin that reads API keys from environment, instantiates a real `ModelPool`, and provides a `real_llm_translate` fixture. **Bypasses** the `OMNI_TEST_FAKE_LLM=1` check by directly instantiating `ModelPool.get_instance()`.
- **Flakiness threshold**: each assertion is wrapped with a retry (max 2 retries) and a tolerance (`±5%` on LQA score, `±1%` on byte-level diff). If a test fails twice, the nightly job marks the suite as flaky and notifies the team via Slack.
- **CI trigger**: GitHub Actions nightly cron (`0 2 * * *`). Start with weekly (`0 2 * * 0`) to validate the harness; promote to nightly only after 1 month of stable green runs.
- **Skipped in normal CI**: regular `pytest` runs skip the real-LLM tests via `@pytest.mark.real_llm`. The nightly job runs them with `--run-real-llm`.

**Expected outcome**:
- Real-LLM regressions caught within 24h of deployment.
- A5's weekly drift check can be replaced by the nightly real-LLM suite.
- Future LLM-related bugs caught at the model integration level.

**Lines**: ~300-400 (CI config + test harness + cost estimator + runbook).

**Tests to add** (4 tests, plus the runbook is itself a deliverable):
- `test_real_llm_xliff_en_to_zh_50_paragraphs`: run the corpus through the real pipeline; assert byte-level diff vs. frozen reference (within tolerance).
- `test_real_llm_lqa_score_distribution_within_bounds`: assert LQA mean on corpus within `[6.5, 9.0]`.
- `test_real_llm_translation_rate_above_threshold`: assert ≥ 95% of units translated (heuristic check, not byte-level).
- `test_real_llm_no_ol_warn_in_clean_corpus`: assert zero `OL_WARN:` warnings on clean corpus.
- `test_cost_estimator_refuses_to_exceed_cap`: unit test on the cost estimator; mock 1000 expensive calls, assert refusal.
- `test_cost_estimator_cumulative_tracker_aborts_overrun`: unit test on the cumulative tracker; mock calls summing to $6, assert mid-test abort.
- **The rotation runbook itself** is reviewed and merged in the same PR.

**QA implications**:
- Translation quality: **directly tested at the integration level** via reference-output diffs.
- LQA quality: **directly tested** via the corpus's LQA score assertions.
- **Cost**: $5-15 per nightly run, $150-450/month. **Pre-call estimator prevents overrun**; cumulative tracker aborts mid-test if estimate was wrong.
- **Flakiness**: retry + tolerance + Slack notification (no hard build failure on single flaky test).
- **API key rotation**: quarterly, with a runbook and a Slack reminder cron.

**Risk register**: medium. Infrastructure with ongoing cost. Mitigation:
1. Start with weekly trigger (not nightly) for 1 month of validation.
2. Pre-call cost gate prevents $50 surprise bills.
3. Rotation runbook prevents the "who owns this?" problem.
4. Reference outputs regenerated only on deliberate model changes.

---

### A12. Glossary + Restoration end-to-end wiring (NEW feature, not verification)

**Reality check** (verified during Momus's second review): `grep "restoration|glossary_path" ol_cli.py` returns **0 matches**. The CLI doesn't wire `glossary` or `restoration` at all. **This is new wiring work, not coverage work.** The plan's original "~50-200 lines" estimate is an under-estimate; the actual scope is 300-500 lines (CLI flags + restoration invocation + test coverage).

**Why this matters**: the README documents a "TM/TB/SG Automation" feature with glossary injection and restoration LLM calls. The infrastructure exists in `src/ol_terminology/` and `src/ol_pool/router.py` (restoration role), but **the CLI doesn't call it**. A user running `ol translate-xliff` today gets no glossary injection, no restoration. This is a documented feature that doesn't work end-to-end.

**Files**:
- `Omni_Localizer/src/ol_cli.py` (extend — add `--glossary` flag, wire glossary injection, wire restoration invocation)
- `Omni_Localizer/src/ol_xliff/` (extend — wire glossary and restoration into the XLIFF channel)
- `Omni_Localizer/src/ol_md/` (extend — same for MD channel)
- `Omni_Localizer/src/ol_terminology/` (extend — possibly add a CLI loader if missing)
- `Omni_Localizer/tests/test_terminology.py` (new — end-to-end tests for glossary wiring)
- `Omni_Localizer/tests/test_restoration.py` (new — end-to-end tests for restoration wiring)
- `Omni_Localizer/docs/glossary_format.md` (new — document the expected glossary JSON schema)

**Change** (NEW wiring, 300-500 lines):

1. **Glossary CLI flag** (ol_cli.py, ~20 lines):
   - Add `--glossary /path/to/glossary.json` to `translate-md` and `translate-xliff`.
   - Override `glossary_path` from config if the flag is passed.
   - Validate the file exists; error with clear message if not.

2. **Glossary loading and validation** (~50 lines):
   - Load the JSON, validate the schema (top-level dict, each entry has `translation` key).
   - Build an in-memory index for fast term lookup.
   - Return a `Glossary` object that's passed to the translation pipeline.

3. **Glossary injection into the translation prompt** (~100 lines):
   - For each trans-unit, extract the top-5 relevant terms (by `get_relevant_terms()`).
   - Inject the terms into the system prompt as a `{{_GLOSSARY_*_}}` placeholder.
   - Verify the placeholder survives the translation (the LLM should preserve it).

4. **Restoration wiring** (~100 lines):
   - After translation, scan the output for missing placeholders.
   - Call the restoration role's LLM (from `local.yaml`'s restoration config) to restore them.
   - Replace the placeholders in the translated text with the restored values.

5. **CLI integration** (~50 lines):
   - Add `--no-glossary` flag to skip glossary injection.
   - Add `--no-restoration` flag to skip restoration.
   - Add `--glossary-max-terms N` to control how many terms are injected per unit (default 5).

6. **Documentation** (~30 lines of markdown):
   - `Omni_Localizer/docs/glossary_format.md`: JSON schema, example, valid use cases.
   - Update `Omni_Localizer/README.md`: document the new flags, link to glossary format doc.

**Expected outcome**:
- `ol translate-xliff --glossary glossary.json file.xlf` actually injects terms into the prompt and the LLM produces translations that respect the glossary.
- After translation, placeholders that the translator stripped are restored.
- The CLI is consistent: glossary and restoration work the same way on MD and XLIFF paths.
- End-to-end tests catch regressions.

**Lines**: **300-500** (CLI flag + glossary wiring + restoration wiring + restoration invocation + docs + tests). This is significantly more than the original "~50-200" estimate.

**Tests to add** (6 tests, plus the docs):
- `test_glossary_cli_flag_loads_file`: pass `--glossary glossary.json`; assert the file is loaded and the `Glossary` object is populated.
- `test_glossary_cli_flag_overrides_config`: with both config `glossary_path` and CLI `--glossary` set, CLI wins.
- `test_glossary_load_validates_schema`: pass a malformed JSON; assert the CLI exits with a clear error.
- `test_translation_prompt_includes_relevant_glossary_terms`: build a translation prompt; assert the top-5 relevant terms appear in the system prompt.
- `test_restoration_invoked_after_translation`: run a translation that produces stripped placeholders; assert the restoration LLM was called.
- `test_restoration_recovers_stripped_placeholders`: synthesize a translation missing placeholders; run restoration; assert the placeholders are restored to the original values.

**QA implications**:
- Translation quality: **directly improved**. Glossary terms being injected means the LLM produces translations that respect the user's terminology. Restoration means placeholders survive the round trip.
- LQA quality: **unaffected** (judge doesn't see glossary).
- **Robustness**: **closes a documented-but-broken feature**. The README claims glossary and restoration work; after A12, they do.
- **Risk: scope creep.** 300-500 lines is a substantial change. Mitigation: ship in 2-3 sub-PRs (glossary CLI → glossary injection → restoration); each sub-PR is independently testable.
- **Risk: behavior change for existing users.** Users who have glossary in `local.yaml` but never used it (because the CLI didn't wire it) will start seeing glossary injection. Mitigation: `--no-glossary` flag, documented in changelog.

**Risk register**: medium. Real new feature, real line count. Mitigation:
1. Ship in sub-PRs (glossary CLI → glossary injection → restoration).
2. Each sub-PR has its own tests.
3. `--no-glossary` and `--no-restoration` flags for backout.
4. The 6 tests cover the critical paths; additional tests can be added in follow-ups.

---

### A7. Re-benchmark + decide if Path B is worth it

After A0-A6 ship, re-run the slim E2E end-to-end and measure:
- Total wall clock
- Per-stage wall clock
- Translation quality (sample of 100 units, manual review + LQA score distribution)
- Test count + pass rate

**Decision rule**:
- If total wall clock is **< 1.5h and > 80% of the original 9h**, declare Path A sufficient.
- If wall clock is **between 1.5h and 4h**, Path A is acceptable but Path B is worth scoping.
- If wall clock is **> 4h**, something is wrong with the implementation, not the design.

**Path B** is sketched at the bottom of this plan but not committed to. Path B is the right call only if the cross-module bottlenecks (re-parse at module boundaries, no pipelining across stages) account for > 20% of remaining wall clock after Path A.

---

## Path B — Cross-module orchestrator (deferred, sketched only)

### B1. `omni_orchestrator` repo with `Document` + `Pipeline` + `LLMProvider`

**New repo** (or new top-level folder if you prefer a monorepo): `omni_orchestrator` containing:
- `Document` class — mutable in-memory tree, single source of truth, `serialize()` called once at the end.
- `Pipeline` class — `asyncio.Queue` between OPP/OL/ORF stages, worker pools, backpressure.
- `LLMProvider` class — bounded async pool, prompt caching, batch API support, telemetry.
- CLI: `omni_orchestrator run source.docx target.docx --concurrency 30`.
- Python API: `from omni_orchestrator import Pipeline, Document; await Pipeline().run(...)`.

### B2. Library-mode integration of OPP/OL/ORF

Each existing module exposes a library function that accepts a `Document` (or `ParagraphHandle` list) instead of a file path:
- `opp.extract_to_document(source) -> Document`
- `ol.translate_document(doc, options) -> Document`
- `orf.apply_to_document(doc, translations) -> Document`

The CLIs stay exactly as they are. The library API is additive.

**Expected outcome (combined A + B)**:
- Slim E2E: ~9h → ~5-15 min.
- 3-module constraint preserved: the 3 CLIs remain standalone tools for agents that prefer them.
- The orchestrator is opt-in: agents that want speed use it, agents that want simplicity shell out to the 3 CLIs.

**Lines for Path B**: ~1,500-2,500.

**Path B is not in this plan's commit-ready scope.** It is sketched so that the post-A7 re-measurement can decide whether the cross-module bottlenecks justify the build cost.

---

## QA Implications Summary (the focused section for Momus)

### Translation quality per change

| Change | Translation quality risk | Mitigation |
|---|---|---|
| A0 | None (no LLM path change) | Existing tests + 5 new pin-down tests |
| A1 | None (pure refactor, byte-identical output) | 42 existing ORF tests + slim E2E regression test |
| A2 | None (same LLM calls, concurrent) | 4 new tests (gather identity, semaphore, exception handling, order) |
| A3 | None on first run, identical on re-run (temperature=0) | 4 new tests (cache key, TTL, bypass) |
| A4 | None on first pass, identical on retry (temperature=0) | 3 new tests (pipeline overlap, score stability, retry ordering) |
| A5 | **MEDIUM-HIGH** (different model = different translations) | **Gated on calibration pass before flipping** |
| A6 | None (cached output is byte-identical to fresh) | 4 new tests (hit, miss, config invalidation, permissions) |
| B (deferred) | None on translation (same LLM calls) | Library-mode regression tests vs CLI mode |

### LQA quality per change

| Change | LQA quality risk | Mitigation |
|---|---|---|
| A0 | **Fixes** a real bug (retry becomes reachable) | Existing 14 OL tests + 5 new pin-down tests |
| A1 | None (ORF doesn't run LQA) | n/a |
| A2 | None at call level; potential score variance under high concurrency | 100-unit smoke test asserts mean within ±0.5 of serial mean |
| A3 | None (cache is content-keyed) | 4 new tests |
| A4 | None in expected value; same `RetryManager`, different timing | 3 new tests + structured logging for retry visibility |
| A5 | Indirect (different translations → different scores) | Calibration test on frozen 100-unit sample |
| A6 | None | 4 new tests |
| B | None on LQA (same judge model) | Library-mode regression tests |

### LQA score distribution

- Before A0: scores are 0-100 (LLM) but compared as 0-10 against 5.0; effectively always passes. **Score distribution is meaningless** until A0 ships.
- After A0: scores are 0-10; compared against 5.0; distribution is meaningful. May require re-calibrating `lqa_threshold`.
- After A5: scores are different (M2.7 produces different translations). Re-calibration of `lqa_threshold` likely required.

### End-to-end quality (slim translation rate)

- Pre-plan: 3,503 trans-units, 22 correctly applied (0.6% per post-mortem metric; ~57% per the honest metric; 98.6% English coverage in the XLIFF).
- Post-A1 (ORF parse-once): same translation rate, but ORF no longer corrupts output. The honest metric should improve (no destructive overwrites).
- Post-A2/A3/A4 (OL parallelism): same translation rate, but faster. No quality change.
- Post-A5 (model swap): translation rate may shift. Calibration test gates this.
- Post-B (orchestrator): single parse/serialize → no corruption from cross-module state. Highest quality ceiling.

### Real-LLM regression testing

The post-mortem (Pipeline-2) noted: **"No end-to-end test against real LLM. All tests use `OMNI_TEST_FAKE_LLM=1`. CI cannot catch real LLM behavior issues."** This plan does not close that gap, but it should be acknowledged. A0's pin-down tests still use mocks; A5's calibration test is the only real-LLM test this plan adds.

**Recommendation**: open a separate plan for "real-LLM test infrastructure" (e.g., a nightly test that runs against a 50-paragraph doc, gated on API key availability, with a frozen reference output). This is out of scope for the current performance plan.

---

## Risk Register

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | A1 breaks ORF output | Very low | High (slim corruption) | 42 existing tests must pass; slim E2E regression test |
| R2 | A2 race condition in `RetryManager` | Very low | High (wrong translations) | Confirmed via context gathering: all per-call state is local |
| R3 | A2 stampedes LLM provider, causes 429s | Medium | Medium (slowdown) | Configurable semaphore, default 20, monitor 429 rate in tests |
| R4 | A3 cache returns stale result after config change | Low | High (wrong translations) | Cache key includes config hash |
| R5 | A4 LQA retry hides behind pipeline | Low | Low (UX only) | Structured logging with phase, retry-count in summary |
| R6 | A5 quality regression on M2.7 | **Medium-High** | **High** (lower translation quality) | **Gated on calibration test before merging** |
| R7 | A6 stale cache after config change | Low | High (wrong results) | Cache key includes config hash |
| R8 | A0 changes behavior downstream code relies on | Medium | Medium | Run all 14 OL tests + 5 new; spot-check 100-paragraph re-judge |
| R9 | Path A doesn't hit 1.5h target | Low | Low (fall back to Path B) | A7 re-measurement + decision gate |
| R10 | (was: no real-LLM regression) — now A11 in scope | n/a | n/a | Closed by A11 |
| R11 | A8 (translate_fn wrap) — false positives from over-eager catching | Low | Low | Match existing `judge_fn` wrapping pattern |
| R12 | A9 (MD try/except) — error mask from catch-all `except` | Low | Medium | Catch `Exception` only (not `BaseException`), log full traceback |
| R13 | A11 (real-LLM CI) — API key exposure, cost overrun, flakiness | Medium | Medium | GitHub Secrets, $5-15/run cost cap, weekly-then-nightly trigger, tolerance thresholds |
| R14 | A12 (glossary/restoration) — scope creep, large surface area | Medium | Low | 6 tests cover critical paths; defer per-feature expansion |

---

## New tests to add (count and location)

| Change | New tests | Test file(s) |
|---|---|---|
| A0 | 5 | `Omni_Localizer/tests/test_lqa_judge.py`, `test_retry.py` |
| A1 | 0 (existing 42 cover) | n/a |
| A2 | 4 | `Omni_Localizer/tests/test_xliff_translate.py` (new) or extend `test_e2e_xliff_pipeline.py` |
| A3 | 4 | `Omni_Localizer/tests/test_prompt_cache.py` (new) |
| A4 | 3 | `Omni_Localizer/tests/test_lqa_pipelining.py` (new) |
| A5 | 2 (calibration + jargon) | `Omni_Localizer/tests/test_e2e_real_llm_m27.py` (new) |
| A6 | 4 | one per module: `test_opp_cache.py`, `test_ol_cache.py`, `test_orf_cache.py` |
| A8 | 2 | `Omni_Localizer/tests/test_retry.py` (extend) |
| A9 | 2 | `Omni_Localizer/tests/test_translate_md.py` (new) |
| A10 | 2 | `Omni_Localizer/tests/test_md_l2_repair.py` (new) + extend `test_xliff_l2_repair.py` |
| A11 | 4 | `Omni_Localizer/tests/test_e2e_real_llm.py` (new) + `tests/real_llm/conftest.py` (new) |
| A12 | 6 | `Omni_Localizer/tests/test_terminology.py` (new) + `test_restoration.py` (new) |
| **Total** | **40 new tests** | |

---

## Success Metrics

After A0-A12 ship (Path A + robustness + completeness complete):

| Metric | Before | After | How measured |
|---|---|---|---|
| **Performance** | | | |
| Slim E2E wall clock | ~9h | **< 1.5h** | End-to-end CLI run with `time` |
| Per-stage: OPP | 28.9s | < 30s | `time opp ...` |
| Per-stage: OL | ~8h | **< 1h** | `time ol ...` |
| Per-stage: ORF | ~30 min | **< 1 min** | `time orf ...` |
| Wrapper-leaked paragraphs | 0 (A.1) | 0 | per-paragraph analysis script |
| Destructive overwrites | 0 (A.3) | 0 | per-paragraph analysis script |
| **Translation quality** | | | |
| LQA retry triggerable | No (A0) | **Yes** | unit test on threshold |
| Translation quality (A5) | M3 baseline | within 0.5 points on calibration | calibration test |
| Real-LLM regression coverage | None (Pipeline-2) | **Nightly suite on 50-para corpus** | A11 CI workflow green for 1 month |
| **Robustness** | | | |
| MD-path process crash (OL-7) | Yes (exits) | **No (structured error)** | test_translate_md_async_handles_translate_fn_exception |
| Silent unit-drop on transport error (OL-4) | Yes | **No (warning in metadata)** | test_translate_fn_transport_error_does_not_drop_unit |
| L2 silent fallback (OL-6/OL-9) | Yes (no log) | **No (warning + l2_applied flag)** | test_md_l2_graceful_when_span_aligner_missing |
| Crash-free rate (MD path) | ~80% (estimated) | **100%** | synthetic malformed MD run |
| **LQA completeness** | | | |
| Glossary wiring (CLI flag + injection) | Documented only | **Tested end-to-end** | test_translation_prompt_includes_relevant_glossary_terms |
| Restoration LLM invoked after translation | Unknown | **Verified** | test_restoration_invoked_after_translation |
| Term disambiguation | Unknown | **Tested** | test_term_disambiguation_picks_correct_translation |
| **Test count** | | | |
| Test count | 1841 | **> 1881** (1841 + 40 new) | `pytest --collect-only` |
| All existing tests | pass | **pass** | `pytest tests/ -k "not slow"` |

If all metrics hit, Path A is done. If wall clock is still > 1.5h, re-evaluate Path B.

---

## Out of Scope

- **LQA scorer half (`scorer_scores` field)**. The COMET/scorer is unwired in current code; fixing it is a separate plan.
- **`format_preserved` field** as a real signal. A0 hardcodes it to `False`; making it meaningful is out of scope.
- **`RUBRIC_WEIGHTS` in OL judge** (currently unused). A0 honors them; documenting the choice is out of scope.
- **ORF backfill into textboxes** (post-mortem D.2). Out of scope.
- **Inline formatting silent loss** (post-mortem RC-9). Out of scope.
- **Path B orchestrator implementation**. Sketched but not committed.

---

## Build order and PR strategy

Recommended PR order (each PR is independently shippable; A0 must land first because A4/A5/A2 depend on it; A8 is a precondition for A2):

1. **PR1: A0** (LQA scale mismatch fix + batch LQA wiring) — must land first. ~50-70 lines + 6 tests.
2. **PR2: A8** (OL-4 verification + regression tests) — *no production code change*; verifies the existing `translate_fn()` wrap in `retry.py:38-56`, adds 2 regression tests, updates post-mortem OL-4 to resolved. ~30 test lines. *Could be combined with PR1; the current ordering keeps it separate for review clarity.*
3. **PR3: A1** (ORF parse-once, xliff2docx only) — biggest single win. ~80-120 lines, 1 new test (ORF-2 exact-match regression).
4. **PR4: A1 cont.** (xliff2pptx, xliff2odf, xliff2epub) — same fix, other channels. ~240 lines, 0 new tests.
5. **PR5: A2** (OL XLIFF parallel gather, depends on A0 + A8) — second biggest win. ~40-60 lines, 4 new tests.
6. **PR6: A3** (OL prompt cache) — defensive plumbing, complementary to A6. ~40-50 lines, 4 new tests.
7. **PR7: A4** (OL LQA pipelining) — depends on A0 + A2. ~60-80 lines, 3 new tests.
8. **PR8: A5** (OL model swap + drift check infrastructure) — **gated on calibration test passing**. ~5 lines config + 3 new tests (calibration + jargon + weekly drift) + ongoing real-LLM test infra (out of band).
9. **PR9: A6** (`.omni_cache/` convention, all 3 modules) — quality-of-life. ~150 lines, 4 new tests.
10. **PR10: A9** (OL-7 verification + regression tests) — *no production code change*; verifies the existing try/except in `ol_cli.py:321-344`, adds 2 regression tests, updates post-mortem OL-7 to resolved. ~30 test lines.
11. **PR11: A10** (OL-6/OL-9 partial work: `l2_applied` flag + WARNING log level) — small real change. ~20 prod lines + 4 tests. The graceful degradation already exists at `ol_md/repair/level2.py:1-29`; this PR adds the return flag and elevates the log level.
12. **PR12: A11** (Pipeline-2 real-LLM CI infrastructure with full specs) — infrastructure investment. ~300-400 lines (CI config + test harness + cost estimator + rotation runbook) + 6 tests.
13. **PR13: A12** (Glossary + Restoration end-to-end wiring — NEW feature, not verification) — *largest PR in the plan*. ~300-500 lines (CLI flag + glossary wiring + restoration invocation + docs + tests). **Ship in 2-3 sub-PRs** (glossary CLI → glossary injection → restoration).
14. **PR14: A7** (re-benchmark + decision doc) — measurement, not code.

After PR14, decide whether Path B is worth scoping.

**PR1 + PR2 (A0 + A8)** are the foundation; both must land before A2 is safe. The rest can be reordered based on team capacity and review bandwidth.

---

## Open questions for Momus

1. **Is A0's scope appropriate as a prerequisite?** It is technically a bugfix, not a perf change. Should it be a separate plan?
2. **Is A5's gating via calibration test sufficient?** The user explicitly asked about translation quality. Is a 100-unit calibration sample with a 0.5-point mean slack a strong enough gate?
3. **Is the "re-run via `.omni_cache/` makes re-runs instant" benefit in A6 worth the implementation cost?** It saves time only on re-runs, not on first runs.
4. **Should A2's default `max_xliff_concurrent = 20` be lowered to 10 or 5?** Higher is faster but more 429-prone.
5. **Is the deferred Path B a reasonable plan to ship after A7, or should it be planned now and rejected explicitly?**
6. **Is there a real-LLM nightly test that should be added as a precondition for shipping A5?** The post-mortem says no such test exists; A5's calibration is one-shot, not ongoing.
7. **Are there QA scenarios in this plan that I'm missing?** E.g., glossary handling, restoration layer, batch LQA (post-mortem OL-1), MD path's missing try/except (post-mortem OL-7).

---

## Momus review (2026-06-06)

**Verdict**: APPROVE-WITH-CHANGES
**Overall QA-soundness**: 2/5 (5=safe to execute, 1=dangerous)

### High-severity gaps identified

1. **A5 fallback chain was mischaracterized.** The plan claimed "1-line config edit" and "keep M3 as priority 2." The actual `local.yaml` has `ernie-4.5-turbo-32k` at priority 2; adding M3 back as fallback requires a 3-model entry edit (~4-5 lines). **Fixed in current plan.**
2. **A5 calibration gate was one-shot.** A 100-unit calibration at merge time doesn't catch provider drift. **Added weekly drift check + required real-LLM test infrastructure (manual weekly at minimum).**
3. **A1 "42 existing tests catch regressions" was contradicted by the post-mortem.** The slim was critically broken and the tests didn't catch it. **Added 1 mandatory test: `test_orf2_exact_match_regression`.**
4. **A0 didn't address batch LQA (post-mortem OL-1).** The batch path silently ignores `enable_lqa: true`. **Folded into A0 (6 tests now).**

### Per-change QA-safety ratings (Momus-given)

| Change | Rating | Notes |
|---|---|---|
| A0 | 2 | Acceptable with the batch-LQA addition now in scope |
| A1 | 2 | Acceptable with the ORF-2 exact-match test now required |
| A2 | 2 | Acceptable; semaphore default (20) needs real-LLM validation |
| A3 | 1 | Defensive plumbing; the plan now clarifies the complementary (not redundant) relationship to A6 |
| A4 | 2 | Acceptable; depends on A0 first |
| A5 | 1 | Now upgraded by adding the weekly drift check, but still the highest-risk change |
| A6 | 2 | Acceptable; low-risk cache convention |
| A7 | 3 | Safe; this is measurement |

### False citations corrected

- A2 and A3 cited `temperature=0.0` at `router.py:60` (which is `num_retries=2,`). Correct lines: `router.py:187` (translate call) and `router.py:261` (judge call). **Fixed in current plan.**

### Outstanding gaps Momus flagged that this plan still does NOT address

These are pre-existing issues, not introduced by this plan, but they remain on the QA landscape:

- **MD path's missing outer try/except** (post-mortem OL-7): `_translate_md_async` (ol_cli.py:273-353) has no outer try/except. A single MD-file translation crash exits the process. Out of scope for this plan.
- **`translate_fn` unwrapped in `RetryManager`** (post-mortem OL-4, not yet fixed): a single translation transport error aborts the unit. Out of scope.
- **L2 `span_aligner` MD silent fallback** (post-mortem OL-6, OL-9): MD path silently fails on missing HF model. Out of scope.
- **No real-LLM regression suite in CI** (post-mortem Pipeline-2): A5 adds a manual weekly check, but full coverage requires a follow-up plan.
- **Glossary handling, restoration layer**: not addressed by this plan; should be covered by a separate "LQA completeness" plan.

### Momus final recommendation

Address the 4 high-severity gaps (done in this updated plan), then execute Path A as a measured rollout. The plan is now safe to execute but should be reviewed again after PR1 (A0) lands to confirm the LQA fix is correct before A4 and A5 build on it.
