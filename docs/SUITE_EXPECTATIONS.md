# Omni Suite — Founder's Expectations + Agent Validation Master Plan

> **版本**: v0.4.0 · **日期**: 2026-07-22
> **范围**: Suite-level（套件层，非单个模块）
> **作用**: 定义创始人期望 + 提供 AI agent 可执行的验证场景

---

## Part 1: Founder's Expectations（创始人期望）

### 1.1 什么是 Omni Suite？

> **一条命令，三步走，文档本地化全链路。**

Omni Suite 是一个三阶段文档本地化流水线，将源文档从一种语言提取、翻译、回写到目标格式：

| 阶段 | 模块 | 职责 | 版本 |
|------|------|------|------|
| 1 | **OPP** (Omni_Pre_Processor) | 提取源文档 → MD + XLIFF + skeleton.zip | v0.9.1 |
| 2 | **OL** (Omni_Localizer) | 翻译 MD/XLIFF 在语言之间 | v0.7.1 |
| 3 | **ORF** (Omni_Re_Formatter) | 回写翻译后的内容到目标文档 | v0.4.17 |

三个模块**独立发布、独立 CLI、独立 MCP 服务**，通过文件工件握手（`.md` + `.xlf` + `manifest.json` + `skeleton.zip`）。

### 1.2 设计原则

| 原则 | 含义 |
|------|------|
| **双通道（Two channels）** | MD 通道（文本优先）和 XLIFF 通道（布局保真），按需选择 |
| **FAKE_LLM 缝（FAKE_LLM seam）** | `OMNI_TEST_FAKE_LLM=1` 即可零成本测试，无需真实 API key |
| **独立可组合（Independent）** | 三个模块可独立升级，版本组合由兼容矩阵保证 |
| **MCP 原生（Agent-native）** | 所有能力以 MCP 工具暴露（9+21+7=37 个模块工具；加 suite 4 个 = 41），CLI 是后备 |
| **回写 16 格式（16 output formats）** | ORF `apply-md` 支持 16 种目标格式 |
| **一次提取，两路可用（`--both`）** | `--target-format both` 同时产出 MD+XLIFF，无需重复提取 |
| **诚实面对差距（Honest about gaps）** | 本文档如实记录已知限制 |

### 1.3 用户类型

| 角色 | 说明 | 界面 |
|------|------|------|
| **流水线操作者（Pipeline operator）** | AI agent 或人类，调用套件完成本地化任务 | MCP 工具（首选）、CLI（后备） |
| **开发者（Developer）** | 集成、扩展、调试套件或单个模块 | CLI、Python API、测试 |
| **最终消费者（End-user）** | 消费翻译后的文档（通常不直接操作套件） | 翻译完成的文件 |

### 1.4 期望目录（Expectation Catalog）

按用户旅程阶段组织。

---

#### Phase 1: Setup（安装与验证）

> "我应该能在 5 分钟内安装并验证三个模块都已就绪。"

| ID | 期望 | 验证方式 |
|----|------|----------|
| **F1** | `bash scripts/setup_dev.sh` 一键安装，自动检测 Python ≥ 3.13，创建 `.venv_ol/` | 执行脚本，exit code 0 |
| **F2** | 三个 CLI（`opp`、`ol`、`orf`）可调用，`--help` 显示帮助 | 各执行一次 `--help` |
| **F3** | `omni-suite --version` 显示 v0.4.0 | 执行命令 |
| **F4** | 版本兼容矩阵与当前版本一致 | `omni-suite --compatibility` 或读取 `COMPATIBILITY.md` |
| **F5** | `OMNI_TEST_FAKE_LLM=1` 环境下可零成本跑完整流水线 | 执行完整 DOCX 流水线（见 Q2-S） |
| **F6** | 三个 MCP 服务器可启动并响应 `ping` | 分别启动并调用 ping 工具（见 Q6-S） |

---

#### Phase 2: Pipeline Selection（流水线选择）

> "我需要在 MD 路径和 XLIFF 路径之间做出正确选择。"

| ID | 期望 | 判断条件 |
|----|------|----------|
| **F7** | **MD 路径**：文本优先，支持 16 种回写格式，适合跨格式转换（如 DOCX→EPUB） | 目标格式与源格式不同时用 MD 路径 |
| **F8** | **XLIFF 路径**：布局保真，需要 skeleton.zip，只能同格式回写（DOCX→DOCX） | 需要精确还原原布局时用 XLIFF 路径 |
| **F9** | 不确定时用 `--target-format both` 同时产出，不丢选择权 | OPP 提取时指定 both |
| **F10** | PDF 无法走 XLIFF 路径（OPP 明确阻止），只能 MD 路径 | PDF→XLIFF 返回明确错误 |

