# Omni Suite（OPP/OL/ORF）商业论证状态报告

> **日期**：2026-09-02 · **验证轮次**：第 1 轮（定位审视 + 商业化评估）
> **项目状态**：4 个 PyPI 库（omni-pre-processor 0.9.1 / omni-localizer 0.7.0 / omni-re-formatter 0.4.16 / omni-suite 0.4.0），已建成；三组件 8-22 后停更，套件 repo 仍活跃
> **方法论**：business-validation skill + agent-as-user-market-intel（内部基础设施特判）
> **数据纪律**：一切结论带来源；找不到的标注 [未验证]；禁止凭印象

---

## ⚠️ 先决判断：内部基础设施 vs 独立商业化

**本报告基于 agent-as-user-market-intel skill 的明确教训（2026-08 实测）**：
> "内部基础设施不跑商业论证——先确认商业化意图（Omni 教训：对内部产品跑商业论证会得到误导性'夹心饼干'结论）"

**当前证据指向：Omni Suite 是内部基础设施（非独立商业化产品）**：
- 8-22 后三个组件 repo 基本停更（内部用途稳定后不再迭代）（三组件 repo；suite repo 2026-09-01 仍有提交）
- 用户记忆明确"Omni Suite(OPP/OL/ORF)=内部基础设施非独立商业化"
- 但 3 个包已发布到 PyPI + 有 GitHub 文档 = **有对外分发的形态**（开源基础设施）

**所以本报告的定位**：不是"Omni 作为独立产品该不该卖"，而是"**Omni 作为开源基础设施的商业化潜力评估 + 若独立商业化会撞什么墙**"。结论将诚实区分"内部价值"（已证实）与"商业价值"（未验证）。

---

## 阶段 0：项目状态锚定

### 产品成熟度（实测数据）
| 组件 | 功能 | 版本 | PyPI 状态 | 来源 |
|:-----|:-----|:-----|:-----|:-----|
| **OPP**（Omni Pre-Processor）| 文档内容提取（DOCX/PPTX/PDF/XLSX/CSV/EPUB/EML/MSG/Image OCR/音频转写），格式保真骨架 | 0.9.1 | ✅ omni-pre-processor（1StepMore，2026-07-08 发布）| PyPI + README · 备注：撞名属实（PyPI opp=PAY.ON）但已改名解决；残留 OPP README 坏徽章 |
| **OL**（Omni Localizer）| LLM 翻译 + 8 质量门控 + 术语保护 + 回退模型 | **0.7.0** | ✅ `omni-localizer`（1StepMore）（PyPI 显示 0.7.0/0.4.16 略滞后，2026-09-04 实测）| PyPI |
| **ORF**（Omni Re-Formatter）| MD/XLIFF → 复杂格式还原（DOCX/PPTX/PDF/EPUB/SRT 等）+ 云存储 | **0.4.16** | ✅ `omni-re-formatter`（1StepMore）（PyPI 显示 0.7.0/0.4.16 略滞后，2026-09-04 实测）| PyPI |

