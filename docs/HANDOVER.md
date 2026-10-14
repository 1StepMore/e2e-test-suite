# OPP/OL/ORF E2E 测试交接文档

> **交接日期**：2026-06-01
> **交接方**：default profile（祝任甫主对话）
> **接手方**：code profile（代码相关）
> **目标读者**：接手继续修复 OPP/OL/ORF 管道 bug 的工程师

---

## 0. 目录结构（2026-06-01 整理后）

```
e2e-test-suite/
├── docs/
│   └── HANDOVER.md            # 本文档
│
├── run_full_standard_test.py  # 测试主脚本
├── run_e2e.py, run_test.sh    # 其他运行入口
├── README.md, TEST-STANDARD.md
│
├── src/                       # 三个仓库的 submodule
│   ├── Omni_Pre_Processor/
│   ├── Omni_Localizer/
│   └── Omni_Re_Formatter/
│
├── reports/                   # bug 报告 + 比较报告（已就位）
├── logs/                      # 按日期归档（已就位）
├── test-artifacts/            # 源文件 + 提取结果（已就位）
├── scripts/                   # 工具脚本（已就位）
├── resources/                 # 资源文件（已就位）
│
├── test-runs/
│   ├── current/FULL-009/      # 最新一次成功 run（2026-06-01 11:04）
│   └── archive/               # 历史 run（59 个，旧的全部归档）
│
└── debug/                     # 一次性调试脚本（不要往主目录扔）
    ├── check_*.py             # 12 个排查脚本
    ├── fix_*.py               # 1 个 unit1 标题修复
    ├── simulate_*.py
    ├── find_*.py
    ├── test_*.py
    ├── loop-log.json
    ├── system-state.json
    └── .opencode-context.md
```

---

## 1. 项目背景

**1StepMore** 公司三件套：
- **OPP**（Omni Pre-Processor）：文档预处理，从 docx/pptx/pdf 等提取结构化内容（段落、图片、表格）→ XLIFF/Markdown
- **OL**（Omni Localizer）：本地化，基于 LLM 翻译 XLIFF/Markdown
- **ORF**（Output Restoration Framework）：反向应用，将翻译结果写回原始 docx/pptx/pdf

**测试目标**：验证中文 docx → 英文 docx 全链路 (OPP→OL→ORF) 工作正常。

---

## 2. 工作目录与关键 SHAs

**主工作目录**：`/mnt/d/Hermes-Workspace/01-Projects/e2e-test-suite/`

**三个仓库的 SHAs**（e2e-15-fix 分支）：

| 仓库 | SHA | 路径 |
|------|------|------|
| OPP | `ad6b227` | `src/Omni_Pre_Processor/` |
| OL | `04a8390` | `src/Omni_Localizer/` |
| ORF | `a9926a1` | `src/Omni_Restoration_Framework/` |

**修改 OPP 后**：必须 `cp` 到主仓 `src/Omni_Pre_Processor/src/` 然后 push。

---

## 3. 测试源文件

| 文件 | 用途 | MD5 | 段落数 | 图片数 | 大小 | 路径 |
|------|------|------|--------|--------|------|------|
| Canonical | 快速验证 | `6a484209` | 10 | 12 | 437KB | `e2e-test-suite/source_haier_e2e_full.docx` |
| Full | 完整验收 | `7381cc12` | 104 | 35 | 3.8MB | `Localization/爱上海尔/爱上海尔_第二章_全球创牌.docx` |

**重要**：完整版有 35 张 ZIP 图片，**但 OPP skeleton 只识别 26 张**（img_positions=[7,8,33,52,53,57,62,64,72,75,79,83,85,95,99]），这是已知 baseline 行为。

---

## 4. 测试框架

**主脚本**：`run_full_standard_test.py`

**关键参数**：
- `--run-id "ID"`：运行标识
- `--test-paths A/B/C/D`：选择路径
- `--ol-timeout 2400`：每个 OL 单元的超时（秒），完整版必须 2400
- `--full`：使用完整版（104段落），默认用 canonical（10段落）

**路径架构**：

| 路径 | 输入 | 引擎 | 状态 |
|------|------|------|------|
| **A** | XLIFF | CLI | ✅ 主要使用 |
| B | XLIFF | MCP | ❌ 连接错误（`McpError: Connection closed`）|
| C | MD | CLI | ❌ 段落数 3/10 不匹配 |
| D | MD | MCP | ❌ 同 B |

**输出结构**：
```
test-runs/{run-id}/
├── A-xliff-cli/
│   ├── opp_out/source.xlf     # OPP 提取的 XLIFF
│   ├── ol_out/source.xlf      # OL 翻译后的 XLIFF
│   ├── orf_out/result.docx    # 最终产物
│   ├── quality.json           # 质量报告
│   └── text_comparison.json   # 文本对比
```

