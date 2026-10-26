> **Status: ARCHIVED (2026-10-26). Reason: Phase artifact; the executable scenario library replaced the prose plan. Superseded by: `tests/` + `scenarios/`.**

# 真实 LLM E2E 测试方案 — 两层级

## 守则

### 第零条：测试前清理中间件

每次测试运行前，必须清除所有前次遗留的中间产物，防止旧资产对测试结果产生误导。

**清理清单：**
- [ ] `/tmp/ol-*/`、`/tmp/e2e-*/`、`/tmp/orf-*` — 旧管线产物
- [ ] `~/.omni_cache/` — OL/ORF 缓存
- [ ] 各 repo 下的 `.omni_cache/` 目录
- [ ] 测试语料目录下的旧输出文件（如 `*_EN.docx`、`*_EN_QA.docx`）
- [ ] OL venv 中的旧模型池缓存
- [ ] 各 CLI 的 `--clear-cache`

**验证：** `find /tmp -maxdepth 2 -name "*.xlf" -o -name "*.docx" | grep -v "爱上海尔" | wc -l` 应为 0

### 其他守则

- **Level 1（小文件）**：每个 feature 独立验证，用小语料（1-3 段），快速 + 便宜。验证 feature 存在且效果正确。
- **Level 2（大文件）**：全管线集成验证，用真实文档（爱上海尔完整版），验证性能/稳定性/资源管理。
- **准入条件**：Level 1 全部通过 → 才能进入 Level 2。
- **不重复测试已在单元测试中覆盖的逻辑**（如 CLI flag parsing、数据类校验）。

---

## Level 1 — 小文件逐项验证

### 1.1 OPP 提取

| # | 测试项 | 输入 | 验证点 | 预期 |
|---|--------|------|--------|------|
| 1 | DOCX → XLIFF + MD | 2 段中文小 DOCX | XLIFF 含 `<source>`、`resname`、`original` | 2 trans-unit |
| 2 | DOCX → 骨架 ZIP | 同上 | skeleton.zip 可解压，含 document.xml | 结构保留 |
| 3 | 样式映射 | 带标题样式的 DOCX | `--style-map` 后 heading 级别正确 | h1/h2 正确识别 |
| 4 | XLIFF 验证 | 合法/非法 XLIFF | `--validate-xliff` 报告正确 | 合法 pass / 非法 fail |

### 1.2 OL 翻译核心功能

| # | 测试项 | 输入 | 命令 | 验证点 |
|---|--------|------|------|--------|
| 5 | translate-md 基础 | small.md（3 段 zh） | `ol translate-md -s zh -t en` | 输出英文 MD，段数一致 |
| 6 | translate-md + --glossary | small.md + glossary.json | `ol translate-md --glossary g.json` | 术语正确命中（如 海尔→Haier） |
| 7 | translate-md + --report-coverage | same | `+ --report-coverage` | 覆盖率报告打印 |
| 8 | translate-md + --polish | small.md（含 typo/连词缺） | `+ --polish` | polish 标注出现在 stderr/XLIFF note |
| 9 | translate-xliff 基础 | small.xlf（2 trans-unit） | `ol translate-xliff -s zh -t en` | 输出 `<target>` 元素 |
| 10 | translate-xliff + --styleguide | small.xlf + styleguide.json | `+ --styleguide` | 译文 tone 符合 styleguide |
| 11 | translate-xliff + --polish | small.xlf | `+ --polish` | polish note 出现 |
| 12 | translate-xliff + --glossary + --polish + --report-coverage + --styleguide | **全组合** | 一次性全部启用 | 所有 flags 共存不冲突 |

### 1.3 OL 辅助功能

| # | 测试项 | 输入 | 验证点 |
|---|--------|------|--------|
| 13 | profile-doc | small.docx | 输出 tone/register/vocabulary JSON |
| 14 | shield-md | 含代码块/链接的 MD | `[OL:CODE:0000]` 标记出现 |
| 15 | unshield-md | 已屏蔽的 MD | 原文恢复 |
| 16 | extract-terms | 中文 MD | 输出 top-N 术语列表 |
| 17 | judge-text | 源+译文对 | 输出评分 |
| 18 | verify-terms | 译文 + glossary | 术语使用正确/错误报告 |
| 19 | disambiguate | 含歧义词的句子 | 正确选择词义 |
| 20 | search-tm | 含 TM 的句子 | 返回匹配条目 |
| 21 | add-tm-entries | 新句对 | TM 中可检索到 |

### 1.4 ORF 重建

| # | 测试项 | 输入 | 验证点 |
|---|--------|------|--------|
| 22 | apply-xliff → DOCX | small.docx + 翻译后 xlf | DOCX 中 `<w:t>` 含目标语言 |
| 23 | apply-xliff → PPTX | small.pptx + xlf | PPTX 中文本替换 |
| 24 | apply-xliff → HTML | small.html + xlf | HTML 文本替换 |
| 25 | apply-md → DOCX | translated.md | `--target-format` 文档正确 |
| 26 | apply-md → PDF | translated.md | PDF 生成成功 |
| 27 | apply-md → PPTX | translated.md | PPTX 生成成功 |
| 28 | 图片注入 | DOCX + images.json | 图片位置正确 |
| 29 | detect-format | 各种文件 | 格式检测正确 |

