# Agent Pipeline Guide

> **Audience**: AI agents and developers orchestrating the Omni Suite
> pipeline (OPP -> OL -> ORF). This is a quick-reference aggregation.
> For detailed per-module internals, follow the links to canonical docs.

---

## 1. Architecture Overview

The Omni Suite is a 3-stage document localization pipeline. Each stage is
an independent module with its own CLI, PyPI package, and MCP server:

| Stage | Module | Role |
|-------|--------|------|
| 1 | **OPP** (Omni Pre Processor) | Extract source document to Markdown + XLIFF + skeleton.zip |
| 2 | **OL** (Omni Localizer) | Translate MD or XLIFF between languages |
| 3 | **ORF** (Omni Re Formatter) | Backfill translated content into a target format document |

```
Source file (DOCX, PPTX, PDF, ...)
        |
        v
  +------------------+
  |  OPP (Extract)   | ----> document.md, document.xlf, skeleton.zip
  +------------------+
        |
        | translated artifacts
        v
  +------------------+
  |  OL (Translate)  | ----> translated.md, translated.xlf
  +------------------+
        |
        v
  +------------------+
  |  ORF (Backfill)  | ----> result.docx (or other target format)
  +------------------+
```

For a full diagram (Mermaid + ASCII) with all artifact paths, see
`docs/ARCHITECTURE.md` (Section 2, Pipeline Diagram). The architecture
doc also covers cross-module data contracts, version compatibility, and
the extraction/translation/backfill data model.

---

## 2. Pipeline Selection Strategy (XLIFF vs MD)

The Omni Suite supports two parallel pipeline paths. Choosing the right
one is the most common agent decision.

**MD Path (text first):**
- OPP produces `.md` files
- OL translates via `translate-md`
- ORF converts via `apply-md` (supports 16 output formats)
- Best for: speed, format conversion, approximate layout

**XLIFF Path (layout faithful):**
- OPP produces `.xlf` + `skeleton.zip`
- OL translates via `translate-xliff`
- ORF backfills via `apply-xliff` (same format as source)
- Best for: pixel perfect output, contracts, branded docs

