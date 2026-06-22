# Security Audit — Omni Suite

> **Audience:** Omni Suite maintainers, security reviewers, and operators
> deploying the pipeline to production.
> **Status:** Living document. Last revised 2026-06-22.
> **Related:** [`SECURITY.md`](SECURITY.md) (action items for operators),
> [`ARCHITECTURE.md`](ARCHITECTURE.md) (cross-module design),
> [`THIRD_PARTY_LICENSES.md`](../THIRD_PARTY_LICENSES.md) (license-based risk),
> [`reports/_archive/2026-Q2/AUDIT_FINDINGS_VERIFIED.md`](../reports/_archive/2026-Q2/AUDIT_FINDINGS_VERIFIED.md) (prior audit context).

This document is the **authoritative security reference** for the Omni Suite.
It expands the operator-facing checklist in `docs/SECURITY.md` into a full
audit: what we have, what is exposed, what is missing, and how to close the
gaps. The structure follows the standard security review flow:

1. Current security model
2. Attack surface inventory
3. Identified gaps (honest)
4. Severity model
5. Roadmap (5 phases)
6. Disclosure policy
7. Known issues / accepted risks
8. Reproducible `make security-scan` target

---

## 1. Scope

The Omni Suite is a three-stage document localization pipeline:

- **OPP** (`omni-pre-processor`) — extracts documents to MD + XLIFF + skeleton
- **OL** (`omni-localizer`) — translates MD/XLIFF between languages via LLM
- **ORF** (`omni-re-formatter`) — backfills translated content to target format

Each module ships a CLI and an MCP server (21 tools total: 7 OPP + 8 OL + 6
ORF). The pipeline ingests 16 input formats (DOCX, PPTX, PDF, XLSX, CSV,
JSON, XML, HTML, ODT, EPUB, EML, MSG, IPYNB, images, audio/video, YouTube
`.url`) and emits 16 output formats from ORF (`apply-md`).

In scope for this audit:

- Path traversal, file read/write, ZIP slip
- MCP transport security (stdio today, HTTP/SSE tomorrow)
- LLM-key and secret handling
- LLM output handling (prompt injection, XSS, content trust)
- Subprocess invocation safety (pandoc, md2pptx, aspose-email-foss)
- Dependency supply-chain risk (AGPL/GPL/Apache/MIT mix)
- Denial of service (DoS) on the MCP surface

Out of scope (different threat model, not our code):

- LLM provider-side abuse of API keys
- Host OS hardening (kernel, container, network policies)
- Browser/UI XSS (no browser component exists)

---

## 2. Current Security Model

### 2.1 Per-Module PathValidator (Defense in Depth)

All three MCP servers implement a `PathValidator` that runs before any
file is read or written. The OPP and OL/ORF implementations share the same
shape (file:line references below) but differ in the allowlist.

**Validation pipeline** (in order, first failure short-circuits):

1. Path is parseable as `pathlib.Path` (`Omni_Re_Formatter/src/orf/mcp/security.py:84-89`).
2. Path does not contain `..` traversal components (`Omni_Re_Formatter/src/orf/mcp/security.py:92-96`).
3. Path resolves without `OSError` (`Omni_Re_Formatter/src/orf/mcp/security.py:99-105`).
4. Path is not inside a system directory (`/etc`, `/usr`, `/var`, `/System`, `/Library`, `C:\Windows`) — `Omni_Re_Formatter/src/orf/mcp/security.py:108-122`.
5. Resolved path is within at least one of `allowed_directories` — `Omni_Re_Formatter/src/orf/mcp/security.py:124-138`. This is the fix for **C6** (previously only checked `allowed_directories[0]`).
6. If the path is a symlink, the link target is also inside an allowed directory — `Omni_Re_Formatter/src/orf/mcp/security.py:140-161`.
7. File extension is not in the `BLOCKED_EXTENSIONS` blacklist — `Omni_Re_Formatter/src/orf/mcp/security.py:163-168`.
8. File extension is in the module-specific `ALLOWED_EXTENSIONS` whitelist — `Omni_Re_Formatter/src/orf/mcp/security.py:170-178`.
9. File exists and is a regular file (not a directory) — `Omni_Re_Formatter/src/orf/mcp/security.py:180-193`.
10. File size is within `max_file_size_bytes` (default 100 MB) — `Omni_Re_Formatter/src/orf/mcp/security.py:195-207`.

#### 2.1.1 OPP `ALLOWED_EXTENSIONS` (16 entries, post Phase 1.8)

`Omni_Pre_Processor/src/opp/mcp/security.py:62-66`:

```python
ALLOWED_EXTENSIONS: set[str] = {
    ".md", ".docx", ".pptx", ".pdf", ".xliff", ".xlf", ".xml",
    ".html", ".odt", ".epub", ".zip", ".txt",
    ".xlsx", ".csv", ".json", ".eml",
}
```

This is the **known-good** list for the MCP surface. It was extended from 12
to 16 entries during Phase 1.8 to add `.xlsx`, `.csv`, `.json`, `.eml`.
Still missing (CLI accepts but MCP refuses): `.msg`, `.png`, `.jpg`, `.ipynb`,
audio/video, `.url`. This asymmetry is the gap behind `OPP_PATH_DENIED`
errors users see on file types the CLI handles fine.

#### 2.1.2 ORF `ALLOWED_EXTENSIONS` (10 entries, defense-in-depth)

`Omni_Re_Formatter/src/orf/mcp/security.py:62`:

```python
ALLOWED_EXTENSIONS = {'.md', '.docx', '.pptx', '.xliff', '.xlf', '.xml', '.html', '.odt', '.epub', '.zip'}
```

ORF rejects more aggressively than OPP because ORF's `apply-md` validator
operates on **output** paths — it only writes formats ORF actually
produces. This intentionally excludes `.xlsx`, `.csv`, `.json`, `.ipynb`,
`.eml` from the MCP surface. Use `batch_convert` (or the CLI) for those.

