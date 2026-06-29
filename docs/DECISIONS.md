# Architecture Decision Records

This file captures significant architectural decisions for the Omni Suite, in
chronological order. Each decision is immutable once accepted; supersede
with a new ADR rather than editing history.

## 0001 — CLI Framework: Defer Unification (2026-06-29)

**Status**: Accepted (deferred)

**Context**: The 3 sub-repos use different CLI frameworks:

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

**Decision**: **Keep as-is.** No reported bugs or user confusion attributable
to the framework mix. The maintenance burden is real but cosmetic.

**Rationale for not unifying now**:

1. Each sub-repo's CLI is already stable and well-tested (OPP ~10 yrs of
   argparse maturity, OL moved to typer in v0.4, ORF uses click idiomatically).
2. Migration risk is non-trivial: rewriting CLI argument definitions, help
   strings, and subcommand dispatch can break undocumented user workflows.
3. Current naming consistency means users can switch between CLIs without
   re-learning flag syntax — the user-visible problem is already solved.

**Future plan** (NOT in scope of the current gap-fix cycle):

1. **Phase A** (separate cleanup sprint, ~2-3 days): Migrate OPP from
   `argparse` → `typer`. OL already uses typer, so this is the lowest-effort
   step. Most OPP commands have <5 flags, so per-command rewrite is small.
2. **Phase B** (if time permits, ~1-2 days): Migrate ORF from `click` → `typer`.
   Click and typer are compatible at the decorator level, buttyper's `Typer()`
   app structure differs from click's `@click.group()`.
3. **Phase C** (optional): Drop the `click>=8.1.0` and `argparse` dependencies
   from `pyproject.toml` files (typer transitively depends on click, so click
   stays; argparse is stdlib so nothing to drop there).

**Estimated total effort** for full unification: 3-5 days.

**Owner**: TBD (not blocking any current work).

**Related**: Suite-level `ARCHITECTURE.md` covers cross-module orchestration;
this ADR is specifically about per-sub-repo CLI surface.
