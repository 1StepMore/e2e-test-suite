# Fix Plan — Round 7 (2026-06-17) — REUSE-BASED REDESIGN

## Critical Course Correction

The first version of this plan (commit `02634f1`) proposed a 350-line
**rewrite** of `omo_loop.py` adding tier modes. **This was wrong.**

User feedback: there is existing comprehensive infrastructure. Don't
redesign — reuse:

| Asset | Lines | What it already does |
|---|---|---|
| `tests/e2e_runner.py` | **801** | Runs all **4 paths** (xliff_cli / xliff_mcp / md_cli / md_mcp) with real LLM + LQA + image positioning checks. The "老规矩" (old rule). |
| `run_test.sh` | **212** | `--module opp/ol/orf` flags to run a single module's pipeline. Module-only self-driven runs already wired. |
| `scripts/omo_loop.py` | 777 | 8-gate convergence loop (Q1–Q8) + fix retries + cycle reports. The orchestrator. |
| `scripts/phase1_runner.py` | 621 | Format matrix P0/P1/P2/P3 (30 cases). Used for batch regression. |

**Total existing infrastructure: ~2400 lines covering exactly the
"comprehensive self-driven loop" the user described.**

The first plan's "350-line rewrite" would have duplicated 4-path logic
that's already in `e2e_runner.py`. **Abandoned.**

## Round 7 Goal — Wrap, Don't Rewrite

Make `omo_loop.py`'s `--tier` flag dispatch to the existing assets:

| Tier | What runs | Asset reused |
|---|---|---|
| 1 (default) | Single doc, XLIFF CLI, gate convergence | `scripts/omo_loop.py` existing logic (unchanged) |
| 2 | All 4 paths on a single doc with real LLM + LQA | **delegate to `tests/e2e_runner.py`** |
| 3 | Format matrix (10 formats × 2 langs via MD) | **delegate to `scripts/phase1_runner.py`** |
| 4 | XLIFF backfill matrix (docx + pptx × 2 langs) | **delegate to `scripts/phase1_runner.py`** |
| 5 | Module-only runs (opp / ol / orf) | **delegate to `run_test.sh --module X`** |

**Net code change: ~80 lines** (CLI args + thin dispatch wrappers).

## Issue Inventory

### User-flagged this round

| ID | Issue | Sev | Effort | Action |
|---|---|---|---|---|
| **NEW-A** | **OMO loop too narrow — covers 0.28% of cell-space** | **High** | **S** | **FIX: add `--tier` to omo_loop.py that delegates to existing assets** |
| NEW-B | `e2e_runner.py` hardcodes `HAIER_DOCX` (no `--input`) | Med | XS | FIX: add `--input`, `--source-lang`, `--target-lang` |
| NEW-C | `omo_loop.py` doesn't expose tier selection | Med | XS | FIX: add `--tier {1,2,3,4,5}` with dispatch table |
| NEW-D | `phase1_runner.py` always calls real LLM | Low | XS | FIX: add `--mock-llm` flag |

### From round 6 backlog (still relevant)

| ID | Issue | Sev | Action this round |
|---|---|---|---|
| #24 | API keys hardcoded in `local.yaml`/`default.yaml` | High | Defer (security review needed) |
| #12 | `try_safe_fix` only does clear_opp_cache | Med | Defer (low impact this round) |
| #15 | MCP `apply_xliff` format enum | Med | Defer (MCP integration design) |

## Round 7 Execution Plan

1. **Plan file (this file)** — done (overwriting round-7 v1).
2. **Commit** — round 7 v2 plan.
3. **Extend `tests/e2e_runner.py`** (XS):
   - Add `--input` (default: HAIER_DOCX)
   - Add `--source-lang` (default: zh)
   - Add `--target-lang` (default: en)
   - Backward compatible (existing behavior unchanged if no flags)
4. **Add `--tier` dispatch to `omo_loop.py`** (S):
   - `--tier 1` (default): existing logic, no change
   - `--tier 2`: invoke `tests/e2e_runner.py` with `--input`/`--source-lang`/`--target-lang`
   - `--tier 3`: invoke `scripts/phase1_runner.py` (P1 tier — 10 formats × 2 langs)
   - `--tier 4`: invoke `scripts/phase1_runner.py` (P2 tier — docx+pptx × 2 langs XLIFF)
   - `--tier 5`: invoke `run_test.sh --module opp/ol/orf` in sequence
   - Each tier wraps the asset's invocation and aggregates pass/fail into
     omo_loop's existing gate system.
5. **Add tests**:
   - `e2e_runner.py` `--input` flag accepts custom doc
   - `omo_loop.py` `--tier 1` is identical to default behavior
   - `omo_loop.py` `--tier 2` invokes e2e_runner.py with correct args
6. **Commit round 7** as separate commits.
7. **Run expanded loop**:
   - Tier 1 (sanity check) — 5 min
   - Tier 2 (4 paths) — 20-40 min via e2e_runner.py
8. **Update plan** with results.

## Verification Targets

- All 39 existing tests still pass.
- New round 7 tests pass (3-4 new).
- Tier 1 still converges in ≤ 2 cycles (regression check).
- Tier 2 invokes e2e_runner.py with all 4 paths and produces a comparison report.
- Existing e2e_runner.py behavior unchanged when no new flags passed.

## What This Round is NOT

- Not redesigning omo_loop.py from scratch.
- Not reimplementing the 4-path runner (already exists).
- Not touching phase1_runner's matrix generation.
- Not adding new gates or convergence logic.

The point of round 7 is **dispatch wiring**, not **logic invention**.

## Risk

- e2e_runner.py's hardcoded `_print_issues` output format might not
  flow cleanly into omo_loop's gate system. Mitigation: parse e2e_runner's
  `comparison_report.md` (its final output) for pass/fail aggregation
  rather than instrumenting its internals.
- Tier 3 (phase1 P1) and Tier 5 (run_test.sh --module) have no existing
  pass/fail metric. Mitigation: for round 7, treat them as fire-and-log;
  the gate system only kicks in for Tier 1 and Tier 2 where artifacts
  are predictable.
",
  "filePath": "/mnt/d/贯维/Omni_Suite/.omo/plans/2026-06-17-fix-plan-round-7.md"
}