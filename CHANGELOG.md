# Changelog

## Unreleased

### Added

- **`feat(check_deps.sh + doctor.yml)`: add `make doctor` + CI gate (7-check health)** — `make doctor` runs Python/keys/pandoc/WeasyPrint/md2pptx/MCP/submodule checks; CI runs on every PR with `continue-on-error: true` initially

- **Multi-language E2E test scenes** (`tests/scenes/scene-07-multi-lang/`, `tests/test_scene_07_multi_lang.py`): 12 cells across 3 language pairs (en→fr, en→ja, en→ru) × 4 formats (DOCX, PDF, HTML, JSON). Uses the FAKE_LLM seam to verify pipeline non-crash and output structure (openable, parseable). Declaratively parametrized via `@pytest.mark.parametrize`. Fixtures generated synthetically via python-docx, PyMuPDF, and inline string literals. Runs via `pytest -m scene07 -v`.

- **`tests/quality_checks.py` — codified translation quality module** (`tests/quality_checks.py`): The QC logic from the 2026-06-24 full-matrix regression test runner (a one-off `/tmp/run_scene_matrix.py` script that produced a 200-cell matrix and flagged 48 false-positive FAILs) is now a proper suite module with 25 regression tests. Fixes the three hardcoded, format-insensitive rules that caused the false positives (issue #4):

  1. **Degenerate detection no longer flags markdown table separator lines** — the original `(.)1{9,}` regex matched `|--------|` (10+ consecutive dashes). Now strips table-separator rows before applying the regex. Resolves 8 DOCX + 2 CSV false-positive cells (Symptom A: 10格).
  2. **Translation-existence check is now target/source length ratio, not absolute** — the original `cn_chars > 20` rejected PDF/PPTX/XLSX/CSV edge cases where the source itself was <20 chars. New defaults: `MIN_TARGET_RATIO=0.25` (calibrated for en→zh density) with per-format overrides (`pdf=0.15`, `pptx=0.20`, `xlsx=0.20`, `csv=0.20`, `json=0.10`, `html=0.10`, `eml=0.20`); `MIN_TARGET_CHARS=1` (50% of source length with hard minimum 1) for short sources (<20 chars). Resolves 12 PDF + 6 PPTX + 3 XLSX + 1 CSV false-positive cells (Symptom B: 22格).
  3. **Source that is entirely fenced code blocks auto-PASSes** — JSON files and HTML files with only `<img>` metadata extract to pure code blocks. After the v0.4.7 #5 fence-preservation fix, the translation is correctly the same code block verbatim, not "missing translation". New check `_is_entirely_fenced_code()` short-circuits to PASS with `source_non_translatable=True`. Resolves 10 JSON + 6 HTML false-positive cells (Symptom C: 16格).

  Public API: `check_translation_quality(source, target, source_format=None, source_lang="en", target_lang="zh") -> QualityResult` returns a structured `QualityResult` dataclass with `is_complete`, `has_translation`, `is_degenerate`, `source_non_translatable`, `target_chars`, `source_chars`, `cn_chars`, `target_source_ratio`, `reason`, `notes`. The matrix test runner consumes this to categorize each cell.

  25 unit tests in `tests/test_quality_checks.py` pin the contract: 5 for the table-separator fix (including negative cases), 9 for the ratio-based check (including format overrides), 6 for the non-translatable source bypass, 4 for module constants, 1 for the dataclass. The 3 false-positive scenarios from issue #4 all now PASS; the 2 negative cases (real degenerate 11 dots, empty target) still correctly FAIL.

### Fixed

- **`fix(setup_dev.sh)`: enforce Python >= 3.13** — was wrongly allowing Python 3.12, which caused cryptic errors downstream from components that now require 3.13 features

- **`fix(setup_dev.sh)`: warn about deprecated `.venv/` (Python 3.12-era)** — the old `.venv/` directory is stale; users get a clear warning to remove it and let setup_dev.sh create `.venv_ol/`

- **Matrix regression false-positive rate: 48格/200 (24%) → 0格/200**. All 48 false-positive cells from the 2026-06-24 matrix run were caused by the three hardcoded QC rules above. The matrix is now expected to report a true pass rate close to 100% (excluding the 16 cells for code-only formats which were never supposed to be tested for translation completeness).

- **`tests/quality_checks.py` — language-pair aware ratio lookup chain** (Issue e2e #6): added `_LANG_RATIO_OVERRIDES: dict[(src, tgt), float]` and `_resolve_min_ratio()` helper implementing a 3-tier lookup (lang pair > format > default `MIN_TARGET_RATIO`). The `source_lang` and `target_lang` parameters of `check_translation_quality` are now consulted (previously marked "reserved for future use"). The lang table is intentionally empty by default — every (src, tgt) pair currently falls through to format/default, preserving all existing behavior. 6 new tests in `TestLangPairRatioLookup` pin the lookup chain: format override used when no lang entry, default used when neither, lang overrides format, lang overrides default, empty table is backward-compatible, existing call signature still works.

- **`fix(scripts/check_deps.sh)`: sub-repo structure check** — replaced sub-repo check (which expected `Omni_*/pyproject.toml`) with suite-self check. After 2026-06-24 the 3 sub-repos are now separate git repos, not submodules of e2e-test-suite. The doctor CI workflow was failing on every push to main before this fix.
- **`fix(scripts/sync_version_docs.py)`: regex backreference bug** (root cause of AGENTS.md version table corruption): the `_count()` callback returned the raw `\g<N>` template string instead of expanded form, causing literal `\g<1>0.2.3\g<2>` artifacts in version tables. Fixed by calling `m.expand(replacement)` before returning. The AGENTS.md version table was manually corrected in PR #33; this fix prevents the bug from recurring.

### Changed

- **`docs(README, SETUP, AGENTS)`: add Python >= 3.13 prerequisite notes** — all onboarding documents now clearly state Python >= 3.13 is required; 3.12 users are directed to upgrade before filing bugs

- **`chore(scripts/README.md)`: document 17 dev scripts** — comprehensive reference for all scripts in `scripts/`, each with purpose, usage, and dependency notes

- **`chore(Makefile)`: `make lint` now depends on `smoke` (contract gate)** — linting no longer runs in isolation; the smoke test contract gate must pass first, preventing lint-only CI passes on broken pipelines

## 0.2.0 — 2026-06-20

### Added

- **Agent onboarding documentation**: Comprehensive AGENTS.md with per-module cheat sheet, MCP configuration for Claude Desktop / Cursor / OpenCode, tool-call scenarios, MCP tool reference tables, format support matrix, pre-commit hooks guide, and MCP local testing guide.
  - `AGENTS.md`, `.opencode/skills/omni-suite/SKILL.md`
  - `Omni_Pre_Processor/.opencode/skills/opp-extractor/SKILL.md`
  - `Omni_Localizer/.opencode/skills/ol-localizer/SKILL.md`
  - `Omni_Re_Formatter/.opencode/skills/orf-formatter/SKILL.md`

- **Omni Suite CLI subcommands**: `omni-suite pipeline`, `omni-suite check`, `omni-suite status` for pipeline orchestration, readiness checks, and status reporting.
  - `omni_suite/cli.py`

- **Cross-format E2E test suite**: 36-path verified format matrix with production-readiness assessment across OPP/OL/ORF (W4).

- **Infrastructure files**: `.cursorrules`, `CLAUDE.md`, `CONTRIBUTING.md`, `Makefile`, `PRODUCTION_READINESS.md`, `scripts/check_readiness.py`, `tests/benchmarks/`

### Fixed

- **OL CLI config validation without API keys**: `test_e2e_path_md_cli.py` and `test_e2e_path_xliff_cli.py` now pass dummy env vars (`ZHIPU_API_KEY`, `AGNES_API_KEY`, `NVIDIA_NIM_API_KEY`) to satisfy Pydantic config validation even with `OMNI_TEST_FAKE_LLM=1`. Also added `--no-cache` to bypass stale OL cache poisoning from prior test runs.
  - `tests/test_e2e_path_md_cli.py`, `tests/test_e2e_path_xliff_cli.py`

- **`XLIFF2DOCXConverter.convert()` API mismatch**: Changed `input_skeleton=` kwarg to `input_path=` in `test_e2e_path_xliff_mcp.py` to match the actual converter signature `(input_path, xliff_path, output_path, options=None)`.

- **Pipeline failure test CLI wrapper**: `_write_cli_failure_wrapper` now patches `_translate_md_async` / `_translate_xliff_async` at module level instead of `_FakeModelPool.translate`. The OL CLI catches translate exceptions internally (falling back to source text with exit code 0), so patching the pool never produced a non-zero exit. Patching the async functions lets the exception propagate to the CLI's outer handler which calls `raise typer.Exit(code=PIPELINE_ERROR)`.
  - `tests/test_e2e_pipeline_failures.py`

- **Added `--config` flag to xliff_cli OL call**: `test_e2e_path_xliff_cli.py` was missing the `-c` flag, causing OL CLI to look for config in CWD (a temp directory) and fail.

- **ORF pyproject.toml stale Python version**: `target-version` was `py310` and `python_version` was `"3.10"` while `requires-python` was `>=3.12`. Updated both to `"py312"` and `"3.12"`.

- **Removed dead turnkey tests** referencing removed `scripts/turnkey/` modules.

### Changed

- **Suite version bumped from 0.1.0 → 0.2.0** (`VERSION`, `pyproject.toml`, `COMPATIBILITY.md`)
- **COMPATIBILITY.md** updated to reflect current suite→submodule version mapping.

## 2026-06-12

### Fixed

- **MD Path paragraph inflation** (E2E-06): OL `TokenPositionTracker.rebuild()` now emits `\n\n` (double newline) on `paragraph_close`, restoring blank-line separators between paragraphs. `ensure_md_block_separation()` regex tightened to only inject `<!-- p -->` at blank-line boundaries, not within soft-wrapped lines.
  - `Omni_Localizer/src/ol_md/token_stream.py`
  - `tests/test_e2e_real_llm.py`

- **Edge-case test failures** (E2E-07): Fixed 9 tests across OPP/ORF/images that failed due to environment differences:
  - OPP: EPUB `OEBPS/` mkdir missing, PPTX `slide_layouts[6]` index error, IPYBN xfail marker
  - ORF: ICML assertion now checks `ParagraphStyleRange`, MD2PPTX skip when CLI missing
  - ORF: PDF default engine changed from `pdflatex` to `weasyprint` (pdflatex unavailable)
  - Images: PPTX slide layout index fix (`slide_layouts[6]` → `[0]`)
  - `tests/test_e2e_opp_all_formats.py`, `tests/test_e2e_orf_all_formats.py`, `tests/test_e2e_images.py`
  - `Omni_Re_Formatter/src/orf/converters/options.py`

### Added

- **Glossary CLI support**: `e2e_runner.py` now accepts `--glossary` argument; `_run_ol()` in `test_e2e_real_llm.py` threads `glossary_path` through to the OL CLI/MCP call.
  - `tests/e2e_runner.py`, `tests/test_e2e_real_llm.py`

## 2026-06-12 (Batch 2 — hardening & audit fix)

### Changed

- **`Optional[X]` → `X | None` migration** across OPP, OL, ORF: 247 instances converted to Python 3.12+ union syntax via ruff UP045/UP006/UP035. Zero `Optional[X]` remain across all 3 components.
  - `ruff check --select=UP045,UP006,UP035 --fix src/` in each project

### Fixed

- **`max_xliff_concurrent` config field silently ignored** (OL): Field was defined in YAML but missing from Pydantic `ProjectConfig` schema, so Pydantic v2 silently dropped it. Added `max_xliff_concurrent: int = Field(...)` to `ol_config/schema.py`; removed `getattr()` workaround from `ol_cli.py:1782`.
  - `Omni_Localizer/src/ol_config/schema.py`, `src/ol_cli.py`, `config/default.yaml`

- **ORF pyproject.toml targets py310 (requires ≥3.12)**: `target-version` and `python_version` were set to 3.10 while `requires-python` was ≥3.12. Updated both to 3.12.
  - `Omni_Re_Formatter/pyproject.toml`

- **OL ruff suppresses F841/F821 (unused vars, undefined names)**: Removed from ignore list; fixed 9 violations across `qa_rules.py`, `ol_restoration/__init__.py`, `ol_tm/_py_tmx.py`.
  - `Omni_Localizer/pyproject.toml` + 3 source files

- **OL MD repair pipeline: `is_complete()` false-positive on consecutive placeholders**: `is_complete()` checked marker keys as substrings of text, but `"CODE_0000" in "\x00OL_CODE_0000\x00"` matched inside unresolved placeholder wrappers. Added `_strip_placeholders()` to remove `\x00OL_...\x00` wrappers before checking. Applied same fix to `missing` computation at L4 fallback.
  - `Omni_Localizer/src/ol_md/pipeline.py` — 16 test failures → 0

- **OL span_aligner import hung at module level**: `span_aligner` package tries to download HuggingFace model on import. Moved import to lazy `_get_span_projector()` with `HF_HUB_OFFLINE=1` guard in both `ol_md/repair/level2.py` and `ol_xliff/repair/level2.py`.
  - Also fixed thread-unsafe `os.environ["HF_HUB_OFFLINE"]` mutation — now confined to single lazy-init call.

- **OL repair tests expected `str` but `repair()` returns `(str, list[str])`**: Added `_repair_text()` helper in both `test_md_repair_pipeline.py` and `test_md_auto_repair.py`. Updated `is_complete` test expectation to match fixed behavior.
  - 21 OL test failures → 2 remaining (pre-existing cascade bugs)

- **Bare `except Exception: pass/return` with no logging** (7 locations): Added `print(f"[WARN] ...")` to `tests/e2e_runner.py` (6) and `tests/test_e2e_pipeline.py` (1).

- **`print()` → `logger.warning()` in OPP CLI**: `Omni_Pre_Processor/src/opp/cli.py:536`

- **OL `opencode_skill` tests used wrong relative path**: Fixed `test_opencode_skill.py` fixture to use `Path(__file__)` relative path.

- **OPP pyright 4/5 checks re-enabled** (`reportMissingTypeStubs`, `reportDeprecated`, `reportUnusedVariable`, `reportUnusedImport`). `reportMissingParameterType` remains suppressed (35+ annotation gaps).
  - `Omni_Pre_Processor/pyproject.toml`

- **ORF HITL `request_approval` didn't raise `NotImplementedError`**: Docstring said it should but implementation auto-approved. Added the missing raise.
  - `Omni_Re_Formatter/src/orf/workflow/hitl_approval.py`

- **ORF `_parse_allowed_dirs` returned `[]` for single paths**: When `ORF_MCP_ALLOWED_DIRS=/tmp` had no `:` separator, the function returned empty list instead of `[Path("/tmp")]`.
  - `Omni_Re_Formatter/src/orf/mcp/config.py`

- **ORF MCP `_path_validator` module-level caching**: Tests that set `ORF_MCP_ALLOWED_DIRS` after module import got a stale validator. Made `_get_path_validator()` lazy with env-var change tracking.
  - `Omni_Re_Formatter/src/orf/mcp/server.py`

- **ORF test fixes** (17 failures → 0, excluding 3 FastMCP suite-isolation):
  - Security tests: `ORF_MCP_ALLOWED_DIRS` conftest setup
  - HITL tests: 49 pass (was 46 + 3 fail)
  - MCP tempfile/identical: path validator mocking
  - md2pdf: explicit `ConverterOptions(engine="pandoc")`
  - md_separate_images: updated manifest path assertions
  - packaging: `cwd=str(_PROJECT_ROOT)` for subprocess calls

### Pre-existing (not addressed)

- OPP EPUB parser fails on minimal EPUB (`dc:` namespace resolution)
- XLIFF2ODF: translate-toolkit `xliff2odf` CLI outputs empty files
- DOCX image extraction: `test_multiple_images_per_paragraph` returns 1 instead of 2+
- 3 ORF MCP tests fail in full-suite context due to FastMCP tool-handler caching (pass individually)
- 2 OL MD repair cascade bugs (consecutive placeholders edge case, HTML entity escaping — pre-existing)

## 0.2.1 — 2026-06-23

### Changed

- **Submodule pointer advance**: OPP 0.6.1 → 0.6.2, OL 0.4.4 → 0.4.5, ORF 0.4.3 → 0.4.4
  - `src/Omni_Pre_Processor` → b98d54a04e614de0649d49b556b5a4a024a0daed
  - `src/Omni_Localizer` → fa00e2fb00bab3a5fa81c7849f6211e87b1eb36d
  - `src/Omni_Re_Formatter` → c875562c8bbde33b07e49606ac132a179e8619b3

### Fixed

- **E2E-15 (OPP)**: Orphaned image double-embedding in MarkdownGenerator
- **E2E-65 (OL)**: Prompt injection stripping in level1 repair
- **E2E-14 (OL)**: Base64 image ref dedup in translate_md_text
- **E2E-64 (OL)**: XLIFF repair is_complete() check + RouterRateLimitError retry
- **E2E-07 (ORF)**: Fuzzy match for length-mismatched paragraphs in xliff2docx

### Updated

- `COMPATIBILITY.md` and `VERSION_COMPATIBILITY.md` matrices

## 0.2.2 — 2026-06-23

### Changed

- **Submodule pointer advance**: OPP 0.6.2 → 0.6.3 (stderr handler for verbose mode UX)
  - `src/Omni_Pre_Processor` → 102353307fe9723cd3c9c478a79a7d8746722451

### Fixed

- **OPP CLI verbose mode UX**: `opp --detect-format -v <file>` now writes `[INFO]   Detected: docx (confidence: 1.0)` to stderr. Previously the message only went to the log file, which broke the human-UX expectation set by `test_detect_format_flag`.

### Updated

- `COMPATIBILITY.md` and `VERSION_COMPATIBILITY.md` matrices
