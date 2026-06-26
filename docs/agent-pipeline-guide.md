# Agent Pipeline Guide — Omni Suite

> **Audience**: AI agents (Claude, Cursor, OpenCode) orchestrating the Omni Suite
> pipeline. This guide aggregates decisions and cross-references canonical docs.
> It does **not** replace them.

---

## 1. Architecture Overview

The Omni Suite is a 3-stage document localization pipeline:

| Stage | Module | What it does |
|-------|--------|-------------|
| 1 | **OPP** (Omni Pre Processor) | Extract source document into Markdown, XLIFF, and a skeleton ZIP |
| 2 | **OL** (Omni Localizer) | Translate Markdown or XLIFF between languages |
| 3 | **ORF** (Omni Re Formatter) | Backfill translated content into a target document |

```
Source doc (DOCX/PPTX/PDF/...) --> [OPP extract] --> MD + XLIFF
                                       |                  |
                                  [OL translate]    [OL translate]
                                       |                  |
                                    MD (translated)    XLIFF (translated)
                                       |                  |
                                  [ORF apply-md]    [ORF apply-xliff]
                                       |                  |
                                 Result doc         Result doc
                                  (16 formats)    (same format as source)
```

For the full architecture guide (515 lines, includes a Mermaid diagram, module
internals, data flow, and cross-module concerns), see
[`docs/ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 2. Pipeline Selection Strategy

The Omni Suite supports two pipeline paths. The choice determines which OPP
output format, which OL translation tool, and which ORF backfill tool to use.

**MD Path (text-first).** Use when text quality and speed matter more than
pixel-perfect layout. You are targeting web, e-book, or plain-text outputs,
or converting to a different format than the source (e.g. DOCX to EPUB).
Image placement is approximate. The MD path works with any input format and
produces 16 possible output formats.

**XLIFF Path (layout-faithful).** Use when the output must look exactly like
the source: contracts, branded documents, regulatory filings. You need a
skeleton ZIP from OPP (produced alongside the XLIFF). You are staying in
the same format (DOCX to DOCX, PPTX to PPTX). Floating images, custom
styles, headers and footers, footnotes, and exact fonts are preserved.

**Both paths can coexist.** OPP `--target-format both` produces MD, XLIFF,
and skeleton ZIP in a single pass. You can feed MD into a knowledge base and
use XLIFF for exact document backfill.

**Automatic pipeline selection.** The OPP `extract_document` MCP tool returns
a `suggested_pipeline` field (since v0.7.5) with values `md_only`, `xliff_only`,
`both`, or `neither`. Agents can use this field to automatically select the
correct pipeline without asking the user.

For the full decision tree (ASCII) and format support table, see
[Pipeline Selection Strategy](../README.md#pipeline-selection-strategy) in
README.md. Per-repo decision trees are linked there for deeper detail.

---

## 3. Format-to-Pipeline Mapping

Not every input format supports both paths. The table below is a quick
reference. A version with notes also lives in
[README.md#format-support-by-path](../README.md#format-support-by-path).

| Input Format | MD Path | XLIFF Path | Notes |
|-------------|---------|------------|-------|
| DOCX | Yes | Yes | Preferred path for both |
| PPTX | Yes | Yes | XLIFF preserves slide masters |
| EPUB | Yes | Yes | XLIFF preserves CSS layout |
| PDF | Yes | No | PDF to XLIFF intentionally blocked |
| HTML | Yes | No | No skeleton ZIP available |
| CSV / JSON / XML | Yes | No | Data formats, no layout |
| EML / MSG | Yes | No | Email formats |
| Images (OCR) | Yes | No | Text extraction only |
| YouTube URL | Yes | No | Transcription only |

The OPP MCP `detect_format_tool` identifies the input format, and
`extract_document` returns a `suggested_pipeline` field to guide the
decision automatically.

---

## 4. MCP Tool Reference

The Omni Suite provides 4 MCP servers. Together they expose over 20 tools.

| Server | Description | Tools | How to start |
|--------|-------------|-------|-------------|
| `opp-mcp-server` | Document extraction (7 tools) | `extract_document`, `batch_extract`, `detect_format_tool`, `generate_markdown`, `generate_xliff`, `save_skeleton`, `ping` | `opp mcp` or `python -m opp.mcp.server` |
| `ol-mcp` | Translation (8 tools) | `translate_md_text`, `translate_xliff`, `judge_text`, `load_glossary`, `get_relevant_terms`, `search_tm`, `batch_translate_texts`, `ping` | `ol mcp` or `python -m ol_mcp` |
| `orf-mcp-server` | Backfill and conversion (6 tools) | `apply_md`, `apply_xliff`, `batch_convert`, `detect_format`, `info`, `ping` | `orf mcp` or `python -m orf.mcp.server` |
| `omni-mcp` | One-step orchestration | `translate_file` (full pipeline in one call) | `python -m omni_mcp` |

**Important**: MCP server naming is not uniform across modules. OPP and ORF
use the `-server` suffix while OL omits it. All three follow the same
protocol.

For the full per-tool parameter reference (descriptions, required vs optional
params, types), see [AGENTS.md](../AGENTS.md#mcp-tool-reference). For MCP
configuration examples (Claude Desktop, Cursor, OpenCode), see the MCP
Configuration section in AGENTS.md.

---

## 5. Standard Response Format

All 4 MCP servers return a uniform response shape, documented in:

- [`docs/ERROR_CODES.md`](ERROR_CODES.md) lines 15-29 (response shape)
- [`docs/API_STABILITY.md`](API_STABILITY.md) line 197 (contract surface 3:
  MCP tool I/O is frozen)

**Success:**

```json
{
  "success": true,
  "content": { ... }
}
```

**Error:**

```json
{
  "success": false,
  "error": {
    "code": "OPP_FILE_NOT_FOUND",
    "message": "A required file was not found."
  },
  "error_code": "OPP_FILE_NOT_FOUND",
  "message": "A required file was not found."
}
```

The `error_code` field is the canonical identifier. The `error` object and
both legacy string fields (`error_code` as a flat string, `message`) are
kept for backward compatibility. New clients should switch on
`error.error_code` only.

Backward-compat aliases are kept for one release cycle after deprecation.

---

## 6. Format Support Matrix

ORF `apply-md` supports 16 output formats:

`DOCX`, `ODT`, `EPUB`, `HTML`, `RTF`, `PDF`, `PPTX`, `ICML`, `SRT`, `CSV`,
`XLSX`, `XML`, `IPYNB`, `EML`, `MSG`, `JSON`

For the full 36-path verified matrix (which input/output combinations have
been tested end-to-end), see:
- [AGENTS.md Format Support Matrix](../AGENTS.md#format-support-matrix)
- [README.md Cross-Format Production-Readiness](../README.md#cross-format-production-readiness)

**Dependency notes:**
- DOCX, ODT, EPUB, RTF, ICML outputs require pandoc (auto-installed via
  `pypandoc-binary`).
- MSG output requires commercial Aspose.Email. Use EML instead (open
  standard, fully supported).
- Cross-format XLIFF (e.g. DOCX XLIFF to PPTX) needs `orf apply-xliff --force`.
- PDF XLIFF generation is intentionally blocked by OPP (unsupported).
