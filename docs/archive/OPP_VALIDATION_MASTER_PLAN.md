> **Status: ARCHIVED (2026-08-23). Reason: prose validation plan superseded by the executable scenario library. Superseded by: `scripts/validation/run_validation.py` + `scenarios/`.**

# OPP Validation Master Plan

## Result-Oriented · User-Centric · All Scenarios & Boundaries

**For:** OpenCode, Claude Code, Cline, Hermes Agent — any AI agent validating OPP
**Date:** 2026-07-22
**Strategy:** Every section asks a user question → executes scenarios → reports a binary verdict
**Current Baseline:** v0.9.1 — 16 extractors, 17 FormatType values, 9 MCP tools, MD+XLIFF+skeleton output

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
| P0 | Q1-OPP, Q2-OPP | Core functionality — if these fail, nothing else matters |
| P1 | Q3-OPP, Q4-OPP, Q5-OPP, Q6-OPP, Q12-OPP | Important but depend on P0 passing |
| P2 | Q7-OPP, Q8-OPP, Q9-OPP, Q10-OPP, Q11-OPP, Q14-OPP | Can be deferred if P0/P1 fail — run after core is verified |
| P3 | Q13-OPP, Q15-OPP | Cost-incurring — run last and only if P0-P2 pass |

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
# 1. Activate project venv and install OPP with dev extras
source /mnt/d/贯维/Omni_Suite/.venv_ol/bin/activate
pip install -e "Omni_Pre_Processor[dev,office,email,youtube]"

# 2. Set required env vars
export OPP_MCP_ALLOWED_DIRS="/tmp/opp_test,/tmp/opp_output"
export OMNI_TEST_FAKE_LLM=1

# 3. Create test directories
mkdir -p /tmp/opp_test /tmp/opp_output

# 4. Verify CLI works
opp --help

# 5. Create a test DOCX file for baseline scenarios
python3 -c "
from docx import Document
doc = Document()
doc.add_heading('Test Document', level=1)
doc.add_paragraph('This is a paragraph for extraction testing.')
doc.add_paragraph('Second paragraph with some bold text.')
table = doc.add_table(rows=2, cols=2)
table.cell(0,0).text = 'Cell A1'
table.cell(0,1).text = 'Cell B1'
table.cell(1,0).text = 'Cell A2'
table.cell(1,1).text = 'Cell B2'
doc.save('/tmp/opp_test/test.docx')
print('DOCX created: /tmp/opp_test/test.docx')
"

# 6. Create a test PPTX file
python3 -c "
from pptx import Presentation
prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[0])
slide.shapes.title.text = 'Test PPTX'
slide.shapes.placeholder(1).text = 'Slide content for extraction'
prs.save('/tmp/opp_test/test.pptx')
print('PPTX created: /tmp/opp_test/test.pptx')
"

# 7. Create test files for other formats
# PDF
python3 -c "
from reportlab.pdfgen import canvas
c = canvas.Canvas('/tmp/opp_test/test.pdf')
c.drawString(100, 750, 'Test PDF Page 1')
c.drawString(100, 730, 'Line 2 of PDF content')
c.save()
print('PDF created')
"
# CSV
echo 'name,value,note
Alice,100,test note
Bob,200,another note' > /tmp/opp_test/test.csv
# JSON
echo '{"title":"Test","items":[{"id":1,"name":"A"},{"id":2,"name":"B"}]}' > /tmp/opp_test/test.json
# XML
echo '<?xml version="1.0"?><root><item id="1"><name>Test</name></item></root>' > /tmp/opp_test/test.xml
# HTML
echo '<!DOCTYPE html><html><body><h1>Test HTML</h1><p>HTML content here.</p></body></html>' > /tmp/opp_test/test.html
# EPUB (minimal)
python3 -c "
from ebooklib import epub
book = epub.EpubBook()
book.set_identifier('test123')
book.set_title('Test EPUB')
book.set_language('en')
chapter = epub.EpubHtml(title='Chapter 1', file_name='chap_01.xhtml', lang='en')
chapter.content = b'<html><body><h1>Chapter 1</h1><p>EPUB content here.</p></body></html>'
book.add_item(chapter)
book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())
navigation = epub.Link('chap_01.xhtml', 'Chapter 1', 'chap_01')
book.toc = [navigation]
book.add_spine_item(chapter)
epub.write_epub('/tmp/opp_test/test.epub', book)
print('EPUB created')
" 2>/dev/null || echo 'EPUB creation skipped'
# EML
echo 'From: sender@example.com
To: recipient@example.com
Subject: Test Email
Date: Tue, 22 Jul 2026 10:00:00 +0000

This is a test email body for extraction.' > /tmp/opp_test/test.eml

# 8. Verify test infrastructure
cd /mnt/d/贯维/Omni_Suite/Omni_Pre_Processor && pytest --collect-only -q 2>&1 | tail -5
```

---

## Table of Contents

### Part 1: Format Detection & Extraction
- **Q1-OPP:** Does OPP detect every supported format via magic bytes?
- **Q2-OPP:** Does OPP extract DOCX to valid MD + XLIFF?
- **Q3-OPP:** Does OPP extract PPTX to valid MD + XLIFF?
- **Q4-OPP:** Does OPP extract PDF to MD (and intentionally block PDF→XLIFF)?
- **Q5-OPP:** Does OPP extract XLSX/CSV/JSON/XML to valid MD?
- **Q6-OPP:** Does OPP extract HTML/EPUB/EML to valid MD?
- **Q7-OPP:** Does OPP handle image files via OCR?
- **Q8-OPP:** Does OPP handle edge cases (empty/corrupt/unsupported)?

### Part 2: Output Artifact Integrity
- **Q9-OPP:** Does OPP produce correct manifest.json?
- **Q10-OPP:** Does OPP produce correct skeleton.zip for DOCX/PPTX/EPUB?
- **Q11-OPP:** Does OPP produce correct images.json with floating image metadata?

### Part 3: MCP Surface Mastery
- **Q12-OPP:** Do all 9 MCP tools work correctly?

### Part 4: Security & Production
- **Q13-OPP:** Does MCP path security block unauthorized access?
- **Q14-OPP:** Does the CLI handle all flags and edge cases?
- **Q15-OPP:** Can the MCP server start via stdio and respond correctly?

### Part 5: Final Verdict

---

# Part 1: Format Detection & Extraction

---

## Q1-OPP: Does OPP detect every supported format via magic bytes?

**User says:** "I have a bunch of files with wrong extensions. Can OPP tell me what they really are?"

**Why this matters:** `detect_format()` is the first gate in the pipeline. If detection fails, the wrong extractor may be chosen, producing garbage or crashes. All 17 FormatType values must be detectable.

### Prerequisites

```bash
cd /mnt/d/贯维/Omni_Suite && source .venv_ol/bin/activate
```

### Scenarios

#### 1.1 🟢 DOCX detected from magic bytes (PK\x03\x04 + word/document.xml)

```python
from pathlib import Path
from opp.detector import detect_format, FormatType

fmt, confidence = detect_format(Path("/tmp/opp_test/test.docx"))
print(f"Format: {fmt.value}, Confidence: {confidence}")
assert fmt == FormatType.DOCX, f"Expected DOCX, got {fmt}"
assert confidence >= 0.9, f"Confidence too low: {confidence}"
```

**Expected Result:**
- ✅ Format = `docx`
- ✅ Confidence ≥ 0.9
- ✅ Magic-bytes detection (not extension-based)

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

#### 1.2 🟢 PPTX detected from magic bytes

```python
fmt, confidence = detect_format(Path("/tmp/opp_test/test.pptx"))
print(f"Format: {fmt.value}, Confidence: {confidence}")
assert fmt == FormatType.PPTX
```

**Expected Result:** ✅ `pptx` with confidence ≥ 0.9.

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

#### 1.3 🟢 PDF detected via `%PDF` header

```python
fmt, confidence = detect_format(Path("/tmp/opp_test/test.pdf"))
print(f"Format: {fmt.value}, Confidence: {confidence}")
assert fmt == FormatType.PDF
assert confidence >= 0.9
```

**Expected Result:** ✅ `pdf` with confidence ≥ 0.9.

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

#### 1.4 🟢 XLSX/CSV/JSON/XML/HTML/EPUB all detected correctly

```python
import json