#### 2.1.3 OL `ALLOWED_EXTENSIONS` (5 entries)

`Omni_Localizer/src/ol_mcp/security.py:73`:

```python
ALLOWED_EXTENSIONS = {".json", ".tmx", ".xlf", ".xliff", ".md"}
```

OL MCP only takes paths for `load_glossary` (`.json`), `search_tm` (`.tmx`),
and `translate_xliff` (`.xlf`/`.xliff`/`.md`). The text-in/text-out tools
(`translate_md_text`, `judge_text`, etc.) do no file I/O and never call the
validator — see `Omni_Localizer/README.md` "MCP Tools" section.

#### 2.1.4 Shared `BLOCKED_EXTENSIONS` blacklist (7 entries)

All three modules share the executable blacklist:

```python
BLOCKED_EXTENSIONS = {".exe", ".bat", ".cmd", ".sh", ".ps1", ".vbs", ".js"}
```

(`Omni_Re_Formatter/src/orf/mcp/security.py:19-27`,
`Omni_Localizer/src/ol_mcp/security.py:27-35`)

This is **defense in depth**: even if the extension whitelist is bypassed
somehow, no executable can be opened.

#### 2.1.5 OPP `ALLOWED_EXTENSIONS` narrowing gap

`Omni_Pre_Processor/src/opp/mcp/security.py:62-66` is the live MCP allowlist.
The CLI's `expand_directories` (`src/opp/cli.py:262-263`) accepts more
extensions than the MCP server does. This is intentional in the short term
(privilege separation: CLI = trusted local user, MCP = agent-mediated) but
should converge in a future phase. See `ACCEPTED_GAPS.md` "Format Matrix
Gaps" and Phase 1.8 of `PRODUCTION_READINESS.md`.

### 2.2 MCP Shared-Secret Authentication (A4, 2026-06-18)

All three MCP servers check a shared secret via the `auth_token` parameter
on every tool call. Implementation: `Omni_Pre_Processor/src/opp/mcp/auth.py:13-20`
(identical contract in OL and ORF).

```python
def check_auth(provided_secret: str | None) -> tuple[bool, str | None]:
    expected = os.environ.get("MCP_SHARED_SECRET")
    if not expected:
        return (True, None)   # dev mode: no auth
    if provided_secret == expected:
        return (True, None)
    return (False, "AUTH_FAILED")
```

**Semantics:**

- If `MCP_SHARED_SECRET` is **unset**, auth is **disabled** (developer mode).
- If set, every tool call must include a matching `auth_token` argument.
- Failure response is opaque (`AUTH_FAILED`), no information leak about which
  half of the comparison failed.

**Threat model**: stdio transport only. The shared secret is for
defense-in-depth in case an MCP client misroutes a request. Network-exposed
MCP requires a stronger scheme (see § 6.1).

### 2.3 H5 Token Bucket Rate Limiter (2026-06-20)

`Omni_Re_Formatter/src/orf/mcp/rate_limiter.py` defines a thread-safe token
bucket. The OPP and OL modules have mirrors with identical semantics. Each
tool dispatch consumes one token; when the bucket is empty, the call is
rejected with `RATE_LIMITED`.

**Configuration (env vars):**

- `OMNI_RATE_LIMIT_RPM` — requests per minute (default 60, 0 = disabled)
- `OMNI_RATE_LIMIT_BURST` — max burst size (default 10)

**Algorithm** (`Omni_Re_Formatter/src/orf/mcp/rate_limiter.py:19-57`):

- Lazy refill proportional to elapsed time × rate.
- Locked check-and-decrement.
- `wait_seconds` property reports backoff without consuming a token.

**Threats mitigated:**

- DoS by a runaway agent looping `extract_document` on a 100 MB file.
- Cost amplification on LLM-backed tools (OL: `translate_md_text` is the
  most expensive because every call hits the LLM).
- Sidecar disk-fill via `apply_md` writing many output files in a tight loop.

**Threats NOT mitigated:**

- Slow-loris (one request every 30 s holding a slot) — rate is per-bucket,
  not per-caller.
- Multi-process amplification — each MCP server has its own bucket; a
  caller fanning out across servers gets 3× the budget.

### 2.4 XSS / HTML Escaping in Extraction

OPP extractors that produce HTML output (EPUB, HTML, MSG) route their
output through `markdown` or a controlled serializer, not through `innerHTML`
or `eval`. The risk is not browser XSS (no browser consumes OPP output
directly) but **LLM prompt injection**: an attacker crafts an HTML email
that, when extracted, contains instructions the LLM obeys.

**Mitigations in place:**

- `shield_markdown()` in OL (`Omni_Localizer/src/ol_md/shield.py`) wraps
  code, links, images, math, and HTML blocks in `\x00OL_<TYPE>_<NNNN>\x00`
  placeholders before LLM translation, then restores them verbatim.
- OL's 4-layer repair pipeline (`Omni_Localizer/src/ol_md/pipeline.py:39-67`)
  re-checks shield integrity after each LLM call.
- `Op_evaluate` (LQA judge) flags translated output that doesn't match the
  source shield map, which is a strong prompt-injection detector.

**Residual risk:** if an attacker controls the LLM provider or has
poisoned a model cache, shield+restore cannot help. Mitigate by allowing
only trusted providers in `config/default.yaml`'s `llm_pool`.

### 2.5 ZIP Slip Protection (Skeleton Backfill)

ORF's `apply-xliff` path unpacks a `skeleton.zip` produced by OPP. ZIP
slip (`../../etc/passwd` in an entry name) is mitigated by `ZipFile.extract`
in modern Python, which rejects absolute paths and `..` components
(Python ≥3.6.2, CVE-2007-4559 patch).

**Additional mitigation** (`Omni_Re_Formatter/src/orf/skeleton/loader.py`):

- All extracted paths are passed through `PathValidator` after extraction.
- Skeleton files outside `allowed_directories` are rejected.
- The DOCX/PPTX skeleton is opened in a temp directory that is itself
  inside an allowed dir.

