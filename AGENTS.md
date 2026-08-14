# AGENTS.md — Omni Suite

This file guides AI agents (Claude, Cursor, OpenCode, etc.) on how to work with the Omni Suite.

## What is this?

A 3-stage document localization pipeline: **OPP** (extract) → **OL** (translate) → **ORF** (backfill). Each module is a standalone sub-repo with its own CLI, MCP server, and test suite.

## Current Versions

| Component | Version | Status |
|---|---|---|
| Omni_Suite | v0.4.0 | Suite-level orchestration + E2E tests |
| OPP | v0.9.1 | 13+ input formats, MCP with path security |
| OL | v0.7.1 | 21 MCP tools, 4-layer repair pipeline, StyleGuide injection, --polish pass, 8 quality gates |
| ORF | v0.4.17 | 16 backfill formats, Foreman/Specialist |

v0.9.1 · v0.7.1 · v0.4.17 · v0.4.0.

## Recent Changes

> **Note**: Entries before v0.2.6 have been condensed for readability.
> See git log for full history (including the submodule era).

**v0.2.5 → v0.2.6** — Doc cleanup batch (OPP#17, OL#20, ORF#15, e2e#22):
- `fix(OPP#17)`: Replace `Omni_Suite` references and `../` paths with absolute URLs in `Omni_Pre_Processor/AGENTS.md`
- `fix(OL#20)`: Same fix in `Omni_Localizer/AGENTS.md`
- `fix(ORF#15)`: Same fix in `Omni_Re_Formatter/AGENTS.md`
- `fix(e2e#22)`: Update Suite README directory tree; clean Suite AGENTS.md version table and history
- Version bumps: OPP v0.9.0, OL v0.6.0, ORF v0.4.16, Suite v0.4.0

> **Prerequisite:** Python >= 3.13. Verify with `python3 --version`.

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
| **OL** | Translate MD/XLIFF between languages | `ol translate-md <file> -s <src> -t <tgt> -o <dir>` | 21 tools (`translate_md_text`, `judge_text`…) | `Omni_Localizer/src/` |
| **ORF** | Backfill translated content → target format | `orf apply-md <file> --target-format <fmt> -o <out>` | 6 tools (`apply_md`, `apply_xliff`…) | `Omni_Re_Formatter/src/` |

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
- `ol-mcp` — 21 translation tools
- `orf-mcp-server` — 6 backfill tools

> **Note**: The MCP server names are not uniform across modules. OPP and ORF use `-server` suffix (`opp-mcp-server`, `orf-mcp-server`) while OL omits it (`ol-mcp`). This is a historical naming inconsistency; all three follow the same protocol.

### MCP Configuration

Configure the three MCP servers in your AI coding tool of choice.

#### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "opp-mcp-server": {
      "command": "uvx",
      "args": ["opp-mcp"]
    },
    "ol-mcp": {
      "command": "uvx",
      "args": ["ol-mcp"]
    },
    "orf-mcp-server": {
      "command": "uvx",
      "args": ["orf-mcp"]
    }
  }
}
```

If installed via pip instead of uvx:

```json
{
  "mcpServers": {
    "opp-mcp-server": {
      "command": "opp",
      "args": ["mcp"]
    },
    "ol-mcp": {
      "command": "ol",
      "args": ["mcp"]
    },
    "orf-mcp-server": {
      "command": "orf",
      "args": ["mcp"]
    }
  }
}
```

#### Cursor

Add to `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "opp-mcp-server": {
      "command": "uvx",
      "args": ["opp-mcp"]
    },
    "ol-mcp": {
      "command": "uvx",
      "args": ["ol-mcp"]
    },
    "orf-mcp-server": {
      "command": "uvx",
      "args": ["orf-mcp"]
    }
  }
}
```

#### OpenCode

Add to `opencode.json`:

```json
{
  "mcpServers": {
    "opp-mcp-server": {
      "command": "uvx",
      "args": ["opp-mcp"]
    },
    "ol-mcp": {
      "command": "uvx",
      "args": ["ol-mcp"]
    },
    "orf-mcp-server": {
      "command": "uvx",
      "args": ["orf-mcp"]
    }
  }
}
```

#### Tool-Call Scenarios

These MCP tool calls work in any AI coding tool that supports MCP. Use them to orchestrate the pipeline step by step.

**Extract a DOCX via OPP MCP:**

```json
{
  "tool": "extract_document",
  "params": {
    "file_path": "/path/to/document.docx",
    "target_format": "both",
    "source_lang": "en",
    "target_lang": "zh",
    "output_dir": "/tmp/opp"
  }
}
```

**Translate via OL MCP:**

```json
{
  "tool": "translate_md_text",
  "params": {
    "file_path": "/tmp/opp/document.md",
    "source_lang": "en",
    "target_lang": "zh",
    "output_dir": "/tmp/ol"
  }
}
```

**Backfill via ORF MCP:**

```json
{
  "tool": "apply_md",
  "params": {
    "file_path": "/tmp/ol/document.md",
    "target_format": "docx",
    "output_path": "/tmp/result.docx"
  }
}
```

**Full pipeline (chain all three MCP tools):**

```json
[
  {
    "tool": "extract_document",
    "params": {
      "file_path": "/path/to/document.docx",
      "target_format": "both",
      "source_lang": "en",
      "target_lang": "zh",
      "output_dir": "/tmp/opp"
    }
  },
  {
    "tool": "translate_md_text",
    "params": {
      "file_path": "/tmp/opp/document.md",
      "source_lang": "en",
      "target_lang": "zh",
      "output_dir": "/tmp/ol"
    }
  },
  {
    "tool": "apply_md",
    "params": {
      "file_path": "/tmp/ol/document.md",
      "target_format": "docx",
      "output_path": "/tmp/result.docx"
    }
  }
]
```

## MCP Tool Reference

### OPP MCP Server (7 tools)

| Tool | Description | Key Parameters |
|------|-------------|---------------|
| `extract_document` | Extract content from a single document file (DOCX, PPTX, PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, images) | `file_path` (str), `output_formats` (list[str]: md, xlf, both), `source_lang` (str, default: zh), `target_lang` (str, default: en), `resource_dir` (str, optional) |
| `batch_extract` | Process multiple files in one request | `file_paths` (list[str]), `output_formats` (list[str]), `source_lang` (str), `target_lang` (str) |
| `detect_format_tool` | Identify file format using magic bytes detection | `file_path` (str) |
| `generate_markdown` | Convert a document to Markdown format | `file_path` (str), `output_path` (str, optional) |
| `generate_xliff` | Convert a document to XLIFF format for translation | `file_path` (str), `source_lang` (str), `target_lang` (str), `output_path` (str, optional) |
| `save_skeleton` | Save skeleton ZIP from extracted document (required by ORF apply_xliff) | `file_path` (str), `base_name` (str, default: document), `output_dir` (str, optional) |
| `ping` | Health check endpoint | (none) |

### OL MCP Server (21 tools)

| Tool | Description | Key Parameters |
|------|-------------|---------------|
| `translate_md_text` | Translate markdown text through shield, translate, repair, unshield pipeline. Returns quality-gate warnings when `quality_gates:` are enabled in config. | `content` (str), `source_lang` (str), `target_lang` (str), `glossary_path` (str, optional), `config_path` (str, optional), `add_frontmatter` (bool) |
| `translate_xliff` | Translate XLIFF file, write translated target back to output. Inserts quality-gate warnings when `quality_gates:` are enabled in config. | `input_path` (str), `output_path` (str, optional), `source_lang` (str), `target_lang` (str), `glossary_path` (str, optional), `config_path` (str, optional) |
| `judge_text` | Evaluate translation quality with rubric scores (adequacy, fluency, terminology, format) | `source` (str), `target` (str), `source_lang` (str), `target_lang` (str), `glossary` (dict, optional) |
| `load_glossary` | Load a JSON glossary file for use in translation | `path` (str), `config_dir` (str, optional) |
| `get_relevant_terms` | Extract top-k relevant glossary terms for a source text | `text` (str), `glossary` (dict), `top_k` (int, default: 5) |
| `search_tm` | Search TMX translation memory for similar past translations | `source_text` (str), `tmx_path` (str), `threshold` (float, default: 0.85) |
| `batch_translate_texts` | Translate multiple markdown texts in parallel | `texts` (list[str]), `source_lang` (str), `target_lang` (str), `glossary_path` (str, optional), `concurrency` (int, default: 5) |
| `translate_file` | End-to-end file translation (OPP→OL→ORF in one call) | `input_path` (str), `source_lang` (str), `target_lang` (str), `target_format` (str), `output_path` (str) |
| `get_translation_status` | Poll status of an async translation task | `request_id` (str) |
| `verify_terms` | Verify glossary term usage in translated content (no LLM) | `source` (str), `target` (str), `glossary` (dict) |
| `profile_doc` | Profile a document's writing style via LLM, producing a StyleGuide | `content` (str), `source_lang` (str) |
| `extract_terms` | Extract key terms from source texts using YAKE | `texts` (list[str]), `top_k` (int) |
| `add_tm_entries` | Add entries to a TMX translation memory file | `tmx_path` (str), `entries` (list[dict]) |
| `disambiguate` | Resolve polysemous glossary terms with LLM context understanding | `text` (str), `glossary` (dict) |
| `shield_md_text` | Shield markdown content (replace code, math, links with markers) | `content` (str) |
| `unshield_md_text` | Unshield markdown content (restore markers from shield_map) | `content` (str), `shield_map` (dict) |
| `generate_report` | Generate a translation report (HTML + CSV) | `source_path` (str), `target_path` (str) |
| `inspect_config` | Inspect the resolved OL configuration | (none) |
| `get_capabilities` | Return module capabilities (roles, language pairs, tools) | (none) |
| `extract_warnings` | Extract warning markers from an output file | `file_path` (str) |
| `ping` | Health check endpoint | (none) |

### ORF MCP Server (6 tools)

| Tool | Description | Key Parameters |
|------|-------------|---------------|
| `apply_md` | Convert MD file to target format (DOCX, ODT, EPUB, HTML, RTF, PDF, PPTX, ICML, SRT, CSV, XLSX, XML, IPYNB, EML, MSG, JSON) | `input_md` (str), `target_format` (str), `output_path` (str, optional), `images` (list[dict], optional), `separate_images` (bool, default: True) |
| `apply_xliff` | Apply XLIFF translation to original document with optional image injection | `input_file` (str), `xliff_path` (str), `output_path` (str), `format` (str), `xliff_content` (str, optional), `images` (list[dict], optional) |
| `batch_convert` | Batch convert MD files in a directory | `input_dir` (str), `target_format` (str), `pattern` (str, default: *.md) |
| `detect_format` | Detect document format | `file_path` (str) |
| `info` | Get document information (format, size, resources) | `file_path` (str) |
| `ping` | Health check endpoint | (none) |

## Format Support Matrix

ORF `apply-md` supports 16 output formats: DOCX, ODT, EPUB, HTML, RTF, PDF, PPTX, ICML, SRT, CSV, XLSX, XML, IPYNB, EML, MSG, JSON.

See `README.md` → "Cross-Format Production-Readiness" for the full 36-path verified matrix.

## Critical Notes

1. **FAKE_LLM required** — All CLI calls need `OMNI_TEST_FAKE_LLM=1` unless real LLM API keys are configured.
2. **pandoc dependency** — DOCX, ODT, EPUB, RTF, ICML outputs require pandoc (auto-installed via `pypandoc-binary`).
3. **MSG → use .eml** — MSG output requires commercial Aspose.Email. Use `.eml` instead (open standard, fully supported).
4. **Cross-format XLIFF** — Converting DOCX XLIFF → PPTX needs `orf apply-xliff --force`.
5. **PDF XLIFF blocked** — OPP intentionally blocks PDF → XLIFF generation (unsupported).

### Pre-commit hooks

Hooks are configured in `.pre-commit-config.yaml` at the project root.

**Install:**

```bash
pip install pre-commit
pre-commit install
```

**Run on all files (CI-style):**

```bash
pre-commit run --all-files
```

**Run a specific hook:**

```bash
pre-commit run gitleaks --all-files
pre-commit run trailing-whitespace --all-files
```

**Hooks included:**

| Hook | Source | What it checks |
|------|--------|----------------|
| `gitleaks` | gitleaks/gitleaks | Hardcoded secrets, API keys |
| `check-added-large-files` | pre-commit-hooks | Files > 512 KB |
| `check-merge-conflict` | pre-commit-hooks | Unresolved merge markers |
| `detect-private-key` | pre-commit-hooks | Leaked SSH/GPG keys |
| `end-of-file-fixer` | pre-commit-hooks | Files end with newline |
| `trailing-whitespace` | pre-commit-hooks | No trailing spaces |
| `omni-contract-smoke` | local | Pipeline contract smoke (manual only) |

**Note**: `omni-contract-smoke` is `stages: [manual]` — it does NOT run on `git commit`. Run it explicitly with `pre-commit run omni-contract-smoke --all-files` or via `make smoke`. It uses `OMNI_TEST_FAKE_LLM=1` and requires the `.venv_ol` venv to be built.

**CI integration**: The Makefile `lint` target runs `pre-commit run --all-files`. Run it before pushing to catch hook violations early.

## MCP Local Testing Guide

Test each MCP server locally without configuring a client. All servers use
stdio transport and can be started from the command line.

### Prerequisites

```bash
# Set fake LLM for zero-cost translation testing
export OMNI_TEST_FAKE_LLM=1

