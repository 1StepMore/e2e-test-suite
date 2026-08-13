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

---

## 0002 — Three Independent Modules, Not a Monolith (2026-08-13)

**Status**: Accepted

**Context**: The suite is three modules, not one program. OPP extracts
(`Omni_Pre_Processor`), OL translates (`Omni_Localizer`), ORF backfills
(`Omni_Re_Formatter`). Each has its own git repo, PyPI package, CLI, and MCP
server. They are composable: any version combination listed in
`VERSION_COMPATIBILITY.md` is contract-tested end-to-end
(`ARCHITECTURE.md:23-25`).

**Decision**: Keep the three modules independent. Do not fold them into a
single monolith package or a single deployable.

**Rationale**: Independence gives each module its own shipping cadence; OPP
can tag and release without waiting on OL or ORF. `pip install opp` works
alone, which matters for users who only need extraction. Failure domains stay
separate, and each MCP server keeps its own security allowlist. The
submodule-era alternative was already tried and removed on 2026-06-24
(`ARCHITECTURE.md` §7 row 9).

**Alternatives considered**:

1. **Single monolith package** (`pip install omni-suite`). One install gives
   all three stages, but couples releases: a fix in OL forces a full suite
   release, and users who want one stage pay for all three.
2. **One repo, shared git history**. The 2026-06-24 submodule removal brought
   the code into one tree, but the modules kept separate `.git/` directories
   and packages. A shared history would lose per-module release control.
3. **Shared codebase with feature flags**. Rejected because the three modules
   share no business logic beyond the file handoff; a monolith would add
   coupling without a payoff.

**Related**: `docs/ARCHITECTURE.md` §1 (lines 23-25), §7 decision #1.

---

## 0003 — MD + XLIFF Dual Channels (2026-08-13)

**Status**: Accepted

**Context**: The pipeline carries content over two parallel channels. The MD
channel uses Markdown and suits layout-tolerant pipelines and simple formats
(HTML, CSV, JSON); ORF needs only `document.md` plus `images.json` for image
injection. The XLIFF channel uses XLIFF 1.2/2.0 with `<bx>`/`<ex>` inline
tags and preserves format for DOCX/PPTX backfill; ORF needs `document.xlf`,
`document.skeleton.zip`, and `document_manifest.json`. The same DOCX can go
through either channel; the choice trades layout fidelity for simplicity, and
the 36-path matrix in the parent README records which combinations are
production-verified (`ARCHITECTURE.md:91-102`).

**Decision**: Maintain both channels and let the user pick per document, with
`--target-format both` as the recommended default when unsure.

**Rationale**: Two audiences want different things. A user converting a
contract wants fonts, styles, and floating images preserved, which only the
XLIFF channel gives. A user exporting a newsletter to HTML wants fast text
output with approximate image placement. Producing both from one OPP pass is
nearly free, so there is no cost pressure to pick one.

**Alternatives considered**:

1. **XLIFF only**. Drops the simple formats (HTML, CSV, JSON, OCR images) and
   forces every translation through skeleton-based backfill, which those
   formats do not support.
2. **MD only**. Loses inline formatting tags and exact layout for DOCX/PPTX,
   which is unacceptable for brand-critical documents.
3. **A single intermediate format that does both**. Rejected: no format
   combines Markdown's readability with XLIFF's structural fidelity without
   inventing a new, unproven schema.

**Related**: `docs/ARCHITECTURE.md` §2 "Two channels" (lines 91-102), §7
decision #2.

---

## 0004 — manifest + skeleton as the OPP → ORF Handoff Contract (2026-08-13)

**Status**: Accepted

**Context**: For the XLIFF channel, OPP hands ORF three artifacts:
`{base_name}_manifest.json` (source info, extraction stats, image metadata,
versioned by `manifest_version`), `{base_name}.skeleton.zip` (the original
OOXML ZIP structure preserved verbatim), and the translated `{base_name}.xlf`.
The manifest is required for the XLIFF channel; the skeleton lets ORF rebuild
the original layout without knowing how OPP extracted it
(`ARCHITECTURE.md:115-120`).

**Decision**: Use `manifest.json` + `skeleton.zip` as the formal OPP → ORF
contract for XLIFF backfill, with `manifest_version` as the versioning signal.

