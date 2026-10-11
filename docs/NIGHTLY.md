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

- **格子 201 个** = md 路径 11 输入 × 15 输出（**165**）+ xliff 路径 6 输入 × 6 输出（**36**）
- **通道 2 条** = CLI（`scripts/format_matrix_verifier.py`）× MCP（`scripts/mcp_matrix_verifier.py`），**同一个 201 格矩阵**，一条走子进程 CLI、一条走 MCP 工具调用
- **合计 402 次格子运行**，全部通过才算达标

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
选到缺 `opp` / `orf` / `ol_cli` 的环境时，**它不报环境错**，而是让 201 格**逐个 FAIL**。

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
| 402 格归零且 skip 未超基线（`nightly_gap.py` exit 0） | **机器**（agent 跑） |
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
# exit 0 = 402 格全过且 skip 未超基线 / 1 = 仍有差距 / 2 = 环境或用法错误（需人介入）

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

## 【活区】当前差距矩阵（真基线 2026-10-01）

### 2026-10-10 夜间复跑（在最新 main `c0c951e` 上）

`.venv_ol/bin/python scripts/nightly_gap.py` **exit 1 —— 仍有差距（`gap_units 58`，0 fail）**，与 2026-10-09 复跑一致，无退步。

- 合计 **402** 格（CLI + MCP）· passed **292** · failed **0** · skipped **110**（豁免 52 + 需清理 58）。
- 每通道：CLI `201 / 146 / 55 / 0` · MCP `201 / 146 / 55 / 0`（逐格一致 → DoD ③ 通道一致成立）；`needs_cleanup = 29 / 通道`。
- 回归护栏：`regression_gap 0`（skipped 55 ≤ 基线 67/通道）。
- **环境类 skip 本轮为 0**（`md2pptx not installed` 等已不再命中）。
- 剩余 29 skip/通道 = **两类已登记的能力债**：
  - `XLIFF cross-format not supported by ORF converters` —— 23 格/通道（跨格式回填 = 研究级工作，见 `ACCEPTED_GAPS.md`）。
  - `XLIFF: OPP doesn't produce skeleton for EML` —— 6 格/通道（**按决定延期**，非遗漏；见 `ACCEPTED_GAPS.md`）。

**读法**：余下 58 是**成对的两类能力债**，已在 `ACCEPTED_GAPS.md` 明面登记，且**故意留在 `gap_units` 里**（不靠改口径洗白）。它不会靠装二进制或补夹具消失，需要 owner 裁定是否投研究级工作量。**最终裁决由 owner 保留**。

### 2026-10-02 夜间复跑（在最新 main 上）

| 通道 | Cells | Pass | Skip | Fail | 时长 |
|:---|---:|---:|---:|---:|---:|
| **CLI** | 195 | **141** | 54 | **0** | 4021.3s |
| **MCP** | 195 | **141** | 54 | **0** | 613.0s |
| **合计** | 390 | **282** | 108 | **0** | — |

`nightly_gap.py`：`gap_units 88 → 41`、`passing_units 256 → 282`、`skipped 134 → 108`、`failed 0 → 0`。
两个通道**逐格一致**（同样的 skip_reasons 计数）→ DoD ③ 通道一致继续成立。

剩余 skip/通道（**下表为 2026-10-04 在 main `6eb6f42` 上的重测值**，非 10-02 原始值）：

| skip 理由 | 每通道格数 | 10-02 原值 | 变化原因 |
|:---|---:|---:|:---|
| `md2pptx` CLI 未安装 | 17 | — | **环境类**，见下方口径更正 |
| MD→SRT 需要时间戳（夹具无） | 11 | 11 | — |
| MD→JSON 需要 JSON 代码块或 OPP key=value | 11 | 11 | — |
| XLIFF 跨格式 ORF 不支持 | 10 | 10 | — |
| XLIFF：OPP 不产 XLSX 骨架 | 4 | 4 | — |
| XLIFF：OPP 不产 HTML 骨架 | 4 | 5 | `md2pptx` 缺失先命中，格数少1 |
| XLIFF：OPP 不产 EML 骨架 | 4 | 5 | 同上 |
| ~~XLIFF：OPP 不产 EPUB 骨架~~ | **0** | 5 | **规则已回收**，见 #140 |
| PPTX→XLSX（夹具无对应内容） | 1 | 3 | `md2pptx` 缺失先命中 |

