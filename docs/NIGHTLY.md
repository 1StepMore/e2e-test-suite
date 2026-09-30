# NIGHTLY.md — Omni Suite · 「不眠计划」执行面

> **两个区，物理分开，权限不同**：
> - **【冻结区】**（完成定义 + 验收命令）：由 code profile 维护。**coding agent 只读、只跑，不得修改。**
> - **【活区】**（差距矩阵 / 下一步队列 / 摩擦账本 / 修订请求）：由 **coding agent 维护**。
>
> L1 总纲：`Hermes-Workspace/00-Records/dev-assets/NIGHTLY-PLAN-L1.md`
> 冻结区要改 → 只能往活区的「修订请求」写，等 owner / code profile 裁定；期间按原样执行。

---

## 【冻结区】完成定义（DoD）

**生产单元 = 格子 × 通道**。

- **格子 195 个** = md 路径 11 输入 × 15 输出（**165**）+ xliff 路径 6 输入 × 5 输出（**30**）
- **通道 2 条** = CLI（`scripts/format_matrix_verifier.py`）× MCP（`scripts/mcp_matrix_verifier.py`），**同一个 195 格矩阵**，一条走子进程 CLI、一条走 MCP 工具调用
- **合计 390 次格子运行**，全部通过才算达标

> 说明：L1 §2.3 写的「16 输入 × 2 通道 = 32」是**粗估，不准**。真实定义以验证器里的
> `FULL_MATRIX` 为准（`ALL_INPUTS` / `ALL_OUTPUTS` / `XLIFF_INPUTS` / `XLIFF_OUTPUTS`）。
> L1 那句待更正（走修订请求）。

**一格达标 = 四件事同时成立**（与 L1 §2.3 一致）：

| 项 | 判据 |
|:---|:---|
| ① 真输入 | 用真实文件走完整链路 OPP 提取 →（OL 翻译）→ ORF 回填/转换 |
| ② 真产出 | 输出文件存在、非空、结构合法（回填类可用 XLIFF 往返校验） |
| ③ 通道一致 | 同一格 CLI 与 MCP **两条通道都跑通**，且产出等价 |
| ④ 错误面稳定 | 越界路径 / 缺配置 / 坏输入 → 稳定错误码（不是 `INTERNAL_ERROR`），退出码非零 |

### ⚠️ 抗作弊规矩一：**跳过 ≠ 通过**

验证器对缺外部二进制的格子（`pandoc` / `md2pptx` / `aspose`）**自动 skip**，且
docstring 明确写着 *"exits 0 if all non-skipped cells pass"*。

**后果**：什么都不装、全靠 skip，也能拿 exit 0 —— 这是**可以用"不装工具"换来的绿**。

**规矩**：`skipped` **单独计数**，且**不得超过冻结基线**。新增 skip = 退步，不是进步。
降低 skip 的唯一正路是把缺的外部二进制装上（这是真进展）。

### ⚠️ 抗作弊规矩二：**解释器必须先探活**

验证器按 `suite_root/.venv_ol/bin/python` 选解释器（`format_matrix_verifier.py:280`）。
选到缺 `opp` / `orf` / `ol_cli` 的环境时，**它不报环境错**，而是让 195 格**逐个 FAIL**。

**实测拿到过 `128 fail / 0 pass / 67 skip` 的整张假红矩阵**（2026-09-30，本机）——
两次原因不同，一次是 `e2e-test-suite/.venv_ol` 指向了已废弃的 `.venv`（缺 `opp`/`orf`），
一次是规范环境 `.venv_ol` 本身没装全 OL（缺 `ol_cli`）。

**规矩**：跑矩阵前必须探活。`scripts/nightly_gap.py` 会先 import
`opp.cli` / `orf` / `ol_pool`，任一失败即 **exit 2 并停下**，**绝不产出假矩阵**。
「环境不通」与「格子失败」是两件事，不许混为一谈。

### 「完成」的裁决是人工保留行

`nightly_gap.py` 退出 0 **只代表「机器可判的差距归零」，不等于项目完成**。
本仓验收体系已有同源原则（见 `docs/ACCEPTANCE.md` / `scripts/acceptance_report.py`：
`HUMAN_RESERVED` 三行在结构上排除机器裁决）。

| 判据 | 谁判 |
|:---|:---|
| 390 格归零且 skip 未超基线（`nightly_gap.py` exit 0） | **机器**（agent 跑） |
| 连续 2 轮不新增「挡住 DoD」的项 | **机器**（agent 跑） |
| **「本计划完成 / Omni 产出没问题」总裁决** | **owner（人工保留）** |

**硬规矩**：coding agent **不得**在任何报告、提交信息、PR 描述或文档里宣布
「矩阵全绿」「Omni 产出没问题」之类的**总裁决**。它只能说「差距矩阵归零，证据在此」。

---

## 【冻结区】验收命令

