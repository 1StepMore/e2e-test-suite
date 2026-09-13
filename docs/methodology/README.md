# Methodology References (vendored)

This directory holds vendored copies of external methodology documents that are
cited by repo artifacts. Vendoring makes those citations resolvable
repo-relative, as required by gap **D-02** in
`.omo/plans/agent-oriented-gap-register.md`.

## Inventory

| File | Source path | Retrieved | Citation form | Vendored content |
|---|---|---|---|---|
| `agent-oriented-design-mindset.md` | `/mnt/d/贯维/Vibe/methodology/agent-oriented-design-mindset.md` | 2026-09-13 | `[DOC §x]` | Byte-identical to the source except (a) a one-line HTML-comment provenance header and (b) a clearly-marked **Local Addendum (Omni Suite)** appended at the end — an intentional, documented exception to the byte-identical invariant (see below). |

### `agent-oriented-design-mindset.md`

- **Source**: `/mnt/d/贯维/Vibe/methodology/agent-oriented-design-mindset.md`
- **Retrieved**: 2026-09-13
- **Source checksum** (md5, pre-vendor): `5094a54016154d25525e099a3fb57533`
- **Diff rule**: `diff <source> docs/methodology/agent-oriented-design-mindset.md`
  differs **only** by line 1 (the provenance header) and by the trailing
  `## Local Addendum (Omni Suite) — Fallbacks Are Never Evidence` section
  (see *Local additions* below). Any other difference means the copy is
  stale — re-vendor.
- **Local additions (documented byte-identical exception)**: the trailing
  `## Local Addendum (Omni Suite) — Fallbacks Are Never Evidence` section is
  an intentional, repo-local addition made 2026-09-13 to satisfy validation
  gap **R-07** sub-item (d) in `.omo/plans/agent-oriented-gap-register.md`.
  It is clearly marked as not part of the upstream source. The source
  checksum above is unchanged because the upstream file is untouched; because
  of this addendum the vendored copy is no longer byte-identical to the
  source. When re-vendoring, re-append the addendum from
  `scenarios/STANDARDS.md#fallbacks-never-evidence` and keep this note in
  sync.
- **Section mapping**: section numbering is preserved verbatim from the source;
  no renumbering was applied. Every `[DOC §x]` citation in
  `.omo/plans/agent-oriented-gap-register.md` resolves to a `###`/`##` heading
  in this copy (§1.2, §2.1, §2.2, §2.4, §2.5, §3.1, §3.3, §4.1, §4.2, §4.3,
  §5.3, §6.1, §6.3, §7.2, §8.1). The literal `[DOC §x]` in the plan is a
  metavariable, not a citation.

Do not edit vendored files in place. Update the upstream source, then re-vendor
and refresh the checksum/date above. The sole exception is the clearly-marked
trailing `## Local Addendum (Omni Suite)` section, which is repo-local by
design and must be recorded in this README whenever it changes.
