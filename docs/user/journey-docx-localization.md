# 旅程：DOCX 端到端本地化（OPP → OL → ORF）

- 基线：`86db206e`（2026-11-07）｜ 角色：User（黑盒）｜ 判定载体：`tests/e2e_runner.py` + `e2e-tests.yml`
- 前置：`bash scripts/setup_dev.sh` 成功；冒烟模式设 `OMNI_TEST_FAKE_LLM=1`（仅管线联调，不是质量证据——根 AGENTS.md Critical Notes #1）

## 步骤结果

| # | 步骤（公开入口） | 预期 | 实际 | 判定 |
|---|---|---|---|---|
| 1 | `opp <doc>.docx --target-format both --source-lang en --target-lang zh --output-dir <dir>` | 产出 `.md` + `.xliff` + skeleton/manifest，退出码 0 | 待执行 | ⬜ |
| 2 | `ol translate-md <dir>/<doc>.md -s en -t zh -o <dir2>` | 产出译文 `.md`，退出码 0 | 待执行 | ⬜ |
| 3 | `orf apply-md <dir2>/<doc>.md --target-format docx -o result.docx` | 产出 `result.docx`，可用 python-docx 打开（#opens-docx） | 待执行 | ⬜ |
| 4 | 质量抽验（可选，需 LLM key） | `scenarios/STANDARDS.md` HUMAN-QUALITY 锚点全过 | 待执行 | ⬜ |

## 差距清单

（执行后填写：docs-bug / product-bug / ux 三类，每条附证据路径）

## 旅程判定

⬜ pass / fail / blocked（执行后填写，附 `validation-runs/<ts>/` 证据）
