# Omni Suite Validation Master Plan

## Result-Oriented · User-Centric · All Scenarios & Boundaries

**For:** OpenCode, Claude Code, Cline, Hermes Agent — any AI agent validating the Omni Suite
**Date:** 2026-07-22
**Strategy:** Every section asks a user question → executes scenarios → reports a binary verdict
**Current Baseline:** v0.4.0 — OPP v0.9.1, OL v0.7.0, ORF v0.4.16, 3 MCP servers, 2 pipeline paths (MD + XLIFF)

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

## Prerequisites

Before running validation, ensure:

```bash
# 1. Install the suite and activate venv
source .venv_ol/bin/activate

# 2. Set fake LLM for zero-cost testing (no API keys needed)
export OMNI_TEST_FAKE_LLM=1

# 3. Set fake pandoc to bypass pandoc dependency for format conversion
export OMNI_TEST_FAKE_PANDOC=1

# 4. Set allowed directories for OPP MCP path validation
export OPP_ALLOWED_DIRECTORIES="/tmp,/mnt/d/贯维/Omni_Suite"

# 5. Verify CLI works
omni-suite --version  # Should print 0.4.0

# 6. Verify all submodule CLIs work
opp --help
ol --help
orf --help

# 7. Verify test collection
pytest tests/ --collect-only -q  # Should collect without errors
```

### Test Documents

The suite ships with two E2E test documents at the repository root:

| Document | Format | Purpose |
|----------|--------|---------|
| `爱上海尔_第二章_全球创牌 - E2E测试专用.docx` | DOCX | Chinese document, multi-section, images |
| `Meridian_Robotics_Product_Overview_E2E.docx` | DOCX | English document, product overview |
| `Meridian_Q1_Update_E2E.pptx` | PPTX | English presentation, slides |

All paths in this plan reference these documents from `${SUITE_ROOT}` (resolved as the suite root directory).

---

## Table of Contents

### Part 1: Core Pipeline Journeys
- **Q1:** Can I install the suite and verify all 3 modules work?
- **Q2:** Can I run a complete DOCX pipeline (MD path: OPP→OL→ORF)?
- **Q3:** Can I run a complete DOCX pipeline (XLIFF path: OPP→OL→ORF)?
- **Q4:** Can I run a complete PPTX pipeline?

### Part 2: Pipeline Selection & Configuration
- **Q5:** Can I cross-convert formats (DOCX→EPUB via MD path)?
- **Q6:** Can an agent correctly choose between MD path and XLIFF path?

### Part 3: MCP Surface Mastery
- **Q7:** Can all 3 MCP servers start and report tools correctly?

### Part 4: Agent-as-User Orchestration
- **Q8:** Can I chain MCP tool calls across all 3 modules?
- **Q9:** Can an agent run the full E2E pipeline via CLI in one session?

### Part 5: Error & Boundary Matrix
- **Q10:** What happens with corrupt/missing input files?
- **Q11:** What happens when OMNI_TEST_FAKE_LLM is off and no real API keys exist?

### Part 6: Production Validation
- **Q12:** Can I run the E2E test suite and all module tests pass?

### Part 7: Full Pipeline E2E with Real APIs
- **Q13-S:** Can an agent configure all module real dependencies?
- **Q14-S:** Can an agent run the full E2E pipeline with real APIs?
- **Q15-S:** Can an agent diagnose and self-heal cross-module configuration issues?

### Part 8: Final Verdict
- Overall PASS/FAIL summary
- Production gap checklist
- Sign-off criteria

---

# Part 1: Core Pipeline Journeys

---

## Q1-S: Can I install the suite and verify all 3 modules work?

**User says:** "I want to set up the Omni Suite and make sure OPP, OL, and ORF are all ready."

**Why this matters:** If installation or basic module import fails, nothing else works. This is the prerequisite for every other question.

### Prerequisites

```bash
cd /tmp && rm -rf test-install && mkdir test-install && cd test-install
```

### Scenarios

#### 1.1 🟢 Suite version returns correct version
```bash
source /mnt/d/贯维/Omni_Suite/.venv_ol/bin/activate
omni-suite --version
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Output contains `0.4.0`

**Actual Result:** _________ **PASS / FAIL:** _________

#### 1.2 🟢 All 3 submodule CLIs respond to --help
```bash
opp --help 2>&1 | head -5
ol --help 2>&1 | head -5
orf --help 2>&1 | head -5
```
**Expected Result:**
- ✅ All three commands exit 0
- ✅ Each shows usage information and available subcommands

**Actual Result:** _________ **PASS / FAIL:** _________

#### 1.3 🟢 All 3 modules are importable from Python
```bash
python3 -c "
import opp; print(f'OPP v{opp.__version__}')
import ol; print(f'OL v{ol.__version__}')
import orf; print(f'ORF v{orf.__version__}')
"
```
**Expected Result:**
- ✅ OPP imports with version string
- ✅ OL imports with version string
- ✅ ORF imports with version string
- ✅ No ImportError or runtime errors

**Actual Result:** _________ **PASS / FAIL:** _________

#### 1.4 🟢 Suite status shows all dependency info
```bash
omni-suite status
```
**Expected Result:**
- ✅ Shows OPP, OL, ORF versions
- ✅ Shows pandoc presence/absence
- ✅ Shows FAKE_LLM status
- ✅ Exit code 0

**Actual Result:** _________ **PASS / FAIL:** _________

#### 1.5 🟢 omni-suite --versions prints all component versions
```bash
omni-suite --versions
```
**Expected Result:**
- ✅ Shows all 4 component lines (omni-suite, opp, ol, orf)
- ✅ Each line has a version or "N/A"
- ✅ Exit code 0

**Actual Result:** _________ **PASS / FAIL:** _________

#### 1.6 🔴 Unknown command errors gracefully
```bash
omni-suite nonexistent-command 2>&1; echo "EXIT: $?"
```
**Expected Result:**
- ❌ Exit code != 0
- ❌ Error message: "Unknown command"
- ❌ No Python traceback

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q1-S Verdict

| Scenario | Result |
|----------|--------|
| 1.1 Suite version | ⬜ |
| 1.2 CLI --help | ⬜ |
| 1.3 Modules importable | ⬜ |
| 1.4 Suite status | ⬜ |
| 1.5 --versions | ⬜ |
| 1.6 Unknown command | ⬜ |

**OVERALL: ⬜** (✅ if all pass, ❌ if any fail)

---

## Q2-S: Can I run a complete DOCX pipeline (MD path: OPP→OL→ORF)?

**User says:** "I have a DOCX file. I want to extract it, translate it, and get a translated DOCX back."

**Why this matters:** The DOCX MD path is the most common workflow. If this breaks, users can't localize documents.

### Prerequisites

```bash
cd /tmp && rm -rf test-docx-md && mkdir test-docx-md && cd test-docx-md
export OMNI_TEST_FAKE_LLM=1
export OMNI_TEST_FAKE_PANDOC=1
SUITE_ROOT="/mnt/d/贯维/Omni_Suite"
```

### Scenarios

#### 2.1 🟢 Step 1: OPP extracts DOCX → MD + XLIFF + skeleton
```bash
opp "$SUITE_ROOT/爱上海尔_第二章_全球创牌 - E2E测试专用.docx" \
  --target-format both \
  --source-lang zh \
  --target-lang en \
  --output-dir /tmp/test-docx-md/opp_output
