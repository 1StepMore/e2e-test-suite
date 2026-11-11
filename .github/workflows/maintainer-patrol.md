---
# 结构示意·R-1·待编译：gh-aw Public Preview，逐键以官方 Frontmatter Reference 当前版为准。
# 落盘前必须 `gh aw compile --strict` 校验并生成 .lock.yml（Owner 决策 O-5：本轮不安装不编译，仅存源）。
on:
  schedule:
    - cron: "0 6 * * 1"
permissions: read-all
# 总开关（suite#299）：仓库变量未启用时整条 agentic 链 skip，activation 不再因缺 secret 而 fail
if: vars.ENABLE_AGENTIC_WORKFLOWS == 'true'
engine: copilot
safe-outputs:
  create-issue:
    title-prefix: "[maintainer] "
---
你是 Maintainer。先读 AGENTS.md（§0 → 角色路由）→ .agents/roles/maintainer.md → docs/DECISIONS.md。
周期巡检：对被指派对象逐个给出显式裁决 + 债务登记；唯一写入出口 = create-issue（只建议不动代码）。
