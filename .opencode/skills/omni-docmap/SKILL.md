---
name: omni-docmap
description: Complete documentation inventory and change-impact map for the Omni Suite project. Use when you need to know what documentation exists, where it lives, and — most importantly — which docs MUST be updated when making any change to the codebase.
---

# Omni Suite — Documentation Map & Change Impact Matrix

## When to use this skill

- **You're making a change** and need to know: "which docs must I update?"
- **You're onboarding** and want to understand the documentation landscape
- **You need to find a specific doc** (architecture, API, security, etc.)
- **You're reviewing a PR** and want to verify doc coverage
- **You're releasing a version** — doc freeze checklist

Load with: `skill(name="omni-docmap")`

---

## Part A — Doc Inventory

All paths are relative to the project root `/mnt/d/贯维/Omni_Suite`. Each entry documents the file's purpose, audience, and what kind of changes trigger an update.

### A1 — Root-Level Docs (Project Entry Points)

| File | Lines | Audience | Purpose | Update Trigger |
|------|-------|----------|---------|---------------|
| `CONTEXT.md` | 292 | All agents | Shared glossary / Ubiquitous Language of pipeline terms (OPP/OL/ORF, MD/XLIFF channels, shield/unshield, FAKE_LLM, Foreman/Specialist, etc.) | New pipeline/domain term added or renamed |
| `README.md` | ~300 | All users | Project overview, pipeline selection strategy, format support matrix, Git submodule notes, environment | Version bumps, pipeline changes, new formats, env changes |
| `AGENTS.md` | ~523 | AI Agents | Per-module cheat sheet, MCP configuration for Claude/Cursor/OpenCode, MCP tool reference (full signatures), env vars, pre-commit hooks, MCP local testing | MCP tool changes, CLI changes, version bumps, env var changes, new formats |
| `CHANGELOG.md` | ~212 | All devs | Suite-level changelog (Unreleased + released versions) | Every change — always add an entry |
| `COMPATIBILITY.md` | ~31 | All devs | Suite↔submodule version compatibility matrix | Version bumps of any module |
| `CONTRIBUTING.md` | ~172 | Contributors | PR workflow, branch naming, test expectations, doc update requirements | Process changes, CI changes |
| `SETUP.md` | ~259 | Developers | Phase 1 setup guide for real LLM integration tests (API keys, config) | API key changes, env var changes, setup process changes |
| `PROJECT_STATUS.md` | ~126 | First file to read | Project snapshot: versions, test matrix health, recent changes | Version bumps, test health changes, architecture changes |
| `PRODUCTION_READINESS.md` | ~187 | Maintainers | V1-V11 production-readiness checklist (version consistency, module integrity, security, observability) | Any new production requirement, new check items |
| `ACCEPTED_GAPS.md` | ~42 | All devs | Known limitations and tradeoffs (PDF→XLIFF blocked, MSG requires commercial, etc.) | New gap discovered, existing gap resolved |
| `CONTRACT.md` | ~180 | All devs | OPP→OL→ORF handoff contract (artifact formats, metadata schemas, failure modes) | Pipeline boundary contract changes |
| `CLAUDE.md` | ~101 | Claude Code | Claude-specific context (architecture summary, commands, tips) | Architecture changes, CLI changes, MCP changes |
| `TESTS.md` | ~335 | Developers | Test instructions for real LLM + E2E suite (14 nightly tests, prerequisites) | Test suite changes, test configuration changes |
| `VERSION` | 3 | All | Suite version number (must match `pyproject.toml [project].version`) | Version bumps |
| `THIRD_PARTY_LICENSES.md` | — | Legal | Third-party license attributions | New dependency added |
| `.cursorrules` | — | Cursor | Cursor agent behavior rules | Agent behavior changes |
| `Makefile` | — | All devs | Build/test/lint targets (`make doctor`, `make smoke`, `make test-quick`, `make lint`) | Build process changes, new targets |

### A2 — `docs/` Directory (Authoritative Reference Docs)

