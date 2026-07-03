# Omni Suite — OPP → OL → ORF Handoff Contract

**Version**: 1.0  
**Status**: Active  
**Last Updated**: 2026-07-03

This document defines the formal handoff contract between the three pipeline stages.
It exists to prevent silent breakage at handoff boundaries (e.g., the OPP→OL silent
MD format drift that caused E2E-06, E2E-14, E2E-15).

---

## Pipeline Overview

```
┌────────┐   MD / XLIFF / images   ┌────────┐   MD / XLIFF   ┌────────┐
│  OPP   │ ──────────────────────▶ │   OL   │ ──────────────▶ │  ORF   │
│ extract│                         │translate│                │backfill│
└────────┘                         └────────┘                └────────┘
```

- **OPP** extracts documents → MD + XLIFF + skeleton.zip
- **OL** translates MD / XLIFF between languages
- **ORF** backfills translated content → target format

---

## Contract Version

This is contract version **1.0**. Changes must bump the version.

See `omni_suite/contract/models.py:TranslationDocument` for the authoritative
Pydantic model — it is the source of truth for the handoff schema.

---

## MD Format Contract (OPP → OL)

OPP produces a Markdown file with YAML frontmatter. Required frontmatter fields:

| Field | Type | Description |
|-------|------|-------------|
| `source_lang` | string (ISO 639-1) | Source language code, e.g., `"en"` |
| `target_lang` | string (ISO 639-1) | Target language code, e.g., `"zh"` |
| `format` | string | Source document format (`docx`, `pptx`, `pdf`, etc.) |

Body content uses standard Markdown. Image references use `![alt](path)` syntax.

### Example MD output

```markdown
---
source_lang: en
target_lang: zh
format: docx
---

# Document Title

This is a translatable paragraph.

![Image](image_001.png)
```

### MD Handoff Rules

1. OPP MUST produce valid Markdown with YAML frontmatter containing `source_lang`,
   `target_lang`, and `format`.
2. OL MUST parse the frontmatter before translation and preserve it in output.
3. Image paths are relative to the output directory.
4. Paragraphs are separated by blank lines (`\n\n`), not single newlines.

---

## XLIFF Format Contract (OPP → OL → ORF)

OPP produces XLIFF 1.2. Required elements:

- `<xliff version="1.2">` root element
- `<file source-language="en" target-language="zh" original="input.docx">`
- `<body>` containing `<trans-unit>` elements with `<source>` and `<target>`

### Example XLIFF output

```xml
<?xml version="1.0" encoding="utf-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file source-language="en" target-language="zh" original="input.docx">
    <body>
      <trans-unit id="1">
        <source>Hello world</source>
        <target>你好世界</target>
      </trans-unit>
    </body>
  </file>
</xliff>
```

### XLIFF Handoff Rules

1. OPP MUST produce XLIFF 1.2 with valid `source-language` and `target-language`.
2. OL MUST populate `<target>` elements (not overwrite `<source>`).
3. ORF MUST receive the skeleton.zip alongside the translated XLIFF.
4. `trans-unit` IDs MUST be stable across extraction and translation.

---

## Pydantic Model (TranslationDocument)

The contract is formally defined in `omni_suite/contract/models.py` as a Pydantic
model. This is the **source of truth** — this Markdown document is a human-readable
summary.

```python
from omni_suite.contract.models import TranslationDocument, DocumentFormat

doc = TranslationDocument(
    format_type=DocumentFormat.DOCX,
    pipeline_path="md",  # or "xliff"
    source_lang="en",
    target_lang="zh",
)
```

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `format_type` | `DocumentFormat` | Source format enum (`docx`, `pptx`, `pdf`, …) |
| `pipeline_path` | `"md"` or `"xliff"` | Which pipeline path was used |
| `source_lang` | `str` | ISO 639-1 source language |
| `target_lang` | `str` | ISO 639-1 target language |
| `segments` | `list[TranslationSegment]` | Extracted translatable units |
| `version` | `str` | Contract version (default `"1.0"`) |

### JSON Schema

Generate the full JSON Schema with:

```bash
python -c "from omni_suite.contract.models import TranslationDocument; print(TranslationDocument.model_json_schema())"
```

---

## Validation

To validate a real OPP output against this contract:

```python
from pathlib import Path
from omni_suite.contract.validator import validate_md_output

doc = validate_md_output(Path("/path/to/output.md"), "en", "zh")
if doc is None:
    print("FAILED: OPP output does not conform to contract")
else:
    print(f"PASSED: {len(doc.segments)} segments, format={doc.format_type}")
```

---

## Breaking Changes

Changes that break the contract (e.g., renaming `source_lang` to `src_lang`) require:

1. Bumping the contract version in this document AND the Pydantic model
2. Updating all 3 sub-repos (OPP, OL, ORF) in the same release
3. Adding migration tests to the contract test suite
4. Notifying downstream consumers via RELEASE_NOTES.md

---

## Related Files

- `omni_suite/contract/models.py` — Pydantic model (source of truth)
- `omni_suite/contract/validator.py` — Validation functions
- `tests/test_translation_document_contract.py` — Contract unit tests
- `tests/contract/test_contract_documentation.py` — Documentation tests
- `.github/workflows/contract-tests.yml` — CI runs contract tests on every PR
