---
name: omni-suite
description: Orchestrate the 3-stage Omni Suite document localization pipeline (OPP extract → OL translate → ORF backfill)
---

# Omni Suite — Document Localization Pipeline

A 3-stage pipeline for translating documents between formats and languages.

## When to use

- User asks to translate a document (DOCX, PPTX, PDF, etc.) between languages
- User asks to convert a document between formats (e.g., DOCX → EPUB)
- User asks to batch-translate or batch-convert multiple files

## The 3 stages

1. **Extract** (OPP):
   ```bash
   opp <file> --target-format both --source-lang en --target-lang zh --output-dir /tmp/opp
   ```
2. **Translate** (OL):
   ```bash
   OMNI_TEST_FAKE_LLM=1 ol translate-md /tmp/opp/file.md -s en -t zh -o /tmp/ol
   ```
3. **Backfill** (ORF):
   ```bash
   orf apply-md /tmp/ol/file.md --target-format <format> -o result.<format>
   ```

## Output formats supported

DOCX, ODT, EPUB, HTML, RTF, PDF, PPTX, ICML, SRT, CSV, XLSX, XML, IPYNB, EML, MSG, JSON

## Critical constraints

- Always set `OMNI_TEST_FAKE_LLM=1` unless real LLM API keys are configured.
- For MSG output, use `.eml` instead — MSG requires commercial Aspose.Email.
- For cross-format XLIFF (e.g., DOCX → PPTX), use `orf apply-xliff --force`.
- Pandoc is required for DOCX, ODT, EPUB, RTF, ICML outputs (auto-installed).

## Example

Translate `report.docx` from English to Chinese, output as DOCX:

```bash
OMNI_TEST_FAKE_LLM=1

opp report.docx --target-format both --source-lang en --target-lang zh --output-dir /tmp/opp
ol translate-md /tmp/opp/report.md -s en -t zh -o /tmp/ol
orf apply-md /tmp/ol/report.md --target-format docx -o report_zh.docx
```
