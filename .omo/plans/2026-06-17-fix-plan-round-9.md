# Fix Plan — Round 9 (2026-06-17) — First Full Tier 2 Run

## Goal

Execute the round 7 tier-dispatch infrastructure end-to-end for the
first time: `omo_loop.py --tier 2` → `tests/e2e_runner.py` → all 4
paths (xliff_cli, xliff_mcp, md_cli, md_mcp) on real LLM.

## Why This Round

Round 7 (commit `ff3f9fe`) wired the dispatch. Round 8 (commit
`6dfeb33`) hardened API key handling. Both rounds shipped without
**verifying** that Tier 2 actually works end-to-end. The dispatch was
tested only with `subprocess.run` mocks. This round exercises the
real path.

Expected outcomes:
1. **Best case**: all 4 paths pass cleanly, confirming the
   round 7+8 wiring is correct.
2. **Realistic case**: 1-2 paths fail with cross-module bugs
   (OPP↔OL↔ORF integration issues that narrow Tier 1 misses).
3. **Worst case**: Tier 2 dispatch has a real wiring bug (env vars,
   PYTHONPATH, subprocess args) that requires a fix.

User intent: catch OPP/OL/ORF cross-module bugs. The 0.28% → 4×
expansion (4 paths instead of 1) is specifically designed to find
issues that the single-path Tier 1 cannot.

## Scope

### Step 1 — Plan + commit (XS)
- Plan file
- Commit

### Step 2 — Pre-flight smoke (S)
Verify `tests/e2e_runner.py` runs end-to-end before committing to the
20-40 min Tier 2 run. Specifically:
- pandoc available (already confirmed: `/home/renanzai/.local/bin/pandoc`)
- Haier DOCX exists (already confirmed)
- BAIDU_API_KEY set in `Omni_Localizer/.env` (already confirmed)
- `tests/e2e_runner.py --help` parses (already confirmed in round 7)
- `OL_ALLOW_HARDCODED_KEYS=1` set (needed because local.yaml has real keys)

If pre-flight fails: surface clearly and stop.

### Step 3 — Run Tier 2 (20-40 min)

```bash
cd /mnt/d/贯维/Omni_Suite
OL_ALLOW_HARDCODED_KEYS=1 .venv_ol/bin/python scripts/omo_loop.py \
    --max-cycles 1 --consecutive-green 1 \
    --tier 2 \
    --input "爱上海尔_第二章_全球创牌 - E2E测试专用.docx" \
    --source-lang zh --target-lang en
```

This invokes `tests/e2e_runner.py` (per round 7 dispatch). e2e_runner:
1. Validates source DOCX (paragraphs, images)
2. Runs `xliff_cli` (CLI subprocess, XLIFF intermediate)
3. Runs `xliff_mcp` (MCP subprocess, XLIFF intermediate)
4. Runs `md_cli` (CLI subprocess, MD intermediate; requires pandoc)
5. Runs `md_mcp` (MCP subprocess, MD intermediate; requires pandoc)
6. Writes `comparison_report.md` with per-path pass/fail + issues

Expected: 4 path reports under `test_artifacts/e2e_runs/<TIMESTAMP>/`.

### Step 4 — Analyze results (S)
Read `comparison_report.md` + per-path issue lists. Categorize:

| Category | Action |
|---|---|
| **CRITICAL open** (translation broken, output missing) | Fix this round |
| MINOR open (LQA score borderline, glossary mismatch) | Document, defer |
| FIXED during run (auto-recovered) | Note in plan |
| All clean | Commit results, no fixes needed |

### Step 5 — Fix critical bugs (M, conditional)
If CRITICAL issues surface: fix root cause, write regression test,
commit. Loop step 3 again if any fix changes path behavior.

### Step 6 — Update plan (XS)
Append results, deferred backlog, recommended next steps.

## Risk

- **API cost**: free-tier (Baichuan/Qianfan + Zhipu + Agnes + NVIDIA NIM
  + OpenCode Go), no billable risk. Round 7/8 verification confirmed
  Baichuan is the primary.
- **Runtime**: 20-40 min real LLM, sequential paths, may exceed 40 min
  if rate-limit retries fire.
- **MCP server start failures**: MCP paths require the MCP servers to
  start cleanly. Pre-existing setup may have residual state. Mitigation:
  log capture during the run will surface any startup errors.

## Verification Targets

- All 4 paths complete (no infinite retry / hang)
- `comparison_report.md` written with per-path results
- Tier 1 OMO loop still passes (regression check)
- 58 OL tests still pass

## What This Round is NOT

- Not modifying Tier 3/4/5 dispatch (only Tier 2 this round)
- Not adding new tests (focus is execution + bug discovery)
- Not changing any OPP/OL/ORF code unless a critical bug is found

## Recommended Next Round (round 10, conditional)

If Tier 2 finds 0 critical bugs: jump to Tier 3 (10 formats × 2 langs
via MD) for even broader coverage.
If Tier 2 finds 1-3 critical bugs: fix them, re-run, then Tier 3.
If Tier 2 fails (dispatch wiring): fix dispatch, re-run.