# Harness 运行事实速查（Omni Suite）

> 仓事实真身。通用执行规则（边界 / 权限 / 合并判定）由 Owner 侧维护，不入库。

**范围**：本仓 + 三个模块仓（Omni_Pre_Processor / Omni_Localizer / Omni_Re_Formatter）——唯一允许跨仓执行的工作空间。

**解释器**：套件根 `uv sync --all-extras`；Windows 原生用 `powershell -ExecutionPolicy Bypass -File scripts/setup_dev.ps1`（建 .venv_win；加 -CheckOnly 只校验不装）。

**必需密钥**：默认不需要 —— FAKE_LLM 走确定性零成本输出；要验真模型质量才需要真 key。

**DoD 顺序**：`make doctor` → `make test`（赶时间 `make test-quick`）。

**陷阱**：Git Bash 下 setup_dev.sh --check-only 按设计 fail-closed，不要"修"它；FAKE_LLM 只能验 plumbing / schema / 退出码，不能当人类质量证据；验证引擎硬编码 .venv_ol（#321）⇒ Windows 上先确认再改；Git Bash 的 PATH 里可能没有 make，用 Makefile 背后的等价命令。

**队列**：`gh issue list -l agent-ready --state open`。

**依赖探针与能力需求**（需求侧 · 跨机器成立；本机结果不入库）

- 探针入口：`bash scripts/check_deps.sh`（与 `make doctor` 同源，`--json` 取机器可读结果）。只检测：不联网、不安装、不改状态。
- 本仓需要哪些能力（由代码决定，与机器无关）：
  - 文本产出/校验 ← 仓库 venv（Python 3.13）+ pandoc（`pypandoc-binary` 内置，PATH 无 pandoc 属预期）
  - 文档渲染校验 ← weasyprint + GTK 系统库（缺 ⇒ PDF 通道记 blocked，不算 bug）
  - 浏览器链路 ← chrome / chromium / playwright（缺 ⇒ 相关场景 blocked，不算 bug）
  - 音频/视频产物 ← 外部音视频工具 + 渲染器（缺 ⇒ 该线活交回具备该能力的机器复验，不在本机修）
- 判定结果怎么写：本机"有/没有"属**机器事实**，逐机器不同且会过期 ⇒ 写到仓外或已被 gitignore 的 `.scratch/`，
  每轮报告「环境」段带出；**禁止把 ✓/✗ 结果提交进本文件**。本文件只回答"这个仓需要什么"，不回答"这台机器有什么"。

**交接状态机（双机协作）**：issue 状态只由标签表达，两侧共用一套；改标签 = 交棒。

| 标签 | 含义 | 谁迁出 |
|:--|:--|:--|
| `agent-ready` | 契约完整，可开工 | 接活方 ⇒ 换 `status:claimed` |
| `status:claimed` | 已认领、在做 | 在做方 ⇒ 做完换 `needs-real-verification`；缺能力换 `blocked:env` |
| `blocked:env` | 缺能力/依赖，等另一台机器 | 具备该能力的一方；**判阻塞方不得自关** |
| `needs-real-verification` | 产物已出，等内容级读数 | 复验方给读数后关门 |

硬规矩：① 改标签必须同时留一行「可复跑命令 / 期望读数 / sha」；② 每条 issue 要有 `needs:` 行
（能力项名见上一节「依赖探针与能力需求」），**派活按能力匹配，不按人**；③ 只有三种情况需要 Owner 出场：
两侧都不具备该能力 / 判据与治理类改动 / 合并与发版；④ 产物验收只认内容级读数，状态枚举不算通过。
