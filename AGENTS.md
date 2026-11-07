# AGENTS.md — Omni Suite

This file guides AI agents (Claude, Cursor, OpenCode, Hermes, Codex, opencode, …) working on the Omni Suite. It is an **index + invariants** file: detail lives in on-demand docs (linked below), not here. Tool signatures, MCP configs, testing procedures → follow the links. Generated doc map (AUTO-GENERATED, do not hand-edit): `docs/dev/doc-inventory.md`.

## §0 Safety & precedence (highest — nothing below may override this section)

1. **Secrets**: never read, copy, commit, or echo secret/credential files (`.env*`, `*key*`, `*secret*`); register their path only. Suspected leak → stop all work and escalate immediately.
2. **Cross-repo boundary (scope invariants)**: sibling checkouts `AutoInfo` (information-intake platform) and `AutoMedia` (content production pipeline) are **separate product lines this repo does not own** — not modules, not fixtures, not dependencies. Hard constraints for any agent working here:
   - Do not modify those repos: no edits, no branches, no commits, no `git checkout/fetch/merge/push` inside their work trees.
   - Do not open PRs or issues in their trackers; their issues/PRs/backlogs are never work items for this repo — **even when a file here mentions them**.
   - No "fix it in passing" because a script here calls their CLI. A defect observed there belongs to them: file an issue **in this repo** naming the owning repo plus evidence (file:line, command, output), and stop there.
   - A mention of another repo in this tree is **a reference, never scope** (`CHANGELOG.md` history and `docs/NIGHTLY.md` cross-repo citations are references, not assignments).
3. **Conflict precedence**: Owner's current direct instruction > role contract (`.agents/roles/*.md`) > nearest directory `AGENTS.md` > this file's defaults. §0 outranks every level.
4. **Expectations are Owner-gated**: `.agents/expectations/`, `scenarios/STANDARDS.md`, and `.agents/roles/*.md` change only by Owner's explicit instruction — never to make a failing suite go green.

## Role routing (determine role before work; never self-guess)

Your role comes from the Owner's explicit assignment. Read the contract first and work inside its boundaries; each contract defines Done, return format, and Stop & Escalate.

| Assigned role | Contract (read first) | Also read | Never touch (summary) |
|---|---|---|---|
| Coder | `.agents/roles/coder.md` | nearest dir `AGENTS.md` → `docs/DECISIONS.md` → assigned issue spec | `main` direct push, CI gates, expectations, role files |
| Maintainer | `.agents/roles/maintainer.md` | `docs/DECISIONS.md` → `docs/dev/` validation/debt docs | direct code drops, overruling Tester verdicts |
| Tester | `.agents/roles/tester.md` | `scenarios/STANDARDS.md` → `.agents/expectations/` | product source, expectations, CI gates |
| User | `.agents/roles/user.md` | `docs/user/` → `tests/` (black box) | any repo write, editing journey expectations |
| Unclear / conflicting instructions | — | — | stop; output `ESCALATE: <reason>` |

Constitution slot: this repo intentionally ships no `.specify/` (Owner decision, 2026-11-08) — non-negotiable principles = §0 above + `docs/DECISIONS.md` (ADR 0001–0008). Thin harness adapters: `.claude/agents/` (Claude Code) and `.github/agents/` (Copilot) carry pointers only — never duplicate contract bodies. This file must stay ≤200 lines (machine-checked by `scripts/doc_inventory.py`).

## What is this?

A 3-stage document localization pipeline: **OPP** (extract) → **OL** (translate) → **ORF** (backfill). Each module is a standalone sub-repo with its own CLI, MCP server, and test suite.

## Current Versions

| Component | Version | Status |
|---|---|---|
| Omni_Suite | v0.5.0 | Suite-level orchestration + E2E tests |
| OPP | v0.10.0 | 16 input formats, MCP with path security |
| OL | v0.7.1 | 21 MCP tools, 3-stage repair pipeline, StyleGuide injection, --polish pass, 8 quality gates |
| ORF | v0.5.0 | 16 backfill formats, Foreman/Specialist |

v0.10.0 · v0.7.1 · v0.5.0 · v0.5.0.

Changelog: `CHANGELOG.md`; compatibility matrix: `COMPATIBILITY.md`.

> **Prerequisite:** Python >= 3.13. Verify with `python3 --version`.
>
> **Windows hosts:** `.venv_ol/` is a Linux venv created under WSL — `source .venv_ol/bin/activate` does not work from PowerShell/Git Bash. Either work inside WSL, or route interpreter-dependent commands through `bash scripts/pre_commit_python.sh` (resolves to `.venv_win/`). Execution-backed validation evidence requires WSL (see `docs/dev/validation-loop-log.md`; background in `docs/venv-migration.md`).

