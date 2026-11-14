# scope: scenarios/

验证场景库 + 判定基准。`STANDARDS.md` 是唯一可引用判定基准（两族：AGENT-SURFACE / HUMAN-QUALITY）；期望映射层在 `.agents/expectations/`（薄指针，禁止在此放松期望）。
改任何 `expect` 前先读 STANDARDS.md 对应锚点；`--check` 校验场景契约。

## 路径约定：临时根占位符（#322）

场景步骤**禁止硬编码 POSIX `/tmp`**：Windows 原生 Python 把 `/tmp` 解析到当前盘根（如 `D:\tmp`），不在 runner 沙箱 allowlist 内，PathValidator 会在场景自己的断言之前就拒绝。用 loader 在加载期替换的两个占位符（值 = `tempfile.gettempdir()`，与 runner allowlist 默认值同根；POSIX 上就是 `/tmp`，行为不变）：

- `$OMNI_TMPDIR` —— 正斜杠形式（`C:/Users/.../Temp`）。用于 python 片段源码（裸反斜杠会成 `\U` 转义）、cli 命令参数、`collect_artifacts[].path`、mcp `arguments`。
- `$OMNI_TMPDIR_NATIVE` —— 原生分隔符形式（Windows 反斜杠）。仅用于 `expect` 断言：模块 CLI 回显路径经 `Path` 归一化，全路径 `stdout_has`/`stderr_has` 必须匹配回显形态。

政策性文字里指"OL 历史 cwd+/tmp 默认行为"的措辞保持字面 `/tmp`（如 `ol-path-denied`），不要替换。
