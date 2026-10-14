# Feature & QA Inventory — Omni Localization Suite

Built from: CLI --help, --capabilities, CHANGELOG.md, AGENTS.md, README.md, pyproject.toml, Makefile, source tree

---

## 1. OPP — Omni Pre-Processor (v0.7.7)

### CLI Commands
```
opp [files...] [options]
```
No subcommands — single flat CLI with positional `files` argument.

| Flag | Description |
|------|-------------|
| `--detect-format` | Auto-detect file format before processing |
| `--resource-dir` | Directory for extracted resources (images, etc.) |
| `--report {html,text}` | Generate html or text report |
| `--batch` | Enable batch processing mode |
| `-o, --output` | Output file for extracted content |
| `--target-format {md,xlf,both,html}` | Output format: markdown, XLIFF, both, or html (PDF→HTML) |
| `--source-lang` | Source language code (default: zh) |
| `--target-lang` | Target language code (required for xlf/both) |
| `--style-map` | JSON mapping of style names to heading levels |
| `--no-embed-images` | Embed images as base64 data URIs instead of separate files |
| `--output-dir` | Output directory for generated files |
| `-v, --verbose` | Enable verbose output |
| `--ocr-engine {tesseract,rapidocr}` | OCR engine for images |
| `--ocr-lang` | Language for Tesseract OCR |
| `--asr-engine {whisper}` | ASR engine for audio |
| `--model-size {tiny,base,small,medium,large-v3}` | Whisper model size |
| `--config` | Path to config file |
| `--no-cache` | Skip .omni_cache/ cache check |
| `--clear-cache` | Remove all cached OPP outputs |
| `--max-file-size, --max-file-size-mb` | Reject files exceeding this size (MB) |
| `--log-format {console,json}` | Log output format |
| `--load-dotenv` | Load .env file before running |
| `--capabilities` | Print OPP module capabilities and exit |
| `--validate-xliff` | Validate XLIFF 1.2 file (schema + trans-unit rules) |
| `--xliff-content` | Inline XLIFF XML string for validation |
| `--xliff-file` | Path to .xlf/.xliff file for validation |

### Input Formats (16)
docx, pptx, pdf, xlsx, csv, json, xml, html, epub, eml, msg, image, audio, video, youtube, ipynb

### Output Formats
md, xliff

### MCP Tools (9)
1. **extract_document** — Extract content from single document
2. **batch_extract** — Process multiple files
3. **detect_format_tool** — Identify file format via magic bytes
4. **generate_markdown** — Convert document to Markdown
5. **generate_xliff** — Convert document to XLIFF
6. **save_skeleton** — Save skeleton ZIP for ORF apply_xliff
7. **validate_xliff** — Validate XLIFF 1.2 format
8. **ping** — Health check
9. **get_capabilities** — Print module capabilities

### Feature Flags / Options
- **OCR** — Tesseract or RapidOCR engines for image text extraction
- **ASR** — Whisper for audio/video transcription
- **YouTube transcription** — via markitdown[youtube-transcription]
- **Style map** — Map DOCX styles to heading levels
- **Cache** — .omni_cache/ with --no-cache and --clear-cache
- **Embed images** — base64 data URI embedding vs separate files
- **XLIFF validation** — Schema + content rule checking
- **Dotenv loading** — opt-in via --load-dotenv
- **Capabilities introspection** — --capabilities flag

### Config File Structure
- `config/default.yaml` — Main config (or `opp_config.yaml` with deprecation warning)
- `${ENV_VAR}` patterns supported
- Environment vars: `OPP_ALLOWED_DIRECTORIES`, `OPP_MCP_ALLOWED_DIRS`, `OMNI_LOG_FORMAT`, `OMNI_TEST_FAKE_LLM`

