# E2E Test Suite

OPP → OL → ORF 全链路集成测试环境，含全自动 bug 发现 → OpenCode 修复 → 验证闭环。

---

## 目录结构

```
e2e-test-suite/
├── src/
│   ├── Omni_Pre_Processor/   # OPP submodule
│   ├── Omni_Localizer/       # OL submodule
│   └── Omni_Re_Formatter/    # ORF submodule
│
├── scripts/
│   └── sync_shallow.sh       # 同步 submodule SHA 到 origin/main
│
├── test-artifacts/           # 源文档（gitkeep）
├── test-output/              # 测试输出（gitkeep）
│   └── {test-name}/
│       ├── runner.log        # 测试运行日志
│       ├── source.docx       # 源文档
│       ├── opp_out/          # OPP 提取产物
│       ├── ol_out/           # OL 翻译产物
│       └── orf_out/          # ORF 还原产物
│
├── reports/
│   ├── TEMPLATE-Bug-Report.md
│   ├── TEMPLATE-Comparison-Report.md
│   └── E2E-*.md              # 具体 bug 报告
│
├── .venv/                    # Python 3.13 venv（系统级）
├── .venv312/                 # Python 3.12 venv
│
├── run_test.sh               # 全链路测试驱动脚本
├── run_e2e.py                # Python 版 E2E（备用）
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
| E2E-04 | OL CLI | ❌ 待修复 | — |

详见 `reports/` 目录。

---

## 环境说明

| 组件 | 路径 | 版本 |
|------|------|------|
| OPP | `src/Omni_Pre_Processor` | `3684e87` |
| OL | `src/Omni_Localizer` | `4685a47` |
| ORF | `src/Omni_Re_Formatter` | `c7d6853`（含 `15834db`）|
| Python 3.13 | `.venv/` | 系统 venv（OL MCP 用）|
| Python 3.12 | `.venv312/` | 套件 venv（OPP/ORF CLI 用）|
| OL venv | `~/.hermes/venvs/omni-localizer` | Python 3.13（OL MCP 服务）|

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
```