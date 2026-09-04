# Omni Suite 后续开发报告（开发视角）

> **日期**：2026-09-02 · **基于**：商业论证报告（omni-suite-business-validation-20260902.md）+ 开发基线实测
> **定位**：聚焦开发的路线图——现有 feature 补强 + 新 feature 加入
> **⚠️ 重要修正（2026-09-04 实测）**：商业报告"撞名无法分发"的结论方向正确但措施已过时——PyPI `opp` 实为 PAY.ON 支付 SDK（撞名属实），OPP 已改名 `omni-pre-processor` 并发布至 0.9.1（2026-07-08）。原开发报告对撞名的判断有误（查询时未核对 pypi.org/pypi/opp 归属，当时以为不存在撞名）。残留问题 = OPP README 徽章仍指向 PAY.ON 包（坏徽章）。

---

## 现状锚定（开发基线实测）

| 项 | 现状 | 位置 |
|:---|:-----|:-----|
| OPP | `omni-pre-processor` v0.9.1（✅ 已发布 PyPI）| `pyproject.toml` |
| OL | `omni-localizer` v0.7.1（✅ 已发布，PyPI 显示 0.7.0 略滞后）| `pyproject.toml` |
| ORF | `omni-re-formatter` v0.4.17（✅ 已发布，PyPI 显示 0.4.16 略滞后）| `pyproject.toml` |
| omni-suite | omni-suite v0.4.0（✅ 已发布 PyPI） | pyproject.toml |
| Python 要求 | 三者均 `>=3.13` | `pyproject.toml` |
| 功能 | OPP 提取（12+ 格式/OCR/音视频）/ OL 翻译（8 门控）/ ORF 还原（MD/XLIFF→复杂格式）| README |
| 测试 | e2e-test-suite（OPP→OL→ORF 全链路）| `e2e-test-suite/` |
| 迭代 | 三组件 8-22 后停更（内部稳定）；套件 repo 仍活跃（2026-09-01）| backup repo commits |

---

## 一、现有 feature 补强

### P0-1：四包发布对齐 + 元数据统一
> **依据**：实测 PyPI 显示 OL 0.7.0 / ORF 0.4.16 vs 本地 0.7.1 / 0.4.17（**发布滞后**）；OPP author="OPP Contributors"、ORF author="1StepMore"（**author 不一致**）；OPP README 徽章误指 `opp`（PAY.ON）坏徽章。

**任务**：
0. 修 OPP README 坏徽章（L3-6 指向 pypi.org/project/opp/ → omni-pre-processor）
1. 重新发布 OL 0.7.1、ORF 0.4.17 到 PyPI（对齐本地）
2. 统一三包 author/homepage（全部指向 `1StepMore` + 各自 repo URL）；OPP author `OPP Contributors` → `1StepMore`（email renanzai@foxmail.com）
3. 三包 README 加统一"Omni Suite"banner + 互链（OPP→OL→ORF 流程说明）；omni-suite README 加同款 banner

**验收标准**：
- [ ] `pip install omni-pre-processor omni-localizer omni-re-formatter omni-suite` 安装的都是最新版（与本地一致）
- [ ] PyPI 四包 author 均为 1StepMore 系，homepage 指向正确 repo
- [ ] 四个 README 顶部有 Omni Suite 流程 banner

### P0-2：Python 版本要求评估（>=3.13 是准入门槛）
> **2026-09-04 裁决：不实施**——三包均 requires-python>=3.13，OL ML 特性在 3.13 有已知依赖问题（sentence-transformers import hang），降级评估收益不确定，留待有外部用户信号再议。
> **依据**：实测三包均 `requires-python>=3.13`——这是**较高的准入门槛**（2026 年 3.13 已普及但非默认），限制潜在用户。

**任务**：评估是否降到 `>=3.12` 或 `>=3.11`：
- 检查代码里用到 3.13 特性的地方（`tomllib` 是 3.11+，需 grep 3.13-specific 如 `typing.TypeAliasType` 等）
- 若可降，pyproject 改 `>=3.11` 并重发

**验收标准**：
- [ ] 明确记录：支持哪些 Python 版本（能降则降，不能降则文档说明原因）
- [ ] CI 加多版本矩阵测试（3.11/3.12/3.13）

### P1-1：测试状态公开化（badge）
> **依据**：商业结论——e2e-test-suite 是竞品（Word-Translator/BabelDOC）没有的信任状。
> **前提修正（2026-09-04）**：三组件 repo 各有 CI workflow（OPP ci/publish、OL test/publish/real-llm-nightly、ORF test/release），套件亦有 validation.yml——但均指向 1StepMore origin，主号 suspend 期间无法触发，backup 镜像不跑 Actions。落地形态 = 四 README 徽章位 + 说明 + 本地验证命令，不新增/不改 workflow。

