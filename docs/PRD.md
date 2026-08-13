# Omni Suite — Product Requirements Document (Baseline)

## 1. Vision

The Omni Suite is a 3-stage document localization pipeline. OPP extracts a source document into Markdown and XLIFF intermediates (plus a skeleton archive for layout-preserving backfill), OL translates those intermediates between languages, and ORF writes the translated content back into a target document. The three stages are independent modules with their own CLI, PyPI package, and MCP server, and they are composable: any version combination covered by the compatibility matrix is contract-tested end to end.

This document is the retrospective baseline. It records what is actually built, grounded in the repository's own docs, so that future issues have a single source of truth for requirements, scope, and acceptance thresholds. It is not a forward-looking spec; everything here describes behavior that already exists and has been verified.

## 2. User Stories

- As a translator, I want to translate a DOCX from English to Chinese end to end via the MD path, so that I get a translated DOCX file from `opp extract` → `ol translate-md` → `orf apply-md`.
- As a localization engineer, I want to translate a document while preserving its original layout, so that I can use the XLIFF path (`ol translate-xliff` + `orf apply-xliff` with skeleton.zip) for contracts and branded documents where fonts, styles, and floating images must survive.
- As a content producer, I want to convert a DOCX into a different format like EPUB through the MD path, so that I can republish a translated document as an e-book without re-authoring.
- As a batch operator, I want to extract and translate multiple files in one request, so that I can process whole directories through `batch_extract` and `batch_translate_texts` instead of file by file.
- As a developer or CI pipeline, I want to run the full pipeline with only the CLI and no LLM API keys, so that I can test locally for free by setting `OMNI_TEST_FAKE_LLM=1` to get deterministic mock translations.

## 3. Scope

**In scope**

- **13+ input formats**: DOCX, PPTX, PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, images (OCR), IPYNB, and `.url` for YouTube auto-detect (ARCHITECTURE.md §3.1).
- **16 output formats** from `orf apply-md`: DOCX, ODT, EPUB, HTML, RTF, PDF, PPTX, ICML, SRT, CSV, XLSX, XML, IPYNB, EML, MSG, JSON (README.md; ORF validation plan Q1).
- **Two pipeline channels**: the MD channel (layout-tolerant, 16 output formats) and the XLIFF channel (format-preserving backfill using skeleton.zip + manifest.json).
- **Three MCP servers**: OPP (7 tools), OL (21 tools), ORF (6 tools), plus the CLI surfaces per module.
- **Quality machinery**: OL's 4-layer repair pipeline, StyleGuide injection, and 8 post-translation quality gates.
- **Zero-cost testing seam**: `OMNI_TEST_FAKE_LLM` and `OMNI_TEST_FAKE_PANDOC` for offline, key-free runs.

**Out of scope (explicit non-goals)**

- **PDF→XLIFF generation is intentionally blocked**. PDF extraction produces no reliable structural units for XLIFF; OPP raises a clear error and the MD path is the supported route (ACCEPTED_GAPS.md).
- **MSG output is not a supported path**. It requires the commercial `aspose-email-foss` (GPLv3); use `.eml` instead, which is fully supported (ACCEPTED_GAPS.md).
- **Pixel-perfect layout on the MD path**. The MD channel trades layout fidelity for simplicity; exact layout is only guaranteed on the XLIFF channel (README.md pipeline selection).
- **Real-time latency guarantees**. The pipeline is batch-oriented; performance thresholds are defined in minutes and docs/hour, not sub-second response times.

## 4. Acceptance Criteria

Each threshold below is transcribed from the cited source and verified against it. No number here was invented. Sources: `docs/ACCEPTANCE.md`, `Makefile`, `tests/fidelity/run_fidelity.py`, `Omni_Localizer/src/ol_mcp/tools.py`, and the four validation master plans.

1. **OPP extract fidelity**: `char_cosine >= 0.9` against the reference corpus. Source: `tests/fidelity/run_fidelity.py:22` (`CHAR_COSINE_THRESHOLD = 0.9`), corroborated by OPP_VALIDATION_MASTER_PLAN.
2. **Test-coverage floor**: `>= 80%` combined across the three module `src/` trees. Source: `Makefile:93` (`--cov-fail-under=80` on the `test-coverage` target).
3. **OL MCP surface**: 21 tools registered. Source: `Omni_Localizer/src/ol_mcp/tools.py` (`TOOL_REGISTRY` / `__all__`), enumerated in OL_VALIDATION_MASTER_PLAN Q7.
4. **Format surface**: 13+ input formats accepted by OPP and 16 output formats from ORF `apply-md`. Sources: ARCHITECTURE.md §3.1 and README.md format matrix.
5. **PDF→XLIFF guard**: OPP blocks PDF→XLIFF generation with a clear error and no crash. Sources: README.md (W3.2 case-insensitive guard), OPP_VALIDATION_MASTER_PLAN Q4, ACCEPTED_GAPS.md.
6. **FAKE_LLM seam**: the pipeline runs end to end without API keys when `OMNI_TEST_FAKE_LLM=1` is set, producing deterministic mock translations. Sources: OL_VALIDATION_MASTER_PLAN Q3, SUITE_VALIDATION_MASTER_PLAN Q11.
7. **OL quality gates**: 8 post-translation quality gates (inline tags, terminology, length ratio, locale, source copy, script check, protocol artifacts, terms audit), advisory and non-blocking. Source: OL_VALIDATION_MASTER_PLAN Q5.
8. **Performance thresholds** (from `docs/ACCEPTANCE.md`): P95 latency < 5 min for a 50MB file (Phase E1), sustained throughput >= 100 docs/hour (Phase E2), 8-hour throughput 100/100 complete (Phase E3), memory growth < 500MB over 1 hour (no leak), and 0 crashes over a 1-hour load (Phase E2).

Additional thresholds from `docs/ACCEPTANCE.md`: multi-judge LQA pass rate >= 85% (avg >= 4.0/5); Spearman rank correlation >= 0.7; inter-judge exact-match agreement >= 60%; security tests 63/63; observability tests 42/42; fresh checkout install (`git clone && uv sync && bash setup_dev.sh`) < 10 min; 0 hardcoded secrets in tracked configs; circuit breaker opens after 5 consecutive failures.

**Executable verification set** (the four validation master plans, one line each):

- `docs/OPP_VALIDATION_MASTER_PLAN.md`: 17 questions over 13 input formats and 7 MCP tools.
- `docs/OL_VALIDATION_MASTER_PLAN.md`: 17 questions over 21 MCP tools, 8 quality gates, and real-LLM scenarios.
- `docs/ORF_VALIDATION_MASTER_PLAN.md`: 14 questions over 16 output formats and 6 MCP tools.
- `docs/SUITE_VALIDATION_MASTER_PLAN.md`: 15 questions over 2 pipeline paths (MD + XLIFF) and 3 MCP servers.

Each plan is executable by any agent: pick a user question, run the scenario, compare actual vs expected, and report a binary verdict.

## 5. Architecture Reference

The full cross-module architecture lives in `docs/ARCHITECTURE.md`, which describes the stage roles (OPP extract, OL translate, ORF backfill), the two channels (MD and XLIFF), the module-by-module contracts, and the shared security and observability model. The formal handoff contract between stages is `CONTRACT.md` (version 1.0), whose authoritative schema is the `TranslationDocument` Pydantic model in `omni_suite/contract/models.py`; it defines the MD frontmatter fields, XLIFF 1.2 structure, and the stability rules for trans-unit IDs that keep the three independent modules interoperable.
