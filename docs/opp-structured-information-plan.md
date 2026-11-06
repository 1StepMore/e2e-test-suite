# OPP 结构化信息增强计划（章节 / 分块元信息 / 术语提取）

> 立项：2026-11-06（goal 批次 P3）。本文件是三支柱的里程碑与验收锚载体——在此之前的
> "推进计划"没有可推进的载体（四处 repo 均无计划文档）。
> 既有原则（`src/opp/chunker.py` 既有注释）：**OPP 只定结构，边界由下游定**——chunker
> 输出结构级 `Chunk`/`ChunkMeta`，不替 Pipeline/OL 决定分块边界；术语候选同理。

## 底账（2026-11-06 盘点）

| 支柱 | 现状 | 位置 |
|---|---|---|
| 章节 | 初版已实现（v0.4.0，2026-05-25）：`ParagraphData.chapter/page`、EPUB spine 章节、PDF 页映射、MD 输出 `<!-- chapter: … -->` | `opp/extractors` + pipeline |
| 分块元信息 | 结构级实现：`Chunk`/`ChunkedResult`/`ChunkMetaBuilder`（按章节聚合 + 字符偏移） | `src/opp/chunker.py` |
| 术语提取 | **OPP 侧为零**；术语面在 OL（`extract_terms` / `get_relevant_terms` / `verify_terms` / `add_tm_entries`），OL 审计 gate 已于 2026-11-06 接入 `run_quality_gates`（M1，见下） | `ol_terminology` |

## 里程碑

### M1（已完成 2026-11-06）：OL 术语审计 gate 接线 —— 归属 OL 仓

- 内容：把 `ol_terminology/verifier.py` 的 `verify_translation`（2026-10-22 审阅发现从未
  被 `run_quality_gates` 调用）接入 Gate 2b——glossary 术语在源文出现但译文缺失
  （`TERM_ABSENT`）、渲染与期望不符（`TERM_MISMATCH`）即以 `OL_WARN` 浮出。
- 验收：`Omni_Localizer/tests/test_quality_gates.py::TestGate2bTerminologyAudit`
  （3 用例；家族 126 passed）；配置沿用既有 `quality_gates.terminology` 开关，无新配置面。

### M2（候选）：章节元信息增强 —— 归属 OPP 仓

- 目标：章节边界置信度与连续性标注；`chapter_id` 贯穿 `ChunkMeta`，跨章节聚合可追溯。
- 验收锚：chunker 单测覆盖跨章节聚合；MD 输出的 chapter 注释与 `ChunkMeta` 一致；
  不改变"边界由下游定"原则（只补结构信息）。

### M3（候选）：术语候选抽取（OPP 侧）—— 归属 OPP 仓

- 目标：抽取期输出术语**候选**结构（频次 / 首现位置 / 大小写变体 / 源文坐标系），
  供 OL `extract_terms` 消费；语义过滤与排序由 OL 决定（OPP 只出候选）。
- 验收锚：`extract_document` 产物含 `terms.json` 候选列表 + 单测锁结构；不引入
  语义模型依赖。

## 分工边界

- **OPP**：结构抽取与候选（章节、分块、术语候选）。
- **OL**：语义消费（术语验证 / 注入、分块边界决策）。
- 推进方式：每个里程碑独立 PR 落地，带测试与场景证据；不引入跨仓新依赖
  （ADR 0007 的发布决策教训——先定解析路径再动依赖图）。