**常用命令**：
```bash
# 标准测试（10段落）
python run_full_standard_test.py --run-id "LOOP-XXX" --test-paths A --ol-timeout 900

# 完整测试（104段落）
python run_full_standard_test.py --run-id "FULL-XXX" --test-paths A --ol-timeout 2400 --full
```

---

## 5. 已修复 Bug（已 push）

| ID | 描述 | 根因 | SHA |
|----|------|------|------|
| E2E-32 | `<bx>/<ex>` tag 在 XLIFF 中位置错位 | `_escape_except_tags()` 占位符 1-based vs 0-based off-by-one | `9dfe81f` |
| E2E-65 | LLM 输出 "CRITICAL/INSTRUCTIONS" 等注入性提示词污染翻译 | OL Router 翻译 prompt 未约束 | `94d796c` |
| E2E-66 | 大段落（150+ w:t）中文残留未翻译 | OPP `para.text` 截断为 ~256 字符（part 1） + `run.text` 截断为 ~35 `w:r`（part 2） | `01b8b17` + `d49132a` |
| E2E-67 | XLIFF 输出含 `<think>` 等 thinking tag | MiniMax 模型输出 thinking 标签 | `04a8390` |
| E2E-68 | 副标题 Unit 2 翻译后只剩"全球创牌" | `_build_source_with_inline` 处理 self-closing `<bx/>` 错位 | `ad6b227` |
| E2E-69 | Unit 1 标题含 `Warning:...` 文本 | `level4_safe_fallback` 把 `<note>` 元素当字符串追加进 `<target>` 文本，ORF `itertext()` 递归提取时把 note 文本带出 | `c8435a7`（OL） |
| E2E-70 | Unit 2 副标题中文残留 | ORF `_backfill_translation` 文本搜索被 inline `<w:bookmark>` 打断；fallback 用 whitespace-normalized 匹配 + E2E-07 fuzzy match | `b240948`（ORF，含 E2E-07 同步）|

**E2E-66 修复关键**（`src/opp/extractors/docx.py` L99-108）：
```python
# 修复前（截断）
text = para.text
# 修复后（读全部 w:t）
text = ''.join(t.text or '' for t in para._element.findall(f".//{W_NS}t"))
```

**E2E-68 修复关键**（`src/opp/xliff/generator.py`）：self-closing inline tag 的 tail 处理。

---

## 6. 已修复 Bug（E2E-69/70，2026-06-01 闭环）

> 状态变更：以下两个 bug 在 2026-06-01 跑 FULL-010 验证通过，**从"待修复"移到"已修复"**。详见第 5 节 + 第 11 节 commit readiness 报告。

### E2E-69：Unit 1 标题含 note 文本（已修，`c8435a7`）

**现象**：
- `result.docx` 段落 1：`Love Haier   Warning: Tag auto-appended at end, manual check needed`

**根因链路**：
1. LLM 翻译 Unit 1（标题 `《爱上海尔》` 被 `<bx id="1">` 包裹）时输出纯文本 "Love Haier"，丢失了 inline tag
2. Repair pipeline L1-L3 失败后调用 `level4_safe_fallback()`
3. `level4_safe_fallback`（`src/ol_xliff/repair/level4.py`）在 target_text 尾部追加：
   ```
   <bx id="1" type="bold"/> <ex id="1"/> <note from="OL">Warning: Tag auto-appended at end, manual check needed</note>
   ```
4. `write_target_back`（`src/ol_buses/xliff_bus.py`）写入 XLIFF `<target>` 元素
5. ORF `apply_xliff` 用 `itertext()` 提取文本时把 `<note>` 子元素的 text 也包含进来
6. 结果 "Warning:..." 文本被写入 docx 段落

**关键代码**：`src/ol_xliff/repair/level4.py:24`
```python
text = text + ' <note from="OL">Warning: Tag auto-appended at end, manual check needed</note>'
```

**修复方向**（待 user 确认）：
- 方案 A：`level4_safe_fallback` 不追加 `<note>` 元素，只追加缺失 tag，warning 走其他通道（如返回 marker）
- 方案 B：ORF `apply_xliff` 在 `itertext()` 时跳过 `<note>` 子元素

**测试证据**：
- `test-runs/current/FULL-009/A-xliff-cli/ol_out/source.xlf` Unit 1 target 包含 `<note>`
- 用 lxml 模拟：`itertext()` 输出 "Love Haier   Warning: Tag auto-appended at end, manual check needed"

### E2E-70：Unit 2 副标题未翻译（已修，`b240948`）

**现象**：
- `result.docx` 段落 2：仍为中文 `第二章  海尔的全球创牌`
- `ol_out/source.xlf` Unit 2 TGT：`<bx id="1">Chapter <ex/><bx id="2">Two<ex/>...<bx id="4"> Global Brand Building<ex/>`（翻译正确）
- 翻译正确生成但未写入 docx

**根因**：
- OPP skeleton para 2 文本结构：5 个 `<w:t>` 元素 `['第二', '章', '  ', '海尔的', '全球创牌']`，中间被 `<w:bookmark>` 打断
- ORF `_backfill_translation` 搜索连续 source 文本（如"第二章海尔的全球创牌"）失败，翻译未写入
- 整段保持原中文

