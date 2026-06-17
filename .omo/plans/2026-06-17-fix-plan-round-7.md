# Fix Plan — Round 7 (2026-06-17)

## User's Round 7 Directives

The user observed that the OMO loop in round 5/6 was unusually fast
(161-276s per cycle, 2 cycles to converge) and suspected the loop is
narrow — only testing DOCX on the XLIFF CLI path with the full
pipeline, missing the other 3 paths (md-cli, mcp-md, mcp-xliff), other
10 input formats, and independent module runs.

**Confirmed by parallel `explore` agents (rounds bg_82ca049d,
bg_f69dea0d)**:

- `omo_loop.py` exercises **0.28%** of the cell-space
  (11 formats × 4 paths × 2 transports × 2 langs × 2 intermediates
  = 352 cells)
- Adding `phase1_runner.py` + `tests/test_e2e_*.py` brings it to ~10%
- Zero MCP coverage in `phase1_runner.py`'s `build_matrix()`
- Zero non-DOCX input testing on the XLIFF backfill path
- Zero OPP-only or ORF-only automated loops
- `phase1_runner.py` has no `--mock-llm` (always real LLM = slow + costly)
- `omo_loop.py` is hardcoded to zh→en (no en→zh in practice)
- Neither script has `--glossary` support

## Goal

Expand the self-driven loop to cover all 3 modules, all 4 paths, and
broad format matrix. Start with Tier 1 + Tier 2 (DOCX core matrix
on both paths × both languages) — Tier 3/4/5 (MCP, format matrix,
independent modules) are follow-on rounds.

## Issue Inventory

### User-flagged this round (NEW)

| ID | Issue | Sev | Effort | Action |
|---|---|---|---|---|
| **NEW-A** | **OMO loop too narrow — covers 0.28% of cell-space** | **High** | **M** | **FIX: add `--tier=1/2` modes to omo_loop.py (this round), Tier 3/4/5 in round 8** |
| NEW-B | `phase1_runner.py` always calls real LLM (no `--mock-llm`) | Med | XS | FIX: add flag, propagates `OMNI_TEST_FAKE_LLM=1` |
| NEW-C | `omo_loop.py` hardcoded zh→en (en→zh never exercised) | Med | XS | FIX: add `--input` flag and use existing fixtures |
| NEW-D | Neither script has `--glossary` support | Med | XS | FIX: add flag, pass to OL via `OMNI_GLOSSARY_PATH` env |
| NEW-E | `XLIFF_OUTPUTS_BY_INPUT` missing epub/html | Low | XS | FIX: add entries (only if ORF supports backfill for these) |

### From round 6 backlog (still relevant)

| ID | Issue | Sev | Effort | Action this round |
|---|---|---|---|---|
| #12 | `try_safe_fix` only does clear_opp_cache | Med | M | Defer to round 8 (low priority) |
| #15 | MCP `apply_xliff` format enum | Med | S | Defer to round 8 (need MCP integration design) |
| #24 | API keys hardcoded in `local.yaml`/`default.yaml` | High | L | Defer to round 8 (security review needed) |

## Round 7 Execution Plan

1. **Plan file (this file)** — done.
2. **Commit** — round 7 plan.
3. **Apply Tier 1+2 expansion** to `omo_loop.py`:
   - Add `--tier {1,2,3,4,5}` flag (only 1 and 2 implemented this round;
     3/4/5 raise `NotImplementedError` with clear message)
   - Add `--input` flag to override the default fixture
   - Add `--target-format {md,xliff,both}` to choose intermediate
   - Add `--glossary` flag (passed to `OMNI_GLOSSARY_PATH`)
   - Add `--source-lang` and `--target-lang` (already exist, but
     document with en→zh in help text)
   - Add `en→zh` fixture path support
4. **Add `--mock-llm` to `phase1_runner.py`**
5. **Add tests**:
   - omo_loop `--tier=2` produces 4 cases
   - omo_loop `--target-format=md` calls MD path
   - omo_loop `--glossary` propagates env var
6. **Commit round 7** as separate commits.
7. **Run expanded loop**:
   - Tier 1 (default, OMO regression) — 5 min
   - Tier 2 (DOCX core matrix) — 30 min
   - Document any new findings.
8. **Update plan** with results.

## What Comes After (round 8+)

| Round | Scope |
|---|---|
| 8 | Tier 3 (format matrix, 20 cases via MD) + Tier 5 (MCP path, 4 cases) + #24 API key security + #12 try_safe_fix |
| 9 | Tier 4 (XLIFF backfill matrix, 4 cases) + #15 MCP format enum + OPP-only/ORF-only loops |
| 10 | en→zh coverage + glossary pass-through + cross-transport scenarios |

## Verification Targets

- All existing tests pass.
- New round 7 tests pass.
- Tier 1 still converges in ≤ 2 cycles (regression).
- Tier 2 runs 4 cases (docx × 2 paths × 2 langs), converges per-case.
- New `--target-format=md` flag actually calls MD path (verified by
  `run_pipeline.py` call).
- New `--input` flag accepts a Path and uses it instead of default.

## Risk

- Tier 2 takes ~30 min real-time. Acceptable for "comprehensive" loop.
- Changing the `_run_pipeline` call signature to add `--target-format`
  is a wider change. Mitigation: keep Tier 1 behavior identical when
  `--target-format` defaults to current behavior (xliff).