OPP also exposes a `suggested_pipeline` enum in its extraction result
(see OPP issue #11) that recommends one path based on the input format.
When the source format supports skeleton preservation, it suggests
XLIFF; for data formats (CSV, JSON, XML) it suggests MD.

For the full decision tree (with a complete ASCII diagram), see
`README.md#pipeline-selection-strategy`. Per-module decision tables
live in each sub repo's AGENTS.md:
- [OPP target format guide](https://github.com/1StepMore/Omni_Pre_Processor/blob/main/AGENTS.md)
- [OL translate-md vs translate-xliff](https://github.com/1StepMore/Omni_Localizer/blob/main/AGENTS.md)
- [ORF apply-md vs apply-xliff](https://github.com/1StepMore/Omni_Re_Formatter/blob/main/AGENTS.md)

---

## 3. Format to Pipeline Mapping

Not every input format supports both paths. This is a condensed summary.
See `README.md` for the full matrix with notes.

| Input Format | MD Path | XLIFF Path | Notes |
|-------------|---------|------------|-------|
| DOCX | Yes | Yes | Preferred path for both |
| PPTX | Yes | Yes | XLIFF preserves slide masters |
| EPUB | Yes | Yes | XLIFF preserves CSS layout |
| PDF | Yes | **No** | PDF to XLIFF intentionally blocked by OPP |
| HTML | Yes | No | No skeleton.zip produced |
| CSV / JSON / XML | Yes | No | Data formats, no layout |
| EML / MSG | Yes | No | Email formats (MSG limited) |
| Images (OCR) | Yes | No | Text extraction only |
| YouTube URL | Yes | No | Transcription only |

When unsure, use `--target-format both` in OPP. This produces MD, XLIFF,
and skeleton.zip simultaneously, keeping both paths open without
re-extraction. The extra disk space is negligible.

---

## 4. MCP Tool Reference

Each module exposes its own MCP server. The table below lists the servers
and their tool counts. For full per-tool parameter reference, see the
suite-level `AGENTS.md` (MCP Tool Reference section) or `docs/API.md`.

### Server Overview

| Server | Tool Count | CLI Start Command | MCP Name |
|--------|-----------|-------------------|----------|
| OPP MCP | 7 | `opp mcp` or `uvx opp-mcp` | `opp-mcp-server` |
| OL MCP | 21 | `ol mcp` or `uvx ol-mcp` | `ol-mcp` |
| ORF MCP | 6 | `orf mcp` or `uvx orf-mcp` | `orf-mcp-server` |
| Omni MCP | N/A (aggregator) | `omni-suite mcp` (print only) | `omni-mcp` |

### Tool Lists

**OPP MCP (7 tools):**
`extract_document`, `batch_extract`, `detect_format_tool`,
`generate_markdown`, `generate_xliff`, `save_skeleton`, `ping`

**OL MCP (21 tools):**
`translate_md_text`, `translate_xliff`, `judge_text`, `load_glossary`,
`get_relevant_terms`, `search_tm`, `batch_translate_texts`, `ping`
Full 21-tool registry: see the OL MCP Tool Reference table in `AGENTS.md`.

**ORF MCP (6 tools):**
`apply_md`, `apply_xliff`, `batch_convert`, `detect_format`, `info`, `ping`

**Omni MCP:** The suite-level aggregator (`omni-suite mcp`) is print-only
and does not expose unique tools. Use per-module servers for real work.

### Per-Tool Parameters

Detailed parameter schemas, required fields, and type information for
every tool live in:
- `AGENTS.md` (suite root) -- MCP Tool Reference tables with descriptions
  and key parameters
- `docs/API.md` -- Full parameter reference with types and defaults

---

## 5. Standard Response Format

All three MCP servers (OPP, OL, ORF) return responses in a uniform
envelope. This is defined as a frozen contract in
`docs/API_STABILITY.md` (Section 5.1, Surface #3: MCP tool I/O).

### Success Response

```json
{
  "success": true,
  "content": { ... }
}
```

### Error Response

```json
{
  "success": false,
  "error_code": "OPP_FILE_NOT_FOUND",
  "message": "A required file was not found."
}
```

OPP and ORF also include a legacy `"error"` field (a string matching
`message`) for backward compatibility with older test assertions. New
clients should switch on `error_code` only. See `docs/ERROR_CODES.md`
(Section "Response Shape", lines 15-29) for the authoritative spec.

### Error Code Catalog

The full error code catalog (shared codes + per-module codes) lives in
`docs/ERROR_CODES.md`. It covers:

- **Shared codes** (all 3 modules): `AUTH_FAILED`
- **OPP codes**: `OPP_FILE_NOT_FOUND`, `OPP_PERMISSION_DENIED`,
  `OPP_INVALID_INPUT`, `OPP_MISSING_KEY`, and others in
  `opp/mcp/_errors.py`
- **OL codes**: Defined in `ol_mcp/_errors.py`
- **ORF codes**: Defined inline in `orf/mcp/server.py`

Each code entry includes the error's meaning, when it occurs, and the
recommended caller action. New codes can be added, but existing codes
must not be renamed or removed (per the stability contract in
`docs/API_STABILITY.md`).

---

## 6. Path Configuration

Each MCP server handles file system access differently. The table below
compares their default behavior and security posture.

| Server | Env Variable | Default | Behavior if Unset | Security |
|--------|-------------|---------|-------------------|----------|
| OPP MCP | `OPP_MCP_ALLOWED_DIRS` | None | Raises `ValueError`, server refuses to start | Fail-closed |
| OL MCP | N/A | N/A | OL has no directory restriction | N/A |
| ORF MCP | `ORF_ALLOWED_DIRECTORIES` | `[Path.cwd()]` | Silently uses CWD | Fail-open |
| Omni MCP | N/A | N/A | Relies on underlying server config | N/A |

### OPP MCP (Fail Closed)

OPP requires explicit configuration via `OPP_MCP_ALLOWED_DIRS`
(colon-separated paths). If unset, the MCP server refuses to start:

```bash
export OPP_MCP_ALLOWED_DIRS="/data/documents:/data/output"
```

Validation includes: directory allowlist membership, symlink boundary
checks, blocked extension filtering (executables), allowed extension
whitelist, and file size limits. See
`Omni_Pre_Processor/AGENTS.md` (Path Configuration section) for details.

### ORF MCP (Fail Open)

ORF uses `ORF_ALLOWED_DIRECTORIES` (note: different variable name from
OPP). If unset, it silently falls back to `[Path.cwd()]` (the current
working directory at server start). This is a potential security gap
for production deployments:

```bash
export ORF_ALLOWED_DIRECTORIES="/data/documents:/data/output"
```

The same validation pipeline (allowlist, extensions, symlinks, size)
applies when the variable is set. See
`Omni_Re_Formatter/AGENTS.md` (Path Configuration section) for details.

### OL MCP

OL has no directory restriction mechanism. Its MCP tools accept file
paths and content directly. Path validation is handled by the caller
or the orchestrating agent.

### Omni MCP

The suite-level aggregator does not implement its own path validation.
It delegates all file operations to the underlying per-module servers.
Configure those individually using the variables above.

### Recommended Setup

Always set both OPP and ORF path variables explicitly:

```bash
export OPP_MCP_ALLOWED_DIRS="/data/documents"
export ORF_ALLOWED_DIRECTORIES="/data/documents"
```

For CI/CD environments:

```bash
export OPP_MCP_ALLOWED_DIRS="${GITHUB_WORKSPACE}/test_fixtures"
export ORF_ALLOWED_DIRECTORIES="${GITHUB_WORKSPACE}/test_fixtures"
```

### Per-Module Documentation

- OPP path config: `Omni_Pre_Processor/AGENTS.md` ->
  Path Configuration (MCP Server) section
- ORF path config: `Omni_Re_Formatter/AGENTS.md` ->
  Path Configuration (MCP Server) section
- Security model: `ARCHITECTURE.md` (cross-module),
  `Omni_Pre_Processor/AGENTS.md` -> PathValidator security model section,
  `Omni_Re_Formatter/AGENTS.md` -> PathValidator security model section
