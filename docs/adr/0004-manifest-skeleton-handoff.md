# ADR 0004 — manifest + skeleton as the OPP → ORF Handoff Contract

**Status**: Accepted

**Date**: 2026-08-13

## Context

For the XLIFF channel, OPP hands ORF three artifacts:

- `{base_name}_manifest.json` — source info, extraction stats, image metadata,
  versioned by `manifest_version`
- `{base_name}.skeleton.zip` — the original OOXML ZIP structure preserved
  verbatim
- `{base_name}.xlf` — the translated XLIFF file

The manifest is required for the XLIFF channel; the skeleton lets ORF rebuild
the original layout without knowing how OPP extracted it.

## Decision

Use `manifest.json` + `skeleton.zip` as the formal OPP → ORF contract for
XLIFF backfill, with `manifest_version` as the versioning signal.

## Rationale

- The manifest is small, machine-readable, and versioned, so ORF can validate
  that it is consuming a compatible extraction before touching the skeleton.
- The skeleton preserves layout without forcing OPP to know about ORF internals,
  keeping the two modules decoupled.
- The contract is the seam where either module can evolve independently.

## Alternatives Considered

1. **OPP converts directly to the target format**. That makes OPP a backfiller
   too, duplicating ORF and coupling extraction to every output format.
2. **Pass an in-memory document object between processes**. Breaks the
   file-based handoff and the independent process boundaries the modules rely
   on.
3. **No manifest, just loose files**. Loses versioning and validation; ORF
   could silently consume an incompatible skeleton and produce corrupt output.

## Consequences

- **Positive**: Clean module boundary; version compatibility checking; safe
  evolution of either module.
- **Negative**: Three files to manage per extraction; manifest schema must be
  versioned and documented.

## Related

- `docs/ARCHITECTURE.md` §3.1 OPP outputs (lines 115-120), §7 decision #3
- `CONTRACT.md` — handoff contract specification

---

*Migrated from: `docs/DECISIONS.md` (original entry #0004)*