### QA & Testing
- **Makefile targets**: `install`, `test`, `lint`, `build`, `docker`, `clean`
- **Test**: `uv run pytest tests/ -v`
- **Lint**: `ruff check src/ tests/`
- **Static typing**: pyright (4/5 checks enabled: reportMissingTypeStubs, reportDeprecated, reportUnusedVariable, reportUnusedImport)
- **Contract**: pre-commit hooks (gitleaks, check-added-large-files, check-merge-conflict, detect-private-key, end-of-file-fixer, trailing-whitespace)
- **Security**: PathValidator path security for MCP, MCP_SHARED_SECRET auth, rate limiter, Prometheus metrics, OTel tracing
- **Version**: 0.7.7 (pyproject.toml)

### Source Tree (src/opp/)
```
cli.py, pipeline.py, detector.py, chunker.py, transcriber.py,
resource_manager.py, logger.py, error_handler.py, cliutils.py
commands/       — extract.py, batch.py, mcp.py
config/         — constants.py
contracts/      — frontmatter.py, images.py, manifest.py, xliff.py
extractors/     — docx.py, pptx.py, pdf.py, pdf2html.py, html/, xlsx.py,
                  csv.py, json.py, xml.py, epub.py, email.py, image_ocr.py,
                  ipynb.py, youtube.py, audio.py, video.py, base.py
mcp/            — server.py, config.py, security.py, auth.py, rate_limiter.py,
                  metrics.py, health.py, tracing.py, common.py, serializers.py,
                  _errors.py, tools/ (9 tool modules)
markdown/       — generator.py
xliff/          — generator.py, validator.py, xliff_dataclasses.py
utils/          — cache.py, security.py, images_json.py, exceptions.py,
                  dataclasses.py, mcp_errors.py
channels/       — table_channel.py, keyvalue_channel.py
```
---

## 2. OL — Omni Localizer (v0.7.0)

### CLI Commands
```
ol [OPTIONS] COMMAND [ARGS]...
```

**17 subcommands:**

| Command | Purpose |
|---------|---------|
| **translate-md** | Translate single markdown file |
| **translate-xliff** | Translate XLIFF file |
| **translate-batch** | Batch translate markdown directory |
| **extract-warnings** | Extract placeholder restoration warnings |
| **capabilities** | Print module capabilities (roles, lang pairs, tools) |
| **shield-md** | Shield code/links/math/HTML/images before LLM |
| **unshield-md** | Restore shielded markers after LLM translation |
| **extract-terms** | Extract key terms via YAKE |
| **add-tm-entries** | Add entries to TMX translation memory |
| **disambiguate** | Resolve polysemous terms (no LLM) |
| **generate-report** | Generate HTML/CSV quality reports |
| **inspect-config** | Inspect OL configuration (models, paths, LQA) |
| **judge-text** | Evaluate translation quality using LLM |
| **load-glossary** | Load JSON glossary |
| **search-tm** | Search TMX translation memory |
| **translation-status** | Poll async translation task status |
| **verify-terms** | Verify glossary term usage in translations |
| **profile-doc** | Profile document writing style → StyleGuide |
| **ping** | Health check |

### Common Flags (translate-md/translate-xliff)
- `--config, -c` — Config file path
- `--source-lang, -s` — Source language
- `--target-lang, -t` — Target language
- `-o` — Output directory
- `--json` — Machine-readable JSON output
- `--frontmatter / --no-frontmatter` — YAML frontmatter control
- `--no-cache / --clear-cache` — Cache control
- `--glossary` — Glossary JSON/YAML path
- `--no-glossary` — Skip glossary injection
- `--no-restoration` — Skip post-translate placeholder restoration
- `--chunk-by-paragraph` — Paragraph-by-paragraph translation (translate-md)
- `--concurrency` — Max concurrent translations (translate-batch, default: 5)
- `--detect-language / --no-detect-language` (translate-batch)
- `--polish` — Post-translation consistency pass (translate-xliff)
- `--styleguide / --no-styleguide` (translate-xliff)
- `--glossary-max-terms` (translate-xliff)
- `--report-coverage / --coverage-threshold` — Glossary coverage report
- `--log-format {console,json}` — Log format