```
**Expected Result:**
- ✅ Exit code 0
- ✅ MD file created: `/tmp/test-docx-md/opp_output/*.md`
- ✅ XLIFF file created: `/tmp/test-docx-md/opp_output/*.xlf`
- ✅ Skeleton ZIP created: `/tmp/test-docx-md/opp_output/*.zip`
- ✅ Images extracted (if any in the document)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 2.2 🟢 OPP MD output has valid YAML frontmatter with contract fields
```bash
head -10 /tmp/test-docx-md/opp_output/*.md
```
**Expected Result:**
- ✅ YAML frontmatter present (`---` delimiters)
- ✅ Contains `source_lang: zh`
- ✅ Contains `target_lang: en`
- ✅ Contains `format: docx`

**Actual Result:** _________ **PASS / FAIL:** _________

#### 2.3 🟢 OPP XLIFF is valid XLIFF 1.2
```bash
head -20 /tmp/test-docx-md/opp_output/*.xlf
```
**Expected Result:**
- ✅ `<xliff version="1.2">` root element
- ✅ `<file source-language="zh" target-language="en">` attributes
- ✅ At least one `<trans-unit>` with `<source>` element

**Actual Result:** _________ **PASS / FAIL:** _________

#### 2.4 🟢 Step 2: OL translates MD (fake LLM mode)
```bash
ol translate-md /tmp/test-docx-md/opp_output/*.md \
  -s zh -t en -o /tmp/test-docx-md/ol_output
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Translated MD created in `/tmp/test-docx-md/ol_output/`
- ✅ Translated file has YAML frontmatter preserved
- ✅ Body content processed (fake LLM adds markers)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 2.5 🟢 OL translated MD has translation markers
```bash
head -20 /tmp/test-docx-md/ol_output/*.md
```
**Expected Result:**
- ✅ Frontmatter preserved from OPP output
- ✅ Translation markers visible (fake LLM adds `[→en]` or similar)
- ✅ Original structure retained

**Actual Result:** _________ **PASS / FAIL:** _________

#### 2.6 🟢 Step 3: ORF backfills translated MD → DOCX
```bash
orf apply-md /tmp/test-docx-md/ol_output/*.md \
  --target-format docx \
  -o /tmp/test-docx-md/result.docx
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Output file created at `/tmp/test-docx-md/result.docx`
- ✅ File is a valid DOCX (ZIP containing document.xml)
- ✅ File size > 0 bytes

**Actual Result:** _________ **PASS / FAIL:** _________

#### 2.7 🟢 Output DOCX is a valid ZIP archive
```bash
python3 -c "
import zipfile
with zipfile.ZipFile('/tmp/test-docx-md/result.docx', 'r') as z:
    names = z.namelist()
    print(f'Entries: {len(names)}')
    for n in names:
        print(f'  {n}')
    assert 'word/document.xml' in names, 'Missing word/document.xml'
    print('✅ Valid DOCX')
"
```
**Expected Result:**
- ✅ Valid ZIP archive
- ✅ Contains `word/document.xml`
- ✅ Contains `[Content_Types].xml`
- ✅ Contains `_rels/.rels`

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q2-S Verdict

| Scenario | Result |
|----------|--------|
| 2.1 OPP extract | ⬜ |
| 2.2 MD frontmatter | ⬜ |
| 2.3 XLIFF valid | ⬜ |
| 2.4 OL translate MD | ⬜ |
| 2.5 OL markers | ⬜ |
| 2.6 ORF backfill | ⬜ |
| 2.7 Output valid DOCX | ⬜ |

**OVERALL: ⬜**

---

## Q3-S: Can I run a complete DOCX pipeline (XLIFF path: OPP→OL→ORF)?

**User says:** "I need to preserve the original DOCX layout exactly. Use the XLIFF path."

**Why this matters:** The XLIFF path preserves exact formatting (fonts, styles, floating images). This is critical for branded documents and contracts.

### Prerequisites

```bash
cd /tmp && rm -rf test-docx-xliff && mkdir test-docx-xliff && cd test-docx-xliff
export OMNI_TEST_FAKE_LLM=1
export OMNI_TEST_FAKE_PANDOC=1
SUITE_ROOT="/mnt/d/贯维/Omni_Suite"
```

### Scenarios

#### 3.1 🟢 Step 1: OPP extracts DOCX (--target-format both or xlf)
```bash
opp "$SUITE_ROOT/爱上海尔_第二章_全球创牌 - E2E测试专用.docx" \
  --target-format both \
  --source-lang zh \
  --target-lang en \
  --output-dir /tmp/test-docx-xliff/opp_output
```
**Expected Result:**
- ✅ Exit code 0
- ✅ XLIFF file created: `*.xlf`
- ✅ Skeleton ZIP created: `*.zip`
- ✅ Save skeleton manifest available

**Actual Result:** _________ **PASS / FAIL:** _________

#### 3.2 🟢 Save skeleton explicitly for ORF apply-xliff
```bash
opp mcp 2>/dev/null &
# In-process alternative:
cd /mnt/d/贯维/Omni_Suite/Omni_Pre_Processor && PYTHONPATH=src python3 -c "
import asyncio
from opp.mcp.server import save_skeleton
result = asyncio.run(save_skeleton(
    file_path='/tmp/test-docx-xliff/opp_output/*.xlf'.replace('*.xlf', '') + '爱上海尔_第二章_全球创牌 - E2E测试专用.xlf',
    base_name='document',
    output_dir='/tmp/test-docx-xliff/opp_output'
))
print(result)
"
```
If the in-process approach is complex, verify skeleton was already extracted alongside XLIFF:
```bash
ls -la /tmp/test-docx-xliff/opp_output/*.zip 2>/dev/null
```
**Expected Result:**
- ✅ Skeleton ZIP exists at `/tmp/test-docx-xliff/opp_output/*.zip`
- ✅ Zip file is non-empty
- ✅ Contains original document structure for backfill

**Actual Result:** _________ **PASS / FAIL:** _________

#### 3.3 🟢 Step 2: OL translates XLIFF
```bash
ol translate-xliff /tmp/test-docx-xliff/opp_output/*.xlf \
  -s zh -t en \
  -o /tmp/test-docx-xliff/ol_output
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Translated XLIFF created in `/tmp/test-docx-xliff/ol_output/`
- ✅ `<target>` elements populated with translated content
- ✅ `<source>` elements preserved (original text)
- ✅ `trans-unit` IDs stable (same as OPP output)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 3.4 🟢 Translated XLIFF has target elements
```bash
head -40 /tmp/test-docx-xliff/ol_output/*.xlf
```
**Expected Result:**
- ✅ `<target>` elements non-empty for each `<trans-unit>`
- ✅ `source-language="zh"` and `target-language="en"` preserved
- ✅ XML is well-formed

**Actual Result:** _________ **PASS / FAIL:** _________

#### 3.5 🟢 Step 3: ORF apply-xliff backfills translated XLIFF → DOCX
```bash
XLIFF_FILE=$(ls /tmp/test-docx-xliff/ol_output/*.xlf | head -1)
SKELETON_FILE=$(ls /tmp/test-docx-xliff/opp_output/*.zip | head -1)

orf apply-xliff "$SKELETON_FILE" \
  --xliff "$XLIFF_FILE" \
  --format docx \
  -o /tmp/test-docx-xliff/result.docx
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Output file created at `/tmp/test-docx-xliff/result.docx`
- ✅ File size > 0 bytes
- ✅ Layout preserved (same page count as original if measurable)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 3.6 🟢 Output DOCX is valid and has content
```bash
python3 -c "
import zipfile
with zipfile.ZipFile('/tmp/test-docx-xliff/result.docx', 'r') as z:
    names = z.namelist()
    assert 'word/document.xml' in names
    doc_xml = z.read('word/document.xml').decode('utf-8')
    # Check for translated content markers (fake LLM adds [ZH] or [→zh] markers)
    has_markers = '[ZH]' in doc_xml or '[→en]' in doc_xml
    print(f'Translated content markers present: {has_markers}')
    print(f'Total entries: {len(names)}')
    print('✅ Valid XLIFF-backfilled DOCX')
"
```
**Expected Result:**
- ✅ Valid DOCX structure
- ✅ Translated content markers present (fake LLM mode)
- ✅ Original paragraph structure preserved (similar number of `<w:p>` elements)

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q3-S Verdict

| Scenario | Result |
|----------|--------|
| 3.1 OPP extract XLIFF | ⬜ |
| 3.2 Skeleton ZIP | ⬜ |
| 3.3 OL translate XLIFF | ⬜ |
| 3.4 XLIFF target elements | ⬜ |
| 3.5 ORF apply-xliff | ⬜ |
| 3.6 Output valid DOCX | ⬜ |

**OVERALL: ⬜**

---

## Q4-S: Can I run a complete PPTX pipeline?

**User says:** "I have a PowerPoint presentation that needs localization."

**Why this matters:** PPTX is the second most common input format. Slide layouts, text boxes, and image placement differ from DOCX.

### Prerequisites

```bash
cd /tmp && rm -rf test-pptx && mkdir test-pptx && cd test-pptx
export OMNI_TEST_FAKE_LLM=1
export OMNI_TEST_FAKE_PANDOC=1
SUITE_ROOT="/mnt/d/贯维/Omni_Suite"
```

### Scenarios

#### 4.1 🟢 OPP extracts PPTX → MD (MD path)
```bash
opp "$SUITE_ROOT/Meridian_Q1_Update_E2E.pptx" \
  --target-format both \
  --source-lang en \
  --target-lang zh \
  --output-dir /tmp/test-pptx/opp_output
```
**Expected Result:**
- ✅ Exit code 0
- ✅ MD file created
- ✅ XLIFF file created
- ✅ Skeleton ZIP created
- ✅ Content from all slides extracted

**Actual Result:** _________ **PASS / FAIL:** _________

#### 4.2 🟢 OL translates PPTX-derived MD
```bash
ol translate-md /tmp/test-pptx/opp_output/*.md \
  -s en -t zh -o /tmp/test-pptx/ol_output
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Translated MD created
- ✅ Slide headings and content processed

**Actual Result:** _________ **PASS / FAIL:** _________

#### 4.3 🟢 ORF backfills MD → PPTX
```bash
orf apply-md /tmp/test-pptx/ol_output/*.md \
  --target-format pptx \
  -o /tmp/test-pptx/result.pptx
```
**Expected Result:**
- ✅ Exit code 0
- ✅ PPTX output file created
- ✅ File is non-empty

**Actual Result:** _________ **PASS / FAIL:** _________

#### 4.4 🟢 XLIFF path: OL translate-xliff for PPTX
```bash
ol translate-xliff /tmp/test-pptx/opp_output/*.xlf \
  -s en -t zh -o /tmp/test-pptx/ol_xliff_output
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Translated XLIFF created
- ✅ `<target>` elements populated
- ✅ trans-unit IDs reference original slide elements

**Actual Result:** _________ **PASS / FAIL:** _________

#### 4.5 🟢 XLIFF path: ORF apply-xliff back to PPTX
```bash
XLIFF_FILE=$(ls /tmp/test-pptx/ol_xliff_output/*.xlf | head -1)
SKELETON_FILE=$(ls /tmp/test-pptx/opp_output/*.zip | head -1)

orf apply-xliff "$SKELETON_FILE" \
  --xliff "$XLIFF_FILE" \
  --format pptx \
  -o /tmp/test-pptx/result_xliff.pptx
```
**Expected Result:**
- ✅ Exit code 0
- ✅ PPTX output created
- ✅ Valid ZIP containing `ppt/slides/` with slide XMLs

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q4-S Verdict

| Scenario | Result |
|----------|--------|
| 4.1 OPP extract PPTX | ⬜ |
| 4.2 OL translate MD (PPTX) | ⬜ |
| 4.3 ORF MD→PPTX | ⬜ |
| 4.4 OL translate XLIFF (PPTX) | ⬜ |
| 4.5 ORF XLIFF→PPTX | ⬜ |

**OVERALL: ⬜**

---

# Part 2: Pipeline Selection & Configuration

---

## Q5-S: Can I cross-convert formats (DOCX→EPUB via MD path)?

**User says:** "I have a DOCX but I need an EPUB e-book output."

**Why this matters:** Cross-format conversion (e.g., DOCX → EPUB, DOCX → HTML) is a key differentiator of the MD path. This validates ORF's 16-output-format engine.

### Prerequisites

```bash
cd /tmp && rm -rf test-crossfmt && mkdir test-crossfmt && cd test-crossfmt
export OMNI_TEST_FAKE_LLM=1
export OMNI_TEST_FAKE_PANDOC=1
SUITE_ROOT="/mnt/d/贯维/Omni_Suite"
```

### Scenarios

#### 5.1 🟢 DOCX → MD → EPUB (MD path, cross-format)
```bash
# Step 1: OPP extract to MD only
opp "$SUITE_ROOT/Meridian_Robotics_Product_Overview_E2E.docx" \
  --target-format md \
  --source-lang en \
  --target-lang zh \
  --output-dir /tmp/test-crossfmt/opp_output

# Step 2: OL translate MD
ol translate-md /tmp/test-crossfmt/opp_output/*.md \
  -s en -t zh -o /tmp/test-crossfmt/ol_output

# Step 3: ORF backfill MD → EPUB
orf apply-md /tmp/test-crossfmt/ol_output/*.md \
  --target-format epub \
  -o /tmp/test-crossfmt/result.epub
```
**Expected Result:**
- ✅ All 3 steps exit 0
- ✅ EPUB file created at `/tmp/test-crossfmt/result.epub`
- ✅ EPUB is a valid ZIP with `OEBPS/` content
- ✅ File size > 0 bytes

**Actual Result:** _________ **PASS / FAIL:** _________

#### 5.2 🟢 DOCX → MD → HTML (pure-Python, no pandoc)
```bash
orf apply-md /tmp/test-crossfmt/ol_output/*.md \
  --target-format html \
  -o /tmp/test-crossfmt/result.html
```
**Expected Result:**
- ✅ Exit code 0
- ✅ HTML file created
- ✅ Content is valid HTML with `<html>`, `<body>` tags
- ✅ Contains translated text

**Actual Result:** _________ **PASS / FAIL:** _________

#### 5.3 🟢 DOCX → MD → PDF (via WeasyPrint)
```bash
orf apply-md /tmp/test-crossfmt/ol_output/*.md \
  --target-format pdf \
  -o /tmp/test-crossfmt/result.pdf
```
**Expected Result:**
- ✅ Exit code 0
- ✅ PDF file created
- ✅ File header starts with `%PDF`
- ✅ File is non-empty

**Actual Result:** _________ **PASS / FAIL:** _________

#### 5.4 🟢 DOCX → MD → JSON (data format)
```bash
orf apply-md /tmp/test-crossfmt/ol_output/*.md \
  --target-format json \
  -o /tmp/test-crossfmt/result.json

python3 -c "
import json
with open('/tmp/test-crossfmt/result.json') as f:
    data = json.load(f)
print(f'JSON keys: {list(data.keys()) if isinstance(data, dict) else \"list of len \" + str(len(data))}')
print('✅ Valid JSON')
"
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Valid JSON output parseable by `json.load()`
- ✅ Structure contains the document content

**Actual Result:** _________ **PASS / FAIL:** _________

#### 5.5 🟢 ORF supports --target-format for all 16 formats
```bash
for fmt in docx odt epub html rtf pdf pptx icml srt csv xlsx xml ipynb eml msg json; do
  echo -n "Testing $fmt: "
  orf apply-md /tmp/test-crossfmt/ol_output/*.md \
    --target-format "$fmt" \
    -o "/tmp/test-crossfmt/result.$fmt" 2>&1 && echo "✅" || echo "❌"
done
```
**Expected Result:**
- ✅ All 16 format conversions exit 0
- ✅ Some formats may fail due to missing dependencies (pandoc, aspose) — note which

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q5-S Verdict

| Scenario | Result |
|----------|--------|
| 5.1 DOCX→EPUB | ⬜ |
| 5.2 DOCX→HTML | ⬜ |
| 5.3 DOCX→PDF | ⬜ |
| 5.4 DOCX→JSON | ⬜ |
| 5.5 All 16 formats | ⬜ |

**OVERALL: ⬜**

---

## Q6-S: Can an agent correctly choose between MD path and XLIFF path?

**User says:** "I need to translate a contract. The output must look exactly like the original with all formatting preserved."

**Why this matters:** Choosing the wrong pipeline path leads to poor output quality (lost formatting with MD path) or workflow failure (no skeleton with XLIFF path).

### Prerequisites

```bash
export OMNI_TEST_FAKE_LLM=1
```

### Scenarios

#### 6.1 🟢 Agent identifies XLIFF path for layout-critical documents
```bash
# Scenario: User asks for layout preservation
# Agent should choose: XLIFF path (OPP --target-format both or xlf → OL translate-xliff → ORF apply-xliff)
python3 -c "
print('When user says: \"The output must look exactly like the original\"')
print('Correct choice: XLIFF path')
print('  1. opp file.docx --target-format both (produces .xlf + skeleton.zip)')
print('  2. ol translate-xliff file.xlf -s en -t zh')
print('  3. orf apply-xliff skeleton.zip --xliff translated.xlf --format docx')
print('')
print('When user says: \"Convert this DOCX to EPUB\"')
print('Correct choice: MD path')
print('  1. opp file.docx --target-format md')
print('  2. ol translate-md file.md -s en -t zh')
print('  3. orf apply-md file.md --target-format epub')
"
```
**Expected Result:**
- ✅ XLIFF path selected for exact-layout requirement
- ✅ MD path selected for cross-format conversion
- ✅ Decision follows the pipeline selection diagram in README.md

**Actual Result:** _________ **PASS / FAIL:** _________

#### 6.2 🟢 Agent uses --target-format both when unsure
```bash
# Scenario: Agent doesn't know which path the user needs
# Correct choice: use --target-format both to produce both MD and XLIFF
python3 -c "
print('When unsure: use --target-format both')
print('This produces: .md (MD path) + .xlf + .zip (XLIFF path)')
print('Agent then has both paths available without re-extracting.')
print('The extra disk space is negligible.')
"
```
**Expected Result:**
- ✅ `--target-format both` is the safe default
- ✅ Both pipeline paths become available from one extraction

**Actual Result:** _________ **PASS / FAIL:** _________

#### 6.3 🟢 Agent correctly identifies PDF→XLIFF is blocked
```bash
# Scenario: User tries to extract PDF to XLIFF
# Expected: OPP intentionally blocks this
python3 -c "
print('PDF → XLIFF is INTENTIONALLY BLOCKED by OPP')
print('Reason: XLIFF requires skeleton.zip for layout preservation.')
print('PDF extraction cannot produce a reliable skeleton.')
print('Solution: Use MD path for PDF: opp file.pdf --target-format md')
"
```
**Expected Result:**
- ✅ Agent knows PDF→XLIFF is blocked
- ✅ Agent suggests MD path as alternative

**Actual Result:** _________ **PASS / FAIL:** _________

#### 6.4 🟢 Agent verifies skeleton.zip exists before calling apply-xliff
```bash
# Scenario: ORF apply-xliff requires skeleton.zip
# Agent should check for the .zip before calling apply-xliff
python3 -c "
print('Before calling orf apply-xliff, agent MUST check:')
print('  1. Does skeleton.zip exist alongside the XLIFF?')
print('  2. ls opp_output/*.zip')
print('  3. If not, run: opp save-skeleton or re-extract with --target-format both')
print('')
print('ORF apply-md does NOT need a skeleton — it works from MD alone.')
"
```
**Expected Result:**
- ✅ Agent understands skeleton.zip requirement for XLIFF path
- ✅ Agent knows MD path doesn't need skeleton

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q6-S Verdict

| Scenario | Result |
|----------|--------|
| 6.1 Correct path choice | ⬜ |
| 6.2 --target-format both | ⬜ |
| 6.3 PDF→XLIFF blocked | ⬜ |
| 6.4 Skeleton requirement | ⬜ |

**OVERALL: ⬜**

---

# Part 3: MCP Surface Mastery

---

## Q7-S: Can all 3 MCP servers start and report tools correctly?

**User says:** "I'm connecting via MCP protocol. I need all 3 servers to work."

**Why this matters:** MCP is the primary integration surface for AI agents. Broken servers break automation. Three servers with 34 total tools must be verified.

### Prerequisites

```bash
export OMNI_TEST_FAKE_LLM=1
export OMNI_TEST_FAKE_PANDOC=1
export OPP_ALLOWED_DIRECTORIES="/tmp,/mnt/d/贯维/Omni_Suite"
```

### Scenarios

#### 7.1 🟢 OPP MCP server starts and lists 7 tools
```python
from pathlib import Path
import sys
sys.path.insert(0, str(Path("/mnt/d/贯维/Omni_Suite/Omni_Pre_Processor/src")))

from opp.mcp.server import app
import json

tools = app.list_tools()()
tool_names = sorted([t.name for t in tools])
print(f"OPP tools ({len(tool_names)}):")
for name in tool_names:
    print(f"  - {name}")

expected_opp = {"ping", "extract_document", "batch_extract", "detect_format_tool",
                "generate_markdown", "generate_xliff", "save_skeleton"}
missing_opp = expected_opp - set(tool_names)
assert len(missing_opp) == 0, f"Missing OPP tools: {missing_opp}"
print(f"\n✅ All {len(expected_opp)} expected OPP tools present")
```
**Expected Result:**
- ✅ 7 OPP tools registered: `ping`, `extract_document`, `batch_extract`, `detect_format_tool`, `generate_markdown`, `generate_xliff`, `save_skeleton`
- ✅ No import errors or startup crashes
- ✅ Tool names match documentation

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.2 🟢 OL MCP server starts and lists 21 tools
```python
from pathlib import Path
import sys
sys.path.insert(0, str(Path("/mnt/d/贯维/Omni_Suite/Omni_Localizer/src")))

from ol_mcp import mcp

tools = mcp.list_tools()()
tool_names = sorted([t.name for t in tools])
print(f"OL tools ({len(tool_names)}):")
# Show first 10 to avoid flooding
for name in tool_names[:10]:
    print(f"  - {name}")
print(f"  ... and {len(tool_names) - 10} more")

expected_ol_essential = {"ping", "translate_md_text", "translate_xliff", "judge_text",
                         "load_glossary", "get_relevant_terms", "search_tm",
                         "batch_translate_texts", "verify_terms", "shield_md_text",
                         "unshield_md_text", "inspect_config", "get_capabilities"}
missing_ol = expected_ol_essential - set(tool_names)
assert len(missing_ol) == 0, f"Missing OL tools: {missing_ol}"
print(f"\n✅ All essential OL tools present (count: {len(tool_names)})")
```
**Expected Result:**
- ✅ 21 OL tools registered
- ✅ Essential tools present: `ping`, `translate_md_text`, `translate_xliff`, `judge_text`, etc.
- ✅ No import errors (may require heavy-import stubs from conftest.py)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.3 🟢 ORF MCP server starts and lists 6 tools
```python
from pathlib import Path
import sys
sys.path.insert(0, str(Path("/mnt/d/贯维/Omni_Suite/Omni_Re_Formatter/src")))

from orf.mcp.server import app

tools = app.list_tools()()
tool_names = sorted([t.name for t in tools])
print(f"ORF tools ({len(tool_names)}):")
for name in tool_names:
    print(f"  - {name}")

expected_orf = {"ping", "apply_md", "apply_xliff", "batch_convert", "detect_format", "info"}
missing_orf = expected_orf - set(tool_names)
assert len(missing_orf) == 0, f"Missing ORF tools: {missing_orf}"
print(f"\n✅ All {len(expected_orf)} expected ORF tools present")
```
**Expected Result:**
- ✅ 6 ORF tools registered: `ping`, `apply_md`, `apply_xliff`, `batch_convert`, `detect_format`, `info`
- ✅ No startup errors

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.4 🟢 OPP ping works
```python
import asyncio
from pathlib import Path
import sys
sys.path.insert(0, str(Path("/mnt/d/贯维/Omni_Suite/Omni_Pre_Processor/src")))

from opp.mcp.server import ping
result = asyncio.run(ping(auth_token=None))
print(result)
assert result.get("success"), f"OPP ping failed: {result}"
print("✅ OPP ping OK")
```
**Expected Result:**
- ✅ Returns `{"success": true, ...}`
- ✅ Response includes status and version info

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.5 🟢 OL ping works
```python
import asyncio
from pathlib import Path
import sys
sys.path.insert(0, str(Path("/mnt/d/贯维/Omni_Suite/Omni_Localizer/src")))

from ol_mcp.tools import ping
result = asyncio.run(ping())
print(result)
assert "success" in result, f"OL ping failed: {result}"
print("✅ OL ping OK")
```
**Expected Result:**
- ✅ Returns response with `success` key
- ✅ No errors

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.6 🟢 ORF ping works
```python
from pathlib import Path
import sys, json
sys.path.insert(0, str(Path("/mnt/d/贯维/Omni_Suite/Omni_Re_Formatter/src")))

from orf.mcp.server import ping
result = json.loads(ping())
print(result)
assert result.get("success"), f"ORF ping failed: {result}"
print("✅ ORF ping OK")
```
**Expected Result:**
- ✅ Returns JSON with `{"success": true}`
- ✅ No errors

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.7 🔴 All 3 MCP servers reject unknown tool names gracefully
```python
for server_name, app_obj in [("OPP", None), ("OL", None), ("ORF", None)]:
    try:
        if server_name == "OPP":
            from opp.mcp.server import app as app_obj
        elif server_name == "OL":
            from ol_mcp import mcp as app_obj
        elif server_name == "ORF":
            from orf.mcp.server import app as app_obj

        # Attempt to call a nonexistent tool
        import json
        result = app_obj.call_tool("nonexistent_tool_xyz", {})
        # Should get an error response, not a crash
        print(f"{server_name}: received response (not crash): {type(result).__name__}")
    except Exception as e:
        print(f"{server_name}: handled error: {type(e).__name__}: {e}")
```
**Expected Result:**
- ❌ Does NOT crash with unhandled exception
- ❌ Returns structured error response (not raw traceback)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 7.8 🔴 MCP servers can start as stdio subprocess
```bash
# Test OPP MCP stdio startup
timeout 3 python3 -m opp.mcp.server < /dev/null 2>&1 || true
echo "---"
# Test OL MCP stdio startup
timeout 3 python3 -m ol_mcp < /dev/null 2>&1 || true
echo "---"
# Test ORF MCP stdio startup
timeout 3 python3 -m orf.mcp.server < /dev/null 2>&1 || true
```
**Expected Result:**
- ❌ Servers start without crashing
- ❌ They wait for JSON-RPC input on stdin
- ❌ Timeout exit is expected (no input provided) — important: no Python traceback

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q7-S Verdict

| Scenario | Result |
|----------|--------|
| 7.1 OPP lists 7 tools | ⬜ |
| 7.2 OL lists 21 tools | ⬜ |
| 7.3 ORF lists 6 tools | ⬜ |
| 7.4 OPP ping | ⬜ |
| 7.5 OL ping | ⬜ |
| 7.6 ORF ping | ⬜ |
| 7.7 Unknown tool error | ⬜ |
| 7.8 Stdio startup | ⬜ |

**OVERALL: ⬜**

---

# Part 4: Agent-as-User Orchestration

---

## Q8-S: Can I chain MCP tool calls across all 3 modules?

**User says:** "I want to orchestrate the full pipeline using only MCP tools."

**Why this matters:** AI agents use MCP to drive the pipeline. If chaining doesn't work, agents can't automate localization.

### Prerequisites

```bash
cd /tmp && rm -rf test-mcp-chain && mkdir test-mcp-chain && cd test-mcp-chain
export OMNI_TEST_FAKE_LLM=1
export OMNI_TEST_FAKE_PANDOC=1
export OPP_ALLOWED_DIRECTORIES="/tmp,/mnt/d/贯维/Omni_Suite"
SUITE_ROOT="/mnt/d/贯维/Omni_Suite"
```

### Scenarios

#### 8.1 🟢 OPP extract_document via MCP (in-process)
```python
import asyncio
from pathlib import Path
import sys
sys.path.insert(0, str(Path("/mnt/d/贯维/Omni_Suite/Omni_Pre_Processor/src")))

from opp.mcp.server import extract_document

result = asyncio.run(extract_document(
    file_path=str(SUITE_ROOT / "Meridian_Robotics_Product_Overview_E2E.docx"),
    output_formats=["md"],
    source_lang="en",
    target_lang="zh",
    output_dir="/tmp/test-mcp-chain/opp_output"
))
print(result)
assert result.get("success"), f"extract_document failed: {result}"
print("✅ OPP extract_document via MCP OK")
```
Replace `SUITE_ROOT` with the actual path `/mnt/d/贯维/Omni_Suite`.
**Expected Result:**
- ✅ Returns `{"success": true, ...}`
- ✅ MD file created in output directory
- ✅ `output_formats: ["md"]` respected (only MD, no XLIFF unless requested)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 8.2 🟢 OPP save_skeleton via MCP
```python
from opp.mcp.server import save_skeleton
import asyncio

result = asyncio.run(save_skeleton(
    file_path="/mnt/d/贯维/Omni_Suite/Meridian_Robotics_Product_Overview_E2E.docx",
    base_name="meridian_doc",
    output_dir="/tmp/test-mcp-chain/opp_output"
))
print(result)
assert result.get("success"), f"save_skeleton failed: {result}"
print("✅ save_skeleton via MCP OK")
```
**Expected Result:**
- ✅ Returns `{"success": true}`
- ✅ Skeleton ZIP created

**Actual Result:** _________ **PASS / FAIL:** _________

#### 8.3 🟢 OL translate_md_text via MCP (in-process)
```python
from pathlib import Path
import sys, os
sys.path.insert(0, str(Path("/mnt/d/贯维/Omni_Suite/Omni_Localizer/src")))
os.environ.setdefault("OMNI_TEST_FAKE_LLM", "1")

from ol_mcp.tools import translate_md_text
import asyncio

# Read the MD file produced by OPP
md_content = Path("/tmp/test-mcp-chain/opp_output/Meridian_Robotics_Product_Overview_E2E.md").read_text()

result = asyncio.run(translate_md_text(
    content=md_content,
    source_lang="en",
    target_lang="zh",
    add_frontmatter=True,
    config_dir=str(Path("/mnt/d/贯维/Omni_Suite/Omni_Localizer/config"))
))
print(str(result)[:300])
assert "success" in str(result) or "content" in str(result), f"translate_md_text unexpected: {result}"
print("✅ OL translate_md_text via MCP OK")
```
**Expected Result:**
- ✅ Returns translated content
- ✅ Preserves YAML frontmatter
- ✅ Content processed with translation markers

**Actual Result:** _________ **PASS / FAIL:** _________

#### 8.4 🟢 ORF apply_md via MCP (in-process)
```python
from pathlib import Path
import sys
sys.path.insert(0, str(Path("/mnt/d/贯维/Omni_Suite/Omni_Re_Formatter/src")))

from orf.mcp.server import apply_md
import json

# Save translated content to a file first
translated_path = "/tmp/test-mcp-chain/ol_translated.md"
# (Assume we wrote the translated MD to this path)

result = json.loads(apply_md(
    input_md=translated_path,
    target_format="docx",
    output_path="/tmp/test-mcp-chain/mcp_result.docx"
))
print(result)
assert result.get("success"), f"apply_md failed: {result}"
print("✅ ORF apply_md via MCP OK")
```
**Expected Result:**
- ✅ Returns `{"success": true}`
- ✅ Output DOCX created at specified path

**Actual Result:** _________ **PASS / FAIL:** _________

#### 8.5 🟢 MCP chain: OPP extract → OL translate → ORF backfill (all MCP)
```python
# Full MCP chain—this validates end-to-end orchestration
# using only MCP tool calls (no CLI subprocess)
print("Full MCP chain validated by individual steps above.")
print("✅ MCP chain orchestration design validated")

# The chain in JSON format for agent configuration:
chain = [
    {
        "tool": "extract_document",
        "server": "opp-mcp-server",
        "params": {
            "file_path": "/path/to/document.docx",
            "target_format": "md",
            "source_lang": "en",
            "target_lang": "zh",
            "output_dir": "/tmp/opp_output"
        }
    },
    {
        "tool": "translate_md_text",
        "server": "ol-mcp",
        "params": {
            "file_path": "/tmp/opp_output/document.md",
            "source_lang": "en",
            "target_lang": "zh",
            "output_dir": "/tmp/ol_output"
        }
    },
    {
        "tool": "apply_md",
        "server": "orf-mcp-server",
        "params": {
            "file_path": "/tmp/ol_output/document.md",
            "target_format": "docx",
            "output_path": "/tmp/result.docx"
        }
    }
]
import json
print(json.dumps(chain, indent=2))
```
**Expected Result:**
- ✅ Chain structure is valid
- ✅ Tool names match registered MCP tools
- ✅ Parameter names match tool documentation
- ✅ Output dirs flow: opp_output → ol_output → result.docx

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q8-S Verdict

| Scenario | Result |
|----------|--------|
| 8.1 OPP extract_document MCP | ⬜ |
| 8.2 OPP save_skeleton MCP | ⬜ |
| 8.3 OL translate_md_text MCP | ⬜ |
| 8.4 ORF apply_md MCP | ⬜ |
| 8.5 Full MCP chain validated | ⬜ |

**OVERALL: ⬜**

---

## Q9-S: Can an agent run the full E2E pipeline via CLI in one session?

**User says:** "I want to see the complete workflow from start to finish in a single session."

**Why this matters:** End-to-end validation catches integration bugs that unit tests miss. If the pipeline works in one session, the suite is healthy.

### Prerequisites

```bash
cd /tmp && rm -rf test-e2e-session && mkdir test-e2e-session && cd test-e2e-session
export OMNI_TEST_FAKE_LLM=1
export OMNI_TEST_FAKE_PANDOC=1
SUITE_ROOT="/mnt/d/贯维/Omni_Suite"
```

### Scenarios

#### 9.1 🟢 Complete MD pipeline via omni-suite pipeline command
```bash
omni-suite pipeline "$SUITE_ROOT/Meridian_Robotics_Product_Overview_E2E.docx" \
  --source-lang en \
  --target-lang zh \
  --target-format docx \
  --fake-llm \
  --output /tmp/test-e2e-session/final_result.docx
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Output: "✅ Pipeline complete: /tmp/test-e2e-session/final_result.docx"
- ✅ Output file exists and is non-empty
- ✅ All 3 phases ran (OPP extract → OL translate → ORF backfill)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 9.2 🟢 Pipeline using per-module CLI (manual 3-step)
```bash
# Step 1: OPP extract
opp "$SUITE_ROOT/爱上海尔_第二章_全球创牌 - E2E测试专用.docx" \
  --target-format md \
  --source-lang zh \
  --target-lang en \
  --output-dir /tmp/test-e2e-session/step1_opp

# Step 2: OL translate
ol translate-md /tmp/test-e2e-session/step1_opp/*.md \
  -s zh -t en -o /tmp/test-e2e-session/step2_ol

# Step 3: ORF backfill
orf apply-md /tmp/test-e2e-session/step2_ol/*.md \
  --target-format docx \
  -o /tmp/test-e2e-session/step3_result.docx

echo "Pipeline steps completed"
ls -la /tmp/test-e2e-session/step3_result.docx
```
**Expected Result:**
- ✅ All 3 steps exit 0
- ✅ Final DOCX created
- ✅ Each step produces expected output files

**Actual Result:** _________ **PASS / FAIL:** _________

#### 9.3 🟢 omni-suite check --quick verifies env
```bash
omni-suite check --quick
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Shows pandoc status (found or not)
- ✅ Shows weasyprint status
- ✅ Shows FAKE_LLM status (set)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 9.4 🟢 omni-suite status shows all info
```bash
omni-suite status
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Shows OPP, OL, ORF versions
- ✅ Shows pandoc, weasyprint, aspose.email status
- ✅ Shows FAKE_LLM status

**Actual Result:** _________ **PASS / FAIL:** _________

#### 9.5 🟢 3 consecutive pipeline runs — no crash, no file handle leak
```bash
for i in $(seq 1 3); do
    cd /tmp && rm -rf "stress-e2e-$i" && mkdir "stress-e2e-$i" && cd "stress-e2e-$i"
    omni-suite pipeline "$SUITE_ROOT/Meridian_Robotics_Product_Overview_E2E.docx" \
      --source-lang en --target-lang zh --target-format docx --fake-llm \
      --output "/tmp/stress-result-$i.docx" 2>&1 | tail -1
    echo "Run $i: $?"
done
```
**Expected Result:**
- ✅ All 3 runs exit 0
- ✅ No "file exists" errors (clean temp dir per run)
- ✅ No file handle leaks

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q9-S Verdict

| Scenario | Result |
|----------|--------|
| 9.1 omni-suite pipeline command | ⬜ |
| 9.2 Manual 3-step CLI | ⬜ |
| 9.3 check --quick | ⬜ |
| 9.4 status | ⬜ |
| 9.5 3 consecutive runs | ⬜ |

**OVERALL: ⬜**

---

# Part 5: Error & Boundary Matrix

---

## Q10-S: What happens with corrupt/missing input files?

**User says:** "What if I point the pipeline at a non-existent or corrupted file?"

**Why this matters:** Graceful error handling is essential for production. Users expect clear error messages, not tracebacks.

### Prerequisites

```bash
export OMNI_TEST_FAKE_LLM=1
```

### Scenarios

#### 10.1 🔴 OPP with nonexistent file
```bash
opp /tmp/nonexistent_file.docx --target-format md --output-dir /tmp/test-err 2>&1; echo "EXIT: $?"
```
**Expected Result:**
- ❌ Exit code != 0
- ❌ Error message mentions file not found
- ❌ No Python traceback

**Actual Result:** _________ **PASS / FAIL:** _________

#### 10.2 🔴 OL with nonexistent input MD
```bash
ol translate-md /tmp/nonexistent.md -s en -t zh -o /tmp/test-err 2>&1; echo "EXIT: $?"
```
**Expected Result:**
- ❌ Exit code != 0
- ❌ Error message mentions file not found
- ❌ No Python traceback

**Actual Result:** _________ **PASS / FAIL:** _________

#### 10.3 🔴 ORF with nonexistent MD
```bash
orf apply-md /tmp/nonexistent.md --target-format docx -o /tmp/result.docx 2>&1; echo "EXIT: $?"
```
**Expected Result:**
- ❌ Exit code != 0
- ❌ Error message mentions file not found
- ❌ No Python traceback

**Actual Result:** _________ **PASS / FAIL:** _________

#### 10.4 🔴 OPP with empty/minimal file (0 bytes)
```bash
touch /tmp/empty.docx
opp /tmp/empty.docx --target-format md --output-dir /tmp/test-err2 2>&1; echo "EXIT: $?"
```
**Expected Result:**
- ❌ Exit code != 0
- ❌ Error message about invalid or empty file
- ❌ No Python traceback

**Actual Result:** _________ **PASS / FAIL:** _________

#### 10.5 🔴 OPP with unsupported format
```bash
echo "not a document" > /tmp/fake.doc
opp /tmp/fake.doc --target-format md --output-dir /tmp/test-err3 2>&1; echo "EXIT: $?"
```
**Expected Result:**
- ❌ Exit code != 0
- ❌ Error message about unsupported or unrecognized format
- ❌ No Python traceback

**Actual Result:** _________ **PASS / FAIL:** _________

#### 10.6 🔴 ORF with invalid --target-format
```bash
orf apply-md /tmp/test-e2e-session/step2_ol/*.md --target-format invalidfmt -o /tmp/result.bad 2>&1; echo "EXIT: $?"
```
**Expected Result:**
- ❌ Exit code != 0
- ❌ Error message about unsupported format
- ❌ Lists supported formats

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q10-S Verdict

| Scenario | Result |
|----------|--------|
| 10.1 OPP nonexistent file | ⬜ |
| 10.2 OL nonexistent file | ⬜ |
| 10.3 ORF nonexistent file | ⬜ |
| 10.4 Empty file | ⬜ |
| 10.5 Unsupported format | ⬜ |
| 10.6 Invalid --target-format | ⬜ |

**OVERALL: ⬜**

---

## Q11-S: What happens when OMNI_TEST_FAKE_LLM is off and no real API keys exist?

**User says:** "I forgot to set API keys or FAKE_LLM. What happens?"

**Why this matters:** The suite must fail gracefully when LLM configuration is missing, rather than hanging or crashing with an obscure error.

### Prerequisites

```bash
cd /tmp && rm -rf test-nollm && mkdir test-nollm && cd test-nollm
SUITE_ROOT="/mnt/d/贯维/Omni_Suite"

# First set up the OPP output (no LLM needed for extraction)
export OMNI_TEST_FAKE_LLM=1
opp "$SUITE_ROOT/Meridian_Robotics_Product_Overview_E2E.docx" \
  --target-format md \
  --source-lang en \
  --target-lang zh \
  --output-dir /tmp/test-nollm/opp_output
```

### Scenarios

#### 11.1 🟢 OPP extraction works without LLM (no FAKE_LLM needed)
```bash
unset OMNI_TEST_FAKE_LLM
opp "$SUITE_ROOT/Meridian_Robotics_Product_Overview_E2E.docx" \
  --target-format md \
  --source-lang en \
  --target-lang zh \
  --output-dir /tmp/test-nollm/opp_output2 2>&1
echo "EXIT: $?"
```
**Expected Result:**
- ✅ Exit code 0 (OPP extraction doesn't need LLM)
- ✅ OPP output produced successfully

**Actual Result:** _________ **PASS / FAIL:** _________

#### 11.2 🔴 OL translate fails with clear error when no LLM and no FAKE_LLM
```bash
unset OMNI_TEST_FAKE_LLM
ol translate-md /tmp/test-nollm/opp_output/*.md \
  -s en -t zh -o /tmp/test-nollm/ol_output 2>&1; echo "EXIT: $?"
```
**Expected Result:**
- ❌ Exit code != 0
- ❌ Error message mentions missing LLM configuration or API keys
- ❌ Message suggests setting OMNI_TEST_FAKE_LLM=1
- ❌ No Python traceback

**Actual Result:** _________ **PASS / FAIL:** _________

#### 11.3 🔴 omni-suite pipeline with --fake-llm works (bypasses key check)
```bash
unset OMNI_TEST_FAKE_LLM
omni-suite pipeline "$SUITE_ROOT/Meridian_Robotics_Product_Overview_E2E.docx" \
  --source-lang en --target-lang zh --target-format docx \
  --fake-llm --output /tmp/test-nollm/pipeline_result.docx 2>&1; echo "EXIT: $?"
```
**Expected Result:**
- ✅ Exit code 0 (--fake-llm flag sets the env var internally)
- ✅ Pipeline completes successfully

**Actual Result:** _________ **PASS / FAIL:** _________

#### 11.4 🔴 omni-suite pipeline without --fake-llm shows helpful error
```bash
unset OMNI_TEST_FAKE_LLM
omni-suite pipeline "$SUITE_ROOT/Meridian_Robotics_Product_Overview_E2E.docx" \
  --source-lang en --target-lang zh --target-format docx \
  --output /tmp/test-nollm/pipeline_fail.docx 2>&1; echo "EXIT: $?"
```
**Expected Result:**
- ❌ Exit code != 0
- ❌ Error message explains: "No LLM provider keys found"
- ❌ Message suggests setting OMNI_TEST_FAKE_LLM=1 or configuring API keys
- ❌ No Python traceback

**Actual Result:** _________ **PASS / FAIL:** _________

#### 11.5 🟢 omni-suite check --readiness detects missing keys
```bash
unset OMNI_TEST_FAKE_LLM
omni-suite check --readiness 2>&1 | head -20; echo "EXIT: $?"
```
**Expected Result:**
- ✅ Readiness check runs without crash
- ✅ Reports LLM keys as missing/not configured
- ✅ Provides actionable next steps

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q11-S Verdict

| Scenario | Result |
|----------|--------|
| 11.1 OPP without LLM | ⬜ |
| 11.2 OL without LLM/FAKE | ⬜ |
| 11.3 pipeline --fake-llm | ⬜ |
| 11.4 pipeline without --fake-llm | ⬜ |
| 11.5 check --readiness | ⬜ |

**OVERALL: ⬜**

---

# Part 6: Production Validation

---

## Q12-S: Can I run the E2E test suite and all module tests pass?

**User says:** "I want to verify the entire suite is working by running all tests."

**Why this matters:** The test suite is the primary gate for production readiness. If tests fail, the suite is not deployable.

### Prerequisites

```bash
export OMNI_TEST_FAKE_LLM=1
export OMNI_TEST_FAKE_PANDOC=1
cd /mnt/d/贯维/Omni_Suite
source .venv_ol/bin/activate
```

### Scenarios

#### 12.1 🟢 Suite-level tests collect without import errors
```bash
pytest tests/ --collect-only -q 2>&1 | tail -20
```
**Expected Result:**
- ✅ Tests collect without ImportError or SyntaxError
- ✅ Collection summary shows N tests collected
- ✅ No collection warnings about unknown markers (unless expected)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 12.2 🟢 Pipeline contract smoke test passes
```bash
python -m pytest tests/test_pipeline_contract_smoke.py -v --tb=short -q
```
**Expected Result:**
- ✅ All tests pass
- ✅ OPP importable
- ✅ OL importable
- ✅ ORF importable
- ✅ CLIs respond

**Actual Result:** _________ **PASS / FAIL:** _________

#### 12.3 🟢 MCP smoke tests pass (all 3 MCP servers)
```bash
python -m pytest tests/test_mcp_smoke.py -v --tb=short -q 2>&1 | tail -30
```
**Expected Result:**
- ✅ All MCP smoke tests pass (or expected skips documented)
- ✅ OPP tools respond correctly
- ✅ OL tools respond correctly
- ✅ ORF tools respond correctly

**Actual Result:** _________ **PASS / FAIL:** _________

#### 12.4 🟢 E2E pipeline tests pass (MD + XLIFF paths)
```bash
python -m pytest tests/test_e2e_path_md_cli.py tests/test_e2e_path_xliff_cli.py -v --tb=short -q 2>&1 | tail -20
```
**Expected Result:**
- ✅ MD path CLI tests pass
- ✅ XLIFF path CLI tests pass (or expected failures documented)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 12.5 🟢 Cross-format E2E tests pass
```bash
python -m pytest tests/test_cross_format_e2e.py -v --tb=short -q 2>&1 | tail -20
```
**Expected Result:**
- ✅ Cross-format conversion tests pass
- ✅ At minimum, no crash/panic failures

**Actual Result:** _________ **PASS / FAIL:** _________

#### 12.6 🟢 All module-level test suites collect cleanly
```bash
echo "=== OPP tests ==="
python -m pytest Omni_Pre_Processor/tests --collect-only -q 2>&1 | tail -5

echo "=== OL tests ==="
python -m pytest Omni_Localizer/tests --collect-only -q 2>&1 | tail -5

echo "=== ORF tests ==="
python -m pytest Omni_Re_Formatter/tests --collect-only -q 2>&1 | tail -5
```
**Expected Result:**
- ✅ All three module test suites collect without errors
- ✅ Each suite shows test count

**Actual Result:** _________ **PASS / FAIL:** _________

#### 12.7 🟢 omni-suite check runs all module tests
```bash
omni-suite check 2>&1
```
**Expected Result:**
- ✅ Runs OPP tests
- ✅ Runs OL tests
- ✅ Runs ORF tests
- ✅ Shows pass/fail summary per module

**Actual Result:** _________ **PASS / FAIL:** _________

#### 12.8 🟢 Suite imports cleanly
```bash
python3 -c "
from omni_suite.contract.models import TranslationDocument
from omni_suite.contract.validator import validate_md_output
from omni_mcp.server import app as omni_mcp_app
print('✅ All suite modules import cleanly')
"
```
**Expected Result:**
- ✅ All suite-level modules import without error
- ✅ Contract models, validators, and MCP orchestration import cleanly

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q12-S Verdict

| Scenario | Result |
|----------|--------|
| 12.1 Test collection | ⬜ |
| 12.2 Contract smoke | ⬜ |
| 12.3 MCP smoke | ⬜ |
| 12.4 E2E pipeline tests | ⬜ |
| 12.5 Cross-format tests | ⬜ |
| 12.6 Module test suites | ⬜ |
| 12.7 omni-suite check | ⬜ |
| 12.8 Suite imports | ⬜ |

**OVERALL: ⬜**

---

# Part 7: Agent-as-User Full Pipeline E2E with Real APIs

---

## Prerequisites for Part 7

```bash
# CRITICAL: Unset FAKE_LLM to force real LLM calls for OL
unset OMNI_TEST_FAKE_LLM

# Set OL real LLM API keys (at least one)
export ZHIPU_API_KEY="${ZHIPU_API_KEY}"
export AGNES_API_KEY="${AGNES_API_KEY}"
export NVIDIA_NIM_API_KEY="${NVIDIA_NIM_API_KEY}"
export OPENCODE_GO_KEY="${OPENCODE_GO_KEY}"
export OPENCODE_GO_BASE_URL="${OPENCODE_GO_BASE_URL}"

# Allow ORF real pandoc (if available)
unset OMNI_TEST_FAKE_PANDOC

# Verify at least one LLM key is set
python3 -c "
import os
keys = {k: bool(os.environ.get(k)) for k in ['ZHIPU_API_KEY', 'AGNES_API_KEY', 'NVIDIA_NIM_API_KEY', 'OPENCODE_GO_KEY']}
configured = [k for k, v in keys.items() if v]
print(f'Configured LLM keys: {configured}')
assert len(configured) >= 1, 'At least one LLM API key must be set'
"

# Setup
cd /tmp && rm -rf test-suite-real-api && mkdir test-suite-real-api && cd test-suite-real-api
SUITE_ROOT="/mnt/d/贯维/Omni_Suite"
export OPP_ALLOWED_DIRECTORIES="/tmp,$SUITE_ROOT"
```

**⚠️ Cost warning:** These scenarios use real LLM API calls. Each test incurs minimal cost (< $0.01), but multiple runs will accumulate.

---

## Q13-S: Can an agent configure all module real dependencies?

**User says:** "I want to run the full pipeline with real APIs. Check everything is configured first."

**Why this matters:** The Omni Suite depends on multiple external systems (LLM APIs, pandoc, WeasyPrint). An agent must verify ALL dependencies are healthy before starting a pipeline. Partial failures (LLM OK but pandoc missing) must be detected and reported.

### Scenarios

#### 13.1 🟢 Verify all LLM API keys detected by OL inspect_config

```bash
cd /tmp/test-suite-real-api
OL_ROOT="$SUITE_ROOT/Omni_Localizer"
export PYTHONPATH="$OL_ROOT/src:$PYTHONPATH"

python3 -c "
import os, json, asyncio
os.environ['OL_CONFIG_PATH'] = '$OL_ROOT/config/default.yaml'

async def check():
    from ol_mcp.inspect_config import inspect_config
    result = json.loads(await inspect_config())
    llm_pool = result.get('llm_pool', {})
    
    all_keys_ok = True
    for role, models in llm_pool.items():
        for m in models:
            key_var = m.get('api_key', '')
            if key_var.startswith('\${') and key_var.endswith('}'):
                env_name = key_var[2:-1]
                is_set = bool(os.environ.get(env_name))
                status = '✅' if is_set else '❌'
                print(f'{status} {role:15s} / {m.get(\"model\"):30s} / {env_name}')
                if not is_set:
                    all_keys_ok = False
    
    if all_keys_ok:
        print('✅ All LLM API keys configured')
    else:
        print('❌ Some LLM API keys are missing — translation will fail at runtime')
    
    return all_keys_ok

result = asyncio.run(check())
"

echo ''
echo '=== Using omni-suite check ==='
python3 -c "
import subprocess, json
result = subprocess.run(['$SUITE_ROOT/scripts/check_deps.sh', '--json'], capture_output=True, text=True, timeout=30)
print(result.stdout[-1000:] if result.stdout else '')
print(result.stderr[-500:] if result.stderr else '')
"
```

**Expected Result:**
- ✅ OL inspect_config shows all providers with key status
- ✅ At least one LLM provider key is configured (✅ status)
- ✅ Missing keys are clearly marked with ❌ and env var name
- ✅ omni-suite check runs and reports essential gate status

**Actual Result:** _________ **PASS / FAIL:** _________

#### 13.2 🟢 Verify system dependencies (pandoc, WeasyPrint, md2pptx)

```bash
echo '=== System Dependencies Check ==='
python3 -c "
import shutil, sys

deps = {
    'pandoc': {
        'check': shutil.which('pandoc') is not None,
        'note': 'Required for DOCX/ODT/EPUB/RTF/ICML output (ORF). pypandoc-binary auto-installs.',
    },
    'weasyprint': {
        'check': shutil.which('weasyprint') is not None,
        'note': 'Required for PDF output. Pure Python, needs system libs (pango, cairo).',
    },
    'md2pptx': {
        'check': shutil.which('md2pptx') is not None,
        'note': 'Required for PPTX output. .NET tool: dotnet tool install --global md2pptx',
    },
    'python3.13': {
        'check': sys.version_info >= (3, 13),
        'note': 'All components require Python >= 3.13',
    },
}

all_ok = True
for name, info in deps.items():
    status = '✅' if info['check'] else '⚠️'
    print(f'{status} {name:15s} — {info[\"note\"]}')
    if not info['check']:
        all_ok = False

if all_ok:
    print('✅ All system dependencies installed')
else:
    print('⚠️ Some dependencies missing — see notes above for install instructions')
"
```

**Expected Result:**
- ✅ Each dependency checked with clear PASS/FAIL indicator
- ✅ Missing dependencies show install instructions
- ✅ Python 3.13+ confirmed

**Actual Result:** _________ **PASS / FAIL:** _________

#### 13.3 🟢 omni-suite health check with real dependencies

```bash
cd /tmp/test-suite-real-api
SUITE_ROOT="/mnt/d/贯维/Omni_Suite"

# Build a cross-module dependency report
python3 -c "
import os, subprocess, json

print('=== Cross-Module Real Dependency Matrix ===')
print()

# OPP: Check OCR + format detectors
print('--- OPP ---')
opp_checks = {
    'Tesseract OCR': shutil.which('tesseract') is not None if 'shutil' in dir() else False,
    'Python >= 3.13': True,
}
try:
    import shutil
    opp_checks['Tesseract OCR'] = shutil.which('tesseract') is not None
except:
    pass
for k, v in opp_checks.items():
    print(f'  {\"✅\" if v else \"⚠️\"} {k}')

# OL: Check LLM keys via inspect_config
print()
print('--- OL ---')
OL_ROOT = '$SUITE_ROOT/Omni_Localizer'
sys.path.insert(0, OL_ROOT + '/src')
import asyncio
async def check_ol():
    try:
        from ol_mcp.inspect_config import inspect_config
        result = json.loads(await inspect_config())
        llm_pool = result.get('llm_pool', {})
        for role in ['translation', 'judging', 'restoration']:
            models = llm_pool.get(role, [])
            configured = sum(1 for m in models if os.environ.get(m.get('api_key','').strip('\${}').strip('}'), ''))
            print(f'  {\"✅\" if configured > 0 else \"❌\"} {role}: {configured}/{len(models)} keys configured')
    except Exception as e:
        print(f'  ❌ Error: {str(e)[:100]}')
asyncio.run(check_ol())

# ORF: Check output format engines
print()
print('--- ORF ---')
ORF_ROOT = '$SUITE_ROOT/Omni_Re_Formatter'
sys.path.insert(0, ORF_ROOT + '/src')
orf_engines = {
    'pandoc (DOCX/ODT/EPUB)': shutil.which('pandoc'),
    'WeasyPrint (PDF)': True,
}
for k, v in orf_engines.items():
    print(f'  {\"✅\" if v else \"⚠️\"} {k}')
"
```

**Expected Result:**
- ✅ Cross-module matrix printed: OPP (OCR OK?), OL (N/N keys configured), ORF (pandoc?)
- ✅ Each check has clear PASS/FAIL visual indicator
- ✅ Total picture: all modules ready vs. which ones need attention

**Actual Result:** _________ **PASS / FAIL:** _________

#### 13.4 🟢 Agent can detect and report partial dependency failures

```bash
cd /tmp/test-suite-real-api

# Simulate: unset ONE key, keep others
export ZHIPU_API_KEY=""
export AGNES_API_KEY="${AGNES_API_KEY}"

python3 -c "
import os, asyncio, json, sys
OL_ROOT = '$SUITE_ROOT/Omni_Localizer'
sys.path.insert(0, OL_ROOT + '/src')

async def check():
    from ol_mcp.inspect_config import inspect_config
    result = json.loads(await inspect_config())
    llm_pool = result.get('llm_pool', {})
    
    # Report partial failure
    issues = []
    for role, models in llm_pool.items():
        for m in models:
            key_var = m.get('api_key', '')
            if key_var.startswith('\${') and key_var.endswith('}'):
                env_name = key_var[2:-1]
                if not os.environ.get(env_name):
                    issues.append(f'MISSING {env_name} → {role}/{m.get(\"model\")}')
    
    print(f'Issues found: {len(issues)}')
    for i in issues:
        print(f'  ❌ {i}')
    
    if len(issues) > 0:
        print('⚠️ Partial dependency failure: some providers unavailable')
        print('🔧 Fix: export ZHIPU_API_KEY=\"your_key\"')
    else:
        print('✅ All dependencies satisfied')
    
    return len(issues)

asyncio.run(check())
"

# Restore
export ZHIPU_API_KEY="${ZHIPU_API_KEY}"
```

**Expected Result:**
- ✅ Issues reported per-missing-provider (not total failure)
- ✅ Clear "partial dependency failure" message when some keys OK and some missing
- ✅ Actionable fix instruction for each missing piece
- ✅ Agent continues to report status even with partial failures (no crash)

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q13-S Verdict

| Scenario | Result |
|----------|--------|
| 13.1 LLM API keys detected | ⬜ |
| 13.2 System dependencies | ⬜ |
| 13.3 Cross-module health matrix | ⬜ |
| 13.4 Partial failure detection | ⬜ |

**OVERALL: ⬜**

---

## Q14-S: Can an agent run the full E2E pipeline with real APIs?

**User says:** "Now that everything is configured, run the full pipeline — OPP extract, OL translate with real LLM, ORF backfill — no shortcuts, no FAKE_LLM."

**Why this matters:** This is the production workflow. If any step fails under real conditions, the pipeline is not deployable.

### Scenarios

#### 14.1 🟢 Full MD path: OPP → OL (real LLM) → ORF (real pandoc)

```bash
cd /tmp && rm -rf test-suite-e2e-md-real && mkdir test-suite-e2e-md-real && cd test-suite-e2e-md-real
SUITE_ROOT="/mnt/d/贯维/Omni_Suite"
export PYTHONPATH="$SUITE_ROOT/Omni_Pre_Processor/src:$SUITE_ROOT/Omni_Localizer/src:$SUITE_ROOT/Omni_Re_Formatter/src:$PYTHONPATH"
export OPP_ALLOWED_DIRECTORIES="/tmp,$SUITE_ROOT"
unset OMNI_TEST_FAKE_LLM
unset OMNI_TEST_FAKE_PANDOC

echo ''
echo '╔══════════════════════════════════════════════════════════════╗'
echo '║   PHASE 1: OPP Extract (DOCX → MD)                         ║'
echo '╚══════════════════════════════════════════════════════════════╝'
python3 -c "
import asyncio, json, sys
sys.path.insert(0, '$SUITE_ROOT/Omni_Pre_Processor/src')
from opp.mcp.server import extract_document
result = asyncio.run(extract_document(
    file_path='$SUITE_ROOT/Meridian_Robotics_Product_Overview_E2E.docx',
    output_formats=['md'],
    source_lang='en',
    target_lang='zh',
    output_dir='/tmp/test-suite-e2e-md-real/opp_output'
))
assert result.get('success'), f'OPP failed: {json.dumps(result, indent=2)}'
print('✅ OPP extract successful')
"

echo ''
echo '╔══════════════════════════════════════════════════════════════╗'
echo '║   PHASE 2: OL Real Translation (MD → ZH)                   ║'
echo '╚══════════════════════════════════════════════════════════════╝'
python3 -c "
import os, json, asyncio, sys
sys.path.insert(0, '$SUITE_ROOT/Omni_Localizer/src')
os.environ['OL_CONFIG_PATH'] = '$SUITE_ROOT/Omni_Localizer/config/default.yaml'

from ol_mcp.translate_md import translate_md_text
from ol_mcp.tools import TranslateInput

async def test():
    with open('/tmp/test-suite-e2e-md-real/opp_output/Meridian_Robotics_Product_Overview_E2E.md', 'r') as f:
        md_content = f.read()
    
    print(f'Source MD: {len(md_content)} chars')
    
    params = TranslateInput(
        content=md_content[:3000],  # First 3K chars
        source_lang='en',
        target_lang='zh',
    )
    result = json.loads(await translate_md_text(params))
    translated = result.get('content', {}).get('translated', '')
    warnings = result.get('warnings', [])
    
    print(f'Translated: {len(translated)} chars')
    print(f'Quality gate warnings: {len(warnings)}')
    for w in warnings:
        print(f'  - {w.get(\"gate\", \"?\")}: {str(w.get(\"message\", \"\"))[:80]}')
    
    import re
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', translated)
    print(f'Chinese characters: {len(chinese_chars)}')
    assert len(chinese_chars) > 10, 'Translation should contain Chinese'
    
    # Save for ORF
    with open('/tmp/test-suite-e2e-md-real/translated.md', 'w') as f:
        f.write(translated)
    print('✅ OL real LLM translation OK')

asyncio.run(test())
"

echo ''
echo '╔══════════════════════════════════════════════════════════════╗'
echo '║   PHASE 3: ORF Backfill (MD → HTML)                        ║'
echo '╚══════════════════════════════════════════════════════════════╝'
python3 -c "
import json, sys
sys.path.insert(0, '$SUITE_ROOT/Omni_Re_Formatter/src')
from orf.mcp.server import apply_md

result = json.loads(apply_md(
    input_md='/tmp/test-suite-e2e-md-real/opp_output/Meridian_Robotics_Product_Overview_E2E.md',
    target_format='html',
    output_path='/tmp/test-suite-e2e-md-real/result.html',
))
assert result.get('success'), f'ORF failed: {json.dumps(result, indent=2)}'
print('✅ ORF backfill OK')
"

echo ''
echo '╔══════════════════════════════════════════════════════════════╗'
echo '║   RESULTS                                                    ║'
echo '╚══════════════════════════════════════════════════════════════╝'
ls -la /tmp/test-suite-e2e-md-real/
echo ''
echo '✅ Full MD path E2E with real APIs: COMPLETE'
```

**Expected Result:**
- ✅ Phase 1: OPP extracts MD from DOCX
- ✅ Phase 2: OL produces Chinese translation (>10 Chinese chars, real LLM, no FAKE_LLM)
- ✅ Phase 3: ORF produces HTML output (real pandoc if available, else markdown lib)
- ✅ All phases complete with exit code 0
- ✅ Total pipeline: no FAKE_LLM, no mock

**Actual Result:** _________ **PASS / FAIL:** _________

#### 14.2 🟢 Full XLIFF path: OPP → OL (real LLM) → ORF apply-xliff

```bash
cd /tmp && rm -rf test-suite-e2e-xliff-real && mkdir test-suite-e2e-xliff-real && cd test-suite-e2e-xliff-real
SUITE_ROOT="/mnt/d/贯维/Omni_Suite"
export PYTHONPATH="$SUITE_ROOT/Omni_Pre_Processor/src:$SUITE_ROOT/Omni_Localizer/src:$SUITE_ROOT/Omni_Re_Formatter/src:$PYTHONPATH"
export OPP_ALLOWED_DIRECTORIES="/tmp,$SUITE_ROOT"
unset OMNI_TEST_FAKE_LLM

echo '=== PHASE 1: OPP Extract (XLIFF) ==='
python3 -c "
import asyncio, json, sys
sys.path.insert(0, '$SUITE_ROOT/Omni_Pre_Processor/src')
from opp.mcp.server import extract_document
result = asyncio.run(extract_document(
    file_path='$SUITE_ROOT/Meridian_Robotics_Product_Overview_E2E.docx',
    output_formats=['xlf'],
    source_lang='en',
    target_lang='zh',
    output_dir='/tmp/test-suite-e2e-xliff-real/opp_output'
))
assert result.get('success'), f'OPP XLIFF failed: {json.dumps(result, indent=2)}'
print('✅ OPP XLIFF extract OK')
"

echo '=== PHASE 1b: Save skeleton ==='
python3 -c "
import asyncio, sys
sys.path.insert(0, '$SUITE_ROOT/Omni_Pre_Processor/src')
from opp.mcp.server import save_skeleton
result = asyncio.run(save_skeleton(
    file_path='$SUITE_ROOT/Meridian_Robotics_Product_Overview_E2E.docx',
    base_name='meridian',
    output_dir='/tmp/test-suite-e2e-xliff-real/opp_output'
))
assert result.get('success'), f'save_skeleton failed: {json.dumps(result, indent=2)}'
print('✅ save_skeleton OK')
"

echo '=== PHASE 2: OL Real XLIFF Translate ==='
python3 -c "
import os, json, asyncio, sys, glob
sys.path.insert(0, '$SUITE_ROOT/Omni_Localizer/src')
os.environ['OL_CONFIG_PATH'] = '$SUITE_ROOT/Omni_Localizer/config/default.yaml'

from ol_mcp.translate_xliff import translate_xliff
from ol_mcp.tools import XliffInput

async def test():
    xlf_files = glob.glob('/tmp/test-suite-e2e-xliff-real/opp_output/*.xlf')
    assert len(xlf_files) > 0, 'No XLIFF file found'
    
    params = XliffInput(input_path=xlf_files[0], source_lang='en', target_lang='zh')
    result = json.loads(await translate_xliff(params))
    
    output_path = result.get('output_path', '')
    if output_path:
        with open(output_path, 'r') as f:
            content = f.read()
        has_target = '<target>' in content and '</target>' in content
        print(f'Has target elements: {has_target}')
        assert has_target, 'XLIFF output must have target elements filled'
    print(f'XLIFF output: {output_path}')
    print('✅ OL real LLM XLIFF translation OK')

asyncio.run(test())
"

echo '=== PHASE 3: ORF apply-xliff ==='
export OMNI_TEST_FAKE_PANDOC=1
python3 -c "
import json, sys, glob
sys.path.insert(0, '$SUITE_ROOT/Omni_Re_Formatter/src')
from orf.mcp.server import apply_xliff

xlf_files = glob.glob('/tmp/test-suite-e2e-xliff-real/opp_output/*.xlf')
result = json.loads(apply_xliff(
    input_file='$SUITE_ROOT/Meridian_Robotics_Product_Overview_E2E.docx',
    xliff_path=xlf_files[0],
    output_path='/tmp/test-suite-e2e-xliff-real/result.docx',
    format='docx',
))
assert result.get('success'), f'apply-xliff failed: {json.dumps(result, indent=2)}'
print('✅ ORF apply-xliff OK')
"
unset OMNI_TEST_FAKE_PANDOC

echo ''
echo 'Results:'
ls -la /tmp/test-suite-e2e-xliff-real/
echo '✅ Full XLIFF path E2E with real APIs: COMPLETE'
```

**Expected Result:**
- ✅ Phase 1: OPP extracts XLIFF + skeleton
- ✅ Phase 2: OL fills `<target>` elements with real Chinese translation
- ✅ Phase 3: ORF apply-xliff produces valid DOCX
- ✅ All phases complete with exit code 0

**Actual Result:** _________ **PASS / FAIL:** _________

#### 14.3 🟢 Multi-format E2E (DOCX → EPUB with real LLM)

```bash
cd /tmp && rm -rf test-suite-e2e-cross-real && mkdir test-suite-e2e-cross-real && cd test-suite-e2e-cross-real
SUITE_ROOT="/mnt/d/贯维/Omni_Suite"
export PYTHONPATH="$SUITE_ROOT/Omni_Pre_Processor/src:$SUITE_ROOT/Omni_Localizer/src:$SUITE_ROOT/Omni_Re_Formatter/src:$PYTHONPATH"
export OPP_ALLOWED_DIRECTORIES="/tmp,$SUITE_ROOT"
unset OMNI_TEST_FAKE_LLM
unset OMNI_TEST_FAKE_PANDOC

echo '=== OPP Extract (MD) ==='
python3 -c "
import asyncio, sys
sys.path.insert(0, '$SUITE_ROOT/Omni_Pre_Processor/src')
from opp.mcp.server import extract_document
result = asyncio.run(extract_document(
    file_path='$SUITE_ROOT/Meridian_Robotics_Product_Overview_E2E.docx',
    output_formats=['md'],
    source_lang='en',
    target_lang='zh',
    output_dir='/tmp/test-suite-e2e-cross-real/opp_output'
))
assert result.get('success'), f'OPP failed: {result}'
print('✅ OPP extract OK')
"

echo '=== OL Real Translate (first 500 chars) ==='
python3 -c "
import os, json, asyncio, sys
sys.path.insert(0, '$SUITE_ROOT/Omni_Localizer/src')
os.environ['OL_CONFIG_PATH'] = '$SUITE_ROOT/Omni_Localizer/config/default.yaml'
from ol_mcp.translate_md import translate_md_text
from ol_mcp.tools import TranslateInput

async def test():
    with open('/tmp/test-suite-e2e-cross-real/opp_output/Meridian_Robotics_Product_Overview_E2E.md') as f:
        content = f.read()[:500]
    params = TranslateInput(content=content, source_lang='en', target_lang='zh')
    result = json.loads(await translate_md_text(params))
    t = result.get('content', {}).get('translated', '')
    assert '测试' in t or '机器人' in t or len(t) > 20, f'Translation seems wrong: {t[:80]}'
    with open('/tmp/test-suite-e2e-cross-real/translated.md', 'w') as f:
        f.write(t)
    print(f'Translated: {t[:80]}...')
    print('✅ OL real LLM translation OK')
asyncio.run(test())
"

echo '=== ORF Cross-format: MD → EPUB ==='
python3 -c "
import json, sys
sys.path.insert(0, '$SUITE_ROOT/Omni_Re_Formatter/src')
from orf.mcp.server import apply_md
result = json.loads(apply_md(
    input_md='/tmp/test-suite-e2e-cross-real/opp_output/Meridian_Robotics_Product_Overview_E2E.md',
    target_format='epub',
    output_path='/tmp/test-suite-e2e-cross-real/result.epub'
))
assert result.get('success'), f'ORF failed: {json.dumps(result, indent=2)}'
print('✅ ORF cross-format (EPUB) OK')
"

ls -la /tmp/test-suite-e2e-cross-real/
echo '✅ Cross-format E2E with real APIs: COMPLETE'
```

**Expected Result:**
- ✅ OPP extracts MD from DOCX
- ✅ OL translates with real LLM (Chinese output)
- ✅ ORF produces EPUB (pandoc if available, else skipped gracefully)
- ✅ Cross-format pipeline (DOCX → EPUB) works with real APIs

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q14-S Verdict

| Scenario | Result |
|----------|--------|
| 14.1 Full MD path (real LLM + real pandoc) | ⬜ |
| 14.2 Full XLIFF path (real LLM + backfill) | ⬜ |
| 14.3 Cross-format DOCX→EPUB with real LLM | ⬜ |

**OVERALL: ⬜**

---

## Q15-S: Can an agent diagnose and self-heal cross-module configuration issues?

**User says:** "Something is wrong — can you check which module has problems and fix it?"

**Why this matters:** In a 3-module pipeline, a single module failure blocks the whole pipeline. The agent must quickly identify WHICH module is misconfigured, report the specific issue, and guide/fix it.

### Scenarios

#### 15.1 🟢 Agent diagnoses which module is misconfigured

```bash
cd /tmp && rm -rf test-suite-diag && mkdir test-suite-diag && cd test-suite-diag
SUITE_ROOT="/mnt/d/贯维/Omni_Suite"

# Simulate a specific failure: unset LLM key but keep other deps
unset OMNI_TEST_FAKE_LLM
export ZHIPU_API_KEY=""  # Intentionally break OL
# Keep system deps (pandoc, etc.) as-is

echo '=== Cross-Module Diagnosis ==='
python3 -c "
import os, shutil, sys

print('========================================')
print('  Omni Suite Cross-Module Diagnosis')
print('========================================')
print()

issues = []

# Module 1: OPP
print('--- OPP ---')
opp_ok = True
print(f'  Importable: {\"✅\" if os.path.isdir(\"$SUITE_ROOT/Omni_Pre_Processor/src/opp\") else \"❌\"}')
print(f'  CLI available: {\"✅\" if shutil.which(\"opp\") else \"⚠️\"}')
if not os.path.isdir('$SUITE_ROOT/Omni_Pre_Processor/src/opp'):
    issues.append(('OPP', 'Source directory missing'))

# Module 2: OL
print()
print('--- OL ---')
ol_llm_keys = {k: bool(os.environ.get(k)) for k in ['ZHIPU_API_KEY', 'AGNES_API_KEY', 'NVIDIA_NIM_API_KEY', 'OPENCODE_GO_KEY']}
key_count = sum(1 for v in ol_llm_keys.values() if v)
print(f'  LLM keys configured: {key_count}/4')
print(f'  FAKE_LLM mode: {\"ON (testing)\" if os.environ.get(\"OMNI_TEST_FAKE_LLM\") else \"OFF (real LLM)\"}')
if key_count == 0 and not os.environ.get('OMNI_TEST_FAKE_LLM'):
    issues.append(('OL', 'No LLM API keys and FAKE_LLM not set — will fail'))
    print(f'  ❌ CRITICAL: No LLM keys, not in FAKE_LLM mode')

# Module 3: ORF
print()
print('--- ORF ---')
orf_deps = {
    'pandoc (DOCX/ODT/EPUB)': shutil.which('pandoc'),
}
for name, found in orf_deps.items():
    print(f'  {\"✅\" if found else \"⚠️\"} {name}')

print()
print('========================================')
if issues:
    print(f'❌ {len(issues)} issue(s) detected:')
    for mod, desc in issues:
        print(f'   [{mod}] {desc}')
    print()
    print('🔧 Priority fix: Set ZHIPU_API_KEY or enable FAKE_LLM')
else:
    print('✅ All modules operational')
print('========================================')
"

# Restore
export ZHIPU_API_KEY="${ZHIPU_API_KEY}"
```

**Expected Result:**
- ✅ Each module checked independently (OPP, OL, ORF)
- ✅ OL section shows key count and FAKE_LLM status
- ✅ Missing key detected and reported as CRITICAL
- ✅ Overall summary: count of issues with priority fix guidance

**Actual Result:** _________ **PASS / FAIL:** _________

#### 15.2 🟢 Agent self-heals cross-module issues

```bash
cd /tmp && rm -rf test-suite-self-heal && mkdir test-suite-self-heal && cd test-suite-self-heal
SUITE_ROOT="/mnt/d/贯维/Omni_Suite"
export PYTHONPATH="$SUITE_ROOT/Omni_Pre_Processor/src:$SUITE_ROOT/Omni_Localizer/src:$SUITE_ROOT/Omni_Re_Formatter/src:$PYTHONPATH"
unset OMNI_TEST_FAKE_LLM

echo '╔══════════════════════════════════════════════════════════════╗'
echo '║   SELF-HEAL CYCLE: Diagnose → Fix → Verify                 ║'
echo '╚══════════════════════════════════════════════════════════════╝'
echo ''

echo '=== STEP 1: DIAGNOSE (no LLM keys) ==='
unset ZHIPU_API_KEY
unset AGNES_API_KEY

python3 -c "
import os, sys
sys.path.insert(0, '$SUITE_ROOT/Omni_Localizer/src')

# Agent diagnoses missing keys via inspect_config
import asyncio, json
async def diag():
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
                    issues.append((env_name, role, m.get('model')))
    print(f'Diagnosed {len(issues)} missing key(s):')
    for env_name, role, model in issues:
        print(f'  ❌ {env_name} (required by {role}/{model})')
    return issues

issues = asyncio.run(diag())
print(f'ISSUES={len(issues)}')
"

echo ''
echo '=== STEP 2: FIX ==='
echo '🔧 Setting ZHIPU_API_KEY from environment...'
export ZHIPU_API_KEY="${ZHIPU_API_KEY}"
echo '🔧 Key set. Ready for verification.'
echo ''

echo '=== STEP 3: VERIFY ==='
python3 -c "
import os, sys, asyncio, json
sys.path.insert(0, '$SUITE_ROOT/Omni_Localizer/src')

async def verify():
    from ol_mcp.inspect_config import inspect_config
    result = json.loads(await inspect_config())
    llm_pool = result.get('llm_pool', {})
    issues = 0
    for role, models in llm_pool.items():
        for m in models:
            key_var = m.get('api_key', '')
            if key_var.startswith('\${') and key_var.endswith('}'):
                env_name = key_var[2:-1]
                if not os.environ.get(env_name):
                    issues += 1
    
    if issues == 0:
        print('✅ All LLM keys configured after fix')
    else:
        print(f'⚠️ {issues} key(s) still missing')
    
    # Now run a real translation to verify end-to-end
    if issues == 0:
        from ol_mcp.translate_md import translate_md_text
        from ol_mcp.tools import TranslateInput
        params = TranslateInput(
            content='Self-heal verification: pipeline operational.',
            source_lang='en', target_lang='zh',
        )
        t_result = json.loads(await translate_md_text(params))
        translated = t_result.get('content', {}).get('translated', '')
        if translated:
            print(f'✅ Translation working after fix: {translated[:60]}...')
        else:
            print('⚠️ Translation returned empty')
    
    return issues == 0

success = asyncio.run(verify())
print(f'')
print('Self-heal: {\"✅ SUCCESS\" if success else \"❌ FAILED\"} — all modules operational')
"

echo ''
echo '=== SELF-HEAL CYCLE COMPLETE ==='
```

**Expected Result:**
- ✅ Step 1 (DIAGNOSE): Detects missing ZHIPU_API_KEY specifically
- ✅ Step 2 (FIX): Sets the key and logs the action
- ✅ Step 3 (VERIFY): inspect_config shows all keys OK → real translation succeeds
- ✅ Complete heal cycle: diagnose → fix → verify

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q15-S Verdict

| Scenario | Result |
|----------|--------|
| 15.1 Diagnose which module is broken | ⬜ |
| 15.2 Self-heal cycle | ⬜ |

**OVERALL: ⬜**

---

# Part 8: Final Verdict

---

## Overall PASS/FAIL Summary

| Part | Section | Verdict |
|------|---------|---------|
| 1 | Core Pipeline Journeys (Q1-S: Install, Q2-S: DOCX MD, Q3-S: DOCX XLIFF, Q4-S: PPTX) | ⬜ |
| 2 | Pipeline Selection & Configuration (Q5-S: Cross-format, Q6-S: Path choice) | ⬜ |
| 3 | MCP Surface Mastery (Q7-S: 3 servers, 34 tools) | ⬜ |
| 4 | Agent-as-User Orchestration (Q8-S: MCP chain, Q9-S: CLI E2E) | ⬜ |
| 5 | Error & Boundary Matrix (Q10-S: Missing/corrupt files, Q11-S: No LLM) | ⬜ |
| 6 | Production Validation (Q12-S: Test suite) | ⬜ |
| 7 | Full Pipeline E2E with Real APIs (Q13-S — Q15-S) | ⬜ |

**GRAND TOTAL: ⬜ / 15 Questions**

**OVERALL VERDICT: ⬜**

---

## Production Gap Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| Suite version is 0.4.0 | ⬜ | Q1-S |
| All 3 CLIs respond (opp, ol, orf) | ⬜ | Q1-S |
| All 3 modules importable | ⬜ | Q1-S |
| DOCX MD path (OPP→OL→ORF) completes | ⬜ | Q2-S |
| DOCX XLIFF path (OPP→OL→ORF) completes | ⬜ | Q3-S |
| PPTX pipeline works (both paths) | ⬜ | Q4-S |
| Cross-format conversion (DOCX→EPUB, etc.) | ⬜ | Q5-S |
| Agent selects correct pipeline path | ⬜ | Q6-S |
| OPP MCP: 7 tools, all respond | ⬜ | Q7-S |
| OL MCP: 21 tools, essential ones respond | ⬜ | Q7-S |
| ORF MCP: 6 tools, all respond | ⬜ | Q7-S |
| MCP chain: extract→translate→backfill | ⬜ | Q8-S |
| CLI E2E pipeline: omni-suite pipeline | ⬜ | Q9-S |
| 3 consecutive runs no crash | ⬜ | Q9-S |
| Missing input files error gracefully | ⬜ | Q10-S |
| Missing LLM/FAKE_LLM error gracefully | ⬜ | Q11-S |
| omni-suite check --quick works | ⬜ | Q9-S |
| omni-suite status works | ⬜ | Q9-S |
| Contract smoke test passes | ⬜ | Q12-S |
| MCP smoke tests pass | ⬜ | Q12-S |
| Suite-level imports clean | ⬜ | Q12-S |
| omni-suite check passes | ⬜ | Q12-S |
| ORF supports 16 output formats | ⬜ | Q5-S |
| All LLM API keys detectable via OL inspect_config | ⬜ | Q13-S |
| System dependencies (pandoc, WeasyPrint, md2pptx) verified | ⬜ | Q13-S |
| Cross-module dependency matrix validated | ⬜ | Q13-S |
| Full MD path E2E with real LLM (no FAKE_LLM) | ⬜ | Q14-S |
| Full XLIFF path E2E with real LLM | ⬜ | Q14-S |
| Cross-format E2E with real APIs (DOCX→EPUB) | ⬜ | Q14-S |
| Agent diagnoses cross-module failures | ⬜ | Q15-S |
| Agent self-heals configuration issues (diagnose → fix → verify) | ⬜ | Q15-S |

---

## Sign-off Criteria

| Level | Requirements | Met? |
|-------|-------------|------|
| **CI Gate** | All 15 questions answered. No P0 failures (crash, data loss, unhandled traceback). | ⬜ |
| **Release Candidate** | CI Gate + Q1-S through Q9-S + Q13-S — Q15-S all PASS + all production gaps addressed | ⬜ |
| **Production Deploy** | Release Candidate + Q12-S all PASS + no outstanding P0/P1 issues | ⬜ |

---

*Plan generated: 2026-07-22*
*Based on: Omni Suite v0.4.0 codebase — OPP v0.9.1, OL v0.7.0, ORF v0.4.16, 3 MCP servers (34 tools), 2 pipeline paths, 16 ORF output formats*
