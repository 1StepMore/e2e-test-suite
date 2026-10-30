# ADR 0008 — Cross-Repo Copy Review: What Stays Duplicated, What Converges, and Why

**Status**: Accepted

**Date**: 2026-10-29

## Context

ADR 0007 converged the path-security policy and recorded two open threads: the
Phase 2B thin wrappers, and a review item naming `detector`, `cache`, `dotenv`
and manifest-schema copies that had drifted across the three sub-repos
(issue #223, P3.4). That review had never been written down, so the same
"should this be shared?" question was being re-litigated in every audit.

This ADR closes the review. It does not change any behaviour; it records which
copies are genuinely duplicated, which are superficially similar but serve
different surfaces, and what triggers each convergence.

## Decision

Keep the three sub-repos independent (ADR 0002). Converge a copy only when it
represents **one policy or one contract**. Do not merge code that merely looks
alike.

### Pairs that are genuinely duplicated

| Copy | Sites | Why it is one thing | Disposition |
|---|---|---|---|
| `SYSTEM_DIRS` / `BLOCKED_EXTENSIONS` | `opp/utils/security.py`, `ol_mcp/security.py`, `orf/mcp/security.py`, `omni_security/_constants.py` | One security boundary; a divergence is a vulnerability (ADR 0007) | Constants are canonical in `omni_security` and gate-enforced by the parity test. Phase 2B (thin wrappers) stays gated on an `omni-security` release. |
| `.env` loading | `opp/cliutils.py:_load_dotenv_for_opp`, `ol/cli/translate_md.py:_load_dotenv`, `orf/cli.py:_load_dotenv_for_orf`, `utils/mcp_client.py` | Near-identical parsing loop (split on `=`, drop quotes, `setdefault`); only OPP/ORF strip an `export` prefix | Converge when a sub-repo next touches its loader: one shared parser, per-module search roots and env-var names. Not urgent — a parser bug is a convenience bug, not a security boundary. |
| Allowlist parsing | `opp/mcp/config.py`, `orf/mcp/config.py`, `ol_mcp/security.py`, `omni_mcp/orchestrator.py` | One syntax (`os.pathsep` + comma) | Already converged and pinned by `TestAllowlistParsingParity`. `ol/cli/load_glossary.py:47` remains a comma-only, fail-open outlier; fold it in the next time that surface changes. |

### Pairs that look duplicated but are not

| Pair | Why it is not one thing |
|---|---|
| `opp/detector.py` vs `orf/commands/detect_format.py` | OPP detects an **input** format to choose an extractor; ORF reports a format over the CLI. Different inputs, outputs and failure modes. |
| `opp/utils/cache.py` vs `ol/cli/cache.py` vs `ol_style/cache.py` | The first is a cache-**root** helper (`OMNI_CACHE_DIR`, 0o700); the second caches translated files by content hash; the third caches StyleGuide profiles. Only the root convention is shared, and it already lives in the OPP helper. |
| `opp/contracts/manifest.py` vs `orf/parsers/manifest.py` | Two sides of one handoff (ADR 0004), not two copies of one schema: OPP **emits** the manifest, ORF **consumes** it. They must be versioned together, which is a contract test, not a shared module. |
| `images.json` writers (OPP, ORF `apply_md`, ORF `apply_xliff`) | ~~Superficially one schema, actually three~~ → **RESOLVED 2026-10-31 (ORF#72).** All three writers now emit the canonical `{"images": [...]}` shape; the `apply_xliff` MCP tool's bare list was the outlier. Both ORF CLI readers were already dual-read (wrapped + legacy bare list), so the writer convergence needed no coordinated release. Locked by `Omni_Re_Formatter/tests/test_mcp_images_json_canonical_shape.py`. |

## Rationale

- A shared package across independently released repos invalidates `uv.lock`
  and forces lockstep releases (ADR 0002, ADR 0007 Alternatives 1 and 3).
- Reviewing the copies removes the repeated "why is this duplicated?" question
  without paying that cost.
- The one security-relevant duplication is already gate-enforced, so the
  residual duplicates are convenience code, not boundaries.

## Alternatives Considered

1. **Extract one `omni-common` package now.** Rejected: same `uv.lock` and
   release-coupling objection as ADR 0007 Phase 2, for code that is not a
   security boundary.
2. **Leave the copies unrecorded.** Rejected: the review item would keep
   resurfacing in every audit (the reason ADR 0007 documented its residuals).
3. **Force all four `.env` loaders into the suite today.** Rejected: it would
   pull a suite-layer dependency into three independently installable
   packages for a convenience feature.

## Consequences

**Positive**

- Every known cross-repo copy now has a recorded disposition and a trigger.
- Future audits can point here instead of re-deriving the answer.

**Negative / residual**

- `.env` parsing stays duplicated until a sub-repo touches it.
- `ol/cli/load_glossary.py` remains comma-only and fail-open until that CLI
  surface is next modified.
- ~~`images.json` still has three shapes (issue #223 P2.2)~~ — resolved by
  ORF#72 (2026-10-31): one canonical shape, dual-read consumers, no release
  coordination needed.

## Related

- ADR 0002 — Three Independent Modules, Not a Monolith
- ADR 0004 — manifest + skeleton as the OPP → ORF handoff contract
- ADR 0007 — Path-Security Validation (Phase 1 + 2A landed; 2B deferred)
- `tests/security/test_path_policy_parity.py` — the gate that keeps the
  security constants aligned
- Issue #223 (P2.1/P2.2/P3.4/P4.1) — the deferred-debt ledger this review closes
  for P3.4
