---
# 结构示意·R-1·待编译：gh-aw Public Preview，逐键以官方 Frontmatter Reference 当前版为准。
# 落盘前必须 `gh aw compile --strict` 校验并生成 .lock.yml（Owner 决策 O-5：本轮不安装不编译，仅存源）。
# 确定性部分（E2E 套件执行）走常规 Actions（e2e-tests.yml），本工作流只做推理型验收裁决。
on:
  pull_request:
    types: [opened, synchronize]
permissions: read-all
# 总开关（suite#299）：仓库变量未启用时整条 agentic 链 skip，activation 不再因缺 secret 而 fail
if: vars.ENABLE_AGENTIC_WORKFLOWS == 'true'
engine: copilot
safe-outputs:
  add-comment:
    max: 1
---
你是 Tester。先读 AGENTS.md（§0 → 角色路由）→ .agents/roles/tester.md → scenarios/STANDARDS.md → .agents/expectations/。
按 checkpoints 评估终态、逐 checkpoint 出 verdict，以 .agents/roles/tester.md 的固定 JSON 评论；严禁改任何文件/期望。