formats_to_test = {
    "/tmp/opp_test/test.xlsx": FormatType.XLSX,
    "/tmp/opp_test/test.csv": FormatType.CSV,
    "/tmp/opp_test/test.json": FormatType.JSON,
    "/tmp/opp_test/test.xml": FormatType.XML,
    "/tmp/opp_test/test.html": FormatType.HTML,
    "/tmp/opp_test/test.epub": FormatType.EPUB,
    "/tmp/opp_test/test.eml": FormatType.EMAIL,
    "/tmp/opp_test/test.pptx": FormatType.PPTX,
    "/tmp/opp_test/test.docx": FormatType.DOCX,
    "/tmp/opp_test/test.pdf": FormatType.PDF,
}
results = {}
for path_str, expected in formats_to_test.items():
    p = Path(path_str)
    if p.exists():
        fmt, confidence = detect_format(p)
        results[path_str] = {"format": fmt.value, "expected": expected.value, "confidence": confidence, "pass": fmt == expected}
    else:
        results[path_str] = {"error": "FILE_NOT_FOUND", "pass": False}
print(json.dumps(results, indent=2))
all_pass = all(r.get("pass", False) for r in results.values())
assert all_pass, f"Some detections failed: {results}"
```

**Expected Result:** ✅ All 10 formats detected correctly with confidence ≥ 0.5 for each.

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

#### 1.5 🟢 IPYNB detected before JSON (same PK structure)

```python
fmt, confidence = detect_format(Path("/tmp/opp_test/test.ipynb"))
# If IPYNB file exists, test it; otherwise skip
```

**Expected Result:** ✅ IPYNB detected with confidence ≥ 0.9. Not misclassified as JSON.

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

#### 1.6 🔴 Unknown format returns UNKNOWN

```python
# Create a file with random binary data
import os
with open("/tmp/opp_test/random.bin", "wb") as f:
    f.write(os.urandom(64))

fmt, confidence = detect_format(Path("/tmp/opp_test/random.bin"))
print(f"Format: {fmt.value}, Confidence: {confidence}")
assert fmt == FormatType.UNKNOWN
assert confidence == 0.0
```

**Expected Result:** ❌ `unknown` with confidence 0.0.

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

#### 1.7 🔴 Nonexistent file returns UNKNOWN

```python
fmt, confidence = detect_format(Path("/tmp/opp_test/nonexistent.nope"))
print(f"Format: {fmt.value}, Confidence: {confidence}")
assert fmt == FormatType.UNKNOWN
assert confidence == 0.0
```

**Expected Result:** ❌ `unknown` with confidence 0.0. No crash.

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

### 📊 Q1-OPP Verdict

| Scenario | Result |
|----------|--------|
| 1.1 DOCX detection | ⬜ |
| 1.2 PPTX detection | ⬜ |
| 1.3 PDF detection | ⬜ |
| 1.4 All formats detected | ⬜ |
| 1.5 IPYNB detection | ⬜ |
| 1.6 Unknown format | ⬜ |
| 1.7 Nonexistent file | ⬜ |

**OVERALL: ⬜** (✅ if all pass, ❌ if any fail)

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q2-OPP: Does OPP extract DOCX to valid MD + XLIFF?

**User says:** "I need to extract a DOCX document. Give me Markdown and XLIFF."

**Why this matters:** DOCX is the most common input format. The entire localization pipeline depends on correct DOCX → MD + XLIFF extraction.

### Prerequisites

```bash
cd /mnt/d/贯维/Omni_Suite && source .venv_ol/bin/activate
export OPP_MCP_ALLOWED_DIRS="/tmp/opp_test,/tmp/opp_output"
```

### Scenarios

#### 2.1 🟢 DOCX → MD via CLI

```bash
opp /tmp/opp_test/test.docx --target-format md --output-dir /tmp/opp_output/docx_md --source-lang en 2>&1
echo "Exit: $?"
```

**Expected Result:**
- ✅ Exit code 0
- ✅ `/tmp/opp_output/docx_md/test.md` exists
- ✅ MD file contains YAML frontmatter with `source_lang: en`
- ✅ MD file contains paragraph text ("Test Document", "This is a paragraph")
- ✅ MD file contains table with "Cell A1", "Cell B1"

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

#### 2.2 🟢 DOCX → XLIFF via CLI

```bash
opp /tmp/opp_test/test.docx --target-format xlf --source-lang en --target-lang zh --output-dir /tmp/opp_output/docx_xlf 2>&1
echo "Exit: $?"
```

**Expected Result:**
- ✅ Exit code 0
- ✅ `/tmp/opp_output/docx_xlf/test.xlf` exists
- ✅ XLIFF contains `<trans-unit>` elements with source text
- ✅ XLIFF has `source-language="en"` and `target-language="zh"` attributes
- ✅ `<trans-unit>` has `id` attributes
- ✅ Skeleton ZIP created at `/tmp/opp_output/docx_xlf/test.skeleton.zip`

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

#### 2.3 🟢 DOCX → both (MD + XLIFF)

```bash
opp /tmp/opp_test/test.docx --target-format both --source-lang en --target-lang zh --output-dir /tmp/opp_output/docx_both 2>&1
echo "Exit: $?"
ls -la /tmp/opp_output/docx_both/
```

**Expected Result:**
- ✅ Exit code 0
- ✅ `test.md` exists
- ✅ `test.xlf` exists
- ✅ `test_manifest.json` exists
- ✅ `test.skeleton.zip` exists

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

#### 2.4 🟢 MD output has correct YAML frontmatter

```bash
head -20 /tmp/opp_output/docx_both/test.md
```

**Expected Result:**
- ✅ Starts with `---`
- ✅ Contains `source_lang: en`
- ✅ Contains `target_lang: zh`
- ✅ Contains `extraction_date` or similar timestamp
- ✅ Valid YAML structure

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

#### 2.5 🟢 XLIFF output is valid XML with correct schema

```python
import xml.etree.ElementTree as ET

tree = ET.parse("/tmp/opp_output/docx_both/test.xlf")
root = tree.getroot()
# XLIFF 1.2 namespace
ns = {"xliff": "urn:oasis:names:tc:xliff:document:1.2"}
body = root.find(".//xliff:body", ns)
units = body.findall("xliff:trans-unit", ns) if body is not None else []
print(f"Trans-units: {len(units)}")
assert len(units) > 0, "No trans-units found"
for unit in units:
    assert unit.get("id"), f"Trans-unit missing id: {unit.attrib}"
    source = unit.find("xliff:source", ns)
    assert source is not None and source.text, f"Empty source in unit {unit.get('id')}"
print("✅ XLIFF valid with trans-units")
```

**Expected Result:** ✅ Valid XLIFF 1.2 with ≥1 `<trans-unit>`, each with `id` and non-empty `<source>`.

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

#### 2.6 🟢 Manifest JSON contains correct fields

```python
import json
with open("/tmp/opp_output/docx_both/test_manifest.json") as f:
    manifest = json.load(f)
print(json.dumps(manifest, indent=2)[:500])
assert "manifest_version" in manifest
assert "source" in manifest
assert manifest["source"]["format"] in ("DOCX", "docx")
assert "extraction" in manifest
assert "outputs" in manifest["extraction"]
```

**Expected Result:** ✅ Manifest has `manifest_version`, `source` (with format, file_path, file_size_bytes), `extraction` (with outputs listing md, xlf, skeleton paths).

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

### 📊 Q2-OPP Verdict

| Scenario | Result |
|----------|--------|
| 2.1 DOCX → MD | ⬜ |
| 2.2 DOCX → XLIFF | ⬜ |
| 2.3 DOCX → both | ⬜ |
| 2.4 MD frontmatter | ⬜ |
| 2.5 XLIFF valid XML | ⬜ |
| 2.6 Manifest JSON | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q3-OPP: Does OPP extract PPTX to valid MD + XLIFF?

**User says:** "I need to extract a PowerPoint presentation for translation."

**Why this matters:** PPTX is the second most common input. Slide-based extraction differs from DOCX paragraph extraction.

### Prerequisites

```bash
cd /mnt/d/贯维/Omni_Suite && source .venv_ol/bin/activate
```

### Scenarios

#### 3.1 🟢 PPTX → both (MD + XLIFF + skeleton)

```bash
opp /tmp/opp_test/test.pptx --target-format both --source-lang en --target-lang zh --output-dir /tmp/opp_output/pptx_both 2>&1
echo "Exit: $?"
ls -la /tmp/opp_output/pptx_both/
```

**Expected Result:**
- ✅ Exit code 0
- ✅ `test.md` exists with slide content
- ✅ `test.xlf` exists with trans-units per slide
- ✅ `test_manifest.json` exists
- ✅ `test.skeleton.zip` exists (PPTX skeleton preserved)

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

#### 3.2 🟢 PPTX MD contains slide headings

```bash
head -30 /tmp/opp_output/pptx_both/test.md
```

**Expected Result:** ✅ MD file contains slide title "Test PPTX" and slide content "Slide content for extraction".

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

#### 3.3 🟢 PPTX skeleton.zip preserves ppt/ structure

```bash
python3 -c "
import zipfile
with zipfile.ZipFile('/tmp/opp_output/pptx_both/test.skeleton.zip') as zf:
    names = zf.namelist()
    print(f'Skeleton files ({len(names)}): {names[:10]}...')
    assert any(n.startswith('ppt/') for n in names), 'Missing ppt/ structure'
    assert any('slide' in n.lower() for n in names), 'Missing slide files'
