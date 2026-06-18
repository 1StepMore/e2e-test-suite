# Round 16 Phase C Handoff — Session Break Recovery

**Date:** 2026-06-18
**Status:** Phases A and B complete. Phase C ready to start.
**Plan:** `.omo/plans/2026-06-18-production-readiness-plan.md`

---

## What We Accomplished (Phases A + B)

### Phase A: Security — COMPLETE

| Item | Scope | Main repo commit | Submodule commit |
|------|-------|-----------------|-----------------|
| A1 — OL MCP path validation | PathValidator + 25 tests | `5b7e400` | OL `2af9eb4` |
| A2 — Hardcoded key removal | 3 keys → env vars + 5 tests | `a658c2f` | — |
| A3 — OPP MCP host/port | config + `_parse_allowed_dirs` fix + 7 tests | `5726efb` | OPP `33b26e8` |
| A4 — MCP shared-secret auth | 3 modules × all tools + 26 tests | `efc6103` (OL tests), `ce73f7a` (OPP+ORF tests) | OL `d6e4d79`, OPP `298f952`, ORF `056e0a9` (amended from `3c6837b`) |
| A5 — Error code catalog | `docs/ERROR_CODES.md` | `0d83399` | — |

**Phase A result:** 79 new security tests, 0 regressions.

### Phase B: Observability — COMPLETE

| Item | Scope | Main repo commit | Submodule commit |
|------|-------|-----------------|-----------------|
| B1 — Circuit breaker | OL only (`pybreaker`, 5 fails/60s reset) | `447b285` (tests) | OL `16ef4ea` |
| B2 — Request ID propagation | All 3 modules: OPP generate → OL read+propagate → ORF read+log | `3df8840` (OPP tests), request_id_orf tests | OPP `503079a`, OL `5972d7b`, ORF `fafea05` |
| B3 — Structured JSON logging | All 3 modules (`OMNI_LOG_FORMAT=json`) | `a3c87ab` (tests) | OL `e15e5d2`, OPP `f33b6c4`, ORF `6e0fc5a` |
| B4 — Health endpoints | OL + ORF (`ping()` tool) | `68762e7` (tests) | OL `26705c1`, ORF `273def6` |
| B5 — Metrics export | Shared `omni_metrics/` + OPP/OL wiring + deps | `2400258` (package), `dd08adf` (wiring tests) | OPP `6c2ea7b`, OL `d02158d` (amended with `import time` fix) |

**Phase B result:** 38 new observability tests, 0 regressions across 154-test regression suite.

### 5 Observability Pillars (all present)

| Pillar | Where |
|--------|-------|
| Errors | `docs/ERROR_CODES.md` |
| Logging | JSON formatter in OPP/OL/ORF (B3) |
| Retries | Circuit breaker in OL (B1) |
| Metrics | `omni_metrics` package + OPP/OL wiring (B5) |
| Tracing | `request_id` OPP→OL→ORF (B2) |

---

## Current State

### Git Status
- Main repo: clean, 15 commits ahead of round 14
- All 3 submodules: clean, all Phase A+B commits present
- No uncommitted changes

### Test Counts (all passing)
- Observability: 38/38
- Security: 63/63
- OPP submodule security: 41/41 (5 skipped)
- ORF submodule security: 12/12
- **Total regression: 154/154**

### Test Commands
```bash
cd /mnt/d/贯维/Omni_Suite
# Observability
OL_ALLOW_HARDCODED_KEYS=1 .venv_ol/bin/python -m pytest tests/observability/ -q --no-header -p no:cacheprovider
# Security
OL_ALLOW_HARDCODED_KEYS=1 .venv_ol/bin/python -m pytest tests/security/ -q --no-header -p no:cacheprovider
# OPP submodule
OL_ALLOW_HARDCODED_KEYS=1 .venv_ol/bin/python -m pytest Omni_Pre_Processor/tests/mcp/test_security.py Omni_Pre_Processor/tests/mcp/test_security_attacks.py -q
# ORF submodule
OL_ALLOW_HARDCODED_KEYS=1 .venv_ol/bin/python -m pytest Omni_Re_Formatter/tests/test_security_extensions.py -q
```

### Key File Locations
- `omni_metrics/metrics.py` — shared Prometheus metrics
- `omni_metrics/__init__.py` — package exports
- `docs/ERROR_CODES.md` — error code catalog
- `tests/observability/` — all B-phase tests
- `tests/security/` — all A-phase tests

### Installed Deps (in `.venv_ol`)
- `python-json-logger>=2.0.0` (B3)
- `pybreaker>=1.0.0` (B1, OL only)
- `prometheus_client>=0.20.0` (B5)

---

## Deferred Items (for Phase C or follow-up)

1. **ORF metrics wiring** — ORF has no `log_mcp_audit` equivalent. Would need a new pattern. Currently OPP and OL only.
2. **B5 sys.path injection is fragile** — OPP/OL use `os.path.dirname` x4/x5 to find the main repo for `omni_metrics` import. Phase C root workspace will fix this properly.
3. **A2 manual step** — `local.yaml` is gitignored. Actual key values must be manually copied to `Omni_Localizer/.env` (out of scope for commits, noted in A2 commit message).

