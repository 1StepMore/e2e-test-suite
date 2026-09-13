# Project Evaluation: Main Pain Points to Improve

**Date**: 2026-09-06
**Evaluator**: Sisyphus (automated codebase analysis)
**Scope**: Omni Suite (OPP → OL → ORF) — full project scan across agent-orientation, robustness, bugs, infrastructure, architecture, security, documentation

---

## Executive Summary

**Overall Grade: B+ (Strong with Known Warts)**

This is an unusually well-engineered agent-first codebase with rare strengths in agent-orientation, validation, and error handling, offset by infrastructure-layer duplication and operational gaps (suspended CI, leaked secrets remediation pending).

| Dimension | Grade | Key Evidence |
|-----------|-------|--------------|
| Agent-Orientation | A | 41 tool scenarios, STANDARDS.md anchors, get_capabilities, FAKE_LLM integrity guard |
| Robustness | A- | 97% typed, 0 bare-except violations, 8 quality gates, dual-engine fallbacks |
| Bugs | B+ | Working discovery→fix→regression loop; SEC-LEAK-1 fully remediated; 14 pre-existing → 13 fixed |
| Vibe Coding Infra | B | Strong pre-commit + validation; no CI, mixed CLI frameworks, inconsistent lint configs |
| Architecture | B+ | Clean decoupling, stateless handoff; 3-4× infrastructure duplication |
| Security | A- | Fail-closed, secret scanning, 63 tests; enforcement asymmetry, key rotation pending |
| Documentation | A | Honest, agent-oriented, versioned contracts, citable standards |

---

## Priority 1 — Critical (Blocking Reliability)

### 1. Infrastructure Duplication (3-4× across modules)

**Impact**: HIGH | **Effort**: HIGH

| Duplicated Component | Copies | Lines Each | Drift Risk |
|---------------------|--------|------------|------------|
| `PathValidator` | 3× | 200-280 | HIGH (ALLOWED_EXTENSIONS already diverged) |
| TokenBucket rate limiter | 4× | 85-119 | MEDIUM (OPP has per-tool buckets) |
| MCP error boundary | 3× | 130-175 | MEDIUM (different return shapes) |
| Pipeline orchestration | 2× | ~300 | HIGH (different arg parsing, output discovery) |
| structlog setup | 3× | 100-240 | LOW (converged) |
| MCP config loader | 2+× | 50-100 | MEDIUM |
| Format detection | 3× | varies | HIGH (magic-bytes tables maintained independently) |

**Why it hurts**: Security fix → apply 3 times. Bug fix → apply 3 times. Divergence is already happening.

**Fix**: Extract `omni-mcp-core` shared package with PathValidator, rate_limiter, error_boundary, structlog setup.

**Evidence**:
- `Omni_Pre_Processor/src/opp/mcp/security.py` (200 lines)
- `Omni_Re_Formatter/src/orf/mcp/security.py` (263 lines) — near-copy
- `Omni_Localizer/src/ol_mcp/security.py` (280 lines) — docstring says "Mirrors orf/mcp/security.py"
- `opp/utils/security.py` docstring claims "shared across OPP, OL, ORF" but ORF and OL never import it

---

### 2. CI/CD Suspended

**Impact**: CRITICAL | **Effort**: LOW-MEDIUM

- GitHub Actions disabled (origin account restricted)
- All test statuses are local-only
- No automated gates on PRs
- Pre-commit hooks run locally but not enforced

**Why it hurts**: No regression detection, no doc-truth enforcement, no security gates on incoming changes.

**Fix**: Restore CI or set up alternative (self-hosted runner, backup mirror Actions).

**Evidence**:
- README badge is static: `<!-- 1StepMore 主号 suspend 期间 GitHub Actions 徽章不实时，此为静态占位 -->`
- `tests/test_ci_no_submodules.py` exists but CI doesn't run

---

### 3. Security Key Rotation Pending (SEC-LEAK-1)

**Impact**: CRITICAL | **Effort**: USER ACTION REQUIRED

- Real API keys (Baidu/MiniMax/Zhipu/NVIDIA) were leaked in docs+plans
- Git history cleaned via `git filter-repo` across 354 commits
- **Action still needed**: Rotate keys at provider consoles + force-push to origin/backup

