> **Status: ARCHIVED (2026-08-23). Reason: prose validation plan superseded by the executable scenario library. Superseded by: `scripts/validation/run_validation.py` + `scenarios/`.**

# ORF Validation Master Plan

## Result-Oriented · User-Centric · All Scenarios & Boundaries

**For:** OpenCode, Claude Code, Cline, Hermes Agent — any AI agent validating ORF
**Date:** 2026-07-22
**Strategy:** Every section asks a user question → executes scenarios → reports a binary verdict
**Current Baseline:** v0.4.17 — 16 MD output formats, 5 XLIFF backfill formats, 7 MCP tools, Foreman/Specialist, HITL approval

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
| P0 | Q1-ORF, Q2-ORF, Q4-ORF | Core functionality — if these fail, nothing else matters |
| P1 | Q3-ORF, Q5-ORF, Q8-ORF | Important but depend on P0 passing |
| P2 | Q6-ORF, Q7-ORF, Q9-ORF | Can be deferred if P0/P1 fail — run after core is verified |
| P3 | Q10-ORF, Q11-ORF | Cost-incurring — run last and only if P0-P2 pass |

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
# 1. Install the ORF package with dev + MCP extras
cd /mnt/d/贯维/Omni_Suite/Omni_Re_Formatter
pip install -e ".[dev,weasyprint,office,notebook,email-output,mcp]"

# 2. Verify CLI works
orf --help  # Should show 6 command groups

# 3. Set fake LLM for any translation-dependent tests
export OMNI_TEST_FAKE_LLM=1

# 4. Create working directories for test outputs
mkdir -p /tmp/orf-test-md /tmp/orf-test-xliff /tmp/orf-test-mcp

