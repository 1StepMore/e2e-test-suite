# Omni Suite Master Validation Plan

## Result-Oriented · User-Centric · All Scenarios & Boundaries

**For:** Hermes, Claude, Cursor, OpenCode — any AI agent validating Omni Suite
**Date:** 2026-07-16
**Strategy:** Every section asks a user question → executes scenarios → reports a binary verdict

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

## Verdict Legend

| Symbol | Meaning |
|--------|---------|
| ✅ PASS | All scenarios in this section match expected results |
| ❌ FAIL | One or more scenarios did NOT match expected results |
| ⚠️ PARTIAL | Some scenarios pass, some fail (list which ones) |
| ➖ SKIP | Scenarios intentionally skipped (reason documented) |

---

## Table of Contents

### Part 1: Core Translation Journeys
- **Q1:** Can I translate a DOCX end-to-end? (MD path)
- **Q2:** Can I translate a DOCX end-to-end? (XLIFF path)
- **Q3:** Can I translate and convert to a different format?
- **Q4:** Can I batch-process multiple documents?

### Part 2: Format Support Mastery
- **Q5:** Does every supported format extract correctly?
- **Q6:** Does every supported output format convert correctly?

### Part 3: Error & Boundary Matrix
- **Q7:** What happens when inputs are missing/corrupt/empty/huge?
- **Q8:** What happens at security boundaries (path traversal, auth)?
- **Q9:** What happens with CJK, emoji, RTL, special characters?
- **Q10:** What happens with concurrent/parallel calls?

### Part 4: Production Trust
- **Q11:** Is the pipeline deterministic? (Same input → same output?)
- **Q12:** Are CLI and MCP outputs equivalent?
- **Q13:** Are images preserved through the XLIFF path?
- **Q14:** Are the 195-cell format matrix results intact?

### Part 5: Production Validation (Real LLM · Real Pandoc · Performance)
- **Q15:** Does real LLM translation produce acceptable quality?
- **Q16:** Does real pandoc produce valid format output?
- **Q17:** Does performance meet production thresholds?
- **Q18:** Does multi-provider failover work?
- **Q19:** Can the system run continuously without degradation?
- **Q20:** Does the real MCP server work via stdio process?

### Part 6: Final Verdict
- Overall PASS/FAIL summary
- Production gap checklist
- Sign-off (CI Gate / Release Candidate / Production Deploy)

### Part 7: Language Pair Expansion
- **Q21:** Does the pipeline work with Japanese (zh↔ja)?
- **Q22:** Does the pipeline work with Korean (zh↔ko)?
- **Q23:** Does the pipeline work with European languages (zh↔fr, zh↔de)?

### Part 8: Media & Format Depth
- **Q24:** Are floating images preserved through the XLIFF path?
- **Q25:** Does OCR extraction produce usable text quality?
- **Q26:** Does YouTube/ASR transcription produce usable text?

### Part 9: Translation Quality Infrastructure
- **Q27:** Is translation consistent across different LLM providers?
- **Q28:** Are LQA quality thresholds calibrated correctly?
- **Q29:** Does the pipeline handle diverse file encodings (UTF-16, GBK)?

### Part 10: Pipeline Infrastructure & Resilience
- **Q30:** Does the OPP cache mechanism work correctly?
- **Q31:** Does OPP style mapping work?
- **Q32:** Can the pipeline recover after partial failure?
- **Q33:** Is the CLI help output format stable?
- **Q34:** Are version combinations compatible?
- **Q35:** Does graceful shutdown work cleanly?
- **Q36:** Are log levels and formats correct?
- **Q37:** Are the pre-commit hooks working?

---

# Part 1: Core Translation Journeys

---

## Q1: Can I translate a DOCX end-to-end? (MD Path)

**User says:** "I have a Chinese DOCX file. I want to translate it to English and get back a DOCX."

**Why this matters:** This is the most common user workflow. If this doesn't work, nothing else matters.

### Scenarios

#### 1.1 🟢 Happy Path — Haier DOCX zh→en→DOCX via CLI

```bash
export OMNI_TEST_FAKE_LLM=1 OMNI_TEST_FAKE_PANDOC=1

# Step 1: OPP extract to MD
opp "爱上海尔_第二章_全球创牌 - E2E测试专用.docx" --target-format md --source-lang zh --target-lang en -o /tmp/q1/opp

# Step 2: OL translate MD zh→en
ol translate-md /tmp/q1/opp/*.md -s zh -t en -c Omni_Localizer/config/default.yaml -o /tmp/q1/ol

# Step 3: ORF backfill MD→DOCX
orf apply-md /tmp/q1/ol/*.md --target-format docx --output /tmp/q1/orf/result.docx
```

**Expected Result:**
- ✅ All 3 commands exit with code 0
- ✅ `/tmp/q1/opp/*.md` exists and is non-empty
- ✅ `/tmp/q1/ol/*.md` exists, content differs from source (contains `[EN]` markers)
- ✅ `/tmp/q1/orf/result.docx` exists, is valid ZIP with `word/document.xml`
- ✅ `word/document.xml` contains translated content (not identical to source)

**Actual Result:** _________
**PASS / FAIL:** _________

#### 1.2 🟢 Happy Path — Meridian DOCX en→zh→DOCX via CLI

Same as 1.1 but with English source → Chinese target:
- Input: `Meridian_Robotics_Product_Overview_E2E.docx`
- Direction: en→zh
- Expected: `[ZH]` markers in output, not `[EN]`

**Actual Result:** _________
**PASS / FAIL:** _________

#### 1.3 🟢 Happy Path — Haier DOCX zh→en→DOCX via MCP

```python
import asyncio, json
from pathlib import Path
from unittest.mock import patch
from tests.test_e2e_pipeline_fixtures import _FakeModelPool

SUITE = Path("/mnt/d/贯维/Omni_Suite")
HAIER = SUITE / "爱上海尔_第二章_全球创牌 - E2E测试专用.docx"

with patch("ol_mcp.tools.ModelPool") as mock_pool:
    mock_pool.get_instance.return_value = _FakeModelPool()
    mock_pool.return_value = _FakeModelPool()

    # OPP MCP generate_markdown
    from opp.mcp.server import generate_markdown
    r = await generate_markdown(str(HAIER), output_path="/tmp/q1/mcp/opp.md")
    assert r["success"]; assert Path("/tmp/q1/mcp/opp.md").exists()

    # OL MCP translate_md_text
    from ol_mcp.tools import TranslateInput
    from ol_mcp.translate_md import translate_md_text
    result = await translate_md_text(TranslateInput(
        content=Path("/tmp/q1/mcp/opp.md").read_text(encoding="utf-8"),
        source_lang="zh", target_lang="en",
    ))
    data = json.loads(result)
    assert data["success"]; assert data["translated"] != ""

    # ORF MCP apply_md
    from orf.mcp.server import apply_md
    r = apply_md(input_md="/tmp/q1/mcp/translated.md",
                 target_format="docx", output_path="/tmp/q1/mcp/result.docx")
    assert json.loads(r)["success"]
```

**Expected Result:**
- ✅ OPP MCP returns success, MD file created
- ✅ OL MCP returns success, translated content differs from source
- ✅ ORF MCP returns success, DOCX output created

**Actual Result:** _________
**PASS / FAIL:** _________

#### 1.4 🟢 FAKE_LLM produces deterministic output

Run the same MD translation twice. Both outputs should be identical.

```bash
# Run 1
ol translate-md /tmp/q1/opp/*.md -s zh -t en -c Omni_Localizer/config/default.yaml -o /tmp/q1/ol1
md5sum /tmp/q1/ol1/*.md > /tmp/q1/hash1

# Run 2
ol translate-md /tmp/q1/opp/*.md -s zh -t en -c Omni_Localizer/config/default.yaml -o /tmp/q1/ol2
md5sum /tmp/q1/ol2/*.md > /tmp/q1/hash2

# Compare
diff /tmp/q1/hash1 /tmp/q1/hash2
```

**Expected Result:** ✅ Both runs produce byte-identical output (no randomness in FAKE_LLM mode).

**Actual Result:** _________
**PASS / FAIL:** _________

#### 1.5 🟢 Input source has no effect on FAKE_LLM output structure

FAKE_LLM produces `[EN]`/`[ZH]` markers. The output structure (paragraphs, headings, tables) should match input structure regardless of content.

**Verify:** The translated MD should have the same number of paragraphs/headings as the source MD (just with translation markers added).

**Actual Result:** _________
**PASS / FAIL:** _________

#### 1.6 🔴 Without FAKE_LLM, pipeline fails gracefully (no API keys)

```bash
unset OMNI_TEST_FAKE_LLM
# Keep dummy API keys (ZHIPU_API_KEY=sk-dummy etc.)
ol translate-md /tmp/q1/opp/*.md -s zh -t en -c Omni_Localizer/config/default.yaml -o /tmp/q1/nofake
```

**Expected Result:** ❌ Returns non-zero exit code. Error message contains "API" or "key" or "connection" or similar. Does NOT crash with unhandled exception.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 1.7 🔴 Missing input file

```bash
opp /nonexistent/path.docx --target-format md -o /tmp/q1/missing
```

**Expected Result:** ❌ Exit code != 0. Error message includes "not found" or "does not exist".

**Actual Result:** _________
**PASS / FAIL:** _________

#### 1.8 🔴 Corrupt input file

```bash
echo "not a real docx" > /tmp/q1/corrupt.docx
opp /tmp/q1/corrupt.docx --target-format md -o /tmp/q1/corrupt_out
```

**Expected Result:** ❌ Exit code != 0. Error message indicates corrupt/invalid file.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 1.9 🔴 Empty input file

```bash
touch /tmp/q1/empty.docx
opp /tmp/q1/empty.docx --target-format md -o /tmp/q1/empty_out
```

**Expected Result:** ❌ Exit code != 0. Error message about empty file or invalid format.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q1 Verdict

| Scenario | Result |
|----------|--------|
| 1.1 Happy path (CLI, zh→en) | ⬜ |
| 1.2 Happy path (CLI, en→zh) | ⬜ |
| 1.3 Happy path (MCP) | ⬜ |
| 1.4 Deterministic output | ⬜ |
| 1.5 Structure preservation | ⬜ |
| 1.6 No FAKE_LLM graceful failure | ⬜ |
| 1.7 Missing input | ⬜ |
| 1.8 Corrupt input | ⬜ |
| 1.9 Empty input | ⬜ |

**OVERALL: ⬜** (✅ if all pass, ❌ if any fail)

---

## Q2: Can I translate a DOCX end-to-end? (XLIFF Path)

**User says:** "I need the translated output to look EXACTLY like the original — same fonts, layout, images."

**Why this matters:** MD path is text-only, loses layout. XLIFF path preserves the original document structure by using skeleton.zip.

### Scenarios

#### 2.1 🟢 Happy Path — Haier DOCX zh→en→DOCX via CLI

```bash
export OMNI_TEST_FAKE_LLM=1 OMNI_TEST_FAKE_PANDOC=1

# Step 1: OPP extract to XLIFF + skeleton
opp "爱上海尔_第二章_全球创牌 - E2E测试专用.docx" --target-format xlf --source-lang zh --target-lang en -o /tmp/q2/opp

# Step 2: OL translate XLIFF zh→en
ol translate-xliff /tmp/q2/opp/*.xlf -s zh -t en -c Omni_Localizer/config/default.yaml -o /tmp/q2/ol

# Step 3: ORF backfill XLIFF→DOCX
orf apply-xliff /tmp/q2/opp/*.skeleton.zip \
  --xliff /tmp/q2/ol/*.xlf \
  --output /tmp/q2/orf/result.docx \
  --format docx
```

**Expected Result:**
- ✅ All 3 commands exit with code 0
- ✅ OPP produces `.xlf`, `.skeleton.zip`, `_manifest.json`
- ✅ Translated XLIFF has `<target>` elements filled, content differs from `<source>`
- ✅ Final DOCX is valid (ZIP + `word/document.xml`)
- ✅ Final DOCX has same visual structure as source (paragraphs, tables preserved)

**Actual Result:** _________
**PASS / FAIL:** _________

#### 2.2 🟢 Happy Path — Meridian PPTX en→zh→PPTX via CLI

Same as 2.1 but:
- Input: `Meridian_Q1_Update_E2E.pptx`
- Direction: en→zh
- ORF target: `--format pptx`

**Expected Result:**
- ✅ All steps pass
- ✅ Final PPTX is valid (ZIP + `ppt/presentation.xml`)

**Actual Result:** _________
**PASS / FAIL:** _________

#### 2.3 🟢 Happy Path — XLIFF via MCP

```python
import asyncio, json
from pathlib import Path
from unittest.mock import patch
from tests.test_e2e_pipeline_fixtures import _FakeModelPool

HAIER = Path("/mnt/d/贯维/Omni_Suite/爱上海尔_第二章_全球创牌 - E2E测试专用.docx")

# Step 1: OPP generate XLIFF + save skeleton
from opp.mcp.server import generate_xliff, save_skeleton
r = await generate_xliff(str(HAIER), "zh", "en", output_path="/tmp/q2/mcp/doc.xlf")
assert r["success"]
await save_skeleton(str(HAIER), base_name="doc", output_dir="/tmp/q2/mcp")

# Step 2: OL translate XLIFF
with patch("ol_mcp.tools.ModelPool") as mock:
    mock.get_instance.return_value = _FakeModelPool()
    mock.return_value = _FakeModelPool()
    from ol_mcp.translate_xliff import translate_xliff
    result = await translate_xliff(
        input_path="/tmp/q2/mcp/doc.xlf",
        source_lang="zh", target_lang="en",
    )

# Step 3: ORF apply XLIFF
from orf.mcp.server import apply_xliff
r = apply_xliff(
    input_file="/tmp/q2/mcp/doc.skeleton.zip",
    xliff_path="/tmp/q2/mcp/translated.xlf",
    output_path="/tmp/q2/mcp/result.docx",
    format="docx",
)
assert json.loads(r)["success"]
```

**Expected Result:**
- ✅ All 3 MCP calls succeed
- ✅ Final DOCX is valid

**Actual Result:** _________
**PASS / FAIL:** _________

#### 2.4 🔴 XLIFF without skeleton (no skeleton for HTML/CSV/JSON/etc.)

**Setup:** Generate XLIFF from an HTML file (which has no skeleton).

```bash
echo "<html><body><p>Test</p></body></html>" > /tmp/q2/test.html
opp /tmp/q2/test.html --target-format xlf --source-lang en --target-lang zh -o /tmp/q2/opp_html
```

**Verify:** No `.skeleton.zip` is produced for HTML.
- ✅ OPP produces XLIFF
- ✅ No skeleton file exists
- ✅ ORF `apply-xliff` without skeleton returns clear error

**Actual Result:** _________
**PASS / FAIL:** _________

#### 2.5 🔴 Cross-format XLIFF (DOCX skeleton → PPTX output) without --force

```bash
orf apply-xliff /tmp/q2/opp/*.skeleton.zip \
  --xliff /tmp/q2/ol/*.xlf \
  --output /tmp/q2/cross/result.pptx \
  --format pptx
# Note: no --force flag
```

**Expected Result:** ❌ Returns error about format mismatch. Does NOT produce a file.
- ✅ Error message mentions "format" or "mismatch" or "force"

**Actual Result:** _________
**PASS / FAIL:** _________

#### 2.6 🟢 Cross-format with --force (may produce partial output)

```bash
orf apply-xliff /tmp/q2/opp/*.skeleton.zip \
  --xliff /tmp/q2/ol/*.xlf \
  --output /tmp/q2/force/result.pptx \
  --format pptx --force
```

**Expected Result:** ⚠️ `--force` bypasses format validation. May produce a malformed PPTX. The important thing is: it does NOT crash with unhandled exception, and returns a clear error or warning.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q2 Verdict

| Scenario | Result |
|----------|--------|
| 2.1 Happy path (CLI, DOCX) | ⬜ |
| 2.2 Happy path (CLI, PPTX) | ⬜ |
| 2.3 Happy path (MCP) | ⬜ |
| 2.4 No skeleton for non-OOXML | ⬜ |
| 2.5 Cross-format without --force | ⬜ |
| 2.6 Cross-format with --force | ⬜ |

**OVERALL: ⬜**

---

## Q3: Can I translate and convert to a different format?

**User says:** "I have a DOCX. I want to translate it and output an EPUB (or HTML, or PDF)."

**Why this matters:** Cross-format conversion is a key value proposition — users often need output in a different format from the input.

### Scenarios

#### 3.1 🟢 DOCX→MD→translate→EPUB

```bash
export OMNI_TEST_FAKE_LLM=1 OMNI_TEST_FAKE_PANDOC=1

opp "爱上海尔_第二章_全球创牌 - E2E测试专用.docx" --target-format md --source-lang zh --target-lang en -o /tmp/q3/opp
ol translate-md /tmp/q3/opp/*.md -s zh -t en -c Omni_Localizer/config/default.yaml -o /tmp/q3/ol
orf apply-md /tmp/q3/ol/*.md --target-format epub --output /tmp/q3/orf/result.epub
```

**Expected Result:**
- ✅ All commands exit with code 0
- ✅ `/tmp/q3/orf/result.epub` exists, non-empty
- ⚠️ With FAKE_PANDOC: output is a stub DOCX, NOT a valid EPUB. Only verify file exists + non-empty.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 3.2 🟢 DOCX→MD→translate→HTML

