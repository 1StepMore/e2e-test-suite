# 体系改进方案：当前架构内的翻译质量提升

> 不改变 OPP→OL→ORF 三阶段拓扑，不引入新组件，不重构现有模块。
> 只做：参数增强 + prompt 改进 + 数据补充。
> 所有改动对任意文档生效。

---

## 目录

1. [StyleGuide 注入 translate-xliff](#1-styleguide-注入-translate-xliff)
2. [专有名词保原文规则](#2-专有名词保原文规则)
3. [--polish 全局一致性后处理](#3---polish-全局一致性后处理)
4. [Glossary 数据补全](#4-glossary-数据补全)
5. [优先排序与实现预估](#5-优先排序与实现预估)

---

## 1. StyleGuide 注入 translate-xliff

### 现状

`profile-doc` 已经能生成 StyleGuide，`StyleGuide` 类已经有 `to_prompt_section()` 方法将其格式化为 prompt section，`build_translate_prompt()` 已经接受 `style_guide` 参数。

但调用链从未传这个参数：

```
CLI path:
  translate_xliff() → _translate_xliff_async() → _translate_units_concurrent()
  → _translate_one_unit() → pool.translate(context=None)
                                          ^^^^^^^^ 从没构建过带 style_guide 的 context

MCP path:
  translate_xliff() → for unit in units:
    build_translate_prompt(text=..., glossary_terms=terms)
                           ^^^^^^^^^^^^ 没传 style_guide
```

StyleGuide 生成了，从未进入翻译 prompt，等于白跑。

### 改动

#### 1a. CLI：`translate_xliff` 加 `--styleguide` 参数

**文件**：`src/cli/translate_xliff.py`

**具体改动**：

A. 在 CLI 函数签名中加参数（line 410-457 区域）：

```python
def translate_xliff(
    # ... 现有参数不变 ...
    styleguide: str | None = typer.Option(
        None, "--styleguide",
        help="Path to a StyleGuide JSON file (output of ol profile-doc). "
             "Style rules are injected into each trans-unit's system prompt.",
    ),
) -> int:
```

B. 在函数体中解析 StyleGuide（在调用 `_translate_xliff_async` 之前）：

```python
# 在 if config: 块附近（~line 492）
styleguide_content: str | None = None
if styleguide:
    from ol_style.schema import StyleGuide
    sg = StyleGuide.from_json_file(styleguide)
    styleguide_content = sg.to_prompt_section()
    if styleguide_content:
        logger.info(f"StyleGuide loaded: {sg.tone}/{sg.register}")
```

C. 将 `styleguide_content` 传给 `_translate_xliff_async`：

```python
output_file = asyncio.run(_translate_xliff_async(
    input_path, output_path, config_path or ...,
    src_lang, tgt_lang,
    glossary=glossary,
    styleguide=styleguide_content,  # ← 新增
))
```

注意：当前调用是 `output_file = asyncio.run(...)`，在 `if no_cache:` 分支上（不在已读的 500 行范围内，需要确认精确位置）。

#### 1b. `_translate_xliff_async` 接受并传递 `styleguide`

**文件**：`src/cli/translate_xliff.py`

```python
# line 280 修改签名
async def _translate_xliff_async(
    input_path: Path,
    output_path: Path,
    config_path: str | None,
    src_lang: str,
    tgt_lang: str,
    glossary: 'Glossary | None' = None,
    styleguide: str | None = None,        # ← 新增
) -> str:
```

在调用 `_translate_units_concurrent` 或 `_translate_xliff_pipelined` 时（~line 352-367），传入 `styleguide`：

```python
results = await _translate_units_concurrent(
    units, pool, judge, retry_mgr,
    src_lang, tgt_lang,
    sem=..., repair_pipeline=..., glossary=glossary,
    styleguide=styleguide,  # ← 新增
)
```

#### 1c. `_translate_units_concurrent` → `_translate_one_unit` 传递 styleguide

**文件**：`src/cli/translate_md.py`

`_translate_units_concurrent`（line 360）新增 `styleguide` 参数，传给 `_tracked_translate` → `_translate_one_unit`。

`_translate_one_unit`（line 241）新增 `styleguide` 参数，在调用 `pool.translate()` 时（line 273-275）构建带 styleguide 的 context：

```python
# 将当前 await pool.translate(context=None, ...) 改为：
context = None
if glossary or styleguide:
    from ol_terminology.rag_injector import build_translate_prompt
    context = build_translate_prompt(
        text=unit.source_text,
        src_lang=src_lang, tgt_lang=tgt_lang,
        glossary_terms=glossary.get_relevant_terms(unit.source_text) if glossary else None,
        style_guide=styleguide,
    )
translated = await pool.translate(
    unit.source_text, src_lang, tgt_lang, context=context,
)
```

**注意**：当前 CLI 路径传 `glossary` 是 `Glossary` 对象，而 `build_translate_prompt()` 需要 `glossary_terms: list[dict]`。这段需要适配——从 `Glossary` 对象中提取 `get_relevant_terms()` 的格式。

#### 1d. MCP：`TranslateXliffInput` 加 `styleguide_path` 字段

**文件**：`src/ol_mcp/tools.py`（line 242-259，`TranslateXliffInput`）

```python
class TranslateXliffInput(BaseModel):
    # ... 现有字段不变 ...
    styleguide_path: str | None = Field(
        default=None,
        description="Path to a StyleGuide JSON file (output of profile_doc). "
                     "Style rules are injected into the translation prompt.",
    )
```

#### 1e. MCP：`translate_xliff` handler 加载并传递 styleguide

**文件**：`src/ol_mcp/translate_xliff.py`

同步分支（~line 242-255）和异步分支（~line 103-113）中，
在调用 `build_translate_prompt()` 之前加载 StyleGuide：

```python
# 在 glossary 加载之后、unit 循环之前
styleguide_section: str | None = None
if params.styleguide_path:
    from ol_style.schema import StyleGuide
    try:
        sg = StyleGuide.from_json_file(params.styleguide_path)
        styleguide_section = sg.to_prompt_section()
    except Exception as e:
        warnings.append(f"StyleGuide load failed: {e}")

# 在 build_translate_prompt 调用时传：
context = build_translate_prompt(
    text=unit.source_text,
    src_lang=..., tgt_lang=...,
    tm_matches=None, glossary_terms=terms,
    styleguide=styleguide_section,  # ← 新增
)
```

### 验证

```bash
# 1. 生成 StyleGuide
ol profile-doc source.txt -s zh -o styleguide.json

# 2. 翻译时注入
ol translate-xliff doc.xlf -s zh -t en --styleguide styleguide.json -o out/
# 日志应输出: "StyleGuide loaded: formal/business"

# 3. 翻译质量差异验证
# 不带 --styleguide: tone 中立
# 带 --styleguide: 翻译应遵从 tone/register/vocabulary 偏好
```

### 影响范围

| 文件 | 改动类型 | 代码量 |
|------|---------|--------|
| `src/cli/translate_xliff.py` | 参数 + 传递 | ~15 行 |
| `src/cli/translate_md.py` | 参数 + prompt 构建 | ~20 行 |
| `src/ol_mcp/tools.py` | Pydantic 字段 | ~5 行 |
| `src/ol_mcp/translate_xliff.py` | 加载 + 传递 | ~15 行 |
| `tests/test_*` | 测试 | ~40 行 |

**总代码量**: ~95 行

---

## 2. 专有名词保原文规则

### 现状

翻译 prompt 没有对"不确定的专有名词如何处理"的指令。当 glossary 未命中时，模型自由发挥——猜测出来的译名可能错误（Carrie→Carrier, Three-Winged Bird→Sanyiniao）。

### 改动

**文件**：`src/ol_terminology/rag_injector.py`（line 72，`build_translate_prompt` 的 instruction 行）

```python
# line 72-73 原代码：
instruction = f"Translate the following {src_lang} text to {tgt_lang}, using the above translation memory and glossary terms when applicable."

# 改为：
instruction = (
    f"Translate the following {src_lang} text to {tgt_lang}, using the "
    f"above translation memory and glossary terms when applicable.\n\n"
    f"RULE: If you encounter an unknown proper noun (company name, product "
    f"name, brand name, person name), ALWAYS keep the original pinyin or "
    f"Chinese characters rather than guessing an English translation. "
    f"When in doubt, preserve the original."
)
```

### 这为什么有效

- 不依赖 glossary 覆盖率（保护所有文档，不只是 glossary 全的文档）
- 不依赖模型能力（即使是弱模型也能执行"保原文"这个简单指令）
- 零性能开销（不加 LLM 调用，不加处理步骤）

### 验证

```bash
# 改之前: "开利" → "Carrie"（错误）
# 改之后: "开利" → "Kaili" 或 "开利 (Carrier)" 或保留原文
```

### 影响范围

| 文件 | 改动类型 | 代码量 |
|------|---------|--------|
| `src/ol_terminology/rag_injector.py` | prompt 文本 | +2 行 |

---

## 3. `--polish` 全局一致性后处理

### 现状

112 个 trans-unit 独立翻译，产生三类跨段问题：

| 问题 | 示例 | 原因 |
|------|------|------|
| 术语不统一 | 同段用 premium，另一段用 high-end | 每段独立选词 |
| 格式不统一 | (3) vs 3. ，引号风格不一致 | 无后续标准化 |
| 缺失连词 | "a global enterprise, a world-class brand" 缺 and | 短上下文 LLM 易漏 |

这些问题在**单个 trans-unit 的 prompt 内无法解决**——翻译时看不到邻居段落。

### 方案

在 OL 侧新增一个可选后处理步骤，在所有 trans-unit 翻译完成后、ORF 还原之前运行。

#### `--polish` 的设计约束

| 约束 | 理由 |
|------|------|
| 不重新翻译 | polish 只修正不一致，不改变译文的语义内容 |
| 用 cheapest 模型 | 任务简单（检查一致性），不需要主翻译的模型能力 |
| 可选，默认关闭 | 用户明确要求才跑，不影响现有工作流 |
| 只改 target | 不改 source，不改未翻译单元 |
| 向后兼容 | 不加 `--polish` 时行为与当前完全一致 |

#### 3a. `ol_cli translate-xliff` 加 `--polish` 参数

**文件**：`src/cli/translate_xliff.py`

```python
def translate_xliff(
    # ... 现有参数 ...
    polish: bool = typer.Option(
        False, "--polish",
        help="After translation, run a lightweight consistency pass: "
             "unify terminology, fix missing conjunctions, normalize formats. "
             "Uses the cheapest available model.",
    ),
) -> int:
```

#### 3b. `_translate_xliff_async` 接受 `polish` 标志

在翻译完成后、`write_target_back` 之前，调用 polish 步骤：

```python
# 在 results = await _translate_units_concurrent(...) 之后
if polish:
    from ol_xliff.polish import polish_translated_units
    polish_warnings = await polish_translated_units(
        units, src_lang, tgt_lang, pool, glossary,
    )
    warnings_per_unit.update(polish_warnings)
```

#### 3c. `src/ol_xliff/polish.py` 新文件

```python
"""Lightweight post-translation consistency pass.

Polishes translated XLIFF units for cross-unit consistency:
1. Terminology unification (against glossary if available)
2. Missing conjunction/article repair
3. Heading format normalization
4. Quote style normalization

Uses the cheapest available model (glm-4-flash priority).
Does NOT retranslate — only fixes inconsistencies.
"""

async def polish_translated_units(
    units: list,
    src_lang: str,
    tgt_lang: str,
    pool: 'ModelPool',
    glossary: 'Glossary | None' = None,
) -> dict[str, list[str]]:
    """Run a single LLM pass over all translated units for consistency.

    The LLM receives the full set of source-target pairs and is asked
    ONLY to fix: (a) glossary term mismatches, (b) missing conjunctions
    before list items, (c) inconsistent heading/quote formats.
    """
    # Build a compact diff view for the LLM
    pairs = []
    for u in units:
        if u.target_text and u.target_text != u.source_text:
            pairs.append({
                "id": u.unit_id,
                "src": u.source_text[:200],
                "tgt": u.target_text[:200],
            })

    if not pairs:
        return {}

    # One LLM call with all pairs
    prompt = _build_polish_prompt(pairs, glossary)
    result = await pool.translate("", src_lang, tgt_lang, context=prompt)
    # ... parse corrections, apply to units ...

    return warnings
```

**Prompt 设计**：

```
You are a consistency checker for translated documents.
Review these source-target pairs and identify:

1. TERM INCONSISTENCY: If the same source term is translated differently
   across pairs, flag them.
2. MISSING CONJUNCTION: If a list item lacks "and" before the last element.
3. FORMAT: If heading/numbering style is inconsistent.
4. QUOTE: If quotation mark style is mixed.

For each issue found, output:
  id: <unit_id>
  fix: <corrected target text>
  reason: <which rule was violated>

If no issues found, output only: NO_ISSUES

Source-target pairs:
{pairs}
```

#### 3d. MCP 对应的 `polish` 参数

与 StyleGuide 注入相同：在 `TranslateXliffInput` 中增加 `polish: bool = False` 字段，
在 `translate_xliff.py` MCP handler 中传递。

### 验证

```bash
# 不带 --polish（当前行为，不变）
ol translate-xliff doc.xlf -s zh -t en -o out/

# 带 --polish（新增后处理）
ol translate-xliff doc.xlf -s zh -t en --polish -o out/
# 日志应输出: "Polish pass: checking N units for consistency"
```

### 影响范围

| 文件 | 改动类型 | 代码量 |
|------|---------|--------|
| `src/ol_xliff/polish.py` | 新文件 | ~100 行 |
| `src/cli/translate_xliff.py` | 参数 + 调用 | ~10 行 |
| `src/cli/translate_md.py` | 传递参数 | ~5 行 |
| `src/ol_mcp/tools.py` | Pydantic 字段 | ~3 行 |
| `src/ol_mcp/translate_xliff.py` | 传递参数 | ~10 行 |
| `tests/test_ol_polish.py` | 测试 | ~60 行 |

**总代码量**: ~188 行

---

## 4. Glossary 数据补全

### 现状

当前爱上海尔 glossary 缺了关键条目或在翻译选择上可优化：

| 中文 | 当前 glossary | 模型输出 | 应输出 | 影响段落数 |
|------|-------------|---------|--------|-----------|
| 三翼鸟 | → "Three-Winged Bird" | Three-Winged Bird | Sanyiniao（音译） | 4 |
| 开利 | ❌ 缺 | "Carrie"（猜错） | Carrier | 1 |
| 滚筒洗衣机 | ❌ 缺 | front-load washing machine | drum washing machine | 1 |
| 波轮洗衣机 | ❌ 缺 | tub washing machine | pulsator washing machine | 1 |
| 朗境 X11 | ❌ 缺 | Langjing X11 | Lanjing X11 | 1 |

### 这不只是"补几个词"的问题

Glossary 补全是**数据维护**，不是代码改动。但它揭示了体系层面的限制：

- 当前缺少**"模型不确定时保原文"**的规则——glossary 补全得再多，新文档仍会出新类型的专有名词错误
- **规则（发现 2）**是体系修法，**数据补全**是兜底

两者都要做。

### 改动

**文件**：`Localization/爱上海尔/glossary.json`

新增/修正条目：

```json
{"source": "开利", "targets": ["Carrier"]},
{"source": "三翼鸟", "targets": ["Sanyiniao", "Three-Winged Bird"]},
{"source": "滚筒洗衣机", "targets": ["drum washing machine"]},
{"source": "波轮洗衣机", "targets": ["pulsator washing machine"]},
{"source": "朗境", "targets": ["Lanjing"]},
{"source": "海尔朗境 X11", "targets": ["Haier Lanjing X11"]},
```

### 验证

```bash
# 改之前
ol translate-md "开利是全球领先的空调制造商" -s zh -t en
# → "Carrie is a global leader in air conditioning manufacturing" ❌

# 改之后（加 glossary）
ol translate-md "开利是全球领先的空调制造商" -s zh -t en --glossary glossary.json
# → "Carrier is a global leader in air conditioning manufacturing" ✅
```

---

## 5. 优先排序与实现预估

| 优先级 | 改动 | 仓库 | 代码量 | 预估工时 | 杠杆 |
|--------|------|------|--------|---------|------|
| **P0** | 专有名词保原文规则（§2） | OL | +2 行 | 10 分钟 | 保护所有文档的所有专有名词 |
| **P0** | StyleGuide 注入（§1） | OL | ~95 行 | 2 小时 | 让 profile-doc 真正影响翻译质量 |
| **P1** | --polish 后处理（§3） | OL | ~188 行 | 3-4 小时 | 解决跨段不一致的根因问题 |
| **P1** | Glossary 数据补全（§4） | 数据 | 0 行 | 10 分钟 | 当前文档的精确性提升 |
| P2 | 默认语言方向修正（#38） | OL | 1 行 | 5 分钟 | 防止新用户踩坑 |
| P2 | FAKE_LLM 文档（#39） | OL | 文档 | 20 分钟 | 减少新用户困惑 |

### 建议执行顺序

```
第 1 轮（P0，今天）:
  §2 专有名词规则 → 1 行，5 分钟
  §1 StyleGuide 注入 → 95 行，2 小时
  §4 Glossary 补全 → 0 行，10 分钟
  效果：StyleGuide + glossary + 专有名词保护同时对任意文档生效

第 2 轮（P1，本周）:
  §3 --polish 后处理 → 188 行，3-4 小时
  效果：解决跨段不一致

第 3 轮（P2，非紧急）:
  #38 默认语言方向
  #39 FAKE_LLM 文档
  #37 translate_file MCP tool（如有需要）
  #49 骨架自动保存
  #50 str 路径崩溃修复
```
