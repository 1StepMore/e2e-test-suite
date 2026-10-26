> **Status: ARCHIVED (2026-10-26). Reason: Phase artifact; the director loop supersedes the standalone workflow. Superseded by: `docs/dev/validation-director-loop.md`.**

# Localization QA Workflow
## — Post-Pipeline Check & Polish 指南

基于 MQM (Multidimensional Quality Metrics) 框架，面向 OPP→OL(SG+Glossary+Polish)→ORF 管线的最终 DOCX 产物。

---

## 一、质量维度总览（MQM 7 维）

| 维度 | 定义 | 在我们管线中的表现 | 检查方法 |
|------|------|-------------------|---------|
| **Accuracy** 准确度 | 译文是否忠实传达原文命题内容 | 漏译、增译、误译、数值/专名错 | 源-目标对比抽样 |
| **Terminology** 术语 | 术语是否符合领域/组织标准 | Glossary 命中率、品牌名一致性 | 全文 Term Scan |
| **Linguistic Conventions** 语言规范 | 语法、拼写、标点正确性 | 英文语法/拼写错误 | LLM 通读 + 拼写检查 |
| **Style** 风格 | 是否符合 StyleGuide + 品牌语域 | SG 设置（formal/business）的执行度 | LLM Style Audit |
| **Locale Conventions** 区域惯例 | 数字、日期、货币、单位格式 | en-US/en-GB 混用检查 | 正则扫描 |
| **Audience Appropriateness** 受众适配 | 文化敏感、隐喻是否跨文化有效 | "与狼共舞"类文化翻译失败 | 母语者视角审查 |
| **Design & Markup** 设计与标记 | 格式、图片、排版完整性 | 段落/图片/粗斜体保留度 | 结构对比脚本 |

---

## 二、质量评分模型（简化 MQM）

基于 MQM 的三级严重度 + 加权扣分：

| 等级 | 扣分 | 定义 | 例子 |
|------|------|------|------|
| ❌ **Critical** | -10 | 导致信息严重误导或不可用 | 关键数字翻错、反义翻译、源语残留 |
| 🔴 **Major** | -5 | 明显影响理解或质量 | 术语不一致、语法错误、文化比喻直译失败 |
| 🟡 **Minor** | -1 | 不影响理解但显粗糙 | 冗余表达、轻微Chinglish、大小写不一致 |

**通过阈值**：≥90 分（满分 100，10 个 minor 扣完即不通过）

实践中未必需要严格算分，但分类框架有用。

---

## 三、全流程 6 阶段

```
OPP → OL(SG+Glossary+Polish) → ORF → [LQA 开始]
                                          ↓
               Phase 1  结构完整性         (自动脚本, 分钟级)
               Phase 2  源语残留扫描       (自动脚本, 分钟级)
               Phase 3  术语一致性检查     (半自动, 10-30min)
               Phase 4  语言质量审查       (LLM + 人工, 30-90min)
               Phase 5  Locale 约定检查    (半自动, 5-10min)
               Phase 6  润色修复           (LLM, 重跑 ORF)
                                          ↓
               最终产物交付
```

---

### Phase 1：结构完整性（全自动）

**检查项** | **脚本** | **通过标准**
--- | --- | ---
段落数 | `len(doc.paragraphs)` | 与源 DOCX 完全一致
有内容段落数 | `sum(1 for p in doc.paragraphs if p.text.strip())` | 与源一致
图片数（rels） | 基于 zipfile/r:embed 扫描 | 与源一致（数量 & MD5）
图片顺序 | `r:embed` 顺序跟踪 | 与源一致
Section 标记 | `#46, #48...` | 全部保留
表格结构 | 行数/列数 | 与源一致
粗斜体 | bold/italic run 计数 | 变动 ≤20%（字体系统差异可接受）

**工具**：`e2e-test-suite/scripts/verify_docx.py`

**典型失败模式**：
- `段落数不一致` → ORF apply-xliff 跳段
- `图片数减少` → OPP extract 漏图
- `Section 标记丢失` → XLIFF 里被翻译了

**修复**：出问题先查 OPP→XLIFF，不直接改 DOCX。

---

### Phase 2：源语残留扫描（全自动）