**合计 62 skip/通道**（10-02 记录为 54）。

> **口径更正（重要）**：10-02 那版称「剩余 54 skip 全部是内容/能力类，
> **已无 `X not installed` 的环境类条目**」。**该断言不成立**——在main `6eb6f42` 上
> 重测，`md2pptx CLI not installed` 命中 **17 格/通道**，是最大的单一 skip 理由，
> 且明确属于环境类。10-02 的表格把它漏掉了，因此 54 这个总数与「无环境类」的结论
> 都不成立。差异来源：`html→pptx` / `xlsx→pptx` / `epub→pptx` / `docx→pptx` 等格在
> `md2pptx` 缺失时**先命中输出可用性规则**，不再走到骨架规则，故 EPUB 的 5 格变 0
> （规则回收，见 e2e-test-suite#140）、HTML/EML 各少 1 格。

> **另一处口径提醒**：`max_skip` 从 200（旧基线）变为 67（当前 main 的 `nightly_gap.py` 默认），
> 因此「gap_units 由 88 → 41」是同口径下的真实下降；`regression_gap` 仍为护栏，不跨通道累加。

### 2026-10-01 基线（历史）

**CLI 通道：跑通了。** 真基线（`.venv_ol`，三件套齐全，`--json --out-dir`）：

| 通道 | Cells | Pass | Skip | Fail | 时长 |
|:---|---:|---:|---:|---:|---:|
| **CLI** | 195 | **128** | 67 | **0** | 809.8s |
| MCP | — | — | — | — | 起不来，见下 |

> CLI 通道 **非跳过的 128 格 100% 通过**，0 失败。
> 产物是真的：例 `md_html_to_docx/result.docx` 10,661 字节、
> `md_eml_to_eml/result.eml` 等，每格都有独立产出目录。

**MCP 通道：一格都没跑过**，两个缺陷（都已提 issue）：

1. **起不来** —— 验证器漏设 OL 白名单变量（`OPP_MCP_ALLOWED_DIRS` /
   `ORF_MCP_ALLOWED_DIRS` 都设了，**唯独漏 OL**），而 OL 的 MCP 服务是 fail-CLOSED，
   没白名单就拒绝启动 → `McpError: Connection closed`，整条通道死在启动阶段。
   **issue #109**。实测补上 `OL_MCP_ALLOWED_DIRS` 后三个服务全起。
2. **起来也全红** —— 验证器读 `opp_resp["md_content"]`，但 OPP 实际返回标准
   envelope `{success, content}`，md 文本在 `content.content`，顶层没有 `md_content`
   → 每个非跳过格子恒判 fail。**issue #110**。
   小样实测：`--subset docx --path-filter md` → `pass 0 / fail 2 / skip 13`，
   2 个非跳过格子全部因这条判红，而同格 CLI 通道是 PASS。

**旧口径的 67 个 skip（已于 2026-10-02 作废，勿再引用）**：来自 `SKIP_RULES` —— 缺 `pandoc` /
`md2pptx` / `aspose` 等外部二进制，以及若干"通用 MD 承载不了该结构"的输入×输出组合
（JSON / XLSX / SRT 等）。当时的说法是「**这 67 个是当前冻结基线**（`--max-skip`，回归护栏用），
其中豁免 23 + 需清理 44」。

**这段数字的问题不是"偏了"，而是"几乎没有信息量"**：它测于 MCP 验证器仍持静态跳过表时，
该表对 `pandoc` / `md2pptx` / `aspose` 类规则**无条件跳过**（不看依赖是否真的缺失），
于是 MCP 通道 195 格里只有 **20 格**真的跑过 —— 也就是下面那句
「MCP 通道的数字目前一个都不能信——不是"全红"，是"没跑"」的字面含义。
`#129` 让 MCP 通道改用 CLI 的动态判定后，**跳过 175 → 64，111 格从 dead 变为实跑**。
**冻结区（DoD 定义与验收判据）以上面那段「跳过数由环境决定」的环境标注表为准。**

