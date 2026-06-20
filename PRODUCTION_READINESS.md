# Omni Suite — Production-Readiness Checklist

> Every item below must pass before a component, pipeline change, or suite release is declared "production-ready."
> Items marked with a wrench (🔧) are auto-checkable by `omni-suite check --readiness`.
> Items marked with a manual (🖐️) require human verification.

---

## V1 — Version Consistency

| # | Check | Method | Auto? |
|---|-------|--------|-------|
| 1.1 | Suite `VERSION` file matches the "Suite" column in `COMPATIBILITY.md` table | Compare `VERSION` content to first column, first data row | 🔧 |
| 1.2 | Each submodule's `pyproject.toml` `version` matches the corresponding column in `COMPATIBILITY.md` | Parse each module's `pyproject.toml` and cross-reference | 🔧 |
| 1.3 | Each submodule's `__version__` attribute (if exposed) matches its `pyproject.toml` | `import opp; opp.__version__` == pyproject version | 🔧 |
| 1.4 | Installed wheel version matches source version (no stale installs) | `pip show omni-pre-processor` version == pyproject version | 🔧 |
| 1.5 | `setup_dev.sh` version-assertion logic references the current `COMPATIBILITY.md` | Parse `setup_dev.sh` for expected version regex | 🔧 |

---

## V2 — Module Integrity

| # | Check | Method | Auto? |
|---|-------|--------|-------|
| 2.1 | Each module is importable without errors | `python -c "import opp"`, `import ol`, `import orf` | 🔧 |
| 2.2 | Each module's CLI entry point responds to `--help` | `opp --help`, `ol --help`, `orf --help` exit 0 | 🔧 |
| 2.3 | Each MCP server starts, responds to `ping`, and shuts down cleanly | MCP client `ping` on all 3 servers | 🔧 |
| 2.4 | Each module's CLI provides a `--version` flag with correct output | Parse CLI output, compare to expected version | 🔧 |
| 2.5 | `omni-suite status` reports all three modules with correct versions | Run `omni-suite status`, check output | 🔧 |
| 2.6 | No circular imports between modules | Module-level static analysis | 🔧 |
| 2.7 | All declared `[project.scripts]` entry points resolve to existing functions | Check each console_scripts target | 🔧 |

---

## V3 — FAKE_LLM Seam Integrity

| # | Check | Method | Auto? |
|---|-------|--------|-------|
| 3.1 | `OMNI_TEST_FAKE_LLM=1` lets OL start without real LLM config | Run `OL_CONFIG_PATH=/dev/null ol --help` with FAKE_LLM | 🔧 |
| 3.2 | OL span_aligner stubs correctly under FAKE_LLM seam | Import OL, check `_FakeModelPool` is installed | 🔧 |
| 3.3 | `OMNI_TEST_FAKE_PANDOC=1` lets ORF run without pandoc | Run `orf --help` with FAKE_PANDOC | 🔧 |
| 3.4 | No test sets `OMNI_TEST_FAKE_LLM` then calls a real LLM | grep for patterns that bypass the seam | 🔧 |
| 3.5 | FAKE_LLM output is deterministic (same input → same output) | Run twice, diff output | 🖐️ |
| 3.6 | Real-LLM tests (`nightly` marker) correctly skip when no API keys | `pytest tests/ -m nightly` should SKIP without keys | 🔧 |

---

## V4 — Test Infrastructure

| # | Check | Method | Auto? |
|---|-------|--------|-------|
| 4.1 | All 12 pytest markers are registered in `tests/conftest.py` | Parse `pytest_configure()` marker registration | 🔧 |
| 4.2 | `tests/test_pipeline_contract_smoke.py` exists and runs | File existence + dry run; this file is referenced but currently MISSING | 🔧 |
| 4.3 | Each module has a `tests/` directory with at least one test | Directory existence check | 🔧 |
| 4.4 | No test file contains `@pytest.mark.skip` without a documented reason | grep for bare `@pytest.mark.skip` | 🔧 |
| 4.5 | All `xfail` markers have a `reason=` string | grep for `@pytest.mark.xfail` without reason | 🔧 |
| 4.6 | CI-mode tests pass with `OMNI_TEST_FAKE_LLM=1` | Run `make test` or equivalent | 🔧 |
| 4.7 | E2E tests cover both the MD channel and XLIFF channel | grep for test functions covering each path | 🔧 |
| 4.8 | Test fixture documents (DOCX, PPTX, PDF) are present and non-empty | File existence + size check | 🔧 |
| 4.9 | No test relies on network access unless marked `nightly` | Static analysis of test imports | 🖐️ |