| File | Lines | Purpose | Update Trigger |
|------|-------|---------|---------------|
| `docs/PRD.md` | 61 | Retrospective baseline PRD — single source of truth for requirements (vision, user stories, scope, acceptance criteria) | Requirement/scope/acceptance changes |
| `docs/七阶段AI开发流程-用CodingAgent交付成品的方法论.md` | 230 | 7-stage AI development methodology reference (how to deliver a finished product with a coding agent) | Methodology revisions |
| `docs/ARCHITECTURE.md` | ~515 | Cross-module architecture, pipeline diagrams, data flow | Architecture changes, new modules, pipeline flow changes |
| `docs/API_STABILITY.md` | ~307 | API stability guarantees per module, SemVer policy, deprecation policy | Version bumps, API surface changes, deprecation decisions |
| `docs/agent-pipeline-guide.md` | — | Full MCP tool signatures for all 34 tools across OPP/OL/ORF (OPP 7 / OL 21 / ORF 6) | MCP tool changes (add/remove/rename params) |
| `docs/DECISIONS.md` | ~59 | Architecture Decision Records (ADR 0001: CLI framework divergence) | New architectural decisions, superseded ADRs |
| `docs/ERROR_CODES.md` | ~113 | MCP error code catalog (OPP/OL/ORF) | Error code changes (add/rename/remove codes) |
| `docs/SECURITY.md` | ~250 | Security posture & user action items (C1, C2), PathValidator, MCP auth | Security model changes, env var changes |
| `docs/SECURITY_AUDIT.md` | ~954 | Full security audit: attack surface, identified gaps, severity model, roadmap | Security audit findings, new threat vectors |
| `docs/SECURITY_FINDINGS.md` | ~78 | venv dependency audit (`pip-audit` results, 19 vulns in 8 packages) | Dependency changes, vulnerability fixes |
| `docs/SLA.md` | ~127 | Service Level Agreement: latency targets, throughput, memory, crash rate | Performance targets change, new benchmarks |
| `docs/ACCEPTANCE.md` | ~84 | Production acceptance thresholds (LQA scores, latency, throughput, security) | Threshold changes, new quality gates |
| `docs/RELEASE_NOTES.md` | ~23 | Cross-repo monthly aggregated release notes | Each release (generated by `scripts/bumpversion.py`) |
| `docs/T14_LIMITATION.md` | ~220 | Historical T14 limitation (hermetic CI seam gap in OL CLI, RESOLVED) | Only if the fix is revisited |
| `docs/OPP_EXPECTATIONS.md` | — | OPP-specific expectations and behavior contracts | OPP behavior changes |
| `docs/OL_EXPECTATIONS.md` | — | OL-specific expectations | OL behavior changes |
| `docs/ORF_EXPECTATIONS.md` | — | ORF-specific expectations | ORF behavior changes |
| `docs/SUITE_EXPECTATIONS.md` | — | Suite-level expectations | Suite orchestration changes |
| `docs/OPP_VALIDATION_MASTER_PLAN.md` | — | OPP validation: 17 questions, 80 executable scenarios | OPP feature additions, format changes |
| `docs/OL_VALIDATION_MASTER_PLAN.md` | — | OL validation: 17 questions, 79 executable scenarios | OL feature additions, quality gate changes |
| `docs/ORF_VALIDATION_MASTER_PLAN.md` | — | ORF validation: 14 questions, 68 executable scenarios | ORF format additions, backfill changes |
| `docs/SUITE_VALIDATION_MASTER_PLAN.md` | — | Suite validation: 15 questions, 3 pipeline paths | Pipeline orchestration changes |
| `docs/observability/README.md` | — | Observability infrastructure docs | Metrics, logging, tracing changes |

### A3 — Skill Files (Agent Instructable Skills)

| File | Lines | Purpose | Update Trigger |
|------|-------|---------|---------------|
| `.opencode/skills/omni-suite/SKILL.md` | ~260 | Pipeline orchestration skill (primary suite skill) — CLI commands, MCP tools, env vars, pipeline selection | Pipeline changes, version bumps, env var changes, MCP changes |
| `.opencode/skills/omni-suite/references/` | 9 symlinks | Convenience symlinks to canonical docs | When referenced docs change (symlinks are gitignored) |
| `Omni_Pre_Processor/src/opp_agent/SKILL.md` | ~67 | OPP extraction skill (OpenCode) — tools, output format selection | OPP MCP tool changes, CLI changes, format changes |
| `Omni_Pre_Processor/src/opp_hermes/SKILL.md` | ~108 | OPP extraction skill (Hermes) | Same as opp_agent but for Hermes agent |
| `Omni_Localizer/src/.opencode/skills/ol-localizer/SKILL.md` | ~76 | OL translation skill (OpenCode) — CLI procedures, quality gates | OL pipeline changes, quality gate changes, MCP changes |
| `Omni_Localizer/src/.hermes/skills/ol-localizer/SKILL.md` | ~76 | OL translation skill (Hermes) | Same as ol-localizer but for Hermes agent |
| `Omni_Re_Formatter/src/.opencode/skills/orf-formatter/SKILL.md` | ~75 | ORF backfill skill (OpenCode) — apply-md vs apply-xliff, formats | ORF format changes, backfill behavior changes |

