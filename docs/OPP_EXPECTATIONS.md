# OPP Founder's Expectations + Agent Validation Master Plan

> **Version:** v0.9.1 · **Role:** Stage 1 — Document Extraction
> **Downstream:** OL (translation) → ORF (backfill)
> **Date:** 2026-07-22

This document defines what OPP must deliver from the founder's perspective and how any AI agent can systematically validate every expectation.

---

# Part 1 — Founder's Expectations

## 1. Introduction

OPP is the **first step** of the Omni Suite pipeline. It ingests documents in 13+ input formats and extracts them into three standardized artifacts:

| Artifact | Purpose | Consumed By |
|----------|---------|-------------|
| **Markdown (`.md`)** | Clean text with YAML frontmatter | OL `translate-md`, ORF `apply-md` |
| **XLIFF (`.xlf`)** | Translation units with `<bx>`/`<ex>` inline tags | OL `translate-xliff`, ORF `apply-xliff` |
| **Skeleton (`.skeleton.zip`)** | Original ZIP structure (DOCX/PPTX/EPUB only) | ORF `apply-xliff` for layout-faithful backfill |

If OPP produces bad output, everything downstream fails. This is the foundation.

## 2. Design Principles

| Principle | Meaning |
|-----------|---------|
| **Format coverage** | Every mainstream document format must have a dedicated extractor |
| **Lossless extraction** | Paragraphs, tables, lists, inline formatting (bold/italic/underline) preserved in XLIFF as `<bx>`/`<ex>` tags |
| **Image fidelity** | Images deduplicated (MD5+UUID), floating vs inline distinguished, position data preserved for ORF |
| **Path security** | MCP PathValidator enforces directory allowlist, blocks traversal, symlink attacks, and blocked extensions |
| **Agent-native** | All capabilities exposed as MCP tools (9 tools) — CLI is a fallback |
| **Fail-closed security** | `OPP_MCP_ALLOWED_DIRS` is required; server refuses to start without it |
| **Defense in depth** | Rate limiter + shared-secret auth + path validation + error boundary decorator on every tool |

## 3. Expectation Catalog

### F01 — Support all 13+ input formats

| Aspect | Specification |
|--------|---------------|
| **Formats with dedicated extractors** | DOCX, PPTX, PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML/MSG, Image (OCR), Audio, Video, IPYNB, YouTube URL — **16 extractors** registered in `opp/extractors/__init__.py` |
| **FormatType enum** | 17 values: `DOCX, PPTX, PDF, XLSX, ODT, CSV, JSON, XML, HTML, EPUB, EMAIL, IMAGE, AUDIO, VIDEO, IPYNB, YOUTUBE, UNKNOWN` |
| **Each extractor** | Extends `ExtractorBase` with `extract()`, `validate_file()`, `get_file_info()`, `supported_extensions()` |
| **Pipeline mapping** | `OPPPipeline.extractors` dict maps each `FormatType` to its extractor instance |

### F02 — Auto-detect format via magic bytes

| Aspect | Specification |
|--------|---------------|
| **Primary detection** | Reads first 8 bytes of file — no extension dependency |
| **PK (ZIP) disambiguation** | `_disambiguate_zip_format()` inspects ZIP contents: `word/document.xml` → DOCX, `ppt/presentation.xml` → PPTX, `xl/workbook.xml` → XLSX, `META-INF/container.xml` → EPUB/ODT |
| **PDF** | `%PDF` header → PDF confidence 1.0; extension-only `.pdf` → 0.5 |
| **JSON** | First byte `{` or `[` or UTF-8 BOM + `{`/`[` |
| **XML** | `<?xml` header (case-insensitive) |
| **HTML** | `<!DOCTYPE html>` or `<html` tag in first 1024 bytes |
| **YouTube `.url`** | Reads first line, matches YouTube URL regex |
| **YouTube URL string** | Regex match passed directly as path |
| **IPYNB** | Extension check BEFORE JSON (IPYNB is valid JSON but handled separately) |
| **Confidence score** | Returns `(FormatType, confidence: float)` tuple — 1.0 = magic bytes match, 0.5–0.9 = extension heuristic |

### F03 — Output clean, valid Markdown with YAML frontmatter

