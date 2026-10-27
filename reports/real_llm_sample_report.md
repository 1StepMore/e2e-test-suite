# T4 — OL 真模型抽样报告（V1 + V2）

- 日期：2026-10-27
- 分支：`feat/eml-matrix-and-scenarios`（suite）
- 模型池预检：`.venv_ol/bin/python scripts/validation/check_llm_pool.py` → `"verdict": "pass"`，`usable_per_role` = translation 2 / judging 2 / restoration 2 / profiling 2；`AMD_API_KEY` 来自进程环境，`ZHIPU_API_KEY` 由 `Omni_Localizer/.env` 自动加载。
- 证据性：两场景均为真实模型调用，未使用任何确定性桩，也未使用 `--allow-fake`。

## 1. 输入 / 中间产物 / 输出文件路径

### V1 — `pipeline-docx-md-docx`（run `validation-runs/20261027-142245`）

| 阶段 | 路径 | 大小 |
|---|---|---|
| 输入 | `/tmp/omni_val/pipeline-docx/source.docx` | 37,584 B |
| OPP 中间产物 | `/tmp/omni_val/pipeline-docx/opp_out/source.md`、`source.xlf`、`source.skeleton.zip`、`source_images.json`、`source_manifest.json` | — |
| OL 产物 | `/tmp/omni_val/pipeline-docx/ol_out/source.md`、`ol_out/source.xlf`、`ol_out/source_images/` | 1,337 B（md） |
| 输出 | `/tmp/omni_val/pipeline-docx/out.docx` | 11,942 B |

### V2 — `pipeline-pptx-md-pptx`（run `validation-runs/20261027-143026`）

| 阶段 | 路径 | 大小 |
|---|---|---|
| 输入 | `/tmp/omni_val/pipeline-pptx/source.pptx` | 30,324 B |
| OPP 中间产物 | `/tmp/omni_val/pipeline-pptx/opp_out/source.md`、`source.xlf`、`source_images.json` | — |
| OL 产物 | `/tmp/omni_val/pipeline-pptx/ol_out/source.md`、`ol_out/source.xlf` | 822 B（md） |
| 输出 | `/tmp/omni_val/pipeline-pptx/out.pptx` | 29,819 B |

## 2. 译文字数比、段数对比（src vs out）

| 指标 | V1 DOCX | V2 PPTX |
|---|---|---|
| 源正文 CJK 字数 | 184 | 103 |
| 译文正文字符数 | 1,031 | 516 |
| OL 自报 target/source 长度比（`LENGTH_RATIO`） | **3.58**（上限 2.0 → 告警） | **5.31**（上限 2.0 → 告警） |
| 段落数（src → out） | 8 → 8（ratio **1.000**，门禁 ±5%） | 6 → 6（ratio **1.000**） |
| 未翻译单元 | 0 / 8 | 0 / 6 |
| CJK 残留密度 | 0.00%（门禁 < 5%） | 0.00% |
| 中文标点残留 | 0 个 | 0 个 |

长度比说明：中→英按字符数计必然显著膨胀（CJK 单字承载的语义密度远高于拉丁字母词），3.58 / 5.31 均超出 `OL_LENGTH_RATIO_MAX=2.0`，属**预期告警而非质量失败**；两场景该 step 均通过，产出的只是 `<!-- OL_WARN: LENGTH_RATIO -->` 注释。真正判定译文完整性的门是「未翻译单元 = 0」（均通过）。

## 3. 图片 / 表格 / slide 数对比

| 指标 | V1 DOCX（src → out） | V2 PPTX（src → out） |
|---|---|---|
| 图片 / drawing | 2 → 2（`#drawing-count` 判定 `src == out`） | — |
| 表格 | 0 → 0（夹具无表格） | 0 → 0（夹具无表格；表格单元格文本由段落计数覆盖的路径本轮无样本） |
| slide 数 | — | 3 → 3 |
| 文本段落数（含 slide 标题） | 8 → 8 | 6 → 6 |
| 可被 python-docx / python-pptx 打开 | 是（8 paragraphs） | 是（3 slides，6 paragraphs） |

## 4. 三段人工可读译文摘录（原 + 译并排）

**摘录 1（V1，第 1 段 —— 夹带缺陷，见下方「缺陷记录」）**

> 源：全球智造科技有限公司成立于2008年，专注于工业自动化系统的研发与制造。
>
> 译：Global Smart Manufacturing Technology Co., Ltd. was founded in 2008 and focuses on the research, development, and manufacturingGovorun of industrial automation systems.

**摘录 2（V1，第 5 段）**

> 源：公司的愿景是通过智能制造技术，帮助全球制造业客户实现数字化转型。
>
> 译：The company's vision is to help manufacturing customers worldwide achieve digital transformation through intelligent manufacturing technology.

**摘录 3（V2，第 2 页正文）**

> 源：协作机器人、视觉引导装配单元、人工智能质量检测平台，服务全球四十多个国家。
>
> 译：Collaborative robots, vision-guided assembly cells, and AI-powered quality inspection platforms, serving more than 40 countries worldwide.

**缺陷记录（必须随报告保留）**：摘录 1 的译文中出现了无来源的夹带词 `Govorun`（`manufacturingGovorun`）。该缺陷躲过了本轮全部自动门禁（长度比只看总量、CJK 密度为 0、标点检查为 0、LQA 仍给 4.85/5），只有人工阅读才能发现 —— 说明 `#lqa-threshold` 通过不等于「无夹带」；后续若要自动化，需要新增「译文不得含源文与目标语言词典之外的孤立词」类断言。该缺陷属 OL 输出质量问题，不在本轮 EML 改动范围内，仅记录。

## 5. LQA 实际分数（只记录，不作门槛）

| 场景 | `judge_overall_avg_5` | 四维平均 `dim_avg_5` | 样本数 n | 发布线 |
|---|---|---|---|---|
| V1 `pipeline-docx-md-docx` | **4.85** | 4.85 | 6 | ≥ 4.0 → 通过 |
| V2 `pipeline-pptx-md-pptx` | **4.12** | 4.12 | 6 | ≥ 4.0 → 通过 |

两个场景的 LQA step 此前均带 `known_gap: true` 豁免；本次实跑两者都越过 4.0，运行器据此输出 `GAP CLOSED`（对应 issue #206 的豁免移除）。本轮**不**就地移除豁免（属另一条改动线），只记录事实。

## 6. V2 的 pandoc 回退声明

本机没有 .NET `md2pptx`（`orf capabilities` 报 `md2pptx CLI not installed`，矩阵中 `→pptx` 的 17 格因此 SKIP）。V2 的 `orf apply-md --target-format pptx` 走的是 **pandoc 回退**路径，实测产出 3 slides / 6 paragraphs。

因此 **V2 的全部结论只对 pandoc 回退成立**，不能外推为「.NET md2pptx 通道已验证」。要覆盖原生通道，需要先在本机装好 .NET `md2pptx` 再重跑同一场景。

## 结论

- V1：`passed`（14 step，14 通过，2 个 known-gap step 本轮转为通过）—— 结构、图片、段落比例、CJK/标点、LQA 全部达标；但译文夹带 `Govorun` 属人工可读性缺陷，已记录。
- V2：`passed`（11 step，11 通过，1 个 known-gap step 转为通过）—— 结论仅限 pandoc 回退。
- 两场景均为真实模型证据，可引用为质量层（L3）证据。
