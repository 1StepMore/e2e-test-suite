# Founder's Expectations + Agent Validation Master Plan — ORF

> **Omni Re-Formatter** · v0.4.17 — Stage 3 (final): backfill translated content into production-ready documents.

---

## Part 1 — Founder's Expectations

### 1.1 Why These Expectations?

ORF is the last mile. OPP extracts, OL translates — but if ORF can't produce a valid, openable DOCX/PPTX/EPUB, nothing matters. This defines "done" from the founder's perspective.

### 1.2 Design Principles

| Principle | Meaning |
|-----------|---------|
| **Format coverage** | 16 MD formats, 5 XLIFF formats. Missing formats = blockers. |
| **Layout preservation** | XLIFF path preserves styles, fonts, floating images, paragraphs. Output must look like input. |
| **Image fidelity** | Inline + floating images survive backfill. No dupes, no dropouts. |
| **Agent-native** | All capabilities exposed as MCP tools. CLI is fallback. |
| **Foreman/Specialist** | Complex jobs decompose intelligently; Foreman routes to specialists with error recovery. |
| **HITL for risk** | Files >100 MB, cloud uploads, manual_intervention recovery need human approval. |
| **Graceful degradation** | Missing pandoc → pure-Python fallback. Missing md2pptx → pandoc fallback. Both missing → actionable install hint. No tracebacks. |
| **Honest about gaps** | MSG requires Aspose. PDF→XLIFF blocked. Cross-format XLIFF needs `--force`. |

### 1.3 Expectation Catalog

#### F01 — MD → 16 output formats
| Aspect | Spec |
|--------|------|
| **Formats** | DOCX, ODT, EPUB, HTML, RTF, PDF, PPTX, ICML, SRT, CSV, XLSX, JSON, XML, IPYNB, EML, MSG |
| **CLI** | `orf apply-md <file> --target-format <fmt> -o <out>` |
| **MCP** | `apply_md(input_md=..., target_format=..., output_path=...)` |
| **Inline content** | `apply_md` also accepts `content` (text-in/text-out agent flow, E2E-76) |
| **Engines** | pandoc→DOCX/ODT/EPUB/RTF/ICML; `markdown`→HTML; weasyprint→PDF; md2pptx→PPTX; `srt`→SRT; pandas→CSV; openpyxl→XLSX; `json`→JSON; `nbformat`→IPYNB; `email`→EML; `aspose-email-foss`→MSG; `lxml`→XML |
| **Expected** | Every format produces a valid, openable file. |

#### F02 — XLIFF backfill preserves original layout
| Aspect | Spec |
|--------|------|
| **Formats** | DOCX, PPTX, EPUB, HTML, ODT |
| **CLI** | `orf apply-xliff <source> --xliff <xlf> --output <out>` |
| **MCP** | `apply_xliff(input_file=..., xliff_path=..., output_path=..., format=...)` |
| **Skeleton** | Requires `skeleton.zip` from OPP (contains `word/document.xml`, styles, media, `[Content_Types].xml`) |
| **Expected** | Same page count, paragraph structure, styles as source. Only text changes. |

#### F03 — Image injection (inline + floating)
| Aspect | Spec |
|--------|------|
| **Inline** | `wp:inline` — flows with paragraph text via `images.json` placement. |
| **Floating** | `wp:anchor` — absolute-positioned. ORF reads `is_floating=true`, `wp_anchor_h/v`, `wp_anchor_relative_h/v` from `images.json`, emits `<w:drawing><wp:anchor>` with `positionH/positionV/wrapNone`. |
| **MD path** | `--separate-images` (default) extracts to `images.json`+`images.zip`. `--embed-images` base64-inlines (DOCX/HTML/EPUB only). |
| **XLIFF path** | Auto-reinjected from skeleton media; `images.json` overlay adds new images. |
| **Expected** | All source images appear. Floating images maintain absolute position. No corrupt blocks. |

