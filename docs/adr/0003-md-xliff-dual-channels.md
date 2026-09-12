# ADR 0003 — MD + XLIFF Dual Channels

**Status**: Accepted

**Date**: 2026-08-13

## Context

The pipeline carries content over two parallel channels:

- **MD channel**: Markdown suited for layout-tolerant pipelines and simple
  formats (HTML, CSV, JSON). ORF needs only `document.md` plus `images.json`.
- **XLIFF channel**: XLIFF 1.2/2.0 with `<bx>`/`<ex>` inline tags, preserving
  format for DOCX/PPTX backfill. ORF needs `document.xlf`,
  `document.skeleton.zip`, and `document_manifest.json`.

The same DOCX can go through either channel; the choice trades layout fidelity
for simplicity.

## Decision

Maintain both channels and let the user pick per document, with
`--target-format both` as the recommended default when unsure.

## Rationale

Two audiences want different things:

- A user converting a contract wants fonts, styles, and floating images
  preserved, which only the XLIFF channel gives.
- A user exporting a newsletter to HTML wants fast text output with
  approximate image placement.

Producing both from one OPP pass is nearly free, so there is no cost pressure
to pick one.

## Alternatives Considered

1. **XLIFF only**. Drops the simple formats (HTML, CSV, JSON, OCR images) and
   forces every translation through skeleton-based backfill, which those
   formats do not support.
2. **MD only**. Loses inline formatting tags and exact layout for DOCX/PPTX,
   which is unacceptable for brand-critical documents.
3. **A single intermediate format that does both**. Rejected: no format
   combines Markdown's readability with XLIFF's structural fidelity without
   inventing a new, unproven schema.

## Consequences

- **Positive**: Users get full flexibility; no format is left behind; the
  recommended default (`both`) covers most cases.
- **Negative**: Two code paths to maintain in ORF; documentation must explain
  when to use which path.

## Related

- `docs/ARCHITECTURE.md` §2 "Two channels" (lines 91-102), §7 decision #2
- `README.md` → Pipeline Selection Strategy

---

*Migrated from: `docs/DECISIONS.md` (original entry #0003)*