**读法**：CLI 通道已经是一条**真的、能出产物的链路**（这是本计划第一个真基线）。
MCP 通道的数字在 `#129` 之前**一个都不能信**——不是"全红"，是"没跑"；`#129` 之后
两通道对每一格给出同一判定（见下表 `CLI vs MCP` 列），才第一次可比。

### 差距计算器用法：口径与参数（活区补充 2026-10-01）

`scripts/nightly_gap.py` 的**用法段落**（只补参数说明；上面【冻结区】的完成定义与验收判据未动）：

```bash
# 全量（默认口径：minimal 夹具、无子集、不算保真度）
.venv_ol/bin/python scripts/nightly_gap.py \
    --json-out test_artifacts/nightly/gap.json \
    --md-out  test_artifacts/nightly/gap.md

# 只跑子集 + 真实夹具 + 保真度（三个参数都原样透传给 CLI 与 MCP 两个验证器）
.venv_ol/bin/python scripts/nightly_gap.py \
    --subset docx --corpus real --fidelity \
    --json-out test_artifacts/nightly/gap.json
```

| 参数 | 默认 | 含义 |
|:---|:---|:---|
| `--subset` | 空 = **全量** | 透传：只跑指定输入子集（逗号分隔，如 `docx,md`）。子集跑总格数变小，需同时给 `--expect-total`（不自动放行） |
| `--corpus` | `minimal` | 透传：矩阵夹具口径。`minimal` = 最小夹具（**默认事实口径**）；`real` = `test_corpus/` 真实夹具 |
| `--fidelity` | 关 | 透传：通过的格子再算内容保真度分数。按能力探测透传——MCP 验证器暂不认 `--fidelity`，会跳过并在 markdown 里写明，不硬传报错 |
| `--max-skip` | `67` | **回归护栏**的每通道跳过基线（不是两条通道相加后的合计基线）。**不参与判定与退出码**。⚠️ 取值**只在它被测量的那个依赖环境下有意义**（见下表：`pandoc+weasyprint+nbformat` 下实测 64，余量仅 3；六项全无时 136，每通道超额 69） |

**两个口径，物理分开（2026-10-01 裁定，活区）**：

```text
# 1) DoD 口径 —— 判定与退出码只用它
gap_units      = fail 合计 + Σ_通道 (skipped_通道 − exempt_通道)      # = 还需清理的跳过格子数

# 2) 回归护栏 —— 只抓「跳过数变多」的退步，不参与判定
regression_gap = fail 合计 + Σ_通道 max(0, skipped_通道 − --max-skip)  # 每通道比，各比各的
```

- **`gap_units == 0` → exit 0；否则 exit 1。** 护栏通过 **≠ 达标**：
  把 `--max-skip` 调宽只会洗掉退步告警，洗不掉 DoD 差距（exit 仍由 `gap_units` 定）。
- CLI、MCP **各自**跟 `--max-skip` 比一次；JSON 看顶层 `regression_gap`（= 各通道
  `regression_excess` 之和 + fail）与 `per_channel: {CLI: {total, passed, skipped,
  failed, exempt, needs_cleanup, regression_excess}, MCP: {…}}`，
  顶层 `channels` 里保留各通道原始 `total/passed/skipped`。
- JSON 另带 `run_options: {subset, corpus, fidelity}` —— 每份矩阵自带口径，横向可比。

> **为什么必须分开**：只有护栏口径时，本仓实测会出现
> 「每通道 skip 67 ≤ 基线 67 → `gap_units 0` → exit 0」的**假达标**，
> 而实际每通道还有 **44 个需清理的 skip**（环境类 15 + 能力类 29）。
> 两个口径同时存在：护栏抓退步，`gap_units` 认差距。

**跳过数由环境决定 —— 必须连环境一起记（2026-10-02 实测）**：

跳过侧数字**不是仓库常量**，而是「矩阵形状 × 可用外部依赖」的函数。把依赖装上，
`skipped` 就下降；把依赖卸掉，`skipped` 就上升。因此**任何只写数字不写环境的
「真值」都是不可复现的** —— 这正是 #131 说的「skip 基线不可判定」。

下表由 `_check_skip`（CLI）与 `_should_skip`（MCP）在**全 201 格网格**上逐一求值得出
（不是抽样，也不是估算）：