**任务**：
- 四 README 各加测试状态徽章位 + 本地验证命令（suspend 期间不新增/不改 CI workflow）
- README 顶部加测试 badge（"OPP→OL→ORF 全链路测试通过"）
- 本地验证命令可复现执行（见各 repo AGENTS.md）

**验收标准**：
- [ ] 四 README Test status 节存在，列出本地可跑命令
- [ ] README Test status 节如实说明 suspend 下 badge 不实时

### P1-2：格式保真 benchmark（把"格式保真"从口头变数据）
> **依据**：商业结论——格式保真是核心卖点，但无量化证据。

**任务**：新增 `benchmarks/format-fidelity/`：
- 用同一份测试文档（含表格/图片/复杂样式）跑：Omni（OPP→OL→ORF）vs pandoc vs DeepL 文档翻译
- 量化指标：段落保留率 / 图片保留率 / 样式保留率 / 回填完整性
- 输出 `BENCHMARK.md`（放 README 引用）

**验收标准**：
- [ ] 3 种路径的保真率数字可复现（脚本化，非手工）
- [ ] BENCHMARK.md 有对比表 + 复现方法

---

## 二、新 feature 加入

### N1：Omni CLI 统一入口补强（三包一键串联）
> **依据**：三包是独立库，但典型用户要"提取→翻译→还原"一条龙。
> **前提修正（2026-09-04）**：omni-suite pipeline（PyPI 0.4.0）已存在，一条命令 OPP→OL→ORF。本任务改为补强：+--dry-run / --gates-only / --keep-intermediate。

**任务**：基于现有 `omni-suite` CLI 补强：
```
omni pipeline input.docx --src zh --dst en --format xliff
  # = OPP 提取 → OL 翻译 → ORF 还原，一条命令
```
- 补强 `pipeline` 子命令串联（依赖已发布的三包）
- 新增 `--dry-run` / `--gates-only`（只看质量门控不产出）/ `--keep-intermediate`

**验收标准**：
- [ ] 现有命令可跑通 + 新增 3 个 flag 有输出
- [ ] 中间产物（XLIFF/骨架）可访问（`--keep-intermediate`）
- [ ] `--gates-only` 输出 OL 8 门控判定（不产出最终文件）

### N2：格式保真 API 服务（面向 AutoMedia + 未来商业化）
> **2026-09-04 裁决：不实施**——仓库内无 AutoMedia 集成点（grep 仅命中报告自身），验收无锚点。
> **依据**：商业结论——Omni 作为 AutoMedia 的 Triad 是内部价值；未来可能随 AutoMedia open-core 变现。

**任务**：新增 `omni serve`（FastAPI）：
- `POST /pipeline`（multipart: 文件 + 参数）→ 返回翻译后文件 + gate 报告
- `POST /translate/docx`（OL 门控完整流程）
- 认证：简单 API key（未来 open-core 收费点）
- 目的：让 AutoMedia/未来托管版通过 HTTP 调 Omni，而非 subprocess

**验收标准**：
- [ ] `omni serve` 启动，`POST /pipeline` 能接收 DOCX 返回翻译版
- [ ] 响应含 gate 报告（8 门控判定）
- [ ] 与 AutoMedia 的 Omni Triad 集成点可切换为 HTTP 调用

### N3：翻译记忆（TM）基础支持
> **2026-09-04 裁决：不实施**——OL 已有完整 TM 栈（src/ol_tm/service.py TMService：TMX+语义搜索+flush+文件锁；MCP search_tm/tm_add；batch 集成），本节提议的 SQLite 方案与之重复且相悖。
> **依据**：本地化行业标准（Phrase/Lokalise 都有 TM）；行业痛点"重复内容重复翻译"。

**任务**：OL 增加轻量 TM：
- SQLite 存储已翻译句段（source_hash → target）
- 翻译前查 TM（命中直接复用，省 LLM 调用）
- 翻译后回写 TM
- 可开关（`--tm path.db`）

**验收标准**：
- [ ] 同一文档二次翻译：重复句段从 TM 复用（LLM 调用减少可量化）
- [ ] TM 文件可移植（拷贝到别的机器可用）

---

## 三、明确不做（当前阶段）

| 不做 | 原因 | 依据 |
|:-----|:-----|:-----|
| 独立托管平台/SaaS | 无商业化意图信号，停更状态 | 商业结论 |
| 大规模 UI | 开发者工具定位，CLI/MCP 优先 | — |
| 新语言对支持 | OL 走 LLM 路由，语言由模型决定非代码 | — |

---

## 四、开发顺序与周期估算

> **2026-09-04 更正**：P0-0（本报告更正）为前置；P0-2/N1/N2/N3 中 P0-2、N2、N3 已裁决不实施，N1 改为补强现有 CLI。