---

## Phase C: Install/CI (P1, est. 1 day)

**Why P1:** The Hermes machine install is currently a copy-the-steps-from-SETUP.md exercise. Should be `git clone && uv sync && bash install.sh`.

### C1. Root workspace + lock file
- **File:** new `Omni_Suite/pyproject.toml`
- Workspace definition covering all 3 submodules
- `uv sync` at the suite root installs everything
- Generates `Omni_Suite/uv.lock`
- Add `omni-suite` as the meta-package name
- **This fixes the B5 sys.path injection problem** — `omni_metrics` becomes a proper workspace dep

### C2. md2pptx install script
- **File:** new `Omni_Suite/scripts/install_md2pptx.sh`
- Clones `MartinPacker/md2pptx` to `~/.local/share/omni-suite/md2pptx/`
- `chmod +x` and symlink to `~/.local/bin/md2pptx`
- Verifies with `md2pptx --version`
- Idempotent: re-running is a no-op
- Documented in `SETUP.md` and called from `setup_dev.sh`

### C3. CI uses uv sync
- **File:** `.github/workflows/e2e-tests.yml`
- Replace `pip install -e ./Omni_Pre_Processor[all,mcp,dev] ...` with `uv sync --frozen`
- Remove duplicate `OMNI_TEST_FAKE_LLM=1` line
- Add step: `bash scripts/install_md2pptx.sh`
- Add step: scan tracked config files for hardcoded secrets (Phase A2 regression guard)

### C4. Legacy cleanup
- Delete `run_test.sh` (broken, references deprecated `.venv312`)
- Delete `.venv/` (Python 3.12, superseded by `.venv_ol/`)
- Update `README.md` to remove all `run_test.sh` references
- Update `setup_dev.sh` to use `uv sync` instead of `pip install -e`

### C5. Suite version + compatibility matrix
- **File:** new `Omni_Suite/VERSION` (single line: `0.1.0`)
- **File:** new `Omni_Suite/COMPATIBILITY.md`
  ```
  | Suite | OL    | OPP   | ORF   | Notes                |
  | 0.1.0 | 0.2.6 | 0.5.7 | 0.3.0 | Initial production   |
  ```
- Add version assertion in `setup_dev.sh`: OPP/OL/ORF versions must match `COMPATIBILITY.md`
- Add `omni-suite --version` CLI (reads VERSION)

### Phase C gate
- Fresh checkout on the user's machine: `git clone && uv sync && bash setup_dev.sh` → working state in <10 min

---

## Phase D: QA System (P1, est. 2 days) — brief

- D1: Multi-judge LLM pool (Spearman ≥ 0.7 + inter-judge exact-match ≥ 60%)
- D2: Regression test suite (golden outputs, D6 failure alert to user)
- D3-D6: See plan at `.omo/plans/2026-06-18-production-readiness-plan.md`

**Must-fix from Momus review (applied to plan in commit `56b0e4b`):**
- D1: Remove deepseek-v4-flash from translation pool (also from multi-judge pool — TBD with user)
- D3/D6: Use exact-match (no ±1 tolerance)

## Phase E: Production validation (P1, est. 1 day) — brief

- E1: 3-nightly gauntlet on Hermes machine
- E2: Rollback plan
- E3: Release notes

---

## If Session Breaks — Recovery Steps

1. `cd /mnt/d/贯维/Omni_Suite` — we're in the main repo
2. Read this file: `.omo/plans/2026-06-18-phase-c-handoff.md`
3. Read the full plan: `.omo/plans/2026-06-18-production-readiness-plan.md`
4. Check `git log --oneline -20` to confirm Phase A+B commits are present
5. Check `git status` — should be clean
6. To resume Phase C, start with C1 (root `pyproject.toml` workspace)

---

## Key Context for Next Session

- **Submodule state:** All 3 submodules installed in editable mode in `.venv_ol` (Python 3.13)
- **Hermes machine:** OL MCP runs from `~/.hermes/venvs/omni-localizer` (separate venv)
- **Test env var:** `OL_ALLOW_HARDCODED_KEYS=1` must be set for security tests (A2 regression guard)
- **Conftest pattern:** `tests/conftest.py` has shared fixtures; `tests/security/conftest.py` may need `allowed_dir` fixture per test file
- **Timeout:** Tests importing `ol_mcp` trigger `litellm` (~26s), need ≥120s timeout
- **pymcp 1.27.2:** No `add_middleware`, no `auth` methods — A4 used per-tool check
- **Commit style:** `fix(scope): round 16 Phase X — description` (round-history in commit body is fine, not in message)
- **Test file style:** 1 file per phase item, classes per concern, fixtures at module/class level
- **Moment-of-truth verification:** Always run the actual test command, never assume it works