**检查容器** | **扫描方法**
--- | ---
正文段落 | `w:t` 元素正则匹配 CJK
文本框 | `w:txbxContent` XML 扫描
页眉/页脚 | `doc.sections[].header/footer`
图片描述 | `pic:cNvPr@descr`
批注 | `w:comment`（如有）

**示例脚本**：

```python
from docx import Document; from docx.oxml.ns import qn; import re
d = Document("result.docx")
texts = [e.text for e in d.element.findall('.//' + qn('w:t')) if e.text]
zh_chars = sum(len(c) for c in re.findall(r'[\u4e00-\u9fff]{2,}', ' '.join(texts)))
print(f"ZH residual: {zh_chars} chars")
```

**通过标准**：0 残留字符（品牌名嵌入例外，如"海纳云"作为 HisenseHainayun 的一个片段不足为患）

**典型问题**：
- `TextBox 残留中文` → OPP extract 时 TextBox 内容未提取，XLIFF 里仍是中文
- `图片描述未翻译` → OPP extract 漏了 `pic:cNvPr@descr`

---

### Phase 3：术语一致性（半自动）

**步骤**：

```
1. 从 Glossary JSON 加载术语表
2. 建立 [{中文词, 标准译文}] 映射
3. 在 DOCX 全文扫描：
   a. 中文词是否不该出现（应已翻译）
   b. 标准译文是否一致出现
   c. 是否出现了非标准变体
4. 报告偏离
```

**检查重点**：

| 类别 | 典型术语 | 常见问题 |
|------|---------|---------|
| 品牌名 | 三翼鸟→Sanyiniao, 卡萨帝→Casarte | 拼写变体、译名不一 |
| 战略术语 | 创牌→brand-building, 三位一体→three-in-one | 上下文变体（trinity vs three-in-one） |
| 产品术语 | 滚筒→drum, 波轮→pulsator, 朗境→Lanjing | 引擎直译（drum→roller, pulsator→impeller） |
| 数字 | 292亿→29.2 billion | 换算错误、单位缺失 |

**格式检查**：
- 数字格式：千分位、小数点（comma vs period）
- 货币单位：RMB vs CNY vs ¥ → 统一
- 单位：cm vs 厘米，kg vs 磅（target locale 决定）

---

### Phase 4：语言质量审查（LLM 辅助）

**适合的问题类别**：

| 子维度 | 检查内容 | LLM 指令要点 |
|--------|---------|-------------|
| **Fluency** | 语法、搭配、冠词/介词 | "Check for grammatical errors and unnatural collocations in this English text" |
| **Style** | 语域是否匹配 SG（formal/business） | "Does the tone match a formal business publication?" |
| **Chinglish** | 字面直译、冗余修饰 | "Identify unnatural phrasing typical of direct Chinese-to-English translation" |
| **Cultural** | 隐喻/典故是否跨文化有效 | "Would a native English reader understand this reference?" |
| **Consistency** | 同类概念是否统一处理 | "Are recurring concepts translated consistently?" |

**操作模式**：

```
for 每 50 段落（约 2000-3000 字）:
    LLM 审查 → 结构化报告:
      段落范围 | 问题类型 | 严重度 | 建议修复 | 置信度
    Agent 汇总 → 排序（critical → minor）
```

**不需要**逐句审查。抽样 20-30% + 聚焦高风险段落（专名密集段、数字段、文化段）即可。

---

### Phase 5：Locale 约定检查

**针对目标语言市场(en-US)**:

| 检查项 | 规则 | 扫描方法 |
|--------|------|---------|
| 日期格式 | en-US: M/D/YYYY; en-GB: D/M/YYYY | 正则 `\d{1,2}/\d{1,2}/\d{4}` |
| 千分位 | en-US: 1,000.00 vs en-GB: 1.000,00 | 正则 `\d{1,3}(,\d{3})*` |
| 货币 | $ = USD, € = EUR, RMB/CNY | 统一写法 |
| 单位 | 米→meters, 寸→inches（文化适配） | 术语表映射 |

**常见问题**：中文用"万"=10,000 → 英文直接写 10,000（不是"10 thousand"的完整写法问题）

---

### Phase 6：润色修复

**策略**：按严重度分类处理

