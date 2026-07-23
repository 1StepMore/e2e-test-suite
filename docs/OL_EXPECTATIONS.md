# OL (Omni Localizer) — Founder's Expectations & Agent Validation Master Plan

> **Version:** v0.7.1 · **Stage:** 2 of 3 (OPP → **OL** → ORF) · **Pipeline:** shield→translate→repair→unshield + postproc + 8 quality gates
> **Design:** Agent-native (21 MCP tools), LLM model pool failover, BYOK, FAKE_LLM seam, 4-layer repair

---

## Part 1 — Founder's Expectations

### 1. Introduction

OL translates MD + XLIFF between languages via a pool of LLM models. It accepts files produced by OPP (extraction) and produces output consumed by ORF (backfill). All capabilities are exposed as MCP tools; CLI is a secondary fallback.

### 2. Design Principles

| Principle | Meaning |
|-----------|---------|
| **Shield → Translate → Repair → Unshield** | Code blocks, math, links, HTML shielded with `[OL:TYPE:NNNN]` markers before LLM call, restored after |
| **LLM Model Pool failover** | Multiple models per role (translation/judging/restoration) with priority fallback + circuit breaker (5 failures → open 60s) |
| **BYOK** | `${ENV_VAR}` in config for API keys. Two-layer: warning at startup, error at runtime. `OMNI_TEST_FAKE_LLM=1` bypasses all |
| **8 Quality Gates** | Pure functions (no LLM, no I/O). Advisory only — never block/discard output. Produce `OL_WARN` annotations |
| **Agent-native** | 21 MCP tools as primary surface. CLI secondary |
| **4-layer Repair** | Regex → span alignment → LLM restorer → safe fallback. Content never silently lost |
| **FAKE_LLM seam** | Zero-cost mock translation for CI/dev. `translate()` echoes `[{target_lang}] {source}`; `judge()` returns fixed 9.0 scores |

### 3. Expectation Catalog

#### F01 — MD Translation Pipeline
6-stage pipeline: `input.md → SHIELD → TRANSLATE → REPAIR → UNSHIELD → POSTPROC → QUALITY GATES → output.md`
- Shield: `[OL:TYPE:NNNN]` markers for code, `$..$` math (LaTeX-guarded), links, images, HTML, autolinks
- Translate: litellm Router with model pool, retry (2x), circuit breaker, rate limit
- Repair (4-layer): regex → span alignment → LLM restorer (`LiteLLMRestorer`) → safe fallback (append with `OL_WARN:missing_shields`)
- Unshield: restore from shield_map; missing markers → `<!-- OL_WARN:missing_shields -->` comment
- Postproc: zh↔en punctuation normalization (`str.maketrans`, O(1)) + YAML frontmatter injection

#### F02 — XLIFF Translation
Reads `<source>` from `<trans-unit>` → LLM translate → writes `<target>` → inline tags (`<bx>`, `<ex>`, `<x>`) preserved → quality gate warnings as `<note from="OL">` elements

#### F03 — LLM Model Pool Failover
- litellm Router, `routing_strategy="simple-shuffle"`, `num_retries=2`
- Per-model: `provider`, `model`, `priority` (1=highest), `role`, `api_key`, `base_url`, `timeout` (120s), `requests_per_minute`
- Circuit breaker: pybreaker, 5 consecutive failures → open 60s
- Exponential backoff on HTTP 429

#### F04 — FAKE_LLM Seam
- `OMNI_TEST_FAKE_LLM=1` → `_FakeModelPool` replaces `ModelPool`
- Fake `translate()` returns `"[{target_lang}] {source}"` (echo + prefix)
- Fake `judge()` returns `{accuracy: 9.0, fluency: 9.0, adequacy: 9.0, terminology_consistency: 9.0, format_preservation: 9.0}`
- Zero API keys, zero network, zero cost. Bypasses `${VAR}` env resolution errors