### A4 — Sub-repo AGENTS.md & README Files

| File | Purpose | Update Trigger |
|------|---------|---------------|
| `Omni_Pre_Processor/AGENTS.md` | OPP agent context: CLI reference, MCP tools, extractor architecture, image pipeline, env vars, tests | OPP feature changes, CLI changes, MCP changes, env changes |
| `Omni_Pre_Processor/README.md` | OPP user readme: features, installation, quick start, architecture | OPP feature additions, installation changes |
| `Omni_Localizer/AGENTS.md` | OL agent context: CLI reference, MCP tools, translation pipeline (6 stages), LLM model pool, quality gates, env vars, FAKE_LLM decision matrix | OL pipeline changes, model pool changes, quality gate changes |
| `Omni_Localizer/README.md` | OL user readme: features, configuration, CLI commands, MCP tools | OL feature additions, config changes |
| `Omni_Re_Formatter/AGENTS.md` | ORF agent context: CLI reference, MCP tools, 16 output formats, Foreman/Specialist, XLIFF backfill, env vars | ORF format additions, agent architecture changes |
| `Omni_Re_Formatter/README.md` | ORF user readme: features, supported formats, installation, architecture | ORF feature additions, format changes |

### A5 — Sub-repo CHANGELOG Files

| File | Purpose | Update Trigger |
|------|---------|---------------|
| `Omni_Pre_Processor/CHANGELOG.md` | OPP changelog | Any OPP change |
| `Omni_Localizer/CHANGELOG.md` | OL changelog | Any OL change |
| `Omni_Re_Formatter/CHANGELOG.md` | ORF changelog | Any ORF change |

### A6 — Other README Files

| File | Purpose |
|------|---------|
| `scripts/README.md` | 17 dev scripts documentation |
| `tests/README.md` | Test suite documentation |
| `tests/golden/xliff2docx/README.md` | Golden test data notes |
| `eval/reference/README.md` | Evaluation reference docs |

### A7 — Reports

| File | Purpose |
|------|---------|
| `reports/TEMPLATE-Bug-Report.md` | Bug report template |
| `reports/TEMPLATE-Comparison-Report.md` | Comparison report template |
| `reports/E2E-*.md` | E2E bug/issue reports |

---

## Part B — Change Impact Matrix

This section tells you **exactly which docs to update** for each type of change. Use it as a checklist.

### B1 — Version Bump (any module)

**Applies when**: Changing version in `pyproject.toml` of any module or suite.

| Priority | Document | What to update |
|----------|----------|----------------|
| 🔴 CRITICAL | `VERSION` | Suite version string |
| 🔴 CRITICAL | `pyproject.toml` (suite) | `[project].version` |
| 🔴 CRITICAL | `COMPATIBILITY.md` | Version matrix row |
| 🔴 CRITICAL | `AGENTS.md` | Version table (line ~11-18) |
| 🔴 CRITICAL | Module's `pyproject.toml` | `[project].version` for that module |
| 🔴 CRITICAL | Module's `AGENTS.md` | Version in header/table |
| 🔴 HIGH | `PROJECT_STATUS.md` | Version table + Git state |
| 🔴 HIGH | `docs/API_STABILITY.md` | Current version table (§2) |
| 🔴 HIGH | `CHANGELOG.md` (suite) | Add unreleased entry or release |
| 🔴 HIGH | Module's `CHANGELOG.md` | Add unreleased entry or release |
| 🟡 MEDIUM | `.opencode/skills/omni-suite/SKILL.md` | Version table (frontmatter + § "Current versions") |
| 🟡 MEDIUM | `docs/RELEASE_NOTES.md` | Release entry |
| 🟡 MEDIUM | `docs/SUITE_EXPECTATIONS.md` | Version numbers |
| 🟢 LOW | `SETUP.md`, `README.md` | Version mentions in examples |

