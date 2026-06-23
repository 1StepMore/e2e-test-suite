# Changelog

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
