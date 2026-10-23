# Omni Suite 代码美学与架构深度审阅

> **审阅日期**：2026-10-22
> **审阅方式**：实测（命令 + 原始输出 + 文件读取），**不以文档声明为结论依据**
> **审阅范围**：顶层 suite + OPP / OL / ORF 三个子仓库（4 个独立 git 仓库）
> **审阅维度**：代码美学（模块深度、命名、重复、层次）+ 氛围编程（agent 协作产物的沉积特征）
> **证据约定**：每条结论标注「实测」或「文档声称」；凡实测与声称不一致之处单独列出
> **与既有报告的关系**：本报告**不重复** [`docs/project-health-report-2026-09-17.md`](project-health-report-2026-09-17.md) 的健康度评分，专注其未覆盖的维度：模块深度、代码重复拓扑、声明与实现的偏离、以及"验证密度已过收益拐点"这一判断。差异清单见 [§七](#七与-2026-09-17-健康度报告的增量差异)

---

## 一、总体结论

**这是一个用验证密度换取可信度的项目，而它已经越过了这条曲线的收益拐点。**

工程纪律是本项目最突出的资产：122 个可执行场景、`STANDARDS.md` 单一判定基准、`known_gap` 反伪绿机制、`doc_inventory` 文档真相门禁 —— 多数同类项目连"错误码表"都做不到自动化校验。这些不是负债，应当保留。

但代码与文档的**当前形态**暴露了三个结构性问题：

1. **最该被验证的真相恰好不在门禁覆盖范围内。** 项目的核心卖点是 "verifiable truth"，而版本表、质量门数量、修复层数、工具总数这四类"会直接误导使用者"的数字，恰好全部游离在自动化校验之外。
2. **深度两极分化，中间层缺失。** 少数模块极深且干净（`family.py`、`artifact_assertions.py`、`loader.py`），大量文件极薄（345 个源文件中 75 个不足 40 行），且**没有一个共享内核**来吸收重复，于是每个模块各自长出相似的器官。
3. **只增不减。** 计划、脚本、抽象、文档、门禁都只做加法；从没有一次"删掉一半脚手架"的收敛动作。氛围编程的典型病理在此暴露无遗：生成物沉降、自指验证、声明漂移、施工现场化的仓库根目录。

**一句话建议**：下一阶段的价值不在"再加一个 gate"，而在**删掉一半脚手架，把真相收敛到三个地方**（`VERSION`/`pyproject.toml`、`CONTRACT.md` + `omni_suite/contract/models.py`、`scenarios/STANDARDS.md`），其余文档只做链接、不做复述。

---

## 二、这个项目在做什么（理解基线）

### 2.1 产品形态

三阶段文档本地化流水线：

```
source.docx
   │
   ├─ OPP extract ──▶ document.md / document.xlf / manifest.json / skeleton.zip / images.json
   │                   （Omni_Pre_Processor，14 种输入格式）
   ├─ OL translate ─▶ translated.md / translated.xlf
   │                   （Omni_Localizer，21 个 MCP 工具）
   └─ ORF backfill ─▶ result.<target_format>
                       （Omni_Re_Formatter，16 种输出格式）
```

### 2.2 真正的产品是"契约"，不是翻译器

三个模块彼此**完全独立**（各自 git 仓库、各自 PyPI 包、各自 CLI、各自 MCP server），它们之间**只通过文件通信**。`docs/ARCHITECTURE.md` §5 称之为 "Stateless design"，`CONTRACT.md` 把它写成版本化契约。

关键洞察：`CONTRACT.md` § "Suite ↔ Module In-Process Import Surface" 甚至把 suite 通过 `sys.path` 注入导入模块内部 registry 名字（`opp.mcp.server._TOOL_SCHEMAS`、`ol_mcp.tools.TOOL_REGISTRY`、`orf.mcp.server._TOOL_DISPATCH`）这种**隐式耦合**显式写进契约，并列出所有必须同步修改的消费者。

> **实测**：绝大多数同类项目会选择假装这种耦合不存在。此处把它写成契约条目，是本项目最成熟的架构判断之一。

### 2.3 双通道是显式取舍，不是"万能转换"

| 通道 | 语义 | 适用场景 |
|---|---|---|
| **MD** | 文本优先，布局容忍 | 跨格式、Web、电子书；支持全部 16 种输出 |
| **XLIFF** | 版式保真，同容器回注 | 合同/品牌文档；字体、浮动图、页边距必须原样 |

项目**刻意拒绝**做不到的事：PDF→XLIFF 硬阻断（ADR-0005）；跨格式 XLIFF 回填恒定失败。

`ACCEPTED_GAPS.md` 中对后者的一段解释尤其值得读：早期 `--force` 会产出"改了扩展名的源文件"（`cross.pptx` 被 `python-pptx` 拒开、`cross.epub` 缺 `mimetype`），**比报错更糟**；因此 `Orf_Re_Formatter#64` 移除了绕过逻辑，使跨格式恒定失败且不产出任何产物。

> **评价**：这种"宁可失败也不给假产物"的取舍，是整份代码库最值钱的气质。

---

## 三、设计哲学（从代码反推，不是从 README 抄的）

| # | 原则 | 代码中的落点 | 证据 |
|---|---|---|---|
| 1 | **文件即协议，进程无状态** | OPP 写完 `manifest.json` 即退出；ORF 只读文件。无共享 DB、无内存握手 | `docs/ARCHITECTURE.md` §5；`CONTRACT.md` |
| 2 | **深模块优先**（Ousterhout） | 少数模块把复杂度藏在极小接口后 | `.opencode/skills/omni-deep-modules/SKILL.md`；`ol_pool/router.py`（1555 行）对外仅 `translate/judge/profile` |
| 3 | **Schema 即契约，未知字段即错误** | 场景加载用闭合字段集校验，多写一个 key 直接失败 | `omni_mcp/validation/loader.py`（`_SCENARIO_FIELDS` / `_STEP_FIELDS` / `KINDS` / `LEVELS`） |
| 4 | **Fallback 永不作证据** | human-quality 场景在 fake 模式下判 `invalid`，`--allow-fake` 也救不了 | `omni_mcp/validation/engine.py::_fake_llm_reason` + `family.py`；`scenarios/STANDARDS.md#fallbacks-never-evidence` |
| 5 | **已知缺口必须被断言** | `known_gap` 在 scenario/steps 双层生效，由 `--check` 强制位置不变量 | `omni_mcp/validation/cli.py:258-314`；`ACCEPTED_GAPS.md` |
| 6 | **Agent 是一等用户（AX）** | MCP 是一等接口而非附属品；稳定错误码、`ping`、path allowlist、rate limit | `docs/methodology/agent-oriented-design-mindset.md`（vendored，带 checksum 与 diff 规则） |
| 7 | **可验证的真相** | 工具数、场景数、版本、归档标记、链接完整性全部机器校验 | `scripts/doc_inventory.py --check` |

### 3.1 最诚实的一页：`ACCEPTED_GAPS.md`

其开篇即规定："Anything NOT listed here is expected to have an automated invariant."（未列于此的缺口，应当已有自动化不变量兜底。）

这把"已知问题管理"从口头承诺变成了契约：**缺口不列出来，就等于缺陷**。这在同类项目中极为罕见，应当作为制度保留。

---

## 四、基础设施盘点（实测）

### 4.1 规模

| 区域 | 行数（`.py`） | 说明 |
|---|---|---|
| OPP `src/` | 14,825 | 14 种输入格式的抽取器 |
| OL `src/` | 22,493 | 最大模块，22 个 `ol_*` 子包 |
| ORF `src/` | 19,651 | 16 种输出格式的回写器 |
| 根 `omni_*` | 7,895 | `omni_suite` + `omni_mcp` + `omni_metrics` + `omni_security` |
| `scripts/` | **14,411** | 验证框架、nightly、矩阵、文档门禁 |
| **产品代码小计** | **~64,900** | 三模块 345 个源文件 + 根 `omni_*`；`scripts/` 单列 |
| OPP `tests/` | 20,848 | |
| OL `tests/` | 34,035 | |
| ORF `tests/` | 23,741 | |
| 顶层 `tests/` | **49,155** | 对应 7,895 行套件源码，**比例 6.2:1** |

> **观察 A**：`scripts/`（14.4k）比套件层产品代码（根 `omni_*`，7.9k）还大。
> **观察 B**：顶层测试（49.2k）是套件层源码（根 `omni_*`，7.9k）的 6.2 倍。这个比例本身对"验证即产品"的项目可以辩护，但它同时意味着**验证体系的维护成本已经超过被验证对象**。

### 4.2 形状分布

```
最大源文件（行）：
  1555  Omni_Localizer/src/ol_pool/router.py
  1523  Omni_Localizer/src/cli/translate_md.py
  1292  scripts/omo_loop.py
  1213  scripts/report_comparison.py
  1172  omni_mcp/validation/dispatch.py
  1165  scripts/doc_inventory.py
  1057  Omni_Re_Formatter/src/orf/channels/xliff2pptx.py
   917  Omni_Pre_Processor/src/opp/extractors/html/__init__.py
   893  omni_mcp/validation/engine.py
   875  Omni_Re_Formatter/src/orf/channels/xliff2docx/__init__.py
```

**345 个源文件中，75 个（22%）不足 40 行。**

> **观察 C**：深度两极分化，中间层缺失。少数文件极深、多数文件极薄，且没有共享内核吸收重复。

### 4.3 文档与场景

| 资产 | 数量 |
|---|---|
| `docs/**/*.md` | 55（本报告加入后 56） |
| 仓库根级 `*.md` | 25 |
| `.omo/plans/*.md` | 80+（仅 19 个入库，见 P4.3） |
| `scenarios/**/*.yaml` | 122（tier-1 108 / tier-2 13 / tier-3 1） |
| 验证框架 `scripts/validation/` + `omni_mcp/validation/` | ~9,300 行 |
| `test_*.py` 文件 | 519 |
| CI workflow | 7 |

---

## 五、美学上真正优秀的地方

先说好的，避免后续批评失真。

### 5.1 `omni_mcp/validation/family.py`（139 行）—— 全库最干净的模块

一个函数 `family_of()`、一个返回形状、一段说明优先级的 docstring。`engine.py` 与 `validation_report.py` 都从它导入，方向被注释固定：

> *"scripts/ is not a package, so the report imports these symbols FROM here — never the other way round."*

规则本身也干净：5 个 AGENT-SURFACE anchor + 7 个 HUMAN-QUALITY anchor，共 12 个常量，无配置、无分支、无优先级黑箱。

### 5.2 `scripts/validation/artifact_assertions.py` —— 声明式表驱动的真深模块

`AssertionFn = Callable[[Path, str, str, str], AssertionResult]` + 四张表（`HARD_SECURITY` / `OPP_STRUCTURE` / `OL_STRUCTURE` / `ORF_STRUCTURE`）。**加一条断言 = 改一行表**，而不是再写一个 if 分支。

### 5.3 `loader.py` 的 schema-as-contract

闭合字段集 + 未知 key 报错。这一条把"文档约定"变成了"类型系统"，直接消灭了"文档说可以但代码不认"的整类扯皮。

### 5.4 `known_gap` 的三层隔离

scenario 级 / step 级 / `--check` 位置不变量（`known_gap: true` 场景只能住在 `known-gaps/` 目录，且该目录下每个场景必须声明该标志）。**失败被记录、可见、但不阻塞，且不会被误读为通过。** 这是本项目最精巧的机制。

### 5.5 错误信息指向替代路径

跨格式 XLIFF 失败时提示 "use `orf apply-md`"，而不是只说 "not supported"。这是 agent 能自我恢复的前提，符合 AX 原则。

---

## 六、改进空间

按"债的类型"分层。**P0 是最讽刺的一类**：项目的核心卖点是真相，而真相本身在漂移。

---

### P0 — 真相债：门禁没覆盖最该覆盖的地方

#### P0.1 版本表已死，而门禁只覆盖三个文件

**实测**（`pyproject.toml`）：

| 组件 | 真实版本 |
|---|---|
| OPP | `0.10.0` |
| OL | `0.7.1` |
| ORF | `0.5.0` |
| suite | `0.5.0` |

**实测**（文档声称）：

- `docs/ARCHITECTURE.md:430-433` → OPP `0.9.1` / OL `0.7.1` / ORF `0.4.17` / suite `0.4.0`
- `docs/ARCHITECTURE.md:452,463` → 目录树内也标注 `version 0.9.1` / `version 0.4.17`
- `PROJECT_STATUS.md:10-12` → OPP `0.9.1` / ORF `0.4.17`

**实测**（为什么门禁没抓到）：`scripts/sync_version_docs.py:35-39` 的 `TARGETS` 只有三个文件，且都不包含这两张过期的表：

```python
TARGETS: list[Path] = [
    SUITE_ROOT / "README.md",
    SUITE_ROOT / "AGENTS.md",
    SUITE_ROOT / "COMPATIBILITY.md",
]
```

`python3 scripts/sync_version_docs.py --check` 输出 `OK: version docs in sync with pyproject.toml` —— 因为它只看它管的这三个文件（README / AGENTS / COMPATIBILITY），而 `ARCHITECTURE.md` / `PROJECT_STATUS.md` 不在其中。`docs/ARCHITECTURE.md` 与 `PROJECT_STATUS.md` 的版本表**自由漂移了约两个版本号**，无人过问。

> **注**：2026-09-17 健康度报告已指出 "PROJECT_STATUS 过期约 2.5 个月"，但**至今未修**，且现在 `ARCHITECTURE.md` 也加入了过期行列。这是"制度化搁置"的第二次复发。

**修法（择一）**：
- (a) 从 `ARCHITECTURE.md` / `PROJECT_STATUS.md` **删掉版本表**，改为指向 `VERSION` / `pyproject.toml` —— 单一真相源，更符合美学；
- (b) 扩展 `sync_version_docs.TARGETS` 覆盖这两个文件。

**倾向 (a)**：版本号是易变事实，不该在多处以散文形式复述。

#### P0.2 "8 quality gates" vs 代码里的 7 个

**文档声称**：`AGENTS.md:15` "8 quality gates"；`AGENTS.md:78` "`--gates-only` # OPP + OL（8 quality gates）"。

**实测**：`Omni_Localizer/src/ol_lqa/quality_gates.py` 的 `run_quality_gates` 实现的是 Gate 1–7：

| Gate | 函数 | 行 |
|---|---|---|
| 1 inline tag parity | `check_inline_tag_counts` | 230 |
| 2 terminology consistency | `check_terminology_consistency` | 264 |
| 3 length ratio | `check_length_ratio` | 328 |
| 4 locale conventions | `check_locale_conventions` | 506 |
| 5 source copy | `check_source_copy` | 588 |
| 6 source script fragments | `check_source_script_fragments` | 371 |
| 7 protocol artifacts | `check_protocol_artifacts` | 643 |

**第 8 个"术语审计"在哪里？** 它的实现在 `Omni_Localizer/src/ol_terminology/verifier.py:347`（`verify_translation`），**只通过独立的 `verify-terms` 工具 / CLI 可达，从未进入 `run_quality_gates`**。

> **后果**：agent 执行 `--gates-only` 时以为自己跑了 8 道门，实际只有 7 道；术语一致性从未在流水线里被自动检查。

#### P0.3 "4-layer repair pipeline" 在生产中只跑 3 层

**文档声称**：`AGENTS.md:15` "4-layer repair pipeline"。

**实测**：L3 需要 `llm_restorer`：

```python
# Omni_Localizer/src/ol_md/pipeline.py:10,70-71
def __init__(self, llm_restorer=None):
    self.llm_restorer = llm_restorer
...
if self.llm_restorer:
    restored = level3_llm_restore(current_text, original_text, shield_map, self.llm_restorer)
```

而**全部 11 个构造点均无参调用**：

```
cli/translate_md.py:542, 741, 892, 990
cli/translate_xliff.py:106, 378
ol_batch/processor.py:259
ol_mcp/batch_translate.py:76
ol_mcp/translate_md.py:127
ol_mcp/translate_xliff.py:126, 323
```

`XLIFFRepairPipeline` 同构（`ol_xliff/pipeline.py:22,30,89-90`）。

> **后果**：生产路径永远是 L1 → L2 → L4，**L3（LLM 兜底恢复）是装饰性代码**。这比"少一层"更糟 —— 文档让人相信最难的场景有 LLM 兜底，实际上没有。

#### P0.4 "41 tools" 完全没被门禁覆盖

**实测**：`python3 scripts/doc_inventory.py --check` 输出 `SOURCE: OPP=9 OL=21 ORF=7 total=37`；`grep -n "41" scripts/doc_inventory.py` 无结果。

即 `AGENTS.md` 的 "all 41 tools: 37 module + 4 suite" 中，**那 4 个 suite 工具从未被任何 doc-truth 检查验证过** —— 而这恰恰是 agent 最常用的入口。

#### P0.5 门禁自身在硬编码历史常量

**实测**（`scripts/doc_inventory.py`）：

| 行 | 内容 | 问题 |
|---|---|---|
| 288 | `_SEVEN_EIGHT_SIX_RE = re.compile(r"7\s*\+\s*8\s*\+\s*6\s*=\s*(\d+)\s+tools?")` | 对应早已不存在的 7/8/6 分解，只校验总和 |
| 626-627 | `if "14 input formats" not in read_text(path)` | 字面量比较，非派生计数；`scenarios/opp/` 已有 16 个 YAML |
| 635-636 | `if "131 PASS, 64 SKIP, 0 FAIL" not in text` | 矩阵快照写死在校验器里 |
| 650-651 | `if "14 nightly tests" not in read_text(tes)` | 同上 |
| 654 | `if "(--collect-only; canonical: 14)" not in read_text(ulw)` | 同上 |

> **本质**：这是**用一个常量去验证另一个常量**，门禁退化成回声室。真正的自检应从源派生（工具数已经是派生的；场景数也是派生的；唯独测试矩阵数字是抄来的）。

#### P0.6 同名不同物的错误类型

**实测**：`ManifestParseError` 被定义两次，基类不同：

- `Omni_Re_Formatter/src/orf/parsers/manifest.py:64` → 继承 `Exception`
- `Omni_Re_Formatter/src/orf/error_handlers/conversion_error.py:44` → 继承 `ConversionError`

CLI 导入的是前者。任何按后者 `catch` 的代码都抓不到真实抛出的异常。

> 这类问题 type checker 查不出来 —— 而 `mypy` 恰好把 `orf/converters` 整个排除在外（见 P4.2）。

---

### P1 — 死代码与半成品：氛围编程的典型残渣

Vibe coding 的典型症状不是写得差，而是**写多了但没删**。本项目有明显的"生成物沉降"：

| 残渣 | 实测证据 | 性质 |
|---|---|---|
| `ol_checkpoint/` 整包 | 生产代码零引用（`grep -rn "from ol_checkpoint\|import ol_checkpoint" Omni_Localizer/src` 排除自身后为空） | 有真实机制（锁、原子写），但从未接线 |
| `ol_routing/` 整包 | 同样零生产引用；且与 `ol_buses/format_guard.py` 功能重复 | 两套路由 |
| `ol_md/repair/level2.py` ≡ `ol_xliff/repair/level2.py` | `md5sum` 完全相同：`57f50601291e2d13b01fe3dee437c046` | **逐字节复制** |
| 两套 XLIFF shield | 生产全部走 `ol_buses/xliff_shield`（`cli/translate_md.py:427`、`cli/translate_xliff.py:299`、`ol_buses/xliff_bus.py:8,256`、`ol_mcp/translate_xliff.py:35`）；`ol_xliff/shield.py` 无生产引用 | 概念重复、实现分叉 |
| ORF `ImageManager` | 定义于 `orf/resources/image_manager.py:34`，经 `orf/resources/__init__.py:7` 导出，但**无任何 channel 使用** | 抽象存在却被绕过；各 channel 各自实现 md5 去重 |
| OPP `contracts.Manifest` / `ImageManifest` | `contracts/manifest.py:197`、`contracts/images.py:101` 定义了 Pydantic 模型，但 `src/` 内**从未实例化**；写 manifest 走 `commands/extract.py` 里的裸 dict | "有 schema"是幻觉 |
| OPP `PDFExtractor` | `extractors/pdf.py:36` 定义，经 `extractors/__init__.py:11` 与 `opp/__init__.py:11` 对外导出；但 pipeline 注册表（`opp/pipeline.py:10-11,69`）用的是 `PDF2HTMLExtractor` | 两套 PDF 实现，一套不在主干 |
| `scripts/validation/run_with_env.py` | 路径算成 `../../..` → `/mnt/d/贯维/01-Projects/Omni_Localizer/config`（应为 `../..`）；硬编码 `/mnt/d/Hermes-Workspace`；docstring 仍写 "full suite (83 scenarios)"（实际 122） | 本地草稿脚本进了仓库 |

> **美学原则**：一个未被调用的抽象不是"预留"，是负债。它会让下一个 agent 误以为它是入口，然后读到错误的实现 —— 上面最后两行正是活例。

---

### P2 — 模块形状：深度两极，中间层缺失

#### P2.1 薄壳与转发链

- `ol/__init__.py` 2 行（仅版本号）；`ol_md/__init__.py` 0 字节 —— 包边界不携带任何信息，调用方必须知道内部结构。
- `ol_buses/__init__.py` 转发 `ol_md.shield` 的符号，形成跨包转发层。
- `cli/__init__.py` 是星号导入的中转站。
- `ol_lqa/__init__.py` 只导出 10 个模块中的 2 个。
- 多个 17–50 行的 `__init__` / `exceptions` / `config` 只是再导出。

#### P2.2 四个 `importlib` 路径加载器（同一个概念需求，四种实现）

**实测**（`grep -rn "spec_from_file_location" scripts/ omni_mcp/`）：

```
scripts/nightly_gap.py:89
scripts/validation/artifact_matrix.py:79
scripts/validation/make_delivery_package.py:48
omni_mcp/validation/cli.py:566
```

根因只有一个：**`scripts/` 不是 Python 包**。

> **修法（高杠杆）**：把 `scripts/` 变成包（`omni_tools/`），一次性消掉这 4 个 shim 与所有 `sys.path.insert`。

#### P2.3 跨仓复制拓扑（ADR-0007 已到复审期）

ADR-0007（2026-09-17）决定"三份 path-security 先收敛、共享包延后"。当时合理，现在应复审：

| 复制品 | 位置 |
|---|---|
| `_disambiguate_zip_format` | `opp/detector.py:47-65` ≡ `orf/detection/magic_bytes.py:26-44`（逐字节相同） |
| 内容寻址缓存 | `opp/cliutils.py` ≈ `orf/cli.py`（key 算法不同） |
| `.env` 向上查找加载 | `opp/cliutils.py:112-156` ≈ `orf/cli.py:255-300` |
| MCP 安全 / 限流 / 配置 / 健康 / metrics 栈 | OPP 与 ORF 各一套近拷贝 |
| **`images.json`** | OPP 写一种 schema；ORF `md2docx.py` **又写同名但形状不同的文件**（多 `total`/`source` 字段） |
| frontmatter 正则 | ORF 内部三处重复（`parsers/frontmatter.py:42`、`md2eml.py:20`、`md2msg.py:21`） |
| Markdown 表格解析 | `opp/markdown/generator.py` 写、`orf/channels/md2csv.py` 与 `md2xlsx.py` 各读一遍 |

> **`images.json` 同名不同 schema 是真实事故风险**：文件名相同、形状不同、消费方不同。这正是 `CONTRACT.md` 开头声明要防止的 E2E-06 类"交接边界静默损坏"。

#### P2.4 跨通道重复

`ol_md/repair/level1.py`（17 行）与 `ol_xliff/repair/level1.py`（90 行）不是同一实现，但 `level2.py` 逐字节相同。MD 与 XLIFF 两条通道各有一套 `pipeline.py` / `repair/` / `shield`，其中 pipeline 已分叉（MD 返回字符串、XLIFF 返回元组），repair 却完全同构。

---

### P3 — 验证框架自身的自指膨胀

框架本身设计得很好，但已长出自我指涉的结构。

#### P3.1 五处场景发现规则

**实测**（`grep -rn 'rglob("\*.yaml")' scripts/ omni_mcp/`）：

```
scripts/doc_inventory.py:605
scripts/validation/coverage_audit.py:164
scripts/validation/coverage_audit.py:283
omni_mcp/validation/cli.py:129      # 注释自认是 loader 的 "mirror"
omni_mcp/validation/loader.py:433
```

第 2 处注释承认了它只是镜像；第 3 处（`coverage_audit`）连点目录过滤都没有。

#### P3.2 `--artifacts` 会让失败的场景集退出 0

**实测**（`omni_mcp/validation/cli.py:827-835`）：

```python
scenario_failures = any(
    r.status in ("failed", "invalid") and not getattr(r, "known_gap", False)
    for r in run.scenarios
)
if matrix_exit_code is not None:
    return matrix_exit_code
return 1 if scenario_failures else 0
```

artifact matrix 一旦启用（`cli.py:792` 设 `matrix_exit_code = 1`），**场景失败只打印、不驱动退出码**。两个独立门用 `if/else` 组合而非"与"。

> **⚠️ 这是已文档化的刻意设计，不是疏漏**：`docs/dev/artifact-assertion-matrix.md:174,178-179` 明确写着 *"the artifact matrix, not the scenario verdicts, decides the exit code"*；`AGENTS.md:118` 与 `CHANGELOG.md`（`e2e-test-suite#44` 条目）同样表述。设计意图是：artifact 断言是对**真实产物**的确定性检查，其结论比场景 verdict 更权威。
>
> **残留风险（仍然成立）**：该设计只在"artifact 失败 ⇒ 1"方向覆盖，**反方向丢失了场景失败信号** —— artifact 全绿但场景有 `failed`/`invalid` 时，退出码为 0。若调用方只看退出码，会把一次失败运行读成通过。
>
> **建议（低成本、不改语义）**：保持 artifact 优先，但让"artifact 通过 + scenario 失败"也返回非 0（或使用可区分的退出码，如 2 = scenario-only 失败），并在 `artifact-assertion-matrix.md` 补一句该组合的行为表。

#### P3.3 `family.py` 只覆盖 14 个 anchor 中的 12 个

**实测**：`scenarios/STANDARDS.md` 有 14 个 `###` anchor；`family.py` 的 `AGENT_SURFACE_ANCHORS`(5) + `HUMAN_QUALITY_ANCHORS`(7) = 12。未纳入的是 `#fallbacks-never-evidence` 与 `#env-gate-semantics`。

只引用这两个 anchor 的场景会退回前缀分类，可能被误判 family。

#### P3.4 重复的判定逻辑与不一致的"通过"定义

**实测**：

- `scripts/validation/validation_report.py:75` 复制了 engine 的正则，注释自认：*"Mirrors `omni_mcp.validation.engine._RATE_LIMIT_RE` ... scripts/ is not a package; keeping the rule local avoids importing the whole engine"*。
- **"pass-like" 有两个定义**：
  - `validation_report.py:69` → `GREEN_STATUSES = {"passed", "recovered"}`
  - `validation_diff.py:85` → `_PASS_LIKE = frozenset({"passed", "recovered", "partial-pass"})`

同一份数据，`partial-pass` 在报告里不算绿、在 diff 里算通过。

#### P3.5 框架用自己生成的产物验证自己

`doc_inventory` 生成 `docs/dev/doc-inventory.md`，再检查该文件的"行集合是否与今天扫描结果一致"。这是自洽，不是外部真值。

---

### P4 — 工程卫生

#### P4.1 ruff 基线红，且本地与 CI 不是同一把尺

**实测**（本地 `ruff 0.15.15`）：

```
$ python -m ruff check .
Found 262 errors.
[*] 201 fixable with the `--fix` option
```

**实测**（版本不一致）：CI 装 `ruff==0.17.1`（`.github/workflows/lint.yml:109`），pre-commit 锁 `rev: v0.17.1`（`.pre-commit-config.yaml:57`），而工作区 venv 里是 `0.15.15`。**开发者本地跑的和 CI 跑的不是同一个 ruff。**

CI 侧只 gate "改动文件的 F 类"，并显式允许 65 个 F 类基线（`lint.yml:137-163`）。`lint.yml` 注释把"基线红"写成既定事实。

#### P4.2 mypy 恰好排除了最复杂的部分

**实测**（`pyproject.toml` `[tool.mypy] exclude`）：

```toml
exclude = [
    "Omni_Pre_Processor/src/opp/extractors",
    "Omni_Localizer/src/ol_buses",
    "Omni_Re_Formatter/src/orf/converters",
    ...
]
```

这三处正是抽取/回填的核心逻辑，也是 P0.6 同名异常类、P2.3 复制代码最容易藏身的地方。

#### P4.3 `.gitignore` 的负向规则是死规则

**实测**：

```
$ git check-ignore -v .omo/plans/system_improvements_v3.md
.gitignore:34:.omo/	.omo/plans/system_improvements_v3.md
```

`.gitignore:33-36` 的意图写得很清楚：

```gitignore
# .omo is mostly runtime state, but plans are source — whitelist plans/
.omo/
!.omo/plans/
!.omo/plans/*.md
```

但 git **不会下降到被排除的目录**，父目录 `.omo/` 被排除后，`!.omo/plans/` 无效。实测结果：`git ls-files .omo | wc -l` → **19**（历史入库的），而磁盘上有 80+ 份新计划**永远进不了库**。

> **注释与行为相反**：注释说 "plans are source"，实际是 "plans are local-only"。

#### P4.4 仓库根目录是施工现场

**实测**：根目录 25 个 `*.md`（其中 `INTEGRATED_TEST_PLAN.md` 52KB、`feature_inventory.md` 25KB、`system_improvements_v2.md` 16KB、`issue-pipeline-quality-improvements.md`、`lqa-workflow.md`、`agent-qa-workflow.md`、`e2e-test-plan.md` 等均为阶段性产物）；根目录 `*.py` 有 `check_opp_orf_tools.py`；目录混居 `dist/`、`eval/`、`logs/`、`resources/`、`test_artifacts/`、`test_corpus/`、`test_fixtures/`、`benchmarks/`、`docker/`、`utils/`、`99-Tools/`、`.codegraph/`、`.hermes/`，以及三个 venv（`.venv` 弃用、`.venv_ol` 在用、`.venv_win`）。

此外根目录残留 `opp_mcp_bhgufg4d_images/`、`opp_mcp_g91nkh8q_images/` —— MCP 运行的产物目录。虽被 `/*_images/` 忽略，但**实体在**仓库根，说明清理逻辑不完整。

> 新人或 agent 打开仓库时，第一眼看到的不是产品，是施工现场。

---

## 七、与 2026-09-17 健康度报告的增量差异

| 维度 | 2026-09-17 报告 | 本次实测（2026-10-22） | 变化 |
|---|---|---|---|
| Suite 版本 | 0.4.0 | 0.5.0 | ↑ |
| OPP 版本 | 0.9.1 | 0.10.0 | ↑ |
| ORF 版本 | 0.4.17 | 0.5.0 | ↑ |
| 场景库 | 119 | **122** | ↑ |
| ruff 错误 | 281 | **262** | ↓（但仍未清零） |
| PROJECT_STATUS 版本表 | 过期 2.5 个月 | **仍过期（0.9.1 / 0.4.17）** | **未修** |
| ARCHITECTURE 版本表 | 未审 | **过期（0.9.1 / 0.4.17 / 0.4.0）** | **新增缺陷** |
| 门禁覆盖的真相 | 未审 | 版本表仅覆盖 README/AGENTS/COMPATIBILITY；ARCHITECTURE / PROJECT_STATUS 未覆盖；41-tool 未覆盖；8-gate / 4-layer 声称与实现不符 | **新增** |
| 死代码 | 未审 | 2 个 OL 子包零引用、1 处逐字节复制、3 处"导出但未接线" | **新增** |

> 结论：2026-09-17 报告提出的问题**尚未闭环**，且本次新增了"门禁盲区"与"生成物沉降"两类诊断。

---

## 八、优先行动清单

按投入产出比排序。**每一项都对应一次删除或一次收敛，而不是一次新增。**

| # | 行动 | 对应问题 | 预计成本 | 风险 |
|---|---|---|---|---|
| **1** | **收敛真相**：删除 `ARCHITECTURE.md` / `PROJECT_STATUS.md` 中的版本表，改为链接 `VERSION` 与 `pyproject.toml`；或扩展 `sync_version_docs.TARGETS` | P0.1 | 0.5 天 | 低（纯文档） |
| **2** | **对齐声明与实现**（三选一，每项独立决策）：8 gates → 7（改文档）或接线术语审计（改代码）；4-layer → 3（改文档）或传入 `llm_restorer`（改代码）；`41 tools` 纳入 doc gate 或改文档 | P0.2 / P0.3 / P0.4 | 文档 0.5 天；接线各 1–2 天 | 接线 L3 会改变翻译行为，需真实 LLM 回归 |
| **3** | **删除生成物**：移除或接线 `ol_checkpoint`、`ol_routing`、`ol_xliff/shield.py`、重复的 `ol_xliff/repair/level2.py`、`run_with_env.py`；把 `PDFExtractor` / ORF `ImageManager` / OPP `contracts.Manifest` 明确标记为死代码或接线 | P1 | 1–2 天（需跑测试确认） | 中（删除前须确认无下游引用） |
| **4** | **`scripts/` 包化**：改为 `omni_tools/` 包，消掉 4 处 `spec_from_file_location` 与所有 `sys.path.insert`；三处/五处 `rglob` 场景发现收敛为一处 | P2.2 / P3.1 | 1 天 | 中（导入路径变更波及 hook 与 CI） |
| **5** | **ruff 全树清零并纳入 CI**：`--fix` 修掉 201 个，手工处理 61 个；CI 从"改动文件 F 类"升级为"全树 E/F/I/B/UP/N"；统一本地与 CI 的 ruff 版本 | P4.1 | 1–2 天 | 低（机械） |
| **6** | **修 `.gitignore` 负向规则**：`!.omo/plans/` 需要先把父目录从排除改为"排除其内容"（`/.omo/*` + `!/.omo/plans/`），并决定 80+ 份计划是否入库或明确归档 | P4.3 | 0.5 天 | 低 |
| **7** | **补门禁信号缺口（不改既有语义）**：`--artifacts` 保留 artifact 优先，但让"artifact 通过 + scenario 失败"也返回非 0（或用可区分退出码）；`family.py` 补齐 2 个 anchor；统一 `GREEN_STATUSES` / `_PASS_LIKE` | P3.2 / P3.3 / P3.4 | 0.5 天 | 低（需同步 `validation_report` 与 `validation_diff` 输出，diff 消费者会看到变化） |
| **8** | **修 `images.json` 双 schema**：统一 OPP 写与 ORF 写为同一形状，并在 `CONTRACT.md` 增列 | P2.3 | 0.5–1 天 | 中（跨仓契约变更，需三仓同版本发布） |
| **9** | **根目录收敛**：把 25 个根级 `*.md` 中的阶段性产物（`INTEGRATED_TEST_PLAN.md`、`feature_inventory.md`、`system_improvements_v2.md`、`e2e-test-plan.md`、`lqa-*.md`、`agent-qa-workflow.md` 等）移入 `docs/archive/` 并加 `ARCHIVED` 首行标记；清理根目录残留 `*_images/` | P4.4 | 0.5 天 | 低（archive 标记由 gate 强制） |
| **10** | **复审 ADR-0007**：`detector` / `cache` / `dotenv` / `manifest schema` 的跨仓复制已产生真实漂移，共享包的收益开始超过独立发布的成本 | P2.3 | 需先做 1–8 | 高（影响三仓发布节奏） |

---

## 九、附：本次审阅使用的复现命令

```bash
# 规模
find Omni_Pre_Processor/src Omni_Localizer/src Omni_Re_Formatter/src \
     omni_mcp omni_suite scripts -name '*.py' -exec wc -l {} + | tail -1
find Omni_Pre_Processor/src Omni_Localizer/src Omni_Re_Formatter/src \
     -name '*.py' -exec wc -l {} + | awk '$1<40 && $2!="total"' | wc -l   # → 75

# 真相债
grep -n "0\.9\.1\|0\.4\.17\|0\.4\.0" docs/ARCHITECTURE.md PROJECT_STATUS.md
sed -n '35,39p' scripts/sync_version_docs.py          # TARGETS 有 3 个文件（ARCHITECTURE/PROJECT_STATUS 不在其中）
grep -n "Gate [1-8]" Omni_Localizer/src/ol_lqa/quality_gates.py
grep -rn "MDRepairPipeline(\|XLIFFRepairPipeline(" Omni_Localizer/src   # 11 处全无参
grep -n "41" scripts/doc_inventory.py                  # 空 → 41-tool 未被 gate

# 死代码
grep -rn "from ol_checkpoint\|import ol_checkpoint" Omni_Localizer/src
grep -rn "from ol_routing\|import ol_routing" Omni_Localizer/src
md5sum Omni_Localizer/src/ol_md/repair/level2.py Omni_Localizer/src/ol_xliff/repair/level2.py
grep -rn "ImageManager" Omni_Re_Formatter/src
grep -rn "Manifest(" Omni_Pre_Processor/src

# 框架自指
grep -rn "spec_from_file_location" scripts/ omni_mcp/
grep -rn 'rglob("\*.yaml")' scripts/ omni_mcp/
sed -n '827,835p' omni_mcp/validation/cli.py

# 卫生
python -m ruff check .                                  # 262 errors
git check-ignore -v .omo/plans/system_improvements_v3.md
git ls-files .omo | wc -l                               # 19

# 门禁
python3 scripts/doc_inventory.py --check
```

---

*本报告为实测审阅，不含推测性结论。所有"实测"条目均可用上述命令复现。文档与门禁的一致性由 `python3 scripts/doc_inventory.py --check` 保证（exit 0 = clean）。*
