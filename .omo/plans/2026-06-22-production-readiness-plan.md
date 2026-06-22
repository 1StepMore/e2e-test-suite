# Omni Suite Production Readiness Plan (2026-06-22)

## 1. Background & Context

### 1.1 项目目标（用户明确诉求）

三个模块 **OPP**、**OL**、**ORF** 必须满足以下要求，**全部满足，不可取舍**：

1. **独立可用**：每个模块可单独 `pip install`，有自己的 CLI/MCP，可独立部署
2. **组合可用**：三个模块能串联成完整 omni-suite 流水线
3. **开箱即用**：客户和 AI agent 部署后无需额外配置即可使用
4. **产品质量过硬**：测试矩阵全绿，真实场景可用
5. **工程完善**：可观测、安全、有文档、有 SLA

### 1.2 当前状态摘要

| 维度 | 状态 |
|------|------|
| 测试矩阵基础设施 | ✅ 完成（Tier 7 + Tier 8，195 单元格） |
| CLI 流水线 | ✅ 工作中（131/131 PASS, 0 FAIL） |
| CLI 确定性 | ✅ 工作中（131/131 byte-identical） |
| **真实 MCP 服务器** | ❌ **不工作**（FastMCP 3.4.2 stdio bug） |
| **真实 LLM 集成** | ❌ **未验证**（只测了 FAKE_LLM） |
| **真实文档测试** | ❌ **未验证**（只测了 5 个手工文档） |
| **端到端部署** | ❌ **未验证**（没测 `pip install` 流程） |
| **用户文档** | ❌ **缺失**（只有开发者 AGENTS.md） |
| **错误处理 UX** | ❌ **未测试** |
| **可观测性** | ❌ **缺失**（无 metrics、tracing、结构化日志） |
| **安全审计** | ❌ **未做** |
| **性能基准** | ❌ **缺失**（无 SLA） |
| **跨平台** | ❌ **未测**（只在 Linux 测） |

### 1.3 已交付的 commits（截至 2026-06-22）

| SHA | Repo | 主题 |
|-----|------|------|
| `a847bf9` | e2e-test-suite | Tier 8 gate requires MCP PASS |
| `b183379` | e2e-test-suite | docs: MCP stdio FIXED |
| `c6197f8` | e2e-test-suite | raw stdio bridge + MCP matrix |
| `5d288b1` | e2e-test-suite | EPUB fixture determinism + equiv field-order fix |
| `2fc8d95` | e2e-test-suite | regression tests + matrix gaps doc |
| `e246eda` | e2e-test-suite | 4-dimension matrix coverage |
| `4187ac1` | Omni_Pre_Processor | OPP: deterministic HTML tag iteration |
| `f7d3316` | Omni_Pre_Processor | OPP: sort EPUB items |
| `684d6d6` | Omni_Pre_Processor | OPP: force stdio transport |
| `12f9769` | Omni_Re_Formatter | ORF: clear error on cross-format skeleton |
| `8120cbc` | Omni_Re_Formatter | ORF: force stdio transport |

---

## 2. 全维度标准矩阵

下表列出所有需要满足的标准，按"是否已满足"分类。这是验收的唯一依据。

### 2.1 已满足（绿色）

| ID | 类别 | 标准 | 证据 |
|----|------|------|------|
| S01 | 测试 | 195 单元格全维度矩阵 | Tier 7/8 验证通过 |
| S02 | 测试 | 回归测试覆盖所有 bug fix | 5+ regression tests pass |
| S03 | 测试 | 自动捕获非确定性 bug | Tier 8 发现 3 个真实 bug |
| S04 | 测试 | 测试可重复性（131/131 byte-identical） | MD5 校验 |
| S05 | CI | Tier 8 自动运行 | omo_loop.py --gate tier8 |
| S06 | CLI | OPP CLI 可独立运行 | 矩阵验证 |
| S07 | CLI | OL CLI 可独立运行 | 矩阵验证 |
| S08 | CLI | ORF CLI 可独立运行 | 矩阵验证 |
| S09 | CLI | 三个模块可串联成流水线 | 矩阵验证 |
| S10 | 多格式 | 11 输入格式支持 | 矩阵覆盖 |
| S11 | 多格式 | 15 MD 输出格式支持 | 矩阵覆盖 |
| S12 | 多格式 | 5 XLIFF 输出格式支持 | 矩阵覆盖 |

### 2.2 未满足（按严重程度排序）

#### 🔴 Blocker 级（P0：必须解决，否则 agent 无法使用）

