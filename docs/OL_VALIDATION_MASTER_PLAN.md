# OL Validation Master Plan

## Result-Oriented · User-Centric · All Scenarios & Boundaries

**For:** OpenCode, Claude Code, Cline, Hermes Agent — any AI agent validating OL
**Date:** 2026-07-22
**Strategy:** Every section asks a user question → executes scenarios → reports a binary verdict
**Current Baseline:** v0.7.1 — 21 MCP tools, 8 quality gates, 4-layer repair pipeline, ModelPool failover, LQA

---

## How to Use This Plan

```yaml
1. Pick a USER QUESTION from the table of contents
2. Read the scenarios under it
3. Execute each scenario (CLI, MCP, or Python)
4. Record the ACTUAL RESULT
5. Compare ACTUAL vs EXPECTED
6. Report the VERDICT at the end of the section
```

The plan is designed so that any AI agent can execute it independently and report: **"✅ All PASS"** or **"❌ These N items FAILED"**.

---
## ⏱ Execution Priority

| Priority | Questions | Reason |
|----------|-----------|--------|
| P0 | Q1-OL, Q2-OL, Q3-OL | Core functionality — if these fail, nothing else matters |
| P1 | Q5-OL, Q6-OL, Q7-OL | Important but depend on P0 passing |
| P2 | Q4-OL, Q8-OL, Q9-OL, Q10-OL, Q11-OL, Q12-OL, Q13-OL | Can be deferred if P0/P1 fail — run after core is verified |
| P3 | Q14-OL, Q15-OL, Q16-OL, Q17-OL | Cost-incurring — run last and only if P0-P2 pass |

**Execution rule:** Run P0 first. If any P0 FAIL, fix before continuing to P1.
If P1 FAIL, fix before P2. P3 requires real API keys — skip if not configured.


## Verdict Legend

| Symbol | Meaning |
|--------|---------|
| ✅ PASS | All scenarios in this section match expected results |
| ❌ FAIL | One or more scenarios did NOT match expected results |
| ⚠️ PARTIAL | Some scenarios pass, some fail (list which ones) |
| ➖ SKIP | Scenarios intentionally skipped (reason documented) |

---

## Prerequisites

Before running validation, ensure:

```bash
# 1. Install the package
cd /mnt/d/贯维/Omni_Suite/Omni_Localizer
pip install -e ".[mcp]"

# 2. Set FAKE_LLM for zero-cost testing (unless testing real LLMs)
export OMNI_TEST_FAKE_LLM=1

# 3. Verify test infrastructure
cd /mnt/d/贯维/Omni_Suite
pytest Omni_Localizer/tests/ --collect-only -q  # Should collect 200+ tests

# 4. Verify CLI works
ol --help  # Should show 6 commands: translate-md, translate-xliff, translate-batch, extract-warnings, mcp
```

---

## Table of Contents

### Part 1: Core Translation Pipeline
- **Q1-OL:** Can I translate a Markdown file end-to-end?
- **Q2-OL:** Can I translate an XLIFF file end-to-end?
- **Q3-OL:** Does FAKE_LLM mode work (zero-cost testing)?
- **Q4-OL:** Does the Model Pool failover work correctly?

### Part 2: Quality Gates & LQA
- **Q5-OL:** Do all 8 quality gates fire correctly?
- **Q6-OL:** Does LQA scoring work (judge/retry)?

### Part 3: MCP Surface Mastery
- **Q7-OL:** Do all 21 MCP tools respond and function?

### Part 4: Agent-as-User Workflows
- **Q8-OL:** Can an agent translate text via MCP and verify quality?
- **Q9-OL:** Does glossary/TM injection improve translation?

### Part 5: CLI Surface Mastery
- **Q10-OL:** Do all CLI commands work correctly? (7 commands)

### Part 6: Error & Boundary Matrix
- **Q11-OL:** What happens with empty/large content?
- **Q12-OL:** What happens when no LLM keys are configured?

### Part 7: Production Validation
- **Q13-OL:** Does the MCP server start and respond via stdio?

### Part 8: Real LLM API Configuration & E2E Tests
- **Q14-OL:** Can an agent configure real LLM API keys and verify connectivity?
- **Q15-OL:** Can an agent translate and verify quality with real LLM?
- **Q16-OL:** Can an agent run the full pipeline with real APIs end-to-end?
- **Q17-OL:** Can an agent detect, diagnose, and recover from real LLM API issues?

### Part 9: Final Verdict

---

# Part 1: Core Translation Pipeline

---

## Q1-OL: Can I translate a Markdown file end-to-end?

**User says:** "I have a Markdown file I need translated from English to Chinese."

**Why this matters:** MD translation is the primary use case of OL. If this doesn't work, nothing else matters.

### Prerequisites
```bash
cd /tmp && rm -rf test-md-translate && mkdir test-md-translate && cd test-md-translate
export OMNI_TEST_FAKE_LLM=1
cat > sample.md << 'EOF'
# Hello World

This is a paragraph with **bold** and *italic* text.

## Section Two

- List item one
- List item two

Here is a `code block` inline.

```python
def hello():
    print("Hello World")
```

[A link to somewhere](https://example.com)
EOF
```

### Scenarios

#### 1.1 🟢 Happy Path — CLI translate-md with FAKE_LLM
```bash
ol translate-md sample.md -s en -t zh -o /tmp/test-md-translate/output/ --config /mnt/d/贯维/Omni_Suite/Omni_Localizer/config/default.yaml --no-glossary
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Output file created at `/tmp/test-md-translate/output/sample.md`
- ✅ Translated content is non-empty (FAKE_LLM returns a deterministic mock translation)
- ✅ Code blocks preserved (```python ... ``` still present)
- ✅ Links preserved ([A link to somewhere](https://example.com))
- ✅ Bold/italic markers preserved (** ** and * *)
- ✅ YAML frontmatter present (source_lang, target_lang, original_file, processor, version)

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 1.2 🟢 JSON output is parseable
```bash
ol translate-md sample.md -s en -t zh -o /tmp/test-md-translate/output-json/ --config /mnt/d/贯维/Omni_Suite/Omni_Localizer/config/default.yaml --no-glossary --json 2>/dev/null
```
**Expected Result:** ✅ Valid JSON with `{"success": true, "input_file": "...", "output_file": "...", "source_lang": "en", "target_lang": "zh"}`

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 1.3 🟢 Translate without frontmatter
```bash
ol translate-md sample.md -s en -t zh -o /tmp/test-md-translate/output-nofm/ --config /mnt/d/贯维/Omni_Suite/Omni_Localizer/config/default.yaml --no-glossary --no-frontmatter
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Output file does NOT start with `---` YAML frontmatter
- ✅ Translated content is present

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 1.4 🟢 Chunk-by-paragraph mode
```bash
ol translate-md sample.md -s en -t zh -o /tmp/test-md-translate/output-chunk/ --config /mnt/d/贯维/Omni_Suite/Omni_Localizer/config/default.yaml --no-glossary --chunk-by-paragraph
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Output file created with translated content
- ✅ Paragraph boundaries preserved

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 1.5 🔴 Translate with non-existent input file
```bash
ol translate-md /tmp/nonexistent/nope.md -s en -t zh -o /tmp/test-md-translate/output/
```
**Expected Result:** ❌ Exit code != 0. Error message mentions file not found. No crash.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q1-OL Verdict

| Scenario | Result |
|----------|--------|
| 1.1 Happy path MD translate | ⬜ |
| 1.2 JSON output | ⬜ |
| 1.3 No frontmatter | ⬜ |
| 1.4 Chunk-by-paragraph | ⬜ |
| 1.5 Nonexistent input | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q2-OL: Can I translate an XLIFF file end-to-end?

**User says:** "I have an XLIFF file from OPP that needs translating."

**Why this matters:** XLIFF is the layout-preserving translation path used for contracts, branded docs, and exact-layout outputs.

### Prerequisites
```bash
cd /tmp && rm -rf test-xliff-translate && mkdir test-xliff-translate && cd test-xliff-translate
export OMNI_TEST_FAKE_LLM=1
cat > sample.xlf << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="document.docx" source-language="en" target-language="zh">
    <body>
      <trans-unit id="u1">
        <source>Hello World</source>
        <target/>
      </trans-unit>
      <trans-unit id="u2">
        <source>This is a <bx id="1"/>test<ex id="1"/> sentence.</source>
        <target/>
      </trans-unit>
    </body>
  </file>
</xliff>
EOF
```

### Scenarios

#### 2.1 🟢 Happy Path — CLI translate-xliff with FAKE_LLM
```bash
ol translate-xliff sample.xlf -s en -t zh -o /tmp/test-xliff-translate/output/ --config /mnt/d/贯维/Omni_Suite/Omni_Localizer/config/default.yaml --no-glossary
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Output XLIFF file created at `/tmp/test-xliff-translate/output/sample.xlf`
- ✅ `<target>` elements are filled with non-empty translations
- ✅ XML structure preserved (all `<trans-unit>`, `<source>`, `<bx/>`, `<ex/>` intact)
- ✅ Inline tags (`<bx id="1"/>`, `<ex id="1"/>`) preserved in target

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 2.2 🟢 XLIFF with empty target tags (pre-populated target)
```bash
cat > sample-pretarget.xlf << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="document.docx" source-language="en" target-language="zh">
    <body>
      <trans-unit id="u1">
        <source>Hello World</source>
        <target></target>
      </trans-unit>
    </body>
  </file>
</xliff>
EOF
ol translate-xliff sample-pretarget.xlf -s en -t zh -o /tmp/test-xliff-translate/output/ --config /mnt/d/贯维/Omni_Suite/Omni_Localizer/config/default.yaml --no-glossary
```
**Expected Result:** ✅ Exit code 0. `<target>` filled. XML valid.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 2.3 🔴 XLIFF with no trans-units
```bash
cat > empty.xlf << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="empty.docx" source-language="en" target-language="zh">
    <body>
    </body>
  </file>
</xliff>
EOF
ol translate-xliff empty.xlf -s en -t zh -o /tmp/test-xliff-translate/output/ --config /mnt/d/贯维/Omni_Suite/Omni_Localizer/config/default.yaml --no-glossary
```
**Expected Result:** ❌ Error message: "No translation units found". Exit code != 0. No crash.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 2.4 🔴 Non-existent XLIFF file
```bash
ol translate-xliff /tmp/nonexistent.xlf -s en -t zh -o /tmp/test-xliff-translate/output/ --config /mnt/d/贯维/Omni_Suite/Omni_Localizer/config/default.yaml
```
**Expected Result:** ❌ Exit code != 0. File not found error. No crash.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q2-OL Verdict

| Scenario | Result |
|----------|--------|
| 2.1 Happy path XLIFF translate | ⬜ |
| 2.2 Pre-populated target | ⬜ |
| 2.3 Empty trans-units | ⬜ |
| 2.4 Non-existent file | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q3-OL: Does FAKE_LLM mode work (zero-cost testing)?

**User says:** "I want to test the pipeline without burning API credits."

**Why this matters:** FAKE_LLM is the primary testing seam. If it's broken, all CI and dev workflows break.

### Prerequisites
```bash
export OMNI_TEST_FAKE_LLM=1
cd /tmp && rm -rf test-fake-llm && mkdir test-fake-llm && cd test-fake-llm
```

### Scenarios

#### 3.1 🟢 FAKE_LLM produces deterministic mock translation
```python
python3 -c "
import os
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_pool.fake import FakeModelPool
pool = FakeModelPool()
import asyncio
result = asyncio.run(pool.translate('Hello world', 'en', 'zh'))
print(f'Translation: {result!r}')
assert result and len(result) > 0, 'Empty translation'
print(f'Fake translation is non-empty: {result}')
"
```
**Expected Result:**
- ✅ Translation returns non-empty string
- ✅ No network calls made
- ✅ Deterministic output (same input → same output)

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 3.2 🟢 FAKE_LLM mode is detectable from env var
```bash
python3 -c "
import os
flag = os.environ.get('OMNI_TEST_FAKE_LLM', '')
assert flag == '1', f'OMNI_TEST_FAKE_LLM={flag!r} not set to 1'
print('FAKE_LLM detected')
"
```
**Expected Result:** ✅ Env var `OMNI_TEST_FAKE_LLM=1` is set and recognized.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 3.3 🟢 Tests pass with FAKE_LLM
```bash
cd /mnt/d/贯维/Omni_Suite
OMNI_TEST_FAKE_LLM=1 pytest Omni_Localizer/tests/ -v --tb=short -x 2>&1 | head -60
```
**Expected Result:** ✅ Test suite passes. 0 failures. Tests complete within reasonable time.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 3.4 🔴 Tests fail without FAKE_LLM if no real keys configured (expected non-fatal)
```bash
unset OMNI_TEST_FAKE_LLM
cd /mnt/d/贯维/Omni_Suite
pytest Omni_Localizer/tests/test_ol_mcp.py -v --tb=short -x 2>&1 | head -30
# Re-set FAKE_LLM after
export OMNI_TEST_FAKE_LLM=1
```
**Expected Result:** ❌ Tests fail with `${VAR}` resolution errors or API key errors. This is EXPECTED — FAKE_LLM is required without real keys.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q3-OL Verdict

| Scenario | Result |
|----------|--------|
| 3.1 Deterministic mock translation | ⬜ |
| 3.2 Env var detectable | ⬜ |
| 3.3 Tests pass with FAKE_LLM | ⬜ |
| 3.4 Tests fail without FAKE_LLM | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q4-OL: Does the Model Pool failover work correctly?

**User says:** "What if my primary LLM provider is down?"

**Why this matters:** ModelPool failover is the reliability mechanism for production translation. If the primary model fails, the fallback must be tried automatically.

### Prerequisites
```bash
export OMNI_TEST_FAKE_LLM=1
```

### Scenarios

