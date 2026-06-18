# Production Readiness Implementation Plan (2026-06-18)

## Goal

Close every P0/P1/P2 gap from the three round-15 audits in a single
implementation pass. After this plan ships, the system is ready for:
- The user's own daily use (their machine)
- Hermes agent's production deployment (Hermes machine)
- Both machines run identical, reproducible installs

**No acceptance threshold is set until the QA system itself is
improved** (see "QA system first" below). Threshold-tightening
without QA-system improvement is meaningless.

## What this plan covers

| Domain | Items |
|--------|-------|
| Security | OL MCP path validation, hardcoded key removal, OPP MCP host/port, MCP auth, error code catalog |
| Observability | Circuit breaker, request ID propagation, JSON logging, health checks, metrics, error schema unification |
| Install/CI | Root lock file, `uv sync`, md2pptx install script, legacy cleanup, suite version, compatibility matrix |
| QA system | Multi-judge LQA, calibration against reference LLM, auto-gen TM, auto-gen glossary, QA regression test |
| Production validation | 50MB file, 5 concurrent, 100 docs/day, full re-audit, Tier 1-5 regression |

## What this plan does NOT cover

- **Docker-compose** (dropped per user instruction)
- Cloud deployment, k8s, Terraform (user runs on local machines)
- Multi-language beyond zh/en (not in scope)
- Scaling beyond 100 docs/day (user's stated ceiling)
- Continuous improvement loop — that's the next phase, AFTER this plan ships

## Key design decision: QA system first

The user's feedback: "adjusting the acceptance won't change anything if
the QA system is not improved."

Current QA (round 12 baseline):
- Single-model LLM judge (`deepseek-v4-flash` per `local.yaml`)
- Score 3.5/5 average, 4.0/5 pass threshold, retry on fail
- No human-rated reference set
- No correlation tracking between LQA scores and actual translation quality

The plan improves the QA system first, then sets acceptance:

1. **Multi-judge** — 3 different LLM judges vote; majority wins.
   Reduces single-model bias. A bad translation needs to fool 2/3
   judges, not 1.
2. **Calibration against reference LLM** — build a 20-doc
   reference set (D1) using the highest-priority model in the
   pool as the implicit "ground truth proxy." LQA judges must
   achieve Spearman ≥ 0.7 + inter-judge agreement ≥ 60% with
   the reference (D3). No humans in the QA system.
3. **Better LLM context** — auto-gen TM and glossary give the
   translator more context, which produces better translations,
   which the QA system can then judge more accurately. The
   quality bar is partly a function of context, not just the
   judge model.
4. **QA system regression test** — runs on every commit. If
   the QA system's Spearman with the reference LLM drops below
   0.7 OR inter-judge agreement drops below 60%, the test
   fails and the user is paged. This is the only human
   touchpoint in the QA system.

Only after the QA system is calibrated do we set the acceptance
threshold for production. The plan proposes ≥ 85% LQA pass rate
at 4.0/5, but this is a **placeholder** until the calibration data
is in.

---

## Phase A: Security (P0, est. 2 days)

**Why P0**: OL MCP path traversal is a live vulnerability. Any
agent calling `load_glossary` / `search_tm` / `translate_xliff`
can read arbitrary files on the host.

### A1. OL MCP path validation
- **File**: `Omni_Localizer/src/ol_mcp/tools.py`
- Add `PathValidator` mirroring `orf/mcp/security.py:PathValidator`:
  - Check `..` in path parts
  - Resolve to absolute path
  - Check against `allowed_directories` (from `OL_ALLOWED_DIRECTORIES` env)
  - Check file extension whitelist (`.json`, `.tmx`, `.xlf`, `.md`)
  - Check file size (100MB default)
  - Check file exists
- Apply in `load_glossary` (line 328-331), `search_tm` (404-405),
  `translate_xliff` (535, 588)
- **Test**: add `test_ol_mcp_path_traversal.py` with attack vectors

### A2. Remove hardcoded API keys
- **File**: `Omni_Localizer/config/local.yaml`
- Replace 6 literal keys (lines 43, 50, 57, 65, 83, 90, 107, 114)
  with `${ENV_VAR}` refs, matching the pattern in `default.yaml`
- Move the actual key values to `.env` (which is gitignored)
- Add a CI check: grep the tracked config files for the 4 secret
  patterns from `loader.py:_check_for_hardcoded_secrets`
  (`sk-[A-Za-z0-9_-]{20,}`, `nvapi-...`, `gsk_...`, `^[a-f0-9]{16,}\.`)
  — fail the build if any match in tracked files
- **Test**: `test_no_hardcoded_keys.py` runs the same grep

### A3. OPP MCP host/port config
- **File**: `Omni_Pre_Processor/src/opp/mcp/config.py`
- Add `host: str = "127.0.0.1"` and `port: int = 8766` fields
  (mirror ORF config)
- Update `__post_init__` to populate from `OPP_MCP_HOST` /
  `OPP_MCP_PORT` env vars
- **Test**: verify config defaults to 127.0.0.1

### A4. MCP auth (shared secret)
- **Files**: all 3 `mcp/server.py`
- Add `MCP_SHARED_SECRET` env var
- Each tool entry checks `MCP_SHARED_SECRET` matches
  (for SSE/HTTP transport only; stdio is local-only)
- On mismatch, return `{"success": False, "error_code": "AUTH_FAILED"}`
- Document in `docs/SECURITY.md`
- **Test**: `test_mcp_auth.py` for each server

### A5. Error code catalog
- **File**: new `docs/ERROR_CODES.md`
- Single document listing all error codes from all 3 MCP servers
  (OPP_*, OL_*, ORF_*) with: code, meaning, when it occurs, what
  the caller should do
- Add `OPPSUITE_*` as a future unified prefix (don't migrate yet;
  document the existing codes)

### Phase A gate
- Re-run security audit (`security_audit.sh` script or equivalent)
- Zero high/critical findings
- Tier 1-5 regression: 36/36 still green

---

## Phase B: Observability (P0/P1, est. 3 days)

**Why P0/P1**: Without circuit breaker, an LLM outage generates
thousands of failing retries. Without request ID, debugging a
failed translation is archaeology across three log files.

### B1. Circuit breaker for LLM calls
- **File**: `Omni_Localizer/src/ol_pool/router.py`
- Use `pybreaker` (add to `pyproject.toml` deps)
- 5 consecutive failures across any model in a role → open
- Reset after 60s
- Half-open: allow 1 probe request
- Log breaker state transitions at WARNING level
- **Test**: `test_circuit_breaker.py` — mock LLM, force 5 failures,
  verify 6th call short-circuits

### B2. Request ID propagation
- **Protocol**: OPP generates `request_id = uuid.uuid4()` on each
  extraction, writes it to `manifest.json` (new field) and
  XLIFF `<header><note from="OPP">request_id=...</note></header>`
- OL reads `request_id` from OPP manifest or XLIFF header
  (line ~300 of `translate_xliff`), writes to MD frontmatter
  `request_id: <uuid>` and XLIFF header
- ORF reads `request_id` from translated MD/XLIFF frontmatter
  or header, logs it in audit log
- All three loggers include `request_id` in every log line
  (structured logging field)
- **Test**: `test_request_id_propagation.py` — run OPP→OL→ORF
  on a doc, verify the same `request_id` appears in all 3
  audit logs and the final output

### B3. Structured JSON logging
- **Files**: all 3 `logger.py` / `logging/__init__.py`
- Use `python-json-logger` (add to deps)
- Every log line is a JSON object with fields:
  `timestamp`, `level`, `module`, `request_id`, `message`,
  plus any context
- Keep human-readable console output via separate handler
  (env var `OMNI_LOG_FORMAT=json|console`, default `console`)
- **Test**: `test_json_logging.py` — log a message, parse the
  output as JSON, verify fields

### B4. Health check endpoints
- **Files**: `ol_mcp/server.py`, `orf/mcp/server.py`
- Add `ping()` tool to both (already in OPP)
- Returns `{"success": True, "module": "ol|orf", "version": "..."}`
- **Test**: `test_mcp_health.py` — call ping, assert success

### B5. Metrics export
- **File**: new `Omni_Suite/omni_metrics/` package (shared)
- Use `prometheus_client` (add to root `pyproject.toml`)
- Counters: `omni_translations_total{module, lang_pair, status}`,
  `omni_llm_errors_total{model, error_type}`,
  `omni_rate_limit_hits_total{model}`
- Histograms: `omni_translation_duration_seconds{module, lang_pair}`,
  `omni_file_size_bytes{module}`
- Expose via `/metrics` endpoint on a separate port (8767)
  (HTTP, localhost only)
- Scrape interval: 15s
- **Test**: `test_metrics.py` — run a translation, scrape
  `/metrics`, verify counter incremented

### B6. MCP error schema unification
- **Files**: all 3 `mcp/_errors.py`
- Pick OPP's dict-based return as the standard
  (not OL's JSON string, not ORF's nested `errors` list)
- Define unified error schema:
  ```json
  {
    "success": false,
    "error_code": "OMNI_*",
    "message": "human-readable",
    "details": {...}  // optional, module-specific
  }
  ```
- Migrate OL and ORF to return dicts (not JSON strings)
- Unified prefix: `OMNI_*` (replaces `OPP_*`, `OL_*`, unprefixed ORF)
- Keep backward compat: old codes map to new (OPP_FILE_NOT_FOUND
  → OMNI_FILE_NOT_FOUND, etc.)
- **Test**: `test_error_schema.py` — call each tool, verify
  schema matches

### Phase B gate
- Re-run observability audit
- All 5 pillars (errors, logging, retries, metrics, tracing) present
- Tier 1-5 regression: 36/36

---

## Phase C: Install/CI (P1, est. 1 day)

**Why P1**: The Hermes machine install is currently a copy-the-
steps-from-SETUP.md exercise. Should be `git clone && uv sync &&
bash install.sh`.

### C1. Root workspace + lock file
- **File**: new `Omni_Suite/pyproject.toml`
- Workspace definition covering all 3 submodules
- `uv sync` at the suite root installs everything
- Generates `Omni_Suite/uv.lock` (replaces the 3 independent
  submodule lockfiles; or keeps them but adds a root one that
  references them)
- Add `omni-suite` as the meta-package name

### C2. md2pptx install script
- **File**: new `Omni_Suite/scripts/install_md2pptx.sh`
- Clones `MartinPacker/md2pptx` to a stable path
  (`~/.local/share/omni-suite/md2pptx/`)
- `chmod +x` and symlink to `~/.local/bin/md2pptx`
- Verifies with `md2pptx --version`
- Idempotent: re-running is a no-op
- Documented in `SETUP.md` and called from `setup_dev.sh`

### C3. CI uses uv sync
- **File**: `.github/workflows/e2e-tests.yml`
- Replace `pip install -e ./Omni_Pre_Processor[all,mcp,dev] ...`
  with `uv sync --frozen` (uses root lock file)
- Remove duplicate `OMNI_TEST_FAKE_LLM=1` line
- Add step: `bash scripts/install_md2pptx.sh`
- Add step: scan tracked config files for hardcoded secrets
  (Phase A2)

### C4. Legacy cleanup
- Delete `run_test.sh` (broken, references deprecated `.venv312`)
- Delete `.venv/` (Python 3.12, superseded by `.venv_ol/`)
- Update `README.md` to remove all `run_test.sh` references
- Update `setup_dev.sh` to use `uv sync` instead of `pip install -e`

### C5. Suite version + compatibility matrix
- **File**: new `Omni_Suite/VERSION` (single line: `0.1.0`)
- **File**: new `Omni_Suite/COMPATIBILITY.md`
  | Suite | OL | OPP | ORF | Notes |
  | 0.1.0 | 0.2.6 | 0.5.7 | 0.3.0 | Initial production |
- Add version assertion in `setup_dev.sh`:
  OPP/OL/ORF versions must match `COMPATIBILITY.md`
- Add `omni-suite --version` CLI (reads VERSION)

### Phase C gate
- Fresh checkout on the user's machine: `git clone && uv sync &&
  bash setup_dev.sh` → working state in <10 min
- Fresh checkout on Hermes machine: same flow, same result
- CI runs `uv sync --frozen` and passes
- Tier 1-5 regression: 36/36

---

## Phase D: QA system (P2, est. 3 days)

**Why P2 but critical for the user's goal**: The user wants
"full auto with QA, auto-gen TM, glossary." The current QA system
is not reliable enough to support full auto. This phase is the
core of the "ready for production" claim.

### D1. LLM-built reference set (no human ratings)
- **File**: new `Omni_Suite/eval/reference/`
- 20 source documents covering: legal (zh/en), product catalog (zh),
  literature (en), technical doc (en), email (mixed), notebook
  (en), CSV (zh), XML (en)
- For each doc, store: source + reference LLM translation
  (generated by the highest-priority model in the pool,
  currently `deepseek-v4-flash`)
- **Reference LLM must be held out from the active translation
  pool**: remove `deepseek-v4-flash` from the `translation:`
  list in `Omni_Localizer/config/local.yaml` and
  `config/default.yaml` before D1 runs. This prevents
  self-referential calibration — the QA system would otherwise
  be measuring whether it agrees with a model that is also
  producing the work being evaluated.
- The reference LLM's output is the implicit "ground truth proxy"
  for calibration — we measure how well the multi-judge
  agrees with the reference, not how well it agrees with humans
- Stored as `{doc_id}_source.md` + `{doc_id}_reference.md`
  (no human scores needed)
- **Effort**: 2-3 hours of automated runs (vs 2 days of human
  review). Cost: ~$5-20 in LLM API calls
- **Rationale**: per user instruction, no human in the loop.
  LLM-built reference is the best available ground truth proxy
  without humans. The multi-judge's job is to rank the same way
  the reference ranks, not to match human quality judgment.

### D2. Multi-judge LQA
- **File**: new `Omni_Localizer/src/ol_lqa/multi_judge.py`
- Use 3 different LLM judges from different providers
  (e.g., Zhipu + Agnes + NVIDIA deepseek)
- Each scores 1-5 on adequacy, fluency, terminology, format
- Majority vote per dimension (2/3 wins)
- If tied, take the median
- Output: `MultiJudgeResult(adequacy, fluency, terminology, format)`
- **Test**: `test_multi_judge.py` — known translation with
  known-good/bad segments, verify majority detects

### D3. Calibration against reference LLM (not human ratings)
- **File**: new `Omni_Localizer/src/ol_lqa/calibration.py`
- Run the multi-judge on the 20-doc reference set (from D1)
- Compute two calibration metrics:
  1. **Spearman ≥ 0.7** between multi-judge scores and reference
     LLM scores (across all 20 docs, per dimension)
  2. **Inter-judge agreement ≥ 60%** (at least 2 of 3 judges
     give the **exact same** score on the 1-5 scale — no
     ±1 tolerance; this prevents the threshold from passing
     on near-random scores)
- If either threshold is violated, log WARNING and emit metric
  `omni_lqa_calibration_drift{metric, value}`
- Calibration run is a CLI: `ol calibrate --reference eval/reference/`
- **Test**: `test_calibration.py` — reference set, verify
  Spearman ≥ 0.7 AND inter-judge agreement ≥ 60%
- **Reference LLM**: the highest-priority model in the pool
  (currently `deepseek-v4-flash`). Re-calibrate if the reference
  model changes.
- **Why this works without humans**: Spearman measures whether
  the multi-judge ranks translations the same way as the
  reference. If both rank A > B > C, they agree on relative
  quality even if their absolute scores differ. The 0.7 bar
  is "strong agreement" — the standard for trustworthy
  automated evaluation.

### D4. Auto-gen translation memory
- **File**: new `Omni_Localizer/src/ol_tm/auto_gen.py`
- On a new translation request, search past TMX for similar
  segments (fuzzy match, cosine similarity via embeddings)
- Top-3 similar segments injected as in-context examples
  in the LLM prompt
- TMX store: `~/.local/share/omni-suite/tm/{lang_pair}.tmx`
- CLI: `ol tm build --corpus ./my-docs/ --lang-pair zh-en`
- **Test**: `test_auto_tm.py` — known corpus, verify top-3
  similar segments are returned

### D5. Auto-gen glossary
- **File**: new `Omni_Localizer/src/ol_terminology/auto_gen.py`
- Use KeyBERT or YAKE (already in OL deps) to extract key terms
  from the source corpus
- For each term, prompt the LLM for the most likely translation
  in the target language
- Output: JSON glossary, injected into OL prompt
- CLI: `ol glossary build --corpus ./my-docs/ --src zh --tgt en`
- **Test**: `test_auto_glossary.py` — known corpus, verify
  domain terms extracted

### D6. QA regression test
- **File**: new `Omni_Suite/tests/qa/test_qa_calibration.py`
- Runs the multi-judge on the 20-doc reference set (D1)
- Asserts both calibration thresholds:
  1. **Spearman ≥ 0.7** with reference LLM (per dimension)
  2. **Inter-judge agreement ≥ 60%** (majority consensus)
- Runs in CI nightly (not on every commit — costs ~5min LLM time)
- **Gate**: if either threshold is violated, the test fails
  and the human (user) is paged. This is the **only** human
  touchpoint in the QA system — a failure alert, not a quality
  gate. The success path is fully automated.

### Phase D gate
- Reference set built (20 docs with reference LLM translations)
- Multi-judge runs on reference set: Spearman ≥ 0.7 AND
  inter-judge agreement ≥ 60%
- Auto-TM: given a new doc, finds ≥1 relevant past segment
- Auto-glossary: given a 10-doc corpus, extracts ≥50 terms
- Tier 1-5 regression: 36/36

---

## Phase E: Production validation (gate, est. 1 day)

**Why**: The plan delivers all the pieces. Now we prove they
work together under the user's stated load.

### E1. 50MB file test
- Generate or find a 50MB DOCX (use `sherlock_holmes.docx` scaled
  up if needed)
- Run OPP→OL→ORF end-to-end
- Verify: no crashes, output valid, P95 latency < 5 min
- **Test**: `test_production_50mb.py` (gated on fixture availability)

### E2. 5 concurrent load test
- Use `locust` or a custom script
- 5 concurrent translations for 1 hour
- 100 docs/hour sustained (way above 100/day target)
- Monitor: CPU, memory, API error rate, queue depth
- Verify: zero crashes, P95 latency stable, no memory leaks
  (heap usage doesn't grow over 1 hour)
- **Test**: `test_load_5concurrent.py` (run manually, not CI)

### E3. 100 docs/day simulation
- 100 docs (mix of formats and sizes) over 8 hours
- Simulate realistic arrival pattern (bursts + quiet periods)
- Verify: 100/100 complete successfully, quality score above
  threshold (set after Phase D calibration)
- **Test**: `test_throughput_100perday.py` (run manually)

### E4. Full re-audit
- Re-run all 3 audit scripts (security, observability, install)
- Zero new high/critical findings
- Tier 1-5 regression: 36/36 still green

### E5. Acceptance threshold (only now)
- After D3 calibration is in, set the production acceptance:
  - **LQA pass rate ≥ 85%** at multi-judge ≥ 4.0/5 average
  - **Spearman ≥ 0.7** between multi-judge and reference LLM
  - **Inter-judge exact-match agreement ≥ 60%**
- These are real numbers based on the calibrated QA system, not
  arbitrary thresholds

### Phase E gate
- 50MB file: PASS
- 5 concurrent / 1 hour: PASS, zero crashes
- 100 docs/day: PASS, ≥ 85% LQA pass rate
- All 3 audits: zero new findings
- Tier 1-5: 36/36
- **→ System is production ready**

---

## Timeline & dependencies

```
Phase A (Security, 2d) ──┐
                         ├─→ Phase B (Observability, 3d) ──┐
                         │                                  ├─→ Phase D (QA, 3d) ──→ Phase E (Validation, 1d)
                         └─→ Phase C (Install/CI, 1d) ─────┘
```

- A and C can run in parallel (independent)
- B depends on A (auth changes affect observability hooks)
- D depends on B (multi-judge needs metrics)
- E depends on all

**Total: ~9 days focused work (no human review in QA), assuming no major surprises**

## After this plan ships: the auto-driven loop

The plan delivers "ready for production." The next loop is
**continuous improvement**, not gap-fixing:

- **Objective**: maximize LQA pass rate while minimizing cost
- **Cycle**:
  1. Run the user's actual document corpus through the pipeline
  2. Collect real-world LQA scores + low-scoring segments
  3. Find the lowest-scoring segments
  4. Improve: better model selection, better glossary, better
     TM, better prompt
  5. Re-run, measure improvement
- **Loop termination**: when improvement plateaus (LQA pass
  rate stops increasing across 3 consecutive cycles)

This loop is fundamentally different from the previous 14 rounds:
- Previous: fix what the test suite flags
- New: improve what real-world quality demands

---

## File-by-file change summary

### New files
- `Omni_Suite/pyproject.toml` (C1)
- `Omni_Suite/uv.lock` (C1)
- `Omni_Suite/VERSION` (C5)
- `Omni_Suite/COMPATIBILITY.md` (C5)
- `Omni_Suite/docs/ERROR_CODES.md` (A5)
- `Omni_Suite/scripts/install_md2pptx.sh` (C2)
- `Omni_Suite/scripts/audit_security.sh` (A gate)
- `Omni_Suite/scripts/audit_observability.sh` (B gate)
- `Omni_Suite/scripts/audit_install.sh` (C gate)
- `Omni_Suite/omni_metrics/` package (B5)
- `Omni_Suite/eval/reference/` directory (D1)
- `Omni_Suite/eval/reference/{doc_id}_source.md` × 20 (D1)
- `Omni_Suite/eval/reference/{doc_id}_reference.md` × 20 (D1)
- `Omni_Localizer/src/ol_lqa/multi_judge.py` (D2)
- `Omni_Localizer/src/ol_lqa/calibration.py` (D3)
- `Omni_Localizer/src/ol_tm/auto_gen.py` (D4)
- `Omni_Localizer/src/ol_terminology/auto_gen.py` (D5)
- `Omni_Suite/tests/qa/test_qa_calibration.py` (D6)
- `Omni_Suite/tests/qa/test_multi_judge.py` (D2)
- `Omni_Suite/tests/qa/test_auto_tm.py` (D4)
- `Omni_Suite/tests/qa/test_auto_glossary.py` (D5)
- `Omni_Suite/tests/security/test_ol_mcp_path_traversal.py` (A1)
- `Omni_Suite/tests/security/test_no_hardcoded_keys.py` (A2)
- `Omni_Suite/tests/security/test_mcp_auth.py` (A4)
- `Omni_Suite/tests/observability/test_circuit_breaker.py` (B1)
- `Omni_Suite/tests/observability/test_request_id_propagation.py` (B2)
- `Omni_Suite/tests/observability/test_json_logging.py` (B3)
- `Omni_Suite/tests/observability/test_mcp_health.py` (B4)
- `Omni_Suite/tests/observability/test_metrics.py` (B5)
- `Omni_Suite/tests/observability/test_error_schema.py` (B6)
- `Omni_Suite/tests/production/test_50mb_file.py` (E1)
- `Omni_Suite/tests/production/test_load_5concurrent.py` (E2)
- `Omni_Suite/tests/production/test_throughput_100perday.py` (E3)

### Modified files
- `Omni_Localizer/src/ol_mcp/tools.py` (A1: path validation)
- `Omni_Localizer/src/ol_mcp/server.py` (A4: auth, B3: logging, B4: ping, B6: error schema)
- `Omni_Localizer/config/local.yaml` (A2: remove hardcoded keys)
- `Omni_Localizer/src/ol_config/loader.py` (B6: error schema)
- `Omni_Localizer/src/ol_pool/router.py` (B1: circuit breaker, B5: metrics)
- `Omni_Localizer/src/ol_logging/core.py` (B3: JSON logging, B2: request_id)
- `Omni_Pre_Processor/src/opp/mcp/config.py` (A3: host/port)
- `Omni_Pre_Processor/src/opp/mcp/server.py` (A4: auth, B2: request_id, B3: logging)
- `Omni_Pre_Processor/src/opp/pipeline.py` (B2: write request_id to manifest)
- `Omni_Pre_Processor/src/opp/logger.py` (B3: JSON logging)
- `Omni_Re_Formatter/src/orf/mcp/server.py` (A4: auth, B3: logging, B4: ping, B6: error schema)
- `Omni_Re_Formatter/src/orf/mcp/_errors.py` (B6: error schema)
- `Omni_Re_Formatter/src/orf/logging/__init__.py` (B2: request_id, B3: JSON logging)
- `Omni_Re_Formatter/src/orf/cli.py` (B2: read request_id)
- `Omni_Re_Formatter/pyproject.toml` (B5: prometheus_client, C1: workspace)
- `Omni_Localizer/pyproject.toml` (B1: pybreaker, B5: prometheus_client, C1: workspace)
- `Omni_Pre_Processor/pyproject.toml` (C1: workspace)
- `Omni_Suite/.github/workflows/e2e-tests.yml` (C3: uv sync, md2pptx install, secrets scan)
- `Omni_Suite/scripts/setup_dev.sh` (C4: use uv sync, call md2pptx install)
- `Omni_Suite/README.md` (C4: remove run_test.sh refs)
- `Omni_Suite/SETUP.md` (C2: document md2pptx, C5: suite version)
- `Omni_Suite/docs/SECURITY.md` (A4: auth model, A5: error code catalog ref)

### Deleted files
- `Omni_Suite/run_test.sh` (C4)
- `Omni_Suite/.venv/` (C4)

### Commit strategy
One commit per phase (A, B, C, D, E), each passing the phase gate.
Within a phase, sub-commits per item (A1, A2, A3, ...).

---

## What I need from you to start

1. **Confirm the plan structure** — 5 phases, this order, this
   scope. Anything you want to add/remove/reorder?

2. **Confirm the QA system approach** — specifically D1 (LLM-
   built reference set, 20 docs, 2-3 hours of automated runs),
   D2 (multi-judge from 3 providers), D3 (calibration via
   Spearman ≥ 0.7 + inter-judge agreement ≥ 60% against the
   reference LLM, not humans). The only human touchpoint is
   the D6 regression test failure alert.

3. **Confirm Phase A is unblocked** — security fixes touch
   production code paths. The user's own usage will exercise
   these. Comfortable shipping them first?

4. **Anything else dropped from the plan** that you want kept
   (e.g., docker-compose for future, cloud deployment hooks)?

Once you confirm, I'll start Phase A immediately. I have all the
context I need from the 3 audits — no more investigation required.