| ID | 类别 | 标准 | 现状 | 后果 |
|----|------|------|------|------|
| P0-01 | Agent | 真实 `opp-mcp-server` 可被 agent 调用 | FastMCP 3.4.2 stdio bug | agent 无法调用 OPP |
| P0-02 | Agent | 真实 `ol-mcp` 可被 agent 调用 | 同上 | agent 无法调用 OL |
| P0-03 | Agent | 真实 `orf-mcp-server` 可被 agent 调用 | 同上 | agent 无法调用 ORF |
| P0-04 | 测试 | 真实 MCP 端到端（不是 bridge） | 只测了自写 bridge | 测试通过 ≠ 产品可用 |
| P0-05 | 产品 | 用真实 LLM API 跑一次 | 只用 FAKE_LLM | 不知道真实延迟/成本/错误 |
| P0-06 | 产品 | 用真实文档（>10 个）测试 | 5 个手工文档 | 不知道真实场景行为 |
| P0-07 | 部署 | `pip install` 端到端可成功 | 未测 | 客户能不能装上未知 |

#### 🟡 重要级（P1：显著影响可用性）

| ID | 类别 | 标准 | 现状 |
|----|------|------|------|
| P1-01 | 用户 | README + quickstart + tutorial | 只有 AGENTS.md |
| P1-02 | 用户 | API reference（每个工具的输入输出） | 缺失 |
| P1-03 | 用户 | 错误处理 UX（每个错误场景） | 未测 |
| P1-04 | Agent | tool schema 文档（让 agent 知道工具） | 部分在 MCP schemas |
| P1-05 | 测试 | 真实 LLM 下的 fidelity 评分 | 未测 |
| P1-06 | 测试 | 真实文档下的 fidelity 评分 | 未测 |
| P1-07 | 部署 | Docker 镜像 | 缺失 |
| P1-08 | 部署 | 跨平台测试（Windows/Mac） | 只测 Linux |
| P1-09 | 部署 | 依赖冲突检测（三个模块一起装） | 未测 |
| P1-10 | 部署 | 快速开始脚本（`setup_dev.sh`） | 已有但未验证 |
| P1-11 | API | 工具的 schema 演进策略 | 缺失 |
| P1-12 | API | 向后兼容性测试 | 缺失 |

#### 🟢 生产级（P2：生产环境需要但 MVP 可后置）

| ID | 类别 | 标准 | 现状 |
|----|------|------|------|
| P2-01 | 可观测 | 结构化日志 | 部分有（OPP log file） |
| P2-02 | 可观测 | Metrics（OpenTelemetry 或 Prometheus） | 缺失 |
| P2-03 | 可观测 | Distributed tracing | 缺失 |
| P2-04 | 可观测 | 健康检查 / readiness probe | 缺失 |
| P2-05 | 安全 | 路径遍历审计 | 基本有（PathValidator） |
| P2-06 | 安全 | 注入攻击审计 | 未做 |
| P2-07 | 安全 | 沙箱逃逸审计 | 未做 |
| P2-08 | 安全 | CVE 扫描（依赖漏洞） | 未做 |
| P2-09 | 安全 | License 合规扫描 | 未做 |
| P2-10 | 性能 | 延迟 SLA 文档 | 缺失 |
| P2-11 | 性能 | 吞吐量基准 | 缺失 |
| P2-12 | 性能 | 内存预算 | 缺失 |
| P2-13 | 性能 | 大文件处理（>1GB PDF） | 未测 |
| P2-14 | 稳定性 | 取消/超时支持 | 未测 |
| P2-15 | 稳定性 | 幂等性 | 未测 |
| P2-16 | 稳定性 | 增量处理 / diff | 未测 |
| P2-17 | 稳定性 | 流式输出 | 未测 |
| P2-18 | 稳定性 | 批处理 | OL 有 batch_translate_texts |
| P2-19 | 稳定性 | 状态恢复（崩溃后） | 未测 |
| P2-20 | 运维 | 速率限制 | 未做 |
| P2-21 | 运维 | 密钥管理（API key） | 通过环境变量 |
| P2-22 | 运维 | 审计日志 | 缺失 |
| P2-23 | 运维 | CI/CD 部署流水线 | 缺失 |
| P2-24 | 社区 | Issue templates | 缺失 |
| P2-25 | 社区 | Contributing guide | 缺失 |
| P2-26 | 社区 | Code of conduct | 缺失 |
| P2-27 | 文档 | Architecture decision records | 缺失 |
| P2-28 | 文档 | Changelog | 缺失 |
| P2-29 | 文档 | Migration guide | 缺失 |

#### 🟣 加分项（P3：锦上添花）

| ID | 类别 | 标准 |
|----|------|------|
| P3-01 | Agent | prompt 友好性（错误信息引导 agent 修正） |
| P3-02 | Agent | token 效率（OL 输出冗余度） |
| P3-03 | Agent | 可发现性（skill / tool catalog） |
| P3-04 | 质量 | property-based testing |
| P3-05 | 质量 | mutation testing |
| P3-06 | 质量 | fuzz testing |
| P3-07 | 质量 | test coverage 指标 |
| P3-08 | 部署 | Kubernetes manifests |
| P3-09 | 部署 | Helm chart |
| P3-10 | 部署 | Terraform modules |