**Automation**: `scripts/sync_version_docs.py` syncs version tables from `pyproject.toml` into README, AGENTS, COMPATIBILITY. Run it after every version bump.

**Verification**: `make doctor` → `omni-suite --compatibility` → check matrix. `pytest tests/integration/test_version_compat.py` validates.

### B2 — MCP Tool Changes (add/remove/rename/param change)

**Applies when**: Adding a new MCP tool, removing one, renaming, changing parameters.

| Priority | Document | What to update |
|----------|----------|----------------|
| 🔴 CRITICAL | `AGENTS.md` | MCP Tool Reference tables (3 tables: OPP 7/OL 21/ORF 6) + tool counts in Per-Module Cheat Sheet |
| 🔴 CRITICAL | `docs/agent-pipeline-guide.md` | Full tool parameter signatures |
| 🔴 CRITICAL | Module's `AGENTS.md` | MCP tool table in that module's AGENTS.md |
| 🔴 HIGH | `.opencode/skills/omni-suite/SKILL.md` | MCP tool quick reference + tool counts |
| 🔴 HIGH | Module's SKILL.md (e.g. `opp_agent/SKILL.md`) | Tool commands and examples |
| 🟡 MEDIUM | `docs/ERROR_CODES.md` | If new error codes are added |
| 🟡 MEDIUM | `docs/API_STABILITY.md` | If the change affects API stability guarantees |
| 🟡 MEDIUM | `CHANGELOG.md` (suite + module) | Changelog entry |
| 🟡 MEDIUM | `CLAUDE.md` | If Claude uses the changed tool |
| 🟢 LOW | `PROJECT_STATUS.md` | If tool count is mentioned |

### B3 — CLI Changes (add/remove/rename flag or command)

**Applies when**: Changing any CLI command, flag, or behavior.

| Priority | Document | What to update |
|----------|----------|----------------|
| 🔴 CRITICAL | Module's `AGENTS.md` | CLI reference table, command examples |
| 🔴 CRITICAL | Module's `README.md` | CLI command sections, Quick Start |
| 🔴 HIGH | `AGENTS.md` (suite) | Per-module cheat sheet, Common Tasks |
| 🔴 HIGH | `.opencode/skills/omni-suite/SKILL.md` | CLI examples, command sections |
| 🟡 MEDIUM | Module's SKILL.md | CLI invocation examples |
| 🟡 MEDIUM | `docs/DECISIONS.md` | If CLI framework divergence is affected |
| 🟡 MEDIUM | `docs/API_STABILITY.md` | If the change affects stability guarantees |
| 🟡 MEDIUM | `CHANGELOG.md` (suite + module) | Changelog entry |
| 🟡 MEDIUM | `CLAUDE.md` | CLI examples for Claude |
| 🟢 LOW | `docs/agent-pipeline-guide.md` | If CLI flag affects MCP behavior |
| 🟢 LOW | `CONTRIBUTING.md` | If CI/build process changes |

### B4 — Pipeline Behavior Changes (OPP→OL→ORF flow)

**Applies when**: Changing how stages interact, handoff contracts, artifact formats.

| Priority | Document | What to update |
|----------|----------|----------------|
| 🔴 CRITICAL | `CONTRACT.md` | Handoff contract version + artifact specs |
| 🔴 CRITICAL | `docs/ARCHITECTURE.md` | Pipeline diagrams, data flow descriptions |
| 🔴 HIGH | `AGENTS.md` | Common Tasks, pipeline examples |
| 🔴 HIGH | `README.md` | Pipeline Selection Strategy, format support table |
| 🔴 HIGH | `.opencode/skills/omni-suite/SKILL.md` | Pipeline examples, env vars |
| 🟡 MEDIUM | `docs/SUITE_VALIDATION_MASTER_PLAN.md` | Validation scenarios |
| 🟡 MEDIUM | `PROJECT_STATUS.md` | Pipeline description |
| 🟡 MEDIUM | `ACCEPTED_GAPS.md` | If limitations change |
| 🟡 MEDIUM | `CHANGELOG.md` | Changelog entry |