```bash
orf apply-md /tmp/q3/ol/*.md --target-format html --output /tmp/q3/orf/result.html
```

**Expected Result:**
- ✅ File exists, non-empty
- ✅ Contains `<!DOCTYPE html>` or `<html>` tags (pure-python path, NOT affected by FAKE_PANDOC)

**Actual Result:** _________
**PASS / FAIL:** _________

#### 3.3 🟢 DOCX→MD→translate→PDF

```bash
orf apply-md /tmp/q3/ol/*.md --target-format pdf --output /tmp/q3/orf/result.pdf
```

**Expected Result:**
- ✅ File exists, non-empty
- ⚠️ With FAKE_PANDOC: stub output. Only verify existence + non-empty.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 3.4 🟢 DOCX→MD→translate→all 16 formats (one-command)

```bash
for fmt in docx odt epub html rtf pdf pptx icml srt csv xlsx xml ipynb eml msg json; do
  orf apply-md /tmp/q3/ol/*.md --target-format $fmt --output /tmp/q3/orf/result.$fmt
  echo "--- $fmt: $? ---"
done
```

**Expected Result:**
- ✅ All formats produce a non-empty output file
- ❌ MSG may fail (requires `aspose-email-foss`, GPLv3)
- ❌ PPTX may fail (requires `md2pptx` CLI)
- ⚠️ IPYNB may fail (requires `nbformat`)
- ⚠️ FAKE_PANDOC formats (docx, odt, epub, rtf, icml, pdf): stub only

**Actual Result:** _________
**PASS / FAIL:** _________

#### 3.5 🔴 Unsupported output format

```bash
orf apply-md /tmp/q3/ol/*.md --target-format unknown --output /tmp/q3/orf/result.xyz
```

**Expected Result:** ❌ Exit code != 0. Error message mentions "unsupported" or "unknown format".

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q3 Verdict

| Scenario | Result |
|----------|--------|
| 3.1 DOCX→MD→EPUB | ⬜ |
| 3.2 DOCX→MD→HTML | ⬜ |
| 3.3 DOCX→MD→PDF | ⬜ |
| 3.4 All 16 formats | ⬜ |
| 3.5 Unsupported format | ⬜ |

**OVERALL: ⬜**

---

## Q4: Can I batch-process multiple documents?

**User says:** "I have 50 documents to translate. I don't want to run them one at a time."

**Why this matters:** Batch processing is essential for real-world use. Tests concurrency, resource limits, and isolation.

### Scenarios

#### 4.1 🟢 OPP batch_extract — 3 files (DOCX + PPTX + HTML)

```python
from opp.mcp.server import batch_extract

result = await batch_extract(
    file_paths=[
        "/mnt/d/贯维/Omni_Suite/爱上海尔_第二章_全球创牌 - E2E测试专用.docx",
        "/mnt/d/贯维/Omni_Suite/Meridian_Q1_Update_E2E.pptx",
        "/tmp/q4/test.html",  # create synthetic HTML first
    ],
    output_formats=["md", "xlf"],
    source_lang="en",
    target_lang="zh",
)
```

**Expected Result:** ✅ All 3 files processed successfully. Each file produces both MD and XLIFF. Result is a list of 3 independent extraction results.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 4.2 🟢 OL batch_translate_texts — 3 texts in parallel

```python
from unittest.mock import patch
from tests.test_e2e_pipeline_fixtures import _FakeModelPool

with patch("ol_mcp.tools.ModelPool") as mock:
    mock.get_instance.return_value = _FakeModelPool()
    mock.return_value = _FakeModelPool()

    from ol_mcp.tools import batch_translate_texts
    result = await batch_translate_texts(
        texts=["# Hello World", "Goodbye", "Paragraph three"],
        source_lang="en",
        target_lang="zh",
        concurrency=5,
    )
```

**Expected Result:** ✅ All 3 texts translated independently. Each result is a separate translation with `[ZH]` markers.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 4.3 🟢 ORF batch_convert — directory of MD files

```bash
mkdir -p /tmp/q4/mds
echo "# Doc 1" > /tmp/q4/mds/doc1.md
echo "# Doc 2" > /tmp/q4/mds/doc2.md

orf convert-batch /tmp/q4/mds --target-format docx --pattern "*.md" --json
```

**Expected Result:** ✅ Both files converted. JSON output lists both conversions with success status.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 4.4 🔴 Batch with one corrupt file — others should still succeed

```bash
mkdir -p /tmp/q4/mixed
echo "valid content" > /tmp/q4/mixed/good.md
echo "not a document" > /tmp/q4/mixed/bad.bin  # wrong extension, skipped by pattern

# ORF batch convert with pattern
orf convert-batch /tmp/q4/mixed --target-format docx --pattern "*.md" --json
```

**Expected Result:** ✅ `.md` files processed. Non-matching patterns skipped. No crash.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 4.5 🔴 OPP batch_extract — resource limit exceeded

Test with a large batch (create 10+ dummy files and attempt batch processing):

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
export OMNI_TEST_FAKE_LLM=1

# Create 10 dummy files in a temp directory
mkdir -p /tmp/q4_batch_limit
for i in $(seq 1 10); do
  python3 -c "
from docx import Document
doc = Document()
doc.add_heading('Document $i', level=1)
doc.add_paragraph('Content for doc $i.' * 50)
doc.save('/tmp/q4_batch_limit/doc_$i.docx')
"
done

