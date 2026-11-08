# Inventory — Omni_Suite @ 86db206e9f6a69993f328722e9bd815f36566a4e (2026-11-07)  SOURCE=LOCAL（§7.5）
| ID | 子系统 | 路径 | 类别 | 测试现状 | 文档现状 | CI 覆盖 | 判定依据 | 处置建议(A编号) |
|----|--------|------|------|----------|----------|---------|----------|----------------|
| S-01 | 套件指令层 | AGENTS.md(280行) | 文档 | — | 高质量 index+invariants，超 C3 上限 | doc_inventory gate | 280>200 (C3) | A1 瘦身(O-1 保留最低集) |
| S-02 | 指令复本 | CLAUDE.md(153行)/.cursorrules(61行) | 文档 | — | 与 AGENTS.md 复本；doc_inventory 仅查 CLAUDE.md 工具数(:400-405)，.cursorrules 零覆盖 | 无 | 复本漂移实证(O-7) | A3/A4 适配 + O-7 转薄指针 |
| S-03 | 验证框架 | scripts/validation/(run_validation/coverage_audit/validation_diff/artifact_matrix/artifact_report/validation_report) | 源码+CI | tier1/2/3 场景库 | STANDARDS.md+director-loop 文档 | validation.yml | AGENTS.md「How to validate」 | A13 gate 并入(既有) |
| S-04 | 文档真相机 | scripts/doc_inventory.py | 源码 | 自身被 CI 调用 | docs/dev/doc-inventory-copies.md(三副本同步) | lint.yml/pre-commit | repo 规则「docs 改动须 regenerate」 | A13 扩展(O-2) |
| S-05 | 场景库 | scenarios/(STANDARDS.md+agent-surface/ol/opp/orf-*/_fixtures) | 测试 | 可执行场景 | STANDARDS.md=可引用判定基准 | validation.yml | 两族判定(AGENT-SURFACE/HUMAN-QUALITY) | O-3 薄映射层目标 |
| S-06 | 套件 MCP | omni_mcp/ | 源码 | contract tests | agent-pipeline-guide.md | contract-tests.yml | 4 工具 | 不动 |
| S-07 | 套件测试 | tests/(contract/fidelity/e2e_runner/benchmarks/error_scenarios…) | 测试 | 有 | tests/README+COVERAGE_REPORT | e2e-tests.yml 等 | e2e_tests 现成 | O-6: A9 以此替代 |
| S-08 | CI 体系 | .github/workflows/(8 tracked: lint/doctor/contract-tests/e2e-tests/fidelity/hardening-tests/validation + ?? pinned-guard) | CI | — | 注释充分 | 自身 | lint=diff-scoped(全树基线红) | A7 补一致性 job(O-2)；O-8 pinned-guard 入 main |
| S-09 | 决策与文档 | docs/(DECISIONS.md ADR0001-0008, ARCHITECTURE, dev/*8, CONTRACT.md, CONTEXT.md…) | 文档 | — | 活维护 | doc_inventory | ADR 体系现成 | O-4: 路由指向 DECISIONS.md |
| S-10 | 子仓挂载 | Omni_*(3 个各自带 .git 的实体目录,readlink 指向自身=非常规 symlink) | 源码(独立仓) | 各自 tests | 各自 AGENTS.md(107/202/175) | 各自 CI | .gitignore 注释称 symlink(2026-10-14),实测为实体目录+独立 .git | D-1/O-1 全套整改对象 |
| S-11 | agent 工具态 | .opencode/(skills×6)/.hermes/skills/omni-validation/.omo/.workbuddy/.codegraph/.zcode | CI(工具配置) | — | 部分 | 无 | P1-S5 清单 | D4 合并登记,不覆盖 |
| S-12 | 杂项 | 爱上海尔_第二章_全球创牌 - E2E测试专用.md(未跟踪)/ACCEPTED_GAPS.md/PROJECT_STATUS.md/PRODUCTION_READINESS.md | 文档 | — | 待核 | 无 | 未跟踪+状态类文档可能过期 | 疑似待废弃→Owner 追认(无条件不足,不删) |

## 待废弃清单（仅标记不删除；三条件证据）
- 无满足三条件者；疑似：S-12 三份状态文档 + 爱上海尔*.md（无 CI 覆盖、无引用声明，但未声明废弃→证据不足，留 Owner）
## 敏感文件清单（仅路径）
.env(已忽略✅) / .env.example / .gitleaks.toml / pre-commit: gitleaks+detect-private-key 已接线 / D:\贯维\Vibe\_credentials(仓库外,范围外登记)
## 现有 agent 设施清单（保留/合并/适配 → D4）
AGENTS.md(合并改造) / CLAUDE.md+APcursorrules(适配为指针) / .opencode/skills×6(保留) / .hermes/skills/omni-validation(保留) / .zcode/config.json(保留) / 无 .agents/.claude/.specify/.github/agents(新建)
## 前置缺口登记（A14/R-5）
| 缺口ID | 类型 | 证据 | 影响的验收项 | 状态 |
|---|---|---|---|---|
| （无——BUILD/TEST/LINT/E2E 全部取证成功） | — | — | — | — |
## 回填参数区
BUILD_CMD=make setup(依赖安装)/pip install -e 各子仓; TEST_CMD=make test(=test-opp test-ol test-orf)+make test-contract; LINT_CMD=make lint(注意: 全树 ruff 基线红,以 diff-scoped lint.yml 为准); E2E_CMD=python tests/e2e_runner.py(见 e2e-tests.yml); E2E_RUNNER=pytest+FAKE_LLM(CI 模式)/real-LLM nightly; REPO=Omni_Suite; PILOT=本轮唯一套件
