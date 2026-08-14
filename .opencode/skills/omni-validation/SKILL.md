---
name: omni-validation
description: Validate the Omni Suite against its 83-scenario library (agent-user conformance + human-quality conformance). List/run/check scenarios, read the director report, audit coverage. Tier-1 runs are hermetic (no LLM keys).
---

# Omni Suite — Validation Framework

Run the suite's agent-testing validation engine (see
`docs/agent-tester-validation-guide.md` for the pattern, `scenarios/`
for the library). Every scenario dispatches through the REAL shipped
surface — no mocks, no FAKE_LLM as evidence (draft D4).

## How to validate

All commands run from the suite root with the shared venv:

```bash
source .venv_ol/bin/activate

# Enumerate the library (name, tier, requires_env, steps) — no execution
python scripts/validation/run_validation.py --list

# Run one scenario by filename substring, hermetic tier (no LLM keys)
python scripts/validation/run_validation.py --scenario <name> --tier 1

# Contract-lint the library itself (falsifiable expects, standard anchors)
python scripts/validation/run_validation.py --check

# Coverage audit: every live MCP tool must be exercised by a scenario
python scripts/validation/coverage_audit.py

# Diff two runs (verdict changes + regression detection)
python scripts/validation/validation_diff.py <runs-dir>/<ts1> <runs-dir>/<ts2>
```

## Reading the results

1. `validation-runs/latest.txt` → path of the newest run
   (`validation-runs/<ts>/scenarios.json`).
2. Generate the director report from that run:

   ```bash
   python scripts/validation/validation_report.py validation-runs/<ts>/scenarios.json
   # → report.md + report.json in the same run dir
   ```

`report.md` renders TWO verdict families side by side (draft D13):

- **agent-user conformance** — tool-* scenarios + AGENT-SURFACE standard
  anchors (`#tool-contract`, `#json-parseable`, `#error-clarity`,
  `#path-security`, `#exit-codes`): every agent-facing surface works as
  an agent would use it.
- **human-quality conformance** — pipeline-* scenarios + HUMAN-QUALITY
  anchors (`#lqa-threshold`, `#para-ratio`, `#cjk-density`,
  `#punct-hygiene`, `#drawing-count`, `#opens-docx`): output satisfies
  human end-users.

`unconfigured` (missing env, e.g. no LLM keys) is a distinct status —
never a pass, never a silent skip.

## Standards

`scenarios/STANDARDS.md` is the single citable bar: every step's
`expect` cites `standard: STANDARDS.md#<anchor>` naming its family.
Read it before judging a verdict; never invent thresholds.

## Director checklist

A human director completes the 10-minute loop per run:
`docs/dev/validation-director-loop.md` (two-role model: agent validator +
human director; per-run standards conformance pass ticking both families).

## When to use this skill

- "Validate the suite / prove this fix / is the regression scenario green?"
- Before handing over a change that touches any agent-facing surface or
  pipeline quality bar — run the relevant scenario and cite the verdict.
- The same engine is exposed via suite MCP tools
  `list_validation_scenarios` + `run_validation_scenario` (omni_mcp).
