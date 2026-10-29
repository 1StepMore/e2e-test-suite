# docs/archive — Retired Documents

> **What this is.** Everything here is **retired**: superseded, resolved, or a
> dated snapshot. Nothing in `docs/archive/` is authoritative. If you are
> looking for current guidance, it lives in the maintained `docs/` tree, the
> root docs, or `scenarios/STANDARDS.md`.
>
> **Marker convention.** Every archived file carries this first-line marker:
>
> ```
> > **Status: ARCHIVED (YYYY-MM-DD). Reason: <reason>. Superseded by: <pointer>.**
> ```
>
> The marker is enforced by `scripts/doc_inventory.py --check` (Gate A): an
> archived file without it, or an ARCHIVED marker outside `docs/archive/`,
> fails the check. `docs/dev/doc-inventory.md` lists every archived file with
> status `archived`.

## What's here

| File | Archived | Reason | Superseded by |
|------|----------|--------|---------------|
| `OPP_VALIDATION_MASTER_PLAN.md` | 2026-08-23 | Prose validation plan superseded by the executable scenario library | `scripts/validation/run_validation.py` + `scenarios/` |
| `OL_VALIDATION_MASTER_PLAN.md` | 2026-08-23 | Same | Same |
| `ORF_VALIDATION_MASTER_PLAN.md` | 2026-08-23 | Same | Same |
| `SUITE_VALIDATION_MASTER_PLAN.md` | 2026-08-23 | Same | Same |
| `T14_LIMITATION.md` | 2026-08-23 | Resolved limitation, retained for history | The fix it documents |
| `SECURITY_FINDINGS.md` | 2026-08-23 | Dated `pip-audit` snapshot (2026-06-22) | `docs/SECURITY_AUDIT.md` (live audit) |
| `e2e-fix-records.md` | 2026-08-23 | One-off E2E bug-fix records moved out of `README.md` | `CHANGELOG.md` + git history |
| `INTEGRATED_TEST_PLAN.md` | 2026-10-26 | Phase artifact; superseded by the executable scenario library | `tests/` + `scenarios/` |
| `feature_inventory.md` | 2026-10-26 | Phase artifact; feature/QA state maintained in `README.md` + module docs | `README.md` |
| `system_improvements_v2.md` | 2026-10-26 | Phase artifact; improvements landed | `CHANGELOG.md` |
| `e2e-test-plan.md` | 2026-10-26 | Phase artifact; superseded by the executable scenario library | `tests/` + `scenarios/` |
| `lqa-pipeline-integration.md` | 2026-10-26 | Phase artifact; LQA expectations moved to maintained docs | `docs/archive/OL_EXPECTATIONS.md` (archived 2026-10-30) |
| `lqa-workflow.md` | 2026-10-26 | Phase artifact; superseded by the director loop | `docs/dev/validation-director-loop.md` |
| `agent-qa-workflow.md` | 2026-10-26 | Phase artifact; superseded by the director loop | `docs/dev/validation-director-loop.md` |
| `issue-pipeline-quality-improvements.md` | 2026-10-26 | Phase artifact; improvements landed | `CHANGELOG.md` |
| `OPP_EXPECTATIONS.md` | 2026-10-30 | Stale Founder's-expectations snapshot (header v0.9.1); function replaced by the scenario library | `scenarios/` + `Omni_Pre_Processor/AGENTS.md` |
| `OL_EXPECTATIONS.md` | 2026-10-30 | Stale expectations snapshot; function replaced by the scenario library | `scenarios/` + `Omni_Localizer/AGENTS.md` |
| `ORF_EXPECTATIONS.md` | 2026-10-30 | Stale expectations snapshot (header v0.4.17); function replaced by the scenario library | `scenarios/` + `Omni_Re_Formatter/AGENTS.md` |
| `SUITE_EXPECTATIONS.md` | 2026-10-30 | Stale expectations snapshot (header v0.4.0 / 2026-07-22); function replaced by the scenario library | `scenarios/` + `AGENTS.md` |
| `master-validation-template.md` | 2026-10-30 | Orphaned validation master template (2026-07-16) | `scenarios/` + `docs/dev/validation-director-loop.md` |
| `handoff-2026-09-18.md` | 2026-10-30 | Point-in-time handoff notes, zero live references | `PROJECT_STATUS.md` + `docs/dev/validation-loop-log.md` |
| `project-code-aesthetics-review-2026-10-22.md` | 2026-10-30 | Dated one-off audit; action items landed or tracked | `CHANGELOG.md` + git history |
| `project-evaluation-pain-points-2026-09-06.md` | 2026-10-30 | Dated one-off pain-point review, zero live references | `docs/project-infrastructure-audit-2026-10-30.md` |

## How to archive something

1. `git mv <file> docs/archive/`.
2. Prepend the `ARCHIVED` marker line above, with today's date, a one-line
   reason, and what supersedes it.
3. Update the table above.
4. Fix every maintained-doc reference to the old path (point at the archive
   or at the successor).
5. `python3 scripts/doc_inventory.py && python3 scripts/doc_inventory.py --check`.

## How to un-archive (rare)

1. `git mv docs/archive/<file> <maintained-path>`.
2. Remove the `ARCHIVED` marker.
3. Update the table, fix references, regenerate the inventory, run `--check`.
