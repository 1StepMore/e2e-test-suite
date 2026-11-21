# issue #349 · 24 红 9 簇分解复核与裁定（架构师 高见远 / software-architect）

> 复核基线：本地 main `172d68f`（= owner 给定 HEAD）；远程 `origin/main` 已到 `cbbe3831`（PR #347 merge，2026-11-22 02:41Z，比本地新 4 个 commit，本地未 fetch）。
> Windows 原生 EVA-01，`.venv_win/Scripts/python.exe`，FAKE_LLM=1（ validator / CLI 场景单测不需要真模型）。
> 复核方式：拉 #349 / #398 / #342 全文 + 源码 read + 针对性 pytest 复跑（命令与读数见下）。**未写代码、未改任何仓库跟踪文件、未开 issue**；本机 `git status --short` 全程仅 `?? .mimosa/`（既有未跟踪目录）。
> 口径：只变严不变松；不过度归一换绿；证据优先于转述。

---

## 1. 复核结论

### 1.1 红数守恒算式（疑点 C）

owner 的 9 簇建议红数相加：

```
5 + 2 + 6 + 3 + 2 + 1 + 1 + 2 + 1 = 23   ← 少 1
```

逐簇核对：`5(YAML) + 2(run_meta) + 6(mcp_smoke) + 3(/tmp) + 2(bash) + 1(信号) + 1(env) + 2(断言) + 1(cli_help) = 23`。

**漏掉的 1 红 = `tests/test_check_module_entry.py::test_fails_on_mismatched_editable_pth`**——它出现在 #349「11-21 晚班 24 红逐文件分布」表（24 = 7+6+2+2+7×1 里那个单红文件），但**没有出现在** `--tb=short` 归因表的 11 行里，也没有被 9 簇建议的任何一簇收编。这是一个「账单记了、拆单漏了」的静默缺口，按红线不得丢弃。

本机复跑实证（Windows 原生）：

```
$ .venv_win\Scripts\python.exe -m pytest tests/test_check_module_entry.py -q --tb=short
...F..                                                              [100%]
FAILED tests\test_check_module_entry.py::test_fails_on_mismatched_editable_pth
E  AssertionError: an editable .pth pointing elsewhere must fail
E  assert 0 == 1
1 failed, 5 passed in 7.97s
```

根因（源码级：`tests/test_check_module_entry.py::_write_pth` L39-43 + `scripts/check_module_entry.py::_iter_pths` L101-123）：夹具把 `.pth` 写到 POSIX 布局 `.venv/lib/python3.13/site-packages`，而 Windows 侧 `_iter_pths()` 只扫 `.venv/Lib/site-packages`（大小写 + 布局差异）⇒ 夹具造的 `.pth` 在 Windows 根本**不被发现** ⇒ 检查器看不到「指向别处」的条目 ⇒ rc=0。与 #332/#345「平台感知 venv 路径」同族，但落点在**夹具侧**（与第 8 簇 matrix_verifier 的平台偏见断言同族但其文件独立）。最小复现脚本已跑：`_iter_pths()` 在 Windows 对 POSIX 布局夹具返回 `[]`，`main()` 返回 0。

**裁定：9 簇不足以覆盖 24 红。必须补第 10 簇**（建议号 C10），独立单文件、可并行、P0。补齐后：

```
5 + 2 + 6 + 3 + 2 + 1 + 1 + 2 + 1 + 1(新增 C10) = 24   ✅ 守恒
```

owner 的 `--tb=short` 归因表自身也少列了这一行（该表 11 行合计 = 23，却在开头声称 24 failed）——这是同一处遗漏在两个文档位置的表现，非 24 之数本身有误（全量 pytest 汇总行确为 24 failed）。

### 1.2 疑点 A 裁定（cli_help ×1 → #342？）

**owner 的第 9 簇建议（归并进 #342）不成立，裁定为「独立新单」。** 证据链：

1. `gh issue view 342`：**state = CLOSED**；`gh pr view 347`：**MERGED @ 2026-11-22T02:41Z**，`closingIssuesReferences` 含 #342，head commit `cbbe3831`。#342 已由 #360（归一化）+ #347（金样采纳 CI `<bool>` 渲染）闭合，**关闭时间晚于 #349 的 11-21 取证**。一个已 CLOSED 的 issue 不能承接新红——归并会使该红失去责任载体。
2. 本机实测（本地 HEAD `172d68f`，含 #360 归一化、不含 #347 金样刷新）：
   ```
   $ .venv_win\Scripts\python.exe -m pytest tests/contract/test_cli_help.py::test_ol_help_contract -q --tb=short
   FAILED ... - Failed: OL CLI --help output changed ...
   1 failed in 6.24s
   ```
   （纠正 owner 表中「单跑该测试被 deselect，需全量上下文」——本机单跑即复现，collect-only 也正常收 1 条。）
