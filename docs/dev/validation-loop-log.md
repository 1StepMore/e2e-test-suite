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
- [ ] **三个模块的 allowlist env 分隔符不同**——OL `MCP_ALLOWED_DIRECTORIES` 用**逗号**(`security.py:276 split(",")`),ORF `ORF_MCP_ALLOWED_DIRS` / OPP `OPP_MCP_ALLOWED_DIRS` 用**冒号**。配错分隔符 → 整个字符串被当成一个目录,任何路径都 OL_PATH_NOT_ALLOWED(failed 而非 unconfigured)。
- [ ] **Hermes 会话注入 PYTHONPATH 含 `~/.hermes/hermes-agent` → OL `from cli import *` 裸导入会命中 hermes-agent 的 cli.py**——表现为 ModuleNotFoundError: prompt_toolkit(其实是 import 错了文件)。跑 OL/OPP/ORF 的 CLI 子进程前 `unset PYTHONPATH`。同坑:`.venv_ol` editable .pth 若指向 `src/Omni_*` 旧副本(被 gitignore),手动改 .pth 指向 `Omni_*/src`,别指望 pip 重装自动修(pip 有 editable 路径缓存)。
- [ ] **NVIDIA NIM key 分两档**:能 `GET /v1/models`(列 102 个)≠ 能调用;免费 key 需在 build.nvidia.com 模型页逐个授权,未授权模型调用 403 "Authorization failed"。

## 循环事件（major events，newest on top）

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