#### F05 — 8 Quality Gates (OL#56)
| # | Gate | Check | Env Override |
|---|------|-------|-------------|
| G1 | `inline_tags` | Parity of `<bx>`, `<ex>`, `<x>` tags source vs target | — |
| G2 | `terminology` | Mixed source/glossary term usage in target | — |
| G3 | `length_ratio` | `len(target)/len(source)` within bounds | `OL_LENGTH_RATIO_MIN` (0.5), `OL_LENGTH_RATIO_MAX` (3.0) |
| G4 | `locale` | Currency mixing, CJK dates, digit grouping, GB/US spelling | `OL_TARGET_LOCALE` |
| G5 | `source_copy` | Unchanged source echoed by LLM | — |
| G6 | `source_script_check` | CJK chars in non-CJK target locale | — |
| G7 | `protocol_artifact_check` | LLM markers (`[INST]`, `<think>`, etc.) leaked | — |
| G8 | `terms_audit` | Full glossary audit via `verify_translation` | — |

All pure functions (no LLM, no I/O). Advisory only — never block/discard.

#### F06 — LQA Scoring
- JudgeService scores: adequacy, fluency, terminology, format (0-10 or 0-100)
- Enabled via `enable_lqa: true` in config
- `lqa_threshold` (default 7.0), `lqa_max_retries` (default 2)
- Low scores → retry via RetryManager

#### F07 — Glossary/TM/TB Injection
- Load glossary JSON → extract top-5 relevant terms per text (`get_relevant_terms`)
- TMX search (`search_tm`) → top-3 matches at threshold 0.85
- `build_translate_prompt()` injects TM matches + glossary terms into LLM prompt
- Graceful degradation: missing TM/glossary → translate without context

#### F08 — Term Disambiguation
- `disambiguate()` resolves polysemous glossary terms with LLM context understanding
- Falls back to confidence-based selection on LLM failure

#### F09 — Prompt Injection Strip (E2E-65)
Level 1 repair regex-strips `CRITICAL: Output ONLY...`, `IMPORTANT:`, `NOTE:` echoes. Agents must NOT strip these — OL handles it.

#### F10 — Truncation Detection (OL#54)
When `finish_reason="stop"` but output looks incomplete (trailing ellipsis, non-terminal punctuation, `completion_tokens >= 90%` of `max_tokens`) → secondary heuristic. `judge()` and `profile()` fail-closed on `finish_reason="length"`.

#### F11 — Polish Language Guard (OL#53)
`polish_translated_units()` / `polish_md_text()` skip corrections that revert to source language (zh→en). `has_source_language_residual()` exported from `ol.pool`.

#### F12 — CLIs and 21 MCP Tools
**CLI:** `ol translate-md`, `ol translate-xliff`, `ol translate-batch`, `ol extract-warnings`, `ol mcp`
**21 MCP:** `translate_md_text`, `translate_xliff`, `judge_text`, `load_glossary`, `get_relevant_terms`, `search_tm`, `batch_translate_texts`, `translate_file`, `get_translation_status`, `verify_terms`, `profile_doc`, `extract_terms`, `add_tm_entries`, `disambiguate`, `shield_md_text`, `unshield_md_text`, `generate_report`, `inspect_config`, `get_capabilities`, `extract_warnings`, `ping`

#### F13 — Post-Processing Punctuation Normalization
- `normalize_to_english()`: full-width Chinese → ASCII (zh→en)
- `normalize_to_chinese()`: ASCII → Chinese equivalents (en→zh)
- O(1) via `str.maketrans`. Zero API cost.

#### F14 — XLIFF Raw XML Tag Normalization (OL#55)
Level 1 repair normalizes LLM-emitted `<x/>`, `<bx/>`, `<ex/>` back to placeholders when shield_map available. Level 4 is bx/ex-pair-aware (no duplicate tag halves).

### 4. Value Proposition

> **OL's value = translation quality + reliability.**
> - Content fidelity: shield preserves code/math/links; 4-layer repair recovers mangled markers; unshield never silently drops content
> - Failover resilience: model pool + circuit breaker + retry means translation completes even when a provider fails
> - Quality assurance: LQA self-corrects low-scoring translations; 8 quality gates catch issues without blocking
> - Agent-native: 21 MCP tools let agents orchestrate the full pipeline without CLI or file I/O
> - Deterministic post-processing: punctuation normalization O(1), zero API cost

