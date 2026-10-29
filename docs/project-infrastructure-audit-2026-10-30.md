# Omni Suite 基础设施有效性审计（2026-10-30）

Status: POINT-IN-TIME AUDIT (2026-10-30). 证据基于本日工作区快照；被点名文件随演进可能已修复。

## 0. 摘要（TL;DR）

以「Agent as a user / Agent as a tester」双角色为基准，对 skills、gates、hooks、validation
scenarios、MCP/CLI 消费面四类基础设施做了静态审计 + 本机实跑验证。

**总体结论：这是一个自我监督机制真实运转、但门禁覆盖面有结构性缺口的仓库。**

- ✅ **有效的核心**：41 个 MCP 工具的文档-实况零漂移；123 个验证场景可证伪且 `--check`
  实跑干净；覆盖审计执行级 41/41（本机 WSL 实跑 PASS）；诚实判定语义
  （`unconfigured`/`invalid`/`known-gap`）在引擎里真实实现；doc-truth 门禁源真相派生、
  实跑通过；验证治理环（LOOP-LOG）有真抓真改的记录。
- ❌ **无效/误导的部分**：所有「主动误导」项共用一个根因——doc-truth 门禁只冻结
  「固定文件清单里的数字」，**行为性声明与清单外副本完全不在真值域内**。由此存活了
  6 处会误导 agent 的高危文档缺陷（见 §3.1、§3.4）；e2e 真实 LLM 夜间验证声明了
  schedule 门控却从未定义 schedule 触发器（§3.3 最大漏洞）。
- 🟡 **环境现实**：`.venv_ol` 是 WSL/Linux venv，Windows 主机上文档化的验证循环
  无法照做，3 个 pre-commit 钩子降级 SKIP（有可见消息、CI 兜底）——基础设施有效性
  实际上以 WSL 为前提，但所有指引只写了 Linux 流程。

方法：4 路并行静态审计（验证框架 / 门禁与 CI / skills 与文档 / MCP-CLI 消费面）+
本机实跑（`doc_inventory.py --check` ✅、`run_validation.py --check` ✅、
`coverage_audit.py` 于 WSL ✅ 41/41）。证据均标注 `file:line`。

---

## 1. 分析基准：双角色如何映射到本项目

项目的设计意图在 AGENTS.md / `scenarios/STANDARDS.md` /
`docs/dev/validation-director-loop.md` 中已有明确的双角色结构，审计直接采用并核验其落地：

| 用户提出的概念 | 项目中的落地 | 判定基准 |
|---|---|---|
| **Agent as a user**：agent 消费产品（发现工具→调用→容错恢复） | AGENT-SURFACE 判定家族（agent-user conformance）：41 个 MCP 工具 + 各模块 CLI；标准锚点 `#tool-contract` `#json-parseable` `#error-clarity` `#path-security` `#exit-codes` | 文档与实况是否一致；错误是否可解析、可行动；path security 是否 fail-closed |
| **Agent as a tester**：agent 验证产品（出证据、拟判定） | 验证框架：validator agent 执行场景/收集证据，human director 终审（"The agent grades; the human disposes"，validation-director-loop.md:23-31）；HUMAN-QUALITY 家族（`#lqa-threshold` 等 6 锚点） | 证据是否可证伪、可引用；判定是否诚实；循环是否闭环 |

一条重要发现：**「Agent as a tester」在本项目里被刻意设计为半自动**——agent 出证据、
人 director 终审。这是合理的治理选择；本审计据此把「director 链路是否真的走通」
（run → report → 人工审阅 → sign-off）作为有效性判据之一，而不是只看引擎是否存在。

有效性判定采用五条标准：

1. **真实接线**——被 hook / CI / Makefile / 文档链路实际调用，而非仅在文档中被描述；
2. **可证伪**——expect 存在能使其失败的世界状态；
3. **与源真相同步**——声称的数字/行为与代码实况一致，或有门禁强制一致；
4. **服务双角色之一**——对 agent-user 的上手/避坑，或对 agent-tester 的取证/回归有实际贡献；
5. **本机可复现**——在当前工作区（Windows + WSL 双环境）能否按文档跑出同样结果。

---

## 2. 设计意图与现实的一句话对照