| 可用依赖 | skipped | 豁免 | 需清理 | 实跑 | CLI vs MCP |
|:---|---:|---:|---:|---:|:--|
| 六项全无（纯净 CI） | 136 | 21 | 115 | 59 | 一致 |
| `+pandoc` | 76 | 21 | 55 | 119 | 一致 |
| `+pandoc,weasyprint,nbformat`（本机） | **64** | **23** | **41** | **131** | 一致 |

`CLI == MCP` 这列是 **#128 的可引用证明**：两条通道现在对每一格给出**同一个跳过判定**，
所以「通道一致」这个判据第一次真正成立。

在最后一行那个环境下，`gap_units = 82 + failed 合计`（= 41 × 2 + fail），
`regression_gap = 0`（64 ≤ 67/通道），**exit 1**（因 `gap_units > 0`）。
注意 `--max-skip 67` 在该环境下只剩 **3 格余量**；而在六项全无的环境里
每通道超额 **69**，护栏会立刻炸响 —— **`--max-skip` 的取值只在它被测量的那个环境里有意义**。

> **`#129` 之前的数字（`skipped 67` / 豁免 23 / 需清理 44 / `gap_units 88`）已于
> 2026-10-02 作废，不要再引用。** 那些数字测于 MCP 验证器仍持静态跳过表时：该表对
> `pandoc` / `md2pptx` / `aspose` 类规则是**无条件跳过**（不看依赖是否真的缺失），
> 于是 MCP 通道 195 格里只有 **20 格**真的跑过 —— 也就是 NIGHTLY.md 上面那句
> 「MCP 通道的数字目前一个都不能信 —— 不是『全红』，是『没跑』」的字面含义。
> `#129` 让 MCP 通道改用 CLI 的动态判定后：**跳过 175 → 64，111 格从『dead』变为实跑**。
> 换句话说，旧数字不是偏了，是**几乎没有信息量**。

**豁免清单 `EXEMPT_SKIP_REASONS`（夹具内容依赖类跳过，单独计数）** —— 子串匹配：

- `MD→SRT requires timestamped cues`
- `MD→JSON requires JSON code block`
- `XLSX→PPTX: no slide content`
- `PPTX→XLSX: no table content`

这些理由的跳过按通道计入 JSON 的 `exempt_skips`（附 `exempt_skip_reasons` 明细），
markdown 里写成「skip 67 = 豁免 23 + 需清理 44」，**豁免 = 夹具内容依赖，非能力缺陷；
要清掉它们需要补语料**（不是装二进制）。**豁免项不计入 `gap_units`，但仍原样出现在
`skipped` 总数里**（不静默吞掉）；`pandoc` / `nbformat` / `xliff` 之类
**环境或能力类跳过不豁免**，仍属「需清理的 skip」，照常计入 `gap_units`。

### 计算器自身修掉的一个假绿（自我披露）

第一版 `nightly_gap.py` 在验证器没落 `matrix.json` 时（`total/passed/failed/skipped`
全为 0）算出 `gap = 0 + 0 = 0`，于是**打印「两通道 390 格全过」**——拿不到数据被判成了通过。
已修：任一通道取不到矩阵、或总数 ≠ 预期 402，一律 **exit 2 并说明原因**，绝不判绿。
配套修了取数：CLI 验证器**只有传 `--json` 才写 `matrix.json`**（不传只写 `matrix.md`），
且 MCP 验证器不认 `--parallel` —— 两者开关差异改为按能力探测。

---

## 【活区】下一步队列

> 策略（L1 §4）：**先纵后横** —— 先把一条通道打穿，再复制。

1. **修 issue #109**（补 OL 白名单变量）→ MCP 通道才起得来。这是 MCP 一切的前提。
2. **修 issue #110**（`md_content` 取值层级）→ MCP 格子才可能真判 pass 而不恒红。
3. **跑出 MCP 通道基线**：`mcp_matrix_verifier.py --out-dir …`，与 CLI 的
   `195/128/67/0` 对比，验「通道一致」（DoD ③）。
4. **清 skip（真进展）**：把 `pandoc` / `md2pptx` / `aspose` 等外部二进制装上，
   逐条把 skip 换成本真的 pass。**skip 数下降才算进度**。
5. **错误面（DoD ④）**：越界/缺配置/坏输入 → 稳定错误码，不是 `INTERNAL_ERROR`。