#### F04 — Image dedup prevents duplicate injection
| Aspect | Spec |
|--------|------|
| **Problem** | Without dedup, ORF re-injects inline duplicates (Haier DOCX: 13 `<w:drawing>` instead of 11). |
| **Fix** | Document-wide `<wp:extent>` cx/cy match (not paragraph-local — OPP's `paragraph_index` is off-by-one vs ORF's `//w:p` enumeration). |
| **Guard** | `tests/turnkey/test_image_fidelity.py::test_drawing_count_equals_source` |
| **Expected** | Output `<w:drawing>` count equals source count. No duplicate images. |

#### F05 — Cross-format XLIFF via --force
| Aspect | Spec |
|--------|------|
| **Scenario** | DOCX XLIFF → backfill to PPTX (different format) |
| **CLI** | `orf apply-xliff source.docx --xliff translated.xlf --output out.pptx --force --format pptx` |
| **Behavior** | Prints "Warning: skeleton format (docx) differs from target (pptx)" then proceeds. Layout is best-effort. |
| **Expected** | Translation text appears. WARNING printed. Some layout fidelity lost (expected). |

#### F06 — MCP server (7 tools + PathValidator)
| Aspect | Spec |
|--------|------|
| **Tools** | `apply_md`, `apply_xliff`, `batch_convert`, `detect_format`, `info`, `ping`, `get_capabilities` |
| **Transport** | stdio via `mcp` v1.27.2. Optional `MCP_SHARED_SECRET` auth. |
| **PathValidator** | Allowlist (`ORF_MCP_ALLOWED_DIRS`), blocked exts (`.exe .bat .sh .ps1`), allowed exts (`.md .docx .pptx .xliff .xlf .xml .html .odt .epub .zip .csv .tsv .xlsx .json .ipynb .eml .msg .srt .icml .rtf .pdf`), symlink containment, file ≤ 100 MB. |
| **Rate limit** | Token bucket: `OMNI_RATE_LIMIT_RPM` (60), `OMNI_RATE_LIMIT_BURST` (10). |
| **Expected** | All 7 tools respond. Paths outside allowlist rejected with clear error. |

#### F07 — Foreman/Specialist orchestration
| Aspect | Spec |
|--------|------|
| **ForemanAgent** | Receives `JobRequest`, assesses complexity (SIMPLE/MODERATE/COMPLEX), routes to specialist, aggregates results. |
| **Specialists** | `FormatSpecialist` (DOCX/ODT/EPUB/PPTX/RTF/PDF/ICML/SRT), `DataSpecialist` (XLSX/CSV/JSON/IPYNB), `MarkupSpecialist` (XML/HTML), `EmailSpecialist` (EML/MSG) |
| **Error recovery** | `NOT_FOUND`/`MISSING`→ABORT; `INVALID`/`MALFORMED`→SKIP; `TIMEOUT`/`NETWORK`→RETRY; `SKELETON`→MANUAL_INTERVENTION; default→FALLBACK |
| **Expected** | `ForemanAgent().run('docs/', target_format='docx')` processes all `.md` files and produces valid DOCX. |

#### F08 — HITL approval
| Aspect | Spec |
|--------|------|
| **Triggers** | File > 100 MB → HIGH; Cloud upload → HIGH; `MANUAL_INTERVENTION` → LIMITED; File > 500 MB → UNACCEPTABLE |
| **Behavior** | Without notification channel: auto-approves with audit log entry. Real integration blocks. |
| **Expected** | `HITLApproval().needs_approval(op)` returns `True` for > 100 MB. Audit log records decision. |

#### F09 — Error recovery
| Aspect | Spec |
|--------|------|
| **Strategies** | RETRY, SKIP, FALLBACK, ABORT, PARTIAL, MANUAL_INTERVENTION |
| **Fallback chain** | MD→PPTX: try md2pptx → if missing, try pandoc → if both missing, actionable install hint. |
| **Error types** | `SkeletonNotFoundError`, `XLIFFParseError`, `ManifestParseError`, `FormatDetectionError`, `ResourceManagementError` |
| **Expected** | Missing dep → FALLBACK or clear install instruction. No tracebacks. |

