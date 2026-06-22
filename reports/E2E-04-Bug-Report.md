# E2E-04 Bug Report (Revised 2026-06-13)
**发现时间**: 2026-05-29
**修订**: 2026-06-13（ULW Cycle 1 重新诊断 + 修复）
**工具**: OL CLI (`translate-xliff`)
**Git SHA**: `4685a47` (pre-fix)
**涉及文件**: `Omni_Localizer/src/ol_terminology/extractor.py`

---

## 1. 问题现象（实际）

调用 `ol translate-xliff` 时（**任何**有 XLIFF 输入的调用）：
- **CLI 完全挂死**（exit 124 / timeout 30s+），**不返回任何输出**
- 不产生 stdout、stderr、日志、输出文件
- 任何使用 `OMNI_TEST_FAKE_LLM=1` 的测试也会挂死

⚠️ **bug 报告原版**（2026-05-29）声称症状是"`<target>` 为空 + `success: true`"。**这个诊断是错的**——实际是 CLI 在模块导入阶段就挂死，根本到不了 LLM 调用。

---

## 2. 真正的根因（2026-06-13 重新诊断）

`Omni_Localizer/src/ol_terminology/extractor.py` 第 7 行：

```python
try:
    from keybert import KeyBERT   # ← 关键
    _KEYBERT_AVAILABLE = True
except ImportError:
    _KEYBERT_AVAILABLE = False
    KeyBERT = None
```

`from keybert import KeyBERT` 在**模块顶层**执行，触发 `KeyBERT` → `sentence-transformers` → 模型预加载。在**没有预下载模型**的环境（CI / 沙箱 / 新机器），这个 import 链**挂死**。

### 受影响的导入链

```
ol_cli.translate_xliff (lazy via __getattr__)
    → load_config(config_path)
    → ol_config.loader
    → from ol_terminology.glossary import load_glossary_from_path
    → ol_terminology/__init__.py runs:
        line 19: from ol_terminology.glossary import ...   # OK
        line 20: from ol_terminology.glossary_class import ... # OK
        line 21: from ol_terminology.rag_injector import ...  # OK
        line 22: from ol_terminology.extractor import ...    # ← HANGS HERE
        line 23: from ol_terminology.disambiguator import ... (never reached)
```

模块 `extractor.py` 顶层的 `from keybert import KeyBERT` 阻塞整个导入链，导致：
1. CLI 启动时 `__getattr__` 触发延迟加载 → 挂
2. 任何间接 import `ol_terminology` 的代码也挂
3. 所有 XLIFF 翻译测试、MD 翻译测试都受影响

---

## 3. 涉及文件

```
Omni_Localizer/src/ol_terminology/extractor.py    ← 修复根因
Omni_Localizer/tests/test_term_extractor.py      ← 适配新设计（patch targets changed）
tests/test_e2e_04_fix.py                         ← 新增：E2E 回归测试
```

---

## 4. 可复现（修复前）

```bash
cd /mnt/d/贯维/Omni_Suite
timeout 30 .venv_ol/bin/python -c "import ol_terminology" 2>&1
# 预期: 成功 (0.85s)
# 实际: timeout 30s — 挂死
```

```bash
cd /mnt/d/贯维/Omni_Suite
timeout 30 .venv_ol/bin/python -m ol_cli translate-xliff tests/fixtures/test.xlf -s zh -t en -o /tmp/out 2>&1
# 预期: exit 0, 输出 XLIFF 含 <target> 内容
# 实际: timeout 30s — CLI 挂死, 无任何输出
```

---

## 5. 修复方案

**最小修改**：`Omni_Localizer/src/ol_terminology/extractor.py` 把 KeyBERT 和 YAKE 改为**惰性 import**。

把模块顶层的 `from keybert import KeyBERT` 和 `import yake` 移到函数内部的 `_probe_keybert()` / `_probe_yake()`。这两个 probe 函数只在第一次调用 `extract_terms()` 时才真正 import。这样：

- 模块 import 永远快（0.85s → 0.00s）
- 任何环境都能加载模块
- 实际使用 `extract_terms()` 时才付出模型加载成本（与原来一致）

修复后行为：
- `import ol_terminology` → 0.85s（原 timeout 30s+）
- `import ol_terminology.extractor` → 0.00s（原 timeout 30s+）
- `import ol_cli` → 0.64s（原 timeout 30s+）
- `ol translate-xliff input.xlf -s en -t zh -o out/` → 31s, exit 0, 输出含 `<target>你好</target>` 等真实翻译

---

## 6. 测试

| Test | File | Status |
|------|------|--------|
| `test_extractor_import_completes_within_5_seconds` | `tests/test_e2e_04_fix.py` (new) | ✅ PASS |
| `test_ol_cli_translate_xliff_produces_output` | `tests/test_e2e_04_fix.py` (new) | ✅ PASS |
| `test_term_extractor.py` (4 tests) | `Omni_Localizer/tests/test_term_extractor.py` (updated) | ✅ PASS |

修复后回归验证：
- OL 模块测试 742 pass / 35 fail（35 个都是预存在失败，与本次修复无关）
- 新增 0 失败
- 修复 +4 失败（term_extractor 测试，已适配）

---

## 7. 修复状态

✅ **已修复**（代码已写，待 commit）

**实际修改清单**：
1. `Omni_Localizer/src/ol_terminology/extractor.py` — KeyBERT/YAKE 改为惰性 import
2. `Omni_Localizer/tests/test_term_extractor.py` — 6 个测试更新 patch 目标（`_probe_keybert` / `_KeyBERT` 替代旧的 `KeyBERT`）
3. `tests/test_e2e_04_fix.py`（新）— 2 个 E2E 回归测试，验证模块快速导入 + CLI 输出非空 target

**未 commit**（等待用户授权）
- Commit 应该在 `Omni_Localizer/` 子仓库执行（不是 suite 仓库）
- 建议 message: `fix(ol-terminology): make KeyBERT/YAKE imports lazy to fix E2E-04 hang (2026-06-13)`
