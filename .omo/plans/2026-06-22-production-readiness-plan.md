# Omni Suite Production Readiness Plan v2 (2026-06-22)

> **Revision history**:
> - v1 (2026-06-22): Initial plan
> - v2 (2026-06-22): Major revision after Metis + Momus review
>   - Fixed fact errors (OPP code style, OL MCP library source)
>   - Made all acceptance criteria quantifiable
>   - Reordered phases: Phase 3 (deploy) before Phase 2 (quality)
>   - Added Phase 0 (pre-flight: version strategy + cross-module compatibility)
>   - Added Section 13: Translation Quality Standards
>   - Added Section 14: Rollback & Migration Plan
>   - Added Section 15: Version Strategy & Cross-Module Coordination
>   - Adjusted time estimates: 75h → 110h
>   - Added legal/IP considerations for real documents

## 1. Background & Context

### 1.1 项目目标（用户明确诉求）

三个模块 **OPP**、**OL**、**ORF** 必须满足以下要求，**全部满足，不可取舍**：

1. **独立可用**：每个模块可单独 `pip install`，有自己的 CLI/MCP，可独立部署
2. **组合可用**：三个模块能串联成完整 omni-suite 流水线
3. **开箱即用**：客户和 AI agent 部署后无需额外配置即可使用
4. **产品质量过硬**：翻译结果在真实场景中可用（不是 50% 文本保留）
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
| **翻译质量** | ❌ **未测量**（fidelity >0.5 对生产是不可接受的低） |
| **版本策略** | ❌ **缺失**（3 模块独立版本号，无兼容性矩阵） |
| **回滚计划** | ❌ **缺失** |
| **可观测性** | ❌ **缺失** |
| **安全审计** | ❌ **未做** |
| **性能基准** | ❌ **缺失** |
| **跨平台** | ❌ **未测** |

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
| `aa16579` | e2e-test-suite | docs: production-readiness plan v1 |

---

## 2. 全维度标准矩阵

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
| P0-08 | 版本 | 三个模块版本兼容性矩阵 | 缺失 | 升级一个可能破坏其他 |
| P0-09 | 回滚 | Phase 1 MCP 重写失败时回退方案 | 缺失 | 没有兜底 |

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
| P1-08 | 部署 | 跨平台测试（Linux + macOS + Windows） | 只测 Linux |
| P1-09 | 部署 | 依赖冲突检测（三个模块一起装） | 未测 |
| P1-10 | 部署 | 快速开始脚本（`setup_dev.sh`） | 已有但未验证 |
| P1-11 | API | 工具的 schema 演进策略 | 缺失 |
| P1-12 | API | 向后兼容性测试 | 缺失 |
| P1-13 | 翻译 | 翻译一致性（相同术语 → 相同翻译） | 未测 |
| P1-14 | 翻译 | 格式保留（DOCX 布局不被破坏） | 未测 |
| P1-15 | 翻译 | 人类审阅工作流 | 未设计 |

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
| P2-13 | 性能 | 大文件处理（>100MB） | 未测 |
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

## 3. Phase 0: 预检（版本策略 + 跨模块兼容性）

**目标**：在开始 MCP 重写之前，先解决三个模块的版本协调问题。否则 Phase 1-4 的所有工作都在不确定的版本基础上进行。

**工作量**：8h

### 3.1 任务分解

| 任务 | 文件 | 验收标准 | 时间 |
|------|------|----------|------|
| 固定三个 submodule 的 SHA 作为工作基线 | `Omni_Suite` + 3 submodules | 三个 submodule 指向已知可工作的 commit，CI 在此基线绿 | 1h |
| 创建 `VERSION_COMPATIBILITY.md` | `Omni_Suite/VERSION_COMPATIBILITY.md` | 列出当前兼容矩阵（如 `opp 0.6.1 ↔ ol 0.4.4 ↔ orf 0.4.3`） | 2h |
| 写跨模块版本兼容性测试 | `tests/integration/test_version_compat.py` | 至少 3 组版本组合（最新+1、最旧+1、跨 major）能跑通完整流水线 | 3h |
| 创建 `bumpversion` 脚本 | `scripts/bumpversion.py` | 一个命令同时 bump 三个模块的版本号 | 2h |

### 3.2 Phase 0 完成标准

- [ ] 三个 submodule 固定到已知绿基线
- [ ] `VERSION_COMPATIBILITY.md` 发布
- [ ] `tests/integration/test_version_compat.py` 在 CI 中运行
- [ ] `bumpversion.py` 可用

---

## 4. Phase 1: Unblock Agent（修复真实 MCP 服务器）

**目标**：让真实的 `opp-mcp-server` / `ol-mcp` / `orf-mcp-server` 能被 agent 调用。

**工作量**：20h（从原 12h 修正，包含被低估的测试重写和安全层移植）

**重要修正**（来自 Momus 审查）：
- OPP 实际使用 `_mcp.add_tool(fn)` 风格（第 676-682 行），不是装饰器风格
- ORF 使用 `@server.tool()` 装饰器在 `_register_tools()` 内部
- OL 使用 `mcp.server.fastmcp.FastMCP`（**标准 mcp 库**），不是独立的 `fastmcp` 包——可能需要不同的修复策略

### 4.1 根因分析（修正版）

| 模块 | 使用的库 | 风格 | 可能根因 | 修复策略 |
|------|---------|------|---------|----------|
| OPP | `fastmcp 3.4.2`（独立包） | `_mcp.add_tool(fn)` | FastMCP 3.4.2 stdio bug | 重写为标准 mcp 库 |
| OL | `mcp.server.fastmcp`（标准库 `mcp==1.27.2`） | 装饰器在模块级 | 标准库 FastMCP 也有类似 bug | 同样重写 |
| ORF | `fastmcp 3.4.2`（独立包） | `@server.tool()` 内部 | FastMCP 3.4.2 stdio bug | 重写为标准 mcp 库 |

**关键验证**：在 Phase 1 开始前，先用一个小脚本测试标准 `mcp` 库的 `stdio_server()` 是否真的工作。如果不工作，整个 Phase 1 的策略需要改变（需要用 raw stdio JSON-RPC 或修 fastmcp）。

### 4.2 方案（推荐）：标准 mcp 库 + 手动重写（不用转换脚本）

