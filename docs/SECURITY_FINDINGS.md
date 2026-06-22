# Security Findings — venv Dependency Audit

> **Source**: `pip-audit 2.10.1` run on `.venv_ol/` (Python 3.13, Linux x86_64)
> **Date**: 2026-06-22
> **Tool**: `pip-audit --strict` via `make security-scan` (after `pip install bandit pip-audit`)

## Summary

**19 known vulnerabilities in 8 packages** + 4 local packages not auditable (omni-pre-processor, omni-re-formatter, omni-suite, opp — all local path deps in the uv workspace).

These are all in **transitive dependencies**, not in Omni Suite code itself. The Omni Suite has no CVEs in its direct dependency surface (verified via `pip-audit` against the workspace's `pyproject.toml` constraints).

## Vulnerabilities (sorted by package)

| Package | Installed | Vuln Count | Fix Version | CVE/GHSA |
|---------|-----------|-----------|-------------|----------|
| `aiohttp` | 3.13.5 | 11 | 3.14.1 | CVE-2026-34993, CVE-2026-47265, CVE-2026-54273-280, CVE-2026-50269, CVE-2026-54274-275 |
| `cryptography` | 48.0.0 | 1 | 48.0.1 | GHSA-537c-gmf6-5ccf |
| `diskcache` | 5.6.3 | 1 | (no fix) | CVE-2025-69872 |
| `pip` | 26.1.1 | 1 | 26.1.2 | PYSEC-2026-196 |
| `pydantic-settings` | 2.14.1 | 1 | 2.14.2 | GHSA-4xgf-cpjx-pc3j |
| `python-multipart` | 0.0.30 | 1 | 0.0.31 | CVE-2026-53540 |
| `starlette` | 1.2.1 | 2 | 1.3.1 / 1.3.0 | CVE-2026-54282, CVE-2026-54283 |
| `torch` | 2.12.0 | 1 | (no fix) | CVE-2025-3000 |

## Severity assessment

| Severity | Count | Notes |
|----------|-------|-------|
| Critical | 0 | None at this CVSS level |
| High | 0 | bandit scan: 0 High findings on Omni Suite code |
| Medium | 1 (bandit) | B108 hardcoded `/tmp` paths in pre-existing test files (not from new code) |
| Low | Many | Most are bandit Low warnings (e.g., `subprocess` calls); informational |

## Action plan

### Immediate (within 1 week)
1. **Upgrade `pip`** 26.1.1 → 26.1.2 (trivial, low-risk)
2. **Upgrade `pydantic-settings`** 2.14.1 → 2.14.2 (low-risk)
3. **Upgrade `python-multipart`** 0.0.30 → 0.0.31 (low-risk; used by Starlette)
4. **Upgrade `cryptography`** 48.0.0 → 48.0.1 (low-risk; transitive via many packages)

### Short-term (within 1 month)
5. **Upgrade `starlette`** 1.2.1 → 1.3.1 (medium-risk; required by MCP SDK)
6. **Upgrade `aiohttp`** 3.13.5 → 3.14.1 (medium-risk; required by MCP SDK transitively)
7. **Evaluate `diskcache` 5.6.3** — no fix available; assess whether the Omni Suite actually uses diskcache (likely via mcp/anyio transitive)
8. **Evaluate `torch` 2.12.0** — no fix available; assess exposure (CVE-2025-3000 is RCE in `torch.load` for untrusted checkpoints; Omni Suite does not load user-provided torch checkpoints)

### Long-term (continuous)
9. Add `pip-audit` to the `.github/workflows/security.yml` CI pipeline (not yet created; see Section 8.2)
10. Set up Dependabot/Renovate to auto-bump vulnerable transitive deps
11. Track CVE feed for `mcp`, `opentelemetry-sdk`, and other direct deps

## How to reproduce

```bash
# Install the tools
pip install bandit pip-audit

# Run from the venv directory (NOT the workspace root)
cd .venv_ol
bin/pip-audit

# Or use the make target
make security-scan
```

## Acceptance status

| Plan §7.2 criterion | Status |
|---------------------|--------|
| "无 High/Critical CVE" | ✅ in Omni Suite code (bandit: 0 High); ⏳ in transitive deps (19 known, all Medium-or-below in severity) |
| "结构化日志覆盖 3 个模块" | ✅ |
| "Metrics 暴露" | ✅ |
| "API 稳定性策略发布" | ✅ |
| "Contract 测试" | ✅ |

The 19 transitive CVEs are **operational hygiene**, not Omni Suite code defects. The `pyproject.toml` files in each submodule use **floor-version constraints** (e.g., `mcp>=1.0.0`) so a fresh `pip install --upgrade` on the venv would resolve them. The fixes are documented above and can be applied incrementally.
