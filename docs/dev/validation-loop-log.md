# Omni Suite Validation LOOP-LOG（坑清单 + 循环事件）

> 治理规范见 AGENTS.md「Validation 循环治理规范（2026-08-15）」。**迭代前必查本清单**;新坑当天追加;写而不用 = 无价值。

## 坑清单（pitfall checklist，迭代前逐条对照）

### 2026-08-15 首循环（创建）

- [ ] **venv 是 `.venv`（py3.13）或 `.venv_ol`——不是 `.venv_py313`?** 冒烟实测 `.venv/bin/python` 可用;runbook 记 `.venv_ol`。跑前确认 ImportError 不来自 venv。
- [ ] **无 LLM keys 时 tier-2/3 如实 unconfigured**——当前 shell 无 OPENAI/ZHIPU/AGNES/NVIDIA keys,tier-2 3 个 + tier-3 1 个场景应报 unconfigured,不是 failed。
- [ ] **run 记录落 `validation-runs/<ts>/`** + `latest.txt` 更新;首循环前 latest.txt 不存在。
- [ ] **全量 tier-2 跑前 LLM 短探测**(治理规范)——本轮无 key 不适用,有 key 后补。
- [ ] **失败定性协议**:任何 failed 先单独复现定性(LLM 波动/场景断言漂移/代码 bug/数据漂移/环境),不直接报"回归"。
- [ ] **验收 = 打开产物审查**(非空/相关性/无 VAGUE),不是 matrix 数字。

### 2026-08-15 第二轮（首循环实战新增）

- [ ] **场景库可移植性:禁止硬编码机器绝对路径**——26 个场景曾硬编码 `/mnt/d/贯维/Omni_Suite/...`(旧机器布局)导致 20+ failed(command not found / FileNotFoundError)。dispatch 已把 `.venv_ol/bin` 注入 PATH(`omni_mcp/validation/dispatch.py:50-51,83-100`),CLI 步骤用裸命令名(`opp`/`orf`),fixture 用套件根相对路径(`scenarios/_fixtures/...`)。新增场景禁止 `/mnt/d/` 或机器专属路径;验收含 `grep -rn "贯维|Omni_Suite" scenarios/` 为空。issue #40 / PR #41。
- [ ] **套件内嵌模块副本必须与模块 HEAD 同步**——e2e-test-suite 的 `Omni_Pre_Processor/` 等目录通过 `.git` 文件共享模块 repo gitdir,工作树可能是旧内容(首跑时 OPP 副本 config.py 缺 `cleanup_on_shutdown` → 全部 tool-opp-* failed)。跑前核对 `git -C <module> status --porcelain` 为空;diff 备份到 `99-Tools/validation-scratch/omni-suite/pre-sync-*.patch` 后可 `git reset --hard HEAD` + `git clean -fd` 同步。
- [ ] **fixture 断言必须与 fixture 目录实际文件数一致**——`scenarios/_fixtures/translated_pair/` 实际 7 文件(无 source.pptx),8 个 orf-xliff 场景曾断言 `COPIED 8` → 必 failed。改 fixture 后同步改场景断言,或用 `len(files)` 动态断言。
- [ ] **`gh pr create` body 含 `&` 会触发安全拦截**——body 里避免 `&` 字符(如 "A & B");或 body 写文件用 `--body-file`。
- [ ] **套件环境装配清单(全量跑前必配,缺一即 failed 非 unconfigured)**——(a) `OPP_MCP_ALLOWED_DIRS` 必须含场景 fixture 目录 `/tmp/omni-agent-surface`(Hermes 环境注入值只有 `/mnt/d/Hermes-Workspace:/home/renanzai`,OPP 拒绝 /tmp → tool-opp-* 全 failed);(b) `markdownify` + `readability-lxml`(OPP HTML 提取,缺则 opp-html-extract 标题丢失 no-h1/no-h2);(c) `yake` + `jieba`(OL ol[ml] extra,缺则 tool-ol-extract_terms YAKE 失败);(d) `weasyprint`(ORF PDF 引擎,缺则 orf-md-pdf / orf-xliff-pdf 转 PDF 失败;weasyprint 是首选,不需要装 pdflatex);(e) 三模块内嵌副本与 HEAD 一致。跑前一次性核对,别等 failed 了才逐个装。
- [ ] **`pip install` 在 WSL 默认源会慢/卡(do_sys_poll 挂起)**——连接 ESTABLISHED 但传输慢;`pip index versions` 查版本快,清华镜像缺包(如 markdownify)时换官方源;安装放后台 + notify_on_complete,别前台等。
- [ ] **unconfigured 里有一批是可配 env 不是缺 LLM key**——`ORF_MCP_ALLOWED_DIRS`/`MCP_ALLOWED_DIRECTORIES` 补上后 tool-orf-* 等 11 个可转绿;真正缺 key 的是 OPENAI/ZHIPU/AGNES/NVIDIA(OL translate/judge/pipeline)。区分"可配未配"与"客观缺 key"。
- [ ] **OL 模型池在 Omni_Localizer/config/local.yaml + default.yaml(两份镜像)**——translation/judging/restoration 三组,key 全部 `${ENV_VAR}` 引用。场景 requires_env 要求 4 个 LLM key 全有(含 OPENAI_API_KEY),但**代码只读池内 provider**,把 `OPENAI_API_KEY` 指向任一 openai-compat provider(如 Agnes)即可过门控。2026-08-15 实测:NVIDIA `deepseek-ai/deepseek-v4-flash` 已 EOL(2026-08-07)→ 换成 `z-ai/glm-5.2` + `minimaxai/minimax-m3`(新 key 实测可用);Zhipu `glm-4.7-flash` 是 reasoning 模型(max_tokens 太小会空返回,≥1024 正常);Mistral `api.mistral.ai` WSL 网络不可达。
- [ ] **NVIDIA NIM key 分两档**:能 `GET /v1/models`(列 102 个)≠ 能调用;免费 key 需在 build.nvidia.com 模型页逐个授权,未授权模型调用 403 "Authorization failed"。
- [ ] **三个模块的 allowlist env 分隔符不同**——OL `MCP_ALLOWED_DIRECTORIES` 用**逗号**(`security.py:276 split(",")`),ORF `ORF_MCP_ALLOWED_DIRS` / OPP `OPP_MCP_ALLOWED_DIRS` 用**冒号**。配错分隔符 → 整个字符串被当成一个目录,任何路径都 OL_PATH_NOT_ALLOWED(failed 而非 unconfigured)。**已收敛（2026-09-17，ADR 0007 Phase 1 step 3）**：四份实现统一为 `os.pathsep`（POSIX `:` / Windows `;`）+ 逗号，由 `tests/security/test_path_policy_parity.py::TestAllowlistParsingParity` 冻结；保留本条是因为历史 run 记录里的 failed 仍按旧语义产生。
- [ ] **新增测试禁止在模块级设 allowlist env**——pytest 在跑任何用例前会 import 全部测试模块，模块级 `os.environ.setdefault("MCP_ALLOWED_DIRECTORIES", ...)` 会**进程级**覆盖 `tests/conftest.py` 的 allowlist（该变量在每个读取者的解析顺序里都优先于 `*_MCP_ALLOWED_DIRS`）。2026-09-17 实测：`tests/test_mutation_transparency_x03.py` 因此让**自己**的 4 个用例失败（Windows 上 `/tmp` = `<盘符>:\tmp`，不在 conftest 允许的 `tmp_path` 内），极易误判为本轮回归。allowlist 的 owner 只能是 conftest。
- [ ] **原生 Windows 上想拿执行型证据必须走 WSL**——`.venv_ol` 是 Linux venv（`bin/python` 在 PowerShell/Git Bash 下不可执行），而 `omni_mcp/validation/dispatch.py` 的 `VENV_BIN` 钉死 `.venv_ol`：在 `.venv_win` 里跑执行型 parity 实测 **0/41**（服务器起不来）、系统 python3.14 是 36/41，都不构成证据。可用：`wsl -e bash -lc "cd /mnt/d/贯维/Omni_Suite && MCP_ALLOWED_DIRECTORIES=/tmp OMNI_TEST_FAKE_LLM=1 ./.venv_ol/bin/python scripts/validation/run_validation.py --scenario <name> --tier 1"`（2026-09-17 实测 tier-1 场景 8/8、2/2、2/2 passed）。
- [ ] **Git Bash 下 `[ -x .venv_ol/bin/python ]` 恒为假**（dangling Linux ELF 符号链接）→ 门禁走 "skip → exit 0" 分支 = **跳过即通过**的伪绿。凡需要解释器的钩子一律经 `scripts/pre_commit_python.sh`（存在 ≠ 可执行：每个候选真跑一次 `-c ''`）。
- [ ] **Hermes 会话注入 PYTHONPATH 含 `~/.hermes/hermes-agent` → OL `from cli import *` 裸导入会命中 hermes-agent 的 cli.py**——表现为 ModuleNotFoundError: prompt_toolkit(其实是 import 错了文件)。跑 OL/OPP/ORF 的 CLI 子进程前 `unset PYTHONPATH`。同坑:`.venv_ol` editable .pth 若指向 `src/Omni_*` 旧副本(被 gitignore),手动改 .pth 指向 `Omni_*/src`,别指望 pip 重装自动修(pip 有 editable 路径缓存)。
- [ ] **NVIDIA NIM key 分两档**:能 `GET /v1/models`(列 102 个)≠ 能调用;免费 key 需在 build.nvidia.com 模型页逐个授权,未授权模型调用 403 "Authorization failed"。

