# Omni Suite — Project Status

> **First file to read in any new agent conversation.** Provides instant context on where the project is RIGHT NOW.
> For deep context, see the canonical docs table below (absolute paths) or the local `references/` symlinks under `.opencode/skills/omni-suite/references/` (if present in your checkout).

## Current versions (2026-10-26)

| Component | Version | Status | Path | Git State |
|---|---|---|---|---|---|
| OPP | **0.10.0** | Active | `Omni_Pre_Processor/` | own `.git/`, branch `main` |
| OL | **0.7.1** | Active | `Omni_Localizer/` | own `.git/`, branch `main` |
| ORF | **0.5.0** | Active | `Omni_Re_Formatter/` | own `.git/`, branch `main` |
| Suite | **0.5.0** | Active | `./` | branch `main` |

Sub-repos were demoted from git submodules to regular directories on 2026-06-24.
Update sub-repos with: `cd <sub-repo> && git pull origin main`.

Version source of truth is each repo's `pyproject.toml` (`[project].version`) — only the
suite root also carries a `VERSION` file. The suite↔sub-repo pinning lives in
`COMPATIBILITY.md`; `scripts/sync_version_docs.py --check` asserts doc↔pyproject agreement.

## Current verdict (2026-11-06)

Full-library baseline run `validation-runs/20261106-061539/report.md`（gitignored 本地产物，交付 zip 内含同源 report）
(`--repo all`, 138 scenarios loaded across the suite + 3 sub-repo libraries; `latest-full.txt` anchor,
first written by this run):

**127 passed / 0 failed / 0 invalid / 6 unconfigured (objective env: TM network, OCR, MSG, ipynb,
youtube) / 4 recovered / 1 known-gap** — per-repo report card fully anchored for the first time
(the `run_meta.repos` collection gap was fixed the same day):

| Repo | Version | SHA | Scenarios | Passed | Failed |
|---|---|---|---|---|---|
| ol | 0.7.1 | 37bbf398 | 34 | 33 | 0 |
| opp | 0.10.0 | 2e2c9dd0 | 31 | 27 | 0 |
| orf | 0.5.0 | 8a99977d | 47 | 44 | 0 |
| suite | 0.5.0 | 0b4cb63c | 26 | 23 | 0 |

Both quality gates (T13-01 `#lqa-threshold`, T13-02 `#drawing-count`) are **closed** and enforced
directly at the literal bars (`ACCEPTED_GAPS.md`; real-model quality baseline:
`docs/dev/quality-baseline.md`). The hermetic tier-1 sweep earlier the same day
(run `20261106-033215`) shows the same 0-failed picture (111 passed). A first full-library
attempt (`20261106-045637`) had 2 failures, both classified away from regression per the
failure-classification protocol: an epub judge truncation (free-tier `finish_reason=length`
fail-closed degradation — rerun self-healed) and a local env override shadowing the engine's
allowlist defaulting (operator error, corrected).

## Test matrix health

**131 PASS, 64 SKIP, 0 FAIL** across 195 cells (last full matrix run 2026-06-29).

These figures measure conversion plumbing, not translation quality: the fixtures are
single-sentence text and the run uses a fake-LLM echo, so PASS means the path produced
a non-empty artifact — it does not assert translation quality or artifact usability.

| Path | Cells | Pass | Skip | Fail |
|---|---|---|---|---|
| MD path | 11 inputs × 15 outputs = 165 | ~110 | ~55 | 0 |
| XLIFF path | 6 inputs × 5 outputs = 30 | ~21 | ~9 | 0 |
| **Total** | **195** | **131** | **64** | **0** |

The 64 SKIPs are intentional (e.g., MD→JSON needs code blocks, XLIFF needs skeleton, MD→SRT needs timestamps).
False-positive rate after 2026-06-29 `tests/quality_checks.py` fix: **0/200** (was 48/200).

Reproduce with (needs the Linux venv — see "Platform notes" below):

```bash
OMNI_TEST_FAKE_LLM=1 OMNI_TEST_FAKE_PANDOC=1 .venv_ol/bin/python scripts/format_matrix_verifier.py \
    --out-dir test_artifacts/matrix --path-filter both --parallel 8 --timeout 120
```

> The matrix number above is a **snapshot** whose last executed run predates 2026-09-17;
> it is re-derived only by running the command above. Do not quote it as fresh evidence.

**Validation framework**: alongside the matrix, the agent-agnostic validation framework
(`scripts/validation/`, scenario library in `scenarios/` with `scenarios/STANDARDS.md`,
director loop in `docs/dev/validation-director-loop.md`) runs real scenarios against the
shipped surface — see suite `AGENTS.md` → "How to validate".

Derived library size: **121 scenario yaml files** (tier-1 = 109, tier-2 = 11, tier-3 = 1; the
two known-gap twins were removed 2026-11-06 when both literal bars held). Latest full-library
baseline: `validation-runs/20261106-061539/` — 127 passed / 0 failed (see "Current verdict"
above); the previous recorded sweep `20260915-014100` predates the 2026-10 scenario-library
expansion and is kept as history only.