#### F10 — Batch conversion
| Aspect | Spec |
|--------|------|
| **CLI** | `orf convert-batch <dir> --target-format <fmt> --pattern '*.md'` |
| **MCP** | `batch_convert(input_dir=..., target_format=..., pattern="*.md")` |
| **Expected** | 5 `.md` files → 5 outputs in one command. One failure doesn't stop the batch. |

#### F11 — Engine fallback chain
| Aspect | Spec |
|--------|------|
| **pandoc** | DOCX, ODT, EPUB, RTF, ICML via `pypandoc-binary` |
| **Pure Python** | HTML (`markdown`), PDF (weasyprint), CSV (pandas), XLSX (openpyxl), JSON (stdlib), IPYNB (nbformat), EML (stdlib), SRT (`srt`), XML (`lxml`) |
| **md2pptx** | .NET CLI. Pre-flight `shutil.which('md2pptx')`. Falls back to pandoc. Both missing → install hint. |
| **FAKE_PANDOC** | `OMNI_TEST_FAKE_PANDOC=1` bypasses pandoc → `python-docx` fallback. |
| **Expected** | `OMNI_TEST_FAKE_PANDOC=1 orf apply-md test.md --target-format docx` produces valid DOCX without pandoc. |

#### F12 — MSG recommends .eml
| Aspect | Spec |
|--------|------|
| **Dep** | Requires `aspose-email-foss` (`pip install 'omni-re-formatter[email-output]'`), GPLv3 fork of commercial Aspose.Email. |
| **Recommendation** | Use `.eml` (open standard, fully supported) — no commercial dependency. |
| **Expected** | MSG without dep → clear error: "MSG requires aspose-email-foss. Use --target-format eml for the open standard." Not ImportError traceback. |

### 1.4 Quality Gates

| Gate | Check | Failure | Pri |
|------|-------|---------|-----|
| **G1: Output valid** | File opens in native app (Word/Acrobat/Reader) | Return corrupt-output error | 🔴 P0 |
| **G2: No content loss** | ¶ count in output ≥ input | Log paragraph diff warning | 🔴 P0 |
| **G3: Image count match** | Output image count = OPP manifest | Log image diff warning | 🔴 P0 |
| **G4: XLIFF page count** | Output page count = source page count | Log page diff warning | 🟡 P1 |
| **G5: Cross-format text** | All translated segments preserved in cross-format | Log missing segment warning | 🟡 P1 |

### 1.5 Value Proposition

**ORF is the final step that makes the entire pipeline worthwhile.** Without ORF: translated text in an intermediate format. With ORF: production-ready document you can email, publish, or print.

**Success looks like:** Contract opens in Word looking identical to original (XLIFF). Manual renders on Kindle (MD). Presentation opens in PowerPoint with all images (XLIFF). Agent does it all via 3 MCP calls. Missing dep → tells you exactly what to install.

---

## Part 2 — Agent Validation Master Plan

> For any AI agent validating ORF. Each section asks a question → executes scenarios → reports binary verdict.

| Symbol | Meaning |
|--------|---------|
| ✅ PASS | All scenarios match |
| ❌ FAIL | One+ scenarios failed |
| ⚠️ PARTIAL | Some pass, some fail |
| ➖ SKIP | Intentional skip |

---

### Q1-ORF: MD → all 16 output formats?

**User:** "Give me a real document from my markdown." · **Why:** Primary path for 90% of users.

```bash
cd /tmp && mkdir -p orf-test && cd orf-test
cat > hello.md << 'EOF'
# Hello World
**bold** and *italic*.
- Item 1
- Item 2
| A | B |
EOF
```

#### 1.1 DOCX `orf apply-md hello.md --target-format docx -o hello.docx`
**Expected:** ✅ Exit 0. File > 1 KB. `file hello.docx` reports "Microsoft Word".