### MCP Tools (17 in capabilities, 8 listed in AGENTS.md)
Listed in `ol capabilities --json`:
1. **translate_md_text** — Translate markdown text (primary Agent tool)
2. **translate_xliff** — Translate XLIFF file
3. **judge_text** — Evaluate translation quality
4. **load_glossary** — Load JSON glossary
5. **get_relevant_terms** — Extract relevant glossary terms
6. **search_tm** — Search TMX translation memory
7. **batch_translate_texts** — Batch translate multiple texts
8. **get_translation_status** — Poll async task status
9. **extract_terms** — Extract key terms (YAKE)
10. **add_tm_entries** — Add TMX entries
11. **shield_md_text** — Shield markdown
12. **unshield_md_text** — Unshield markdown
13. **generate_report** — Generate HTML/CSV reports
14. **inspect_config** — Inspect configuration
15. **disambiguate** — Resolve polysemous terms
16. **ping** — Health check
17. **get_capabilities** — Capabilities

### Feature Flags / Options
- **Model Pool Failover** — LiteLLM Router with priority-based failover across 5 providers (Zhipu, Agnes, NVIDIA NIM, Moonshot Kimi, Opencode Go)
- **3 LLM roles**: translation, judging, restoration (+ profiling via optional role)
- **Content Shielding** — Code blocks, math (`$..$`), links, images, HTML, autolinks → `[OL:TYPE:NNNN]` markers
- **4-Layer Repair**: Regex (L1) → Span alignment (L2) → LLM restoration (L3) → Safe fallback (L4)
- **LQA (Linguistic Quality Assurance)** — Auto-judging with retry on low scores (config: `enable_lqa`, `lqa_threshold`, `lqa_max_retries`)
- **TM/TB/SG Automation** — TMX translation memory + glossary injection + styleguide
- **Term Disambiguation** — LLM-based polyseme resolution
- **QA Rules Subset** — translate-toolkit pofilter rules (accelerators, brackets, printf, variables, xmltags)
- **Punctuation Normalizer** — zh↔en (str.maketrans, zero API cost)
- **Polish Pass** — Post-translation consistency check (spelling, grammar, non-standard expression, redundancy)
- **StyleGuide Injection** — Document profiling → StyleGuide → injection into translation prompt
- **Coverage Report** — Glossary coverage stats post-translation
- **Cultural Transformation** — Idiom/metaphor cultural-equivalent rewriting
- **Proper-Noun Preservation** — Keep unknown proper nouns in original
- **Circuit Breaker** — 5 consecutive failures → open for 60s
- **RetryManager** — Exponential backoff on LLM failures
- **Translation Checkpointing** — Resume interrupted translations
- **Content-addressed Prompt Cache** — Cache key includes styleguide, polish settings
- **Concurrency Limiter** — Semaphore-based

### Config File Structure
- `config/default.yaml` — LLM pool per role (translation/judging/restoration/profiling)
- `config/local.yaml` — Local overrides
- `${ENV_VAR}` syntax for api_key/base_url
- Two-layer env var resolution: warning at startup, ValueError at runtime
- `OL_CONFIG_PATH` env var override

### QA & Testing
- **Makefile targets**: `install`, `test` (FAKE_LLM), `lint`, `build`, `docker`, `run`, `clean`
- **Test**: `OMNI_TEST_FAKE_LLM=1 uv run pytest tests/ -v`
- **Lint**: `ruff check src/ tests/`
- **Static typing**: mypy (warn_return_any, warn_unused_configs, check_untyped_defs)
- **Coverage target**: ≥90%
- **FAKE_LLM seam** — `_FakeModelPool` for hermetic tests
- **Pytest markers**: `real_llm_required`, `real_llm_optional`
- **Key test files**:
  - `test_e2e_74_translate_context.py` — Context type handling
  - `test_e2e_77_math_shield.py` — Math regex false positives
  - `test_e2e_78_html_shield_unshield.py` — Marker format + unshield
  - `test_e2e_83_large_content.py` — Large content + Router config
  - `test_md_shield.py` — Shield basics
  - `test_xliff_repair_pipeline.py` — XLIFF repair
  - `test_ol_cli.py` — CLI entry
  - `test_ol_cache.py` — Content-addressed cache
  - `test_opencode_skill.py` / `test_hermes_skill.py` — Agent skill tests