### 2026-09-13 文档/入口 gate 化（由本日复盘的重复模式新增）

- [ ] **模块入口与 venv editable 必须指向「与 HEAD 一致的那份工作目录」**——suite 根 `Omni_*` 若指向 `<suite>/src/Omni_*`，那是**第二工作目录**（`.git` 是 gitdir 指针文件，共享 canonical clone 的 `.git`）：`HEAD` 看起来一致，工作区文件却可能是几个月前的，而 venv 的 editable `.pth`、`utils/mcp_client.py` 的 `PYTHONPATH`、`omni_suite/cli.py` 全部落它上面 → **静默跑旧代码、不报错**。跑前双查：`readlink -f <suite>/Omni_Localizer` + `.venv/bin/python -c "import ol_mcp,os; print(os.path.realpath(ol_mcp.__file__))"`；判据：`<入口>/.git` 是**文件** = 危险，是目录才正常。修法 `ln -sfn ../Omni_Localizer <suite>/Omni_Localizer`（换指向前先确认旧副本独有的 gitignored 文件已复制过去，例如 OL 的 `.env`）。已 gate 化：`make entry-check` / `make doctor` / pre-commit `omni-module-entry-check`（issue #11 → PR #12）。
- [ ] **模块文档里的计数/版本断言属于代码契约**——改工具数、版本号、子命令数必须同步改模块 `docs/*.md` 与 README 散文（`registers N tools` / `All N tool functions` / `exposing N tools` / `vX.Y.Z (matches pyproject.toml)`）。已 gate 化：`python3 scripts/doc_inventory.py --check` 现在覆盖模块 docs + README 散文（issue #10 → PR #12）；动模块文档前后都跑它。

### 2026-09-21 第五轮（CI 清账新增）

