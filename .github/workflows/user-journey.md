<!-- 结构示意·R-1·待编译：gh-aw Public Preview，逐键以官方 Frontmatter Reference 当前版为准。
落盘前必须 `gh aw compile --strict` 校验并生成 .lock.yml（Owner 决策 O-5：本轮不安装不编译，仅存源）。
旅程为管线级黑盒（docs/user/），无 UI、不用 Playwright（O-6）。 -->
---
on:
  workflow_dispatch:
permissions: read-all
engine: copilot
safe-outputs:
  create-issue:
    title-prefix: "[user] "
---
你是 User。先读 docs/user/ → .agents/roles/user.md；按旅程逐条走完公开入口，产出旅程报告 issue（四段式）。