| Aspect | Specification |
|--------|---------------|
| **MD generation** | `MarkdownGenerator` via `OPPPipeline.generate_markdown()` |
| **Frontmatter** | YAML with `source_lang`, `target_lang`, `source_file`, `extracted_at` |
| **Structure preservation** | Paragraphs separated by double newlines; tables rendered as Markdown tables; lists preserved |
| **Image references** | Base64-embedded inline images or `![alt](path)` references depending on `--no-embed-images` flag |
| **Orphan images** | Images without paragraph anchor → trailing `## Images` section (E2E-15 behavior) |

### F04 — Output valid XLIFF 1.2/2.0 with `<bx>`/`<ex>` inline tags

| Aspect | Specification |
|--------|---------------|
| **XLIFF generation** | `XLIFFFileGenerator` in `opp/xliff/generator.py` |
| **Versions** | Supports XLIFF 1.2 and 2.0 |
| **Inline formatting** | Bold/italic/underline/strikethrough preserved as `<bx>`/`<ex>` / `<it>` tags per XLIFF spec |
| **Trans-units** | Each `<trans-unit>` maps to one source paragraph; `source_lang`/`target_lang` in `<file>` element |
| **Validation** | `validate_xliff` MCP tool validates schema + trans-unit content rules (non-empty source, unique IDs, valid lang codes) |
| **PDF guard** | `generate_xliff` raises `ValueError` on PDF input (intentionally blocked) |

### F05 — Produce skeleton.zip for DOCX/PPTX/EPUB

| Aspect | Specification |
|--------|---------------|
| **Skeleton content** | Preserves original ZIP structure: DOCX → `word/`, `[Content_Types].xml`; PPTX → `ppt/slides/`, `ppt/media/`; EPUB → `OEBPS/`, `META-INF/` |
| **Produced alongside** | XLIFF output (CLI `--target-format xlf`/`both`) and MCP `extract_document`/`save_skeleton` |
| **File naming** | `<stem>.skeleton.zip` in output directory |
| **Consumed by** | ORF `apply-xliff` for layout-faithful backfill |
| **Not produced for** | PDF, HTML, CSV, JSON, XML, EML, MSG, images, YouTube |

### F06 — Handle images correctly — inline, floating, dedup

| Aspect | Specification |
|--------|---------------|
| **Dedup** | `ResourceManager` uses MD5 hash + UUID naming to avoid duplicate image storage |
| **Inline images** | `ImageData.element_index` set → injected into MD paragraph by `MarkdownGenerator._escape_inline()` |
| **Floating images** | `ImageData.is_floating=True` with `wp_anchor_h`/`wp_anchor_v` (EMU units) for ORF `<wp:anchor>` rebuild |
| **HTML images** | `is_inline_in_md=True` for every HTML image (markdownify already embedded the reference); `MarkdownGenerator` skips double-embed (E2E-75) |
| **DOCX drawings** | `paragraph_index` for anchored drawings → preserved in skeleton.zip |
| **Image manifest** | `images.json` lists all images with MIME type, dimensions, position data |

### F07 — OCR from images (Tesseract + RapidOCR)

| Aspect | Specification |
|--------|---------------|
| **Engine** | `ImageOCRExtractor` supports Tesseract and RapidOCR |
| **Fallback** | If one engine fails, the other is tried (graceful degradation) |
| **Language** | Configurable via `OPP_OCR_LANG` env var (default: `eng`; supports `chi_sim`, `jpn`, `fra`, etc.) |
| **CLI flag** | `--ocr-engine tesseract|rapidocr` and `--ocr-lang <code>` |
| **MCP param** | `ocr_lang` parameter on `extract_document` tool |

### F08 — Email extraction (EML + MSG with attachment recursion)

| Aspect | Specification |
|--------|---------------|
| **EML** | RFC 822 via Python `email` stdlib |
| **MSG** | Outlook `.msg` format support |
| **Attachment recursion** | Attachments of supported types are also extracted (recursive into `AttachmentHandler`) |
| **Headers preserved** | From, To, Subject, Date, CC extracted as metadata |

### F09 — MCP server with 9 tools, path security, rate limiting

