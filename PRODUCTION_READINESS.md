# Omni Suite — Production-Readiness Gates

The V1–V11 checklist that lived here has been migrated to the executable gate
registry: **[`GATES.yaml`](GATES.yaml)** (repo root) — its `readiness` layer
holds all 75 declared rows with per-row evidence, and
`omni-suite check --readiness` (via `scripts/check_readiness.py`) dispatches
the auto-checked subset against it.

The retired full document is preserved at
[`docs/archive/PRODUCTION_READINESS.md`](docs/archive/PRODUCTION_READINESS.md).
