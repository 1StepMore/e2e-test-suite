> **Status: ARCHIVED (2026-10-26). Reason: Phase artifact; the director loop supersedes the standalone workflow. Superseded by: `docs/dev/validation-director-loop.md`.**

# Agent 协作质检工作流
## — 体系外维度的质量控制

当 OPP→OL(SG+Glossary+Polish)→ORF 管线产出 result.docx 后，Agent 作为质检环节接管以下四个管线内无法或难以保障的维度：

---

## 总览

```
体系外质检分为 4 个独立 Pass，按顺序执行：
        ┌─ Pass 1: Structural & Residual (全自动脚本)
        ├─ Pass 2: Accuracy (源-目标对比 — 最耗时)
        ├─ Pass 3: Locale + Terminology 一致性 (半自动)
        └─ Pass 4: Native Reader Review (LLM 通读 — 最综合)
```

---

## Pass 1：结构 + 残留检查（全自动，~2 分钟）

**目标维度**：⑦ Design & Markup（验证）、③ Linguistic（源语残留）

**工具**：`e2e-test-suite/scripts/verify_docx.py`

**执行步骤**：

```python
# Agent 执行
1. 运行 verify_docx.py（对比源 DOCX vs 目标 DOCX）
2. 检查结果：
   ✅ 段落数一致
   ✅ 图片数 & MD5 一致
   ✅ Section 标记（#46, #48...）全部保留
   ✅ 0 残留中文（w:t / w:txbxContent / header / footer / 图片描述）
3. 任意 ❌ → stop，修复管线问题后再继续
```

**输出**：`{run-id}/qa-pass1-structural.json`

**决策**：通过才进 Pass 2。结构不对后面所有检查无意义。

---

## Pass 2：Accuracy 准确度（半自动，~20 分钟 / 100 段落）

**目标维度**：④ Accuracy（最关键的维度）

**方法**：段落对齐 + LLM 差异报告

### 核心流程

```
源 DOCX ──→ python-docx 提取为 [段1, 段2, ...]（by 段落索引）
目标 DOCX ──→ python-docx 提取为 [段1', 段2', ...]（by 段落索引）

按段落索引对齐 → 跳过分隔线/图片标记段（#46 等）
              → 对文本段，逐段提交 LLM 审查
```

### LLM 审查指令

```
对比以下中文原文和对应的英文译文，报告所有差异。

中文段: {source_text}
英文段: {target_text}

只报告以下类型的差异：
1. ❌ 数字不一致（年份、金额、百分比）
2. ❌ 专名不一致（人名、品牌名、产品名）
3. ❌ 否定翻成肯定或反之
4. ❌ 显著增译或漏译（超过 5 个词的增减）
5. ❌ 语义相反或明显偏离

对于每个差异，给出：
- 严重度：Critical / Major
- 原文片段
- 译文片段
- 建议修正

如果无差异，只输出 "✅ ACCURATE"。
```

### 执行策略

- **全量通读**：所有文本段都过一遍 LLM（不是抽样）
- **分段提交**：每次 5-10 段，避免超上下文
- **跳过**：纯图片段（#46 等）、空段

### 输出格式

```json
{
  "pass": 2,
  "total_segments": 85,
  "checked": 72,
  "skipped": 13,
  "issues": [
    {
      "segment_idx": 33,
      "severity": "major",
      "type": "number_mismatch",
      "source": "1992年",
      "target": "1990",
      "suggestion": "改为 1992"
    },
    ...
  ]
}
```

### 决策

| 结果 | 动作 |
|------|------|
| 0 Critical + ≤2 Major | ✅ 继续 Pass 3 |
| 任何 Critical 或 >2 Major | ❌ stop，修复后重跑管线（或手动改 DOCX 后继续） |

---

## Pass 3：Locale + Terminology 一致性（半自动，~5 分钟）

**目标维度**：⑤ Locale Conventions、① Terminology（跨段一致性）

### 3.1 Locale 约定检查