**Why it hurts**: Leaked keys may still be active at providers.

**Evidence**:
- `CHANGELOG.md` documents full remediation trail
- `SECURITY_AUDIT.md` has incident details

---

## Priority 2 — High (Degrading Developer/Agent Experience)

### 4. Doc Drift on Tool Counts

**Impact**: MEDIUM-HIGH | **Effort**: LOW

6 different numbers appear for OPP/OL/ORF tool counts across AGENTS.md, README, agent-pipeline-guide.md, .cursorrules, CLAUDE.md, get_capabilities.py:

| Module | Claimed In | Actual (Live Server) |
|--------|-----------|---------------------|
| OPP | 7 (README, agent-pipeline-guide.md, .cursorrules) | 9 |
| OL | 17 (get_capabilities.py docstring) | 21 |
| ORF | 6 (.cursorrules) | 7 |

**Why it hurts**: Agents cannot trust documentation. `scripts/doc_inventory.py` exists but isn't catching these.

**Fix**: Single canonical registry; fix `doc_inventory.py` to validate tool counts against live server schemas.

---

### 5. Mixed CLI Frameworks

**Impact**: MEDIUM | **Effort**: MEDIUM

| Module | Framework | Style |
|--------|-----------|-------|
| OPP | argparse | Manual `--help` formatting |
| OL | typer | Decorator-based, rich help |
| ORF | click | Group-based |

**Why it hurts**: Duplicated test strategies (`test_cli_help.py` has 3 separate fixture sets), inconsistent UX, harder for agents to discover commands.

**Fix**: Standardize on typer (best agent ergonomics: auto-generated JSON schemas, rich help).

---

### 6. Inconsistent Lint/Type Configs

**Impact**: MEDIUM | **Effort**: LOW

| Module | Ruff Select | Mypy |
|--------|-------------|------|
| Root | E, F, I, B, UP, N | check_untyped_defs=true |
| OL | E, F only | Different ignores |
| ORF | None defined | Inherits root |
| OPP | Inherits root | Inherits root |

**Why it hurts**: Code quality rules drift per module; OL has less strict linting than root.

**Fix**: Single ruff/mypy config at root; per-module overrides only when justified.

---

### 7. OL PathValidator Default Asymmetry

**Impact**: MEDIUM | **Effort**: LOW

| Module | Default Allowlist | Behavior |
|--------|-------------------|----------|
| OPP | None | **Fail-closed** (raises ValueError) |
| ORF | `[Path.cwd()]` | Fail-closed after fallback |
| OL | `[cwd, /tmp]` | **Fail-open** |

**Why it hurts**: OL MCP server is less secure by default. Agent may not realize `/tmp` is world-writable.

**Fix**: Make OL fail-closed like OPP/ORF. Document the difference clearly.

**Evidence**:
- `opp/mcp/config.py:171-173`: `raise ValueError("allowed_directories cannot be empty")`
- `ol_mcp/security.py:278-279`: falls back to `[Path.cwd(), Path("/tmp")]`

---

## Priority 3 — Medium (Code Quality & Maintainability)

### 8. Suite CLI Hardcoded Path

**Impact**: LOW-MEDIUM | **Effort**: LOW

```python
# omni_suite/cli.py:14
VENV_PATH = Path(__file__).parent.parent / ".venv_ol"
```

**Why it hurts**: Suite CLI only works in dev workspace, not as installed tool.

**Fix**: Use `sys.executable` or configurable path.

---

### 9. `punctuation.py` SyntaxWarning

**Impact**: LOW | **Effort**: TRIVIAL

```python
# Omni_Localizer/src/ol_post/punctuation.py:20
"""...``..."""  # invalid escape \`
```

**Why it hurts**: Warns on Python 3.12+, will error on 3.14+.

**Fix**: Raw string or escape the backtick.

---

### 10. OL `cli` Package Name Shadowing

**Impact**: LOW | **Effort**: MEDIUM

```python
# Omni_Localizer/src/ol_cli.py lines 46-79
# sys.path surgery to protect against generic 'cli' name being shadowed
```

**Why it hurts**: Code smell; fragile import workaround.

**Fix**: Rename to `ol_cli/` package (breaking change for OL imports).

---