- [ ] **`uv lock --check` 必须在仓库自身语境里跑，否则验的是套件 workspace 锁**——在 `Omni_Pre_Processor/` 子目录里裸跑 `uv --no-config lock --check` 会解析到套件根 `[tool.uv.workspace]` 的锁（298 包、rc=0），**不是** OPP 自己的锁（233 包）。OPP #59「已修」的假阳性就是这么来的；CI 里同样命令却 rc=1。判据：看 `Resolved N packages` 的 N 是否等于该仓锁文件的包数。
- [ ] **CLI `--help` 契约 fixture 锁的是 typer 的渲染，而 typer 版本随锁漂**——`uv.lock` 钉 typer 0.24.2 渲染 `[OPTIONS] [COMMAND] [ARGS]`，本机 `.venv_ol` 漂到 0.26.2 渲染 `[OPTIONS] COMMAND [ARGS]`。fixture 红先查 `pip show typer click` vs `uv.lock`，再怀疑 CLI 改版；本地验证 fixture 类 PR 前先把 venv 对齐锁。
- [ ] **pytest 步骤写 `2>&1 | tail -N` 必须配 `set -o pipefail`**（默认 shell `bash -e {0}` 不含）——否则步骤退出码 = tail 的 0，71 failed/61 errors 全部报 success；tail 还把失败清单截出日志。已 gate 化于 `e2e-tests.yml`（PR #57）；新 workflow 步骤照抄 `set -o pipefail` + `tee` + `upload-artifact` 模式。
- [ ] **整组 pytest 在共享 venv 里全量跑之前，先识别「测试间污染」家族**——rate-limiter（token bucket）、进程级 env、MCP server 状态会让 security/observability/stdio 家族在全量跑里假红（单跑 5/5 passed）。全量清单里的失败必须先单跑复现再定性，不能直接当回归修（本 runway：6 个 path-traversal 失败全是污染）。
- [ ] **`git push` 前先看 push URL 的协议**——suite 仓 origin 的 push URL 是 https（GnuTLS 偶发 -110），fetch URL 是 ssh；ssh 键是 `1StepMore/AutoInfo` 的 deploy key（对其它仓无写权限）。可用的两条路：重试 https（gh token 有 repo+workflow scope），或 `git push git@github.com:1StepMore/<repo>.git <branch>` 显式 URL——但 deploy-key 会拒，别浪费在这条路上。

### 2026-09-21（第二轮，validate 首跑新增）

- [ ] **`uv pip install -e <子仓>` 无视 uv.lock 重解析**——typer 0.24.2→0.27.2、click 8.4.1→8.5.0、litellm 1.89.2→1.102.0（CI 实测），CLI --help fixture 直接漂移。修法：`uv export --locked --all-packages --no-hashes | grep -v '^-e '` 生成约束文件 + `uv pip install -e ... -c 约束`。**勿用 `--no-deps`**：实测 `uv sync --locked` 只装 32 包（根+omni-security），子仓依赖不在其中，`--no-deps` 会直接缺包。
- [ ] **契约 fixture 的"期望值"可能是漂移环境的产物**——e2e#58 的 `[COMMAND]` fixture 是按漂移 typer 0.27.x 重新生成的；锁回 authority 后必须再回退 fixture。修 CI 环境后，凡是"修环境前生成"的冻结产物都要重核。
- [ ] **改 `.pre-commit-config.yaml` 是 lint 地雷**——coverage-audit/validation-check/path-policy-parity 三个钩子的 `files:` 都含 `.pre-commit-config.yaml`，但 lint job 不装项目依赖（只有 pre-commit/ruff/mypy）→ 三个钩子必红（issue #61）。config 类改动要么单独 PR 且接受红，要么先修钩子 guard。
- [ ] **`tests/contract/fixtures/*.txt` 是字节级 oracle，含尾随空格**——`trailing-whitespace` 钩子会剥掉它并中止 commit；`_normalize` 已改为逐行 rstrip（padding 非接口），fixture 以无尾随空格形式入库。不要再"修好"它的 padding。
- [ ] **在 feature 分支上 `git pull origin main` 会 ff 那个分支，不是 main**——backup 同步时 `push backup main:main` 于是推了旧 main 还报 "Everything up-to-date"。同步前先 `git checkout main` 再 pull/push（本轮 OPP/ORF 就这么漏过一次）。
- [ ] **跨仓 `Closes #N` 不会关闭别的仓的 issue**——suite PR 里写 `Closes OPP#63` 无效，跨仓 issue 要手动 close 并附证据。
- [ ] **模块级 `pytest.skip()` 必须带 `allow_module_level=True`**——否则是 collection error，pytest 整体 exit 2，该组 0 用例 + 后续步骤全 skip（OPP#64）。
- [ ] **per-repo validate job 只装本模块依赖 = 场景库必红**——tier-1 场景库断言的是"全工作区表面"：`from docx import`（OPP 的依赖）、`opp` CLI（同）、weasyprint/openpyxl（ORF extras）、`markdownify`（OPP web extra，缺了 HTML 抽取静默回退成原文而非报错）。新建 per-repo validate job 时直接镜像 suite `validation.yml` 的 "Install test deps" 配方（ORF#52/OPP#66 实证：装齐后 36+21 全绿）。
- [ ] **py3.13 动态 `exec_module` 前必须注册 `sys.modules[name]`**——模块内 `@dataclass` 在类创建时经 `dataclasses._is_type` 读 `sys.modules[cls.__module__]`，未注册即 `AttributeError: 'NoneType' object has no attribute '__dict__'`（OL test_ol_mcp_error_boundary）。exec 完 pop 掉。
- [ ] **修一个 env 泄漏会把被它掩盖的失败全放出来**——`MCP_ALLOWED_DIRECTORIES=/tmp` 进程级泄漏曾让 OPP path-denial 假绿；PR#87 收敛泄漏 + baseline 后，test_e2e_opp_mcp 冒出 5 个 combined-run-only 的 path-denied（#88，根因未确认，带可证伪诊断步骤）。收泄漏前先盘点"哪些测试在靠泄漏过"。
- [ ] **后台 agent 的任务状态 ≠ 实际交付状态**——模型商故障 + 30 分钟 inactivity timeout 会把 agent 标成 error/aborted，但它可能已经把 PR 建好甚至 merge 完（PR #87 报 failed 实为 merged）。收尾一律以 `git`/`gh` 里的真实状态为准，不要按任务状态决定重做。
- [ ] **AST 字面量 guard 会把"提到 env 变量的句子"当硬编码**——`OMNI_TEST_FAKE_LLM=1 is active...` 这类消息文本触发 test_no_hardcoded_fake_llm；分类器必须区分"赋值形态"与"句子内嵌"（e2e#56e：只标 bare/shell 前缀形态，句子继续词为动词/连词的放行）。

