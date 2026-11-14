# Harness 运行事实速查（Omni Suite）

> 仓事实真身。通用执行规则（边界 / 权限 / 合并判定）由 Owner 侧维护，不入库。

**范围**：本仓 + 三个模块仓（Omni_Pre_Processor / Omni_Localizer / Omni_Re_Formatter）——唯一允许跨仓执行的工作空间。

**解释器**：套件根 `uv sync --all-extras`；Windows 原生用 `powershell -ExecutionPolicy Bypass -File scripts/setup_dev.ps1`（建 .venv_win；加 -CheckOnly 只校验不装）。

**必需密钥**：默认不需要 —— FAKE_LLM 走确定性零成本输出；要验真模型质量才需要真 key。

**DoD 顺序**：`make doctor` → `make test`（赶时间 `make test-quick`）。

**陷阱**：Git Bash 下 setup_dev.sh --check-only 按设计 fail-closed，不要"修"它；FAKE_LLM 只能验 plumbing / schema / 退出码，不能当人类质量证据；验证引擎硬编码 .venv_ol（#321）⇒ Windows 上先确认再改；Git Bash 的 PATH 里可能没有 make，用 Makefile 背后的等价命令。

**队列**：`gh issue list -l agent-ready --state open`。
