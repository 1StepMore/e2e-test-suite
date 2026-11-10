---
# 结构示意·R-1·待编译：gh-aw Public Preview，逐键以官方 Frontmatter Reference 当前版为准。
# 落盘前必须 `gh aw compile --strict` 校验并生成 .lock.yml（Owner 决策 O-5：本轮不安装不编译，仅存源）。
on:
  issues:
    types: [labeled]
permissions: read-all
engine: copilot
safe-outputs:
  create-pull-request:
    title-prefix: "[coder] "
    draft: true
---
你是 Coder。先读 AGENTS.md（§0 → 角色路由）→ .agents/roles/coder.md；功能分支实现，产出待评审 PR（四段式）。
确定性部分（BUILD/TEST/LINT）走常规 Actions（lint.yml / ci 类工作流），不进本工作流。