---

## V5 — CI/CD Pipeline

| # | Check | Method | Auto? |
|---|-------|--------|-------|
| 5.1 | GitHub Actions workflow `.github/workflows/e2e-tests.yml` is valid YAML | YAML parse | 🔧 |
| 5.2 | Pre-commit hooks pass on all files | `pre-commit run --all-files` exit 0 | 🔧 |
| 5.3 | gitleaks hook is configured and runs | Check `.pre-commit-config.yaml` for gitleaks | 🔧 |
| 5.4 | `Makefile` targets work: `test`, `smoke`, `lint`, `clean` | Dry-run each target | 🔧 |
| 5.5 | CI workflow has a timeout set (prevent runaway jobs) | Check `timeout-minutes` in workflow | 🔧 |
| 5.6 | Nightly job depends on CI passing (not orphaned) | Check `needs:` in workflow | 🔧 |
| 5.7 | Test output is captured as CI artifacts if tests fail | Check `actions/upload-artifact` usage | 🔧 |
| 5.8 | CI uses `uv sync --frozen` (reproducible installs) | Check CI workflow for frozen flag | 🔧 |

---

## V6 — Production Tests (E1–E3)

| # | Check | Method | Auto? |
|---|-------|--------|-------|
| 6.1 | E1: 50MB DOCX processes within P95 latency < 5 minutes | Run `test_e1_50mb.py` with fixture | 🔧 |
| 6.2 | E1 fixture exists when test is not skipped | Check `OMNI_E1_FIXTURE_PATH` or default path | 🔧 |
| 6.3 | E2: 5-concurrent load produces zero crashes | Run `test_e2_load.py` | 🔧 |
| 6.4 | E2: Memory growth stays under 500 MB during concurrent load | Check heap delta in E2 output | 🔧 |
| 6.5 | E3: 100 docs/day throughput target is reachable | Run `test_e3_throughput.py` | 🔧 |
| 6.6 | E3: Pass rate meets 85% threshold | Check pass rate in E3 output | 🔧 |
| 6.7 | Each E test has a `SKIP_ENV` escape hatch | grep for `SKIP_ENV` in each e test | 🔧 |
| 6.8 | E tests are NOT marked `nightly` (they run in CI) | Check pytest markers on E tests | 🔧 |

---

## V7 — Security

| # | Check | Method | Auto? |
|---|-------|--------|-------|
| 7.1 | No hardcoded API keys, tokens, or secrets in source | `gitleaks` scan + `tests/security/test_no_hardcoded_keys.py` | 🔧 |
| 7.2 | MCP servers validate file paths (no path traversal) | `tests/security/` path traversal tests pass | 🔧 |
| 7.3 | Pre-commit `detect-private-key` hook fires | Check `.pre-commit-config.yaml` | 🔧 |
| 7.4 | No `.env` files committed to git | Check `.gitignore` + git tracked files | 🔧 |
| 7.5 | MCP `allowed_directories` is configured (OPP_ALLOWED_DIRECTORIES) | grep for env var in MCP server code | 🔧 |
| 7.6 | All security tests pass | `pytest tests/security/` exit 0 | 🔧 |

---

## V8 — Observability

| # | Check | Method | Auto? |
|---|-------|--------|-------|
| 8.1 | Circuit breaker tests pass | `pytest tests/observability/` for circuit_breaker | 🔧 |
| 8.2 | JSON logging is structured and parseable | Run pipeline, check log output is valid JSON | 🔧 |
| 8.3 | Each MCP server has a working health/ping endpoint | MCP ping on all 3 servers | 🔧 |
| 8.4 | Metrics are exported via prometheus_client | Check `omni_metrics` for metric definitions | 🔧 |
| 8.5 | Request IDs flow through the pipeline (OPP→OL→ORF trace) | Run pipeline, check request_id propagation | 🔧 |
| 8.6 | All 38 observability tests pass | `pytest tests/observability/ -q` | 🔧 |