| Aspect | Specification |
|--------|---------------|
| **Total tools** | **9** (extract_document, batch_extract, detect_format_tool, generate_markdown, generate_xliff, save_skeleton, ping, validate_xliff, get_capabilities) |
| **PathValidator** | Enforces: directory allowlist, no symlink escape, no traversal (`..`), extension whitelist, blocked extension blacklist (`.exe .bat .sh .ps1 .vbs .js`), file size ≤ 100 MB |
| **Rate limiter** | Token bucket per tool; configured via `OMNI_RATE_LIMIT_RPM` (default: 60) and `OMNI_RATE_LIMIT_BURST` (default: 10) |
| **Auth** | Optional shared-secret via `MCP_SHARED_SECRET` env var; `auth_token` parameter on every tool |
| **Error boundary** | `@mcp_error_boundary` decorator on all tools — no internal traceback leaks to client |
| **Tracing** | W3C Trace Context `traceparent` propagation on `extract_document` |

### F10 — Error resilience

| Aspect | Specification |
|--------|---------------|
| **Bad files** | Extraction failure returns error dict — never crashes the MCP server or CLI |
| **Missing format** | `detect_format` returns `(UNKNOWN, 0.0)` — agent gets actionable `OPP_UNKNOWN_FORMAT` error |
| **Empty output** | Each extractor must produce at least some content or a warning; silent empty output is a bug |
| **Timeout** | Per-tool timeout configurable via `OPP_MCP_TIMEOUT` (default: 300s) |

### F11 — PDF→XLIFF intentionally blocked

| Aspect | Specification |
|--------|---------------|
| **Guard** | `generate_xliff` tool raises `ValueError` for PDF input; CLI `--target-format xlf`/`both` on PDF returns actionable error |
| **Why** | PDF structure is too lossy for clean XLIFF `<trans-unit>` extraction |
| **Workaround** | Extract PDF→MD, then translate MD directly (OL `translate-md`) |

### F12 — Batch processing

| Aspect | Specification |
|--------|---------------|
| **CLI** | `opp --batch file1.docx file2.pdf file3.pptx` or `opp folder/` (directory expansion) |
| **MCP** | `batch_extract` tool accepts `file_paths` array, returns per-file results + aggregate counts |
| **Isolation** | One file failing does not prevent others from processing |

## 4. Quality Gates

| Gate | Check | Failure mode |
|------|-------|-------------|
| **G1** | Every format extractor produces at least some content | Empty output → warning in manifest, flagged for agent review |
| **G2** | MD content preserves paragraph structure, tables, lists | Structural corruption detected via roundtrip comparison |
| **G3** | XLIFF `<trans-unit>` count matches source paragraph count | Misaligned trans-units cause OL translation errors |
| **G4** | Image count in output ≤ image count in source | Phantom images (double-embed) flagged; dedup count mismatch |
| **G5** | skeleton.zip roundtrip (save → extract → verify internal structure) | Missing key files → ORF `apply-xliff` will fail |

## 5. Value Proposition

OPP is the **first step** in the Omni Suite pipeline. Every downstream module depends on OPP output quality:

```
  OPP ──→ OL ──→ ORF
  │              │
  │              └── Bad skeleton → incorrect DOCX/PPTX backfill
  │
  ├── Bad MD → OL translates garbage → ORF produces garbage output
  ├── Lost images → ORF can't reinject → broken layout
  └── Bad XLIFF → OL skips units → ORF produces incomplete document
```

**Reliability is non-negotiable.** If OPP silently drops content, misformats XLIFF, or produces empty output, the entire pipeline produces unusable results. The file format landscape is messy (encrypted PDFs, malformed DOCX, CSV encoding issues) — OPP must handle all of it without crashing.

---

# Part 2 — Agent Validation Master Plan

## Verdict Legend

| Symbol | Meaning |
|--------|---------|
| ✅ PASS | All scenarios match expected results |
| ❌ FAIL | One or more scenarios did NOT match |
| ⚠️ PARTIAL | Some pass, some fail |
| ➖ SKIP | Intentionally skipped (reason documented) |

## Prerequisites