3. 用测试自带 `_normalize()` 对比 `ol_help.txt` vs 本机 11-21 落盘的 `ol_help.actual.txt`（归一化后 42 vs 43 行）：
   - 差异**不是** `<bool>` 注解（那是 #342/#347 的内容，已随 #347 金样刷新解决）；
   - 实际差异是 **rich 表格边框字符 `╭╮╰╯` ↔ `┌┐└┘`**（Windows 控制台/字体导致的 Unicode box-drawing 变体）+ **`search-tm` 描述行折行**（42→43 行）。
4. #342 评论明确：「`\r\n→\n` 与行尾 padding 本就被归一掉，行尾不可能是差异源」「真实根因是 typer 渲染 `<bool>`」——即 #342 的归一化**不处理** box-drawing 字形与折行。因此这 1 红是 #342 修复集合**未覆盖的新漂移**：Windows 控制台把 rich 圆角框渲染成直角框 + 列宽变化导致描述折行。

**可证伪判据**（三选一，跑一次即可定性）：
- (a) 若把本机 `ol_help.actual.txt` 与金样归一后仍见 `╭/┌` 字形差与行数 42≠43 ⇒ **新回归/新漂移，独立新单**（当前证据已满足此条 ⇒ 本裁定成立）。
- (b) 若切到远程 `cbbe3831`（含 #347 金样刷新）后 `--help` 输出与金样在归一后逐字相等 ⇒ 该红随 #347 一起被解决，则标为「取证过期」不拆单、仅在 #349 账本回填复验读数（当前无证据支持）。
- (c) 若差异仅为 `<bool>` 两行 ⇒ 才是 #342 遗留，但 #342 已 CLOSED，仍须**新开单并引用 #342** 而非并入。

归属：**独立新单**（建议 C09），修法方向 = 扩展 `test_cli_help.py::_normalize()`，把 rich box-drawing 全套字形（`╭╮╰╯┌┐└┘─│` 角/线）映射为统一 ASCII/统一字形，**并按语义合并折行**（不能简单 `rstrip`，折行改变行数，需把连续描述行拼回 token 流再比；参照既有 `return "\n".join(" ".join(line.split()) ...)` 的 token 化思路升级）。**禁止重新生成金样**以对齐全 Windows 字面（#342 已否定该路径，会漂成平台专属金样）；DoD 需 POSIX/CI 双平台仍绿 + 反向实证（退回归一化 ⇒ Windows 1 红复现）。

> 需 owner 拍板项见 §5：#342 遗留设计张力「金样权威宇宙 = uv.lock 还是 CI 浮动 pip」尚未决断（#342 评论「决断请求 #1」，默认行为 B）。C09 只做测试侧字形/折行归一，不改 CI 配置、不碰金样，与决断「A 方案」无冲突；但若 owner 想借 C09 顺带根治，需先答 §5-Q1。

### 1.3 疑点 B 裁定（exit_code_matrix ×1：机器隔离缺口 vs 产品 fail-closed 失效）

**裁定：测试/机器 env 隔离缺口，归属 suite 仓测试层（不是产品 fail-closed 失效，不转派 OL 仓）。** 证据链（4 次针对性复跑）：