### 1.5 管线级（小文件）

| # | 测试项 | 流程 | 验证点 |
|---|--------|------|--------|
| 30 | OPP→OL→ORF 完整小管线 | small.docx → OPP → OL(with SG+GL+Polish) → ORF | 最终 DOCX 含英文译文，结构完整 |
| 31 | OPP→ORF apply-md 替代路径 | small.docx → OPP(md) → ORF apply-md | 最终 DOCX 含英文 |

---

## Level 2 — 大文件全管线集成测试

**准入条件**：Level 1 全部通过。

**测试语料**：爱上海尔_第二章_全球创牌（完整中 DOCX，~440KB，20 trans-units）

| # | 测试项 | 流程 | 验证点 | 额外 QA |
|---|--------|------|--------|---------|
| 32 | 全管线 + 所有 QA flags | DOCX→OPP→OL(SG+GL+Polish+Coverage)→ORF | 20/20 trans-units 翻译 + 回填 | 见下方 QA 清单 |
| 33 | 大文件 translate-md | OPP 提取 MD → `ol translate-md` | 全部段翻译 | 词汇量/速度 |
| 34 | 大文件多格式重建 | ORF apply-md → PDF / PPTX / HTML | 生成成功，内容完整 | 跨格式验证 |

### Level 2 QA 验证清单

每个大文件测试后执行：

```
□ Phase 1: 结构完整性
   - 段落数匹配（源 vs 目标）
   - 图片数匹配 + MD5 一致
   - 节标记保留（#46, #47 等）

□ Phase 2: 源语言残留扫描
   - Body <w:t> 无中文
   - 文本框 / 表格 / 页眉页脚扫描
   - 图片描述文字扫描

□ Phase 3: 术语审计
   - Glossary 术语命中率
   - 无源语言术语残留
   - 目标术语一致性

□ Phase 4: 语言质量抽样
   - 5-8 段 native-reader 审查
   - Chinglish / adverb overuse / 句式多样性

□ Phase 5: 本地化惯例
   - 数字格式（千分位）
   - 货币单位统一

□ Phase 6: Polish 标记校验
   - XLIFF 中 polish:NOTE 数量 > 0
   - 无虚假标注
```

---

## 测试顺序图

```
Level 1 ─────────────────────────────────────────────────────
│
├─ 1.1 OPP 提取 ──→ [1-4] 小 DOCX
│
├─ 1.2 OL 翻译核心 ──→ [5-12] 小 MD/XLIFF，逐步叠加 flags
│
├─ 1.3 OL 辅助功能 ──→ [13-21] 小输入
│
├─ 1.4 ORF 重建 ──→ [22-29] 小文件 + 翻译 xlf
│
├─ 1.5 小管线集成 ──→ [30-31] 全流程走通
│
└─ ✅ Level 1 全部通过
         │
         ▼
Level 2 ─────────────────────────────────────────────────────
│
├─ 2.1 全管线 + QA ──→ [32] 爱上海尔完整版 + 全部 flags
│
├─ 2.2 大文件 MD 路径 ──→ [33] translate-md
│
├─ 2.3 大文件多格式 ──→ [34] apply-md → PDF/PPTX/HTML
│
└─ 6-Phase QA 验证
         │
         ▼
    ✅ 测试完成
```

---

## 测试数据准备

### Level 1 小文件清单

需提前创建以下文件（都在 e2e-test-suite 下）：

| 文件 | 内容 | 用途 |
|------|------|------|
| `test_corpus/small_zh.docx` | 2 段中文（~50 字） | OPP 提取 + ORF 回填 |
| `test_corpus/small_zh.md` | 3 段中文（~100 字） | OL translate-md |
| `test_corpus/small_zh.xlf` | 2 trans-unit | OL translate-xliff |
| `test_corpus/small_zh.pptx` | 2 页中文 | ORF 多格式 |
| `test_corpus/small_zh.html` | 中文 HTML 片段 | ORF 多格式 |
| `test_corpus/glossary_test.json` | 3-5 个术语（含海尔） | Glossary 测试 |
| `test_corpus/with_code.md` | MD 含代码块/链接 | shield 测试 |
| `test_corpus/with_disambig.md` | 含歧义词 | disambiguate 测试 |

### Level 2 大文件

爱上海尔_第二章_全球创牌 - E2E测试专用.docx（已在 repo 中）

---

## 注意事项

1. **API Key 管理**：不 `source.env`，只 export 5 个 key
2. **LiteLLM 延迟**：首次 import 约 30s，设置 `LITELLM_LOG=ERROR` + 充足超时
3. **OL 工作目录**：`cd /mnt/d/Hermes-Workspace/01-Projects/Omni_Localizer`（找 config）
4. **OL_CONFIG_PATH 陷阱**：不要从 .env 导入
5. **ORF 安全策略**：需设 `MCP_ALLOWED_DIRECTORIES`
6. **快速失败**：每个测试独立运行，一个失败不阻塞其他