# Set allowed directories for path validation
export OPP_ALLOWED_DIRECTORIES="/tmp/opp,/tmp/output"
```

### Start Each Server

**OPP MCP Server:**

```bash
# From the Omni_Pre_Processor directory
cd Omni_Pre_Processor
python -m opp.mcp.server

# Or via installed CLI
opp mcp
```

**OL MCP Server:**

```bash
# From the Omni_Localizer directory
cd Omni_Localizer
python -m ol_mcp

# Or via installed CLI
ol mcp
```

**ORF MCP Server:**

```bash
# From the Omni_Re_Formatter directory
cd Omni_Re_Formatter
python -m orf.mcp.server

# Or via installed CLI
orf mcp
```

### Test with MCP Inspector

Use the MCP Inspector (from the `mcp` CLI tool) to interactively test any
server:

```bash
# Install mcp CLI
pip install mcp

# Inspect OPP
mcp dev Omni_Pre_Processor/src/opp/mcp/server.py

# Inspect OL
mcp dev Omni_Localizer/src/ol_mcp/__init__.py

# Inspect ORF
mcp dev Omni_Re_Formatter/src/orf/mcp/server.py
```

### Test via Python (in-process)

Each MCP server exposes its tool functions as regular Python functions that
can be called directly:

**OPP in-process test:**

```bash
cd Omni_Pre_Processor
PYTHONPATH=src python -c "
from opp.mcp.server import ping
import asyncio
result = asyncio.run(ping(auth_token=None))
print('ping OK' if result.get('success') else 'FAIL')
"
```

**OL in-process test:**

```bash
cd Omni_Localizer
PYTHONPATH=src python -c "
from ol_mcp.tools import ping
import asyncio
result = asyncio.run(ping())
print('ping OK' if 'success' in result else 'FAIL')
"
```

**ORF in-process test:**

```bash
cd Omni_Re_Formatter
PYTHONPATH=src python -c "
from orf.mcp.server import ping
import json
result = json.loads(ping())
print('ping OK' if result.get('success') else 'FAIL')
"
```

### Test with Direct CLI Subprocess

Each MCP server delegates to the module's CLI. Test the CLI directly:

```bash
export OMNI_TEST_FAKE_LLM=1

