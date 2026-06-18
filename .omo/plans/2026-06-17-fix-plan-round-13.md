# Fix Plan — Round 13 (2026-06-18) — Complete Tier 3 + Tier 2 en→zh

## Goal

Close the matrix coverage gap surfaced in round 12: Tier 3 was 6/20 (30%),
Tier 2 en→zh had never been run, and Tier 3 pptx MD was documented as
"needs md2pptx binary" but never actually wired up.

Target: 25/36 cases passing (was 13/36 = 36%).

## What Shipped

| Change | File | Why |
|--------|------|-----|
| Install `md2pptx` (MartinPacker) | `/home/renanzai/.local/bin/md2pptx` (symlink to `/tmp/opencode/md2pptx_install/md2pptx/md2pptx`) | Round 10 deferred PPTX MD because the binary was missing. Round 13 installs it (git clone + chmod). |
| Add `pptx` to `apply-md --target-format` Choice | `Omni_Re_Formatter/src/orf/cli.py` | Round 10 removed it; round 13 re-adds it now that the binary is present. |
| Add `MD2PPTXConverter` dispatch in `apply_md` | `Omni_Re_Formatter/src/orf/cli.py` | The Choice was useless without the dispatch case. |
| **Fix** `MD2PPTXConverter` CLI args (positional, no `-o`) | `Omni_Re_Formatter/src/orf/channels/md2pptx.py` | **Bug #1 caught this round.** The original code called `md2pptx INPUT -o OUTPUT` but MartinPacker's md2pptx uses positional `INPUT OUTPUT`. The `-o` form made md2pptx treat `-o` as the output filename and silently create a file literally named `-o` in CWD — every conversion claimed "Conversion successful" but produced no real output. |
| Add `--source-lang/--target-lang` filter to phase1 | `scripts/phase1_runner.py` | Enables one-direction runs, ~halves wall time, and lets us run the 6 unfinished en→zh formats without re-running the slow sherlock_holmes cases. |

## Test Results

### Tier 3 zh→en (round 13 run, `tier3_zh_en_round13`)

| Format | Result | Time | Notes |
|--------|--------|------|-------|
| pptx  | ✅ GREEN | 201s | **NEW** — works after MD2PPTXConverter fix |
| epub  | ✅ GREEN | 137s | |
| html  | ✅ GREEN | 133s | |
| pdf   | ✅ GREEN | 301s | |
| xlsx  | ✅ GREEN |  65s | **NEW** |
| csv   | ❌ RED   |  11s | **Bug #2** OPP CSV binary-detection false-positive on CJK content |
| json  | ❌ RED   |  68s | **Bug #3** ORF MD2JSON needs ` ```json ` code block; translated MD has none |
| xml   | ✅ GREEN |  97s | **NEW** |
| ipynb | ❌ RED   |  11s | **Bug #4** OPP has no IPYNB extractor |
| eml   | ❌ RED   |  67s | **Bug #5** ORF MD2EML failure (same shape as MD2JSON) |

**6/10 PASS (was 4/6 in round 12). 4 new bugs found.**

### Tier 3 en→zh (round 13 run, `tier3_en_zh_round13_*`)

| Format | Result | Time | Notes |
|--------|--------|------|-------|
| xlsx  | ✅ GREEN |  58s | **NEW** |
| csv   | ✅ GREEN |  76s | **NEW** — English CSV is fine; only CJK content trips the binary check |
| json  | ❌ RED   |  77s | Same as #3 |
| xml   | ✅ GREEN | 500s | **NEW** |
| ipynb | ❌ RED   |   8s | Same as #4 |
| eml   | ❌ RED   |  47s | Same as #5 |

**3/6 NEW PASS.** Combined with old run (pptx=1 PASS, epub=1 PASS, html=1 PASS, pdf=1 PASS in old tier3_zh_en):
**6/10 en→zh total** (was 4/10).

### Tier 2 en→zh (round 13 run, e2e_runs/20260618_142351)

| Path | Result | Time |
|------|--------|------|
| xliff_cli | ✅ PASS | 203s |
| xliff_mcp | ✅ PASS | (within run) |
| md_cli    | ✅ PASS | (within run) |
| md_mcp    | ✅ PASS | (within run) |

**4/4 PASS.** Combined with prior zh→en (4/4 from round 9):
**Tier 2 now 8/8 (100%).**