### Source Tree (src/)
```
ol_cli.py                     — CLI entry (Typer)
ol_review_extractor.py        — Review warning extraction
ol_config/                    — schema.py, loader.py
ol_pool/                      — router.py, fake.py
ol_md/                        — shield.py, extractor.py, pipeline.py,
                                 repair/ (level1-4), token_stream.py
ol_xliff/                     — parser.py, bus.py, polish.py, shield.py,
                                 repair/ (level1-4)
ol_buses/                     — md_bus, xliff_bus
ol_batch/                     — BatchProcessor
ol_terminology/               — extractor.py, disambiguator.py, rag_injector.py,
                                 verifier.py, coverage.py, glossary.py,
                                 glossary_class.py, schema.py
ol_lqa/                       — judge.py, scorer.py, report.py, stability.py,
                                 qa_rules.py
ol_restoration/               — Post-translate placeholder restoration
ol_concurrency/               — ConcurrencyLimiter
ol_retry/                     — RetryManager
ol_logging/                   — Structured JSON + console
ol_checkpoint/                — Translation checkpointing
ol_mcp/                       — server.py, config.py, security.py, auth.py,
                                 rate_limiter.py, metrics.py, health.py,
                                 tracing.py, tools/ (20 tool modules)
ol_post/                      — punctuation.py
ol_style/                     — schema.py, doc_profiler.py, cache.py
ol_tm/                        — service.py, auto_gen.py, _py_tmx.py
ol_routing/                   — router.py
```
---

## 3. ORF — Omni Re-Formatter (v0.4.16)

### CLI Commands
```
orf [OPTIONS] COMMAND [ARGS]...
```

| Command | Purpose |
|---------|---------|
| **apply-md** | Convert MD to target format (16 outputs) |
| **apply-xliff** | Backfill XLIFF into source document |
| **convert-batch** | Batch convert MD files |
| **detect-format** | Detect file format |
| **info** | Show document info (format, size, resources) |
| **capabilities** | Print ORF capabilities (formats, tools) |

### Global CLI Options
- `--version` — Show version
- `-v, --verbose` — Verbose logging
- `--log-format {console,json}` — Log output format
- `--load-dotenv` — Load .env file

### apply-md Options
- `--target-format, -t` — 17 choices: auto, docx, odt, epub, html, rtf, pdf, pptx, csv, json, xlsx, xml, ipynb, eml, msg, icml, srt
- `--auto-detect` — Auto-detect input format
- `-o, --output` — Output file path
- `--template` — Pandoc template
- `--reference-doc` — Reference DOCX for styles
- `--reference-doc-content` — Inline base64 DOCX bytes
- `--title` / `--author` / `--lang` — EPUB metadata
- `--embed-images` — EPUB embed images
- `--json` — JSON output
- `--text-only` — Skip all image references
- `--separate-images / --no-separate-images` — Extract images separately (default: on)
- `--images-json` — Image placement data from OPP
- `--no-cache / --clear-cache` — Cache control
- `--max-file-size-mb` — Max input file size

### apply-xliff Options
- `--xliff, -x` — Translated XLIFF file (required)
- `--xliff-content` — Inline XLIFF content
- `-o, --output` — Output file path (required)
- `-f, --format` — Output format (docx, pptx, epub, html, odt, pdf, json)
- `--json` — JSON output
- `--images-json` — Image placement data
- `--no-cache / --clear-cache` — Cache control
- `--max-file-size-mb` — Max input file size
- `--force` — Bypass skeleton format validation
- `--original-json` — Original JSON for structure reconstruction (json format)
- `--skeleton-html` — Skeleton HTML for PDF format