设计意图：agent-first 的三段文档本地化流水线（OPP 提取 → OL 翻译 → ORF 回填），
3 个独立子仓 + 套件级编排；文档按「index + invariants」（AGENTS.md）+ 按需加载组织；
用一套 agent 无关的验证框架以诚实判定语义产出可引用证据。

现实：**核心承诺兑现**（工具清单、验证场景、诚实语义、文档门禁全部真实且实跑通过），
但「门禁只看数字」+「单环境文档」+「headline 指针噪声」三个结构性缺口，使
agent-user 会踩中若干文档地雷，agent-tester 的本地循环体验与文档承诺不符。

---

## 3. 分类判定

### 3.1 Agent-as-user 消费面（MCP / CLI / 行为契约）

| # | 基础设施 | 判定 | 证据 |
|---|---|---|---|
| A1 | 41 工具注册表与文档一致性 | ✅ 有效 | `docs/agent-pipeline-guide.md:126-145` 与 4 个 live registry（`opp/mcp/server.py:104-290`、`ol_mcp/tools.py`、`orf/mcp/server.py:88-96`、`omni_mcp/server.py:319-451`）逐名核对 **0 漂移**；`agent-surface/` 恰好 41 个 `tool-*` 场景一一对应 |
| A2 | 成功响应包络 | ✅ 有效 | 四服务器统一 `{"success": true, "content": …}`（`omni_mcp/server.py:64-66` 等） |
| A3 | 错误响应包络 | 🟡 部分有效 | 核心字段统一；但 **OL 无 `recovery`**（`ol_mcp/tools.py:51-64`）、ORF 未知工具抛 `ValueError` 绕过包络（`orf/mcp/server.py:344`）、ORF 未捕获异常走 `isError` 裸文本（:351-361）。统一解析 `recovery` 的 agent 会在 OL 上破预期；guide 的包络章节（:209-237）未记录这些差异 |
| A4 | Path security | ✅ 有效（一处文档不符） | 四服务器均 fail-closed：OPP 启动即拒（`opp/mcp/config.py:183`）、OL 启动 SystemExit（`ol_mcp/server.py:27-32`）、omni 无 allowlist 全拒（`orchestrator.py:160-166`）；**ORF 是惰性的**（首次调用才校验，`orf/mcp/common.py:62-82`），与 guide :289 「startup raises」不符 |
| A5 | `omni_security` 包 | 🟡 名不副实但可控 | 三子仓 **零 import**，各持副本；靠 589 行平价测试冻结（`tests/security/test_path_policy_parity.py:23-52`）。「single source」仅对 omni_mcp 成立——鉴于子仓是独立 repo，这是合理妥协，但文档不应暗示共享 |
| A6 | Agent Tips 行为契约（4 条） | 🟡 3 真 1 假 | E2E-65 注入剥离 ✅（`ol_md/repair/level1.py:4`）、E2E-15 孤儿图过滤 ✅（`opp/markdown/generator.py:147-158`）、E2E-07 模糊匹配 ✅（`orf/channels/xliff2docx/matcher.py:672-697`）、OL 门禁 env vars ✅（`ol_lqa/quality_gates.py:9-11`）；**「`omni_suite/cli.py` is print-only」为假**（AGENTS.md:201 vs `cli.py:299-353` 真跑 subprocess，仅 `--dry-run` 打印） |
| A7 | agent-pipeline-guide.md 的安全与配置章节 | ❌ 主动误导 | **:318-322 安全方向写反**（称 omni 委托子模块校验；实际 omni 绕过子模块 PathValidator、自持 allowlist，`omni_mcp/server.py:536-541`）；**:332,340 推荐不存在的 `ORF_ALLOWED_DIRECTORIES`**（真实链是 `MCP_ALLOWED_DIRECTORIES`/`ORF_MCP_ALLOWED_DIRS`），与自表 :267 矛盾；**:115,117 握手名错**（真实 `Server()` 名是 `opp-mcp`/`orf-mcp`，`-server` 只是启动命令名） |
| A8 | 模块 API.md 签名 | 🟡 小缺口 | OL `translate_md_text` 漏 `traceparent`/`async_mode`；ORF `apply_md` 漏 `content`（inline text-in/text-out）、行号引用过期；cross-doc 覆盖部分补偿 |