#### 1.2 HTML `orf apply-md hello.md --target-format html -o hello.html`
**Expected:** ✅ Contains `<h1>Hello World</h1>` and `<strong>bold</strong>`.

#### 1.3 PDF `orf apply-md hello.md --target-format pdf -o hello.pdf`
**Expected:** ✅ `file hello.pdf` reports "PDF document".

#### 1.4 CSV/JSON/XML/EPUB `orf apply-md hello.md --target-format csv|json|xml|epub -o hello.<fmt>`
**Expected:** ✅ Exit 0 each. Files valid per format.

#### 1.5 PPTX `orf apply-md hello.md --target-format pptx -o hello.pptx`
**Expected:** ✅ Exit 0. Pandoc fallback if md2pptx missing.

#### 1.6 EML `orf apply-md hello.md --target-format eml -o hello.eml`
**Expected:** ✅ Contains `Content-Type:` header.

#### 1.7 Inline content MCP
```python
import json; from orf.mcp.tools import apply_md
r = json.loads(apply_md(content="# Inline", target_format="html"))
assert r.get("success")
```
**Expected:** ✅ `success: true`, rendered HTML from inline string.

| 1.1 DOCX | 1.2 HTML | 1.3 PDF | 1.4 Data | 1.5 PPTX | 1.6 EML | 1.7 Inline |
|----------|----------|---------|----------|----------|---------|------------|
| ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

**OVERALL: ⬜**

---

### Q2-ORF: XLIFF → DOCX backfill with skeleton?

**User:** "I need the output to look exactly like the original." · **Why:** Layout-faithful translation depends on this.

```bash
cd /tmp && rm -rf orf-xlf && mkdir orf-xlf && cd orf-xlf
python3 -c "from docx import Document; d=Document(); d.add_paragraph('Original text'); d.save('source.docx')"
# Create skeleton.zip from source.docx
python3 -c "
import zipfile, os, shutil
os.makedirs('skel', exist_ok=True)
with zipfile.ZipFile('source.docx') as z:
    for n in z.namelist():
        os.makedirs(os.path.dirname(f'skel/{n}'), exist_ok=True)
        open(f'skel/{n}','wb').write(z.read(n))
with zipfile.ZipFile('skeleton.zip','w',zipfile.ZIP_DEFLATED) as z:
    for r,_,fs in os.walk('skel'):
        for f in fs: z.write(os.path.join(r,f), os.path.relpath(os.path.join(r,f),'skel'))
shutil.rmtree('skel')
"
cat > translated.xlf << 'XEOF'
<?xml version="1.0" encoding="utf-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file source-language="en" target-language="zh" datatype="plaintext">
    <body><trans-unit id="1">
      <source>Original text</source>
      <target>翻译后的文本</target>
    </trans-unit></body>
  </file>
</xliff>
XEOF
```

#### 2.1 🟢 Happy path `orf apply-xliff source.docx --xliff translated.xlf --output result.docx`
**Expected:** ✅ Exit 0. `result.docx` shows "翻译后的文本" with layout matching `source.docx`.

#### 2.2 🔴 Missing skeleton `orf apply-xliff source.docx --xliff translated.xlf --output result.docx` (no skeleton.zip)
**Expected:** ❌ Exit != 0. Error about missing skeleton. Not a traceback.

| 2.1 Happy path | 2.2 Missing skeleton |
|----------------|---------------------|
| ⬜ | ⬜ |

**OVERALL: ⬜**

---

### Q3-ORF: XLIFF → PPTX backfill?

**User:** "Translated PowerPoint — slides must keep layout." · **Why:** PPTX is core enterprise format.

```bash
cd /tmp && rm -rf orf-pptx && mkdir orf-pptx && cd orf-pptx
python3 -c "from pptx import Presentation; p=Presentation(); s=p.slides.add_slide(p.slide_layouts[6]); s.shapes.title.text='Original'; p.save('source.pptx')"
```