**Rationale**: The manifest is small, machine-readable, and versioned, so ORF
can validate that it is consuming a compatible extraction before touching the
skeleton. The skeleton preserves layout without forcing OPP to know about ORF
internals, keeping the two modules decoupled. The contract is the seam where
either module can evolve independently.

**Alternatives considered**:

1. **OPP converts directly to the target format**. That makes OPP a backfiller
   too, duplicating ORF and coupling extraction to every output format.
2. **Pass an in-memory document object between processes**. Breaks the
   file-based handoff and the independent process boundaries the modules rely
   on.
3. **No manifest, just loose files**. Loses versioning and validation; ORF
   could silently consume an incompatible skeleton and produce corrupt output.

**Related**: `docs/ARCHITECTURE.md` §3.1 OPP outputs (lines 115-120), §7
decision #3.

---

## 0005 — PDF → XLIFF Blocked by Design (2026-08-13)

**Status**: Accepted

**Context**: OPP enforces a case-insensitive guard that blocks PDF → XLIFF
generation with a `ValueError` and a clear message. PDF extraction produces no
meaningful structural units for XLIFF, and a PDF cannot be backfilled into a
structural DOCX/PPTX layout. PDF → MD remains allowed but is limited to
text-only extraction (`ARCHITECTURE.md:124-129`; `ACCEPTED_GAPS.md` row 10,
2026-06-20).

**Decision**: Keep the block. PDF input routes through the MD channel only.

**Rationale**: XLIFF works on translatable units with inline formatting tags;
a PDF gives neither paragraph structure nor a skeleton to backfill into.
Generating an XLIFF anyway would set up ORF to fail or to produce a
layout-degraded document. The guard turns that into an early, explicit error
at extraction time instead of a silent failure at backfill time.

**Alternatives considered**:

1. **Allow PDF → XLIFF with a best-effort skeleton**. The skeleton serializer
   has no structural OOXML to preserve, so the backfill would drop layout
   silently. Worse than an explicit error.
2. **Invent structural units from PDF text runs**. Fabricating paragraphs and
   inline tags from ambiguous PDF text would mislead downstream QA and produce
   translations keyed to invented boundaries.
3. **Remove the guard and let ORF fail**. Moves the error later in the
   pipeline, after translation work has already been spent. The OPP guard is
   the cheapest place to reject.

**Related**: `docs/ARCHITECTURE.md` §3.1 format guards (lines 124-129), §7
decision #4, `ACCEPTED_GAPS.md` line 10.

---

## 0006 — FAKE_LLM / FAKE_PANDOC Hermetic Test Seam (2026-08-13)

**Status**: Accepted

**Context**: All CLI calls need `OMNI_TEST_FAKE_LLM=1` unless real LLM API
keys are configured; `OMNI_TEST_FAKE_PANDOC=1` bypasses the pandoc subprocess
for ORF format conversion. The seam replaces the LLM and pandoc steps with
deterministic stand-ins and is the contract for CI and local dev across all
three modules (`AGENTS.md` Critical Notes #1; `ARCHITECTURE.md` §7 decision
#5).

**Decision**: Keep the environment-variable seam as the standard test path.
Real-LLM tests are the explicit exception, gated behind installed keys.

**Rationale**: Tests must never require real API keys. The seam makes the test
suite hermetic: no network, no keys, no flaky model output. Two FAKE_LLM runs
produce byte-identical outputs (`ACCEPTED_GAPS.md` line 19), so CI assertions
are stable. FAKE_PANDOC removes the one heavy external binary from the suite's
critical path.

**Alternatives considered**:

1. **Call the real LLM in tests**. Costs money, needs secrets in CI, and model
   output is non-deterministic, which breaks byte-for-byte assertions.
2. **Record and replay responses (VCR-style)**. Keeps determinism but adds a
   fixture-maintenance burden every time a prompt changes.
3. **Monkeypatch the HTTP layer**. Brittle against library internals and
   harder to audit than a single well-documented environment variable.

**Related**: `AGENTS.md` Critical Notes #1 and the Environment Variables
table, `docs/ARCHITECTURE.md` §7 decision #5.