### B5 — Environment Variable Changes (add/remove/rename)

**Applies when**: Adding, removing, or renaming any env var.

| Priority | Document | What to update |
|----------|----------|----------------|
| 🔴 CRITICAL | `AGENTS.md` | Environment variables cheatsheet |
| 🔴 CRITICAL | Module's `AGENTS.md` | Env var table in that module |
| 🔴 CRITICAL | `.opencode/skills/omni-suite/SKILL.md` | Environment variables cheatsheet |
| 🟡 MEDIUM | Module's `README.md` | Env var section |
| 🟡 MEDIUM | `docs/SECURITY.md` | If the var is security-related (MCP auth, path allowlist) |
| 🟡 MEDIUM | `SETUP.md` | If the var affects setup process |
| 🟡 MEDIUM | `CHANGELOG.md` | Changelog entry |
| 🟢 LOW | `docs/ARCHITECTURE.md` | If the var changes architectural boundaries |

### B6 — Input/Output Format Changes

**Applies when**: Adding a new input format, new output format, changing format behavior.

| Priority | Document | What to update |
|----------|----------|----------------|
| 🔴 CRITICAL | Module's `README.md` | Supported formats list, feature section |
| 🔴 CRITICAL | Module's `AGENTS.md` | Extractor/format reference, format support table |
| 🔴 HIGH | `AGENTS.md` (suite) | Per-module cheat sheet, format support matrix |
| 🔴 HIGH | `README.md` (suite) | Cross-Format Production-Readiness table |
| 🟡 MEDIUM | `.opencode/skills/omni-suite/SKILL.md` | Output formats table, critical constraints |
| 🟡 MEDIUM | Module's SKILL.md | Format-related examples |
| 🟡 MEDIUM | `docs/ARCHITECTURE.md` | Pipeline diagram, format flow |
| 🟡 MEDIUM | `docs/API_STABILITY.md` | If format support affects API stability |
| 🟡 MEDIUM | `PRODUCTION_READINESS.md` | If production checks need updating |
| 🟡 MEDIUM | `docs/OPP_VALIDATION_MASTER_PLAN.md` | New format validation scenarios |
| 🟡 MEDIUM | `docs/ORF_VALIDATION_MASTER_PLAN.md` | New format validation scenarios |
| 🟡 MEDIUM | `ACCEPTED_GAPS.md` | If format-related gaps change |
| 🟡 MEDIUM | `CHANGELOG.md` | Changelog entry |
| 🟢 LOW | `CONTRACT.md` | If format affects handoff contract |

### B7 — Security Changes

**Applies when**: Modifying PathValidator, auth, secrets handling, security model.

| Priority | Document | What to update |
|----------|----------|----------------|
| 🔴 CRITICAL | `docs/SECURITY.md` | Security posture, action items |
| 🔴 CRITICAL | `docs/SECURITY_AUDIT.md` | Attack surface, gaps, roadmap |
| 🔴 HIGH | Module's `AGENTS.md` | PathValidator section, auth section |
| 🟡 MEDIUM | `docs/SECURITY_FINDINGS.md` | Dependency audit (if deps change) |
| 🟡 MEDIUM | `PRODUCTION_READINESS.md` | Security checks (V5-V7) |
| 🟡 MEDIUM | `ACCEPTED_GAPS.md` | If security gaps change |
| 🟡 MEDIUM | `CHANGELOG.md` | Changelog entry |

### B8 — Architecture Changes

**Applies when**: Refactoring modules, changing source layout, adding new agents.

| Priority | Document | What to update |
|----------|----------|----------------|
| 🔴 CRITICAL | `docs/ARCHITECTURE.md` | Architecture description, diagrams |
| 🔴 HIGH | `docs/DECISIONS.md` | New ADR or superseding existing ADR |
| 🟡 MEDIUM | Module's `AGENTS.md` | Source layout tree |
| 🟡 MEDIUM | Module's `README.md` | Architecture diagram |
| 🟡 MEDIUM | `.opencode/skills/omni-suite/SKILL.md` | Architecture overview |
| 🟡 MEDIUM | `CLAUDE.md` | Architecture summary for Claude |
| 🟡 MEDIUM | `CHANGELOG.md` | Changelog entry |