```bash
# Set environment for safe testing
export OMNI_TEST_FAKE_LLM=1
export OPP_MCP_ALLOWED_DIRS="/tmp/opp_test,/tmp/output"
mkdir -p /tmp/opp_test /tmp/output

# Verify CLI works
opp --help

# Verify MCP imports
python3 -c "from opp.mcp.server import server; print('MCP server OK')"

# Run existing test suite
cd /mnt/d/贯维/Omni_Suite/Omni_Pre_Processor
uv run pytest tests/ -v --tb=short 2>&1 | tail -20
```

---

## Q1-OPP: Does OPP detect every supported format correctly?

**User says:** "I have a file with no extension. What format is it?"

**Why this matters:** F02 — detection must work by content, not extension.

### Prerequisites
```bash
mkdir -p /tmp/opp_test && cd /tmp/opp_test
```

### Scenarios

#### 1.1 🟢 DOCX detected by magic bytes
```bash
# Create a minimal DOCX and strip extension
cp sample.docx /tmp/opp_test/naked_file
opp --detect-format /tmp/opp_test/naked_file -v
```
**Expected Result:** ✅ Detected format is `DOCX`, confidence ≥ 0.9

**Actual Result:** _____ **PASS / FAIL:** _____

#### 1.2 🟢 PDF detected by `%PDF` header
```bash
opp --detect-format sample.pdf
```
**Expected Result:** ✅ Format `PDF`, confidence 1.0

**Actual Result:** _____ **PASS / FAIL:** _____

#### 1.3 🟢 JSON detected by first byte `{`
```bash
echo '{"key": "value"}' > /tmp/opp_test/test.json
opp --detect-format /tmp/opp_test/test.json
```
**Expected Result:** ✅ Format `JSON`, confidence 1.0

**Actual Result:** _____ **PASS / FAIL:** _____

#### 1.4 🟢 YouTube `.url` detected
```bash
echo "URL=https://www.youtube.com/watch?v=dQw4w9WgXcQ" > /tmp/opp_test/video.url
opp --detect-format /tmp/opp_test/video.url
```
**Expected Result:** ✅ Format `YOUTUBE`, confidence 1.0

**Actual Result:** _____ **PASS / FAIL:** _____

#### 1.5 🔴 Unknown format returns UNKNOWN
```bash
echo "not a file format" > /tmp/opp_test/unknown.bin
opp --detect-format /tmp/opp_test/unknown.bin
```
**Expected Result:** ❌ Format `UNKNOWN`, confidence 0.0

**Actual Result:** _____ **PASS / FAIL:** _____

### 📊 Q1-OPP Verdict

| Scenario | Result |
|----------|--------|
| 1.1 DOCX magic bytes | ⬜ |
| 1.2 PDF header | ⬜ |
| 1.3 JSON first byte | ⬜ |
| 1.4 YouTube `.url` | ⬜ |
| 1.5 Unknown format | ⬜ |
| **OVERALL** | ⬜ |

---

## Q2-OPP: Does OPP extract DOCX to valid MD + XLIFF + skeleton?

**User says:** "Extract this Word document for translation."

**Why this matters:** DOCX is the most common input format — F01, F03, F04, F05.

### Prerequisites
```bash
mkdir -p /tmp/opp_test/docx_test
```

### Scenarios

#### 2.1 🟢 DOCX → MD + XLIFF + skeleton (target-format both)
```bash
opp /path/to/sample.docx --target-format both --source-lang en --target-lang zh --output-dir /tmp/opp_test/docx_test -v
```
**Expected Result:** ✅ Exit 0. Output files: `sample.md`, `sample.xlf`, `sample_manifest.json`, `sample.skeleton.zip`

**Actual Result:** _____ **PASS / FAIL:** _____

#### 2.2 🟢 MD has YAML frontmatter
```bash
head -10 /tmp/opp_test/docx_test/sample.md
```
**Expected Result:** ✅ Starts with `---`, contains `source_lang: en`, `target_lang: zh`, `source_file`

**Actual Result:** _____ **PASS / FAIL:** _____

#### 2.3 🟢 XLIFF has `<trans-unit>` elements with source lang
```bash
grep -c '<trans-unit' /tmp/opp_test/docx_test/sample.xlf
```
**Expected Result:** ✅ At least 1 trans-unit. `source_language="en"` in `<file>` element.

**Actual Result:** _____ **PASS / FAIL:** _____

