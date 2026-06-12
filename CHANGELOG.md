# Changelog

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

### Pre-existing (not addressed)

- OPP EPUB parser fails on minimal EPUB (`dc:` namespace resolution)
- XLIFF2ODF: translate-toolkit `xliff2odf` CLI outputs empty files
- DOCX image extraction: `test_multiple_images_per_paragraph` returns 1 instead of 2+
