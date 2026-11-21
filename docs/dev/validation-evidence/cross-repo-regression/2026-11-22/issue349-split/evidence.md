# 证据：e2e#349 Windows 原生 24 红拆单（2026-11-22 早班）

- 类别：**治理/链路证据（非真模型质量）** → `confidence=mock`。
- 本轮交付：把 #349 总账的 24 个 deterministic 测试层红，按架构师定稿拆成 9 个子单（C01/C02 合并），红数守恒 24，零遗漏。
- **不是质量通过声明**：本轮未跑真模型质量门、未跑全量矩阵真跑；24 红均为 FAKE_LLM 测试层红，与判据①（矩阵满格 0 missing）、判据②（真模型质量门全绿）无直接关系。quality.verdict 记 `not-applicable`（拆单治理），不得被解读为质量绿。

## 命令 / sha / 时间 / 错误类（policy §4 四要素）

- 基线 sha：`cbbe3831c2bf0643662c6a7e8869260517254544`（origin/main，已从 172d68f ff 同步）；拆单取证基线 `172d68f`。
- 时间：2026-11-22 早班（GMT+8）。
- 复跑命令（取证）：
  - 3 红抽样：`OMNI_TEST_FAKE_LLM=1 .venv_win/Scripts/python.exe -m pytest tests/test_mcp_matrix_verifier.py tests/error_scenarios/test_exit_code_matrix.py tests/test_ol_graceful_degradation.py -q --tb=line` ⇒ 3 failed / 34 passed（见 `spotcheck-3reds.txt`）。
  - C09 隔离：` .venv_win/Scripts/python.exe -m pytest tests/contract/test_cli_help.py::test_ol_help_contract -q --tb=short` ⇒ 1 failed（`└/╰` box-drawing 字形差）。
  - C10 隔离：` .venv_win/Scripts/python.exe -m pytest tests/test_check_module_entry.py -q --tb=short` ⇒ 1 failed（`assert 0 == 1`，架构师复跑，读数内联在 decomposition.md §1.1）。
- 失败格错误类：全部 `deterministic`（测试层/平台债/conftest 隔离/断言口径），transient ×0、quality ×0。

## 证据文件

| 文件 | 内容 | sha256 |
|---|---|---|
| `decomposition.md` | 架构师十簇定稿：疑点 A/B/C/D 裁定 + 十簇规格表 + 执行契约 + owner 拍板项 | `ddd76977cd8bbbb029d9f27289266ce1d5c661680ca17c275a079e6f1754411d` |
| `spotcheck-3reds.txt` | 3 红抽样复现原始读数 | `b943eae43d658b66c65dba777ff7177262eb7a93bd81ee4e40855d2a9aa155f5` |
| `created-issues.txt` | 9 子单创建 URL 映射 | `e213eb0e92907e5569d20e8b6f2de21cb6c675d6bb96b678adca1137034ac09e` |

## 落库子单（红数守恒 7+6+3+2+1+1+2+1+1 = 24）

#401(C1-2,7) · #402(C3,6) · #403(C4,3) · #404(C5,2) · #405(C6,1) · #406(C7,1) · #407(C8,2) · #408(C9,1) · #409(C10,1)

## 已知诚实缺口（不得当成已达标）

- 判据①：本轮未做矩阵真跑（`nightly_gap.py` 去 `--skip-run` 的全量 402 格）；仓库 `goal ACHIEVED` 是 `--skip-run` 读缓存 + fake echo 覆盖 + 104 skip，严口径下不算。待后续缺口推进。
- 判据②：真模型质量门证据仍是 11-20 历史，非本轮真跑。
- 判据③自检脚本 `99-Tools/check_evidence_committed.py` 在本 checkout 不存在（README/协议指向的 workspace 根真身缺失）；本轮以 manifest + 入库证据文件 + git commit 作为证据载体，等待该脚本补齐后复跑自检。