### 11. Cross-Module Off-by-One (OPP paragraph_index vs ORF //w:p)

**Impact**: LOW | **Effort**: LOW

OPP's `paragraph_index` doesn't match ORF's `//w:p` enumeration — worked around document-wide.

**Why it hurts**: Latent contract hazard for future XLIFF work.

**Fix**: Document the mapping; add assertion in ORF that catches drift.

---

### 12. Legacy Directories Excluded from Lint/Type Checks

**Impact**: LOW | **Effort**: MEDIUM

Ruff excludes `opp/extractors`, `ol_buses`, `orf/converters` from checks.

**Why it hurts**: Most `except Exception` blocks live in extractors; no static analysis coverage.

**Fix**: Incrementally fix lint issues in excluded dirs; remove exclusions.

---

## Priority 4 — Low (Polish & Consistency)

### 13. Mixed-Language Documentation

- README heavy Chinese; AGENTS.md English
- Code comments mixed English + Chinese
- Error messages mixed

**Fix**: Standardize on English for code/docs; Chinese only where user-facing.

---

### 14. Env Var Naming Inconsistency

```
OPP_MCP_ALLOWED_DIRS
ORF_MCP_ALLOWED_DIRS
OL_MCP_ALLOWED_DIRS / OL_ALLOWED_DIRECTORIES / MCP_ALLOWED_DIRECTORIES
```

**Fix**: Adopt `MCP_ALLOWED_DIRECTORIES` everywhere (already documented as target).

---

### 15. Error Code Prefix Divergence

```
OPP_PATH_DENIED
ORF_ERROR
OL_INVALID_INPUT
OMNI_*
```

**Fix**: Standardize prefix convention (e.g., `MODULE_ACTION_DETAIL`).

---

### 16. No Devcontainer/Dockerfile

**Impact**: LOW | **Effort**: MEDIUM

No containerized dev environment for new contributors.

**Fix**: Add `.devcontainer/devcontainer.json` with Python 3.13, uv, pre-commit.

---

## Summary: Top 5 Fixes by ROI

| Rank | Pain Point | Impact | Effort | ROI |
|------|-----------|--------|--------|-----|
| 1 | **Restore CI** | CRITICAL | LOW-MED | ⭐⭐⭐⭐⭐ |
| 2 | **Fix doc-drift (tool counts)** | HIGH | LOW | ⭐⭐⭐⭐⭐ |
| 3 | **Extract shared omni-mcp-core** | HIGH | HIGH | ⭐⭐⭐⭐ |
| 4 | **OL PathValidator fail-closed** | MEDIUM | LOW | ⭐⭐⭐⭐ |
| 5 | **Fix punctuation.py SyntaxWarning** | LOW | TRIVIAL | ⭐⭐⭐ |

---

## Appendix: Key Files Referenced

| File | Relevance |
|------|-----------|
| `Omni_Pre_Processor/src/opp/mcp/security.py` | PathValidator copy #1 |
| `Omni_Re_Formatter/src/orf/mcp/security.py` | PathValidator copy #2 |
| `Omni_Localizer/src/ol_mcp/security.py` | PathValidator copy #3 |
| `Omni_Pre_Processor/src/opp/utils/security.py` | Intended shared validator (unreachable by OL/ORF) |
| `omni_suite/cli.py` | Pipeline orchestration copy #1 |
| `omni_mcp/orchestrator.py` | Pipeline orchestration copy #2 |
| `docs/ERROR_CODES.md` | Error code catalog with known gaps |
| `docs/ARCHITECTURE.md` | Self-documented "known warts" |
| `CHANGELOG.md` | Full bug/fix history incl. SEC-LEAK-1 |
| `ACCEPTED_GAPS.md` | Honestly documented limitations |
| `reports/PRE_EXISTING_ISSUES_ANALYSIS.md` | 14 pre-existing failures → 13 fixed |
| `scenarios/STANDARDS.md` | Agent-surface + human-quality conformance bars |
| `tests/test_no_broad_except.py` | AST meta-test for error handling hygiene |
| `tests/test_no_hardcoded_fake_llm.py` | FAKE_LLM integrity guard |
| `scripts/doc_inventory.py` | Doc-truth verifier (needs tool-count validation) |
