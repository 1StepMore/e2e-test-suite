# 矩阵归属（模态分工）

> owner 2026-11-19 定：**视频 / 语音 / 图片 = code profile（本机 code 侧）**；**文本 = owner 侧 agent / harness**。
> 判定口径见 `docs/dev/matrix-verdict-policy.md`（跨仓契约，勿只改本仓副本）。

## 本仓矩阵与格子数

- `scripts/nightly_gap.py` —— DoD = **201 格 × 2 通道（CLI / MCP）= 402 次**。
  201 = md 路径 11 输入 × 15 输出（165）+ xliff 路径 6 × 6（36）。
- `scripts/validation/artifact_matrix.py` —— 按产物断言，P0/P1 失败驱动非零退出（本仓唯一真门禁）。
- `utils/e2e_matrix_runner.py` —— 6 场景 × 16 格式 = 96（报告在 `campaign-realistic-e2e/reports/`，现存 2026-06-23 版已过时）。

## 谁跑哪些格

| 模态 | 格 | 格数 | Owner |
|:--|:--|--:|:--|
| 字幕 | 任意输入 → `srt`（11 输入各 1 格） | **11** | **code**（语音/字幕模态） |
| 文本（文档格式互转） | md 路径其余 154 格 + xliff 路径 36 格 | **190** | **owner 侧** |
| 图片（产物中的图片/封面） | 随 artifact assertions 覆盖 | — | **code**（见图即验） |

命令：

```bash
# CLI 通道（全量或按格）
python3 scripts/format_matrix_verifier.py --json --out-dir <dir>
python3 scripts/format_matrix_verifier.py --subset "docx>srt"
# MCP 通道
python3 scripts/mcp_matrix_verifier.py
# 差距矩阵（两通道合一，402 格）
python3 scripts/nightly_gap.py --out-dir <dir> --json-out <gap.json> --md-out <gap.md>
```

## 硬规矩

- `nightly_gap.py` 三条抗作弊规矩**不许放宽**：跳过≠通过、解释器先探活、拿不到矩阵一律 exit 2（不许判绿）。
- 报告里的 skip 必须写在报告面上，不许从分母里消失。
- 本仓只跑不自评：缺陷出现在兄弟仓 ⇒ 在本仓提 issue 指出归属仓 + 证据，不跨界修改。