决策树已在 `README.md` 中完整图示。

---

#### Phase 3: End-to-End Pipeline（端到端流水线）

> "我能对 DOCX、PPTX、EPUB 三种源格式跑通完整流水线。"

| ID | 期望 | 路径 |
|----|------|------|
| **F11** | DOCX → OPP(extract) → OL(translate-md) → ORF(apply-md) → result.docx | MD 路径 |
| **F12** | DOCX → OPP(both) → OL(translate-xliff) → ORF(apply-xliff) → result.docx | XLIFF 路径 |
| **F13** | PPTX → OPP(extract) → OL(translate) → ORF → result.pptx | 双路径 |
| **F14** | EPUB → OPP(extract) → OL(translate) → ORF → result.epub | 双路径 |
| **F15** | `--target-format both` 同时产出 .md + .xlf + skeleton.zip + manifest.json | 验证输出文件完整性 |

---

#### Phase 4: Cross-Format Backfill（跨格式回写）

> "我能把 DOCX 翻译后输出为 EPUB，也能把 XLIFF 强制回写到不同的格式。"

| ID | 期望 | 注意 |
|----|------|------|
| **F16** | DOCX → OPP(MD) → OL → ORF(apply-md) → EPUB | 跨格式标准路径 |
| **F17** | DOCX → OPP(XLIFF) → OL → ORF(apply-xliff --force) → PPTX | 跨格式 XLIFF 需要 `--force` |
| **F18** | 跨格式回写时 ORF 给出明确警告 | `--force` 使覆盖显式化 |
| **F19** | 不兼容的格式组合给出可理解的错误信息 | 不静默失败 |

---

#### Phase 5: Agent Operation（Agent 操作）

> "AI agent 可以启动三个 MCP 服务、发现工具、串联调用。"

| ID | 期望 | 说明 |
|----|------|------|
| **F20** | MCP 服务器名称不一致（`opp-mcp-server`、`ol-mcp`、`orf-mcp-server`）但协议一致 | 已知历史不一致，不改 |
| **F21** | Agent 可发现工具列表（OPP 7 工具、OL 21 工具、ORF 6 工具） | 通过 MCP 协议自动发现 |
| **F22** | 三个 `ping` 工具均返回 `{"success": true}` | 健康检查 |
| **F23** | Agent 可串联调用：OPP extract → OL translate → ORF apply | 传递 output_dir 参数 |
| **F24** | `OL_CONFIG_PATH` 可覆盖 OL LLM 配置 | 环境变量覆盖 |
| **F25** | `OPP_ALLOWED_DIRECTORIES` / `ORF_ALLOWED_DIRECTORIES` 路径校验生效 | 安全边界 |

---

#### Phase 6: Error Recovery（错误恢复）

> "系统在出错时不崩溃，给出清晰原因和修复建议。"

| ID | 期望 | 错误场景 |
|----|------|----------|
| **F26** | 源文件不存在时 → 明确错误信息，非 traceback | `File not found` |
| **F27** | 缺少 skeleton.zip 时 → "请先运行 OPP save_skeleton" | ORF apply-xliff 缺少骨架 |
| **F28** | 未设置 `OMNI_TEST_FAKE_LLM` 且无真实 LLM key → OL 给出友好错误 | LLM 未配置 |
| **F29** | pandoc 缺失时 → "请安装 pandoc 或设置 OMNI_TEST_FAKE_PANDOC=1" | 依赖缺失 |
| **F30** | module A 失败不影响 module B | 错误隔离 |

---

#### Phase 7: Compatibility & Versioning（兼容性）

> "升级版本不打破现有功能。"

| ID | 期望 | 机制 |
|----|------|------|
| **F31** | 版本组合记录在 `COMPATIBILITY.md`，每个组合经过 E2E 测试 | 兼容矩阵 |
| **F32** | `pytest tests/integration/test_version_compat.py` 验证当前组合 | 集成测试 |
| **F33** | `scripts/setup_dev.sh` 断言子模块版本匹配矩阵 | 安装时校验 |
| **F34** | 模块独立 SemVer，公共表面（CLI flag、MCP 工具名和 schema）稳定 | API_STABILITY.md |

---

### 1.5 质量门（Quality Gates）