---

## 3. Phase 1: Unblock Agent（MCP 真实服务器）

**目标**：让真实的 `opp-mcp-server` / `ol-mcp` / `orf-mcp-server` 能被 agent 调用。

**验收标准**：
- [ ] `npx @modelcontextprotocol/inspector Omni_Pre_Processor/src/opp/mcp/server.py` 能列出 7 个工具
- [ ] 通过 inspector 能成功调用 `extract_document` 拿到 MD
- [ ] OL 和 ORF 同上
- [ ] 移除 `scripts/mcp_bridge.py`（不再需要 workaround）

### 3.1 根因分析

**FastMCP 3.4.2 的 stdio transport bug**：
- 服务器启动后读取 stdin，但从不写响应
- 已在本地环境多次复现
- 根本原因可能是 fastmcp 3.4.2 在异步事件循环中处理 stdio 的方式有缺陷

### 3.2 方案对比

| 方案 | 优点 | 缺点 | 风险 | 评估 |
|------|------|------|------|------|
| **A. 升级 fastmcp 到 ≥3.5** | 最简单 | 3.4.2 是最新版本 | 等待上游修复 | ❌ 不可行 |
| **B. 降级到 fastmcp 2.x** | 2.x 稳定 | 2.x/3.x API 不兼容 | import 错误 | ⚠️ 需要大量适配 |
| **C. 替换为标准 `mcp` 库** | 标准方案 | 需要重写所有 `@tool` 装饰器 | 重写工作量大 | ✅ **推荐** |
| **D. 用 HTTP 传输代替 stdio** | 绕过 stdio bug | agent 通常用 stdio | 不符合 MCP 规范 | ❌ 不推荐 |

### 3.3 推荐方案：标准 `mcp` 库 + StdioServerTransport

#### 3.3.1 OPP 重构（`Omni_Pre_Processor/src/opp/mcp/server.py`）

**当前状态**（FastMCP 3.x 风格）：
```python
from fastmcp import FastMCP
_mcp = FastMCP("OPP MCP Server")

@_mcp.tool()
def extract_document(file_path: str, output_formats: list, ...) -> dict:
    ...

_mcp.add_tool(extract_document)
_mcp.run(transport="stdio")
```

**目标状态**（标准 `mcp` 库风格）：
```python
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

server = Server("OPP MCP Server")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="extract_document",
            description="Extract document content",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "output_formats": {"type": "array", "items": {"type": "string"}},
                    "source_lang": {"type": "string"},
                    "target_lang": {"type": "string"},
                },
                "required": ["file_path"],
            },
        ),
        # ... 其他 6 个工具
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.ContentBlock]:
    if name == "extract_document":
        result = extract_document(**arguments)
        return [types.TextContent(type="text", text=json.dumps(result))]
    # ... 其他工具

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream,
            server.create_initialization_options(),
        )
```

**具体步骤**：
1. 创建 `scripts/fix_mcp/rewrite_opp_mcp.py`（一次性脚本，完成后删除）
2. 该脚本读取 `Omni_Pre_Processor/src/opp/mcp/server.py`
3. 解析所有 `@_mcp.tool()` 装饰的函数
4. 生成新的使用标准 `mcp` 库的版本
5. 人工 review 生成结果
6. 替换原文件
7. 提交到 `Omni_Pre_Processor` 仓库

#### 3.3.2 ORF 重构（`Omni_Re_Formatter/src/orf/mcp/server.py`）

同样的方法应用到 ORF。ORF 有 6 个工具。

#### 3.3.3 OL 验证

OL 已经使用 `mcp.run_stdio_async()`，应该可以工作。需要验证：
- 检查实际响应
- 如不工作，同样重构

### 3.4 验证步骤

1. **单元验证**：
   ```bash
   # 启动 OPP MCP server
   python -m opp.mcp.server &
   SERVER_PID=$!
   
   # 用 stdio 发送 initialize
   echo 'Content-Length: 121
   
   {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}' | python -c "
   import sys, json
   # ... 读取响应
   "
   
   kill $SERVER_PID
   ```

2. **集成验证**：
   ```bash
   # 用 MCP Inspector 测试
   npx @modelcontextprotocol/inspector python -m opp.mcp.server
   ```

3. **端到端验证**：
   - 写一个最小 Python 脚本，用 `mcp` 客户端库连接三个服务器
   - 调用 `extract_document` → 拿到 MD
   - 调用 `translate_md_text` → 拿到翻译
   - 调用 `apply_md` → 拿到输出文件

### 3.5 任务分解