---

## Part 2 — Agent Validation Master Plan

**How to use:** Pick a question → read scenarios → execute CLI/MCP/Python → record result → report verdict.

**Prerequisites:**
```bash
export OMNI_TEST_FAKE_LLM=1
```

---

### Q1-OL: MD translation pipeline (shield→translate→repair→unshield)?

| # | Scenario | Command | Expected |
|---|----------|---------|----------|
| 1.1 | Basic MD | `echo '# Hello' > /tmp/q1/a.md && ol translate-md /tmp/q1/a.md -s en -t zh -o /tmp/q1/out` | Exit 0, YAML frontmatter with `source_lang: en`, `target_lang: zh`, `[zh]` prefix |
| 1.2 | Code shielded | Create MD with python codeblock, translate | Code verbatim, no `OL_WARN:missing_shields` |
| 1.3 | Links/images | MD with `[link](...)` and `![img](...)` | URLs and image refs preserved |
| 1.4 | Punctuation zh→en | `echo '你好，世界！' \| ol translate-md -s zh -t en -o /tmp/q1/out2` | `，` → `,`, `！` → `!` |

**Verdict:** ⬜ (✅ all pass / ❌ any fail)

---

### Q2-OL: XLIFF translation?

| # | Scenario | Command | Expected |
|---|----------|---------|----------|
| 2.1 | Basic XLF | Create XLF with `<source>Hello</source>`, `ol translate-xliff` | `<target>` filled, valid XML |
| 2.2 | Inline tags | XLF with `<bx id="1"/>` / `<ex id="1"/>` | Tags preserved in `<target>` |

**Verdict:** ⬜

---

### Q3-OL: FAKE_LLM seam?

| # | Scenario | Command | Expected |
|---|----------|---------|----------|
| 3.1 | translate | `python3 -c "from ol_pool.fake import _FakeModelPool; ... asyncio.run(pool.translate('Hello', source_lang='en', target_lang='zh'))"` | Returns `[zh] Hello` |
| 3.2 | judge | `...pool.judge('s', 't')` | All scores 9.0 |
| 3.3 | CLI E2E | `ol translate-md` with `OMNI_TEST_FAKE_LLM=1` and NO keys | Exit 0, output contains `[zh]` prefix |

**Verdict:** ⬜

---

### Q4-OL: Model Pool failover?

| # | Scenario | Command | Expected |
|---|----------|---------|----------|
| 4.1 | Circuit breaker | Init `ModelPool` with broken provider, call translate | pybreaker tracks failures, opens after 5 |
| 4.2 | Priority config | `python3 -c "from ol_config.loader import load_config; cfg=load_config(); print(len(cfg['llm_pool']['translation']))"` | ≥2 translation models with ascending priority |

**Verdict:** ⬜

---

### Q5-OL: All 8 quality gates?

| # | Scenario | Command | Expected |
|---|----------|---------|----------|
| 5.1 | Length ratio | `check_length_ratio('Long source', 'Hi')` | Warning when ratio < `OL_LENGTH_RATIO_MIN` |
| 5.2 | Inline tags | `check_inline_tags(src, tgt)` matching vs dropped | Matching = pass, dropped = `INLINE_TAG_MISMATCH` |
| 5.3 | Source copy | `check_source_copy('X', 'X', 'en', 'zh')` | `SOURCE_COPY` warning |
| 5.4 | Protocol artifacts | `check_protocol_artifacts('text [INST]...[/INST]')` | `PROTOCOL_ARTIFACT` warning |
| 5.5 | Advisory only | `run_quality_gates()` with failing inputs | Returns warnings list, never raises exception |

**Verdict:** ⬜

---

### Q6-OL: LQA scoring?

| # | Scenario | Command | Expected |
|---|----------|---------|----------|
| 6.1 | Judge scores | `pool.judge('source', 'target')` | Dict with `accuracy`, `fluency`, `terminology_consistency`, `format_preservation` |

**Verdict:** ⬜

---

### Q7-OL: Glossary injection?

