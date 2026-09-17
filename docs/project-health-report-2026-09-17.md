# Omni Suite 项目健康度报告

> **审计日期**：2026-09-17
> **审计方式**：实测（命令 + 原始输出 + 文件读取），**不以文档声明为结论依据**
> **审计范围**：顶层 suite + OPP / OL / ORF 三个子仓库（4 个独立 git 仓库）
> **证据约定**：每条结论标注「实测」或「文档声称」；凡实测与声称不一致之处单独列出

---

## 一、总体结论

**综合健康度：74 / 100 — 良好（B）**

工程纪律与验证体系是这个项目**最突出的资产**，明显高于同类项目平均水平；
**仓库卫生**与**存量技术债的制度化搁置**是最大短板。

| 维度 | 得分 | 等级 | 一句话结论 |
|---|---|---|---|
| 测试与验证体系 | **88** | 优秀 | 1362 测试 + 119 场景 + known_gap 反伪绿机制 |
| 安全 | **82** | 良好 | 密钥未泄漏、鉴权/沙箱齐全；扣分在策略实现三份复制 |
| 交付就绪度 | **75** | 良好 | 16 格式 × 195 单元矩阵 0 FAIL；但 2 个质量门禁已知不达标 |
| 文档 | **74** | 良好 | doc-truth 门禁有效；但 PROJECT_STATUS 过期约 2.5 个月 |
| 架构与模块边界 | **72** | 中等 | 三阶段分层清晰；PathValidator 三份复制 + sys.path 注入 |
| CI/CD 与工程规范 | **68** | 中等 | 7 个 workflow 真跑；但门禁范围被大幅收窄 |
| 代码质量与静态检查 | **60** | 中等 | 存量 281 个 ruff 错误被"制度化不修"，含 1 处死代码 |
| 仓库卫生 | **42** | 需改进 | 工作区 ~8 GB 垃圾，`99-Tools/` 6.3 GB 且未被忽略 |

**加权口径**：测试 20%、架构 15%、代码质量 15%、安全 15%、CI 10%、文档 10%、交付 10%、卫生 5%。

---

## 二、规模与版本基线（实测）

### 2.1 代码规模

统计命令（PowerShell，排除 `.venv` / `__pycache__` / 子模块 tests）：

| 模块 | 文件数 | 行数 | 说明 |
|---|---|---|---|
| OPP | 87 | 13,581 | `Omni_Pre_Processor/` |
| OL | 150 | 20,683 | `Omni_Localizer/` |
| ORF | 107 | 18,011 | `Omni_Re_Formatter/` |
| omni_suite | 8 | 1,056 | 编排层 |
| omni_mcp | 13 | 4,438 | suite 级 MCP |
| scripts | 25 | 11,089 | 工具与验证框架 |
| **生产代码小计** | **390** | **68,858** | |
| tests（顶层） | 152 | 40,700 | 不含三个子仓库内的 tests |

**测试/生产代码比 = 0.59**，对流水线型项目属健康区间。

### 2.2 版本与 Git 状态

| 组件 | 版本 | 分支 | 工作区 | 末次提交 |
|---|---|---|---|---|
| Suite | 0.4.0 | main | 仅 `?? 99-Tools/` | `a2c8b6d` 2026-09-15 |
| OPP | 0.9.1 | main | 干净 | `bad3db9` 2026-09-14 |
| OL | 0.7.1 | main | 干净 | `7fb0d55` 2026-09-14 |
| ORF | 0.4.17 | main | 干净 | `8c17abf` 2026-09-14 |

**实测结论**：`VERSION`（`0.4.0`）与根 `pyproject.toml` 版本一致；三个子仓库工作区全干净 → 无"改完未提交"的悬挂状态。

---

## 三、分维度详析

### 3.1 测试与验证体系：88 / 100（最强项）

#### 实测证据

```
$ python -m pytest tests/ --collect-only -q
1362 tests collected, 9 errors in 13.52s
```

9 个 collection error 的根因（实测回溯栈）为 `ModuleNotFoundError: No module named 'prometheus_client'` ——
**属本地环境未 `uv sync`，不是代码缺陷**。该包已在根 `pyproject.toml` 第 7 行声明为运行时依赖。

#### 场景库规模

| 项 | 实测值 |
|---|---|
| scenarios YAML 总数 | **119** |
| tier 1（hermetic，无需 LLM key） | 105 |
| tier 2（需真实 LLM key） | 13 |
| tier 3（付费/外部网络） | 1 |
| red-team 场景 | 4 |

#### 历史运行证据

| Run | 场景数 | 结果分布 |
|---|---|---|
| `20260915-014100`（最新完整） | 105 | passed=90, unconfigured=9, recovered=3, failed=1, partial-pass=1, known-gap=1 |
| `20260914-231641` | 117 | passed=101, failed=2, known-gap=1, partial-pass=1, recovered=3, unconfigured=9 |

`20260915-014100` 非 passed 明细：

| 状态 | 场景 |
|---|---|
| `failed` | `suite-resume-killed-subprocess` |
| `partial-pass` | `orf-md-batch-partial-success` |
| `known-gap` | `md-msg-eml-fallback-known-gap` |
| `recovered` | `orf-md-failure-injection-recovery`、`orf-missing-engine-recovery`、`suite-resume-midstage-failure` |
| `unconfigured` | `opp-ipynb-extract`、`opp-msg-extract`、`opp-ocr-extract`、`orf-md-msg`、`tool-ol-add_tm_entries`、`tool-ol-extract_warnings`、`tool-ol-inspect_config`、`tool-ol-load_glossary`、`tool-ol-search_tm` |

**判读**：唯一 `failed` 是 kill 中断后的恢复语义场景；上一轮有 2 个失败，本轮 1 个 → 属波动而非堆积。
`unconfigured` 全部对应可选依赖缺失（IPYNB / MSG / OCR、OL 的工具类场景），符合声明，未伪绿。

#### 优秀设计（应保持）

`scenarios/STANDARDS.md` 的 **`known_gap` 机制**：达不到的公开阈值**不被悄悄调低**，而是
1. 在通过-bar 场景中断言**字面阈值**并标 `known_gap: true`（该步失败不计入场景 verdict）；
2. 弱化观测隔离在 `scenarios/pipeline/known-gaps/` 下，独立声明 `known_gap: true`，永不 GREEN、永不阻塞。

且 `omni_mcp/validation/cli.py:197-203` 用 contract lint **强制**"`known_gap: true` 只能出现在 `known-gaps/` 目录"。
这是**防伪绿**的正确做法，值得复用到其他项目。

#### 扣分项

- 本地 Windows 完全无法执行任何测试或 lint（见 3.5），验证证据只能靠 CI。
- 9 个 `unconfigured` 长期存在，占 tier 1 的 8.6%，说明可选依赖矩阵未被 CI 覆盖。

---

### 3.2 安全：82 / 100

#### 通过项（实测）

| 检查 | 结果 |
|---|---|
| `.env` 是否被 git 跟踪 | `git ls-files --error-unmatch .env` → `did not match any file(s) known to git` ✓ **未跟踪** |
| `.gitignore` 覆盖 | L10-24 覆盖 `.env` / `.env.local` / `*.env` / `api_key*` ✓ |
| gitleaks 规则 | `.gitleaks.toml` 自定义 `sk-` / `sk-cp-` / `bce-v3/ALTAK-` / `nvapi-` 模式 + allowlist |
| pre-commit 密钥检测器 | L71-90 "hardcoded API key detector"，扫描 3 个子仓库 + config/docs/tests |
| MCP 鉴权 | `MCP_SHARED_SECRET`（`omni_mcp/orchestrator.py:221-289` 先校验 secret 再处理路径） |
| `# type: ignore` | **0 处** |
| `TODO/FIXME/XXX/HACK` | **1 处**（`tests/test_ol_lqa_autoinvoke.py:7`） |
| bare `except:` | 6 处，**全部在审计脚本自身**（`scripts/audit_except_blocks.py:5,91,102,148`、`scripts/check_readiness.py:645,647`），属工具实现需要，可接受 |
| broad `except Exception:` | 18 处（suite 层），且项目有 `tests/test_no_broad_except.py` 静态护栏 |

#### 风险项

**R1（本次审计发现的最重要架构风险）：PathValidator 存在三份独立实现**

| 文件 | 起始行 | 行数 |
|---|---|---|
| `Omni_Pre_Processor/src/opp/mcp/security.py` | 44 | 166 |
| `Omni_Localizer/src/ol_mcp/security.py` | 55 | 288 |
| `Omni_Re_Formatter/src/orf/mcp/security.py` | 45 | 263 |
| （另有）`Omni_Pre_Processor/src/opp/utils/security.py` | — | 200 |

`ol_mcp/security.py` 文件头注释直接承认：*"Mirrors `orf/mcp/security.py:PathValidator`"*。
三者 `ALLOWED_EXTENSIONS` 各不相同 → **安全策略漂移**：修一处漏洞不会传播到另外两处，
且修复者无法察觉另两处仍需同步。

**R2：suite 层绕过子模块 PathValidator**

`omni_mcp/orchestrator.py:7-15` 文档自陈：orchestrator 以 subprocess 调用 OPP/OL/ORF CLI，
**会绕过子模块 MCP 的 `PathValidator`**，因此接受任意 `file_path`，仅靠自身 `_path_denial_message()`
（`orchestrator.py:106`）兜底 → 存在校验口径不一致的窗口。

**R3：依赖侧**：`THIRD_PARTY_LICENSES.md` 记录的 `aspose-email-foss`（GPLv3）为 MSG 输出所必需，
项目已给出 `.eml` 替代方案（开放标准），风险已被显式接受。

---

### 3.3 代码质量与静态检查：60 / 100

#### 实测证据

```
$ python -m ruff check omni_suite omni_mcp scripts tests --statistics   # ruff 0.15.11
Found 281 errors.
[*] 209 fixable with the --fix option (46 hidden fixes can be enabled with --unsafe-fixes)

$ python -m ruff check . --statistics                                    # 全量含子模块
Found 584 errors.

子模块 F-class 单独统计：OPP 22（F401=18 / F841=3 / F541=1）、OL 6（F841=6）、ORF 0
```

suite 层 281 个错误的完整分布：

| 规则 | 数量 | 规则 | 数量 |
|---|---|---|---|
| I001 unsorted-imports | 104 | UP037 quoted-annotation | 5 |
| F841 unused-variable | 43 | E401 multiple-imports-on-one-line | 4 |
| F541 f-string-missing-placeholders | 42 | E701 multiple-statements-on-one-line-colon | 4 |
| F401 unused-import | 31 | N811 constant-imported-as-non-constant | 4 |
| UP045 non-pep604-annotation-optional | 14 | UP015 redundant-open-modes | 4 |
| B007 unused-loop-control-variable | 5 | UP024 / UP035 / E741 / F821 | 各 3 / 3 / 2 / 2 |
| E702 multiple-statements-on-one-line-semicolon | 5 | 其余（B023/E402/F811/N806/UP032/UP042） | 各 1 |

#### 真实缺陷（非风格问题）

**`scripts/omo_loop.py:397-400` —— 不可达死代码 + 未定义变量**

```python
    return GateResult(...)   # L393-396 已返回
    return GateResult(       # L397-400 永远不会执行
        "Q2_lqa", False, 0.0,
        f"avg LQA {avg_5:.2f}/5 (< {threshold}); n={len(scores)}, ..."
    )                        # threshold / scores 均未定义 —— 即 ruff 报的 2 个 F821
```

因前文已 `return`，**不会崩溃**，但属明显的复制粘贴残留，且是静态检查噪声源。

#### 根本原因：存量债被制度化搁置

`.github/workflows/lint.yml:129-150` 明文记录：

> whole-tree 有 **116 个 F-class 预存错误**（F541×42, F841×40, F401×32, F821×2）……
> **"plan guardrail" 禁止修复**，门禁只跑 **changed files**。

后果：**存量债永远不被清理，只保证不新增**。且该基线数字已腐化 ——
实测当前 F-class 为 **146 个**（suite 层 118 + 子模块 28），远超记录的 116。

#### 规范配置本身合理（非宽松）

`pyproject.toml:56-69`：`select = [E, F, I, B, UP, N]`，`ignore` 仅 3 条（`E501` / `B008` / `B904`），
判据明确。mypy 开启 `warn_unused_ignores` / `warn_redundant_casts` / `no_implicit_optional` / `check_untyped_defs`。

**但** `extend-exclude` 排除了三个模块的 `extractors` / `ol_buses` / `converters`
（`pyproject.toml:44-54`）—— 恰恰是最核心的格式转换代码不在检查范围内。
**→ 已于第十轮处理，并更正了本行的因果判断，见 §18**

#### 文件规模热点

| 行数 | 文件 |
|---|---|
| 1789 | `tests/test_mcp_smoke.py` |
| 1530 | `tests/test_cross_format_e2e.py` |
| 1481 | `tests/test_e2e_real_llm.py` |
| 1299 | `scripts/omo_loop.py` |
| 1082 | `tests/conftest.py` |
| 1072 | `scripts/doc_inventory.py` |
| 967 | `tests/test_e2e_orf_all_formats.py` |
| 883 | `omni_mcp/validation/dispatch.py` |

---

### 3.4 架构与模块边界：72 / 100

#### 优点

- 三阶段 OPP → OL → ORF 职责清晰，各自具备 CLI + MCP + tests 三层。
- `[tool.uv.workspace]` 统一管理三个子仓库；`[tool.uv.sources]` 用 path source 关联。
- `CONTRACT.md` 定义 OPP→OL→ORF 交接契约；`CONTEXT.md` 提供统一术语表。
- 子仓库已从 git submodule 降级为普通目录（2026-06-24），规避了 submodule 的常见陷阱。

#### 风险：sys.path 注入使子模块内部布局成为事实公共 API

```python
# omni_mcp/validation/dispatch.py:64-109
_COMPONENT_SRC_DIRS = ...
sys.path.insert(...)   # 直接把三个子仓库的 src 塞进 sys.path
```

`omni_mcp/validation/dispatch.py:64-109` 与 `scripts/validation/coverage_audit.py:97-143`
均采用此方式导入子模块真实工具注册表。这意味着**子仓库的内部模块布局被外部依赖**，
子仓库重构会静默打断 suite 层。

#### 代码重复

除 3.2 的 PathValidator 三份实现外，`scripts/mcp_bridge.py`（为规避 FastMCP 3.4.2 stdio bug）
也是一层额外的 CLI 包装，与各模块原生 MCP server 存在职责重叠。
**→ 已于第十一轮更正：该文件在报告成文前三个月就已删除，本句是过期结论，见 §19.1**

---

### 3.5 CI/CD 与工程规范：68 / 100

#### 7 个 workflow 均为真实执行（非空壳）

| Workflow | 体积 | 关键执行内容 |
|---|---|---|
| `validation.yml` | 10,527 B | `run_validation.py --tier 1` + `coverage_audit.py` + `pytest tests/contract tests/validation` |
| `e2e-tests.yml` | 8,911 B | `verify_usability.py` + `verify_mcp.py` + nightly LLM job |
| `lint.yml` | 9,087 B | pre-commit（changed files）+ ruff F-class + mypy |
| `contract-tests.yml` | 6,009 B | 契约文档 / CLI help / MCP schemas 三组契约测试 |
| `hardening-tests.yml` | 3,265 B | 加固回归 |
| `fidelity.yml` | 3,094 B | `tests/fidelity/run_fidelity.py`（sacrebleu） |
| `doctor.yml` | 1,340 B | `make doctor` 7 项健康检查 |

全部使用 `uv sync --locked`（锁文件守卫），并在 2026-09-14 完成 setup-uv pin —— 供应链意识良好。

#### 实测收窄项

| # | 问题 | 证据 |
|---|---|---|
| 1 | **mypy 门禁近乎空转** | `lint.yml:152-163` 仅执行 `python -m mypy omni_metrics`；注释自陈 `mypy .` 超时（exit 124），`mypy scripts` 有 16 错、`mypy omni_suite omni_metrics omni_mcp` 有 5 错，故缩到最小范围 |
| 2 | **doctor 不阻塞** | `doctor.yml:25` `continue-on-error: true`（**→ 已于第七轮转为阻塞，见 §15.4**；修复过程中还发现 `make doctor` 在本机静默 exit 49，见 §15.1） |
| 3 | **ruff 版本漂移** | CI 固定 `ruff==0.6.0`，本地实测 `0.15.11` → 规则集不同，**本地干净 ≠ CI 干净** |
| 4 | **门禁仅覆盖 changed files** | 存量 281 错永不暴露；见 3.3 |

#### 本地开发体验严重受损（重要）

实测：工作区 `.venv` 与 `.venv_ol` 的内容结构为 `bin/ lib/ lib64/ share/ pyvenv.cfg`
—— 这是 **Linux（WSL）创建的 venv**，Windows 下两者均 `Test-Path` 失败，**完全不可用**。

直接后果 —— 实测 `python scripts/doc_inventory.py --check`：

```
doc_inventory --check
SOURCE: OPP=9 OL=21 ORF=7 total=37
  scenarios/: 119 yaml files; tiers={'1': 105, '2': 13, '3': 1}
  ...
check FAILED (1 issue(s)):
  - scripts/sync_version_docs.py --check failed (rc=9009)
```

根因在 `scripts/doc_inventory.py:665` 硬编码 `["python3", str(sync), "--check"]` ——
Windows 无 `python3` 命令（`rc=9009` 即 Windows "命令未找到"）。
同一问题使 `.pre-commit-config.yaml:105-111` 的 doc-truth 门禁**在本地 Windows 上完全无法运行**，
只有 CI（Linux）能跑。

同类问题：`scripts/validation/coverage_audit.py` 在 `prometheus_client` 缺失时直接抛栈退出，
无友好降级提示。

**定性**：CI 是 Linux-only（`bash scripts/*.sh`、`.venv_ol/bin/python`、`/tmp` 路径），
本地 Windows 开发者无法复现任何门禁 → **反馈环路断裂**。

