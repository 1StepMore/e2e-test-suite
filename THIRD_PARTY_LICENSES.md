# Third-Party Licenses

> **Status**: baseline. Generated from `pyproject.toml` of all 3 modules.
> Re-run `python -c "import tomllib, pathlib; ..."` or `pip-licenses` after
> dependency updates. A future revision will auto-generate this file from
> `pip-licenses --format=markdown` in CI.

## 1. Direct runtime dependencies (3 modules combined)

The Omni Suite depends on the following third-party Python packages across
its three modules (OPP, OL, ORF). Licenses are sourced from the PyPI
metadata of each package at the time of writing.

### 1.1 OPP (`omni-pre-processor`) — core deps

| Package | Version | License | Notes |
|---------|---------|---------|-------|
| `beautifulsoup4` | ≥4.12.0 | MIT | HTML/XML parser |
| `chardet` | ≥5.0.0 | LGPL-2.1 | Encoding detection |
| `ebooklib` | ≥0.5.0 | AGPL-3.0 | EPUB reader/writer |
| `lxml` | ≥5.0.0 | BSD-3-Clause | XML/HTML parser |
| `openpyxl` | ≥3.1.5,<3.2 | MIT | XLSX reader/writer |
| `pandas` | ≥2.0.0 | BSD-3-Clause | DataFrame |
| `prometheus_client` | ≥0.20.0 | Apache-2.0 | Metrics |
| `pymupdf` | ≥1.27.0 | AGPL-3.0 | PDF rendering |
| `python-docx` | ≥1.0.0 | MIT | DOCX reader/writer |
| `python-json-logger` | ≥2.0.0 | BSD-2-Clause | JSON logging |
| `python-pptx` | ≥1.0.0 | MIT | PPTX reader/writer |
| `translate-toolkit` | ≥3.0.0 | GPL-2.0 | XLIFF / TM / QA |

### 1.2 OL (`omni-localizer`) — core deps

| Package | Version | License | Notes |
|---------|---------|---------|-------|
| `PyYAML` | ≥6.0.0 | MIT | YAML parser |
| `hypomnema` | ≥0.8 | MIT | Translation memory |
| `jinja2` | ≥3.1.0 | BSD-3-Clause | Templating |
| `keybert` | ≥0.9.0 | MIT | Keyword extraction |
| `litellm` | ≥1.82.0 | MIT | Multi-provider LLM router |
| `markdown-it-py` | ≥3.0.0 | MIT | Markdown parser |
| `openevalkit` | ≥0.1.7 | MIT | Translation evaluation |
| `prometheus_client` | ≥0.20.0 | Apache-2.0 | Metrics |
| `pybreaker` | ≥1.0.0 | MIT | Circuit breaker |
| `pydantic` | ≥2.0.0 | MIT | Data validation |
| `python-json-logger` | ≥2.0.0 | BSD-2-Clause | JSON logging |
| `rich` | ≥13.0.0 | MIT | Terminal formatting |
| `sacrebleu` | ≥2.0 | Apache-2.0 | BLEU scoring |
| `span-aligner` | ≥0.3.2 | MIT | Token alignment |
| `translate-toolkit` | ≥3.19.9 | GPL-2.0 | XLIFF / TM / QA |
| `typer` | ≥0.15.0 | MIT | CLI framework |
| `yake` | ≥0.5.0 | MIT | Keyword extraction |

### 1.3 ORF (`omni-re-formatter`) — core deps

| Package | Version | License | Notes |
|---------|---------|---------|-------|
| `anyio` | ≥4.0.0 | MIT | Async I/O |
| `beautifulsoup4` | ≥4.12.0 | MIT | HTML/XML parser |
| `click` | ≥8.1.0 | BSD-3-Clause | CLI framework |
| `lxml` | ≥5.0.0 | BSD-3-Clause | XML/HTML parser |
| `markdown` | ≥3.5 | BSD-3-Clause | Markdown → HTML |
| `mcp` | ≥1.0.0 | MIT | Model Context Protocol |
| `pydantic` | ≥2.0.0 | MIT | Data validation |
| `pypandoc-binary` | ≥1.17 | GPL-2.0 | Pandoc binary |
| `python-json-logger` | ≥2.0.0 | BSD-2-Clause | JSON logging |
| `python-magic` | ≥0.4.27 | MIT | File-type detection |
| `pyyaml` | ≥6.0 | MIT | YAML parser |
| `tqdm` | ≥4.66.0 | MPL-2.0 | Progress bar |

## 2. Optional dependency groups (extras)

| Module | Extra | Notable deps | License implications |
|--------|-------|--------------|----------------------|
| OPP | `[ocr]` | `rapidocr-onnxruntime` ≥1.3 | Apache-2.0 |
| OPP | `[youtube]` | `markitdown[youtube-transcription]` ≥0.0.1 | MIT |
| OPP | `[audio]` | `faster-whisper`, `torch` ≥2.0.0 | MIT + BSD-3-Clause |
| OPP | `[email]` | `extract-msg` ≥0.55.0 | Apache-2.0 (covers .msg reading) |
| OPP | `[notebook]` | `nbformat` ≥5.0.0 | BSD-3-Clause |
| OPP | `[office]` | `numpy` ≥2.0.0 | BSD-3-Clause |
| OPP | `[web]` | `docling`, `markdownify`, `readability-lxml` | MIT |
| OPP | `[mcp]` | `mcp` ≥1.0.0, `pyyaml` | MIT |
| OL | `[ml]` | `sentence-transformers` ≥3.0.0 | Apache-2.0 |
| ORF | `[weasyprint]` | `weasyprint` ≥60.0 | BSD-3-Clause |
| ORF | `[cloud]` | `boto3`, `azure-storage-blob` | Apache-2.0 / MIT |
| ORF | `[ai]` | `openai` ≥1.12.0 | Apache-2.0 |
| ORF | `[office]` | `openpyxl` ≥3.0.0 | MIT |
| ORF | `[notebook]` | `nbformat` ≥5.0.0 | BSD-3-Clause |
| ORF | `[email-output]` | `aspose-email-foss` ≥24.0.0 | **GPL-3.0** (Aspose fork) |
| ORF | `[mcp]` | `mcp` ≥1.0.0 | MIT |