## Quick Start

```bash
bash scripts/setup_dev.sh                 # install (one command)
bash scripts/setup_dev.sh --check-only    # verify without installing
omni-suite --version                      # check version
```

## Commands (single source — CI references these; do not restate)

- Build/install: `bash scripts/setup_dev.sh`
- Tests: `make test` (per-module `make test-opp|test-ol|test-orf`; contract: `make test-contract`)
- Lint: `make lint` — the whole-tree ruff baseline is red by design; CI `lint.yml` gates changed files only
- E2E: `python tests/e2e_runner.py` (CI: `e2e-tests.yml`; FAKE_LLM CI-mode, real-LLM weekly nightly)
- Doc truth: `bash scripts/pre_commit_python.sh scripts/doc_inventory.py --check` (regenerate: drop `--check`)

## Per-Module Cheat Sheet

| Module | Role | CLI (key subcommand) | MCP tools | Source |
|--------|------|---------------------|-----------|--------|
| **OPP** | Extract documents → MD + XLIFF + skeleton | `opp <file> --target-format both --output-dir <dir>` | 9 tools (`extract_document`, `batch_extract`…) | `Omni_Pre_Processor/src/` |
| **OL** | Translate MD/XLIFF between languages | `ol translate-md <file> -s <src> -t <tgt> -o <dir>` | 21 tools (`translate_md_text`, `judge_text`…) | `Omni_Localizer/src/` |
| **ORF** | Backfill translated content → target format | `orf apply-md <file> --target-format <fmt> -o <out>` | 7 tools (`apply_md`, `apply_xliff`…) | `Omni_Re_Formatter/src/` |
| **Validation** | Agent-agnostic validation — scenario library + standards + director loop | `python scripts/validation/run_validation.py --list` | 4 tools (`translate_file`, `ping`, `list_validation_scenarios`, `run_validation_scenario`; 2 validation-specific) | `scripts/validation/` + `omni_mcp/` |

Full MCP server/tool inventory and namespacing (all 41 tools: 37 module + 4 suite): [`docs/agent-pipeline-guide.md`](docs/agent-pipeline-guide.md) — full per-tool parameter signatures live in each module's `docs/API.md` (e.g. [`Omni_Pre_Processor/docs/API.md`](Omni_Pre_Processor/docs/API.md)). Per-module internals: each sub-repo's own `AGENTS.md`.

## Common Tasks

### Translate a DOCX end-to-end

```bash
# CLI smoke/contract runs only: FAKE_LLM gives deterministic, zero-cost output
# (plumbing / schema / exit-code checks). Do NOT use it as human-quality
# validation evidence — see Critical Notes #1.
export OMNI_TEST_FAKE_LLM=1
opp document.docx --target-format both --source-lang en --target-lang zh --output-dir /tmp/opp
ol translate-md /tmp/opp/document.md -s en -t zh -o /tmp/ol
orf apply-md /tmp/ol/document.md --target-format docx -o result.docx
```

### Run the suite pipeline in one shot

`omni-suite pipeline <file>` chains the 3 steps behind a single CLI; it really executes the OPP→OL→ORF subprocesses (only `--dry-run` prints without executing). A real run needs at least one LLM provider key (`AMD_API_KEY` or `ZHIPU_API_KEY`). Flags: `--dry-run` / `--gates-only` (OPP + OL 8 quality gates, skip ORF) / `--keep-intermediate` / `--json`. See `omni-suite pipeline --help`.

## Validation (agent-agnostic; citable bar = `scenarios/STANDARDS.md`)