# OPP
opp --target-format=md sample.docx --output-dir /tmp/test_opp

# OL
ol translate-md /tmp/test_opp/sample.md -s en -t zh -o /tmp/test_ol

# ORF
orf apply-md /tmp/test_ol/sample.md --target-format docx -o /tmp/result.docx
```

### Environment Variables for Testing

| Variable | Purpose |
|----------|---------|
| `OMNI_TEST_FAKE_LLM=1` | Use mock LLM responses (no API keys needed) |
| `OMNI_TEST_FAKE_PANDOC=1` | Bypass pandoc for ORF format conversion |
| `OPP_ALLOWED_DIRECTORIES` | Comma-separated allowed paths for OPP MCP |
| `OL_CONFIG_PATH` | Override OL LLM config path |
| `MCP_SHARED_SECRET` | Enable shared-secret auth (omit for dev testing) |

## Agent Tips

- Use the FAKE_LLM seam for zero-cost testing — no API keys needed.
- **Glossary**: see [CONTEXT.md](CONTEXT.md) — shared pipeline terminology (Ubiquitous Language).
- ORF `apply-md` supports 16 formats; check the table before assuming availability.
- `omni_suite/cli.py` is print-only — use per-module CLIs for real work.
- For end-to-end orchestration, chain per-module MCPs in sequence.
- Per-sub-repo `AGENTS.md` files (in each sub-repo root) cover dev
  / agent context for that sub-repo: architecture, CLI, MCP tools,
  env vars, test patterns, known gotchas. SKILL.md files exist in
  OPP and OL sub-repos at `src/.../SKILL.md` for tool-level references;
  ORF has no SKILL.md (worst-off, see its AGENTS.md "Known issues"
  for context).
- Tests live under `tests/` at suite root and within each `Omni_*/tests/` sub-repo.
- For end-to-end orchestration, chain per-module MCPs in sequence, passing `output_dir` from each step as input to the next.
- OPP MCP provides 7 tools: `extract_document`, `batch_extract`, `detect_format_tool`, `generate_markdown`, `generate_xliff`, `save_skeleton`, `ping`.
- OL MCP provides 21 tools (8 listed here): `translate_md_text`, `judge_text`, `load_glossary`, `get_relevant_terms`, `search_tm`, `batch_translate_texts`, `translate_xliff`, `ping`, + 13 more — full table in the OL MCP Tool Reference section above.
- ORF MCP provides 6 tools: `apply_md`, `apply_xliff`, `batch_convert`, `detect_format`, `info`, `ping`.
- Use `uvx` for quick MCP server execution without manual install. For pip-installed variants, use `opp mcp`, `ol mcp`, and `orf mcp` as the command.
- Set `OMNI_TEST_FAKE_LLM=1` in the MCP server environment for zero-cost testing without real API keys.
- Use `batch_extract` (OPP) or `batch_translate_texts` (OL) for processing multiple files in a single call.
- **`opp -v` now writes to stderr** (as of v0.6.2). Use `--detect-format -v file.docx` to see the detected format in your terminal without reading the log file.
- **OL E2E-65 (prompt injection strip)**: when calling `translate_md_text` with real LLMs, the output is post-processed to strip `CRITICAL/IMPORTANT/NOTE: Output ONLY...` echoes. Don't strip these patterns yourself; OL handles it.
- **OL quality gates**: Post-translation quality gates are configurable via `quality_gates:` in OL config. When enabled, `translate_md_text` returns quality warnings in its output and `translate_xliff` inserts them into the XLIFF. Tune length ratio thresholds with `OL_LENGTH_RATIO_MIN` / `OL_LENGTH_RATIO_MAX` env vars. Set `OL_TARGET_LOCALE` to enforce locale-specific checks.
- **OPP E2E-15 (orphan image filter)**: `extract_document` with `--target-format both` will not double-embed images that were already output inline. The image `images.json` manifest reflects this.
- **ORF E2E-07 (fuzzy match)**: `apply_xliff` to DOCX now tolerates small text mismatches between XLIFF source and DOCX paragraphs (up to 5-char length diff, 0.85 ratio). If you previously got `SKIPPED units`, retry — they should now backfill.

## How to validate (Codex)

Codex-specific entry point to the validation framework — same engine as
every other agent, driven purely from the CLI:

```bash
source .venv_ol/bin/activate

