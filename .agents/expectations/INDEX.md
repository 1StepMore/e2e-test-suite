<!-- 薄映射层（Owner 裁决 O-3, 2026-11-08）：期望唯一事实源 = scenarios/STANDARDS.md。
本文件只做指针映射，禁止复制正文；改期望只能经 Owner 显式指令改 STANDARDS.md，
改本映射层不得放松任何期望（C7 检查锚点存在性）。 -->
# Expectations Index — Omni Suite

| id | 标题 | 期望来源（唯一事实源锚点） | owner | 版本 |
|---|---|---|---|---|
| E-01 | Fallback 铁律（FAKE_LLM 永非质量证据） | `scenarios/STANDARDS.md` #fallbacks-never-evidence | Owner | 2026-11-08 |
| E-02 | 环境门禁语义（unconfigured ≠ pass） | `scenarios/STANDARDS.md` #env-gate-semantics | Owner | 2026-11-08 |
| E-03 | 工具契约符合性 | `scenarios/STANDARDS.md` #tool-contract | Owner | 2026-11-08 |
| E-04 | JSON 可解析性 | `scenarios/STANDARDS.md` #json-parseable | Owner | 2026-11-08 |
| E-05 | 错误信息清晰度 | `scenarios/STANDARDS.md` #error-clarity | Owner | 2026-11-08 |
| E-06 | 路径安全 | `scenarios/STANDARDS.md` #path-security | Owner | 2026-11-08 |
| E-07 | 退出码契约 | `scenarios/STANDARDS.md` #exit-codes | Owner | 2026-11-08 |
| E-08 | LQA 阈值 | `scenarios/STANDARDS.md` #lqa-threshold | Owner | 2026-11-08 |
| E-09 | 段落比例 | `scenarios/STANDARDS.md` #para-ratio | Owner | 2026-11-08 |
| E-10 | CJK 密度 | `scenarios/STANDARDS.md` #cjk-density | Owner | 2026-11-08 |
| E-11 | 未翻译单元 | `scenarios/STANDARDS.md` #untranslated-units | Owner | 2026-11-08 |
| E-12 | 标点卫生 | `scenarios/STANDARDS.md` #punct-hygiene | Owner | 2026-11-08 |
| E-13 | Drawing 计数 | `scenarios/STANDARDS.md` #drawing-count | Owner | 2026-11-08 |
| E-14 | 产物可打开（python-docx） | `scenarios/STANDARDS.md` #opens-docx | Owner | 2026-11-08 |

Tester 判定输出 = `.agents/roles/tester.md` 固定 JSON；执行载体 = `scripts/validation/run_validation.py` 场景库（两族判定：AGENT-SURFACE / HUMAN-QUALITY）。
