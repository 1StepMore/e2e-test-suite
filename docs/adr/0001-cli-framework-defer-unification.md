# ADR 0001 — CLI Framework: Defer Unification

**Status**: Accepted (deferred)

**Date**: 2026-06-29

## Context

The 3 sub-repos use different CLI frameworks:

| Sub-repo | Framework | Entry point | Version pin |
|----------|-----------|-------------|-------------|
| OPP (`Omni_Pre_Processor/`) | `argparse` | `src/opp/cli.py:8` | (stdlib) |
| OL (`Omni_Localizer/`) | `typer` | `src/ol_cli.py:10` | `typer>=0.15.0` |
| ORF (`Omni_Re_Formatter/`) | `click` | `src/orf/cli.py:14` | `click>=8.1.0` |

Parameter naming is **already consistent** across all three: all flags use
`--kebab-case` (e.g., `--target-format`, `--output-dir`, `--source-lang`).
The real differences are in how each framework handles internal mechanics:

- **Boolean flags**: argparse `store_true` (`--no-embed-images`) vs click
  double-flag pair (`--separate-images/--no-separate-images`) vs typer `Flag`
  class.
- **Help generation**: raw argparse text vs click rich help vs typer auto.
- **Subcommand dispatch**: argparse subparsers vs click `@click.group()` vs
  typer `@app.command()`.

## Decision

**Keep as-is.** No reported bugs or user confusion attributable to the framework
mix. The maintenance burden is real but cosmetic.

## Rationale

1. Each sub-repo's CLI is already stable and well-tested (OPP ~10 yrs of
   argparse maturity, OL moved to typer in v0.4, ORF uses click idiomatically).
2. Migration risk is non-trivial: rewriting CLI argument definitions, help
   strings, and subcommand dispatch can break undocumented user workflows.
3. Current naming consistency means users can switch between CLIs without
   re-learning flag syntax — the user-visible problem is already solved.

## Alternatives Considered

1. **Unify now**. High migration risk for cosmetic benefit; no user-facing gain.
2. **Standardize on click**. Would require rewriting OL's typer decorators; no
   clear advantage over current state.

## Consequences

- **Positive**: Zero migration risk; no user-facing changes; modules stay
  independently releasable.
- **Negative**: Three CLI frameworks to maintain; new contributors must know
  all three; some internal patterns differ.

## Future Plan (NOT in scope)

1. **Phase A** (~2-3 days): Migrate OPP from `argparse` → `typer`.
2. **Phase B** (~1-2 days): Migrate ORF from `click` → `typer`.
3. **Phase C** (optional): Drop `click>=8.1.0` and `argparse` dependencies.

**Estimated total effort**: 3-5 days.

## Related

- Suite-level `ARCHITECTURE.md` covers cross-module orchestration
- Per-sub-repo AGENTS.md files cover CLI internals

---

*Migrated from: `docs/DECISIONS.md` (original entry #0001)*