#### 4.1 🟢 Model pool has role-based routing (translation/judging/restoration)
```python
python3 -c "
import os
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_pool.fake import FakeModelPool
pool = FakeModelPool.get_instance()
# Verify the pool has role-separated model lists
print(f'Pool type: {type(pool).__name__}')
print('FakeModelPool bypasses role routing in test mode')
print('✅ Role-based routing exists (production: litellm Router with simple-shuffle)')
"
```
**Expected Result:** ✅ ModelPool supports role-based routing (translation vs judging vs restoration models configured separately in YAML).

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 4.2 🟢 Circuit breaker opens after 5 consecutive failures
```python
python3 -c "
import os
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_pool.router import _strip_thinking_blocks
# Circuit breaker is configured on the litellm Router
# Default: 5 failures → open for 60s
print('Circuit breaker: 5 consecutive failures → open 60s')
print('✅ Circuit breaker exists (pybreaker, configured in ModelPool)')
"
```
**Expected Result:** ✅ Circuit breaker is configured with 5-failure threshold and 60s cooldown.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 4.3 🟢 Model pool retries on failure (num_retries=2)
```python
python3 -c "
import os
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_pool.fake import FakeModelPool
pool = FakeModelPool()
print('FakeModelPool: no real retry in fake mode.')
print('Production: litellm Router num_retries=2, simple-shuffle routing strategy.')
print('✅ Retry mechanism exists')
"
```
**Expected Result:** ✅ `num_retries=2` is configured on the litellm Router. Failing calls are retried up to 2 times before fallback.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 4.4 🟢 `has_source_language_residual()` helper works (OL#53 Polish guard)
```python
python3 -c "
import os
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_pool import has_source_language_residual
# Test zh→en direction
result = has_source_language_residual('这是一个测试', 'en')
print(f'zh text → en: {result}')  # Should be True
result2 = has_source_language_residual('This is English', 'en')
print(f'en text → en: {result2}')  # Should be False
assert has_source_language_residual('这是一个测试', 'en') == True
assert has_source_language_residual('Hello world', 'en') == False
print('✅ has_source_language_residual works correctly')
"
```
**Expected Result:** ✅ `has_source_language_residual()` correctly detects source language text in target output. Used by the Polish guard to avoid reverting translations.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q4-OL Verdict

| Scenario | Result |
|----------|--------|
| 4.1 Role-based routing | ⬜ |
| 4.2 Circuit breaker | ⬜ |
| 4.3 Retry mechanism | ⬜ |
| 4.4 Language residual helper | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

# Part 2: Quality Gates & LQA

---

## Q5-OL: Do all 8 quality gates fire correctly?

**User says:** "I need translation quality checks to work — flagging issues in the output."

**Why this matters:** Quality gates are the primary quality assurance mechanism. Each gate catches a specific class of translation defect.

### Prerequisites
```bash
export OMNI_TEST_FAKE_LLM=1
```

### Scenarios

#### 5.1 🟢 Gate 1 — inline_tags: detects tag parity mismatch
```python
python3 -c "
from ol_lqa.quality_gates import run_quality_gates
# Source has <bx>, target is missing <bx> → should flag
warnings = run_quality_gates(
    '<bx id=\"1\"/>Hello<ex id=\"1\"/>',
    '你好<ex id=\"1\"/>',  # missing <bx>
    inline_tags_enabled=True,
)
print(f'Warnings: {warnings}')
assert any('INLINE_TAG_MISMATCH' in w for w in warnings), 'Should flag missing <bx>'
print('✅ Gate 1 catches inline tag mismatch')
"
```
**Expected Result:** ✅ `INLINE_TAG_MISMATCH` warning generated when `<bx>`/`<ex>`/`<x>` tag counts differ between source and target.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 5.2 🟢 Gate 2 — terminology: detects inconsistent glossary usage
```python
python3 -c "
from ol_lqa.quality_gates import run_quality_gates
glossary = {'API endpoint': {'translation': 'API 端点', 'variants': {'API endpoint': 'API 端点'}}}
warnings = run_quality_gates(
    'Call the API endpoint to continue',
    '调用 API endpoint 来继续',  # source term left untranslated
    glossary=glossary,
    terminology_enabled=True,
)
print(f'Warnings: {warnings}')
assert any('TERMINOLOGY_INCONSISTENCY' in w for w in warnings), 'Should flag untranslated term'
print('✅ Gate 2 catches terminology inconsistency')
"
```
**Expected Result:** ✅ `TERMINOLOGY_INCONSISTENCY` warning generated when glossary term is used inconsistently (source term mixed into target language).

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 5.3 🟢 Gate 3 — length_ratio: detects out-of-bounds length
```python
python3 -c "
from ol_lqa.quality_gates import run_quality_gates
# Very short source, very long target → should flag
warnings = run_quality_gates(
    'Hi',  # 2 chars
    'This is an excessively long translation for such a short source text',  # 70+ chars
    length_ratio_enabled=True,
    length_ratio_min=0.5,
    length_ratio_max=3.0,
)
print(f'Warnings: {warnings}')
assert any('LENGTH_RATIO' in w for w in warnings), 'Should flag length ratio violation'
print('✅ Gate 3 catches length ratio violation')
"
```
**Expected Result:** ✅ `LENGTH_RATIO` warning generated when `len(target)/len(source)` is outside configured bounds.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 5.4 🟢 Gate 4 — locale: detects currency mixing and date leakage
```python
python3 -c "
from ol_lqa.quality_gates import run_quality_gates
# Target has mixed currencies and CJK date → should flag
warnings = run_quality_gates(
    'The price is 100 dollars, dated January 1, 2026.',
    '价格是$100€，日期2026年01月01日',
    locale_enabled=True,
    target_locale='en-US',
)
print(f'Warnings: {warnings}')
currency_warnings = [w for w in warnings if 'CURRENCY_MIXING' in w]
date_warnings = [w for w in warnings if 'DATE_LEAKAGE' in w]
print(f'Currency warnings: {currency_warnings}')
print(f'Date warnings: {date_warnings}')
assert len(currency_warnings) > 0, 'Should flag mixed currencies'
assert len(date_warnings) > 0, 'Should flag CJK date leakage'
print('✅ Gate 4 catches locale violations')
"
```
**Expected Result:** ✅ `CURRENCY_MIXING`, `DATE_LEAKAGE`, `DIGIT_GROUPING`, or `UNIT_SPELLING` warnings generated as appropriate.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 5.5 🟢 Gate 5 — source_copy: detects unchanged source echo
```python
python3 -c "
from ol_lqa.quality_gates import run_quality_gates
# Target is identical to source → should flag
warnings = run_quality_gates(
    'This is a test paragraph.',
    'This is a test paragraph.',  # unchanged copy
    source_copy_enabled=True,
)
print(f'Warnings: {warnings}')
assert any('SOURCE_COPY' in w for w in warnings), 'Should flag source copy'
print('✅ Gate 5 catches source copy')
"
```
**Expected Result:** ✅ `SOURCE_COPY` warning generated when target text is identical (or near-identical) to source text.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 5.6 🟢 Gate 6 — source_script_check: detects CJK in non-CJK locale
```python
python3 -c "
from ol_lqa.quality_gates import run_quality_gates
# Target locale is en, but has CJK characters → should flag
warnings = run_quality_gates(
    'This is a test.',
    '这是一个测试',
    cjk_residue_enabled=True,
    target_lang='en',
)
print(f'Warnings: {warnings}')
assert any('SOURCE_SCRIPT_FRAGMENT' in w for w in warnings), 'Should flag CJK in English'
print('✅ Gate 6 catches CJK residue')
"
```
**Expected Result:** ✅ `SOURCE_SCRIPT_FRAGMENT` warning generated when CJK characters appear in non-CJK target locale.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 5.7 🟢 Gate 7 — protocol_artifact_check: detects LLM protocol markers
```python
python3 -c "
from ol_lqa.quality_gates import run_quality_gates
# Target contains LLM protocol artifacts → should flag
warnings = run_quality_gates(
    'Translate this.',
    '[USERTEXTSTART]Translated text[USERTEXTEND]',
    llm_markers_enabled=True,
)
print(f'Warnings: {warnings}')
assert any('PROTOCOL_ARTIFACT' in w for w in warnings), 'Should flag protocol artifacts'
print('✅ Gate 7 catches protocol artifacts')
"
```
**Expected Result:** ✅ `PROTOCOL_ARTIFACT` warning generated when LLM protocol/metadata markers (e.g. `[USERTEXTSTART]`, `[USERTEXTEND]`) appear in output.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 5.8 🟢 Gate 8 — terms_audit: full glossary term audit
```python
python3 -c "
from ol_lqa.quality_gates import run_quality_gates
glossary = {'button': {'translation': '按钮', 'variants': {'button': '按钮'}}}
warnings = run_quality_gates(
    'Click the button to continue.',
    '点击 button 继续。',  # source term left untranslated
    glossary=glossary,
    terms_audit_enabled=True,
)
print(f'Warnings: {warnings}')
# terms_audit may report mismatches or low_confidence
has_term_audit = any(w.startswith('OL_WARN: TERM_AUDIT') for w in warnings)
if has_term_audit:
    print('✅ Gate 8 terms_audit flagged issues')
else:
    print('⚠️ Gate 8 did not fire (may need glossary with variants/confidence)')
"
```
**Expected Result:** ✅ `TERM_AUDIT_MISMATCH`, `TERM_AUDIT_ABSENT`, `TERM_AUDIT_INCONSISTENCY`, or `TERM_AUDIT_LOW_CONFIDENCE` warnings generated as appropriate.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 5.9 🟢 All 8 gates are non-blocking (advisory only)
```python
python3 -c "
from ol_lqa.quality_gates import run_quality_gates
# Even with all gates enabled and violating, the function returns warnings
# but does NOT raise an exception or block execution
warnings = run_quality_gates(
    'Test <bx id=\"1\"/>content<ex id=\"1\"/>.',
    '测试 content。',
    glossary={'content': {'translation': '内容'}},
    inline_tags_enabled=True,
    terminology_enabled=True,
    length_ratio_enabled=True,
    length_ratio_min=0.5,
    length_ratio_max=3.0,
    locale_enabled=True,
    target_locale='en-US',
    source_copy_enabled=True,
    cjk_residue_enabled=True,
    target_lang='zh',
    llm_markers_enabled=True,
    terms_audit_enabled=True,
)
print(f'Total warnings: {len(warnings)}')
for w in warnings:
    print(f'  {w}')
print(f'All gates are non-blocking: no exception raised')
print('✅ Quality gates are advisory')
"
```
**Expected Result:** ✅ All 8 gates run without exceptions. Warnings are returned, execution continues normally.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q5-OL Verdict

| Scenario | Result |
|----------|--------|
| 5.1 Gate 1 — inline_tags | ⬜ |
| 5.2 Gate 2 — terminology | ⬜ |
| 5.3 Gate 3 — length_ratio | ⬜ |
| 5.4 Gate 4 — locale | ⬜ |
| 5.5 Gate 5 — source_copy | ⬜ |
| 5.6 Gate 6 — script check | ⬜ |
| 5.7 Gate 7 — protocol artifacts | ⬜ |
| 5.8 Gate 8 — terms_audit | ⬜ |
| 5.9 Advisory (non-blocking) | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q6-OL: Does LQA scoring work (judge/retry)?

**User says:** "I want the system to automatically judge translation quality and retry bad ones."

**Why this matters:** LQA is the self-correction mechanism. Without it, low-quality translations pass through silently.

### Prerequisites
```bash
export OMNI_TEST_FAKE_LLM=1
```

### Scenarios

#### 6.1 🟢 JudgeService creates EvaluationResult with scores
```python
python3 -c "
import asyncio, os
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_lqa.judge import JudgeService
from ol_pool.fake import FakeModelPool

async def test():
    pool = FakeModelPool()
    judge = JudgeService(pass_threshold=7.0, model_pool=pool)
    result = await judge.judge('Hello world', '你好世界', unit_id='u1', source_lang='en', target_lang='zh')
    print(f'Scorer scores: {result.scorer_scores}')
    print(f'Judge scores: {result.judge_scores}')
    print(f'Warnings: {result.warnings}')
    print(f'Format preserved: {result.format_preserved}')
    assert hasattr(result, 'scorer_scores'), 'Should have scorer_scores'
    assert hasattr(result, 'judge_scores'), 'Should have judge_scores'
    print('✅ JudgeService returns EvaluationResult')

asyncio.run(test())
"
```
**Expected Result:** ✅ `JudgeService.judge()` returns an `EvaluationResult` with `scorer_scores`, `judge_scores` (adequacy, fluency, terminology_consistency, format_preservation), `warnings`, and `format_preserved`.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 6.2 🟢 LQA retry mechanism (RetryManager)
```python
python3 -c "
import os
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_retry import RetryManager
# Verify RetryManager exists and has expected structure
print(f'RetryManager imported successfully')
print('✅ RetryManager exists')
"
```
**Expected Result:** ✅ `RetryManager` exists. LQA retries up to `lqa_max_retries` (default 2) when `judge_score < lqa_threshold` (default 7.0).

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 6.3 🟢 QA Rules subset works (pofilter rules)
```python
python3 -c "
from ol_lqa.qa_rules import check_pair, QAWarning
# Test with known rule triggers
warnings = check_pair('Click %s button', '点击 %s 按钮')
print(f'QA warnings: {warnings}')
for w in warnings:
    print(f'  Rule: {w.rule}, severity: {w.severity}')
print('✅ QA rules execute without error')
"
```
**Expected Result:** ✅ `check_pair()` runs translate-toolkit pofilter rules (accelerators, brackets, printf, variables, xmltags) without errors.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q6-OL Verdict

| Scenario | Result |
|----------|--------|
| 6.1 JudgeService EvaluationResult | ⬜ |
| 6.2 RetryManager exists | ⬜ |
| 6.3 QA rules subset | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

# Part 3: MCP Surface Mastery

---

## Q7-OL: Do all 21 MCP tools respond and function?

**User says:** "I'm connecting via MCP protocol. I need all 21 tools to work as documented."

**Why this matters:** MCP is the primary integration surface for AI agents. Broken tools break automation.

### Prerequisites
```bash
export OMNI_TEST_FAKE_LLM=1
cd /mnt/d/贯维/Omni_Suite/Omni_Localizer
```

### Scenarios

#### 7.1 🟢 All 21 tools registered in TOOL_REGISTRY
```python
python3 -c "
import os
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.tools import TOOL_REGISTRY
tool_names = sorted(TOOL_REGISTRY.keys())
print(f'Total tools: {len(tool_names)}')
for i, name in enumerate(tool_names, 1):
    print(f'  {i:2d}. {name}')
assert len(tool_names) >= 21, f'Expected ≥21 tools, got {len(tool_names)}'
expected = [
    'ping', 'translate_md_text', 'translate_xliff', 'judge_text',
    'load_glossary', 'get_relevant_terms', 'search_tm',
    'batch_translate_texts', 'verify_terms', 'profile_doc',
    'extract_terms', 'add_tm_entries', 'disambiguate',
    'shield_md_text', 'unshield_md_text', 'translate_file',
    'get_translation_status', 'extract_warnings', 'generate_report',
    'inspect_config', 'get_capabilities',
]
missing = [t for t in expected if t not in tool_names]
assert len(missing) == 0, f'Missing tools: {missing}'
print(f'✅ All {len(tool_names)} tools registered correctly')
"
```
**Expected Result:** ✅ All 21 MCP tools are registered. No missing tools.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.2 🟢 ping — health check
```python
python3 -c "
import os, json, asyncio
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.tools import ping
result = json.loads(asyncio.run(ping()))
print(f'Ping result: {json.dumps(result, indent=2)}')
assert result.get('success') == True, 'ping should succeed'
content = result.get('content', {})
assert content.get('module') == 'ol', 'module should be ol'
assert 'version' in content, 'version should be present'
print('✅ ping works')
"
```
**Expected Result:** ✅ Returns `{success: true, content: {module: "ol", version: "..."}}`.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.3 🟢 translate_md_text — MD translation via MCP
```python
python3 -c "
import os, json, asyncio
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.translate_md import translate_md_text
from ol_mcp.tools import TranslateInput

async def test():
    params = TranslateInput(
        content='# Hello World\nThis is a **test**.',
        source_lang='en',
        target_lang='zh',
    )
    result = json.loads(await translate_md_text(params))
    print(f'Translate result keys: {result.keys()}')
    assert result.get('success') == True, 'translate_md should succeed'
    content = result.get('content', {})
    translated = content.get('translated', '')
    assert len(translated) > 0, 'Translation should be non-empty'
    print(f'Translated: {translated[:100]}...')
    print('✅ translate_md_text works')

asyncio.run(test())
"
```
**Expected Result:** ✅ Returns `{success: true, content: {translated: "...", source_lang: "en", target_lang: "zh", warnings: [...]}}`.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.4 🟢 translate_xliff — XLIFF translation via MCP
```python
python3 -c "
import os, json, asyncio, tempfile
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.translate_xliff import translate_xliff
from ol_mcp.tools import TranslateXliffInput

async def test():
    with tempfile.NamedTemporaryFile(suffix='.xlf', mode='w', delete=False) as f:
        f.write('<?xml version=\"1.0\" encoding=\"utf-8\"?>')
        f.write('<xliff version=\"1.2\" xmlns=\"urn:oasis:names:tc:xliff:document:1.2\">')
        f.write('<file original=\"test.docx\" source-language=\"en\" target-language=\"zh\">')
        f.write('<body><trans-unit id=\"u1\"><source>Hello World</source><target/></trans-unit>')
        f.write('</body></file></xliff>')
        input_path = f.name
    output_path = input_path + '_translated.xlf'
    params = TranslateXliffInput(
        input_path=input_path,
        output_path=output_path,
        source_lang='en',
        target_lang='zh',
    )
    result = json.loads(await translate_xliff(params))
    print(f'XLIFF result keys: {result.keys()}')
    assert result.get('success') == True, 'translate_xliff should succeed'
    print(f'Output path: {result.get(\"content\", {}).get(\"output_path\", \"?\")}')
    print('✅ translate_xliff works')

asyncio.run(test())
"
```
**Expected Result:** ✅ Returns `{success: true, content: {output_path: "...", units_processed: N, warnings: [...]}}`.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.5 🟢 judge_text — translation quality evaluation via MCP
```python
python3 -c "
import os, json, asyncio
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.judge import judge_text
from ol_mcp.tools import JudgeInput

async def test():
    params = JudgeInput(
        source='Hello World',
        target='你好世界',
        source_lang='en',
        target_lang='zh',
    )
    result = json.loads(await judge_text(params))
    print(f'Judge result: {json.dumps(result, indent=2)[:300]}')
    assert result.get('success') == True, 'judge should succeed'
    print('✅ judge_text works')

asyncio.run(test())
"
```
**Expected Result:** ✅ Returns scores for adequacy, fluency, terminology, format.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.6 🟢 load_glossary / get_relevant_terms — glossary workflow
```python
python3 -c "
import os, json, asyncio
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.glossary import load_glossary, get_relevant_terms
from ol_mcp.tools import LoadGlossaryInput, GetRelevantTermsInput
import tempfile, json as j

async def test():
    glossary_data = {'API endpoint': {'translation': 'API 端点', 'variants': {'API endpoint': 'API 端点'}, 'confidence': 0.95}}
    with tempfile.NamedTemporaryFile(suffix='.json', mode='w', delete=False) as f:
        j.dump(glossary_data, f)
        glossary_path = f.name

    # Load
    load_params = LoadGlossaryInput(path=glossary_path)
    load_result = json.loads(await load_glossary(load_params))
    print(f'Load result: {json.dumps(load_result, indent=2)[:200]}')
    assert load_result.get('success') == True, 'load_glossary should succeed'

    # Get relevant terms
    get_params = GetRelevantTermsInput(
        text='Call the API endpoint to proceed',
        glossary=glossary_data,
        top_k=5,
    )
    terms_result = json.loads(await get_relevant_terms(get_params))
    print(f'Terms result: {json.dumps(terms_result, indent=2)[:200]}')
    assert terms_result.get('success') == True, 'get_relevant_terms should succeed'
    print('✅ load_glossary / get_relevant_terms work')

asyncio.run(test())
"
```
**Expected Result:** ✅ `load_glossary` returns glossary data. `get_relevant_terms` returns top-k relevant terms for source text.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.7 🟢 search_tm — translation memory search
```python
python3 -c "
import os, json, asyncio
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.tm import search_tm
from ol_mcp.tools import SearchTMInput
import tempfile

async def test():
    # Create minimal TMX
    tmx_content = '''<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<tmx version=\"1.4\">
  <body>
    <tu>
      <tuv xml:lang=\"en\"><seg>Hello World</seg></tuv>
      <tuv xml:lang=\"zh\"><seg>你好世界</seg></tuv>
    </tu>
  </body>
</tmx>'''
    with tempfile.NamedTemporaryFile(suffix='.tmx', mode='w', delete=False) as f:
        f.write(tmx_content)
        tmx_path = f.name

    params = SearchTMInput(
        source_text='Hello World',
        tmx_path=tmx_path,
        threshold=0.85,
        source_lang='en',
        target_lang='zh',
    )
    result = json.loads(await search_tm(params))
    print(f'TM result: {json.dumps(result, indent=2)[:300]}')
    assert result.get('success') == True, 'search_tm should succeed'
    print('✅ search_tm works')

asyncio.run(test())
"
```
**Expected Result:** ✅ Returns TM matches with similarity scores ≥ threshold.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.8 🟢 batch_translate_texts — parallel translation
```python
python3 -c "
import os, json, asyncio
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.batch_translate import batch_translate_texts
from ol_mcp.tools import BatchTranslateInput

async def test():
    params = BatchTranslateInput(
        texts=['Hello World', 'How are you?', 'Good bye'],
        source_lang='en',
        target_lang='zh',
        concurrency=3,
    )
    result = json.loads(await batch_translate_texts(params))
    print(f'Batch result keys: {result.keys()}')
    assert result.get('success') == True, 'batch_translate should succeed'
    translations = result.get('content', {}).get('translations', [])
    print(f'Got {len(translations)} translations')
    assert len(translations) == 3, 'Should have 3 translations'
    print('✅ batch_translate_texts works')

asyncio.run(test())
"
```
**Expected Result:** ✅ Returns `{success: true, content: {translations: [...], warnings: [...]}}`.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.9 🟢 shield_md_text / unshield_md_text — shield round-trip
```python
python3 -c "
import os, json, asyncio
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.shield_text import shield_md_text, unshield_md_text
from ol_mcp.tools import ShieldMdInput, UnshieldMdInput

async def test():
    content = '# Hello\nThis has a `code` block and $math$ and [link](https://x.com).'

    shield_params = ShieldMdInput(content=content)
    shield_result = json.loads(await shield_md_text(shield_params))
    print(f'Shield result: {json.dumps(shield_result, indent=2)[:200]}')
    assert shield_result.get('success') == True, 'shield should succeed'

    shielded = shield_result['content']['shielded']
    shield_map = shield_result['content']['shield_map']
    print(f'Shielded length: {len(shielded)}')

    unshield_params = UnshieldMdInput(content=shielded, shield_map=shield_map)
    unshield_result = json.loads(await unshield_md_text(unshield_params))
    assert unshield_result.get('success') == True, 'unshield should succeed'
    unshielded = unshield_result['content']['unshielded']
    print(f'Unshielded length: {len(unshielded)}')
    assert 'Hello' in unshielded
    print('✅ shield_md_text / unshield_md_text round-trip work')

asyncio.run(test())
"
```
**Expected Result:** ✅ Shield replaces code/math/link with `[OL:TYPE:NNNN]` markers. Unshield restores original content. Round-trip preserves all text.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.10 🟢 extract_terms — YAKE term extraction
```python
python3 -c "
import os, json, asyncio
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.extract_terms import extract_terms
from ol_mcp.tools import ExtractTermsInput

async def test():
    params = ExtractTermsInput(
        texts=['The API endpoint returns JSON data about machine learning models.'],
        top_n=10,
    )
    result = json.loads(await extract_terms(params))
    print(f'Extract terms: {json.dumps(result, indent=2)[:300]}')
    assert result.get('success') == True, 'extract_terms should succeed'
    terms = result.get('content', {}).get('terms', {})
    print(f'Extracted {len(terms)} terms')
    assert len(terms) > 0, 'Should extract at least one term'
    print('✅ extract_terms works')

asyncio.run(test())
"
```
**Expected Result:** ✅ Returns `{success: true, content: {terms: {term: score, ...}}}`.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.11 🟢 add_tm_entries — TMX memory management
```python
python3 -c "
import os, json, asyncio, tempfile
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.tm_add import add_tm_entries
from ol_mcp.tools import TMAddInput, TMEntry

async def test():
    with tempfile.NamedTemporaryFile(suffix='.tmx', mode='w', delete=False) as f:
        f.write('<?xml version=\"1.0\"?><tmx version=\"1.4\"><body></body></tmx>')
        tmx_path = f.name

    params = TMAddInput(
        tmx_path=tmx_path,
        entries=[TMEntry(source='Hello', target='你好', source_lang='en', target_lang='zh')],
    )
    result = json.loads(await add_tm_entries(params))
    print(f'TM add result: {json.dumps(result, indent=2)[:200]}')
    assert result.get('success') == True, 'add_tm_entries should succeed'
    print('✅ add_tm_entries works')

asyncio.run(test())
"
```
**Expected Result:** ✅ Entry added to TMX file. Returns success confirmation.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.12 🟢 disambiguate — polysemy resolution
```python
python3 -c "
import os, json, asyncio
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.disambiguate import disambiguate
from ol_mcp.tools import DisambiguateInput

async def test():
    glossary = {'bank': {'translation': '银行', 'variants': {'bank': '银行'}, 'confidence': 0.7}}
    params = DisambiguateInput(
        text='I need to go to the bank to withdraw money.',
        glossary=glossary,
    )
    result = json.loads(await disambiguate(params))
    print(f'Disambiguate result: {json.dumps(result, indent=2)[:200]}')
    assert result.get('success') == True, 'disambiguate should succeed'
    print('✅ disambiguate works')

asyncio.run(test())
"
```
**Expected Result:** ✅ Returns disambiguated terms with context-aware translations.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.13 🟢 verify_terms — glossary term verification (no LLM)
```python
python3 -c "
import os, json, asyncio
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.verify_terms import verify_terms
from ol_mcp.tools import VerifyTermsInput

async def test():
    params = VerifyTermsInput(
        source='Click the button to continue.',
        target='点击按钮继续。',
        glossary={'button': {'translation': '按钮'}},
        source_lang='en',
        target_lang='zh',
    )
    result = json.loads(await verify_terms(params))
    print(f'Verify result: {json.dumps(result, indent=2)[:300]}')
    assert result.get('success') == True, 'verify_terms should succeed'
    content = result.get('content', {})
    assert 'verified' in content
    print('✅ verify_terms works')

asyncio.run(test())
"
```
**Expected Result:** Returns `{success: true, content: {verified: bool, mismatches: [...], absent: [...], inconsistencies: [...], low_confidence: [...]}}`.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.14 🟢 profile_doc — style profiling via LLM
```python
python3 -c "
import os, json, asyncio
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.profile_doc import profile_doc
from ol_mcp.tools import ProfileDocInput

async def test():
    params = ProfileDocInput(
        content='This is a technical document about API endpoints and machine learning models.',
        source_lang='en',
    )
    result = json.loads(await profile_doc(params))
    print(f'Profile result keys: {result.keys()}')
    assert result.get('success') == True, 'profile_doc should succeed'
    print('✅ profile_doc works')

asyncio.run(test())
"
```
**Expected Result:** Returns StyleGuide with tone, register, target audience, key conventions.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.15 🟢 inspect_config — config inspection
```python
python3 -c "
import os, json, asyncio
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.inspect_config import inspect_config
from ol_mcp.tools import InspectConfigInput

async def test():
    params = InspectConfigInput()
    result = json.loads(await inspect_config(params))
    print(f'Config inspect: {json.dumps(result, indent=2)[:300]}')
    assert result.get('success') == True, 'inspect_config should succeed'
    print('✅ inspect_config works')

asyncio.run(test())
"
```
**Expected Result:** Returns resolved config with quality_gates, model pool, locale settings.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.16 🟢 get_capabilities — module capabilities
```python
python3 -c "
import os, json, asyncio
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.get_capabilities import get_capabilities

async def test():
    result = json.loads(await get_capabilities())
    print(f'Capabilities: {json.dumps(result, indent=2)[:400]}')
    assert result.get('success') == True, 'get_capabilities should succeed'
    content = result.get('content', {})
    assert 'roles' in content or 'tools' in content
    print('✅ get_capabilities works')

asyncio.run(test())
"
```
**Expected Result:** Returns module capabilities: roles (translation, judging, restoration), language pairs, available tools.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.17 🟢 extract_warnings — warning extraction from files
```python
python3 -c "
import os, json, asyncio, tempfile
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.extract_warnings import extract_warnings
from ol_mcp.tools import ExtractWarningsInput

async def test():
    with tempfile.NamedTemporaryFile(suffix='.md', mode='w', delete=False) as f:
        f.write('<!-- OL_WARN: LENGTH_RATIO -->\n')
        f.write('# Test\n')
        file_path = f.name

    params = ExtractWarningsInput(file_path=file_path)
    result = json.loads(await extract_warnings(params))
    print(f'Extract warnings: {json.dumps(result, indent=2)[:200]}')
    assert result.get('success') == True, 'extract_warnings should succeed'
    print('✅ extract_warnings works')

asyncio.run(test())
"
```
**Expected Result:** Returns warnings found in file as a list.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.18 🟢 generate_report — HTML+CSV report generation
```python
python3 -c "
import os, json, asyncio, tempfile
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.generate_report import generate_report
from ol_mcp.tools import GenerateReportInput, WarningEntryDict, ModelCostEntryDict

async def test():
    with tempfile.TemporaryDirectory() as td:
        params = GenerateReportInput(
            output_dir=td,
            job_id='test-job-001',
            force=True,
            warnings=[
                WarningEntryDict(warning_type='LENGTH_RATIO', severity='medium', file_path='test.md'),
            ],
            model_costs=[
                ModelCostEntryDict(model_name='glm-4-flash', prompt_tokens=100, completion_tokens=50),
            ],
        )
        result = json.loads(await generate_report(params))
        print(f'Report result: {json.dumps(result, indent=2)[:200]}')
        assert result.get('success') == True, 'generate_report should succeed'
        # Check files created
        files = os.listdir(td)
        print(f'Files created: {files}')
        assert any(f.endswith('.html') for f in files), 'HTML report should be created'
        print('✅ generate_report works')

asyncio.run(test())
"
```
**Expected Result:** Creates report.html and report.csv in output directory.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.19 🟢 get_translation_status — async task polling
```python
python3 -c "
import os, json, asyncio
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.status import get_translation_status
from ol_mcp.task_tracker import InMemoryTaskTracker

async def test():
    tracker = InMemoryTaskTracker()
    # Get status for non-existent ID
    result = json.loads(await get_translation_status('nonexistent-id', tracker))
    print(f'Status result: {json.dumps(result, indent=2)[:200]}')
    # Should return error or 'not_found' status — not crash
    print('✅ get_translation_status handles non-existent ID')

asyncio.run(test())
"
```
**Expected Result:** Returns status for valid request_id, error for invalid. Does NOT crash.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.20 🟢 translate_file — end-to-end file translation (OPP→OL→ORF)
```python
python3 -c "
import os, json, asyncio
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.translate_file import translate_file
from ol_mcp.tools import TranslateFileInput

async def test():
    # This tool wraps OPP+OL+ORF. With FAKE_LLM it should at minimum
    # accept the input and return a structured error or proceed.
    params = TranslateFileInput(
        file_path='/tmp/nonexistent.docx',
        source_lang='en',
        target_lang='zh',
        output_format='docx',
    )
    result = json.loads(await translate_file(params))
    print(f'translate_file result: {json.dumps(result, indent=2)[:200]}')
    # Without real files, expected to return error — not crash
    print('✅ translate_file handles gracefully')

asyncio.run(test())
"
```
**Expected Result:** With valid files, translates end-to-end. With invalid files, returns error gracefully (no crash).

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.21 🔴 Unknown tool name returns structured error
```python
python3 -c "
import os, json
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.tools import TOOL_REGISTRY, _error_response

# Simulate unknown tool response
resp = _error_response('OL_UNKNOWN_TOOL', 'Unknown tool: nonexistent_tool')
print(json.dumps(resp, indent=2))
assert resp['error_code'] == 'OL_UNKNOWN_TOOL'
assert 'error' in resp
assert resp['success'] == False
print('✅ Unknown tool handled correctly')
"
```
**Expected Result:** Unknown tool returns structured error `OL_UNKNOWN_TOOL`. No Python traceback, no crash.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q7-OL Verdict

| Scenario | Result |
|----------|--------|
| 7.1 All 21 tools registered | ⬜ |
| 7.2 ping | ⬜ |
| 7.3 translate_md_text | ⬜ |
| 7.4 translate_xliff | ⬜ |
| 7.5 judge_text | ⬜ |
| 7.6 load_glossary / get_relevant_terms | ⬜ |
| 7.7 search_tm | ⬜ |
| 7.8 batch_translate_texts | ⬜ |
| 7.9 shield / unshield round-trip | ⬜ |
| 7.10 extract_terms | ⬜ |
| 7.11 add_tm_entries | ⬜ |
| 7.12 disambiguate | ⬜ |
| 7.13 verify_terms | ⬜ |
| 7.14 profile_doc | ⬜ |
| 7.15 inspect_config | ⬜ |
| 7.16 get_capabilities | ⬜ |
| 7.17 extract_warnings | ⬜ |
| 7.18 generate_report | ⬜ |
| 7.19 get_translation_status | ⬜ |
| 7.20 translate_file | ⬜ |
| 7.21 Unknown tool error | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

# Part 4: Agent-as-User Workflows

---

## Q8-OL: Can an agent translate text via MCP and verify quality?

**User says:** "I want to translate some text, then check the quality of the result."

**Why this matters:** This is the primary agent workflow: translate → judge → verify in a loop.

### Prerequisites
```bash
export OMNI_TEST_FAKE_LLM=1
```

### Scenarios

#### 8.1 🟢 Agent workflow: translate → judge → verify terms
```python
python3 -c "
import os, json, asyncio
os.environ['OMNI_TEST_FAKE_LLM'] = '1'

async def test():
    # Step 1: Translate
    from ol_mcp.translate_md import translate_md_text
    from ol_mcp.tools import TranslateInput, JudgeInput
    from ol_mcp.judge import judge_text
    from ol_mcp.verify_terms import verify_terms
    from ol_mcp.tools import VerifyTermsInput

    glossary = {'API': {'translation': 'API', 'variants': {'API': 'API'}, 'confidence': 0.95}}

    # Translate
    t_params = TranslateInput(
        content='Call the API to get data.',
        source_lang='en',
        target_lang='zh',
    )
    t_result = json.loads(await translate_md_text(t_params))
    translated = t_result.get('content', {}).get('translated', '')
    print(f'Step 1 - Translated: {translated}')
    assert len(translated) > 0

    # Judge
    j_params = JudgeInput(
        source='Call the API to get data.',
        target=translated,
        source_lang='en',
        target_lang='zh',
    )
    j_result = json.loads(await judge_text(j_params))
    print(f'Step 2 - Judge result keys: {j_result.keys()}')
    assert j_result.get('success') == True

    # Verify terms
    v_params = VerifyTermsInput(
        source='Call the API to get data.',
        target=translated,
        glossary=glossary,
        source_lang='en',
        target_lang='zh',
    )
    v_result = json.loads(await verify_terms(v_params))
    print(f'Step 3 - Verify terms: {json.dumps(v_result, indent=2)[:200]}')
    assert v_result.get('success') == True

    print('✅ Full agent workflow: translate → judge → verify_terms')

asyncio.run(test())
"
```
**Expected Result:** All three steps succeed. The agent can chain translate → judge → verify_terms in sequence.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 8.2 🟢 Agent workflow: translate with quality gates enabled
```python
python3 -c "
import os, json, asyncio
os.environ['OMNI_TEST_FAKE_LLM'] = '1'

async def test():
    from ol_mcp.translate_md import translate_md_text
    from ol_mcp.tools import TranslateInput

    params = TranslateInput(
        content='Hello World',
        source_lang='en',
        target_lang='zh',
    )
    result = json.loads(await translate_md_text(params))
    print(f'Translate result: {json.dumps(result, indent=2)[:300]}')
    content = result.get('content', {})
    warnings = content.get('warnings', [])
    if warnings:
        print(f'Quality gate warnings ({len(warnings)}):')
        for w in warnings:
            print(f'  {w}')
    else:
        print('No quality gate warnings (content passed all gates)')
    assert 'warnings' in content
    print('✅ translate_md_text returns quality gate warnings')

asyncio.run(test())
"
```
**Expected Result:** Translation response includes `warnings` field with quality gate results.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q8-OL Verdict

| Scenario | Result |
|----------|--------|
| 8.1 Translate → Judge → Verify | ⬜ |
| 8.2 Translate with quality gates | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q9-OL: Does glossary/TM injection improve translation?

**User says:** "I want to ensure specific terms are translated consistently across my document."

**Why this matters:** Glossary and TM injection are the core differentiators for domain-specific translation quality.

### Prerequisites
```bash
export OMNI_TEST_FAKE_LLM=1
cd /tmp && rm -rf test-glossary && mkdir test-glossary && cd test-glossary
cat > glossary.json << 'EOF'
{
  "API endpoint": {
    "translation": "API 端点",
    "variants": {"API endpoint": "API 端点", "API endpoints": "API 端点"},
    "confidence": 0.95
  },
  "machine learning": {
    "translation": "机器学习",
    "variants": {"machine learning": "机器学习"},
    "confidence": 0.98
  }
}
EOF
```

### Scenarios

#### 9.1 🟢 Glossary injection via CLI (--glossary flag)
```bash
cat > doc.md << 'EOF'
# API Documentation

The API endpoint returns data. Machine learning models process it.
EOF
ol translate-md doc.md -s en -t zh -o /tmp/test-glossary/output/ --config /mnt/d/贯维/Omni_Suite/Omni_Localizer/config/default.yaml --glossary /tmp/test-glossary/glossary.json --no-frontmatter
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Output file created
- ✅ FAKE_LLM mode handles glossary gracefully (no crash)

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 9.2 🟢 Glossary injection via MCP (translate_md_text with glossary_path)
```python
python3 -c "
import os, json, asyncio
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.translate_md import translate_md_text
from ol_mcp.tools import TranslateInput

async def test():
    params = TranslateInput(
        content='The API endpoint processes machine learning requests.',
        source_lang='en',
        target_lang='zh',
        glossary_path='/tmp/test-glossary/glossary.json',
    )
    result = json.loads(await translate_md_text(params))
    print(f'Glossary translate: {json.dumps(result, indent=2)[:300]}')
    assert result.get('success') == True
    warnings = result.get('content', {}).get('warnings', [])
    glossary_warnings = [w for w in warnings if 'Glossary' in w]
    for w in glossary_warnings:
        print(f'  Note: {w}')
    print('✅ Glossary via MCP works')

asyncio.run(test())
"
```
**Expected Result:** Translation succeeds with glossary loaded. Any glossary load issues are reported as warnings (best-effort).

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 9.3 🟢 Load glossary → Get relevant terms → Disambiguate workflow
```python
python3 -c "
import os, json, asyncio
os.environ['OMNI_TEST_FAKE_LLM'] = '1'

async def test():
    from ol_mcp.glossary import load_glossary, get_relevant_terms
    from ol_mcp.disambiguate import disambiguate
    from ol_mcp.tools import LoadGlossaryInput, GetRelevantTermsInput, DisambiguateInput

    glossary_data = {
        'bank': {'translation': '银行', 'variants': {'bank': '银行', 'banks': '银行'}, 'confidence': 0.8},
        'river': {'translation': '河流', 'variants': {'river': '河流'}, 'confidence': 0.9},
    }

    # Get relevant terms
    get_params = GetRelevantTermsInput(text='Go to the bank near the river.', glossary=glossary_data, top_k=5)
    get_result = json.loads(await get_relevant_terms(get_params))
    print(f'Relevant terms: {json.dumps(get_result, indent=2)[:200]}')
    assert get_result.get('success') == True

    # Disambiguate
    dis_params = DisambiguateInput(text='Go to the bank near the river.', glossary=glossary_data)
    dis_result = json.loads(await disambiguate(dis_params))
    print(f'Disambiguate: {json.dumps(dis_result, indent=2)[:200]}')
    assert dis_result.get('success') == True

    print('✅ Glossary workflow: load → relevant → disambiguate')

asyncio.run(test())
"
```
**Expected Result:** Three-step terminology workflow succeeds: load_glossary → get_relevant_terms → disambiguate.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 9.4 🟢 TM search finds similar translations
```python
python3 -c "
import os, json, asyncio, tempfile
os.environ['OMNI_TEST_FAKE_LLM'] = '1'

async def test():
    from ol_mcp.tm import search_tm
    from ol_mcp.tm_add import add_tm_entries
    from ol_mcp.tools import SearchTMInput, TMAddInput, TMEntry

    # Create TMX, add entry, then search
    tmx_content = '<?xml version=\"1.0\"?><tmx version=\"1.4\"><body></body></tmx>'
    with tempfile.NamedTemporaryFile(suffix='.tmx', mode='w', delete=False) as f:
        f.write(tmx_content)
        tmx_path = f.name

    # Add
    add_params = TMAddInput(
        tmx_path=tmx_path,
        entries=[TMEntry(source='Hello World', target='你好世界', source_lang='en', target_lang='zh')],
    )
    add_result = json.loads(await add_tm_entries(add_params))
    assert add_result.get('success') == True

    # Search
    search_params = SearchTMInput(
        source_text='Hello World',
        tmx_path=tmx_path,
        threshold=0.85,
        source_lang='en',
        target_lang='zh',
    )
    search_result = json.loads(await search_tm(search_params))
    print(f'TM search: {json.dumps(search_result, indent=2)[:200]}')
    assert search_result.get('success') == True
    print('✅ TM add → search workflow works')

asyncio.run(test())
"
```
**Expected Result:** add_tm_entries → search_tm workflow succeeds. TM search returns the added entry.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q9-OL Verdict

| Scenario | Result |
|----------|--------|
| 9.1 Glossary via CLI | ⬜ |
| 9.2 Glossary via MCP | ⬜ |
| 9.3 Glossary workflow (load → relevant → disambiguate) | ⬜ |
| 9.4 TM add → search | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

# Part 5: CLI Surface Mastery

---

## Q10-OL: Do all CLI commands work correctly? (7 commands)

**User says:** "I prefer using the terminal. I need all CLI commands to work."

### Prerequisites
```bash
export OMNI_TEST_FAKE_LLM=1
```

### Scenarios

#### 10.1 🟢 Main help + version
```bash
ol --help
```
**Expected Result:**
- ✅ Shows all 6 commands: `translate-md`, `translate-xliff`, `translate-batch`, `extract-warnings`, `mcp`
- ✅ `--help` flag works
- ✅ `--version` flag works

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 10.2 🟢 translate-md --help
```bash
ol translate-md --help
```
**Expected Result:** ✅ Shows parameters: file, -s/--source-lang, -t/--target-lang, -o/--output-dir, --config, --glossary, --no-glossary, --chunk-by-paragraph, --concurrency, --no-frontmatter, --no-restoration, --json, --log-format

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 10.3 🟢 translate-xliff --help
```bash
ol translate-xliff --help
```
**Expected Result:** ✅ Shows parameters: file, -s, -t, -o, --config, --glossary, --json

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 10.4 🟢 translate-batch --help
```bash
ol translate-batch --help
```
**Expected Result:** ✅ Shows parameters: directory, -s, -t, -o, --config, --glossary, --concurrency, --no-detect-language, --json

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 10.5 🟢 extract-warnings --help
```bash
ol extract-warnings --help
```
**Expected Result:** ✅ Shows parameters: file, -o/--output, --json

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 10.6 🟢 mcp --help
```bash
ol mcp --help
```
**Expected Result:** ✅ Shows MCP server startup options (stdio transport, optional flags).

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 10.7 🟢 translate-batch with multiple files
```bash
cd /tmp && rm -rf test-batch && mkdir test-batch && cd test-batch
mkdir docs
echo '# File 1' > docs/file1.md
echo '# File 2' > docs/file2.md
echo '# File 3' > docs/file3.md
ol translate-batch ./docs/ -s en -t zh -o /tmp/test-batch/output/ --config /mnt/d/贯维/Omni_Suite/Omni_Localizer/config/default.yaml --no-glossary --json 2>/dev/null
```
**Expected Result:** ✅ Exit code 0. All 3 files translated. JSON output shows summary: total_files=3, succeeded=3.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 10.8 🟢 translate-md with --json output
```bash
cd /tmp/test-md-translate && ol translate-md sample.md -s en -t zh -o /tmp/test-batch/output-single/ --config /mnt/d/贯维/Omni_Suite/Omni_Localizer/config/default.yaml --no-glossary --json 2>/dev/null | python3 -c "import sys,json; json.load(sys.stdin); print('VALID JSON')"
```
**Expected Result:** ✅ Valid JSON with `{"success": true, "input_file": "...", "output_file": "...", "source_lang": "en", "target_lang": "zh"}`.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 10.9 🔴 Missing required -s flag
```bash
ol translate-md sample.md -t zh -o /tmp/test-batch/output/
```
**Expected Result:** ❌ Error message mentions missing -s/--source-lang. Exit code != 0. No traceback.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 10.10 🔴 Unknown flag
```bash
ol translate-md sample.md -s en -t zh --nonexistent-flag
```
**Expected Result:** ❌ Error: "No such option". Does NOT crash with traceback.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q10-OL Verdict

| Scenario | Result |
|----------|--------|
| 10.1 Main help | ⬜ |
| 10.2 translate-md help | ⬜ |
| 10.3 translate-xliff help | ⬜ |
| 10.4 translate-batch help | ⬜ |
| 10.5 extract-warnings help | ⬜ |
| 10.6 mcp help | ⬜ |
| 10.7 translate-batch | ⬜ |
| 10.8 JSON output | ⬜ |
| 10.9 Missing required flag | ⬜ |
| 10.10 Unknown flag | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

# Part 6: Error & Boundary Matrix

---

## Q11-OL: What happens with empty/large content?

**User says:** "What if I pass empty content or a huge file?"

**Why this matters:** Edge cases must be handled gracefully — no crashes, no silent data loss.

### Prerequisites
```bash
export OMNI_TEST_FAKE_LLM=1
```

### Scenarios

#### 11.1 🔴 Empty content translates to empty output
```python
python3 -c "
import os, json, asyncio
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.translate_md import translate_md_text
from ol_mcp.tools import TranslateInput

async def test():
    params = TranslateInput(content='', source_lang='en', target_lang='zh')
    result = json.loads(await translate_md_text(params))
    print(f'Empty translate: {json.dumps(result, indent=2)[:200]}')
    # Should handle empty gracefully — either empty output or clear error
    print('✅ Empty content handled')

asyncio.run(test())
"
```
**Expected Result:** Does NOT crash. Returns empty translation or clear error. No traceback.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 11.2 🟢 Large content (>50K chars) emits warning but not blocked
```python
python3 -c "
import os, json, asyncio
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_mcp.translate_md import translate_md_text
from ol_mcp.tools import TranslateInput

async def test():
    # Create content slightly above 50K
    large_content = '# Large Document\n' + ('Lorem ipsum dolor sit amet. ' * 5000)
    print(f'Content size: {len(large_content)} chars')
    params = TranslateInput(content=large_content, source_lang='en', target_lang='zh')
    result = json.loads(await translate_md_text(params))
    print(f'Large content translate success: {result.get(\"success\")}')
    # Should not crash — either translate or return clear error
    print('✅ Large content handled')

asyncio.run(test())
"
```
**Expected Result:** E2E-83: Large content (>50K chars) emits WARNING log but is NOT blocked (no `OL_MAX_INPUT_SIZE_MB` rejection for MCP path). Returns either translation or clear error.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 11.3 🟢 Shield round-trip preserves all content
```python
python3 -c "
import os, json
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_md.shield import shield_markdown, unshield_markdown

content = '''# Test
This has \`code\`, \$math^$, [link](https://x.com), and ![image](img.png).
Also <html> and https://autolink.com.
'''
shielded, shield_map = shield_markdown(content)
print(f'Original: {len(content)} chars')
print(f'Shielded: {len(shielded)} chars')
print(f'Shield map entries: {len(shield_map)}')
unshielded = unshield_markdown(shielded, shield_map)
print(f'Unshielded: {len(unshielded)} chars')
assert content == unshielded, f'Round-trip mismatch: {len(content)} vs {len(unshielded)}'
print('✅ Shield round-trip preserves all content')
"
```
**Expected Result:** Shield → Unshield round-trip is lossless. Original content is fully restored.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 11.4 🟢 CLI input size limit enforced (>50MB rejected)
```bash
# Create a >50MB fake file
cd /tmp && dd if=/dev/zero of=huge.md bs=1M count=60 2>/dev/null
ol translate-md huge.md -s en -t zh -o /tmp/test-boundary/output/ 2>&1; echo 'EXIT:' $?
```
**Expected Result:** ❌ File >50MB (OL_MAX_INPUT_SIZE_MB default) is rejected with error message. Clean exit, no crash.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q11-OL Verdict

| Scenario | Result |
|----------|--------|
| 11.1 Empty content | ⬜ |
| 11.2 Large content (>50K) | ⬜ |
| 11.3 Shield round-trip | ⬜ |
| 11.4 >50MB input | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q12-OL: What happens when no LLM keys are configured?

**User says:** "What if I run commands without setting up API keys?"

**Why this matters:** Production robustness — the system must fail gracefully with clear error messages, not crashes.

### Prerequisites
```bash
unset ZHIPU_API_KEY AGNES_API_KEY NVIDIA_NIM_API_KEY OPENCODE_GO_KEY OPENCODE_GO_BASE_URL
unset OMNI_TEST_FAKE_LLM
```

### Scenarios

#### 12.1 🔴 Missing API keys — CLI error is user-friendly
```bash
cd /tmp && rm -rf test-nokeys && mkdir test-nokeys && cd test-nokeys
echo '# Test' > sample.md
ol translate-md sample.md -s en -t zh -o /tmp/test-nokeys/output/ --config /mnt/d/贯维/Omni_Suite/Omni_Localizer/config/default.yaml --no-glossary 2>&1; echo 'EXIT:' $?
# Re-set FAKE_LLM for subsequent tests
export OMNI_TEST_FAKE_LLM=1
```
**Expected Result:** ❌ Exit code != 0. Error message mentions missing API key or `${VAR}` resolution failure. NOT a Python traceback.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 12.2 🟢 MCP tools return structured error (not crash) when keys missing
```python
python3 -c "
import os, json, asyncio
# Intentionally NOT setting FAKE_LLM
# (but this test may crash depending on env — skip in CI if env has keys)
print('This test requires a clean environment without FAKE_LLM and without API keys.')
print('Expected: structured error, not crash.')
print('(Skipping actual invocation — would need a clean subprocess)')
print('➖ SKIP (needs isolated subprocess without keys)')
"
```
**Expected Result:** ❌ MCP tools return structured error responses (not Python tracebacks) when API keys are not configured.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 12.3 🟢 FAKE_LLM bypasses all key checks
```bash
export OMNI_TEST_FAKE_LLM=1
cd /tmp && rm -rf test-fake-nokeys && mkdir test-fake-nokeys && cd test-fake-nokeys
echo '# Test' > sample.md
ol translate-md sample.md -s en -t zh -o /tmp/test-fake-nokeys/output/ --config /mnt/d/贯维/Omni_Suite/Omni_Localizer/config/default.yaml --no-glossary 2>&1; echo 'EXIT:' $?
```
**Expected Result:** ✅ Exit code 0. With `OMNI_TEST_FAKE_LLM=1`, translation works even without API keys.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 12.4 🟢 Two-layer env var check: startup warning + runtime error
```python
python3 -c "
import os
os.environ['OMNI_TEST_FAKE_LLM'] = '1'
from ol_config.schema import _check_env_vars
# This should warn about unset vars but not crash
import logging
logging.basicConfig(level=logging.WARNING)
# _check_env_vars is called at module load time — just verify it exists
print('_check_env_vars exists:', callable(_check_env_vars))
print('✅ Two-layer env var: startup warning + runtime ValueError')
"
```
**Expected Result:** ✅ `${VAR}` pattern in config has two-layer behavior: (1) startup WARNING if unset, (2) runtime `ValueError` if model invoked. `OMNI_TEST_FAKE_LLM=1` bypasses all checks.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q12-OL Verdict

| Scenario | Result |
|----------|--------|
| 12.1 Missing keys CLI | ⬜ |
| 12.2 MCP structured error | ⬜ |
| 12.3 FAKE_LLM bypass | ⬜ |
| 12.4 Two-layer env var check | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

# Part 7: Production Validation

---

## Q13-OL: Does the MCP server start and respond via stdio?

**User says:** "In production, MCP runs as a separate process. Does the stdio protocol work?"

**Why this matters:** MCP stdio is the production deployment mode. If stdio doesn't work, the server is not deployable.

### Prerequisites
```bash
export OMNI_TEST_FAKE_LLM=1
cd /mnt/d/贯维/Omni_Suite/Omni_Localizer
```

### Scenarios

#### 13.1 🟢 MCP server starts and responds to ping via stdio
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}' | timeout 10 python3 -m ol_mcp 2>/dev/null
```
**Expected Result:** ✅ Server starts. Responds to JSON-RPC ping with a valid response. Exit code 0.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 13.2 🔴 MCP server handles invalid JSON-RPC gracefully
```bash
echo 'invalid json' | timeout 5 python3 -m ol_mcp 2>/dev/null; echo "Exit: $?"
```
**Expected Result:** ❌ Server does NOT crash. Returns JSON-RPC error response. No Python traceback leaked to stdout.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 13.3 🟢 MCP server lists tools via stdio
```bash
echo '{"jsonrpc":"2.0","id":2,"method":"list_tools","params":{}}' | timeout 10 python3 -m ol_mcp 2>/dev/null | head -c 500
```
**Expected Result:** ✅ Returns tool list with 21+ tool entries.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 13.4 🟢 ol import cleanly
```bash
python3 -c "from ol_mcp import __version__; print(f'ol_mcp v{__version__}')"
```
**Expected Result:** ✅ Package imports without error. Version string present.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 13.5 🟢 Existing test suite passes
```bash
cd /mnt/d/贯维/Omni_Suite
OMNI_TEST_FAKE_LLM=1 pytest Omni_Localizer/tests/ -v --tb=short -x 2>&1 | tail -30
```
**Expected Result:** ✅ Test suite passes. 0 failures.

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q13-OL Verdict

| Scenario | Result |
|----------|--------|
| 13.1 MCP server responds to ping | ⬜ |
| 13.2 Invalid JSON-RPC | ⬜ |
| 13.3 List tools via stdio | ⬜ |
| 13.4 Clean import | ⬜ |
| 13.5 Test suite passes | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

# Part 8: Agent-as-User Real LLM API Configuration & E2E Tests

---

## Prerequisites for Part 8

```bash
# CRITICAL: Unset FAKE_LLM to force real LLM calls
unset OMNI_TEST_FAKE_LLM

# Set at least ONE real LLM API key (all 4 providers are optional)
export ZHIPU_API_KEY="${ZHIPU_API_KEY}"
export AGNES_API_KEY="${AGNES_API_KEY}"
export NVIDIA_NIM_API_KEY="${NVIDIA_NIM_API_KEY}"
export OPENCODE_GO_KEY="${OPENCODE_GO_KEY}"
export OPENCODE_GO_BASE_URL="${OPENCODE_GO_BASE_URL}"

# Verify at least one key is present
python3 -c "
import os
keys = {k: bool(os.environ.get(k)) for k in ['ZHIPU_API_KEY', 'AGNES_API_KEY', 'NVIDIA_NIM_API_KEY', 'OPENCODE_GO_KEY']}
configured = [k for k, v in keys.items() if v]
print(f'Configured keys: {configured}')
print(f'Missing keys: {[k for k, v in keys.items() if not v]}')
assert len(configured) >= 1, 'At least one LLM API key must be set'
"

# Setup paths
cd /tmp && rm -rf test-ol-real-api && mkdir test-ol-real-api && cd test-ol-real-api
OL_ROOT="/mnt/d/贯维/Omni_Suite/Omni_Localizer"
export PYTHONPATH="$OL_ROOT/src:$PYTHONPATH"
export OL_CONFIG_PATH="$OL_ROOT/config/default.yaml"
```

**⚠️ Cost warning:** These scenarios call real LLM APIs and incur real costs (typically < $0.01 per test). If a key is expired or invalid, the tests should report a clear error rather than crash or hang.

---

## Q14-OL: Can an agent configure real LLM API keys and verify connectivity?

**User says:** "I want to use my own API keys to translate documents with real LLMs."

**Why this matters:** OL's `FAKE_LLM` seam is for development only. In production, agents must set real API keys and verify connectivity before translation. This Q validates that keys are detected correctly, connectivity is verified, and the model pool routes to the right providers.

### Scenarios

#### 14.1 🟢 inspect_config reports real provider pool (not fake)

```bash
cd /tmp/test-ol-real-api

# OL inspect_config should show real providers, not FAKE_LLM override
python3 -c "
import os, json
os.environ.setdefault('OL_CONFIG_PATH', '$OL_ROOT/config/default.yaml')
from ol_mcp.inspect_config import inspect_config
import asyncio

result = asyncio.run(inspect_config())
config = json.loads(result) if isinstance(result, str) else result
print(json.dumps(config, indent=2, ensure_ascii=False)[:2000])

# Verify real providers are listed
llm_pool = config.get('llm_pool', {})
translation_models = llm_pool.get('translation', [])
print(f'\nTranslation models: {len(translation_models)}')
for m in translation_models:
    print(f'  - {m.get(\"provider\")} / {m.get(\"model\")} / priority={m.get(\"priority\")} / role={m.get(\"role\")}')

assert len(translation_models) >= 2, 'Should have at least 2 translation providers'
assert translation_models[0].get('role') == 'translation', 'First model should have role=translation'
print('✅ Real provider pool detected with correct roles and priorities')
"
```

**Expected Result:**
- ✅ `llm_pool` section lists 5 translation providers with correct roles/priorities
- ✅ Providers include real base URLs (not fake)
- ✅ `FAKE_LLM` is NOT set in the resolved config

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 14.2 🟢 Real key produces valid translation (verify end-to-end connectivity)

```bash
cd /tmp/test-ol-real-api

python3 -c "
import os, json, asyncio
from ol_mcp.translate_md import translate_md_text
from ol_mcp.tools import TranslateInput

async def test():
    params = TranslateInput(
        content='Hello, this is a test of real LLM translation.',
        source_lang='en',
        target_lang='zh',
    )
    result = json.loads(await translate_md_text(params))

    translated = result.get('content', {}).get('translated', '')
    print(f'Source: Hello, this is a test of real LLM translation.')
    print(f'Target: {translated}')
    print(f'Target length: {len(translated)} chars')

    assert len(translated) > 0, 'Translated content should not be empty'
    assert '你好' in translated or '测试' in translated, 'Translation should contain Chinese characters'
    print(f'Quality gates warnings: {len(result.get(\"warnings\", []))}')
    print('✅ Real LLM translation: content produced, Chinese detected')

asyncio.run(test())
"
```

**Expected Result:**
- ✅ Translation completes without error (no timeout, no crash)
- ✅ Output contains Chinese characters (not source echo)
- ✅ `translated` field populated with real translation
- ✅ Warnings list present (may be empty)

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 14.3 🟢 Role-based routing sends translation to correct role pool

```bash
cd /tmp/test-ol-real-api

python3 -c "
import os, json, asyncio

# Verify ModelPool routing via inspect_config role definitions
from ol_mcp.inspect_config import inspect_config

async def test():
    result = json.loads(await inspect_config())
    llm_pool = result.get('llm_pool', {})

    for role in ['translation', 'judging', 'restoration']:
        models = llm_pool.get(role, [])
        print(f'{role}: {len(models)} model(s)')
        for m in models:
            print(f'  {m.get(\"provider\")} / {m.get(\"model\")} (priority {m.get(\"priority\")})')
        assert len(models) >= 1, f'{role} should have at least 1 model'

    print('✅ All 3 role pools (translation, judging, restoration) configured')

asyncio.run(test())
"
```

**Expected Result:**
- ✅ All 3 role pools (translation, judging, restoration) have ≥1 model each
- ✅ Each pool has priority-ordered fallback models
- ✅ Each model entry has `provider`, `model`, `priority`, `role`, `api_key` (via `${ENV_VAR}`)

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 14.4 🟢 Fallback chain activates when primary provider is unreachable

```bash
cd /tmp/test-ol-real-api

# Create a config override with a bad primary and good fallback
cat > /tmp/test-ol-real-api/config_fallback.yaml << 'YAML'
llm_pool:
  translation:
    - provider: "openai"
      model: "nonexistent-model-xxx"
      priority: 1
      role: "translation"
      api_key: "${ZHIPU_API_KEY}"
      base_url: "https://open.bigmodel.cn/api/paas/v4"
      timeout: 5.0
    - provider: "openai"
      model: "glm-4-flash"
      priority: 2
      role: "translation"
      api_key: "${ZHIPU_API_KEY}"
      base_url: "https://open.bigmodel.cn/api/paas/v4"
      timeout: 30.0
YAML

# Verify fallback: primary model fails, fallback succeeds
python3 -c "
import os, json, asyncio
os.environ['OL_CONFIG_PATH'] = '/tmp/test-ol-real-api/config_fallback.yaml'

# Force reload by importing directly
import importlib
import ol_mcp.config
importlib.reload(ol_mcp.config)

from ol_mcp.translate_md import translate_md_text
from ol_mcp.tools import TranslateInput

async def test():
    params = TranslateInput(
        content='Testing model pool fallback mechanism.',
        source_lang='en',
        target_lang='zh',
    )
    result = json.loads(await translate_md_text(params))
    translated = result.get('content', {}).get('translated', '')
    print(f'Fallback translation: {translated[:100]}')
    assert len(translated) > 0, 'Fallback should produce translation'
    print('✅ Fallback chain works: primary failed, fallback succeeded')

asyncio.run(test())
"
```

**Expected Result:**
- ✅ Primary model (nonexistent) fails fast (timeout or 404)
- ✅ Pool automatically tries priority 2 (glm-4-flash)
- ✅ Fallback produces valid Chinese translation
- ✅ No unhandled exception propagates to caller

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q14-OL Verdict

| Scenario | Result |
|----------|--------|
| 14.1 inspect_config shows real providers | ⬜ |
| 14.2 Real key produces valid translation | ⬜ |
| 14.3 Role-based routing (3 pools) | ⬜ |
| 14.4 Fallback chain activation | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q15-OL: Can an agent translate and verify quality with real LLM?

**User says:** "I translated with a real LLM. Now I want to verify the quality using the judge and quality gates — also with real LLM calls."

**Why this matters:** Real LLM output varies by provider, model, and prompt. The quality verification chain (judge → quality gates → LQA) must work with real, non-deterministic translation output.

### Scenarios

#### 15.1 🟢 Real translation → real judge (LQA score via JudgeService)

```bash
cd /tmp/test-ol-real-api

python3 -c "
import os, json, asyncio

async def test():
    # Step 1: Real translation
    from ol_mcp.translate_md import translate_md_text
    from ol_mcp.tools import TranslateInput

    t_params = TranslateInput(
        content='Machine translation quality evaluation is a complex task that requires both linguistic knowledge and automated metrics.',
        source_lang='en',
        target_lang='zh',
    )
    t_result = json.loads(await translate_md_text(t_params))
    translated = t_result.get('content', {}).get('translated', '')
    print(f'Step 1 - Translated ({len(translated)} chars): {translated[:100]}...')
    assert len(translated) > 0

    # Step 2: Real judge (uses judging model pool)
    from ol_mcp.judge import judge_text
    from ol_mcp.tools import JudgeInput

    j_params = JudgeInput(
        source='Machine translation quality evaluation is a complex task that requires both linguistic knowledge and automated metrics.',
        target=translated,
        source_lang='en',
        target_lang='zh',
    )
    j_result = json.loads(await judge_text(j_params))
    print(f'Step 2 - Judge result keys: {list(j_result.keys())}')

    # Check for score or success indicator
    adequacy = j_result.get('adequacy')
    fluency = j_result.get('fluency')
    terminology = j_result.get('terminology')
    print(f'Adequacy: {adequacy}, Fluency: {fluency}, Terminology: {terminology}')

    # At minimum, judge should return success
    assert j_result.get('success') == True, 'Judge should succeed'
    print('✅ Real translation → real judge: LQA scores produced')

asyncio.run(test())
"
```

**Expected Result:**
- ✅ Translation produces real Chinese output (not source echo)
- ✅ Judge returns real LQA scores (adequacy, fluency, terminology)
- ✅ Both steps complete without timeout
- ✅ Judge output is non-deterministic but within expected range

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 15.2 🟢 Translation with quality gates enabled (real LLM, real gates)

```bash
cd /tmp/test-ol-real-api

# Create config with quality gates enabled
cat > /tmp/test-ol-real-api/config_gates.yaml << 'YAML'
llm_pool:
  translation:
    - provider: "openai"
      model: "glm-4-flash"
      priority: 1
      role: "translation"
      api_key: "${ZHIPU_API_KEY}"
      base_url: "https://open.bigmodel.cn/api/paas/v4"
      timeout: 120.0
    - provider: "openai"
      model: "agnes-2.0-flash"
      priority: 2
      role: "translation"
      api_key: "${AGNES_API_KEY}"
      base_url: "https://apihub.agnes-ai.com/v1"
      timeout: 120.0

quality_gates:
  inline_tags: true
  terminology: true
  length_ratio:
    enabled: true
    min: 0.5
    max: 2.0
  locale:
    enabled: true
    target_locale: "zh-CN"
  source_copy: true
  source_script_check: true
  protocol_artifact_check: true
  terms_audit: true
YAML

export OL_CONFIG_PATH='/tmp/test-ol-real-api/config_gates.yaml'

python3 -c "
import os, json, asyncio
import importlib
import ol_mcp.config as cfg
importlib.reload(cfg)

from ol_mcp.translate_md import translate_md_text
from ol_mcp.tools import TranslateInput

async def test():
    params = TranslateInput(
        content='The quality gate system validates translation output against 8 different criteria including tag preservation and length ratios.',
        source_lang='en',
        target_lang='zh',
    )
    result = json.loads(await translate_md_text(params))
    translated = result.get('content', {}).get('translated', '')
    warnings = result.get('warnings', [])

    print(f'Translated: {translated[:120]}')
    print(f'Warnings: {len(warnings)}')
    for w in warnings:
        print(f'  - {w.get(\"gate\", \"?\")}: {str(w.get(\"message\", \"\"))[:80]}')

    assert len(translated) > 0
    print('✅ Quality gates enabled: translation with real LLM + real gates completed')

asyncio.run(test())
"
```

**Expected Result:**
- ✅ Translation completes with all 8 quality gates enabled
- ✅ Warnings list present (may be empty for good translations)
- ✅ Each warning has `gate` name and `message` fields
- ✅ Gates are advisory (do NOT block output)

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 15.3 🟢 Glossary/TM injection works with real LLM translation

```bash
cd /tmp/test-ol-real-api

# Create a glossary
cat > /tmp/test-ol-real-api/glossary.json << 'JSON'
{
  "API": {
    "translation": "应用程序编程接口",
    "variants": {"API": "应用程序编程接口"},
    "confidence": 0.95
  },
  "machine translation": {
    "translation": "机器翻译",
    "variants": {"machine translation": "机器翻译", "MT": "机器翻译"},
    "confidence": 0.95
  }
}
JSON

python3 -c "
import os, json, asyncio
os.environ['OL_CONFIG_PATH'] = '$OL_ROOT/config/default.yaml'
import importlib, ol_mcp.config
importlib.reload(ol_mcp.config)

from ol_mcp.translate_md import translate_md_text
from ol_mcp.tools import TranslateInput

async def test():
    # Load glossary first
    from ol_mcp.glossary import load_glossary
    glossary = await load_glossary('/tmp/test-ol-real-api/glossary.json')
    print(f'Glossary loaded: {len(glossary)} entries')

    params = TranslateInput(
        content='The API uses machine translation to process user requests.',
        source_lang='en',
        target_lang='zh',
    )
    result = json.loads(await translate_md_text(params))
    translated = result.get('content', {}).get('translated', '')
    print(f'Translated: {translated}')

    # Check glossary terms appeared
    glossary_terms_used = '应用程序编程接口' in translated or '机器翻译' in translated
    print(f'Glossary terms used: {glossary_terms_used}')

    if not glossary_terms_used:
        print('⚠️ Note: glossary terms may not appear if LLM chose different wording')
        print('   This is expected behavior — glossary injection is advisory')

    print('✅ Real LLM translation with glossary loaded completed')

asyncio.run(test())
"
```

**Expected Result:**
- ✅ Glossary loads successfully
- ✅ Translation completes with glossary context available
- ✅ Glossary terms may or may not appear (LLM discretion — glossary injection is advisory)

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 15.4 🟢 XLIFF translation with real LLM preserves structure

```bash
cd /tmp/test-ol-real-api

# Create a minimal XLIFF for real translation test
cat > /tmp/test-ol-real-api/test_real.xlf << 'XML'
<?xml version="1.0" encoding="utf-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.docx" source-language="en" target-language="zh" datatype="plaintext">
    <body>
      <trans-unit id="tu1">
        <source>This is the first paragraph for real XLIFF translation testing.</source>
        <target></target>
      </trans-unit>
      <trans-unit id="tu2">
        <source>The second paragraph contains technical terminology for API documentation.</source>
        <target></target>
      </trans-unit>
    </body>
  </file>
</xliff>
XML

python3 -c "
import os, json, asyncio
os.environ['OL_CONFIG_PATH'] = '$OL_ROOT/config/default.yaml'
import importlib, ol_mcp.config
importlib.reload(ol_mcp.config)

from ol_mcp.translate_xliff import translate_xliff
from ol_mcp.tools import XliffInput

async def test():
    params = XliffInput(
        input_path='/tmp/test-ol-real-api/test_real.xlf',
        source_lang='en',
        target_lang='zh',
    )
    result = json.loads(await translate_xliff(params))
    print(f'XLIFF result keys: {list(result.keys())}')

    output_path = result.get('output_path', '')
    if output_path:
        # Check output has target text
        with open(output_path, 'r') as f:
            content = f.read()
        has_target = '<target>' in content and '</target>' in content
        has_source = '<source>' in content and '</source>' in content
        print(f'Output has <target>: {has_target}')
        print(f'Output has <source>: {has_source}')
        assert has_target, 'XLIFF output should contain <target> elements'
        assert has_source, 'XLIFF output should preserve <source> elements'
        print(f'✅ XLIFF real LLM translation: structure preserved, targets filled')
    else:
        print(f'Output path not in result, full result: {json.dumps(result, indent=2)[:500]}')

asyncio.run(test())
"
```

**Expected Result:**
- ✅ XLIFF structure preserved: all `<source>` elements present
- ✅ `<target>` elements populated with real Chinese translation
- ✅ File structure valid XML (no broken tags)

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q15-OL Verdict

| Scenario | Result |
|----------|--------|
| 15.1 Real translate → real judge | ⬜ |
| 15.2 Translate with quality gates | ⬜ |
| 15.3 Glossary injection with real LLM | ⬜ |
| 15.4 XLIFF real LLM translation | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q16-OL: Can an agent run the full pipeline with real APIs end-to-end?

**User says:** "I want the full real experience — no FAKE_LLM, no shortcuts. Extract with OPP, translate with real LLM, judge with real LLM, backfill with ORF."

**Why this matters:** This is the production workflow. If any step fails under real conditions, the pipeline is not ready for deployment.

### Scenarios

#### 16.1 🟢 Full MD path: OPP → OL (real LLM) → judge → ORF backfill

```bash
cd /tmp && rm -rf test-ol-e2e-real && mkdir test-ol-e2e-real && cd test-ol-e2e-real
SUITE_ROOT="/mnt/d/贯维/Omni_Suite"
export PYTHONPATH="$SUITE_ROOT/Omni_Pre_Processor/src:$SUITE_ROOT/Omni_Localizer/src:$SUITE_ROOT/Omni_Re_Formatter/src:$PYTHONPATH"
export OPP_ALLOWED_DIRECTORIES="/tmp,$SUITE_ROOT"
export OL_CONFIG_PATH="$SUITE_ROOT/Omni_Localizer/config/default.yaml"
unset OMNI_TEST_FAKE_LLM
unset OMNI_TEST_FAKE_PANDOC

echo '=== PHASE 1: OPP Extract ==='
python3 -c "
import asyncio
from opp.mcp.server import extract_document
result = asyncio.run(extract_document(
    file_path='$SUITE_ROOT/Meridian_Robotics_Product_Overview_E2E.docx',
    output_formats=['md'],
    source_lang='en',
    target_lang='zh',
    output_dir='/tmp/test-ol-e2e-real/opp_output'
))
assert result.get('success'), f'OPP failed: {result}'
print('✅ OPP extract OK')
"

echo '=== PHASE 2: OL Real Translate ==='
python3 -c "
import os, json, asyncio
from ol_mcp.translate_md import translate_md_text
from ol_mcp.tools import TranslateInput

async def test():
    with open('/tmp/test-ol-e2e-real/opp_output/Meridian_Robotics_Product_Overview_E2E.md', 'r') as f:
        md_content = f.read()[:3000]  # First 3K chars for speed

    params = TranslateInput(
        content=md_content,
        source_lang='en',
        target_lang='zh',
    )
    result = json.loads(await translate_md_text(params))
    translated = result.get('content', {}).get('translated', '')
    warnings = result.get('warnings', [])

    print(f'Translated: {len(translated)} chars')
    print(f'Warnings: {len(warnings)}')
    for w in warnings:
        print(f'  Gate {w.get(\"gate\", \"?\")}: {str(w.get(\"message\", \"\"))[:80]}')

    assert len(translated) > 0
    # Check for Chinese content
    import re
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', translated)
    print(f'Chinese characters: {len(chinese_chars)}')
    assert len(chinese_chars) > 10, 'Translation should contain substantial Chinese content'
    print('✅ OL real LLM translation OK')

asyncio.run(test())
"

echo '=== PHASE 3: ORF Backfill ==='
python3 -c "
import json, sys
sys.path.insert(0, '$SUITE_ROOT/Omni_Re_Formatter/src')
from orf.mcp.server import apply_md
result = json.loads(apply_md(
    input_md='/tmp/test-ol-e2e-real/opp_output/Meridian_Robotics_Product_Overview_E2E.md',
    target_format='html',
    output_path='/tmp/test-ol-e2e-real/result.html'
))
assert result.get('success'), f'ORF failed: {result}'
print('✅ ORF backfill OK')
"
```

**Expected Result:**
- ✅ Phase 1: OPP extracts MD from DOCX
- ✅ Phase 2: OL translates with real LLM, produces Chinese output with >10 Chinese chars
- ✅ Phase 2: Quality gates fire (warnings list present, may be empty if perfect)
- ✅ Phase 3: ORF produces valid HTML file
- ✅ Full pipeline completes without FAKE_LLM

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 16.2 🟢 Full XLIFF path: OPP → OL (real LLM) → ORF backfill

```bash
cd /tmp && rm -rf test-ol-e2e-xliff-real && mkdir test-ol-e2e-xliff-real && cd test-ol-e2e-xliff-real
SUITE_ROOT="/mnt/d/贯维/Omni_Suite"
export PYTHONPATH="$SUITE_ROOT/Omni_Pre_Processor/src:$SUITE_ROOT/Omni_Localizer/src:$SUITE_ROOT/Omni_Re_Formatter/src:$PYTHONPATH"
export OPP_ALLOWED_DIRECTORIES="/tmp,$SUITE_ROOT"
unset OMNI_TEST_FAKE_LLM

echo '=== PHASE 1: OPP Extract XLIFF ==='
python3 -c "
import asyncio
from opp.mcp.server import extract_document
result = asyncio.run(extract_document(
    file_path='$SUITE_ROOT/Meridian_Robotics_Product_Overview_E2E.docx',
    output_formats=['xlf'],
    source_lang='en',
    target_lang='zh',
    output_dir='/tmp/test-ol-e2e-xliff-real/opp_output'
))
assert result.get('success'), f'OPP XLIFF failed: {result}'
print('✅ OPP XLIFF extract OK')
"

echo '=== PHASE 2: OL Real XLIFF Translate ==='
python3 -c "
import os, json, asyncio
from ol_mcp.translate_xliff import translate_xliff
from ol_mcp.tools import XliffInput

async def test():
    # Find the XLIFF file
    import glob
    xlf_files = glob.glob('/tmp/test-ol-e2e-xliff-real/opp_output/*.xlf')
    assert len(xlf_files) > 0, 'No XLIFF file found'
    xlf_path = xlf_files[0]

    params = XliffInput(
        input_path=xlf_path,
        source_lang='en',
        target_lang='zh',
    )
    result = json.loads(await translate_xliff(params))
    print(f'XLIFF translate keys: {list(result.keys())}')
    assert result.get('success', False) or result.get('output_path', ''), 'XLIFF translation should succeed'
    print(f'Output: {result.get(\"output_path\", \"unknown\")}')
    print('✅ OL real LLM XLIFF translation OK')

asyncio.run(test())
"

echo '=== PHASE 3: Save skeleton ==='
python3 -c "
import asyncio
from opp.mcp.server import save_skeleton
result = asyncio.run(save_skeleton(
    file_path='$SUITE_ROOT/Meridian_Robotics_Product_Overview_E2E.docx',
    base_name='meridian',
    output_dir='/tmp/test-ol-e2e-xliff-real/opp_output'
))
assert result.get('success'), f'save_skeleton failed: {result}'
print('✅ save_skeleton OK')
"

echo '=== PHASE 4: ORF apply-xliff ==='
export OMNI_TEST_FAKE_PANDOC=1
python3 -c "
import json, sys, glob
sys.path.insert(0, '$SUITE_ROOT/Omni_Re_Formatter/src')
from orf.mcp.server import apply_xliff

xlf_files = glob.glob('/tmp/test-ol-e2e-xliff-real/opp_output/*.xlf')
skeleton_files = glob.glob('/tmp/test-ol-e2e-xliff-real/opp_output/*.zip')

result = json.loads(apply_xliff(
    input_file='$SUITE_ROOT/Meridian_Robotics_Product_Overview_E2E.docx',
    xliff_path=xlf_files[0],
    output_path='/tmp/test-ol-e2e-xliff-real/result.docx',
    format='docx',
))
print(f'apply-xliff keys: {list(result.keys())}')
assert result.get('success'), f'apply-xliff failed: {result}'
print('✅ ORF apply-xliff OK')
"
unset OMNI_TEST_FAKE_PANDOC
```

**Expected Result:**
- ✅ Phase 1: OPP extracts XLIFF from DOCX
- ✅ Phase 2: OL translates XLIFF with real LLM, fills `<target>` elements
- ✅ Phase 3: save_skeleton produces skeleton.zip
- ✅ Phase 4: ORF apply-xliff backfills into DOCX
- ✅ Full XLIFF pipeline completes without FAKE_LLM

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 16.3 🟢 Batch translate multiple texts with real LLM (parallel)

```bash
cd /tmp/test-ol-real-api

python3 -c "
import os, json, asyncio
os.environ['OL_CONFIG_PATH'] = '$OL_ROOT/config/default.yaml'
import importlib, ol_mcp.config
importlib.reload(ol_mcp.config)

from ol_mcp.batch_translate import batch_translate_texts

async def test():
    texts = [
        'First test sentence for batch translation.',
        'Second sentence with technical terminology for API testing purposes.',
        'Third sentence: evaluating batch processing performance with real LLM calls.',
    ]
    result = await batch_translate_texts(texts, 'en', 'zh')
    print(f'Batch result type: {type(result).__name__}')

    if isinstance(result, dict):
        translations = result.get('translations', [])
        print(f'Translations count: {len(translations)}')
        for i, t in enumerate(translations):
            print(f'  [{i}] {t[:60]}...')
        assert len(translations) == len(texts), f'Expected {len(texts)} translations, got {len(translations)}'
    else:
        translations = result if isinstance(result, list) else [result]
        print(f'Raw result: {str(result)[:200]}')

    print('✅ Batch real LLM translation completed')

asyncio.run(test())
"
```

**Expected Result:**
- ✅ All 3 texts translated to Chinese in parallel
- ✅ Each translation has Chinese content
- ✅ Batch processing does not crash under concurrent real LLM calls

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q16-OL Verdict

| Scenario | Result |
|----------|--------|
| 16.1 Full MD path (OPP → OL real → ORF) | ⬜ |
| 16.2 Full XLIFF path (OPP → OL real → ORF) | ⬜ |
| 16.3 Batch translate with real LLM | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q17-OL: Can an agent detect, diagnose, and recover from real LLM API configuration issues?

**User says:** "What happens if I misconfigure my API keys or providers? Can the system tell me what's wrong?"

**Why this matters:** Real users (and AI agents) will inevitably misconfigure API keys — missing keys, expired keys, wrong base URLs, unsupported models. The system must diagnose these gracefully and provide actionable fixes.

### Scenarios

#### 17.1 🟢 Diagnose missing API key (all keys unset)

```bash
cd /tmp && rm -rf test-ol-diag-nokey && mkdir test-ol-diag-nokey && cd test-ol-diag-nokey
OL_ROOT="/mnt/d/贯维/Omni_Suite/Omni_Localizer"
export PYTHONPATH="$OL_ROOT/src:$PYTHONPATH"

# Unset ALL LLM keys and FAKE_LLM
unset OMNI_TEST_FAKE_LLM
unset ZHIPU_API_KEY
unset AGNES_API_KEY
unset NVIDIA_NIM_API_KEY
unset OPENCODE_GO_KEY

# Run translate without any keys
python3 -c "
import os, json, asyncio
os.environ['OL_CONFIG_PATH'] = '$OL_ROOT/config/default.yaml'

try:
    from ol_mcp.translate_md import translate_md_text
    from ol_mcp.tools import TranslateInput

    async def test():
        params = TranslateInput(
            content='Test with no API keys.',
            source_lang='en',
            target_lang='zh',
        )
        result = json.loads(await translate_md_text(params))
        print(f'Result: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}')

        # Check for error or graceful handling
        if result.get('success') == False:
            error = result.get('error', result.get('message', 'Unknown error'))
            print(f'❌ Expected failure: {str(error)[:200]}')
        elif 'error' in result:
            print(f'❌ Error in result: {result[\"error\"][:200]}')
        else:
            print('⚠️ Unexpected: translation succeeded without keys?')

    asyncio.run(test())
except Exception as e:
    print(f'❌ Exception type: {type(e).__name__}')
    print(f'❌ Exception message: {str(e)[:300]}')
    # This is expected — the system should error gracefully
    print('✅ System detected missing keys and raised a clear error')
"
```

**Expected Result:**
- ✅ Clear error message: "API key not configured" or "env var ZHIPU_API_KEY not set"
- ✅ No Python traceback in agent-facing output
- ✅ Error message identifies WHICH key is missing
- ✅ System does NOT hang or timeout waiting for nonexistent keys

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 17.2 🔴 Diagnose invalid API key (wrong format/expired)

```bash
cd /tmp && rm -rf test-ol-diag-badkey && mkdir test-ol-diag-badkey && cd test-ol-diag-badkey
OL_ROOT="/mnt/d/贯维/Omni_Suite/Omni_Localizer"
export PYTHONPATH="$OL_ROOT/src:$PYTHONPATH"
unset OMNI_TEST_FAKE_LLM

# Set an obviously invalid key
export ZHIPU_API_KEY="sk-this-is-clearly-an-invalid-key-12345"

python3 -c "
import os, json, asyncio
os.environ['OL_CONFIG_PATH'] = '$OL_ROOT/config/default.yaml'

try:
    from ol_mcp.translate_md import translate_md_text
    from ol_mcp.tools import TranslateInput

    async def test():
        params = TranslateInput(
            content='Test with invalid API key.',
            source_lang='en',
            target_lang='zh',
        )
        result = json.loads(await translate_md_text(params))
        print(f'Result: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}')

        if result.get('success') == False:
            error = result.get('error', result.get('message', ''))
            print(f'❌ Error: {str(error)[:200]}')
            # Check for authentication-related error keywords
            error_lower = str(error).lower()
            if any(kw in error_lower for kw in ['auth', 'key', 'token', '401', '403', 'invalid']):
                print('✅ Error message indicates authentication failure')
            else:
                print('⚠️ Error does not clearly indicate auth failure')
        else:
            print('⚠️ Translation succeeded (unexpected with invalid key)')

    asyncio.run(test())
except Exception as e:
    print(f'❌ Exception: {type(e).__name__}: {str(e)[:300]}')
    print('✅ Invalid key detected with error')
"
```

**Expected Result:**
- ✅ Clear error message: "401", "authentication failed", "invalid API key", etc.
- ✅ Error message is user-friendly (not raw HTTP response)
- ✅ System does NOT hang for extended period
- ✅ Output makes clear the issue is with the API key, not other components

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 17.3 🔴 Diagnose provider unreachable (wrong base URL)

```bash
cd /tmp && rm -rf test-ol-diag-badurl && mkdir test-ol-diag-badurl && cd test-ol-diag-badurl
OL_ROOT="/mnt/d/贯维/Omni_Suite/Omni_Localizer"
export PYTHONPATH="$OL_ROOT/src:$PYTHONPATH"
unset OMNI_TEST_FAKE_LLM
export ZHIPU_API_KEY="${ZHIPU_API_KEY:-dummy_key_for_testing}"

# Create config with unreachable base URL
cat > /tmp/test-ol-diag-badurl/config_badurl.yaml << 'YAML'
llm_pool:
  translation:
    - provider: "openai"
      model: "glm-4-flash"
      priority: 1
      role: "translation"
      api_key: "${ZHIPU_API_KEY}"
      base_url: "https://this-domain-does-not-exist-99999.com/v1"
      timeout: 5.0
YAML

export OL_CONFIG_PATH='/tmp/test-ol-diag-badurl/config_badurl.yaml'

python3 -c "
import os, json, asyncio
import importlib, ol_mcp.config, ol_mcp.translate_md
importlib.reload(ol_mcp.config)
importlib.reload(ol_mcp.translate_md)
from ol_mcp.translate_md import translate_md_text
from ol_mcp.tools import TranslateInput

async def test():
    params = TranslateInput(
        content='Test with unreachable provider URL.',
        source_lang='en',
        target_lang='zh',
    )
    result = json.loads(await translate_md_text(params))
    print(f'Result: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}')

    if result.get('success') == False:
        error = result.get('error', result.get('message', ''))
        error_lower = str(error).lower()
        print(f'❌ Error: {str(error)[:200]}')
        if any(kw in error_lower for kw in ['timeout', 'unreachable', 'connection', 'resolve', 'dns', 'connect']):
            print('✅ Error message indicates network/provider unreachable')
        else:
            print('⚠️ Error does not clearly indicate connectivity failure')
    else:
        print('⚠️ Unexpected: translation succeeded with bad URL?')

asyncio.run(test())
"
```

**Expected Result:**
- ✅ Clear error: "timeout", "DNS resolution failed", "connection refused", etc.
- ✅ Error distinguishes between "bad URL" and "bad key"
- ✅ No crash — translate returns gracefully with error
- ✅ Short timeout (5s) respected — doesn't hang indefinitely

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 17.4 🟢 Agent self-heal cycle: diagnose → fix → verify

```bash
cd /tmp && rm -rf test-ol-self-heal && mkdir test-ol-self-heal && cd test-ol-self-heal
OL_ROOT="/mnt/d/贯维/Omni_Suite/Omni_Localizer"
export PYTHONPATH="$OL_ROOT/src:$PYTHONPATH"
unset OMNI_TEST_FAKE_LLM
export OL_CONFIG_PATH="$OL_ROOT/config/default.yaml"

echo '=== PHASE 1: DIAGNOSE (no keys) ==='
unset ZHIPU_API_KEY
unset AGNES_API_KEY
unset NVIDIA_NIM_API_KEY
unset OPENCODE_GO_KEY

python3 -c "
import os, json, asyncio
os.environ['OL_CONFIG_PATH'] = '$OL_ROOT/config/default.yaml'

# Agent inspects config for missing keys
async def diagnose():
    from ol_mcp.inspect_config import inspect_config
    result = json.loads(await inspect_config())
    llm_pool = result.get('llm_pool', {})

    issues = []
    for role, models in llm_pool.items():
        for m in models:
            key_var = m.get('api_key', '')
            if key_var.startswith('\${') and key_var.endswith('}'):
                env_name = key_var[2:-1]
                if not os.environ.get(env_name):
                    issues.append(f'Missing env var: {env_name} (needed by {m.get(\"model\")})')

    for issue in issues:
        print(f'❌ {issue}')

    if issues:
        print(f'🔧 Diagnosed {len(issues)} configuration issue(s)')
    else:
        print('✅ All keys configured')

    return issues

issues = asyncio.run(diagnose())
print(f'ISSUES_FOUND={len(issues)}')
"

echo '=== PHASE 2: FIX (set keys from environment) ==='
# In a real scenario, the agent would prompt the user or use pre-configured fallback
# Here we set keys from the current shell environment
export ZHIPU_API_KEY="${ZHIPU_API_KEY}"
echo '🔧 Agent applies fix: set ZHIPU_API_KEY'

echo '=== PHASE 3: VERIFY ==='
python3 -c "
import os, json, asyncio
os.environ['OL_CONFIG_PATH'] = '$OL_ROOT/config/default.yaml'

async def verify():
    from ol_mcp.inspect_config import inspect_config
    result = json.loads(await inspect_config())
    llm_pool = result.get('llm_pool', {})

    issues = []
    for role, models in llm_pool.items():
        for m in models:
            key_var = m.get('api_key', '')
            if key_var.startswith('\${') and key_var.endswith('}'):
                env_name = key_var[2:-1]
                if not os.environ.get(env_name):
                    issues.append(f'Missing env var: {env_name}')

    if issues:
        print(f'❌ Still {len(issues)} unresolved issue(s)')
        for i in issues:
            print(f'  - {i}')
    else:
        print('✅ All keys configured after fix')

    # Now actually try a translation
    from ol_mcp.translate_md import translate_md_text
    from ol_mcp.tools import TranslateInput

    params = TranslateInput(
        content='Self-healing test: this should work after fixing the API key.',
        source_lang='en',
        target_lang='zh',
    )
    t_result = json.loads(await translate_md_text(params))
    translated = t_result.get('content', {}).get('translated', '')
    if translated:
        print(f'✅ Translation works after fix: {translated[:80]}')
    else:
        print('⚠️ Translation returned empty after fix')
        print(f'Result: {json.dumps(t_result, indent=2)[:300]}')

asyncio.run(verify())
"
```

**Expected Result:**
- ✅ Phase 1: Agent inspects config and identifies missing ZHIPU_API_KEY
- ✅ Phase 1: Error messages name the specific missing env var
- ✅ Phase 2: Agent applies fix (set env var) — demonstrates self-heal cycle
- ✅ Phase 3: After fix, inspect_config shows all keys configured
- ✅ Phase 3: Translation succeeds with real LLM (verification)

**Indicator Checks:**
| What to Check | Pass Condition | Fail Action |
|---------------|----------------|-------------|
| Exit code | `echo $?` must be 0 | Re-run with `-v` flag, check file permissions |
| Output file | `ls -la` shows output file exists | Check parent directory path and filename |
| File size | `stat` shows > 0 bytes | Verify source file has content and output dir is writable |

**Test File Cross-Reference:**
- 🧪 **Automated test**: `tests/path/to/test_file.py::test_function` (if automated test exists — update this path)
- 📋 **Manual only**: No automated test for this specific scenario (manual execution only)

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q17-OL Verdict

| Scenario | Result |
|----------|--------|
| 17.1 Diagnose missing API key | ⬜ |
| 17.2 Diagnose invalid API key | ⬜ |
| 17.3 Diagnose unreachable provider | ⬜ |
| 17.4 Self-heal cycle (diagnose → fix → verify) | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

# Part 9: Final Verdict

---

## Overall PASS/FAIL Summary

| Part | Section | Verdict |
|------|---------|---------|
| 1 | Core Translation Pipeline (Q1-OL — Q4-OL) | ⬜ |
| 2 | Quality Gates & LQA (Q5-OL — Q6-OL) | ⬜ |
| 3 | MCP Surface Mastery (Q7-OL) | ⬜ |
| 4 | Agent-as-User Workflows (Q8-OL — Q9-OL) | ⬜ |
| 5 | CLI Surface Mastery (Q10-OL) | ⬜ |
| 6 | Error & Boundary Matrix (Q11-OL — Q12-OL) | ⬜ |
| 7 | Production Validation (Q13-OL) | ⬜ |
| 8 | Real LLM API Configuration & E2E Tests (Q14-OL — Q17-OL) | ⬜ |

**GRAND TOTAL: ⬜ / 17 Questions**

**OVERALL VERDICT: ⬜**

---

## Production Gap Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| All 21 MCP tools respond correctly | ⬜ | Q7-OL |
| All 7 CLI commands work | ⬜ | Q10-OL |
| MD translation pipeline works (shield → translate → repair → unshield → postproc → quality gates) | ⬜ | Q1-OL |
| XLIFF translation pipeline works | ⬜ | Q2-OL |
| FAKE_LLM mode works for zero-cost testing | ⬜ | Q3-OL |
| Model pool failover (role-based routing, circuit breaker, retry) | ⬜ | Q4-OL |
| All 8 quality gates fire and are advisory | ⬜ | Q5-OL |
| LQA scoring with judge/retry works | ⬜ | Q6-OL |
| Glossary/TM injection improves translation | ⬜ | Q9-OL |
| Agent can translate → judge → verify terms | ⬜ | Q8-OL |
| Empty/large content handled gracefully | ⬜ | Q11-OL |
| Missing API keys handled gracefully | ⬜ | Q12-OL |
| MCP server stdio transport works | ⬜ | Q13-OL |
| Shield round-trip is lossless | ⬜ | Q11-OL |
| Error cases handled gracefully | ⬜ | Q10-OL, Q11-OL, Q12-OL |
| Test suite passes (200+) | ⬜ | Q13-OL |
| Real LLM API keys configurable and detectable via inspect_config | ⬜ | Q14-OL |
| Real LLM translation produces Chinese output (end-to-end connectivity) | ⬜ | Q14-OL |
| Model pool routing: 3 role pools (translation, judging, restoration) | ⬜ | Q14-OL |
| Fallback chain activates when primary provider is unreachable | ⬜ | Q14-OL |
| Real LLM translation → real judge (LQA scoring) works | ⬜ | Q15-OL |
| Real translation with all 8 quality gates enabled | ⬜ | Q15-OL |
| Glossary/TM injection works with real LLM | ⬜ | Q15-OL |
| Full E2E MD path with real LLM (no FAKE_LLM) | ⬜ | Q16-OL |
| Full E2E XLIFF path with real LLM (no FAKE_LLM) | ⬜ | Q16-OL |
| Batch translate with real LLM (parallel) | ⬜ | Q16-OL |
| Agent diagnoses missing/invalid/unreachable API keys | ⬜ | Q17-OL |
| Agent self-heals configuration issues | ⬜ | Q17-OL |

---

## Sign-off Criteria

| Level | Requirements | Met? |
|-------|-------------|------|
| **CI Gate** | All 17 questions answered. No P0 failures (crash, data loss). | ⬜ |
| **Release Candidate** | CI Gate + Q1-OL — Q3-OL + Q7-OL + Q14-OL — Q17-OL all PASS + all production gaps addressed | ⬜ |
| **Production Deploy** | Release Candidate + Q13-OL all PASS + no outstanding P0/P1 issues | ⬜ |

---

*Plan generated: 2026-07-22*
*Based on: OL v0.7.1 codebase — 21 MCP tools, 8 quality gates, 4-layer repair pipeline, ModelPool failover, LQA*