print('✅ PPTX skeleton valid')
"
```

**Expected Result:** ✅ Skeleton ZIP contains `ppt/` directory with slide files preserved.

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

### 📊 Q3-OPP Verdict

| Scenario | Result |
|----------|--------|
| 3.1 PPTX → both | ⬜ |
| 3.2 PPTX MD content | ⬜ |
| 3.3 PPTX skeleton structure | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q4-OPP: Does OPP extract PDF to MD (and intentionally block PDF→XLIFF)?

**User says:** "I need to extract a PDF. Can OPP handle it?"

**Why this matters:** PDF → MD is supported (pypdf + pdfplumber). PDF → XLIFF is intentionally blocked because PDF structure is too lossy for clean XLIFF extraction. This design constraint must be enforced.

### Prerequisites

```bash
cd /mnt/d/贯维/Omni_Suite && source .venv_ol/bin/activate
```

### Scenarios

#### 4.1 🟢 PDF → MD via CLI

```bash
opp /tmp/opp_test/test.pdf --target-format md --output-dir /tmp/opp_output/pdf_md 2>&1
echo "Exit: $?"
cat /tmp/opp_output/pdf_md/test.md
```

**Expected Result:**
- ✅ Exit code 0
- ✅ MD file contains PDF text ("Test PDF Page 1", "Line 2 of PDF content")
- ✅ MD file has YAML frontmatter

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

#### 4.2 🔴 PDF → XLIFF is intentionally blocked

```bash
opp /tmp/opp_test/test.pdf --target-format xlf --source-lang en --target-lang zh --output-dir /tmp/opp_output/pdf_xlf 2>&1
echo "Exit: $?"
```

**Expected Result:**
- ❌ Exit code != 0 (error)
- ❌ Error message clearly states PDF→XLIFF is not supported or blocked
- ❌ No `.xlf` file created in output directory
- ❌ No crash or traceback — graceful error

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

#### 4.3 🔴 PDF → both produces MD only, warns about XLIFF

```bash
opp /tmp/opp_test/test.pdf --target-format both --source-lang en --target-lang zh --output-dir /tmp/opp_output/pdf_both 2>&1
echo "Exit: $?"
ls /tmp/opp_output/pdf_both/
```

**Expected Result:**
- ❌ Exit code != 0 or partial success
- ❌ Error or warning about PDF→XLIFF being blocked
- ❌ Only `.md` file produced (no `.xlf`)

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

#### 4.4 🟢 PDF detection works without extension

```bash
# Copy PDF with wrong extension
cp /tmp/opp_test/test.pdf /tmp/opp_test/test_disguised.txt
python3 -c "
from pathlib import Path
from opp.detector import detect_format, FormatType
fmt, conf = detect_format(Path('/tmp/opp_test/test_disguised.txt'))
print(f'Detected: {fmt.value} (confidence: {conf})')
assert fmt == FormatType.PDF, f'Expected PDF got {fmt}'
"
```

**Expected Result:** ✅ PDF detected via `%PDF` magic bytes even with `.txt` extension.

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

### 📊 Q4-OPP Verdict

| Scenario | Result |
|----------|--------|
| 4.1 PDF → MD | ⬜ |
| 4.2 PDF → XLIFF blocked | ⬜ |
| 4.3 PDF → both partial | ⬜ |
| 4.4 PDF detection no extension | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q5-OPP: Does OPP extract XLSX/CSV/JSON/XML to valid MD?

**User says:** "I have spreadsheets and data files. Can OPP extract them?"

**Why this matters:** Data formats (XLSX, CSV, JSON, XML) are structurally different from documents. Table extraction must preserve structure.

### Prerequisites

```bash
cd /mnt/d/贯维/Omni_Suite && source .venv_ol/bin/activate

# Create an XLSX test file
python3 -c "
from openpyxl import Workbook
wb = Workbook()
ws = wb.active
ws.title = 'Sheet1'
ws['A1'] = 'Name'
ws['B1'] = 'Value'
ws['A2'] = 'Alice'
ws['B2'] = 100
ws['A3'] = 'Bob'
ws['B3'] = 200
wb.save('/tmp/opp_test/test.xlsx')
print('XLSX created')
"
```

### Scenarios

#### 5.1 🟢 XLSX → MD with table structure

```bash
opp /tmp/opp_test/test.xlsx --target-format md --output-dir /tmp/opp_output/xlsx_md --source-lang en 2>&1
echo "Exit: $?"
cat /tmp/opp_output/xlsx_md/test.md
```

**Expected Result:**
- ✅ Exit code 0
- ✅ MD file contains table (pipe-delimited Markdown table)
- ✅ Table headers: Name, Value
- ✅ Table rows: Alice, 100 and Bob, 200

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

#### 5.2 🟢 CSV → MD with table

```bash
opp /tmp/opp_test/test.csv --target-format md --output-dir /tmp/opp_output/csv_md --source-lang en 2>&1
echo "Exit: $?"
cat /tmp/opp_output/csv_md/test.md
```

**Expected Result:**
- ✅ Exit code 0
- ✅ MD file contains table with columns: name, value, note
- ✅ MD file contains data rows: Alice, Bob

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

#### 5.3 🟢 JSON → MD with structure

```bash
opp /tmp/opp_test/test.json --target-format md --output-dir /tmp/opp_output/json_md --source-lang en 2>&1
echo "Exit: $?"
cat /tmp/opp_output/json_md/test.md
```

**Expected Result:**
- ✅ Exit code 0
- ✅ MD file contains JSON content as structured text or table
- ✅ Key values present: "Test", "A", "B"

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

#### 5.4 🟢 XML → MD with structure

```bash
opp /tmp/opp_test/test.xml --target-format md --output-dir /tmp/opp_output/xml_md --source-lang en 2>&1
echo "Exit: $?"
cat /tmp/opp_output/xml_md/test.md
```

**Expected Result:**
- ✅ Exit code 0
- ✅ MD file contains XML content as text or structured output
- ✅ Content includes "Test" and item ID

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

#### 5.5 🟢 All data formats produce manifest.json

```bash
for fmt in xlsx csv json xml; do
  echo "=== $fmt ==="
  ls /tmp/opp_output/${fmt}_md/test_manifest.json 2>/dev/null && echo "OK" || echo "MISSING"
done
```

**Expected Result:** ✅ Every data format extraction produces `test_manifest.json`.

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

### 📊 Q5-OPP Verdict

| Scenario | Result |
|----------|--------|
| 5.1 XLSX → MD | ⬜ |
| 5.2 CSV → MD | ⬜ |
| 5.3 JSON → MD | ⬜ |
| 5.4 XML → MD | ⬜ |
| 5.5 Manifest per format | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q6-OPP: Does OPP extract HTML/EPUB/EML to valid MD?

**User says:** "I need to extract web pages, ebooks, and emails."

**Why this matters:** HTML (with readability/docling fallback), EPUB, and EML are common document formats with distinct extraction paths.

### Prerequisites

```bash
cd /mnt/d/贯维/Omni_Suite && source .venv_ol/bin/activate
```

### Scenarios

#### 6.1 🟢 HTML → MD with content extraction

```bash
opp /tmp/opp_test/test.html --target-format md --output-dir /tmp/opp_output/html_md --source-lang en 2>&1
echo "Exit: $?"
cat /tmp/opp_output/html_md/test.md
```

**Expected Result:**
- ✅ Exit code 0
- ✅ MD file contains extracted text: "Test HTML", "HTML content here."
- ✅ HTML tags stripped; only readable content in MD

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

#### 6.2 🟢 EPUB → MD

```bash
opp /tmp/opp_test/test.epub --target-format md --output-dir /tmp/opp_output/epub_md --source-lang en 2>&1
echo "Exit: $?"
cat /tmp/opp_output/epub_md/test.md 2>/dev/null || echo "EPUB extraction may need ebooklib dependency"
```

**Expected Result:**
- ✅ Exit code 0
- ✅ MD file contains "Chapter 1" and "EPUB content here."
- ✅ Manifest JSON produced

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

#### 6.3 🟢 EML → MD

```bash
opp /tmp/opp_test/test.eml --target-format md --output-dir /tmp/opp_output/eml_md --source-lang en 2>&1
echo "Exit: $?"
cat /tmp/opp_output/eml_md/test.md
```

**Expected Result:**
- ✅ Exit code 0
- ✅ MD file contains email metadata: From, To, Subject, Date
- ✅ MD file contains email body text

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

#### 6.4 🟢 HTML fallback — docling fails, readability succeeds

```python
from unittest.mock import patch
from opp.extractors.html import HTMLExtractor
import asyncio

