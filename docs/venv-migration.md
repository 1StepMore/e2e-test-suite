# Venv 迁移指南（`.venv/` → `.venv_ol/`）

> 背景issue：#106。`SETUP.md` 曾让读者去看 `.venv/DEPRECATED.md`，而该文件不存在。

## 为什么废弃 `.venv/`

Suite 现在只需要**一个**整合 venv：`.venv_ol/`，OPP / OL / ORF 三件套都以 editable 模式装在里面。
`.venv/` 是早期只装 OPP/ORF 的过渡环境，OL 从没完整装进去过——实测 `.venv/bin/python -c "import ol_cli"`
仍然 `ModuleNotFoundError`，而 `.venv_ol/bin/python` 三个模块都在。

后果不只是"版本旧"，而是**用 `.venv/` 跑验证器会产出整张假红矩阵**：`scripts/format_matrix_verifier.py`
过去不检查解释器能否 import 三件套，缺模块时每一格都走到子进程再失败（实测 128 fail / 0 pass），
看起来像"128 个格子全坏了"，实际只是环境没装齐。#105 给验证器加了探活闸，现在这种情况会
直接 exit 2 并说清缺哪个模块。

## 怎么迁移

```bash
cd "${OMNI_ROOT:-.}"
# 用 .venv_ol 重建三件套（editable），这是唯一权威做法
.venv_ol/bin/pip install -e Omni_Pre_Processor/ -e Omni_Localizer/ -e Omni_Re_Formatter/
```

验证装好了（三个模块都要import 成功）：

```bash
for m in opp.cli ol_cli orf; do .venv_ol/bin/python -c "import $m" && echo "$m OK"; done
```

或者直接跑探活闸——它会用**格子本身要用的那个解释器和环境**去探活：

```bash
python scripts/format_matrix_verifier.py --suite-root . --subset docx --path-filter md
# 第一行打印 `Interpreter: <path>`，缺模块则 exit 2 并列出缺哪个
```

## 两个必须注意的坑

1. **`.venv_ol` 必须是真实目录，不要软链到 `.venv/`。**
   曾出现过 `e2e-test-suite/.venv_ol -> .venv` 的软链，于是按 `SETUP.md` 推荐的
   `.venv_ol/bin/python` 跑，实际用的是缺 OL 的废弃环境——这就是本文件存在的原因。
   排查：`readlink .venv_ol` 应当无输出（不是软链）。

2. **不要往 `.venv/` 里加依赖**，它们对测试套件不可见（套件只认 `.venv_ol`）。

## 为什么这份文件不在 `.venv/` 里

`.venv/` 在 `.gitignore` 第 55 行被忽略，所以 `.venv/DEPRECATED.md`
**根本无法提交**——原 issue 建议的修法在结构上就不成立。本文件放在
`docs/`，是仓库里唯一能被版本管理、也唯一能在新机器上被读到的地方。

> 维护提醒：`docs/dev/validation-loop-log.md` 里已有一条同族坑
> ——「在 worktree 里跑测试必须显式 `PYTHONPATH=<worktree>/src`」，因为
> editable `.pth` 指向主检出目录。同源问题：**先确认解释器与环境解析到哪，再判定失败真假。**
