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

## 循环事件（major events，newest on top）

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