| # | Scenario | Command | Expected |
|---|----------|---------|----------|
| 7.1 | Load + extract | Load JSON glossary, call `get_relevant_terms(text, glossary, top_k=2)` | Non-empty relevant terms list |
| 7.2 | Term verify | `verify_translation('Click the button', '点击按钮', glossary)` vs `'点击按键'` | Correct → no mismatches; wrong → mismatches |

**Verdict:** ⬜

---

### Q8-OL: Prompt injection strip?

| # | Scenario | Command | Expected |
|---|----------|---------|----------|
| 8.1 | Strip CRITICAL | Regex `r'^(CRITICAL\|IMPORTANT\|NOTE):\s*(Output ONLY\|Only output\|Translate only)'` on `"CRITICAL: Output ONLY... 你好世界"` | Prefix stripped, `你好世界` remains |

**Verdict:** ⬜

---

### Q9-OL: CLIs work?

| # | Scenario | Command | Expected |
|---|----------|---------|----------|
| 9.1 | Help | `ol --help`, `ol translate-md --help`, `ol translate-xliff --help`, `ol translate-batch --help` | All show params, no crashes |
| 9.2 | translate-md | `echo '# Test' \| ol translate-md -s en -t zh -o /tmp/q9/out` | Exit 0, output file created |
| 9.3 | translate-batch | `mkdir -p /tmp/q9/{in,out}; echo '# D1' > /tmp/q9/in/d1.md; echo '# D2' > /tmp/q9/in/d2.md; ol translate-batch /tmp/q9/in -s en -t zh -o /tmp/q9/out` | All files translated, exit 0 |

**Verdict:** ⬜

---

### Q10-OL: All 21 MCP tools?

| # | Scenario | Command | Expected |
|---|----------|---------|----------|
| 10.1 | Registry | `python3 -c "from ol_mcp.tools import _TOOLS; print(len(_TOOLS))"` | 21 tools registered |
| 10.2 | ping | Call `handle_ping()` | Returns success |
| 10.3 | get_capabilities | Call `handle_get_capabilities()` | Returns roles/tools info |

**Verdict:** ⬜

---

### Q11-OL: Empty/large content?

| # | Scenario | Command | Expected |
|---|----------|---------|----------|
| 11.1 | Empty | `touch /tmp/q11/empty.md && ol translate-md /tmp/q11/empty.md -s en -t zh -o /tmp/q11/out` | Exit 0 or graceful error — not crash |
| 11.2 | Large (~60KB) | Create 60KB file, translate | WARNING log, NOT blocked (E2E-83) |

**Verdict:** ⬜

---

### Q12-OL: No LLM key configured?

| # | Scenario | Command | Expected |
|---|----------|---------|----------|
| 12.1 | Missing var warning | Load config with no keys and `OMNI_TEST_FAKE_LLM` unset | Warning about unset `${VAR}`, or clear error mentioning which env vars |
| 12.2 | CLI without keys | `echo "Hello" > /tmp/q12/test.md && ol translate-md /tmp/q12/test.md -s en -t zh -o /tmp/q12/out` 2>&1 | Error exit, clear message — no traceback |

**Verdict:** ⬜

---

## Final Verdict

| Q | Check | Result |
|---|-------|--------|
| Q1 | MD pipeline (shield→translate→repair→unshield) | ⬜ |
| Q2 | XLIFF translation | ⬜ |
| Q3 | FAKE_LLM seam (zero-cost) | ⬜ |
| Q4 | Model Pool failover + circuit breaker | ⬜ |
| Q5 | 8 quality gates (advisory, non-blocking) | ⬜ |
| Q6 | LQA scoring (JudgeService) | ⬜ |
| Q7 | Glossary/TM/TB injection | ⬜ |
| Q8 | Prompt injection strip (E2E-65) | ⬜ |
| Q9 | CLI commands (translate-md/xliff/batch) | ⬜ |
| Q10 | 21 MCP tools operational | ⬜ |
| Q11 | Edge cases (empty/large content) | ⬜ |
| Q12 | Missing LLM key behavior | ⬜ |

**OVERALL: ⬜** (✅ all PASS / ❌ any FAIL)