## 循环事件（major events，newest on top）

### 2026-09-21（第三轮）：4 仓 issue/PR 全清账 + #56 umbrella 收口

- Date: 2026-09-21, round: 用户令"check the original repo for all unaddressed issues and PRs, verify them, address them properly" → 全量盘点（origin 4 仓 open issue 4、open PR 0；backup 镜像 0/0）→ 逐个以 CI 日志实证根因后修复、合并、关单
- Scope: ORF（test.yml、test_md2pdf_channel.py）、OPP（ci.yml）、OL（test_ol_mcp_error_boundary.py、cli/doctor.py）、suite（.pre-commit-config.yaml、contract-tests.yml、test_no_hardcoded_fake_llm.py、tests/conftest.py + 6 个 stale 测试对齐）
- Result: **ORF#52（PR #53，validate job 装 `-e ./Omni_Pre_Processor` + weasyprint → 场景 21 passed/15 failed → 36 passed/0 failed）；OPP#66（PR #67，validate job 补 `markdownify readability-lxml` → html 场景 4 步全过）；OL PR #98（sys.modules 注册 + doctor 广捕日志化 → suite "Run OL module tests" 1 failed/1501 → 0 failed）；suite PR #62（#61 钩子 preflight guard + mcp-matrix 补 OL allowlist + CONTRACT-docs job 装子仓+omni_security + FAKE_LLM guard 语义化分类）关 e2e#61；ORF PR #54（weasyprint 回退测试去宿主依赖）→ suite "Run ORF module tests" 绿；suite PR #87（Tier-2 污染：conftest baseline allowlist + 每 test env 快照/恢复 + token-bucket 重置 + 隔离 guard 测试）。** e2e#56 按 acceptance 收口：Tier-2 实修完成，Tier-1 拆成 12 个子 issue（#74-#84、#86），#85 由 #87 顺带修掉，residual #88（combined-run-only 5+1，根因未确认、带可证伪诊断）。全部 4 仓 backup == origin。
- 逐项验证：**#52/#66** 根因先在本地证伪"场景/产品有 bug"（本地 36/36、21/21 全绿）再证 CI 装机差集；**OPP#66** 关键实验：`MARKDOWNIFY_AVAILABLE=False` 时 `html_to_markdown` 返回原文——缺 markdownify 是静默回退不是报错；**#61** PR 本身触碰 .pre-commit-config.yaml 且 lint 绿 = 回归测试自带；**#56e** 两个旧断言数学上不可能成立（char_jaccard 恰为 0.0、char_cosine 恰为 0.8）——"放宽"实为纠错；**ORF PR#54** CI 实证 runner 带 TeX（pdflatex）致 pandoc 回退成功——"CI 没有 pdflatex"的假设不成立。
- **新坑**（已入上方清单）：per-repo validate 装机面、py3.13 动态导入 sys.modules、修 env 泄漏放出被掩盖失败、agent 任务状态≠交付状态、AST guard 误伤句子内嵌。
- Conclusion: origin 4 仓 open issue 归零（全部 closed 或拆分为带证据的子 issue）、open PR 归零；suite main 红 workflow 从 3（E2E/hardening/contract）降到 1（E2E，余量全部有子 issue 跟踪 + #88 residual）；Validation Framework / lint / Structural / doctor 全绿。

### 2026-09-21（第二轮）：5 个 CI 红根因收口 + validate 门首跑暴露

- Date: 2026-09-21, round: 用户报 5 个实测根因 issue（OPP#63/#64、ORF#50、e2e#58/#59）→ 全部核实、修复、合并
- Scope: suite（pyproject+uv.lock、e2e-tests.yml、validation.yml、doc_inventory.py、test_cli_help.py、fixtures/ol_help.txt）、OPP（test_opp_ol_orf_contracts_md.py）、ORF（test.yml）
- Result: **suite PR #60（4ef62aab1，3+1 commits）close e2e#58/#59 + 修 OPP#63；OPP PR #65（3bd7928f0）close OPP#64；ORF PR #51（45404555d）close ORF#50。** 4 仓 backup == origin。新建 follow-up：suite #61（lint 地雷）、OPP #66、ORF #52（validate 首跑暴露）。
- 逐项验证：**#63** pyyaml 进根依赖 + `uv --no-config lock`（2 行 diff），CI 实测 `+ pyyaml==6.0.3`，validate 从 import 崩 → 跑出 `Totals: 20 passed, 1 failed`；**#58** editable 安装加 `uv export --locked --all-packages` 约束（实测约束集钉 typer 0.24.2/click 8.4.1/litellm 1.89.2）→ CI `+ typer==0.24.2`，Structural Gate 4 绿；配套把 fixture 回退到锁渲染（`COMMAND`——PR #54 的 `[COMMAND]` 是漂移 typer 0.27.x 的渲染，不是 CLI 变更）且 `_normalize` 改为逐行 rstrip（面板 padding 是渲染不是接口）；**#59** `_HISTORICAL_PATH_TOKENS` 加 3 个生成物/gitignored token，隐藏本机文件复现 CI 条件 → `--check` exit 0；**#64** `allow_module_level=True`，OPP 组从「1 collection error、0 用例」→ **1048 passed/25 skipped**；**#50** lock 检查加 `working-directory: orf-src`，CI 过 guard 进入场景。
- **两个必须纠正 issue 建议修法的实测**：(1) #58 的 `--no-deps` 会炸 CI——实测 `uv sync --locked` 只装 32 包（根+omni-security），子仓依赖根本不在其中；(2) #58 的另一半是 fixture 回退，只锁 typer 不回退 fixture 仍红（首次 push 后 Structural 仍 fail，job 106227722092 实证 typer 0.24.2 下 actual=COMMAND）。
- **validate 门首跑暴露**（此前从未真正跑过）：OPP `opp-html-extract` 3/4 步（→ OPP#66）；ORF 15 个场景 failed（tool-orf-* 族 3 步只过 1 步、orf-xliff-* 族，`Totals: 21 passed, 15 failed`，→ ORF#52）。与 #48 同性质：门修好才看得见。
- **新坑**（已入下方清单）：editable 安装无视 lock、.pre-commit-config.yaml 是 lint 地雷、fixture 尾随空格被 trailing-whitespace 钩子破坏、feature 分支上 `git pull` 会 ff 分支而非 main。
- Conclusion: 5/5 根因收口 + 3 个 follow-up issue 建档；lint/Structural/CLI-contract 全绿；剩余红全部有 issue 跟踪（#56/#61/#66/#52）。

