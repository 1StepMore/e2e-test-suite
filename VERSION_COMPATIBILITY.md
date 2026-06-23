# Version Compatibility Matrix

> **Last updated**: 2026-06-22
> **Purpose**: Records which OPP / OL / ORF version combinations are tested and compatible.
> **Maintenance**: Update this table EVERY TIME you deploy a new version of ANY module.
> **CI validation**: `tests/integration/test_version_compat.py` verifies the marked combinations.

## Compatibility Table

| opp | ol | orf | Status | Last Tested | Notes |
|-----|-----|-----|--------|-------------|-------|
| 0.6.2 | 0.4.5 | 0.4.4 | ✅ Tested | 2026-06-23 | E2E-07/14/15/64/65 surgical cherry-picks |
| 0.6.3 | 0.4.5 | 0.4.4 | ✅ Tested | 2026-06-23 | OPP v0.6.3: stderr handler in verbose mode (test_detect_format_flag) |
| 0.6.1 | 0.4.4 | 0.4.3 | ✅ Tested | 2026-06-22 | Current production baseline |
| 0.6.0 | 0.4.3 | 0.4.2 | ✅ Tested | 2026-06-15 | Previous release |
| 0.5.0 | 0.4.0 | 0.4.0 | ⚠️ Partial | 2026-06-01 | Known XLIFF schema mismatch |

## Compatibility Rules

| Rule | Description |
|------|-------------|
| **Same major** | Modules with the same major version number are guaranteed compatible |
| **Lower major + higher minor** | Usually compatible — run tests before production deployment |
| **Different major** | NOT compatible. Breaking changes have been introduced. Do not deploy |

## How to Add a Row

1. Run `scripts/bumpversion.py` to update all three versions together
2. Run `tests/integration/test_version_compat.py` to verify the new combination
3. If tests pass, add a new row above with status ✅ Tested
4. If some tests fail, add a row with ⚠️ Partial and document the gaps

## Current Versions

```
opp: 0.6.1 (commit 4187ac1)
ol:  0.4.4 (commit e52597f)
orf: 0.4.3 (commit 8120cbc)
```

## Integration Pipeline Versions

The following pipeline components are pinned to specific versions for stability:

| Component | Version | Repo |
|-----------|---------|------|
| OPP (CLI) | v0.6.1+ | Omni_Pre_Processor |
| OPP (MCP) | v0.6.1+ | Omni_Pre_Processor |
| OL (CLI) | v0.4.4+ | Omni_Localizer |
| OL (MCP) | v0.4.4+ | Omni_Localizer |
| ORF (CLI) | v0.4.3+ | Omni_Re_Formatter |
| ORF (MCP) | v0.4.3+ | Omni_Re_Formatter |
| omni-suite | v0.2.0 | e2e-test-suite (root) |

## Dependency Graph

```
OPP ──MD / XLIFF──▶ OL ──MD / XLIFF──▶ ORF
  │                   │                   │
  └── images.json ────┘                   │
  └── skeleton.zip ───────────────────────┘
```

**Contract**: OPP produces → OL accepts → ORF consumes.
Breaking this chain requires a compatibility row with test evidence.