| 任务 | 文件 | 估计时间 |
|------|------|----------|
| 写 OPP 重构脚本 | `scripts/fix_mcp/rewrite_opp_mcp.py` | 2h |
| 人工 review + 调整 | `Omni_Pre_Processor/src/opp/mcp/server.py` | 1h |
| 写 ORF 重构脚本 | `scripts/fix_mcp/rewrite_orf_mcp.py` | 2h |
| 人工 review + 调整 | `Omni_Re_Formatter/src/orf/mcp/server.py` | 1h |
| OL 验证 + 修复 | `Omni_Localizer/src/ol_mcp/server.py` | 1h |
| 单元验证脚本 | `tests/mcp/test_real_servers.py` | 2h |
| MCP Inspector 验证 | 手动 | 30min |
| 端到端验证脚本 | `tests/mcp/test_e2e_agent_flow.py` | 2h |
| 提交 + 推送 | 三个 submodule | 30min |
| **Phase 1 总计** | | **~12h** |

### 3.6 完成后

- 删除 `scripts/mcp_bridge.py`（workaround）
- 删除 `scripts/mcp_matrix_verifier.py` 中的 bridge 引用
- 恢复 `mcp_matrix_verifier.py` 使用真实 MCP 客户端
- 更新 `mcp_matrix_verifier.py` 重新跑全矩阵（应该是 0 FAIL + MCP PASS）

---

## 4. Phase 2: 产品质量

**目标**：用真实 LLM、真实文档、真实错误场景验证产品质量。

**验收标准**：
- [ ] 真实 LLM（OpenAI/Anthropic/Zhipu）跑一次完整流水线
- [ ] 10+ 真实文档（不同类型）通过流水线
- [ ] 每个常见错误场景都有明确、友好的错误信息
- [ ] Fidelity 评分在真实场景下有意义

### 4.1 真实 LLM 集成测试

**当前状态**：所有测试都用 `OMNI_TEST_FAKE_LLM=1`，从未用真实 API。

**所需工作**：
1. **准备 API key**：
   - 至少一个 LLM provider 的 API key（OpenAI、Anthropic、Zhipu）
   - 通过 `OMNI_OPENAI_API_KEY` 等环境变量传递

2. **写真实 LLM 集成测试**（`tests/integration/test_real_llm.py`）：
   ```python
   @pytest.mark.real_llm
   @pytest.mark.skipif(not os.environ.get("OMNI_OPENAI_API_KEY"),
                       reason="No real LLM API key")
   def test_docx_to_docx_via_openai():
       """End-to-end: real DOCX → OpenAI → real DOCX."""
       src = download_real_docx()  # 见 4.2
       with tempfile.TemporaryDirectory() as tmp:
           # OPP extract
           md = opp_extract(src, tmp)
           # OL translate via OpenAI
           translated = ol_translate(md, provider="openai")
           # ORF backfill
           output = orf_apply(translated, target="docx")
           # Verify
           assert output.exists()
           assert output.stat().st_size > 1000
           # Fidelity check
           fidelity = compute_fidelity(src, output, "docx")
           assert fidelity.text_score > 0.5  # 至少 50% 文本保留
   ```

3. **CI 集成**：
   - 默认 skip（需要 API key）
   - 在 nightly build 中运行
   - 报告真实 LLM 下的 fidelity 分数

### 4.2 真实文档测试

**当前状态**：只用 `scripts/corpus_generator.py` 生成的 5 个手工文档。

**所需工作**：
1. **建立真实文档库**（`test_corpus/real/`）：
   - 从公开来源下载 10+ 真实文档
   - 覆盖不同类型：DOCX（学术论文）、PPTX（商业演示）、PDF（技术文档）、XLSX（财务报表）、HTML（网页）
   - 不同语言：英文、中文、日文
   - 不同大小：<1MB, 1-10MB, >10MB
   - 不同复杂度：纯文本、表格、图表、公式

2. **真实文档的合法来源**：
   - 学术论文：arXiv 公开论文
   - 政府文档：data.gov 公开数据
   - Wikipedia 导出：英文/中文维基百科条目
   - 开源项目 README：GitHub 上知名项目的 README
   - 标准文档：W3C 规范、RFC 文档

3. **真实文档测试**（`tests/integration/test_real_corpus.py`）：
   ```python
   REAL_CORPUS = Path("test_corpus/real")
   
   @pytest.mark.parametrize("doc_path", list(REAL_CORPUS.glob("*.docx")))
   def test_real_docx_roundtrip(doc_path):
       """Every real DOCX in the corpus must pass the pipeline."""
       result = run_full_pipeline(doc_path, target="docx")
       assert result.exit_code == 0
       assert result.output_path.exists()
   ```

### 4.3 错误处理 UX

**当前状态**：错误信息没有系统测试过。

**所需工作**：
1. **错误场景矩阵**：

