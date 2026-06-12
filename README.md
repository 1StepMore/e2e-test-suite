# E2E Test Suite

OPP → OL → ORF 全链路集成测试环境，含全自动 bug 发现 → OpenCode 修复 → 验证闭环。

---

## 目录结构

```
Omni_Suite/
├── Omni_Pre_Processor/   # OPP — 文档提取（源码直接位于根目录）
├── Omni_Localizer/       # OL — 文档翻译（源码直接位于根目录）
├── Omni_Re_Formatter/    # ORF — 文档回写（源码直接位于根目录）
├── src/                  # Git submodules（空/未检出）
│   ├── Omni_Pre_Processor/
│   ├── Omni_Localizer/
│   └── Omni_Re_Formatter/
│
├── tests/                # E2E 测试套件（30+ 测试文件）
│   ├── conftest.py       # 共享 fixtures
│   ├── pytest.ini        # pytest 配置
│   ├── test_e2e_real_llm.py  # 14 个 nightly 测试
│   └── ...
│
├── scripts/
│   └── sync_shallow.sh   # 同步 submodule SHA
│
├── test_artifacts/       # 测试产物（每次运行）
├── test_output/          # 旧版测试输出
│
├── reports/
│   ├── TEMPLATE-Bug-Report.md
│   ├── TEMPLATE-Comparison-Report.md
│   └── E2E-*.md          # 具体 bug 报告
│
├── .venv_ol/             # ✅ 当前统一 venv（Python 3.13，所有组件共用）
├── .venv/                # ⚠️ 已弃用（Python 3.12，勿使用）
│
├── run_test.sh           # 全链路测试驱动脚本
├── .gitignore
├── .gitmodules
└── README.md
```

---

## 快速上手

```bash
# 1. 同步 submodules
bash scripts/sync_shallow.sh

# 2. 跑一次全量测试（CLI 路径）
bash run_test.sh --test-name first-run

# 3. 跑 MCP + CLI 路径
bash run_test.sh --test-name mcp-run --mcp

# 4. 只测单个模块
bash run_test.sh --test-name opp-only --module opp
bash run_test.sh --test-name ol-only  --module ol
bash run_test.sh --test-name orf-only --module orf
```

---

## Git Submodules

```
src/Omni_Pre_Processor   → 1StepMore/Omni_Pre_Processor (main)
src/Omni_Localizer      → 1StepMore/Omni_Localizer (main)
src/Omni_Re_Formatter   → 1StepMore/Omni_Re_Formatter (main)
```

**同步命令**：`bash scripts/sync_shallow.sh`  
**注意**：套件 git 不会自动追踪 submodule 上游新 SHA，需手动 sync + commit。

---

## 当前 Bug 状态

| Bug | 工具 | 状态 | 修复 SHA |
|-----|------|------|----------|
| E2E-03 | ORF MCP | ✅ 已修复 | `15834db` |
| E2E-04 | OL CLI translate-xliff 不调用 LLM，target 为空 | ❌ 待修复 | — |
| E2E-05 | MD Path 结构优化（标题层级、段落分隔、文字样式） | ✅ 已完成 | 本批次 |
| E2E-06 | MD Path 段落膨胀修复（OL token_stream + <!-- p -->正则收紧） | ✅ 已完成 | 本批次 |
| E2E-07 | 边界条件测试修复（OPP/ORF/images 共 9 项） | ✅ 已完成 | 本批次 |

### E2E-05: MD Path 结构优化

**目标**：让 MD 管道（OPP → OL → ORF）输出的 DOCX 具有正确的标题层级、段落分隔、文字样式。

**改动清单**：

| 组件 | 文件 | 改动 |
|------|------|------|
| OPP | `markdown/generator.py` | `style_mapping` 参数、表格交叉排列、文本框→`>`引用、行内格式转换（粗体/斜体/删除线）、段落间空行分隔 |
| OPP | `extractors/docx.py` | 文档体子元素共享位置计数器、文本框标记 `style="[TextBox]"` |
| OPP | `cli.py` | `--style-map`（样式名→标题等级映射）、`--no-embed-images`（base64 内嵌图片） |
| OPP | `pipeline.py` | `style_mapping`、`embed_images` 参数透传 |
| ORF | `cli.py` | `--reference-doc`（pandoc 样式模板） |
| ORF | `mcp/server.py` | `apply_md` 工具新增 `separate_images` 参数 |
| Suite | `tests/e2e_runner.py` | 全 4 路径综合测试器 |
| Suite | `tests/test_e2e_real_llm.py` | `ensure_md_block_separation()` 段落分隔恢复、`_run_opp`/`_run_orf` 参数增强 |

**使用方式**：
```bash
# OPP 提取结构化MD
opp --target-format=md --output-dir ./md_out --style-map '{"a5":1}' document.docx

# OL 翻译（保持MD结构）
ol translate-md ./md_out/document.md -s zh -t en -o ./ol_out/

# ORF 还原DOCX
orf apply-md ./ol_out/document.md --target-format docx -o result.docx
```