#### 3.1 🟢 PPTX backfill `orf apply-xliff source.pptx --xliff translated.xlf --output result.pptx`
**Expected:** ✅ Exit 0. Opens in PowerPoint/LibreOffice with translated text.

| 3.1 PPTX |
|----------|
| ⬜ |

**OVERALL: ⬜**

---

### Q4-ORF: Image injection (inline + floating)?

**User:** "My doc has inline and floating images. Both must appear." · **Why:** Image loss blocks real documents.

#### 4.1 🟢 Floating → `wp:anchor`
```python
from orf.resources import ImagePlacement
ip = ImagePlacement.from_dict({"id":"img1","src":"m.png","is_floating":True,"wp_anchor_h":100,"wp_anchor_v":200})
assert ip.is_floating
```
**Expected:** ✅ `is_floating=True` → produces `wp:anchor`.

#### 4.2 🟢 Inline → `wp:inline`
```python
ip = ImagePlacement.from_dict({"id":"img2","src":"m.png","is_floating":False})
assert not ip.is_floating
```
**Expected:** ✅ `is_floating=False` → produces `wp:inline`.

| 4.1 Floating | 4.2 Inline |
|--------------|------------|
| ⬜ | ⬜ |

**OVERALL: ⬜**

---

### Q5-ORF: Image dedup prevents double injection?

**User:** "Don't add duplicate images." · **Why:** E2E-07 regression. Without dedup, 13 `<w:drawing>` instead of 11.

#### 5.1 🟢 Regression guard `uv run pytest Omni_Re_Formatter/tests/turnkey/test_image_fidelity.py::test_drawing_count_equals_source -v`
**Expected:** ✅ PASSED. Drawing count equals source.

#### 5.2 🟢 Dedup cx/cy match
```python
from orf.resources import ImagePlacement
deduped = ImagePlacement.deduplicate([
    {"id":"a","cx":1000,"cy":500},{"id":"a2","cx":1000,"cy":500},{"id":"b","cx":2000,"cy":500}
])
assert len(deduped) == 2
```
**Expected:** ✅ Duplicate cx/cy pairs filtered. 3→2.

| 5.1 Regression guard | 5.2 Dedup logic |
|----------------------|-----------------|
| ⬜ | ⬜ |

**OVERALL: ⬜**

---

### Q6-ORF: Cross-format XLIFF (--force)?

**User:** "DOCX translation, but I need PPTX output." · **Why:** Enables workflows across formats.

#### 6.1 🟢 With --force `orf apply-xliff source.docx --xliff translated.xlf --output cross.pptx --format pptx --force`
**Expected:** ✅ Exit 0. Warning about format mismatch. File has translated text.

#### 6.2 🔴 Without --force `orf apply-xliff source.docx --xliff translated.xlf --output cross.pptx --format pptx`
**Expected:** ⚠️ Exit != 0 or warning. Cross-format blocked/warned without `--force`.

| 6.1 With --force | 6.2 Without --force |
|------------------|---------------------|
| ⬜ | ⬜ |

**OVERALL: ⬜**

---

### Q7-ORF: All 7 MCP tools respond?

**User:** "I'm connecting via MCP. All tools must work." · **Why:** MCP is the primary agent surface.

#### 7.1 `ping` `orf.mcp.tools.ping()`
**Expected:** ✅ `{"success": true, "version": "..."}`

#### 7.2 `get_capabilities` `orf.mcp.tools.get_capabilities()`
**Expected:** ✅ 16+ MD formats, 5+ XLIFF formats, 6+ tools listed.

#### 7.3 `detect_format` — create temp DOCX, detect
**Expected:** ✅ Detected format = `docx`.

#### 7.4 `info` — create temp DOCX, get info
**Expected:** ✅ Returns format, size, resource count.

#### 7.5 `batch_convert` — verify function signature
**Expected:** ✅ Params: `input_dir`, `target_format`, `pattern`.