| 场景 | 预期行为 |
|------|----------|
| 文件不存在 | `ERROR: file not found: /path/to/file` + exit code 2 |
| 文件无权限 | `ERROR: permission denied: /path/to/file` + exit code 13 |
| 文件格式不受支持 | `ERROR: unsupported format: .xyz. Supported: docx, pptx, ...` + exit code 3 |
| 损坏的文件 | `ERROR: file appears to be corrupted: <details>` + exit code 4 |
| OPP 内部错误 | `ERROR: extraction failed: <exception type>: <message>` + exit code 5 |
| OL API key 缺失 | `ERROR: API key not set. Set OMNI_OPENAI_API_KEY or use --mock-llm` + exit code 6 |
| OL API 错误（429） | `ERROR: rate limited, retrying in 60s (attempt 1/3)` + 自动重试 |
| OL API 错误（5xx） | `ERROR: LLM service unavailable: <message>` + exit code 7 |
| ORF 输出目录不可写 | `ERROR: cannot write to /path: <reason>` + exit code 8 |
| 磁盘空间不足 | `ERROR: insufficient disk space` + exit code 28 |

2. **错误信息测试**（`tests/test_error_messages.py`）：
   ```python
   def test_missing_file_error():
       result = subprocess.run(
           ["opp", "/nonexistent/file.docx"],
           capture_output=True, text=True,
       )
       assert result.returncode == 2
       assert "file not found" in result.stderr.lower()
       assert "/nonexistent/file.docx" in result.stderr
   ```

3. **错误信息文案标准**：
   - 人类可读（不是堆栈跟踪）
   - 包含可操作信息（哪个文件、什么问题、怎么修）
   - 包含退出码（machine-readable）
   - 支持 `--json` 模式（agent-friendly）

### 4.4 任务分解

| 任务 | 文件 | 估计时间 |
|------|------|----------|
| 准备真实 LLM API key | 环境变量 | 30min |
| 写真实 LLM 集成测试 | `tests/integration/test_real_llm.py` | 3h |
| 下载真实文档 | `test_corpus/real/` | 2h |
| 写真实文档测试 | `tests/integration/test_real_corpus.py` | 2h |
| 错误场景矩阵 | `docs/error-codes.md` | 1h |
| 错误信息测试 | `tests/test_error_messages.py` | 3h |
| 改进现有错误信息 | OPP/OL/ORF CLI | 3h |
| Fidelity 真实场景验证 | `tests/integration/test_real_fidelity.py` | 2h |
| **Phase 2 总计** | | **~16h** |

---

## 5. Phase 3: 部署体验

**目标**：`pip install opp ol orf` 后能立即使用，无需额外配置。

**验收标准**：
- [ ] 在干净环境中（Docker）`pip install` 三个模块成功
- [ ] 安装后 `opp --version`, `ol --version`, `orf --version` 输出正确
- [ ] 安装后 `opp file.docx` 能成功提取
- [ ] 三个模块的依赖不冲突
- [ ] Docker 镜像 `omni-suite:latest` 可用
- [ ] 跨平台测试（至少 Linux + macOS）通过

### 5.1 `pip install` 端到端

**当前状态**：从未在干净环境中测试过 `pip install`。

**所需工作**：
1. **干净环境测试**（`tests/installation/`）：
   ```bash
   # Dockerfile.test
   FROM python:3.13-slim
   RUN pip install opp omni-localizer omni-re-formatter
   RUN opp --version
   RUN ol --version
   RUN orf --version
   RUN echo "Hello" | opp /dev/stdin
   ```

2. **依赖冲突检测**：
   ```bash
   pip install opp omni-localizer omni-re-formatter --dry-run
   pip check  # 检查依赖冲突
   ```

3. **修复发现的问题**：
   - 可能某些依赖需要放宽版本约束
   - 可能某些包需要在 `setup.py` 中标记为 extras_require

### 5.2 用户文档

**当前状态**：只有 `AGENTS.md`（开发者文档），没有用户文档。

**所需工作**：

1. **README.md**（每个模块根目录）：
   ```markdown
   # OPP — Omni Pre-Processor
   
   Extract content from 12 document formats.
   
   ## Quick Start
   
   ```bash
   pip install opp
   opp document.docx --output-dir ./output
   ```
   
   ## Supported Formats
   
   | Input | Output |
   |-------|--------|
   | DOCX  | MD, XLIFF |
   | PPTX  | MD, XLIFF |
   | PDF   | MD |
   | ...   | ... |
   
   ## Examples
   
   ### Extract to Markdown
   ```bash
   opp document.docx
   ```
   
   ### Extract with options
   ```bash
   opp document.docx --source-lang en --target-lang zh --ocr-engine tesseract
   ```
   
   ## MCP Server
   
   ```bash
   opp-mcp-server
   ```
   
   See [MCP.md](docs/MCP.md) for tool reference.
   ```

2. **API reference**（`docs/API.md` 每个模块）：
   - 每个 CLI 命令的所有参数
   - 每个 MCP 工具的输入输出 schema
   - 错误码表

3. **Tutorial**（`docs/TUTORIAL.md`）：
   - "5 分钟快速开始"
   - "翻译一份 PDF 文档"
   - "批量处理 100 个文件"
   - "用 Claude 翻译整个文档库"