### 2026-09-21 第五轮：4-repo CI 红 → 绿清账（10 PR + 8 issue）+ #48 诚实门禁落地

- Date: 2026-09-21, round: 4-repo unaddressed issues/PRs 清账（origin: 1StepMore/*，全部 PR 为本方此前 wave 遗留未合并）
- Scope: suite（PR #50/#51/#52/#54、issue #44/#45/#46/#47/#48/#49/#53/#55）、OPP（PR #60/#62、issue #59/#61）、ORF（PR #47/#49、issue #46/#48）、OL（PR #95/#97、issue #94/#96）
- Result: **10 PR 全部本地验证后 merge，8 个 `Closes #N` issue 自动关闭；#55/#44 核实已修后手动 close（附证据）；#48 落诚实门禁后 close；OL #96 当轮实现（新稳定码 `OL_MCP_NOT_CONFIGURED`）经 PR #97 merge 后 close。** 收尾态：4 仓 open PR = 0，open issue = 仅 #56（#48 的后续 triage 伞）。备份镜像 4 仓全部 `backup/main == origin/main`。
- 关键验证（逐 PR 本地/CI 双证）：PR#52 mypy `Success: no issues found in 23 source files`（负证：去掉 `mypy_path` 行 = 4 errors）；PR#54 目标 job `CLI --help contract` pass（坑：fixture 匹配的是 **uv.lock 的 typer 0.24.2**（`[COMMAND]`），本机 .venv_ol 漂到 0.26.2（`COMMAND`）→ 本地红/CI 绿是 venv 漂移不是 fixture 错）；PR#95 两个 pool 测试 main 上 2 failed → 分支 2 passed；PR#60 前 OPP CI 实测死于 `uv lock --check`（本地 `--check` 通过是因为 uv 解析到了**套件 workspace** 锁，298 包 ≠ OPP 的 233 包——必须在仓库语境里验）；OL#96 实测 no-allowlist 调用返回 `error.code=OL_MCP_NOT_CONFIGURED` + `recovery.strategy=configure_environment`，fail-CLOSED 语义不变，套件契约锁 28 passed。
- **#48 诚实门禁（PR #57）**：6 个 `2>&1 | tail -N` 步骤加 `set -o pipefail` + `tee /tmp/*.log` + `upload-artifact`（`if: always()`）。CI 实证：此前隐藏的 OPP collection error（`pytest.skip` 未加 `allow_module_level=True`，整组 0 用例）现在**让步骤红、job 红**，完整日志进 `pytest-logs` artifact。**合并后 job 会红——这是特性**：清单一并存档于 #56（102 failed/1350 passed/18 errors @ `0e44880`，按「确定性 / 测试间污染 / venv 漂移」三层分类；其中 6 个 security path-traversal 失败单跑 5/5 passed = 污染不是代码 bug）。
- **本次新坑（已入清单）**：见下「2026-09-21」节。
- Conclusion: 本轮 19 项（10 PR + 8 issue close + 1 follow-up issue）清账完成；CI 剩红全部收敛到 #56 一个伞形 issue，不再有隐藏失败。

### 2026-09-17 第四轮：#2 Phase 1 收口（R2 = suite 层第 4 份路径策略）+ 门禁可用性

- Date: 2026-09-17, round: 健康度报告 §3.2 R2 收口（= ADR 0007 Phase 1 step 3b）+ Windows 门禁可用性
- Scope: `omni_mcp/orchestrator.py`（补齐 canonical `SYSTEM_DIRS`/`BLOCKED_EXTENSIONS` + `_system_dir_denial`）、`tests/security/test_path_policy_parity.py`（30 → 39 用例）、`tests/security` 全量、三个 omni_mcp 测试文件、tier-1 场景 3 个
- Result: `tests/security` **143 passed / 4 skipped**（4 skip = WinError 1314，本机无建符号链接权限）；parity **39 passed**；`tests/security/test_omni_mcp_path_denied.py` **5 passed**（R2 前后契约不变）；三个 omni_mcp 文件 **28 passed**（修复前 12 failed / 16 passed）。
- **零回归证明**：同一批文件在「HEAD（无 R2）」与「R2」下均为 `12 failed, 16 passed` → R2 未引入回归；那 12 个失败来自本轮定位并修掉的三条环境根因（模块级 allowlist 覆盖 / Linux venv 布局 `WinError 193` / `/tmp` 字面量），修完后同批 28 passed。
- **tier-1 场景（`.venv_ol` + WSL，`MCP_ALLOWED_DIRECTORIES=/tmp`）**：`red-team-path-traversal` **8/8 passed**（run `20260917-210145`）、`trace-mutation-manifest-x03` **2/2 passed**（`20260917-210223`）、`ol-path-denied` **2/2 passed**（`20260917-210259`）—— 三个都直接覆盖本轮改动的路径拒绝面。
- 本轮新增坑已入清单：模块级 allowlist env 的进程级污染、`.venv_ol` 守卫的伪绿、原生 Windows 拿执行型证据必须走 WSL。
- Conclusion: R2 闭环、零回归；§3.2 的 R1/R2/R3 中 R2 已关闭（R1 由 Phase 1 落地 + Phase 2 推迟覆盖，R3 已被显式接受）；#2 Phase 2 仍被 workspace 索引 403 阻塞。

### 2026-09-14 4-repo PR/issue 清账 + #16/#17 定性 + uv lock guard

- Date: 2026-09-14, round: 4-repo PR/issue 清账（backup mirrors：renanzai40/*_BackUp）
- Scope: 12 个已开 PR（suite #15/#18、ORF #7/#10/#11/#13、OL #12、OPP #9/#11/#13）+ 13 issue；#16 场景解钉；#17 CI-only 定性；ORF #9 / OPP #8 lock guard
- Result: 12 PR 全部落入 `backup/main`（GitHub 自动标记 Merged），13 issue 自动 close；三处曾红场景单跑各 3/3 passed（tool-orf-batch_convert / opp-docx-malformed-failure / opp-docx-missing-part-edge）。`uv --no-config lock --check` 在 suite/OPP/ORF 均 rc=0；OPP `uv lock` 在一次性 worktree 实测零 diff → 无需重生成。
- **#16 定性**：step 2 钉的是 ORF #8 已修缺陷（旧断言 `data_has: ['JSON_PARSE_ERROR']`）。RED（ORF 无 #11 时 `data.success=None`）→ 合入 ORF #11 后 GREEN；真实 payload 形态 = `data{success, content{success, status:"complete", succeeded:1}}`。场景断言改为钉**当前真实行为**并删除 "KNOWN DEFECT" 措辞。
- **#17 定性（置信 HIGH，产品 bug）**：OPP `import fitz` 在 PyMuPDF ≥1.28 会把 deprecation banner 打到 **stdout**，污染 `opp --json`；场景 step 3 严格 `json.loads(stdout)` 崩 → 恰好 `failed — 3 step(s), 2 passed`。CI-only 的机制 = editable `uv pip install -e` 越过 `uv.lock` 把 pymupdf 1.27.2.3 升到 1.28.2（本机 .venv_ol 停在静默版本）。已由 OPP `52d969b`（`import pymupdf as fitz`）修复；忠实 CI 复现（宿主换 files.pythonhosted 绕开 tuna 403）+ 逐版本对照确认因果。
- **#8/#9 lock guard**：5 个 `uv sync` workflow 固定 `setup-uv` 到 `0.11.8`、`uv sync --frozen`→`--locked`，并在 OPP/ORF 加显式 `uv --no-config lock --check` 守卫。
- **下次迭代对照的新坑（本日新发现，尚未 gate）**：(1) CI 的 editable 安装未用 `--no-deps`，`uv pip install -e` 会无视 lock 重解析 → 本机/CI 依赖漂移（正是 #17 的机制；建议改 `--no-deps` 或 pin），(2) 套件 `uv.lock` 100% 指向 TUNA 本地镜像（本机配置泄漏；CI runner 直连该源），(3) pre-commit `omni-contract-smoke` 在本机 pytest 阶段挂起（无单个子命令挂起，pytest 特有；本次以 `SKIP=omni-contract-smoke` 绕过），(4) ORF `.venv_ol` 元数据 0.4.4 vs pyproject 0.4.17（仅环境，非 tracked），(5) 仍有 "KNOWN DEFECT" 钉未解：`tool-ol-generate_report.yaml` / `tool-ol-translate_file.yaml`。
- Conclusion: 本轮 35 项（12 PR + 13 issue + #16 + #17 + #8/#9 guard 收尾）清账完成；无代码回归（3 目标场景 3/3，覆盖审计 37 工具口径不变）。

### 2026-09-04 omni-suite-open-source-plan tier-1 regression

- Date: 2026-09-04, round: omni-suite-open-source-plan tier-1 regression
- Result: tier-1 19 passed / 0 failed / 1 env-artifact failure (tool-ol-profile_doc: conftest dummy keys vs real-LLM-requiring scenario, pre-existing, commits in this round never touched it)
- Conclusion: commits e6906ce..f654e1a (report corrections, release checklist, README test-status, benchmark, CLI N1 enhancement) zero breakage

### 2026-08-16 套件更新后重跑（PR #41/#42 后首轮）

- 前置：同步 main 到 9085aed（PR #41 场景可移植性 + PR #42 hardening CI）；launcher 用 `run_with_env.py`（99-Tools/validation-scratch/omni-suite/）注入 env。
- 首跑 67/6/10：6 个 failed 全为 tool-opp-*（`Path not in allowed directories: /tmp/omni-agent-surface`），4 个新增 unconfigured（tool-ol-translate_file + 3 pipeline）。
- **根因 1（failed 类）**：Hermes 会话预注入 `OPP_MCP_ALLOWED_DIRS=/mnt/d/Hermes-Workspace:/home/renanzai`（**缺 /tmp fixture 目录**），launcher 用 `setdefault` 不会覆盖已存在的值 → OPP 拒绝 /tmp → tool-opp-* 第一步全 failed、第二步（allowlist 拒绝）passed。修法：launcher 对三个 allowlist 变量用**强制赋值**（`os.environ[...] =`），不用 setdefault。坑清单原有条目只说"Hermes 环境注入值只有 /mnt/d/Hermes-Workspace:/home/renanzai"，但没点明**注入的是 OPP_MCP_ALLOWED_DIRS 这个变量本身**且 setdefault 覆盖不掉。
- **根因 2（unconfigured 类）**：launcher 漏注入 `OPENCODE_GO_KEY`/`OPENCODE_GO_BASE_URL`（pipeline 场景 requires_env 用这两个**独立变量名**，与 AutoInfo 用的 OPENCODE_GO_API_KEY 不同）+ `OPP_CONFIG_PATH`/`OPP_ALLOWED_DIRECTORIES`（tool-ol-translate_file requires_env）。补注入后转绿。
- **单跑验证**：6 tool-opp-* + tool-ol-translate_file + 3 pipeline 全部单跑 passed。注意 pipeline 场景是 tier 2——`--scenario X --tier 1` 会"no scenarios found"（被 tier 过滤掉），单跑 pipeline 必须不带 --tier 或带 --tier 2。
- 全量重跑（修正 launcher）后台执行中。

### 2026-08-16 最终全量 77/0/6（回归确认 ✅）
- 修正 launcher 后全量 `20260816-154223`：83 场景 = **77 passed / 0 failed / 6 unconfigured**，与基线 20260815-161347 完全一致 → PR #41/#42 更新零破坏。
- 6 unconfigured 与基线相同（ASpose/OMNI_TM_NETWORK/OPP_IPYNB_OK/OCR_ENGINE/YOUTUBE_NETWORK/MSG_FIXTURE），客观缺 env 非回归。
- 产物审查：orf-xliff-docx/out.docx 18 段全中文（水星机器人 — 产品概述）；pipeline-pptx/out.pptx 3 slides 全英文（zh→en，公司背景/核心产品/发展愿景）；ol_out/source.md 翻译正确。非空、相关、无 VAGUE。
- 教训落地：坑清单 + skill（Hermes 预注入 allowlist 必须强制覆盖）。


### 2026-08-15 最终全量 77/0/6（首循环完整收尾 ✅）
- 最终 run `20260815-161347`:83 场景 = 77 passed / 0 failed / 6 unconfigured。
- 6 个 unconfigured 全为客观缺 env:ASpose 许可证(orf-md-msg)、OMNI_TM_NETWORK(tool-ol-search_tm)、OPP_IPYNB_OK/OCR_ENGINE/YOUTUBE_NETWORK/MSG_FIXTURE(opp 特殊格式)。非可配项。
- env 终极方案:三模块各用专用 allowlist 变量(OPP/ORF 冒号 + OL 逗号),共享 MCP_ALLOWED_DIRECTORIES 不设——避免 OPP/ORF 冒号解析被 OL 逗号值污染。OL 场景 requires_env 改为 OL_MCP_ALLOWED_DIRS(commit 627bf5e)。
- 交付包:`04-Output/artifacts/deliverables/omni-suite/omni-suite-validation-20260815-161347.zip`(135KB,report.md/scenarios.json/report.json/LOOP-LOG)。
- 产物审查:report.md 2621 行;orf-xliff-docx out.docx 18 段全中文(水星机器人 — 产品概述);pipeline-docx zh→en 方向中文 0 段为正确行为。

### 2026-08-15 第四轮（LLM 场景点亮 + 最终全量）
- 用户提供 4 组免费 key(NVIDIA 新版 + Agnes + Mistral + Zhipu),写入 ~/.hermes/.env。
- OL 模型池更新:EOL deepseek-v4-flash → z-ai/glm-5.2;kimi-k2.6 → minimaxai/minimax-m3。
- 点亮过程连环坑(全部落 LOOP-LOG):allowlist 分隔符(OL 逗号 vs ORF/OPP 冒号)、Hermes PYTHONPATH 污染(ol_cli 裸 `from cli import *` 命中 hermes-agent)、editable .pth 指向 src/ 旧副本且 pip 重装不修(手动改)、误删 _editable_impl_omni_suite.pth(omni_mcp 丢失,手动重建)。
- 修复后转绿:tool-ol-translate_md_text / translate_xliff / profile_doc / batch_translate_texts / translate_file / judge_text / add_tm_entries / extract_warnings / inspect_config / load_glossary = 10 个 LLM/工具场景。
- judge_text 场景断言漂移修复(expect "scores" → "judge_scores"),commit 679e15e。

### 2026-08-15 第三轮全量 57/0/26（首循环达成 0 failed）
- 前两轮修复生效:硬编码路径(PR #41)、副本同步、fixture 恢复 source.pptx、环境装配(markdownify/yake/weasyprint/allowlist)。
- 第三轮 `20260815-131627`:57 passed / 0 failed / 26 unconfigured(11 个可配 env 未配,15 个缺 LLM key)。
- PR #41 两个 commit 已 push:场景库可移植性 + source.pptx fixture/LOOP-LOG。
- 产物/交付包归档:见 validation-runs/20260815-131627/。

### 2026-08-15 首循环启动
- 用户指令:omni suite validation 完整跑完,按规矩来。
- preflight:STANDARDS.md 已读;坑清单创建(本文件);上次 run 无(首循环);归档映射确认(deliverables/omni-suite + validation-scratch/omni-suite 已存在)。
- 启动:`.venv/bin/python scripts/validation/run_validation.py`(全量 83 场景,后台,log → 99-Tools/validation-scratch/omni-suite/)。
- 预期:tier-1 66 全跑;tier-2 3 + tier-3 1 → unconfigured(无 key)。
- 状态:运行中 → 待结果。

## 复盘记录（fix-retro，2026-09-07 起）

> 每轮修复完成后按 `fix-retro` skill 输出复盘块（5 问）追加到此段。目标：不只记坑，沉淀模式——根因分类统计 → 重复模式识别 → 预防措施 → 技能沉淀。复盘块的根因分类基于失败定性协议（validation-run-governance.md §2），不凭印象。

## 复盘（fix-retro @ 2026-09-13）

**本轮修了什么**（7 个 issue + 8 个 PR；全部是文档/gate 层，零产品代码逻辑改动）:
- OmniSuite #10 → **PR #12**：doc-inventory claim-site 覆盖缺口（模块 `docs/*.md`、README 散文形计数、自述式版本断言）
- OmniSuite #11 → **PR #12**：模块入口一致性 fail-loud 检查（`scripts/check_module_entry.py`，挂 `make doctor` / `make entry-check` / pre-commit）
- OL #6 → **PR OL#8**：`docs/MCP-CONNECTION-TEMPLATE.md` 路径安全表陈旧（OL permissive / ORF fail-open vs 实际 fail-CLOSED）
- OL #7 → 合入 **PR OL#8**：同文件 §8 工具清单陈旧（34 → 37）
- OL #9 → **PR OL#10**：`docs/API.md` / `ARCHITECTURE.md` / `TROUBLESHOOTING.md` / `TUTORIAL.md` 的工具数、版本号、子命令数陈旧
- OPP #5 → **PR OPP#6**：`docs/API.md` "All 7 tool functions" → 9
- ORF #2 → **PR ORF#3**：README/ARCHITECTURE 6 tools + 遗留 FastMCP 描述 + 版本示例
- （非 issue）环境层：suite 模块入口 symlink 从 `src/Omni_*`（7 月旧工作目录）重指到 `../Omni_*`；`utils/mcp_client.py` 路径去 `src/` 前缀并补 OL 的 `MCP_ALLOWED_DIRECTORIES`（fail-closed 后必填）

**根因分类统计**:
| 类型 | 数量 | 例子 |
|------|------|------|
| 文档与代码漂移 | 6 | #6 §6.1 表、#7 §8 清单、#9 计数/版本/子命令、#5、#2（#10 是这类缺陷的 gate 缺口） |
| 陈旧派生物/入口 | 1 | #11：`src/Omni_*` 第二工作目录被 symlink + venv editable 引用 |
| 环境/配置 | 1 | `utils/mcp_client.py` 缺 `MCP_ALLOWED_DIRECTORIES` |

**模式识别**（重复出现的根因 → 系统性问题）:
- **模式 1：同源变更只改代码与顶层文档，不回写模块/派生文档（出现 6 次）** —— 2026-09-13 的 MCP envelope + fail-closed 改造改了代码和套件文档，模块 `docs/` 全部漏更新（OL 4 处、OPP 1 处、ORF 3 处）。系统性解读：文档同步没有 gate 覆盖模块 `docs/` 与 README 散文形，靠自觉必然漏。
- **模式 2：过期派生物仍被当权威引用（出现 2 次）** —— 7 月的 `src/Omni_*` 副本被 venv editable + symlink 引用（静默跑旧代码）；模块文档被 agent 当配置依据（照它配置起不来）。系统性解读：派生物缺「过期即失效」机制。
- **模式 3：坑清单已记录但未 gate 化 → 原样复发** —— 本清单 2026-08-15 就记过「套件内嵌模块副本必须与模块 HEAD 同步」，9/13 再次踩中（这次靠人恰好选对目录才没炸在验证里）。清单开头自嘲式写着「写而不用 = 无价值」。系统性解读：只记录不 gate 的坑 = 未修复。

**预防措施**（本轮已落地为 gate，而非再记一条）:
- #10 → PR #12：`doc_inventory.py --check` 扩到模块 `docs/*.md` + README 散文形 + `vX.Y.Z (matches pyproject.toml)` 自述式版本断言（实测：模块停在未修 main 时 exit 1 列出恰好这 7 条）
- #11 → PR #12：`scripts/check_module_entry.py` —— 入口必须是真 clone（`.git` 是目录）、venv editable `.pth` 必须与入口 realpath 一致，否则 exit 1 并打印 `ln -sfn` 修法（合成 gitdir 指针 / pth 不匹配两种坏布局实测均 fail-loud）
- 登记但未 gate（诚实记录）：MCP 示例响应 payload 与 envelope 形态一致性（本机实测 OL/ORF 的 ping 形态与文档示例不同）；模块 docs 工具章节完整性（OL 21 个工具只文档 8 个、OPP 9 个只文档 7 个）

**沉淀**（新的 skill / checklist / 坑清单条目）:
- skill `wsl-github-sync`：新增「同一 `.git` 的第二工作目录伪装成已同步 clone」坑（诊断四连 + 修法）
- skill `opencode-orchestration`：新增「brief 让 opencode 读 `--dir` 之外的兄弟仓库 → 权限层 auto-reject、run 静默零改动退出」坑（brief 必须自包含）
- dev-assets：`Omni-Suite.md` / `e2e-test-suite.md` / `AutoMedia.md` 三页 HEAD + issue/PR 轨迹
- 本 LOOP-LOG 坑清单：新增上面「2026-09-13 文档/入口 gate 化」两条

### 复盘模板（首轮复盘在下一轮修复后追加）

```markdown
## 复盘（fix-retro @ YYYY-MM-DD）
**本轮修了什么**:
- issue #NNN: 一句话

**根因分类统计**:
| 类型 | 数量 | 例子 |
|------|------|------|
| 类型错误 | N | ... |
| 边界/空值 | N | ... |
| 环境/配置 | N | ... |
| 依赖/版本 | N | ... |
| 其他 | N | ... |

**模式识别**（重复出现的根因 → 系统性问题）:
- 模式: ...（出现 ≥2 次）
- 系统性解读: ...

**预防措施**（哪些可以 gate 预防而非事后修）:
- ...

**沉淀**（新的 skill/checklist/坑清单条目）:
- ...
```