### MD Backfill Formats (16)
DOCX, ODT, EPUB, HTML, RTF, PDF, PPTX, ICML, SRT, CSV, XLSX, JSON, XML, IPYNB, EML, MSG

### XLIFF Backfill Formats (7)
DOCX, PPTX, EPUB, HTML, ODT, PDF, JSON

### MCP Tools (7)
1. **apply_md** — Convert MD to target format (accepts path OR inline content)
2. **apply_xliff** — Backfill XLIFF with optional image injection
3. **batch_convert** — Batch convert MD files
4. **detect_format** — Magic-bytes format detection
5. **info** — Document info (format, size, resources)
6. **ping** — Health check
7. **get_capabilities** — Module capabilities

### Feature Flags / Options
- **ForemanAgent orchestration** — Auto-decompose jobs, route to Format/Data/Markup/Email Specialists
- **4 Format Specialists**: FormatSpecialist (docx/odt/epub/pptx), DataSpecialist (xlsx/csv/json), MarkupSpecialist (xml/html), EmailSpecialist (eml/msg)
- **HITL Approval** — Files >100MB / cloud uploads / manual intervention require human approval
- **Audit Trail** — correlation_id + agent_id full-chain tracing (logs/audit_{date}.log)
- **PathValidator** — Directory traversal protection (allowed dirs, extension whitelist, symlink check, file size check)
- **Image Injection** — Floating images (wp:anchor) + inline images, dedup via cx/cy matching
- **MD Image Separation** — --separate-images extracts images to separate directory
- **Layout Overflow Detection/Correction** — AI-powered expansion ratio estimation with per-language pair ratios
- **Cloud Storage** — AWS S3 + Azure Blob clients
- **Cross-format XLIFF** — --force bypass for format validation
- **Pandoc Fallback** — PPTX falls back to pandoc if md2pptx missing
- **Reference DOCX Support** — Custom styles via --reference-doc or inline base64
- **Response Caching** — .omni_cache/ with --no-cache/--clear-cache
- **Shared-Secret Auth** — MCP_SHARED_SECRET env var
- **Rate Limiter** — Token bucket per MCP tool (OMNI_RATE_LIMIT_RPM)
- **Prometheus Metrics** — OMNI_METRICS_DIR
- **OTel Tracing** — OMNI_TRACING_ENABLED, OMNI_TRACES_DIR
- **Health Endpoint** — OMNI_HEALTH_HOST/PORT/ENABLED

### Config File Structure
- `.env` auto-load via `--load-dotenv` or `ORF_AUTOLOAD_DOTENV=1`
- `ORF_MCP_ALLOWED_DIRS` — Colon-separated allowed directories (required for MCP)
- `ORF_MCP_MAX_FILE_SIZE` — Max file size in bytes (default: 100MB)
- `ORF_MCP_TIMEOUT` — Per-tool timeout (default: 30s)
- `ORF_LOG_LEVEL` — Log level
- `OMNI_CACHE_DIR` — Cache root (default: ~/.omni_cache)
- `OMNI_LOG_FORMAT` — console or json
- `MCP_SHARED_SECRET` — Auth secret

### QA & Testing
- **Makefile targets**: `install`, `test`, `lint`, `build`, `docker`, `run`, `clean`
- **Test**: `uv run pytest tests/ -v`
- **Test markers**: `unit`, `integration`, `e2e`
- **Lint**: `ruff check src/ tests/`
- **Static typing**: mypy
- **Coverage target**: ≥90%
- **Key test files**:
  - `test_orf_mcp_server.py` — MCP integration
  - `test_apply_md_target_format.py` — Per-format tests
  - `test_mcp_apply_md_xliff_parity.py` — CLI/MCP parity
  - `test_xliff2epub_channel.py` — Segment ID matching
  - `test_xliff2json_channel.py` — JSON XLIFF pipeline
  - `test_md2json_combined.py` — Combined mode (13 tests)
  - `test_env_autoload.py` — Dotenv loading (110 lines)
  - `test_image_fidelity.py` — Image dedup regression
  - `test_expansion_ratios_defined` — AI overflow ratios
  - `turnkey/test_image_fidelity.py` — Image dedup