## 3. License implications

### 3.1 Permissive (MIT / BSD / Apache-2.0) — no obligations beyond attribution

The vast majority of OPP/OL/ORF dependencies fall in this category. No
copyleft obligations; commercial use is unrestricted as long as the license
text and copyright notice are preserved (typically in `NOTICE` or
`THIRD_PARTY_LICENSES.md`).

### 3.2 LGPL-2.1 (chardet)

LGPL allows linking from proprietary code as long as the LGPL library is
dynamically linked and the user is able to re-link with a modified version.
`chardet` is imported as a normal Python package; this is considered
"weak linking" and is generally compatible with MIT-licensed projects.

### 3.3 GPL-2.0 (translate-toolkit, pypandoc-binary → pandoc)

`translate-toolkit` (used in OL and OPP) is GPL-2.0. Per the FSF, dynamic
linking of a GPL-2.0 library is permitted in a non-GPL application; static
linking or close coupling would impose GPL-2.0 on the whole. Python imports
of `translate-toolkit` are considered dynamic linking. The Omni Suite
remains MIT-licensed.

`pypandoc-binary` bundles the pandoc binary (GPL-2.0). The binary is
invoked as a subprocess; the Omni Suite does not link against pandoc
libraries. The subprocess invocation pattern is compatible with MIT
licensing for the Omni Suite itself, but **end users who redistribute the
pandoc binary** must comply with pandoc's GPL-2.0 license.

### 3.4 AGPL-3.0 (ebooklib, pymupdf)

`ebooklib` and `pymupdf` are AGPL-3.0. AGPL adds a network clause: if the
Omni Suite is run as a network service that exposes AGPL functionality to
end users, the AGPL terms require the Omni Suite to also be AGPL-licensed
(or the AGPL functionality to be replaced).

**Mitigation**: the Omni Suite is currently distributed as a CLI / MCP tool
intended for local use. If a future revision adds a hosted service that
exposes OPP's EPUB/PDF extraction over the network, the project must
either (a) switch to MIT/Apache-licensed EPUB and PDF libraries or (b)
re-license Omni Suite under AGPL-3.0.

### 3.5 GPL-3.0 (aspose-email-foss)

`aspose-email-foss` is the GPL-3.0 fork of Aspose.Email. It is **only
required for ORF's `[email-output]` extra** (MD → MSG conversion). The
default ORF install does NOT pull this in. ORF users who want MSG output
must explicitly `pip install omni-re-formatter[email-output]`. The
recommended alternative is `.eml` (open standard, fully supported by ORF
without this extra).

### 3.6 MPL-2.0 (tqdm)

MPL-2.0 is a weak copyleft license. Modifications to `tqdm` itself must be
released; combining `tqdm` with proprietary code is permitted.

## 4. System-level dependencies (not pip-installed)

These are binaries the user must install via the OS package manager:

| Binary | Debian/Ubuntu | macOS (Homebrew) | Windows | License |
|--------|---------------|------------------|---------|---------|
| `pandoc` | `apt install pandoc` | `brew install pandoc` | `choco install pandoc` | GPL-2.0 |
| `tesseract` | `apt install tesseract-ocr` | `brew install tesseract` | installer | Apache-2.0 |
| `poppler-utils` | `apt install poppler-utils` | `brew install poppler` | included in PDF viewers | GPL-2.0 |
| `libreoffice` (optional, for non-pandoc DOCX export) | `apt install libreoffice` | `brew install --cask libreoffice` | installer | MPL-2.0 |

## 5. Compliance checklist

For each release:

- [ ] All `dependencies` in `pyproject.toml` of all 3 modules are listed
      in §1 of this file.
- [ ] All `optional-dependencies` (extras) are listed in §2 of this file.
- [ ] Any new dependency's license is compatible with the Omni Suite's MIT
      license; if not, document the impact in §3.
- [ ] The pypandoc-binary AGPL/GPL-2.0 caveat is acknowledged in the
      release notes.
- [ ] If a hosted service is added, the AGPL-3.0 caveat for
      `ebooklib` / `pymupdf` is re-evaluated.

## 6. How to regenerate

```bash
# Per-module
pip install pip-licenses
pip-licenses --format=markdown --output-file=<module>-LICENSES.md

# Full audit (requires each module installed)
pip-licenses --format=markdown --output-file=THIRD_PARTY_LICENSES.md
```

## 7. Revision history

- **v0.1 (2026-06-22)**: Initial licenses document generated from
  `pyproject.toml` of OPP, OL, ORF. Manual table; future revision will be
  auto-generated from `pip-licenses`.