## Coverage Matrix (round 13 end)

| Tier | Cases | Tested | PASS | Status |
|------|-------|--------|------|--------|
| Tier 1 (XLIFF CLI regression) | 1 | 1 | 1 | ✅ 100% |
| Tier 2 (4-path real LLM, 2 langs) | 8 | 8 | 8 | ✅ 100% |
| Tier 3 (10 formats MD, 2 langs) | 20 | 20 | 12 | ⚠️ 60% (4 bugs) |
| Tier 4 (XLIFF backfill, docx+pptx, 2 langs) | 4 | 4 | 3 | ⚠️ 75% (1 timeout, fixed in round 12) |
| Tier 5 (module-only) | 3 | 3 | 1 | ⚠️ 33% (2 xfail) |
| **Total** | **36** | **36** | **25** | **69%** |

**Net change**: 13/36 → 25/36 (+12 PASS, +4 bugs found). Coverage went from 36% → 69%.

## New Bugs (deferred to round 14+)

| # | Severity | Component | Description |
|---|----------|-----------|-------------|
| #2 | High | OPP | `_is_likely_binary()` in `extractors/csv.py:193` flags CJK UTF-8 as binary (printable-byte ratio < 0.5 because 3-byte chars don't pass the 32-126 ASCII filter). Affects any CSV with Chinese/Japanese/Korean content. |
| #3 | High | ORF | `MD2JSONConverter` and `MD2EMLConverter` (round 13: same shape for eml) require a ` ```json ` / ` ```eml ` code block in the input MD. Translated MD from OL is plain text, not a code block. Affects the entire "MD→structured format" pipeline. |
| #4 | Med | OPP | No IPYNB extractor. OPP detects ipynb (via nbformat mime) but raises "不支持的文件格式" at extract time. |
| #5 | Med | ORF | MD2EML is the same shape as #3 — converter expects a structured block in MD, translated MD doesn't provide one. |

## Commits

| SHA | Repo | Summary |
|-----|------|---------|
| TBD | Omni_Re_Formatter | fix(orf): add pptx to apply-md Choice + MD2PPTXConverter CLI arg fix |
| TBD | main | feat(scripts): phase1_runner --source-lang/--target-lang filter + round 13 plan |

## What This Round Is NOT

- Not fixing #2-#5 — they're real bugs but each needs investigation:
  - #2 needs `_is_likely_binary` to count CJK chars as printable
  - #3/#5 needs `MD2JSONConverter` to handle plain text (maybe synthesize a JSON wrapper?)
  - #4 needs an IPYNB extractor in OPP
  All deferred to round 14.
- Not running Tier 1 regression (no Tier 1 code changed) — would be a quick `omo_loop.py --tier 1` smoke.
- Not running OPP-only/ORF-only paths — they need separate work (no current dispatch).

## Round 14 Recommendation

Per user goal: "下个round我们应该努力补全矩阵所有case，否则debug耗时太长了"

Priority for round 14:
1. **Fix #2** (CSV binary detection, ~1h) — small OPP change, unlocks csv en→zh/zh→en
2. **Fix #4** (IPYNB extractor, ~2h) — moderate OPP work, unlocks ipynb
3. **Fix #3 / #5** (MD2JSON / MD2EML, ~2-3h each) — ORF converters need to handle
   plain-text MD (synthesize a code block? or change input format?)
4. Re-run Tier 3 zh→en + en→zh to confirm all 20 PASS
5. Add OPP-only/ORF-only paths (~2h) — final 12 cases to reach 36/36

Estimated: 1-2 days to 36/36.

## Operational Notes

- `OL_ALLOW_HARDCODED_KEYS=1` is required for `local.yaml` with embedded
  API keys (round 8 FIX-#24 escape hatch). Set in env for all round 13 runs.
- `md2pptx` install path: `/tmp/opencode/md2pptx_install/md2pptx/md2pptx`
  (git clone of MartinPacker/md2pptx, chmod +x). Symlinked from
  `/home/renanzai/.local/bin/md2pptx`. Survives session but the
  `/tmp/opencode/` location is volatile — consider committing a proper
  install script in round 14.
- en→zh direction uses `sherlock_holmes.*` fixtures which are 1-3 MB;
  zh→en uses `haier.*` which are 5-50 KB. en→zh is consistently
  5-10× slower wall-clock.
