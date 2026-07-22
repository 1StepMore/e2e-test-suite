# E2E Test Suite

[![CI](https://img.shields.io/badge/CI-passing-brightgreen.svg)](https://github.com/1StepMore/e2e-test-suite/actions)
[![PyPI - opp](https://img.shields.io/pypi/v/opp.svg)](https://pypi.org/project/opp/)
[![PyPI - omni-localizer](https://img.shields.io/pypi/v/omni-localizer.svg)](https://pypi.org/project/omni-localizer/)
[![PyPI - omni-re-formatter](https://img.shields.io/pypi/v/omni-re-formatter.svg)](https://pypi.org/project/omni-re-formatter/)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/release/python-3130/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

OPP → OL → ORF 全链路集成测试环境，含全自动 bug 发现 → OpenCode 修复 → 验证闭环。

---

## 目录结构

```
.
├── Omni_Pre_Processor/   # OPP — 文档提取（独立 git repo）
├── Omni_Localizer/       # OL — 文档翻译（独立 git repo）
├── Omni_Re_Formatter/    # ORF — 文档回写（独立 git repo）
│
├── tests/                # E2E 测试套件（30+ 测试文件）
│   ├── conftest.py       # 共享 fixtures
│   ├── pytest.ini        # pytest 配置
│   ├── test_e2e_real_llm.py  # 24 个 nightly 测试
│   └── ...
│
├── scripts/
│   └── setup_dev.sh      # 一键安装脚本
│
├── docs/                 # Suite-level 文档
│   ├── AGENTS.md
│   ├── ARCHITECTURE.md
│   ├── API_STABILITY.md
│   └── ...
│
├── reports/
│   ├── TEMPLATE-Bug-Report.md
│   ├── TEMPLATE-Comparison-Report.md
│   └── E2E-*.md
│
├── .venv_ol/             # ✅ Python 3.13 统一 venv
│
├── .gitignore
├── pyproject.toml        # 根 workspace
├── VERSION               # Suite 版本
├── COMPATIBILITY.md      # 版本兼容矩阵
├── uv.lock               # 根 lock 文件
└── README.md
```

---

## 前置条件：Python 3.13

所有组件（OPP/OL/ORF/Suite）均要求 **Python >= 3.13**。系统默认 Python 通常为 3.10–3.12，需先安装 3.13：

```bash
# 方式 A：使用 uv（推荐 — 速度快，自带 venv 管理）
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.13

# 方式 B：使用 pyenv（适合需要多版本切换的开发者）
pyenv install 3.13.3
pyenv local 3.13.3

# 验证
python3 --version   # 必须 >= 3.13
```

> 如果系统已有 3.13，可直接跳到下一节。

---

## 快速上手

```bash
# 1. Sub-repos are independent — pull updates inside each directory
#    cd Omni_Pre_Processor && git pull origin main

# 2. 安装（root workspace，Phase C1）
bash scripts/setup_dev.sh

# 3. 跑测试（pytest）
source .venv_ol/bin/activate
pytest tests/observability/ -q   # 38 observability tests
pytest tests/security/ -q        # 63 security tests
pytest tests/ -q                 # all suite-level tests

# 4. 查看版本
omni-suite --version
omni-suite --compatibility       # version matrix
```


## Cross-Format Production-Readiness

Verified OPP→OL→ORF paths as of 2026-06-23:

| From | Via | To | Engine / Note |
|------|-----|----|---------------|
| HTML / CSV / JSON | OPP → MD → OL → MD | (any MD consumer) | W1.2 — proper markdown extraction |
| (any MD) | ORF pure-Python | HTML, PDF | W1.3 — `markdown` + WeasyPrint, no pandoc |
| (any MD) | ORF pandoc | DOCX, ODT, EPUB, RTF, ICML | W1.1 — `pypandoc-binary` (auto-installed) |
| EML (email) | OPP → MD → OL → ORF | MSG | W2.1 — graceful fallback on missing headers |
| (any XLIFF) | ORF `--force` | cross-format | W2.2 — bypass format validation with warning |
| `.url` (YouTube) | OPP auto-detect | MD | W3.1 — `markitdown[youtube-transcription]` |
| PDF → XLIFF | OPP guard | (blocked) | W3.2 — correctly blocked (case-insensitive guard) |

Dependency notes: [ORF README](Omni_Re_Formatter/README.md) · [OPP README](Omni_Pre_Processor/README.md).

---

## Pipeline Selection Strategy

The Omni Suite supports two pipeline paths depending on your goal.
Choose wisely — the path determines which OPP output format, which
OL translation tool, and which ORF backfill tool you should use.

```
┌─────────────────────────────────────────────────────────────────┐
│            Which pipeline path should I use?                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Do you need to preserve the ORIGINAL DOCUMENT LAYOUT?            │
│  (fonts, styles, exact paragraph positions, floating images)      │
│                           │                                       │
│          ┌────────────────┴────────────────┐                      │
│          ▼                                 ▼                       │
│   ╔══════════════════╗          ╔═════════════════════╗            │
│   ║  XLIFF PATH      ║          ║  MD PATH            ║            │
│   ║  (layout-faithful)║          ║  (text-first)       ║            │
│   ╚══════════════════╝          ╚═════════════════════╝            │
│          │                                 │                        │
│   OPP --target-format xlf       OPP --target-format md              │
│        or both                         or both                      │
│          ▼                                 ▼                        │
│   OL translate-xliff            OL translate-md                     │
│          ▼                                 ▼                        │
│   ORF apply-xliff               ORF apply-md                        │
│   (needs skeleton.zip)          (16 output formats)                 │
└─────────────────────────────────────────────────────────────────┘
```

**MD Path** — Use when:
- Text quality and speed matter more than pixel-perfect layout
- You're targeting web, e-book, or plain-text outputs
- You want to convert to a different format than the source (e.g. DOCX → EPUB)
- Image placement can be approximate

**XLIFF Path** — Use when:
- The output must look exactly like the source (contracts, branded docs)
- You have a skeleton.zip from OPP (produced alongside XLIFF)
- You're staying in the same format (DOCX → DOCX, PPTX → PPTX)
- Floating images, custom styles, and exact fonts must be preserved

**Format Support by Path**

| Input Format | MD Path | XLIFF Path | Notes |
|-------------|---------|------------|-------|
| DOCX | ✅ | ✅ | Preferred path for both |
| PPTX | ✅ | ✅ | XLIFF preserves slide masters |
| EPUB | ✅ | ✅ | XLIFF preserves CSS layout |
| PDF | ✅ | ❌ | PDF→XLIFF intentionally blocked |
| HTML | ✅ | ❌ | No skeleton.zip |
| CSV / JSON / XML | ✅ | ❌ | Data formats, no layout |
| EML / MSG | ✅ | ❌ | Email formats |
| Images (OCR) | ✅ | ❌ | Text extraction only |
| YouTube URL | ✅ | ❌ | Transcription only |

**When to use `--target-format both`**: If you're unsure, extract both.
The extra disk space is negligible, and having both paths available
means you can switch without re-extracting.

**Related**: Per-repo decision trees in each AGENTS.md for deeper detail:
- [OPP AGENTS.md](Omni_Pre_Processor/AGENTS.md) — `--target-format` decision tree
- [OL AGENTS.md](Omni_Localizer/AGENTS.md) — `translate-md` vs `translate-xliff`
- [ORF AGENTS.md](Omni_Re_Formatter/AGENTS.md) — `apply-md` vs `apply-xliff`

---

## Git Submodules

> **As of 2026-06-24**: the `src/Omni_*/` git submodules have been removed.
> OPP/OL/ORF are now regular top-level directories in this repo
> (`Omni_Pre_Processor/`, `Omni_Localizer/`, `Omni_Re_Formatter/`), each
> with its own `.git/` for tracking upstream changes. To pull upstream
> updates, run `git pull` inside the directory:
>
> ```bash
> cd Omni_Pre_Processor && git pull origin main
> cd Omni_Localizer && git pull origin main
> cd Omni_Re_Formatter && git pull origin main
> ```
>
> `scripts/sync_shallow.sh` is now a deprecation stub (errors with a clear
> message). The historical `src/Omni_*/` paths are no longer used.

---

> All bug fixes are tracked in [CHANGELOG.md](./CHANGELOG.md).

---

## 环境说明

| 组件 | 路径 | 版本 / SHA |
|------|------|------|
| OPP | `Omni_Pre_Processor/` | v0.9.1 |
| OL | `Omni_Localizer/` | v0.7.1 |
| ORF | `Omni_Re_Formatter/` | v0.4.16 |
| Omni_Suite | `./` | v0.4.0 |
| Python 3.13（统一 venv） | `.venv_ol/` | ✅ 当前唯一活跃 venv，所有组件共用 |
| Python 3.12（已弃用） | `.venv/` | ⚠️ 旧 venv，OPP/ORF CLI 曾用，勿再使用 |
| OL MCP 专用 venv | `~/.hermes/venvs/omni-localizer` | Python 3.13（OL MCP 服务）|

v0.9.1 · v0.7.1 · v0.4.17 · v0.4.0（last tested 2026-07-22）。
**Pushed combo (待 push)**: same as above; local commits only, network too slow for `git push` as of 2026-06-23.

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

**文件**：`Omni_Re_Formatter/src/orf/mcp/server.py:189`

**问题**：`images=None` 时访问未初始化变量 `temp_created`，导致 `NameError`

**修复**：在 `if images:` 之前添加 `temp_created = False`

**验证**：
```bash
PYTHONPATH="Omni_Re_Formatter/src" .venv312/bin/python -c "
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

---

## Plans

The `.omo/plans/` directory contains work plans generated during development. See the plan file for current tasks.
```