**小结**：agent-user 拿到的**工具清单可信**（这是 doc-truth 门禁的功劳），但拿到的
**行为/配置叙事不可全信**——A6/A7 的四处缺陷全部是散文性声明，恰好落在门禁视野外。

### 3.2 Agent-as-tester 验证框架（scenarios / scripts / 语义 / 治理环）

| # | 基础设施 | 判定 | 证据 |
|---|---|---|---|
| B1 | 场景库（123 个 YAML；tier 109/13/1） | ✅ 有效 | 分布：agent-surface 41、opp 16、orf-md 20、orf-xliff 12、ol 7、pipeline 9、regression 5、red-team 4、recovery 3、traceability 3、agent-interaction 2、perf 1 |
| B2 | 证伪性与锚点纪律 | ✅ 有效 | `run_validation.py --check` 本机实跑 clean；自回声禁令（`omni_mcp/validation/cli.py:147-152`）、锚点必须解析到 STANDARDS.md 标题（:250-260）；抽样 4 场景全部强证伪（`regression/t2-pdf-xliff-guard.yaml:37-39` 精确 stderr + exit 1；`red-team-path-traversal.yaml:55-59` 含 egress 检查 `stdout_not_has: root:x:0:0`；pipeline 场景断言字面数值阈值） |
| B3 | 诚实判定语义 | ✅ 有效 | fallback 激活 → 人质量场景判 `invalid`（`omni_mcp/validation/engine.py:263-293`）；`unconfigured` 独立状态永不计绿；`known_gap` 带 `recheck_by` |
| B4 | 覆盖审计 | ✅ 有效 | 执行级（真 MCP 协议 transport parity，非名字匹配）；**本机 WSL 实跑 41/41 PASS exit 0**，且能报 phantom 场景名（`json-failure-exit`）与 fixture 冻结漂移；CI Gate 2 每次 push 强制（`validation.yml:128-131`） |
| B5 | 运行记录 | 🟡 名不副实 | 1030 个 run 目录中 **89% 是单场景抽查**（MCP spot-check）；`latest.txt` 指向的 20261029-224820 仅含 1 个场景；最近一次全库 run 是 **2026-10-12**（106 场景 0 failed），其 `report.md` 迟了 10 天才生成——本地 director 链最后一环（run→report→人审）断裂 |
| B6 | 回归 diff 工具 | 🟡 半接线 | `validation_diff.py`/`artifact_diff.py`（四类回归检测）**无任何 CI/Makefile/钩子接线**，全靠人记得跑 |
| B7 | 交付机制 | 🟡 低使用度 | `--deliver` → `04-Output/artifacts/deliverables/omni-suite/` 全史仅 2026-08-15 一次（validation-loop-log.md:209）；且 `04-Output/` 在本机不存在 |
| B8 | known-gap 生命周期 | 🟡 过期未摘 | `pipeline-docx-md-docx.yaml:306,446` 两个 `known_gap` 标记（`recheck_by: 2026-11-30`），LOOP-LOG 已于 2026-10-27 记录 GAP CLOSED（LQA 4.85、drawings 2→2），标记未按自身规则摘除 |
| B9 | 治理环（LOOP-LOG） | ✅ 大体遵守 | ~60 条坑、最新 2026-10-27；有真抓真改记录：`ol-capabilities-contract` 抓到 OL#139 角色数漂移并 CI 红（run 39084375604）；T2 种子证明「单测绿/集成红」可被场景抓出。**未遵守处**：10-26..10-29 的 ~140 次抽查未记 loop-event 行（与 89% 单场景噪声一致） |
| B10 | STANDARDS.md（可引用基准） | 🟡 自身漂移 | :97「suite omni_mcp 2 at baseline」（实际 4）；:254「OPP inputs 14」（源真相 16，`doc_inventory` 实读 `get_capabilities.py`）。「可引用的单一基准」文件内含过期数字，且该句还声称数字「来自 live registries，而非过期的 AGENTS.md 表」 |

**小结**：验证框架的**引擎、语义、场景质量是真实且高质量的**；弱在**运行记录的
headline 语义**（latest ≠ 全库）、**diff 工具无自动化**、以及**报告生成步骤的本地执行率**。
「验证循环在持续运行」的表象强于实质——实质是 CI 结构门每日在跑 + 周期性全库 run +
治理环，而非本地 loop 每日全量。