#### 2.4 🟢 skeleton.zip contains DOCX key files
```bash
unzip -l /tmp/opp_test/docx_test/sample.skeleton.zip | grep -E "word/document\.xml|\[Content_Types\]\.xml"
```
**Expected Result:** ✅ `word/document.xml` and `[Content_Types].xml` present.

**Actual Result:** _____ **PASS / FAIL:** _____

### 📊 Q2-OPP Verdict

| Scenario | Result |
|----------|--------|
| 2.1 DOCX → MD+XLIFF+skeleton | ⬜ |
| 2.2 MD frontmatter | ⬜ |
| 2.3 XLIFF trans-units | ⬜ |
| 2.4 skeleton key files | ⬜ |
| **OVERALL** | ⬜ |

---

## Q3-OPP: Does OPP extract PPTX to valid MD + XLIFF + skeleton?

**User says:** "Extract this PowerPoint deck."

**Why this matters:** PPTX is #2 most common input — large slides, images, text boxes.

### Scenarios

#### 3.1 🟢 PPTX → MD + XLIFF + skeleton
```bash
opp /path/to/sample.pptx --target-format both --source-lang en --target-lang zh --output-dir /tmp/opp_test/pptx_test
```
**Expected Result:** ✅ Exit 0. `sample.md`, `sample.xlf`, `sample.skeleton.zip` created.

**Actual Result:** _____ **PASS / FAIL:** _____

#### 3.2 🟢 skeleton.zip has `ppt/` prefix files
```bash
unzip -l /tmp/opp_test/pptx_test/sample.skeleton.zip | grep "ppt/slides/"
```
**Expected Result:** ✅ `ppt/slides/slide1.xml` and `ppt/media/` present.

**Actual Result:** _____ **PASS / FAIL:** _____

### 📊 Q3-OPP Verdict

| Scenario | Result |
|----------|--------|
| 3.1 PPTX extraction | ⬜ |
| 3.2 PPTX skeleton | ⬜ |
| **OVERALL** | ⬜ |

---

## Q4-OPP: Does OPP extract PDF to MD (and block PDF→XLIFF)?

**User says:** "Extract this PDF — I need the text, and I want to try XLIFF too."

**Why this matters:** F11 — PDF→MD works, PDF→XLIFF must fail with clear message.

### Scenarios

#### 4.1 🟢 PDF → MD succeeds
```bash
opp /path/to/sample.pdf --target-format md --output-dir /tmp/opp_test/pdf_test
```
**Expected Result:** ✅ Exit 0. `sample.md` created with extracted text content.

**Actual Result:** _____ **PASS / FAIL:** _____

#### 4.2 🔴 PDF → XLIFF blocked
```bash
opp /path/to/sample.pdf --target-format xlf --source-lang en --target-lang zh --output-dir /tmp/opp_test/pdf_xlf_test
```
**Expected Result:** ❌ Exit code != 0. Error message: "PDF to XLIFF is not supported" or similar.

**Actual Result:** _____ **PASS / FAIL:** _____

#### 4.3 🔴 PDF → both also blocks XLIFF (MD still works)
```bash
opp /path/to/sample.pdf --target-format both --source-lang en --target-lang zh --output-dir /tmp/opp_test/pdf_both_test
```
**Expected Result:** ⚠️ MD file created, but XLIFF generation fails with clear error. Exit may be 0 or non-zero depending on implementation — but XLIFF file must not exist.

**Actual Result:** _____ **PASS / FAIL:** _____

### 📊 Q4-OPP Verdict

| Scenario | Result |
|----------|--------|
| 4.1 PDF→MD | ⬜ |
| 4.2 PDF→XLIFF blocked | ⬜ |
| 4.3 PDF→both partial | ⬜ |
| **OVERALL** | ⬜ |

---

## Q5-OPP: Does OPP extract image files via OCR?

**User says:** "Scan this image for text."

**Why this matters:** F07 — OCR is a key differentiator for scanned documents.

### Prerequisites
```bash
# Ensure Tesseract is installed
which tesseract || apt-get install -y tesseract-ocr
```

### Scenarios

#### 5.1 🟢 OCR with Tesseract
```bash
opp /path/to/scanned.png --ocr-engine tesseract --output-dir /tmp/opp_test/ocr_test
```
**Expected Result:** ✅ `scanned.md` created with OCR-extracted text. Non-empty content.