### 已完成（agent 追加）

- 2026-10-02：**MCP 通道跑通**（`195 | 141 | 54 | 0`，613.0s），与 CLI 通道逐格一致。
  队列第 1–3 项（#109 白名单、#110 `md_content` 层级、跑 MCP 基线）**均已闭合**。
- 2026-10-02：两通道合计 `390 | 282 | 108 | 0`；`gap_units 88 → 41`（同口径）。
  ⚠️ 2026-10-04 更正：本条「已无环境类」的结论**不成立** —— main `6eb6f42` 重测显示
  `md2pptx CLI not installed` 命中 17 格/通道，为最大单一理由且属环境类。
  详见上方「口径更正」。
- 2026-10-01：**CLI 通道跑出真基线** `Cells 195 | Pass 128 | Skip 67 | Fail 0`（809.8s），
  非跳过格子 100% 通过、每格都有真实产物文件。
- 2026-10-01：本机环境修好三处 —— 补装 `omni-pre-processor` 与 `omni-localizer`（editable）；
  `e2e-test-suite/.venv_ol` 软链从误指的废弃 `.venv` 改指到三件套齐全的环境。
  手工验通完整链路：OPP 提取 → OL 翻译（en→zh）→ ORF 转换（产出 478 字节 XML）。
- 2026-10-01：`nightly_gap.py` 修掉自身一个**假绿**（拿不到矩阵时判成"全过"）——
  改为取数失败即 exit 2；并修取数开关（CLI 需 `--json` 才落 json、MCP 不认 `--parallel`，
  按能力探测）。
- 2026-10-10：夜间复跑 `gap_units 58` 不变（两类能力债），`regression_gap 0`，无退步。

---

## 【活区】摩擦账本

> 规则（L1 §5）：**不挡住 DoD 的发现，当晚一律不修，只记账**。本阶段摩擦预算 = 0。

| 日期 | 发现 | 是否挡住 DoD | 处置 |
|:---|:---|:---|:---|
| 2026-09-30 | `SETUP.md` 引用的 `.venv/DEPRECATED.md` **不存在** | 否 | 已修（#106）：`.venv/` 被 gitignore，那份文件**根本无法提交**，故改放 `docs/venv-migration.md` 并修好引用 |
| 2026-09-30 | 验证器解释器解析失败时**静默产出假红**，不报环境错 | **是** | 已加探活闸（`nightly_gap.py`）；仓库侧 `format_matrix_verifier.py` 同步加闸（#105，缺模块即 exit 2） |
| 2026-10-01 | MCP 验证器漏设 OL 白名单变量 → 整条 MCP 通道死在启动 | **是**（挡住 DoD ③） | 已提 issue #109 |
| 2026-10-01 | MCP 验证器取 `md_content` 层级错 → 非跳过格恒判红 | **是**（挡住 DoD ③） | 已提 issue #110 |
| 2026-10-01 | `nightly_gap.py` 自身在取数失败时判"全过" | **是**（假绿） | 已自修（取数失败即 exit 2），见上「自我披露」 |
| 2026-10-02 | OPP 本地 `.venv` 缺 `nbformat`（`src/opp/extractors/ipynb.py` 需它），但矩阵跑在 `.venv_ol`（有 nbformat），因此**不影响矩阵**；L1 §2.3 记的「nbformat 未声明」已过期（OPP/ORF 的 pyproject 都有 `notebook` extra） | 否 | 记账（L1 文字由 owner/code profile 改） |
| 2026-10-02 | `.venv_ol` 缺 `extract_msg` / `aspose.email`，但本轮 msg 相关格未出现在 skip_reasons 里，故未构成实际 gap | 否 | 记账（若将来 msg 格转红再处理） |

---

## 【活区】修订请求

> 认为冻结区某条不合理 → 写这里（附证据）。**不得自行修改冻结区。**

| 日期 | 目标条款 | 理由 + 证据 | 裁定 |
|:---|:---|:---|:---|
| 2026-09-30 | L1 §2.3「16 输入 × 2 通道 = 32」 | 真实矩阵是 195 格（165 md + 30 xliff）× 2 通道 = **390**；验证器 `FULL_MATRIX` 为准 | 待裁 |
