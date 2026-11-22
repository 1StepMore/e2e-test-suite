# 证据：e2e#349 九簇收口（2026-11-22）

- 类别：**治理/链路证据（非真模型质量）** → `confidence=mock`。
- 结论范围：**仅**「#349 的 24 个平台债测试红已清零」。**不**代表 Windows 全量 pytest 全绿，**更不**代表 owner 三判据达成。
- quality.verdict：`not-applicable`（这是红账单收口，不是质量门通过判定）。

## 结果

| 项 | 数 | 说明 |
|---|--:|---|
| 原账单红 | 24 | 11-21 全量 `--tb=short` 取证 |
| 转绿 | **23** | C1-2(7) C3(6) C4(3) C5(2) C7(1) C8(2) C9(1) C10(1) |
| 转 skip（gap，不算绿） | **1** | C6：Windows 无 POSIX SIGINT 语义；POSIX CI 覆盖真实契约 |
| 本单剩余红 | **0** | — |

- 子单：#401–#409 全部 CLOSED；PR：#412–#420 全部 squash merged。
- **真绿率 23/24 = 95.8%**；skip 1 格不计入覆盖。

## 命令 / sha / 时间 / 错误类（policy §4 四要素）

- 验收基线：`origin/main = 414b146820ee59e9deba34a64b4f1d25ff8828be`（本地 checkout 因 git-over-HTTPS 阻断仍停在 cbbe383；13 个改动文件经 GitHub API 逐 blob 同步到 main 状态，blob SHA 已核对一致）。
- 时间：2026-11-22 晚班（GMT+8）。
- **13 个受影响文件全跑**：
  `OMNI_TEST_FAKE_LLM=1 .venv_win/Scripts/python.exe -m pytest <13 files> -q --tb=short`
  ⇒ **191 passed, 1 skipped, 1 xfailed, 0 failed**（2:43）。
- **全量参考（含已知污染）**：
  `OMNI_TEST_FAKE_LLM=1 .venv_win/Scripts/python.exe -m pytest tests/ -m "not nightly" -q --tb=no --basetemp=<fresh>`
  ⇒ **31 failed / 4149 passed / 189 skipped / 25 deselected / 13 xfailed / 5 xpassed**（28:56）。
  - 31 个**均不在** #349 的 24 红清单内；抽样 4 文件（覆盖 17 红）单独跑全绿（test_mcp_smoke 45P / test_coverage_audit 27P / test_e2e_pipeline_full 19P / test_e2e_concurrency 4P），且文件 blob 与 main 逐字节一致 ⇒ **测试间污染**，另立 **#421** 独立记账。
- 失败错误类（#349 范围内）：全部 `deterministic`，transient ×0、quality ×0。

## 逐簇质量拦截（记录，证明不是无脑放行）

1. **C7 断言放宽被驳回**：工程师初版在 stderr 断言新增 `fail-closed`/`provider` 两个接受词；对照实验（移除后仍 1 passed）证明多余 ⇒ 删除，口径只许变严。
2. **C9 过度归一被证伪**：自建对照——篡改金样内容 token `translate-md`→`translate-xmd`，升级后的 `_normalize()` **仍让测试红** ⇒ 未吃掉真实差异；金样 sha256 保持 `9d9721cf6686da7279ad81ead3699b6d1fe707500145f4e60be14e6447e99ea1`（未重生）。
3. **C5 裸 bash 必要性实证**：`subprocess.run(['bash',...])` 在原生 Windows 被 System32 的 WSL 桩拦截（沙箱 `PROGRAM BLOCKED: wsl.exe` + GBK 乱码），证明 `shutil.which` 绝对路径修法必要。

## 诚实缺口（不得当成已达标）

- **#421**：全量 31 个顺序依赖假红仍在，Windows 全量 pytest 未达 0 failed。
- **C6**：Windows 该格覆盖 0（skip）。
- **owner 三判据**：判据① 矩阵 402 格真跑、判据② 真模型质量门本轮真跑、判据③ 证据自检脚本（`check_evidence_committed.py` 在本 checkout 缺失）—— 本轮均未做。