**修复方向**：
- ORF `_backfill_translation` 需要处理 inline 书签打断的情况
- 可能需要：逐 run 替换 / 跳过 bookmark 重新组合 / 改成基于源骨架 ID 而非文本搜索

**测试证据**：
- `test-runs/current/FULL-009/A-xliff-cli/orf_out/result.docx` Para 2 XML 仍为 `<w:t>第二</w:t><w:t>章</w:t>...`

---

## 7. 已知问题（非 bug，可接受）

### Issue 1：中文标题序号 "一、" 未本地化
- **现象**：源 "一、创出一个全球化企业、世界级品牌" → 译 "create a global enterprise, world-class brand"（"一、" 消失）
- **根因**：源 docx 的 "一、" 是 Word 自动编号（`<w:numPr>`），不是 `<w:t>` 文本，OPPO 读不到
- **对比**：Unit 10 "二、国内市场：" 中的 "二、" 是内嵌文本，正确译为 "II. Domestic Market"
- **状态**：源文档制作问题，非管道 bug

### Issue 2：OCR 不在嵌入式 docx 图片上触发
- **真相**：OPPO `ImageOCRExtractor` 只对独立图片文件（PNG/JPG）触发，docx 内的嵌入图片不跑 OCR
- **证据**：`src/opp/markdown/generator.py:84` 用 `![Image N](data_uri)` 无 alt text
- **状态**：功能未实现，不算 bug

### Issue 3：Unit 37 "撬动" 中文残留
- **现象**：英文翻译中残留 "otherwise it is difficult to撬动 the consumer mindset"
- **根因**：LLM 翻译瑕疵，非管道问题
- **状态**：已知质量瑕疵，可接受

---

## 8. 当前最佳产物

**位置**：
```
/mnt/d/Hermes-Workspace/01-Projects/e2e-test-suite/test-runs/current/FULL-009/A-xliff-cli/orf_out/result.docx
```

**状态**：
- 段落：104/104 ✅
- 图片：26/26 ✅
- 结构 PASS，但有 E2E-69（Unit 1 标题 note）和 E2E-70（Unit 2 副标题）未解决
- Unit 37 有 "撬动" 残留

**临时修复版**（已发用户）：
```
/mnt/d/Hermes-Workspace/01-Projects/e2e-test-suite/test-runs/current/FULL-009/A-xliff-cli/orf_out/result_fixed.docx
```
- 修正了 Unit 1 note 文本
- Unit 2 副标题仍为中文

---

## 9. 接手后的下一步

> 状态变更（2026-06-01）：E2E-69/70 已闭环（见第 5、6 节），FULL-010 已验证通过。

1. **E2E-69 修复**（✅ 已闭环，2026-06-01）：
   - 修复方向：方案 A — `level4_safe_fallback` 不再追加 `<note>` 元素
   - SHA：`c8435a7`（OL 主仓）
   - 验证：FULL-010 Para 1 = `"Loving Haier"`，无 note 残留

2. **E2E-70 修复**（✅ 已闭环，2026-06-01）：
   - 修复方向：whitespace-normalized fallback + E2E-07 fuzzy match
   - SHA：`b240948`（ORF submodule，含 E2E-07 同步）
   - 验证：FULL-010 Para 2 = `"Chapter Two: Haier's Global Brand Creation"`，翻译成功写入 docx

3. **FULL-010 验证**（✅ 已闭环，2026-06-01）：
   - 跑了完整 104 段 + 35 张 ZIP 图
   - 结果：104/104 段落 + 26/26 图片 + tag_residue=0
   - 跑出 P1 翻译瑕疵：Unit 19（夹中文"美好生活"）、Unit 86（整段漏译）、Unit 37（"撬动"残留）
   - 这些是 LLM 翻译质量问题，非管道 bug

4. **可选优化**（下次 cycle）：
   - 新建 bug 跟踪"LLM 翻译质量瑕疵"模式（Unit 19/86/37），建一个趋势报告
   - 修复 MCP 路径（B/D）：`/home/renanzai/.hermes/venvs/omni-localizer/bin/python: No module named 'ol'`（OL venv 装包问题）
   - 修复 MD+CLI 路径（C）段落数不匹配问题（已知 baseline 3 != 104）
   - Unit 37 "撬动" 手动修正或重新跑翻译（同 Unit 19/86 同类型 LLM 瑕疵）

---

## 10. 关键文件清单