- **Security**: gitleaks, bandit, pip-audit (via suite Makefile)

### Source Tree (src/orf/)
```
cli.py
commands/         — apply_md.py, apply_xliff.py, convert_batch.py,
                    detect_format.py, info.py, capabilities.py
channels/         — md2docx.py, md2pptx.py, md2html.py, md2pdf.py, md2odt.py,
                    md2epub.py, md2rtf.py, md2icml.py, md2srt.py, md2csv.py,
                    md2xlsx.py, md2json.py, md2xml.py, md2ipynb.py, md2eml.py,
                    md2msg.py, xliff2docx/ (5 files), xliff2pptx.py,
                    xliff2html/ (4 files), xliff2epub.py, xliff2odf.py,
                    xliff2pdf.py, xliff2json.py
converters/       — base.py, options.py, stream_converter.py,
                    chunked_md_converter.py
parsers/          — manifest.py, frontmatter.py
detection/        — magic_bytes.py, format_detector.py
resources/        — image_manager.py, path_resolver.py
skeleton/         — skeleton_loader.py, inline_formatting.py
cloud/            — s3_client.py, azure_blob_client.py, cloud_resource_manager.py
ai/               — overflow_corrector.py
mcp/              — server.py, config.py, security.py, auth.py, rate_limiter.py,
                    metrics.py, health.py, tracing.py, common.py, schemas.py,
                    tools/ (7 tool modules)
agents/           — foreman.py, specialists/ (4 specialists)
workflow/         — hitl_approval.py
logging/          — structured logging + audit
error_handlers/   — conversion_error.py
```
---

## 4. omni-suite — E2E Test Suite (v0.4.0)

### CLI Commands
```
omni-suite <command> [options]
```

| Command | Purpose |
|---------|---------|
| `--version` | Print suite version |
| `--versions` | Print all component versions |
| `--compatibility` | Print version compatibility matrix |
| `pipeline <file>` | Run OPP→OL→ORF pipeline on a file (`--fake-llm`) |
| `check [--quick\|--readiness[ --verbose]]` | Run module tests, quick-env check, or production-readiness check |
| `status` | Show env, dependency, and version status |

### Suite CLI Features
- Pipeline orchestration across OPP→OL→ORF
- Fake LLM mode for pipeline testing
- Readiness checks
- Version compatibility matrix

### QA & Testing Infrastructure

**Makefile targets (26+):**

| Target | Description |
|--------|-------------|
| `setup` | Full dev environment setup |
| `doctor` | Dependency health check (Python/pandoc/WeasyPrint/md2pptx/MCP) |
| `test` | All CI-mode tests (OPP + OL + ORF + suite) |
| `test-quick` | Root suite only (not nightly) |
| `test-opp / test-ol / test-orf` | Per-component CI tests |
| `test-contract` | CLI + MCP contract tests |
| `test-contract-cli` | CLI --help contract tests |
| `test-contract-mcp` | MCP tool-schema contract tests (21 tools) |
| `test-coverage` | Coverage with --cov-fail-under=80 |
| `test-logs` | Structured JSON logging tests |
| `test-metrics` | Metrics + Prometheus wiring tests |
| `test-tracing` | OTel tracing tests |
| `test-distributed-tracing` | W3C trace context propagation |
| `test-health` | MCP /health endpoint tests |
| `test-error-scenarios` | 11 exit-code matrix tests |
| `fidelity` | Fidelity scoring on translation (char_cosine >= 0.9 gate) |
| `fidelity-unit` | FidelityScorer unit tests |
| `fidelity-nightly` | Regenerate candidate via real LLM |
| `smoke` | Pipeline contract smoke test |
| `e2e` | Real-LLM E2E pipeline tests (19 tests, nightly) |
| `security-scan` | gitleaks + bandit + pip-audit |
| `lint` | ruff check + mypy (depends on smoke first) |
| `matrix` | Full MD matrix (165 cells, real MCP) |
| `matrix-subset` | MD matrix on single input format |
| `clean` / `clean-artifacts` | Clean build artifacts |

