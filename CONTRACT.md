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

## Suite ↔ Module In-Process Import Surface

The sections above describe the **data** handoff (MD/XLIFF/JSON). This section
describes a second, easily-overlooked interface: the **names the suite imports
from inside each module** when it reads a module's live tool registry.

The suite never hardcodes tool lists — the coverage audit, the doc-truth
counters and several contract tests all read the *live* registries, in-process.
That makes the following names load-bearing: renaming or moving one of them
breaks the suite even though the module's own CLI/MCP surface is unchanged.
They are therefore part of this contract.

| Module | Package the suite puts on `sys.path` | Imported name | Expected shape |
|---|---|---|---|
| OPP | `Omni_Pre_Processor/src` | `opp.mcp.server._TOOL_SCHEMAS` | `list[dict]`, every entry carrying a `"name"` key |
| OPP | `Omni_Pre_Processor/src` | `opp.mcp.server._TOOL_DISPATCH` | `dict` mapping tool name → callable |
| OL | `Omni_Localizer/src` | `ol_mcp.tools.TOOL_REGISTRY` | `dict` mapping tool name → `(callable, input model type, description)` |
| ORF | `Omni_Re_Formatter/src` | `orf.mcp.server._TOOL_DISPATCH` | `dict` mapping tool name → callable |
| (suite) | repo root | `omni_mcp.server._TOOL_SCHEMAS` | same shape as OPP |
| (suite) | repo root | `omni_mcp.server._TOOL_DISPATCH` | same shape as OPP |

Additionally, scenario steps and tests import the **public** tool functions and
their `*Input` models from the same modules (e.g.
`from ol_mcp.tools import TranslateInput, translate_md_text`) — the
in-process agent-surface pattern used throughout `scenarios/`.

Consumers that must be updated together with any rename/move:

- `scripts/validation/coverage_audit.py` — `_import_module_tools()`
- `omni_mcp/validation/dispatch.py` — in-process MCP dispatch
- `scripts/doc_inventory.py` — counts tools by **parsing the source text** of
  the registries above (so the *shape*, not just the name, is load-bearing: a
  restructure that keeps the name but changes the literal form silently
  undercounts)
- `tests/test_docs_mcp_tool_consistency.py`, `tests/test_docs_claude_md_tools_exist.py`
- `tests/contract/test_contract_documentation.py` — asserts the table above is
  true and that every declared path resolves

---

## Breaking Changes

Changes that break the contract (e.g., renaming `source_lang` to `src_lang`) require:

1. Bumping the contract version in this document AND the Pydantic model
2. Updating all 3 sub-repos (OPP, OL, ORF) in the same release
3. Adding migration tests to the contract test suite
4. Notifying downstream consumers via RELEASE_NOTES.md

The same four rules apply to the in-process import surface above — renaming one
of those registry names (or changing its shape) is a breaking change of this
contract, not an internal refactor.

---

## Related Files

- `omni_suite/contract/models.py` — Pydantic model (source of truth)
- `omni_suite/contract/validator.py` — Validation functions
- `tests/test_translation_document_contract.py` — Contract unit tests
- `tests/contract/test_contract_documentation.py` — Documentation tests
- `.github/workflows/contract-tests.yml` — CI runs contract tests on every PR