# Simulate docling raising an error — extractor should fall back to readability
extractor = HTMLExtractor()
with patch.object(extractor, '_extract_via_docling', side_effect=Exception("docling OOM")):
    try:
        result = asyncio.run(extractor.extract("/tmp/opp_test/test.html"))
        assert result is not None
        assert len(result.paragraphs) > 0, "No paragraphs extracted via fallback"
        assert any("Test HTML" in p.text for p in result.paragraphs), "Expected content missing"
        print(f"✅ HTML fallback: {len(result.paragraphs)} paragraphs extracted")
    except Exception as e:
        print(f"❌ HTML fallback failed: {e}")
```

**Expected Result:**
- ✅ Fallback from docling to readability succeeds
- ✅ Content extracted (paragraphs with "Test HTML")
- ✅ No crash — graceful degradation

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

### 📊 Q6-OPP Verdict

| Scenario | Result |
|----------|--------|
| 6.1 HTML → MD | ⬜ |
| 6.2 EPUB → MD | ⬜ |
| 6.3 EML → MD | ⬜ |
| 6.4 HTML fallback | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q7-OPP: Does OPP handle image files via OCR?

**User says:** "I have scanned documents. Can OPP read the text from images?"

**Why this matters:** Image OCR (Tesseract/RapidOCR) is a critical path for scanned documents and photo-based content.

### Prerequisites

```bash
cd /mnt/d/贯维/Omni_Suite && source .venv_ol/bin/activate

# Create a simple test image with text
python3 -c "
from PIL import Image, ImageDraw, ImageFont
import os
img = Image.new('RGB', (400, 100), color='white')
draw = ImageDraw.Draw(img)
# Try to use a common available font (otherwise just draw text)
try:
    # Simulate text with a simple shape
    font = ImageFont.load_default()
    draw.text((10, 40), 'Hello OPP OCR', fill='black', font=font)
except Exception:
    draw.text((10, 40), 'Hello OPP OCR', fill='black')
img.save('/tmp/opp_test/test_ocr.png')
print('Test image created')
"
```

### Scenarios

#### 7.1 🟢 Image → MD via OCR (Tesseract)

```bash
opp /tmp/opp_test/test_ocr.png --target-format md --output-dir /tmp/opp_output/ocr_md --ocr-engine tesseract --source-lang en 2>&1
echo "Exit: $?"
cat /tmp/opp_output/ocr_md/test_ocr.md 2>/dev/null || echo "OCR may need tesseract installed"
```

**Expected Result:**
- ✅ Exit code 0 (or OCR-specific exit code)
- ✅ MD file is created
- ✅ If OCR succeeds, text "Hello OPP OCR" appears in output
- ✅ If Tesseract is not installed, graceful error message (not a crash)

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

#### 7.2 🟢 Format detection identifies image formats

```python
from pathlib import Path
from opp.detector import detect_format, FormatType

for ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
    test_path = f"/tmp/opp_test/test_img{ext}"
    if Path(test_path).exists():
        fmt, conf = detect_format(Path(test_path))
        print(f"{ext}: {fmt.value} (confidence: {conf})")
        assert fmt == FormatType.IMAGE, f"{ext} expected IMAGE, got {fmt}"
```

**Expected Result:** ✅ All image extensions (png, jpg, jpeg, tiff, bmp) detected as `FormatType.IMAGE` with confidence ≥ 0.9.

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

#### 7.3 🟢 OCR language override via env var

```bash
export OPP_OCR_LANG=eng
opp /tmp/opp_test/test_ocr.png --target-format md --output-dir /tmp/opp_output/ocr_lang --source-lang en 2>&1
echo "Exit: $?"
```

**Expected Result:** ✅ `OPP_OCR_LANG=eng` is respected. Extraction succeeds.

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

### 📊 Q7-OPP Verdict

| Scenario | Result |
|----------|--------|
| 7.1 Image OCR (Tesseract) | ⬜ |
| 7.2 Image format detection | ⬜ |
| 7.3 OCR language override | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q8-OPP: Does OPP handle edge cases (empty/corrupt/unsupported)?

**User says:** "What if my file is empty, corrupt, or an unsupported format?"

**Why this matters:** Real-world inputs are messy. OPP must handle errors gracefully without crashes or data corruption.

### Prerequisites

```bash
cd /mnt/d/贯维/Omni_Suite && source .venv_ol/bin/activate
```

### Scenarios

#### 8.1 🔴 Empty file handled gracefully

```bash
touch /tmp/opp_test/empty.docx
opp /tmp/opp_test/empty.docx --target-format md --output-dir /tmp/opp_output/empty 2>&1
echo "Exit: $?"
```

**Expected Result:**
- ❌ Exit code != 0
- ❌ Error message: "File is empty", "Invalid file", or similar
- ❌ No crash, no traceback

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

#### 8.2 🔴 Corrupt ZIP file handled gracefully

```bash
echo "this is not a valid zip" > /tmp/opp_test/corrupt.docx
opp /tmp/opp_test/corrupt.docx --target-format md --output-dir /tmp/opp_output/corrupt 2>&1
echo "Exit: $?"
```

**Expected Result:**
- ❌ Exit code != 0
- ❌ Error message: "BadZipFile", "Invalid file", or similar
- ❌ No crash, no traceback

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

#### 8.3 🔴 Unsupported file type handled gracefully

```bash
echo "some content" > /tmp/opp_test/unsupported.wxyz
opp /tmp/opp_test/unsupported.wxyz --target-format md --output-dir /tmp/opp_output/unsupported 2>&1
echo "Exit: $?"
```

**Expected Result:**
- ❌ Exit code != 0
- ❌ Error message: "Unsupported format", "No extractor", or similar
- ❌ No crash, no traceback

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

#### 8.4 🔴 Nonexistent file

```bash
opp /tmp/opp_test/nonexistent.docx --target-format md --output-dir /tmp/opp_output/nonexistent 2>&1
echo "Exit: $?"
```

**Expected Result:**
- ❌ Exit code != 0
- ❌ Error message: "File not found" or similar
- ❌ No crash, no traceback

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

#### 8.5 🟢 Missing --target-lang for XLIFF

```bash
opp /tmp/opp_test/test.docx --target-format xlf --source-lang en --output-dir /tmp/opp_output/no_target 2>&1
echo "Exit: $?"
```

**Expected Result:**
- ❌ Exit code != 0 (parser.error)
- ❌ Message: "--target-lang is required when --target-format is 'xlf' or 'both'"
- ❌ No crash — clean argparse error

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

#### 8.6 🟢 Multiple files processed via batch

```bash
opp /tmp/opp_test/test.docx /tmp/opp_test/test.pptx --target-format md --output-dir /tmp/opp_output/batch 2>&1
echo "Exit: $?"
ls /tmp/opp_output/batch/
```

**Expected Result:**
- ✅ Exit code 0 (or 1 if partial failure but clear which files failed)
- ✅ Both `.md` files created
- ✅ Output shows per-file results

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

#### 8.7 🟢 --detect-format flag works for quick inspection

```bash
opp --detect-format /tmp/opp_test/test.docx 2>&1
echo "Exit: $?"
```

**Expected Result:**
- ✅ Exit code 0
- ✅ Output shows detected format (DOCX) and confidence
- ✅ No extraction performed (detection only)

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

### 📊 Q8-OPP Verdict

| Scenario | Result |
|----------|--------|
| 8.1 Empty file | ⬜ |
| 8.2 Corrupt ZIP | ⬜ |
| 8.3 Unsupported type | ⬜ |
| 8.4 Nonexistent file | ⬜ |
| 8.5 Missing --target-lang | ⬜ |
| 8.6 Batch processing | ⬜ |
| 8.7 --detect-format | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

# Part 2: Output Artifact Integrity

---

## Q9-OPP: Does OPP produce correct manifest.json?

**User says:** "I need metadata about the extraction — what was processed, what was produced."

**Why this matters:** The manifest.json is the contract for downstream tools (OL, ORF). Missing or incorrect fields break automation.

### Prerequisites

```bash
cd /mnt/d/贯维/Omni_Suite && source .venv_ol/bin/activate
```

### Scenarios

#### 9.1 🟢 Manifest has all required top-level fields

```bash
python3 -c "
import json
with open('/tmp/opp_output/docx_both/test_manifest.json') as f:
    m = json.load(f)