| ID | 门 | 标准 |
|----|----|------|
| **Q1** | 流水线完整无数据丢失 | 提取的文本字数 ≥ 源文档字数的 95%（翻译前后） |
| **Q2** | 文本保真度：提取文本 ≈ 翻译文本 ≈ 回写文本（往返） | `fidelity_checker.py compute_fidelity()` ≥ 0.9（真实 LLM）、≥ 0.0（FAKE_LLM） |
| **Q3** | 图片保留数 | 回写后的图片数量 ≥ 源文档图片数（浮动图片+内联图片） |
| **Q4** | 格式支持完整度 | 16 种 ORF 回写格式均可由至少一种路径到达；36 路径矩阵已验证 |

---

### 1.6 核心价值评估

| 承诺 | 现状 | 差距 |
|------|------|------|
| **"一键安装，三模块就绪"** | ✅ `setup_dev.sh` + `.venv_ol/` 统一 venv | — |
| **"三种格式端到端"** | ✅ DOCX/PPTX/EPUB 均已验证 | — |
| **"双通道任选"** | ✅ MD 路径（16 格式）+ XLIFF 路径（布局保真） | — |
| **"跨格式转换"** | ✅ DOCX→EPUB（标准），XLIFF→PPTX（需 --force） | — |
| **"Agent 原生"** | ✅ 34 个 MCP 工具，三个独立服务器 | 服务器命名不一致 `ol-mcp` vs `*-server` |
| **"零成本测试"** | ✅ FAKE_LLM seam + FAKE_PANDOC seam | T14 已修复（span_aligner 模拟） |
| **"安全边界"** | ✅ PathValidator + 共享密钥 + 速率限制 | ORF MCP 默认 CWD（fail-open，需显式配置） |
| **"版本兼容保障"** | ✅ 兼容矩阵 + 集成测试 | 仍处 v0.x 阶段，前 1.0 可能有破坏性变更 |

---

### 1.7 当前现实（v0.4.0）

| 方面 | 状态 |
|------|------|
| **输入格式** | 13+（DOCX, PPTX, PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, images, IPYNB, YouTube URL） |
| **回写格式** | 16（DOCX, ODT, EPUB, HTML, RTF, PDF, PPTX, ICML, SRT, CSV, XLSX, XML, IPYNB, EML, MSG, JSON） |
| **MCP 工具总数** | 37 模块工具（9 + 21 + 7）；加 suite 4 个 = 41 |
| **兼容性** | Suite v0.4.0 / OPP v0.9.1 / OL v0.7.1 / ORF v0.4.17 |
| **已知限制** | PDF→XLIFF 阻止（有意）；MSG 输出需要 Aspose.Email（建议用 .eml）；ORF MCP fail-open（需设置 `ORF_ALLOWED_DIRECTORIES`）；`omni-suite mcp` 是 print-only |
| **Python 版本** | ≥ 3.13，统一 `.venv_ol/` |

---

## Part 2: Agent Validation Master Plan（Agent 验证主计划）

> **策略**: 每个章节是一个用户问题 → 执行场景 → 报告通过/失败

### 验证符号

| 符号 | 含义 |
|------|------|
| ✅ | 场景通过 |
| ❌ | 场景失败 |
| ⚠️ | 部分通过（列出失败项） |
| ➖ | 跳过（记录原因） |

---

### Q1-S: 安装验证 — 三个模块是否就绪？

**用户说：** "我想装一下套件，确认三个模块都能用。"

**为什么重要：** 安装是用户第一接触点。如果 `setup_dev.sh` 失败，什么都做不了。

**前置条件：**
```bash
python3 --version  # 要求 ≥ 3.13
```

**场景 1.1: 一键安装**
```bash
bash scripts/setup_dev.sh --check-only
```
**预期结果:**
- ✅ Exit code 0
- ✅ 输出 Python 版本 ≥ 3.13
- ✅ 所有模块版本正确

**实际结果:** _________ **PASS / FAIL:** _________

**场景 1.2: CLI 可调用**
```bash
opp --help && echo "---" && ol --help && echo "---" && orf --help
```
**预期结果：**
- ✅ 三个 CLI 均输出帮助信息
- ✅ 无 ImportError 或 ModuleNotFoundError

**实际结果:** _________ **PASS / FAIL:** _________

**场景 1.3: 统一 venv 存在**
```bash
ls .venv_ol/bin/python && .venv_ol/bin/python --version
```
**预期结果：** ✅ Python ≥ 3.13

**实际结果:** _________ **PASS / FAIL:** _________

