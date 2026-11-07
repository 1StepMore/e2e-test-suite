# docs/user/ — User Journeys（用户旅程）

User 角色（`.agents/roles/user.md`）的黑盒旅程来源。旅程 = **管线级**走查（本仓无 UI，不用 Playwright）：
仅通过公开入口（`opp` / `ol` / `orf` / `omni-suite` CLI 与产物文件）验证端到端行为。

| 旅程 | 文件 | 入口 | 判定 |
|---|---|---|---|
| DOCX 端到端本地化（抽取→翻译→回填） | `journey-docx-localization.md` | 三条模块 CLI | journey pass/fail/blocked |

写新旅程：一文件一旅程，固定骨架 = `## 旅程`（名+基线 commit）/ `## 步骤结果`（预期 vs 实际表）/ `## 差距清单`（docs-bug/product-bug/ux）/ `## 旅程判定`。
旅程期望改判 = Owner 显式指令（根 AGENTS.md §0-4）；执行载体可复用 `tests/e2e_runner.py` 与 `e2e-tests.yml`（O-6：不另起 Gherkin 骨架）。