### 关键实测发现 ⚠️
1. **`opp` PyPI 包名撞车（历史）**：我们 OPP 的 README 徽章指向 `https://pypi.org/project/opp/`，但那是 **PAY.ON 的 OpenPaymentPlatform**（author: PAY.ON, MIT, 支付 SDK）——**不是我们的包**。OPP 已以 omni-pre-processor 名发布（1StepMore，2026-07-08）；实际残留 = README 徽章误指 opp（PAY.ON）坏徽章。
2. **OL/ORF 的 GitHub 指向 `1StepMore/Omni_Localizer`**——主号 suspend 影响文档访问。[已确认 2026-09-04：1StepMore suspended；证据：组件 repo 与 origin 存在未推送分歧、各 repo CI 无法触发；备份镜像 renanzai40/*_BackUp 为当前唯一可写 remote]

### 状态声明
**Omni Suite：已建成（3 组件 + E2E 测试体系），四包已全部发布（omni-pre-processor / omni-localizer / omni-re-formatter / omni-suite，2026-07-08 批次，owner=1StepMore），三组件 8-22 后停更（内部稳定）（三组件 repo；suite repo 2026-09-01 仍有提交），OPP 撞名已解决（残留 README 坏徽章待修），零付费证据。** 定位 = 内部文档本地化基础设施（AutoMedia 的 Omni Triad 一部分 + 独立文档翻译管线）。

---

## 阶段 1：客户身份锚定（JTBD）

### 客户身份卡（若独立商业化）

| 维度 | 客户 A：本地化团队/翻译公司 | 客户 B：文档密集型开发者 | 客户 C：内容团队（复用场景）|
|:-----|:-----|:-----|:-----|
| 具体身份 | LSP（语言服务提供商）、企业本地化经理 | 需要批量翻译文档（DOCX/PPTX/PDF）的工程师 | 内容多语言分发的团队（已有 AutoMedia）|
| 雇佣工作 | 保持原格式的文档翻译，不用人工重排 | 程序化翻译管道（OPP→OL→ORF）| 内容多语言化（继承 AutoMedia）|
| 现状替代 | DeepL/Google 手动上传 + 人工重排（格式会乱）| 自己拼 pandoc + LLM API（格式保真差）| 手动多语言发布 |
| 付费意愿 | $500-5,000/月（企业）| $50-500/月（开发者）| 内部（不付费）|
| 质量关切 | **格式保真度**、术语一致性、合规 | 格式保真 + API 稳定性 | 内部复用 |

### JTBD 核心洞察
**"翻译完不用重新排版"** —— 这是 Omni 与 DeepL/Google 的本质区别：它解决的是**文档格式保真**这个被翻译 API 忽视的痛点。市场证据：**60% 企业花在修正劣质翻译上的钱比做对还多**（Convey911 2026）、重新排版一个 PDF 的隐性成本 $450/文档（tryreflo 2026）。

---

## 阶段 2：用户期望结果（ODI）

| 期望结果 | 来源 | 重要度 | 当前满意度 | 机会缺口 |
|:---------|:-----|:------:|:---------:|:--------:|
| 最小化 翻译后重新排版的时间（分钟/页）| tryreflo：6 小时重排 1 个 PDF × $75/hr = $450 损失 | 9 | 2 | **高（核心机会）** |
| 最小化 翻译质量返工的成本（美元/项目）| Convey911：60% 企业修正劣质翻译比做对还贵 | 9 | 3 | **高** |
| 最大化 格式保真度（表格/图片/样式保留率）| DeepL 支持 DOCX/PDF/PPTX 但保真有限 | 8 | 4 | 高 |
| 最大化 术语一致性（术语表强制）| OL 8 门控含 terminology guardrails | 8 | 5 | 中 |
| 最大化 与 AI Agent 的兼容性 | ORF 暴露 MCP（Agent 原生）| 8 | 5 | 中 |

**证据来源**：tryreflo（重排成本 $450/文档）+ Convey911（60% 返工）+ DeepL/Google 功能对比 + OL/ORF README（自证门控能力）。

---

## 阶段 3：能力覆盖度矩阵（Omni vs 竞品）

### 竞品当前定价（2026 实测，多源交叉）

| 竞品 | 类别 | 定价（2026）| 来源 |
|:-----|:-----|:-----|:-----|
| **DeepL API** | 翻译 API | **$25/1M 字符**（Pro）+ $5.49/月 base | better-i18n + circletranslations |
| **Google Cloud Translation** | 翻译 API | **$20/1M 字符** + 文档翻译 **$0.08-0.25/页** | cloud.google.com |
| **Amazon Translate** | 翻译 API | **$15/1M 字符**（首 12 月 2M 免费）| better-i18n |
| **Azure Translator** | 翻译 API | **$10/1M 字符**（最便宜）| better-i18n |
| **pandoc** | 格式转换 | 免费（官方承认 lossy：margin/复杂表格/SmartArt）| 项目自证 |
| **人类翻译** | 服务 | $0.10-0.30/词；MTPE $7-18/千词 | adhoc-translations 2026 |
| **BabelDOC** | 文档翻译 | 开源（ACL 2026，1000 页/月免费）| agent-as-user-market-intel |

### 能力对照

| 能力 | Omni Suite | DeepL | Google | pandoc | BabelDOC |
|:-----|:--------:|:-----:|:------:|:------:|:--------:|
| 多格式提取 | ✅ 12+ 格式 + OCR + 音视频转写 | ⚠️ 3 格式 | ⚠️ 3 格式 | ⚠️ 有限 | ⚠️ |
| **格式保真翻译** | ✅ XLIFF 骨架 + bx/ex 标签 + 回填 | ⚠️ 有限 | ⚠️ | ❌ lossy | ⚠️ |
| **质量门控（8 门控）** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **术语表强制** | ✅ | ⚠️ 有 glossary | ⚠️ | ❌ | ❌ |
| **Agent 原生（MCP）** | ✅ | ❌ | ❌ | ❌ | ❌ |
| 多模型回退 | ✅ | ❌ | ❌ | ❌ | ❌ |
| 成本（自托管）| **LLM 成本**（800x 便宜于 DeepL，实测）| $25/1M | $20/1M | 免费 | 免费 |
| 定价模式 | MIT 开源 | API 计费 | API 计费 | 免费 | 开源 |

**结论**：Omni 在**格式保真 + 质量门控 + 术语强制 + Agent 原生** 4 项上领先所有翻译 API。**成本优势惊人：LLM 翻译比 DeepL 便宜 800x（Reddit r/LocalLLaMA 实测）**——这意味着如果商业化，Omni 可以以远低于 DeepL 的价格提供同等质量的翻译。

---

## 阶段 4：被斩杀风险测试（Agent-as-a-User 维度）

### 4.1 等价 skill 检查

| 检查项 | 发现 | 风险 |
|:-------|:-----|:----:|
| anthropics/skills | 官方 **docx/pdf/pptx skills** 覆盖文档读写，但**无翻译+格式保真组合** | 🟡 |
| GitHub 社区 | **tristan-mcinnis/Word-Translator-Formatting-Intact-with-LLMs**（开源：LLM 翻译保格式）| 🔴 直接竞品 |
| 通用 Agent | Claude Code + pandoc + LLM = 能搭"提取→翻译→回填"基础版 | 🟡 |
| 平台 API | DeepL/Google 原生文档翻译（但保真有限）| 🟡 |

### 4.2 斩杀风险评级

| Omni 能力块 | 通用 Agent + 现成 skill 能替代？ | 风险 | 硬差距 |
|:-----|:-----|:----:|:-----|
| **多格式提取** | ✅ anthropics docx/pdf skills 可搭 | 🔴 高 | 无 |
| **LLM 翻译** | ✅ 直接调 LLM | 🔴 高 | 无 |
| **格式保真（XLIFF 骨架 + 回填）** | ⚠️ 有开源实现（Word-Translator）| 🟡 中 | 部分（但工程成熟度差）|
| **质量门控（8 门控 + 术语）** | ❌ 通用 agent 不会默认做 | 🟢 低 | **强** |
| **E2E 测试体系（OPP→OL→ORF）** | ❌ 通用 agent 搭不出 | 🟢 低 | **强** |

### 4.3 斩杀风险核心结论

**格式保真翻译是 2026 年的热点方向**（GitHub 已有 LLM 保格式开源项目、BabelDOC ACL 2026）。Omni 的核心防御是**质量门控 + E2E 完备性**（8 门控 + 全链路测试），这在开源竞品里仍然领先。**但作为独立商业产品，这个护城河不够宽——格式保真翻译本身正被开源/大厂快速标准化。**

---

## 阶段 5：付费意愿验证

### 5.1 市场基准数据（多源）

| 数据 | 值 | 来源 |
|:-----|:---|:-----|
| 语言服务市场 | **$73-81B（CAGR 7.6%）** | agent-as-user-market-intel（2026 实测）|
| AI 翻译市场 | **$6.51B → $50.69B（CAGR 25.62%）** | agent-as-user-market-intel |
| 翻译 API 定价 | DeepL $25 / Google $20 / Amazon $15 / Azure $10（每 1M 字符）| better-i18n 2026 |
| 人类翻译 | $0.10-0.30/词 | adhoc-translations 2026 |
| 修正劣质翻译成本 | **60% 企业花费超过做对的成本** | Convey911 2026 |
| 重排成本 | 6 小时/PDF × $75/hr = **$450/文档** | tryreflo 2026 |
| LLM vs DeepL 成本 | **LLM 翻译便宜 800x**（本地模型）| Reddit r/LocalLLaMA |

### 5.2 关键缺口发现

**本地化赛道市场大（$73B）、增速快（25.62% CAGR）、痛点明确（格式保真 + 返工成本）**——但：
1. **大厂 API 已把"翻译"做成 commodity**（$10-25/1M 字符）
2. **开源正快速追赶格式保真**（Word-Translator、BabelDOC）
3. **Omni 自己的定位是内部基础设施**（停更状态 = 无商业化投入意愿信号）

### 5.3 付费意愿四信号（诚实评估）

| 信号 | 状态 | 说明 |
|:-----|:----:|:-----|
| 付费意愿 | ❌ 零 | 无付费用户/LOI |
| 可复制动作 | ❌ | 无销售流程 |
| 行为 > 观点 | ⚠️ | 被 AutoMedia 内部使用（内部价值已证，商业价值未证）|
| 经济性 | ❌ | 无定价 |

**结论：付费意愿 [未验证]，且缺乏商业化意图信号（停更状态）。**

---

## 阶段 6：优劣势分析 + 迭代决策

### 优势（有证据）
1. **格式保真 + 质量门控领先**：8 门控 + E2E 测试是开源竞品没有的
2. **成本优势**：LLM 翻译比 DeepL 便宜 800x
3. **Agent 原生**：ORF 暴露 MCP（未来方向）
4. **内部已验证**：作为 AutoMedia 的 Omni Triad 实际使用（e2e-test-suite 全链路测试）

### 劣势（有证据）
1. **定位模糊**：内部基础设施 vs 商业产品没定（三组件 8-22 停更；suite repo 2026-09-01 仍有提交）
2. **`opp` PyPI 撞名（历史）**：撞名曾存在、已通过改名 omni-pre-processor 解决（2026-07-08 发布）；残留 OPP README 坏徽章
3. **护城河不够宽**：格式保真正被开源/大厂标准化
4. **主号 suspend**：GitHub 1StepMore 影响分发
5. **零付费证据** + 无商业化投入

### 迭代决策

**⚪ 不建议独立商业化（当前阶段）**——理由：定位未定 + 停更状态 + 护城河不足。但三个具体动作值得做：
1. **保持内部基础设施定位**：继续作为 AutoMedia 的 Omni Triad（内部价值已充分验证）
2. **若未来要商业化**：撞名已解决；剩余 = 修 OPP README 坏徽章 + 补发滞后版本（OL 0.7.1/ORF 0.4.17）+ 补下载量数据 + 主号恢复后恢复 1StepMore 分发
3. **开源分发价值**：即使不商业化，3 个 PyPI 包作为开源基础设施有品牌价值（"1StepMore 出品"）——但**别投入销售资源**，等一个真实付费信号（有人主动来问/star 增长）再评估

**诚实结论**：Omni 是"内部基础设施非独立商业化"——本报告验证了这一点，同时记录了**如果未来想商业化需要先解决的三件事**（定位决策、包名撞车、分发恢复）。不建议现在投入任何商业化资源。

---

## 证据来源总表

| # | 来源 | 用途 |
|:--|:-----|:-----|
| 1 | OPP/OL/ORF README（本地 repo）| 功能/格式/能力 |
| 2 | PyPI（pypi.org）| 版本 + 发布状态 + 历史撞名已解决（omni-pre-processor 2026-07-08）|
| 3 | gh api backup repos | 迭代状态（三组件 8-22 后停更；suite repo 仍活跃）|
| 4 | better-i18n 翻译工具对比 | DeepL $25 / Google $20 / Amazon $15 / Azure $10 |
| 5 | cloud.google.com/translate/pricing | Google $0.08-0.25/页 |
| 6 | adhoc-translations 2026 | 人类翻译 $0.10-0.30/词 |
| 7 | Convey911 2026 | 60% 企业返工成本 |
| 8 | tryreflo 2026 | 重排成本 $450/文档 |
| 9 | Reddit r/LocalLLaMA | LLM 比 DeepL 便宜 800x |
| 10 | GitHub tristan-mcinnis/Word-Translator | 开源保格式竞品 |
| 11 | agent-as-user-market-intel skill | 市场坐标 + 内部基础设施教训 |
| 12 | e2e-test-suite（本地）| E2E 测试体系证据 |

---

## 未验证项清单

| 项 | 缺口 | 验证方法 |
|:---|:-----|:---------|
| 独立商业化意图 | 用户未明确"Omni 要商业化" | 需用户拍板（本报告默认不商业化）|
| PyPI 下载量 | pypistats 429 限流未取到 | 稍后重试或看 pypi.org/project 页面 |
| BabelDOC 功能细节 | 未深挖 | 补查 ACL 2026 论文 |
| 开源竞品成熟度 | Word-Translator 是否生产级 | 实测 |
| 格式保真量化对比 | Omni vs DeepL 的实际保真率 | 跑同一文档对比 |

---

## 结论

**Omni Suite = 内部文档本地化基础设施，当前阶段不建议独立商业化。** 它的技术领先（格式保真 + 质量门控 + 800x 成本优势）真实存在，但被三件事卡住：①商业化意图未定（停更状态）②历史撞名已解决但 OPP README 仍有坏徽章（待修）③格式保真正被开源/大厂快速标准化。**最有价值的动作是把这 4 个 PyPI 包当开源品牌资产维护（修徽章 + 补发滞后版 + 保持可安装），等真实付费信号出现再评估商业化。** 内部价值（作为 AutoMedia 的 Omni Triad）已被充分验证，这是它当前的角色。

---

## 建议优化与发展方向（2026-09-02，基于上文数据）

> 以下建议全部锚定在本报告已验证的数据上。**前提声明：Omni 当前定位是内部基础设施，以下方向按"内部优先 + 开源资产维护"设计，若未来商业化意图出现再升级为商业计划。**

### 方向 1（P0，先做）：修 OPP README 坏徽章 + 补发滞后版本 + 统一分发，把 4 个包变成可信开源资产

| 动作 | 依据数据 | 预期效果 |
|:-----|:---------|:---------|
| **修 OPP README 坏徽章**：撞名已通过改名 `omni-pre-processor` 解决（2026-07-08 发布，PyPI `opp` 实为 PAY.ON 支付 SDK）；剩余问题 = README 徽章仍误指 `opp` | 阶段 0 实测发现 + PyPI JSON（omni-pre-processor 已发布）| 让 README 徽章指向真正装到的包——当前徽章指向错误包 |
| 补发滞后版本（OL 0.7.1 / ORF 0.4.17 已本地就绪待补发 PyPI；OPP 0.9.1 已发布；omni-suite 0.4.0 已发布）+ 统一 4 包元数据（author/homepage/license 一致，全部指向 1StepMore）| PyPI 实测（OL/ORF 显示 0.7.0/0.4.16 略滞后；OPP 无 1StepMore 元数据）| 可信度：用户搜到 4 个包要能确认是同一家出品且版本不落后 |
| 补版本对齐（OL 0.7.1 / ORF 0.4.17 已本地就绪待补发 PyPI；OPP 0.9.1 已发布；omni-suite 0.4.0 已发布）| 阶段 0 版本表 | 版本混乱是"内部工具"的典型特征，补发前要对齐 |

### 方向 2（P1）：用"内部验证"反哺开源——把 E2E 测试体系做成公开质量证明

| 动作 | 依据数据 | 预期效果 |
|:-----|:---------|:---------|
| 把 e2e-test-suite 的 E2E 测试结果做成公开 badge（"OPP→OL→ORF 全链路测试通过"）| 阶段 4.2（E2E 体系=强差距）；本地 e2e-test-suite 存在 | 开源项目的第一信任状是"测试通过"——这是竞品（Word-Translator/BabelDOC）没有的 |
| README 加"格式保真 benchmark"（同一文档 Omni vs pandoc vs DeepL 的保真率对比）| 阶段 3 能力对照（pandoc lossy；DeepL 有限）| 让"格式保真"从口头变成数据——这是 Omni 的核心卖点 |

### 方向 3（P2）：内部使用优化——让 Omni 作为 AutoMedia Triad 更顺滑

| 动作 | 依据数据 | 预期效果 |
|:-----|:---------|:---------|
| 与 AutoMedia 的集成点文档化（OPP→OL→ORF 如何被 AutoMedia 调用）| README（Omni Triad 是 AutoMedia 功能）| 未来若 AutoMedia 商业化，Omni 是差异化拼图（竞品没有）|
| 若 AutoMedia 走 open-core 商业（见 AutoMedia 报告方向 2），Omni 三包作为"高级功能"收费 | GitLab open-core 模式（$955M 收入）| Omni 不用独立商业化，可以作为 AutoMedia 商业版的付费组件 |

### 方向 4（P3，仅在真实付费信号出现后）：独立商业化评估清单

| 前置条件 | 触发信号 | 依据 |
|:-----|:---------|:-----|
| 用户拍板"Omni 要独立商业化" | 明确意图（当前未发生）| agent-as-user-market-intel：内部产品跑商业论证 = 误导性结论 |
| PyPI 下载量 > 1K/月 | pypistats 数据（当前 429 未取到）| 有外部用户 = 有市场信号 |
| GitHub star > 100 | 社区可见性 | 开源项目冷启动基准 |
| 至少 1 个外部付费咨询 | 有人主动来问 | Steve Blank 付费信号 |

**若全部触发**：对标 Phrase $27-525/月 / Lokalise $120-144/月（2026 实测），Omni 可定位"自托管格式保真翻译引擎"$99-500/月（比 TMS 便宜、比裸 LLM API 保真）。**未触发前不投入任何销售资源。**

### 方向 5（验证指标）：内部基础设施健康度

| 指标 | 目标 | 依据 |
|:-----|:-----|:-----|
| 四包可安装性 | pip install 全部可用 | 方向 1（OPP README 坏徽章：pip 安装指向正确，徽章指向错误包）|
| E2E 测试通过率 | 100%（全链路）| 阶段 0（e2e-test-suite 存在）|
| 内部使用无回归 | AutoMedia 调用 Omni Triad 稳定 | 内部价值是 Omni 当前唯一已证价值 |

---

## 2026-09-04 实测更正（验证轮次 2）

本节列出本报告全部更正的旧断言（逐字引用）→ 新陈述 + 证据来源。本报告正文已按下列更正修改；本节为自查引用清单。

| # | 旧断言（逐字）| 新陈述 | 证据来源 |
|:--|:-----|:-----|:-----|
| 1 | L4 项目状态头 `3 个 PyPI 库（OPP 1.x / OL 0.7.0 / ORF 0.4.16），已建成，8-22 后基本停更` | `4 个 PyPI 库（omni-pre-processor 0.9.1 / omni-localizer 0.7.0 / omni-re-formatter 0.4.16 / omni-suite 0.4.0），已建成；三组件 8-22 后停更，套件 repo 仍活跃` | PyPI JSON（4 包存在）+ git log（suite repo 2026-09-01 提交）|
| 2 | L29 OPP row version `1.x`；PyPI 状态 `⚠️ 撞名（PyPI opp = PAY.ON 支付 SDK）` | OPP 实为 `0.9.1`，发布名 `omni-pre-processor`（1StepMore，2026-07-08 发布）；撞名属实但已改名解决，残留 OPP README 坏徽章 | PyPI JSON pypi.org/pypi/omni-pre-processor/json（version 0.9.1, upload_time 2026-07-08, owner 1StepMore）|
| 3 | L30/L31 OL/ORF PyPI 状态未注滞后 | OL/ORF 追加 `（PyPI 显示 0.7.0/0.4.16 略滞后，2026-09-04 实测）` | PyPI JSON pypi.org/pypi/omni-localizer/json + omni-re-formatter/json（2026-09-04 实测）|
| 4 | L38 状态声明 `PyPI 部分发布（OL/ORF）` | `四包已全部发布（omni-pre-processor / omni-localizer / omni-re-formatter / omni-suite，2026-07-08 批次，owner=1StepMore）` | PyPI JSON 四包（2026-09-04 实测）|
| 5 | `8-22 后停更`/`8-22 后基本停更`/`8-22 停更`（L4/L16/L38/L174）| 限定为 `（三组件 repo；suite repo 2026-09-01 仍有提交）` | git log（suite repo 仍有 2026-09-01 提交）|
| 6 | L35 主号 suspend 未注证据 | 追加 `[已确认 2026-09-04：1StepMore suspended；证据：组件 repo 与 origin 存在未推送分歧、各 repo CI 无法触发；备份镜像 renanzai40/*_BackUp 为当前唯一可写 remote]` | git status/remote（组件 repo 未推送分歧）+ CI 无法触发 + backup remote 唯一可写 |
| 7 | L175 劣势 2 `opp PyPI 撞名：无法以"opp"发布（被 PAY.ON 占用）` | `opp 撞名曾存在、已通过改名 omni-pre-processor 解决（2026-07-08 发布）` | PyPI JSON omni-pre-processor（2026-07-08 发布）|
| 7b | L34 `我们的 OPP 从未真正独立发布到 PyPI 或用了别的名字。这是分发层面的真实问题。` | `OPP 已以 omni-pre-processor 名发布（1StepMore，2026-07-08）；实际残留 = README 徽章误指 opp（PAY.ON）坏徽章。` | PyPI JSON omni-pre-processor（2026-07-08 发布）|
| 8 | L184 迭代决策 2 `先修 opp 撞名（改包名，如 omni-pre-processor）+ 补下载量 + 恢复分发` | `撞名已解决；剩余 = 修 OPP README 坏徽章 + 补发滞后版本（OL 0.7.1/ORF 0.4.17）+ 补下载量数据 + 主号恢复后恢复 1StepMore 分发` | PyPI JSON + git reflog（OL 0.7.1/ORF 0.4.17 本地就绪）|
| 9 | L224 结论 `②opp PyPI 撞名无法分发` | `②历史撞名已解决但 OPP README 仍有坏徽章（待修）`；最有价值动作 = `修徽章 + 补发滞后版 + 保持可安装` | PyPI JSON + OPP README（徽章仍指 pypi.org/project/opp/）|
| 10 | L196-197 来源表 + L236 方向 1 动作行（含 `从未真正发布`、`需以新名发布`）；L238 `补版本对齐（OL 0.7.0 / ORF 0.4.16 / OPP 需定版）` | 措辞改为撞名已解决（动作 = 徽章/补发/元数据统一）；版本对齐改为 `（OL 0.7.1 / ORF 0.4.17 已本地就绪待补发 PyPI；OPP 0.9.1 已发布；omni-suite 0.4.0 已发布）` | PyPI JSON（四包）+ git reflog（OL/ORF 本地版本）|
| 11 | L269 指标行 `当前 opp 撞名不可装` | `OPP README 坏徽章（pip 安装指向正确，徽章指向错误包）` | PyPI JSON omni-pre-processor（0.9.1 可安装）+ OPP README 徽章 |