**场景 1.4: 套件版本正确**
```bash
omni-suite --version
```
**预期结果：** ✅ 输出 `v0.4.0`

**实际结果:** _________ **PASS / FAIL:** _________

### 📊 Q1-S 裁决

| 场景 | 结果 |
|------|------|
| 1.1 一键安装 | ⬜ |
| 1.2 CLI 可调用 | ⬜ |
| 1.3 统一 venv | ⬜ |
| 1.4 套件版本 | ⬜ |
| **总体** | ⬜ |

---

### Q2-S: DOCX 端到端（MD 路径）

**用户说：** "给我跑一个完整的 DOCX 翻译流水线，从提取到回写。"

**为什么重要：** DOCX 是最常见的输入格式。MD 路径是最常用的路径。

**前置条件：**
```bash
export OMNI_TEST_FAKE_LLM=1
```

**场景 2.1: 完整 MD 路径**
```bash
cd /tmp && rm -rf test_docx_md && mkdir test_docx_md && cd test_docx_md
# 准备测试文件（使用 OPP 自带的测试文件或生成一个最小 DOCX）
opp /mnt/d/贯维/Omni_Suite/Omni_Pre_Processor/tests/fixtures/sample.docx \
  --target-format md --output-dir ./opp_out --source-lang en --target-lang zh
ls opp_out/
```
**预期结果:**
- ✅ Exit code 0
- ✅ `opp_out/sample.md` 存在，包含 YAML frontmatter
- ✅ `opp_out/images.json` 存在（如果文档有图片）

**实际结果:** _________ **PASS / FAIL:** _________

```bash
ol translate-md opp_out/sample.md -s en -t zh -o ./ol_out
```
**预期结果:**
- ✅ Exit code 0
- ✅ `ol_out/sample.md` 存在，内容是翻译后的（FAKE_LLM 返回模拟翻译）

**实际结果:** _________ **PASS / FAIL:** _________

```bash
orf apply-md ol_out/sample.md --target-format docx -o ./result.docx
```
**预期结果:**
- ✅ Exit code 0
- ✅ `result.docx` 存在且是有效 ZIP 文件

**实际结果:** _________ **PASS / FAIL:** _________

**场景 2.2: 输出文件有效性**
```bash
python3 -c "
import zipfile
with zipfile.ZipFile('./result.docx') as z:
    names = z.namelist()
    print(f'Valid DOCX: {len(names)} entries')
    assert 'word/document.xml' in names, 'Missing word/document.xml'
    print('OK')
"
```
**预期结果：** ✅ 是有效 DOCX（含 `word/document.xml`）

**实际结果:** _________ **PASS / FAIL:** _________

### 📊 Q2-S 裁决

| 场景 | 结果 |
|------|------|
| 2.1 MD 路径完整链 | ⬜ |
| 2.2 DOCX 有效性 | ⬜ |
| **总体** | ⬜ |

---

### Q3-S: DOCX 端到端（XLIFF 路径）

**用户说：** "我要布局保真的翻译，不损失原文样式。"

**为什么重要：** XLIFF 路径保留内联格式标签，适合合同、品牌文档。

**前置条件：**
```bash
export OMNI_TEST_FAKE_LLM=1
```

**场景 3.1: 完整 XLIFF 路径**
```bash
cd /tmp && rm -rf test_docx_xlf && mkdir test_docx_xlf && cd test_docx_xlf
opp /mnt/d/贯维/Omni_Suite/Omni_Pre_Processor/tests/fixtures/sample.docx \
  --target-format both --output-dir ./opp_out --source-lang en --target-lang zh
ls opp_out/
```
**预期结果:**
- ✅ `opp_out/sample.md`（MD）
- ✅ `opp_out/sample.xlf`（XLIFF）
- ✅ `opp_out/sample_manifest.json`（清单）
- ✅ `opp_out/sample.skeleton.zip`（骨架）

**实际结果:** _________ **PASS / FAIL:** _________

```bash
ol translate-xliff opp_out/sample.xlf -s en -t zh -o ./ol_out
```
**预期结果:** ✅ `ol_out/sample.xlf` 存在，target 已填充

**实际结果:** _________ **PASS / FAIL:** _________

```bash
orf apply-xliff opp_out/sample.skeleton.zip \
  --xliff ol_out/sample.xlf --output ./result.docx --format docx
```
**预期结果:**
- ✅ Exit code 0
- ✅ `result.docx` 存在，布局与源文档一致

**实际结果:** _________ **PASS / FAIL:** _________

