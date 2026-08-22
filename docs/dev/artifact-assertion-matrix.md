# Artifact-Assertion Matrix

Deterministic P0/P1 assertions on the **actual produced files** of the OPP → OL → ORF
pipeline (issue [e2e-test-suite#44](https://github.com/1StepMore/e2e-test-suite/issues/44)).
Unlike the scenario library (which asserts that commands ran and their stdout/stderr
looked right), the artifact matrix opens every artifact and checks its content and
structure with pure, stdlib-only Python: no LLM, no network, no subprocess.

- Engine: `scripts/validation/artifact_assertions.py` (one readable function per assertion)
- Aggregator + standalone CLI: `scripts/validation/artifact_matrix.py`
- Four-class diff across runs: `scripts/validation/artifact_diff.py`
- Wired into the validation CLI: `run_validation.py --matrix --artifacts <dir-or-zip> --module <m>`

---

## 1. Quick start

```bash
source .venv_ol/bin/activate

# Artifact matrix through the validation CLI (runs the scenario library too, then
# asserts the produced files). --artifacts implies --matrix.
MCP_ALLOWED_DIRECTORIES=/tmp python scripts/validation/run_validation.py \
  --repo orf --tier 1 \
  --matrix --artifacts /tmp/omni_val/orf-backfill-html --module orf

# Standalone on any directory of produced files (no scenario run needed):
python scripts/validation/artifact_matrix.py /tmp/omni_val/orf-backfill-html \
  --module orf --out /tmp/omni_val/artifact-report.json

# Four-class artifact diff between two runs (base = older, head = newer):
python scripts/validation/artifact_diff.py \
  /tmp/omni_val/artifact-report.json \
  /tmp/omni_val/artifact-report-v2.json
```

Real output of the standalone run above:

```
ARTIFACT MATRIX: /tmp/omni_val/artifact-report.json
  in.md                    PASS  (4 assertion(s))
  out.html                 PASS  (5 assertion(s))
  sample.html              PASS  (5 assertion(s))
Totals: 3 artifact(s), 14 assertion(s), 14 passed, 0 failed (P0: 0, P1: 0)
```

---

## 2. What it accepts

`--artifacts <path>` (and the standalone positional) takes either:

- **a directory** of produced files, or
- **a delivery `.zip`** (from `run_validation.py --deliver`, or any zip). A zip is
  unzipped into a temp dir; the extracted `01-RAW/` subdir is asserted when present
  (the delivery layout), otherwise the whole extraction.

Noise is skipped automatically: `.DS_Store`, `Thumbs.db`, `.gitkeep`, `*.pyc`/`*.pyo`,
and `__pycache__/`, `.git/`, `.venv/`, `.venv_ol/`, `.mypy_cache/` directories.

---

## 3. Modules and assertion groups

Every text artifact always runs the **hard-security group** (4 assertions). Structure
groups run only when the artifact's extension matches the selected module.

| Module | Structure assertions | Applies to |
|--------|---------------------|------------|
| `opp` | `_md_nonempty`, `_html_no_tag_leak`, `_manifest_json_parseable`, `_csv_structure` | `.md`, `.json`, `.csv` |
| `ol` | `_target_complete`, `_no_source_echo`, `_shield_roundtrip` | `.md`, `.xlf` |
| `orf` | `_html_has_structure`, `_srt_timecodes`, `_json_parseable`, `_xml_parseable`, `_docx_pptx_zip_ok` | `.html`/`.htm`, `.srt`, `.json`, `.xml`, `.docx`, `.pptx` |
| `suite` | none (hard-security only) | every text artifact |
| `all` | every group whose extension the artifact matches | union of the above |

### Hard-security group (every module)

| Assertion | Severity | What it catches |
|-----------|----------|-----------------|
| `_no_placeholder_leak` | **P0** | Unresolved placeholders in the artifact body: `_No ..._` empty-state markers, `{{...}}` mustache, skeleton echoes (`<finding 1>`), standalone `TBD`/`N/A`/`Not available`/`To be determined` as a whole table cell or list item, leftover `[OL:TYPE:NNNN]` shield markers (skeleton-echo `<tag>` detection is skipped for `.html`/`.htm`/`.xml`/`.xlf`, where tags are real markup) |
| `_no_secret_leak` | **P0** | Credential shapes: `sk-`/`AIza`/`AKIA`/`ghp_` API-key prefixes, PEM private-key headers, `api_key=...` values, unresolved `${OPENAI_API_KEY}`-style env refs as values (lenient: a YAML frontmatter key-definition line like `api_key: ${X}` is excluded) |
| `_no_external_error_text` | **P0** | External-lib error / LLM leakage: Python tracebacks, litellm/BerriAI/"Give Feedback" markers, ANSI escapes, "Internal Server Error", `TimeoutError`, `openai.`/`zhipu`/`bigmodel.cn` error text, HTTP 5xx / 429/500/502/503 status lines (checked in the first 2000 chars) |
| `_no_broken_reference` | **P1** | Malformed references: empty/whitespace-only link targets (`[text]()`, `![alt]()`, `[View Source]()`), empty `<img src>`/`<a href>`, and markdown link targets that are not a plausible URL/path. Relative repo paths like `images/foo.png` are NOT flagged |

### OPP structure (extraction)

| Assertion | Severity | What it catches |
|-----------|----------|-----------------|
| `_md_nonempty` | P1 | `.md` with zero non-blank lines, or only `<!-- -->` comments / frontmatter markers |
| `_manifest_json_parseable` | P1 | `*_manifest.json` / `.json` that fails `json.loads`; a manifest missing `source.file_path`, `source.format`, or `extraction.outputs` |
| `_csv_structure` | P1 | `.csv` that fails `csv.reader`, has no header + data rows, or rows of inconsistent column widths |
| `_html_no_tag_leak` | P1 | Raw `<html>`/`<body>` tags leaked into an OPP-produced `.md` (html→md extraction should convert, not leak). Source: OPP#36 |

### OL structure (translation)

| Assertion | Severity | What it catches |
|-----------|----------|-----------------|
| `_target_complete` | P1 | Empty translated artifact; frontmatter without `target_lang`; an `.xlf` with any `<trans-unit>` whose `<target>` is empty |
| `_no_source_echo` | P1 | An `.xlf` whose `<target>` equals `<source>` for more than half its trans-units; an `.md` with identical `source_lang`/`target_lang` (self-translation) |
| `_shield_roundtrip` | P1 | Leftover `[OL:TYPE:NNNN]` shield markers in an OL `.md` (module-specific stricter check on top of the P0 placeholder leak). Source: E2E-77/78 |

### ORF structure (backfill)

| Assertion | Severity | What it catches |
|-----------|----------|-----------------|
| `_srt_timecodes` | P1 | An `.srt` cue containing `-->` but no valid `HH:MM:SS,mmm --> HH:MM:SS,mmm` timecode line (a passthrough with no timing blocks is not a failure) |
| `_html_has_structure` | P1 | `.html` that is empty, or has neither `<html>`+`<body>` nor a `<!DOCTYPE>` + top-level element |
| `_json_parseable` | P1 | `.json` that fails `json.loads` |
| `_xml_parseable` | P1 | `.xml` that fails `xml.etree.ElementTree` parsing |
| `_docx_pptx_zip_ok` | P1 | `.docx`/`.pptx` that does not open as a zip (OOXML integrity) or opens empty |

---

## 4. Report shape (`artifact-report.json`)

The matrix aggregates per-artifact results into a report card keyed by **artifact
basename** and writes it into the run dir (or the `--out` path).

```json
{
  "matrix_type": "artifact",
  "module": "orf",
  "run_id": "20260822-074459",
  "timestamp": "2026-08-22T07:43:31",
  "artifacts_dir": "/tmp/omni_val/orf-backfill-html",
  "report_card": {
    "out.html": {
      "passed": true,
      "assertions": [
        {
          "name": "_html_has_structure",
          "passed": true,
          "issue": "orf",
          "severity": "P1",
          "module": "orf",
          "artifact": "out.html",
          "detail": "html structure ok"
        },
        {
          "name": "_no_placeholder_leak",
          "passed": true,
          "issue": "e2e#44",
          "severity": "P0",
          "module": "orf",
          "artifact": "out.html",
          "detail": "clean"
        }
      ]
    }
  },
  "counts": {
    "artifacts": 3,
    "assertions": 14,
    "passed": 14,
    "failed": 0,
    "p0_failed": 0,
    "p1_failed": 0
  }
}
```

- An artifact's `passed` is true only when **all** its assertions passed.
- `counts.p0_failed` / `counts.p1_failed` count **failed** assertions by severity.
- Each assertion carries `name` (id), `passed`, `issue` (source reference),
  `severity` (`P0` | `P1`), `module`, `artifact` (basename), `detail` (human one-liner).

---

## 5. Exit-code contract

| Command | Exit 0 | Exit 1 | Exit 2 |
|---------|--------|--------|--------|
| `run_validation.py --matrix --artifacts` | no P0/P1 assertion failures | any P0 or P1 assertion failed (the artifact matrix, not the scenario verdicts, decides the exit code) | n/a |
| `artifact_matrix.py` (standalone) | no P0/P1 failures | any P0 or P1 assertion failed | n/a |
| `artifact_diff.py <base> <head>` | no regressions, no existing-failings | `regressed > 0` OR `existing-failing > 0` | usage/input error (missing file, unparseable JSON, not an artifact-report shape) |

The artifact matrix runs even when the scenarios themselves pass; with `--artifacts`
the artifact verdict **overrides** the scenario exit code (any P0/P1 failure → 1).

---

## 6. Four-class artifact diff

`artifact_diff.py` compares two persisted `artifact-report.json` files (base = older,
head = newer) and classifies **every artifact**:

| Class | Meaning |
|-------|---------|
| `new` | present only in the head run |
| `regressed` | passed → failed (a P0/P1 bar that used to hold now fails) |
| `fixed` | failed → passed |
| `existing-failing` | failed → failed (still failing, not new) |
| `missing` | present only in the base run, reported **separately as a note**, never one of the four classes, does not affect the exit code |

Failed-assertion names are carried on `regressed` / `existing-failing` rows so you can
see which assertion flipped or is still red. On a module mismatch (base module ≠ head
module) every head artifact is classified `new` and every base-only artifact `missing`
(cross-module diffing would otherwise report false regressions).

Real output (base = clean run, head = a run with a leaking artifact added):

```
Artifact-assertion diff (four-class) — base -> head
  base: orf run (unknown run)  @ 2026-08-22T07:43:31
  head: orf run (unknown run)  @ 2026-08-22T07:43:54

CHANGES:
  leaky.html: - -> False (new)

  class              count
  -----------------  -----
  new               1
  regressed         0
  fixed             0
  existing-failing  0


VERDICT: no regressions, no existing-failings -> PASS (exit 0)
```

When a regression or existing-failing exists the verdict flips and the exit code is 1:

```
  class              count
  -----------------  -----
  new               0
  regressed         1
  fixed             0
  existing-failing  1

VERDICT: 1 regressed, 1 existing-failing -> FAIL (exit 1)
```

---

## 7. Commands reference

```bash
# Validation CLI: run scenarios + assert produced files (implies --matrix)
MCP_ALLOWED_DIRECTORIES=/tmp python scripts/validation/run_validation.py \
  --repo orf --tier 1 \
  --matrix --artifacts /tmp/omni_val/orf-backfill-html --module orf
#   -> artifact-report.json in validation-runs/<ts>/, prints "ARTIFACT MATRIX: <path>"

# --artifacts alone also implies --matrix
MCP_ALLOWED_DIRECTORIES=/tmp python scripts/validation/run_validation.py \
  --repo orf --tier 1 --artifacts /tmp/omni_val/orf-backfill-html --module orf

# --matrix without --artifacts keeps the scenario report card
# (report.md + report.json with the per-repo report_card)
python scripts/validation/run_validation.py --repo orf --tier 1 --matrix --deliver
#   --deliver -> delivery .zip under 04-Output/artifacts/deliverables/omni-suite/
#   (01-RAW/ real artifacts, 02-PROCESSED/ reports, manifest.json)

# Standalone matrix (directory OR delivery .zip; --out can be a file path or a dir)
python scripts/validation/artifact_matrix.py /tmp/omni_val/orf-backfill-html \
  --module orf --out /tmp/omni_val/artifact-report.json
python scripts/validation/artifact_matrix.py 04-Output/artifacts/deliverables/omni-suite/omni-suite.zip \
  --module all --out /tmp/omni_val/delivery-report.json

# Four-class artifact diff (exit 1 on regressed>0 or existing-failing>0)
python scripts/validation/artifact_diff.py \
  validation-runs/<older>/artifact-report.json \
  validation-runs/<newer>/artifact-report.json
```

---

## 8. Notes

- The engine is deterministic and hermetic: stdlib only, no LLM, no network, no
  subprocess. Results are returned sorted by `(artifact, name)`.
- `module` defaults to `suite` (hard-security only); `all` runs every structure group
  whose extension an artifact matches.
- `--artifacts` is a coverage-audit-friendly surface: every shipped module tool
  produces artifacts the matrix can assert, so a tool whose output cannot pass the
  hard-security group is a real finding, not a FAKE_LLM artifact of the harness.
- Requires Python 3.13 (same as the rest of the suite). No new dependencies.