### B9 — Quality Gate / LQA Changes

**Applies when**: Adding/changing OL quality gates, LQA judging, post-processing.

| Priority | Document | What to update |
|----------|----------|----------------|
| 🔴 CRITICAL | `Omni_Localizer/AGENTS.md` | Quality gates table, pipeline diagram (stage 6) |
| 🔴 CRITICAL | `docs/OL_VALIDATION_MASTER_PLAN.md` | Quality gate validation scenarios (Q5-OL, Q6-OL) |
| 🟡 MEDIUM | `Omni_Localizer/README.md` | Quality gates config documentation |
| 🟡 MEDIUM | `.opencode/skills/omni-suite/SKILL.md` | Quality gates note |
| 🟡 MEDIUM | `docs/ACCEPTANCE.md` | LQA thresholds |
| 🟡 MEDIUM | `CHANGELOG.md` (OL + suite) | Changelog entry |

### B10 — Test Suite Changes

**Applies when**: Adding, removing, or restructuring tests.

| Priority | Document | What to update |
|----------|----------|----------------|
| 🔴 HIGH | `TESTS.md` | Test instructions, command examples, expected results |
| 🟡 MEDIUM | `PROJECT_STATUS.md` | Test matrix health table |
| 🟡 MEDIUM | `CONTRIBUTING.md` | Test expectations section |
| 🟡 MEDIUM | `CHANGELOG.md` | Changelog entry |

---

## Part C — Doc Update Workflow

### Step-by-step for any change:

```
1. Identify the change type from Part B (B1-B10)
2. Check the priority-ordered doc list for that change type
3. 🔴 CRITICAL items MUST be updated before merge — these are blockers
4. 🟡 MEDIUM items SHOULD be updated — create follow-up if not possible
5. 🟢 LOW items are nice-to-have
6. Run `scripts/sync_version_docs.py` if version numbers changed
7. Run `make doctor` to verify the system is still healthy
8. Check `lsp_diagnostics` on all changed doc files
```

### Branch naming convention (from CONTRIBUTING.md):

| Prefix | When |
|--------|------|
| `docs/` | Documentation-only changes |
| `feat/` | Feature + its docs |
| `fix/` | Bug fix + its docs |
| `chore/` | Build/config + its docs |

Every non-docs branch MUST include doc updates per the impact matrix above.

---

## Part D — Key Automation Tools

| Tool | Purpose | Run After |
|------|---------|-----------|
| `scripts/sync_version_docs.py` | Sync version tables from `pyproject.toml` into README, AGENTS, COMPATIBILITY | Version bumps (B1) |
| `scripts/check_readiness.py` | Auto-verify all 🔧 items from PRODUCTION_READINESS.md | Before release |
| `scripts/verify_mcp.py` | MCP smoke test orchestrator | MCP changes (B2) |
| `make doctor` | 7-check health gate (Python, keys, pandoc, WeasyPrint, md2pptx, MCP, sub-repos) | After any change |
| `make smoke` | Pipeline contract smoke test (pre-commit gate) | After pipeline changes (B4) |
| `pre-commit run --all-files` | Run all pre-commit hooks (gitleaks, formatting, etc.) | Before commit |

---

## Part E — Quick Reference: Doc Map by Audience

| Reader | Start with | Then read |
|--------|------------|-----------|
| **New developer** | `PROJECT_STATUS.md` → `README.md` | `AGENTS.md` → `docs/ARCHITECTURE.md` |
| **AI Agent (OpenCode)** | `AGENTS.md` → `.opencode/skills/omni-suite/SKILL.md` | Relevant module AGENTS.md |
| **Contributor** | `CONTRIBUTING.md` → `TESTS.md` | Module README, CHANGELOG |
| **Security reviewer** | `docs/SECURITY.md` → `docs/SECURITY_AUDIT.md` | `docs/SECURITY_FINDINGS.md` |
| **Release manager** | `VERSION` → `COMPATIBILITY.md` | `PRODUCTION_READINESS.md` |
| **Integrator** | `docs/API_STABILITY.md` → `docs/agent-pipeline-guide.md` | `CONTRACT.md` |
| **QA engineer** | `docs/*_VALIDATION_MASTER_PLAN.md` | `TESTS.md` |
