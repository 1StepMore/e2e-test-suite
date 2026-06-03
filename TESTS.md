# Test Instructions — Real LLM + E2E Suite

> How to run the test suite at `/mnt/d/贯维/Omni_Suite/tests/`. Read `SETUP.md` first if you haven't filled in `.env` and `local.yaml` yet.

---

## TL;DR — one command, all 3 nightly tests

```bash
cd /mnt/d/贯维/Omni_Suite
.venv_ol/bin/python -m pytest tests/test_e2e_real_llm.py -m "nightly" -v
```

**Expected:** `3 passed in ~6–8 minutes` (each test does 1 LLM round-trip × N units + 1 OPP extraction + 1 ORF injection).

---

## Prerequisites

Already done in this session, but verify before running:

```bash
# 1. .env has real API keys
grep -E "^(MINIMAX_API_KEY|BAIDU_API_KEY)=" Omni_Localizer/.env | sed 's/=.*$/=<SET>/'
# Expected: two non-empty lines

# 2. local.yaml exists and is gitignored
ls -la Omni_Localizer/config/local.yaml
cd Omni_Localizer && git check-ignore -v config/local.yaml
# Expected: ".gitignore:66:config/local.yaml    config/local.yaml"

# 3. .venv_ol has all packages
.venv_ol/bin/python -c "import ol_cli, ol_config, ol_lqa, ol_retry, ol_pool, ol_mcp, opp, orf, docx, lxml; print('OK')"
# Expected: OK

# 4. Markers are registered
.venv_ol/bin/python -m pytest tests/test_e2e_real_llm.py --collect-only -q 2>&1 | head -10
# Expected: 3 tests collected, all marked nightly + requires_api_key
```

If any fails, see `SETUP.md` to redo Phase 1.

---

## Run options

| Goal | Command | Duration |
|---|---|---|
| **All 3 nightly tests** (the main one) | `.venv_ol/bin/python -m pytest tests/test_e2e_real_llm.py -m "nightly" -v` | ~6-8 min |
| Just Test 1 (Path A MCP image positioning) | `.venv_ol/bin/python -m pytest tests/test_e2e_real_llm.py::TestE2ERealLLMImagePositioning::test_path_a_mcp_image_positioning_7_of_7 -v` | ~2-3 min |
| Just Test 2 (Path B CLI image positioning) | `.venv_ol/bin/python -m pytest tests/test_e2e_real_llm.py::TestE2ERealLLMImagePositioning::test_path_b_cli_image_positioning_7_of_7 -v` | ~2-3 min |
| Just Test 3 (LQA judge 4-dim avg) | `.venv_ol/bin/python -m pytest tests/test_e2e_real_llm.py::TestE2ERealLLMTranslationQuality -v` | ~2-3 min |
| All tests except nightly (CI mode) | `.venv_ol/bin/python -m pytest tests/ -m "not nightly" -v` | varies |
| Specific test, full traceback | `.venv_ol/bin/python -m pytest tests/test_e2e_real_llm.py::TestE2ERealLLMTranslationQuality --tb=long -v` | ~2-3 min |

> All commands assume working directory = `/mnt/d/贯维/Omni_Suite/`. The `.venv_ol` venv at the suite root contains all packages (ol_*, opp, orf, docx, lxml, openpyxl, ebooklib, python-docx, etc.).

---

## What the 3 nightly tests do

| # | Test | What it verifies | ~Time |
|---|---|---|---|
| 1 | `test_path_a_mcp_image_positioning_7_of_7` | OPP→OL (via MCP `translate_xliff`)→ORF: 7/7 unique image files in Haier DOCX preserve paragraph_index within ±2 | ~2-3 min |
| 2 | `test_path_b_cli_image_positioning_7_of_7` | Same as #1, but OL called via `subprocess` (CLI path) instead of MCP | ~2-3 min |
| 3 | `test_lqa_judge_4_dim_average_above_threshold` | Real LLM translation quality: JudgeService scores 4-dim avg (adequacy, fluency, terminology, format) ≥ 5.0 for all 9 XLIFF units | ~2-3 min |