1. 测试全貌：`tests/error_scenarios/test_exit_code_matrix.py::TestOLAPIKeyMissing::test_ol_without_api_key_exits_nonzero`（L382-404）。它 `env.pop("OMNI_TEST_FAKE_LLM")` 故意走真 LLM 路径，期望「无 key ⇒ 非零退出 + 凭据字样」。`_BASE_ENV`（L62-78）只 strip 了 `AMD_API_KEY`/`ZHIPU_API_KEY`，**未 strip `SPARK_API_KEY`**；本机实测 `SPARK_API_KEY = SET`，其余 provider key 全 unset。
2. 现象复跑：本机跑该测试 → CLI 真发请求到讯飞 xf-yun 端点、被 429/401 打回但**进程退 0**，断言 `returncode != 0` 失败，`1 failed in 54.03s`。
3. 反事实 1：`env -u SPARK_API_KEY` 再跑 → **仍 1 failed**（仍真发请求、退 0）。说明泄漏面不止 shell env：本机 gitignored 的 `Omni_Localizer/config/local.yaml`（4 角色 3 provider 全填字面 key，L24-122）经 `ol_config/resolver.py` 的 4 级优先（level 2 local.yaml > default.yaml）在**子进程 cwd = suite 根**时并不命中（suite 根无 `config/local.yaml`），但 CLI 的 `ol.exe` 由 `.venv_win/Scripts` 启动、cwd 继承 pytest 的 suite 根——解析到 default.yaml（ZHIPU）；ZHIPU 被 strip 后 litellm/router 仍从**进程环境残留 + pool seam** 取到可用凭据。无论具体端口，结论一致：**测试没有把「无凭据」这个前提真正建立起来**。
4. 反事实 2（决定性）：构造全 sanitized env（strip 所有 `*_API_KEY` + `OMNI_TEST_FAKE_LLM` + `OL_CONFIG_PATH`）+ 显式 key-less config（把 default.yaml 全部 `api_key` 置空），再跑同一 CLI ⇒
   ```
   RC = 1
   ERROR: 1 of 1 unit(s) were returned untranslated after retries - failing (fail-closed) and removing the partial output.
   ```
   产品**正确 fail-closed**。

**可证伪判据（已满足=测试侧问题）**：只要「彻底清凭据」时产品返回非零且带 fail-closed 字样（步骤 4 已实证）⇒ 产品契约完好 ⇒ 该红 100% 是测试没隔离干净本机凭据，修法在**测试侧**：为该测试显式构造 hermetic env（去掉 `OMNI_TEST_FAKE_LLM` 的同时，strip 全部 `*_API_KEY`、`OL_CONFIG_PATH`，并显式注入一份 key-less config 或断言 CLI 落在无凭据解析路径），不得靠「本机恰好没设 key」成立。反向：若 sanitized env 下产品仍返回 0 ⇒ 才是产品 fail-closed 失效，转派 OL 仓。**当前证据指向前者，归属测试层 C07。**

> 该结论与 owner 定性方向一致（机器隔离缺口），但把范围从「仅 SPARK_API_KEY」修正为「全部 provider key + config 解析路径」，因为仅 unset SPARK 不足以复现绿——修法按更严口径写。

### 1.4 疑点 D 裁定（并行性与依赖顺序）

- **可并行的簇**（互不碰同一文件）：C01/C02 同文件但不同函数块（`_cli_steps` 与 `collect_run_meta`），建议**合并为 1 个 PR 串行内做**或分 2 单但同分支顺序提交（文件冲突风险低但同文件易撞 diff）；C03（test_mcp_smoke.py）、C04（r01 + tier_dispatch，2 文件）、C05（pre_commit_python_noargs.py）、C06（graceful_degradation.py）、C07（exit_code_matrix.py）、C08（determinism + matrix_verifier，2 文件）、C09（cli_help.py + fixtures）、C10（check_module_entry.py + scripts/check_module_entry.py）**文件集两两不交**，可全部并行。
- **依赖顺序**：全 9→10 簇之间**无硬依赖**（都是测试/platform-fix，互不产出对方输入）。唯一软顺序约束：
  1. C09 依赖远程 `cbbe3831` 的金样状态判定（先 fetch 再决定是「归一字形/折行」还是「取证过期」）；不 fetch 就动手会基于过期金样改错。⇒ **C09 排在每个执行者 fetch 之后**。
  2. C01/C02 因同文件，若拆两单则后者 rebase 前者；建议合并为一单避免。
- **建议执行顺序**：`fetch → C10（最小、证 24 守恒，立即可绿）→ C03（最大面 6 红）→ C01/C02（合并）→ C04 → C08 → C05 → C06 → C07 → C09（金样判定最后，需新金样/归一方案拍板）`。每簇做完即按 `make doctor → make test-quick（或对应文件全绿）→ 全量复跑记红数递减 → 证据入库` 收口，再取下一条。

### 1.5 总账（三判据口径）

- 拆单前：24 红（deterministic ×24 / transient ×0 / quality ×0）。
- 拆单后覆盖：10 簇 = 24 红，零遗漏。
- 判据①（矩阵满格 0 missing）与判据②（真模型质量门）**不受本轮影响**（本轮全是 deterministic 测试层红，FAKE_LLM 场景，无 LLM 抖动格）；判据③（证据入库）由 team-lead 在每簇复验后落 scratch + LOOP-LOG。

