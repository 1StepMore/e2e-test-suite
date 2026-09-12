# ADR 0005 — PDF → XLIFF Blocked by Design

**Status**: Accepted

**Date**: 2026-08-13

## Context

OPP enforces a case-insensitive guard that blocks PDF → XLIFF generation with
a `ValueError` and a clear message. PDF extraction produces no meaningful
structural units for XLIFF, and a PDF cannot be backfilled into a structural
DOCX/PPTX layout. PDF → MD remains allowed but is limited to text-only
extraction.

## Decision

Keep the block. PDF input routes through the MD channel only.

## Rationale

- XLIFF works on translatable units with inline formatting tags; a PDF gives
  neither paragraph structure nor a skeleton to backfill into.
- Generating an XLIFF anyway would set up ORF to fail or to produce a
  layout-degraded document.
- The guard turns that into an early, explicit error at extraction time instead
  of a silent failure at backfill time.

## Alternatives Considered

1. **Allow PDF → XLIFF with a best-effort skeleton**. The skeleton serializer
   has no structural OOXML to preserve, so the backfill would drop layout
   silently. Worse than an explicit error.
2. **Invent structural units from PDF text runs**. Fabricating paragraphs and
   inline tags from ambiguous PDF text would mislead downstream QA and produce
   translations keyed to invented boundaries.
3. **Remove the guard and let ORF fail**. Moves the error later in the
   pipeline, after translation work has already been spent. The OPP guard is
   the cheapest place to reject.

## Consequences

- **Positive**: Early, explicit error; no wasted translation work; clear
  user expectation.
- **Negative**: PDF users must use the MD channel; no layout preservation
  possible for PDF input.

## Related

- `docs/ARCHITECTURE.md` §3.1 format guards (lines 124-129), §7 decision #4
- `ACCEPTED_GAPS.md` line 10

---

*Migrated from: `docs/DECISIONS.md` (original entry #0005)*
