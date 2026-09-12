# ADR 0002 — Three Independent Modules, Not a Monolith

**Status**: Accepted

**Date**: 2026-08-13

## Context

The suite is three modules, not one program. OPP extracts
(`Omni_Pre_Processor`), OL translates (`Omni_Localizer`), ORF backfills
(`Omni_Re_Formatter`). Each has its own git repo, PyPI package, CLI, and MCP
server. They are composable: any version combination listed in
`VERSION_COMPATIBILITY.md` is contract-tested end-to-end.

## Decision

Keep the three modules independent. Do not fold them into a single monolith
package or a single deployable.

## Rationale

- Independence gives each module its own shipping cadence; OPP can tag and
  release without waiting on OL or ORF.
- `pip install opp` works alone, which matters for users who only need
  extraction.
- Failure domains stay separate, and each MCP server keeps its own security
  allowlist.
- The submodule-era alternative was already tried and removed on 2026-06-24.

## Alternatives Considered

1. **Single monolith package** (`pip install omni-suite`). One install gives
   all three stages, but couples releases: a fix in OL forces a full suite
   release, and users who want one stage pay for all three.
2. **One repo, shared git history**. The 2026-06-24 submodule removal brought
   the code into one tree, but the modules kept separate `.git/` directories
   and packages. A shared history would lose per-module release control.
3. **Shared codebase with feature flags**. Rejected because the three modules
   share no business logic beyond the file handoff; a monolith would add
   coupling without a payoff.

## Consequences

- **Positive**: Independent releases; per-module security; users can install
  only what they need.
- **Negative**: Three packages to maintain; version compatibility matrix
  required; cross-module testing overhead.

## Related

- `docs/ARCHITECTURE.md` §1 (lines 23-25), §7 decision #1
- `COMPATIBILITY.md` — version compatibility matrix

---

*Migrated from: `docs/DECISIONS.md` (original entry #0002)*