See `.omo/plans/real-llm-integration-tests.md` Section 0 for the ground truth — the Haier DOCX has **12 drawings** but only **7 unique image files** (5 drawings are duplicates of existing images). The "7" baseline is correct.

---

## What passing looks like

```
============================= test session starts ==============================
platform linux -- Python 3.13.13, pytest-9.0.3
cachedir: .pytest_cache
rootdir: /mnt/d/贯维/Omni_Suite/tests
configfile: pytest.ini
collected 3 items

tests/test_e2e_real_llm.py::TestE2ERealLLMImagePositioning::test_path_a_mcp_image_positioning_7_of_7 PASSED [ 33%]
tests/test_e2e_real_llm.py::TestE2ERealLLMImagePositioning::test_path_b_cli_image_positioning_7_of_7 PASSED [ 66%]
tests/test_e2e_real_llm.py::TestE2ERealLLMTranslationQuality::test_lqa_judge_4_dim_average_above_threshold PASSED [100%]

======================== 3 passed in ~400s (0:06:40) =========================
```

You'll see lots of `litellm.acompletion(...) 200 OK` lines from real LLM calls (MiniMax-M3 + ernie-4.5-turbo-32k). That's expected — the tests are exercising the real APIs.

To reduce noise, add `-q` for quieter output:

```bash
.venv_ol/bin/python -m pytest tests/test_e2e_real_llm.py -m "nightly" -q
```

---

## If a test fails — quick diagnostic

```bash
# Re-run with full traceback and stdout/stderr captured
.venv_ol/bin/python -m pytest tests/test_e2e_real_llm.py::<FailingTest> --tb=long -v -s 2>&1 | tail -100

# Check the OPP log for extraction details
ls -t Omni_Pre_Processor/logs/opp_*.log | head -1 | xargs tail -50

# Check the ORF log for injection details
ls -t Omni_Re_Formatter/logs/orf_*.log | head -1 | xargs tail -50

# Check the OL log for translation details
ls -t Omni_Localizer/logs/ol-*.log | head -1 | xargs tail -50
```

### Common failures

| Symptom | Cause | Fix |
|---|---|---|
| `RuntimeError: There is no current event loop` | `asyncio.gather` called from sync context | Already fixed — `TestE2ERealLLMTranslationQuality` wraps gather in `async def _judge_all()` |
| `lxml.etree.XMLSyntaxError: xmlParseEntityRef: no name` | LLM wrote unescaped `&` in XLIFF target text | Already fixed — `xliff_bus.py:_escape_xml_entities()` runs before `restore_tags` |
| `litellm.BadRequestError: LLM Provider NOT provided ... You passed model=baidu/...` | `baidu` is not a litellm provider | Already fixed — use `provider: "openai"` with Baidu's OpenAI-compatible V2 base_url (done in `local.yaml`) |
| `Expected 7 unique image files in output, got N` | ORF dropped/added images | Check ORF log; verify the 7 unique files (image1.jpeg + image2.png + image8-12.png) are all in the output DOCX |
| `ValueError: Attempt to use ZIP archive that was already closed` | `with zipfile.ZipFile(...) as zf:` block too narrow | Already fixed — the block was extended in `extract_image_positions` |
| Test takes >10 min | LLM API slow or rate-limited | Each LLM call has 60s timeout. Check `litellm` warnings in stderr. If rate-limited, wait 60s and re-run |
| `ModuleNotFoundError: No module named 'X'` | Missing dep in `.venv_ol` | `.venv_ol/bin/pip install -i https://pypi.tuna.tsinghua.edu.cn/simple X` |
| `ResourceWarning: coroutine 'X' was never awaited` | An `await` was missed | Look for `asyncio.run(...)` wrapping — must be `asyncio.run(async_func())`, not `asyncio.run(sync_func_returning_coro())` |
| Test 1 or 2 fails: `paragraph_index mismatch: expected X, got Y, abs > 2` | Real LLM translated adjacent paragraphs in a way that shifted image positions | Loosen the tolerance to ±3, OR investigate which paragraph the LLM inserted images into (the OPP gives the original paragraph_index, ORF injects into the translated paragraph) |

---

## How to add a new nightly test

