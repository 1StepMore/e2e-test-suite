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

## Round 9 Results — Tier 2 SUCCESS

### Tier 2 first run (after dispatch wiring verified)

```
$ omo_loop.py --tier 2 --input "爱上海尔_第二章_全球创牌 - E2E测试专用.docx"
→ delegates to tests/e2e_runner.py
→ runs 4 paths: xliff_cli, xliff_mcp, md_cli, md_mcp
```

**Outcome: 5 iterations required to converge.**

| Iteration | Critical issues | Detail |
|---|---|---|
| v1 | 2 | Bug 1 (xliff_cli .zip rejected) + Bug 2 (xliff_mcp await on sync tool) + Bug 0 (NameError on `start`) |
| v2 | 2 | Bug 0 fixed (added `start = time.time()`). Bugs 1+2 still open |
| v3 | 2 | Bug 1 fixed (ORF accepts .zip). Bug 2 partial fix (removed await on translate_xliff but kept on translate_md_text) |
| v4 | 1 | Bug 2 partially fixed — but `translate_md_text` IS async, needs await. xliff_mcp still fails |
| v5 | **0** | Made `translate_xliff` truly async (matched translate_md_text), all paths PASS |

### Bugs caught

| # | Severity | Location | Root cause | Fix |
|---|---|---|---|---|
| 0 | High | `tests/e2e_runner.py:652` | `start = time.time()` referenced but never defined in main() | Added `start = time.time()` before path loop |
| 1 | High | `Omni_Re_Formatter/src/orf/cli.py:764` (FIX-#8) | Round 5 guard rejected `.zip` skeleton; OPP packages DOCX as skeleton.zip — legitimate skeleton format | Extended `_FORMAT_EXT` check to also accept `.zip` for docx/pptx/epub |
| 2 | Critical | `Omni_Localizer/src/ol_mcp/tools.py:489` (`translate_xliff`) | Sync function using `asyncio.run()` internally — fails inside event loop | Made `async def`, await the pool.translate() directly |
| 3 | Medium | `tests/test_e2e_real_llm.py:426,441` | Await pattern inconsistent across the two MCP translate functions | Aligned — both async, both await |

### Commits

| Repo | SHA | Summary |
|---|---|---|
| main | `510d7a7` | fix(tests): translate_xliff/translate_md_text await fix |
| main | `a9e43c6` | fix(tests): e2e_runner.py NameError on `start` |
| Omni_Localizer | `eea657f` | fix(ol): translate_xliff async + NameError + Tier 2 |
| Omni_Re_Formatter | `190ea6b` | fix(orf): FIX-#8 extension — accept .zip skeleton |
| Omni_Re_Formatter | `f6ce509` | test(orf): 3 regression tests for .zip / cross-format |

### Final Tier 2 results

```
xliff_cli: PASS (102.3s) — produces 442KB DOCX
xliff_mcp: PASS (277.8s) — produces 442KB DOCX
md_cli:   PASS (14.4s) — produces 12KB DOCX (text-only, images separate)
md_mcp:   PASS (15.7s) — produces 12KB DOCX (text-only, images separate)

Total issues: 12 minor (image count, LQA quality observations — non-blocking)
```

### Tests added
- 3 new in `Omni_Re_Formatter/tests/test_apply_xliff_format_validation.py`
  covering `.zip` skeleton accepted + pptx/html cross-format still rejected.

### Verification
- All 4 paths PASS
- Tier 1 OMO still GREEN (162.9s, 8/8)
- 5 commits shipped
- All existing tests still pass

## Impact

Tier 2 was the **first time** the round 7 dispatch infrastructure was
exercised end-to-end. It caught 4 real bugs that narrow Tier 1 would
never have surfaced:

1. **e2e_runner.py:652 NameError** — bug existed for who knows how long;
   Tier 2 was the first to invoke it.
2. **FIX-#8 too strict** — round 5 was correct in principle (fail-fast
   cross-format) but missed the OPP `skeleton.zip` case. Round 9 extends it.
3. **`translate_xliff` sync/async mismatch** — pre-existing design
   defect. Made the function async to match `translate_md_text`.
4. **await inconsistency in test helper** — root cause was the sync
   wrapper above; fixing #3 fixed this naturally.

The dispatch wiring (round 7) + API key guard (round 8) + Tier 2 bug
discovery (round 9) combine into a working comprehensive self-driven
loop for the first time.

## Recommended Next Round (round 10)

Round 10 candidates (in priority order):

1. **Tier 3** — format matrix (10 formats × 2 langs via MD).
   Will surface format-specific OPP/ORF bugs that Tier 2's single
   DOCX cannot.
2. **MCP integration tests** for OPP/ORF (Tier 5) — round 7
   infrastructure also supports this but never exercised.
3. **#12 try_safe_fix** — extend OMO's auto-recovery from 1 fix
   (clear_opp_cache) to other failure modes.
4. **#4 en→zh long-tail** — fix the 2028-unit doc slowness with
   prefer-OPENCODE_GO for large docs.

Tier 3 is the most impactful next step for bug discovery.