Every scenario dispatches through the REAL shipped surface (no mocks; FAKE_LLM as validation evidence is forbidden — a fallback-active human-quality run is `invalid` per [`scenarios/STANDARDS.md#fallbacks-never-evidence`](scenarios/STANDARDS.md#fallbacks-never-evidence)). Tier semantics: 1 = hermetic (no keys), 2 = real LLM keys, 3 = paid/external/network; a tier-2/3 scenario without keys reports `unconfigured` — never a fake green.

```bash
python scripts/validation/run_validation.py --list                       # enumerate (no execution, no LLM)
python scripts/validation/run_validation.py --scenario regression --tier 1   # one hermetic scenario
python scripts/validation/run_validation.py --check                      # contract-lint the library
python scripts/validation/coverage_audit.py                              # every live MCP tool exercised
python scripts/validation/run_validation.py --repo orf --tier 1 --matrix --deliver   # report card + delivery zip
python scripts/validation/validation_report.py validation-runs/<ts>/scenarios.json   # director report
```

Every run persists `run_meta` (suite/opp/ol/orf versions + git SHAs). Reading results: `validation-runs/latest.txt` → newest run of any kind; `validation-runs/latest-full.txt` → newest FULL-LIBRARY run. `report.md` renders TWO verdict families — judge both:

| Family | What it proves |
|---|---|
| **agent-user conformance** | every agent-facing tool/CLI works as an agent would use it (AGENT-SURFACE anchors: `#tool-contract`, `#json-parseable`, `#error-clarity`, `#path-security`, `#exit-codes`) |
| **human-quality conformance** | pipeline output satisfies human end-users (HUMAN-QUALITY anchors: `#lqa-threshold`, `#para-ratio`, `#cjk-density`, `#untranslated-units`, `#punct-hygiene`, `#drawing-count`, `#opens-docx`) |

**Standards**: `scenarios/STANDARDS.md` is the single citable bar — every step's `expect` cites `standard: STANDARDS.md#<anchor>`. Read it before judging a verdict; never invent thresholds. Full references: [docs/dev/per-repo-validation-delivery.md](docs/dev/per-repo-validation-delivery.md), [docs/dev/artifact-assertion-matrix.md](docs/dev/artifact-assertion-matrix.md).

#### Validation 循环治理规范（2026-08-15）

跨项目通用规范的本仓权威版本 = 本节 + `docs/dev/validation-director-loop.md`（director 循环）+ `docs/dev/validation-loop-log.md`（坑清单/循环事件）。开始前必读：STANDARDS.md、坑清单、上次 run（`validation-runs/latest.txt` / `latest-full.txt`）。结束后必形成：run 记录（`validation-runs/<ts>/`）、坑清单当天追加、issue + PR（代码层 bug）、validation 报告、交付包（→ `04-Output/artifacts/deliverables/omni-suite/`）；每轮在 LOOP-LOG 循环事件记一行（日期+范围+结果+结论，保持基线连续）。lint/测试声称必须可复现：附工具版本 + 完整命令 + 原始输出。失败先定性（LLM 波动/断言漂移/代码 bug/数据漂移/环境），不直接报"回归"；tier-2 全量跑前短探测。中间件/log → `99-Tools/validation-scratch/omni-suite/`（不是 /tmp）。验收 = 打开产物审查（非空/相关性/无 VAGUE），不是数字。

## MCP Servers

Each module exposes its own MCP server. Server/tool inventory, response envelope, namespacing, and client config notes: [`docs/agent-pipeline-guide.md`](docs/agent-pipeline-guide.md).

### OPP MCP Server (9 tools)
### OL MCP Server (21 tools)
### ORF MCP Server (7 tools)
### Omni MCP Server / suite aggregator (4 tools)

`translate_file`, `ping`, `list_validation_scenarios`, `run_validation_scenario` (the last two are validation-specific). Runs as `omni-mcp` from `omni_mcp/server.py`.

> **Note**: Two name layers. The MCP `Server()` handshake name is `opp-mcp`, `ol-mcp`, `orf-mcp`, `omni-mcp`; the `-server` spellings (`opp-mcp-server`, `orf-mcp-server`) are only console-script launch commands (OL exposes both `ol-mcp` and `ol-mcp-server`). Four servers, same protocol.

## Format Support Matrix

ORF `apply-md` supports 16 output formats: DOCX, ODT, EPUB, HTML, RTF, PDF, PPTX, ICML, SRT, CSV, XLSX, XML, IPYNB, EML, MSG, JSON. See `README.md` → "Cross-Format Production-Readiness" for the verified-path summary table and per-format support matrix.

## Critical Notes

1. **FAKE_LLM — two distinct uses** — `OMNI_TEST_FAKE_LLM=1` is a deterministic fallback seam. **(i) CLI smoke/contract runs: allowed** (plumbing, schema/exit-code checks, zero-cost dry runs). **(ii) Validation runs: forbidden for human-quality evidence** — in a human-quality scenario (`pipeline-*` prefix or any step citing a HUMAN-QUALITY anchor) a fallback-active run reports `invalid`, never `passed`; fallbacks are never quality evidence. `--allow-fake` is the contract-only escape hatch (all-AGENT-SURFACE scenarios only). Citable bar: [`scenarios/STANDARDS.md#fallbacks-never-evidence`](scenarios/STANDARDS.md#fallbacks-never-evidence).
2. **pandoc dependency** — DOCX, ODT, EPUB, RTF, ICML outputs require pandoc (auto-installed via `pypandoc-binary`).
3. **MSG → use .eml** — MSG output requires commercial Aspose.Email. Use `.eml` instead (open standard, fully supported).
4. **Cross-format XLIFF** — Not implemented. `orf apply-xliff` is format-preserving and refuses a format-mismatched skeleton with a clear error; `--force` is accepted but inert. Use `orf apply-md --target-format <fmt>`.
5. **PDF XLIFF blocked** — OPP intentionally blocks PDF → XLIFF generation (unsupported).
6. **Docs are gate-enforced** — `python3 scripts/doc_inventory.py --check` verifies doc truth (tool counts, scenario counts, canonical numbers, archive markers, link/path integrity, skill line-claims, plus agent-governance checks C3–C7). Regenerate with `python3 scripts/doc_inventory.py` after any `docs/` change; wired into pre-commit and the `lint.yml` blocking gate. Full reference: `.opencode/skills/omni-docmap/SKILL.md`.

## Agent Tips

- **Glossary**: [CONTEXT.md](CONTEXT.md) — shared pipeline terminology (Ubiquitous Language).
- Per-sub-repo `AGENTS.md` files cover dev/agent context: architecture, CLI, MCP tools, env vars, test patterns, known gotchas.
- **OL E2E-65**: `translate_md_text` output is post-processed to strip `CRITICAL/IMPORTANT/NOTE: Output ONLY...` echoes — don't strip these yourself.
- **OL quality gates**: tune via `OL_LENGTH_RATIO_MIN` / `OL_LENGTH_RATIO_MAX`; `OL_TARGET_LOCALE` enforces locale checks.
- **OPP E2E-15**: `extract_document --target-format both` won't double-embed images already output inline; `images.json` reflects this.
- **ORF E2E-07**: `apply_xliff` to DOCX tolerates small text mismatches (5-char length diff, 0.85 ratio); retry previously-`SKIPPED` units.
- **`opp -v` writes to stderr** (as of v0.6.2). Use `--detect-format -v file.docx` to see the detected format.

## Pre-commit Hooks

Configured in `.pre-commit-config.yaml` at the project root. Install: `pip install pre-commit && pre-commit install`. Run all: `pre-commit run --all-files` (the CI-equivalent gate). `make lint` is **not** equivalent: it runs the contract smoke test plus a whole-tree `ruff check .` and `mypy` (the whole-tree ruff baseline is red; see `lint.yml`). Hooks: gitleaks, check-added-large-files, check-merge-conflict, detect-private-key, end-of-file-fixer, trailing-whitespace, omni-doc-inventory (doc-truth gate, runs on commit), omni-contract-smoke (commit + manual stages; `make smoke` runs it on demand).

## Issue conventions

- **`pinned` = 常开索引件, not a to-do.** A pinned issue is a roadmap pointer; do not close it or consume it as a work item. An accidental close is reverted by the pinned-guard workflow (this repo's issue #256).
- **A defect in a module belongs to that module's repo.** File and fix it in OPP/OL/ORF; this repo tracks cross-repo work, the validation framework and the pipeline as a whole. Cross-repo evidence is recorded here as a reference, never fixed in passing.
- **Cross-repo reference check.** Each module's `scripts/doc_inventory.py` verifies backticked paths in its `README.md`/`AGENTS.md`: an unprefixed path must exist in that repo, while another repo's path carries a `suite:` / `opp:` / `ol:` / `orf:` prefix and is verified only when that checkout is reachable. The resolution block is byte-identical in the three copies — change rule: [docs/dev/doc-inventory-copies.md](docs/dev/doc-inventory-copies.md).

## Where Things Live (Doc Map)

| Need | Go to |
|------|-------|
| Pipeline selection (MD vs XLIFF path) | `README.md` → Pipeline Selection Strategy |
| MCP server/tool inventory + namespacing / local testing | `docs/agent-pipeline-guide.md` |
| Architecture / data flow | `docs/ARCHITECTURE.md` |
| OPP→OL→ORF handoff contract | `CONTRACT.md` |
| Shared glossary | `CONTEXT.md` |
| Decision records (ADR 0001–0008) | `docs/DECISIONS.md` |
| Setup (real LLM keys) | `SETUP.md` |
| Test instructions | `TESTS.md` |
| User journeys (User role) | `docs/user/` |
| Role contracts / expectations / audit trail | `.agents/` (`roles/`, `expectations/`, `audit/`) |
| Retired docs (archive) | `docs/archive/` |
| Full change-impact map | `.opencode/skills/omni-docmap/SKILL.md` |