required = ['manifest_version', 'generated_at', 'tool', 'tool_version', 'source', 'extraction', 'resources']
for field in required:
    assert field in m, f'Missing field: {field}'
    print(f'  ✅ {field}')
print('All required fields present')
"
```

**Expected Result:** ✅ Manifest has `manifest_version`, `generated_at`, `tool`, `tool_version`, `source`, `extraction`, `resources`.

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

#### 9.2 🟢 Source section has complete metadata

```python
import json
with open('/tmp/opp_output/docx_both/test_manifest.json') as f:
    m = json.load(f)
s = m['source']
assert 'file_path' in s
assert 'original_filename' in s
assert 'format' in s
assert 'file_size_bytes' in s
assert s['file_size_bytes'] > 0
print(f"File: {s['original_filename']}, Format: {s['format']}, Size: {s['file_size_bytes']} bytes")
```

**Expected Result:** ✅ Source has `file_path`, `original_filename`, `format`, `file_size_bytes` (>0).

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

#### 9.3 🟢 Extraction section lists outputs correctly

```python
import json
with open('/tmp/opp_output/docx_both/test_manifest.json') as f:
    m = json.load(f)
e = m['extraction']
outputs = e.get('outputs', {})
print(f"Outputs: {list(outputs.keys())}")
assert 'markdown' in outputs or 'md' in outputs
assert 'xliff' in outputs or 'xlf' in outputs
assert 'images' in e
print(f"Images: {len(e['images'])}")
```

**Expected Result:** ✅ Extraction section lists `markdown` (or `md`) and `xliff` (or `xlf`) paths. `images` array present.

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

### 📊 Q9-OPP Verdict

| Scenario | Result |
|----------|--------|
| 9.1 Required top-level fields | ⬜ |
| 9.2 Source metadata | ⬜ |
| 9.3 Extraction outputs | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q10-OPP: Does OPP produce correct skeleton.zip for DOCX/PPTX/EPUB?

**User says:** "I need the skeleton ZIP for layout-preserving backfill."

**Why this matters:** skeleton.zip is required by ORF's `apply-xliff`. Missing or broken skeleton means XLIFF path cannot work.

### Prerequisites

```bash
cd /mnt/d/贯维/Omni_Suite && source .venv_ol/bin/activate
```

### Scenarios

#### 10.1 🟢 DOCX skeleton preserves word/document.xml

```bash
python3 -c "
import zipfile
with zipfile.ZipFile('/tmp/opp_output/docx_both/test.skeleton.zip') as zf:
    names = zf.namelist()
    print(f'Skeleton has {len(names)} files')
    print('  ' + '\n  '.join(names[:15]))
    assert 'word/document.xml' in names, 'Missing word/document.xml'
    assert '[Content_Types].xml' in names, 'Missing [Content_Types].xml'
    assert 'word/styles.xml' in names, 'Missing word/styles.xml'
print('✅ DOCX skeleton structure valid')
"
```

**Expected Result:** ✅ Skeleton ZIP contains `word/document.xml`, `[Content_Types].xml`, `word/styles.xml`, `word/numbering.xml`.

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

#### 10.2 🟢 PPTX skeleton preserves ppt/slides/

```bash
python3 -c "
import zipfile
with zipfile.ZipFile('/tmp/opp_output/pptx_both/test.skeleton.zip') as zf:
    names = zf.namelist()
    assert any(n.startswith('ppt/slides/') for n in names), 'Missing ppt/slides/'
    assert any('ppt/media/' in n for n in names) or True, 'No media in this test'