---

## 2. 九簇 → 十簇任务规格表

> 标题类型前缀统一规则：`fix(tests):` / `fix(test):` —— 与头提交 conventional commit 类型一致（仓库现行：#345 `fix(tests):`、#360 `fix(test):`、#347 `fix(tests):`）。建议全部用 `fix(tests):` 保持与 #345/#347 同族；#342 的 `fix(test):` 是单数历史写法，不强制。
> 「依赖簇」列：无 = 可独立开工；所列 = 软顺序。

| 簇号 | 建议 issue 标题（含 type 前缀） | 涉及文件 | 红数 | error shape | 根因定性 | 修法方向 | DoD 验收命令 + 期望读数 | 依赖簇 | 可并行 |
|---|---|---|---:|---|---|---|---|---|---|
| C01 | `fix(tests): escape Windows paths in validation scenario fixtures (suite#349 cluster 1)` | `tests/validation/test_engine.py` | 5 | `yaml.scanner.ScannerError: expected escape sequence of 8 hex numbers, but found 's'`（`\s`） | 夹具侧：Windows 反斜杠路径写进双引号 YAML 标量 | 夹具写 YAML 时对路径 `as_posix()` 或整段用单引号/YAML 字面块、或 `yaml.safe_dump`；不动被测引擎 | `.venv_win\Scripts\python.exe -m pytest tests/validation/test_engine.py -q --tb=short` ⇒ 期望 **76 passed**（当前 71 passed / 5 failed） | 无（与 C02 同文件，建议合并单或同分支顺序） | 是（文件集与它簇不交） |
| C02 | `fix(tests): scope validation-runs collection to per-test temp dir (suite#349 cluster 2)` | `tests/validation/test_engine.py` | 2 | `assert ['opp','ol','orf'] == ['opp']`（`test_collect_run_meta_has_suite_keys_and_repo_entries` / `test_run_scenarios_run_meta_auto_collected_component_dir`） | 隔离缺口：run_meta 收集器把共享 `validation-runs/` 里其它 repo 的 run 收进来 | 收集器按显式 `--dir`/`runs_dir` 过滤；测试各自用 `tmp_path / validation-runs`，不读共享目录 | 同 C01 命令 ⇒ 76 passed（与 C01 合并后一次到位；分单时复跑本簇 2 条断言绿） | C01（同文件，软顺序） | 条件（同文件） |
| C03 | `fix(tests): allow Windows pytest temp in OPP MCP smoke allowed-dirs (suite#349 cluster 3)` | `tests/test_mcp_smoke.py` | 6 | `OPP_PATH_DENIED`：tmp 在 `...\AppData\Local\Temp\pytest-of-...` 不在白名单 | MCP sandbox 白名单缺 Windows temp | 仿 OL conftest `MCP_ALLOWED_DIRECTORIES` 修法：把 `tempfile.gettempdir()` / pytest `tmp_path_factory` 根并入 `allowed_directories` 与 `OPP_MCP_ALLOWED_DIRS`，保持「拒绝白名单外路径」断言不放松 | `.venv_win\Scripts\python.exe -m pytest tests/test_mcp_smoke.py -q --tb=short` ⇒ **45 passed**（当前 39 passed / 6 failed） | 无 | 是 |
| C04 | `fix(tests): replace POSIX /tmp assumptions in resume and tier-dispatch tests (suite#349 cluster 4)` | `tests/test_pipeline_resume_r01.py`, `tests/test_round7_tier_dispatch.py` | 3 (2+1) | `FileNotFoundError: '\tmp\omni-suite-pipeline\r01-unit-*\manifest.json'`；argv `\tmp\fake.docx` ≠ `/tmp/fake.docx` | Windows 路径假设 / POSIX 路径断言 | 用 `tempfile.gettempdir()` 或 `tmp_path` 替换硬编码 `/tmp`；断言用 `Path(...).as_posix()` 或 `os.path.normcase`，不能写死 `/tmp/` | `.venv_win\Scripts\python.exe -m pytest tests/test_pipeline_resume_r01.py tests/test_round7_tier_dispatch.py -q --tb=short` ⇒ **14 passed**（当前 11 passed / 3 failed） | 无 | 是 |
| C05 | `fix(tests): POSIX-quote script path passed to bash in pre-commit noargs test (suite#349 cluster 5)` | `tests/scripts/test_pre_commit_python_noargs.py` | 2 | rc=127 `bash: D:贯维Omni_Suitescriptspre_commit_python.sh: No such file or directory` / timeout | Windows 反斜杠路径进 bash 被当转义吃掉 | `cmd = ["bash", "-c", f"bash {SCRIPT.as_posix()} {stdin_spec}"]` 或 shlex.quote；保持 `eof ⇒ exit 2` / `live stdin 不阻塞` 断言不变 | `.venv_win\Scripts\python.exe -m pytest tests/scripts/test_pre_commit_python_noargs.py -q --tb=short` ⇒ **2 passed**（当前 0 passed / 2 failed） | 无 | 是 |
| C06 | `fix(tests): branch SIGINT exit-code assertion on os.name (suite#349 cluster 6)` | `tests/test_ol_graceful_degradation.py` | 1 | `ValueError: Unsupported signal: 2` | Windows 信号语义：`signal.SIGINT` 数值 / `send_signal` 行为与 POSIX 不同 | 按 `os.name` 分支：POSIX 保留进程级 SIGINT→exit 3；Windows 用 `CTRL_C_EVENT` 或降级为跳过并 `pytest.skip(reason)`（带原因、计入 gap 不消失，依 policy §3）；不得把退出码期望改成 0 | `.venv_win\Scripts\python.exe -m pytest tests/test_ol_graceful_degradation.py -q --tb=short` ⇒ 期望 **2 passed（若给出 Windows 等价机制）或 1 passed + 1 skipped(reason)（若 Windows 无等价信号）**；当前 1 passed / 1 failed | 无 | 是 |
| C07 | `fix(tests): hermetic no-credential env for OL API-key-missing exit test (suite#349 cluster 7)` | `tests/error_scenarios/test_exit_code_matrix.py` | 1 | 期望缺 key 非零，实得 rc=0（真请求被 429/401 打回但进程退 0） | 测试 env 隔离缺口（非产品 fail-closed 失效，见 §1.3 实证）：strip 表漏 `SPARK_API_KEY`，且未封住 local.yaml/配置解析路径 | 该测试用 monkeypatch/env 构造 hermetic：去掉 FAKE_LLM 同时 strip **全部** `*_API_KEY` + `OL_CONFIG_PATH`，显式 key-less config；断言非零 + 凭据/fail-closed 字样；**不改产品 CLI** | `.venv_win\Scripts\python.exe -m pytest tests/error_scenarios/test_exit_code_matrix.py -q --tb=short` ⇒ 期望 **17 passed**（当前 16 passed / 1 failed） | 无 | 是 |
| C08 | `fix(tests): platform-aware venv and manifest exemption assertions (suite#349 cluster 8)` | `tests/test_e2e_determinism.py`, `tests/test_mcp_matrix_verifier.py` | 2 | ① manifest `resources.storage_dir` 绝对路径漂移不在 `_VOLATILE_MANIFEST_KEYS`；② `assert '.venv_ol' in '...\.venv_win\Lib\site-packages'` | 断言口径：豁免表缺字段 + 平台偏见断言（#394 同族残留） | ① 把 `resources.storage_dir`（或其中绝对路径部分）纳入 provenance 豁免，归一为相对路径再比；② 按 `os.name` 期望 `.venv_win`/`.venv_ol`，或断言「解释器路径存在且含 `site-packages`」不写死名字 | `.venv_win\Scripts\python.exe -m pytest tests/test_e2e_determinism.py tests/test_mcp_matrix_verifier.py -q --tb=short` ⇒ **25 passed**（当前 23 passed / 2 failed） | 无 | 是 |
| C09 | `fix(tests): normalize rich box-drawing and wrapped lines in OL help contract (suite#349 cluster 9, supersedes #342 pointer)` | `tests/contract/test_cli_help.py`, `tests/contract/fixtures/ol_help.txt`（只读/不重生，除非 §5-Q1 拍 A 方案） | 1 | 归一后 42 vs 43 行；`╭╮╰╯` ↔ `┌┐└┘`；`search-tm` 描述折行 | 新漂移（非 `<bool>`、非 CRLF）：Windows 控制台 rich 字形变体 + 列宽折行 | 升级 `_normalize()`：box-drawing 字形统一映射 + 描述行 token 化合并折行；**禁止**按 Windows 字面重生金样；POSIX/CI 双平台仍绿 + 反向实证 | `.venv_win\Scripts\python.exe -m pytest tests/contract/test_cli_help.py -q --tb=short` ⇒ **6 passed**（当前 5 passed / 1 failed）；另附 POSIX/CI 同文件绿 + 反向实证日志；**前置**：先 fetch 到 `cbbe3831` 复验是否仍红（判据 a/b） | fetch 到 `cbbe3831`（前置，非簇依赖） | 是（fetch 后） |
| C10 **(新增，勿遗漏)** | `fix(tests): make editable .pth fixture discoverable on Windows venv layout (suite#349 cluster 10)` | `tests/test_check_module_entry.py`, （可选）`scripts/check_module_entry.py` | 1 | `assert 0 == 1`（`test_fails_on_mismatched_editable_pth`）：Windows 下 gate 没发现夹具造的 `.pth` | 夹具侧 POSIX 布局假设：夹具写 `.venv/lib/python3.13/site-packages`，Windows `_iter_pths()` 只扫 `.venv/Lib/site-packages` | 夹具按 `os.name` 写对应布局（`nt ⇒ .venv/Lib/site-packages`），或让 `_write_pth` 读取 `_iter_pths` 的平台布局常量；**生产 gate 逻辑不动**（它在 Windows 上的扫描是对的） | `.venv_win\Scripts\python.exe -m pytest tests/test_check_module_entry.py -q --tb=short` ⇒ **6 passed**（当前 5 passed / 1 failed） | 无 | 是 |

