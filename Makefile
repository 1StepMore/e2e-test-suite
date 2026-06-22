# =============================================================================
# Omni Suite — Developer Makefile
# =============================================================================
#
# Targets:
#   setup         — Full dev environment setup (venv, install, smoke test)
#   test          — Run all CI-mode tests (OPP + OL + ORF + suite e2e)
#   test-quick    — Run root suite only (pytest tests/ -m "not nightly" -q)
#   test-opp      — Run OPP CI-mode tests
#   test-ol       — Run OL CI-mode tests
#   test-orf      — Run ORF CI-mode tests
#   test-contract       — Run CLI + MCP contract tests (Section 7.5 + Phase 4.7)
#   test-contract-cli   — Run CLI --help contract tests only
#   test-contract-mcp   — Run MCP tool-schema contract tests only (21 tools)
#   smoke         — Run contract smoke test
#   lint          — Run ruff + mypy on parent + submodules
#   matrix        — Run full MD matrix via real MCP (165 cells)
#   matrix-subset — Run MD matrix on a single input format
#   clean         — Remove __pycache__, .pytest_cache, build artifacts
#
# =============================================================================

.PHONY: setup test test-quick test-opp test-ol test-orf test-contract test-contract-cli test-contract-mcp test-logs test-metrics test-tracing test-distributed-tracing test-health test-error-scenarios smoke security-scan lint matrix matrix-subset clean help

PYTHON := .venv_ol/bin/python
PYTEST := $(PYTHON) -m pytest
FAKE_ENV := OMNI_TEST_FAKE_LLM=1 OMNI_TEST_FAKE_PANDOC=1

help:
	@echo "Omni Suite targets:"
	@echo "  setup         — bash scripts/setup_dev.sh"
	@echo "  test          — Run all CI-mode tests (OPP + OL + ORF + suite e2e)"
	@echo "  test-quick    — pytest tests/ -m \"not nightly\" -q"
	@echo "  test-opp      — Run OPP CI-mode tests"
	@echo "  test-ol       — Run OL CI-mode tests"
	@echo "  test-orf      — Run ORF CI-mode tests"
	@echo "  test-contract       — Run CLI + MCP contract tests (10 currently PASS)"
	@echo "  test-contract-cli   — Run CLI --help contract tests only (Section 7.5)"
	@echo "  test-contract-mcp   — Run MCP tool-schema contract tests only (21 tools)"
	@echo "  test-logs           — Run structured JSON logging tests (Phase 4.1, OMNI_LOG_FORMAT=json)"
	@echo "  test-metrics        — Run metrics + prometheus wiring tests"
	@echo "  test-tracing        — Run OTel tracing tests (Phase 4.5, OMNI_TRACING_ENABLED=1)"
	@echo "  test-distributed-tracing — Run W3C trace context propagation tests (Phase 4.5)"
	@echo "  test-health         — Spawn MCP servers with /health endpoint, assert 200 OK"
	@echo "  test-error-scenarios — Run the 11 exit-code matrix tests (plan § 6.4)"
	@echo "  smoke         — Run contract smoke test"
	@echo "  security-scan — Run gitleaks + bandit + pip-audit"
	@echo "  lint          — ruff check + mypy on parent + submodules"
	@echo "  matrix        — Run full MD matrix (165 cells, ~3min, real MCP)"
	@echo "  matrix-subset FMT=<fmt> — Run MD matrix on one input format (e.g. FMT=docx)"
	@echo "  clean         — Remove __pycache__, .pytest_cache, build artifacts"

setup:
	bash scripts/setup_dev.sh

test: test-opp test-ol test-orf
	$(FAKE_ENV) $(PYTEST) tests/ -m "not nightly" --tb=short -q --no-header

test-quick:
	$(FAKE_ENV) $(PYTEST) tests/ -m "not nightly" -q

test-opp:
	$(FAKE_ENV) $(PYTEST) Omni_Pre_Processor/tests/ -m "not nightly" --tb=short -q --no-header

test-ol:
	$(FAKE_ENV) $(PYTEST) Omni_Localizer/tests/ -m "not nightly" --tb=short -q --no-header

test-orf:
	$(FAKE_ENV) $(PYTEST) Omni_Re_Formatter/tests/ --tb=short -q --no-header

test-contract:
	$(FAKE_ENV) $(PYTEST) tests/contract/ --tb=short -v

test-contract-cli:
	$(FAKE_ENV) $(PYTEST) tests/contract/test_cli_help.py --tb=short -v

test-contract-mcp:
	$(FAKE_ENV) $(PYTEST) tests/contract/test_mcp_schemas.py --tb=short -v

test-coverage:
	$(FAKE_ENV) $(PYTEST) tests/ -m "not nightly" --tb=short -q --no-header --cov=Omni_Pre_Processor/src --cov=Omni_Localizer/src --cov=Omni_Re_Formatter/src --cov-report=term-missing --cov-report=html:test_artifacts/coverage-html --cov-fail-under=80

test-metrics:
	$(FAKE_ENV) $(PYTEST) tests/observability/test_metrics.py tests/observability/test_metrics_wiring.py Omni_Pre_Processor/tests/mcp/test_opp_metrics.py Omni_Localizer/tests/test_ol_metrics.py Omni_Re_Formatter/tests/test_orf_metrics.py -v --tb=short

test-logs:
	$(FAKE_ENV) OMNI_LOG_FORMAT=json $(PYTEST) tests/observability/test_json_logging.py tests/observability/test_request_id_opp.py -v --tb=short

test-tracing:
	$(FAKE_ENV) OMNI_TRACING_ENABLED=1 $(PYTEST) tests/observability/tracing_health/test_tracing.py -v --tb=short --timeout=30

test-distributed-tracing:
	$(FAKE_ENV) OMNI_TRACING_ENABLED=1 $(PYTEST) tests/distributed_tracing/test_distributed_tracing.py -v --tb=short --timeout=120

test-health:
	$(FAKE_ENV) $(PYTEST) tests/observability/tracing_health/test_health.py -v --tb=short --timeout=60

test-error-scenarios:
	$(FAKE_ENV) $(PYTEST) tests/error_scenarios/ -v --tb=short --timeout=30

security-scan:
	@echo "Running security scans (gitleaks + bandit + pip-audit)..."
	@command -v gitleaks >/dev/null 2>&1 && gitleaks detect --no-banner || echo "  [skip] gitleaks not installed"
	@command -v bandit >/dev/null 2>&1 && .venv_ol/bin/python -m bandit -r scripts/ tests/observability/ tests/error_scenarios/ tests/contract/ -ll || echo "  [skip] bandit not installed"
	@command -v pip-audit >/dev/null 2>&1 && (cd .venv_ol && bin/pip-audit 2>&1 | tail -30) || echo "  [skip] pip-audit not installed"
	@echo "See docs/SECURITY_AUDIT.md for the full audit roadmap."
	@echo "See docs/SECURITY_FINDINGS.md for the latest CVE list."

smoke:
	$(FAKE_ENV) $(PYTEST) tests/test_pipeline_contract_smoke.py --tb=short -v

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m mypy . --no-incremental || true

matrix:
	$(FAKE_ENV) $(PYTHON) scripts/mcp_matrix_verifier.py --out-dir /tmp/mcp-matrix-full --path-filter md --corpus minimal

matrix-subset:
	@test -n "$(FMT)" || (echo "Usage: make matrix-subset FMT=docx"; exit 1)
	$(FAKE_ENV) $(PYTHON) scripts/mcp_matrix_verifier.py --out-dir /tmp/mcp-matrix-$(FMT) --path-filter md --subset $(FMT) --corpus minimal

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info