# Enumerate the library — no execution
python scripts/validation/run_validation.py --list

# Run one hermetic scenario (tier 1 = no LLM keys needed)
python scripts/validation/run_validation.py --scenario <name> --tier 1

# Contract-lint the library itself
python scripts/validation/run_validation.py --check
```

Only these scripts exist — do not invent other commands:
`scripts/validation/{run_validation.py, coverage_audit.py, validation_report.py, validation_diff.py}`.

**Reading results**: `validation-runs/latest.txt` points at the newest
run (`validation-runs/<ts>/scenarios.json`). Generate the director
report with
`python scripts/validation/validation_report.py validation-runs/<ts>/scenarios.json`
→ `report.md` in the same dir, with TWO verdict families side by side:
**agent-user conformance** (tool-* scenarios + AGENT-SURFACE standards:
contract, JSON shape, error clarity, path security, exit codes) and
**human-quality conformance** (pipeline-* scenarios + HUMAN-QUALITY
standards: LQA ≥ 4.0/5, paragraph ratio ±5%, CJK density < 5%, zero
foreign punctuation, drawing count, opens in python-docx). `unconfigured`
(missing env, e.g. no LLM keys) is never a pass and never a silent skip.

**Standards**: `scenarios/STANDARDS.md` — the single citable bar, two
families, exact anchors per step (`standard: STANDARDS.md#<anchor>`).
Read it before judging a verdict.