`validation-runs/latest.txt` points at the newest run of **any** scope, which may be a
single-scenario run — for the full sweep read `validation-runs/latest-full.txt` (written only
by full-library runs since 2026-11-06) or the timestamped directory.

## Working tree state

Synced 2026-11-06: all four repos' `main` match `origin/main` (suite #247, `Omni_Localizer`#170,
`Omni_Re_Formatter`#78, `Omni_Pre_Processor`#115 merged). Residual local-only dirt (uncommitted,
pre-existing, none of it from the 2026-11-06 batch): suite `.github/workflows/lint.yml` (+ the
three untracked working docs `2026-11-05/06-*.md`), `Omni_Pre_Processor` `scripts/coverage_matrix.py`.
Always run `git status` in each repo before any work.

## Recent fixes

| Date | Module | Fix |
|---|---|---|
| 2026-11-06 | Suite | **Goal batch closed**: T13-01 + T13-02 gates formally closed (#244), known-gap twins removed (123→121), `run_meta` per-repo anchoring fixed (`_dirs_to_repo_keys`), first `latest-full.txt` written, full-library baseline 127/0, real-model quality baseline doc. PR #247. |
| 2026-11-06 | OL | **T13-02 root cause** — marker-form completeness + unshield-first order + level2 dual-format placeholders + post-unshield image-ref self-check (#244; PR #170; OL suite 1890 passed). |
| 2026-11-06 | ORF | EPUB byte determinism — content-hash `SOURCE_DATE_EPOCH` + uuid5 `dc:identifier` (PR #78; two runs in different dirs → identical sha256). |
| 2026-11-06 | OPP | EPUB image-item ordering determinism in `_parse_epub` (PR #115). |
| 2026-09-17 | Suite | Health-audit round: `99-Tools/` gitignored; dead code removed from `scripts/omo_loop.py`; `doc_inventory.py` Windows interpreter fix; ruff pinned 0.15.11 across pre-commit/CI/pyproject; mypy scope widened to `omni_metrics omni_suite omni_mcp` (23 files, clean); `setup_dev.ps1` native-Windows bootstrap; contract smoke test platform-aware interpreter. |
| 2026-09-17 | OL | **T13-01/T13-02** — judge score renormalization (`_remap_llm_fields` omits absent criteria instead of zero-filling) + judge prompt covers all `RUBRIC_WEIGHTS` dimensions + `is_complete()`/`repair()` match key **or** original value (fixes duplicated image refs). Pending tier-2 re-verification. |
| 2026-09-15 | Suite | Validation run record `20260915-014100` + loop-log 2026-09-14 clear-out; #16 (stale ORF defect pinner retired) / #17 (validation-runs uploaded on structural job) qualified. |
| 2026-09-14 | Suite | `setup-uv` pinned to 0.11.8 + workspace lock freshness asserted via `uv sync --locked` in CI. |
| 2026-09-14 | Suite | CI clones module repos from the authoritative backup org (#14). |
| 2026-09-13 | Suite | Pipeline output survival + `--resume-from` checkpoint; fail-closed path security, sanitized errors, async progress, run manifest; execution-backed coverage + scenario level lint; module-doc claim drift gate. |
| 2026-06-29 | Suite | `make doctor` 7-check health gate. Matrix false-positive fix (0/200). `check_deps.sh` sub-repo check fix. `sync_version_docs.py` regex bug fix. |
| 2026-06-28 | OPP | **#28 CRITICAL** — PDF text+image positions. Fixed 552pt offset (wrong bottom-left origin assumption). |
| 2026-06-27 | OPP | **#26** — PDF zero body margin in `DEFAULT_PDF2HTML_CSS` (eliminates +12pt Y image offset). |
| 2026-06-26 | OPP | **#24** — PDF image position via `page.get_image_info()` bbox + `doc.extract_image()`. |
| 2026-06-24 | OPP/ORF | **#20/21/22** — PDF2HTML integration, skeleton `<head>`+page-break, base64 filter. |
| 2026-06-23 | OL | **E2E-83** — litellm pre-call check removed. |
| 2026-06-22 | OL/OPP/ORF | **E2E-77/78/79/80/81/82** — math/HTML shield, md2pptx pre-flight, PathValidator, CSV, docling fallback. |
| 2026-06-21 | OL | **E2E-74** — `ModelPool.translate(context=...)` supports dict/str. |

Full history: `CHANGELOG.md` (last 283 lines).

## Open work (top 3)

1. **PathValidator is implemented four times** — `Omni_Pre_Processor/src/opp/mcp/security.py`,
   `Omni_Localizer/src/ol_mcp/security.py`, `Omni_Re_Formatter/src/orf/mcp/security.py`, plus the
   functional `Omni_Pre_Processor/src/opp/utils/security.py`. Each carries its own
   `ALLOWED_EXTENSIONS`, so a security fix does not propagate. Unifying them needs an ADR first.
   (Update 2026-11-06: `docs/adr/0007` Phase 1 + 2A have landed — the parity gate and the shared
   `omni_security` package exist; what remains is Phase 2B: the three sub-repo validators as thin
   wrappers + the four CLI-surface residual copies.)
2. ~~T13-01 / T13-02 await tier-2 re-verification~~ — **CLOSED 2026-11-06**: both literal bars are
   enforced directly and hold (nightly 2026-11-01..04 for T13-01; local tier-2 re-verification
   `20261106-012511` + the 2026-11-06 full-library baseline for T13-02; e2e-test-suite#244).
3. ~~EPUB non-determinism~~ — **largely closed 2026-11-06**: OPP image ordering + ORF byte-deterministic
   EPUB production (`Omni_Re_Formatter`#78); matrix-level equivalence double-run re-measurement lands
   with the P1-B batch.

For the full gap list, see `ACCEPTED_GAPS.md`. PDF XLIFF is intentionally blocked (use the MD
path); MSG output needs commercial `aspose-email-foss` (GPLv3) — use `.eml` instead.

## Platform notes (read before running anything)

`.venv/`, `.venv_ol/` and `.venv312/` in this checkout are **Linux (uv) virtualenvs** — their
`pyvenv.cfg` points at a Linux CPython and `.venv_ol/bin/python` is a Linux ELF binary. CI and
WSL depend on them, so **never delete or recreate them**. On native Windows they cannot be
executed (`OSError: [WinError 1920]`).

| Environment | Entry point | Interpreter |
|---|---|---|
| Linux / WSL / CI | `bash scripts/setup_dev.sh` | `.venv_ol/bin/python` |
| Native Windows | `powershell -ExecutionPolicy Bypass -File scripts/setup_dev.ps1` | `.venv_win\Scripts\python.exe` |

## Bootstrap commands (run first in any new conversation)

```bash
make doctor              # 7-check health (Python >=3.13, keys, pandoc, WeasyPrint, md2pptx, MCP)
make smoke               # Pipeline contract smoke test (pre-commit gate)
make test-quick          # pytest tests/ -m "not nightly" -q
export OMNI_TEST_FAKE_LLM=1
```

If `make doctor` fails, the pipeline won't work. Fix those issues before any translation task.
On native Windows, `make` targets need a POSIX shell — prefer the explicit commands in
`SETUP.md` / `scripts/setup_dev.ps1`.

## Pointer to canonical docs

| Doc | Purpose | Size |
|---|---|---|
| `CONTEXT.md` | Shared glossary / Ubiquitous Language of pipeline terms (suites, modules, channels, artifacts, MCP) | 292 lines |
| `docs/PRD.md` | Retrospective baseline PRD — single source of truth for requirements (vision, user stories, scope, acceptance criteria) | 61 lines |
| `AGENTS.md` | Comprehensive agent guide (per-module cheat sheet, MCP config, env vars) | 16KB |
| `docs/agent-pipeline-guide.md` | MCP server/tool inventory + namespacing (names/counts); per-tool params in each module's `docs/API.md` | 13KB |
| `docs/ARCHITECTURE.md` | Cross-module architecture (3-stage pipeline internals) | 25KB |
| `docs/DECISIONS.md` | Architecture Decision Records (ADRs) | 1KB |
| `docs/API_STABILITY.md` | API stability guarantees | 16KB |
| `docs/SECURITY.md` | Security model (PathValidator, MCP auth, rate limits) | 12KB |
| `docs/ERROR_CODES.md` | Exit code / error code reference | 19KB |
| `docs/RELEASE_NOTES.md` | Cross-repo release notes (AUTO-GENERATED, full history) | 66116 bytes (`wc -c`, 2026-11-07) |
| `COMPATIBILITY.md` | Suite↔sub-repo version matrix | 2KB |
| `ACCEPTED_GAPS.md` | Known limitations and workarounds | 9KB |
| `CHANGELOG.md` | Suite changelog (last 283 lines) | 27KB |
| `.opencode/skills/omni-suite/SKILL.md` | This skill (gateway entry point) | 288 lines |

## Sub-repo skills (for deep work inside one module)

- OPP: `Omni_Pre_Processor/src/opp_agent/SKILL.md` (OpenCode) / `Omni_Pre_Processor/src/opp_hermes/SKILL.md` (Hermes)
- OL: `Omni_Localizer/src/.opencode/skills/ol-localizer/SKILL.md`
- ORF: `Omni_Re_Formatter/src/.opencode/skills/orf-formatter/SKILL.md`

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

# Working on suite-level (same commands in any shell; only the path spelling differs)
#   WSL / Linux : cd /mnt/d/贯维/Omni_Suite
#   Windows     : cd D:\贯维\Omni_Suite
cd D:\贯维\Omni_Suite
git status
git pull origin main
# ... work ...
git add <files>
git commit -m "feat(suite): <description>"
git push origin main
```

`scripts/setup_dev.sh` (and `scripts/setup_dev.ps1` on Windows) asserts submodule versions
match `COMPATIBILITY.md` — if you bump a sub-repo version, also update the matrix.

## Recent activity

```bash
git log -1                          # suite level
git -C Omni_Pre_Processor log -1
git -C Omni_Localizer log -1
git -C Omni_Re_Formatter log -1
```

Suite HEAD as of 2026-09-17: `a2c8b6d` (2026-09-15, loop-log clear-out).