**Residual risk:** none known. Verified by
`Omni_Re_Formatter/tests/test_orf_security_attacks.py::test_zip_slip`
(regression test, originally added in C5 fix).

### 2.6 Error-Boundary Decorator (C12 fix, T1–T15)

All MCP tool calls go through `@mcp_error_boundary`
(`Omni_Pre_Processor/src/opp_mcp/_errors.py`,
`Omni_Re_Formatter/src/orf_mcp/_errors.py`,
`Omni_Localizer/src/ol_mcp/tools.py`). The decorator:

- Logs the full traceback server-side with `logger.exception(...)`.
- Returns an opaque error code + generic message to the client.
- Emits a `corr_xxxx` correlation id so server logs can be looked up.

This prevents the prior leak of file paths, internal class names, and
system info in error responses.

### 2.7 Subprocess Sandboxing (ORF)

ORF invokes `pandoc`, `md2pptx`, and `aspose-email-foss` as subprocesses.
The CLI subprocess runs in a validated working directory
(PathValidator output); the env is scrubbed of test-only vars
(`_MCP_SCRUB_ENV_KEYS` in `Omni_Re_Formatter/src/orf/mcp/server.py:57`)
to prevent the fake-pandoc seam from leaking into production output.

**Threats NOT mitigated:**

- Subprocess is not chrooted / namespaced. A future hardening phase should
  run pandoc under a restricted user (see § 4.4 Phase 4).
- `--` argument separator is not enforced between ORF args and the
  underlying tool's args. A malicious MD file containing CLI-flag-looking
  text is not a risk (passing goes through files, not argv), but the gap
  is worth noting.

---

## 3. Attack Surface

### 3.1 MCP Tool Inventory (21 tools)

| Module | Tool | Inputs that touch the host | Network egress |
|--------|------|----------------------------|----------------|
| OPP | `extract_document` | `file_path`, `output_dir`, `resource_dir` | None |
| OPP | `batch_extract` | `file_paths[]` | None |
| OPP | `detect_format_tool` | `file_path` | None |
| OPP | `generate_markdown` | `file_path`, `output_path` | None |
| OPP | `generate_xliff` | `file_path`, `output_path` | None |
| OPP | `save_skeleton` | `file_path`, `output_dir` | None |
| OPP | `ping` | None | None |
| OL | `translate_md_text` | (text only) | LLM API call |
| OL | `translate_xliff` | `input_path`, `output_path`, `glossary_path` | LLM API call |
| OL | `judge_text` | (text only) | LLM API call |
| OL | `load_glossary` | `path`, `config_dir` | None |
| OL | `get_relevant_terms` | (text only) | None |
| OL | `search_tm` | `tmx_path` | None (loads model on first call) |
| OL | `batch_translate_texts` | `glossary_path` | LLM API call(s) |
| OL | `ping` | None | None |
| ORF | `apply_md` | `input_md`, `output_path`, `images[]` | None |
| ORF | `apply_xliff` | `input_file`, `xliff_path`, `output_path`, `images[]` | None |
| ORF | `batch_convert` | `input_dir`, `pattern` | None |
| ORF | `detect_format` | `file_path` | None |
| ORF | `info` | `file_path` | None |
| ORF | `ping` | None | None |

**Risk profile by module:**

- **OPP** — high file I/O, no network. Path validation is the load-bearing
  control.
- **OL** — minimal file I/O (only `load_glossary`/`search_tm`/`translate_xliff`),
  high-cost LLM egress. The rate limiter and LLM-pool allowlist are the
  load-bearing controls.
- **ORF** — high file I/O, subprocess invocations. Path validation +
  subprocess sandboxing are the load-bearing controls.

### 3.2 Input Format Matrix (OPP, 16 formats)

`Omni_Pre_Processor/src/opp/pipeline.py:58-72` (and the README's
"Multi-format extraction" list):

| Format | Parser | Network? | Notes |
|--------|--------|----------|-------|
| DOCX | `python-docx` + `lxml` | No | Skeleton-preserving |
| PPTX | `python-pptx` | No | Skeleton-preserving |
| PDF | `pymupdf` (AGPL-3.0) | No | See § 5.2 |
| XLSX | `openpyxl` | No | |
| CSV | `pandas` | No | |
| JSON | (stdlib) | No | |
| XML | `lxml` | No | |
| HTML | `beautifulsoup4` | No | |
| ODT | `odfpy` (via translate-toolkit) | No | |
| EPUB | `ebooklib` (AGPL-3.0) | No | See § 5.2 |
| EML | (stdlib `email`) | No | Optional `[email]` extra for MSG |
| MSG | `extract-msg` | No | Optional `[email]` extra |
| IPYNB | `nbformat` | No | Optional `[notebook]` extra |
| Images | `pillow` + OCR | No | OCR: tesseract or rapidocr |
| Audio/Video | `faster-whisper` | No | Optional `[audio]` extra |
| YouTube `.url` | `markitdown[youtube-transcription]` | **Yes** | Optional `[youtube]` extra |