合计红数：5+2+6+3+2+1+1+2+1+1 = **24** ✅

---

## 3. 每簇执行契约

**通用（所有簇）**
- 基线 sha：本地取证基线 `172d68f`（owner 给定 HEAD）。**开工第一步先 `git fetch origin`** 并在 #349 评论登记「本地基线 → 远程 HEAD `cbbe3831` 的 4 个 commit 差」（#398 已记录 #347 在途，现已是 merge）。每个子单的 head commit 正文须带 `suite#349 cluster Cn` 与 `Co-Authored-By` 按仓库既有规范。
- 建议分支名：`fix/issue349-c{NN}-{slug}`（如 `fix/issue349-c03-mcp-allowed-dirs`），从最新 `origin/main` 切，单簇单 PR，不跨簇混提。
- 边界（硬）：**不改产品代码**（除 C10 生产 gate 经证据确需时，默认不动）、**不调低/跳过断言换绿**（Windows 无等价信号只能带原因 `pytest.skip` 并计入 gap，不得断言 rc=0）、**不重生 cli_help / schema 金样**（C09 受此约束）、**不碰 `.venv_ol` 硬编码以外平台判定口径**（C08 修断言不修产品）、**不动 #349 的 `owner:human-agent` 标签**（由 owner/team-lead 摘）。
- 卡住怎么办：同一簇连续 **3 次**修复尝试仍红（或需改产品 / 需 owner 拍板项）⇒ 停止，在子单评论记 `blocked` + 已试 3 种修法 + 失败读数 + 末次 `--tb=short` 日志路径，转下一簇；不空转、不越界改产品换绿。
- 收口证据（每簇）：① 本簇文件全绿汇总行；② `OMNI_TEST_FAKE_LLM=1 .venv_win\Scripts\python.exe -m pytest tests/ -m "not nightly" -q` 全量汇总行（记红数从 24 递减到 24−已修）；③ 命令 + sha + 时间 + 失败格错误类（policy §4 四要素）；④ scratch `shift-20261122-morning/` 落 log + LOOP-LOG 条目。

