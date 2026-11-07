# scope: scripts/

确定性脚本层：`validation/`（场景库运行器/覆盖率/diff/交付）、`doc_inventory.py`（文档真相 + 治理检查 C1–C7）、`sync_version_docs.py`（版本同步）、`pre_commit_python.sh`（Windows 解释器解析）。
文档真相门禁用法见根 `AGENTS.md` Commands 节；改本目录 checker 后须重跑各仓 `--check` 与 `tests/test_doc_inventory_copy_parity.py`。
