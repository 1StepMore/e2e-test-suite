---
name: omni-validation
description: Validate the Omni Suite against its scenario library (agent-user conformance + human-quality conformance). List, run, and check validation scenarios, then read the director report. No LLM calls needed for tier-1 runs.
compatibility: hermes
---

# Omni-Suite Validation

## When to Use
Use this skill when asked to validate the Omni Suite, prove a fix, or
report on pipeline health. Examples:
- "Run the validation suite and report the verdicts"
- "Is the regression scenario still green after this change?"
- "What does the coverage audit say about the agent surface?"

## How to validate

Run from the suite root (`/mnt/d/贯维/Omni_Suite`) with the shared venv:

```bash
source .venv_ol/bin/activate

# 1. See what exists (no execution, no LLM)
python scripts/validation/run_validation.py --list

# 2. Run one hermetic scenario (tier 1 = no LLM keys needed)
python scripts/validation/run_validation.py --scenario <name> --tier 1

# 3. Lint the library itself (contract lint, no execution)
python scripts/validation/run_validation.py --check
```

Only these scripts exist — do not invent other commands:
`scripts/validation/{run_validation.py, coverage_audit.py, validation_report.py, validation_diff.py}`.

## Reading the results

- `validation-runs/latest.txt` — points at the most recent run directory
  (`validation-runs/<ts>/scenarios.json`) and its verdict counts.
- The **director report** is generated from a persisted run:

  ```bash
  python scripts/validation/validation_report.py validation-runs/<ts>/scenarios.json
  # → report.md + report.json in the same run dir
  ```

The report carries TWO verdict families side by side (judge both):

| Family | What it proves | Typical statuses |
|---|---|---|
| **agent-user conformance** | every agent-facing tool/CLI works as an agent would use it (tool-* scenarios + AGENT-SURFACE standards) | passed / failed / unconfigured |
| **human-quality conformance** | pipeline output satisfies human end-users (pipeline-* scenarios + HUMAN-QUALITY standards, needs real LLM keys) | passed / failed / unconfigured |

`unconfigured` means the scenario needs env vars that are absent — it is
NEVER a pass and NEVER a silent skip.

## Standards

Every scenario step cites the exact bar it enforces:
`scenarios/STANDARDS.md` — two named families: **AGENT-SURFACE**
(`#tool-contract`, `#json-parseable`, `#error-clarity`, `#path-security`,
`#exit-codes`) and **HUMAN-QUALITY** (`#lqa-threshold`, `#para-ratio`,
`#cjk-density`, `#punct-hygiene`, `#drawing-count`, `#opens-docx`).
Read it before judging a verdict; do not invent thresholds.

## Director checklist

A human (or lead agent) completes the 10-minute director loop per run:
see `docs/dev/validation-director-loop.md` (two-role model: agent
validator + human director, per-run standards conformance pass).

## Pitfalls
- Tier 2/3 scenarios need real LLM keys — without them they report
  `unconfigured`; do not present that as a failure or a pass.
- Runs persist to `validation-runs/` (gitignored) — quote
  `validation-runs/latest.txt`, never a stale timestamp you guess.
- The suite `omni_mcp` server exposes the same scenarios as MCP tools
  (`list_validation_scenarios`, `run_validation_scenario`).