**逐簇特化**
- C01/C02：合并为一单时 head commit `fix(tests): scope validation fixtures and run_meta collection (suite#349 cluster 1-2)`；DoD 用同一 76 passed 读数，不要分别提两个 PR 造成同文件冲突。
- C03：白名单只允许新增 Windows temp 根，不得把整个 `C:\` 或仓库外目录放行（MCP sandbox 安全语义不得放宽）。
- C06：Windows 若无 CTRL_C 等价机制，`pytest.skip` 必须带 reason 且该格在账单里显示，不算绿（policy §3）。
- C07：修完必须附 §1.3 步骤 4 的「sanitized env ⇒ rc=1 fail-closed」反向实证，证明产品未被动过。
- C09：开工前 fetch + 判据 a/b/c 复验留证；若判据 b（随 #347 已绿）⇒ 不提 C09 单，转 #349 回填「取证过期」读数。
- C10：最小改动优先（只改夹具），若必须动 `scripts/check_module_entry.py` 需在单内说明为何 Windows 扫描逻辑也要改，否则 team-lead 驳回。

---

## 4. 给 team-lead 的开单建议

1. **开 10 个子单**（C01/C02 建议合并为 1 单 ⇒ 实开 9 单），全部以 `fix(tests):` 起标题，挂 `suite#349 cluster Cn` 正文引用，指向本 decomposition 作规格来源。
2. **不再把 cli_help 归并进 #342**（#342 已 CLOSED）；C09 独立开单，正文引用 #342 + #347 + 本裁定 §1.2 证据（归一后 42≠43 行、box-drawing 字形差）。
3. **标签策略**：
   - 子单一律 `agent-ready, bug`，**不加 `owner:human-agent`**（#349 的 owner 标签是总账「本机 WSL 不能判定 Windows 原生」的历史定性；拆单后每簇有明确 Windows 复跑 DoD，按 `docs/dev/harness-run-facts.md`「派活按能力匹配」，`agent-ready` 即可认领）。可按执行机加 `needs:` 行（能力项 = `Windows 原生 .venv_win`），符合状态机硬规矩②。
   - #349 总账**保留** `bug, owner:human-agent` 作父账，等 10 簇全绿后由 owner 决定是否摘标签关闭；子单用 sub-issues 关联（若 GitHub 支持）或正文 `#349 cluster Cn` 交叉引用。
   - #398 handoff 中「#349 派单」前置条件「owner 已摘标签」需 owner 确认：摘标签 = 交棒给 code 侧；**摘的是 #349 父账标签，不影响子单 `agent-ready`**。若 owner 暂不摘 #349，子单仍可开（子单自身 agent-ready），只是父账不关闭。