### 3.3 门禁 / hooks / CI

| # | 基础设施 | 判定 | 证据 |
|---|---|---|---|
| C1 | CI 骨干网 | ✅ 有效 | `e2e ci-suite` 全量 `pytest tests/ -m "not nightly"`（e2e-tests.yml:149）是最宽 blocking 网；`validation.yml` Gates 1/2/4 每次 push + 每日 cron；doctor 自 2026-09-17 起 blocking |
| C2 | **e2e 真实 LLM 夜间验证** | ❌ **最大漏洞** | `nightly-llm` job 门控 `github.event_name == 'schedule'`（e2e-tests.yml:199-209），但 `on:` 块（:3-8）**没有 schedule 触发器**——真 LLM 端到端 OPP→OL→ORF 验证无任何自动执行，只能手动 dispatch。自动触发的真 LLM 信号仅剩 fidelity.yml 每周一单文件语料 + validation nightly（密钥缺失时 tier-2 降级 `unconfigured` 不算红，validation.yml:186-189） |
| C3 | lint.yml | 🟡 建立在红基线上 | 65 条 F-class 全树发现被文档化为「永不修复基线」（yml:161-168）——树级卫生永久不设防，只有 delta 门禁；`make lint` 因此永红且 `mypy` 不可达 |
| C4 | pre-commit 11 hooks | ✅ 设计诚实，🟡 本机降级 | 3 个钩子在本机 SKIP：coverage audit 硬编码 `.venv_ol/bin/python`（config:190，Linux venv）；path parity 因 `omni_security` 未装入 `.venv_win`。SKIP 均有可见消息 + CI 兜底（诚实降级非假绿），**但 config:248-249 注释声称的 validation.yml Structural 兜底是假的**（Gate 4 只跑 `tests/contract tests/validation`，validation.yml:143-144） |
| C5 | doc_inventory doc-truth 门禁 | ✅ 有效但**范围有缺口** | 源真相派生（工具数现读 4 个 server 源文件，doc_inventory.py:1176-1196；62 行注册表全自动）；本机实跑 PASS。**缺口**：门禁域 = 「固定文件清单中的数字」——散文/行为声明与清单外文件不在真值域（这是 §3.1/§3.4 全部误导项存活的公共根因，详见 §4.1） |
| C6 | Makefile | 🟡 半瘫痪 | `doctor`/`doc-inventory`/`entry-check`/fidelity/validate 可用；`test*` 目标硬编码 `.venv_ol/bin/python` 本机不可用（Makefile:28）；`make lint` 永红；`make security-scan` 三工具全 `[skip]` 永不可能 fail（:138-140）——纯剧场 |
| C7 | 门禁层维护活跃度 | ✅ | pre-commit 2 commits、workflows 10 commits、validation.yml 近月 6 次调优——在活跃校准期，非死重 |
| C8 | 版本同步链 | 🟡 有空洞 pass 风险 | `sync_version_docs.py` 曾发生「正则零匹配仍报 in sync」事故（:133-139），修复后**仍无 N 行匹配断言**；CI 不直跑，仅靠 lint changed-file 钩子 |
| C9 | 根目录卫生 | 🟡 | tracked 孤儿：`check_opp_orf_tools.py`（零引用）、`PROMPT_OL_TRANSLATE.md`/`PROMPT_OPP_IPYNB.md`（已完成的工作项仍扮开放任务）；untracked `爱上海尔*.md` 同时逃过 gitignore 与 root-sample 守卫（后者只查文档二进制，doc_inventory.py:806-809）；`reports/` 内 5 个 tracked 文件被「先跟踪后忽略」规则夹住 |

**小结**：门禁层**真实且在维护**，骨干网（e2e ci-suite + validation Gates + parity test
+ doctor）确实拦截回归；但**真 LLM 质量维度的自动执行是空的**（C2），树级卫生永久豁免
（C3），且「本地全绿」在 Windows 上是弱保证（C4）。

### 3.4 Skills 与知识层