**Actual Result:** _____ **PASS / FAIL:** _____

#### 5.2 🟢 OCR with specified language
```bash
export OPP_OCR_LANG=eng
opp /path/to/scanned.png --ocr-engine tesseract --ocr-lang eng --output-dir /tmp/opp_test/ocr_lang_test
```
**Expected Result:** ✅ Text extracted with specified language model.

**Actual Result:** _____ **PASS / FAIL:** _____

### 📊 Q5-OPP Verdict

| Scenario | Result |
|----------|--------|
| 5.1 Tesseract OCR | ⬜ |
| 5.2 OCR language | ⬜ |
| **OVERALL** | ⬜ |

---

## Q6-OPP: Does OPP handle edge cases gracefully?

**User says:** "What happens if my file is corrupt or the wrong format?"

**Why this matters:** F10 — pipeline must never crash on bad input.

### Scenarios

#### 6.1 🔴 Corrupt file
```bash
echo "corrupt data" > /tmp/opp_test/corrupt.docx
opp /tmp/opp_test/corrupt.docx --target-format md --output-dir /tmp/opp_test/corrupt_test
```
**Expected Result:** ❌ Exit code != 0. Error message about invalid/corrupt file, no traceback.

**Actual Result:** _____ **PASS / FAIL:** _____

#### 6.2 🔴 Empty file
```bash
touch /tmp/opp_test/empty.docx
opp /tmp/opp_test/empty.docx --target-format md --output-dir /tmp/opp_test/empty_test
```
**Expected Result:** ❌ Exit code != 0. Friendly error message.

**Actual Result:** _____ **PASS / FAIL:** _____

#### 6.3 🔴 Unsupported format
```bash
opp /tmp/opp_test/unknown.bin --target-format md --output-dir /tmp/opp_test/unknown_test
```
**Expected Result:** ❌ Exit code != 0. Message: "Unsupported format" or "Format not supported".

**Actual Result:** _____ **PASS / FAIL:** _____

#### 6.4 🔴 Non-existent file
```bash
opp /tmp/opp_test/nonexistent.docx --target-format md
```
**Expected Result:** ❌ Exit code != 0. Error about file not found.

**Actual Result:** _____ **PASS / FAIL:** _____

### 📊 Q6-OPP Verdict

| Scenario | Result |
|----------|--------|
| 6.1 Corrupt file | ⬜ |
| 6.2 Empty file | ⬜ |
| 6.3 Unsupported format | ⬜ |
| 6.4 Non-existent file | ⬜ |
| **OVERALL** | ⬜ |

---

## Q7-OPP: Do all MCP tools work correctly?

**User says:** "I'm connecting via MCP. I need all 9 tools to work."

**Why this matters:** F09 — MCP is the primary agent interface.

### Prerequisites
```bash
cd /mnt/d/贯维/Omni_Suite/Omni_Pre_Processor
export OPP_MCP_ALLOWED_DIRS="/tmp/opp_test,/tmp/output"
```

### Scenarios

#### 7.1 🟢 ping returns version
```python
PYTHONPATH=src python3 -c "
from opp.mcp.tools.ping import ping
import asyncio
r = asyncio.run(ping())
print(r)
assert r.get('success'), f'FAIL: {r}'
print('✅ ping OK')
"
```
**Expected Result:** ✅ `{"success": true, "version": "0.9.1", "name": "opp-mcp"}` or similar.

**Actual Result:** _____ **PASS / FAIL:** _____

#### 7.2 🟢 detect_format_tool returns format
```python
PYTHONPATH=src python3 -c "
from opp.mcp.tools.detect_format import detect_format_tool
import asyncio
r = asyncio.run(detect_format_tool(file_path='/tmp/opp_test/sample.docx'))
print(r)
assert r.get('success'), f'FAIL: {r}'
print('✅ detect_format_tool OK')
"
```
**Expected Result:** ✅ Returns format name + confidence.

**Actual Result:** _____ **PASS / FAIL:** _____