**Director checklist**: a human director completes the 10-minute loop
per run — see `docs/dev/validation-director-loop.md` (agent validator +
human director roles, per-run standards conformance pass).

## How to validate (any agent)

Generic instructions — applies to Hermes, Claude, Cursor, Codex,
opencode, or any agent that can run shell commands. The validation
framework is agent-agnostic: every scenario dispatches through the REAL
shipped surface (no mocks, no FAKE_LLM as evidence); tier-1 scenarios
are hermetic and need no LLM keys.

```bash
source .venv_ol/bin/activate

# 1. See what exists (no execution, no LLM)
python scripts/validation/run_validation.py --list

# 2. Run one hermetic scenario (tier 1 = no LLM keys needed)
python scripts/validation/run_validation.py --scenario <name> --tier 1

# 3. Lint the library itself (falsifiable expects, standard anchors)
python scripts/validation/run_validation.py --check

# 4. Coverage audit — every live MCP tool must be exercised by a scenario
python scripts/validation/coverage_audit.py

# 5. Diff two runs (verdict changes + regression detection)
python scripts/validation/validation_diff.py <runs-dir>/<ts1> <runs-dir>/<ts2>
```

**Reading results**:
1. `validation-runs/latest.txt` → path of the newest run
   (`validation-runs/<ts>/scenarios.json`).