4. **Troubleshooting**（`docs/TROUBLESHOOTING.md`）：
   - 常见错误及解决方法
   - 环境依赖问题
   - API key 配置

5. **Architecture**（`docs/ARCHITECTURE.md`）：
   - 模块关系图
   - 数据流图
   - 关键设计决策

### 5.3 Docker 镜像

**当前状态**：没有 Docker 镜像。

**所需工作**：

1. **基础镜像**（`docker/Dockerfile.opp`）：
   ```dockerfile
   FROM python:3.13-slim
   RUN apt-get update && apt-get install -y \
       pandoc \
       tesseract-ocr \
       poppler-utils \
       && rm -rf /var/lib/apt/lists/*
   RUN pip install --no-cache-dir opp
   ENTRYPOINT ["opp"]
   ```

2. **多模块镜像**（`docker/Dockerfile.suite`）：
   ```dockerfile
   FROM python:3.13-slim
   RUN apt-get update && apt-get install -y pandoc tesseract-ocr poppler-utils
   RUN pip install --no-cache-dir \
       opp omni-localizer omni-re-formatter
   ENTRYPOINT ["omni-suite"]
   ```

3. **CI 自动构建**：
   - 三个 submodule 各打一个 Docker 镜像
   - 推送到 GitHub Container Registry

### 5.4 跨平台测试

**当前状态**：只在 Linux 测过。

**所需工作**：

1. **CI matrix**（`.github/workflows/test.yml`）：
   ```yaml
   strategy:
     matrix:
       os: [ubuntu-latest, macos-latest, windows-latest]
       python-version: ["3.13"]
   ```

2. **平台特定修复**：
   - Windows 路径处理
   - macOS 系统依赖
   - Linux 不同发行版

### 5.5 任务分解

| 任务 | 文件 | 估计时间 |
|------|------|----------|
| 干净环境安装测试 | `tests/installation/` | 2h |
| 依赖冲突检测 + 修复 | `setup.py` × 3 | 2h |
| README 文档（3 个模块） | `README.md` × 3 | 3h |
| API reference 文档 | `docs/API.md` × 3 | 3h |
| Tutorial 文档 | `docs/TUTORIAL.md` | 2h |
| Troubleshooting 文档 | `docs/TROUBLESHOOTING.md` | 1h |
| Architecture 文档 | `docs/ARCHITECTURE.md` | 1h |
| Docker 基础镜像（3 个） | `docker/Dockerfile.*` | 3h |
| Docker 套件镜像 | `docker/Dockerfile.suite` | 1h |
| CI 自动构建 | `.github/workflows/docker.yml` | 1h |
| 跨平台 CI | `.github/workflows/test.yml` | 2h |
| **Phase 3 总计** | | **~21h** |

---

## 6. Phase 4: 生产就绪

**目标**：可在生产环境部署，有 SLA、有监控、有安全审计。

**验收标准**：
- [ ] 结构化日志（JSON 格式）
- [ ] Metrics 暴露（Prometheus 或 OpenTelemetry）
- [ ] 延迟 SLA 文档化（如：DOCX <5s, PDF <30s）
- [ ] 安全审计报告
- [ ] CVE 扫描通过
- [ ] 错误码完整文档化

### 6.1 可观测性

**当前状态**：OPP 有 log file，但没有结构化日志；OL/ORF 无可观测性。

**所需工作**：

1. **结构化日志**（统一使用 `structlog`）：
   ```python
   import structlog
   log = structlog.get_logger()
   log.info("extraction_complete",
            file=file_path,
            duration_ms=duration,
            pages=page_count,
            words=word_count)
   ```

2. **Metrics**（OpenTelemetry）：
   ```python
   from opentelemetry import metrics
   meter = metrics.get_meter("opp")
   extraction_counter = meter.create_counter("opp_extractions_total")
   extraction_duration = meter.create_histogram("opp_extraction_duration_ms")
   ```

3. **Tracing**：
   - 每个 CLI 调用是一个 trace
   - OPP/OL/ORF 是 span
   - 支持 OTLP 导出

### 6.2 安全审计

**所需工作**：

1. **路径遍历**：
   - 审计 `PathValidator` 是否覆盖所有入口
   - 添加 fuzz 测试

2. **注入攻击**：
   - OPP: 文件名注入
   - OL: prompt 注入（LLM-specific）
   - ORF: 输出文件名注入

3. **沙箱逃逸**：
   - OPP: 临时文件清理
   - ORF: 子进程隔离

4. **CVE 扫描**：
   ```yaml
   # .github/workflows/security.yml
   - name: Run Trivy vulnerability scanner
     uses: aquasecurity/trivy-action@master
   ```

5. **License 合规**：
   ```bash
   pip-licenses --format=markdown --output-file=THIRD_PARTY_LICENSES.md
   ```

### 6.3 性能基准

**所需工作**：