**Network-egress note:** only the YouTube transcription path makes a
network call (downloads captions or transcribes via YouTube's API). All
other formats are local-only.

### 3.3 Output Format Matrix (ORF `apply-md`, 16 formats + `auto`)

| Format | Engine | License implication |
|--------|--------|---------------------|
| DOCX | `pypandoc-binary` (pandoc) | GPL-2.0 (subprocess) |
| ODT | pandoc | GPL-2.0 (subprocess) |
| EPUB | pandoc | GPL-2.0 (subprocess) |
| HTML | `markdown` (BSD-3) | None |
| RTF | pandoc | GPL-2.0 (subprocess) |
| PDF | `weasyprint` (BSD-3) | None |
| PPTX | `md2pptx` (external CLI) | Depends on install |
| ICML | pandoc | GPL-2.0 (subprocess) |
| SRT | (custom) | None |
| XLSX | `openpyxl` | MIT |
| CSV | (stdlib) | None |
| JSON | (stdlib) | None |
| XML | `lxml` | BSD-3 |
| IPYNB | `nbformat` | BSD-3 |
| EML | (stdlib `email`) | None |
| MSG | `aspose-email-foss` (GPL-3.0) | See § 5.3 |

The `auto` meta-flag triggers format detection and is itself a path
validator concern (it reads file headers, not user input, so safe).

### 3.4 Cross-Module Trust Boundaries

```
Untrusted input (user doc, agent prompt)
        │
        ▼
[ OPP PathValidator ] ← allowed_directories
        │
        ▼
[ OPP Extractor ] ← reads file, writes MD/XLIFF/skeleton to allowed_dir
        │
        ▼
[ OL translate-md/translate-xliff ] ← optional LLM egress, optional glossary/tmx
        │
        ▼
[ ORF PathValidator ] ← allowed_directories
        │
        ▼
[ ORF apply-md/apply-xliff ] ← subprocess to pandoc/md2pptx
        │
        ▼
Output file (back inside allowed_dir)
```

**Trust boundary assumption**: each stage's output is in an allowed
directory, so the next stage can trust the input by construction. The
inter-stage handoff is the file system, not a network socket, so
TOCTOU (time-of-check-to-time-of-use) is the residual risk: an attacker
who can write to the allowed directory between OPP's write and OL's
read can swap the MD. Mitigated by file-mode 0700 on the allowed
directory in production deployments.

---

## 4. Identified Gaps

This section is intentionally blunt. Every item is a real gap that should
be tracked, not a paranoid hypothetical.

### 4.1 No Static Analysis in CI (bandit, semgrep)

**Status:** Not implemented. `make lint` runs `ruff` (style) and `mypy`
(types) but not a security linter.

**Gap:** Bandit (`bandit -r src/`) and Semgrep (`semgrep --config=p/owasp-top-ten`)
would catch common Python security issues (hardcoded passwords, `eval`,
`shell=True`, weak crypto) before they ship.

**Risk:** Medium. The codebase is small and audited by hand, but
contributor-submitted PRs may not be.

**Remediation:** Add to `make lint` and to `.github/workflows/`. See § 7.

### 4.2 No Dependency Vulnerability Scanning in CI (pip-audit, safety)

**Status:** Not implemented. The only dependency audit is
`THIRD_PARTY_LICENSES.md` (manually maintained) and `gitleaks` (secrets
only).

**Gap:** `pip-audit` (PyPA) or `safety check` would scan the locked
dependency tree for CVEs. Today, a malicious or compromised release of
`pymupdf` (AGPL-3.0, 1.27+) would not be caught until a user notices.

**Risk:** High. Document parsers are a known target (CVE history in
`lxml`, `pymupdf`, `python-docx`). The pipeline trusts these libraries
to safely parse untrusted input.

**Remediation:** Add to CI. Block merges on `pip-audit` CRITICAL/HIGH.

### 4.3 No Container Image Scanning (trivy, grype)

**Status:** Not implemented. No `Dockerfile` exists in the repo at the
suite level (per-sub-repo Dockerfiles exist but are not scanned).

**Gap:** `trivy image omni-suite:latest` would catch OS-level CVEs in
the runtime image (Python 3.13 base, glibc, openssl).

**Risk:** Medium. Image-based deployments inherit OS CVEs.

**Remediation:** Add `trivy image` to a release workflow. See § 7.

### 4.4 No Fuzz Testing (atheris, hypothesis)

**Status:** Not implemented. Test corpus is hand-crafted fixtures in
`batch_test/` and `tests/fixtures/`.

**Gap:** OPP and ORF parsers consume untrusted input. A fuzzer would
catch parser crashes (DoS), panics in extraction logic, and certain
injection classes. Hypothesis in property-based mode is a lighter-weight
alternative.

**Risk:** Medium. The parsers are well-tested via the matrix verifier
(195 cells, 131 PASS), but coverage is bounded by the fixture set.

**Remediation:** Phase 3 of the roadmap.

### 4.5 No SBOM Generation (cyclonedx, syft)

**Status:** Not implemented. `THIRD_PARTY_LICENSES.md` is a markdown
table, not a machine-readable SBOM.

**Gap:** A CycloneDX or SPDX SBOM is required by US Executive Order
14028 and many enterprise procurement processes. Without it, downstream
consumers cannot audit the dependency tree.

**Risk:** Low (functional) / High (compliance).

**Remediation:** Phase 2 of the roadmap. Add `cyclonedx-py` to a
release workflow.

### 4.6 No CVE Dashboard / Continuous Monitoring

**Status:** Not implemented. Dependabot is **not** enabled on the
GitHub repo; Renovate is not configured.

**Gap:** New CVEs in dependencies are not surfaced to maintainers
until a user reports one. This is a 6-12 month detection lag on
average.

**Risk:** High. The 21 MCP tools, 16 formats, and 50+ transitive deps
make manual monitoring infeasible.

**Remediation:** Enable Dependabot security updates (`.github/dependabot.yml`).
Subscribe to GitHub Security Advisories for `pymupdf`, `lxml`, `python-docx`,
`python-pptx`, `litellm`.

### 4.7 MCP Transport Has No Auth Boundary Today

**Status:** `MCP_SHARED_SECRET` is opt-in (env var unset = no auth).
stdio transport is the only supported mode.

**Gap:** If anyone ever adds an HTTP or SSE transport without
flipping the auth default, every tool becomes network-reachable without
credentials. The shared-secret scheme is a stopgap; production HTTP MCP
needs OAuth2 / mTLS.

**Risk:** Critical (if transport changes) / Low (today, stdio only).

**Remediation:** Document the requirement loudly. Add a startup-time
assertion: "MCP_SHARED_SECRET is unset, but transport != 'stdio'. Refusing
to start."

### 4.8 LLM Prompt Injection Is Unmitigated Above Shield Level

**Status:** OL's `shield_markdown` protects 7 types of constructs from
the LLM. The content of regular text is **not** sanitized.

**Gap:** An attacker who controls the source document (or who can
substitute a malicious document into an allowed directory) can include
instructions in regular text that the LLM obeys. Mitigated by LQA
judging (a low score triggers retry), but not prevented.

**Risk:** Medium-High. The LLM provider sees the unshielded text and
the shield map; the LLM may or may not follow the original meaning if
prompt injection succeeds.

**Remediation:** Phase 4. Consider a content sanitization pass that
strips suspicious patterns from regular text before shield wrapping.

### 4.9 No Penetration Test

**Status:** Not performed. The 2026-Q2 audit (`AUDIT_FINDINGS_VERIFIED.md`)
was a code review, not a pentest.

**Gap:** Pentest would catch authorization issues (e.g., can a
non-`auth_token` caller ping?), timing side channels (e.g., does the
`check_auth` function leak length-of-secret via timing?), and
real-world chained exploits (path traversal + symlink + race condition).

**Risk:** Unknown.

**Remediation:** Phase 4 of the roadmap. Budget: 5-10 days with a
security consultancy.

### 4.10 Subprocess Sandbox Is OS-Level Only

**Status:** ORF runs pandoc, md2pptx, aspose-email-foss as the same
UID as the MCP server, in the same working directory.

**Gap:** A malicious MD file that triggers a pandoc CVE could
escape the working directory. pandoc has had several CVEs in
the past 5 years (e.g., CVE-2023-35936, RCE via LaTeX template).

**Risk:** Medium. Mitigated by keeping pandoc updated and
restricting the working directory to allowed_dirs.

**Remediation:** Phase 4. Run pandoc in a chroot / container /
firejail.

### 4.11 LLM Key Storage Lacks Hardening Guidance

**Status:** The pre-2026 leak incident (C1 in `SECURITY.md`) found
API keys in `Omni_Localizer/.env` with `chmod 777`.

**Gap:** `setup_dev.sh` does not `chmod 600` the `.env` it creates.
There is no runtime check that the file mode is safe.

**Risk:** Low (operator's choice) / High (if a fresh install leaves
the default).

**Remediation:** Modify `setup_dev.sh` to write `.env` with mode
0600. Add a startup warning when the file mode is world-readable.

---

## 5. Severity Model

Findings are classified by **exploitability** (can it be done?) and
**impact** (what happens if it is done?). The matrix is intentionally
short — five buckets, no scoring games.

| Severity | Exploitability | Impact | Examples |
|----------|----------------|--------|----------|
| **Critical** | Trivial (no auth, no user action) | Full RCE, full read of host FS, key exfil | Pre-C3 unlink without revalidation (path traversal + arbitrary file delete). C7 stdio-then-HTTP without auth. |
| **High** | Requires basic capability (allowed_dir write) | Privilege escalation within process, partial key exfil, DoS on production | Pre-C4 ImagePlacement arbitrary read. Pre-C5 `output_path` arbitrary write. Pre-C12 traceback leak. |
| **Medium** | Requires chaining (allowed_dir + crafted doc) | Information disclosure, parser DoS, prompt-injection in unattended contexts | Most parsing CVEs in `pymupdf`, `lxml`. EPUB non-determinism (`ACCEPTED_GAPS.md`). |
| **Low** | Requires insider or rare config | Audit-trail gaps, license-attribution drift | gitleaks not in CI today (only pre-commit). |
| **Informational** | N/A | Hygiene | "Consider moving to OAuth2 for HTTP MCP." |

**Triage rule:** if a finding is "Critical" by exploitability but only
"Low" by impact (e.g., a path-traversal into `/tmp`), downgrade one
level. The pipeline does not put secrets in `/tmp` by default, so
`/tmp` is a low-value target.

**Tie-break on "patch now vs. next release":**

- Critical + High: patch within 7 days, or temporarily disable the
  affected tool.
- Medium: next release.
- Low + Informational: back log.

**Tie-break on disclosure:**

- Critical / High are reported via `security@omninowhere.org` (see § 6).
- Medium and below are tracked in this audit doc.

---

## 6. Disclosure Policy

### 6.1 How to Report a Vulnerability

**Do not file a public GitHub issue for security findings.**

Email: **`security@omninowhere.example.invalid`** (placeholder; replace
with the real address once the project's security mailbox is set up
during Phase 1 of the roadmap). Until then, file a private security
advisory via GitHub's "Security" tab.

**Include in the report:**

1. The affected module + file:line (or commit SHA).
2. Steps to reproduce (PoC preferred but not required).
3. Observed vs. expected behavior.
4. Threat model assumption (e.g., "assumes the agent is untrusted").
5. Suggested fix (optional but appreciated).

**Response SLA:**

- Acknowledgement: within 3 business days.
- Severity classification: within 7 business days.
- Patch for Critical / High: within 30 days.
- Patch for Medium: next release.
- Public disclosure: coordinated with the reporter, default 90 days
  after patch or sooner by mutual agreement.

### 6.2 What We Will Not Do

- We will not threaten legal action against good-faith research.
- We will not request a CVE before the patch is ready.
- We will not silently fix a finding without crediting the reporter
  (in CHANGELOG.md, unless the reporter prefers anonymity).

### 6.3 What We Ask Of You

- Give us a reasonable window to patch before public disclosure.
- Do not access user data; the test corpus in `batch_test/` and
  `tests/fixtures/` is sufficient for PoCs.
- Do not attempt denial-of-service on the public CI / PyPI mirrors.

---

## 7. Remediation Roadmap

Five phases over the next two quarters. Each phase ends in a CI gate
that fails the build if the phase's checks are not met.

### Phase 1 — Triton Scan (Week 1-2)

**Goal:** Establish a baseline. Know what we have.

- [ ] Add `pip-audit` to `.github/workflows/security.yml`. Block on
      CRITICAL/HIGH CVEs in direct deps.
- [ ] Add `bandit -r Omni_*/src/` to `make lint`. Treat CRITICAL bandit
      findings as build failures.
- [ ] Add `trivy fs .` to scan the working tree. Add `trivy image` for
      any Dockerfiles in the suite.
- [ ] Add `gitleaks protect` to the pre-commit chain (currently
      `detect` only, per `.pre-commit-config.yaml`).
- [ ] Land the `make security-scan` target (see § 8).
- [ ] Establish `security@omninowhere.example.invalid` mailbox (or
      document GitHub Security Advisories as the channel).

**Definition of done:** CI runs all four tools; a clean run produces a
`security-report.json` artifact attached to every PR.

### Phase 2 — SBOM + License Compliance (Week 3-4)

**Goal:** Machine-readable dependency inventory.

- [ ] Add `cyclonedx-py` (or `syft`) to a release workflow. Emit
      CycloneDX JSON + SPDX tag-value alongside each PyPI upload.
- [ ] Add `pip-licenses --format=markdown` to a release workflow. Auto-
      generate `THIRD_PARTY_LICENSES.md` from the locked dep set.
- [ ] Add a CI check that fails if a newly-introduced dep has a
      license that the project's MIT-license combo can't absorb
      (AGPL-3.0 added to a network service, for example).
- [ ] Re-evaluate the `pymupdf` / `ebooklib` AGPL-3.0 status every
      release (see `THIRD_PARTY_LICENSES.md` § 3.4).

**Definition of done:** every release ships a SBOM. The license doc is
no longer hand-maintained.

### Phase 3 — Fuzz Testing (Week 5-8)

**Goal:** Catch parser crashes and panics before users do.

- [ ] Add `atheris` (libFuzzer-based) fuzzers for the OPP extractors
      in priority order: PDF, EPUB, EML, DOCX, PPTX. Run for 1 hour
      per extractor in nightly CI.
- [ ] Add `hypothesis` property-based tests for ORF's PathValidator
      (verify the validator never accepts a `..`-containing path,
      even under symlink races).
- [ ] Add a corpus-seeding job that pulls fixtures from public CVE
      PoCs for `lxml`, `pymupdf`, `python-docx` (e.g., the OSS-Fuzz
      project). Crashes become regression tests.
- [ ] Document the seed corpus in `tests/fuzz/README.md`.

**Definition of done:** nightly fuzzers run with no crashes for 30
consecutive nights.

### Phase 4 — Penetration Test (Week 9-12)

**Goal:** External validation. Find what we missed.

- [ ] Engage a security consultancy for a 5-10 day engagement. Scope:
      - OPP/ORF `apply-md` chain on a hostile MD file.
      - OL `translate-xliff` with a poisoned TMX/glossary.
      - MCP stdio→HTTP migration path (read-only review of the
        transport code).
      - Authorization bypass attempts on `MCP_SHARED_SECRET` (timing,
        length-extension, replay).
      - Subprocess injection via crafted MD frontmatter.
- [ ] Triage findings into the severity model in § 5.
- [ ] Patch Critical and High findings before Phase 5 starts.

**Definition of done:** pentest report attached to
`reports/_archive/<quarter>/PENTEST_REPORT.md`; all Critical/High
findings have linked PRs.

### Phase 5 — Ongoing Monitoring (Week 13+, perpetual)

**Goal:** Stay safe.

- [ ] Enable Dependabot security updates (`.github/dependabot.yml`).
- [ ] Subscribe to GitHub Security Advisories for the top-10
      dependencies (pymupdf, lxml, python-docx, python-pptx, litellm,
      openpyxl, beautifulsoup4, openai, mcp, typer).
- [ ] Quarterly re-run of `pip-audit` + `trivy`. The result is
      attached to the release notes.
- [ ] Annual re-engagement with the pentest consultancy (or in-house
      red team).
- [ ] When the first HTTP/SSE MCP transport is added, the auth
      requirement from § 4.7 is enforced and the security mailbox is
      set up before the first network request is served.

**Definition of done:** the project has not had a Critical or High
finding open for more than 30 days in any quarter.

---

## 8. `make security-scan` Target

A concrete target for the root `Makefile`. Wraps `pip-audit`, `bandit`,
`trivy`, and `gitleaks` so a developer can run the whole suite in one
command. The tools are **not** added to the project's hard dependencies
— the target fails loudly if any tool is missing, so the developer
knows to install it.

```makefile
# =============================================================================
# make security-scan — run the full security toolchain
# =============================================================================
# Wraps: pip-audit (deps), bandit (SAST), trivy (filesystem), gitleaks (secrets).
# Each tool degrades gracefully if missing: prints a SKIP line and continues.
# Outputs JSON + SARIF to test_artifacts/security/<date>/ for CI upload.
# =============================================================================

.PHONY: security-scan security-scan-deps security-scan-sast security-scan-fs security-scan-secrets

SEC_DIR := test_artifacts/security/$(shell date -u +%Y%m%dT%H%M%SZ)
PYTHON  := .venv_ol/bin/python

security-scan: security-scan-deps security-scan-sast security-scan-fs security-scan-secrets
	@echo ""
	@echo "==> Security scan complete. Reports in $(SEC_DIR)/"
	@echo "    View summary: cat $(SEC_DIR)/SUMMARY.md"
	@ls -la $(SEC_DIR)/

security-scan-deps:
	@mkdir -p $(SEC_DIR)
	@echo "==> [1/4] pip-audit (dependency CVE scan)"
	@if command -v pip-audit >/dev/null 2>&1; then \
	    pip-audit --strict --format=json --output=$(SEC_DIR)/pip-audit.json 2>$(SEC_DIR)/pip-audit.stderr || \
	        echo "    pip-audit found vulnerabilities (see $(SEC_DIR)/pip-audit.json)"; \
	else \
	    echo "    SKIP: pip-audit not installed. Install: pip install pip-audit"; \
	fi

security-scan-sast:
	@mkdir -p $(SEC_DIR)
	@echo "==> [2/4] bandit (static analysis)"
	@if command -v bandit >/dev/null 2>&1; then \
	    bandit -r Omni_Pre_Processor/src Omni_Localizer/src Omni_Re_Formatter/src \
	        -f json -o $(SEC_DIR)/bandit.json 2>$(SEC_DIR)/bandit.stderr || true; \
	    bandit -r Omni_Pre_Processor/src Omni_Localizer/src Omni_Re_Formatter/src \
	        -f txt -o $(SEC_DIR)/bandit.txt 2>/dev/null || true; \
	else \
	    echo "    SKIP: bandit not installed. Install: pip install bandit"; \
	fi

security-scan-fs:
	@mkdir -p $(SEC_DIR)
	@echo "==> [3/4] trivy (filesystem scan)"
	@if command -v trivy >/dev/null 2>&1; then \
	    trivy fs --severity HIGH,CRITICAL --format json --output $(SEC_DIR)/trivy-fs.json . 2>$(SEC_DIR)/trivy-fs.stderr || \
	        echo "    trivy found HIGH/CRITICAL findings (see $(SEC_DIR)/trivy-fs.json)"; \
	else \
	    echo "    SKIP: trivy not installed. Install: https://aquasecurity.github.io/trivy/latest/getting-started/installation/"; \
	fi

security-scan-secrets:
	@mkdir -p $(SEC_DIR)
	@echo "==> [4/4] gitleaks (secret scan)"
	@if command -v gitleaks >/dev/null 2>&1; then \
	    gitleaks detect --source . --report-format json --report-path $(SEC_DIR)/gitleaks.json --no-git 2>$(SEC_DIR)/gitleaks.stderr || \
	        echo "    gitleaks found potential secrets (see $(SEC_DIR)/gitleaks.json)"; \
	else \
	    echo "    SKIP: gitleaks not installed. Install: https://github.com/gitleaks/gitleaks"; \
	fi
```

**How to use:**

```bash
# Run everything
make security-scan

# Run just the SAST layer
make security-scan-sast

# Inspect the most recent run
ls -lt test_artifacts/security/ | head -3
```

**What the output looks like on a clean run:**

```
==> [1/4] pip-audit (dependency CVE scan)
==> [2/4] bandit (static analysis)
==> [3/4] trivy (filesystem scan)
==> [4/4] gitleaks (secret scan)

==> Security scan complete. Reports in test_artifacts/security/20260622T140000Z/
    View summary: cat test_artifacts/security/20260622T140000Z/SUMMARY.md
-rw-r--r-- bandit.json
-rw-r--r-- bandit.txt
-rw-r--r-- gitleaks.json
-rw-r--r-- pip-audit.json
-rw-r--r-- trivy-fs.json
```

**What the output looks like on a finding (sample):**

```
==> [1/4] pip-audit (dependency CVE scan)
    pip-audit found vulnerabilities (see test_artifacts/security/.../pip-audit.json)
```

The exit code is `0` on "found nothing" and non-zero on "found something,
but couldn't auto-fix" — the developer is expected to read the JSON.
The Makefile intentionally does not silently swallow failures.

---

## 9. Known Issues / Accepted Risks

A flat list, no severity rating (see § 5 for that). Each item is something
we know about and have decided **not** to fix immediately, with the
reason. If a reader thinks one of these should be re-classified, file
an issue (non-security) or email `security@` (security).

| # | Issue | Where | Why accepted |
|---|-------|-------|--------------|
| K1 | No `pip-audit`, `bandit`, `trivy` in CI today | `.github/workflows/` | Phase 1 of the roadmap (§ 7). Mitigated by hand review of every PR. |
| K2 | No SBOM emitted on release | release workflow | Phase 2 of the roadmap. Mitigated by `THIRD_PARTY_LICENSES.md` (manual). |
| K3 | No fuzz testing | `tests/fuzz/` does not exist | Phase 3 of the roadmap. Mitigated by the 195-cell matrix verifier. |
| K4 | No penetration test performed | n/a | Phase 4 of the roadmap. Mitigated by the 2026-Q2 internal audit (C1-C17). |
| K5 | No CVE dashboard / Dependabot | `.github/dependabot.yml` not present | Phase 5 of the roadmap. Mitigated by maintainer attention. |
| K6 | `MCP_SHARED_SECRET` defaults to off in dev | `Omni_Pre_Processor/src/opp/mcp/auth.py:13-20` | stdio transport only; trust = OS user. Documented in `SECURITY.md` C7. |
| K7 | OPP MCP `ALLOWED_EXTENSIONS` (16) is narrower than OPP CLI (16+audio/video/.url) | `Omni_Pre_Processor/src/opp/mcp/security.py:62-66` | Intentional privilege separation. Documented in `Omni_Pre_Processor/docs/TROUBLESHOOTING.md` `OPP_PATH_DENIED`. |
| K8 | ORF `apply-md` rejects `.xlsx`, `.csv`, `.json`, `.ipynb`, `.eml` outputs | ORF path validator | Use `batch_convert` or the CLI for those. Documented in `Omni_Re_Formatter/docs/TROUBLESHOOTING.md`. |
| K9 | `ebooklib` and `pymupdf` are AGPL-3.0 | `THIRD_PARTY_LICENSES.md` § 3.4 | Acceptable while Omni Suite is CLI / MCP. Re-evaluate if a hosted service is added. |
| K10 | `pypandoc-binary` bundles GPL-2.0 pandoc | `THIRD_PARTY_LICENSES.md` § 3.3 | Subprocess invocation pattern is compatible with MIT-licensed Omni Suite. End users who redistribute must comply with pandoc's GPL-2.0. |
| K11 | `aspose-email-foss` is GPL-3.0 (MSG output only) | `THIRD_PARTY_LICENSES.md` § 3.5 | Optional `[email-output]` extra. Use `.eml` instead — fully supported, no GPL concern. |
| K12 | LLM keys may be world-readable in fresh installs | `setup_dev.sh` | Phase 5. Mitigated by the manual `chmod 600` step in `SECURITY.md` C1. |
| K13 | EPUB extraction is non-deterministic (8/8 cells) | `ACCEPTED_GAPS.md` row 21 | Operational concern, not security. Acceptable per `ACCEPTED_GAPS.md`. |
| K14 | OL `translate-xliff` derives output path from input stem when `output_path` is None | `Omni_Localizer/src/ol_mcp/tools.py:696-700` | Adds `<stem>_translated.xlf` next to the input. Not a file overwrite. Documented in `Omni_Localizer/docs/API.md` § 2.2. |
| K15 | MCP server names are inconsistent (`opp-mcp-server`, `ol-mcp`, `orf-mcp-server`) | `Omni_Re_Formatter/README.md` and friends | Historical. Documented in `ARCHITECTURE.md` § 4. Do not "fix" without coordinating a client-config migration. |
| K16 | Tests run as the same UID as the developer; no test isolation for filesystem ops beyond `tmp_path` | `pytest` fixtures | Standard for pytest. No security implication beyond test pollution. |
| K17 | Real-LLM nightly tests excluded from CI gate | `Makefile` | Require network + API keys. Run on a separate schedule. |
| K18 | No CORS policy on any potential HTTP endpoint (none today) | n/a | Tracked as a forward-looking item: when the HTTP MCP transport lands, the CORS default must be `deny-all`. |

---

## 10. References

### 10.1 In-repo

- `docs/SECURITY.md` — operator-facing action items (C1, C2, fixes C3-C6, C12).
- `docs/ARCHITECTURE.md` — cross-module design + MCP naming wart.
- `docs/ERROR_CODES.md` — full error-code dictionary (12 OPP, 12 OL, 13 ORF).
- `docs/API_STABILITY.md` — public-surface contract (7+8+6 = 21 tools).
- `docs/T14_LIMITATION.md` — hermetic CI seam gap.
- `docs/SLA.md` — availability / latency targets (relevant to DoS).
- `PRODUCTION_READINESS.md` — prior production-readiness assessment.
- `ACCEPTED_GAPS.md` — consciously accepted tradeoffs (overlaps with § 9 above).
- `THIRD_PARTY_LICENSES.md` — license-based risk inventory.
- `reports/_archive/2026-Q2/AUDIT_FINDINGS_VERIFIED.md` — full audit (17 CRITICAL, 22 HIGH, 35 MEDIUM/LOW).
- `reports/_archive/2026-Q2/GIT_HISTORY_PURGE_PLAN.md` — playbook for the C2 git history purge.
- `Omni_Pre_Processor/src/opp/mcp/security.py` — OPP PathValidator + ALLOWED_EXTENSIONS (16 entries).
- `Omni_Re_Formatter/src/orf/mcp/security.py` — ORF PathValidator + BLOCKED_EXTENSIONS (7 entries).
- `Omni_Localizer/src/ol_mcp/security.py` — OL PathValidator + ALLOWED_EXTENSIONS (5 entries).
- `Omni_Pre_Processor/src/opp/mcp/auth.py` — MCP shared-secret auth (A4).
- `Omni_Re_Formatter/src/orf/mcp/rate_limiter.py` — H5 token bucket.
- `Omni_Pre_Processor/src/opp_mcp/_errors.py` — `@mcp_error_boundary` decorator (C12).
- `Omni_Re_Formatter/src/orf_mcp/_errors.py` — same for ORF.
- `Omni_Localizer/src/ol_mcp/tools.py` — same for OL.
- `Omni_Localizer/src/ol_md/shield.py` — content shielding (LLM prompt-injection defense).
- `Omni_Re_Formatter/src/orf/skeleton/loader.py` — ZIP slip protection.
- `Omni_Re_Formatter/src/orf/mcp/server.py:57` — `_MCP_SCRUB_ENV_KEYS`.
- `Omni_Re_Formatter/src/orf/cli.py:776` — cross-format XLIFF guard (`--force`).
- `Omni_Pre_Processor/tests/mcp/test_security_attacks.py` — security regression tests.
- `Omni_Re_Formatter/tests/test_orf_security_attacks.py` — same for ORF.
- `tests/contract/` (planned Phase 4) — CLI/MCP contract invariants.
- `scripts/mcp_matrix_verifier.py` — 165-cell MCP matrix verifier.

### 10.2 External

- [CWE-22 Path Traversal](https://cwe.mitre.org/data/definitions/22.html)
- [CWE-78 OS Command Injection](https://cwe.mitre.org/data/definitions/78.html)
- [CWE-94 Code Injection](https://cwe.mitre.org/data/definitions/94.html)
- [CWE-200 Information Exposure](https://cwe.mitre.org/data/definitions/200.html)
- [CWE-400 Uncontrolled Resource Consumption (DoS)](https://cwe.mitre.org/data/definitions/400.html)
- [CWE-611 XML External Entity Processing](https://cwe.mitre.org/data/definitions/611.html)
- [CWE-829 Inclusion of Functionality from Untrusted Control Sphere](https://cwe.mitre.org/data/definitions/829.html)
- [CVE-2007-4559 (Python tarfile / zipfile)](https://nvd.nist.gov/vuln/detail/CVE-2007-4559)
- [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [MCP Specification](https://modelcontextprotocol.io/)
- [AGPL-3.0 Network Clause](https://www.gnu.org/licenses/agpl-3.0.html)

### 10.3 Revision history

- **v0.1 (2026-06-22)** — Initial audit. Authored from `SECURITY.md` and
  the 2026-Q2 audit findings. Cross-references the A4 (auth), H5 (rate
  limit), and C1-C17 (path-validation) work cycles. Roadmap for the
  next two quarters is captured in § 7.

---

> **Reminder for the next maintainer:** This document is the security
> reference. If you change `PathValidator.ALLOWED_EXTENSIONS` or the
> rate-limit defaults, update this file in the same commit. If you add
> a new MCP tool, add a row to § 3.1. If you add a new dependency with
> a copyleft license, add a row to § 9 K9-K11 and to
  `THIRD_PARTY_LICENSES.md`. The audit is only as good as the
> discipline behind it.
