# Agent-tester validation guide — moved out of this repo

The generic methodology ("validating coding agents as testers") is **not product code**, and its
worked example documents **another product line's internals**. Keeping it here made agents treat
that repo as in-scope (see `AGENTS.md` → "Repository boundary"), so it now lives at workspace level:

> `/mnt/d/Hermes-Workspace/99-Tools/methodology/agent-tester-validation-guide.md`

## What applies in this repo

The suite's own, citable half — read these, not the external guide:

| Doc | What it settles |
|:--|:--|
| `scenarios/STANDARDS.md` | the two verdict families (AGENT-SURFACE / HUMAN-QUALITY) + per-anchor thresholds — **the only citable bar** |
| `scenarios/` | the scenario library (`python scripts/validation/run_validation.py --list`) |
| `docs/dev/validation-director-loop.md` | the human director's per-run 10-minute loop |
| `docs/dev/artifact-assertion-matrix.md` | deterministic P0/P1 assertions on produced artifacts |

Do **not** restore a copy of the external guide into this repo.