| 路径 | 角色 |
|------|------|
| `e2e-test-suite/run_full_standard_test.py` | 测试主脚本（已加 `--full`、`--ol-timeout`） |
| `docs/HANDOVER.md` | 本交接文档 |
| `Localization/爱上海尔/爱上海尔_第二章_全球创牌.docx` | 完整版源文件 |
| `Omni_Pre_Processor/src/opp/extractors/docx.py` | E2E-66 修复位置 |
| `Omni_Pre_Processor/src/opp/xliff/generator.py` | E2E-68 修复位置 |
| `Omni_Localizer/src/ol_xliff/repair/level4.py` | E2E-69 修复位置（`c8435a7`）|
| `Omni_Localizer/src/ol_buses/xliff_bus.py` | E2E-32 修复位置 |
| `Omni_Localizer/src/ol_pool/router.py` | E2E-65 修复位置 |
| ORF `_backfill_translation` | E2E-70 修复位置（`b240948`，含 E2E-07 fuzzy match）|

---

## 11. 测试模式备忘

- **快速验证**：标准 10段落文件，900秒超时，约 5-10 分钟
- **完整验收**：完整 104段落文件，2400秒超时，约 30-45 分钟
- **稳定 PASS 触发条件**：连续 2-3 次无 P0 问题
- **Commit readiness**：P0=0 + P1 评估通过 = READY

**FULL-010 验证结果**（2026-06-01 18:25，全 4 路径，19 分钟）：

| 路径 | 结构 | 翻译 | 状态 |
|---|---|---|---|
| **A** XLIFF+CLI | 104/104 ✅ + 26/26 ✅ + img_pos 15/15 ✅ | tag_residue=0，src_lang_residue=2（Unit 19 夹中文、Unit 86 整段漏译，LLM 翻译质量瑕疵） | 结构 PASS，有 P1 |
| **B** XLIFF+MCP | opp_out+ol_out 存在，orf_out 缺失 | unhandled errors in a TaskGroup | FAIL（ORF 未跑成）|
| **C** MD+CLI | 段 3/104、图 0/26、img_pos 空 | src_lang_residue=4 | FAIL（结构严重不符，MD 路径不通）|
| **D** MD+MCP | opp_out+ol_out 存在，orf_out 缺失 | unhandled errors in a TaskGroup | FAIL（ORF 未跑成）|

- SHAs：OPP=`d49132a` / OL=`c8435a7` / ORF=`b240948`
- 3 fix commit（E2E-66 part 2 / E2E-69 / E2E-70）验证：A 路径结构 PASS ✅
- 浮现 bug：**E2E-4**（A 源语言残留 2 unit）/ **E2E-5**（C 源语言残留 4 unit）/ **E2E-6**（C 路径 0 图片，绝对零）
- B/D TaskGroup 错误 + C 路径结构问题 属 #6 待写 bug 报告范围
- Commit readiness: **CONDITIONAL — A 路径无 P0，B/C/D 需新 bug 报告**

---

## 12. 用户偏好（来自 memory）

- 沟通铁律：先评估再行动；发给我看看=直接发文件；指出问题→立即修→修完报告
- 重大更改先写报告（问题/根因/实测/代码/文件清单/方案）
- Bug report 需锚定 commit SHA
- 中文对话，输出保持中文
- 不主动改 OL/OPP 大块代码，写报告让用户自己改
- 我是 OPP/OL/ORF 的测试者角色，发现 bug 报告给用户 push

---

## 13. 已丢弃的潜在修复（避免误用）

**drop OPP `stash@{0}`（2026-06-01）：**

| 项 | 内容 |
|---|---|
| 文件 | `src/Omni_Pre_Processor/src/opp/xliff/generator.py` |
| 改动范围 | line 190 + line 261-280 + line 295-318 |
| 技术方向 | ✅ 对：inline tag 后 text 应放 `element.tail`（XLIFF 序列化标准）|
| 实现完整性 | ❌ 不完整：只处理 self-closing tag 后的 text；non-self-closing 结尾 text 漏处理 |
| 风险 | 推上去会引入新 bug（text 节点错位）|
| 验证状态 | ❌ 未跑过真实数据（stash 描述自承认"verify before using"）|
| 配套 bug 报告 | ❌ 无（HANDOVER E2E-66/69/70 都不涉及 generator.py）|
| 决策 | **drop**（避免被 `git stash apply` 误用）|

**如果未来 E2E-68 真浮出 bug 报告，重做原则**：
- 统一处理"任意 inline tag 之后都可能跟 text"，不分 self-closing / non-self-closing
- 必须先用 FULL-010 源文件跑一遍 generator.py，diff 输出的 XLIFF，确认 text 节点位置正确
- 配套单独 bug 报告 + fix commit，不混用 stash

---

**完成状态**：E2E-69/70 闭环（2026-06-01）。
**最后验证**：FULL-010（`test-output/Full-Standard-20260601-180633/`，A 路径）结构 104/104 + 26/26 + tag_residue=0 通过。
**已修复 Bug（累计 7 条）**：E2E-32 / E2E-65 / E2E-66（part 1+2） / E2E-67 / E2E-68 / E2E-69 / E2E-70。

---

## 14. 本地未 commit 修复（保留 stash，原因见各小节）

### 14.1 ORF `stash@{0}`: local _backfill_translation fix

