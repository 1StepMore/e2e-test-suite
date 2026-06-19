# AGENTS.md — Omni Suite

This file guides AI agents (Claude, Cursor, OpenCode, etc.) on how to work with the Omni Suite.

## What is this?

A 3-stage document localization pipeline: **OPP** (extract) → **OL** (translate) → **ORF** (backfill). Each module is a standalone sub-repo with its own CLI, MCP server, and test suite.

## Quick Start

```bash
# Install (one command)
bash scripts/setup_dev.sh

# Verify without installing
bash scripts/setup_dev.sh --check-only

# Check version
omni-suite --version
```

## Per-Module Cheat Sheet

| Module | Role | CLI (key subcommand) | MCP tools | Source |
|--------|------|---------------------|-----------|--------|
| **OPP** | Extract documents → MD + XLIFF + skeleton | `opp <file> --target-format both --output-dir <dir>` | 7 tools (`extract_document`, `batch_extract`…) | `Omni_Pre_Processor/src/` |
| **OL** | Translate MD/XLIFF between languages | `ol translate-md <file> -s <src> -t <tgt> -o <dir>` | 8 tools (`translate_md_text`, `judge_text`…) | `Omni_Localizer/src/` |
| **ORF** | Backfill translated content → target format | `orf apply-md <file> --target-format <fmt> -o <out>` | 7 tools (`apply_md`, `apply_xliff`…) | `Omni_Re_Formatter/src/` |

## Common Tasks

### Translate a DOCX end-to-end

```bash
# Always set FAKE_LLM unless you have real API keys
export OMNI_TEST_FAKE_LLM=1

# 1. Extract
opp document.docx --target-format both --source-lang en --target-lang zh --output-dir /tmp/opp

# 2. Translate
ol translate-md /tmp/opp/document.md -s en -t zh -o /tmp/ol

# 3. Backfill
orf apply-md /tmp/ol/document.md --target-format docx -o result.docx
```

### Use MCP servers (for Claude / Cursor / Hermes)

Each module exposes its own MCP server. Configure in your agent's MCP settings:

- `opp-mcp-server` — 7 extraction tools
- `ol-mcp-server` — 8 translation tools
- `orf-mcp-server` — 7 backfill tools

## Format Support Matrix

ORF `apply-md` supports 16 output formats: DOCX, ODT, EPUB, HTML, RTF, PDF, PPTX, ICML, SRT, CSV, XLSX, XML, IPYNB, EML, MSG, JSON.

See `README.md` → "Cross-Format Production-Readiness" for the full 36-path verified matrix.

## Critical Notes

1. **FAKE_LLM required** — All CLI calls need `OMNI_TEST_FAKE_LLM=1` unless real LLM API keys are configured.
2. **pandoc dependency** — DOCX, ODT, EPUB, RTF, ICML outputs require pandoc (auto-installed via `pypandoc-binary`).
3. **MSG → use .eml** — MSG output requires commercial Aspose.Email. Use `.eml` instead (open standard, fully supported).
4. **Cross-format XLIFF** — Converting DOCX XLIFF → PPTX needs `orf apply-xliff --force`.
5. **PDF XLIFF blocked** — OPP intentionally blocks PDF → XLIFF generation (unsupported).

## Agent Tips

- Use the FAKE_LLM seam for zero-cost testing — no API keys needed.
- ORF `apply-md` supports 16 formats; check the table before assuming availability.
- `omni_suite/cli.py` is print-only — use per-module CLIs for real work.
- For end-to-end orchestration, chain per-module MCPs in sequence.
- Per-module `AGENTS.md` / `SKILL.md` files exist in each sub-repo for deeper context.
- Tests live under `tests/` at suite root and within each `Omni_*/tests/` sub-repo.