#### 7.3 🟢 get_capabilities returns tool list
```python
PYTHONPATH=src python3 -c "
from opp.mcp.tools.get_capabilities import get_capabilities
import asyncio
r = asyncio.run(get_capabilities())
print(r)
assert r.get('success'), f'FAIL: {r}'
tools = r['content']['tools']
assert len(tools) >= 9, f'Expected ≥9 tools, got {len(tools)}'
print(f'✅ {len(tools)} tools: {tools}')
"
```
**Expected Result:** ✅ Returns module info, input formats list (≥16), output formats, tools list (≥9).

**Actual Result:** _____ **PASS / FAIL:** _____

#### 7.4 🟢 validate_xliff validates or rejects XLIFF
```python
PYTHONPATH=src python3 -c "
from opp.mcp.tools.validate_xliff import validate_xliff
import asyncio
# Test with invalid XLIFF
r = asyncio.run(validate_xliff(xliff_content='<invalid>'))
print(r)
assert not r.get('success') or r.get('content', {}).get('is_valid') == False
print('✅ validate_xliff rejects invalid content')
"
```
**Expected Result:** ✅ Returns validation result with `is_valid`, schema errors.

**Actual Result:** _____ **PASS / FAIL:** _____

#### 7.5 🟢 extract_document returns md_content
```python
PYTHONPATH=src python3 -c "
from opp.mcp.tools.extract_document import extract_document
import asyncio
r = asyncio.run(extract_document(
    file_path='/tmp/opp_test/sample.docx',
    output_formats='md'
))
print(f'success={r.get(\"success\")}, has_md={\"md_content\" in r}')
assert r.get('success'), f'FAIL: {r}'
assert 'md_content' in r, 'No md_content in response'
print('✅ extract_document OK')
"
```
**Expected Result:** ✅ MD content returned, success=true.

**Actual Result:** _____ **PASS / FAIL:** _____

#### 7.6 🔴 Path security blocks unauthorized paths
```python
PYTHONPATH=src python3 -c "
from opp.mcp.tools.extract_document import extract_document
import asyncio
r = asyncio.run(extract_document(
    file_path='/etc/passwd',
    output_formats='md'
))
print(r)
assert not r.get('success'), 'Should have been blocked!'
assert 'OPP_PATH_DENIED' in str(r) or 'path' in str(r).lower()
print('✅ Path security blocked /etc/passwd')
"
```
**Expected Result:** ❌ Error code `OPP_PATH_DENIED`, path validation fails.

**Actual Result:** _____ **PASS / FAIL:** _____

#### 7.7 🔴 Unknown tool returns error
```python
from opp.mcp.server import _TOOL_DISPATCH
assert 'nonexistent_tool' not in _TOOL_DISPATCH
print('✅ Unknown tool correctly missing from dispatch')
```
**Expected Result:** ✅ Unknown tool name returns structured error, not crash.

**Actual Result:** _____ **PASS / FAIL:** _____

### 📊 Q7-OPP Verdict

| Scenario | Result |
|----------|--------|
| 7.1 ping | ⬜ |
| 7.2 detect_format_tool | ⬜ |
| 7.3 get_capabilities | ⬜ |
| 7.4 validate_xliff | ⬜ |
| 7.5 extract_document | ⬜ |
| 7.6 Path security block | ⬜ |
| 7.7 Unknown tool error | ⬜ |
| **OVERALL** | ⬜ |

---

## Q8-OPP: Does OPP MCP path security correctly block unauthorized paths?

**User says:** "Can I use OPP MCP to read files outside the allowed directory?"

**Why this matters:** F09 — security is fail-closed; unauthorized access must be impossible.

### Scenarios

#### 8.1 🔴 Path traversal attack
```python
PYTHONPATH=src python3 -c "
from opp.mcp.tools.detect_format import detect_format_tool
import asyncio
r = asyncio.run(detect_format_tool(
    file_path='/tmp/opp_test/../../etc/passwd'
))
print(r)
assert not r.get('success'), 'Path traversal should be blocked!'
print('✅ Path traversal blocked')
"
```
**Expected Result:** ❌ Blocked with path validation error.

**Actual Result:** _____ **PASS / FAIL:** _____