```
Critical / Major → 必须修
      └─ 直接在 DOCX 中定位修复（python-docx）
      └─ 如果是体系问题 → 更新 Glossary/SG → 重跑管线
Minor → 批量修
      └─ LLM polish pass（输入上下文段落 + 润色指令）
      └─ 逐段替换跑 ORF apply-xliff（如果源头在XLIFF）
```

**修复纪律**（来自 code profile 的 Karpathy 指南）：
- 只改有问题的那句，不"顺手优化"相邻文本
- 每次改完验证：改前→改后 diff 只含目标改动
- 如果 3 次修改还没解决 → 退一步看是不是体系问题

---

## 四、本管线特有的陷阱与缓解

| 陷阱 | 现象 | 原因 | 缓解 |
|------|------|------|------|
| **廖误信号** | 中文残留扫描发现少量汉字 | 品牌名/书名在正文中自然出现（如"海纳云"） | 检查前排除 Brand Name List |
| **术语上下文变体** | 相同中文在不同段落被译不同（trinity vs three-in-one） | LLM 逐段翻译无全局上下文 | --polish pass + Glossary 强制匹配 |
| **SG 未生效** | 多份文档风格不一致 | SG 由 profile-doc 自动生成，每份不同 | 对系列文档手动校准 SG |
| **图片描述未译** | 无障碍文本仍是中文 | OPP extract 容器覆盖不全 | 检查 OPP extract 覆盖的 XLIFF 源 |
| **TextBox 漏译** | TextBox 文字保持中文 | OPP 未提取 TextBox 内容 | OPP 加 TextBox 提取（如缺失则补） |
| **方向反转** | en→zh 出拉丁字符，zh→en 出中文 | -s/-t 未传或传反 | Phase 2 源语残留扫描直接捕获 |

---

## 五、检查清单速查表（可打印）

### 自动化检查（Phase 1-2）

- [ ] Phase 1: 段落数匹配
- [ ] Phase 1: 图片数匹配
- [ ] Phase 1: 图片内容（MD5）一致
- [ ] Phase 1: Section 标记保留
- [ ] Phase 2: 正文无源语字符
- [ ] Phase 2: TextBox 无源语字符
- [ ] Phase 2: 页眉/页脚无源语字符
- [ ] Phase 2: 图片描述无源语字符

### 人工/半自动检查（Phase 3-5）

- [ ] Phase 3: 品牌名一致性
- [ ] Phase 3: 战略术语一致性
- [ ] Phase 3: 产品术语 Glossary 命中
- [ ] Phase 3: 数字换算无错误
- [ ] Phase 4: 无语法/拼写错误
- [ ] Phase 4: 风格符合 SG
- [ ] Phase 4: 无 Chinglish
- [ ] Phase 4: 文化隐喻有效
- [ ] Phase 5: 日期格式正确
- [ ] Phase 5: 货币单位统一

### 修复

- [ ] Phase 6: Critical/Major 全部修复
- [ ] Phase 6: Minor 按需修复
- [ ] Phase 6: 每次修完验证 diff
- [ ] Phase 6: 体系性问题已开 Issue

---

## 六、每次质检后的决策框架

```
是否有 Critical 错误？
  ├─ Yes → ❌ 不交付，修复后再跑全流程
  └─ No → 看 Major 错误数
            ├─ 0-2 个 → ✅ 可交付（修完 major）
            ├─ 3-5 个 → ⚠️ 条件交付（列明已知问题）
            └─ >5 个 → ❌ 不交付，体系整改
```

对于经常出同一类问题（如 TextBox 总漏译），不开单个 Issue 而是开体系 Issue（第 1 层 / 第 2 层 / 第 3 层分析）。

---

## 七、与现有技能/工具的集成

| 已有资源 | 对应阶段 |
|---------|---------|
| `e2e-test-suite/scripts/verify_docx.py` | Phase 1 结构检查 |
| `docx-quality-verification.md` | Phase 1-2 参考 |
| `translation-quality-gap-analysis.md` | 决策前分类 |
| OL `--polish` | Phase 6 批量润色 |
| OL `--glossary` | Phase 3 术语强制 |
| OL `--styleguide` | Phase 4 风格保障 |
