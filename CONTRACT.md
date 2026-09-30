# Omni Suite — OPP → OL → ORF Handoff Contract

**Version**: 1.1
**Status**: Active
**Last Updated**: 2026-09-30

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

### Table Cell Coordinates (`resname`)

Table cell text is addressed by a positional `resname` with this grammar:

```
table_{t}_r{r}_c{c}              # whole cell (legacy form)
table_{t}_r{r}_c{c}_para{p}       # one paragraph within a multi-paragraph cell
```

where `{t}` is the table, `{r}` the row, `{c}` the column and `{p}` the
paragraph index within the cell.

A consumer MUST treat the two forms differently:

| Form | Meaning |
|---|---|
| `table_{t}_r{r}_c{c}` | The WHOLE cell. One trans-unit carries every paragraph, joined with `"\n"`. |
| `table_{t}_r{r}_c{c}_para{p}` | ONLY paragraph `{p}` of that cell. |

`{p}` is the 0-based index into the cell's **RAW direct-child paragraph list,
INCLUDING empty paragraphs**. It MUST match the consumer's own enumeration of
that cell's paragraph children. An extractor MUST NOT skip empty paragraphs when
computing `{p}`; skipping them shifts every later index and silently targets the
wrong paragraph.

When a cell has MORE THAN ONE paragraph and the extractor emits per-paragraph
units, EVERY paragraph MUST carry the `_para{p}` suffix — including `{p}` = 0.
A consumer MUST NOT receive a mix of suffixed and bare units for the same cell.
The reason is destructive: a bare unit makes a legacy consumer write positionally
and then clear the cell's remaining paragraph runs, destroying their text.

If any unit for a cell carries `_para`, a consumer MUST treat every unit for that
cell as per-paragraph. A bare unit arriving for such a cell MUST be skipped with
a warning — it MUST NOT fall back to whole-cell writing, which would clear the
per-paragraph writes already applied.

An out-of-range or duplicated `{p}` MUST be skipped with a warning. A consumer
MUST NOT guess a paragraph and MUST NOT crash.

The `_para` form is opt-in and additive: a consumer that does not implement it
MUST still accept the bare form. A consumer predating this clause will not match
the `_para` form at all and will fall through to its text-matching path, which
MUST NOT be relied on for correctness.

`t`/`r`/`c` are RAW NODE INDICES into the extractor's source tree. They are NOT
expanded to a merged-cell grid: a cell that spans several grid columns still
advances the column counter by one, and merged-away cells never advance it. A
coordinate therefore names the XML node OPP visited, not a logical spreadsheet
position.

An empty cell produces NO trans-unit. A consumer MUST read a missing table
coordinate as "no text", never as a lost or failed unit.

`t` is per-format:

- **DOCX and HTML**: the table index over the whole document, in document order.
- **PPTX**: a SINGLE index accumulated across slides in presentation order. It
  never resets per slide.

The consumer (ORF) MUST resolve PPTX slide order from the slide-ID list,
`<p:sldIdLst>` in ppt/presentation.xml, then follow the relationship part that
maps each `r:id` to its slide:

```
ppt/presentation.xml             # <p:sldIdLst> lists the slides in order
ppt/_rels/presentation.xml.rels  # r:id -> slides/slideN.xml
```

A numeric sort of slide filenames is INCORRECT. A valid package can list
slide10.xml before slide2.xml, and the sldIdLst order can disagree with the
filenames.

When a cell contains multiple paragraphs and the extractor emits the BARE form,
OPP joins the paragraph texts with `"\n"`, and the consumer MUST split on that
newline to restore the paragraphs.

That newline split is NOT RELIABLE on its own: the newline count belongs to the
translated text, so a translation that changes the number of lines silently
changes the paragraph count, and a consumer that distributes lines across the
cell's paragraph runs will CLEAR the runs it has no line for, losing source text.
The bare form therefore guarantees only best-effort paragraph restoration.
Extractors SHOULD prefer the `_para{p}` form for multi-paragraph cells; see
`OPP_TABLE_PARAGRAPH_UNITS` in the OPP README for the opt-in switch.

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
