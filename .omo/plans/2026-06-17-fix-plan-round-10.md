# Fix Plan — Round 10 (2026-06-17) — Tier 3 Format Matrix

## Goal

Run `omo_loop.py --tier 3` → `scripts/phase1_runner.py --tier P1` →
format matrix (10 input formats × 2 langs via MD path, 20 cases).
This is the **first broad-coverage Tier 3 run**.

## Why This Round

Round 9 Tier 2 verified all 4 paths on a single DOCX. Tier 3 expands
to 10 input formats — this is where format-specific OPP/ORF bugs
hide. Round 9 docx-only path passed cleanly; format-specific code
paths (PDF OCR, EPUB chapters, XLSX tables, IPYNB notebooks) have
not been exercised end-to-end with real LLM in this session.

## Tier 3 Matrix

20 cases from `phase1_runner.build_matrix()` P1 tier:

| # | Format | Input | Output | Lang | Path |
|---|---|---|---|---|---|
| 1-2 | pptx | haier/sherlock | pptx | zh→en, en→zh | cli-md |
| 3-4 | epub | haier/sherlock | epub | zh→en, en→zh | cli-md |
| 5-6 | html | haier/sherlock | html | zh→en, en→zh | cli-md |
| 7-8 | pdf  | haier/sherlock | pdf | zh→en, en→zh | cli-md |
| 9-10 | xlsx | haier/sherlock | xlsx | zh→en, en→zh | cli-md |
| 11-12 | csv | haier/sherlock | csv | zh→en, en→zh | cli-md |
| 13-14 | json | haier/sherlock | json | zh→en, en→zh | cli-md |
| 15-16 | xml | haier/sherlock | xml | zh→en, en→zh | cli-md |
| 17-18 | ipynb | haier/sherlock | ipynb | zh→en, en→zh | cli-md |
| 19-20 | eml | haier/sherlock | eml | zh→en, en→zh | cli-md |

## Scope

### Step 1 — Plan + commit (XS)
- Plan file (this)
- Commit

### Step 2 — Pre-flight (XS)
Already verified:
- 20 fixtures exist (10 formats × 2 langs)
- `phase1_runner.py --tier P1 --dry-run` enumerates 20 cases
- `OL_ALLOW_HARDCODED_KEYS=1` set at run time (local.yaml has real keys)
- pandoc available

### Step 3 — Run Tier 3 (20-100 min)

```bash
cd /mnt/d/贯维/Omni_Suite
OL_ALLOW_HARDCODED_KEYS=1 .venv_ol/bin/python scripts/omo_loop.py \
    --tier 3 \
    --source-lang zh --target-lang en
```

phase1_runner P1 only does zh→en, then needs to be re-run for en→zh
(per `--source-lang`/`--target-lang`). So actually 2 runs (one
each direction).

Actually re-reading omo_loop.py dispatch:
```python
def _run_tier_3(args) -> int:
    cmd = [
        sys.executable, str(phase1),
        "--tier", "P1",
        "--source-lang", args.source_lang,
        "--target-lang", args.target_lang,
    ]
```

So Tier 3 runs only ONE language direction. To get full 20 cases
I'd need 2 separate runs (zh→en + en→zh).

For round 10, do BOTH runs back-to-back: total 40 cases.

### Step 4 — Analyze (S)
Read phase1_runner output per case. Categorize:
- CRITICAL (OPP/OL/ORF pipeline crash)
- MINOR (LQA below threshold, format conversion quality)
- PASS

### Step 5 — Fix critical bugs (M)
Format-specific bugs found (PDF OCR, EML parsing, XLSX tables, etc.).

### Step 6 — Update plan (XS)
Append results, recommended next steps.

## Expected Outcomes

| Outcome | Probability | Action |
|---|---|---|
| All 20 cases PASS | ~30% | Commit results, jump to Tier 4 (XLIFF backfill) |
| 1-3 format-specific bugs | ~50% | Fix, re-run, jump to Tier 4 |
| 4+ bugs | ~20% | Triage; some formats may need investigation |
| Major infra issue | <5% | Fix dispatch, re-run |

## Risk

- **Runtime**: 40-100 min for both directions.
- **API cost**: free tier, no billable risk.
- **PDF OCR**: PDF cases may need tesseract OCR; may fail if not installed.
- **Format-specific failures**: pdf/eml/ipynb historically have had edge cases.

## Verification Targets

- All 20 (or 40 for both directions) cases execute
- Per-case pass/fail captured
- Tier 1 + Tier 2 still pass (regression)

## What This Round is NOT

- Not modifying Tier 4/5 dispatch (only Tier 3)
- Not adding new test infrastructure (focus is execution)
- Not changing OPP/ORF format-specific code unless a bug is found

## Recommended Next Round (round 11)

- Tier 4 (XLIFF backfill matrix) if Tier 3 passes
- Tier 5 (module-only) if more bugs found
- En→zh long-tail optimization (#4) if long documents surface
- Address specific format bugs from Tier 3 results