---

### 3.6 文档：74 / 100

#### 通过项（实测）

`doc_inventory --check` 的 source-truth 交叉验证输出与文档声明**完全一致**：

| 交叉验证项 | source-truth 输出 | 文档声明 | 一致性 |
|---|---|---|---|
| MCP 工具数 | `OPP=9 OL=21 ORF=7 total=37` | `AGENTS.md:34-43` 同 | ✓ |
| 场景文件数 | `119 yaml files` | `AGENTS.md` 同 | ✓ |
| 版本号 | `VERSION` = `0.4.0` | `pyproject.toml` = `0.4.0` | ✓ |
| Stray `test_bug_*` in tests/ | `none -> ok` | — | ✓ |

文档体系层次分明：`AGENTS.md`(17KB) + `docs/ARCHITECTURE.md`(25KB) + `docs/API_STABILITY.md`(16KB)
+ `docs/DECISIONS.md`(ADR) + `CONTEXT.md`(术语表) + `docs/SECURITY.md`(12KB) + `docs/ERROR_CODES.md`(7KB)。

#### 腐化项

`PROJECT_STATUS.md` 头部自称 *"First file to read in any new agent conversation"*，但：

| 字段 | 文档值 | 实测值 |
|---|---|---|
| "Current versions" 日期 | 2026-06-29 | 实际提交至 2026-09-15 |
| "Last verified clean" | 2026-06-29 | — |
| 测试矩阵 | "131 PASS, 64 SKIP, 0 FAIL"（195 cells） | 未复测，数字时效不明 |

**过期约 2.5 个月**。新 agent 读此文件会拿到错误的仓库基线（版本、测试状态、工作区干净度）。

---

### 3.7 仓库卫生：42 / 100（最弱项）

#### 实测

| 路径 | 体积 | git 跟踪文件数 | 是否被 ignore |
|---|---|---|---|
| `99-Tools/` | **6,366 MB** | 0 | ~~未忽略~~ → **已修复**：`.gitignore:85` 已忽略 ✓（`git check-ignore -v "99-Tools/x.txt"` → `.gitignore:85:99-Tools/`） |
| `test_artifacts/` | **1,559 MB** | **1**（有意 force-add，见下） | 已忽略（`.gitignore:79`）✓ |
| `.backup-bundles/` | 125 MB | 0 | 已忽略 ✓ |
| `.codegraph/` | 12.7 MB | 0 | 已忽略 ✓ |
| `validation-runs/` | 17.1 MB | 2 | — |
| `resources/` | 3.1 MB | 0 | — |
| `benchmarks/` | 2.6 MB | 5 | — |
| `.omo/` | 2.4 MB | 19 | — |
| `logs/` | 2.1 MB | 0 | 已忽略 ✓ |
| `dist/` | 2 MB | 0 | — |
| `reports/` | 0.2 MB | 4 | — |
| `eval/` | ~0 | 68 | — |

**工作区合计约 8 GB 非源码数据。**

**最危险的一条**：`99-Tools/` **未被任何 ignore 规则覆盖** ——
`git status --short` 直接输出 `?? 99-Tools/`，一次 `git add .` 即可把 6.3 GB 送进仓库。