纯正则脚本，不需要 LLM：

```python
import re

locale_rules = {
    "en-US": {
        "number": r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b",  # 1,000.00
        "date": r"\b\d{1,2}/\d{1,2}/\d{4}\b",           # M/D/YYYY
        "currency": {"¥": "USD", "rmb": "USD", "€": "EUR"},
    },
    "en-GB": {
        "number": r"\b\d{1,3}(?:\.\d{3})*(?:,\d+)?\b",  # 1.000,00
        "date": r"\b\d{1,2}/\d{1,2}/\d{4}\b",           # D/M/YYYY
    },
}

# 扫描全文
for rule_name, pattern in locale_rules[target_locale].items():
    matches = re.findall(pattern, full_text)
    for m in matches:
        if not is_expected_format(m, target_locale):
            issues.append(f"Unexpected {rule_name} format: {m}")
```

**需配置的参数**：`target_locale`（en-US / en-GB / zh-CN 等）

### 3.2 术语一致性扫描

```python
# 从 Glossary JSON 加载
glossary = json.load(open("glossary.json"))
# 提取所有标准英文译名
expected_en = {v for v in glossary.values() if is_english(v)}

# 在目标 DOCX 中扫描非标准变体
variants_found = {}
for term_en in expected_en:
    # 模糊匹配：大小写/连字符/单复数变体
    found = find_variants(full_text, term_en)
    if len(found) > 1:
        variants_found[term_en] = found
```

**检查重点**：
- 品牌名：三翼鸟→Sanyiniao（不是 Three-Winged Bird）
- 战略术语：三位一体→three-in-one（不是 trinity / tripartite / three-pronged）
- 产品名：朗境→Lanjing（不是 Bright View / Langjing 等音译变体）

### 3.3 输出

```json
{
  "pass": 3,
  "locale_issues": [...],
  "terminology_inconsistencies": {
    "three-in-one": ["three-in-one", "trinity", "tripartite"]
  }
}
```

### 决策

| 结果 | 动作 |
|------|------|
| 0 inconsistency | ✅ 继续 Pass 4 |
| 有 inconsistencies | 记入修复清单，Pass 4 后一起修 |

---

## Pass 4：Native Reader Review（LLM 通读，~15 分钟 / 全书）

**目标维度**：③ Linguistic（深度）、⑥ Audience Appropriateness

**方法**：以英语母语者身份全文通读，报告"读起来有问题"的地方。

### 执行步骤

```
全文提取 → 按每 ~50 段落为一批
         → 每批提交 LLM 审查：

"你是一名英语母语编辑。阅读以下英文文本，找出所有：
1. 🔴 语法/拼写错误
2. 🟡 表达不地道（Chinglish、异常搭配）
3. 🔵 文化比喻失效（英文读者看不懂的隐喻/典故）
4. 🟢 风格不一致（与正式商业出版物的调性不符）

对于每个问题，给出原文片段和建议修改。
如果一段没有问题，跳过。
"
```

### 批次策略

| 文档大小 | 批次策略 | 预计时间 |
|---------|---------|---------|
| <50 段 | 1 批全量提交 | ~5 min |
| 50-150 段 | 分 2-3 批 | ~15 min |
| >150 段 | 分 4-5 批 | ~30 min |

### 输出

```json
{
  "pass": 4,
  "batches": 3,
  "issues": [
    {
      "segment_idx": 49,
      "severity": "major",
      "type": "cultural_metaphor",
      "text": "...dancing with wolves...",
      "suggestion": "replace with 'taking on industry giants'"
    },
    {
      "segment_idx": 85,
      "severity": "minor",
      "type": "chinglish",
      "text": "...deeply cultivating its brand journey...",
      "suggestion": "...through sustained brand building..."
    },
    ...
  ]
}
```

---

## 修复阶段

四个 Pass 完成后，汇总所有问题：

