# Omni Suite — Claude Code Context

## What is this?

A 3-stage document localization pipeline. Each module is a standalone sub-repo with its own CLI, MCP server, and test suite.

```
OPP (extract) → OL (translate) → ORF (backfill)
```

## Architecture

### Module 1: OPP (Omni Pre-Processor)
- **Source**: `Omni_Pre_Processor/src/opp/`
- **CLI**: `opp --target-format=md|xliff|both <file>`
- **MCP**: `opp-mcp-server` (stdio transport)
- **Tests**: `Omni_Pre_Processor/tests/` (544+ tests)
- **Outputs**: Markdown, XLIFF 1.2/2.0, skeleton.zip, manifest.json
- **Extractors**: DOCX, PPTX, PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, images (OCR), audio (Whisper), YouTube URLs

### Module 2: OL (Omni Localizer)
- **Source**: `Omni_Localizer/src/ol/`
- **CLI**: `ol translate-md <file> -s <src> -t <tgt> -o <dir>`
- **MCP**: `ol-mcp` (stdio transport)
- **Tests**: `Omni_Localizer/tests/` (90+ test files)
- **Features**: Model pool failover, 4-layer repair (regex→span→LLM→fallback), LQA judging, TM/glossary injection, translation memory

### Module 3: ORF (Omni Re-Formatter)
- **Source**: `Omni_Re_Formatter/src/orf/`
- **CLI**: `orf apply-md <file> --target-format <fmt> -o <out>`
- **MCP**: `orf-mcp-server` (stdio transport)
- **Tests**: `Omni_Re_Formatter/tests/` (65 test files)
- **Output formats**: DOCX, ODT, EPUB, HTML, RTF, PDF, PPTX, ICML, SRT, CSV, XLSX, XML, IPYNB, EML, MSG, JSON

### Suite-Level Tests
- **Location**: `tests/` (30+ test files)
- **E2E tests**: `test_e2e_pipeline.py`, `test_e2e_real_llm.py`, `test_e2e_path_md_cli.py`, `test_e2e_path_xliff_cli.py`, etc.
- **Smoke test**: `tests/test_pipeline_contract_smoke.py`

## Key Seams for Development

### FAKE_LLM (mandatory for offline work)
```bash
export OMNI_TEST_FAKE_LLM=1
export OMNI_TEST_FAKE_PANDOC=1
```
Set these before any CLI or test invocation unless real LLM API keys are configured. The fake LLM short-circuits all external API calls, making tests hermetic.

### Python Environment
- **Unified venv**: `.venv_ol/` (Python 3.13)
- All commands use `.venv_ol/bin/python`
- Root `pyproject.toml` manages workspace dependencies via `uv`

### Pandoc Dependency
- DOCX, ODT, EPUB, RTF, ICML outputs require pandoc (auto-installed via `pypandoc-binary`)
- PDF via weasyprint engine does not need pandoc

## Common Development Tasks

```bash
# Run quick suite-level tests
make test-quick

# Run all CI-mode tests (OPP + OL + ORF + suite)
make test

# Run contract smoke test
make smoke

# Run pre-commit lint on all files
make lint

# Clean build artifacts
make clean
```

## Pre-commit Hooks

Install:
```bash
pip install pre-commit
pre-commit install
```

Run on demand:
```bash
pre-commit run --all-files
```

The `omni-contract-smoke` hook is manual-only (`stages: [manual]`), skipped on `git commit`. It runs the pipeline contract smoke test to catch API-shape regressions.

## MCP Tool Quick Reference

### opp-mcp-server (7 tools)
`extract_document`, `batch_extract`, `detect_format_tool`, `generate_markdown`, `generate_xliff`, `save_skeleton`, `ping`

### ol-mcp (8 tools)
`translate_md_text`, `translate_xliff`, `judge_text`, `load_glossary`, `get_relevant_terms`, `search_tm`, `batch_translate_texts`, `ping`

### orf-mcp-server (6 tools)
`apply_md`, `apply_xliff`, `batch_convert`, `detect_format`, `info`, `ping`

## How to validate

Run the agent-testing validation engine (83 scenarios; no mocks, no
FAKE_LLM as evidence). All commands from the suite root with the venv:

```bash
source .venv_ol/bin/activate

# Enumerate the library — no execution
python scripts/validation/run_validation.py --list

# Run one hermetic scenario (tier 1 = no LLM keys needed)
python scripts/validation/run_validation.py --scenario <name> --tier 1

# Contract-lint the library itself
python scripts/validation/run_validation.py --check
```

Only these scripts exist — do not invent other commands:
`scripts/validation/{run_validation.py, coverage_audit.py, validation_report.py, validation_diff.py}`.

**Reading results**: `validation-runs/latest.txt` points at the newest
run (`validation-runs/<ts>/scenarios.json`). Generate the director
report with
`python scripts/validation/validation_report.py validation-runs/<ts>/scenarios.json`
→ `report.md` in the same dir, with TWO verdict families side by side:
**agent-user conformance** (tool-* scenarios + AGENT-SURFACE standards:
contract, JSON shape, error clarity, path security, exit codes) and
**human-quality conformance** (pipeline-* scenarios + HUMAN-QUALITY
standards: LQA ≥ 4.0/5, paragraph ratio ±5%, CJK density < 5%, zero
foreign punctuation, drawing count, opens in python-docx). `unconfigured`
(missing env, e.g. no LLM keys) is never a pass and never a silent skip.

**Standards**: `scenarios/STANDARDS.md` — the single citable bar, two
families, exact anchors per step (`standard: STANDARDS.md#<anchor>`).
Read it before judging a verdict.

**Director checklist**: a human director completes the 10-minute loop
per run — see `docs/dev/validation-director-loop.md` (agent validator +
human director roles, per-run standards conformance pass).