### 📊 Q3-S 裁决

| 场景 | 结果 |
|------|------|
| 3.1 OPP both 输出 | ⬜ |
| 3.2 OL translate-xliff | ⬜ |
| 3.3 ORF apply-xliff | ⬜ |
| **总体** | ⬜ |

---

### Q4-S: PPTX 端到端

**用户说：** "我有个 PPT 需要翻译，保持幻灯片布局。"

**为什么重要：** PPTX 是重要的企业格式，XLIFF 路径保持幻灯片母版。

**前置条件：**
```bash
export OMNI_TEST_FAKE_LLM=1
```

**场景 4.1: PPTX MD 路径**
```bash
cd /tmp && rm -rf test_pptx && mkdir test_pptx && cd test_pptx
opp /mnt/d/贯维/Omni_Suite/Omni_Pre_Processor/tests/fixtures/sample.pptx \
  --target-format both --output-dir ./opp_out --source-lang en --target-lang zh
ol translate-md opp_out/sample.md -s en -t zh -o ./ol_out
orf apply-md ol_out/sample.md --target-format pptx -o ./result.pptx
```
**预期结果：** ✅ `result.pptx` 存在且是有效 PPTX

**实际结果:** _________ **PASS / FAIL:** _________

**场景 4.2: PPTX XLIFF 路径**
```bash
ol translate-xliff opp_out/sample.xlf -s en -t zh -o ./ol_out_xlf
orf apply-xliff opp_out/sample.skeleton.zip \
  --xliff ol_out_xlf/sample.xlf --output ./result_pptx.pptx --format pptx
```
**预期结果：** ✅ `result_pptx.pptx` 存在，幻灯片数量一致

**实际结果:** _________ **PASS / FAIL:** _________

### 📊 Q4-S 裁决

| 场景 | 结果 |
|------|------|
| 4.1 PPTX MD 路径 | ⬜ |
| 4.2 PPTX XLIFF 路径 | ⬜ |
| **总体** | ⬜ |

---

### Q5-S: 跨格式转换（DOCX→EPUB）

**用户说：** "把这份 DOCX 翻译后输出成 EPUB 电子书。"

**为什么重要：** 跨格式转换是核心场景之一，EPUB 是重要的电子书格式。

**前置条件：**
```bash
export OMNI_TEST_FAKE_LLM=1
```

**场景 5.1: DOCX→MD→OL→ORF→EPUB**
```bash
cd /tmp && rm -rf test_cross && mkdir test_cross && cd test_cross
opp /mnt/d/贯维/Omni_Suite/Omni_Pre_Processor/tests/fixtures/sample.docx \
  --target-format md --output-dir ./opp_out --source-lang en --target-lang zh
ol translate-md opp_out/sample.md -s en -t zh -o ./ol_out
orf apply-md ol_out/sample.md --target-format epub -o ./result.epub
```
**预期结果：** ✅ `result.epub` 存在且是有效 EPUB（ZIP 含 `OEBPS/`）

**实际结果:** _________ **PASS / FAIL:** _________

**场景 5.2: XLIFF 跨格式（需 --force）**
```bash
opp sample.docx --target-format both --output-dir ./opp2
ol translate-xliff opp2/sample.xlf -s en -t zh -o ./ol2
orf apply-xliff opp2/sample.skeleton.zip \
  --xliff ol2/sample.xlf --output ./out.pptx --format pptx --force
```
**预期结果：**
- ✅ Exit code 0（因为 --force）
- ✅ 输出文件存在
- ⚠️ 警告信息提醒跨格式覆盖

**实际结果:** _________ **PASS / FAIL:** _________

### 📊 Q5-S 裁决

| 场景 | 结果 |
|------|------|
| 5.1 DOCX→EPUB | ⬜ |
| 5.2 XLIFF 跨格式 --force | ⬜ |
| **总体** | ⬜ |

---

### Q6-S: MCP 服务器健康检查

**用户说：** "三个 MCP 服务器都能启动并响应 ping 吗？"

**为什么重要：** Agent 依赖 MCP 服务器运行。如果服务器连不上，agent 什么都做不了。

**前置条件：**
```bash
export OMNI_TEST_FAKE_LLM=1
export OPP_ALLOWED_DIRECTORIES="/tmp"
```

**场景 6.1: OPP MCP ping**
```bash
cd Omni_Pre_Processor && PYTHONPATH=src python -c "
import asyncio
from opp.mcp.server import ping
result = asyncio.run(ping(auth_token=None))
print(result)
assert result.get('success') == True
print('OPP MCP OK')
"
```
**预期结果：** ✅ `{"success": true}`

