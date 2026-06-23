---
name: omni-suite
description: Orchestrate the 3-stage Omni Suite document localization pipeline (OPP extract → OL translate → ORF backfill). Current versions: opp 0.6.3, ol 0.4.5, orf 0.4.4, suite 0.2.2.
---

# Omni Suite — Document Localization Pipeline

A 3-stage pipeline for translating documents between formats and languages.

## Current versions (2026-06-23)

- **OPP** 0.6.3, **OL** 0.4.5, **ORF** 0.4.4, **suite** 0.2.2
- All 4 repos on `main`, working trees clean, ready to test
- E2E-65/64/15/14/07 cherry-picks + OPP stderr-handler fix landed

## When to use

- User asks to translate a document (DOCX, PPTX, PDF, etc.) between languages
- User asks to convert a document between formats (e.g., DOCX → EPUB)
- User asks to batch-translate or batch-convert multiple files
- User asks to detect a file's format (use `opp -v` to see the result in stderr)

## The 3 stages

1. **Extract** (OPP):
   ```bash
   opp <file> --target-format both --source-lang en --target-lang zh --output-dir /tmp/opp
   ```
   Add `-v` to see progress + detected format in stderr (e.g. `[INFO] Detected: docx (confidence: 1.0)`).

2. **Translate** (OL):
   ```bash
   OMNI_TEST_FAKE_LLM=1 ol translate-md /tmp/opp/file.md -s en -t zh -o /tmp/ol
   ```
   The E2E-65 prompt-injection strip is auto-applied to LLM output (defends against echo of "CRITICAL/IMPORTANT/NOTE: Output ONLY..." patterns).

3. **Backfill** (ORF):
   ```bash
   orf apply-md /tmp/ol/file.md --target-format <format> -o result.<format>
   ```
   The E2E-07 fuzzy paragraph match handles XLIFF source ↔ DOCX paragraph mismatches (up to 5-char length diff, ratio ≥ 0.85).

## Output formats supported

DOCX, ODT, EPUB, HTML, RTF, PDF, PPTX, ICML, SRT, CSV, XLSX, XML, IPYNB, EML, MSG, JSON

## Critical constraints

- Always set `OMNI_TEST_FAKE_LLM=1` unless real LLM API keys are configured.
- For MSG output, use `.eml` instead — MSG requires commercial Aspose.Email.
- For cross-format XLIFF (e.g., DOCX → PPTX), use `orf apply-xliff --force`.
- Pandoc is required for DOCX, ODT, EPUB, RTF, ICML outputs (auto-installed).

## Recent fixes (since 2026-06-01)

- **E2E-65 (OL)**: prompt injection strip in level1 repair
- **E2E-64 (OL)**: XLIFF repair `is_complete()` checks XML tag presence; `RouterRateLimitError` retry
- **E2E-14 (OL)**: b64 image ref dedup in `translate_md_text` MCP tool
- **E2E-15 (OPP)**: orphan image filter (no more double-embedding via Pandoc)
- **E2E-07 (ORF)**: fuzzy paragraph match in `_backfill_split_runs`
- **OPP stderr handler**: `opp -v` now writes to terminal (was file-only)

## Example

Translate `report.docx` from English to Chinese, output as DOCX:

```bash
OMNI_TEST_FAKE_LLM=1

opp report.docx --target-format both --source-lang en --target-lang zh --output-dir /tmp/opp
ol translate-md /tmp/opp/report.md -s en -t zh -o /tmp/ol
orf apply-md /tmp/ol/report.md --target-format docx -o report_zh.docx
```