| # | 基础设施 | 判定 | 证据 |
|---|---|---|---|
| D1 | `omni-docmap`（382 行） | ✅ 最强 skill | B1-B10/D1-D4 与 `doc_inventory.py` 实现对齐；抽检路径全真；Part A 行数准确。小瑕疵：D2 写「37 total」漏 4 个 suite 工具；是 4 份过期 EXPECTATIONS 文档的唯一活指针 |
| D2 | `omni-validation`（78 行） | ✅ 有效 | 最薄最准：所有路径真实，123 计数被门禁冻结（doc_inventory.py:619-624） |
| D3 | `omni-suite`（288 行） | ❌ 双重误导 | :131/:172/:226 指向 **2026-06-22 已删除的 `scripts/mcp_bridge.py`**（:226 还称 "Required for MCP to work"），与自己引用的 ACCEPTED_GAPS.md 更正行（"MECHANISM REMOVED — no bridge is involved"）矛盾；:161 教 agent 用 `orf apply-xliff --force` 做跨格式 XLIFF，与 AGENTS.md:193「Not implemented，--force inert」直接矛盾——照做会产生静默空操作 |
| D4 | `omni-deep-modules`（205 行） | 🟡 | 内容有价值（可测性抽取陷阱守卫）；但其「已知漂移」警告自身已过期（说 OPP 7/ORF 6，实际早已修为 9/7）——提醒别人漂移的文档自己漂移了 |
| D5 | `omni-issue-pr`（330 行） | 🟡 环境锁定 | SOP 有效、状态标注诚实；但硬编码 WSL 路径与 SSH host alias（:26,:68-71,:116），离开本机不可复现 |
| D6 | 验证环 adapter 副本（6 份） | ❌ 漂移实测 | 仅 2 份被门禁（`_SCENARIO_CLAIM_SITES`，doc_inventory.py:619-637）。实测：CLAUDE.md:113 写 120、`.cursorrules:92` 写 119、`Omni_Localizer/src/.hermes/skills/omni-validation/SKILL.md:3` 一句话三个错数字（83 场景/14 inputs/自相矛盾）；omni-docmap 矩阵把 CLAUDE.md 列 🟡 且**从不提 .cursorrules 与两份 .hermes 副本** |
| D7 | `CLAUDE.md` | 🟡 平行第二大脑 | 不是 AGENTS.md 副本，无同步机制；工具表被门禁（对）、场景数没被门禁（错）——**精确展示了门禁边界内外的差别** |
| D8 | docs/ 大部头过期层 | ❌ 约 9,300+ 行 | EXPECTATIONS 四件套 2,515 行（版本头 v0.9.1/v0.4.17/v0.4.0，仅 omni-docmap 可达）、`master-validation-template.md` 4,153 行孤儿（docs/ 最大文档）、3 份审计/交接报告 ~2,650 行 0 引用、`SECURITY_AUDIT.md` 自称 "Living document" 但 2026-06-22 后未动。对比之下 `docs/archive/` 的 Gate-A marker 纪律与 `FINAL_VERDICT.md`/`SUITE_VERDICT.md` 的 HISTORICAL SNAPSHOT 标记是**正确做法的样板**——这批文档只是没走同样的流程 |
| D9 | 知识层外部依赖 | ❌ 多处死指针 | `04-Output/`（本机不存在）；`99-Tools/`（本机存在但 gitignored，6.3GB 机器本地 scratch）；**全局 skill `validation-framework-execution` → `references/validation-run-governance.md`（AGENTS.md:158 标注「开始前必读」，实为不可解析死指针）**；`Hermes-Workspace` 路径（NIGHTLY/HANDOVER 多处，本机不存在） |
| D10 | `omni-docmap/references/` 16 个文件 | ✅（结构性无漂移）| 是 **symlink 非 copy**（gitignored）——零漂移但 fresh clone 为空（omni-suite SKILL.md:267-271 自己承认）；fresh-clone agent 拿到空目录，属已知妥协 |

**小结**：知识层的**核心索引链**（AGENTS.md → PROJECT_STATUS → omni-validation →
ACCEPTED_GAPS → docs/archive 纪律） unusually 自洽；**入口 skill（omni-suite）反而是
最危险的**——一个新 agent 最早加载的 skill 里有两处会直接导致错误行为的指令（D3）。

---

## 4. 三个跨领域根因

### 4.1 「数字门禁」 vs 「行为声明」缺口（最重要的发现）