4. **顺序建议**：先开 C10（证明 24 守恒、立即可绿）+ C03（6 红大头），同批把 C01/C02/C04/C05/C06/C07/C08 全开并行；C09 等 fetch + 判据复验后再开（或直接在 C09 单内第一步做判据复验）。
5. **不留孤儿红**：开单后核对子单红数之和 = 24，任何一红无单 ⇒ 回到本表 §1.1 算式重算。

---

## 5. 需 owner 拍板的事项（仅列影响目标判定/不可逆者）

- **Q1（C09 方案岔路，不阻塞开单，但影响 C09 修法）**：#342 遗留的「金样权威宇宙」决断请求（#342 评论「决断请求 #1」）仍未决：A = contract-tests.yml 改用 uv.lock 钉住 typer（改 CI 配置，Owner 级别）；B = 维持浮动 pip + 测试侧归一宽容（默认行为）。**本裁定默认 B**：C09 只做测试侧 box-drawing/折行归一，不碰 CI、不重生金样，最可逆。若 owner 要改 A，须先拍板，C09 改为「归一 + CI 钉版本」联合单，且与 #342 的决断一起结掉。不拍板 ⇒ 按 B 执行并登记。

- **Q2（#349 父账标签交棒，影响谁认领）**：#349 现挂 `owner:human-agent`（owner 在 #349 首评写明「本机 WSL 不能判定 Windows 原生」）。开子单派活前，owner 是否摘该标签？本裁定建议：**摘**，并把「可做判定」下放到子单的 Windows DoD；子单自身 `agent-ready` 可认领，与父账标签解耦。若 owner 坚持保留，则仅本机（有 `.venv_win` 的 EVA-01）可做，需登记能力归属。

> 其余按最严口径自决并已登记：疑点 A 独立新单、疑点 B 测试侧隔离、疑点 C 补第 10 簇、疑点 D 并行顺序、金样不重生、skip 带原因计 gap、失败 3 次记 blocked。

---

### 复核证据索引（本机 scratch，非入库）
- 本文件：`99-Tools/validation-scratch/omni-suite/shift-20261122-morning/issue349-decomposition.md`
- 复跑读数均在本文件 §1 内联记录（命令 + 汇总行 + 关键 error shape），未另存大 log；需要原始输出可按各命令重跑。
- 参考事实源：`gh issue view 349/398/342 --comments`、`gh pr view 347/345`、`docs/dev/matrix-verdict-policy.md`、`docs/dev/harness-run-facts.md`、相关源码行号见 §1/§2 表。