```bash
cd <repo>

# —— 唯一判据入口（内置探活闸；探活失败 exit 2，不产假矩阵）——
.venv_ol/bin/python scripts/nightly_gap.py \
    --json-out test_artifacts/nightly/gap.json \
    --md-out  test_artifacts/nightly/gap.md
# exit 0 = 390 格全过且 skip 未超基线 / 1 = 仍有差距 / 2 = 环境或用法错误（需人介入）

# —— 单通道直跑（定位用；注意必须用 .venv_ol 且三件套齐全）——
.venv_ol/bin/python scripts/format_matrix_verifier.py --json --out-dir /tmp/fm
.venv_ol/bin/python scripts/mcp_matrix_verifier.py    --out-dir /tmp/fm_mcp

# —— 快跑子集（验证链路是否通，不构成达标证据）——
.venv_ol/bin/python scripts/format_matrix_verifier.py --subset docx --path-filter md
```

**解释器要求**：`.venv_ol/bin/python` 必须能 import `opp.cli` / `orf` / `ol_pool` / `ol_cli`。
缺任何一个 → 见 `SETUP.md`，用 `pip install -e` 把三件套装齐；**不要**用废弃的 `.venv/`
（SETUP.md 明确 DEPRECATED）。

---

## 【活区】当前差距矩阵（基线 2026-09-30）

**基线尚未取得 —— 环境正在修**。已确认的事实：

| 事项 | 状态 |
|:---|:---|
| CLI 通道矩阵能否跑 | ❌ 不能，见下方两个根因 |
| MCP 通道矩阵 | 未试（先修 CLI） |
| 已测到的矩阵 | `total 195 / passed 0 / failed 128 / skipped 67` —— **这是假红**，不是真实差距 |

**两个根因（都已定位到行级）**：

1. `e2e-test-suite/.venv_ol` 是软链 → 指向**已废弃的 `.venv`**（缺 `opp`、`orf`）。
   验证器优先取 `suite_root/.venv_ol/bin/python`（`format_matrix_verifier.py:280`），
   于是 195 格在 OPP 那一步全部 `ModuleNotFoundError`。
2. 规范环境 `01-Projects/.venv_ol`（SETUP.md 指定的那个）**没装全 OL** ——
   `ol_pool` 可导入但 **`ol_cli` 缺失**，OL 那步全军覆没。
   已按 SETUP.md 路径补装 `omni-pre-processor`；`omni-localizer` 正在补。

**已知的 67 个 skip**（待与真基线对齐）：来自 `SKIP_RULES` —— 缺 `pandoc` /
`md2pptx` / `aspose` 等外部二进制，以及若干"通用 MD 承载不了该结构"的输入×输出组合
（JSON / XLSX / SRT 等）。**这 67 个是当前冻结基线**。

---

## 【活区】下一步队列

> 策略（L1 §4）：**先纵后横** —— 先把一条通道打穿，再复制。

1. **让验收命令真的能跑**（当前唯一阻塞）：修好解释器（已补 OPP，补 OL 中），
   跑通 `--subset docx --path-filter md`，拿到第一格真 `pass`。**这之前一切数字都不可信。**
2. **跑出 CLI 通道真基线**：`format_matrix_verifier.py --parallel 4`，记录
   passed / failed / skipped 三个数，写回本节。
3. **跑 MCP 通道基线**：`mcp_matrix_verifier.py`，与 CLI 对比，验「通道一致」（DoD ③）。
4. **清 skip**：把 `pandoc` 等外部二进制装上，逐条把 skip 换成本真的 pass（DoD 真进展）。
5. **错误面（DoD ④）**：越界/缺配置/坏输入 → 稳定错误码，不是 `INTERNAL_ERROR`。

### 已完成（agent 追加）

- 2026-09-30：本机环境补装 `omni-pre-processor`（editable）；定位并修正
  `e2e-test-suite/.venv_ol` 指向废弃 `.venv` 的软链。

---

## 【活区】摩擦账本

> 规则（L1 §5）：**不挡住 DoD 的发现，当晚一律不修，只记账**。本阶段摩擦预算 = 0。

| 日期 | 发现 | 是否挡住 DoD | 处置 |
|:---|:---|:---|:---|
| 2026-09-30 | `SETUP.md` 引用的 `.venv/DEPRECATED.md` **不存在** | 否 | 记账（已提 issue） |
| 2026-09-30 | 验证器解释器解析失败时**静默产出假红**，不报环境错 | **是**（挡住第 1 项） | 已在 `nightly_gap.py` 加探活闸；仓库侧已提 issue |

---

## 【活区】修订请求

> 认为冻结区某条不合理 → 写这里（附证据）。**不得自行修改冻结区。**

| 日期 | 目标条款 | 理由 + 证据 | 裁定 |
|:---|:---|:---|:---|
| 2026-09-30 | L1 §2.3「16 输入 × 2 通道 = 32」 | 真实矩阵是 195 格（165 md + 30 xliff）× 2 通道 = **390**；验证器 `FULL_MATRIX` 为准 | 待裁 |