1. **基准测试**（`tests/benchmark/`）：
   ```python
   def test_bench_docx_extraction(benchmark):
       result = benchmark(opp_extract, "test_corpus/complex.docx")
       assert result.stats.stats.median < 5000  # < 5s
   ```

2. **SLA 文档**（`docs/SLA.md`）：
   - DOCX 提取：<5s (P95)
   - PDF 提取：<30s (P95)
   - OL 翻译：<10s (P95) per 1000 tokens
   - ORF backfill：<10s (P95)

### 6.4 API 稳定性

**所需工作**：

1. **版本策略**（`docs/API_STABILITY.md`）：
   - SemVer 严格遵守
   - 公开 API 在 minor 版本内不变
   - 弃用流程：先标记 deprecated，再过两个 minor 版本才删除

2. **Contract 测试**：
   ```python
   def test_cli_help_contract():
       """CLI --help output must not change without major version bump."""
       result = subprocess.run(["opp", "--help"], capture_output=True, text=True)
       assert result.stdout == load_fixture("opp_help.txt")
   ```

### 6.5 任务分解

| 任务 | 文件 | 估计时间 |
|------|------|----------|
| 结构化日志（3 模块） | `*` × 3 | 6h |
| Metrics + tracing（3 模块） | `*` × 3 | 6h |
| 安全审计 | `docs/SECURITY_AUDIT.md` | 4h |
| CVE 扫描 | `.github/workflows/security.yml` | 1h |
| License 合规 | `THIRD_PARTY_LICENSES.md` | 1h |
| 性能基准 | `tests/benchmark/` | 3h |
| SLA 文档 | `docs/SLA.md` | 1h |
| API 稳定性策略 | `docs/API_STABILITY.md` | 1h |
| Contract 测试 | `tests/contract/` | 3h |
| **Phase 4 总计** | | **~26h** |

---

## 7. 跨切关注点

### 7.1 测试策略

每个 phase 完成后必须满足：

| 测试类型 | 工具 | 目标覆盖率 |
|---------|------|-----------|
| 单元测试 | pytest | >80% |
| 集成测试 | pytest | 所有 CLI/MCP 入口 |
| 端到端测试 | pytest | 每个 phase 的验收场景 |
| 性能测试 | pytest-benchmark | SLA 文档化 |
| 安全测试 | bandit, safety | 无高危漏洞 |
| 模糊测试 | hypothesis | 边界情况 |

### 7.2 持续集成

每个 PR 必须通过：

- [ ] 单元测试
- [ ] 集成测试
- [ ] Lint (ruff)
- [ ] Type check (mypy)
- [ ] Security scan
- [ ] Coverage 报告（>80%）

### 7.3 发布流程

1. 创建 release branch
2. 更新 CHANGELOG.md
3. 更新版本号（三个模块同步）
4. 运行完整测试矩阵
5. Tag 三个仓库
6. 构建 Docker 镜像
7. 发布到 PyPI
8. 发布到 GitHub Container Registry
9. 更新文档站点

---

## 8. 验收标准总览

### 8.1 Phase 1 完成标准

- [ ] `opp-mcp-server` 可被 MCP Inspector 列出 7 个工具
- [ ] `ol-mcp` 可被 MCP Inspector 列出 8 个工具
- [ ] `orf-mcp-server` 可被 MCP Inspector 列出 6 个工具
- [ ] 端到端 agent flow 脚本通过
- [ ] `scripts/mcp_bridge.py` 已删除
- [ ] `mcp_matrix_verifier.py` 改用真实 MCP 客户端并通过

### 8.2 Phase 2 完成标准

- [ ] 真实 LLM 集成测试通过（>80%）
- [ ] 真实文档测试通过（>90%）
- [ ] 错误信息测试覆盖所有错误码
- [ ] Fidelity 评分在真实场景下 >0.5

### 8.3 Phase 3 完成标准

- [ ] 干净环境 `pip install` 成功
- [ ] README/API/Tutorial/Troubleshooting 文档完成
- [ ] Docker 镜像可用
- [ ] 跨平台 CI 通过
- [ ] 用户能 "5 分钟内" 完成第一个翻译任务

### 8.4 Phase 4 完成标准

- [ ] 结构化日志（JSON 格式）
- [ ] Metrics 暴露
- [ ] 安全审计无高危
- [ ] 性能 SLA 文档化并满足
- [ ] API 稳定性策略发布

### 8.5 总体"Production Ready"标准

**所有以下条件必须同时满足**：

1. ✅ 测试矩阵全绿（已满足）
2. ⏳ Phase 1-4 全部完成
3. ⏳ 客户/agent 可开箱即用
4. ⏳ 所有 P0/P1 标准满足
5. ⏳ 文档完整
6. ⏳ 部署验证通过

---