**实际结果:** _________ **PASS / FAIL:** _________

**场景 6.2: OL MCP ping**
```bash
cd Omni_Localizer && PYTHONPATH=src python -c "
import asyncio
from ol_mcp.tools import ping
result = asyncio.run(ping())
print(result)
assert 'success' in result
print('OL MCP OK')
"
```
**预期结果：** ✅ 响应包含 `success`

**实际结果:** _________ **PASS / FAIL:** _________

**场景 6.3: ORF MCP ping**
```bash
cd Omni_Re_Formatter && PYTHONPATH=src python -c "
from orf.mcp.server import ping
import json
result = json.loads(ping())
print(result)
assert result.get('success') == True
print('ORF MCP OK')
"
```
**预期结果：** ✅ `{"success": true}`

**实际结果:** _________ **PASS / FAIL:** _________

**场景 6.4: 工具数量验证**
```python
# OPP: 9 tools (extract_document, batch_extract, detect_format_tool,
#       generate_markdown, generate_xliff, save_skeleton, ping,
#       validate_xliff, get_capabilities)
# OL: 21 tools (translate_md_text, translate_xliff, judge_text, ...)
# ORF: 7 tools (apply_md, apply_xliff, batch_convert, detect_format, info,
#       ping, get_capabilities)
# 总计: 9 + 21 + 7 = 37 个模块工具；加 suite 4 个 = 41
```
**预期结果：** ✅ OPP 9 工具 / OL 21 工具 / ORF 7 工具

**实际结果:** _________ **PASS / FAIL:** _________

### 📊 Q6-S 裁决

| 场景 | 结果 |
|------|------|
| 6.1 OPP MCP ping | ⬜ |
| 6.2 OL MCP ping | ⬜ |
| 6.3 ORF MCP ping | ⬜ |
| 6.4 工具数量 | ⬜ |
| **总体** | ⬜ |

---

### Q7-S: MCP 工具链串联调用

**用户说：** "我在 agent 里怎么把三个 MCP 串起来？"

**为什么重要：** 这是 agent 做端到端翻译的标准模式。

**前置条件：**
```bash
export OMNI_TEST_FAKE_LLM=1
export OPP_ALLOWED_DIRECTORIES="/tmp"
```

**场景 7.1: 三工具链调用（MCP JSON 格式）**
```json
[
  {
    "tool": "extract_document",
    "params": {
      "file_path": "/path/to/document.docx",
      "target_format": "both",
      "source_lang": "en",
      "target_lang": "zh",
      "output_dir": "/tmp/opp_out"
    }
  },
  {
    "tool": "translate_md_text",
    "params": {
      "file_path": "/tmp/opp_out/document.md",
      "source_lang": "en",
      "target_lang": "zh",
      "output_dir": "/tmp/ol_out"
    }
  },
  {
    "tool": "apply_md",
    "params": {
      "file_path": "/tmp/ol_out/document.md",
      "target_format": "docx",
      "output_path": "/tmp/result.docx"
    }
  }
]
```
**预期结果：** ✅ 三个工具依次调用成功，无报错

**实际结果:** _________ **PASS / FAIL:** _________

### 📊 Q7-S 裁决

| 场景 | 结果 |
|------|------|
| 7.1 三工具链 | ⬜ |
| **总体** | ⬜ |

---

### Q8-S: 错误输入处理

**用户说：** "如果文件不存在或损坏了会怎样？"

**为什么重要：** 系统必须优雅处理错误输入，不崩溃。

**场景 8.1: 不存在的文件**
```bash
opp /tmp/nonexistent_file.docx --target-format md --output-dir /tmp/out 2>&1; echo "EXIT: $?"
```
**预期结果：**
- ❌ Exit code ≠ 0
- ✅ 错误信息清晰（非 Python 堆栈）
- ✅ 不含 `Traceback`

**实际结果:** _________ **PASS / FAIL:** _________

**场景 8.2: 损坏的 XLIFF 输入**
```bash
echo "garbage" > /tmp/bad.xlf
ol translate-xliff /tmp/bad.xlf -s en -t zh -o /tmp/ol_out 2>&1; echo "EXIT: $?"
```
**预期结果：** ❌ Exit code ≠ 0，错误信息可理解

**实际结果:** _________ **PASS / FAIL:** _________

