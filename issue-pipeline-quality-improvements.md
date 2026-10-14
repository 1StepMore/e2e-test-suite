# 体系内质量改进：三个维度的管线增强

## 背景

基于 MQM 框架分析 OPP→OL(SG+Glossary+Polish)→ORF 管线，以下三个质量维度可以通过管线内改进显著提升，无需外部 QA 介入。

---

## 一、Terminology：Glossary 覆盖率报告

**问题**：`--glossary` 能强制术语命中，但用户不知道多少术语被实际命中。低覆盖率时翻译质量不可见。

**改进方案**：

### 1.1 `--glossary --report-coverage` 参数

OL `translate-xliff` / `translate-md` 加 `--report-coverage` flag，译后输出：

```
Glossary Coverage Report
────────────────────────
Total terms: 47
Matched in source: 31 (66%)
Unmatched: 16
  - 海尔 → (未命中，因为不在当前段落)
  - 人单合一 → (同上)
Suggested: add '商业模式' → 'business model'

Match type breakdown:
  Exact: 24 (77%)
  Fuzzy (>80%): 5 (16%)
  Case-normalized: 2 (7%)
```

**实现位置**：
- `src/ol_translate/pipeline.py` — 译后统计
- `src/cli/translate_md.py` / `translate_xliff.py` — CLI 入口

**代码量**：~80 行（统计模块 + CLI 参数）

### 1.2 低覆盖率告警

`--glossary --coverage-threshold 50` 低于阈值时 warn（不阻断，不 fail）

```
⚠ WARNING: Glossary coverage is 31% (14/47 terms matched)
  Consider expanding the glossary or checking term spelling.
```

### 1.3 跨段一致性后处理（架构扩展）

**问题**：LLM 逐段翻译，同一个中文术语在不同段的译文可能不一致（"三翼鸟"→Sanyiniao vs Three-Winged Bird）。

**实现方向**：`--polish` 增强，增加 `--glossary-consistency` 子 pass：

```python
def check_glossary_consistency(xliff, glossary):
    """扫描所有 target，对 glossary 中的术语做一致性校验"""
    for term, expected in glossary.items():
        variants = find_variants(xliff.targets, term, expected)
        if variants:
            report.append(f"术语 '{term}': 期望 '{expected}', 发现变体 {variants}")
```

**位置**：`src/ol_xliff/repair/level4_safe_fallback.py` 或新 `level5_consistency.py`

**代码量**：~150 行

---

## 二、Linguistic Conventions：增强 --polish

**问题**：当前 `--polish` 做流畅度润色，但不处理拼写错误、语法问题、重复冗余。

**改进方案**：

### 2.1 Polish 增加 grammar 指令

当前 polish prompt 缺少语法/拼写关注。在 `src/ol_translate/pipeline.py` 的 polish prompt 模板中加入：

```
请检查并修复以下问题（按优先级）：
1. 拼写错误（如 Carrierr → Carrier）
2. 语法错误（主谓一致、冠词、介词）
3. 非标准表达（如 "revenue balance" → "break-even"）
4. 冗余修饰（如 "always been continuously" → "been continuously"）
5. 保持原有风格和术语不变
```

**位置**：`src/ol_translate/pipeline.py` — `_build_polish_prompt()`

**代码量**：~10 行（prompt 文本修改）

### 2.2 外部拼写检查集成（可选增强）

`--polish --spell-check` 调用系统 `aspell` 或 `hunspell` 生成拼写错误列表，注入 polish prompt 作为参考：

```python
import subprocess
result = subprocess.run(['aspell', 'list'], input=text, text=True, capture_output=True)
spell_errors = result.stdout.strip().split('\n')
```

**位置**：`src/ol_translate/pipeline.py`

**代码量**：~20 行，非必需（拼写检查可外挂）

---

## 三、Audience Appropriateness：Prompt 规则

**问题**：中文独特文化比喻（"与狼共舞""马到成功"）被 LLM 直译，英文读者无法理解。

**改进方案**：

### 3.1 Translate prompt 加文化转换规则

在 `src/ol_translate/prompt_templates.py` 的 system prompt 中加入：

```
文化转换规则：
- 如果原文包含中文特有的文化比喻、成语、典故（如"与狼共舞"、"马到成功"），
  不要直译，而是改写为英文读者能理解的等效表达
- 例如："与狼共舞" → "competing with industry giants"
- 保留原文的事实信息，只转换比喻部分
- 如果不确定某个表达是否有文化隔阂，优先使用直接、清晰的平实语言
```

**位置**：`src/ol_translate/prompt_templates.py`

**代码量**：~8 行（prompt 文本）

### 3.2 可选：文化隐喻检测告警

`--polish` 中加一道文化隐喻扫描：

```python
# 常用的中文商业比喻列表
CHINESE_METAPHORS = [
    '与狼共舞', '马到成功', '望子成龙', '画龙点睛',
    '未雨绸缪', '破釜沉舟', '卧薪尝胆', '百里挑一',
    # ...
]

def detect_metaphors(text):
    for meta in CHINESE_METAPHORS:
        if meta in text:
            return [meta]
    return []
```

译前检测到则 warn，提醒用户注意文化转换。

**位置**：`src/ol_translate/preprocessor.py` 或 `src/cli/` 

**代码量**：~30 行

---

## 汇总

| 改进项 | 价值 | 代码量 | 优先级 | 目标版本 |
|--------|------|--------|--------|---------|
| Glossary 覆盖率报告 | 高（质量可见性） | ~80 行 | P1 | v0.7 |
| 低覆盖率告警 | 中（防漏） | ~20 行 | P1 | v0.7 |
| 跨段一致性检查 | 高（术语统一） | ~150 行 | P2 | v0.8 |
| Polish grammar 指令增强 | 高（减少 Chinglish） | ~10 行 | P1 | v0.7 |
| 文化转换 prompt 规则 | 高（减少文化误译） | ~8 行 | P1 | v0.7 |
| 文化隐喻检测 | 中（辅助告警） | ~30 行 | P2 | v0.8 |

---

## 相关文件

- `src/cli/translate_md.py` — 入口
- `src/cli/translate_xliff.py` — 入口
- `src/ol_translate/pipeline.py` — 翻译/润色管线
- `src/ol_translate/prompt_templates.py` — Prompt 模板
- `src/ol_xliff/repair/level4_safe_fallback.py` — 后处理
- `src/ol_terminology/extractor.py` — 术语提取
- `src/ol_terminology/manager.py` — 术语管理