| 7.1 ping | 7.2 capabilities | 7.3 detect | 7.4 info | 7.5 batch sig |
|----------|------------------|------------|----------|---------------|
| ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

**OVERALL: ⬜**

---

### Q8-ORF: MCP security blocks unauthorized paths?

**User:** "Don't let agents access my system files." · **Why:** Path traversal = security vulnerability.

```python
from orf.mcp.security import PathValidator
from pathlib import Path
v = PathValidator(allowed_directories=[Path("/tmp/safe")])
```

#### 8.1 `v.validate_path("/etc/passwd")` → **Expected:** ❌ Blocked.
#### 8.2 `v.validate_path("/tmp/safe/../../etc/passwd")` → **Expected:** ❌ Traversal blocked.
#### 8.3 `v.validate_path("/tmp/safe/virus.exe")` → **Expected:** ❌ .exe blocked.
#### 8.4 `v.validate_path("/tmp/safe/file.xyz")` → **Expected:** ❌ Unknown ext blocked.
#### 8.5 `v.validate_path("/tmp/safe/doc.docx", allow_missing=True)` → **Expected:** ✅ .docx allowed.

| 8.1 /etc | 8.2 Traversal | 8.3 .exe | 8.4 .xyz | 8.5 .docx |
|----------|---------------|----------|----------|-----------|
| ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

**OVERALL: ⬜**

---

### Q9-ORF: Foreman/Specialist orchestration?

**User:** "Route files to the right converter automatically." · **Why:** Manual routing is error-prone.

#### 9.1 Routing
```python
from orf.agents.foreman import ForemanAgent, JobRequest
f = ForemanAgent()
tests = {"docx":"format","pptx":"format","xlsx":"data","csv":"data","xml":"markup","html":"markup","eml":"email","msg":"email"}
for fmt,cat in tests.items():
    assert f.route_to_specialist(JobRequest(input_path=f"/tmp/x.{fmt}", target_format=fmt)) == cat
```
**Expected:** ✅ All formats route correctly.

#### 9.2 Complexity
```python
assert f.assess_complexity(JobRequest(input_path="/tmp/x.md", file_count=1, estimated_size_mb=10)).name == "SIMPLE"
assert f.assess_complexity(JobRequest(input_path="/tmp", is_batch=True, file_count=5)).name == "MODERATE"
assert f.assess_complexity(JobRequest(input_path="/tmp/x.docx", file_count=1, estimated_size_mb=100)).name == "COMPLEX"
```
**Expected:** ✅ SIMPLE/MODERATE/COMPLEX correct.

#### 9.3 Recovery strategies
```python
from orf.error_handlers.conversion_error import ErrorDetail, RecoveryStrategy
for code, exp in [("MISSING_SKELETON",RecoveryStrategy.ABORT),("INVALID_XLIFF",RecoveryStrategy.SKIP),
                  ("TIMEOUT_NETWORK",RecoveryStrategy.RETRY),("SKELETON_CORRUPT",RecoveryStrategy.MANUAL_INTERVENTION)]:
    assert f.handle_error(ErrorDetail(code=code, message="test")) == exp
```
**Expected:** ✅ Error codes map correctly.

| 9.1 Routing | 9.2 Complexity | 9.3 Recovery |
|-------------|----------------|--------------|
| ⬜ | ⬜ | ⬜ |

**OVERALL: ⬜**

---

### Q10-ORF: HITL for > 100 MB files?

**User:** "A 200 MB doc — get approval first." · **Why:** Large files can overwhelm memory.

```python
from orf.workflow.hitl_approval import HITLApproval, Operation
h = HITLApproval()
```

#### 10.1 `h.needs_approval(Operation("convert","/tmp/huge.docx",150.0))` → **Expected:** ✅ True.
#### 10.2 `h.needs_approval(Operation("convert","/tmp/small.docx",5.0))` → **Expected:** ✅ False.
#### 10.3 `h.needs_approval(Operation("upload","/tmp/out.docx",5.0,target="s3"))` → **Expected:** ✅ True.