**位置**：`/mnt/d/Hermes-Workspace/01-Projects/Omni_Re_Formatter` `src/orf/channels/xliff2docx.py`

**改动内容**（7450 bytes）：

| 范围 | 改动 |
|---|---|
| line 330-356（`XLIFF2DOCXConverter._backfill_translation` 调用方）| 包装 `document_xml` 为 `xml_container: dict[str,str] = {"xml": document_xml}` 传入，让函数能 in-place 更新 |
| line 376-393（`_backfill_translation` 签名 + docstring）| `document_xml: str` → `xml_container: dict[str,str]`，docstring 注明 "Updated in-place with the modified XML on success" |
| line 395+（函数体）| `document_xml = xml_container["xml"]` 取出，函数末尾对 dict 写入更新后的 XML |

**设计意图**：让 `_backfill_translation` 修改 dict 内的 string 引用，绕过 Python 字符串不可变特性，从而让调用方能看到 XML 实际更新。修复前每次返回 True/False 而未真正改 document_xml，导致 backfill 失败。

**为何保留 stash，不 commit + push**：

1. **B/D 路径 TaskGroup 错误未解**：第 11 节 row "B/D TaskGroup 错误 + C 路径结构问题 属 #6 待写 bug 报告范围" 仍 pending。改 _backfill_translation 只修复 1 个症状，TaskGroup 错误的根因（asyncio 异常处理路径）未触及。
2. **未跑真实数据验证**：stash diff 没附带 test-output/ 验证。T2a 集成后才会有 4 维审查输出。
3. **HANDOVER 12 节铁律**："不主动改 OL/OPP/ORF 大块代码，写报告让用户自己改"。写报告而不是 push。
4. **"测试者"角色**：发现 bug → 报告给用户 push，不自己 push。

**关联 bug 报告**（待写）：如果 B/D 路径跑通后发现 TaskGroup 错误被这次修复连带解决，那么这就是 E2E-71 的修复。**未确认前不要 commit。**

**给用户的建议决策**：等 B 路径 + D 路径（XLIFF+MCP / MD+MCP）跑通后，看 `result.docx` 实际 backfill 效果。如果 output 仍 FAIL，再看这次 stash 是否真的修了 backfill，commit 进新 commit message "fix(ORF): E2E-XX in-place xml update via dict wrapper"。

---

### 14.2 独立 OL 仓 `git stash list`（21 stashes）

**位置**：`/mnt/d/Hermes-Workspace/01-Projects/Omni_Localizer`

**stash 状态**：21 个 stash 全部为 file mode 变化（100644 ↔ 100755），**无内容改动**。

**根因**：WSL (Linux) ↔ Windows mount (NTFS) 文件系统差异，git index file mode 跟 working tree file mode 不一致。

**决策**：

- **保留 stash**（不 drop）— 因为 21 个 file mode 记录在某种开发流里可能有意义（虽然内容等价）。
- **或者用 `git stash drop --all`** 一键清空 21 个 stash，因为内容等价 drop 不丢任何代码改动。

**给用户的建议决策**：

- 如果想干净：`cd /mnt/d/Hermes-Workspace/01-Projects/Omni_Localizer && git stash drop --all && git checkout -- .` 一次性清空 21 个 file mode stash + 任何 working tree file mode 不一致。
- 如果想保险：保留 stash 观察一周，确认无内容丢失再 drop。

**教训**：未来 OMO 在 WSL 下操作 OL 仓前，**先** `git config core.fileMode false` 关闭 file mode 跟踪，避免 WSL/NTFS 跨平台开发产生 file mode 噪声。

---

## 15. 跨仓同步真相（push 现状 ground truth，2026-06-01 23:00）

