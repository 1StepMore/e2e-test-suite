# =============================================================================
# Omni Suite — Developer Makefile
# =============================================================================
#
# Targets:
#   setup       — Full dev environment setup (venv, install, smoke test)
#   test        — Run all CI-mode tests (OPP + OL + ORF + suite e2e)
#   test-quick  — Run root suite only (pytest tests/ -m "not nightly" -q)
#   test-opp    — Run OPP CI-mode tests
#   test-ol     — Run OL CI-mode tests
#   test-orf    — Run ORF CI-mode tests
#   smoke       — Run contract smoke test
#   lint        — Run pre-commit on all files
#   clean       — Remove __pycache__, .pytest_cache, build artifacts
#
# =============================================================================

.PHONY: setup test test-quick test-opp test-ol test-orf smoke lint clean help

PYTHON := .venv_ol/bin/python
PYTEST := $(PYTHON) -m pytest
FAKE_ENV := OMNI_TEST_FAKE_LLM=1 OMNI_TEST_FAKE_PANDOC=1

help:
	@echo "Omni Suite targets:"
	@echo "  setup       — bash scripts/setup_dev.sh"
	@echo "  test        — Run all CI-mode tests (OPP + OL + ORF + suite e2e)"
	@echo "  test-quick  — pytest tests/ -m \"not nightly\" -q"
	@echo "  test-opp    — Run OPP CI-mode tests"
	@echo "  test-ol     — Run OL CI-mode tests"
	@echo "  test-orf    — Run ORF CI-mode tests"
	@echo "  smoke       — Run contract smoke test"
	@echo "  lint        — pre-commit run --all-files"
	@echo "  clean       — Remove __pycache__, .pytest_cache, build artifacts"

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

smoke:
	$(FAKE_ENV) $(PYTEST) tests/test_pipeline_contract_smoke.py --tb=short -v

lint:
	pre-commit run --all-files

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info
