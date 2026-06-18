# Production Acceptance Thresholds (Phase E5)

These are the real numbers the system must meet before declaring
"production ready." They are derived from the Phase D calibration
and the Phase E validation results, not arbitrary targets.

## QA Quality Thresholds

| Metric | Threshold | Source |
|--------|-----------|--------|
| Multi-judge LQA pass rate (avg ≥ 4.0/5) | ≥ 85% | Phase E5 |
| Spearman rank correlation (judge vs reference) | ≥ 0.7 | Phase D3 |
| Inter-judge exact-match agreement | ≥ 60% | Phase D3 |
| Inter-judge agreement tolerance | exact (no ±1) | Phase D3 |

## Performance Thresholds

| Metric | Threshold | Source |
|--------|-----------|--------|
| P95 latency (50MB file, E1) | < 5 min | Phase E1 |
| Sustained throughput | ≥ 100 docs/hour | Phase E2 |
| 8-hour throughput (100 docs) | 100/100 complete | Phase E3 |
| Memory growth over 1 hour (E2) | < 500MB (no leak) | Phase E2 |
| Crash rate (E2 1-hour load) | 0 crashes | Phase E2 |

## Security & Observability Thresholds

| Metric | Threshold | Source |
|--------|-----------|--------|
| Security tests (Phase A) | 63/63 pass | Phase A gate |
| Observability tests (Phase B) | 42/42 pass | Phase B gate |
| Install/CI (Phase C) | `git clone && uv sync && bash setup_dev.sh` < 10 min | Phase C gate |
| Hardcoded secrets in tracked configs | 0 | Phase A2 + C3 regression |
| Circuit breaker threshold | 5 consecutive failures → open | Phase B1 |

## Process

- **Calibration run**: `ol calibrate --reference eval/reference/`
  (Phase D3 CLI). Run after any change to the judge pool or
  reference LLM.
- **Validation run**: run E1-E4 in order. E1-E3 are manual
  (gated on fixture/infrastructure availability).
- **Nightly CI**: runs the 42 observability + 63 security + 4 QA
  tests automatically. E1-E3 are excluded.
- **D6 gate**: if Spearman < 0.7 OR agreement < 60%, the test
  fails and the user is alerted. This is the only human
  touchpoint in the QA system.

## Status (as of round 16 Phase E)

| Phase | Status | Tests |
|-------|--------|-------|
| A (Security) | ✅ pass | 63/63 |
| B (Observability) | ✅ pass | 42/42 |
| C (Install/CI) | ✅ pass | fresh checkout works |
| D (QA system) | ✅ code complete | 4/4 regression |
| D2/D3/D4 unit | ✅ pass | 46/46 |
| E1 (50MB) | ⏸ gated on fixture | needs 50MB DOCX |
| E2 (load) | ⏸ gated on infra | needs locust/load gen |
| E3 (throughput) | ⏸ gated on time | 8-hour manual run |
| E4 (re-audit) | ✅ pass | all regression green |
| E5 (acceptance) | ✅ documented | this file |
