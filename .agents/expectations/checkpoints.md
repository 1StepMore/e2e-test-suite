<!-- 离散检查点（期望的执行映射,非定义）：每行把一个 checkpoint 绑到仓库既有可复现证据。
新增 checkpoint 须同时给出可复现判定方式；禁止仅写"人工确认"。 -->
# Checkpoints — Omni Suite

| checkpoint | 应发生的状态变化 | 判定方式（可复现证据） |
|---|---|---|
| CP-01 | 场景库可枚举且契约自洽 | `python scripts/validation/run_validation.py --list` 退出码 0；`--check` 退出码 0 |
| CP-02 | 工具面与场景覆盖一致 | `python scripts/validation/coverage_audit.py` 无未覆盖工具 |
| CP-03 | 文档真相成立（含治理检查 C1–C7） | `bash scripts/pre_commit_python.sh scripts/doc_inventory.py --check` 退出码 0 |
| CP-04 | 一致性 gate 实测能挡 CI | 故意制造断链 → `doc_inventory.py --check` 退出码非 0（CI: `lint.yml` doc-consistency 步骤） |
| CP-05 | 单场景终态可复现 | `python scripts/validation/run_validation.py --scenario <name> --tier 1` 产出 `validation-runs/<ts>/scenarios.json` |
| CP-06 | 版本文档同步 | `python scripts/sync_version_docs.py --check` 退出码 0 |
| CP-07 | 期望锚点映射完整 | `.agents/expectations/INDEX.md` 引用的每个锚点在 `scenarios/STANDARDS.md` 中存在（C7） |