```python
# In tests/test_e2e_real_llm.py (or a new file in tests/)

@pytest.mark.requires_api_key
@pytest.mark.nightly
def test_your_new_real_llm_test(
    haier_real_docx_path: Path,  # the 24-image Haier DOCX
    use_real_llm,                # auto-skips if MINIMAX/BAIDU key missing
    tmp_path: Path,              # per-test scratch dir
):
    """Describe what this test verifies."""
    # ... your test logic ...
    # Use:
    #   - xliff_path, opp_images, skeleton_path = _run_opp_extraction(haier_real_docx_path, tmp_path)
    #   - images_json_path = tmp_path / "images.json"
    #   - _write_images_json(opp_images, images_json_path)
    #   - for MCP: from ol_mcp import tools as ol_mcp_tools; await ol_mcp_tools.translate_xliff(...)
    #   - for CLI: subprocess.run([sys.executable, "-m", "ol_cli", "translate-xliff", ...])
    #   - for ORF: subprocess.run([sys.executable, "-m", "orf.cli", "apply-xliff", ...])
    #   - actual_positions = extract_image_positions(output_docx)
```

### Conventions to follow

- **Always mark with both** `@pytest.mark.requires_api_key` AND `@pytest.mark.nightly` (not just one). `requires_api_key` lets `pytest -m "not nightly"` skip it cleanly; `nightly` lets `pytest -m "nightly"` pick it up.
- **Always use the `use_real_llm` fixture** — it sets `OL_CONFIG_PATH` to `Omni_Localizer/config/local.yaml` and skips the test if no key is found.
- **Use `haier_real_docx_path`** for the standard test DOCX. For other DOCX files, write a new fixture in `conftest.py` or pass `tmp_path` to a custom helper.
- **Use `_run_opp_extraction(docx, tmp_path)`** for OPP setup — returns `(xliff_path, opp_images, skeleton_path)`.
- **Use `_write_images_json(opp_images, json_path)`** to format OPP images for ORF.
- **For async LLM calls** (judge, MCP): wrap in `async def` and call via `asyncio.run(...)`. `asyncio.gather` is itself a sync function; it needs a running event loop, so don't call it from `pytest` sync context without an async wrapper.

---

## Reference files

| File | Purpose |
|---|---|
| `tests/test_e2e_real_llm.py` | The 3 nightly tests + supporting helpers (`_run_opp_extraction`, `_write_images_json`, `extract_image_positions`, `extract_xliff_units`, `use_real_llm` fixture) |
| `tests/conftest.py:617-630` | `haier_real_docx_path` fixture definition |
| `tests/test_e2e_real_llm.py:48-75` | `use_real_llm` fixture definition (sets `OL_CONFIG_PATH` to `local.yaml`) |
| `tests/pytest.ini:46-55` | `requires_api_key` + `nightly` marker registration |
| `Omni_Localizer/.env` | Real API keys (gitignored) |
| `Omni_Localizer/config/local.yaml` | Real LLM pool config (gitignored) |
| `SETUP.md` | Phase 1 setup guide — fill `.env` + `local.yaml` |
| `.omo/plans/real-llm-integration-tests.md` | Full plan with Section 0 ground-truth (12 drawings, 0 floating, 7 unique files) |
| `爱上海尔_第二章_全球创牌 - E2E测试专用.docx` | Test fixture (447 KB, 24 images, 9 paragraphs) |

---

## Cheat sheet — copy-paste ready

```bash
# Run all nightly tests
cd /mnt/d/贯维/Omni_Suite && .venv_ol/bin/python -m pytest tests/test_e2e_real_llm.py -m "nightly" -v

# Run all CI tests (excludes nightly)
cd /mnt/d/贯维/Omni_Suite && .venv_ol/bin/python -m pytest tests/ -m "not nightly"

# Run one test with full traceback
cd /mnt/d/贯维/Omni_Suite && .venv_ol/bin/python -m pytest tests/test_e2e_real_llm.py::TestE2ERealLLMTranslationQuality --tb=long -v -s

# Quick verify everything is set up
cd /mnt/d/贯维/Omni_Suite && .venv_ol/bin/python -m pytest tests/test_e2e_real_llm.py --collect-only -q
```