**场景 8.3: 缺少 skeleton.zip 时 apply-xliff**
```bash
orf apply-xliff /tmp/nonexistent.zip --xliff some.xlf --output /tmp/out.docx --format docx 2>&1; echo "EXIT: $?"
```
**预期结果：** ❌ "请先运行 OPP save_skeleton" 或类似信息

**实际结果:** _________ **PASS / FAIL:** _________

### 📊 Q8-S 裁决

| 场景 | 结果 |
|------|------|
| 8.1 不存在的文件 | ⬜ |
| 8.2 损坏的 XLIFF | ⬜ |
| 8.3 缺少 skeleton | ⬜ |
| **总体** | ⬜ |

---

### Q9-S: FAKE_LLM 环境配置

**用户说：** "我能不设置 API key 就跑通测试吗？"

**为什么重要：** FAKE_LLM 是 CI/CD 和本地开发的基础设施，确保零成本可测试性。

**场景 9.1: 已设置 FAKE_LLM → 成功**
```bash
export OMNI_TEST_FAKE_LLM=1
cd /tmp && rm -rf test_fake && mkdir test_fake && cd test_fake
opp sample.docx --target-format md --output-dir opp_out
ol translate-md opp_out/sample.md -s en -t zh -o ol_out
echo "FAKE_LLM pipeline OK"
```
**预期结果：** ✅ 三步均 exit code 0

**实际结果:** _________ **PASS / FAIL:** _________

**场景 9.2: 未设置 FAKE_LLM 且无 API key → 友好错误**
```bash
unset OMNI_TEST_FAKE_LLM
ol translate-md opp_out/sample.md -s en -t zh -o /tmp/ol_no_key 2>&1; echo "EXIT: $?"
```
**预期结果：** ❌ Exit code ≠ 0，错误提及 LLM API key

**实际结果:** _________ **PASS / FAIL:** _________

### 📊 Q9-S 裁决

| 场景 | 结果 |
|------|------|
| 9.1 FAKE_LLM 设置 | ⬜ |
| 9.2 FAKE_LLM 未设置 | ⬜ |
| **总体** | ⬜ |

---

### Q10-S: Pandoc 缺失

**用户说：** "我没有安装 pandoc，DOCX 回写能行吗？"

**为什么重要：** 部分格式（DOCX、ODT、EPUB）依赖 pandoc，但系统应给出明确提示。

**场景 10.1: pandoc 缺失时 apply-md 给出提示**
```bash
export OMNI_TEST_FAKE_PANDOC=1  # 模拟 pandoc 缺失
orf apply-md /tmp/test.md --target-format docx -o /tmp/out.docx 2>&1; echo "EXIT: $?"
```
**预期结果：**
- ✅ Exit code 0（FAKE_PANDOC 绕过）
- 或者 ❌ 错误提到 "pandoc not found"

**实际结果:** _________ **PASS / FAIL:** _________

**场景 10.2: 设置 FAKE_PANDOC 可绕过**
```bash
export OMNI_TEST_FAKE_PANDOC=1
orf apply-md /tmp/test.md --target-format docx -o /tmp/out.docx 2>&1
echo "EXIT: $?"
ls -la /tmp/out.docx 2>&1
```
**预期结果：** ✅ Exit code 0，输出文件存在

**实际结果:** _________ **PASS / FAIL:** _________

### 📊 Q10-S 裁决

| 场景 | 结果 |
|------|------|
| 10.1 pandoc 缺失提示 | ⬜ |
| 10.2 FAKE_PANDOC 绕过 | ⬜ |
| **总体** | ⬜ |

---

### Q11-S: 版本兼容矩阵

**用户说：** "当前三个模块的版本组合是经过测试的吗？"

**为什么重要：** 独立发布的模块可能产生不兼容组合，兼容矩阵是保障。

**场景 11.1: 读取兼容矩阵**
```bash
cat COMPATIBILITY.md | head -20
```
**预期结果：** ✅ 最新行显示 Suite v0.4.0 / OPP v0.9.1 / OL v0.7.1 / ORF v0.4.17

**实际结果:** _________ **PASS / FAIL:** _________

**场景 11.2: 集成测试通过**
```bash
source .venv_ol/bin/activate
pytest tests/integration/test_version_compat.py -v 2>&1 | tail -10
```
**预期结果：** ✅ 测试通过（PASSED）

**实际结果:** _________ **PASS / FAIL:** _________

