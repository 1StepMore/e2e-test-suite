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

## 归属（owner）

- [ ] **任一侧可做**（默认 —— 不打 `owner:*` 标签）
- [ ] 只有本机侧能做：重依赖模态（视频/音频/图片渲染）→ `owner:code-auto`
- [ ] 只有主人侧能做：Windows 原生 / 需要他的账号额度或外部动作 → `owner:human-agent`

> 判据见 `docs/dev/autonomy.md`：可做名单 = `agent-ready` ∧ 无 `owner:*` ∧ 无 `status:claimed` ∧ 未被 open PR 认领。
> **不标 `owner:*` 就是「任一侧可做」，这是默认，不是遗漏。**

## Title

One-line summary of the bug.

## Environment

OS, Python version, Omni Suite version, module versions (OPP / OL / ORF), relevant env vars.
(e.g. Ubuntu 22.04, Python 3.13, Suite v0.5.0, OPP v0.10.0, OL v0.7.1, ORF v0.5.0)

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