`doc_inventory.py` 冻结的是：**固定文件清单中的数字**（工具数、场景数、版本、格式数、
行数声明）+ 结构完整性（链接/路径/归档标记）。它不覆盖：

- **行为性声明**：「cli.py is print-only」（假）、「mcp_bridge.py Required」（指向已删文件）、
  「`--force` 可用于跨格式」（假）、「omni 委托子模块做 path 校验」（方向写反）；
- **清单外副本**：`.cursorrules`、两份 `.hermes` skill、CLAUDE.md 的场景数——
  全部在 `_SCENARIO_CLAIM_SITES` / 工具数检查的文件清单之外。

结果是一个精确的模式：**凡是被门禁的数字，131 天 41 工具零漂移；凡在门禁外的声明，
从 2026-06-22 删除 mcp_bridge 到今天仍在被入口 skill 推荐。**这不是执行不力，
是门禁模型的覆盖面定义问题。可选修法：(a) 把行为契约改为**可执行断言**（如
print-only 声明 → 用 `--dry-run` 差分测试冻结进 contract smoke）；(b) 把所有 agent
adapter 文件纳入门禁清单；(c) 对「指向脚本/命令」的声明做存在性 lint（路径引用
完整性检查已有先例，扩展到 scripts/ 即可）。

### 4.2 双环境现实 vs 单环境文档

`.venv_ol` 是 WSL 内创建的 Linux venv（`pyvenv.cfg: home = /home/renanzai/...`），
Windows 侧真实解释器是 `.venv_win`（靠 `scripts/pre_commit_python.sh` 解析）。
后果：AGENTS.md/验证文档的全部流程示例（`source .venv_ol/bin/activate`）在 Windows
主机上不可照做；3 个 pre-commit 钩子降级 SKIP；`make test*` 不可用。基础设施的
**可复现性以 WSL 为隐藏前提**，而文档写成单环境。审计为取得执行级证据也不得不在
WSL 内跑 coverage audit。可选修法：AGENTS.md 加一段「Windows 主机 → 用
`scripts/pre_commit_python.sh` 或进 WSL」的双路径说明（`venv-migration.md` 已有素材）。

### 4.3 headline 指针 vs 长尾噪声

`validation-runs/` 的 89% 是单场景 MCP spot-check（由 `run_validation_scenario` 工具
天然产生），`latest.txt` 因此几乎总指向一个抽查而非全库 run；最近全库 run（10-12）
的报告还迟了 10 天。director 链的「读最新 run → 生成报告 → 人审」在本地实际很少
走通。可选修法：区分 `latest.txt`（任意 run）与 `latest-full.txt`（全库 run），或让
run 元数据标记 `kind: spot-check|full-library`；把 `validation_report.py` 生成步骤接进
Makefile/CI nightly（CI 已有 nightly 调用，本地缺省执行）。

---

## 5. 判定汇总

**✅ 有效（有实跑/CI/代码证据支撑）**
41 工具清单与文档一致性 · 成功包络统一 · path security fail-closed（四服务器）·
123 场景库证伪性与锚点纪律 · 诚实判定语义（unconfigured/invalid/known-gap）·
覆盖审计执行级 41/41（本机 WSL 实跑）· CI 骨干网（e2e ci-suite + validation Gates +
parity test + doctor）· doc_inventory 源真相派生 · 验证治理环 LOOP-LOG ·
bug→regression 飞轮（T2 种子实例）· omni-docmap / omni-validation skill ·
docs/archive marker 纪律 · ACCEPTED_GAPS 更正纪律 · 门禁层维护活跃度

**🟡 部分有效（真实但名不副实 / 半接线 / 本机降级）**
错误包络跨服务器差异 · omni_security「共享」叙事 · ORF 惰性 fail-closed ·
运行记录 headline 语义（latest=抽查）· validation_diff/artifact_diff 无接线 ·
交付机制使用度 · known_gap 标记过期 · STANDARDS.md 自身两处漂移 · lint 红基线 ·
Makefile 半瘫痪 · sync_version_docs 空洞 pass 风险 · 根目录卫生 ·
omni-deep-modules / omni-issue-pr · CLAUDE.md 平行大脑 ·
omni-docmap/references 本地性 · `.venv_ol` 双环境现实