### Suite-Level Testing Capabilities

**Translation Quality Module** (`tests/quality_checks.py`):
- `check_translation_quality(source, target, source_format, source_lang, target_lang) -> QualityResult`
- Checks: is_complete, has_translation, is_degenerate, source_non_translatable
- Per-format ratio overrides (pdf=0.15, pptx=0.20, json=0.10, etc.)
- Language-pair aware ratio lookup (3-tier: lang pair > format > default)
- Fenced code detection (auto-pass for non-translatable sources)
- 25 unit tests in `tests/test_quality_checks.py`

**Contract Tests** (`tests/contract/`):
- `test_cli_help.py` — CLI --help output consistency
- `test_mcp_schemas.py` — MCP tool-schema contract (21 tools)
- `test_mcp_io_contract.py` — MCP input/output contract
- `test_contract_documentation.py` — Documentation consistency

**Observability Tests** (`tests/observability/`):
- Metrics + Prometheus wiring
- Structured JSON logging
- OTel tracing
- Health endpoint
- Distributed tracing (W3C trace context)

**Error Scenario Tests** (`tests/error_scenarios/`):
- 11 exit-code matrix tests

**Fidelity Tests** (`tests/fidelity/`):
- `FidelityScorer` — character cosine similarity
- `run_fidelity.py` — scoring gate
- `regenerate_candidate.py` — nightly real LLM regeneration

**E2E Tests**:
- `test_e2e_real_llm.py` — 19 nightly tests across 4 tiers
- `test_e2e_pipeline.py` — Pipeline orchestration tests
- `test_suite_cli_fake_llm.py` — FAKE_LLM pipeline tests
- `test_scene_07_multi_lang.py` — Multi-language (en→fr, en→ja, en→ru) × 4 formats
- `test_pipeline_contract_smoke.py` — Pipeline contract gate

**Security Tests** (`tests/security/`):
- 63 security tests

**Format Tests** (`tests/formats/`):
- Format matrix verification

**Pre-commit Hooks** (`.pre-commit-config.yaml`):
- gitleaks — Hardcoded secrets, API keys
- check-added-large-files — Files >512 KB
- check-merge-conflict — Unresolved merge markers
- detect-private-key — Leaked SSH/GPG keys
- end-of-file-fixer — Newline at EOF
- trailing-whitespace — No trailing spaces
- omni-contract-smoke — Pipeline contract smoke (manual)

**Makefile Dependency**: `lint` depends on `smoke` — contract gate must pass before linting.

### Config File Structure
- `pyproject.toml` — Workspace with uv workspace members (OPP, OL, ORF)
- `.venv_ol/` — Unified Python 3.13 venv
- `VERSION` — Suite version file
- `COMPATIBILITY.md` — Version compatibility matrix
- `uv.lock` — Workspace lock file
- `docs/` — Suite-level docs (AGENTS.md, ARCHITECTURE.md, API_STABILITY.md, etc.)
- `.pre-commit-config.yaml` — Pre-commit hooks
- `scripts/` — 17 dev scripts (setup, check_deps, sync_version, mcp_matrix_verifier, etc.)

### Source Tree (omni_suite/)
```
cli.py              — Suite CLI
contract/           — validator.py, models.py
rate_limiter.py     — Rate limiter
__main__.py         — Module entry
```
