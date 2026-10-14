# LLM 翻译瑕疵趋势跟踪

> **创建日期**：2026-06-01
> **目的**：跟踪 LLM 翻译过程中反复出现的"非 bug"瑕疵（不影响结构、不影响功能，仅译文质量），为未来 patch 提供数据基础
> **位置说明**：本文件**不进 git**（交接物，untracked，与 HANDOVER.md 同样定位）
> **数据源**：`test-runs/current/FULL-XXX/A-xliff-cli/text_comparison.json` → `quality_issues.source_lang_residue`

---

## 1. 已知瑕疵类型

| 类型代号 | 名称 | 现象 | 根因猜想 |
|---|---|---|---|
| **T1** | 输出截断（Truncation）| 翻译结果在句子中间断掉，无句末标点 | LLM 输出达到 `max_tokens` 限制被迫截断 |
| **T2** | 整段漏译 + 源语言残留 | target 完全是中文（源语言）| LLM 未识别 prompt 中的 inline tag 包裹规则，把 inline tag 内的中文原样输出 |
| **T3** | Prompt 泄露 | target 出现"CRITICAL: Output ONLY the en translation" 等 prompt 头 | LLM 未正确区分 system prompt vs 翻译任务 |
| **T4** | 半翻译（Half-translation）| target 混合中英文（如"Haier's international布局 early on"）| LLM 漏译部分短语 |

> **重要**：这些是 LLM 本身输出瑕疵，**不是 OPP/OL/ORF 管道 bug**。修在 prompt 层（OL 侧）或后处理（OL 侧）才有效。

---

## 2. 历史趋势（A 路径 source_lang_residue）

| Run ID | 时间 | 残留数 | 涉及 Unit | 类型分布 |
|---|---|---|---|---|
| `Full-Standard-20260531-214500` | 5/31 21:45 | 1 | 71 | T3（prompt 泄露）|
| `Full-Standard-20260601-104308` | 6/1 10:43 | 2 | 19, 71 | T1 + T3 |
| `Full-Standard-20260601-110400` (FULL-009) | 6/1 11:04 | 1 | 37 | T1（截断）|
| `Full-Standard-20260601-180633` (FULL-010) | 6/1 18:25 | 2 | 19, 86 | T1 + T2 |

**观察**：
- **T1 截断是高频问题**（4/4 run 中 3 个出现）
- **T2 整段漏译**仅 FULL-010 出现 1 次（Unit 86），未确认趋势
- **T3 prompt 泄露**在 5/31 后未复现（可能 OL 某次 prompt 更新消除了）
- **T4 半翻译**仅 1 次历史样本（Unit 71, 6/1 10:43），可能是 T1 的变体

---

## 3. 当前待修队列（截止 FULL-010）

| Unit | 类型 | 首次出现 | 最近出现 | 当前状态 |
|---|---|---|---|---|
| 19 | T1 | 6/1 10:43 | 6/1 18:25 | **未修**（4 run 中出现 2 次）|
| 37 | T1 | 6/1 11:04 | 6/1 11:04 | **未修**（1 次）|
| 71 | T3 → T4 | 5/31 21:45 | 6/1 10:43 | **T3 已消失，T4 残留**（2 次）|
| 86 | T2 | 6/1 18:25 | 6/1 18:25 | **未修**（1 次，新出现）|

> **优先级建议**：T1（截断）> T2（漏译）> T4（半翻译）> T3（已消失）

---

## 4. 根因深入分析

### T1 截断（最常见）

**典型样本**（Unit 19, FULL-010）：
```
<target>First is customization capability. This is also the most core characteristic and capability</target>
```
句子末尾"capability"无句号，明显被截断。

**猜想验证方向**：
1. 检查 OL `max_tokens` 参数设置（默认可能是 1024 或 2048）
2. 统计出现截断的 unit 的源文本长度分布（确认是否长文本专项问题）
3. 对比 full mode vs chunk mode 的 token 分配策略

### T2 整段漏译（Unit 86, FULL-010）

**典型样本**（Unit 86, FULL-010）：
```
<target><bx id="1" type="bold"/>（三）走上去：成为全球用户喜爱的本土化品牌<ex id="1"/></target>
```
target 完全是中文（带 inline tag 包裹），LLM 完全没有翻译。

**猜想验证方向**：
1. 检查 Unit 86 源文本中是否有特殊 inline tag 模式（如 `<bx/>...<ex/>` 包裹整个段标题）
2. OL prompt 是否对 inline tag 内的文本有特殊处理指令
3. 同样 Unit 19/37 也有 `<bx/>` 包裹结构吗？需要交叉验证

### T3 → T4 演变

5/31 出现的 T3（prompt 泄露）在 6/1 后未复现，但 6/1 10:43 出现 T4 变体（"布局 early on" 残留）。**这可能说明 prompt 改对了开头，但没修干净**——prompt 头里仍有"布局"这样的中文词没被强制要求翻译。

---

## 5. 建议修复方向

按"问题背后的问题来源"原则：

1. **不是一个个 unit 修 prompt**（治标，会复现新 unit）
2. **应在 OL prompt 层加显式约束**：
   - "Do NOT include prompt headers in your output"
   - "Translate ALL text inside inline tags, including section markers"
   - "Output must end with complete sentences (no truncation)"
3. **同时加 post-translation QC**（QA rules 已有 translate-toolkit pofilter，可加 custom rule 检测中文残留）
4. **L8/4 层 safe fallback 应主动检测 trunc/incomplete 输出并重试**（已部分实现 E2E-69/70，可考虑扩展）

---

## 6. 数据收集方法

每次 FULL run 完成后：
```bash
python3 -c "
import json
with open('test-runs/current/<RUN_ID>/A-xliff-cli/text_comparison.json') as f:
    d = json.load(f)
residue = d['quality_issues']['source_lang_residue']
for u in residue:
    print(f'Unit {u[0]}: {u[1][:150]}')
"
```

新发现 unit 追加到第 3 节"当前待修队列"表格。

---

**最后更新**：2026-06-01 FULL-010 完成后建档
