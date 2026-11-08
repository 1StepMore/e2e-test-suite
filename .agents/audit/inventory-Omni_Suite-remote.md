# Inventory — Omni_Suite @ origin 1StepMore/e2e-test-suite  SOURCE=REMOTE（§7.5）
| ID | 项 | 实测 | 判定依据 | 处置建议 |
|----|----|------|----------|----------|
| R-1 | 远端 URL | https://github.com/1StepMore/e2e-test-suite.git（fetch+push）；目录名 Omni_Suite ≠ 远端名 e2e-test-suite（任务单已知事实） | git remote -v + gh repo view | 如实登记 |
| R-2 | 默认分支 | main | gh api | — |
| R-3 | 权限 | viewerPermission=ADMIN；认证身份=1StepMore(id 140780063) | gh api user/repo | — |
| R-4 | ruleset | main-protection ACTIVE on refs/heads/main：rules=[pull_request, required_status_checks, deletion, non_fast_forward]；bypass_actors=[User 140780063 mode=always]=当前身份 | gh api rulesets/25385981 | O-8 直推 main 可行（bypass 放行）；不动设置 |
| R-5 | classic 分支保护 | 无(404 "Branch not protected") | gh api branches/main/protection | — |
| R-6 | CODEOWNERS | 无(404) | gh api contents/.github/CODEOWNERS | 方针③层缺口→本轮仅登记(改远端设置未授权) |
| R-7 | backup 远端 | git@github.com-renanzai40:renanzai40/OmniSuite_BackUp.git（任务单:仅登记不使用） | git remote -v | 不触碰 |