#### 8.2 🔴 Symlink escape
```bash
ln -s /etc/passwd /tmp/opp_test/evil_symlink
PYTHONPATH=src python3 -c "
from opp.mcp.tools.detect_format import detect_format_tool
import asyncio
r = asyncio.run(detect_format_tool(file_path='/tmp/opp_test/evil_symlink'))
print(r)
assert not r.get('success'), 'Symlink escape should be blocked!'
print('✅ Symlink escape blocked')
"
```
**Expected Result:** ❌ Blocked because symlink target is outside allowed dirs.

**Actual Result:** _____ **PASS / FAIL:** _____

#### 8.3 🟢 Allowed path succeeds
```python
PYTHONPATH=src python3 -c "
from opp.mcp.tools.detect_format import detect_format_tool
import asyncio
r = asyncio.run(detect_format_tool(file_path='/tmp/opp_test/sample.docx'))
print(r)
assert r.get('success'), f'Allowed path should succeed: {r}'
print('✅ Allowed path works')
"
```
**Expected Result:** ✅ Detection succeeds for path within allowed dirs.

**Actual Result:** _____ **PASS / FAIL:** _____

### 📊 Q8-OPP Verdict

| Scenario | Result |
|----------|--------|
| 8.1 Path traversal | ⬜ |
| 8.2 Symlink escape | ⬜ |
| 8.3 Allowed path works | ⬜ |
| **OVERALL** | ⬜ |

---

## Q9-OPP: Does OPP CLI work correctly?

**User says:** "I'm using the terminal. All CLI flags must work."

**Why this matters:** CLI is the fallback interface — must be reliable.

### Scenarios

#### 9.1 🟢 `opp --help` shows all options
```bash
opp --help
```
**Expected Result:** ✅ Shows usage, all flags (--target-format, --output-dir, --source-lang, etc.)

**Actual Result:** _____ **PASS / FAIL:** _____

#### 9.2 🟢 `opp --target-format md` produces .md only
```bash
opp /path/to/sample.docx --target-format md --output-dir /tmp/opp_test/cli_md
ls /tmp/opp_test/cli_md/
```
**Expected Result:** ✅ Only `sample.md` and `sample_manifest.json` — no `.xlf`, no `.skeleton.zip`

**Actual Result:** _____ **PASS / FAIL:** _____

#### 9.3 🟢 `opp --detect-format` works
```bash
opp --detect-format /path/to/sample.pdf
```
**Expected Result:** ✅ Prints detected format and confidence.

**Actual Result:** _____ **PASS / FAIL:** _____

#### 9.4 🔴 Missing `--target-lang` with XLIFF
```bash
opp /path/to/sample.docx --target-format xlf
```
**Expected Result:** ❌ Error: "--target-lang is required when --target-format is 'xlf' or 'both'"

**Actual Result:** _____ **PASS / FAIL:** _____

#### 9.5 🟢 `-v` verbose output
```bash
opp -v /path/to/sample.docx --target-format md --output-dir /tmp/opp_test/verbose
```
**Expected Result:** ✅ Verbose info prints to stderr (since v0.6.2). MD file still written to output dir.

**Actual Result:** _____ **PASS / FAIL:** _____

### 📊 Q9-OPP Verdict

| Scenario | Result |
|----------|--------|
| 9.1 --help | ⬜ |
| 9.2 --target-format md | ⬜ |
| 9.3 --detect-format | ⬜ |
| 9.4 Missing --target-lang | ⬜ |
| 9.5 -v verbose | ⬜ |
| **OVERALL** | ⬜ |

---

## Final Summary

| Q | Focus | Verdict |
|---|-------|---------|
| Q1 | Format detection (magic bytes + confidence) | ⬜ |
| Q2 | DOCX → MD + XLIFF + skeleton | ⬜ |
| Q3 | PPTX → MD + XLIFF + skeleton | ⬜ |
| Q4 | PDF → MD (XLIFF blocked) | ⬜ |
| Q5 | Image OCR | ⬜ |
| Q6 | Edge cases (corrupt/empty/unknown) | ⬜ |
| Q7 | MCP tools (9 tools) | ⬜ |
| Q8 | MCP path security | ⬜ |
| Q9 | CLI correctness | ⬜ |
| **OVERALL** | | **⬜** |

**Sign-off:** All 9 questions must show ✅ PASS for OPP v0.9.1 to be considered production-ready.
