# Real-Model Quality Baseline — Omni Suite

> 本文件记录**真实 LLM** 下 HUMAN-QUALITY 判据的数值基线。阈值以
> [`scenarios/STANDARDS.md`](../../scenarios/STANDARDS.md) 为唯一出处，此处不得发明新阈值。
> 防假绿红线：FAKE_LLM 产出永不入册（`STANDARDS.md#fallbacks-never-evidence`）。
>
> **刷新规则**：每次全库 tier-2 载荷 run 落盘后更新「最新基线」行；judge_overall 相邻观测差
> > 0.5/5 或任何 anchor 跨阈值时，先按失败定性协议（AGENTS.md 循环治理规范）归因再更新。
>
> **模型池**：免费档（Zhipu GLM 系 reasoning 模型 + 池内 fallback；OL
> `config/local.yaml` + `config/default.yaml`，key 经 `${ENV_VAR}` 引用）。
> 已知方差：判官响应截断（`finish_reason=length` → fail-closed 降级分）偶发。

## 最新基线（2026-11-06 · run `20261106-061539` · 全库 127 passed / 0 failed）

| Anchor | 发布标准（STANDARDS.md） | 本次观测 | 备注 |
|---|---|---|---|
| `#lqa-threshold` | judge_overall ≥ 4.0/5 | docx **4.06** · epub **4.82** · pptx **4.91**（n=6 each） | docx 4.06 贴线：见「已知方差」——观测区间下缘 |
| `#para-ratio` | out/src ∈ [0.95, 1.05] | **1.000**（docx 8/8 · pptx 6/6） | |
| `#cjk-density` | < 5% | **0.00%**（docx / epub / pptx） | |
| `#punct-hygiene` | 英文目标 0 个中文标点 | **0 hits**（epub strict-set 2 hits = pandoc smart quotes，场景已声明的非缺陷） | |
| `#drawing-count` | src == out | **2 == 2**（docx） | T13-02 已关闭（e2e-test-suite#244） |
| `#untranslated-units` | 0 | **0**（全部管线场景） | |

## 历史锚点（真实 LLM，按时间）

| 日期 | run / 载荷 | judge_overall | 备注 |
|---|---|---|---|
| 2026-10-27 | 本地 tier-2 轮（docx 14/14、pptx 11/11） | 4.85 / 4.12 | 首次真模型复验，T13-01/T13-02 GAP CLOSED |
| 2026-11-01…04 | CI nightly × 4（main） | 4.93–4.95（Q2 每晚绿） | T13-01 稳定；T13-02 复燃（#244，当时未修） |
| 2026-11-05 | `20261105-012731`（docx 点检） | 4.95 | |
| 2026-11-06 | `20261106-012511`（docx，#244 修复后复验） | 4.99 | drawings 2→2 |
| 2026-11-06 | `20261106-045637`（全库第一次） | epub Q2 **3.22** | 判官截断（fail-closed）→ 定性为波动，重跑自愈 |
| 2026-11-06 | **`20261106-061539`（全库，本表锚定批次）** | 4.06 / 4.82 / 4.91 | 127 passed / 0 failed |

## 已知方差来源与判读口径

- **判官截断**：免费档 reasoning 模型偶发 `finish_reason=length`，OL 判官 fail-closed
  返回降级分（`20261106-045637` epub Q2 3.22 即此因，stderr 有截断记录）。缓解
  （max_tokens 预算）属 OL follow-up，见 LOOP-LOG 2026-11-06 事件。
- **judge_overall 观测区间**：4.06–4.99（2026-10-27 以来全部 ≥ 4.0 过线）。4.06 已贴
  发布线：**单次 < 4.0 不构成回归信号**；连续两晚 nightly < 4.0 才按回归处理（先定性后处置）。
- **6 个 unconfigured 为客观缺 env**（TM 网络 / OCR / MSG / ipynb / youtube 等），
  不是 pass 也不是 fail——口径见 `scenarios/STANDARDS.md`。