| 10.1 > 100 MB | 10.2 < 100 MB | 10.3 Cloud |
|---------------|---------------|------------|
| ⬜ | ⬜ | ⬜ |

**OVERALL: ⬜**

---

### Q11-ORF: Missing deps — graceful errors?

**User:** "I don't have everything installed. What happens?" · **Why:** Graceful degradation is a principle.

#### 11.1 Missing md2pptx `orf apply-md hello.md --target-format pptx -o fallback.pptx`
**Expected:** ✅ If pandoc available: success. If both missing: "Install: dotnet tool install --global md2pptx".

#### 11.2 Missing pandoc `OMNI_TEST_FAKE_PANDOC=1 orf apply-md hello.md --target-format docx -o nopandoc.docx`
**Expected:** ✅ Exit 0. `python-docx` fallback. No traceback.

#### 11.3 Missing skeleton `orf apply-xliff missing.docx --xliff test.xlf --output out.docx`
**Expected:** ❌ Exit != 0. Error about missing file/skeleton. No traceback.

#### 11.4 MSG without aspose `orf apply-md hello.md --target-format msg -o hello.msg`
**Expected:** ❌ Error mentions aspose-email-foss, recommends --target-format eml. No ImportError traceback.

| 11.1 md2pptx | 11.2 pandoc | 11.3 skeleton | 11.4 MSG |
|--------------|-------------|---------------|----------|
| ⬜ | ⬜ | ⬜ | ⬜ |

**OVERALL: ⬜**

---

### Q12-ORF: Batch conversion?

**User:** "50 MD files → convert all at once." · **Why:** Batch is core productivity feature.

```bash
cd /tmp && rm -rf orf-batch && mkdir orf-batch && cd orf-batch
for i in 1 2 3; do echo "# Ch $i" > "ch$i.md"; done
```

#### 12.1 CLI `orf convert-batch /tmp/orf-batch --target-format epub --pattern "*.md" --json`
**Expected:** ✅ Exit 0. JSON lists 3 files. All .epub exist.

#### 12.2 MCP `orf.mcp.tools.batch_convert(input_dir="/tmp/orf-batch", target_format="docx", pattern="*.md")`
**Expected:** ✅ Success. All files converted.

| 12.1 CLI | 12.2 MCP |
|----------|----------|
| ⬜ | ⬜ |

**OVERALL: ⬜**

---

## Final Verdict

| Question | Result |
|----------|--------|
| Q1: MD → 16 formats | ⬜ |
| Q2: XLIFF → DOCX | ⬜ |
| Q3: XLIFF → PPTX | ⬜ |
| Q4: Image injection | ⬜ |
| Q5: Image dedup | ⬜ |
| Q6: Cross-format XLIFF | ⬜ |
| Q7: MCP 7 tools | ⬜ |
| Q8: MCP security | ⬜ |
| Q9: Foreman/Specialist | ⬜ |
| Q10: HITL approval | ⬜ |
| Q11: Error handling | ⬜ |
| Q12: Batch conversion | ⬜ |

**OVERALL: ⬜** (✅ all pass, ❌ any fail, ⚠️ partial)

### Sign-off

| Criterion | Status |
|-----------|--------|
| 16 MD formats produce valid files | ⬜ |
| XLIFF backfill layout-faithful | ⬜ |
| Image dedup guard passes (E2E-07) | ⬜ |
| All 7 MCP tools respond | ⬜ |
| Path security blocks unauthorized paths | ⬜ |
| Missing deps → actionable errors (not tracebacks) | ⬜ |
| Batch conversion works | ⬜ |
| Foreman routes & recovers | ⬜ |
| HITL triggers > 100 MB | ⬜ |
| Cross-format --force works with warning | ⬜ |
| MSG recommends .eml when dep missing | ⬜ |

---

*ORF v0.4.17 · 2026-07-22*