转换脚本的复杂度超过其价值。手动重写每个工具到标准 `mcp` 库 API：

#### 4.2.1 OPP 重写（`Omni_Pre_Processor/src/opp/mcp/server.py`，684 行）

**当前**（使用 FastMCP）：
```python
from fastmcp import FastMCP
_mcp = FastMCP("OPP MCP Server")
# ... 函数定义 ...
_mcp.add_tool(extract_document)
_mcp.add_tool(batch_extract)
# ... 7 个工具
_mcp.run(transport="stdio")
```

**目标**（使用标准 mcp 库）：
```python
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

server = Server("OPP MCP Server")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(name="extract_document", description="...",
                   inputSchema={...}),
        # ... 7 个工具的 schema
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.ContentBlock]:
    if name == "extract_document":
        result = extract_document(**arguments)
        return [types.TextContent(type="text", text=json.dumps(result))]
    # ... 7 个工具的分发

async def main():
    async with stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

**具体步骤**：
1. 先用最小脚本测试标准 `mcp` 库 `stdio_server()` 在本环境是否工作（1h）
2. 如果工作，开始重写：
   - 保留所有业务逻辑函数（`extract_document` 等）不变
   - 替换 `_mcp` 相关代码为标准 `mcp` 库的 `Server`
   - 手动编写 `list_tools()` 和 `call_tool()` 分发
   - 移植 `PathValidator`、`check_auth`、`check_rate_limit`、`mcp_error_boundary` 到新架构
3. 删除 `Omni_Pre_Processor/pyproject.toml` 中对 `fastmcp` 的依赖，添加对 `mcp>=1.0.0` 的依赖

#### 4.2.2 ORF 重写（`Omni_Re_Formatter/src/orf/mcp/server.py`，845 行）

同样的方法应用到 ORF。ORF 有 6 个工具，通过 `_run_cli_command()` 委派给 CLI 子进程。

注意：ORF 的 `pyproject.toml` 中 `mcp = ["fastmcp>=0.1.0"]` 缺少 `mcp` 库本身。需要在重写时添加。

#### 4.2.3 OL 重写（`Omni_Localizer/src/ol_mcp/`）

OL 使用的是 `mcp.server.fastmcp`（标准库），但有相同的 stdio 问题（如果标准库也有）。重写方法同上，但起点不同。

### 4.3 验证步骤

1. **最小 stdio 验证脚本**（`tests/mcp/test_minimal_stdio.py`）：
   ```python
   # 测试标准 mcp 库 stdio_server() 是否在本环境工作
   async def test_standard_mcp_stdio():
       from mcp.server import Server
       from mcp.server.stdio import stdio_server
       server = Server("test")
       @server.list_tools()
       async def lst():
           return [types.Tool(name="ping", description="p", inputSchema={"type": "object"})]
       @server.call_tool()
       async def call(name, args):
           return [types.TextContent(type="text", text="pong")]
       async with stdio_server() as (r, w):
           await server.run(r, w, server.create_initialization_options())
   ```

2. **MCP Inspector 验证**（手动）：
   ```bash
   npx @modelcontextprotocol/inspector python -m opp.mcp.server
   npx @modelcontextprotocol/inspector python -m ol_mcp
   npx @modelcontextprotocol/inspector python -m orf.mcp.server
   ```

3. **端到端 agent flow 验证**（`tests/mcp/test_e2e_agent_flow.py`）：
   ```python
   # 完整 agent flow：调用 extract_document → translate_md_text → apply_md
   async def test_full_agent_flow():
       # 用标准 mcp 客户端连接三个服务器
       # 验证完整 pipeline 工作
   ```

### 4.4 任务分解（修正版）

| 任务 | 文件 | 验收标准 | 时间 |
|------|------|----------|------|
| 标准 mcp 库 stdio 验证 | `tests/mcp/test_minimal_stdio.py` | 简单 ping 工作 | 1h |
| 如果失败：实施 raw stdio fallback | — | 备选方案 | 4h |
| OPP 重写 | `Omni_Pre_Processor/src/opp/mcp/server.py` | MCP Inspector 列出 7 个工具 | 6h |
| OPP 测试更新 | `Omni_Pre_Processor/tests/test_e2e_opp_mcp.py` | 测试用标准客户端 | 2h |
| ORF 重写 | `Omni_Re_Formatter/src/orf/mcp/server.py` | MCP Inspector 列出 6 个工具 | 6h |
| ORF 测试更新 | `Omni_Re_Formatter/tests/test_orf_mcp_*.py` | 测试用标准客户端 | 2h |
| OL 验证/重写 | `Omni_Localizer/src/ol_mcp/` | MCP Inspector 列出 8 个工具 | 3h |
| 端到端 agent flow 验证 | `tests/mcp/test_e2e_agent_flow.py` | 三服务器串联工作 | 2h |
| 提交 + 推送 | 三个 submodule | CI 绿 | 30min |
| **Phase 1 总计** | | | **~20h** |

### 4.5 Phase 1 完成标准

- [ ] `npx @modelcontextprotocol/inspector python -m opp.mcp.server` 列出 7 个工具
- [ ] `npx @modelcontextprotocol/inspector python -m ol_mcp` 列出 8 个工具
- [ ] `npx @modelcontextprotocol/inspector python -m orf.mcp.server` 列出 6 个工具
- [ ] `tests/mcp/test_e2e_agent_flow.py` 通过
- [ ] `scripts/mcp_bridge.py` 已删除（Phase 1 完成后）
- [ ] `mcp_matrix_verifier.py` 改用真实 MCP 客户端并通过全矩阵（0 FAIL）

---

## 5. Phase 2: 部署体验（pip install + Docker + 跨平台）

**目标**：`pip install opp ol orf` 后能立即使用。Docker 镜像可用。跨平台 CI 通过。

**工作量**：25h

**重要决策**（来自 Metis 审查）：Phase 2 应在 Phase 3（产品质量）之前，因为如果部署不通，Phase 3 的测试也没法验证"产品可用性"。

### 5.1 pip install 端到端验证

**当前状态**：从未在干净环境中测试过 `pip install`。

**所需工作**：

1. **干净环境 Docker 镜像**（`docker/Dockerfile.test`）：
   ```dockerfile
   FROM python:3.13-slim
   RUN apt-get update && apt-get install -y \
       pandoc tesseract-ocr poppler-utils && rm -rf /var/lib/apt/lists/*
   RUN pip install --no-cache-dir opp omni-localizer omni-re-formatter
   RUN opp --version && ol --version && orf --version
   RUN opp /usr/share/doc/python3/copyright --output-dir /tmp/test
   ```

2. **依赖冲突检测**：
   ```bash
   pip install opp omni-localizer omni-re-formatter --dry-run
   pip check
   ```

3. **修复发现的问题**：
   - ORF 的 `pyproject.toml` 缺少 `mcp` 库依赖（只有 `fastmcp`）
   - OL 的 `pyproject.toml` 有 `mcp>=1.0.0` 但也需要检查版本约束
   - 可能需要放宽某些依赖的版本约束

### 5.2 用户文档

**当前状态**：只有 `AGENTS.md`（开发者文档），没有用户文档。

**所需工作**：

1. **README.md**（每个模块根目录），每个至少包含：
   - 一句话描述 + Quick Start
   - 支持的输入/输出格式表
   - 至少 3 个示例
   - MCP server 启动方式
   - 链接到详细文档

2. **API reference**（`docs/API.md` 每个模块）：
   - 每个 CLI 命令的所有参数
   - 每个 MCP 工具的输入输出 schema
   - 错误码表
   - 退出码表

3. **Tutorial**（`docs/TUTORIAL.md`），至少包含：
   - "5 分钟快速开始"
   - "翻译一份 PDF 文档"
   - "批量处理 100 个文件"
   - "用 Claude 翻译整个文档库"

4. **Troubleshooting**（`docs/TROUBLESHOOTING.md`）：
   - 常见错误及解决方法
   - 环境依赖问题
   - API key 配置
   - 性能问题

5. **Architecture**（`docs/ARCHITECTURE.md`）：
   - 模块关系图
   - 数据流图
   - 关键设计决策（ADR 风格）

### 5.3 Docker 镜像

1. **基础镜像**（`docker/Dockerfile.opp` 等 3 个）：
   - 基于 `python:3.13-slim`
   - 安装系统依赖（pandoc、tesseract、poppler）
   - `pip install <module>`
   - ENTRYPOINT 设置

2. **多模块镜像**（`docker/Dockerfile.suite`）：
   - 安装所有三个模块
   - ENTRYPOINT 是 `omni-suite`

3. **CI 自动构建**（`.github/workflows/docker.yml`）：
   - 三个 submodule 各打一个镜像
   - 推送到 GitHub Container Registry
   - 标签策略：`latest`、`<version>`、`<sha>`

### 5.4 跨平台测试

**CI matrix**（`.github/workflows/test.yml`）：
```yaml
strategy:
  matrix:
    os: [ubuntu-latest, macos-latest, windows-latest]
    python-version: ["3.13"]
```

**平台特定修复预算**：
- Windows 路径处理：2h
- macOS 权限问题：1h
- Linux 多发行版测试：1h

### 5.5 任务分解

| 任务 | 文件 | 验收标准 | 时间 |
|------|------|----------|------|
| 干净环境 Docker 测试 | `docker/Dockerfile.test` | 3 模块 `--version` 通过 | 2h |
| 依赖冲突检测 + 修复 | `setup.py` × 3 | `pip check` 零冲突 | 2h |
| README 文档（3 个模块） | `README.md` × 3 | 每个 ≥50 行，包含 Quick Start | 4h |
| API reference 文档 | `docs/API.md` × 3 | 每个 CLI/MCP 工具都有 schema | 4h |
| Tutorial 文档 | `docs/TUTORIAL.md` | 4 个教程场景 | 2h |
| Troubleshooting 文档 | `docs/TROUBLESHOOTING.md` | 10+ 常见问题 | 1h |
| Architecture 文档 | `docs/ARCHITECTURE.md` | 模块图 + 数据流 | 1h |
| Docker 基础镜像（3 个） | `docker/Dockerfile.*` | 镜像构建成功 | 3h |
| Docker 套件镜像 | `docker/Dockerfile.suite` | 三个模块共存 | 1h |
| CI Docker 构建 | `.github/workflows/docker.yml` | 自动构建+推送 | 1h |
| 跨平台 CI | `.github/workflows/test.yml` | 3 OS × 1 Python | 2h |
| 平台特定修复 | 3 个 submodule | CI 在所有平台绿 | 2h |
| **Phase 2 总计** | | | **~25h** |

### 5.6 Phase 2 完成标准

- [ ] `docker/Dockerfile.test` 在干净环境能 build 且三个模块 `--version` 通过
- [ ] `pip install opp omni-localizer omni-re-formatter` 在干净环境零冲突
- [ ] 每个模块有 README + API reference + tutorial + troubleshooting + architecture
- [ ] Docker 镜像构建成功并推送到 GHCR
- [ ] 跨平台 CI（Linux + macOS + Windows）绿

---

## 6. Phase 3: 产品质量（真实 LLM + 真实文档 + 翻译质量）

**目标**：用真实 LLM、真实文档、真实错误场景验证产品质量。**翻译质量是核心**。

**工作量**：30h（从原 16h 修正，包含翻译质量测试、跨模块集成测试）

**重要修正**（来自 Metis 审查）：
- "Fidelity > 0.5" 太低，对生产是不可接受的
- 需要翻译一致性、格式保留、人类审阅工作流
- 真实文档来源需要法律考虑（CC0 vs CC-BY-SA vs 商业）

### 6.1 翻译质量标准（新章节）

对于文档本地化工具，"产品质量"的核心是**翻译质量**，不是测试覆盖率。

| 指标 | 目标 | 测试方法 |
|------|------|----------|
| 翻译一致性 | 同一术语在不同文档中翻译相同 | 跨 10 个文档的术语表，验证 95%+ 一致性 |
| 格式保留 | DOCX 布局/样式/表格不被破坏 | 翻译后用 python-docx 解析，断言结构完整 |
| 术语准确性 | 特定术语翻译正确 | 建立测试术语表（医学、法律、IT），人工标注 ground truth |
| 文本保留率 | 翻译后文本不丢失 | Fidelity 文本分数 > 0.9（**不是 0.5**） |
| 表格保留率 | 表格行列数不变 | Fidelity 表格分数 > 0.95 |
| 图片保留率 | 图片位置不变 | Fidelity 图片分数 > 0.8 |
| 语言对覆盖 | 至少测试 5 个语言对 | en↔zh, en↔ja, en↔de, en↔fr, en↔ko |

**关键阈值**：
- Fidelity text_score > 0.9（不是 0.5）
- 格式保留率 > 95%
- 翻译一致性 > 95%
- 错误率 < 5%

### 6.2 真实 LLM 集成测试

**当前状态**：所有测试都用 `OMNI_TEST_FAKE_LLM=1`，从未用真实 API。

**所需工作**：

1. **API key 管理**：
   - 至少一个 LLM provider（推荐 gpt-4o-mini 用于成本控制）
   - 通过 `OMNI_OPENAI_API_KEY` 等环境变量
   - CI 中用 secrets 管理

2. **真实 LLM 集成测试**（`tests/integration/test_real_llm.py`）：
   ```python
   @pytest.mark.real_llm
   @pytest.mark.skipif(not os.environ.get("OMNI_OPENAI_API_KEY"),
                       reason="No real LLM API key")
   def test_docx_to_docx_via_openai():
       """End-to-end: real DOCX → OpenAI → real DOCX."""
       src = download_real_docx()
       with tempfile.TemporaryDirectory() as tmp:
           md = opp_extract(src, tmp)
           translated = ol_translate(md, provider="openai")
           output = orf_apply(translated, target="docx")
           # Fidelity 检查
           fidelity = compute_fidelity(src, output, "docx")
           assert fidelity.text_score > 0.9, f"Text fidelity {fidelity.text_score} < 0.9"
           assert fidelity.table_score > 0.95
   ```

3. **成本控制**：
   - 每个测试用例限制 max_tokens
   - 使用 gpt-4o-mini 而非 gpt-4
   - 测试用小文档（<10 页）
   - CI 中 nightly build 运行，单次运行成本 < $5

4. **错误处理**：
   - API key 缺失 → 友好错误
   - 速率限制（429）→ 自动重试
   - 5xx 错误 → 明确错误信息
   - 超时 → 明确超时信息

### 6.3 真实文档测试

**当前状态**：只用 5 个手工文档。

**所需工作**：

1. **真实文档库**（`test_corpus/real/`）：
   - 20+ 真实文档
   - 覆盖：DOCX, PPTX, PDF, XLSX, HTML
   - 覆盖：英文、中文、日文、德文、法文、韩文
   - 覆盖：< 1MB, 1-10MB, 10-50MB
   - 覆盖：纯文本、表格、图片、公式、脚注、交叉引用

2. **法律考虑**：
   - **只能用 CC0 / Public Domain 文档**（不是 CC-BY-SA）
   - 来源：
     - Project Gutenberg（public domain 书籍）
     - 美国政府作品（gutenberg.org 上的政府文档）
     - 维基百科 CC0 内容（部分条目）
     - 自己生成的合成真实风格文档
   - **不能用**：arXiv 论文、GitHub README、商业文档
   - 每个文档在 `test_corpus/real/SOURCES.md` 记录来源和许可证

3. **真实文档测试**（`tests/integration/test_real_corpus.py`）：
   ```python
   @pytest.mark.parametrize("doc_path", list(REAL_CORPUS.glob("*.docx")))
   def test_real_docx_roundtrip(doc_path):
       """Every real DOCX in the corpus must pass the pipeline."""
       result = run_full_pipeline(doc_path, target="docx")
       assert result.exit_code == 0
       assert result.output_path.exists()
       # Fidelity 检查
       fidelity = compute_fidelity(doc_path, result.output_path, "docx")
       assert fidelity.text_score > 0.8  # 真实文档阈值略低
   ```

### 6.4 错误处理 UX

**当前状态**：错误信息没有系统测试过。

**错误场景矩阵**：

| 场景 | 预期输出 | 退出码 |
|------|----------|--------|
| 文件不存在 | `ERROR: file not found: /path/to/file (errno=2)` | 2 |
| 文件无权限 | `ERROR: permission denied: /path/to/file (errno=13)` | 13 |
| 文件格式不受支持 | `ERROR: unsupported format: .xyz. Supported: docx, pptx, ...` | 3 |
| 损坏的文件 | `ERROR: file corrupted: <details>` | 4 |
| OPP 内部错误 | `ERROR[opp]: extraction failed: <exception>` | 5 |
| OL API key 缺失 | `ERROR[ol]: API key not set. Set OMNI_OPENAI_API_KEY or use --mock-llm` | 6 |
| OL 速率限制 | `WARN[ol]: rate limited, retrying in 60s (attempt 1/3)` | 0（重试成功） |
| OL 5xx 错误 | `ERROR[ol]: LLM service unavailable: <message>` | 7 |
| ORF 输出不可写 | `ERROR[orf]: cannot write to /path: <reason>` | 8 |
| 磁盘空间不足 | `ERROR: insufficient disk space (need 10MB, have 1MB)` | 28 |
| 翻译中途 OPP 成功但 OL 失败 | 清理 OPP 输出，返回明确错误 | 9 |

**测试**（`tests/test_error_messages.py`）：覆盖每个错误场景，断言退出码 + stderr 内容。

### 6.5 翻译一致性测试

**当前状态**：未测。

**所需工作**（`tests/integration/test_translation_consistency.py`）：
```python
# 建立术语表（人工标注的 ground truth）
TERMINOLOGY = {
    "machine learning": "机器学习",
    "neural network": "神经网络",
    # ... 100+ 术语
}

def test_terminology_consistency():
    """Same English term should produce same Chinese translation across documents."""
    docs = [test_doc_a, test_doc_b, test_doc_c]  # 包含相同术语
    translations = [run_pipeline(d, "en", "zh") for d in docs]
    for term_en, term_zh in TERMINOLOGY.items():
        # 验证每个翻译中都包含 term_zh
        for t in translations:
            if term_en in t.source:
                assert term_zh in t.target, f"术语 {term_en} 在文档中未翻译为 {term_zh}"
```

### 6.6 任务分解

| 任务 | 文件 | 验收标准 | 时间 |
|------|------|----------|------|
| 翻译质量标准文档 | `docs/TRANSLATION_QUALITY.md` | 7 个指标的定义和阈值 | 1h |
| 真实 LLM 集成测试 | `tests/integration/test_real_llm.py` | 至少 5 个测试通过 | 6h |
| 真实文档库（CC0 来源） | `test_corpus/real/` + `SOURCES.md` | 20+ 文档，来源可追溯 | 4h |
| 真实文档测试 | `tests/integration/test_real_corpus.py` | 80%+ 文档通过 | 3h |
| 错误场景实现 | 3 个 submodule | 所有错误场景有明确消息+退出码 | 4h |
| 错误信息测试 | `tests/test_error_messages.py` | 覆盖所有错误码 | 3h |
| 翻译一致性测试 | `tests/integration/test_translation_consistency.py` | 术语一致性 > 95% | 3h |
| 格式保留测试 | `tests/integration/test_format_preservation.py` | DOCX 表格/样式保留 | 2h |
| CI 集成（nightly build） | `.github/workflows/nightly.yml` | 真实 LLM 测试 nightly 运行 | 2h |
| **Phase 3 总计** | | | **~30h** |

### 6.7 Phase 3 完成标准

- [ ] 真实 LLM 集成测试通过（5+ 个）
- [ ] 真实文档测试通过（80%+ 文档）
- [ ] 所有错误场景有测试覆盖
- [ ] 翻译一致性测试通过（>95%）
- [ ] Fidelity text_score > 0.9（不是 0.5）
- [ ] CI nightly build 运行真实 LLM 测试

---

## 7. Phase 4: 生产就绪（可观测 + 安全 + 性能）

**目标**：可在生产环境部署，有 SLA、有监控、有安全审计。

**工作量**：27h（从原 26h 微调）

**重要修正**（来自 Momus 审查）：
- 可观测性不是"客户问的"，但没有它，调试生产问题是盲目的
- 安全审计需要明确阈值和 fail 机制

### 7.1 可观测性

**当前状态**：OPP 有 log file，但不是结构化；OL/ORF 无可观测性。

**所需工作**：

1. **结构化日志**（统一使用 `structlog`）：
   ```python
   import structlog
   log = structlog.get_logger()
   log.info("extraction_complete",
            file=file_path,
            duration_ms=duration,
            pages=page_count)
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

### 7.2 安全审计

**所需工作**：

1. **路径遍历**：审计 `PathValidator`，添加 fuzz 测试
2. **注入攻击**：文件名注入、prompt 注入、输出文件名注入
3. **沙箱逃逸**：临时文件清理、子进程隔离
4. **CVE 扫描**（`trivy`）：
   - CI 中每次 PR 扫描
   - High/Critical 级别 CVE 必须修复或豁免
   - 豁免必须有理由和过期日期
5. **License 合规**：
   - `pip-licenses` 生成依赖 license 清单
   - 确保所有依赖兼容项目 license
   - 注意 `poppler-utils`（GPLv2）和 `tesseract-ocr`（Apache 2.0）

### 7.3 性能基准

**当前状态**：没有 SLA 文档。

**SLA 文档**（`docs/SLA.md`）：

| 指标 | 目标 | 测量方法 |
|------|------|----------|
| DOCX 提取 P95 | < 5s | 30+ 次运行 |
| PDF 提取 P95 | < 30s | 30+ 次运行 |
| OL 翻译 P95 | < 10s/1000 tokens | 真实 LLM |
| ORF backfill P95 | < 10s | 30+ 次运行 |
| 内存峰值 | < 500MB (DOCX < 10MB) | memory_profiler |
| 启动时间 | < 1s | cold start |

**性能测试**（`tests/benchmark/`）：
- 使用 `pytest-benchmark`
- 在 CI 中定期运行（防止回归）
- 报告存储在 `test_artifacts/benchmarks/`

### 7.4 API 稳定性

**当前状态**：三个模块独立版本号，无版本策略。

**版本策略**（`docs/API_STABILITY.md`）：
- 严格遵守 SemVer
- 公开 API 在 minor 版本内不变
- 弃用流程：先标记 deprecated → 过两个 minor 版本 → 删除
- 三个模块的版本号可以独立，但需要 `VERSION_COMPATIBILITY.md`（Phase 0 建的）保证协同工作

**Contract 测试**（`tests/contract/`）：
```python
def test_cli_help_contract():
    """CLI --help output must not change without major version bump."""
    result = subprocess.run(["opp", "--help"], capture_output=True, text=True)
    assert result.stdout == load_fixture("opp_help.txt")
```

### 7.5 任务分解

| 任务 | 文件 | 验收标准 | 时间 |
|------|------|----------|------|
| 结构化日志（3 模块） | `*` × 3 | JSON 格式输出，字段标准化 | 6h |
| Metrics + tracing（3 模块） | `*` × 3 | OTel exporter 工作 | 6h |
| 安全审计 + 修复 | `docs/SECURITY_AUDIT.md` | 无 High/Critical 漏洞 | 4h |
| CVE 扫描 CI | `.github/workflows/security.yml` | 每次 PR 扫描，High 阻塞 | 1h |
| License 合规 | `THIRD_PARTY_LICENSES.md` | 所有依赖 license 记录 | 1h |
| 性能基准 + SLA | `docs/SLA.md` + `tests/benchmark/` | SLA 文档化，CI 集成 | 4h |
| API 稳定性策略 | `docs/API_STABILITY.md` | SemVer + 弃用流程 | 1h |
| Contract 测试 | `tests/contract/` | CLI/MCP 接口冻结 | 3h |
| **Phase 4 总计** | | | **~26h** |

### 7.6 Phase 4 完成标准

- [ ] 结构化日志（JSON 格式）覆盖 3 个模块
- [ ] Metrics 暴露（OTel 或 Prometheus）
- [ ] 安全审计无 High/Critical CVE
- [ ] 性能 SLA 文档化并满足
- [ ] API 稳定性策略发布

---

## 8. 跨切关注点

### 8.1 测试策略

每个 phase 完成后必须满足：

| 测试类型 | 工具 | 目标覆盖率 |
|---------|------|-----------|
| 单元测试 | pytest | > 80% |
| 集成测试 | pytest | 所有 CLI/MCP 入口 |
| 端到端测试 | pytest | 每个 phase 的验收场景 |
| 性能测试 | pytest-benchmark | SLA 文档化 |
| 安全测试 | bandit, trivy | 无高危漏洞 |

### 8.2 持续集成

每个 PR 必须通过：
- [ ] 单元测试
- [ ] 集成测试
- [ ] Lint (ruff)
- [ ] Type check (mypy)
- [ ] Security scan
- [ ] Coverage 报告（>80%）

### 8.3 发布流程

1. 跑 `bumpversion.py` 更新三个模块版本号
2. 更新 `VERSION_COMPATIBILITY.md`
3. 运行完整测试矩阵（Tier 7/8）
4. Tag 三个 submodule 仓库
5. 推送到 PyPI
6. 构建 Docker 镜像
7. 推送到 GitHub Container Registry
8. 更新文档站点

---

## 9. 验收标准总览

### 9.1 Phase 0 完成标准

- [ ] 三个 submodule 固定到已知绿基线
- [ ] `VERSION_COMPATIBILITY.md` 发布
- [ ] `tests/integration/test_version_compat.py` 在 CI 中运行
- [ ] `bumpversion.py` 可用

### 9.2 Phase 1 完成标准

- [ ] `npx @modelcontextprotocol/inspector python -m opp.mcp.server` 列出 7 个工具
- [ ] `npx @modelcontextprotocol/inspector python -m ol_mcp` 列出 8 个工具
- [ ] `npx @modelcontextprotocol/inspector python -m orf.mcp.server` 列出 6 个工具
- [ ] `tests/mcp/test_e2e_agent_flow.py` 通过
- [ ] `scripts/mcp_bridge.py` 已删除
- [ ] `mcp_matrix_verifier.py` 改用真实 MCP 客户端并通过全矩阵

### 9.3 Phase 2 完成标准

- [ ] `docker/Dockerfile.test` 在干净环境能 build
- [ ] `pip install opp omni-localizer omni-re-formatter` 在干净环境零冲突
- [ ] 每个模块有 README + API reference + tutorial + troubleshooting + architecture
- [ ] Docker 镜像构建成功并推送到 GHCR
- [ ] 跨平台 CI（Linux + macOS + Windows）绿

### 9.4 Phase 3 完成标准

- [ ] 真实 LLM 集成测试通过（5+ 个）
- [ ] 真实文档测试通过（80%+ 文档，来源可追溯）
- [ ] 所有错误场景有测试覆盖
- [ ] 翻译一致性测试通过（>95%）
- [ ] Fidelity text_score > 0.9
- [ ] CI nightly build 运行真实 LLM 测试

### 9.5 Phase 4 完成标准

- [ ] 结构化日志（JSON 格式）覆盖 3 个模块
- [ ] Metrics 暴露
- [ ] 安全审计无 High/Critical CVE
- [ ] 性能 SLA 文档化并满足
- [ ] API 稳定性策略发布

### 9.6 总体"Production Ready"标准

**所有以下条件必须同时满足**：

1. ✅ Phase 0 全部完成
2. ⏳ Phase 1 全部完成（MCP 真实服务器工作）
3. ⏳ Phase 2 全部完成（部署体验）
4. ⏳ Phase 3 全部完成（产品质量 + 翻译质量）
5. ⏳ Phase 4 全部完成（生产就绪）
6. ⏳ 三个模块的 `pip install` 端到端通过
7. ⏳ 真实 LLM + 真实文档测试通过
8. ⏳ 翻译质量指标满足阈值（fidelity > 0.9）
9. ⏳ MCP 服务器可被 Claude/Cursor agent 实际调用
10. ⏳ 客户文档完整（README + Tutorial + API reference + Troubleshooting）

---

## 10. 风险登记（更新版）

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 标准 `mcp` 库也有 stdio bug | 中 | 高 | Phase 0 验证；如不行，保留 `mcp_bridge.py` 作为兜底 |
| Phase 1 重写引入新 bug，破坏现有测试 | 高 | 中 | 在重写前先备份 + 跑完整测试；如失败回滚 |
| 真实 LLM API 成本超预算 | 中 | 中 | 使用 gpt-4o-mini，限制 token，nightly 而非每次 PR |
| 真实文档版权问题 | 中 | 中 | 仅用 CC0/Public Domain；记录来源；自生成合成文档 |
| 跨模块版本不兼容 | 高 | 高 | Phase 0 的 `VERSION_COMPATIBILITY.md` + 兼容性测试 |
| 跨平台兼容性（Windows 路径分隔符） | 高 | 中 | 5.4 节有专门预算 |
| 翻译质量不达标（fidelity < 0.9） | 中 | 高 | 用更大模型、人工审阅、术语表管理 |
| 真实文档大文件（>100MB）超时 | 中 | 中 | Phase 3.2 限制 50MB，Phase 4.13 单独处理大文件 |
| 三个 submodule 发布不同步 | 高 | 中 | `bumpversion.py` + `VERSION_COMPATIBILITY.md` |
| 回滚困难（无 feature flag） | 中 | 中 | Phase 1 添加 `OPP_USE_NEW_MCP` 环境变量回退 |

---

## 11. 时间线（修正版）

| Phase | 内容 | 估计时间 | 累计 |
|-------|------|----------|------|
| Phase 0 | 预检（版本策略 + 跨模块兼容） | 8h | 8h |
| Phase 1 | Unblock Agent（MCP 真实服务器） | 20h | 28h |
| Phase 2 | 部署体验（pip install + Docker + 跨平台） | 25h | 53h |
| Phase 3 | 产品质量（真实 LLM + 真实文档 + 翻译质量） | 30h | 83h |
| Phase 4 | 生产就绪（可观测 + 安全 + 性能） | 26h | **109h** |

**总计约 109 工时**（3-4 周全职，含缓冲）

**建议从 Phase 0 开始**——它解决了一个被原计划完全忽略的基础问题：三个模块的版本协调。没有它，后续 phase 的所有测试都建立在不确定的版本基础上。

---

## 12. 立即下一步

**建议从 Phase 0 开始**（不是 Phase 1），因为：
1. 它是所有后续 phase 的基础
2. 它暴露了跨模块依赖的真实情况
3. 它是 8h 的可控工作量
4. 没有它，Phase 1-4 的工作都在不确定的版本基础上

**具体第一步**（Phase 0 任务 1）：
1. 在 `Omni_Suite` monorepo 中固定三个 submodule 的 SHA
2. 验证 CI 在此基线绿
3. 创建 `VERSION_COMPATIBILITY.md` 文档

---

## 13. 版本策略与跨模块协调（新章节）

### 13.1 版本号策略

**当前状态**：
- OPP 0.6.1、OL 0.4.4、ORF 0.4.3（独立版本号）
- 没有兼容性矩阵
- 没有发布协调流程

**目标**：
- 三个模块独立 SemVer（不同团队可以独立发布）
- 但有 `VERSION_COMPATIBILITY.md` 声明哪些版本组合是测试过的
- `bumpversion.py` 同时更新三个版本号（用于协调发布）

### 13.2 VERSION_COMPATIBILITY.md 格式

```markdown
# Version Compatibility Matrix

| opp | ol | orf | Status | Last Tested |
|-----|-----|-----|--------|-------------|
| 0.6.1 | 0.4.4 | 0.4.3 | ✅ Tested | 2026-06-22 |
| 0.6.0 | 0.4.3 | 0.4.2 | ✅ Tested | 2026-06-15 |
| 0.5.0 | 0.4.0 | 0.4.0 | ⚠️ Partial | 2026-06-01 |

## Compatibility Rules

- Same major version: guaranteed compatible
- Lower major + higher minor: usually compatible, test before upgrading
- Different major versions: NOT compatible, breaking changes

## Tested Combinations

CI runs `tests/integration/test_version_compat.py` on every PR to verify
new version combinations work end-to-end.
```

### 13.3 bumpversion.py

```python
#!/usr/bin/env python3
"""Bump version across OPP, OL, ORF simultaneously."""
import sys
import re
import subprocess
from pathlib import Path

SUITE_ROOT = Path(__file__).resolve().parent.parent
MODULES = {
    "opp": SUITE_ROOT / "Omni_Pre_Processor/pyproject.toml",
    "ol": SUITE_ROOT / "Omni_Localizer/pyproject.toml",
    "orf": SUITE_ROOT / "Omni_Re_Formatter/pyproject.toml",
}

def bump(level: str):
    """Bump version (major|minor|patch) in all three modules."""
    for name, path in MODULES.items():
        content = path.read_text()
        # ... bump version
        path.write_text(content)
        print(f"✅ Bumped {name} to new version")

if __name__ == "__main__":
    level = sys.argv[1] if len(sys.argv) > 1 else "patch"
    bump(level)
```

---

## 14. 回滚与迁移计划（新章节）

### 14.1 回滚策略

每个 phase 的重大变更都应该有回滚方案。

| Phase | 变更 | 回滚方案 |
|-------|------|----------|
| Phase 1 | OPP/ORF MCP 重写 | 环境变量 `OPP_USE_LEGACY_MCP=1` 切回旧实现 |
| Phase 1 | 删除 `mcp_bridge.py` | 从 git history 恢复（tag `pre-phase-1`） |
| Phase 2 | 文档重写 | git revert + 从 git history 恢复 |
| Phase 3 | 真实 LLM 默认开启 | 环境变量 `OMNI_USE_FAKE_LLM=1` 回退 |
| Phase 4 | OpenTelemetry 集成 | 环境变量 `OMNI_DISABLE_OTEL=1` 关闭 |

### 14.2 迁移指南

每个 phase 完成后必须有 `docs/MIGRATION_<phase>.md`：

#### Phase 1 迁移指南（MCP 重写）

**对用户的影响**：
- 如果你直接用 `mcp_bridge.py`（unlikely），需要切换到标准 MCP 客户端
- 如果你用 `opp-mcp-server` / `ol-mcp` / `orf-mcp-server`，无影响（接口不变）
- 如果你用 FastMCP 自定义工具，需要更新到标准 mcp 库

**步骤**：
1. `pip install --upgrade opp omni-localizer omni-re-formatter`
2. 重启 MCP 服务器
3. 验证：`npx @modelcontextprotocol/inspector python -m opp.mcp.server`

**回滚**：
```bash
pip install opp==0.6.1 omni-localizer==0.4.4 omni-re-formatter==0.4.3
```

---

## 15. 翻译质量标准（新章节）

对于文档本地化工具，**翻译质量是核心**，不是测试覆盖率。

### 15.1 翻译质量指标

| 指标 | 定义 | 目标阈值 | 测量方法 |
|------|------|----------|----------|
| **Fidelity text_score** | 翻译后保留的源文本比例 | > 0.9 | `fidelity_checker.py` |
| **Fidelity table_score** | 表格行列保留率 | > 0.95 | `fidelity_checker.py` |
| **Fidelity image_score** | 图片保留率 | > 0.8 | `fidelity_checker.py` |
| **翻译一致性** | 相同术语在不同文档中翻译相同 | > 95% | 跨文档术语对比 |
| **格式保留** | DOCX 布局/样式不被破坏 | > 95% | python-docx 解析 |
| **错误率** | 翻译错误（拼写、语法、术语） | < 5% | 人工标注 + 自动检测 |
| **语言对覆盖** | 支持的语言对数量 | ≥ 5 对 | en↔zh, en↔ja, en↔de, en↔fr, en↔ko |

### 15.2 翻译质量测试

```python
@pytest.mark.translation_quality
def test_terminology_accuracy():
    """术语翻译准确性：人工标注的 ground truth 术语表。"""
    # Ground truth from TRANSLATION_QUALITY.md
    GROUND_TRUTH = {
        "machine learning": "机器学习",
        "neural network": "神经网络",
        "deep learning": "深度学习",
        "transformer": "Transformer",  # 专业术语不翻译
        # ... 200+ 术语
    }
    
    # 在 10 个真实文档上运行
    for doc in REAL_CORPUS:
        translated = run_pipeline(doc, "en", "zh")
        for en, zh in GROUND_TRUTH.items():
            if en.lower() in doc.text.lower():
                assert zh in translated.text, f"术语 {en} 应翻译为 {zh}"

@pytest.mark.translation_quality
def test_format_preservation():
    """DOCX 格式保留：表格、样式、页眉页脚不被破坏。"""
    src = REAL_CORPUS / "complex.docx"
    translated = run_pipeline(src, "en", "zh")
    
    # 用 python-docx 解析翻译后的文件
    from docx import Document
    src_doc = Document(src)
    out_doc = Document(translated)
    
    # 表格数量不变
    assert len(src_doc.tables) == len(out_doc.tables)
    
    # 段落数大致相同（允许 ±10% 因为语言膨胀）
    src_paras = len(src_doc.paragraphs)
    out_paras = len(out_doc.paragraphs)
    assert 0.9 * src_paras <= out_paras <= 1.3 * src_paras
```

### 15.3 人类审阅工作流

对于翻译工具，"生产就绪"传统上意味着有人类审阅。

**未来 Phase（v3+）考虑**：
- 何时需要人工审阅？（专业领域、法律文档、医疗）
- 翻译人员如何访问待审阅的翻译？
- 质量保证步骤（编辑、校验）
- 用户如何覆盖 LLM 的翻译选择？

**当前 Phase 不实现**（标记为 v3+ 任务），但文档中说明。

---

## 16. 附录

### 16.1 三个模块的当前状态

#### OPP (`Omni_Pre_Processor` @ `3684e87` + patches)
- **版本**：0.6.1
- **支持的输入**：16 种格式
- **CLI**：`opp`
- **MCP**：`opp-mcp-server`（7 个工具）— **不可用**（FastMCP bug）
- **MCP 实现**：`from fastmcp import FastMCP`，使用 `_mcp.add_tool()` 命令式注册
- **已知 bug**：EPUB 提取非确定性（已修）

#### OL (`Omni_Localizer` @ `4685a47` + patches)
- **版本**：0.4.4
- **支持的输入**：MD, XLIFF
- **CLI**：`ol translate-md`, `ol translate-xliff`
- **MCP**：`ol-mcp`（8 个工具）— **不可用**
- **MCP 实现**：`from mcp.server.fastmcp import FastMCP`（**标准 mcp 库的 fastmcp 子模块**，不是独立 fastmcp 包）— 这意味着 OL 的根因可能与 OPP/ORF 不同
- **依赖**：LLM API（OpenAI, Anthropic, Zhipu 等）

#### ORF (`Omni_Re_Formatter` @ `c7d6853` + patches)
- **版本**：0.4.3
- **支持的输入**：MD, XLIFF
- **支持的输出**：16 种格式
- **CLI**：`orf apply-md`, `orf apply-xliff`
- **MCP**：`orf-mcp-server`（6 个工具）— **不可用**
- **MCP 实现**：`from fastmcp import FastMCP`，使用 `@server.tool()` 装饰器
- **依赖**：缺少 `mcp` 库（只有 `fastmcp`）

### 16.2 现有测试基础设施

| 文件 | 行数 | 用途 |
|------|------|------|
| `scripts/format_matrix_verifier.py` | 678 | Tier 7/8 矩阵验证器 |
| `scripts/mcp_matrix_verifier.py` | 452 | MCP 矩阵验证器（Phase 1 后需更新） |
| `scripts/mcp_bridge.py` | 230 | MCP workaround（Phase 1 后删除） |
| `scripts/equivalence_checker.py` | 241 | 确定性检查 |
| `scripts/fidelity_checker.py` | 240 | 真实度评分 |
| `scripts/corpus_generator.py` | 250 | 手工文档生成器 |
| `scripts/omo_loop.py` | 1299 | 主控循环 |
| `tests/test_format_matrix_verifier.py` | 239 | 矩阵验证器测试 |
| `tests/test_corpus_fidelity_equivalence.py` | 300+ | 新组件测试 |
| `tests/test_convergence_watch_gates.py` | ? | Tier 6/7/8 gate 测试 |

### 16.3 关键发现（来自 Metis + Momus 审查）

1. **MCP 是最大 blocker**：三个真实 MCP 服务器都不能用
2. **真实 LLM 未测**：所有测试用 FAKE_LLM
3. **真实文档未测**：只有 5 个手工文档
4. **bridge 是 workaround**：不是真正的产品修复
5. **测试矩阵本身是好的**：能发现真实 bug
6. **OPP 代码风格不准确**（Momus 指出）：计划展示 `@_mcp.tool()` 装饰器，实际用 `_mcp.add_tool()`
7. **OL 根因可能不同**（Momus 指出）：OL 用标准 mcp 库，不是独立 fastmcp 包
8. **Phase 顺序应调整**（Metis 建议）：Phase 2（部署）应在 Phase 3（质量）之前
9. **时间估计严重低估**：75h → 109h（含缓冲）
10. **缺少版本策略**（Momus 严重批评）：三个独立版本号无协调
11. **缺少回滚计划**（Momus 严重批评）：Phase 1 后无兜底
12. **翻译质量被低估**（Metis 严重批评）：fidelity > 0.5 对生产不可接受
13. **真实文档来源法律问题**（Momus 指出）：arXiv、GitHub README 不能用

### 16.4 关键决策记录

| 决策 | 理由 |
|------|------|
| 新增 Phase 0 | 原计划缺失跨模块版本协调，会导致后续 phase 不可靠 |
| Phase 顺序：1 → 2 → 3 → 4 | Metis 建议：部署（2）应在质量（3）之前 |
| Phase 1 用标准 mcp 库替换 FastMCP | FastMCP 3.4.2 是最新且有 bug，升级/降级都不可行 |
| Phase 1 后删除 mcp_bridge.py | bridge 是测试 workaround，不是产品 |
| 保留 mcp_bridge.py 作为回滚兜底 | 风险登记建议：标准 mcp 库可能也有 bug |
| Phase 3 用小模型（gpt-4o-mini）测试 | 控制 API 成本 |
| Phase 3 真实文档用 CC0/public domain | 避免版权问题 |
| Phase 3 文档按用户视角写 | 当前文档是开发者视角，用户看不懂 |
| Phase 4 选 OpenTelemetry | 行业标准，避免 vendor lock-in |
| Fidelity 阈值 0.9（不是 0.5） | Metis 指出 0.5 对生产不可接受 |
| 错误码标准化 | 每个错误场景有明确退出码和 stderr 内容 |
| VERSION_COMPATIBILITY.md | 三个模块独立版本，但需要兼容性矩阵 |
| bumpversion.py | 协调三个模块的发布 |

---

**文档版本**：2.0  
**创建日期**：2026-06-22  
**v1 → v2 更新**：基于 Metis + Momus 审查，重大修订  
**状态**：待审阅 + 执行