```
P0-0 本报告更正（2026-09-04 实测更正）─ 前置
P0-1 发布对齐  ──┐
P0-2 Python 评估（不实施）┼── 第 1 周（把 4 个包修成可信开源资产）
                 │
P1-1 测试状态公开─┤
P1-2 保真 bench ┼── 第 2 周（质量证明）
                │
N1 omni CLI 补强─┤
N2 omni serve（不实施）┼── 第 3-4 周（统一入口补强；服务化/TM 已裁决不做）
N3 翻译记忆（不实施）┘
```

**验收里程碑**：第 4 周末，`pip install omni-suite` 后一条 `omni pipeline` 命令完成 DOCX 翻译（含 gate 报告 + 保真数据）；新增能力（--gates-only/--dry-run/--keep-intermediate + benchmark + 徽章位）验收通过。

---

## 2026-09-04 实测更正（验证轮次 2）

本节列出本报告全部更正的旧断言（逐字引用）→ 新陈述 + 证据来源。本报告正文已按下列更正修改；本节为自查引用清单。

| # | 旧断言（逐字）| 新陈述 | 证据来源 |
|:--|:-----|:-----|:-----|
| 1 | L5 `opp` 撞名问题不存在，商业报告该判断作废 | 撞名属实（PyPI `opp` 实为 PAY.ON 支付 SDK）；OPP 已改名 `omni-pre-processor` 并发布至 0.9.1（2026-07-08）。原判断有误（查询时未核对 pypi.org/pypi/opp 归属）。残留问题 = OPP README 徽章仍指向 PAY.ON 包（坏徽章）| PyPI JSON pypi.org/pypi/opp/json（author PAY.ON）+ pypi.org/pypi/omni-pre-processor/json（version 0.9.1, upload_time 2026-07-08）|
| 2 | L13-15 现状表无 suite 行；L19 迭代 `8-22 后停更（内部稳定）` | 现状表新增 `omni-suite 0.4.0（已发布 PyPI）`；OL/ORF 保留 PyPI 滞后注记；迭代改为 `三组件 8-22 后停更（内部稳定）；套件 repo 仍活跃（2026-09-01）` | PyPI JSON omni-suite（0.4.0）+ git log（suite repo 2026-09-01 提交）|
| 3 | P0-1 无徽章任务；task 2 未含 OPP；无 suite banner；验收只查三包 | P0-1 新增任务 0 `修 OPP README 坏徽章`；OPP author 统一为 `1StepMore`（renanzai@foxmail.com）；task 3 加 omni-suite README banner；验收 2/3 含 omni-suite | OPP README L3-6（徽章指 pypi.org/project/opp/）+ PyPI JSON |
| 4 | P1-1 L53 `三 repo 各加 CI（GitHub Actions）跑 e2e-test-suite 对应路径`；L55 `失败自动标记（badge 变红）`；L58 验收 `三 repo CI 配置存在，push 触发跑测试`；L59 `README badge 实时反映测试状态` | 三组件 repo 各有 CI workflow（OPP ci/publish、OL test/publish/real-llm-nightly、ORF test/release），套件亦有 validation.yml——但均指向 1StepMore origin，主号 suspend 期间无法触发。落地形态 = 四 README 徽章位 + 说明 + 本地验证命令，不新增/不改 workflow | 各组件 repo `.github/workflows/`（ci/publish.yml、test.yml、release.yml 等）+ suite `.github/workflows/validation.yml`；git status（CI 无法触发）|
| 5 | N1 L78 `现在要分别调 3 个 CLI` | omni-suite pipeline（PyPI 0.4.0）已存在，一条命令 OPP→OL→ORF；本任务改为补强：+--dry-run / --gates-only / --keep-intermediate；验收改为 `现有命令可跑通 + 新增 3 个 flag 有输出` | PyPI JSON omni-suite（0.4.0）+ omni_suite/cli.py（pipeline 已存在）|
| 6 | P0-2（L38-47）/N2（L93-106）/N3（L108-119）原文案 | 三节均标记 `2026-09-04 裁决：不实施`（原因见正文各节），正文保留原文以存史 | P0-2：三包 requires-python>=3.13 + OL ML 依赖问题；N2：repo 内 grep AutoMedia 无集成点；N3：OL src/ol_tm/service.py 已有 TMService（TMX+语义搜索+flush+文件锁）+ MCP search_tm/tm_add |
| 7 | 顺序图含 P0-2/N1/N2/N3 全量；里程碑 `三包 PyPI 元数据统一、E2E badge 上线` | P0-0（本报告更正）为前置；P0-2、N2、N3 已裁决不实施，N1 改为补强现有 CLI；里程碑改为 `新增能力（--gates-only/--dry-run/--keep-intermediate + benchmark + 徽章位）验收通过` | 本表 #3-#6 |
