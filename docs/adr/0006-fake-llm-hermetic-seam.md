# ADR 0006 — FAKE_LLM / FAKE_PANDOC Hermetic Test Seam

**Status**: Accepted

**Date**: 2026-08-13

## Context

All CLI calls need `OMNI_TEST_FAKE_LLM=1` unless real LLM API keys are
configured; `OMNI_TEST_FAKE_PANDOC=1` bypasses the pandoc subprocess for ORF
format conversion. The seam replaces the LLM and pandoc steps with
deterministic stand-ins and is the contract for CI and local dev across all
three modules.

## Decision

Keep the environment-variable seam as the standard test path. Real-LLM tests
are the explicit exception, gated behind installed keys.

## Rationale

- Tests must never require real API keys.
- The seam makes the test suite hermetic: no network, no keys, no flaky model
  output.
- Two FAKE_LLM runs produce byte-identical outputs, so CI assertions are
  stable.
- FAKE_PANDOC removes the one heavy external binary from the suite's critical
  path.

## Alternatives Considered

1. **Call the real LLM in tests**. Costs money, needs secrets in CI, and model
   output is non-deterministic, which breaks byte-for-byte assertions.
2. **Record and replay responses (VCR-style)**. Keeps determinism but adds a
   fixture-maintenance burden every time a prompt changes.
3. **Monkeypatch the HTTP layer**. Brittle against library internals and harder
   to audit than a single well-documented environment variable.

## Consequences

- **Positive**: Hermetic tests; no secrets in CI; deterministic assertions;
  zero-cost local dev.
- **Negative**: Real-LLM behavior not tested in standard CI; seam must be
  maintained as LLM/pandoc APIs evolve.

## Related

- `AGENTS.md` Critical Notes #1 and Environment Variables table
- `docs/ARCHITECTURE.md` §7 decision #5

---

*Migrated from: `docs/DECISIONS.md` (original entry #0006)*
