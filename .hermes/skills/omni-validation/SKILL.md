---
name: omni-validation
description: Validate the Omni Suite against its scenario library (agent-user conformance + human-quality conformance). Thin pointer — the authoritative SOP with gate-enforced counts lives in the suite checkout's .opencode/skills/omni-validation.
compatibility: hermes
---

# Omni-Suite Validation (pointer)

This is a **thin pointer**: it carries no counts and no thresholds —
those drift, so they live only in the gated source:

    <suite checkout root>/.opencode/skills/omni-validation/SKILL.md

Read that skill first. It owns: the scenario-library SOP (`--list` /
`--scenario <stem> --tier 1` / `--check`), the coverage audit, the
director report, the two verdict families, and the honesty rules
(`unconfigured` is never a pass; FAKE_LLM is never quality evidence).

Quick shape — run everything from the suite checkout root (the directory
containing `scenarios/`, `scripts/validation/`, `omni_mcp/`):

```bash
python scripts/validation/run_validation.py --list                  # enumerate (no execution)
python scripts/validation/run_validation.py --scenario <name> --tier 1
python scripts/validation/run_validation.py --check                 # contract-lint the library
python scripts/validation/coverage_audit.py                         # every live MCP tool exercised
```

The same engine is exposed via suite MCP tools
`list_validation_scenarios` + `run_validation_scenario` (omni_mcp).

Standards bar: `scenarios/STANDARDS.md`. Director loop:
`docs/dev/validation-director-loop.md`.