```
qa_report.json:
├── pass1: structural ✅ / ❌
├── pass2: accuracy — N issues (C/M)
├── pass3: locale — N issues, terminology — N inconsistencies
└── pass4: native review — N issues (M/m)
```

### 修复策略

| 严重度 | 修复方式 |
|--------|---------|
| **Critical** | 必须修。如果是管线问题→重跑；如果是局部问题→python-docx 定位改 |
| **Major** | 必须修。优先改 DOCX，批量同类问题考虑改管线配置 |
| **Minor** | 可选择性修。累计 >10 个则最批量改 |

**修复纪律**（Karpathy 规则）：
- 只改有问题的那句，不顺手优化相邻文本
- 修完验证：改前→改后 diff 只含目标改动
- 同类问题出现 ≥3 次 → 开体系 Issue（配置/Prompt/架构）

### 重验证

修完后，对修复区域做定向验证（不跑全 4 个 Pass），确认改对且无回退。

---

## Pass 4（Native Review）的详细操作指南

因为这是最综合、最依赖 Agent 判断的环节，单独展开。

### 关注信号

| 信号 | 例子 | 严重度 |
|------|------|--------|
| 拼写错误 | Carrierr, publically | 🔴 Critical |
| 语法错误 | "This represent that..." | 🔴 Major |
| 非标准术语 | "revenue balance" → break-even | 🔴 Major |
| 词性错误 | "to layout the market" | 🔴 Major |
| Chinglish 直译 | "deeply cultivating" / "zero-distance interaction" | 🟡 Minor |
| 冗余 | "always been continuously" | 🟡 Minor |
| 文化比喻 | "dancing with wolves" | 🟡 Minor |
| 大小写不一致 | "adhere to" vs "Build" | 🔵 Polish |
| 过长的句子 | 70 词单句 | 🟡 Minor |

### 不关注信号（Pass 1-3 已覆盖）

- 图片/段落结构 → Pass 1
- 数字/日期格式 → Pass 3
- 术语一致性 → Pass 3
- 源语残留 → Pass 1
- 准确度 → Pass 2

### 限制

- **LLM 无法完美自检**：Pass 4 的目的是发现"一眼就看出不对"的问题，不是捕获所有差异。深层的 subtle 问题（语气偏差、隐含偏见）需要真人。
- **分批发更有质量**：一次提交全部段落会让 LLM 注意力稀释，5-50 段/批效果最佳。
- **优先检查高密度段**：专名密集的段（收购列表、产品名列表）、文化段（开头结语、引用名言）、数据段（多数字句）。

---

## 全流程耗时预估

| Pass | 内容 | 全自动 | 耗时 |
|------|------|--------|------|
| Pass 1 | 结构+残留 | ✅ | ~2 min |
| Pass 2 | 准确度 | ⚠️ LLM 辅助 | ~20 min |
| Pass 3 | Locale+术语 | ⚠️ 半自动 | ~5 min |
| Pass 4 | Native 通读 | ⚠️ LLM 辅助 | ~15 min |
| 修复 | 汇总+改 | Agent | ~10 min |
| 再验证 | 定向检查 | ✅ | ~5 min |
| **总计** | | | **~1 小时** |

---

## 与 LQA 评分模型的对应

| MQM 维度 | 覆盖 Pass | 体系内/外 |
|----------|----------|-----------|
| ① Terminology | Pass 3（一致性）+ 体系内（Glossary 命中） | 内+外 |
| ② Style | 体系内（SG 注入+Polish） | 内 |
| ③ Linguistic Conventions | Pass 1（残留）+ Pass 4（语法/Chinglish）+ 体系内（Polish） | 内+外 |
| ④ Accuracy | Pass 2 | 全外 |
| ⑤ Locale Conventions | Pass 3 | 全外 |
| ⑥ Audience Appropriateness | Pass 4（文化）+ 体系内（Prompt 规则） | 内+外 |
| ⑦ Design & Markup | Pass 1（验证）+ 体系内（OPP→ORF 保留） | 已覆盖 |