# Try to batch-process all 10
opp batch-extract /tmp/q4_batch_limit/*.docx --target-format md -o /tmp/q4_batch_limit/out
echo "Exit code: $?"
```

**Expected Result:** ❌ Either:
- Returns `OPP_RESOURCE_EXHAUSTED` (if the batch limit is exceeded), OR
- Successfully processes all 10 files (if no batch limit is configured — note the actual limit)

In either case, the system must:
- NOT crash with an unhandled exception
- NOT leak temporary files
- Return a clear error message if limit is hit

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q4 Verdict

| Scenario | Result |
|----------|--------|
| 4.1 OPP batch 3 files | ⬜ |
| 4.2 OL batch 3 texts | ⬜ |
| 4.3 ORF batch convert dir | ⬜ |
| 4.4 Mixed valid/invalid | ⬜ |
| 4.5 Resource limit | ⬜ |

**OVERALL: ⬜**

---

# Part 2: Format Support Mastery

---

## Q5: Does every supported input format extract correctly?

**User says:** "I have documents in various formats — DOCX, PPTX, PDF, HTML, CSV, JSON, XML, EPUB, EML, images, YouTube URLs. Can OPP handle all of them?"

**Why this matters:** OPP supports 13+ input formats. Each has unique extraction characteristics. Missing format support = lost documents.

### Input Format Matrix

For each format, we verify:
1. ✅ `detect_format_tool` correctly identifies the format
2. ✅ `generate_markdown` produces valid markdown output
3. ✅ `generate_xliff` produces valid XLIFF (for formats that support it)
4. ✅ `save_skeleton` works (for OOXML formats)
5. ✅ `extract_document` with `output_formats="both"` works

#### 5.1 🟢 DOCX (Microsoft Word)

**File:** `爱上海尔_第二章_全球创牌 - E2E测试专用.docx` (real, 447 KB)

```python
from opp.mcp.server import detect_format_tool, generate_markdown, generate_xliff

# detect
r = await detect_format_tool(file_path=str(docx_path))
assert r["format"] == "docx"  # or similar

# markdown
r = await generate_markdown(file_path=str(docx_path))
assert r["success"]

# xliff
r = await generate_xliff(file_path=str(docx_path), source_lang="zh", target_lang="en")
assert r["success"]
```

**Expected Result:** ✅ All 3 tools succeed. Markdown contains headings/paragraphs/tables. XLIFF contains trans-units with inline formatting tags.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 5.2 🟢 PPTX (PowerPoint)

**File:** `Meridian_Q1_Update_E2E.pptx` (real, 30 KB)

**Same 3-tool test as 5.1.**

**Expected Result:** ✅ All succeed. Markdown preserves slide structure. XLIFF preserves slide content.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 5.3 🟢 PDF

Create minimal PDF:

```python
# Use pytest fixture from conftest.py
from tests.conftest import sample_pdf_path  # needs reportlab
```

**Expected Result:**
- ✅ `detect_format_tool` identifies as PDF
- ✅ `generate_markdown` extracts text
- ❌ `generate_xliff` intentionally BLOCKED (OPP raises ValueError — see ACCEPTED_GAPS.md)

**Actual Result:** _________
**PASS / FAIL:** _________

#### 5.4 🟢 HTML

```bash
echo '<html><body><h1>Title</h1><p>Content</p></body></html>' > /tmp/q5/test.html
opp /tmp/q5/test.html --target-format both --source-lang en --target-lang zh -o /tmp/q5/html_out
```

**Expected Result:**
- ✅ MD extraction works (content extracted)
- ✅ XLIFF NOT produced (HTML has no skeleton)
- ✅ No skeleton.zip for HTML input

**Actual Result:** _________
**PASS / FAIL:** _________

#### 5.5 🟢 CSV

```bash
echo -e 'name,age\nAlice,30\nBob,25' > /tmp/q5/test.csv
opp /tmp/q5/test.csv --target-format md -o /tmp/q5/csv_out
```

**Expected Result:** ✅ MD output contains table representation of CSV data.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 5.6 🟢 JSON

```bash
echo '{"name": "test", "value": 42}' > /tmp/q5/test.json
opp /tmp/q5/test.json --target-format md -o /tmp/q5/json_out
```

**Expected Result:** ✅ MD output contains JSON content in readable format.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 5.7 🟢 XML

```bash
echo '<?xml version="1.0"?><root><item id="1">text</item></root>' > /tmp/q5/test.xml
opp /tmp/q5/test.xml --target-format md -o /tmp/q5/xml_out
```

**Expected Result:** ✅ MD output contains XML content in readable format.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 5.8 🟢 EPUB

```python
# Create minimal EPUB (use pytest fixture or ebooklib)
```

**Expected Result:** ✅ MD extraction works. EPUB→XLIFF is supported (has skeleton-like structure).

**Actual Result:** _________
**PASS / FAIL:** _________

#### 5.9 🟢 EML (Email)

```bash
echo -e 'From: test@example.com\nTo: user@example.com\nSubject: Test\n\nHello world' > /tmp/q5/test.eml
opp /tmp/q5/test.eml --target-format md -o /tmp/q5/eml_out
```

**Expected Result:** ✅ MD extraction works. Email headers preserved in metadata.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 5.10 🟢 MSG (Outlook) — optional dependency

```bash
# Requires extract-msg pip package
# If not installed: should skip gracefully (not crash)
opp /tmp/q5/test.msg --target-format md -o /tmp/q5/msg_out
```

**Expected Result:** ✅ If `extract-msg` installed: extraction works. If not: graceful error message (not crash).

**Actual Result:** _________
**PASS / FAIL:** _________

#### 5.11 🟢 Image OCR (PNG/JPG)

```bash
# Requires tesseract or rapidocr
# Create a simple test image first
opp /tmp/q5/test.png --target-format md -o /tmp/q5/img_out
```

**Expected Result:** ✅ Text extracted from image via OCR. Output may contain OCR errors (expected for automated OCR).

**Actual Result:** _________
**PASS / FAIL:** _________

#### 5.12 🟢 XLSX (Excel)

Create minimal XLSX or use test fixture.

**Expected Result:** ✅ MD output contains table representation. Sheet names preserved.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 5.13 🔴 Unsupported format — detect + error

```bash
echo "binary data" > /tmp/q5/test.bin
opp /tmp/q5/test.bin --target-format md -o /tmp/q5/bin_out
```

**Expected Result:** ❌ Clear error message about unsupported format. Does NOT crash.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 5.14 🔴 Format detection without extension

```bash
cp /tmp/q5/test.html /tmp/q5/no_ext  # no .html extension
opp /tmp/q5/no_ext --target-format md -o /tmp/q5/noext_out
```

**Expected Result:** ✅ Detects format by magic bytes (not extension). Extraction succeeds.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q5 Verdict

| Format | detect | MD | XLIFF | Skeleton |
|--------|--------|----|-------|----------|
| DOCX | ⬜ | ⬜ | ⬜ | ⬜ |
| PPTX | ⬜ | ⬜ | ⬜ | ⬜ |
| PDF | ⬜ | ⬜ | ➖ (blocked) | ➖ |
| HTML | ⬜ | ⬜ | ⬜ | ➖ |
| CSV | ⬜ | ⬜ | ⬜ | ➖ |
| JSON | ⬜ | ⬜ | ⬜ | ➖ |
| XML | ⬜ | ⬜ | ⬜ | ➖ |
| EPUB | ⬜ | ⬜ | ⬜ | ⬜ |
| EML | ⬜ | ⬜ | ⬜ | ➖ |
| MSG | ⬜ | ⬜ | ⬜ | ➖ |
| Image | ⬜ | ⬜ | ➖ | ➖ |
| XLSX | ⬜ | ⬜ | ⬜ | ➖ |
| Unsupported | ✅ (error) | — | — | — |
| No extension | ✅ | ✅ | — | — |

**OVERALL: ⬜**

---

## Q6: Does every supported output format convert correctly?

**User says:** "I need my translated document as DOCX, but also as PDF for printing, EPUB for e-readers, and HTML for web."

**Why this matters:** ORF supports 16 output formats. Each has different conversion paths (pandoc vs pure-python). Some have dependencies.

### 6.1 🟢 ORF apply_md — All 16 formats (one test per format)

Create a test MD file with diverse content:

```bash
cat > /tmp/q6/test.md << 'EOF'
---
source_lang: en
target_lang: zh
---

# Test Document

This is a paragraph with **bold** and *italic* text.

## Section 1

- List item 1
- List item 2

> A blockquote

| Col1 | Col2 |
|------|------|
| A    | B    |

EOF
```

Then test each format:

| # | Format | Command | Expected |
|---|--------|---------|----------|
| 6.1a | DOCX | `orf apply-md test.md --target-format docx -o test.docx` | ✅ valid DOCX (ZIP) |
| 6.1b | ODT | `orf apply-md test.md --target-format odt -o test.odt` | ⚠️ FAKE_PANDOC stub |
| 6.1c | EPUB | `orf apply-md test.md --target-format epub -o test.epub` | ⚠️ FAKE_PANDOC stub |
| 6.1d | HTML | `orf apply-md test.md --target-format html -o test.html` | ✅ real HTML content |
| 6.1e | RTF | `orf apply-md test.md --target-format rtf -o test.rtf` | ⚠️ FAKE_PANDOC stub |
| 6.1f | PDF | `orf apply-md test.md --target-format pdf -o test.pdf` | ⚠️ FAKE_PANDOC stub |
| 6.1g | PPTX | `orf apply-md test.md --target-format pptx -o test.pptx` | ❌ may fail (md2pptx) |
| 6.1h | ICML | `orf apply-md test.md --target-format icml -o test.icml` | ⚠️ FAKE_PANDOC stub |
| 6.1i | SRT | `orf apply-md test.md --target-format srt -o test.srt` | ✅ real SRT (may be empty w/o timestamps) |
| 6.1j | CSV | `orf apply-md test.md --target-format csv -o test.csv` | ✅ real CSV |
| 6.1k | XLSX | `orf apply-md test.md --target-format xlsx -o test.xlsx` | ✅ real XLSX |
| 6.1l | XML | `orf apply-md test.md --target-format xml -o test.xml` | ✅ real XML |
| 6.1m | IPYNB | `orf apply-md test.md --target-format ipynb -o test.ipynb` | ⚠️ requires nbformat |
| 6.1n | EML | `orf apply-md test.md --target-format eml -o test.eml` | ✅ real EML |
| 6.1o | MSG | `orf apply-md test.md --target-format msg -o test.msg` | ❌ requires aspose-email-foss |
| 6.1p | JSON | `orf apply-md test.md --target-format json -o test.json` | ✅ real JSON |

**Actual Result:** _________
**PASS / FAIL:** _________

### 6.2 🔴 Unsupported format

```bash
orf apply-md test.md --target-format xyz -o test.xyz
```

**Expected Result:** ❌ Error message about unsupported format.

**Actual Result:** _________
**PASS / FAIL:** _________

### 6.3 🟢 Pure-python formats produce real content (not stubs)

For HTML (6.1d), CSV (6.1j), XLSX (6.1k), XML (6.1l), JSON (6.1p), EML (6.1n):
- Verify content is NOT a ZIP archive (stub DOCX is ZIP)
- Verify content has format-appropriate structure:
  - HTML: contains `<html>` or `<!DOCTYPE html>`
  - CSV: contains commas or tab separators
  - JSON: parseable as JSON
  - XML: has `<?xml` declaration or root element

**Actual Result:** _________
**PASS / FAIL:** _________

### 6.4 🟢 Pandoc-dependent formats produce stubs in FAKE_PANDOC mode

For DOCX (6.1a), ODT (6.1b), EPUB (6.1c), RTF (6.1e), ICML (6.1h):
- With `OMNI_TEST_FAKE_PANDOC=1`: file is a ZIP archive (stub DOCX)
- Without FAKE_PANDOC: real format (requires pandoc installed)

**Verify stub behavior:**
```python
import zipfile
assert zipfile.is_zipfile("/tmp/q6/test.docx")  # stub is ZIP
```

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q6 Verdict

| Format | Exists | Non-empty | Real content | Notes |
|--------|--------|-----------|--------------|-------|
| DOCX | ⬜ | ⬜ | ⬜ | FAKE_PANDOC stub |
| ODT | ⬜ | ⬜ | ➖ | FAKE_PANDOC stub |
| EPUB | ⬜ | ⬜ | ➖ | FAKE_PANDOC stub |
| HTML | ⬜ | ⬜ | ✅ | Pure python |
| RTF | ⬜ | ⬜ | ➖ | FAKE_PANDOC stub |
| PDF | ⬜ | ⬜ | ➖ | FAKE_PANDOC stub |
| PPTX | ⬜ | ⬜ | ⬜ | May fail without md2pptx |
| ICML | ⬜ | ⬜ | ➖ | FAKE_PANDOC stub |
| SRT | ⬜ | ⬜ | ⬜ | May be empty |
| CSV | ⬜ | ⬜ | ✅ | Pure python |
| XLSX | ⬜ | ⬜ | ✅ | Pure python |
| XML | ⬜ | ⬜ | ✅ | Pure python |
| IPYNB | ⬜ | ⬜ | ⬜ | Requires nbformat |
| EML | ⬜ | ⬜ | ✅ | Pure python |
| MSG | ⬜ | ⬜ | ❌ | GPLv3 restriction |
| JSON | ⬜ | ⬜ | ✅ | Pure python |

**OVERALL: ⬜**

---

# Part 3: Error & Boundary Matrix

---

## Q7: What happens when inputs are missing/corrupt/empty/huge?

**User says:** "What if I accidentally pass the wrong file path? What if the file is corrupted? What if it's a 1GB file?"

**Why this matters:** Real-world usage involves mistakes, bad data, and edge cases. The system should fail gracefully, not crash.

### Error Matrix

For each module (OPP, OL, ORF), test these boundary conditions:

| # | Condition | OPP | OL (translate_md) | OL (translate_xliff) | ORF (apply_md) |
|---|-----------|-----|-------------------|----------------------|-----------------|
| 7.1 | **Missing file** | `OPP_FILE_NOT_FOUND` | `OL_FILE_NOT_FOUND` (if glossary/config path) | `OL_FILE_NOT_FOUND` | `CLI_ERROR` (or PATH_NOT_ALLOWED) |
| 7.2 | **Empty file** | `OPP_INVALID_INPUT` | Success with empty translation | `OL_INVALID_INPUT` | `CLI_ERROR` |
| 7.3 | **Corrupt file** | `OPP_INVALID_INPUT` | N/A (text content, not file) | `OL_INVALID_INPUT` | `CLI_ERROR` |
| 7.4 | **Wrong format** | `OPP_INVALID_INPUT` | N/A | `OL_INVALID_INPUT` | `CLI_ERROR` |
| 7.5 | **Huge file (>100MB)** | `OPP_RESOURCE_EXHAUSTED` | May timeout (`OL_TIMEOUT`) | May timeout | May timeout |
| 7.6 | **Minimal content** | Empty MD | `""` → `""` | Empty `<source>` → error | `CLI_ERROR` |

#### 7.1 🔴 Missing file — all modules

```bash
opp /nonexistent.docx --target-format md -o /tmp/q7/opp       # → OPP_FILE_NOT_FOUND
ol translate-md /nonexistent.md -s en -t zh -o /tmp/q7/ol     # → OL_FILE_NOT_FOUND (config? or error)
orf apply-md /nonexistent.md --target-format docx -o out.docx  # → CLI_ERROR
```

**Expected Result:** ❌ Each returns error. Error CODE (OPP_FILE_NOT_FOUND, OL_FILE_NOT_FOUND, CLI_ERROR) is correct. Message is human-readable.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 7.2 🔴 Empty file — all modules

```bash
touch /tmp/q7/empty.docx /tmp/q7/empty.md /tmp/q7/empty.xlf

opp /tmp/q7/empty.docx --target-format md -o /tmp/q7/opp_empty       # → OPP_INVALID_INPUT
ol translate-md /tmp/q7/empty.md -s en -t zh -o /tmp/q7/ol_empty    # → success? empty output?
orf apply-md /tmp/q7/empty.md --target-format docx -o empty.docx     # → CLI_ERROR
```

**Expected Result:** ❌ OPP returns error. OL may return success with empty output (valid — no content to translate). ORF returns error.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 7.3 🔴 Corrupt file

```bash
echo "this is not a real docx" > /tmp/q7/corrupt.docx
echo "not xml" > /tmp/q7/corrupt.xlf

opp /tmp/q7/corrupt.docx --target-format md -o /tmp/q7/opp_corrupt    # → OPP_INVALID_INPUT
ol translate-xliff /tmp/q7/corrupt.xlf -s en -t zh -o /tmp/q7/ol_corrupt  # → OL_INVALID_INPUT
```

**Expected Result:** ❌ Both return appropriate errors. No crash, no traceback leak.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 7.4 🔴 Wrong format for tool

```bash
# Feed a DOCX to translate_xliff (expects XLIFF)
ol translate-xliff /tmp/q7/sample.docx -s en -t zh -o /tmp/q7/ol_wrong  # → OL_INVALID_INPUT
```

**Expected Result:** ❌ OL_INVALID_INPUT. Message mentions "XLIFF" or "XML" or "invalid".

**Actual Result:** _________
**PASS / FAIL:** _________

#### 7.5 🔴 Huge file test (if feasible)

Create a large MD file (>100MB):
```bash
# Create ~150MB file
for i in $(seq 1 1000000); do echo "Line $i with some padding text to make this line longer and increase the file size substantially" >> /tmp/q7/huge.md; done

ol translate-md /tmp/q7/huge.md -s en -t zh -o /tmp/q7/ol_huge -c Omni_Localizer/config/default.yaml
```

**Expected Result:** ⚠️ May timeout (`OL_TIMEOUT`) or exhaust resources. Should NOT crash with memory error.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 7.6 🟢 Minimal content — empty string translation

```python
from unittest.mock import patch
from tests.test_e2e_pipeline_fixtures import _FakeModelPool

with patch("ol_mcp.tools.ModelPool") as mock:
    mock.get_instance.return_value = _FakeModelPool()
    mock.return_value = _FakeModelPool()
    from ol_mcp.translate_md import translate_md_text
    from ol_mcp.tools import TranslateInput
    result = await translate_md_text(TranslateInput(
        content="",
        source_lang="en",
        target_lang="zh",
    ))
```

**Expected Result:** ✅ Success, translated content is empty string. Does NOT error on empty input.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q7 Verdict

| # | Condition | OPP | OL MD | OL XLIFF | ORF |
|---|-----------|-----|-------|----------|-----|
| 7.1 | Missing file | ⬜ | ⬜ | ⬜ | ⬜ |
| 7.2 | Empty file | ⬜ | ⬜ | ⬜ | ⬜ |
| 7.3 | Corrupt file | ⬜ | ⬜ | ⬜ | ➖ |
| 7.4 | Wrong format | ⬜ | ➖ | ⬜ | ➖ |
| 7.5 | Huge file | ⬜ | ⬜ | ⬜ | ⬜ |
| 7.6 | Minimal empty | ➖ | ✅ | ➖ | ➖ |

**OVERALL: ⬜**

---

## Q8: What happens at security boundaries?

**User says:** "Can someone use this to read my private files? Can they inject malicious paths?"

**Why this matters:** MCP servers have filesystem access. Path traversal and injection attacks must be blocked.

### Scenarios

#### 8.1 🔴 Path traversal — OPP MCP

```python
# Configure allowlist to only allow /tmp
import os; os.environ["OPP_MCP_ALLOWED_DIRS"] = "/tmp"
from opp.mcp.server import detect_format_tool

result = await detect_format_tool(file_path="/tmp/../etc/passwd")
```

**Expected Result:** ❌ `OPP_PATH_DENIED`. Message mentions "not allowed", "outside", or "traversal".

**Actual Result:** _________
**PASS / FAIL:** _________

#### 8.2 🔴 Path traversal — ORF MCP

```python
os.environ["ORF_MCP_ALLOWED_DIRS"] = "/tmp"
from orf.mcp.server import apply_md

result = apply_md(input_md="/tmp/../etc/passwd", target_format="docx", output_path="/tmp/out.docx")
```

**Expected Result:** ❌ `PATH_NOT_ALLOWED`.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 8.3 🔴 Symlink to restricted file — OPP

```bash
ln -s /etc/passwd /tmp/innocent.docx
# Try to read it
opp /tmp/innocent.docx --target-format md -o /tmp/q8/symlink_out
```

**Expected Result:** ❌ `OPP_PATH_DENIED` (symlinks to disallowed targets blocked).

**Actual Result:** _________
**PASS / FAIL:** _________

#### 8.4 🔴 Symlink — ORF

```bash
ln -s /etc/passwd /tmp/innocent.md
orf apply-md /tmp/innocent.md --target-format docx --output /tmp/q8/symlink_out.docx
```

**Expected Result:** ❌ `PATH_NOT_ALLOWED`.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 8.5 🔴 XLIFF image path injection

If an XLIFF contains an `<image file_path="/etc/passwd">` element:

**Expected Result:** ❌ `FILE_PATH_NOT_ALLOWED`. ORF rejects image paths outside working directory.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 8.6 🟢 Authentication — with MCP_SHARED_SECRET

```bash
export MCP_SHARED_SECRET=test-secret-123

# Call without auth token
opp mcp ping  # ← via MCP protocol
```

**Expected Result:** ❌ `AUTH_FAILED`. Call with correct token succeeds.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 8.7 🟢 No allowlist configured

```bash
unset OPP_MCP_ALLOWED_DIRS
opp /tmp/test.docx --target-format md -o /tmp/q8/noallow
```

**Expected Result:** ❌ `OPP_PATH_DENIED` (no paths allowed when allowlist is empty).

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q8 Verdict

| Scenario | Expected | Result |
|----------|----------|--------|
| 8.1 OPP path traversal | `OPP_PATH_DENIED` | ⬜ |
| 8.2 ORF path traversal | `PATH_NOT_ALLOWED` | ⬜ |
| 8.3 OPP symlink | `OPP_PATH_DENIED` | ⬜ |
| 8.4 ORF symlink | `PATH_NOT_ALLOWED` | ⬜ |
| 8.5 XLIFF image injection | `FILE_PATH_NOT_ALLOWED` | ⬜ |
| 8.6 Auth with MCP_SHARED_SECRET | `AUTH_FAILED` | ⬜ |
| 8.7 No allowlist | `OPP_PATH_DENIED` | ⬜ |

**OVERALL: ⬜**

---

## Q9: What happens with CJK, emoji, RTL, special characters?

**User says:** "My documents contain Chinese, Japanese, emoji 😊, Arabic text, and special characters like ©®™. Will they survive translation?"

**Why this matters:** Localization handles global content. Characters must survive extraction → translation → backfill intact.

### Scenarios

#### 9.1 🟢 CJK characters preserved through pipeline

Create a test file with Chinese text:
```bash
echo '# 中文测试文档

这是一段中文内容。包含简体中文和数字 123。

## 第二部分

- 列表项一
- 列表项二

> 引用文本' > /tmp/q9/cjk.md

# Round-trip through OL and ORF
export OMNI_TEST_FAKE_LLM=1 OMNI_TEST_FAKE_PANDOC=1
ol translate-md /tmp/q9/cjk.md -s zh -t en -c Omni_Localizer/config/default.yaml -o /tmp/q9/ol
orf apply-md /tmp/q9/ol/cjk.md --target-format docx --output /tmp/q9/orf/cjk.docx
```

**Expected Result:** ✅ CJK characters preserved in output. No garbled text, no `???` replacements, no mojibake.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 9.2 🟢 Emoji preserved

```bash
echo '# Test 😊🚀🌟
Paragraph with emoji: Hello 👋 World 🌍
And more: ❤️🔥🎉' > /tmp/q9/emoji.md

ol translate-md /tmp/q9/emoji.md -s en -t zh -c Omni_Localizer/config/default.yaml -o /tmp/q9/ol_emoji
```

**Expected Result:** ✅ Emoji characters preserved in output. Not stripped, not replaced with `??`.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 9.3 🟢 Special characters (©®™—±×÷∈∏∑)

```bash
echo '# Special: ©®™
Math: ±×÷∈∏∑
Dashes: —–-
Quotes: "" '' «»' > /tmp/q9/special.md

ol translate-md /tmp/q9/special.md -s en -t zh -c Omni_Localizer/config/default.yaml -o /tmp/q9/ol_special
```

**Expected Result:** ✅ Special characters preserved. Not converted/escaped incorrectly.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 9.4 🟢 Mixed CJK + Latin

```bash
echo '# 中文English混合
This is 中文 in a sentence.
API 接口 and 数据库 integration' > /tmp/q9/mixed.md

ol translate-md /tmp/q9/mixed.md -s zh -t en -c Omni_Localizer/config/default.yaml -o /tmp/q9/ol_mixed
```

**Expected Result:** ✅ Mixed content preserved. Latin characters not lost in CJK context.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 9.5 🟢 XML/HTML entities in source

```bash
echo '# Entities: &amp; &lt; &gt; &quot; &#39;
Code: <div class="test">Hello</div>' > /tmp/q9/entities.md

ol translate-md /tmp/q9/entities.md -s en -t zh -c Omni_Localizer/config/default.yaml -o /tmp/q9/ol_entities
```

**Expected Result:** ✅ Entities either preserved or properly decoded. No double-encoding (`&amp;amp;`).

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q9 Verdict

| Scenario | Result |
|----------|--------|
| 9.1 CJK characters | ⬜ |
| 9.2 Emoji | ⬜ |
| 9.3 Special characters | ⬜ |
| 9.4 Mixed CJK + Latin | ⬜ |
| 9.5 XML/HTML entities | ⬜ |

**OVERALL: ⬜**

---

## Q10: What happens with concurrent/parallel calls?

**User says:** "I need to process 10 documents simultaneously. Will the system handle it?"

**Why this matters:** Concurrency is essential for throughput. Tests resource management, race conditions, and server stability.

### Scenarios

#### 10.1 🟢 OL batch_translate_texts with concurrency

```python
from unittest.mock import patch
from tests.test_e2e_pipeline_fixtures import _FakeModelPool

with patch("ol_mcp.tools.ModelPool") as mock:
    mock.get_instance.return_value = _FakeModelPool()
    mock.return_value = _FakeModelPool()

    texts = [f"# Document {i}\n\nContent paragraph for doc {i}." for i in range(5)]
    from ol_mcp.tools import batch_translate_texts
    result = await batch_translate_texts(texts=texts, source_lang="en", target_lang="zh", concurrency=5)
```

**Expected Result:** ✅ All 5 texts translated. Results returned in order. No cross-contamination between texts.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 10.2 🟢 OPP batch 5 files concurrently

```python
from opp.mcp.server import extract_document

# Call extract_document for 5 files in parallel (use asyncio.gather)
```

**Expected Result:** ✅ All 5 files processed independently. One failure does not affect others.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 10.3 🟢 Repeated calls — server doesn't degrade

Call `ping` on each MCP server 10 times in sequence:
- OPP MCP: `ping`
- OL MCP: `ping`
- ORF MCP: `ping`

**Expected Result:** ✅ All 10 calls succeed. Response time doesn't increase significantly.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q10 Verdict

| Scenario | Result |
|----------|--------|
| 10.1 OL batch concurrency | ⬜ |
| 10.2 OPP batch concurrency | ⬜ |
| 10.3 Repeated ping (no degradation) | ⬜ |

**OVERALL: ⬜**

---

# Part 4: Production Trust

---

## Q11: Is the pipeline deterministic?

**User says:** "If I translate the same document twice with the same settings, will I get the same output?"

**Why this matters:** Non-determinism causes QA failures, cache misses, and trust issues. In FAKE_LLM mode, output MUST be byte-identical.

### Scenarios

#### 11.1 🟢 OPP extraction is deterministic

```bash
opp /tmp/q11/sample.docx --target-format both --source-lang en --target-lang zh -o /tmp/q11/run1
opp /tmp/q11/sample.docx --target-format both --source-lang en --target-lang zh -o /tmp/q11/run2

diff /tmp/q11/run1/*.md /tmp/q11/run2/*.md
diff /tmp/q11/run1/*.xlf /tmp/q11/run2/*.xlf
```

**Expected Result:** ✅ MD and XLIFF outputs are byte-identical between runs.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 11.2 🟢 OL FAKE_LLM translation is deterministic

```bash
ol translate-md /tmp/q11/sample.md -s en -t zh -c Omni_Localizer/config/default.yaml -o /tmp/q11/ol1
ol translate-md /tmp/q11/sample.md -s en -t zh -c Omni_Localizer/config/default.yaml -o /tmp/q11/ol2

diff /tmp/q11/ol1/*.md /tmp/q11/ol2/*.md
```

**Expected Result:** ✅ Outputs are byte-identical.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 11.3 🟢 ORF FAKE_PANDOC conversion is deterministic

```bash
orf apply-md /tmp/q11/sample.md --target-format docx --output /tmp/q11/orf1.docx
orf apply-md /tmp/q11/sample.md --target-format docx --output /tmp/q11/orf2.docx

diff /tmp/q11/orf1.docx /tmp/q11/orf2.docx
```

**Expected Result:** ✅ Outputs are byte-identical.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 11.4 ⚠️ Known non-determinism: EPUB extraction

Per `ACCEPTED_GAPS.md`: EPUB extraction is non-deterministic (8/8 cells produce different MD5 between runs).

```bash
opp /tmp/q11/sample.epub --target-format md -o /tmp/q11/epub1
opp /tmp/q11/sample.epub --target-format md -o /tmp/q11/epub2

diff /tmp/q11/epub1/*.md /tmp/q11/epub2/*.md
```

**Expected Result:** ❌ Files DIFFER (known issue). Root cause: `ebooklib` returns items in non-deterministic order.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q11 Verdict

| Scenario | Expected | Result |
|----------|----------|--------|
| 11.1 OPP deterministic | ✅ identical | ⬜ |
| 11.2 OL FAKE_LLM deterministic | ✅ identical | ⬜ |
| 11.3 ORF FAKE_PANDOC deterministic | ✅ identical | ⬜ |
| 11.4 EPUB known non-determinism | ❌ different | ⬜ |

**OVERALL: ⬜**

---

## Q12: Are CLI and MCP outputs equivalent?

**User says:** "Does it matter whether I use the CLI or the MCP API? Will I get the same result?"

**Why this matters:** Users access the system through both CLI and MCP. They should produce equivalent results.

### Scenarios

#### 12.1 🟢 OPP CLI vs MCP — MD extraction

Compare output of:
- CLI: `opp sample.docx --target-format md -o /tmp/q12/cli`
- MCP: `generate_markdown(file_path="sample.docx")`

```bash
diff /tmp/q12/cli/*.md /tmp/q12/mcp/*.md
```

**Expected Result:** ✅ MD content is functionally equivalent (may have minor metadata differences like timestamps).

**Actual Result:** _________
**PASS / FAIL:** _________

#### 12.2 🟢 OPP CLI vs MCP — XLIFF extraction

Compare:
- CLI: `opp sample.docx --target-format xlf --source-lang en --target-lang zh -o /tmp/q12/xlf_cli`
- MCP: `generate_xliff(file_path="sample.docx", source_lang="en", target_lang="zh")`

**Expected Result:** ✅ XLIFF content is equivalent (trans-units match).

**Actual Result:** _________
**PASS / FAIL:** _________

#### 12.3 🟢 ORF CLI vs MCP — DOCX output

Compare:
- CLI: `orf apply-md sample.md --target-format docx --output /tmp/q12/cli.docx`
- MCP: `apply_md(input_md="sample.md", target_format="docx", output_path="/tmp/q12/mcp.docx")`

**Expected Result:** ✅ Both produce valid DOCX files. Content structure matches.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q12 Verdict

| Scenario | Result |
|----------|--------|
| 12.1 OPP MD CLI vs MCP | ⬜ |
| 12.2 OPP XLIFF CLI vs MCP | ⬜ |
| 12.3 ORF DOCX CLI vs MCP | ⬜ |

**OVERALL: ⬜**

---

## Q13: Are images preserved through the XLIFF path?

**User says:** "My DOCX has images. Will they survive translation and come out in the right place?"

**Why this matters:** Image preservation is the key differentiator between MD path (no images) and XLIFF path (images preserved). This is a core feature.

### Scenarios

#### 13.1 🟢 Haier DOCX — all 7 unique images preserved

```python
from pathlib import Path
from tests.test_e2e_pipeline_full import (
    _run_opp, _translate_xliff_in_process,
    _extract_image_positions_from_docx,
    _count_unique_images_by_data_hash,
    HAIER_DOCX,
)
import asyncio

# Full XLIFF pipeline
opp = asyncio.run(_run_opp("cli", HAIER_DOCX, tmp_path / "opp", "zh", "en"))

xliff_text = opp.xliff_path.read_text(encoding="utf-8")
translated = tmp_path / "ol" / opp.xliff_path.name
asyncio.run(_translate_xliff_in_process(xliff_text, translated, "zh", "en"))

# ORF backfill with image injection
import subprocess, sys
result = subprocess.run([
    sys.executable, "-m", "orf.cli", "apply-xliff",
    str(opp.skeleton_path), "--xliff", str(translated),
    "--output", str(tmp_path / "orf/result.docx"),
    "--format", "docx",
    "--images-json", str(opp.images_json_path),
], capture_output=True, text=True)
assert result.returncode == 0

# Count unique images by data hash (NOT by paragraph_index — see Q6)
positions = _extract_image_positions_from_docx(tmp_path / "orf/result.docx")
unique = _count_unique_images_by_data_hash(positions)
```

**Expected Result:** ✅ `unique == 7`. All 7 unique images from the Haier DOCX are present in the final output.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 13.2 🟢 No duplicate images in output

The final DOCX should have the same number of `<w:drawing>` elements as the source.

```python
from lxml import etree
import zipfile

def count_drawings(docx_path):
    with zipfile.ZipFile(docx_path) as zf:
        doc_xml = zf.read("word/document.xml")
    tree = etree.fromstring(doc_xml)
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    return len(tree.findall(f".//{ns}drawing"))

source_count = count_drawings(HAIER_DOCX)
final_count = count_drawings(tmp_path / "orf/result.docx")
```

**Expected Result:** ✅ `source_count == final_count`. No duplicate images injected. Regression guard for the v0.4.3 inline-image dedup fix.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 13.3 🟢 MD path produces 0 images

The MD path (OPP→MD→OL→ORF) does NOT inject images.

```python
# Run MD path pipeline
# Verify: final DOCX has 0 drawings
assert count_drawings(md_path_docx) == 0
```

**Expected Result:** ✅ 0 drawings in MD path output.

**Actual Result:** _________
**PASS / FAIL:** _________

#### 13.4 🟢 Floating images preserved (`wp:anchor`)

OPP marks floating images with `is_floating: true`. ORF should inject `wp:anchor` instead of `wp:inline`.

**Verify:**
```python
# Check that the source DOCX has wp:anchor elements
# Verify the final DOCX also has wp:anchor elements
```

**Expected Result:** ✅ Floating images in source → floating images in output.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q13 Verdict

| Scenario | Result |
|----------|--------|
| 13.1 7 unique images preserved | ⬜ |
| 13.2 No duplicate images | ⬜ |
| 13.3 MD path has 0 images | ⬜ |
| 13.4 Floating images preserved | ⬜ |

**OVERALL: ⬜**

---

## Q14: Are the 195-cell format matrix results intact?

**User says:** "Can I be sure that all format combinations work? What's the known status?"

**Why this matters:** The format matrix is the definitive measure of system coverage. 195 cells (11 inputs × 15 outputs MD + 6 inputs × 5 outputs XLIFF). 131 expected pass, 64 expected skip, 0 expected fail.

### 14.1 🟢 Run format matrix verifier

```bash
OMNI_TEST_FAKE_LLM=1 OMNI_TEST_FAKE_PANDOC=1 \
  .venv_ol/bin/python scripts/format_matrix_verifier.py \
  --out-dir test_artifacts/matrix --path-filter both --parallel 8 --timeout 120
```

**Expected Result:** ✅ **131 PASS, 64 SKIP, 0 FAIL** in ~5-6 min.

**Actual Result:** _________
**PASS / FAIL:** _________

### 14.2 🟢 Compare against ACCEPTED_GAPS.md

Check that the skip categories match `ACCEPTED_GAPS.md`:
- 11 MD→JSON skips
- 11 MD→SRT skips
- 15 MD→PPTX skips (no md2pptx CLI)
- 20 XLIFF skips (no skeleton for non-OOXML)
- 5 Cross-format XLIFF skips
- 2 PPTX→XLSX / XLSX→PPTX skips

**Expected Result:** ✅ Skip counts match documented gaps.

**Actual Result:** _________
**PASS / FAIL:** _________

### 14.3 🔴 Verify 0 FAIL

Any cell marked FAIL is a regression. NO failures should exist.

**Expected Result:** ✅ Zero failures.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q14 Verdict

| Scenario | Result |
|----------|--------|
| 14.1 Matrix run: 131/64/0 | ⬜ |
| 14.2 Skips match ACCEPTED_GAPS | ⬜ |
| 14.3 Zero failures | ⬜ |

**OVERALL: ⬜**

---

# Part 5: Final Verdict

---

# Part 5: Production Validation (Real LLM · Real Pandoc · Performance)

---

## Q15: Does real LLM translation produce acceptable quality?

**User says:** "FAKE_LLM just returns `[ZH]` markers. I need to know the actual translation quality is good enough for production."

**Why this matters:** This is the entire reason the pipeline exists. FAKE_LLM mode validates structure; real LLM mode validates value.

**Prerequisites:**
- `.env` must have at least one real API key (Zhipu, Agnes, NVIDIA, or OpenCode Go)
- `OMNI_TEST_FAKE_LLM` must NOT be set
- Config: `Omni_Localizer/config/local.yaml` (real LLM config)

```bash
export OMNI_RUN_REAL_LLM=1
unset OMNI_TEST_FAKE_LLM
```

### 15.1 🟢 Run existing nightly LQA tests (Tier 3)

The existing `test_e2e_real_llm.py` has LQA tests. Run them:

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
source .env  # load real API keys
unset OMNI_TEST_FAKE_LLM
export OMNI_RUN_REAL_LLM=1

pytest tests/test_e2e_real_llm.py -v -m "nightly and not slow" --timeout 600
```

**Expected Result:**
- ✅ All LQA tests pass (LQA score ≥ 5.0/10 on 4-dim rubric)
- ✅ All pipeline tests complete (Tier 1 + Tier 2)
- ✅ Tier 4 format coverage tests pass (EPUB, HTML)

**Thresholds (from existing tests):**
- LQA average ≥ 5.0 (adequacy, fluency, terminology, format)
- Each dimension ≥ 3.0 (no catastrophic failure in any dimension)
- Translation produces real translated text (not meta-commentary)

**Actual Result:** _________
**PASS / FAIL:** _________

### 15.2 🟢 Real translation produces actual translated content

```bash
ol translate-md /tmp/q15/test.md -s zh -t en -c Omni_Localizer/config/local.yaml -o /tmp/q15/ol
```

**Verify:** Output file contains real English text, NOT `[EN]` markers.
- ✅ Content is actual translated English (sentences make sense)
- ✅ No `[EN]` or `[ZH]` placeholder markers in output
- ✅ YAML frontmatter present with translation metadata

**Actual Result:** _________
**PASS / FAIL:** _________

### 15.3 🟢 Punctuation normalizer works with real LLM output

Run zh→en translation on Chinese source. Verify:
- ✅ Full-width Chinese punctuation（，。！）→ ASCII (, . !)
- ✅ No residual Chinese punctuation in English output
- ✅ CJK characters correctly translated (not left untranslated)

Run en→zh on English source. Verify:
- ✅ ASCII punctuation ,.;: → Chinese ，。；：
- ✅ Quotation marks converted to Chinese-style 「」

**Actual Result:** _________
**PASS / FAIL:** _________

### 15.4 🟢 Glossary terms respected in translation

Create a glossary JSON and translate with `--glossary`:

```bash
echo '{"API endpoint": {"translation": "API 接口", "confidence": 0.95}}' > /tmp/q15/glossary.json
ol translate-md /tmp/q15/test.md -s en -t zh -c Omni_Localizer/config/local.yaml -o /tmp/q15/glossary_out --glossary /tmp/q15/glossary.json
```

**Verify:** The term "API endpoint" is translated as "API 接口" consistently.

**Actual Result:** _________
**PASS / FAIL:** _________

### 15.5 🟢 LQA auto-retry works (existing tests)

When `enable_lqa: true` and score < `lqa_threshold`, OL retries. Use existing test suites:

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate

# Run the dedicated LQA auto-invoke unit tests (mocked LLM, no API key needed)
pytest tests/test_ol_lqa_autoinvoke.py -v --timeout 120
```

**Expected Result:** ✅ All LQA tests pass, including:
- `test_lqa_default_no_retry` — `enable_lqa=False` calls translate once
- `test_lqa_retry_happens` — score < threshold triggers retry
- `test_lqa_best_of_n` — best-of-N picking works
- `test_lqa_max_retries_exhausted` — retry exhaustion produces warnings
- `test_lqa_no_retry_when_judge_high` — high score suppresses retry

```bash
# Also run the XLIFF + LQA + image placement E2E test (uses real config with enable_lqa: true)
export OMNI_TEST_FAKE_LLM=1
pytest tests/test_e2e_xliff_lqa_image_placement.py -v --timeout 120
```

**Expected Result:** ✅ XLIFF+LQA integration test passes. Translation + LQA judge activated for each unit.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q15 Verdict

| Scenario | Result |
|----------|--------|
| 15.1 Existing nightly LQA tests | ⬜ |
| 15.2 Real translation content | ⬜ |
| 15.3 Punctuation normalizer | ⬜ |
| 15.4 Glossary term adherence | ⬜ |
| 15.5 LQA auto-retry | ⬜ |

**OVERALL: ⬜**

---

## Q16: Does real pandoc produce valid format output?

**User says:** "I've been testing with FAKE_PANDOC stubs. I need to know the real EPUB/PDF/RTF output is valid."

**Why this matters:** FAKE_PANDOC writes a stub DOCX regardless of target format. Real pandoc produces format-specific files.

**Prerequisite:** `pandoc 3.9` is installed (verified on this machine).

```bash
unset OMNI_TEST_FAKE_PANDOC  # USE REAL PANDOC
```

### 16.1 🟢 Real DOCX output — full structure validation

```bash
export OMNI_TEST_FAKE_LLM=1
unset OMNI_TEST_FAKE_PANDOC

orf apply-md /tmp/q16/test.md --target-format docx --output /tmp/q16/real/result.docx
```

**Verify (beyond FAKE_PANDOC stub checks):**
- ✅ DOCX is valid (ZIP + `word/document.xml`)
- ✅ `[Content_Types].xml` exists and is well-formed
- ✅ `word/styles.xml` exists (pandoc-generated styles)
- ✅ `docProps/core.xml` exists (metadata)
- ✅ Document opens without corruption (python-docx can read it)
- ✅ Content matches expected markdown structure (headings → heading styles)

```python
from docx import Document
doc = Document("/tmp/q16/real/result.docx")
assert len(doc.paragraphs) > 0
assert doc.paragraphs[0].style.name.startswith("Heading")  # H1 is heading
```

**Actual Result:** _________
**PASS / FAIL:** _________

### 16.2 🟢 Real EPUB output — validate EPUB structure

```bash
orf apply-md /tmp/q16/test.md --target-format epub --output /tmp/q16/real/result.epub
```

**Verify EPUB-specific structure:**
- ✅ File starts with `mimetype` entry containing `application/epub+zip`
- ✅ `META-INF/container.xml` exists
- ✅ Content OPF file exists and is valid XML
- ✅ EPUB is a valid ZIP with proper ordering (mimetype first, no compression)

```bash
# Check mimetype first entry in ZIP
python3 -c "
import zipfile
with zipfile.ZipFile('/tmp/q16/real/result.epub') as z:
    names = z.namelist()
    assert names[0] == 'mimetype', f'First entry should be mimetype, got {names[0]}'
    assert z.read('mimetype') == b'application/epub+zip'
    assert 'META-INF/container.xml' in names
    print('✅ Valid EPUB structure')
"
```

**Actual Result:** _________
**PASS / FAIL:** _________

### 16.3 🟢 Real HTML output — validate HTML5 structure

```bash
orf apply-md /tmp/q16/test.md --target-format html --output /tmp/q16/real/result.html
```

**Verify:**
- ✅ Contains `<!DOCTYPE html>` declaration
- ✅ Contains `<html>`, `<head>`, `<body>` tags
- ✅ Markdown headings convert to `<h1>`, `<h2>`, etc.
- ✅ Lists convert to `<ul>`/`<ol>`
- ✅ Tables convert to `<table>`
- ✅ No pandoc stub content (not a ZIP file)

```bash
file /tmp/q16/real/result.html  # Should be "HTML document" not "Zip archive"
head -5 /tmp/q16/real/result.html  # Should start with <!DOCTYPE html>
```

**Actual Result:** _________
**PASS / FAIL:** _________

### 16.4 🟢 Real PDF output — validate PDF structure

```bash
orf apply-md /tmp/q16/test.md --target-format pdf --output /tmp/q16/real/result.pdf
```

**Verify:**
- ✅ File starts with `%PDF-1.x` header
- ✅ Has at least 1 page
- ✅ Text content is extractable (not just images)

```bash
head -c 10 /tmp/q16/real/result.pdf  # Should start with %PDF-
python3 -c "
with open('/tmp/q16/real/result.pdf', 'rb') as f:
    header = f.read(8)
    assert header.startswith(b'%PDF-'), f'Bad PDF header: {header}'
    print('✅ Valid PDF header')
"
```

**Actual Result:** _________
**PASS / FAIL:** _________

### 16.5 🟢 All 16 formats with real pandoc — validate each

```bash
for fmt in docx odt epub html rtf pdf; do
  unset OMNI_TEST_FAKE_PANDOC
  orf apply-md /tmp/q16/test.md --target-format $fmt --output /tmp/q16/full/result.$fmt
  echo "--- $fmt: $? ---"
done
```

**Expected:**
- docx: ✅ valid DOCX
- odt: ✅ valid ODT (ZIP with `content.xml`)
- epub: ✅ valid EPUB (mimetype first)
- html: ✅ real HTML (not ZIP)
- rtf: ✅ valid RTF (starts with `{\rtf`)
- pdf: ✅ valid PDF (starts with `%PDF-`)

**Note:** FAKE_PANDOC format (icml, pptx, etc.) still need FAKE_PANDOC or real dependencies.

**Actual Result:** _________
**PASS / FAIL:** _________

### 16.6 🔴 Real pandoc output has correct content

Compare real pandoc output content against source markdown:
- ✅ All headings present (same content, potentially reformatted)
- ✅ All paragraphs present
- ✅ All list items present
- ✅ Table structure preserved (rows × columns match)

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q16 Verdict

| Scenario | Result |
|----------|--------|
| 16.1 Real DOCX full validation | ⬜ |
| 16.2 Real EPUB structure | ⬜ |
| 16.3 Real HTML structure | ⬜ |
| 16.4 Real PDF structure | ⬜ |
| 16.5 All 6 pandoc formats | ⬜ |
| 16.6 Content fidelity | ⬜ |

**OVERALL: ⬜**

---

## Q17: Does performance meet production thresholds?

**User says:** "How long does it take to translate a 50-page document? Will the server hold up under load?"

**Why this matters:** Performance determines whether the system is usable for real workloads. The 14MB slim DOCX (7,681 paragraphs, 390 images) is the stress test.

**Prerequisites:**
- `（slim）爱上海尔.docx` (14MB, exists) for large document testing
- Existing benchmark infrastructure in `tests/benchmarks/`

### 17.1 🟢 OPP extraction performance (existing test)

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate

pytest tests/test_e2e_performance.py -v --timeout 300
```

**Expected thresholds (from existing tests):**
- ✅ Large synthetic DOCX (200 paragraphs): extraction < 30s
- ✅ Real slim DOCX (14MB, 7,681 paragraphs): extraction < 120s
- ✅ Peak memory < 500MB for slim DOCX
- ✅ Memory growth over 5 runs < 50MB (no leak)
- ✅ Throughput > 1 doc/min

**Actual Result:** _________
**PASS / FAIL:** _________

### 17.2 🟢 OL translation throughput (existing benchmark)

```bash
pytest tests/benchmarks/test_translation_throughput.py -v --timeout 300
```

**Expected Result:** ✅ Translation throughput is measured and reported in chars/sec or docs/min.

**Actual Result:** _________
**PASS / FAIL:** _________

### 17.3 🟢 ORF conversion throughput (existing benchmark)

```bash
pytest tests/benchmarks/test_backfill_throughput.py -v --timeout 300
```

**Expected Result:** ✅ Conversion throughput is measured and reported.

**Actual Result:** _________
**PASS / FAIL:** _________

### 17.4 🟢 OPP extraction throughput (existing benchmark)

```bash
pytest tests/benchmarks/test_extraction_throughput.py -v --timeout 300
```

**Expected Result:** ✅ Extraction throughput measured.

**Actual Result:** _________
**PASS / FAIL:** _________

### 17.5 🟢 Full pipeline E2E timing (real LLM)

```bash
unset OMNI_TEST_FAKE_LLM
source .env  # load real API keys

time ( \
  opp "爱上海尔_第二章_全球创牌 - E2E测试专用.docx" --target-format both --source-lang zh --target-lang en -o /tmp/q17/opp && \
  ol translate-md /tmp/q17/opp/*.md -s zh -t en -c Omni_Localizer/config/local.yaml -o /tmp/q17/ol && \
  orf apply-md /tmp/q17/ol/*.md --target-format docx --output /tmp/q17/orf/result.docx \
)
```

**Expected Result:**
- ✅ Total time < 10 minutes (acceptable for a 447KB document with real LLM)
- ✅ Each step completes without timeout

**Actual Result:** _________
**PASS / FAIL:** _________

### 17.6 🟢 Full pipeline E2E timing (FAKE_LLM — baseline)

Same as 17.5 but with `OMNI_TEST_FAKE_LLM=1`:

```bash
export OMNI_TEST_FAKE_LLM=1
time ( \
  opp "爱上海尔_第二章_全球创牌 - E2E测试专用.docx" --target-format both --source-lang zh --target-lang en -o /tmp/q17/fake_opp && \
  ol translate-md /tmp/q17/fake_opp/*.md -s zh -t en -c Omni_Localizer/config/default.yaml -o /tmp/q17/fake_ol && \
  orf apply-md /tmp/q17/fake_ol/*.md --target-format docx --output /tmp/q17/fake_orf/result.docx \
)
```

**Expected Result:**
- ✅ Total time < 30 seconds (FAKE_LLM is instant)
- ✅ Baseline for comparing real LLM overhead

**Actual Result:** _________
**PASS / FAIL:** _________

### 17.7 🟢 Real LLM pipeline: big document (14MB slim DOCX)

```bash
unset OMNI_TEST_FAKE_LLM
source .env
time ( \
  opp "（slim）爱上海尔.docx" --target-format md --source-lang zh --target-lang en -o /tmp/q17/big_opp && \
  ol translate-md /tmp/q17/big_opp/*.md -s zh -t en -c Omni_Localizer/config/local.yaml -o /tmp/q17/big_ol \
)
```

**Expected:**
- ✅ OPP extraction: <120s, memory <500MB
- ⚠️ OL translation of 7,681 paragraphs may take 30+ minutes with real LLM
- This test is FOR INFORMATIONAL PURPOSES — may exceed CI time limits

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q17 Verdict

| Scenario | Result |
|----------|--------|
| 17.1 OPP extraction perf | ⬜ |
| 17.2 OL translation throughput | ⬜ |
| 17.3 ORF conversion throughput | ⬜ |
| 17.4 OPP extraction throughput | ⬜ |
| 17.5 Pipeline timing (real LLM) | ⬜ |
| 17.6 Pipeline timing (FAKE_LLM baseline) | ⬜ |
| 17.7 Big document (14MB) | ⬜ |

**OVERALL: ⬜**

---

## Q18: Does multi-provider failover work?

**User says:** "What if one LLM provider goes down? Will the system fall back to another provider?"

**Why this matters:** Production reliability depends on failover. The config has 5 translation providers in priority order. When primary fails, backup should take over.

**Prerequisites:** All 4 real API keys configured (Zhipu, Agnes, NVIDIA, OpenCode Go)

### 18.1 🟢 Each provider translates independently

Test each configured provider by temporarily editing the config to only include one provider:

```bash
# Test with Zhipu only (priority 1)
ol translate-md /tmp/q18/test.md -s en -t zh -c Omni_Localizer/config/local.yaml -o /tmp/q18/zhipu
# Verify: translation produced, real Chinese content

# Test with Agnes only
# (edit local.yaml to only include agnes provider)
ol translate-md /tmp/q18/test.md -s en -t zh -c /tmp/q18/agnes_only.yaml -o /tmp/q18/agnes
# Verify: translation produced

# Test with NVIDIA NIM only
ol translate-md /tmp/q18/test.md -s en -t zh -c /tmp/q18/nvidia_only.yaml -o /tmp/q18/nvidia
# Verify: translation produced
```

**Expected Result:** ✅ Each provider produces a valid translation when used alone.

**Actual Result:** _________
**PASS / FAIL:** _________

### 18.2 🔴 Primary provider fails → backup takes over

Simulate primary provider failure by setting an invalid API key for the primary:

```yaml
# local_failover.yaml — same as local.yaml but ZHIPU_API_KEY is deliberately wrong
llm_pool:
  translation:
    - provider: "openai"
      model: "glm-4-flash"
      api_key: "${ZHIPU_API_KEY}"
      # ... but ZHIPU_API_KEY is set to "INVALID_KEY"
```

```bash
export ZHIPU_API_KEY=INVALID_KEY
ol translate-md /tmp/q18/test.md -s en -t zh -c /tmp/q18/local_failover.yaml -o /tmp/q18/failover
```

**Expected Result:**
- ✅ Translation STILL succeeds (falls back to Agnes or NVIDIA)
- ✅ Warning or info message about primary failure
- ✅ Output is valid translation (not error)

**Actual Result:** _________
**PASS / FAIL:** _________

### 18.3 🔴 All providers fail → graceful error

```bash
export ZHIPU_API_KEY=INVALID
export AGNES_API_KEY=INVALID
export NVIDIA_NIM_API_KEY=INVALID
export OPENCODE_GO_KEY=INVALID

ol translate-md /tmp/q18/test.md -s en -t zh -c Omni_Localizer/config/local.yaml -o /tmp/q18/all_fail
```

**Expected Result:**
- ❌ Translation fails (no valid provider)
- ✅ Error message clearly states "all providers failed" or "no valid API key"
- ✅ Does NOT crash with unhandled exception
- ✅ Returns non-zero exit code

**Actual Result:** _________
**PASS / FAIL:** _________

### 18.4 🟢 Rate limiting handled gracefully

NVIDIA NIM free tier is capped at 40 RPM. Test by sending multiple concurrent translation requests:

```python
import asyncio
from ol_mcp.translate_md import translate_md_text
from ol_mcp.tools import TranslateInput

async def stress_test():
    tasks = []
    for i in range(10):
        tasks.append(translate_md_text(TranslateInput(
            content=f"# Document {i}\n\nTest paragraph content here.",
            source_lang="en", target_lang="zh",
            config_path="Omni_Localizer/config/local.yaml",
        )))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

**Expected Result:**
- ✅ All 10 requests complete (may retry on rate limit)
- ✅ No crashes from rate limiting
- ✅ Some requests may be slower (rate-limited retries)

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q18 Verdict

| Scenario | Result |
|----------|--------|
| 18.1 Each provider works independently | ⬜ |
| 18.2 Primary fails → backup takes over | ⬜ |
| 18.3 All providers fail → graceful error | ⬜ |
| 18.4 Rate limiting handled | ⬜ |

**OVERALL: ⬜**

---

## Q19: Can the system run continuously without degradation?

**User says:** "I need to run 100 documents through the pipeline. Will it slow down or leak memory over time?"

**Why this matters:** Memory leaks and performance degradation are production killers. This validates long-running stability.

### 19.1 🟢 10 consecutive OPP extractions — memory stable

```python
import tracemalloc
from pathlib import Path
from opp.pipeline import OPPPipeline

pipeline = OPPPipeline(resource_storage_dir="/tmp/q19/resources")
tracemalloc.start()

sizes = []
for i in range(10):
    result = pipeline.process_file("/mnt/d/贯维/Omni_Suite/（slim）爱上海尔.docx")
    current, peak = tracemalloc.get_traced_memory()
    sizes.append(current)
    print(f"Run {i+1}: {current/1024/1024:.1f}MB (peak: {peak/1024/1024:.1f}MB)")

tracemalloc.stop()
growth = sizes[-1] - sizes[0]
```

**Expected Result:**
- ✅ Memory growth over 10 runs < 100MB
- ✅ No single run shows significant jump (>200MB increase)
- ✅ All 10 runs succeed

**Actual Result:** _________
**PASS / FAIL:** _________

### 19.2 🟢 10 consecutive pipeline runs — no crash

```bash
for i in $(seq 1 10); do
  opp "爱上海尔_第二章_全球创牌 - E2E测试专用.docx" --target-format both --source-lang zh --target-lang en -o /tmp/q19/run_$i
  echo "Run $i: $?"
done
```

**Expected Result:** ✅ All 10 runs succeed (exit code 0). No crash, no file handle leak.

**Actual Result:** _________
**PASS / FAIL:** _________

### 19.3 🟢 File handle leak check

After 19.2, verify the system can still process files:
```bash
opp "爱上海尔_第二章_全球创牌 - E2E测试专用.docx" --target-format md -o /tmp/q19/final_check
echo "Final check: $?"
```

**Expected Result:** ✅ Still works. No "too many open files" errors.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q19 Verdict

| Scenario | Result |
|----------|--------|
| 19.1 10x OPP — memory stable | ⬜ |
| 19.2 10x pipeline — no crash | ⬜ |
| 19.3 File handle leak check | ⬜ |

**OVERALL: ⬜**

---

## Q20: Does the real MCP server work via stdio process?

**User says:** "I've been testing MCP tools by importing Python modules in-process. But in production, MCP runs as a separate process. Does the stdio protocol actually work?"

**Why this matters:** All in-process MCP testing bypasses the actual MCP transport layer. Process-level testing validates the real protocol.

**Note:** `scripts/mcp_bridge.py` was deleted in a previous refactor. The alternatives below use:
- `scripts/verify_mcp.py` — subprocess pytest runner for the MCP smoke test suite
- `scripts/mcp_matrix_verifier.py` — subprocess MCP matrix runner
- Direct JSON-RPC over stdio for raw protocol tests
- Python subprocess for targeted tool tests

### 20.1 🟢 OPP MCP server — run MCP smoke test suite (subprocess)

This runs the comprehensive MCP smoke test suite as a real subprocess (not in-process), testing all 7 OPP tools, 8 OL tools, and 6 ORF tools through the actual stdio transport:

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
export OMNI_TEST_FAKE_LLM=1
export OMNI_TEST_FAKE_PANDOC=1

python3 scripts/verify_mcp.py
```

**Expected Result:** ✅ All 3 MCP groups pass (OPP MCP, OL MCP, ORF MCP). Output shows `✅ All MCP tests passed`.

**Actual Result:** _________
**PASS / FAIL:** _________

### 20.2 🟢 OPP MCP — raw JSON-RPC ping over stdio

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
export OMNI_TEST_FAKE_LLM=1

echo '{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}' | \
  timeout 10 opp mcp 2>/dev/null
```

**Expected Result:** ✅ MCP server responds with a JSON-RPC response containing `"success": true`. No crash on invalid input.

**Actual Result:** _________
**PASS / FAIL:** _________

### 20.3 🟢 OPP MCP — generate_markdown via subprocess

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
export OMNI_TEST_FAKE_LLM=1
export OMNI_TEST_FAKE_PANDOC=1

python3 -c "
import subprocess, json, sys
from pathlib import Path

# Build a JSON-RPC request for generate_markdown
docx = Path('/mnt/d/贯维/Omni_Suite/爱上海尔_第二章_全球创牌 - E2E测试专用.docx')
request = {
    'jsonrpc': '2.0',
    'id': 1,
    'method': 'tools/call',
    'params': {
        'name': 'generate_markdown',
        'arguments': {
            'file_path': str(docx),
            'output_path': '/tmp/q20/opp_out.md'
        }
    }
}

proc = subprocess.run(
    ['opp', 'mcp'],
    input=json.dumps(request),
    capture_output=True, text=True, timeout=30,
    env={**__import__('os').environ, 'OMNI_TEST_FAKE_LLM': '1'}
)
print('STDOUT:', proc.stdout[:500])
print('STDERR:', proc.stderr[:500] if proc.stderr else '(none)')
print('RC:', proc.returncode)
"
```

**Expected Result:** ✅ Subprocess returns. JSON-RPC response indicates success. MD file produced at `/tmp/q20/opp_out.md`.

**Actual Result:** _________
**PASS / FAIL:** _________

### 20.4 🟢 OL MCP — translate_md_text via subprocess

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
export OMNI_TEST_FAKE_LLM=1

echo "# Hello World" > /tmp/q20/test.md

python3 -c "
import subprocess, json

request = {
    'jsonrpc': '2.0',
    'id': 1,
    'method': 'tools/call',
    'params': {
        'name': 'translate_md_text',
        'arguments': {
            'content': '# Hello World',
            'source_lang': 'en',
            'target_lang': 'zh'
        }
    }
}

proc = subprocess.run(
    ['ol', 'mcp'],
    input=json.dumps(request),
    capture_output=True, text=True, timeout=30,
    env={**__import__('os').environ, 'OMNI_TEST_FAKE_LLM': '1'}
)
print('STDOUT:', proc.stdout[:500])
print('RC:', proc.returncode)
"
```

**Expected Result:** ✅ JSON-RPC response with translated text content (contains `[ZH]` markers since FAKE_LLM is set).

**Actual Result:** _________
**PASS / FAIL:** _________

### 20.5 🟢 ORF MCP — apply_md via subprocess

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
export OMNI_TEST_FAKE_LLM=1
export OMNI_TEST_FAKE_PANDOC=1

python3 -c "
import subprocess, json

request = {
    'jsonrpc': '2.0',
    'id': 1,
    'method': 'tools/call',
    'params': {
        'name': 'apply_md',
        'arguments': {
            'input_md': '/tmp/q20/test.md',
            'target_format': 'docx',
            'output_path': '/tmp/q20/result.docx'
        }
    }
}

proc = subprocess.run(
    ['orf', 'mcp'],
    input=json.dumps(request),
    capture_output=True, text=True, timeout=30,
    env={**__import__('os').environ, 'OMNI_TEST_FAKE_LLM': '1', 'OMNI_TEST_FAKE_PANDOC': '1'}
)
print('STDOUT:', proc.stdout[:500])
print('RC:', proc.returncode)
"
```

**Expected Result:** ✅ JSON-RPC response indicates success. DOCX file produced at `/tmp/q20/result.docx`.

**Actual Result:** _________
**PASS / FAIL:** _________

### 20.6 🔴 MCP server rejects invalid JSON-RPC

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate

echo 'invalid json' | timeout 5 opp mcp 2>/dev/null; echo "Exit: $?"
```

**Expected Result:** ❌ Server does NOT crash. Returns JSON-RPC error response (parse error or invalid request). Exit code may be non-zero but no Python traceback is printed.

**Actual Result:** _________
**PASS / FAIL:** _________

### 20.7 🔴 MCP server rejects unauthorized path

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
export OPP_ALLOWED_DIRECTORIES="/tmp"
export OMNI_TEST_FAKE_LLM=1

python3 -c "
import subprocess, json

request = {
    'jsonrpc': '2.0',
    'id': 1,
    'method': 'tools/call',
    'params': {
        'name': 'detect_format_tool',
        'arguments': {'file_path': '/etc/passwd'}
    }
}

proc = subprocess.run(
    ['opp', 'mcp'],
    input=json.dumps(request),
    capture_output=True, text=True, timeout=10,
    env={
        **__import__('os').environ,
        'OPP_ALLOWED_DIRECTORIES': '/tmp',
        'OMNI_TEST_FAKE_LLM': '1',
    }
)
print('STDOUT:', proc.stdout[:500])
print('RC:', proc.returncode)
"
```

**Expected Result:** ❌ Returns error indicating path is not allowed (should contain `OPP_PATH_DENIED` or similar "not allowed" message). Server does NOT expose the file content.

**Actual Result:** _________
**PASS / FAIL:** _________

### 20.8 🔴 MCP matrix verifier via subprocess (195 cells)

This runs the full MCP matrix (same 195 cells as the CLI matrix, but via MCP tool calls) as a subprocess:

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
export OMNI_TEST_FAKE_LLM=1
export OMNI_TEST_FAKE_PANDOC=1

python3 scripts/mcp_matrix_verifier.py --check-only
```
(or without `--check-only` if you have 30+ minutes)

**Expected Result:** ❌ If any MCP matrix cell fails, those cells are reported. ✅ At minimum, the script should start up, establish MCP connections, and produce a partial matrix without crashing.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q20 Verdict

| Scenario | Result |
|----------|--------|
| 20.1 MCP smoke suite via subprocess (all 3 servers) | ⬜ |
| 20.2 OPP MCP raw JSON-RPC ping | ⬜ |
| 20.3 OPP MCP generate_markdown via subprocess | ⬜ |
| 20.4 OL MCP translate_md_text via subprocess | ⬜ |
| 20.5 ORF MCP apply_md via subprocess | ⬜ |
| 20.6 Invalid JSON-RPC rejection | ⬜ |
| 20.7 Unauthorized path rejection | ⬜ |
| 20.8 MCP matrix verifier via subprocess | ⬜ |

**OVERALL: ⬜**

---

# Part 7: Language Pair Expansion (Beyond zh↔en)

---

## Q21: Does the pipeline work with Japanese (zh↔ja)?

**User says:** "My documents are in Japanese. Will OPP extract them correctly? Can OL translate ja→zh or ja→en?"

**Why this matters:** OPP uses OCR + extractors that may not handle Japanese glyphs. OL relies on LLM prompt engineering tuned for zh↔en. Japanese introduces CJK ambiguity, full-width vs half-width, and kanji/hiragana/katakana mixing.

### 21.1 🟢 OPP extracts a Japanese DOCX correctly

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
export OMNI_TEST_FAKE_LLM=1

# Create a Japanese test DOCX
python3 -c "
from docx import Document
from docx.shared import Pt
doc = Document()
doc.add_heading('日本語の見出し', level=1)
doc.add_paragraph('これは日本語のテスト文書です。')
doc.add_paragraph('第二段落：ひらがな・カタカナ・漢字が混在。')
doc.add_heading('仕様一覧', level=2)
table = doc.add_table(rows=2, cols=2)
table.cell(0,0).text = '項目'
table.cell(0,1).text = '値'
table.cell(1,0).text = 'バージョン'
table.cell(1,1).text = '1.0'
doc.save('/tmp/q21/sample_ja.docx')
"

opp /tmp/q21/sample_ja.docx --target-format both --source-lang ja --target-lang zh -o /tmp/q21/opp
```

**Expected Result:** ✅ OPP extracts Japanese text correctly. Markdown contains correct Japanese characters (not mojibake). Tables preserved. YAML frontmatter shows `source_lang: ja`.

**Actual Result:** _________
**PASS / FAIL:** _________

### 21.2 🟢 OL translates Japanese to Chinese (FAKE_LLM)

```bash
ol translate-md /tmp/q21/opp/sample_ja.md -s ja -t zh -o /tmp/q21/ol --config Omni_Localizer/config/default.yaml
```

**Expected Result:** ✅ OL accepts ja→zh language pair. Output contains `[ZH]` markers (FAKE_LLM mode), proving the language pair is at least routed through the pipeline.

**Actual Result:** _________
**PASS / FAIL:** _________

### 21.3 🔴 OL translates Japanese to Chinese (real LLM)

```bash
unset OMNI_TEST_FAKE_LLM
source /mnt/d/贯维/Omni_Suite/.env
ol translate-md /tmp/q21/opp/sample_ja.md -s ja -t zh -o /tmp/q21/ol_real --config Omni_Localizer/config/local.yaml
```

**Expected Result:** ⚠️ May partially succeed or fail. If:
- ✅ Translation produced → check quality manually (is it real Chinese? preserved 日本語 terms?)
- ❌ Error → document the error for upstream (zh↔en is the calibrated pair)

**Actual Result:** _________
**PASS / FAIL:** _________

### 21.4 🟢 ORF backfills Japanese-sourced MD to DOCX

```bash
export OMNI_TEST_FAKE_LLM=1
orf apply-md /tmp/q21/ol/sample_ja.md --target-format docx --output /tmp/q21/orf/result.docx
```

**Expected Result:** ✅ DOCX produced. Text is readable (Japanese characters preserved). No encoding errors.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q21 Verdict

| Scenario | Result |
|----------|--------|
| 21.1 OPP extracts Japanese DOCX | ⬜ |
| 21.2 OL translate ja→zh (FAKE_LLM) | ⬜ |
| 21.3 OL translate ja→zh (real LLM) | ⬜ |
| 21.4 ORF backfill Japanese DOCX | ⬜ |

**OVERALL: ⬜**

---

## Q22: Does the pipeline work with Korean (zh↔ko)?

**User says:** "Korean uses Hangul. Does extraction and translation handle it?"

**Why this matters:** Korean has a different character set from CJK (Hangul vs Hanja/Kanji). Tests whether OPP extractors handle Unicode correctly beyond CJK shared characters.

### 22.1 🟢 OPP extracts a Korean DOCX

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
export OMNI_TEST_FAKE_LLM=1

python3 -c "
from docx import Document
doc = Document()
doc.add_heading('한국어 제목', level=1)
doc.add_paragraph('이것은 한국어 테스트 문서입니다.')
doc.add_paragraph('한글은 세종대왕이 창제한 문자입니다.')
doc.save('/tmp/q22/sample_ko.docx')
"

opp /tmp/q22/sample_ko.docx --target-format md --source-lang ko --target-lang zh -o /tmp/q22/opp
```

**Expected Result:** ✅ Korean text extracted. Hangul characters preserved. No mojibake.

**Actual Result:** _________
**PASS / FAIL:** _________

### 22.2 🟢 OL translates Korean → Chinese

```bash
export OMNI_TEST_FAKE_LLM=1
ol translate-md /tmp/q22/opp/sample_ko.md -s ko -t zh -o /tmp/q22/ol
```

**Expected Result:** ✅ FAKE_LLM accepts ko→zh. Output has `[ZH]` placeholders.

**Actual Result:** _________
**PASS / FAIL:** _________

### 22.3 🔴 Real LLM: Korean translation quality (diagnostic)

```bash
unset OMNI_TEST_FAKE_LLM
source /mnt/d/贯维/Omni_Suite/.env
ol translate-md /tmp/q22/opp/sample_ko.md -s ko -t zh -o /tmp/q22/ol_real --config Omni_Localizer/config/local.yaml
```

**Expected Result:** ⚠️ Diagnostic — not a gate. Record whether translation succeeds or fails.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q22 Verdict

| Scenario | Result |
|----------|--------|
| 22.1 OPP extracts Korean DOCX | ⬜ |
| 22.2 OL translate ko→zh (FAKE) | ⬜ |
| 22.3 OL translate ko→zh (real) | ⬜ |

**OVERALL: ⬜**

---

## Q23: Does the pipeline work with European languages (zh↔fr, zh↔de)?

**User says:** "I need to translate between Chinese and French. Does OL support non-CJK pairs?"

**Why this matters:** OL's LLM prompts are tuned for zh↔en. European languages introduce Latin scripts with diacritics (é, ü, ç, ñ, etc.). Tests whether OL handles lang pairs where the source and target use different alphabets.

### 23.1 🟢 OPP extracts French DOCX → OL translate (FAKE)

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
export OMNI_TEST_FAKE_LLM=1

python3 -c "
from docx import Document
doc = Document()
doc.add_heading('Titre en Français', level=1)
doc.add_paragraph('Ceci est un document de test en français.')
doc.add_paragraph('Caractères accentués: é, è, ê, ë, à, â, ç, ô, û, ü, î, ï.')
doc.add_paragraph('Le français utilise des guillemets « comme ça ».')
doc.save('/tmp/q23/sample_fr.docx')
"

opp /tmp/q23/sample_fr.docx --target-format md --source-lang fr --target-lang zh -o /tmp/q23/opp_fr
ol translate-md /tmp/q23/opp_fr/sample_fr.md -s fr -t zh -o /tmp/q23/ol_fr
```

**Expected Result:** ✅ French text extracted with diacritics preserved. OL accepts fr→zh language pair.

**Actual Result:** _________
**PASS / FAIL:** _________

### 23.2 🟢 German DOCX → OL translate (FAKE)

```bash
python3 -c "
from docx import Document
doc = Document()
doc.add_heading('Deutsche Überschrift', level=1)
doc.add_paragraph('Dies ist ein deutsches Testdokument.')
doc.add_paragraph('Umlaute: ä, ö, ü, ß.')
doc.add_paragraph('Deutsche Anführungszeichen: „so“')
doc.save('/tmp/q23/sample_de.docx')
"

opp /tmp/q23/sample_de.docx --target-format md --source-lang de --target-lang zh -o /tmp/q23/opp_de
ol translate-md /tmp/q23/opp_de/sample_de.md -s de -t zh -o /tmp/q23/ol_de
```

**Expected Result:** ✅ German text extracted with umlauts preserved. OL accepts de→zh.

**Actual Result:** _________
**PASS / FAIL:** _________

### 23.3 🟢 Full round-trip: French DOCX → MD → translate → DOCX

```bash
orf apply-md /tmp/q23/ol_fr/sample_fr.md --target-format docx --output /tmp/q23/orf/result_fr.docx
```

**Expected Result:** ✅ DOCX produced. French characters readable. No encoding corruption.

**Actual Result:** _________
**PASS / FAIL:** _________

### 23.4 🔴 Real LLM: French translation (diagnostic)

```bash
unset OMNI_TEST_FAKE_LLM
source /mnt/d/贯维/Omni_Suite/.env
ol translate-md /tmp/q23/opp_fr/sample_fr.md -s fr -t zh -o /tmp/q23/ol_real_fr --config Omni_Localizer/config/local.yaml
```

**Expected Result:** ⚠️ Diagnostic — record whether real LLM can translate fr→zh.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q23 Verdict

| Scenario | Result |
|----------|--------|
| 23.1 French zh→fr FAKE_LLM | ⬜ |
| 23.2 German zh→de FAKE_LLM | ⬜ |
| 23.3 French round-trip to DOCX | ⬜ |
| 23.4 French real LLM (diag) | ⬜ |

**OVERALL: ⬜**

---

# Part 8: Media & Format Depth

---

## Q24: Are floating images preserved through the XLIFF path?

**User says:** "My DOCX has images that float next to text. Do they survive the round-trip?"

**Why this matters:** Q13 covers inline images only. Floating images (`wp:anchor`) have position coordinates that must be preserved through XLIFF → skeleton → ORF backfill.

**Prerequisite:** A DOCX with at least one floating image. Create programmatically.

### 24.1 🟢 OPP detects floating images in a DOCX

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
export OMNI_TEST_FAKE_LLM=1

# First check: does the Haier DOCX have floating images?
python3 -c "
from opp.detector import detect_format
from opp.extractors.docx import DOCXExtractor
from pathlib import Path

ext = DOCXExtractor()
result = ext.extract(Path('$(ls 爱上海尔*.docx | head -1)'))
floating = [img for img in result.images if getattr(img, 'is_floating', False)]
print(f'Total images: {len(result.images)}')
print(f'Floating images: {len(floating)}')
for img in floating:
    print(f'  Floating: {img.image_id}, pos=({getattr(img, \"wp_anchor_h\", \"?\")},{getattr(img, \"wp_anchor_v\", \"?\")})')
"
```

**Expected Result:** ✅ OPP correctly distinguishes floating from inline images. Floating images have `is_floating=True` in their ImageData.

**Actual Result:** _________
**PASS / FAIL:** _________

### 24.2 🟢 Floating images in XLIFF output

```bash
opp <haier.docx> --target-format xlf --source-lang zh --target-lang en -o /tmp/q24/opp

# Check XLIFF for image handling
grep -c "image" /tmp/q24/opp/*.xlf || echo "No images in XLIFF"
```

**Expected Result:** ✅ XLIFF references images. Image metadata (position, type) is preserved in the skeleton.

**Actual Result:** _________
**PASS / FAIL:** _________

### 24.3 🟢 ORF backfill preserves floating position

Create a test DOCX with known floating image → extract → translate → backfill → verify position:

```bash
python3 -c "
from docx import Document
from docx.shared import Inches, Emu
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

doc = Document()
doc.add_heading('Floating Image Test', level=1)

# Create a drawing with wp:anchor (floating)
p = doc.add_paragraph()._element
run = OxmlElement('w:r')
drawing = OxmlElement('w:drawing')

# wp:anchor with position
anchor = OxmlElement('wp:anchor')
anchor.set('simplePos', '0')
anchor.set('relativeHeight', '0')

# Position
positionH = OxmlElement('wp:positionH')
positionH.set('relativeFrom', 'column')
posH_offset = OxmlElement('wp:posOffset')
posH_offset.text = '914400'  # 1 inch right
positionH.append(posH_offset)

positionV = OxmlElement('wp:positionV')
positionV.set('relativeFrom', 'paragraph')
posV_offset = OxmlElement('wp:posOffset')
posV_offset.text = '914400'  # 1 inch down
positionV.append(posV_offset)

anchor.append(positionH)
anchor.append(positionV)
# Minimal extent
extent = OxmlElement('wp:extent')
extent.set('cx', '914400')
extent.set('cy', '914400')
anchor.append(extent)

drawing.append(anchor)
run.append(drawing)
p.append(run)

doc.save('/tmp/q24/floating_test.docx')
print('✅ Floating image DOCX created')
"

# Extract → translate → backfill
export OMNI_TEST_FAKE_LLM=1
opp /tmp/q24/floating_test.docx --target-format both --source-lang en --target-lang zh -o /tmp/q24/opp
ol translate-xliff /tmp/q24/opp/*.xlf -s en -t zh -o /tmp/q24/ol
orf apply-xliff /tmp/q24/opp/floating_test.docx --xliff /tmp/q24/ol/*.xlf --output /tmp/q24/orf/result.docx

# Verify floating image position in output
python3 -c "
from zipfile import ZipFile
from pathlib import Path

with ZipFile('/tmp/q24/orf/result.docx') as z:
    doc_xml = z.read('word/document.xml').decode()
    if 'wp:anchor' in doc_xml:
        print('✅ Floating image (wp:anchor) preserved in output')
    elif 'wp:inline' in doc_xml:
        print('⚠️ Floating image demoted to inline')
    else:
        print('❌ No drawing found in output')
"
```

**Expected Result:** ✅ Output DOCX contains `wp:anchor` elements OR `wp:inline` if floating was demoted. At minimum, the image is present (not lost).

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q24 Verdict

| Scenario | Result |
|----------|--------|
| 24.1 OPP detects floating images | ⬜ |
| 24.2 Floating images in XLIFF | ⬜ |
| 24.3 Floating position preserved after backfill | ⬜ |

**OVERALL: ⬜**

---

## Q25: Does OCR extraction produce usable text quality?

**User says:** "I scanned a Chinese PDF. Will OPP extract the text correctly via OCR?"

**Why this matters:** OCR is the fallback for scanned PDFs and images. Q5 only checks "extraction succeeded" — not quality.

### 25.1 🟢 OPP OCR extracts text from a scanned image

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate

# Create a simple test image with text
python3 -c "
from PIL import Image, ImageDraw, ImageFont
img = Image.new('RGB', (400, 100), 'white')
draw = ImageDraw.Draw(img)
draw.text((20, 30), 'Hello OCR World', fill='black')
img.save('/tmp/q25/test_ocr.png')
"

opp /tmp/q25/test_ocr.png --target-format md -o /tmp/q25/opp
cat /tmp/q25/opp/test_ocr.md
```

**Expected Result:** ✅ Text extracted. Contains "Hello OCR World" or similar readable text (may have minor OCR errors).

**Actual Result:** _________
**PASS / FAIL:** _________

### 25.2 🟢 OPP OCR extracts Chinese text

```bash
python3 -c "
from PIL import Image, ImageDraw, ImageFont
img = Image.new('RGB', (600, 150), 'white')
draw = ImageDraw.Draw(img)

# Use a font that supports CJK if available, otherwise draw rectangles
try:
    font = ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc', 28)
    draw.text((20, 40), '光学字符识别测试', fill='black', font=font)
except:
    draw.text((20, 40), 'OCR Test Fallback', fill='black')
img.save('/tmp/q25/test_cjk_ocr.png')
"

opp /tmp/q25/test_cjk_ocr.png --target-format md --source-lang zh --target-lang en -o /tmp/q25/opp_cjk
cat /tmp/q25/opp_cjk/test_cjk_ocr.md
```

**Expected Result:** ⚠️ If CJK font available: Chinese characters extracted. Otherwise: at minimum text extraction doesn't crash.

**Actual Result:** _________
**PASS / FAIL:** _________

### 25.3 🟢 Scanned PDF → OCR → translate pipeline

```bash
# Use a scanned-image PDF (create one if no real scanned PDF exists)
python3 -c "
from PIL import Image
from fpdf import FPDF
import os

pdf = FPDF()
pdf.add_page()
pdf.add_font('DejaVu', '', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', uni=True)
pdf.set_font('DejaVu', '', 16)
pdf.cell(40, 10, 'Scanned PDF Text for OCR')
pdf.output('/tmp/q25/scanned_test.pdf')
"

export OMNI_TEST_FAKE_LLM=1
opp /tmp/q25/scanned_test.pdf --target-format md -o /tmp/q25/scanned_opp
cat /tmp/q25/scanned_opp/scanned_test.md
```

**Expected Result:** ✅ OPP processes PDF (either via text extraction or OCR fallback). Some text content is extracted.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q25 Verdict

| Scenario | Result |
|----------|--------|
| 25.1 English OCR text extraction | ⬜ |
| 25.2 CJK OCR text extraction | ⬜ |
| 25.3 Scanned PDF via OCR | ⬜ |

**OVERALL: ⬜**

---

## Q26: Does YouTube/ASR transcription produce usable text?

**User says:** "Can I transcribe a YouTube video via the `.url` file feature? Is the transcription usable for translation?"

**Why this matters:** YouTube `.url` input is a unique OPP feature. Q5 only checked "extraction succeeds" — not transcription quality.

### 26.1 🟢 `.url` file detection works

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate

echo 'https://www.youtube.com/watch?v=dQw4w9WgXcQ' > /tmp/q26/test.url
opp /tmp/q26/test.url --target-format md -o /tmp/q26/opp
```

**Expected Result:** ⚠️ OPP detects `.url` file format (not just text file). If no YouTube API key configured, returns a clear error about missing dependency rather than crashing.

**Actual Result:** _________
**PASS / FAIL:** _________

### 26.2 🟢 ASR (audio transcription) — diagnostic

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate

# Check if Whisper or ASR dependencies are available
python3 -c "
try:
    import whisper
    print('whisper available')
except ImportError:
    print('whisper not installed')
try:
    import markitdown
    print('markitdown available')
except ImportError:
    print('markitdown not installed')
"
```

**Expected Result:** ❌ Whisper likely not installed (~2GB dep). `markitdown` may be available. Document current ASR status.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q26 Verdict

| Scenario | Result |
|----------|--------|
| 26.1 YouTube .url detection | ⬜ |
| 26.2 ASR dependency check | ⬜ |

**OVERALL: ⬜**

---

# Part 9: Translation Quality Infrastructure

---

## Q27: Is translation consistent across different LLM providers?

**User says:** "Our English document was translated with Zhipu GLM last week. This week we use Agnes. Will the translation be consistent?"

**Why this matters:** Translation inconsistency between providers is a production risk. If terms, style, or tone vary significantly, the product is unusable.

### 27.1 🟢 Same text translated by all 4 providers — compare output

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
unset OMNI_TEST_FAKE_LLM
source /mnt/d/贯维/Omni_Suite/.env

echo '# API Documentation

## Authentication

To authenticate, send a POST request to /api/v1/auth/login with your credentials.

## Rate Limiting

The API allows 100 requests per minute. Exceeding this limit will return a 429 status code.

## Pagination

Results are paginated in pages of 20 items. Use the `page` and `limit` parameters.
' > /tmp/q27/sample.md

# Translate with each provider by temporarily switching config
# (Each run needs a config that pins a single provider)
for PROVIDER in zhipu agnes nvidia opencode; do
    echo "=== $PROVIDER ==="
    ol translate-md /tmp/q27/sample.md -s en -t zh \
      -c Omni_Localizer/config/only_$PROVIDER.yaml \
      -o /tmp/q27/$PROVIDER 2>&1 | head -5
done
```

**Expected Result:** ⚠️ Diagnostic. Collect translations from each provider and compute:
- ✅ All 4 produce valid Chinese translations
- ⚠️ BLEU score between any pair ≥ 0.5 (rough consistency)
- ❌ If any provider fails entirely (error), document it
- 🔴 If translations contradict each other (same term → different Chinese), flag it

**Actual Result:** _________
**PASS / FAIL:** _________

### 27.2 🟢 Terminology consistency check

```bash
python3 -c "
# Check if key terms like 'API endpoint', 'authentication', 'rate limit'
# are translated consistently across providers
import os, glob

terms = {
    'authentication': None,
    'rate limiting': None,
    'pagination': None,
}

for provider in ['zhipu', 'agnes', 'nvidia', 'opencode']:
    md_files = glob.glob(f'/tmp/q27/{provider}/*.md')
    if md_files:
        text = open(md_files[0]).read()
        for term in terms:
            # Find the term in translation
            if term not in text.lower():
                pass  # may not appear in output
        print(f'{provider}: {len(text)} chars')
"
```

**Expected Result:** ⚠️ Diagnostic. Report whether key technical terms are translated consistently.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q27 Verdict

| Scenario | Result |
|----------|--------|
| 27.1 All 4 providers translate same text | ⬜ |
| 27.2 Terminology consistency | ⬜ |

**OVERALL: ⬜**

---

## Q28: Are LQA quality thresholds calibrated correctly?

**User says:** "The plan says LQA ≥ 5.0/10. Why 5.0? Is that a real threshold or a guess?"

**Why this matters:** Arbitrary thresholds give false confidence. This question validates the threshold against real translations.

### 28.1 🟢 Run LQA on 10 real translations, record scores

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
unset OMNI_TEST_FAKE_LLM
source /mnt/d/贯维/Omni_Suite/.env

# Create 10 diverse test sentences
python3 -c "
import json
sentences = [
    ('en', 'zh', 'The system requires administrator privileges to complete this operation.'),
    ('en', 'zh', 'Click the Save button to persist your changes to the database.'),
    ('en', 'zh', 'An unexpected error occurred. Please try again later.'),
    ('en', 'zh', 'The document contains 15 tables, 3 images, and 2 embedded objects.'),
    ('en', 'zh', 'This API endpoint returns a JSON array of user objects sorted by creation date.'),
    ('en', 'zh', 'Please ensure the input file does not exceed 10MB in size.'),
    ('en', 'zh', 'The translation quality gate evaluates adequacy, fluency, terminology, and format.'),
    ('en', 'zh', 'Bold text and italic text should be preserved during the localization process.'),
    ('en', 'zh', 'Floating images maintain their position relative to the paragraph anchor.'),
    ('en', 'zh', 'The batch processing mode can handle up to 50 documents in a single run.'),
]
json.dump(sentences, open('/tmp/q28/sentences.json', 'w'))
"

# Translate each and run LQA
python3 << 'PYEOF'
import subprocess, json, os

sentences = json.load(open('/tmp/q28/sentences.json'))
results = []

for src_lang, tgt_lang, text in sentences:
    # Run translate via OL CLI
    env = os.environ.copy()
    env.pop('OMNI_TEST_FAKE_LLM', None)
    proc = subprocess.run(
        ['ol', 'translate-md', '-', '-s', src_lang, '-t', tgt_lang,
         '-c', 'Omni_Localizer/config/local.yaml', '-o', '/tmp/q28/run'],
        input=text, capture_output=True, text=True, timeout=60, env=env
    )
    results.append({
        'source': text[:50],
        'target': proc.stdout[:100] if proc.stdout else '(empty)',
        'exit_code': proc.returncode,
    })
    print(f'  [{len(results)}] exit={proc.returncode}')

json.dump(results, open('/tmp/q28/lqa_results.json', 'w'), ensure_ascii=False, indent=2)
PYEOF

# Now run LQA judge on each translation
python3 << 'PYEOF'
import subprocess, json, os

results = json.load(open('/tmp/q28/lqa_results.json'))
scores = []
env = os.environ.copy()
env.pop('OMNI_TEST_FAKE_LLM', None)

# Use OL judge tool to score
for i, r in enumerate(results):
    if r['exit_code'] != 0 or r['target'] == '(empty)':
        print(f'  [{i+1}] SKIP (translation failed)')
        continue
    proc = subprocess.run(
        ['ol', 'judge-text', r['source'][:200], r['target'][:200],
         '-s', 'en', '-t', 'zh'],
        capture_output=True, text=True, timeout=30, env=env
    )
    try:
        score = json.loads(proc.stdout)
        scores.append(score)
        print(f'  [{i+1}] score={score.get("score", "?")}')
    except:
        print(f'  [{i+1}] parse error: {proc.stdout[:100]}')

if scores:
    avg = sum(s.get('score', 0) for s in scores) / len(scores)
    print(f'\nAverage LQA score: {avg:.1f}/10')
    print(f'Range: {min(s.get(\"score\", 0) for s in scores):.1f} - {max(s.get(\"score\", 0) for s in scores):.1f}')
    print(f'Samples: {len(scores)}')
PYEOF
```

**Expected Result:** ⚠️ Diagnostic. Report:
- Average LQA score across 10 diverse sentences
- Minimum and maximum scores
- Whether ≥5.0/10 is too lenient or too strict
- Recommendation: adjust threshold if needed

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q28 Verdict

| Scenario | Result |
|----------|--------|
| 28.1 10-sentence LQA calibration | ⬜ |

**OVERALL: ⬜**

---

## Q29: Does the pipeline handle diverse file encodings (UTF-16, GBK)?

**User says:** "Our legacy documents are in GBK encoding. Can OPP extract them?"

**Why this matters:** Q5 uses well-formed UTF-8 files. Real-world docs may use GBK (Chinese legacy), Shift-JIS (Japanese), or UTF-16.

### 29.1 🟢 OPP handles GBK-encoded CSV

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate

# Create GBK-encoded CSV
python3 -c "
content = '名称,数量,价格\n苹果,10,5.00\n香蕉,20,3.50\n橘子,15,4.00\n'
with open('/tmp/q29/test_gbk.csv', 'w', encoding='gbk') as f:
    f.write(content)
"

opp /tmp/q29/test_gbk.csv --target-format md -o /tmp/q29/opp
cat /tmp/q29/opp/test_gbk.md
```

**Expected Result:** ✅ OPP detects and reads GBK-encoded CSV. Chinese text in output is correct (not mojibake).

**Actual Result:** _________
**PASS / FAIL:** _________

### 29.2 🟢 OPP handles UTF-16 encoded text file

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate

python3 -c "
content = 'Hello UTF-16 World\n第二行文字\nThird line with symbols: ©®™\n'
with open('/tmp/q29/test_utf16.txt', 'w', encoding='utf-16') as f:
    f.write(content)
"

opp /tmp/q29/test_utf16.txt --target-format md -o /tmp/q29/opp_utf16
cat /tmp/q29/opp_utf16/test_utf16.md
```

**Expected Result:** ⚠️ OPP may or may not detect .txt as a supported format. If unsupported, returns clear error (not crash). If supported, text is correctly extracted.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q29 Verdict

| Scenario | Result |
|----------|--------|
| 29.1 GBK-encoded CSV | ⬜ |
| 29.2 UTF-16 plain text | ⬜ |

**OVERALL: ⬜**

---

# Part 10: Pipeline Infrastructure & Resilience

---

## Q30: Does the OPP cache mechanism work correctly?

**User says:** "OPP has `--no-cache` and `--clear-cache` flags. Have they ever been tested?"

**Why this matters:** Cache mechanism is infrastructure — if it's broken, repeated extractions may return stale results or waste disk space.

### 30.1 🟢 Cache directory is created and used

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
export OMNI_TEST_FAKE_LLM=1
export OMNI_CACHE_DIR=/tmp/q30_cache

# First extraction
opp /mnt/d/贯维/Omni_Suite/爱上海尔_第二章_全球创牌 - E2E测试专用.docx --target-format md -o /tmp/q30/run1

# Check cache
python3 -c "
from pathlib import Path
cache = Path('/tmp/q30_cache')
if cache.exists():
    items = list(cache.rglob('*'))
    print(f'Cache directory: {cache}')
    print(f'Cache entries: {len(items)}')
    for item in items[:5]:
        print(f'  {item.relative_to(cache)} ({item.stat().st_size} bytes)')
else:
    print('No cache directory created')
"
```

**Expected Result:** ✅ Cache directory `/tmp/q30_cache/opp/` is created and contains cache entries.

**Actual Result:** _________
**PASS / FAIL:** _________

### 30.2 🟢 Second extraction is faster (cache hit)

```bash
export OMNI_CACHE_DIR=/tmp/q30_cache
time opp /mnt/d/贯维/Omni_Suite/爱上海尔_第二章_全球创牌 - E2E测试专用.docx --target-format md -o /tmp/q30/run2 2>&1
```

**Expected Result:** ⚠️ Second run should be faster if cache is working. Record times and compare.

**Actual Result:** _________
**PASS / FAIL:** _________

### 30.3 🟢 `--no-cache` bypasses cache

```bash
export OMNI_CACHE_DIR=/tmp/q30_cache
time opp /mnt/d/贯维/Omni_Suite/爱上海尔_第二章_全球创牌 - E2E测试专用.docx --target-format md --no-cache -o /tmp/q30/run3 2>&1
```

**Expected Result:** ✅ With `--no-cache`, extraction runs without reading from cache (same speed as first run).

**Actual Result:** _________
**PASS / FAIL:** _________

### 30.4 🟢 `--clear-cache` empties cache

```bash
opp --clear-cache
python3 -c "
from pathlib import Path
cache = Path('/tmp/q30_cache')
if cache.exists():
    items = list(cache.rglob('*'))
    print(f'Remaining cache entries: {len(items)}')
else:
    print('Cache directory removed')
"
```

**Expected Result:** ✅ Cache is cleared (either directory removed or emptied).

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q30 Verdict

| Scenario | Result |
|----------|--------|
| 30.1 Cache directory created | ⬜ |
| 30.2 Cache hit (second run faster) | ⬜ |
| 30.3 `--no-cache` works | ⬜ |
| 30.4 `--clear-cache` works | ⬜ |

**OVERALL: ⬜**

---

## Q31: Does OPP style mapping work?

**User says:** "I want to map custom paragraph styles to heading levels via `--style-map`. Does that work?"

**Why this matters:** Q5 never tested `--style-map`. It's a key feature for preserving document hierarchy.

### 31.1 🟢 `--style-map` promotes a custom style to H1

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
export OMNI_TEST_FAKE_LLM=1

# Create DOCX with custom paragraph style
python3 -c "
from docx import Document
from docx.shared import Pt
from docx.enum.style import WD_STYLE_TYPE

doc = Document()
# Create a custom style
style = doc.styles.add_style('Title1', WD_STYLE_TYPE.PARAGRAPH)
style.font.size = Pt(18)
style.font.bold = True

# Add content with custom style
p = doc.add_paragraph('This Should Be H1', style='Title1')
doc.add_paragraph('Normal body text here.')
p2 = doc.add_paragraph('Another Custom Heading', style='Title1')
doc.add_paragraph('More body text.')
doc.save('/tmp/q31/style_test.docx')
"

# Extract WITHOUT style map
opp /tmp/q31/style_test.docx --target-format md -o /tmp/q31/no_map
echo "=== Without style map ==="
cat /tmp/q31/no_map/style_test.md | head -10

# Extract WITH style map
opp /tmp/q31/style_test.docx --target-format md --style-map '{"Title1": 1}' -o /tmp/q31/with_map
echo "=== With --style-map '{\"Title1\": 1}' ==="
cat /tmp/q31/with_map/style_test.md | head -10
```

**Expected Result:** ✅ Without `--style-map`, custom style is extracted as plain paragraph. With `--style-map '{"Title1": 1}'`, the custom paragraphs are promoted to `# H1` headings in the markdown output.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q31 Verdict

| Scenario | Result |
|----------|--------|
| 31.1 `--style-map` promotes to H1 | ⬜ |

**OVERALL: ⬜**

---

## Q32: Can the pipeline recover after partial failure?

**User says:** "OL crashed halfway through translating my document. Do I have to restart from OPP?"

**Why this matters:** Production resilience depends on checkpoint/restart. For long documents (7,681 paragraphs), full restart is expensive.

### 32.1 🟢 OPP output can be re-used after OL failure

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
export OMNI_TEST_FAKE_LLM=1

# Step 1: Extract (always works)
opp /mnt/d/贯维/Omni_Suite/爱上海尔_第二章_全球创牌 - E2E测试专用.docx --target-format md -o /tmp/q32/opp

# Step 2: Translate (simulate crash by killing mid-way)
timeout 5 ol translate-md /tmp/q32/opp/*.md -s zh -t en -o /tmp/q32/ol_crash 2>&1 || echo "OL crashed (expected)"

# Step 3: Retry translation using same OPP output
ol translate-md /tmp/q32/opp/*.md -s zh -t en -o /tmp/q32/ol_retry 2>&1
echo "OL retry exit code: $?"
```

**Expected Result:** ⚠️ If OL supports resume (checkpoint file exists): retry is faster. If not: translation restarts from scratch but USES THE SAME OPP OUTPUT (no need to re-extract). The key insight is: OPP output is the checkpoint.

**Actual Result:** _________
**PASS / FAIL:** _________

### 32.2 🟢 OL has checkpoint/resume capability

```bash
# Check if OL creates checkpoint or temp files during translation
ls -la /tmp/q32/ol_crash/ 2>/dev/null || echo "No partial output from crashed run"
ls -la /tmp/q32/ol_retry/ 2>/dev/null || echo "No retry output"
```

**Expected Result:** ❌ If OL does not support incremental resume, document this gap. The workaround is: OPP output is the checkpoint — you never re-extract.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q32 Verdict

| Scenario | Result |
|----------|--------|
| 32.1 OPP output re-usable after OL crash | ⬜ |
| 32.2 OL checkpoint/resume capability | ⬜ |

**OVERALL: ⬜**

---

## Q33: Is the CLI help output format stable?

**User says:** "I parse `opp --help` output. Will the format change between versions?"

**Why this matters:** CLI help text is a de facto API contract. If help format changes unpredictably, automation breaks.

### 33.1 🟢 CLI help outputs without error

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate

for cmd in "opp --help" "ol --help" "orf --help" "omni-suite --help"; do
    echo "=== $cmd ==="
    $cmd 2>/dev/null | head -5
    echo "exit: $?"
done
```

**Expected Result:** ✅ All 4 CLIs print help text and exit with code 0. No tracebacks or errors.

**Actual Result:** _________
**PASS / FAIL:** _________

### 33.2 🟢 Help text contains expected sections

```bash
opp --help 2>/dev/null | grep -i "usage\|positional\|options\|commands" > /dev/null && echo "✅ opp --help has expected sections" || echo "❌ Missing standard help sections"
```

**Expected Result:** ✅ All CLIs have `usage:`, positional arguments, and options sections. None show "command not found" errors.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q33 Verdict

| Scenario | Result |
|----------|--------|
| 33.1 All CLIs print help | ⬜ |
| 33.2 Help has standard sections | ⬜ |

**OVERALL: ⬜**

---

## Q34: Are version combinations compatible?

**User says:** "I have OPP v0.8.0 and OL v0.5.8. Will they work together?"

**Why this matters:** Each submodule evolves independently. The compatibility matrix exists but is never tested end-to-end.

### 34.1 🟢 Current installed versions match COMPATIBILITY.md

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate

python3 -c "
import importlib.metadata as m
versions = {
    'opp': m.version('omni-pre-processor'),
    'ol': m.version('omni-localizer'),
    'orf': m.version('omni-re-formatter'),
}
for k, v in versions.items():
    print(f'{k}: v{v}')

# Compare with COMPATIBILITY.md
compat = open('COMPATIBILITY.md').read()
suite_v = open('VERSION').read().strip()
print(f'\nSuite version: v{suite_v}')
print(f'Check COMPATIBILITY.md for the correct version set.')
"
```

**Expected Result:** ✅ Installed versions match a row in COMPATIBILITY.md. Suite version from VERSION file is consistent.

**Actual Result:** _________
**PASS / FAIL:** _________

### 34.2 🟢 Pipeline works end-to-end with current versions

If Q1 or any pipeline test already passes, this is implicitly verified. Explicit check:

```bash
export OMNI_TEST_FAKE_LLM=1
export OMNI_TEST_FAKE_PANDOC=1

# Quick sanity: OPP extract → OL translate → ORF backfill
python3 /mnt/d/贯维/Omni_Suite/tests/test_e2e_pipeline.py -v --timeout 60 2>&1 | tail -5
```

**Expected Result:** ✅ Pipeline E2E tests pass. Versions are compatible.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q34 Verdict

| Scenario | Result |
|----------|--------|
| 34.1 Versions match compatibility matrix | ⬜ |
| 34.2 Pipeline works end-to-end | ⬜ |

**OVERALL: ⬜**

---

## Q35: Does graceful shutdown work cleanly?

**User says:** "I hit Ctrl+C during a long extraction. Does it leave temp files behind?"

**Why this matters:** Graceful shutdown prevents resource leaks and corrupted output files.

### 35.1 🔴 Ctrl+C during OPP extraction — no dirty output

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
export OMNI_TEST_FAKE_LLM=1

# Start extraction on big file, interrupt after 2 seconds
timeout --preserve-status 2 opp /mnt/d/贯维/Omni_Suite/（slim）爱上海尔.docx --target-format md -o /tmp/q35/interrupted 2>&1 || true

# Check: no partial output file pretending to be complete
ls /tmp/q35/interrupted/ 2>/dev/null && echo "⚠️ Partial output exists" || echo "✅ No partial output left behind"

# Check: no stale temp files
find /tmp -name "opp_*" -mmin -5 2>/dev/null | head -5
```

**Expected Result:** ✅ Interrupted extraction does NOT leave:
- A partial `.md` file (or if it does, it's clearly incomplete)
- Stale temp files in `/tmp`
- Lock files

**Actual Result:** _________
**PASS / FAIL:** _________

### 35.2 🔴 SIGTERM handled by OPP MCP server

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
export OMNI_TEST_FAKE_LLM=1

# Start MCP server in background, kill it, check cleanup
opp mcp &
MCP_PID=$!
sleep 1
kill $MCP_PID 2>/dev/null
wait $MCP_PID 2>/dev/null
echo "MCP server exit code: $?"
```

**Expected Result:** ✅ MCP server exits cleanly on SIGTERM. No "Killed" message. Exit code 0 or non-zero but not 137 (SIGKILL).

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q35 Verdict

| Scenario | Result |
|----------|--------|
| 35.1 Ctrl+C during extraction | ⬜ |
| 35.2 SIGTERM to MCP server | ⬜ |

**OVERALL: ⬜**

---

## Q36: Are log levels and formats correct?

**User says:** "I set `OMNI_LOG_FORMAT=json` but the logs look wrong. Is this tested?"

**Why this matters:** Logging is the primary observability mechanism in production.

### 36.1 🟢 OMNI_LOG_FORMAT=json produces valid JSON logs

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
export OMNI_TEST_FAKE_LLM=1
export OMNI_LOG_FORMAT=json

opp --detect-format 爱上海尔_第二章_全球创牌\ -\ E2E测试专用.docx 2>/tmp/q36/opp_json.log
cat /tmp/q36/opp_json.log | python3 -m json.tool --no-ensure-ascii 2>&1 | head -20
```

**Expected Result:** ✅ OPP verbose output (stderr) contains valid JSON lines when `OMNI_LOG_FORMAT=json` is set.

**Actual Result:** _________
**PASS / FAIL:** _________

### 36.2 🟢 Default log format is readable text

```bash
unset OMNI_LOG_FORMAT
opp --detect-format 爱上海尔_第二章_全球创牌\ -\ E2E测试专用.docx 2>/tmp/q36/opp_text.log
head -5 /tmp/q36/opp_text.log
```

**Expected Result:** ✅ Default log format is human-readable text (not JSON).

**Actual Result:** _________
**PASS / FAIL:** _________

### 36.3 🟢 OPP log level respects OMNI_LOG_LEVEL

```bash
export OMNI_LOG_LEVEL=DEBUG
opp --detect-format 爱上海尔_第二章_全球创牌\ -\ E2E测试专用.docx 2>/tmp/q36/opp_debug.log
wc -l /tmp/q36/opp_debug.log

export OMNI_LOG_LEVEL=ERROR
opp --detect-format 爱上海尔_第二章_全球创牌\ -\ E2E测试专用.docx 2>/tmp/q36/opp_error.log
wc -l /tmp/q36/opp_error.log
```

**Expected Result:** ✅ DEBUG log level produces more output than ERROR log level. Log level filtering works.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q36 Verdict

| Scenario | Result |
|----------|--------|
| 36.1 JSON log format | ⬜ |
| 36.2 Default text format | ⬜ |
| 36.3 Log level filtering | ⬜ |

**OVERALL: ⬜**

---

## Q37: Are the pre-commit hooks working?

**User says:** "I keep getting pre-commit failures in CI. Are the hooks themselves tested?"

**Why this matters:** Pre-commit hooks enforce code quality. If they're broken or misconfigured, CI gates are ineffective.

### 37.1 🟢 All pre-commit hooks pass on current codebase

```bash
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate

# Run all hooks (except manual ones) on all files
# Note: this may take time on a large repo
pre-commit run --all-files 2>&1 | tail -20
```

**Expected Result:** ✅ All non-manual hooks pass. No "Failed" messages (or only pre-existing failures unrelated to current changes).

**Actual Result:** _________
**PASS / FAIL:** _________

### 37.2 🟢 Individual hooks can be run separately

```bash
pre-commit run trailing-whitespace --all-files
pre-commit run end-of-file-fixer --all-files
pre-commit run check-added-large-files --all-files
```

**Expected Result:** ✅ Each hook runs without error.

**Actual Result:** _________
**PASS / FAIL:** _________

### 37.3 🟢 Manual hooks are documented (omni-contract-smoke)

```bash
pre-commit run omni-contract-smoke --all-files 2>&1 || true
```

**Expected Result:** ⚠️ `omni-contract-smoke` is `stages: [manual]` — it's expected to do nothing when run without `--hook-stage manual`. At minimum, it doesn't crash.

**Actual Result:** _________
**PASS / FAIL:** _________

---

### 📊 Q37 Verdict

| Scenario | Result |
|----------|--------|
| 37.1 All hooks pass | ⬜ |
| 37.2 Individual hooks run | ⬜ |
| 37.3 Manual hooks documented | ⬜ |

**OVERALL: ⬜**

---

# Final Verdict

## Complete Dashboard

| # | Question | Tier | Verdict |
|---|----------|------|---------|
| Q1 | Translate DOCX end-to-end (MD path) | ⬜ Baseline | ⬜ |
| Q2 | Translate DOCX end-to-end (XLIFF path) | ⬜ Baseline | ⬜ |
| Q3 | Translate and convert to different format | ⬜ Baseline | ⬜ |
| Q4 | Batch-process multiple documents | ⬜ Baseline | ⬜ |
| Q5 | All input formats extract correctly | ⬜ Baseline | ⬜ |
| Q6 | All output formats convert correctly | ⬜ Baseline | ⬜ |
| Q7 | Error boundaries (missing/corrupt/empty/huge) | ⬜ Baseline | ⬜ |
| Q8 | Security boundaries (traversal/auth/symlink) | ⬜ Baseline | ⬜ |
| Q9 | CJK/emoji/special characters | ⬜ Baseline | ⬜ |
| Q10 | Concurrent/parallel calls | ⬜ Baseline | ⬜ |
| Q11 | Deterministic output | ⬜ Baseline | ⬜ |
| Q12 | CLI/MCP equivalence | ⬜ Baseline | ⬜ |
| Q13 | Image preservation | ⬜ Baseline | ⬜ |
| Q14 | 195-cell format matrix | ⬜ Baseline | ⬜ |
| Q15 | Real LLM translation quality | ⬜ Production | ⬜ |
| Q16 | Real pandoc format validity | ⬜ Production | ⬜ |
| Q17 | Performance & throughput | ⬜ Production | ⬜ |
| Q18 | Multi-provider failover | ⬜ Production | ⬜ |
| Q19 | Long-running stability | ⬜ Production | ⬜ |
| Q20 | Real MCP server via stdio | ⬜ Production | ⬜ |
| Q21 | Japanese (zh↔ja) pipeline | ⬜ Language Pair | ⬜ |
| Q22 | Korean (zh↔ko) pipeline | ⬜ Language Pair | ⬜ |
| Q23 | European languages (zh↔fr/de) | ⬜ Language Pair | ⬜ |
| Q24 | Floating image preservation | ⬜ Media Depth | ⬜ |
| Q25 | OCR quality | ⬜ Media Depth | ⬜ |
| Q26 | YouTube/ASR transcription | ⬜ Media Depth | ⬜ |
| Q27 | Cross-provider translation consistency | ⬜ Quality Infra | ⬜ |
| Q28 | LQA threshold calibration | ⬜ Quality Infra | ⬜ |
| Q29 | File encoding diversity (GBK/UTF-16) | ⬜ Quality Infra | ⬜ |
| Q30 | OPP cache mechanism | ⬜ Pipeline Infra | ⬜ |
| Q31 | OPP style mapping | ⬜ Pipeline Infra | ⬜ |
| Q32 | Pipeline recovery after partial failure | ⬜ Pipeline Infra | ⬜ |
| Q33 | CLI help format stability | ⬜ Pipeline Infra | ⬜ |
| Q34 | Version compatibility | ⬜ Pipeline Infra | ⬜ |
| Q35 | Graceful shutdown | ⬜ Pipeline Infra | ⬜ |
| Q36 | Log levels and formats | ⬜ Pipeline Infra | ⬜ |
| Q37 | Pre-commit hooks | ⬜ Pipeline Infra | ⬜ |

## Tier Summary

| Tier | Questions | Purpose | When to Run | Expected Time |
|------|-----------|---------|-------------|---------------|
| **🚦 CI Gate** (Q1-Q14) | 14 | Structural integrity, FAKE_LLM | Every commit | ~10-15 min |
| **🚀 Release Candidate** (Q1-Q20) | 20 | + Real LLM/pandoc/perf/stability/MCP | Before release | ~30-60 min |
| **🌐 Language Pair** (Q21-Q23) | 3 | Japanese/Korean/European coverage | Quarterly | ~15 min |
| **🖼️ Media Depth** (Q24-Q26) | 3 | Floating images, OCR, ASR | Quarterly | ~15 min |
| **📐 Quality Infra** (Q27-Q29) | 3 | Consistency, thresholds, encoding | Per-release | ~20 min |
| **🔩 Pipeline Infra** (Q30-Q37) | 8 | Cache, style map, recovery, CLI, compat, shutdown, logs, hooks | Per-release | ~20 min |

## Sign-off Levels

| Level | Required Verdict | Gates |
|-------|-----------------|-------|
| **🚦 CI Gate** | Q1-Q14 all ✅ | Every commit, pre-merge |
| **🚀 Release Candidate** | Q1-Q20 all ✅ | Before tagged release |
| **🌐 Full Coverage** | Q1-Q37 all ✅ | Full certification |
| **✅ Production Deploy** | CI Gate + Release Candidate + Full Coverage | Final sign-off |

## Production Gap Checklist

This extends the Known Gap Checklist from ACCEPTED_GAPS.md with full-coverage findings:

| Gap | Affects | Status | Mitigation |
|-----|---------|--------|------------|
| Real LLM quality (Q15) | Translation value | ⬜ To verify | Run Q15 tests |
| Real pandoc output (Q16) | Format quality | ⬜ To verify | Run Q16 tests |
| Performance baselines (Q17) | SLO/SLA | ⬜ To verify | Run Q17 tests |
| Provider failover (Q18) | Reliability | ⬜ To verify | Run Q18 tests |
| Long-running stability (Q19) | Production ops | ⬜ To verify | Run Q19 tests |
| Real MCP process (Q20) | Integration | ⬜ To verify | Run Q20 tests |
| Language pair zh↔ja (Q21) | Coverage | ⬜ To verify | Run Q21 tests |
| Language pair zh↔ko (Q22) | Coverage | ⬜ To verify | Run Q22 tests |
| European lang pairs (Q23) | Coverage | ⬜ To verify | Run Q23 tests |
| Floating images (Q24) | Layout fidelity | ⬜ To verify | Run Q24 tests |
| OCR quality (Q25) | Text extraction | ⬜ To verify | Run Q25 tests |
| YouTube/ASR (Q26) | Transcription | ⬜ To verify | Run Q26 tests |
| Cross-provider consistency (Q27) | Translation quality | ⬜ To verify | Run Q27 tests |
| LQA threshold calibration (Q28) | Quality gates | ⬜ To verify | Run Q28 tests |
| File encoding diversity (Q29) | Unicode handling | ⬜ To verify | Run Q29 tests |
| OPP cache mechanism (Q30) | Performance | ⬜ To verify | Run Q30 tests |
| OPP style mapping (Q31) | Document structure | ⬜ To verify | Run Q31 tests |
| Pipeline recovery (Q32) | Resilience | ⬜ To verify | Run Q32 tests |
| CLI help format (Q33) | Automation | ⬜ To verify | Run Q33 tests |
| Version compatibility (Q34) | Deployment | ⬜ To verify | Run Q34 tests |
| Graceful shutdown (Q35) | Ops hygiene | ⬜ To verify | Run Q35 tests |
| Log correctness (Q36) | Observability | ⬜ To verify | Run Q36 tests |
| Pre-commit hooks (Q37) | Code quality | ⬜ To verify | Run Q37 tests |

## Sign-off

**Validated by:** _________
**Date:** _________
**Environment:** _________

**CI Gate (Q1-Q14):** ✅ ALL PASS / ❌ FAIL / ⚠️ PARTIAL
**Production (Q15-Q20):** ✅ ALL PASS / ❌ FAIL / ⚠️ PARTIAL
**Overall:** ✅ RELEASE CANDIDATE / ❌ BLOCKED

---

*End of Master Validation Plan — Production-Ready Edition*