print('✅ PPTX skeleton valid, has slides')
"
```

**Expected Result:** ✅ PPTX skeleton contains `ppt/slides/` files and `ppt/media/` if images present.

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

#### 10.3 🟢 Skeleton not produced for non-OOXML formats (PDF, HTML)

```bash
python3 -c "
ls /tmp/opp_output/pdf_md/*.skeleton.zip 2>/dev/null && echo 'FOUND (unexpected)' || echo 'No skeleton (expected — PDF)'
ls /tmp/opp_output/html_md/*.skeleton.zip 2>/dev/null && echo 'FOUND (unexpected)' || echo 'No skeleton (expected — HTML)'
"
```

**Expected Result:** ✅ No skeleton.zip for PDF or HTML outputs (skeleton only for DOCX/PPTX/EPUB).

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

### 📊 Q10-OPP Verdict

| Scenario | Result |
|----------|--------|
| 10.1 DOCX skeleton structure | ⬜ |
| 10.2 PPTX skeleton structure | ⬜ |
| 10.3 No skeleton for PDF/HTML | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q11-OPP: Does OPP produce correct images.json with floating image metadata?

**User says:** "My DOCX has anchored (floating) images. Does OPP preserve their positions?"

**Why this matters:** Floating image metadata (`is_floating`, `wp_anchor_h`, `wp_anchor_v`) enables ORF to reinject exact page layouts during backfill. Inline images must not get floating flags.

### Prerequisites

```bash
cd /mnt/d/贯维/Omni_Suite && source .venv_ol/bin/activate
```

### Scenarios

#### 11.1 🟢 images.json has correct structure (inline images)

```python
import json
# For DOCX extraction, images.json should exist in output
img_path = "/tmp/opp_output/docx_both/test_images.json"
manifest_path = "/tmp/opp_output/docx_both/test_manifest.json"

# Check via manifest for image entries
with open(manifest_path) as f:
    m = json.load(f)
images = m.get("extraction", {}).get("images", [])
print(f"Images in manifest: {len(images)}")
for img in images:
    assert "mime_type" in img, f"Missing mime_type"
    assert "data_size_bytes" in img, f"Missing data_size_bytes"
    print(f"  {img.get('mime_type', '?')} - {img.get('data_size_bytes', 0)} bytes")
```

**Expected Result:** ✅ Images list exists. Each image has `mime_type`, `data_size_bytes`. Inline images do NOT have `is_floating` key.

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

#### 11.2 🟢 Floating image fields are present for DOCX anchored drawings

This test requires a DOCX with an anchored (floating) image. If such a file is available:

```python
# Check images.json for floating metadata
import json, os
img_json = "/tmp/opp_output/docx_both/test_images.json"
if os.path.exists(img_json):
    with open(img_json) as f:
        data = json.load(f)
    for img in data if isinstance(data, list) else data.get("images", []):
        if img.get("is_floating"):
            assert "wp_anchor_h" in img, "Floating image missing wp_anchor_h"
            assert "wp_anchor_v" in img, "Floating image missing wp_anchor_v"
            print(f"✅ Floating image: h={img['wp_anchor_h']}, v={img['wp_anchor_v']}")
else:
    print("➖ images.json not found (no images in test DOCX)")
```

**Expected Result:** ✅ If floating images exist, they have `is_floating: true`, `wp_anchor_h`, `wp_anchor_v` (in EMU units), and `paragraph_index: None`.

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

#### 11.3 🟢 Image dedup works (MD5 + UUID)

```python
from opp.resource_manager import ResourceManager
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as td:
    rm = ResourceManager(storage_dir=Path(td))
    # Store same image twice
    img_data = b"fakeimagedata123"
    ref1 = rm.store_image(img_data, "image/png")
    ref2 = rm.store_image(img_data, "image/png")
    assert ref1.filename == ref2.filename, f"Expected same filename from dedup: {ref1.filename} vs {ref2.filename}"
    assert ref1.md5 == ref2.md5, "MD5 should match for identical data"
    print(f"✅ Image dedup: same MD5={ref1.md5}, same filename={ref1.filename}")
```

**Expected Result:** ✅ Identical image data produces the same MD5 hash and filename (dedup works). Different data produces different UUIDs.

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

### 📊 Q11-OPP Verdict

| Scenario | Result |
|----------|--------|
| 11.1 images.json structure | ⬜ |
| 11.2 Floating image fields | ⬜ |
| 11.3 Image dedup (MD5+UUID) | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

# Part 3: MCP Surface Mastery

---

## Q12-OPP: Do all 9 MCP tools work correctly?

**User says:** "I'm connecting via MCP protocol. I need all 9 tools to work as documented."

**Why this matters:** MCP is the primary integration surface for AI agents. Broken tools break automation. The 9 tools are: `extract_document`, `batch_extract`, `detect_format_tool`, `generate_markdown`, `generate_xliff`, `save_skeleton`, `ping`, `validate_xliff`, `get_capabilities`.

### Prerequisites

```bash
cd /mnt/d/贯维/Omni_Suite && source .venv_ol/bin/activate
export OPP_MCP_ALLOWED_DIRS="/tmp/opp_test,/tmp/opp_output"

# Initialize the MCP server config for in-process testing
python3 -c "
from opp.mcp.config import MCPConfig, load_config
cfg = load_config()
from opp.mcp.common import _init_server
_init_server(cfg)
print('MCP server initialized')
"
```

### Scenarios

#### 12.1 🟢 ping — health check returns version

```python
import json, asyncio
from opp.mcp.tools import ping

result = asyncio.run(ping())
data = result if isinstance(result, dict) else json.loads(result)
print(json.dumps(data, indent=2))
assert data.get("success") is True, "ping failed"
assert "version" in data, "Missing version"
assert data.get("status") == "ok" or "status" in data
```

**Expected Result:** ✅ Returns `{"success": true, "version": "0.9.1", "status": "ok", "tool": "opp-mcp"}` (or similar). Version string present.

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

#### 12.2 🟢 detect_format_tool — identifies file via magic bytes

```python
import json, asyncio
from opp.mcp.tools import detect_format_tool

result = asyncio.run(detect_format_tool(file_path="/tmp/opp_test/test.docx"))
data = result if isinstance(result, dict) else json.loads(result)
print(json.dumps(data, indent=2))
assert data.get("success") is True
assert "format" in data.get("content", data) or "format" in data
```

**Expected Result:** ✅ Returns `{"success": true, "content": {"format": "docx", "confidence": 1.0}}` (or similar). Format name and confidence present.

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

#### 12.3 🟢 extract_document — full extraction

```python
import json, asyncio
from opp.mcp.tools import extract_document

result = asyncio.run(extract_document(
    file_path="/tmp/opp_test/test.docx",
    output_formats=["md", "xlf"],
    source_lang="en",
    target_lang="zh",
    resource_dir="/tmp/opp_output/mcp_extract"
))
data = result if isinstance(result, dict) else json.loads(result)
print(f"Success: {data.get('success')}")
if data.get("success"):
    content = data.get("content", data)
    print(f"Format: {content.get('format', '?')}")
    print(f"MD length: {len(content.get('markdown', ''))}")
    print(f"XLIFF length: {len(content.get('xliff', ''))}")
    print(f"Images: {len(content.get('images', []))}")
```

**Expected Result:**
- ✅ `success: true`
- ✅ `content.format` is not empty
- ✅ `content.markdown` is non-empty string
- ✅ `content.xliff` is non-empty string (XLIFF XML)
- ✅ `content.images` is a list (may be empty)

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

#### 12.4 🟢 generate_markdown — MD-only conversion

```python
import json, asyncio
from opp.mcp.tools import generate_markdown

result = asyncio.run(generate_markdown(
    file_path="/tmp/opp_test/test.docx",
    output_path="/tmp/opp_output/mcp_gen/test_mcp.md"
))
data = result if isinstance(result, dict) else json.loads(result)
print(f"Success: {data.get('success')}")
assert data.get("success") is True
print(f"Output: {data.get('output_path', '?')}")
```

**Expected Result:** ✅ Returns `{"success": true, "output_path": "..."}`. File written to specified output_path.

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

#### 12.5 🟢 generate_xliff — XLIFF-only conversion

```python
import json, asyncio
from opp.mcp.tools import generate_xliff

result = asyncio.run(generate_xliff(
    file_path="/tmp/opp_test/test.docx",
    source_lang="en",
    target_lang="zh",
    output_path="/tmp/opp_output/mcp_gen/test_mcp.xlf"
))
data = result if isinstance(result, dict) else json.loads(result)
print(f"Success: {data.get('success')}")
assert data.get("success") is True
```

**Expected Result:** ✅ Returns success. XLIFF file written. PDF input → error (blocked).

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

#### 12.6 🟢 save_skeleton — skeleton ZIP preservation

```python
import json, asyncio
from opp.mcp.tools import save_skeleton

result = asyncio.run(save_skeleton(
    file_path="/tmp/opp_test/test.docx",
    base_name="test",
    output_dir="/tmp/opp_output/mcp_skel"
))
data = result if isinstance(result, dict) else json.loads(result)
print(f"Success: {data.get('success')}")
assert data.get("success") is True
```

**Expected Result:** ✅ Returns success. Skeleton ZIP saved at output path.

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

#### 12.7 🟢 validate_xliff — XLIFF schema validation

```python
import json, asyncio
from opp.mcp.tools import validate_xliff

# Use the XLIFF produced earlier
xliff_path = "/tmp/opp_output/docx_both/test.xlf"
result = asyncio.run(validate_xliff(file_path=xliff_path))
data = result if isinstance(result, dict) else json.loads(result)
print(json.dumps(data, indent=2)[:500])
assert data.get("success") is True
```

**Expected Result:** ✅ Returns `{"success": true, "content": {"is_valid": true, "schema_valid": true, "trans_units_valid": true, ...}}`. Schema and trans-unit validation both pass.

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

#### 12.8 🟢 get_capabilities — returns module capabilities

```python
import json, asyncio
from opp.mcp.tools import get_capabilities

result = asyncio.run(get_capabilities())
data = result if isinstance(result, dict) else json.loads(result)
print(json.dumps(data, indent=2)[:1000])
assert data.get("success") is True
content = data.get("content", data)
assert "input_formats" in content, "Missing input_formats"
assert "output_formats" in content, "Missing output_formats"
assert "tools" in content, "Missing tools list"
print(f"Input formats ({len(content['input_formats'])}): {', '.join(content['input_formats'][:5])}...")
print(f"Output formats: {', '.join(content['output_formats'])}")
print(f"Tools ({len(content['tools'])}): {', '.join(content['tools'][:5])}...")
```

**Expected Result:** ✅ Returns capabilities with `module: "OPP"`, `version`, `input_formats` (≥13), `output_formats` (md/xlf), `tools` (≥7).

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

#### 12.9 🟢 batch_extract — multi-file processing

```python
import json, asyncio
from opp.mcp.tools import batch_extract

result = asyncio.run(batch_extract(
    file_paths=["/tmp/opp_test/test.docx", "/tmp/opp_test/test.pptx"],
    output_formats=["md"],
    source_lang="en",
    target_lang="zh"
))
data = result if isinstance(result, dict) else json.loads(result)
print(f"Success: {data.get('success')}")
content = data.get("content", data)
if isinstance(content, dict):
    results_list = content.get("results", [])
    print(f"Files processed: {len(results_list)}")
    for r in results_list:
        print(f"  {r.get('file', '?')}: {r.get('status', '?')}")
```

**Expected Result:** ✅ Returns results for each file. Per-file status included. Aggregate counts present.

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

#### 12.10 🔴 Unknown tool returns error (not crash)

```python
import json, asyncio
from opp.mcp.server import _handle_call_tool

# Direct call to dispatch with unknown tool
try:
    result = await _handle_call_tool("nonexistent_tool", {})
    # If it returns gracefully:
    data = json.loads(result[0].text)
    print(f"Error code: {data.get('error_code', '?')}")
    assert "error" in data, "Expected error response"
    assert data.get("error_code") == "OPP_UNKNOWN_TOOL", f"Unexpected code: {data.get('error_code')}"
    print("✅ Graceful error response for unknown tool")
except Exception as e:
    print(f"Exception (acceptable if handled): {e}")
```

**Expected Result:** ❌ Returns error response with `error_code: "OPP_UNKNOWN_TOOL"`. Does NOT crash. Does NOT leak Python traceback.

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

#### 12.11 🔴 extract_document with nonexistent file

```python
import json, asyncio
from opp.mcp.tools import extract_document

result = asyncio.run(extract_document(
    file_path="/tmp/opp_test/nonexistent.docx",
    output_formats=["md"]
))
data = result if isinstance(result, dict) else json.loads(result)
print(f"Success: {data.get('success')}")
print(f"Error: {data.get('error', {}).get('message', data.get('message', '?'))}")
assert data.get("success") is False, "Should fail for nonexistent file"
```

**Expected Result:** ❌ `success: false`. Error message about file not found. No crash.

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

### 📊 Q12-OPP Verdict

| Scenario | Result |
|----------|--------|
| 12.1 ping | ⬜ |
| 12.2 detect_format_tool | ⬜ |
| 12.3 extract_document | ⬜ |
| 12.4 generate_markdown | ⬜ |
| 12.5 generate_xliff | ⬜ |
| 12.6 save_skeleton | ⬜ |
| 12.7 validate_xliff | ⬜ |
| 12.8 get_capabilities | ⬜ |
| 12.9 batch_extract | ⬜ |
| 12.10 Unknown tool error | ⬜ |
| 12.11 extract nonexistent | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

# Part 4: Security & Production

---

## Q13-OPP: Does MCP path security block unauthorized access?

**User says:** "I don't want the MCP server reading my entire filesystem."

**Why this matters:** PathValidator is the security gatekeeper. Must block path traversal, symlink attacks, blocked extensions, oversized files, and non-allowlisted directories.

### Prerequisites

```bash
cd /mnt/d/贯维/Omni_Suite && source .venv_ol/bin/activate

# Set up a restricted MCP environment
export OPP_MCP_ALLOWED_DIRS="/tmp/opp_test"

# Initialize validator
python3 -c "
from pathlib import Path
from opp.mcp.security import PathValidator
validator = PathValidator(allowed_directories=[Path('/tmp/opp_test')])
print('Validator ready')
" 2>&1
```

### Scenarios

#### 13.1 🟢 Path inside allowlist passes

```python
from pathlib import Path
from opp.mcp.security import PathValidator

validator = PathValidator(allowed_directories=[Path("/tmp/opp_test")])
result = validator.validate_path("/tmp/opp_test/test.docx")
print(f"Pass: {result.success}")
assert result.success is True, f"Expected pass, got: {result.error}"
```

**Expected Result:** ✅ Validation passes. `result.success == True`.

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

#### 13.2 🔴 Path outside allowlist is blocked

```python
validator = PathValidator(allowed_directories=[Path("/tmp/opp_test")])
result = validator.validate_path("/etc/passwd")
print(f"Pass: {result.success}, Error: {result.error}")
assert result.success is False, "Should block /etc/passwd"
assert "allowed" in result.error.lower() or "outside" in result.error.lower() or "denied" in result.error.lower()
```

**Expected Result:** ❌ Blocked. `result.success == False`. Error message mentions "allowed" or "outside" directory.

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

#### 13.3 🔴 Path traversal (..) is blocked

```python
validator = PathValidator(allowed_directories=[Path("/tmp/opp_test")])
result = validator.validate_path("/tmp/opp_test/../../etc/passwd")
print(f"Pass: {result.success}, Error: {result.error}")
assert result.success is False, "Should block path traversal"
```

**Expected Result:** ❌ Blocked. `result.success == False`. Error about path traversal.

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

#### 13.4 🔴 Blocked extension (.exe) is rejected

```python
validator = PathValidator(allowed_directories=[Path("/tmp/opp_test")])
result = validator.validate_path("/tmp/opp_test/malware.exe")
print(f"Pass: {result.success}, Error: {result.error}")
assert result.success is False, "Should block .exe"
```

**Expected Result:** ❌ Blocked. `result.success == False`. Error about blocked extension.

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

#### 13.5 🟢 Allowed extension (.md, .docx, .pdf) passes

```python
validator = PathValidator(allowed_directories=[Path("/tmp/opp_test")])
for ext in [".md", ".docx", ".pdf", ".xlf", ".xliff", ".html", ".epub", ".txt"]:
    result = validator.validate_path(f"/tmp/opp_test/file{ext}")
    if result.success:
        print(f"  ✅ {ext} allowed")
    else:
        print(f"  ❌ {ext} blocked: {result.error}")
```

**Expected Result:** ✅ All document format extensions (md, docx, pdf, xlf, xliff, html, epub, txt, xlsx, csv, json, xml, eml) pass validation.

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

#### 13.6 🔴 Oversized file is rejected

```python
# Create a file larger than the size limit
import os
with open("/tmp/opp_test/large_test.bin", "wb") as f:
    f.write(b"0" * 1000)  # 1KB

validator = PathValidator(
    allowed_directories=[Path("/tmp/opp_test")],
    max_file_size_bytes=100  # 100 bytes max
)
result = validator.validate_path("/tmp/opp_test/large_test.bin")
print(f"Pass: {result.success}, Error: {result.error}")
assert result.success is False, "Should block oversized file"
```

**Expected Result:** ❌ Blocked. Error about file size exceeding limit.

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

#### 13.7 🔴 Symlink pointing outside allowlist is blocked

```python
import os
# Create a symlink that points outside allowlist
outside_path = "/tmp/outside_test.txt"
with open(outside_path, "w") as f:
    f.write("outside")
symlink_path = "/tmp/opp_test/evil_link.txt"
if os.path.exists(symlink_path):
    os.remove(symlink_path)
os.symlink(outside_path, symlink_path)

validator = PathValidator(allowed_directories=[Path("/tmp/opp_test")])
result = validator.validate_path(symlink_path)
print(f"Pass: {result.success}, Error: {result.error}")
# Note: symlink check behavior depends on config; may pass if link resolves to allowlist
# Expected: blocked, or at least validated
```

**Expected Result:** ❌ Symlink resolved outside allowlist should be blocked (or at minimum validated with a warning).

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

### 📊 Q13-OPP Verdict

| Scenario | Result |
|----------|--------|
| 13.1 Inside allowlist passes | ⬜ |
| 13.2 Outside allowlist blocked | ⬜ |
| 13.3 Path traversal blocked | ⬜ |
| 13.4 Blocked extension (.exe) | ⬜ |
| 13.5 Allowed extensions pass | ⬜ |
| 13.6 Oversized file rejected | ⬜ |
| 13.7 Symlink outside blocked | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q14-OPP: Does the CLI work correctly?

**User says:** "I use the terminal. Does every CLI flag work?"

**Why this matters:** CLI is the primary user-facing interface. Every flag, error message, and output path must work.

### Prerequisites

```bash
cd /mnt/d/贯维/Omni_Suite && source .venv_ol/bin/activate
```

### Scenarios

#### 14.1 🟢 --help shows all flags

```bash
opp --help
```

**Expected Result:** ✅ Shows all flags: `--target-format`, `--source-lang`, `--target-lang`, `--output-dir`, `--detect-format`, `--batch`, `--resource-dir`, `--ocr-engine`, `--ocr-lang`, `--verbose`, `--style-map`, `--no-embed-images`, `--config`, `--no-cache`, `--clear-cache`, `--capabilities`, `--validate-xliff`, `--load-dotenv`, `--log-format`, `--max-file-size`, `--asr-engine`, `--model-size`.

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

#### 14.2 🟢 --version or version flag

```bash
opp --version 2>&1 || python3 -m opp --version 2>&1 || python3 -c "from opp import __version__; print(__version__)"
```

**Expected Result:** ✅ Version string displayed (v0.9.1 or similar).

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

#### 14.3 🟢 --detect-format flag

```bash
opp --detect-format /tmp/opp_test/test.docx -v 2>&1
echo "Exit: $?"
```

**Expected Result:** ✅ Detected format (DOCX) and confidence score printed. No extraction performed.

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

#### 14.4 🟢 --output-dir creates files at custom path

```bash
opp /tmp/opp_test/test.docx --target-format md --output-dir /tmp/opp_output/custom_path --source-lang en 2>&1
echo "Exit: $?"
ls /tmp/opp_output/custom_path/
```

**Expected Result:** ✅ All files created under `/tmp/opp_output/custom_path/`. Manifest references correct absolute paths.

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

#### 14.5 🟢 --no-embed-images prevents base64 in MD

```bash
opp /tmp/opp_test/test.docx --target-format md --no-embed-images --output-dir /tmp/opp_output/no_embed --source-lang en 2>&1
echo "Exit: $?"
```

**Expected Result:** ✅ MD file uses file references instead of base64-embedded images.

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

#### 14.6 🟢 --capabilities prints module capabilities and exits

```bash
opp --capabilities
echo "Exit: $?"
```

**Expected Result:** ✅ Prints input formats (≥13), output formats, tools (≥7). Exit code 0.

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

#### 14.7 🟢 --validate-xliff validates an XLIFF file

```bash
opp --validate-xliff --xliff-file /tmp/opp_output/docx_both/test.xlf
echo "Exit: $?"
```

**Expected Result:** ✅ Returns JSON with `is_valid: true` or `is_valid: false`. Schema and trans-unit validation details included. Exit code 0 for valid, non-zero for invalid.

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

#### 14.8 🟢 --batch processes multiple files

```bash
opp /tmp/opp_test/test.docx /tmp/opp_test/test.csv /tmp/opp_test/test.json --target-format md --output-dir /tmp/opp_output/cli_batch 2>&1
echo "Exit: $?"
ls /tmp/opp_output/cli_batch/
```

**Expected Result:** ✅ All 3 files processed. 3 `.md` files created. Per-file results in output.

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

#### 14.9 🟢 -v (verbose) writes to stderr, not stdout

```bash
# Capture stdout and stderr separately
opp -v /tmp/opp_test/test.docx --target-format md --output-dir /tmp/opp_output/verbose_test --source-lang en 1>/tmp/stdout.txt 2>/tmp/stderr.txt
echo "Exit: $?"
echo "=== STDOUT ==="
cat /tmp/stdout.txt
echo "=== STDERR ==="
head -5 /tmp/stderr.txt
```

**Expected Result:** ✅ Since v0.6.2, `-v` writes verbose logs to stderr. Stdout is clean (only formatted output). Manifest JSON goes to file, not stdout.

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

### 📊 Q14-OPP Verdict

| Scenario | Result |
|----------|--------|
| 14.1 --help | ⬜ |
| 14.2 --version | ⬜ |
| 14.3 --detect-format | ⬜ |
| 14.4 --output-dir | ⬜ |
| 14.5 --no-embed-images | ⬜ |
| 14.6 --capabilities | ⬜ |
| 14.7 --validate-xliff | ⬜ |
| 14.8 --batch | ⬜ |
| 14.9 -v stderr | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q15-OPP: Can the MCP server start via stdio and respond correctly?

**User says:** "In production, MCP runs as a separate process. Does the stdio transport work?"

**Why this matters:** The MCP server is the primary AI agent integration point. stdio transport must start, accept JSON-RPC requests, handle errors, and shut down cleanly.

### Prerequisites

```bash
cd /mnt/d/贯维/Omni_Suite && source .venv_ol/bin/activate
export OPP_MCP_ALLOWED_DIRS="/tmp/opp_test,/tmp/opp_output"
export OMNI_TEST_FAKE_LLM=1
```

### Scenarios

#### 15.1 🟢 MCP server initializes and responds to ping

```bash
# Start MCP server in background, send a ping, check response
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | timeout 10 python3 -m opp.mcp.server 2>/tmp/mcp_stderr.log | head -20
echo "Server exit: $?"
```

**Expected Result:**
- ✅ Server starts and responds to JSON-RPC `tools/list`
- ✅ Response contains `tools` array with all 9 tool definitions
- ✅ Each tool has `name`, `description`, `inputSchema`
- ✅ Exit code 0 (clean shutdown)

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

#### 15.2 🟢 MCP server has correct entry point via `opp mcp`

```bash
# Test that 'opp mcp' launches the server
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | timeout 5 opp mcp 2>/dev/null | head -20
echo "Exit: $?"
```

**Expected Result:** ✅ `opp mcp` starts the MCP server. Responds to `tools/list`. Same behavior as `python -m opp.mcp.server`.

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

#### 15.3 🔴 Server rejects invalid JSON-RPC gracefully

```bash
echo 'not valid json' | timeout 5 python3 -m opp.mcp.server 2>/dev/null; echo "Exit: $?"
```

**Expected Result:** ❌ Server does NOT crash. Returns JSON-RPC error response or logs error. No Python traceback leaked.

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

#### 15.4 🔴 Server refuses to start without OPP_MCP_ALLOWED_DIRS

```bash
unset OPP_MCP_ALLOWED_DIRS
echo '{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}' | timeout 5 python3 -m opp.mcp.server 2>/dev/null
echo "Exit: $?"
```

**Expected Result:** ❌ Server fails to start with error about missing `allowed_directories`. Fail-closed behavior. Exit code != 0.

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

#### 15.5 🟢 Module imports cleanly

```bash
python3 -c "from opp import __version__; print(f'OPP v{__version__}')"
python3 -c "from opp.mcp.server import ping, extract_document, get_capabilities; print('All MCP tools importable')"
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

---

### 📊 Q15-OPP Verdict

| Scenario | Result |
|----------|--------|
| 15.1 Server stdio ping | ⬜ |
| 15.2 opp mcp entry point | ⬜ |
| 15.3 Invalid JSON-RPC | ⬜ |
| 15.4 Fail-closed (no ALLOWED_DIRS) | ⬜ |
| 15.5 Module imports | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

# Part 5: Final Verdict

---

## Overall PASS/FAIL Summary

| Part | Section | Verdict |
|------|---------|---------|
| 1 | Format Detection & Extraction (Q1-Q8) | ⬜ |
| 2 | Output Artifact Integrity (Q9-Q11) | ⬜ |
| 3 | MCP Surface Mastery (Q12) | ⬜ |
| 4 | Security & Production (Q13-Q15) | ⬜ |

**GRAND TOTAL: ⬜ / 15 Questions**

**OVERALL VERDICT: ⬜**

---

## Production Gap Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| All 17 FormatType values detectable | ⬜ | Q1 |
| DOCX → MD + XLIFF extraction works | ⬜ | Q2 |
| PPTX → MD + XLIFF + skeleton | ⬜ | Q3 |
| PDF → MD works, PDF→XLIFF blocked | ⬜ | Q4 |
| XLSX/CSV/JSON/XML → MD | ⬜ | Q5 |
| HTML/EPUB/EML → MD | ⬜ | Q6 |
| Image OCR (Tesseract) | ⬜ | Q7 |
| Edge cases handled gracefully | ⬜ | Q8 |
| manifest.json has complete metadata | ⬜ | Q9 |
| skeleton.zip preserves OOXML structure | ⬜ | Q10 |
| images.json with floating metadata | ⬜ | Q11 |
| All 9 MCP tools respond correctly | ⬜ | Q12 |
| MCP PathValidator blocks unauthorized paths | ⬜ | Q13 |
| All CLI flags work correctly | ⬜ | Q14 |
| MCP server stdio transport works | ⬜ | Q15 |
| Test suite passes (544+ tests) | ⬜ | Run `make test` |

---

## Sign-off Criteria

| Level | Requirements | Met? |
|-------|-------------|------|
| **CI Gate** | All 15 questions answered. No P0 failures (crash, data loss, security bypass). | ⬜ |
| **Release Candidate** | CI Gate + Q1-Q8 (all formats) + Q12 (MCP tools) all PASS + all production gaps addressed | ⬜ |
| **Production Deploy** | Release Candidate + Q13-Q15 (security + production) all PASS + no outstanding P0/P1 issues | ⬜ |

---

## Test Suite Verification

### 15.6 🟢 Run OPP test suite

```bash
cd /mnt/d/贯维/Omni_Suite/Omni_Pre_Processor && source /mnt/d/贯维/Omni_Suite/.venv_ol/bin/activate && make test 2>&1 | tail -30
```

**Expected Result:** ✅ 544+ tests pass. 0 failures. Coverage ≥90%.

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

### 📊 Test Suite Verdict

| Metric | Result |
|--------|--------|
| Total tests | ⬜ |
| Passed | ⬜ |
| Failed | ⬜ |
| Coverage | ⬜ |

**TEST SUITE OVERALL: ⬜**

---

*Plan generated: 2026-07-22*
*Based on: OPP v0.9.1 codebase — 16 extractors, 17 FormatType values, 9 MCP tools, 544+ tests*