## 9. 风险登记

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| FastMCP 修复工作量大 | 中 | 高 | 标准 mcp 库重写，预计 4-5h |
| 真实 LLM API 成本超预算 | 中 | 中 | 使用小模型（gpt-4o-mini），限制 token |
| 真实文档版权问题 | 低 | 中 | 只用 CC0/public domain 文档 |
| 跨平台兼容性 | 中 | 中 | CI matrix 测试 + 平台特定修复 |
| 依赖冲突无法解决 | 低 | 高 | 考虑用 extras_require 分组 |
| 真实 MCP 客户端库也有 bug | 低 | 高 | 已有 bridge 兜底 |

---

## 10. 时间线

| Phase | 内容 | 估计时间 | 累计 |
|-------|------|----------|------|
| Phase 1 | MCP 真实服务器 | 12h | 12h |
| Phase 2 | 产品质量 | 16h | 28h |
| Phase 3 | 部署体验 | 21h | 49h |
| Phase 4 | 生产就绪 | 26h | 75h |

**总计约 75 工时**（1-2 周全职）

---

## 11. 立即下一步

**建议从 Phase 1 开始**，因为：
1. 它是 Blocker（agent 实际无法使用）
2. 它是其他 phase 的前置（Phase 2 的 agent 集成测试需要 MCP 工作）
3. 它的工作量可控（12h）

**具体第一步**：
1. 创建 `scripts/fix_mcp/` 目录
2. 写 `rewrite_opp_mcp.py` 转换脚本
3. 人工 review 生成的 OPP MCP server
4. 在本地用 MCP Inspector 验证
5. 通过后提交到 `Omni_Pre_Processor` 仓库

---

## 12. 附录

### 12.1 三个模块的当前状态

#### OPP (`Omni_Pre_Processor` @ `3684e87` + patches)
- **版本**：0.6.1
- **支持的输入**：16 种格式
- **CLI**：`opp`
- **MCP**：`opp-mcp-server`（7 个工具）— **不可用**（FastMCP bug）
- **已知 bug**：EPUB 提取非确定性（已修）

#### OL (`Omni_Localizer` @ `4685a47` + patches)
- **版本**：0.4.4
- **支持的输入**：MD, XLIFF
- **CLI**：`ol translate-md`, `ol translate-xliff`
- **MCP**：`ol-mcp`（8 个工具）— **不可用**（FastMCP bug）
- **依赖**：LLM API（OpenAI, Anthropic, Zhipu）

#### ORF (`Omni_Re_Formatter` @ `c7d6853` + patches)
- **版本**：0.4.3
- **支持的输入**：MD, XLIFF
- **支持的输出**：16 种格式
- **CLI**：`orf apply-md`, `orf apply-xliff`
- **MCP**：`orf-mcp-server`（6 个工具）— **不可用**（FastMCP bug）

### 12.2 现有测试基础设施

| 文件 | 行数 | 用途 |
|------|------|------|
| `scripts/format_matrix_verifier.py` | 678 | Tier 7/8 矩阵验证器 |
| `scripts/mcp_matrix_verifier.py` | 452 | MCP 矩阵验证器（需更新） |
| `scripts/mcp_bridge.py` | 230 | MCP workaround（Phase 1 后删除） |
| `scripts/equivalence_checker.py` | 241 | 确定性检查 |
| `scripts/fidelity_checker.py` | 240 | 真实度评分 |
| `scripts/corpus_generator.py` | 250 | 手工文档生成器 |
| `scripts/omo_loop.py` | 1299 | 主控循环 |
| `tests/test_format_matrix_verifier.py` | 239 | 矩阵验证器测试 |
| `tests/test_corpus_fidelity_equivalence.py` | 300+ | 新组件测试 |
| `tests/test_convergence_watch_gates.py` | ? | Tier 6/7/8 gate 测试 |

### 12.3 关键发现

1. **MCP 是最大 blocker**：三个真实 MCP 服务器都不能用
2. **真实 LLM 未测**：所有测试用 FAKE_LLM
3. **真实文档未测**：只有 5 个手工文档
4. **bridge 是 workaround**：不是真正的产品修复
5. **测试矩阵本身是好的**：能发现真实 bug（如 EPUB 非确定性）

### 12.4 关键决策记录

| 决策 | 理由 |
|------|------|
| Phase 1 用标准 mcp 库替换 FastMCP | FastMCP 3.4.2 是最新且有 bug，升级/降级都不可行 |
| Phase 1 后删除 mcp_bridge.py | bridge 是测试 workaround，不是产品 |
| Phase 2 用小模型（gpt-4o-mini）测试 | 控制 API 成本 |
| Phase 2 真实文档用 CC0/public domain | 避免版权问题 |
| Phase 3 文档按用户视角写 | 当前文档是开发者视角，用户看不懂 |
| Phase 4 选 OpenTelemetry | 行业标准，避免 vendor lock-in |

---

**文档版本**：1.0  
**创建日期**：2026-06-22  
**最后更新**：2026-06-22  
**状态**：待审阅 + 执行
