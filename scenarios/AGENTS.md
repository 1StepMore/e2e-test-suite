# scope: scenarios/

验证场景库 + 判定基准。`STANDARDS.md` 是唯一可引用判定基准（两族：AGENT-SURFACE / HUMAN-QUALITY）；期望映射层在 `.agents/expectations/`（薄指针，禁止在此放松期望）。
改任何 `expect` 前先读 STANDARDS.md 对应锚点；`--check` 校验场景契约。