**❌ 无效 / 主动误导（按危害排序）**
1. `agent-pipeline-guide.md:318-322` 安全章节方向写反（agent 会配错安全 env）
2. e2e `nightly-llm` schedule 门控无触发器（真 LLM 质量验证零自动执行）
3. `omni-suite` SKILL.md 的 mcp_bridge 死指针 + `--force` 矛盾指令（入口 skill）
4. `agent-pipeline-guide.md:332,340` 幽灵环境变量 `ORF_ALLOWED_DIRECTORIES`
5. AGENTS.md:201 「cli.py is print-only」假声明（门禁内文件的行为声明）
6. 验证环 4 份未门禁副本的场景数漂移（CLAUDE.md 120 / .cursorrules 119 / .hermes 83）
7. 知识层外部死指针（全局 skill validation-framework-execution 等）
8. ~9,300 行过期 snapshot/孤儿文档占据 docs/ 可达面
9. STANDARDS.md:97/:254 过期数字（「可引用基准」自身）
10. `make security-scan` 纯剧场

---

## 6. 建议（按优先级）

**P0 — 修会直接误导 agent 的项（半天量级）**
1. 改写 `agent-pipeline-guide.md:318-322`（omni 自持 allowlist 的事实）+ 删 :332,340
   幽灵变量 + 修 :115,117 握手名。
2. 删除/改写 `omni-suite` SKILL.md 的 mcp_bridge 段落与 `--force` 指令（与
   ACCEPTED_GAPS.md 对齐）。
3. 修 AGENTS.md:201 print-only 声明（改为「`--dry-run` 为 print-only；默认模式真实执行」）。
4. `e2e-tests.yml` 的 `on:` 补 `schedule:`（与 validation.yml 对齐），或把 nightly-llm
   改为 `workflow_dispatch` 并删掉 schedule 措辞——让文档与触发器一致。

**P1 — 补齐 tester 循环的自动化缺口（1-2 天量级）**
5. 把 `.cursorrules`、两份 `.hermes` skill、CLAUDE.md 场景数纳入 doc_inventory 门禁
   （扩展 `_SCENARIO_CLAIM_SITES`），或将其收敛为指针而非副本。
6. 修 STANDARDS.md:97/:254；摘除已 GAP CLOSED 的 `known_gap` 标记。
7. run 记录降噪：区分 spot-check 与 full-library（`latest-full.txt` 或 run 元数据）；
   让 nightly 自动产出 `validation_report.py` 报告。
8. `validation_diff.py` 接入 Makefile（如 `make validate-diff`）+ LOOP-LOG 模板加一步。

**P2 — 卫生与可持续性**
9. docs/ 清理：EXPECTATIONS 四件套、master-validation-template、handoff/两份审计报告
   移入 `docs/archive/` 并补 marker（仓库已有现成纪律，照做即可）。
10. 删除 tracked 孤儿（`check_opp_orf_tools.py`、`PROMPT_*`、`run_with_env.py`——
    后者已被 aesthetics-review 建议删除）；root-sample 守卫扩到 `.md`。
11. AGENTS.md 补双环境说明（Windows → `pre_commit_python.sh` / WSL）。
12. 修 `.pre-commit-config.yaml:248-249` 的虚假兜底注释；给 `sync_version_docs.py`
    加 N 行匹配断言。

---

## 7. 审计方法备注

- 静态审计 4 路：验证框架（scenarios/scripts/runs/CI）、门禁与 CI（7 workflows +
  pre-commit + Makefile + doc_inventory）、skills 与文档（5 skills + ~60 docs 三态分类 +
  6 份 adapter 对比）、MCP/CLI 消费面（4 registry 逐名核对 + 错误/安全路径追踪）。
- 本机实跑：`doc_inventory.py --check` PASS；`run_validation.py --list`（123 场景枚举）
  与 `--check` PASS；`coverage_audit.py` 于 WSL `.venv_ol` 内 PASS（41/41, exit 0）。
- 局限：未在真实 LLM key 下跑 tier-2；未复核 GitHub Actions 实际运行历史
  （以 workflow 定义与 LOOP-LOG 中的 run 编号为准）；`99-Tools` 内容未审计（gitignored
  机器本地 scratch）。
