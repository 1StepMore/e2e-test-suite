---
name: Bug report
about: Report a bug and link a regression scenario (bug → regression-scenario flywheel)
title: "[Bug] "
labels: ["bug"]
assignees: ""
---

<!--
Agent-friendly bug report. Every bug fixed MUST be locked by a regression
scenario in scenarios/regression/ — the flywheel depends on it.
Fill every section; delete nothing. Keep reproduction steps executable.
-->

## Title

One-line summary of the bug.

## Environment

OS, Python version, Omni Suite version, module versions (OPP / OL / ORF), relevant env vars.
(e.g. Ubuntu 22.04, Python 3.13, Suite v0.4.0, OPP v0.9.1, OL v0.7.1, ORF v0.4.17)

## Expected behavior

What should happen.

## Actual behavior

What actually happens (include the error message / stack trace).

## Steps to reproduce

1. Run '...'
2. Configure '...'
3. See error '...'

## Root cause

Tool / file / code line / reason (as determined by investigation).

## Impact

Which pipelines, formats, or MCP tools are affected.

## Fix status

- [ ] Reproduced
- [ ] Root cause identified
- [ ] Fix implemented
- [ ] Fix verified
- [ ] **Regression scenario:** will you add a `scenarios/regression/<bug>.yaml` locking this fix? (required for merge)

## Verification commands

```bash
# Commands proving the fix works and the regression scenario passes.
```

## Notes / Appendix

Relevant logs, related issues, links.