---

## V9 — Cross-Format Compatibility

| # | Check | Method | Auto? |
|---|-------|--------|-------|
| 9.1 | All 16 ORF output formats are listed in `apply_md` tool definition | Parse MCP tool definition | 🔧 |
| 9.2 | DOCX → MD → DOCX roundtrip preserves content | Run pipeline on fixture, diff content | 🔧 |
| 9.3 | XLIFF → cross-format conversion works (e.g., DOCX XLIFF → PPTX) | `orf apply-xliff --force` on cross-format | 🔧 |
| 9.4 | HTML/CSV/JSON input extracts correctly via MD path | Run OPP on each format | 🔧 |
| 9.5 | PDF → XLIFF is correctly blocked (not silently broken) | `orf generate-xliff` on PDF should error | 🔧 |
| 9.6 | EML → MSG path does not crash on missing headers | Run OPP on EML, verify graceful handling | 🔧 |
| 9.7 | `.url` (YouTube) transcription does not hang | Run OPP with timeout guard | 🔧 |
| 9.8 | Image extraction produces valid image files | Check images from pipeline are non-corrupt | 🖐️ |

---

## V10 — Error Handling & Resilience

| # | Check | Method | Auto? |
|---|-------|--------|-------|
| 10.1 | Missing input file → informative error, not traceback | Run CLI on nonexistent file | 🔧 |
| 10.2 | Corrupted input file → informative error, not crash | Run CLI on corrupted file | 🔧 |
| 10.3 | Empty XLIFF → proper validation error | Run with empty XLIFF | 🔧 |
| 10.4 | Pipeline timeout produces exit code 1 with message | Run pipeline on oversized input with short timeout | 🔧 |
| 10.5 | All `except` blocks log the error (no silent swallows) | grep for `except:` without logging | 🖐️ |
| 10.6 | Subprocess failures propagate to CLI exit code | Check return codes from subprocess.run callers | 🔧 |
| 10.7 | Skeleton ZIP corruption is handled (partial recovery, not crash) | Apply corrupted skeleton, verify graceful error | 🔧 |

---

## V11 — Documentation

| # | Check | Method | Auto? |
|---|-------|--------|-------|
| 11.1 | `README.md` exists and is non-empty at suite root | File existence + size | 🔧 |
| 11.2 | Each submodule has a `README.md` or `AGENTS.md` | File existence | 🔧 |
| 11.3 | `AGENTS.md` CLI cheat sheet table matches current tool counts | Check table row counts vs actual | 🖐️ |
| 11.4 | Cross-format support matrix in README is up to date | Review matrix against test coverage | 🖐️ |
| 11.5 | All `--help` output is accurate and matches actual CLI | Spot-check each CLI | 🖐️ |

---

## Scoring

| Score | Meaning |
|-------|---------|
| 🔴 Not Ready | 1+ V1–V3 items failing (blocking) |
| 🟡 Needs Work | All V1–V3 pass, but 1+ V4–V7 items failing |
| 🟢 Production-Ready | All 🔧 items pass, no known 🖐️ failures |
| 🏆 Certified | All items pass, including 🖐️ human verification |

### Scoring Rules

- **V1–V3 are blocking**: Version inconsistency or module breakage means the suite is not in a shippable state.
- **V4–V7 are required**: Test infrastructure, CI/CD, production tests, and security must be green.
- **V8–V11 are quality gates**: Observability, format coverage, error handling, and docs determine the quality level.

### How to Score

```bash
# Quick score (auto-checkable items only)
omni-suite check --readiness

# Full score (includes items requiring human verification)
omni-suite check --readiness --verbose
# Then manually verify the 🖐️ items listed in the output
```

The output from `omni-suite check --readiness` reports pass/fail counts per version category and the overall score.
