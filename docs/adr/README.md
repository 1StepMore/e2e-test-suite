# Architecture Decision Records (ADR)

This directory contains immutable architecture decision records for the Omni
Suite. Each ADR captures a significant decision: context, decision, alternatives
considered, and rationale.

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0001](0001-cli-framework-defer-unification.md) | CLI Framework: Defer Unification | Accepted (deferred) | 2026-06-29 |
| [0002](0002-three-independent-modules.md) | Three Independent Modules, Not a Monolith | Accepted | 2026-08-13 |
| [0003](0003-md-xliff-dual-channels.md) | MD + XLIFF Dual Channels | Accepted | 2026-08-13 |
| [0004](0004-manifest-skeleton-handoff.md) | manifest + skeleton as OPP → ORF Handoff Contract | Accepted | 2026-08-13 |
| [0005](0005-pdf-xliff-blocked.md) | PDF → XLIFF Blocked by Design | Accepted | 2026-08-13 |
| [0006](0006-fake-llm-hermetic-seam.md) | FAKE_LLM / FAKE_PANDOC Hermetic Test Seam | Accepted | 2026-08-13 |

## Rules

1. **One file per decision.** No multi-decision epics.
2. **Immutable once accepted.** To reverse or modify, create a new ADR and mark
   the old one as `Superseded by NNNN`.
3. **Number sequentially.** Never reuse numbers.
4. **Template:** Use `TEMPLATE.md` for new ADRs.

## Creating a New ADR

```bash
# 1. Copy the template
cp docs/adr/TEMPLATE.md docs/adr/NNNN-short-title.md

# 2. Fill in the sections

# 3. Add to this index

# 4. Commit
git add docs/adr/NNNN-short-title.md docs/adr/README.md
git commit -m "docs: add ADR NNNN — [title]"
```