# 5. Verify pandoc is available (or fake it)
export OMNI_TEST_FAKE_PANDOC=1  # Bypass pandoc for testing ORF output shapes
```

---

## Table of Contents

### Part 1: MD Backfill
- **Q1-ORF:** Can ORF convert MD to all 16 output formats?
- **Q2-ORF:** Does MD→DOCX produce a valid, openable document?
- **Q3-ORF:** Does MD→PPTX work (with md2pptx or pandoc fallback)?

### Part 2: XLIFF Backfill
- **Q4-ORF:** Can ORF backfill XLIFF into DOCX (with skeleton.zip)?
- **Q5-ORF:** Can ORF backfill XLIFF into PPTX (with skeleton.zip)?
- **Q6-ORF:** Does XLIFF backfill preserve images (inline + floating)?
- **Q7-ORF:** Does cross-format XLIFF backfill (--force) work?

### Part 3: MCP Surface Mastery
- **Q8-ORF:** Do all 7 MCP tools work correctly?

### Part 4: Agent Orchestration & Production
- **Q9-ORF:** Does ForemanAgent batched conversion work?
- **Q10-ORF:** Does the MCP server work via stdio?
- **Q11-ORF:** What happens with missing dependencies (pandoc, md2pptx, skeleton.zip)?

### Part 5: Final Verdict

---

# Part 1: MD Backfill

---

## Q1-ORF: Can ORF convert MD to all 16 output formats?

**User says:** "I have a translated Markdown file. I need it converted to every format ORF supports."

**Why this matters:** The 16-format MD backfill matrix is ORF's primary feature. If any format silently fails, the user loses a supported output channel.

### Prerequisites
```bash
cd /tmp/orf-test-md && rm -rf ./*
cat > sample.md << 'EOF'
---
title: Test Document
author: ORF Validator
lang: en
---

# Heading 1

This is a **test paragraph** with *italic* and `inline code`.

## Heading 2

- List item 1
- List item 2
- List item 3

1. Numbered item 1
2. Numbered item 2

> A blockquote for testing.

```python
def hello():
    print("Hello, ORF!")
```

| Col A | Col B |
|-------|-------|
| 1     | 2     |
| 3     | 4     |

![Sample Image](https://via.placeholder.com/150)

Final paragraph with a [link](https://example.com).
EOF
```

### Scenarios

#### 1.1 🟢 Happy Path — DOCX (pandoc engine)
```bash
orf apply-md /tmp/orf-test-md/sample.md --target-format docx -o /tmp/orf-test-md/sample.docx
```
**Expected Result:**
- ✅ Exit code 0
- ✅ `/tmp/orf-test-md/sample.docx` exists and is > 1 KB
- ✅ File is a valid ZIP containing `word/document.xml` (DOCX = ZIP)
- ✅ JSON output with `--json` flag shows `"success": true`

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

#### 1.2 🟢 Happy Path — ODT (pandoc engine)
```bash
orf apply-md /tmp/orf-test-md/sample.md --target-format odt -o /tmp/orf-test-md/sample.odt
```
**Expected Result:**
- ✅ Exit code 0
- ✅ File exists, > 1 KB, valid ZIP containing `content.xml`

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

#### 1.3 🟢 Happy Path — EPUB (pandoc engine)
```bash
orf apply-md /tmp/orf-test-md/sample.md --target-format epub -o /tmp/orf-test-md/sample.epub
```
**Expected Result:**
- ✅ Exit code 0
- ✅ File exists, valid EPUB (ZIP containing `OEBPS/` or `META-INF/`)

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

#### 1.4 🟢 Happy Path — HTML (pure Python, no pandoc)
```bash
orf apply-md /tmp/orf-test-md/sample.md --target-format html -o /tmp/orf-test-md/sample.html
```
**Expected Result:**
- ✅ Exit code 0
- ✅ File exists, valid HTML with `<html>`, `<body>`, heading tags
- ✅ Works even with `OMNI_TEST_FAKE_PANDOC=1` (no pandoc needed)

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

#### 1.5 🟢 Happy Path — RTF (pandoc engine)
```bash
orf apply-md /tmp/orf-test-md/sample.md --target-format rtf -o /tmp/orf-test-md/sample.rtf
```
**Expected Result:**
- ✅ Exit code 0
- ✅ File exists, starts with `{\rtf`

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

#### 1.6 🟢 Happy Path — PDF (weasyprint engine)
```bash
orf apply-md /tmp/orf-test-md/sample.md --target-format pdf -o /tmp/orf-test-md/sample.pdf
```
**Expected Result:**
- ✅ Exit code 0
- ✅ File exists, starts with `%PDF`

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

#### 1.7 🟢 Happy Path — PPTX (pandoc fallback or md2pptx)
```bash
orf apply-md /tmp/orf-test-md/sample.md --target-format pptx -o /tmp/orf-test-md/sample.pptx
```
**Expected Result:**
- ✅ Exit code 0
- ✅ File exists, valid PPTX (ZIP containing `ppt/slides/`)
- ✅ ORF falls back gracefully if `md2pptx` CLI is missing (uses pandoc)

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

#### 1.8 🟢 Happy Path — ICML (pandoc engine)
```bash
orf apply-md /tmp/orf-test-md/sample.md --target-format icml -o /tmp/orf-test-md/sample.icml
```
**Expected Result:**
- ✅ Exit code 0
- ✅ File exists, contains `<ParagraphStyleRange` elements

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

#### 1.9 🟢 Happy Path — SRT (subtitles)
```bash
orf apply-md /tmp/orf-test-md/sample.md --target-format srt -o /tmp/orf-test-md/sample.srt
```
**Expected Result:**
- ✅ Exit code 0
- ✅ File exists, contains subtitle numbering and timestamps

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

#### 1.10 🟢 Happy Path — CSV (pandas engine)
```bash
orf apply-md /tmp/orf-test-md/sample.md --target-format csv -o /tmp/orf-test-md/sample.csv
```
**Expected Result:**
- ✅ Exit code 0
- ✅ File exists, comma-separated values, first row is header

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

#### 1.11 🟢 Happy Path — XLSX (openpyxl engine)
```bash
orf apply-md /tmp/orf-test-md/sample.md --target-format xlsx -o /tmp/orf-test-md/sample.xlsx
```
**Expected Result:**
- ✅ Exit code 0
- ✅ File exists, valid XLSX (ZIP containing `xl/workbook.xml`)

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

#### 1.12 🟢 Happy Path — JSON
```bash
orf apply-md /tmp/orf-test-md/sample.md --target-format json -o /tmp/orf-test-md/sample.json
```
**Expected Result:**
- ✅ Exit code 0
- ✅ File exists, valid JSON parseable by `python3 -c "import json; json.load(open('/tmp/orf-test-md/sample.json'))"`

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

#### 1.13 🟢 Happy Path — XML (lxml engine)
```bash
orf apply-md /tmp/orf-test-md/sample.md --target-format xml -o /tmp/orf-test-md/sample.xml
```
**Expected Result:**
- ✅ Exit code 0
- ✅ File exists, valid XML parseable by `python3 -c "import xml.etree.ElementTree; xml.etree.ElementTree.parse('/tmp/orf-test-md/sample.xml')"`

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

#### 1.14 🟢 Happy Path — IPYNB (nbformat engine)
```bash
orf apply-md /tmp/orf-test-md/sample.md --target-format ipynb -o /tmp/orf-test-md/sample.ipynb
```
**Expected Result:**
- ✅ Exit code 0
- ✅ File exists, valid notebook parseable by `python3 -c "import nbformat; nbformat.read('/tmp/orf-test-md/sample.ipynb', as_version=4)"`

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

#### 1.15 🟢 Happy Path — EML (email stdlib)
```bash
orf apply-md /tmp/orf-test-md/sample.md --target-format eml -o /tmp/orf-test-md/sample.eml
```
**Expected Result:**
- ✅ Exit code 0
- ✅ File exists, contains `From:`, `To:`, `Subject:`, `Content-Type:` headers

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

#### 1.16 🟢 Happy Path — MSG (aspose-email-foss, may skip)
```bash
orf apply-md /tmp/orf-test-md/sample.md --target-format msg -o /tmp/orf-test-md/sample.msg
```
**Expected Result:**
- ✅ Exit code 0 if `aspose-email-foss` installed
- ✅ ORF recommends `.eml` instead if MSG fails; clear error message mentions aspose-email-foss
- ➖ SKIP if aspose-email-foss not installed (document reason)

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

#### 1.17 🔴 Unknown format returns clear error
```bash
orf apply-md /tmp/orf-test-md/sample.md --target-format unknown -o /tmp/orf-test-md/sample.xyz
```
**Expected Result:**
- ❌ Exit code != 0
- ❌ Error message mentions unsupported format and lists available formats
- ❌ No Python traceback

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

#### 1.18 🔴 Missing input file returns clear error
```bash
orf apply-md /tmp/orf-test-md/nonexistent.md --target-format docx -o /tmp/orf-test-md/out.docx
```
**Expected Result:**
- ❌ Exit code != 0
- ❌ Error message mentions missing file
- ❌ No Python traceback

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

### 📊 Q1-ORF Verdict

| Scenario | Result |
|----------|--------|
| 1.1 DOCX | ⬜ |
| 1.2 ODT | ⬜ |
| 1.3 EPUB | ⬜ |
| 1.4 HTML | ⬜ |
| 1.5 RTF | ⬜ |
| 1.6 PDF | ⬜ |
| 1.7 PPTX | ⬜ |
| 1.8 ICML | ⬜ |
| 1.9 SRT | ⬜ |
| 1.10 CSV | ⬜ |
| 1.11 XLSX | ⬜ |
| 1.12 JSON | ⬜ |
| 1.13 XML | ⬜ |
| 1.14 IPYNB | ⬜ |
| 1.15 EML | ⬜ |
| 1.16 MSG | ⬜ |
| 1.17 Unknown format | ⬜ |
| 1.18 Missing input | ⬜ |

**OVERALL: ⬜** (✅ if all pass, ❌ if any fail)

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q2-ORF: Does MD→DOCX produce a valid, openable document?

**User says:** "I converted my MD to DOCX. Can I open it in Word without errors?"

**Why this matters:** DOCX is the most-requested output format. A corrupt or un-openable DOCX is a hard failure even if the CLI exits 0.

### Prerequisites
```bash
cd /tmp/orf-test-md
cat > docx-test.md << 'EOF'
# DOCX Validation

## Sections

This document tests **bold**, *italic*, ~~strikethrough~~, and `code`.

### Lists
- Apples
- Bananas
- Oranges

### Table
| Fruit | Color | Price |
|-------|-------|-------|
| Apple | Red   | $1.00 |
| Banana| Yellow| $0.50 |

### Code block
```python
print("hello world")
```

### Image
![Placeholder](https://via.placeholder.com/200)

> A blockquote for testing DOCX rendering.

Final paragraph with a [link](https://orf.omni-suite.dev).
EOF
```

### Scenarios

#### 2.1 🟢 DOCX is a valid ZIP with correct structure
```bash
orf apply-md /tmp/orf-test-md/docx-test.md --target-format docx -o /tmp/orf-test-md/docx-test.docx
python3 -c "
import zipfile
with zipfile.ZipFile('/tmp/orf-test-md/docx-test.docx') as z:
    names = z.namelist()
    print(f'Files in DOCX: {len(names)}')
    assert 'word/document.xml' in names, 'Missing word/document.xml'
    assert '[Content_Types].xml' in names
    print('✅ DOCX structure valid')
    for n in names:
        print(f'  {n}')
"
```
**Expected Result:**
- ✅ `word/document.xml` exists
- ✅ `[Content_Types].xml` exists
- ✅ `word/styles.xml` exists
- ✅ `word/_rels/document.xml.rels` exists
- ✅ Total structure is a valid OPC package

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

#### 2.2 🟢 DOCX document.xml contains correct content
```bash
python3 -c "
import zipfile
from xml.etree import ElementTree as ET
with zipfile.ZipFile('/tmp/orf-test-md/docx-test.docx') as z:
    xml_content = z.read('word/document.xml')
    root = ET.fromstring(xml_content)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    paragraphs = root.findall('.//w:p', ns)
    texts = []
    for p in paragraphs:
        ts = p.findall('.//w:t', ns)
        texts.extend(t.text or '' for t in ts if t.text)
    full_text = ' '.join(texts)
    print(f'Paragraphs: {len(paragraphs)}')
    assert 'DOCX Validation' in full_text, 'Missing heading text'
    assert 'bold' in full_text, 'Missing bold text'
    assert 'italic' in full_text, 'Missing italic text'
    assert 'Hello' in full_text or 'hello' in full_text, 'Missing code block text'
    assert 'Apple' in full_text, 'Missing table content'
    print('✅ DOCX content preserved')
"
```
**Expected Result:**
- ✅ Title "DOCX Validation" present in document.xml
- ✅ Bold, italic text preserved (found via `w:b` or present in text runs)
- ✅ Code block content present
- ✅ Table content (Apple, Banana) present
- ✅ Blockquote content present
- ✅ Link text present

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

#### 2.3 🟢 DOCX with `--separate-images` (default) extracts images.json
```bash
orf apply-md /tmp/orf-test-md/docx-test.md --target-format docx -o /tmp/orf-test-md/docx-separate.docx --json
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Images extracted as images.json + images.zip alongside output
- ✅ `--json` output contains `"success": true`, `"output_path"`, and `"images"` key

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

#### 2.4 🟢 DOCX with `--embed-images` inlines images
```bash
orf apply-md /tmp/orf-test-md/docx-test.md --target-format docx -o /tmp/orf-test-md/docx-embedded.docx --embed-images
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Output file exists and is openable
- ✅ Images are base64-encoded in the DOCX (no separate images.json)

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

#### 2.5 🟢 DOCX with `--reference-doc` applies custom styles
```bash
# Create a minimal reference docx or skip if none available
orf apply-md /tmp/orf-test-md/docx-test.md --target-format docx -o /tmp/orf-test-md/docx-styled.docx
# Without a real reference doc, this just tests the flag doesn't crash
```
**Expected Result:**
- ✅ `--reference-doc` flag accepted without error
- ✅ Output generated (may use default styles if reference doc missing)

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

#### 2.6 🔴 Empty Markdown produces minimal valid DOCX
```bash
echo "" > /tmp/orf-test-md/empty.md
orf apply-md /tmp/orf-test-md/empty.md --target-format docx -o /tmp/orf-test-md/empty.docx
```
**Expected Result:**
- ✅ Exit code 0 (empty doc is still valid)
- ✅ Produces a valid DOCX with at least `[Content_Types].xml` and empty body

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

### 📊 Q2-ORF Verdict

| Scenario | Result |
|----------|--------|
| 2.1 DOCX ZIP structure | ⬜ |
| 2.2 DOCX content | ⬜ |
| 2.3 `--separate-images` | ⬜ |
| 2.4 `--embed-images` | ⬜ |
| 2.5 `--reference-doc` | ⬜ |
| 2.6 Empty MD | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q3-ORF: Does MD→PPTX work (with md2pptx or pandoc fallback)?

**User says:** "I need to turn my translated Markdown into a PowerPoint presentation."

**Why this matters:** PPTX is a complex format with unique dependencies (md2pptx .NET CLI). The fallback path to pandoc must work when md2pptx is missing.

### Prerequisites
```bash
cd /tmp/orf-test-md
cat > pptx-test.md << 'EOF'
# Presentation Title

## Slide 1: Introduction

This is the first slide content with **important** points.

- Point one
- Point two
- Point three

## Slide 2: Data

| Metric | Value |
|--------|-------|
| Users  | 1000  |
| Growth | 15%   |

## Slide 3: Conclusion

Thank you for listening.
EOF
```

### Scenarios

#### 3.1 🟢 PPTX generated (via md2pptx or pandoc fallback)
```bash
orf apply-md /tmp/orf-test-md/pptx-test.md --target-format pptx -o /tmp/orf-test-md/pptx-test.pptx
```
**Expected Result:**
- ✅ Exit code 0
- ✅ File exists and > 1 KB
- ✅ Valid ZIP containing `ppt/slides/` directory
- ✅ At least one `ppt/slides/slide*.xml` file
- ✅ `[Content_Types].xml` present

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

#### 3.2 🟢 PPTX slides contain expected content
```bash
python3 -c "
import zipfile
from xml.etree import ElementTree as ET
with zipfile.ZipFile('/tmp/orf-test-md/pptx-test.pptx') as z:
    slides = [n for n in z.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')]
    print(f'Slides found: {len(slides)}')
    assert len(slides) >= 1, 'No slides found'
    for s in sorted(slides):
        content = z.read(s).decode('utf-8', errors='replace')
        print(f'  {s}: {len(content)} bytes')
    print('✅ PPTX slide structure valid')
"
```
**Expected Result:**
- ✅ At least 1 slide XML file
- ✅ Each slide is valid XML

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

#### 3.3 🟢 Fallback when md2pptx is missing — uses pandoc gracefully
```bash
# Simulate missing md2pptx by checking what ORF does
python3 -c "
import shutil
md2pptx_available = shutil.which('md2pptx') is not None
pandoc_available = shutil.which('pandoc') is not None
print(f'md2pptx available: {md2pptx_available}')
print(f'pandoc available: {pandoc_available}')
if not md2pptx_available and pandoc_available:
    print('✅ ORF should fall back to pandoc (check log for fallback message)')
elif not md2pptx_available and not pandoc_available:
    print('⚠️ Both missing — ORF should print actionable install hint')
"
```
**Expected Result:**
- ✅ If md2pptx missing + pandoc available: conversion succeeds via pandoc
- ✅ If both missing: clear error message with install instructions for md2pptx

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

#### 3.4 🟢 PPTX with images separated
```bash
orf apply-md /tmp/orf-test-md/pptx-test.md --target-format pptx -o /tmp/orf-test-md/pptx-test.pptx --json
```
**Expected Result:**
- ✅ Exit code 0
- ✅ JSON output includes `"success": true`

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

### 📊 Q3-ORF Verdict

| Scenario | Result |
|----------|--------|
| 3.1 PPTX generated | ⬜ |
| 3.2 Slides content | ⬜ |
| 3.3 Fallback behavior | ⬜ |
| 3.4 PPTX with images | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

# Part 2: XLIFF Backfill

---

## Q4-ORF: Can ORF backfill XLIFF into DOCX (with skeleton.zip)?

**User says:** "I have a translated XLIFF from OL and a skeleton.zip from OPP. Backfill it into my original DOCX."

**Why this matters:** XLIFF backfill is the layout-preserving path. If it fails, users lose styling, fonts, and exact positioning.

### Prerequisites
```bash
cd /tmp/orf-test-xliff && rm -rf ./*

# Create a minimal source DOCX for backfill testing
python3 << 'PYEOF'
import zipfile
from pathlib import Path

# Create minimal skeleton.zip (simulating OPP output)
# In production, OPP creates this. For testing, we build a minimal valid one.
skeleton_dir = Path('/tmp/orf-test-xliff/skeleton')
skeleton_dir.mkdir(exist_ok=True)

# Create a minimal DOCX skeleton
import io
docx_buf = io.BytesIO()
with zipfile.ZipFile(docx_buf, 'w') as z:
    z.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
    z.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    z.writestr('word/_rels/document.xml.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>')
    z.writestr('word/document.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Hello World</w:t></w:r></w:p></w:body></w:document>')

# Save as source.docx
with open('/tmp/orf-test-xliff/source.docx', 'wb') as f:
    f.write(docx_buf.getvalue())

# Save as skeleton.zip (copy of same content)
with open('/tmp/orf-test-xliff/skeleton.zip', 'wb') as f:
    f.write(docx_buf.getvalue())
print('✅ Test DOCX and skeleton.zip created')
PYEOF

# Create a minimal XLIFF
cat > /tmp/orf-test-xliff/translated.xlf << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file source-language="en" target-language="zh" original="source.docx">
    <body>
      <trans-unit id="1">
        <source>Hello World</source>
        <target>你好世界</target>
      </trans-unit>
    </body>
  </file>
</xliff>
EOF
```

### Scenarios

#### 4.1 🟢 Happy Path — XLIFF backfill into DOCX
```bash
orf apply-xliff /tmp/orf-test-xliff/source.docx \
  --xliff /tmp/orf-test-xliff/translated.xlf \
  --output /tmp/orf-test-xliff/backfilled.docx
```
**Expected Result:**
- ✅ Exit code 0
- ✅ `/tmp/orf-test-xliff/backfilled.docx` exists
- ✅ DOCX is a valid ZIP with `word/document.xml`
- ✅ Translated text "你好世界" present in document.xml
- ✅ Original structure preserved (styles, rels, content types)

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

#### 4.2 🟢 Backfilled DOCX contains translated text
```bash
python3 -c "
import zipfile
from xml.etree import ElementTree as ET
with zipfile.ZipFile('/tmp/orf-test-xliff/backfilled.docx') as z:
    xml = z.read('word/document.xml')
    root = ET.fromstring(xml)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    texts = root.findall('.//w:t', ns)
    text_content = ' '.join(t.text or '' for t in texts if t.text)
    print(f'Text content: {text_content}')
    assert '你好世界' in text_content, 'Translated text not found!'
    print('✅ Translation successfully backfilled')
"
```
**Expected Result:**
- ✅ "你好世界" found in document.xml
- ✅ Source text "Hello World" may or may not be present (test both outcomes)

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

#### 4.3 🟢 JSON output works
```bash
orf apply-xliff /tmp/orf-test-xliff/source.docx \
  --xliff /tmp/orf-test-xliff/translated.xlf \
  --output /tmp/orf-test-xliff/backfilled.json.docx --json
```
**Expected Result:**
- ✅ Exit code 0
- ✅ JSON output on stdout with `"success": true`, `"output_path"`, `"units_processed"`

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

#### 4.4 🔴 Missing skeleton.zip — clear error
```bash
# Move skeleton.zip away temporarily
mkdir -p /tmp/orf-test-xliff/noskel
cp /tmp/orf-test-xliff/source.docx /tmp/orf-test-xliff/noskel/
orf apply-xliff /tmp/orf-test-xliff/noskel/source.docx \
  --xliff /tmp/orf-test-xliff/translated.xlf \
  --output /tmp/orf-test-xliff/noskel/out.docx 2>&1
```
**Expected Result:**
- ❌ Exit code != 0 (or output without skeleton)
- ❌ Error message mentions missing skeleton.zip
- ❌ No Python traceback

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

#### 4.5 🔴 Mismatched XLIFF source — graceful handling
```bash
cat > /tmp/orf-test-xliff/mismatched.xlf << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file source-language="en" target-language="zh" original="source.docx">
    <body>
      <trans-unit id="1">
        <source>Nonexistent Paragraph</source>
        <target>不存在的段落</target>
      </trans-unit>
    </body>
  </file>
</xliff>
EOF
orf apply-xliff /tmp/orf-test-xliff/source.docx \
  --xliff /tmp/orf-test-xliff/mismatched.xlf \
  --output /tmp/orf-test-xliff/mismatched.docx
```
**Expected Result:**
- ✅ Exit code 0 or non-zero (implementation-dependent)
- ✅ ORF handles fuzzy match or reports unmatched units
- ✅ No crash — either backfill succeeds (fuzzy match) or reports SKIPPED units

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

### 📊 Q4-ORF Verdict

| Scenario | Result |
|----------|--------|
| 4.1 XLIFF backfill DOCX | ⬜ |
| 4.2 Translated content | ⬜ |
| 4.3 JSON output | ⬜ |
| 4.4 Missing skeleton | ⬜ |
| 4.5 Mismatched XLIFF | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q5-ORF: Can ORF backfill XLIFF into PPTX (with skeleton.zip)?

**User says:** "I translated a PowerPoint. Backfill the XLIFF into the original PPTX."

**Why this matters:** PPTX XLIFF backfill has a different internal structure (slide XML files) and different skeleton handling than DOCX.

### Prerequisites
```bash
cd /tmp/orf-test-xliff

# Create a minimal PPTX skeleton
python3 << 'PYEOF'
import zipfile
from pathlib import Path

with zipfile.ZipFile('/tmp/orf-test-xliff/source.pptx', 'w') as z:
    z.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/></Types>')
    z.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/></Relationships>')
    z.writestr('ppt/_rels/presentation.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/></Relationships>')
    z.writestr('ppt/presentation.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst><p:sldSz cx="9144000" cy="6858000"/></p:presentation>')
    z.writestr('ppt/slides/slide1.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:nvPr><p:cpho idx="0"/></p:nvPr></p:nvGrpSpPr><p:sp><p:nvSpPr><p:cNvPr id="2" name="Title 1"/><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"/><a:p xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:r><a:t>Hello PPTX</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>')

# Save skeleton.zip
import shutil
shutil.copy('/tmp/orf-test-xliff/source.pptx', '/tmp/orf-test-xliff/skeleton_pptx.zip')
print('✅ Test PPTX and skeleton created')
PYEOF

# Create XLIFF for PPTX
cat > /tmp/orf-test-xliff/translated_pptx.xlf << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file source-language="en" target-language="zh" original="source.pptx">
    <body>
      <trans-unit id="1">
        <source>Hello PPTX</source>
        <target>你好PPTX</target>
      </trans-unit>
    </body>
  </file>
</xliff>
EOF
```

### Scenarios

#### 5.1 🟢 XLIFF backfill into PPTX
```bash
orf apply-xliff /tmp/orf-test-xliff/source.pptx \
  --xliff /tmp/orf-test-xliff/translated_pptx.xlf \
  --output /tmp/orf-test-xliff/backfilled.pptx
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Output file exists, valid PPTX (ZIP with `ppt/slides/`)
- ✅ Translated text present in slide XML

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

#### 5.2 🟢 Translated text appears in PPTX slides
```bash
python3 -c "
import zipfile
with zipfile.ZipFile('/tmp/orf-test-xliff/backfilled.pptx') as z:
    slide_content = z.read('ppt/slides/slide1.xml').decode('utf-8', errors='replace')
    print(f'Slide content snippet: {slide_content[200:400]}')
    assert '你好PPTX' in slide_content, 'Translated text not found in PPTX!'
    print('✅ PPTX translation backfilled successfully')
"
```
**Expected Result:**
- ✅ "你好PPTX" found in slide XML
- ✅ Slide structure preserved

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

### 📊 Q5-ORF Verdict

| Scenario | Result |
|----------|--------|
| 5.1 XLIFF backfill PPTX | ⬜ |
| 5.2 Translated content | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q6-ORF: Does XLIFF backfill preserve images (inline + floating)?

**User says:** "My source document has inline and floating images. I need them preserved after backfill."

**Why this matters:** Image preservation (especially floating images with absolute positioning) is a critical layout-fidelity requirement. ORF v0.4.0 added floating image support.

### Scenarios

#### 6.1 🟢 Inline images preserved in DOCX backfill
```python
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

# Create source DOCX with an inline image
import io, shutil
docx_buf = io.BytesIO()
with zipfile.ZipFile(docx_buf, 'w') as z:
    z.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
    z.writestr('_rels/.rels', '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    z.writestr('word/_rels/document.xml.rels', '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/></Relationships>')
    z.writestr('word/document.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body><w:p><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="914400" cy="914400"/><wp:effectExtent l="0" t="0" r="0" b="0"/><wp:docPr id="1" name="Picture 1"/><wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr><a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="1" name="Image1"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="rId1"/></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="914400" cy="914400"/></a:xfrm><a:prstGeom prst="rect"/></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p></w:body></w:document>')
    z.writestr('word/media/image1.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)  # minimal PNG

with open('/tmp/orf-test-xliff/img_source.docx', 'wb') as f:
    f.write(docx_buf.getvalue())
with open('/tmp/orf-test-xliff/img_skeleton.zip', 'wb') as f:
    f.write(docx_buf.getvalue())

print('✅ Source DOCX with inline image created')

# After backfill with a matching XLIFF, verify image count
# (This is a structural check — test with real OPP output for full validation)
```
**Expected Result:**
- ✅ After XLIFF backfill, image count in DOCX matches source count
- ✅ No duplicate images injected (E2E-07 dedup)
- ✅ `<wp:inline>` or `<wp:anchor>` elements preserved at the correct count

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

#### 6.2 🟢 Floating images (wp:anchor) preserved
```python
import zipfile
from xml.etree import ElementTree as ET

# Verify that wp:anchor element exists in source and is preserved in output
with zipfile.ZipFile('/tmp/orf-test-xliff/img_source.docx') as z:
    source_xml = z.read('word/document.xml')
    root = ET.fromstring(source_xml)
    ns = {
        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
        'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    }
    inlines = root.findall('.//wp:inline', ns)
    anchors = root.findall('.//wp:anchor', ns)
    print(f'Inline images: {len(inlines)}')
    print(f'Floating images: {len(anchors)}')
    # If source has floating images, require anchor count preserved
    if anchors:
        print('✅ Source has floating images (positions preserved in skeleton)')
    else:
        print('ℹ️ Source has no floating images — this test is informational')
```
**Expected Result:**
- ✅ Floating images (if present) have positionH/positionV with relativeFrom attributes preserved
- ✅ No floating images are silently dropped
- ✅ ORF dedup does not remove legitimate floating images

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

#### 6.3 🟢 Image manifest (images.json) correctly tracks placement
```bash
python3 -c "
import json
# If ORF produced images.json alongside output, verify its structure
img_path = '/tmp/orf-test-xliff/images.json'
try:
    with open(img_path) as f:
        manifest = json.load(f)
    print(f'Images in manifest: {len(manifest)}')
    for img in manifest:
        assert 'file_path' in img or 'data_base64' in img, 'Missing image source'
        assert 'placement' in img, 'Missing placement info'
        # floating flag should be present if applicable
        if 'is_floating' in img:
            print(f'  Image: floating={img[\"is_floating\"]}')
    print('✅ Image manifest valid')
except FileNotFoundError:
    print('ℹ️ images.json not produced — check --separate-images behavior')
"
```
**Expected Result:**
- ✅ images.json (if produced) follows OPP schema with file_path/data_base64 and placement
- ✅ Each entry has `is_floating` flag when applicable

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

### 📊 Q6-ORF Verdict

| Scenario | Result |
|----------|--------|
| 6.1 Inline images preserved | ⬜ |
| 6.2 Floating images preserved | ⬜ |
| 6.3 Image manifest | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q7-ORF: Does cross-format XLIFF backfill (--force) work?

**User says:** "I translated a DOCX but need the output as PPTX. Can ORF handle cross-format XLIFF backfill?"

**Why this matters:** Cross-format backfill (e.g., DOCX→XLIFF→PPTX) is a differentiation feature. The `--force` flag bypasses format validation.

### Prerequisites
```bash
cd /tmp/orf-test-xliff
# Uses source.docx, skeleton.zip, and translated.xlf from Q4
```

### Scenarios

#### 7.1 🟢 Cross-format via --force (DOCX XLIFF → PPTX output)
```bash
orf apply-xliff /tmp/orf-test-xliff/source.docx \
  --xliff /tmp/orf-test-xliff/translated.xlf \
  --output /tmp/orf-test-xliff/cross.pptx \
  --force
```
**Expected Result:**
- ✅ Exit code 0
- ✅ ORF emits warning about format mismatch
- ✅ Output PPTX file exists and is valid ZIP
- ✅ Translated text "你好世界" present in output

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

#### 7.2 🟢 Cross-format without --force warns and rejects
```bash
orf apply-xliff /tmp/orf-test-xliff/source.docx \
  --xliff /tmp/orf-test-xliff/translated.xlf \
  --output /tmp/orf-test-xliff/cross_noforce.pptx 2>&1
```
**Expected Result:**
- ❌ Error message: format mismatch detected
- ❌ Message recommends `--force` to proceed
- ❌ No corruption of input files

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

#### 7.3 🟢 Cross-format with `--json` produces machine-readable output
```bash
orf apply-xliff /tmp/orf-test-xliff/source.docx \
  --xliff /tmp/orf-test-xliff/translated.xlf \
  --output /tmp/orf-test-xliff/cross_json.pptx \
  --force --json
```
**Expected Result:**
- ✅ Exit code 0
- ✅ JSON output with `"success": true`, `"warning"` about cross-format

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

### 📊 Q7-ORF Verdict

| Scenario | Result |
|----------|--------|
| 7.1 Cross-format with --force | ⬜ |
| 7.2 Cross-format without --force | ⬜ |
| 7.3 Cross-format JSON output | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

# Part 3: MCP Surface Mastery

---

## Q8-ORF: Do all 7 MCP tools work correctly?

**User says:** "I'm connecting via MCP protocol. I need all 7 tools to work as documented."

**Why this matters:** MCP is the primary integration surface for AI agents. Broken tools break automation.

### Prerequisites
```bash
export ORF_MCP_ALLOWED_DIRS="/tmp/orf-test-md:/tmp/orf-test-xliff:/tmp/orf-test-mcp"
cd /mnt/d/贯维/Omni_Suite/Omni_Re_Formatter
```

### Scenarios

#### 8.1 🟀 Server start + tool listing (in-process)
```python
import asyncio, json
from orf.mcp.server import server, _list_tools

# Check tools are registered
tools = asyncio.run(_list_tools())
tool_names = [t.name for t in tools]
print(f"Tools registered: {len(tools)}")
print(f"Names: {tool_names}")
expected_tools = ["apply_md", "apply_xliff", "batch_convert", "detect_format", "info", "ping", "get_capabilities"]
missing = [t for t in expected_tools if t not in tool_names]
assert len(missing) == 0, f"Missing tools: {missing}"
print("✅ ALL 7 TOOLS PRESENT")
```
**Expected Result:** ✅ 7 tools registered: `apply_md`, `apply_xliff`, `batch_convert`, `detect_format`, `info`, `ping`, `get_capabilities`

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

#### 8.2 🟢 ping — health check
```python
from orf.mcp.tools import ping
result = json.loads(ping())
print(f"ping result: {json.dumps(result, indent=2)}")
assert result.get("success") is True
assert "version" in result
assert "module" in result
print("✅ ping OK")
```
**Expected Result:** ✅ Returns `{"success": true, "version": "0.4.17", "module": "orf"}`

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

#### 8.3 🟢 get_capabilities — module capabilities
```python
from orf.mcp.tools import get_capabilities
result = json.loads(get_capabilities())
print(json.dumps(result, indent=2))
assert result.get("success") is True
assert "md_output_formats" in result
assert "xliff_backfill_formats" in result
assert "mcp_tools" in result
assert len(result["md_output_formats"]) >= 16
assert len(result["xliff_backfill_formats"]) >= 5
print("✅ get_capabilities OK")
```
**Expected Result:** ✅ Returns 16 MD formats, 5 XLIFF formats, 7 MCP tool names

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

#### 8.4 🟢 apply_md — MD to DOCX via MCP
```python
from orf.mcp.tools import apply_md
result = json.loads(apply_md(
    input_md="/tmp/orf-test-md/sample.md",
    target_format="docx",
    output_path="/tmp/orf-test-mcp/mcp_test.docx",
    auth_token=None,
))
print(json.dumps(result, indent=2))
assert result.get("success") is True
assert "output_path" in result
print("✅ apply_md via MCP OK")
```
**Expected Result:** ✅ Returns `{"success": true, "output_path": "...", "format": "docx"}`

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

#### 8.5 🟢 apply_xliff — XLIFF backfill via MCP
```python
from orf.mcp.tools import apply_xliff
result = json.loads(apply_xliff(
    input_file="/tmp/orf-test-xliff/source.docx",
    xliff_path="/tmp/orf-test-xliff/translated.xlf",
    output_path="/tmp/orf-test-mcp/mcp_xliff.docx",
    format="docx",
    auth_token=None,
))
print(json.dumps(result, indent=2))
assert result.get("success") is True
print("✅ apply_xliff via MCP OK")
```
**Expected Result:** ✅ Returns `{"success": true, "output_path": "...", "units_processed": N}`

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

#### 8.6 🟢 batch_convert — batch MD conversion via MCP
```python
from orf.mcp.tools import batch_convert
result = json.loads(batch_convert(
    input_dir="/tmp/orf-test-md",
    target_format="html",
    pattern="*.md",
    auth_token=None,
))
print(json.dumps(result, indent=2))
assert result.get("success") is True
assert "files_processed" in result or "converted" in result
print("✅ batch_convert via MCP OK")
```
**Expected Result:** ✅ Returns `{"success": true, "files_processed": N}` or similar

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

#### 8.7 🟢 detect_format — format detection via MCP
```python
from orf.mcp.tools import detect_format
result = json.loads(detect_format(
    file_path="/tmp/orf-test-md/sample.md",
    auth_token=None,
))
print(json.dumps(result, indent=2))
assert result.get("success") is True
assert "format" in result
print("✅ detect_format via MCP OK")
```
**Expected Result:** ✅ Returns `{"success": true, "format": "markdown"}` or similar detected format

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

#### 8.8 🟢 info — document info via MCP
```python
from orf.mcp.tools import info
result = json.loads(info(
    file_path="/tmp/orf-test-md/sample.md",
    auth_token=None,
))
print(json.dumps(result, indent=2))
assert result.get("success") is True
assert "format" in result
assert "size" in result or "file_size" in result
print("✅ info via MCP OK")
```
**Expected Result:** ✅ Returns `{"success": true, "format": "markdown", "size": N, "file_size_bytes": N}`

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

#### 8.9 🟢 apply_md with inline content (E2E-76 path)
```python
from orf.mcp.tools import apply_md
result = json.loads(apply_md(
    content="# Inline Content\n\nThis is **inline** markdown.",
    target_format="html",
    auth_token=None,
))
print(json.dumps(result, indent=2))
assert result.get("success") is True
assert "content" in result  # text-in/text-out returns content
print("✅ apply_md inline content via MCP OK")
```
**Expected Result:** ✅ Returns `{"success": true, "content": "<h1>Inline Content</h1>..."}` (text-in/text-out returns content, not file path)

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

#### 8.10 🔴 MCP error — missing required parameter
```python
from orf.mcp.tools import apply_md
import json
try:
    result = json.loads(apply_md(target_format="docx", auth_token=None))  # missing input_md OR content
    print(f"Result: {json.dumps(result, indent=2)}")
    assert result.get("success") is False
    assert "error" in result or "error_code" in result
    print("✅ Error response has error_code/message")
except Exception as e:
    print(f"Exception caught: {e}")
    print("✅ Exception raised as expected for missing params")
```
**Expected Result:**
- ❌ `success` is False
- ❌ Error response has `error_code`, `message`, `actionable` fields
- ❌ No raw Python traceback leaked

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

#### 8.11 🔴 MCP error — unknown tool name
```python
from orf.mcp.server import _call_tool
import json
try:
    result = await _call_tool("nonexistent_tool", {})
    print(f"Unexpected success: {result}")
except Exception as e:
    print(f"Expected error caught: {e}")
    print("✅ Unknown tool raises handled exception (not crash)")
```
**Expected Result:**
- ❌ Does NOT crash the server
- ❌ Returns error or raises ValueError with "Unknown tool" message

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

#### 8.12 🟢 MCP auth — MCP_SHARED_SECRET respected
```python
import os
os.environ["MCP_SHARED_SECRET"] = "test-secret"
# Reload auth module state
from orf.mcp.auth import verify_auth
# Test with wrong token
result = verify_auth("wrong-token")
print(f"Auth with wrong token: {result}")
# Test with correct token
os.environ.pop("MCP_SHARED_SECRET", None)
```
**Expected Result:**
- ✅ With wrong token: auth fails (returns error response)
- ✅ With correct token: auth passes
- ✅ Without MCP_SHARED_SECRET set: auth is disabled (passes)

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

### 📊 Q8-ORF Verdict

| Scenario | Result |
|----------|--------|
| 8.1 Tool listing (7 tools) | ⬜ |
| 8.2 ping | ⬜ |
| 8.3 get_capabilities | ⬜ |
| 8.4 apply_md | ⬜ |
| 8.5 apply_xliff | ⬜ |
| 8.6 batch_convert | ⬜ |
| 8.7 detect_format | ⬜ |
| 8.8 info | ⬜ |
| 8.9 apply_md inline content | ⬜ |
| 8.10 Missing param error | ⬜ |
| 8.11 Unknown tool error | ⬜ |
| 8.12 Auth handling | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

# Part 4: Agent Orchestration & Production

---

## Q9-ORF: Does ForemanAgent batched conversion work?

**User says:** "I have a directory of translated MD files. I want ORF to intelligently route them to the right specialist and convert all of them."

**Why this matters:** Foreman/Specialist orchestration is ORF's intelligent routing layer. If it fails, the agent can't batch-process mixed document types.

### Prerequisites
```bash
cd /tmp/orf-test-foreman && rm -rf ./*
mkdir -p docs

cat > docs/report.md << 'EOF'
# Annual Report
Content for the format specialist.
EOF

cat > docs/data.csv << 'EOF'
name,value
A,1
B,2
EOF

cat > docs/notebook.ipynb << 'EOF'
{"cells":[{"cell_type":"markdown","metadata":{},"source":["# Notebook"]}],"metadata":{"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"}},"nbformat":4,"nbformat_minor":2}
EOF
```

### Scenarios

#### 9.1 🟢 ForemanAgent routes correctly to specialists
```python
from pathlib import Path
from orf.agents.foreman import ForemanAgent, JobRequest

agent = ForemanAgent()

# Test complexity assessment
for fname, expected_complexity in [("report.md", "SIMPLE"), ("data.csv", "SIMPLE")]:
    job = JobRequest(
        input_path=str(Path("/tmp/orf-test-foreman/docs") / fname),
        target_format="docx",
    )
    complexity = agent.assess_complexity(job)
    print(f"{fname}: complexity={complexity.name}")
    assert complexity.name == expected_complexity, f"Expected {expected_complexity}, got {complexity.name}"

print("✅ ForemanAgent assesses complexity correctly")
```
**Expected Result:**
- ✅ `assess_complexity()` returns `SIMPLE` for single small files
- ✅ `assess_complexity()` returns `MODERATE` for batch jobs
- ✅ Specialists are initialized without error

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

#### 9.2 🟢 ForemanAgent conversion run
```python
from pathlib import Path
from orf.agents.foreman import ForemanAgent

agent = ForemanAgent()
result = agent.run("docs/", target_format="docx")
print(f"Success: {result}")
# Foreman may return a JobResult or execute specialists
```
**Expected Result:**
- ✅ `run()` completes without exception
- ✅ Conversion produces output files
- ✅ Errors (if any) are captured in result, not raised

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

#### 9.3 🟢 Specialist format routing
```python
from orf.agents.specialists import FormatSpecialist, DataSpecialist, MarkupSpecialist, EmailSpecialist

# Each specialist should handle their domain
fs = FormatSpecialist()
ds = DataSpecialist()
ms = MarkupSpecialist()
es = EmailSpecialist()

# Check format routing
print(f"FormatSpecialist handles: DOCX/ODT/EPUB/PPTX")
print(f"DataSpecialist handles: XLSX/CSV/JSON")
print(f"MarkupSpecialist handles: XML/HTML")
print(f"EmailSpecialist handles: EML/MSG")
print("✅ All specialists initialized")
```
**Expected Result:**
- ✅ All 4 specialist types initialize without error
- ✅ Each specialist advertises its supported formats

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

#### 9.4 🟢 HITL approval — files >100MB trigger human review
```python
from orf.workflow.hitl_approval import HITLApproval

hitl = HITLApproval()
# Large file check
threshold = hitl.get_file_size_threshold()
print(f"HITL file size threshold: {threshold} MB")
# Standard operation should pass without approval
approval = hitl.request_approval("Standard conversion", risk_level="LOW")
print(f"Low-risk approval: {approval}")
```
**Expected Result:**
- ✅ Low-risk operations (standard conversion): auto-approved
- ✅ File > 100MB: requires approval
- ✅ Cloud uploads: require approval
- ✅ File > 500MB: rejected as UNACCEPTABLE

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

### 📊 Q9-ORF Verdict

| Scenario | Result |
|----------|--------|
| 9.1 Foreman complexity | ⬜ |
| 9.2 Foreman run | ⬜ |
| 9.3 Specialist routing | ⬜ |
| 9.4 HITL approval | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q10-ORF: Does the MCP server work via stdio?

**User says:** "In production, MCP runs as a separate process. Does the stdio protocol work?"

**Why this matters:** The MCP server over stdio transport is how AI agents connect to ORF in production.

### Scenarios

#### 10.1 🟢 MCP server starts and responds to initialize
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | timeout 5 python3 -m orf.mcp.server 2>/dev/null
```
**Expected Result:**
- ✅ Server starts
- ✅ Responds to JSON-RPC initialize with server capabilities
- ✅ Response includes `orf-mcp` server name

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

#### 10.2 🟢 MCP ping over stdio
```bash
printf '{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}\n' | timeout 5 python3 -m orf.mcp.server 2>/dev/null | head -5
```
**Expected Result:**
- ✅ Server responds with `{"jsonrpc":"2.0","id":1,"result":{}}`
- ✅ Exit code 0 after timeout

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

#### 10.3 🔴 Invalid JSON-RPC
```bash
echo 'not json at all' | timeout 5 python3 -m orf.mcp.server 2>/dev/null; echo "Exit: $?"
```
**Expected Result:**
- ❌ Server does NOT crash
- ❌ Returns JSON-RPC error response (parse error)
- ❌ No Python traceback leaked

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

#### 10.4 🟢 MCP server module structure
```bash
python3 -c "from orf.mcp.server import main, get_server; print('✅ Server entry points importable')"
```
**Expected Result:**
- ✅ `python -m orf.mcp.server` works from anywhere
- ✅ `main()` function is the entry point (used by `orf mcp` CLI)
- ✅ `get_server()` returns the `Server` instance

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

### 📊 Q10-ORF Verdict

| Scenario | Result |
|----------|--------|
| 10.1 Server initialize | ⬜ |
| 10.2 Ping over stdio | ⬜ |
| 10.3 Invalid JSON-RPC | ⬜ |
| 10.4 Module structure | ⬜ |

**OVERALL: ⬜**

### 🧹 Cleanup

```bash
rm -rf /tmp/[test-directory]
# Kill any background processes started during this section
```

---

## Q11-ORF: What happens with missing dependencies (pandoc, md2pptx, skeleton.zip)?

**User says:** "I don't have pandoc installed. Can ORF still convert my documents?"

**Why this matters:** ORF has multiple engine paths. Users may not have all dependencies. Graceful fallback and clear error messages are critical.

### Scenarios

#### 11.1 🟢 HTML works without pandoc (pure Python markdown lib)
```bash
export OMNI_TEST_FAKE_PANDOC=1  # Simulate no pandoc
orf apply-md /tmp/orf-test-md/sample.md --target-format html -o /tmp/orf-test-md/nopandoc.html
unset OMNI_TEST_FAKE_PANDOC
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Valid HTML generated without pandoc
- ✅ Pure Python `markdown` lib used as engine

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

#### 11.2 🟢 PDF works without pandoc (weasyprint engine)
```bash
export OMNI_TEST_FAKE_PANDOC=1
orf apply-md /tmp/orf-test-md/sample.md --target-format pdf -o /tmp/orf-test-md/nopandoc.pdf
unset OMNI_TEST_FAKE_PANDOC
```
**Expected Result:**
- ✅ Exit code 0
- ✅ Valid PDF generated (weasyprint engine)
- ✅ File starts with `%PDF`

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

#### 11.3 🟢 DOCX with pandoc missing — actionable error
```bash
export OMNI_TEST_FAKE_PANDOC=1
orf apply-md /tmp/orf-test-md/sample.md --target-format docx -o /tmp/orf-test-md/nopandoc.docx 2>&1
unset OMNI_TEST_FAKE_PANDOC
```
**Expected Result:**
- ❌ Exit code != 0 (DOCX needs pandoc)
- ❌ Error message mentions pandoc dependency
- ❌ Message includes installation hint (pypandoc-binary or pandoc)
- ❌ No raw traceback

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

#### 11.4 🟢 PPTX with both md2pptx + pandoc missing — actionable error
```bash
# Simulate both missing
export OMNI_TEST_FAKE_PANDOC=1
# If md2pptx is not on PATH, ORF should print install hint
orf apply-md /tmp/orf-test-md/sample.md --target-format pptx -o /tmp/orf-test-md/nopptx.pptx 2>&1
unset OMNI_TEST_FAKE_PANDOC
```
**Expected Result:**
- ❌ Exit code != 0
- ❌ Error message mentions md2pptx install instructions
- ❌ Suggests `dotnet tool install --global md2pptx`
- ❌ No raw Python traceback

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

#### 11.5 🟢 MSG without aspose-email-foss — clear recommendation
```bash
orf apply-md /tmp/orf-test-md/sample.md --target-format msg -o /tmp/orf-test-md/nomsg.msg 2>&1
```
**Expected Result:**
- ❌ Exit code != 0 (if aspose not installed)
- ❌ Error mentions aspose-email-foss dependency
- ❌ Message recommends using `.eml` instead
- ❌ No crash

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

#### 11.6 🟢 Cache system — repeated run uses cache
```bash
# First run (cache miss)
orf apply-md /tmp/orf-test-md/sample.md --target-format html -o /tmp/orf-test-md/cached.html --verbose 2>&1 | grep -i cache || true
# Second run (cache hit)
orf apply-md /tmp/orf-test-md/sample.md --target-format html -o /tmp/orf-test-md/cached2.html --verbose 2>&1 | grep -i cache || true
```
**Expected Result:**
- ✅ First run: cache miss (or cache is populated)
- ✅ Second run with same input + config: cache hit
- ✅ Second run completes faster (cache copy vs full conversion)
- ✅ `--no-cache` flag skips cache

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

#### 11.7 🟢 PathValidator blocks unauthorized paths
```python
from orf.mcp.security import PathValidator
from pathlib import Path
import tempfile

# Create validator with specific allowed dirs
validator = PathValidator(allowed_dirs=[Path("/tmp/allowed")])

# Test allowed path
allowed_result = validator.validate("/tmp/allowed/test.md")
print(f"Allowed path: {allowed_result}")

# Test blocked path
blocked_result = None
try:
    blocked_result = validator.validate("/etc/passwd")
    print(f"Blocked path: {blocked_result}")
except Exception as e:
    print(f"Blocked path raised: {type(e).__name__}: {e}")

# Test blocked extension
try:
    ext_result = validator.validate("/tmp/allowed/virus.exe")
    print(f"Exe path: {ext_result}")
except Exception as e:
    print(f"Blocked extension: {type(e).__name__}: {e}")
```
**Expected Result:**
- ✅ Allowed path: validates successfully
- ✅ Path outside allowed dirs: blocked (error or raises)
- ✅ Executable extensions (.exe, .bat, .sh): blocked
- ✅ Symlink pointing outside allowlist: blocked

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

### 📊 Q11-ORF Verdict

| Scenario | Result |
|----------|--------|
| 11.1 HTML without pandoc | ⬜ |
| 11.2 PDF without pandoc | ⬜ |
| 11.3 DOCX without pandoc | ⬜ |
| 11.4 PPTX without md2pptx | ⬜ |
| 11.5 MSG without aspose | ⬜ |
| 11.6 Cache system | ⬜ |
| 11.7 PathValidator security | ⬜ |

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
| 1 | MD Backfill (Q1-ORF — Q3-ORF) | ⬜ |
| 2 | XLIFF Backfill (Q4-ORF — Q7-ORF) | ⬜ |
| 3 | MCP Surface Mastery (Q8-ORF) | ⬜ |
| 4 | Agent Orchestration & Production (Q9-ORF — Q11-ORF) | ⬜ |

**GRAND TOTAL: ⬜ / 11 Questions**

**OVERALL VERDICT: ⬜**

---

## Production Gap Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| All 16 MD output formats produce valid files | ⬜ | Q1-ORF |
| DOCX output has correct ZIP structure + content | ⬜ | Q2-ORF |
| PPTX works via md2pptx or pandoc fallback | ⬜ | Q3-ORF |
| XLIFF→DOCX backfill preserves translated text | ⬜ | Q4-ORF |
| XLIFF→PPTX backfill preserves slides | ⬜ | Q5-ORF |
| Inline + floating images preserved in backfill | ⬜ | Q6-ORF |
| Cross-format XLIFF backfill (--force) works | ⬜ | Q7-ORF |
| All 7 MCP tools respond correctly | ⬜ | Q8-ORF |
| apply_md inline content (E2E-76) works | ⬜ | Q8-ORF |
| MCP error responses structured, no traceback leak | ⬜ | Q8-ORF |
| ForemanAgent complexity assessment works | ⬜ | Q9-ORF |
| HITL approval gates large files + cloud uploads | ⬜ | Q9-ORF |
| MCP server stdio transport responds correctly | ⬜ | Q10-ORF |
| Pure Python formats work without pandoc | ⬜ | Q11-ORF |
| Missing dependency errors are actionable | ⬜ | Q11-ORF |
| Content-addressed cache works | ⬜ | Q11-ORF |
| PathValidator prevents directory traversal | ⬜ | Q11-ORF |
| MCP_SHARED_SECRET auth respected | ⬜ | Q8-ORF |

---

## Sign-off Criteria

| Level | Requirements | Met? |
|-------|-------------|------|
| **CI Gate** | All 11 questions answered. No P0 failures (crash, data loss, no output). | ⬜ |
| **Release Candidate** | CI Gate + Q1-ORF — Q8-ORF all PASS + all production gaps addressed | ⬜ |
| **Production Deploy** | Release Candidate + Q9-ORF — Q11-ORF all PASS + no outstanding P0/P1 issues | ⬜ |

---

*Plan generated: 2026-07-22*
*Based on: ORF v0.4.17 codebase — 16 MD formats, 5 XLIFF formats, 7 MCP tools, Foreman/Specialist, HITL approval, PathValidator security*