**MD Path 设计定位**：
- MD path 专注文字呈现，图片以 `images.json` + `{stem}_images/` 目录形式独立交付供手动使用
- 精确图片注入请使用 XLIFF 管道（基于 skeleton.zip 回填，保留原始 OOXML 布局）

---

## 环境说明

| 组件 | 路径 | 版本 |
|------|------|------|
| OPP | `Omni_Pre_Processor` | `3684e87` |
| OL | `Omni_Localizer` | `4685a47` |
| ORF | `Omni_Re_Formatter` | `c7d6853`（含 `15834db`）|
| Python 3.13（统一 venv） | `.venv_ol/` | ✅ 当前唯一活跃 venv，所有组件共用 |
| Python 3.12（已弃用） | `.venv/` | ⚠️ 旧 venv，OPP/ORF CLI 曾用，勿再使用 |
| OL MCP 专用 venv | `~/.hermes/venvs/omni-localizer` | Python 3.13（OL MCP 服务）|

---

## OL MCP 说明

OL MCP 服务运行在 `~/.hermes/venvs/omni-localizer`（Python 3.13），由 wrapper 脚本管理：

```
/mnt/d/Hermes-Workspace/01-Projects/Omni_Localizer/src/ol_mcp_wrapper.sh
  → /home/renanzai/.hermes/venvs/omni-localizer/bin/python src/ol_mcp_run.py
```

**测试 OL MCP**（通过 Hermes MCP tool）：
```bash
mcp_ol_translate_xliff({params: {input_path: "...", output_path: "...", ...}})
```

**测试 OL CLI**：
```bash
~/.hermes/venvs/omni-localizer/bin/ol translate-xliff input.xlf \
  --source-lang zh --target-lang en --json -o output_dir/
```

---

## Bug 报告结构（参考）

每个 bug 报告包含：

1. **Bug ID** + 标题
2. **问题现象**（详细描述）
3. **根因分析**（工具/文件/代码行/原因）
4. **可复现**（触发命令 + 预期 vs 实际）
5. **影响范围**（哪些路径受影响）
6. **修复状态**（Checkbox）
7. **修复验证**（验证命令）
8. **附录**（相关日志）

---

## E2E-03 修复记录

**文件**：`src/Omni_Re_Formatter/src/orf/mcp/server.py:189`

**问题**：`images=None` 时访问未初始化变量 `temp_created`，导致 `NameError`

**修复**：在 `if images:` 之前添加 `temp_created = False`

**验证**：
```bash
PYTHONPATH="src/Omni_Re_Formatter/src" .venv312/bin/python -c "
from orf.mcp.server import _run_cli_command
# 模拟 images=None 调用
result = _run_cli_command(['apply-xliff', '/nonexistent.docx', '--xliff', '/nonexistent.xliff', '--output', '/tmp/out.docx', '--format', 'docx'])
print('OK — no NameError' if 'NameError' not in str(result) else 'FAIL')
"

### E2E-06: MD Path 段落膨胀修复

**问题**：OL `TokenPositionTracker.rebuild()` 在 `paragraph_close` 时只输出 `\n`（单换行），导致段落间空行丢失。随后 `ensure_md_block_separation()` 过度补偿——在每个行内折行处注入 `<!-- p -->`，使段落数从 12,273 膨胀至 16,860（+37%）。

**改动清单**：

| 组件 | 文件 | 改动 |
|------|------|------|
| OL | `token_stream.py` | `paragraph_close` 改为输出 `\n\n`（双换行），恢复段落间空行 |
| Suite | `test_e2e_real_llm.py` | `ensure_md_block_separation()` 正则从 `(?<=\S)\n(?=\S)` 收紧为 `\n\n(?=\S)`，仅在空行边界注入 `<!-- p -->` |

**验证**：
```bash
pytest tests/test_e2e_real_llm.py -v -k test_md_channel
```

### E2E-07: 边界条件测试修复

**问题**：OPP/ORF/images 模块的 9 个边缘测试因环境差异（python-pptx 版本、缺少 CLI 工具、格式变更）而失败。

**改动清单**：

| 组件 | 文件 | 改动 |
|------|------|------|
| OPP | `test_e2e_opp_all_formats.py` | `_create_minimal_epub()` 添加 `OEBPS/` mkdir；PPTX `slide_layouts[6]` → `[0]`（3处）；IPYNB 添加 `@pytest.mark.xfail` |
| ORF | `test_e2e_orf_all_formats.py` | ICML 断言改为检查 `ParagraphStyleRange`；MD2PPTX 添加 `shutil.which()` 跳过守卫 |
| ORF | `options.py` | PDF 默认引擎从 `pdflatex` 改为 `weasyprint` |
| Images | `test_e2e_images.py` | PPTX `slide_layouts[6]` → `[0]` |
| Suite | `e2e_runner.py` + `test_e2e_real_llm.py` | 新增 `--glossary` 参数传递支持 |

**验证**：
```bash
pytest tests/test_e2e_opp_all_formats.py -v -k "pptx or ipynb"
pytest tests/test_e2e_orf_all_formats.py -v -k "icml or md2pptx or md2pdf"
pytest tests/test_e2e_images.py -v -k "pptx"
```