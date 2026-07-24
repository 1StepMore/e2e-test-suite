# Omni Suite — Project Status

> **First file to read in any new agent conversation.** Provides instant context on where the project is RIGHT NOW.
> For deep context, see the canonical docs table below (absolute paths) or the local `references/` symlinks under `.opencode/skills/omni-suite/references/` (if present in your checkout).

## Current versions (2026-06-29)

| Component | Version | Status | Path | Git State |
|---|---|---|---|---|---|
| OPP | **0.9.1** | Active | `Omni_Pre_Processor/` | own `.git/`, branch `main` |
| OL | **0.7.1** | Active | `Omni_Localizer/` | own `.git/`, branch `main` |
| ORF | **0.4.17** | Active | `Omni_Re_Formatter/` | own `.git/`, branch `main` |
| Suite | **0.4.0** | Active | `./` | branch `main` |

Sub-repos were demoted from git submodules to regular directories on 2026-06-24.
Update sub-repos with: `cd <sub-repo> && git pull origin main`.

## Test matrix health

**131 PASS, 64 SKIP, 0 FAIL** across 195 cells (verified 2026-06-29).

| Path | Cells | Pass | Skip | Fail |
|---|---|---|---|---|
| MD path | 11 inputs × 15 outputs = 165 | ~110 | ~55 | 0 |
| XLIFF path | 6 inputs × 5 outputs = 30 | ~21 | ~9 | 0 |
| **Total** | **195** | **131** | **64** | **0** |

The 64 SKIPs are intentional (e.g., MD→JSON needs code blocks, XLIFF needs skeleton, MD→SRT needs timestamps).
False-positive rate after 2026-06-29 `tests/quality_checks.py` fix: **0/200** (was 48/200).

Reproduce with: `OMNI_TEST_FAKE_LLM=1 OMNI_TEST_FAKE_PANDOC=1 .venv_ol/bin/python scripts/format_matrix_verifier.py --out-dir test_artifacts/matrix --path-filter both --parallel 8 --timeout 120`

## Working tree state

Last verified clean: 2026-06-29. Use `git status` in each sub-repo to confirm before any work.

## Recent critical fixes (last 14 days)

| Date | Module | Fix |
|---|---|---|
| 2026-06-29 | Suite | `make doctor` 7-check health gate. Matrix false-positive fix (0/200). `check_deps.sh` sub-repo check fix. `sync_version_docs.py` regex bug fix. |
| 2026-06-28 | OPP | **#28 CRITICAL** — PDF text+image positions. Fixed 552pt offset (wrong bottom-left origin assumption). |
| 2026-06-27 | OPP | **#26** — PDF zero body margin in `DEFAULT_PDF2HTML_CSS` (eliminates +12pt Y image offset). |
| 2026-06-26 | OPP | **#24** — PDF image position via `page.get_image_info()` bbox + `doc.extract_image()`. |
| 2026-06-24 | OPP/ORF | **#20/21/22** — PDF2HTML integration, skeleton `<head>`+page-break, base64 filter. |
| 2026-06-23 | OL | **E2E-83** — litellm pre-call check removed. |
| 2026-06-22 | OL/OPP/ORF | **E2E-77/78/79/80/81/82** — math/HTML shield, md2pptx pre-flight, PathValidator, CSV, docling fallback. |
| 2026-06-21 | OL | **E2E-74** — `ModelPool.translate(context=...)` supports dict/str. |
| 2026-06-21 | Suite | **`scripts/mcp_bridge.py`** — FastMCP 3.4.2 stdio bug workaround. **Required for MCP to work.** |
| 2026-06-20 | Suite | v0.2.0 — initial agent-onboarding docs, `omni-suite` CLI, 36-path matrix. |

Full history: `CHANGELOG.md` (16KB).

## Open work (top 3)

1. **PDF XLIFF blocked (intentional)** — Use MD path. See `ACCEPTED_GAPS.md`.
2. **EPUB non-determinism** — 8/8 `epub→*` cells produce different MD5 between runs. Partially fixed 2026-06-21 (`book.get_items()` sort). Root cause: `ebooklib` returns items in non-deterministic order. Affects equivalence checks.
3. **MSG output** requires commercial `aspose-email-foss` (GPLv3). Use `.eml` instead (open standard, fully supported).

For the full gap list, see `ACCEPTED_GAPS.md`.

## Bootstrap commands (run first in any new conversation)

```bash
make doctor              # 7-check health (Python ≥3.13, keys, pandoc, WeasyPrint, md2pptx, MCP)
make smoke               # Pipeline contract smoke test (pre-commit gate)
make test-quick          # pytest tests/ -m "not nightly" -q
export OMNI_TEST_FAKE_LLM=1
```

If `make doctor` fails, the pipeline won't work. Fix those issues before any translation task.

## Pointer to canonical docs

| Doc | Purpose | Size |
|---|---|---|
| `AGENTS.md` | Comprehensive agent guide (per-module cheat sheet, MCP config, env vars) | 17KB |
| `docs/agent-pipeline-guide.md` | MCP tool full parameter reference | 9KB |
| `docs/ARCHITECTURE.md` | Cross-module architecture (3-stage pipeline internals) | 25KB |
| `docs/DECISIONS.md` | Architecture Decision Records (ADRs) | 3KB |
| `docs/API_STABILITY.md` | API stability guarantees | 16KB |
| `docs/SECURITY.md` | Security model (PathValidator, MCP auth, rate limits) | 12KB |
| `docs/ERROR_CODES.md` | Exit code / error code reference | 7KB |
| `docs/RELEASE_NOTES.md` | Cross-repo release notes (monthly) | 1KB |
| `COMPATIBILITY.md` | Suite↔submodule version matrix | 2KB |
| `ACCEPTED_GAPS.md` | Known limitations and workarounds | 5KB |
| `CHANGELOG.md` | Suite changelog (last 208 lines) | 16KB |
| `.opencode/skills/omni-suite/SKILL.md` | This skill (gateway entry point) | ~250 lines |

## Submodule skills (for deep work inside one module)

- OPP: `Omni_Pre_Processor/.opencode/skills/opp-extractor/SKILL.md`
- OL: `Omni_Localizer/.opencode/skills/ol-localizer/SKILL.md`
- ORF: `Omni_Re_Formatter/.opencode/skills/orf-formatter/SKILL.md`

## Git workflow

```bash
# Working on a single sub-repo
cd Omni_Pre_Processor
git status
git pull origin main
# ... work ...
git add <files>
git commit -m "fix(OPP#29): <description>"
git push origin main

# Working on suite-level
cd /mnt/d/贯维/Omni_Suite
git status
git pull origin main
# ... work ...
git add <files>
git commit -m "feat(suite): <description>"
git push origin main
```

`scripts/setup_dev.sh` asserts submodule versions match `COMPATIBILITY.md` —
if you bump a sub-repo version, also update the matrix.

## Recent activity

Last Suite commit: see `git log -1` (suite level).
Last OPP commit: see `git -C Omni_Pre_Processor log -1`.
Last OL commit: see `git -C Omni_Localizer log -1`.
Last ORF commit: see `git -C Omni_Re_Reformatter log -1`.
