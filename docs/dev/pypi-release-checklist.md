# PyPI Release Checklist — OL 0.7.1 / ORF 0.4.17 补发（准备 + 验证）

> **日期**：2026-09-04 · **状态：已准备未上传** — 需 1StepMore PyPI 凭证 + 主号恢复后执行；**当前不执行上传**。
> **背景**：PyPI 实测 omni-localizer 最新 0.7.0、omni-re-formatter 最新 0.4.16，本地已就绪 0.7.1 / 0.4.17（滞后补发）。omni-pre-processor 0.9.1 与 omni-suite 0.4.0 已发布（2026-07-08 批次，owner=1StepMore）。

---

## OL 0.7.1 补发

### 本地验证（2026-09-04 已执行）

```bash
# 在 Omni_Localizer repo 内（.venv_ol 为 Python 3.13 构建环境）
.venv_ol/bin/python -m build                       # 产出 dist/omni_localizer-0.7.1-py3-none-any.whl

# 依赖解析证明（离线 dry-run，全依赖闭包 satisfied，仅 Would install omni-localizer-0.7.1）
.venv_ol/bin/pip install --dry-run --no-index dist/omni_localizer-0.7.1-py3-none-any.whl

# 可装性证明：scratch venv（Python 3.13）内真实安装 + import 验证
python3 -m venv /tmp/omni-release-venv             # 注：本机系统 python 为 3.14，须用 .venv_ol/bin/python 建 3.13 venv
/tmp/omni-release-venv/bin/pip install --no-index --no-deps dist/omni_localizer-0.7.1-py3-none-any.whl
/tmp/omni-release-venv/bin/python -c "import ol; print(ol.__version__)"   # → 0.7.1 ✓
```

- **实测输出**：`ol 0.7.1` ✓（import 包名是 `ol`，wheel 发行名 `omni_localizer` 为归一化名）
- 说明：上述 scratch-venv 安装走 `--no-index --no-deps` 离线路径，但依赖解析已由前一行 dry-run 对**完整依赖闭包**（litellm/typer/lxml/translate-toolkit/torch/span-aligner 等）证明 satisfied。完整在线 `pip install` 因当前网络（pypi.org ~12 kB/s 且连接重置）不可行——恢复后建议重跑一次完整在线安装复核。

### 补发命令（**待 1StepMore PyPI 凭证 + 主号恢复后执行**，当前不执行）

```bash
.venv_ol/bin/python -m twine check dist/omni_localizer-0.7.1-py3-none-any.whl
.venv_ol/bin/python -m twine upload --repository-url https://upload.pypi.org/legacy/ \
  --username __token__ --password <PYPI_TOKEN_1STEPMORE> \
  dist/omni_localizer-0.7.1-py3-none-any.whl
```

- **恢复后核对**：pyproject `[project.urls]` homepage 指向 `1StepMore/Omni_Localizer`（suspend 期间不可达）——主号恢复后确认 URL 有效。

---

## ORF 0.4.17 补发

### 本地验证（2026-09-04 已执行）

```bash
# 在 Omni_Re_Formatter repo 内
.venv_ol/bin/python -m build                       # 产出 dist/omni_re_formatter-0.4.17-py3-none-any.whl

# 依赖解析证明（离线 dry-run，全闭包 satisfied，仅 Would install omni-re-formatter-0.4.17）
.venv_ol/bin/pip install --dry-run --no-index dist/omni_re_formatter-0.4.17-py3-none-any.whl

# 可装性证明：同一 scratch venv（Python 3.13）内安装 + import 验证
/tmp/omni-release-venv/bin/pip install --no-index --no-deps dist/omni_re_formatter-0.4.17-py3-none-any.whl
/tmp/omni-release-venv/bin/python -c "import orf; print(orf.__version__)"   # → 0.4.17 ✓
```

- **实测输出**：`orf 0.4.17` ✓（import 包名 `orf`，wheel 发行名 `omni_re_formatter`）

### 补发命令（**待 1StepMore PyPI 凭证 + 主号恢复后执行**，当前不执行）

```bash
.venv_ol/bin/python -m twine check dist/omni_re_formatter-0.4.17-py3-none-any.whl
.venv_ol/bin/python -m twine upload --repository-url https://upload.pypi.org/legacy/ \
  --username __token__ --password <PYPI_TOKEN_1STEPMORE> \
  dist/omni_re_formatter-0.4.17-py3-none-any.whl
```

---

## omni-suite 元包依赖缺口（已记录，不改）

`omni-suite`（0.4.0）pyproject `[project].dependencies` 仅声明 3 个运行时依赖：
`prometheus_client>=0.20.0`、`mcp>=1.0.0,<2.0.0`、`anyio>=4.5.0,<5.0.0`——**未依赖**三包
（omni-pre-processor / omni-localizer / omni-re-formatter）。

**已知缺口**：`pip install omni-suite` 后，`omni-suite pipeline` 会因缺 `opp`/`ol`/`orf` 命令而失败。

**处理**：有意**不补依赖**——补上会拉入全部重型传递依赖（torch/scipy 等）。待有真实外部用户信号时再评估（见 dev-roadmap P0-1 裁决）。

---

## 四 README banner / 互链一致性（2026-09-04 核对）

| README | 顶部 Omni Suite banner | 备注 |
|:-------|:----------------------|:-----|
| OPP（Omni_Pre_Processor）| ✅ 已对齐（2026-09-04 commit `9131b72`，顶部标题下）| 原 banner 在中部，已提升/复制到顶部 |
| OL（Omni_Localizer）| ✅ 已有（~L385-402 顶部区）| 一致 |
| ORF（Omni_Re_Formatter）| ✅ 已有（~L312+）| 一致 |
| omni-suite（根 README）| ✅ 已有 | 一致 |

差异已消除；四包徽章均不再指向错误的 `pypi.org/project/opp`（PAY.ON）。