**场景 11.3: 版本与 pyproject.toml 一致**
```bash
python3 -c "
import importlib.metadata
print('opp:', importlib.metadata.version('omni-pre-processor'))
print('ol:', importlib.metadata.version('omni-localizer'))
print('orf:', importlib.metadata.version('omni-re-formatter'))
"
cat VERSION
```
**预期结果：** ✅ 版本号与 COMPATIBILITY.md 一致

**实际结果:** _________ **PASS / FAIL:** _________

### 📊 Q11-S 裁决

| 场景 | 结果 |
|------|------|
| 11.1 兼容矩阵 | ⬜ |
| 11.2 集成测试 | ⬜ |
| 11.3 版本一致性 | ⬜ |
| **总体** | ⬜ |

---

### Q12-S: E2E 测试套件

**用户说：** "套件自带的测试能全跑通吗？"

**为什么重要：** 测试是软件质量的客观度量。E2E 测试验证各个流水线路径的正确性。

**前置条件：**
```bash
export OMNI_TEST_FAKE_LLM=1
source .venv_ol/bin/activate
```

**场景 12.1: 安全测试套件**
```bash
pytest tests/security/ -q 2>&1 | tail -5
```
**预期结果：** ✅ 63/63 pass

**实际结果:** _________ **PASS / FAIL:** _________

**场景 12.2: 可观测性测试**
```bash
pytest tests/observability/ -q 2>&1 | tail -5
```
**预期结果：** ✅ 38 tests pass（或相关计数）

**实际结果:** _________ **PASS / FAIL:** _________

**场景 12.3: 完整套件收集**
```bash
pytest tests/ --collect-only -q 2>&1 | tail -3
```
**预期结果：** ✅ 测试可正常收集，无语法错误

**实际结果:** _________ **PASS / FAIL:** _________

**场景 12.4: 预提交烟雾测试（manual）**
```bash
pre-commit run omni-contract-smoke --all-files 2>&1
```
**预期结果：** ✅ 通过（需要 `.venv_ol` 已构建）或 ➖ 跳过

**实际结果:** _________ **PASS / FAIL:** _________

### 📊 Q12-S 裁决

| 场景 | 结果 |
|------|------|
| 12.1 安全测试 | ⬜ |
| 12.2 可观测性测试 | ⬜ |
| 12.3 收集测试 | ⬜ |
| 12.4 预提交烟雾 | ⬜ |
| **总体** | ⬜ |

---

## Final Verdict（最终裁决）

### 全局通过条件

| 条件 | 状态 |
|------|------|
| **所有 Q1-S ~ Q12-S 全部 PASS** → ✅ 套件通过验证 |
| **部分 FAIL** → ⚠️ 标记失败项，制定修复计划 |
| **全部 FAIL** → ❌ 套件不可用，需重新评估 |

### 总表决

| 问题 | 结果 |
|------|------|
| Q1-S: 安装 | ⬜ |
| Q2-S: DOCX MD 路径 | ⬜ |
| Q3-S: DOCX XLIFF 路径 | ⬜ |
| Q4-S: PPTX 端到端 | ⬜ |
| Q5-S: 跨格式转换 | ⬜ |
| Q6-S: MCP 健康检查 | ⬜ |
| Q7-S: MCP 链调用 | ⬜ |
| Q8-S: 错误输入 | ⬜ |
| Q9-S: FAKE_LLM | ⬜ |
| Q10-S: Pandoc 缺失 | ⬜ |
| Q11-S: 版本兼容 | ⬜ |
| Q12-S: E2E 测试 | ⬜ |
| **OVERALL** | ⬜ |

---

### 执行验证的推荐顺序

```
1. Q1-S   (安装)     → 基础通断测试
2. Q9-S   (FAKE_LLM) → 确保零成本环境
3. Q11-S  (兼容性)   → 确认版本匹配
4. Q6-S   (MCP ping) → 服务健康
5. Q2-S   (DOCX MD)  → 核心流水线
6. Q3-S   (DOCX XLIFF) → 核心流水线
7. Q4-S   (PPTX)     → 第二种格式
8. Q5-S   (跨格式)   → 高级场景
9. Q7-S   (MCP 链)   → Agent 场景
10. Q8-S  (错误处理) → 健壮性
11. Q10-S (Pandoc)   → 依赖处理
12. Q12-S (E2E 测试) → 全面回归
```

---

> **维护说明**: 每个 Suite 版本更新时，更新 `COMPATIBILITY.md` 版本行和本文档的版本号。
> 新增模块/工具时在对应 Q 中添加新场景。
> 发现新错误时记录到 `reports/` 目录并通过 Q 场景验证修复。