2. Generate the director report:
   `python scripts/validation/validation_report.py validation-runs/<ts>/scenarios.json`
   → `report.md` + `report.json` in the same run dir.

`report.md` renders TWO verdict families side by side — judge both:

| Family | What it proves |
|---|---|
| **agent-user conformance** | every agent-facing tool/CLI works as an agent would use it (tool-* scenarios + AGENT-SURFACE anchors: `#tool-contract`, `#json-parseable`, `#error-clarity`, `#path-security`, `#exit-codes`) |
| **human-quality conformance** | pipeline output satisfies human end-users (pipeline-* scenarios + HUMAN-QUALITY anchors: `#lqa-threshold`, `#para-ratio`, `#cjk-density`, `#punct-hygiene`, `#drawing-count`, `#opens-docx`) |

`unconfigured` (missing env, e.g. no LLM keys) is a distinct status —
never a pass, never a silent skip.

**Standards**: `scenarios/STANDARDS.md` is the single citable bar —
every step's `expect` cites `standard: STANDARDS.md#<anchor>` naming its
family. Read it before judging a verdict; never invent thresholds.

**Director checklist**: a human director completes the 10-minute loop
per run — `docs/dev/validation-director-loop.md` (two-role model: agent
validator + human director; per-run standards conformance pass ticking
both families).