**已复核为非缺陷**：`test_artifacts/` 中那个被跟踪的文件（`test_artifacts/ol/alice_ch1_zhipu_real.md`，10KB）
是 **2026-06-23 有意 force-add** 的（commit `a1be051`："fix(fidelity): force-add candidate translation
(was .gitignore'd by test_artifacts/)"）—— 它是 fidelity 检查的候选译文基准，**不是误加**。
`.gitignore:79` 的 `test_artifacts/` 规则对已跟踪文件无效，故该文件不受影响，行为正确。

#### 根目录散落样本文件（已被跟踪）

```
Meridian_Q1_Update_E2E.pptx
Meridian_Robotics_Product_Overview_E2E.docx
爱上海尔_第二章_全球创牌 - E2E测试专用.docx
（slim）爱上海尔.docx
```

这些 E2E 测试样本直接躺在仓库根目录，而非 `scenarios/_fixtures/` 或 `test_fixtures/`。

> **已修复（2026-09-17，第五轮）**：四个样本全部迁出根目录 —— 两个 Meridian 文件与
> `scenarios/_fixtures/` 内的副本字节相同，故直接去重；海尔 DOCX 成为
> `scenarios/_fixtures/haier_ch2_zh.docx`；`（slim）` 样本移入 `test_fixtures/zh/`。
> 注意 `test_fixtures/` 被 `.gitignore:109` 整目录忽略（`git ls-files test_fixtures`
> 为空），**不能**承载被跟踪的 fixture。详见 §十三。

---

### 3.8 交付就绪度：75 / 100

#### 通过项（文档声称，未全量复测）

- ORF `apply-md` 支持 **16 种输出格式**：DOCX / ODT / EPUB / HTML / RTF / PDF / PPTX / ICML / SRT / CSV / XLSX / XML / IPYNB / EML / MSG / JSON。
- 格式矩阵 **195 单元（MD 路径 165 + XLIFF 路径 30）**：文档声称 131 PASS / 64 SKIP / **0 FAIL**。
  SKIP 均为有意为之（MD→JSON 需代码块、MD→SRT 需时间戳、缺少 md2pptx CLI 等）。
- 跨格式生产就绪矩阵 36 条路径已验证。

#### 已知的产品级缺口（`ACCEPTED_GAPS.md`，已显式声明，未伪绿）

| 编号 | 缺口 | 性质 |
|---|---|---|
| **T13-01** | `#lqa-threshold` 公开标准（judge_overall ≥ 4.0/5）**数学上不可达** | OL 的 judge prompt 未询问 `terminology_consistency` / `format_preservation`，而 `RUBRIC_WEIGHTS` 给这两项合计 0.35 权重 → 满分也只能得 **3.25/5** |
| **T13-02** | `#drawing-count` 公开标准（`src == out`）不达标 | `ol translate-md` 会**重复插入每个图片引用**（level4_safe_fallback 占位符重插；实测 2 进 → 4 出，12 进 → 24 出） |

**判读**：这两项是**真实的产品缺陷**，不是文档问题。项目的处理方式是
"断言字面阈值 + 标记 known_gap + 弱化观测隔离"，属**诚实的失败呈现**，
但缺陷本身仍未修复。

---

## 四、实测与文档声称不一致清单

| # | 文档声称 | 实测结果 | 定性 |
|---|---|---|---|
| 1 | `PROJECT_STATUS.md`：版本/状态基准 2026-06-29 | 实际提交至 2026-09-15 | 文档过期 2.5 月 → **已刷新（第十节 10.1）** |
| 2 | `lint.yml`：whole-tree baseline 116 个 F-class | 实测 146 个（suite 118 + 子模块 28） | 基线数字腐化 → **已校正**；且第二轮校正为 123 的读数本身又已腐化，本轮实测 **107** 并改为「快照 + 复现命令」（第十一节 11.1） |
| 3 | CI ruff pin `0.6.0` | 本地实测 `0.15.11` | 版本漂移 → **已统一到 0.15.11（第十节 10.1）** |
| 4 | doc-truth 门禁 `doc_inventory.py --check` 应通过 | Windows 下 `rc=9009` 失败（硬编码 `python3`） | 跨平台缺陷 → **已修（`sys.executable`）** |
| 5 | `.venv_ol` 应可用（多处文档引用 `.venv_ol/bin/python`） | Windows 下为 Linux 格式 venv，不可用 | 开发环境断裂 → **已补 `setup_dev.ps1` + README 入口（第十节 10.1）** |

---

## 五、必须处理的风险（按优先级）

| # | 风险 | 影响 | 建议动作 | 成本 |
|---|---|---|---|---|
| 1 | ~~`99-Tools/` 6.3 GB 未被 ignore~~ → **已修复（2026-09-17）** | 一次误 `git add .` 污染仓库 | `.gitignore:85` 新增 `99-Tools/`；`git check-ignore -v "99-Tools/x.txt"` 命中（`→ .gitignore:85:99-Tools/`），`git status` 不再显示 | 极低 |
| 2 | PathValidator 三份复制实现 → **Phase 1 已落地（2026-09-17）**，Phase 2 已批准推迟 | 安全修复不传播 → 策略漂移漏洞 | Phase 1（对齐 `SYSTEM_DIRS`/`BLOCKED_EXTENSIONS` + 修 legacy `validate()` env 失效 + 30 用例 parity 门禁接 pre-commit/CI）已完成；Phase 2（抽 `omni_security`，三处改薄封装）被 `uv.lock` 无法重生成阻塞（索引 403）→ [ADR 0007](file:///d:/贯维/Omni_Suite/docs/adr/0007-path-security-convergence.md)，见第十一节 | 中高（跨 3 子仓库） |
| 3 | ~~`scripts/omo_loop.py:397-400` 死代码 + F821×2~~ → **已修复** | 静态噪声 / 潜在复制源 | 已删除不可达块（内含未定义 `threshold` / `scores`，即那 2 个 F821） | 极低 |
| 4 | ~~`doc_inventory.py:665` 硬编码 `python3`~~ → **已修复** | Windows 本地门禁不可用 | 已改用 `sys.executable`；`python scripts/doc_inventory.py --check` → `check passed`，EXIT=0 | 极低 |
| 5 | 本地 venv 为 Linux 格式 → **已修复（2026-09-17）** | Windows 无法跑任何测试/lint | 新增 [setup_dev.ps1](file:///d:/贯维/Omni_Suite/scripts/setup_dev.ps1)（原生 Windows 引导，`.venv_win/` 独立 venv，不破坏 CI/WSL 依赖的 `.venv_ol`）+ `setup_dev.sh` 的 MINGW 分流 + README 原生 Windows 入口说明；本轮又修掉脚本自身两处缺陷 | 低 |
| 6 | ~~CI ruff 0.6.0 vs 本地 0.15.11~~ → **已修复（2026-09-17）** | 本地绿 ≠ CI 绿 | pre-commit rev 与 CI pin 统一到 `ruff==0.15.11`；`mypy` 同样统一到 `2.3.1`；第三处 pin（`pyproject` dev extras）已回退并写明理由（会打挂 `uv.lock`） | 低 |
| 7 | ~~`PROJECT_STATUS.md` 过期 2.5 月~~ → **已修复（2026-09-17）** | 新 agent 拿错基线 | 日期刷新至 2026-09-17，指针表 14 处行数/体积按实测替换，并诚实记录「suite git status 不干净」 | 低 |
| 8 | T13-01 / T13-02 质量门禁不达标 → **代码已修复（2026-09-17）**，待 tier-2 复验 | 产品级质量指标未达成 | 已修 judge 权重归一化 + judge prompt 维度 + 图片引用重复插入（详见第九节） | 中 |
| 9 | ~~`test_artifacts/` 部分被跟踪~~ → **已复核：非缺陷** | 该文件是 2026-06-23 有意 force-add 的 fidelity 基准（`a1be051`），`.gitignore:79` 行为正确 | 无需动作 | — |
| 10 | ~~mypy 仅查 `omni_metrics`~~ → **已修复（2026-09-17）** | 类型检查形同虚设 | 范围放宽到 `mypy omni_metrics omni_suite omni_mcp`（2 → **23 文件**，全绿）；14 个存量错误逐个真修，`# type: ignore` 全仓仍为 0 | 中 |

---

## 六、亮点（应保持）

1. **反伪绿验证架构** —— `known_gap` 隔离 + `unconfigured` distinct status + `invalid`（FAKE_LLM 不可作质量证据），
   这套机制在本次审计中**行为与声明一致**，是本项目最值得复用到其他项目的资产。
2. **密钥卫生** —— `.env` 确实未被跟踪，且 gitleaks + 自定义检测器 + pre-commit 三层防守。
3. **日常纪律** —— `# type: ignore` 为 0、`TODO` 仅 1 处、三个子仓库工作区全干净。
4. **文档即门禁** —— 37 个 MCP 工具数、119 个场景数可被自动交叉验证，且实测通过，非纸面声明。
5. **契约测试分层** —— `tests/contract/` 独立覆盖文档契约 / CLI help / MCP schema 三组。
6. **供应链守卫** —— 全 CI 使用 `uv sync --locked`，2026-09-14 完成 setup-uv pin + lock 新鲜度断言。

---

## 七、审计方法与复现命令

本报告所有结论均可复现。执行环境：Windows，Python 3.13.5，ruff 0.15.11。

```bash
# 代码规模
for m in Omni_Pre_Processor Omni_Localizer Omni_Re_Formatter omni_suite omni_mcp scripts tests; do
  # 统计 .py 文件数与总行数（排除 .venv/__pycache__/build/dist）
done

# 静态检查
python -m ruff check omni_suite omni_mcp scripts tests --statistics
python -m ruff check . --statistics
python -m ruff check <module>/src --select F --statistics

# 测试收集
python -m pytest tests/ --collect-only -q

# 文档门禁
python scripts/doc_inventory.py --check

# 覆盖率审计
python scripts/validation/coverage_audit.py

# Git 状态（4 个独立仓库）
git status --short && git log -3 --format="%h %ad %s" --date=short
git -C Omni_Pre_Processor status --short
git -C Omni_Localizer status --short
git -C Omni_Re_Formatter status --short
git ls-files --error-unmatch .env     # 验证 .env 未被跟踪

# 仓库卫生
git ls-files 99-Tools | Measure-Object    # 0
git check-ignore -v 99-Tools test_artifacts
```

---

## 八、未覆盖的审计面

以下维度本次**未做实测**，如需完整评估可另行补充：

| 维度 | 原因 |
|---|---|
| 运行时性能基准 | `benchmarks/` 未执行（需完整环境） |
| 依赖 CVE 扫描 | 未联网核查 `litellm` / `mcp` / `pymupdf` 等版本已知漏洞 |
| Licensing 合规细节 | 仅读 `THIRD_PARTY_LICENSES.md` 摘要，未逐包核对许可证 |
| 195 单元格式矩阵复测 | 需 Linux 环境 + 完整依赖；本次仅引用文档声称并标注 |
| 真实 LLM 质量基线 | tier 2/3 场景需真实 API key，本次未运行 |

---

## 九、本轮优化落地（2026-09-17）

依据本报告第五节风险表，本轮修完 **#1 / #3 / #4 / #8** 四项（其中 #8 为唯一的"产品级"缺陷），
#9 经复核为非缺陷。**未启动** #2 / #5 / #6 / #7 / #10（原因见 9.4）。

### 9.1 已落地改动

| 项 | 改动的文件 | 机制 |
|---|---|---|
| #1 仓库卫生 | [.gitignore](file:///d:/贯维/Omni_Suite/.gitignore#L85) | 新增 `99-Tools/` 忽略规则，6.3 GB 中间件不再进入 `git status`（第二轮又追加 4 行 venv 规则，行号由 82 漂移到 85） |
| #4 Windows 门禁 | [doc_inventory.py](file:///d:/贯维/Omni_Suite/scripts/doc_inventory.py#L665) | 子进程解释器由硬编码 `python3` 改为 `sys.executable` |
| #3 死代码 | [omo_loop.py](file:///d:/贯维/Omni_Suite/scripts/omo_loop.py) | 删除 L397-400 不可达块（即 F821×2 的来源） |
| #8-a judge 权重 | [judge.py](file:///d:/贯维/Omni_Suite/Omni_Localizer/src/ol_lqa/judge.py#L16-L48) | `_remap_llm_fields` 改为**省略**缺席字段而非补 0；`EnsembleJudge.judge` 聚合跳过全体缺席的 criterion |
| #8-b judge prompt | [router.py](file:///d:/贯维/Omni_Suite/Omni_Localizer/src/ol_pool/router.py#L805-L816) | judge prompt 补齐 `terminology_consistency` / `format_preservation` 两维，百分比重排与 `RUBRIC_WEIGHTS` 一致 |
| #8-c 图片重复 | [pipeline.py](file:///d:/贯维/Omni_Suite/Omni_Localizer/src/ol_md/pipeline.py#L16-L82) | `is_complete()` / `repair()` 的 `missing` 判据由"查 shield_map 键名"改为"键名或原值命中" |

**#8 根因说明**

- **T13-01（LQA 封顶 3.25/5）**：`judge_overall_score` 做的是 `weighted_sum / total_weight` 归一化，
  但 `_remap_llm_fields` 把 LLM 未返回的维度补 0 —— 权重进分母、分子不贡献，
  总分被硬性封顶在 `0.65 × 10 = 6.5/10`（即 3.25/5）。叠加 judge prompt 原本只问
  `accuracy / fluency / adequacy / score`，两个维度必然缺席。两处同修后，
  单元测试 `test_partial_scores_renormalize_to_full_range` 由修复前的 5.85 变为 **9.0**。
- **T13-02（图片引用 2 进 4 出）**：MD 通道调用顺序为 `unshield_markdown()` → `repair()`，
  正文中恢复的是 shield_map 的**原值**（如 `![Image 1](a.png)`），而旧实现只查**键名**
  （`image_0000`）⇒ 永远判定"不完整" ⇒ 一路升级到 Level 4 `level4_safe_fallback`
  把每个受保护内容**再追加一遍**。现改为"键名或原值任一命中即视为已恢复"。

### 9.2 验证证据（本轮实测）

```
# 回归测试（新增 12 个用例，全部通过）
$ python -m pytest Omni_Localizer/tests/test_md_repair_pipeline.py Omni_Localizer/tests/test_lqa_judge.py -q
69 passed

# 全量 OL 测试（设置 MCP_ALLOWED_DIRECTORIES 后）
$ python -m pytest Omni_Localizer/tests -q -m "not real_llm_required"
1482 passed, 22 failed, 14 skipped, 6 deselected, 1 xfailed, 1 xpassed
# 22 个 failed 全部为 Windows/环境专有（WinError 1314 符号链接特权、WinError 32 日志占用、
# 缺 sacrebleu、缺 ARK_API_KEY、缺 config\default.yaml 等），与本轮改动文件无关

# 静态检查（5 个改动文件）
$ python -m ruff check Omni_Localizer/src/ol_lqa/judge.py Omni_Localizer/src/ol_pool/router.py \
    Omni_Localizer/src/ol_md/pipeline.py Omni_Localizer/tests/test_md_repair_pipeline.py \
    Omni_Localizer/tests/test_lqa_judge.py
All checks passed!

# 文档门禁
$ python scripts/doc_inventory.py --check
check passed        # EXIT=0

# 场景契约 lint
$ PYTHONPATH=. python scripts/validation/run_validation.py --check
Contract check: clean   # EXIT=0
```

### 9.3 known_gap 标记的处理（**保留**）

`ACCEPTED_GAPS.md`、`scenarios/pipeline/pipeline-*.yaml` 的步骤级 `known_gap: true`
与 `scenarios/pipeline/known-gaps/` 下的弱化观测**全部保留**，仅把叙事从"cannot meet"
改为"could not meet (fixed in code 2026-09-17, pending tier-2 re-verification)"。

理由：两条 bar 是**字面阈值**（`src == out`、`judge_overall >= 4.0`），
要证明它们被真正满足，必须有真实 LLM key 的 tier-2 运行。
本环境无法执行 tier-2，**仅凭单元/封闭证据解除标记即构成 false green**，
违反 [STANDARDS.md](file:///d:/贯维/Omni_Suite/scenarios/STANDARDS.md) 的反伪绿原则。

### 9.4 未启动项及原因

> **第二轮更新（同日）**：下表是**第一轮结束时刻**的记录。第二轮已启动其中的
> #5 / #6 / #7 / #10 四项并全部落地，仅 #2 仍停留在「计划已出、未实施」——
> 见[第十节](#十第二轮优化落地2026-09-17同日续做)。

| 项 | 未启动原因 |
|---|---|
| #2 抽 PathValidator 共享包 | 跨 3 个子仓库的公共 API 变更，需先定 ADR；非本轮范围 |
| #5 补 `setup_dev.ps1` | 属新增开发体验能力，需独立设计（WSL 明示 vs 原生 Windows 支持二选一） |
| #6 统一 ruff 版本 | 涉及 CI pin 与 pre-commit rev 联动，需确认 CI 绿基线后再改 |
| #7 刷新 `PROJECT_STATUS.md` | 依赖 #6/#10 的结论，宜在一次集中收尾中一并刷新 |
| #10 mypy 扩展范围 | 需先清 5 个既有类型错误，属独立工作量 |

---

## 十、第二轮优化落地（2026-09-17，同日续做）

第一轮（第九节）修完 #1/#3/#4/#8 并明确「未启动」#2/#5/#6/#7/#10。第二轮把这四项中的
**#5 / #6 / #7 / #10 全部落地**，并为 #2 产出 ADR 级计划（第十节 10.3）。

### 10.1 已落地改动

| 项 | 改动的文件 | 机制 |
|---|---|---|
| #7 状态基线刷新 | [PROJECT_STATUS.md](file:///d:/贯维/Omni_Suite/PROJECT_STATUS.md) | 日期 2026-06-29→2026-09-17；修 `Omni_Re_Reformatter` 笔误；`/mnt/d/…` 单路径改为 WSL/Windows 双写；新增「Platform notes」（.venv_ol 是 Linux venv、不可重建）；「Recent fixes」表补 2026-09-13~09-17 六条；指针表 14 处行数/体积由实测值替换；matrix 数字明确标注为「最后一次实跑快照」而非当日新证据 |
| #7 连带修正 | [SKILL.md](file:///d:/贯维/Omni_Suite/.opencode/skills/omni-docmap/SKILL.md#L37) | `PROJECT_STATUS.md` 行数声称 `~126` → `~189`（doc-inventory 的行数门禁 ±15% 带，超带即 FAIL） |
| #10 mypy 真门禁 | [lint.yml](file:///d:/贯维/Omni_Suite/.github/workflows/lint.yml#L157-L160) | 范围由 `mypy omni_metrics`（2 文件，形同虚设）放宽到 `mypy omni_metrics omni_suite omni_mcp`（**23 文件，全绿**）；14 个存量错误逐个真修，未新增任何 `# type: ignore`（全仓仍为 0） |
| #10 修错清单 | `omni_suite/cli.py`、`omni_suite/contract/validator.py`、`omni_mcp/orchestrator.py`、`omni_mcp/validation/{dispatch,engine,cli}.py` | dict 值类型收窄；`dict` 当作 `TranslationSegment` 传入；未收窄的 `errors` 列表；循环变量跨类型复用；`os.environ` 实为 `Mapping` 而非 `dict`；`list[str]` 不变性 vs `Sequence[str \| Path]`；`str \| None` 传给 `Path` |
| #6 ruff 版本统一 | [.pre-commit-config.yaml](file:///d:/贯维/Omni_Suite/.pre-commit-config.yaml#L45-L50) + [lint.yml](file:///d:/贯维/Omni_Suite/.github/workflows/lint.yml#L97-L98) | pre-commit rev `v0.6.0`→`v0.15.11`；CI 安装步由 `pip install pre-commit` 改为 `pip install pre-commit ruff==0.15.11 mypy==2.3.1`；两处注释的 F 类基线由旧记录 x116 校正为实测 **123**（F841×43 / F541×42 / F401×36 / F811×1 + 1 invalid-syntax） |
| #6 不可行的一环（已回退） | `pyproject.toml` | 曾尝试把 `ruff==0.15.11` / `mypy==2.3.1` 写进 `[project.optional-dependencies].dev`，使「一处定义、处处一致」。**回退**：任何依赖声明变更都会使 `uv.lock` 失效，而本环境无法重新锁（见 10.3）；留下过期 lock 会直接打挂所有 `uv sync --locked` 作业。改为在 lint.yml 就地写明「pin 只在此处与 pre-commit config」 |
| #5 Windows 开发入口 | [setup_dev.ps1](file:///d:/贯维/Omni_Suite/scripts/setup_dev.ps1)（新增） | 原生 Windows 引导：校验 Python≥3.13 → 建/复用**独立** `.venv_win` → editable 装 3 子仓库 → 版本校验 → `.env` → pandoc 校验 → C-3 冒烟。7 步、中文注释、UTF-8 **with BOM**（PowerShell 5.1 读无 BOM 文件按 GBK 解码会解析失败） |
| #5 入口分流 | [setup_dev.sh](file:///d:/贯维/Omni_Suite/scripts/setup_dev.sh#L96-L101) | 检测到 `MINGW*/MSYS*/CYGWIN*` 时不再尝试复用 Linux venv，改为指向 `setup_dev.ps1` 并给出可直接复制的一行命令 |
| #5 同族缺陷 | [.gitignore](file:///d:/贯维/Omni_Suite/.gitignore#L52-L58) | 显式注明 `.venv/`/`.venv_ol/` 是 Linux（uv）venv、勿动；新增 `.venv_win/` 忽略 |
| 缺陷族修复（预存 bug） | [setup_dev.sh](file:///d:/贯维/Omni_Suite/scripts/setup_dev.sh#L204-L215) + `setup_dev.ps1` | 两处版本校验原先取 `COMPATIBILITY.md` 的**第一行**匹配 → 永远命中历史版本 `0.2.0`，与 0.7.1/0.9.1/0.4.17 必然误报不一致。改为按 `VERSION` 取**最后一行**匹配 |
| 缺陷族修复（预存 bug） | [test_pipeline_contract_smoke.py](file:///d:/贯维/Omni_Suite/tests/test_pipeline_contract_smoke.py#L20-L78) | C-3 冒烟硬编码 `.venv_ol/bin/python`（Linux ELF）。改为平台感知探测 + 真实 `import opp, ol, orf` 准入探测；并把解释器执行固定 `cwd=_SUITE_ROOT`，使断言不依赖调用者目录 |

**为什么 `.venv_win` 而不是重建 `.venv_ol`**：`.venv/` 与 `.venv_ol/` 的 `pyvenv.cfg`
指向 Linux CPython，CI 用 `mkdir -p .venv_ol/bin && ln -sf $(which python) .venv_ol/bin/python`
构造、WSL 工作流也依赖它们。删除/重建会同时打挂 CI 与 WSL，因此 Windows 侧必须是**新增**
独立 venv。

### 10.2 验证证据（本轮实测，可复现）

```
# 文档真值门禁（PROJECT_STATUS + SKILL 行数声称 + 引用完整性 + 清单新鲜度）
$ python scripts/doc_inventory.py --check
check passed: source truth matches claims, no stray files, inventory fresh.
EXIT=0
$ python scripts/doc_inventory.py
Wrote D:\贯维\Omni_Suite\docs\dev\doc-inventory.md (46 files, 25118 lines).

# mypy 新门禁（CI 同款命令）
$ python -m mypy omni_metrics omni_suite omni_mcp
Success: no issues found in 23 source files
EXIT=0

# 场景契约 lint
$ PYTHONPATH=. python scripts/validation/run_validation.py --check
Contract check: clean — every step falsifiable, no self-echo PASS/FAIL,
standard citations resolve to STANDARDS.md anchors, known-gap scenarios
isolated under known-gaps/, every scenario declares an approved user level
EXIT=0

# C-3 契约冒烟（Windows 原生）
$ python -m pytest tests/test_pipeline_contract_smoke.py -q --no-header
1 failed, 8 passed in 25.48s
#   唯一失败 = 系统解释器缺 ORF 声明依赖 markdown（环境未装完，非契约破损）
#   修复前基线为 5 failed / 4 passed（全部 WinError 1920）

# setup_dev.sh 语法（WSL）
$ wsl bash -n scripts/setup_dev.sh
EXIT=0

# ruff 三方对齐后的实测版本
$ python -m ruff --version   -> ruff 0.15.11
$ python -m mypy --version   -> mypy 2.3.1 (compiled: yes)
```

### 10.3 #2 PathValidator：计划已出，实施被环境阻塞

按「复杂任务先 plan 后 implement」，本轮先完成**计划**（未改任何校验代码）：
[ADR 0007](file:///d:/贯维/Omni_Suite/docs/adr/0007-path-security-convergence.md)。

审计修正了第一轮的一处事实错误：**OPP 并不是第四份复制实现**。它是「共享底层 + 薄 MCP
包装」的既有分层——`opp/mcp/security.py:104-109` 把 Phase 1 委托给
`opp/utils/security.py`，自己只追加扩展名白名单。真正重复的是 OL 与 ORF 两份自含实现
（OL 的文件头自陈 "Mirrors ``orf/mcp/security.py:PathValidator``"）。

审计同时发现了**第一轮未识别出的真实策略漂移**：

| 常量 | OPP 共享层 | OL | ORF |
|---|---|---|---|
| `SYSTEM_DIRS` | 9 项（含 `/proc`、`/sys`、`/C:/Windows`） | **6 项（缺 `/proc`、`/sys`、`/C:/Windows`）** | **7 项（缺 `/proc`、`/sys`）** |
| `BLOCKED_EXTENSIONS` | 7 项 | 7 项（一致） | 7 项（一致） |

即：`/proc` 与 `/sys` 在 OPP 被拦、在 OL/ORF 未被拦（`/proc/self/environ` 会暴露环境变量）。
另有一处静默分歧：OPP `opp/mcp/security.py:157` 与 ORF `orf/mcp/security.py:254` 的 legacy
`validate()` 读的是**类常量**，而 `validate_path()` 读的是**实例上被
`MCP_ALLOWED_EXTENSIONS` 覆盖过的集合** —— 于是环境变量在 legacy 路径上不生效。

ADR 0007 的结论是**两阶段**：

| 阶段 | 内容 | 是否需要改依赖/lock | 本轮可执行 |
|---|---|---|---|
| Phase 1 | 三份的 `SYSTEM_DIRS`/`BLOCKED_EXTENSIONS` 对齐到同一份 canonical 取值；修 legacy `validate()` 的 env 覆盖 bug；新增**行为向量表 + 三份一致性检查器**（pre-commit + CI 门禁），使「只改一份」直接红灯 | 否 | **是** |
| Phase 2 | 抽 `omni_security` 为第 4 个 workspace member，OL/ORF 声明依赖，三处改薄包装 | **是** | **否** |

Phase 2 被环境阻塞，证据可复现：

```
$ wsl uv --version                     -> uv 0.11.8
$ wsl uv lock                          -> mypy==2.3.1 无解
$ curl -o /dev/null -w '%{http_code}' https://pypi.tuna.tsinghua.edu.cn/simple/        -> 403
$                                    .../simple/ruff/                                -> 403
$                                    .../simple/structlog/                            -> 403
$ curl ... https://pypi.org/simple/mypy/                                              -> 200
```

workspace 配置的索引（清华镜像）在本环境对所有路径返回 403，`uv lock` 无法完成；
换索引会把 lock 里每个包的 registry URL 全部改写（841 KB 全量 diff），且会改变 CI 的
下载来源。因此必须先把共享模块的落地方式设计成「不需要 relock」，或由能访问该索引的环境
（CI 侧）完成 relock。

**Phase 2 的另一半约束**：OL 与 ORF 的 `pyproject.toml` 都**没有**声明依赖 OPP
（OL 的 20 条依赖里没有 `omni-pre-processor`），子仓库是三个独立可安装发行包，所以
Phase 2 必然要新增依赖声明 —— 这正是它绕不开 lock 的原因。ADR 中已把「让 OL/ORF 隐式
import `opp.utils.security` 而不声明依赖」列为被否决方案。

### 10.4 仍未解决 / 遗留

| 项 | 状态 |
|---|---|
| #2 Phase 1（对齐常量 + legacy bug + 一致性门禁） | **已落地（2026-09-17）** → 见第十一节；ADR 0007 转 Accepted |
| #2 Phase 2（抽共享包） | 被环境阻塞（索引 403，无法 relock）；需 CI 侧或可达索引 |
| #6 第三处 pin（`pyproject` dev extras） | 已回退并说明；不引入 lock 失效 |
| `setup_dev.ps1` 端到端验证 | **已完成（2026-09-17，见 11.2）**：全量 bootstrap `EXIT=0` + C-3 冒烟 9 passed |
| 报告第二轮改动的 commit | 本轮改动全部未提交（suite 21 个文件 + OL 5 个文件） |

---

## 十一、第三轮优化落地（2026-09-17，同日续做）：#2 Phase 1

按用户批准的「实施 Phase 1」，把 [ADR 0007](file:///d:/贯维/Omni_Suite/docs/adr/0007-path-security-convergence.md)
的三条全部落地并接入门禁；ADR 状态由 `Proposed` 改为 `Accepted (Phase 1 implemented)`。
本轮不做 Phase 2（抽 `omni_security` 共享包）—— 它仍被 `uv.lock` 无法重新生成阻塞（索引 403）。

### 11.1 已落地改动

| ADR 条目 | 改动的文件 | 机制 |
|---|---|---|
| Phase 1 步 1（常量对齐） | `Omni_Localizer/src/ol_mcp/security.py`、`Omni_Re_Formatter/src/orf/mcp/security.py` | `SYSTEM_DIRS` 由 6 项 / 7 项统一为 **9 项**（补 `/proc`、`/sys`、`/C:/Windows`），与 OPP 共享层逐项一致。纯增量 = 严格更严：原先能过的路径不会变松，原先漏掉的（如 `/proc/self/environ`）现在被拦 |
| Phase 1 步 2（legacy `validate()` env 失效） | `Omni_Pre_Processor/src/opp/mcp/security.py`、`Omni_Re_Formatter/src/orf/mcp/security.py` | 类方法 `validate()` 改走与 `validate_path()` 同一个 env 感知解析（`resolve_allowed_extensions()`），`MCP_ALLOWED_EXTENSIONS` 在两个入口都生效 |
| Phase 1 步 3（一致性不变量） | [tests/security/test_path_policy_parity.py](file:///d:/贯维/Omni_Suite/tests/security/test_path_policy_parity.py)（新增，30 用例） | 冻结 canonical 常量 + 共享行为向量表 + 三份校验器一致性检查 + legacy/env 回归 + **allowlist 解析一致性**。两套失败 API（OPP 抛异常 / OL·ORF 返回 `ValidationResult`）由 `_Copy` 适配器归一 |
| Phase 1 步 3（门禁·本地） | [.pre-commit-config.yaml](file:///d:/贯维/Omni_Suite/.pre-commit-config.yaml#L158-L166) | 新增 `omni-path-policy-parity` hook，作用域限定在策略面（orchestrator + 三份 security + 测试 + 自身配置）；**作用域与 CI 半门禁逐项对齐**（含各拷贝里的 allowlist 解析器 `src/.*/config\.py`，即 D-4 的落点）——已用脚本校验：6 条策略面路径全部命中、3 条无关路径均不命中 |
| Phase 1 步 3（门禁·CI） | [lint.yml](file:///d:/贯维/Omni_Suite/.github/workflows/lint.yml#L179-L205) | 新增 blocking step「path-security parity (three copies, one policy)」，沿用该 job 的 changed-file 作用域；命中策略面改动时**同时**跑三份拷贝 |
| ADR 记录的偏离 | 同上 | canonical 常量与向量表落在**测试模块内**而非独立运行时模块：跨子仓库的运行时共享模块需要新依赖声明（= Phase 2 的 lock 阻塞）。该偏离已在 ADR「Implementation」中写明理由 |
| 同族缺陷 D-3 | [omni_mcp/orchestrator.py](file:///d:/贯维/Omni_Suite/omni_mcp/orchestrator.py#L85-L125) | allowlist 按 `":"` 切分 → 改按 `os.pathsep` + 逗号 |
| 同族缺陷 D-4 | `opp/mcp/config.py`、`orf/mcp/config.py`、`ol_mcp/security.py` | `_parse_allowed_dirs` 在三份实现里都**优先按 `":"` 切分**。Windows 盘符含 `:`，文档给出的 Windows 写法 `OPP_MCP_ALLOWED_DIRS=C:\docs;C:\out` 会被切成 `["C","\docs;C","\out"]` —— allowlist 在 Windows 上**完全失效**。改为 `os.pathsep`（POSIX `:` / Windows `;`）+ 逗号；OL 侧新增了模块级 `_parse_allowed_dirs`（此前只有逗号切分，与 orchestrator 的报错文案不符） |
| 同族缺陷 D-5 | [opp/cli.py](file:///d:/贯维/Omni_Suite/Omni_Pre_Processor/src/opp/cli.py#L365-L386) | CLI `--resource-dir` 守卫原用 `Path("/tmp")`（Windows 上是 `<盘符>:\tmp`，与真实临时目录无关）+ 仅按逗号切分 → 改用 `tempfile.gettempdir()` 并复用 MCP 侧解析器 |
| 同族缺陷 D-6 | [opp/mcp/common.py](file:///d:/贯维/Omni_Suite/Omni_Pre_Processor/src/opp/mcp/common.py#L148-L184) | shutdown 清理的「拒绝根路径」守卫比较 `str(resolved) == "/"`，Windows 永不命中（`D:\` ≠ `/`）→ 改比 `Path.anchor`；另把计数用的 `rglob` 移入 `try`（遍历期的 `OSError` 原先会逃出 shutdown 钩子） |
| 测试侧平台假设（同族） | `Omni_Pre_Processor/tests/mcp/test_security.py`、`tests/mcp/test_phase2_mcp_consistency.py`、`tests/test_opp_cache.py`、`tests/test_opp_security_attacks.py`、`Omni_Localizer/tests/conftest.py`、`Omni_Re_Formatter/tests/test_mcp_config_fail_closed.py`、`tests/test_orf_security_attacks.py`、`tests/conftest.py`、`tests/security/test_opp_mcp_path_traversal.py` 等 | `xfail` 方向写反（POSIX 用例标在非 Windows 上 → 两侧都不生效）改为 `skipif(os.name == "nt")` + 说明；`"/tmp/unified"` 字面量断言改 `str(Path(...))`；`PathValidator(allowed_directories=[Path("/tmp")])` 改 `tempfile.gettempdir()`；硬编码 `":"` 拼 allowlist 改 `os.pathsep.join`；符号链接用例统一 `_symlink_or_skip`（WinError 1314 属环境限制，条件跳过并写明理由）；Windows 无 POSIX mode 位 → `0o700` 断言条件跳过 |
| 契约测试修复（审计中新发现） | `Omni_Pre_Processor/tests/test_opp_ol_orf_contracts.py`、`..._md.py` | 8 个 OPP→OL→ORF 契约用例**长期全红**：mock 目标 `ol_mcp.tools.ModelPool` 早已不存在（`ModelPool` 在 `ol_mcp/translate_xliff.py` / `translate_md.py`），且 OL 的 MCP 表面是 fail-CLOSED 的（三个 allowlist 变量皆空时抛错）。修正 mock 目标 + 补最小 allowlist 后 8/8 通过 —— 即「交付就绪度」里那条跨模块链路重新被真正验证 |
| ruff F 类（changed-file 门禁） | `opp/cli.py`、`opp/mcp/common.py`、`tests/mcp/test_security.py`、`Omni_Re_Formatter/tests/test_orf_security_attacks.py` 等 | 门禁语义是「改动文件不得有任何 F 类问题」。本轮清掉改动文件上的全部 F 类（含 2 处长期 F841 死赋值：`start_time`、以及一个「取到 `cmd_str` 却 `pass`」的空循环——后者顺势补上注释所声称的断言）。`opp/mcp/security.py` 的 `PathValidationError` 属有意再导出，改用 `X as X` 显式冗余别名而非删除 |
| `setup_dev.ps1` 两处缺陷（风险 #5 收尾，本轮实测发现） | [scripts/setup_dev.ps1](file:///d:/贯维/Omni_Suite/scripts/setup_dev.ps1) | (a) 步骤 3 只 `pip install -e` 三个子仓库，**不装根工程** —— 而冒烟门禁要在进程内 `import opp.mcp.server`，需要根工程声明的 `mcp` / `anyio`（三个子仓库的依赖里没有；`setup_dev.sh` 走 `uv sync` 会一并装上根 workspace，此处对齐同一语义）。(b) 步骤 7 仅凭 `.venv_win\Scripts\python.exe` **文件存在**就选它当解释器 —— 依赖未装完时（`-CheckOnly`，或上次 `pip install` 被打断）它以 `No module named pytest` 退出，把「环境未装完」误报成「C-3 契约被破坏」。改为探测 `import pytest` 通过才使用，且 `-CheckOnly` 下明确 WARN 跳过而不是红 —— 与 `tests/test_pipeline_contract_smoke.py` 自身 `_is_provisioned()` 同一原则 |
| F 类基线快照再校正（§4 第 2 条自身也在腐化） | [lint.yml](file:///d:/贯维/Omni_Suite/.github/workflows/lint.yml#L145-L156) | 注释里的 whole-tree 基线在第二轮由 `x116` 校正为 `123`，本轮实测已是 **107**（F841×40 / F541×37 / F401×29 + 1 invalid-syntax）——**同一棵树、同一 ruff 版本**（用 `pip install --target` 装入 pin 版本 `ruff 0.15.11` 复测，得 107；本机默认 `ruff 0.16.8` 同样得 107，故差异来自代码而非版本）。下降原因正是 changed-file 门禁清掉了改动文件上的真实存量。据此把注释改成「快照 + 复现命令 + 说明它会移动」，避免再犯「记一个常量然后腐化」的错。注：`ruff check .`（尊重 `force-exclude`/`extend-exclude`）与 `ruff check <module>/src`（显式路径不套 exclude）本就不同口径，第一轮的 146 属后者，两者不矛盾 |
| 报告自身引用复核（对报告自己执行同一标准） | 本报告 §3.8 与 §5 第 1 条 | 两处写「`.gitignore:82` 新增 `99-Tools/`」——实测 `git check-ignore -v` 报的是 **`.gitignore:85`**（第 82 行是 `test_artifacts/`）→ 已就地更正。报告的审计标准是「以实测为准」，对自身同样适用 |
| 本轮自伤回归（被 OPP 全量门禁抓到，已修） | [opp/cli.py](file:///d:/贯维/Omni_Suite/Omni_Pre_Processor/src/opp/cli.py#L362-L377) | D-5 修复时在该文件写了中文注释，撞上 OPP 自身的 P5-T1 硬化不变量 `test_p5_t1_cli_help_is_in_english`（扫描**整个 `src/opp/cli.py`** 的 CJK 字符，0 容忍）。这是全量 suite 才有、定向用例覆盖不到的不变量 —— 已把该文件注释改回英文并在注释中写明该门禁的存在，`test_phase5_opp_hardening.py` 5 passed |
| README 陈旧数字 + Windows 入口缺口 | [README.md](file:///d:/贯维/Omni_Suite/README.md#L99-L119) | 快速上手里的「38 observability tests / 63 security tests」实测为 **61 / 138**（`pytest --co`）→ 按实测校正；并在安装段补一条**原生 Windows 入口**说明（`.venv_ol/` 是 Linux venv，改用 `scripts/setup_dev.ps1`，`-CheckOnly` 只校验）。此前只有 `setup_dev.sh` 的报错会指路，README/SETUP/TESTS 三份面向开发者的文档都不提 —— 风险 #5 的修复在文档面等于不可见 |

### 11.2 验证证据（本轮实测，可复现）

```
# 一致性不变量（本轮新增，30 用例）
$ python -m pytest tests/security/test_path_policy_parity.py -q
30 passed

# 套件级安全测试（CI 式 FAKE_LLM）
$ python -m pytest tests/security -q
134 passed, 4 skipped
#   4 个 skip 全部是 WinError 1314（本机未开开发者模式，无法建符号链接），理由已写在 skip 里

# OPP MCP + 攻击面 + shutdown 清理
$ python -m pytest Omni_Pre_Processor/tests/mcp Omni_Pre_Processor/tests/test_opp_security_attacks.py \
      Omni_Pre_Processor/tests/test_mcp_shutdown_cleanup.py -q
168 passed, 9 skipped

# OPP 跨模块契约（修复前 8 个全红）
$ python -m pytest Omni_Pre_Processor/tests/test_opp_ol_orf_contracts.py Omni_Pre_Processor/tests/test_opp_ol_orf_contracts_md.py -q
8 passed

# ORF 安全攻击面
$ python -m pytest Omni_Re_Formatter/tests/test_orf_security_attacks.py Omni_Re_Formatter/tests/test_mcp_config_fail_closed.py -q
13 passed

# OL 侧安全回归（Phase 1 步 1 动过 OL 的 SYSTEM_DIRS，必须证明没被改坏）
$ python -m pytest Omni_Localizer/tests/test_phase2_ol_mcp.py \
      Omni_Localizer/tests/test_ol_mcp_verify_terms_path_denied.py \
      Omni_Localizer/tests/test_loader_security.py -q
38 passed

# OPP 全量基线（本轮最终，沙箱外运行）
$ $env:OMNI_TEST_FAKE_LLM="1"
$ python -m pytest Omni_Pre_Processor/tests -q
1047 passed, 34 skipped, 1 xpassed, 3 warnings in 590.10s
#   exit 0。对照：同一命令在沙箱内跑是 5 failed / 1043 passed —— 其中 4 个是沙箱
#   禁止写 C:\Users\...\.omni_cache 与 D:\tmp 造成的 PermissionError 伪失败（纯环境），
#   第 5 个是本轮自伤的真实回归（cli.py 中文注释，见 11.1），已修复。
#   `1 xpassed` 在修复前后两次运行中都存在，非本轮引入。

# Windows 引导脚本（风险 #5 收尾）：-CheckOnly 路径
$ powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup_dev.ps1 -CheckOnly
[OK]   Python 3.13 已就绪
[INFO]   版本校验 OL/OPP/ORF: 与 COMPATIBILITY.md 一致
[WARN] 未检测到 pandoc —— ORF 生成 DOCX/ODT/EPUB/RTF/ICML 需要它。
[WARN] D:\贯维\Omni_Suite\.venv_win\Scripts\python.exe 尚不可用（依赖未安装，-CheckOnly 模式不安装）—— 跳过 C-3 冒烟测试。
EXIT=0
#   修复前同一命令会以 `No module named pytest` 判红（exit 1）；修复后是明确的
#   「环境未装完，跳过门禁」而非伪红。

# Windows 引导脚本（风险 #5 收尾）：全量安装路径，沙箱外运行至结束
$ powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup_dev.ps1
...
Obtaining file:///D:/%E8%B4%AF%E7%BB%B4/Omni_Suite          # ← 修复后的步骤 3：根工程也装
Obtaining file:///D:/%E8%B4%AF%E7%BB%B4/Omni_Suite/Omni_Pre_Processor
Obtaining file:///D:/%E8%B4%AF%E7%BB%B4/Omni_Suite/Omni_Localizer
Obtaining file:///D:/%E8%B4%AF%E7%BB%B4/Omni_Suite/Omni_Re_Formatter
Successfully built omni-suite omni-pre-processor omni-localizer omni-re-formatter
Successfully installed ... omni-localizer-0.7.1 omni-pre-processor-0.9.1 omni-re-formatter-0.4.17 omni-suite-0.4.0 ...
[OK]    OMNI-SUITE / OPP / OL / ORF 安装完成
[INFO]    版本校验 OL: COMPATIBILITY=0.7.1 实际=0.7.1
[INFO]    版本校验 OPP: COMPATIBILITY=0.9.1 实际=0.9.1
[INFO]    版本校验 ORF: COMPATIBILITY=0.4.17 实际=0.4.17
[OK]    子仓库版本与 COMPATIBILITY.md 一致
[WARN]  未检测到 pandoc —— ORF 生成 DOCX/ODT/EPUB/RTF/ICML 需要它。
[INFO]  C-3 冒烟测试解释器: D:\贯维\Omni_Suite\.venv_win\Scripts\python.exe
tests\test_pipeline_contract_smoke.py ... 9 passed, 1 warning in 12.86s
[OK]    C-3 契约冒烟测试通过
[INFO]  安装完成。快速开始（Windows PowerShell）：
EXIT=0
#   ① 四处 editable 安装（根工程 + 三个子仓库）确实都进了 .venv_win（修复 (a) 被这里实证）；
#   ② 解释器选择走到 `import pytest` 探测通过分支 → 冒烟 9 passed（修复 (b) 被实证）。
#      对照第十节 10.2 里系统解释器跑同一文件是 `1 failed, 8 passed`
#      （失败项 = 系统解释器缺 ORF 声明的 markdown）——即 .venv_win 路径比原回退路径更强。
#   ③ pandoc 仍缺（本机未装）；ORF 的 pandoc 系输出用 pypandoc-binary 兜底，属已知项。

# 静态检查：改动文件集合（CI changed-file 语义）
$ python -m ruff check --select F <本轮全部改动的 .py>
All checks passed!

# F 类 whole-tree 基线（配 lint.yml 注释里的快照；用 pin 版本复测以排除版本因素）
$ python -m pip install --target "$env:TEMP\ruff_0_15_11" --no-deps ruff==0.15.11   # pin 版本
$ & "$env:TEMP\ruff_0_15_11\bin\ruff.exe" --version        -> ruff 0.15.11
$ & "$env:TEMP\ruff_0_15_11\bin\ruff.exe" check . --select F --statistics
40 F841 / 37 F541 / 29 F401 / 1 invalid-syntax = 107 errors
$ python -m ruff --version                                 -> ruff 0.16.8   # 本机默认
$ python -m ruff check . --select F --statistics           -> 同样 107 errors
#   两个版本同值 → 123→107 的差来自本轮改动清掉的存量，不是 ruff 版本漂移。

# 类型检查门禁（CI 同款命令，第十节放宽后的范围）
$ python -m mypy omni_metrics omni_suite omni_mcp
Success: no issues found in 23 source files

# 文档真值门禁
$ python scripts/doc_inventory.py --check
check passed: source truth matches claims, no stray files, inventory fresh.

# 场景库契约 lint
$ PYTHONPATH=. python scripts/validation/run_validation.py --check
Contract check: clean — ...

# lint.yml 语法与新增门禁的正则行为
$ python -c "import yaml;yaml.safe_load(open('.github/workflows/lint.yml',encoding='utf-8'))"
yaml ok, steps: 13（最后一步 = path-security parity）
#   5 条策略面路径命中、3 条无关路径不命中（脚本化验证）
```

「先证明不是本轮引入」的证据（方法：`git stash push -- src tests` 回到 HEAD 再跑同一批用例）：

```
$ git -C Omni_Pre_Processor stash push -- src tests
$ python -m pytest <9 个当时失败的用例> -q
9 failed, 2 passed            # HEAD 状态同样 9 failed → 零回归
$ git -C Omni_Pre_Processor stash pop
```

### 11.3 本轮遗留（明确记录，未伪装为已解决）

| 项 | 状态 |
|---|---|
| #2 Phase 2（抽 `omni_security` 第 4 个 workspace member） | 仍被环境阻塞：workspace 索引（清华镜像）403，`uv lock` 无法完成；任何 `pyproject` 依赖变更都会打挂 `uv sync --locked` |
| OL CLI 的第 4 份 allowlist 解析（`Omni_Localizer/src/cli/load_glossary.py`） | 仅逗号切分，且带 `cwd + /tmp` 的 **fail-open** 回退；属 CLI 表面、不在本次 MCP 策略面内，未纳入 parity 门禁。已在 ADR「Residual differences」写明 |
| OPP 包内**未改动**文件的存量 F 类 | 例如 `opp/commands/batch.py`(F401×3+F841)、`opp/logger.py`(F841)、`opp/mcp/server.py`(F401×2)、`opp/pipeline.py`(F401) 等 11 处，位于本轮改动集合之外，按 changed-file 门禁语义保留未动 |
| `Omni_Pre_Processor/batch_test/phase0_office/normal.skeleton.zip` | **已删除**（副产物本体 `Test-Path` 复核为 `False`）。根因未修：跑 ORF 测试时 `pipeline.py` 会把骨架写进**受跟踪的 fixture 目录**，属测试污染受跟踪目录的独立问题，不在本轮范围 |
| `setup_dev.ps1` 端到端验证 | **已跑完并全绿（2026-09-17）**：全量 bootstrap `EXIT=0`，`C-3 契约冒烟测试通过`（`.venv_win` 下 **9 passed**）。详见 11.2 末段 |
| 本轮改动的 commit | 全部未提交（系统规则：未经用户明确要求不提交）。实测 `git status --short`：suite 27 modified + 4 untracked、OPP 10 modified、OL 7 modified、ORF 4 modified |
| `Omni_Pre_Processor/batch_test/phase0_office/normal_generated.md` 的 ` M` 标记 | **非内容改动**：`git diff --numstat` 与 `git diff --ignore-all-space --stat` 均为空输出 → 仅 stat-dirty（行尾/元数据），不构成待提交内容，本轮不动 |

---

## 十二、第四轮优化落地（2026-09-17，同日续做）：R2 收口 + 门禁可用性

本报告 §3.2 的 **R2（suite 层绕过子模块 PathValidator）是最后一条未处理的报告结论**。
本轮把它收口（= ADR 0007 Phase 1 的 step 3b），并顺带清掉「文件在 Windows 上根本跑不起来」
这条使前几轮证据打折的同族缺陷。Phase 2 仍按已批准的推迟处理（`uv.lock` 无法重生成）。

### 12.1 已落地改动

| 条目 | 文件 | 机制 |
|---|---|---|
| **§3.2 R2**：orchestrator 只有 allowlist 一层 | [omni_mcp/orchestrator.py](file:///d:/贯维/Omni_Suite/omni_mcp/orchestrator.py#L97-L119)、[L166-L240](file:///d:/贯维/Omni_Suite/omni_mcp/orchestrator.py#L166-L240) | 补齐 canonical `SYSTEM_DIRS`（9 项）/ `BLOCKED_EXTENSIONS`（7 项）与 `_system_dir_denial()`（与三份校验器**同一** `Path.parts` 前缀算法）。`_path_denial_message()` 的检查顺序改为：fail-CLOSED allowlist 前置 → 系统目录 → 黑名单扩展名 → allowlist 包含。修复前：只要路径落在 allowlist 内，`/etc/shadow.md`、`evil.exe` 都会被交给子进程 |
| R2 的另一半：陈旧的"我校验过"声明 | 同上（模块 docstring、`translate_file` 的 `logger.warning`） | 原文自陈「accepts arbitrary file_path values without path validation」，而 `translate_file` 的 warning 又称请求经子模块 `PathValidator` 校验 —— subprocess 路径**根本到不了** `PathValidator`。两处改为如实描述本层强制的是**策略副本**，并显式列出**未**复制项（per-module 扩展名白名单、体积上限、symlink 复查）与理由 |
| parity 扩到第 4 份拷贝 | [tests/security/test_path_policy_parity.py](file:///d:/贯维/Omni_Suite/tests/security/test_path_policy_parity.py) | 30 → **39** 用例：canonical 常量断言覆盖 orchestrator；新增 orchestrator 专属行为向量表（= 共享表去掉 `missing_file_inside_allowlist` —— 存在性由 `translate_file` 的 `FILE_NOT_FOUND` 负责，塞进本层会变成行为回退）；`ALLOWLIST_PARSERS` 3 → 4 项 |
| 门禁与 ADR 的计数/措辞 | [lint.yml](file:///d:/贯维/Omni_Suite/.github/workflows/lint.yml#L179-L210)、[ADR 0007](file:///d:/贯维/Omni_Suite/docs/adr/0007-path-security-convergence.md) | "three copies" → "every copy"；ADR 策略面表新增 suite orchestrator 行、新增 **Step 3b** 小节（四个改动点 + 5 条契约不变）、Residual/Consequences 的「三份」计数改四份 |
| 同族：CLI 集成用例在 Windows 上跑不起来 | [tests/test_omni_mcp_translate_file.py](file:///d:/贯维/Omni_Suite/tests/test_omni_mcp_translate_file.py#L33-L57) | `_VENV_BIN = .venv_ol/bin` 是 **Linux 布局** → `subprocess` 报 `WinError 193`（不是有效的 Win32 应用程序），4 个「OPP→OL→ORF 真的能跑」的集成用例长期判红。改为平台感知（Windows `.venv_win/Scripts`，依次试 `name` / `name.exe`，再回退 `shutil.which`）+ `/tmp` 字面量改 `tempfile.gettempdir()`；与 `tests/test_pipeline_contract_smoke.py`、`scripts/pre_commit_python.sh` 同族同修法 |
| 同族：模块级 setdefault 进程级污染 allowlist | [tests/test_mutation_transparency_x03.py](file:///d:/贯维/Omni_Suite/tests/test_mutation_transparency_x03.py#L26-L39) | 该文件在 import 期 `setdefault("MCP_ALLOWED_DIRECTORIES", "/tmp")`。pytest 在跑任何用例前会 import 全部测试模块，而该变量在**每个**读取者里优先级都高于 `ORF_MCP_ALLOWED_DIRS` → 收集期就把 conftest 的更宽 allowlist 覆盖掉；Windows 上 `Path("/tmp")` = `<当前盘符>:\tmp`，于是 conftest 明确允许的 `tmp_path` 被判 `Path is not within the allowed directories` —— 本文件 4 个用例为**环境原因**自伤失败。删掉该 setdefault，allowlist owner 归还 conftest |
| 同族：安全警告断言的文案 | [tests/test_omni_mcp_security_warning.py](file:///d:/贯维/Omni_Suite/tests/test_omni_mcp_security_warning.py) | docstring 随 R2 如实化（原文声称 warning 表示"经 PathValidator 校验"）；断言仍要求日志含 `SECURITY` 与 `PathValidator` 两个词 —— 新文案两者都含，**未放松** |
| changed-file F 门禁 | [tests/test_omni_mcp_translate_file.py](file:///d:/贯维/Omni_Suite/tests/test_omni_mcp_translate_file.py#L11-L17) | 清掉该改动文件上的 2 个 F401（`json`、`unittest.mock.MagicMock` 均为死导入）。门禁语义是「改动文件不得有任何 F 类」，与是否本轮引入无关 |

### 12.2 验证证据（本轮实测，可复现）

```
# 一致性不变量：第 4 份拷贝入表（30 → 39）
$ .venv_win\Scripts\python.exe -m pytest tests/security/test_path_policy_parity.py -q
39 passed, 1 warning in 23.45s

# 套件级安全测试（147 collected）
$ .venv_win\Scripts\python.exe -m pytest tests/security -q
143 passed, 4 skipped, 1 warning in 47.08s
#   4 个 skip 全部是 WinError 1314（本机未开开发者模式，无法建符号链接），理由已写在 skip 里

# R2 不得破坏的 5 条既有契约（allowlist 外拒 / 无 allowlist fail-CLOSED /
# allowlist 内可达 pipeline / secret 不匹配 AUTH_FAILED / fixtures）
$ .venv_win\Scripts\python.exe -m pytest tests/security/test_omni_mcp_path_denied.py -q
5 passed, 1 warning in 6.68s

# 三个 omni_mcp 测试文件（平台修复后）
$ .venv_win\Scripts\python.exe -m pytest tests/test_omni_mcp_translate_file.py \
      tests/test_omni_mcp_security_warning.py tests/test_mutation_transparency_x03.py -q
28 passed, 1 warning in 30.18s

# 「先证明不是 R2 引入的」——同一批文件，R2 前后各跑一次
$ Copy-Item omni_mcp\orchestrator.py $env:TEMP\orchestrator_r2.py
$ git checkout -- omni_mcp/orchestrator.py        # 回到 HEAD（无 R2）
$ .venv_win\Scripts\python.exe -m pytest <上述三个文件> -q   -> 12 failed, 16 passed
$ Copy-Item $env:TEMP\orchestrator_r2.py omni_mcp\orchestrator.py   # 恢复 R2
$ .venv_win\Scripts\python.exe -m pytest <上述三个文件> -q   -> 12 failed, 16 passed
#   两次同值 → R2 零回归；那 12 个失败来自本轮已定位并修掉的三个环境根因
#   （模块级 allowlist 覆盖、Linux venv 布局 WinError 193、/tmp 字面量），
#   修完后同批为 28 passed。

# 类型检查（CI 同款命令 + CI 同款 pin，本机系统 Python 3.13.5 已装 mypy 2.3.1）
$ mypy --version                              -> mypy 2.3.1 (compiled: yes)
$ mypy omni_metrics omni_suite omni_mcp
Success: no issues found in 23 source files

# ruff changed-file F 类门禁
$ ruff check --select F (git diff --name-only HEAD -- '*.py')     -> All checks passed!
#   本机默认 ruff 0.16.8；commit 路径由 ruff-pre-commit rev v0.15.11（CI 同 pin）再跑一次

# 文档真值门禁（SOURCE: OPP=9 OL=21 ORF=7 total=37 / 119 场景）
$ .venv_win\Scripts\python.exe scripts/doc_inventory.py --check     -> check passed, EXIT=0

# 场景库契约 lint
$ .venv_win\Scripts\python.exe scripts/validation/run_validation.py --check    -> clean, EXIT=0

# tier-1 场景端到端（真实 .venv_ol，经 WSL —— 原生 Windows 跑不了 Linux venv，
# 而 dispatch.py 的 VENV_BIN 钉死 .venv_ol，所以执行型证据只能走 WSL）
$ wsl -e bash -lc "cd /mnt/d/贯维/Omni_Suite && MCP_ALLOWED_DIRECTORIES=/tmp OMNI_TEST_FAKE_LLM=1 \
      ./.venv_ol/bin/python scripts/validation/run_validation.py --scenario red-team-path-traversal --tier 1"
Run 20260917-210145 — red-team-path-traversal  passed — 8 step(s), 8 passed
$ ... --scenario trace-mutation-manifest-x03 --tier 1
Run 20260917-210223 — trace-mutation-manifest-x03  passed — 2 step(s), 2 passed
$ ... --scenario ol-path-denied --tier 1
Run 20260917-210259 — ol-path-denied  passed — 2 step(s), 2 passed
#   三个场景都直接落在本轮改动的路径拒绝面上（traversal / omni_mcp manifest / allowlist 拒绝）
```

### 12.3 本轮遗留（明确记录，未伪装为已解决）

| 项 | 状态 |
|---|---|
| #2 Phase 2（抽 `omni_security` 共享包） | 仍被环境阻塞（清华镜像 403 → `uv lock` 无法完成）。ADR 0007 维持 `Accepted (Phase 1 implemented; Phase 2 deferred)` |
| `omni_mcp` 仍是第 4 份**策略副本**（非共享实现） | ADR 0007 的原则是「策略只有一份、门禁冻结每一份拷贝」；`omni_mcp` 零依赖三个子仓库，所以 Phase 1 只能到「常量逐字一致 + parity 冻结」。Phase 2 落地时才可能收敛为共享包 |
| OL CLI 的第 4 份 allowlist 解析（`Omni_Localizer/src/cli/load_glossary.py`） | 仍是仅逗号切分 + `cwd + /tmp` 的 **fail-open** 回退；属 CLI 表面，不在 MCP 策略面内，未纳入 parity 门禁（ADR「Residual differences」已写明） |
| §5 第 8 条（T13-01 / T13-02） | 代码已修，**待 tier-2 真 LLM 复验**（本机无 key；门禁语义下 tier-2 缺 key = `unconfigured`，不作通过） |
| 本轮改动的 commit | 随本次 commit 一并提交（suite 单 commit，含第二/三/四轮此前未提交的改动）；OPP / OL / ORF 三个子仓库的对应改动已在各自仓库单独提交 |
| 报告 §5 十条风险的当前状态 | 1/3/4/5/6/7/9/10 已闭环；2 = Phase 1 落地、Phase 2 经批准推迟；8 = 代码已修、待 tier-2 复验 |

---

## 十三、第五轮优化落地（2026-09-17，同日续做）：§3.7 仓库卫生收尾

§3.7 是报告评分最低的维度（42/100），其「根目录散落样本文件（已被跟踪）」一条此前只处理了
`99-Tools/` 的 ignore 规则，**样本文件本身仍在根目录**。本轮把四个样本全部迁出根目录。

### 13.1 关键判定：目标目录只能是 `scenarios/_fixtures/`

| 候选目录 | 判定 | 证据 |
|---|---|---|
| `test_fixtures/` | **不可用** | `.gitignore:109` 忽略整个目录；`git ls-files test_fixtures` 输出为空——该目录是**纯本地** fixture 暂存区（22 个文件全部未跟踪） |
| `scenarios/_fixtures/` | **采用** | 唯一承载被跟踪 fixture 的目录（`git ls-files scenarios/_fixtures` 23 项），且报告 L390 本身把它列为首选 |

### 13.2 落地改动

| 原位置（根目录） | 新位置 | 处理方式 | 依据 |
|---|---|---|---|
| `Meridian_Robotics_Product_Overview_E2E.docx` | `scenarios/_fixtures/meridian_robotics.docx` | **去重**：根目录副本删除，引用重指到已存在的副本 | 两者 SHA256 均为 `C8DB5E79…FFA928`（字节相同） |
| `Meridian_Q1_Update_E2E.pptx` | `scenarios/_fixtures/meridian_q1.pptx` | **去重**：同上 | 两者 SHA256 均为 `1E9F8C0D…1655C19C`（字节相同） |
| `爱上海尔_第二章_全球创牌 - E2E测试专用.docx` | `scenarios/_fixtures/haier_ch2_zh.docx` | `git mv`（git 识别为 rename，`R`） | commit 内 ASCII 名符合该目录命名惯例（`meridian_*.docx` / `sample.ipynb`），且可在 CLI 步骤中免引号使用 |
| `（slim）爱上海尔.docx`（14 MB，未跟踪） | `test_fixtures/zh/（slim）爱上海尔.docx` | 移动（`.gitignore:105` 规则对任意层级生效，仍被忽略） | 它本就是本地验证靶，属 `test_fixtures/` 的语义 |

同步的引用面（逐处核对，`grep` 全仓零残留）：

- **scenarios（4）**：`opp/opp-docx-extract.yaml` 与 `opp/opp-pptx-extract.yaml` 不只要改 fixture 路径，
  还要改它们**断言的 OPP 输出 stem**（输出名派生自输入 stem）：
  `md-path=Meridian_Robotics_Product_Overview_E2E.md` → `md-path=meridian_robotics.md`，
  `Meridian_Q1_Update_E2E_manifest.json` → `meridian_q1_manifest.json` 等；
  `agent-interaction/agent-interaction-multiturn-context.yaml`（turn-1 的 `doc`）；
  `pipeline/pipeline-pptx-md-pptx.yaml`（说明文字）。
- **tests（12 文件）**：`conftest.py`（3 个 path fixture）、`e2e_runner.py`、
  `test_cross_format_e2e.py`、`test_e2e_performance.py`、`test_e2e_pipeline_full.py`、
  `test_e2e_real_llm.py`、`test_e2e_xliff_lqa_image_placement.py`、`test_mcp_smoke.py`、
  `test_omni_suite_cli.py`、`test_orf_skeleton_large_file.py`、`turnkey/test_image_fidelity.py`。
- **scripts（3）**：`check_readiness.py`（V4.8 fixture 存在性）、`omo_loop.py`（`_DEFAULT_FIXTURE`）、
  `phase1_runner.py`。
- **docs（2）**：`SETUP.md`、`TESTS.md`；`.gitignore` 的 `（slim）` 注释。

顺带修掉的两处同族缺陷：

1. `tests/turnkey/test_image_fidelity.py:30` 硬编码 `"/mnt/d/贯维/Omni_Suite/…"` —— 正是本轮
   LOOP-LOG 坑清单第 2 条禁止的**机器绝对路径**；改为套件根相对路径。
2. `scripts/phase1_runner.py` 的 `resolve_fixture()` 有一个 docx-only 特例去套件根找文件，
   兜底却指向 `test_fixtures/zh/爱上海尔_第二章…docx`（该文件从不存在 → 该行 fixture 一直是悬空路径）。
   现在统一指向 `scenarios/_fixtures/`，docx/zh 这一格才真正可用。

### 13.3 验证证据（2026-09-17 实测，命令可复现）

```bash
# 根目录已无样本（迁移前：2 个 docx + 1 个 pptx + 1 个 14MB docx）
$ Get-ChildItem <suite 根> -File -Filter *.docx          -> 空
$ Get-ChildItem <suite 根> -File | ? Name -like '*Meridian*'   -> 空
$ git status --short                                     -> 根目录仅 D（删除）与 R（重命名）

# 门禁一：文档真值 + 链接/路径完整性
$ .venv_win\Scripts\python.exe scripts/doc_inventory.py --check
check passed: source truth matches claims, no stray files, inventory fresh.   EXIT=0

# 门禁二：场景库契约 lint
$ .venv_win\Scripts\python.exe scripts/validation/run_validation.py --check
Contract check: clean — every step falsifiable ... every scenario declares an approved user level   EXIT=0

# 门禁三：tier-1 场景端到端（真实 .venv_ol，经 WSL；含被改动的 fixture 路径与 stem 断言）
$ wsl -e bash -lc 'cd /mnt/d/贯维/Omni_Suite && MCP_ALLOWED_DIRECTORIES=/tmp OMNI_TEST_FAKE_LLM=1 \
    ./.venv_ol/bin/python scripts/validation/run_validation.py --scenario opp-docx-extract --tier 1'
Run 20260917-212138 — opp-docx-extract   passed — 3 step(s), 3 passed
$ ... --scenario opp-pptx-extract --tier 1
Run 20260917-212159 — opp-pptx-extract   passed — 3 step(s), 3 passed
$ ... --scenario agent-interaction-multiturn-context --tier 1
Run 20260917-212242 — agent-interaction-multiturn-context  passed — 3 step(s), 3 passed

# 门禁四：路径敏感测试 + 全部改动模块的导入完整性
$ .venv_win\Scripts\python.exe -m pytest tests/test_link_integrity.py \
      tests/turnkey/test_image_fidelity.py tests/test_orf_skeleton_large_file.py -q
1 failed, 6 passed, 2 skipped        # 唯一 failed = 下述既有漂移（test_agent_docs）
# 其中 tests/test_orf_skeleton_large_file.py 的 4 个用例由「skip」变为**真跑并 passed**
# —— 它们加载的正是被移动的 14MB slim，这是 slim 路径迁移的直接证据。
$ .venv_win\Scripts\python.exe -m pytest tests/test_e2e_performance.py \
      tests/test_cross_format_e2e.py tests/test_omni_suite_cli.py tests/test_mcp_smoke.py \
      tests/test_e2e_pipeline_full.py tests/test_e2e_xliff_lqa_image_placement.py \
      tests/test_e2e_real_llm.py tests/e2e_runner.py --collect-only -q
149 tests collected in 1.37s          # 8 个模块全部可导入，无残留路径
$ .venv_win\Scripts\python.exe -m pytest tests/test_phase1_p2_matrix.py \
      tests/test_link_integrity.py -q   -> passed（phase1_runner 改动后的矩阵用例仍绿）
```

### 13.4 本轮遗留与新发现（不伪装为已解决）

| 项 | 状态与证据 |
|---|---|
| `tests/test_agent_docs.py::test_skill_md_exists` 失败 | **既有漂移，非本轮回归**：它断言 `.opencode/skills/omni-suite/SKILL.md` 含 `Output formats supported`；该文件**不在本次改动集内**，且 `git show HEAD:.opencode/skills/omni-suite/SKILL.md \| Select-String 'Output formats supported'` 在 HEAD 上同样无匹配。**→ 已于第六轮修复，见 §14.1** |
| `tests/test_convergence_watch_gates.py` 2 个失败 | **既有测试漂移，非本轮回归**：`git show HEAD:scripts/omo_loop.py` 已有 `gates = ["tier6","tier7","tier8"]`，测试却只 stub `_run_verify_all`/`_run_format_matrix`，于是真 tier8 门跑起来（单跑该文件 157 s）并返回 1，而断言要求 `rc == 0`。本轮在该文件只改了 `_DEFAULT_FIXTURE`（仅被 argparse 默认值引用，那两个用例传的 `argparse.Namespace` 连 `input` 都没有，不可达）。修法是把 tier8 一并 stub（1 行），留待下一轮决策。**→ 已于第六轮修复，见 §14.1** |
| 缺少「根目录不得出现样本文件」的守卫 | 未加。本轮按报告 §3.7 的范围只做迁移 + 引用同步；若要把 42/100 的这个维度长期钉住，可加一条断言「套件根无 `*.docx / *.pptx` 被跟踪文件」的测试或 pre-commit 检查。**→ 已于第九轮落地，见 §17** |
| 仓库内仍存同字节副本 | `scenarios/_fixtures/translated_pair/source.docx` 与 `meridian_robotics.docx` 字节相同（XLIFF 场景的 pre-translated 对，属有意设计：该目录是自包含的 8 文件 fixture 对，删任何一个都会破坏 `COPIED 8` 断言）。未动 |

---

## 十四、第六轮优化落地（2026-09-17，同日续做）：门禁实盘化 + 测试漂移修复

第五轮（§十三）收尾时留下了两项红测与一项「门禁不触发」的疑点。本轮把红测清零，
并查出并修掉了一个**让三条 pre-commit 门禁长期空转**的正则缺陷。

### 14.1 修复 §13.4 的两项测试漂移（红测清零）

| 测试 | 根因（实测） | 修复 | 证据 |
|---|---|---|---|
| `tests/test_convergence_watch_gates.py`（2 failed，单文件 157 s） | `_run_convergence_watch` 的 `both` 门集早已是 `["tier6","tier7","tier8"]`，测试却只 stub 了 tier6/tier7 → **真** Tier 8 门（真语料 + 保真度 + 等价性）被拉起、返回 1，两条断言 `rc == 0` 因此失败 | 新增 `_stub_all_gates()` 统一 stub 三个门（并在 docstring 写明必须与门集保持同步）；补两条缺失契约用例：`--gate tier8` 只跑 Tier 8、仅 Tier 8 红即阻断收敛；顺手删 `import pytest`（F401） | `pytest tests/test_convergence_watch_gates.py tests/test_agent_docs.py -q` → **10 passed in 8.08s**（原单文件即 157 s） |
| `tests/test_agent_docs.py::test_skill_md_exists` | 断言的字面量是 `Output formats supported`，而 `SKILL.md` 实际标题为 `## Output formats (16, ORF \`apply-md\`)` —— 章节存在，是期望子串陈旧 | 期望子串改为 `Output formats`；其余 4 个必需章节命中，未动 | 同上 10 passed |

生产侧文档真值同步：`scripts/omo_loop.py` 的 `_run_convergence_watch` docstring 与
`--gate` 的 help 文本仍写着「both = Tier 6 + Tier 7」，与
`choices=["tier6","tier7","tier8","both"]` 的实际派发不符 —— 已更新为三个门，
避免下一个人按注释误判默认门集。

### 14.2 新发现：3 条 pre-commit hook 的 `files:` 正则永久失配（门禁在空转）

**现象（第五轮 commit 的钩子输出，改动集含 `docs/project-health-report-*.md` 与 4 个 `scenarios/**/*.yaml`）**：

```
Omni Suite doc-inventory check (…)................................(no files to check)Skipped
Omni Suite MCP tool coverage audit (execution-backed).............(no files to check)Skipped
Omni Suite scenario-library contract lint.........................(no files to check)Skipped
```

**根因**：pre-commit 用 `re.search` 匹配 `files:`，而这三条 hook 写成
`^(docs/|scenarios/|scripts/validation/|omni_mcp/|…)$`。`docs/` 这类分支被 `$`
钉死为「路径恰好等于 `docs/`」，于是 `docs/x.md`、`scenarios/x.yaml` **永远不匹配**：
门禁只在改动 `.pre-commit-config.yaml` 自身时才跑，日常改动一律空转。

| hook | 死掉的分支 | 修复 |
|---|---|---|
| `omni-doc-inventory` | `docs/`、`reports/`、`scenarios/` | `docs/.*`、`reports/.*`、`scenarios/.*` |
| `omni-validation-check` | `scenarios/`、`scripts/validation/`、`omni_mcp/` | 同构补 `.*` |
| `omni-coverage-audit` | `scenarios/`、`scripts/validation/`、`omni_mcp/`、`Omni_*/src/.*/mcp/` | 同构补 `.*` |

（`omni-version-docs-sync` 与 `omni-path-policy-parity` 的 pattern 全是精确文件名或已带
`.*`，未受影响。）

**验证一（正则前后对照，23 条真实路径）**：
`99-Tools/validation-scratch/omni-suite/verify_files_glob.py` → 旧 pattern 对所有前缀路径
`False`、新 pattern 全部 `True`，`mismatches=0`。脚本用 `re.search` 直接复现
pre-commit 的匹配语义，改 pattern 后可重跑复核。

**验证二（真实触发，此前一律 Skipped）**：

```bash
$ pre-commit run omni-validation-check --files scenarios/opp/opp-docx-extract.yaml
Omni Suite scenario-library contract lint.......................................................Passed
$ pre-commit run omni-doc-inventory  --files docs/project-health-report-2026-09-17.md
Omni Suite doc-inventory check (AUTO-GENERATED header + source-truth MCP counts)................Passed
$ pre-commit run omni-coverage-audit --files scenarios/opp/opp-docx-extract.yaml
Omni Suite MCP tool coverage audit (execution-backed)...........Passed  (duration: 0.63s)
SKIP: .venv_ol is not runnable on this platform — execution-backed coverage parity is not
      exercised locally (CI runs it on Linux)
```

即：三条门禁不但开始**真正触发**，且对本仓库当前状态是**真绿** —— doc-inventory、
scenario-lint 通过；coverage-audit 在 Windows 上按设计打印显式 `SKIP` 行（`verbose: true`
使该行可见），而不是静默通过。

副作用提示：这三条 hook 从此会在日常提交时运行，其中 doc-inventory 会强制
「docs 改动 → `docs/dev/doc-inventory.md` 必须新鲜」，这正是原设计意图，但此前从未真正生效。

### 14.3 本轮遗留（不伪装为已解决）

| 项 | 状态 |
|---|---|
| 「根目录不得出现样本文件」守卫（§13.4 第 3 行） | 仍未加。落点建议：`scripts/doc_inventory.py` 的 stray 检查家族 + `tests/test_doc_inventory.py` 里对**真实仓库**的断言（CI 的 `pytest tests/ -m "not nightly"` 会跑到）。**→ 已于第九轮落地，见 §17** |
| 报告 §3.3 `extend-exclude` 排除 `extractors/ ol_buses/ converters/` | **已于第十轮处理并更正因果，见 §18** |
| 报告 §3.4 `sys.path` 注入 / `scripts/mcp_bridge.py` 职责重叠 | **已于第十一轮处理（含 mcp_bridge 过期结论更正），见 §19** |
| 报告 §3.5 `doctor.yml` `continue-on-error: true` | **已于第七轮处理，见 §15.4**（同轮发现并修掉 `make doctor` 在本机的静默 `exit 49`） |
| `coverage_audit.py` 无友好降级 | 未处理；14.2 已让 coverage-audit 的 SKIP 行为在本机可见 |
| 报告 §5 #2 Phase 2（外部索引 403）、#8（tier-2 真 LLM 复验） | 仍处外部阻塞／待 key，不可伪绿 |

---

## 十五、第七轮：`make doctor` 静默失效修复 + doctor 门禁转阻塞（2026-09-17）

承接 §14.3 的「§3.5 `doctor.yml` `continue-on-error: true` 未处理」。取证时先撞上一个**更基础的问题**：
`make doctor` 在本机（Windows / Git Bash）根本不是「跑完了有几项警告」，而是**打一行就死、且不报错**。

### 15.1 发现：`make doctor` 打一行 `[INFO]` 后静默退出（exit 49）

把 HEAD 版脚本还原后在同一环境实跑（修复前的真实行为）：

```bash
$ git show HEAD:scripts/check_deps.sh > 99-Tools/validation-scratch/omni-suite/check_deps_HEAD.sh
$ OMNI_TEST_FAKE_LLM=1 OMNI_TEST_FAKE_PANDOC=1 OMNI_DOCTOR_SKIP_PDF=1 \
    bash 99-Tools/validation-scratch/omni-suite/check_deps_HEAD.sh
[INFO]  Checking Python version …
RC_HEAD=49
```

7 项检查里**后 6 项从未执行**，没有 `[ERR]`、没有原因、没有任何提示。根因链（三环，缺一不成立）：

1. `scripts/check_deps.sh:36` `PYTHON_BIN="${PYTHON_BIN:-python3}"` + `:37` 的 `command -v` 守卫——Git Bash 下 `python3` **是存在的**（`%LOCALAPPDATA%\Microsoft\WindowsApps\python3`，Microsoft Store 的 execution-alias 占位程序），所以「找不到 python3」这条分支永远不走；
2. `:41-43` 真的去执行它 → 占位程序不执行任何代码，直接返回 **49**；
3. 脚本是 `set -euo pipefail`，而这三行是**赋值语句里的命令替换**——命令替换失败会被 `set -e` 直接终止脚本。于是「环境坏」被翻译成「脚本无声退出」。

这属于 `scenarios/STANDARDS.md` 所禁止的那类失败：**不是失败，也不是通过，而是看起来跑过了**。同一份陈旧模式在 `scripts/setup_dev.sh:116-123` 也有，但那里 **不是缺陷**——该脚本 L97-104 有 Windows OS 守卫，会先明确报错并把人引到 `setup_dev.ps1`。这也正是本轮只改 doctor 侧的原因。

### 15.2 修复（3 个文件）

| 文件 | 改动 | 理由 |
|---|---|---|
| `scripts/check_deps.sh` | Check 1 重写：解释器改经 `scripts/pre_commit_python.sh` 解析（项目 venv 的 `bin/` 与 `Scripts/` 两种布局 → 系统 `python`/`python3`/`py`，逐个真跑 `-c ''` 探测）；`PYTHON_BIN` 显式覆盖保留；解析不到时**红并给三条出路**（`setup_dev.sh` / `setup_dev.ps1` / `PYTHON_BIN`） | 复用仓库既有的单一解析器（`.pre-commit-config.yaml:26-36` 已把这条规则写成注释；`docs/dev/validation-loop-log.md:30` 把它定为常设约束），不再出现第 2 份"裸 python3"实现 |
| `Makefile` | `doctor` 第二条：`@python3 scripts/check_module_entry.py` → `@bash scripts/pre_commit_python.sh scripts/check_module_entry.py` | 同一缺陷的第二处：本机 `python3` 不存在（PowerShell/CMD 下 rc=9009），先修复 `check_deps.sh` 仍会在下一行失败 |
| `.github/workflows/doctor.yml` | `continue-on-error: true` → `false`，并把「一周绿后翻」的旧注释改写成**实际依据** | §3.5 收窄项 #2 |

### 15.3 验证：同环境前/后对照 + 跨平台可达性

修复后（同一条命令、同一组 env）：

```
[OK]    Python 3.13.5
[OK]    LLM API key: skipped (OMNI_TEST_FAKE_LLM=1)
[OK]    pandoc: skipped (OMNI_TEST_FAKE_PANDOC=1)
[OK]    WeasyPrint libs: skipped (OMNI_DOCTOR_SKIP_PDF=1)
[OK]    dotnet: /c/Program Files/dotnet/dotnet
[WARN]  OPP_MCP_ALLOWED_DIRS: not set (fine for CLI use, required for MCP server)
[WARN]  ORF_MCP_ALLOWED_DIRS: not set (fine for CLI use, required for MCP server)
[OK]    Suite structure: all key files present

[WARN]  PASSED with 1 warning(s) — review above
RC_WORKTREE=0
```

`make doctor` 第二条（本机 `make` 未安装，两条命令逐条等价实跑）：

```
check_module_entry (root: D:\贯维\Omni_Suite)
Omni_Pre_Processor: entry=...\Omni_Pre_Processor -> realpath=...\Omni_Pre_Processor
  HEAD 3f92ee0  dirty 1
  WARNING: 1 tracked change(s) in the module worktree
Omni_Localizer: ... HEAD c0c3cb6  dirty 0
Omni_Re_Formatter: ... HEAD d14e0c8  dirty 0

check passed: module entries resolve to their clones.
ENTRY_CHECK_EXIT=0
```

（`dirty 1` 是 warning 而非失败——脚本契约明确「dirty is a WARNING, never a failure」。）

对照结论：**前 = 1 行输出 + 静默 49；后 = 7 项检查全跑到 + exit 0**。

### 15.4 转阻塞的依据（含不可验证项）

旧注释的前置条件是「绿了一周后翻 false」。该条件**本轮无法在本机核实**，如实记录：

- `gh` 未安装（`gh auth status` → 命令不存在）；
- `api.github.com` 匿名配额（60/h/ IP）已耗尽，两次都是 `API rate limit exceeded for 153.254.103.229`；
- 直连 `github.com` 超时（连 badge SVG 都取不到）。

所以转阻塞的依据是**静态枚举 + 同环境本机复现**，不是 CI 运行历史：

| 检查 | CI（`ubuntu-latest` + workflow 里那 3 个变量）下的结果 |
|---|---|
| 1 Python ≥3.13 | workflow `setup-python@v5 python-version: 3.13`；解析器落到 layer 3 的 `python` → OK |
| 2 keys / 3 pandoc / 4 WeasyPrint | 被 `OMNI_TEST_FAKE_LLM` / `OMNI_TEST_FAKE_PANDOC` / `OMNI_DOCTOR_SKIP_PDF` 跳过 |
| 5 md2pptx·dotnet / 6 MCP dirs | 仅 `WARN`；脚本契约是 `FAILURES>0` 才 exit 1，警告不触发 |
| 7 suite files | 5 个文件全为 `100644` 且随 checkout 到位（`git ls-files --stage` 实测） |
| `make doctor` 第二条 | **本仓库未跟踪模块入口**（`git ls-files Omni_Pre_Processor Omni_Localizer Omni_Re_Formatter` 实测为空）→ CI 里模块缺席 → `check_module_entry.py` 自身 skip → exit 0 |

残留风险：若 CI 上出现本表未枚举到的失败，doctor 会**显式红并指明是哪一项**——这正是本轮修复的直接目标（把"看起来跑过了"换成"要么真过、要么真红"）。`CHANGELOG.md:30` / `:231` 里 `continue-on-error: true` 的表述**保持不动**：那是历史条目的当时状态，改写反而失真。

### 15.5 本轮遗留（不伪装为已解决）

| 项 | 状态 |
|---|---|
| 「根目录不得出现样本文件」守卫（§13.4 第 3 行） | **已于第九轮落地，见 §17** |
| 报告 §3.3 `extend-exclude`、§3.4 `sys.path` 注入 / `mcp_bridge.py` | §3.3 **已于第十轮处理，见 §18**；§3.4 **已于第十一轮处理，见 §19** |
| `coverage_audit.py` 无友好降级 | **已于第十二轮处理并更正判断，见 §20.2**（原有逐模块 SERVER ERROR 行；只补一行 ROOT CAUSE 摘要） |
| 报告 §5 #2 Phase 2（外部索引 403）、#8（tier-2 真 LLM 复验） | 外部阻塞／待 key，不可伪绿 |

---

## 十六、第八轮：两项测试漂移修复（Windows 参数化 id / 平台反向 xfail）（2026-09-17）

§15 收尾后跑受影响的三个测试文件，暴露两项**既有**红测（均与本轮 4 个改动文件无关，定性见 16.3）。

### 16.1 `artifact_dir` 把参数化 id 当目录名 → Windows `WinError 123`

复现（`tests/test_doc_inventory.py` 的模块文档 claim 用例）：

```
ERROR tests/test_doc_inventory.py::test_check_rejects_module_doc_stale_tool_claim[Omni_Localizer/docs/ARCHITECTURE.md-ol-8 tools, all in `TOOL_REGISTRY`:]
tests\conftest.py:279: in artifact_dir
    test_dir.mkdir(parents=True, exist_ok=True)
E   OSError: [WinError 123] 文件名、目录名或卷标语法不正确。:
    '.../test_doc_inventory__test_check_rejects_mo..._8tools,allin`TOOL_REGISTRY`:'      ← 反引号 + 冒号
```

根因：`tests/conftest.py` 的 `artifact_dir`（autouse 链路 `_copy_component_logs_to_artifact_dir` 依赖它，故**每个**用例都会建目录）把 `request.node.nodeid` 直接当目录名，只替换了 `::` `/` `.py` `[` `]` 空格 —— 而参数化 id 可以含**任意**字符。`MODULE_DOC_STALE_CASES` 里那条待检 claim 原文带反引号与结尾冒号，NTFS 不允许 `:`，于是 **Linux/CI 永远绿、Windows 上必然红**。

修复（`tests/conftest.py`，入口处收敛一次）：

```python
safe_id = re.sub(r'[<>:"\\|?*`\x00-\x1f]+', "_", safe_id).strip("._") or "test"
```

覆盖 NTFS 全部非法字符 `<>:"/\|?*` + 控制字符 + 反引号，并处理「不得以点/空格结尾」；`\w` 保留中文（产物目录本就 `gitignore`，见 `.gitignore:82`）。**不改**参数化 id 本身——id 是给人看的断言说明，不该为文件系统让路。

验证：修复前 `1 failed, 36 passed, 1 error` → 修复后 **`38 passed`**（同一条命令）。已复核无其它消费者依赖目录命名（`grep safe_id` 仅命中 conftest 自身，无任何用例断言该命名方案）。

### 16.2 OPP `test_security.py` 平台门：suite 侧断言过期

`tests/test_phase7_root_test_isolation.py::test_security_windows_test_uses_xfail` 要求 OPP 该文件**必须**含 `@pytest.mark.xfail` 且**不得**含 `@pytest.mark.skipif`。该断言写死于 **2026-07-03**（`c004359`）；OPP 在**今天** `3f92ee0` 把它改成 `skipif(os.name == "nt")`，并在 docstring 里写明理由。

先独立复核 OPP 的理由是否成立（不轻信注释）：

- 用例参数全是 POSIX 目录 `/etc` `/usr` `/var` `/System` `/Library`；
- `Omni_Pre_Processor/src/opp/utils/security.py:24-34` 的 `SYSTEM_DIRS` 里**确有** `/etc` 等；
- 故在 POSIX 上 `validate_path("/etc/some/file.txt")` 必然命中 system-directory 拦截 → **该用例在 POSIX 上本就通过**；
- 而 marker 是 `xfail(os.name != "nt")` → POSIX 上恒为 XPASS（默认 `strict=False` 不计失败，纯噪音），Windows 上 marker 反而失效。

**方向确实写反** → OPP 的修正是对的，过期的是 suite 侧断言。

修复：把断言从「marker 叫什么名字」改成守 P7-T1 真正要防的两条不变量 ——

| 不变量 | 断言 |
|---|---|
| 方向写反的平台 xfail 不得回归 | 只在**生效的 marker 行**里搜 `os.name != "nt"`（不看 docstring 散文，OPP 的说明里正引用了旧写法） |
| 跳过 ≠ 放弃覆盖 | 必须保留 `def test_windows_paths_on_unix` 作为被跳过平台的反向补位用例 |
| 跳过必须显式限定平台 | 若出现 `skipif`，必须写明 `os.name == "nt"`，不得无条件跳过 |

可证伪性自检（`STANDARDS.md` 对 `expect` 的要求：必须能被证伪）：

```
regressed sample -> True     # @pytest.mark.xfail(os.name != "nt", reason="x")
current sample   -> False    # 「这里原本是 xfail(os.name != "nt", ...)」这类说明不算
plain xfail      -> False    # @pytest.mark.xfail(os.name == "nt", ...) 合法
```

### 16.3 反例澄清：本机 77 个 MCP 执行型失败**不是**本轮回归

为扩大验证面，同机跑 `tests/{observability,error_scenarios,validation,distributed_tracing}` → `77 failed, 504 passed`。定性证据（非推测）：

```
tests\error_scenarios\test_exit_code_matrix.py:72: in _run
    return subprocess.run(
        cmd = ['D:\\贯维\\Omni_Suite\\.venv_ol\\bin\\opp', ...]
```

即「在 Windows 上直接执行 `.venv_ol`（Linux venv）的 console script」→ `WinError 1920`。这是 `docs/dev/validation-loop-log.md:29` 早已记录的已知限制（原生 Windows 上拿执行型证据必须走 WSL），与 `artifact_dir` 命名毫无关系，且**在本轮改动之前就存在**。故本轮不把它算作回归，也不伪绿。

### 16.4 本轮遗留

| 项 | 状态 |
|---|---|
| 「根目录不得出现样本文件」守卫（§13.4 第 3 行） | **已于第九轮落地，见 §17** |
| 报告 §3.3 `extend-exclude`、§3.4 `sys.path` 注入 / `mcp_bridge.py`、`coverage_audit.py` 友好降级 | §3.3 **已于第十轮处理，见 §18**；§3.4 **已于第十一轮处理，见 §19**；coverage_audit **已于第十二轮处理，见 §20.2** |
| 报告 §5 #2 Phase 2（外部索引 403）、#8（tier-2 真 LLM 复验） | 外部阻塞／待 key，不可伪绿 |
| 4 个 `.venv_ol` 依赖测试目录在原生 Windows 上不可执行（77 failed） | 环境限制，已由 loop-log 记录；CI（Linux）为准 |

---

## 十七、第九轮：根目录样本守卫落地（§3.7 的长期钉子）（2026-09-17）

§3.7 把 4 个样本搬出根目录（仓库卫生维度当时是全报告最低分 42/100），但**没有任何机制阻止它们回来**。
本轮按 §14.3 给出的落点补上守卫，并把「门禁必须真的触发」这条 §14.2 的教训一并适用于它。

### 17.1 落点（两处，各司其职）

| 落点 | 作用 | 触发时机 |
|---|---|---|
| `scripts/doc_inventory.py` 新增 `check_root_samples()`（挂在既有 stray 检查家族，紧跟 `check_stray`） | 只扫**套件根**（非递归）的文档类后缀 `.doc/.docx/.odt/.epub/.msg/.pdf/.ppt/.pptx/.rtf/.xls/.xlsx`，命中即 `exit 1` 并指名文件 | `pre-commit` 的 `omni-doc-inventory` 钩子 + `make doc-inventory-check` |
| `tests/test_doc_inventory.py` 新增 4 个用例 | ① 根目录样本 → `exit 1`；② fixture 目录内的样本**不受影响**；③ 后缀集合无缺口；④ **对真实仓库**的断言（CI `pytest tests/ -m "not nightly"` 会跑到） | pytest（本地 + CI） |

**为什么是「根目录 + 非递归」**：fixture 本来就该住在 `scenarios/_fixtures/`（被跟踪）与 `test_fixtures/`（本地、已 `gitignore`）。递归扫描需要维护这两个目录的允许清单，一旦新增 fixture 目录就会腐化 —— 这正是报告 §13.4 里那些「迁移完就没人再管」的坑。根目录的合法内容只有配置文件与 Markdown。

### 17.2 让它真的触发（不是又一个空转门禁）

原 `omni-doc-inventory` 的 `files:` 正则不含任何文档后缀，因此「只 `git add` 一个样本」的提交**匹配不到任何分支** → 钩子不运行 → 守卫形同虚设（与 §14.2 修掉的三条空转正则同一失败模式）。故在正则尾部追加 root-only 分支：

```
|[^/]+\.(doc|docx|odt|epub|msg|pdf|ppt|pptx|rtf|xls|xlsx))$
```

**同族修复（同一缺陷类的剩余三处）**：`Makefile` 的 `doc-inventory` / `doc-inventory-check` / `entry-check`
三条目标也硬编码裸 `python3` —— 与 §15.1 的 `make doctor` 完全同因（Git Bash 下命中 Microsoft Store
占位程序 → `exit 49`，且**零输出**）。三条一并改走 `scripts/pre_commit_python.sh`：

```
--- 旧写法对照：裸 python3 ---
$ python3 scripts/check_module_entry.py
RC_OLD_PYTHON3=49                      ← 一行输出都没有
--- 新写法：doc-inventory-check ---
check passed: source truth matches claims, no stray files, inventory fresh.   RC=0
--- 新写法：entry-check ---
check passed: module entries resolve to their clones.                        RC=0
```

至此 `git grep -n python3 -- Makefile` 为空 —— Makefile 里不再有裸 `python3`。

### 17.3 验证：可证伪性四路证据（真实仓库实跑）

```
1) 守卫正样例（无样本）      -> "Sample files in suite root: none -> ok"        RC=0
2) 注入根目录样本            -> "Sample files in suite root: _probe_root_sample.docx -> FAIL"
                                "check FAILED (1 issue(s)): suite root contains 1 document
                                 sample(s): _probe_root_sample.docx — move them into
                                 scenarios/_fixtures/ (tracked) or test_fixtures/ (gitignored)"
                                                                              RC=1
3) 样本放进 test_fixtures/   -> check passed                                  RC=0
4) files: 正则逐路径判定（re.search，与 pre-commit 同语义）
     '_probe_root_sample.docx'                     matched=True  want=True   OK
     'leftover.pdf'                                matched=True  want=True   OK
     'scenarios/_fixtures/haier_ch2_zh.docx'       matched=True  want=True   OK
     'test_fixtures/zh/slim.docx'                  matched=False want=False  OK
     'docs/project-health-report-2026-09-17.md'    matched=True  want=True   OK
```

第 2 路是本轮最关键的一条：**守卫在真实仓库上确实会红**，而不是「加了但永远不会说话」。第 3 路证明 fixture 目录不误伤。
pytest 侧：`pytest tests/test_doc_inventory.py -q` → **32 passed**（含新增 4 例）。

### 17.4 本轮遗留

| 项 | 状态 |
|---|---|
| 报告 §3.3 `extend-exclude` 排除 `extractors/ ol_buses/ converters/` | **已于第十轮处理并更正因果，见 §18** |
| 报告 §3.4 `sys.path` 注入 / `scripts/mcp_bridge.py` 职责重叠 | **已于第十一轮处理（含 mcp_bridge 过期结论更正），见 §19** |
| `coverage_audit.py` 无友好降级 | **已于第十二轮处理并更正判断，见 §20.2**（原有逐模块 SERVER ERROR 行；只补一行 ROOT CAUSE 摘要） |
| 报告 §5 #2 Phase 2（外部索引 403）、#8（tier-2 真 LLM 复验） | 外部阻塞／待 key，不可伪绿 |

---

## 十八、第十轮：§3.3 落地（清除核心转换代码的潜伏债 + 更正因果）（2026-09-17）

### 18.1 先更正 §3.3 的因果判断（本报告的自我修正）

报告原文的判断是「`extend-exclude` 让最核心的格式转换代码不在检查范围内」。**这个因果是错的**，本轮取证推翻了自己：

| 事实 | 证据 |
|---|---|
| `.gitignore:6-8` 忽略 `Omni_Pre_Processor/`、`Omni_Localizer/`、`Omni_Re_Formatter/`（三个子仓库是独立 git 仓库） | `git check-ignore -v` 三条全部命中 `.gitignore:6/7/8` |
| ruff 默认 `respect_gitignore = true` | `ruff check --show-settings <OPP 文件>` → `file_resolver.respect_gitignore = true` |
| 因此 `ruff check .`（全树）**从来不遍历三个子仓库** | 全树 F 运行 80 行输出里 `extractors` 命中 0 次，路径样例全是套件层的 `eval/ scenarios/ scripts/` |
| `extend-exclude` 对**显式传入的路径**不生效（ruff 默认 `--no-force-exclude`） | 同一文件分别带配置与 `--isolated` 运行，findings 完全一致 |

**真正的因果**：那三条 `extend-exclude` 是**永不生效的死配置**；而子仓库源码的现实覆盖是——

| 调用方式 | 是否覆盖 `Omni_*/src/**` |
|---|---|
| `ruff check .`（`make lint`） | **否**（被 gitignore 挡住） |
| pre-commit ruff 钩子（暂存文件 = 显式路径） | 是 |
| CI `ruff check --select F <changed_py.txt>` | 是 |

所以 `extractors/` 的存量债之所以长期存活，不是「被排除」，而是**只被「改动文件」门禁覆盖**——没人动它，就没人看见它（与 §3.3 收窄项 4 同一机制）。

### 18.2 实测规模（ruff 0.15.11，仓库 pin 的版本）

34 条，**全部集中在 OPP `src/opp/extractors/`**（21 个文件）：
`I001`×14、`N806`×8、`B007`×4、`F401`×2、`N803`×2、`UP015`×2、`UP032`×1、`F541`×1。

OL `ol_buses/` 与 ORF `converters/` 在这套规则下**0 条**——因为这两个子仓库各自的 `pyproject.toml` 带 `[tool.ruff]` 且只 `select = ["E","F"]`，配置解析到的是子仓库那份，不是套件根这份（OPP 未声明 `[tool.ruff]`，才落到根配置）。
注：全局 ruff 0.16.8 会多报 20 条（`UP045`×6、`B023`×4、`UP035`/`UP037`/`UP043` 等新版规则）——**门禁按 pin 版本判定**，故以 34 为准；0.16.8 的增量已在下方遗留项登记。

### 18.3 处置与验证

- `pyproject.toml`：删除三条死配置（`docker`/`build`/`dist` 等保留）。
- OPP `src/opp/extractors/`：18 条自动修 + 16 条手修（详见该仓库 commit `f3c1739`）。其中
  `F401`×2 不是死导入——`tests/test_html_extractor_split.py:28-29` 用 `hasattr` 断言这两个可用性开关可从本包取到，属**再导出契约**，故用冗余别名而非删除。
- 复核后落地（不靠猜）：`W_NS/WP_NS/A_NS/R_NS/MC_NS` 全部是函数局部/参数，无模块级定义、无外部导入方、**所有调用点均为位置传参**，故参数改名不会影响关键字调用方。

验证：

```
ruff check src/opp/extractors     (pinned 0.15.11)  ->  Found 0 errors
零回归 A/B（stash 前后跑同一批受影响用例）
  A) 带改动：  7 failed, 13 passed, 2 skipped
  B) HEAD：    7 failed, 13 passed, 2 skipped      ← 完全一致
OPP 全量：1035 passed, 10 failed（10 个失败已用同一 A/B 证明在 HEAD 上同样失败）
```

那 10 个失败的定性：`.venv_win` 未装 `nbformat` 等可选依赖（`python -c "import nbformat"` → `ModuleNotFoundError`），属本机环境缺口，非本轮引入。

### 18.4 本轮新发现（未处置，登记备查）

**三个子仓库的本地 git 钩子只有 secrets 类**：OPP `.git/hooks/pre-commit` 是手写脚本（无 pre-commit-framework 标记），其 `.pre-commit-config.yaml` 只声明 `gitleaks` + `check-secrets`。即：**lint/test 门禁只存在于套件侧，且只覆盖 changed files**；子仓库内的提交没有任何 lint 门禁。这与 §18.1 的机制叠加，正是 `extractors/` 债长期存活的土壤。

### 18.5 本轮遗留

| 项 | 状态 |
|---|---|
| ruff 0.16.8 比 pin 版本多报的 20 条（`UP045`×6、`B023`×4 等） | 未处理；`B023`（闭包捕获循环变量）是真实 bug 类，建议升级 pin 时同步清 |
| 子仓库侧无 lint/test 钩子（§18.4） | **已于第十三轮处理，见 §21**（OPP 补 F 类 lint 门禁；OL 固定 ruff 版本；ORF 与 lock 一致不动）；§18.4「门禁只在套件侧」的结论已被 **§21.1 更正** |
| 报告 §3.4 `sys.path` 注入 / `mcp_bridge.py` 职责重叠 | **已于第十一轮处理，见 §19** |
| `coverage_audit.py` 无友好降级 | **已于第十二轮处理并更正判断，见 §20.2**（原有逐模块 SERVER ERROR 行；只补一行 ROOT CAUSE 摘要） |
| 报告 §5 #2 Phase 2、#8（tier-2 真 LLM 复验） | 外部阻塞／待 key，不可伪绿 |

---

## 十九、第十一轮：§3.4 收口（更正过期结论 + 把承重接口写成契约）（2026-09-18）

### 19.1 更正：报告 §3.4 的 `mcp_bridge.py` 是过期结论

报告 §3.4「代码重复」段称 `scripts/mcp_bridge.py` 与各模块原生 MCP server 职责重叠。实测：

```
Test-Path scripts/mcp_bridge.py            -> NOT PRESENT
git log --oneline -1 -- scripts/mcp_bridge.py
                                          -> 5d163d4（2026-06-22）
```

且 `5d163d4` 的 commit message 自己的 "### Deleted" 列表第一行就是
`scripts/mcp_bridge.py (245 lines, was a workaround for fastmcp stdio bug)`。
即：**该文件在报告成文（2026-09-17）前近三个月就已删除**。§3.4「职责重叠」这一半不成立，属于报告对旧印象的转述而非实测——与本报告 §3.3、§18.1 同类错误（本轮再次证明「不得转述、必须实测」这条标准的必要性）。

### 19.2 另一半（`sys.path` 注入）比报告描述的更宽

报告只举了 `dispatch.py` 与 `coverage_audit.py` 两处。实测耦合面（子仓库被 `.gitignore` 挡住，`Grep` 默认看不到——须用 `Select-String` 或直接读文件）：

| 子仓库 | 承重的**私有**名字 | 形状 | 套件侧消费者 |
|---|---|---|---|
| OPP | `opp.mcp.server._TOOL_SCHEMAS` | `list[dict]`，每条含 `"name"` | `coverage_audit.py:120`、`tests/test_docs_mcp_tool_consistency.py:23`、`tests/test_docs_claude_md_tools_exist.py:18`、`doc_inventory.py`（**按源码文本正则计数**） |
| OPP | `opp.mcp.server._TOOL_DISPATCH` | `dict` 名→callable | `doc_inventory.py`（同上） |
| OL | `ol_mcp.tools.TOOL_REGISTRY` | `dict` 名→`(callable, InputModel, str)` | `coverage_audit.py:123`、`dispatch.py:534`、两个 docs 一致性测试、`doc_inventory.py` |
| ORF | `orf.mcp.server._TOOL_DISPATCH` | `dict` 名→callable | `coverage_audit.py:131`、两个 docs 一致性测试、`doc_inventory.py` |

外加：约 60 个 scenario YAML 的 python 步骤 `sys.path.insert(0, "Omni_X/src")` 后直接
`from ol_mcp.tools import TranslateInput, translate_md_text` 之类（in-process agent-surface 模式），
以及 `tests/` 内多处同类导入。

**真正的缺陷不是耦合本身**（读活注册表比硬编码工具清单正确），而是**这个名字从未被写成契约**：
`CONTRACT.md`（0 处命中 `TOOL_SCHEMAS` / `TOOL_REGISTRY` / `注册表`）只讲数据交接，
子仓库维护者没有任何文档告诉他们「这几个下划线开头的名字是套件承重的」。
于是重命名会以一个看似无关的 ImportError 炸在别人的测试里 —— 这正是报告所说「静默打断」的来源。

### 19.3 处置：声明接口 + 把文档与代码锁在一起

1. **`CONTRACT.md` 新增 `## Suite ↔ Module In-Process Import Surface`**：接口表（模块 / sys.path 目录 / 导入名 / 期望形状）、必须同步更新的消费者清单、以及一条明确的变更规则；`## Breaking Changes` 末尾补一句把该接口纳入同一条 4 步流程（「这是契约破坏，不是内部重构」）。
2. **`tests/contract/test_contract_documentation.py` 新增两条测试**（该文件已被 CI `contract-tests.yml` 覆盖）：
   - `test_contract_declares_in_process_import_surface` —— 文档必须记载表中每个路径（漏一个就红，并提示改文档或改 `DECLARED_IMPORT_SURFACE`）；
   - `test_declared_in_process_import_surface_resolves` —— 每个路径必须真的能导入且形状符合承诺（`list[dict]` 带 `name` / mapping 且非空），失败信息**指名 CONTRACT.md 那一节**并列出该同步哪些消费者。

   两条测试互为补角：文档不能描述一个不存在的接口，接口也不能在无人知晓的情况下改名。

### 19.4 验证

```
pytest tests/contract/test_contract_documentation.py \
       tests/test_docs_mcp_tool_consistency.py \
       tests/test_docs_claude_md_tools_exist.py -q      ->  22 passed
pytest tests/contract/ -q --tb=no -rf                   ->  15 failed，全部 WinError 1920
                                                           （test_cli_help / test_mcp_io_contract /
                                                             test_mcp_schemas 里 spawn .venv_ol 的用例，
                                                             环境类，本轮未触碰这些文件）
doc_inventory --check                                   ->  先红后绿：
    FAIL: omni-docmap SKILL.md claims `CONTRACT.md` ~180 lines, actual is 224
    -> 同步该行数声明（并补一句接口职责）后 PASS
```

门禁先红后绿这一段本身是证据：doc-truth 的 Gate C（行数声明漂移）真的在守卫文档与文件的对应关系。

### 19.5 本轮遗留

| 项 | 状态 |
|---|---|
| 三个子仓库的本地 git 钩子只有 secrets 类（§18.4） | 本地钩子仍未接 pre-commit（候选）；但 §18.4「lint/test 门禁只在套件侧」已被 **§21.1 更正**——OL/ORF 的 CI 一直有 ruff |
| `coverage_audit.py` 无友好降级 | **已于第十二轮处理并更正判断，见 §20.2**（原有逐模块 SERVER ERROR 行；只补一行 ROOT CAUSE 摘要） |
| ruff pin 升级（0.16.8 多报的 `UP045`×6、`B023`×4 等） | 未处理 |
| 报告 §5 #2 Phase 2（外部索引 403）、#8（tier-2 真 LLM 复验） | 外部阻塞／待 key，不可伪绿 |

---

## 二十、第十二轮：完成度审计 + 第三处自我更正（2026-09-18）

### 20.1 逐条审计：报告结论 vs 当前状态

以「能证明完成的权威证据」为准，不看意图、不看记忆：

| 报告结论项 | 权威证据（实测） | 状态 |
|---|---|---|
| §5 #1 `99-Tools/` ignore | `git check-ignore -v 99-Tools/x.txt` → `.gitignore:85` | ✅ |
| §5 #2 PathValidator 三份实现 | Phase 1 已落地（ADR 0007 + parity 39 用例，第四轮）；**Phase 2 外部阻塞**：`uv.lock` 重生成遇索引 403 | ⛔ 外部 |
| §5 #3 `omo_loop.py` 死代码 | 已删（第九轮） | ✅ |
| §5 #4 `doc_inventory.py` 硬编码 `python3` | 改 `sys.executable` + 本轮再加 `pre_commit_python.sh` 路径 | ✅ |
| §5 #5 本地 Linux venv | `setup_dev.ps1` + `README` 入口 | ✅ |
| §5 #6 ruff pin 漂移 | pre-commit / CI / 文档统一 0.15.11 | ✅ |
| §5 #7 `PROJECT_STATUS.md` 过期 | 已刷新至 2026-09-17 | ✅ |
| §5 #8 T13-01/02 质量门禁 | 代码已修（第九轮）；**tier-2 复验无本地 key** | ⛔ 外部 |
| §5 #9 `test_artifacts/` 被跟踪 | 复核为非缺陷（有意 force-add 的 fidelity 基准） | ✅ |
| §5 #10 mypy 范围 | 放宽到 `omni_metrics omni_suite omni_mcp`（23 文件全绿） | ✅ |
| §3.2 R2 suite 层路径策略漂移 | 4 份策略收敛 + `test_path_policy_parity` 39 用例 | ✅ |
| §3.3 `extend-exclude` | 三条死配置删除 + OPP `extractors/` 34 条清零（`f3c1739`），见 §18 | ✅ |
| §3.4 `sys.path` 注入 / `mcp_bridge` | 承重接口写成契约 + 两条绑定测试；`mcp_bridge` 过期结论更正，见 §19 | ✅ |
| §3.5 收窄项 #1–#4 | mypy 已放宽；doctor 已转阻塞（§15）；ruff 已统一；门禁「只覆盖 changed files」的**机制面**已实盘化（§14.2 三条死正则 + §17.2 新增 root-sample 分支） | ✅ |
| §3.5 `coverage_audit.py` 无友好降级 | 见 20.2（先更正自己的误判，再补一行根因摘要） | ✅ |
| §3.7 仓库卫生（42/100） | 样本迁移 + 根目录守卫（§17） | ✅ |

结论：**报告项已无「本机可做而没做」的遗留**；剩余两项为外部阻塞（索引 403 / 无 LLM key），按 `STANDARDS.md#fallbacks-never-evidence` 不得伪绿。

### 20.2 第三处自我更正：`coverage_audit.py` 并非「无友好降级」

我在第十一轮的汇报里说它「把传输层没跑起来误诊成 41 个场景缺覆盖」。**这句是错的**，成因是我当时只看输出尾部 20 行。完整输出（本轮实测）：

```
  execution: 0/41 tools execution-backed; 41 diverged
    SERVER ERROR (ol): server failed: Client failed to connect: [WinError 1920] …
    SERVER ERROR (omni_mcp): …
    SERVER ERROR (opp): …
    SERVER ERROR (orf): …
  MISSING (41) — not execution-backed (an agent-user would hit it blind)
  VERDICT (execution-backed): 0/41 passed, 41 missing -> FAIL (missing > 0), exit 1
```

即：**逐模块根因行一直在**（`coverage_audit.py:440-441`）。而 `missing` 计数「不放过起不来的服务器」也是**刻意的 fail-closed 设计**——`tests/validation/test_coverage_audit.py:9-11` 明写「a deliberately broken tool must make the audit fail」。所以报告 §3.5 那半句「无友好降级」不准确，而「降级」本身也不该做（降级=伪绿）。

本轮只做**诊断性**的增量，不动判定：当**所有**声明模块的服务器都没起来时，在 SERVER ERROR 行后补一行

```
    ROOT CAUSE: every module server failed to start — a transport/environment problem,
    not a scenario-coverage gap. The suite venv must be runnable here (on native Windows
    .venv_ol is a Linux venv: run under WSL or CI — docs/dev/validation-loop-log.md).
```

只有部分模块失败时改用限定措辞（`N of M module servers failed to start`）——因为那**不能**排除真实覆盖缺口，把话说满会变成另一种误导。

### 20.3 验证

```
pytest tests/validation/test_coverage_audit.py -q       ->  26 passed, 1 failed
   那 1 个 = test_real_execution_marks_suite_tools_passed（需要真起服务器）
   零回归 A/B（stash 前后同一用例）：
     A) 带改动： 1 failed（server_errors != {}，WinError 1920）
     B) HEAD：   1 failed（完全相同的断言差异）
真实运行（.venv_win）：
   ROOT CAUSE 行已出现在 VERDICT 上一行；VERDICT 仍为 FAIL … exit 1（fail-closed 不变）
```

### 20.4 遗留

| 项 | 状态 |
|---|---|
| §5 #2 Phase 2（外部索引 403）、§5 #8（tier-2 真 LLM 复验） | **外部阻塞**，需外部状态变化，不可伪绿 |
| 三个子仓库的本地 git 钩子只有 secrets 类（§18.4） | **主体已于第十三轮处理，见 §21**（OPP 补 lint 门禁 + OL 固定版本 + 结论更正）；pre-commit 本地安装/钩子写法仍待定（§21.4） |
| ruff pin 升级（0.16.8 多报的 `UP045`×6、`B023`×4 等） | 未处理（候选下一轮） |
| `coverage_audit` / `contract` 在本机的执行型失败（WinError 1920） | 环境限制，CI（Linux）为准 |

---

## 二十一、第十三轮：子仓库门禁补齐 + 第四处自我更正（2026-09-18）

### 21.1 第四处自我更正：子仓库并非「没有 lint/test 门禁」

§18.4 与 §19.5 写「lint/test 门禁只存在于套件侧，且只覆盖 changed files」——**前半句是错的**。逐仓库实测（直接读各自的 `.github/workflows/`）：

| 仓库 | lint 门禁（本轮实测） | 处置 |
|---|---|---|
| OPP | **无 lint 步骤**；CI 只跑 pytest | 新增 `ruff check --select F src/`（pin `ruff==0.15.11`，与套件 pre-commit / CI 同版本） |
| OL | 有 `ruff check src/ tests/`，但 `pip install ruff` **未固定版本** | 固定为 `ruff==0.15.16`（= `Omni_Localizer/uv.lock` 实测解析版本） |
| ORF | 有 `ruff check src/orf/`，pin `ruff==0.15.14`，**与其 `uv.lock` 一致**（实测 lock `ruff` = 0.15.14） | **不动**（改它要动 `uv.lock`，正撞索引 403 的外部阻塞） |

§18.4 说对的是这一半：三个子仓库的**本地 git 钩子**确实只有 secrets 类（三份 `.git/hooks/pre-commit` 内容相同，是纯 bash + grep，只扫 staged 的密钥模式；且三仓库都未安装 pre-commit 框架）。错的是由此推出的「lint/test 门禁只存在于套件侧」——OL/ORF 的 CI 一直有 ruff，只是**版本未全部固定**、且**不在本地提交路径上**。§14.2 的「门禁只覆盖 changed files」同样只适用于**套件侧变更文件门禁**，不能推广成「子仓库无门禁」。

### 21.2 OPP：补上第一个 lint 门禁（此前完全没有）

落点 `.github/workflows/ci.yml`，范围刻意取 `src/` + F 类（pyflakes），理由写进 workflow 注释：

- F 是项目选定的「类 bug」底线（套件 pre-commit 对变更文件用的也是同一规则集）；
- `tests/` 有 **132** 条既有 F（含 1 个 `invalid-syntax`：`tests/fixtures/ipynb/sample.ipynb` 缺 `outputs` 字段），政策是不成批修既有债，故不纳入；
- `src/` 在套件全规则集（E,F,I,B,UP,N）下**清理后仍有 253 条**（见 21.3），全规则集门禁会先天红；清干净的 F 类才能开门即绿。

同轮把 `src/` 的 13 条 F 清零：11 条未使用导入（F401，自动修）+ 2 条死局部变量（`commands/batch.py` 的 `detected_format`、`logger.py` 的 `json_mode`，手修；均为纯读、无副作用、无外部引用）。

### 21.3 本轮实测数字（可复现）

在套件根配置下 in-place 测量。先用本机可得的 ruff **0.15.21**，随后又从 wheel 装到 pin 的 **0.15.11** 复核（见 21.6），**两者数字完全一致**：

```
OPP src 全规则集 E,F,I,B,UP,N
  f3c1739（清理前）: 265 = 102 E501 + 39 B904 + 38 I001 + 32 UP045 + 24 E402
                          + 11 F401 + 8 UP015 + 3 UP037 + 2 UP035 + 2 F841
                          + 1 UP024 + 1 N818 + 1 N806 + 1 B905
  清理后          : 253 = 同上去掉 11 F401、2 F841，且 I001 38 -> 39
                         （删导入后有一个 import block 变成待排序）
OPP src   F 类: 13 -> 0
OPP tests F 类: 132（不动；门禁不取 tests/）
```

`265 → 253` 与 §20 之前的记录一致：13 条 F 清掉、1 条 I001 因导入块重排而出现。无论取哪个数，全规则集都先天红，故门禁取 F 类。

### 21.4 `.pre-commit-config.yaml` 的解释器修复：先试错 `language: python`，改用套件解析器

三个子仓库的 `check-secrets` 钩子原先写 `entry: python3 …` + `language: system`（Windows 下 `python3` 命中 Microsoft Store 占位程序、exit 49）。本轮试图改成 `entry: python …` + `language: python`，**验证未通过，故该文件留在工作树未提交**（本报告不把它记为已完成）：

- 实测（离线、仅含该钩子的最小 config）：`language: python` 会让 pre-commit 对 `repo: local` 执行 `python -m pip install .`——对子仓库本身做构建 + 隔离安装。本机索引 403 → 取不到 `setuptools>=40.8.0` → **环境创建失败**，钩子根本跑不起来。
- 这恰好背离该钩子的设计目的（其 docstring 明写：gitleaks 拉不下来时它仍应能跑）。改成 `language: python` 会把它从「离线可用的 stdlib 扫描」变成「需要访问索引 + 把整个子仓库依赖装进钩子环境」。
- 更早那次 `subrepo_hook_out.txt` 其实没走到这一步：它在 pre-commit 拉 gitleaks 仓库时就被网络断连挂掉（`Connection was reset` / `Could not connect to server`），且其 `python3` 对照组取的是 `tail` 的 rc 而非 `python3` 的——那次运行不构成证据。
- 事实澄清：子仓库**真实生效的提交钩子**是那份手写 bash 脚本（纯 grep，无 python3），所以**今天的真实提交路径不受 `python3` 缺陷影响**；有问题的只是尚未生效的 pre-commit 配置。
- 候选修法：(a) 回退到 `language: system` + `python3`；(b) 复用套件的 `scripts/pre_commit_python.sh` 解释器解析器；(c) 先给三仓库装 pre-commit（§2.7 的自发现问题）。

**处置（用户确认后采纳 b）**：三个子仓库各新增 `scripts/pre_commit_python.sh`（与套件同内容、同 md5 的副本，已核验），`check-secrets` 改为：

```yaml
entry: bash scripts/pre_commit_python.sh scripts/check-secrets.py
language: system
```

实测（离线、仅含该钩子的 config）：干净文件 → `Passed` / rc 0；写入一个 AWS 形状的假 key → 拦截 / rc 1（报 `[aws_access_key]`）。三仓库均已提交（见 21.5）。解析器按「项目 venv（`bin/` 与 `Scripts/` 两种布局）→ 系统 `python`/`python3`/`py`」逐个**真跑**探测，只需本地解释器、不需网络。注意：OL 仓库内已有 `.venv/`（Linux 布局），本机命中第 1 层；若该 venv 在某平台不可执行，解析器第 2 层会 fail-loud（刻意设计，不静默跳过）。候选 (c) 仍未做。

### 21.5 本轮落地的提交

| commit | 仓库 | 内容 |
|---|---|---|
| `7328591` | OPP | 新增 F 类 lint 门禁 + `src` 13 条 F 清零（9 文件：8 src + ci.yml） |
| `45225e0` | OPP | 更正 ci.yml 注释里的门禁范围数字（改用 pin 版复核） |
| `07b5e7f` | OL | lint 依赖从 unpinned 固定到 `ruff==0.15.16`（= uv.lock） |
| `32bc21a` / `f6c8f3f` / `2de67f3` | OPP / OL / ORF | `check-secrets` 改用套件解释器解析器（各新增 `scripts/pre_commit_python.sh`） |
| `b683f55` / `781bad2` | suite | 本报告 §21 |

### 21.6 附带发现：「索引 403」是本机镜像配置，不是外部阻塞

为复核 21.3 需要 pin 的 ruff 0.15.11，实测发现 403 的来源是**本机 pip 全局配置的 Tsinghua 镜像**，而非公网不可达：

```
pip config list                                              -> global.index-url='https://pypi.tuna.tsinghua.edu.cn/simple'
curl -o /dev/null -w '%{http_code}' https://pypi.tuna.tsinghua.edu.cn/simple/ruff/  -> 403
curl -o /dev/null -w '%{http_code}' https://pypi.org/simple/ruff/                    -> 200
pip download ruff==0.15.11 -i https://pypi.org/simple                                -> 下载成功
```

含义（**登记，不据此宣称 §5 #2 已完成**）：§5 #2 Phase 2 一直被记为「外部阻塞：索引返回 403」。该 403 只出现在**本机配置的镜像**上，公网 PyPI 可达且可下载。所以这更像**本地环境问题（镜像不可用）**，而非「外部状态」。切公网索引后 Phase 2 大概率可推进，但它要重生成 `uv.lock`、动跨仓库依赖，属独立任务；本轮只做登记，是否推进由用户定夺（且需先确认镜像 403 是否持续）。

---
*报告生成：2026-09-17 · 审计人：AI Agent（TraeCode）· 结论基于实测，非文档转述*
*第二十节追加：2026-09-18 · 完成度审计 + 第三处自我更正*
*第二十一节追加：2026-09-18 · 子仓库门禁补齐 + 第四处自我更正*
*第十九节追加：2026-09-18 · §3.4 收口 + 第二处因果更正*
*第十八节追加：2026-09-17（同日续做，第十轮）· §3.3 落地 + 因果更正*
*第十七节追加：2026-09-17（同日续做，第九轮）· 根目录样本守卫*
*第十六节追加：2026-09-17（同日续做，第八轮）· 两项测试漂移修复*
*第十五节追加：2026-09-17（同日续做，第七轮）· make doctor 静默失效修复 + doctor 门禁转阻塞*
*第十四节追加：2026-09-17（同日续做，第六轮）· 门禁实盘化 + 测试漂移修复*
*第十三节追加：2026-09-17（同日续做，第五轮）· §3.7 仓库卫生收尾*
*第十二节追加：2026-09-17（同日续做，第四轮）· R2 收口 + 门禁可用性*
*第十一节追加：2026-09-17（同日晚）· #2 Phase 1 落地与验证证据*
*第十节追加：2026-09-17（同日续做，第二轮）*
