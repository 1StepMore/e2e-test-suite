# E2E-04 Bug Report (Revised)
**发现时间**: 2026-05-29（修订于同日）
**工具**: OL CLI (`translate-xliff`)
**Git SHA**: `4685a47`
**涉及文件**: `src/ol_cli.py`

---

## 1. 问题现象（修订）

调用 `ol translate-xliff` 时：
- 返回 `success: true` ✅
- 但输出 XLIFF 中 **`<target>` 标签为空/缺失** ❌
- 原文内容 + `<note from="OL">Translated from zh to en by OL</note>` 都在，唯独没有翻译后的 target

---

## 2. 根因分析

OL CLI 的 `translate-xliff` 命令**根本不调用 LLM**。

关键代码（`src/ol_cli.py` 第 512–580 行）：

```python
def translate_xliff(input: str, output_dir: str, ...):
    original_text = input_path.read_text(encoding="utf-8")
    pipeline = XLIFFRepairPipeline()
    repaired = pipeline.repair(original_text, original_text, {})
    xliff_header = _build_xliff_header_note(src_lang, tgt_lang)
    repaired = _inject_xliff_header(repaired, xliff_header)
    output_file.write_text(repaired, encoding="utf-8")   # ← 直接写回，没有 LLM 调用
```

对比 MCP 版本（`src/ol_mcp/tools.py`）：

```python
async def translate_xliff(params: TranslateXliffInput) -> str:
    pool = ModelPool.get_instance(config_path)          # ← 获取 LLM pool
    for unit in units:
        translated = await pool.translate(             # ← 真正调用 LLM 翻译
            unit.source_text,
            params.source_lang,
            params.target_lang,
            context
        )
        unit.target_text = repaired
    write_target_back(ctx, output_path)                # ← target 写入 XLIFF
```

**结论**：CLI 版本是残缺的——只有修复 pipeline，没有翻译 LLM 调用。
CLI 开发者可能把 MCP 的翻译逻辑漏掉了一半。

---

## 3. 涉及文件

```
src/ol_cli.py   ← translate_xliff 函数（缺失 LLM 调用）
```

---

## 4. 可复现

**是**。在任意环境执行：

```bash
/home/renanzai/.hermes/venvs/omni-localizer/bin/ol translate-xliff \
  /tmp/haier_e2e_in.xlf \
  --source-lang zh --target-lang en \
  --json -o /tmp/cli_test_out
```

检查输出：`grep "<target>" /tmp/cli_test_out/haier_e2e_in.xlf`  
预期：有内容 | 实际：无（0 个 `<target>`）

---

## 5. 修复方案

在 `translate_xliff` CLI 函数中补充 LLM 调用逻辑：

```python
from ol_pool.router import ModelPool
from ol_xliff.parser import XliffParser

pool = ModelPool.get_instance(config_path)
parser = XliffParser()
units = parser.parse(input_path)

for unit in units:
    translated = await pool.translate(
        unit.source_text, src_lang, tgt_lang, context
    )
    unit.target_text = translated

write_target_back(ctx, output_path)
```

参考 MCP 版本的完整实现（`src/ol_mcp/tools.py::translate_xliff`）。

---

## 6. 测试建议

修复后验证：

| 场景 | 检查项 | 预期 |
|------|--------|------|
| CLI + 3单元 XLIFF | `<target>` 数量 | = 3（有内容）|
| MCP + 3单元 XLIFF | `<target>` 数量 | = 3（有内容）|
| CLI vs MCP 一致性 | diff 两个输出 | 完全相同 |

---

## 7. 修复状态

❌ **未修复** — CLI 缺失 LLM 翻译逻辑，需补充 `pool.translate()` + `write_target_back()` 调用。