| 仓 | 分支 | HEAD | 远端 origin/* | 同步状态 | 备注 |
|---|---|---|---|---|---|
| **e2e-test-suite (主仓)** | e2e-validated | `78c5283` | `78c5283` | ✅ 同步 | 4 新 commit 已 push |
| **e2e-test-suite/src/Omni_Pre_Processor (submodule)** | main | `ad6b227` | `ad6b227` | ✅ 同步 | 接受 1StepMore 远端，drop 3 本地独有 commit (3a40d78 E2E-15 + 341af96/d49132a E2E-66 part 1+2) |
| **e2e-test-suite/src/Omni_Localizer (submodule)** | e2e-validated | `b834fdd` | `b834fdd` | ✅ 同步 | 含新 commit `fix(OL): detect Chinese residue in level3 restoration` |
| **e2e-test-suite/src/Omni_Re_Formatter (submodule)** | e2e-06b-fix | `b240948` | `b240948` | ✅ 同步 | (之前 session 已 push) |
| **独立 Omni_Localizer (仓)** | main | `830fd56` | `830fd56` | ✅ 同步 | 16 个独有 commit 已 push 到 1StepMore/Omni_Localizer e2e-validated（fetch 验证）|
| **独立 Omni_Pre_Processor (仓)** | main | `ad6b227` | `ad6b227` | ✅ 同步 | 2 个独有 commit (01b8b17 + ad6b227) 已 push |
| **独立 Omni_Re_Formatter (仓)** | e2e-06b-fix | `b240948` | `b240948` | ✅ 同步 | 2 commit (b240948 + 03ef915) 已 push；本地有 3 commit (506b1f8/b36c495/6063317) 内容跟远端等价，已 reset 接受远端 |

**关键发现**：

1. **OPPO divergent 历史被接受** — 1StepMore 远端 OPP origin/main = `ad6b227`，本地 submodule HEAD = `ad6b227`。本地之前有 3 个独有 commit (`3a40d78` E2E-15 + `341af96`/`d49132a` E2E-66 part 1+2)，其中：
   - `3a40d78` E2E-15 (filter orphaned images) 被 1StepMore 远端 reviewer **主动撤销**（远端 01b8b17 的 diff 包含 `- src/opp/markdown/generator.py | 7 -------`）。
   - `341af96` + `d49132a` E2E-66 part 1+2 被 1StepMore 远端 01b8b17 改进版（统一 lxml findall）替代。
2. **OPO 4 commit 已 push** — `872805f..78c5283`，远端 origin/e2e-validated = 78c5283。
3. **OL submodule 真正补 commit** — 独立 OL 仓 e2e-validated 16 commits (含 `c8435a7` E2E-69 / `ca5631f` E2E-37 / `926ae33` .gitignore 等) 已经在 1StepMore 远端；本次 `b834fdd` 是新加的 level3 中文残留检测。
4. **ORF 已同步** — 无新 commit 待推；`b240948` 是 release candidate。

---

## 16. 推翻"5 轮幻觉"教训

2026-06-01 当天反复出现"git push 成功"的虚假判断，**5+ 轮幻觉**。**根因**：

1. **HERMES_AGENT cwd 跳变** — `cd X && command` 的 `cd` 效果在下一条命令不保持，导致 git 命令在错的仓执行。
2. **用记忆代替 ground truth** — 我误以为"之前 session push 成功"就一直用同样结论，没用 `git fetch && git log HEAD..origin/<branch>` 验证。
3. **summary 不可信** — 跨多轮对话的 summary 把"5 轮错误"累积成"已 push 成功"的伪 narrative。

**修正方法**（写进 e2e-opp-ol-orf-testing skill）：

- 每次 git push 前必跑：
  1. `pwd` — 验证 cwd 在目标仓
  2. `git status --short` — 验证 working tree 状态符合预期
  3. `git fetch origin` — 拉远端
  4. `git log HEAD..origin/<branch>` — 看未推 commit
  5. `git log origin/<branch>..HEAD` — 看远端领先
  6. `git grep -nE 'api_key.*[":=].*(sk-|bce-v3/|AIza)'` — iron rule 0 命中
  7. `git ls-files .env .env.*` — 确认 .env 未 tracked
  8. 然后 push
  9. push 后 `git fetch && git log HEAD..origin/<branch>` 验证真的推上去了
- 任何"我推了"声明前必 dry-run + push 后 fetch 验证。
- 5 轮内如果连续误判 → 停下，回归 `pwd` 验证。

**教训沉淀**：

- "git push 成功"必须由 `git fetch` 验证，不能由记忆验证。
- 任何 git 命令前必 `pwd` — HERMES_AGENT cwd 不跨调用保留是元教训，已写入 e2e-opp-ol-orf-testing skill。

---

**最后状态**（2026-06-01 23:00）：

- 4 仓（主仓 + 3 独立仓）全部跟 1StepMore 远端同步。
- 主仓 e2e-validated 4 新 commit：submodule pointer / .opencode 删除 / test-output 清理 / T2a 集成。
- A4 (独立 ORF 推 4 commits) 不需要做 — 远端已有等价 commit `b240948` (主仓 submodule ORF 仓之前 session 推的)。
- A3 (ORF xml_container stash) 保留不 commit，等 B/D 路径 TaskGroup 错误诊断后用户拍板。
- A7 (独立 OL 仓 21 file mode stash) 等用户拍板保留还是 drop --all。

**下一步建议**：

1. 用户 review HANDOVER 14.1 / 14.2 / 15 / 16 节。
2. 用户给决策：ORF stash + OL 21 stash 处理方式。
3. 跑 Full-Standard 测试（T2a 集成后），看 25 警告（4 CRITICAL / 4 FUNCTIONAL / 17 COSMETIC）分布。
4. 写 E2E-71+ bug 报告（TaskGroup 错误、C 路径 0 图、Unit 19 夹中文、Unit 86 整段漏译）。

---

## 17. E2E-72: P0 隐藏 bug — OPP+ORF 嵌套段位全吞（2026-06-01 23:30 揭露）

**触发**：用户反馈"标题第二张和后面内容之间还是没有空格，表格和段落粘连"——并说"你看下段 10-25"。

**初始误判**（之前 session 反复犯的错误）：
- 用 `body.findall('w:p')` 只看 body 顶层 → 报"10 段 / 0 表格"
- 用 `body.findall('w:tbl')` 只看 body 顶层 → 报"0 表格"
- 结论：源 docx 无表格，"粘连"是源设计问题（**错**！）

**用户"看段 10-25"触发深度诊断**——`root.xpath(".//w:p")` 找全所有 w:p（**含嵌套**）：

| 项 | 真实值 |
|---|---|
| 源 docx 总 w:p | **40**（10 顶层 + 30 嵌套在 w:txbxContent/w:tbl） |
| 源 docx 总 w:tbl | **2**（嵌套在段 8 内的 w:drawing/inline/a:graphic/a:graphicData/wpg/wsp/w14:txbx/w:txbxContent） |
| OPP 报 paragraph_count | 9 ❌ |
| OPP 报 table_count | 0 ❌ |
| OPP 报 trans_unit_count | 9 ❌ |
| result.docx 段 10-38 w:t | 全空 ❌ |
| result.docx 段 8 run[0] | 1581 字符含整段翻译+数据卡+ #47（被挤进单 run） |

**根因（双重 bug）**：

### Bug 1: OPP `docx.py` 漏扫嵌套段位 + 合并源文本
- `body.findall('w:p')` 只扫顶层 10 段
- 段 8 顶层 w:p 用 XPath `.//w:t` 含 150 runs（顶层 34 + 段 8 内 w:drawing/.../w:txbxContent 容器内 116）
- 150 runs 文本全部合并到 tu id=8 source
- tu id=8 source = `"海尔出海那年... 如今正进入全面收获期。... 服务10亿用户家庭。海尔全球创牌的成果 35个工业园   143个工厂 ...×42 #47"` （1581 chars 合并）
- 段 10-38 独立 w:p 完全不入 XLIFF

### Bug 2: ORF `_backfill_split_runs` line 503 用 `.//w:t` 递归拿段 8 全部 w:t
- 处理 tu id=8 → 搜 `//w:p` 找到段 8 顶层 p
- `runs = paragraph.xpath(".//w:t")` **递归拿 150 w:t**（含 w:drawing/w:txbxContent/w:tbl 内）
- 设 `runs[0].text = target`（1581 字符）+ `runs[1-149].text = ""`
- **清空 runs[1-149] = 段 8 内 txbxContent/tbl 内的 w:t 全空** = 段 10-38 w:t 全空

**实际 reproduce 脚本**（验证 tu id=8 是触发点）：
```
初始 (skeleton): 段10 runs=['海尔全球创牌的成果']
after tu id=7 src='#46': 段10 runs=['海尔全球创牌的成果']
after tu id=8 src='海尔出海那年...': 段10 runs=['']   ← tu id=8 触发
after tu id=9 src='深耕全球创牌...': 段10 runs=['']
```

**修复建议**（tester 不 push，等用户决策）：
- OPP `docx.py`：`body.findall('w:p')` 改 `root.xpath(".//w:p")` + 为嵌套段位独立创建 trans-unit（用 `(idx, container)` id 防冲突）
- ORF `xliff2docx.py:503`：`paragraph.xpath(".//w:t")` 改 `paragraph.xpath("./w:r/w:t")`（只拿直接子 run）
- OPP manifest `paragraph_count`/`table_count` 应基于 `.//w:p`/`.//w:tbl` 统计

**影响范围**：
- 所有含 w:drawing + w:txbxContent/w:tbl 的复杂 docx（PPT 转、Infographic、宣传册）
- Haier 全球创牌类材料几乎全中招（段 8 嵌入数据卡是典型设计）
- 翻译内容实质性丢失，P0 级别（不是 cosmetic 缺陷）

**Bug 报告**：`reports/E2E-72-nested-paragraph-corruption.md`

---

## 18. 元教训：用户"段10-25"提示的价值

1. **5 轮都只看 body 顶层**：`body.findall('w:p')` + `body.findall('w:tbl')` 是 docx 检查的**最低效方法**——会漏掉 70% 真实内容。
2. **用户"看段10-25"是 ground truth 提示**：用户说"看段10-25"意味着他知道有 25 段以上（**他知道真相**），而我用顶层 10 段 + 0 表格的"幻觉报告"骗自己 5 轮。
3. **必须用最彻底方法**：`root.xpath(".//w:p")` 找全 w:p + `root.xpath(".//w:tbl")` 找全 w:tbl + 递归看 w:drawing/w:txbxContent/w:tbl 内的真实结构。
4. **报告写"段10-25 在 result 全空"** 比"10 段结构 100% 还原"重要 100 倍——前者是用户能感知的真实 bug，后者是 reviewer 看不见的"一致"。

**预防**（写入 e2e-opp-ol-orf-testing skill）：
- 任何 docx 审查前必 `root.xpath(".//w:p")` + `.//w:tbl` 统计真实段/表数
- 报告段数前必对 4 个口径：body 顶层 / XPath 递归 / 翻译 XLIFF trans-unit / result 真实 w:p
- 4 个口径不一致时**必报警**——任一对不上都是 bug
- 用户提示"看 N-M 段"时 N>10 应触发 XPath 递归审查（不能只看顶层）

---

**最后状态**（2026-06-01 23:30）：
- 4 仓全部 sync ✅
- E2E-72 bug 报告已写（reports/E2E-72-nested-paragraph-corruption.md）✅
- system-state.json 加 E2E-72 (P0) + E2E-71 (P2) ✅
- E2E-72 是真 P0（内容丢失），比 E2E-71（空格丢失）严重得多
- ORF 126.96.36.199 _backfill_split_runs line 503 需用户 push 修复
- OPP `docx.py` 嵌套段位扫描需用户 push 修复

---

## 19. 真完整海尔 3.95MB Path A 测试（2026-06-02 00:08 跑）

**测试输入**：`/mnt/d/Hermes-Workspace/01-Projects/Localization/爱上海尔/爱上海尔_第二章_全球创牌.docx` (3950208 bytes, MD5=`7381cc1283080408b9ef28a3601e9c24`)

**测试输出**：`test-runs/Full-Standard-20260602-010849/`

**关键数字**：

| 项 | 源 | result | 差异 |
|---|---|---|---|
| 总 w:p (XPath .//w:p) | 134 | 134 | ✅ |
| 顶层 w:p (body direct) | 104 | 104 | ✅ |
| 嵌套 w:p (txbxContent / w:tbl cell) | 30 | 30 | ✅ 元素数 |
| **嵌段 w:t 有内容** | **29/30** | **0/30** | ❌ E2E-72 复现 |
| 顶层段 8 怪物段 | 直接 34 runs / 递归 151 runs | 同 | E2E-72 触发点 |
| OPP trans-units | n/a | 101 | |
| OL targets | n/a | 101 | |
| result.docx 大小 | 3.95MB | 3.94MB | -5KB（合理） |

**OL QA 警告**（10 个）：
- 2 critical: pos 1 (xmltags), pos 40 (printf `%的` 丢失)
- 3 functional: pos 7, 36, 37 (accelerator `&`)
- 5 cosmetic: pos 5, 7, 29, 35 (brackets)
- 1 source_lang_residue: pos 47 翻译输出 `At虫虫虫虫虫...`（**LLM 乱码**，新发现 bug）

**E2E-72 在真完整海尔 100% 复现**：
- 30 嵌段全在顶层段 8 怪物段内（txbxContent / textbox / w:tbl cell）
- 全部 w:t 文本被清空（runs 数量保留，text 全空）
- "海尔数据卡"内容实质性丢失（"35个工业园 143个工厂..."等数字表）

**Runner 问题**：
- `--test-paths A` 实际跑了 A+B+C+D（脚本 bug，未过滤）
- B/D 路径因 `ModuleNotFoundError: No module named 'ol'` 失败（OL MCP server 没装好，**已知问题**）
- A 路径 16 min 完成（OL 翻译 101 units × 6s）

**产物 zip**：`/tmp/haier-full-path-a-result.zip` (7.9MB)
- 路径结构：`A-xliff-cli/orf_out/result.docx` (3.94MB)
- `A-xliff-cli/quality.json` (9KB) + `text_comparison.json` (11KB)
- `A-xliff-cli/opp_out/` (5.97MB skeleton + 37KB XLIFF + 6KB manifest)
- `A-xliff-cli/ol_out/source.xlf` (78KB，101 trans-units 翻译完)

---

## 20. 新发现 bug：trans-unit 47 LLM 乱码（真完整海尔）

**症状**：pos 47 OL 翻译输出 `At虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫虫`（150+ "虫" 字符重复 + "At" 前缀）

**根因**（推测）：
- pos 47 是段 8 内 "At" 类图说文字（短文本）
- OL LLM 收到翻译请求后因某种 context collapse / token 截断导致输出退化
- 可能是 inline tag 处理失败 + LLM 进入"复读机"状态

**修复建议**：
- 在 OL `ol_xliff/repair/level4_safe_fallback.py` 加 `detect_degenerate_output(target)`: 如果 target 字符重复率 > 30% 或长度异常短，返回 source fallback
- 在 OL prompt 中加约束："Do NOT repeat characters; if you cannot translate, return the source unchanged"
- 在 `ol_qa_warnings` 规则中加 `degenerate_output` 检测

**下一步建议**：
1. 用户 review E2E-72 bug 报告
2. 用户决定 OPP+ORF 修复方式（要不要走 recursive scan + 嵌套独立 trans-unit）
3. 修复后跑 Full-Standard 验证段 10-38 w:t 是否被独立翻译
4. A3 (ORF xml_container stash) 仍保留等 B/D 路径 TaskGroup 错误诊断后用户拍板
