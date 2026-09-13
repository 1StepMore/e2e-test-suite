# Validation Standards — Omni Suite

This is the centralized, citable standards reference for the Omni Suite
validation framework. Every scenario step that enforces a quality bar cites
the exact standard it checks as `standard: STANDARDS.md#<anchor-id>` (see
`docs/agent-tester-validation-guide.md` §2-§3 — the `standard` field rides
alongside the five-part evidence contract: surface / real call / expect /
actual / artifact-to-show).

The bars are grouped into two named families, one per validation mission
(draft D13): **AGENT-SURFACE** (agent-user conformance — every agent-facing
tool works as an agent would use it) and **HUMAN-QUALITY** (human-result
quality — the pipeline's output satisfies human end-users).

Thresholds are NOT invented: HUMAN-QUALITY bars copy the exact gate
implementations from `scripts/omo_loop.py` (Q1-Q6, lines 191-299), and the
format-engines reference copies `Omni_Re_Formatter/AGENTS.md:101-120` and
`Omni_Pre_Processor/AGENTS.md:87`.

## Fallbacks are never evidence {#fallbacks-never-evidence}

Deterministic fallbacks — `OMNI_TEST_FAKE_LLM=1`,
`OMNI_TEST_FAKE_PANDOC=1`, and every equivalent test seam in this class
(`OMNI_TEST_FAKE_*`, monkey-patched engines, stub backends) — are **NEVER
admissible as quality evidence**. A fallback emits synthetic, deterministic
output; a green verdict obtained under one proves the plumbing ran, not that
the result meets the human-quality bar.

The engine enforces this in `omni_mcp/validation/engine.py`
(`_fake_llm_reason`, lines 263-293), using the ONE family rule in
`omni_mcp/validation/family.py` (prefix-first, anchor-fallback):

- When `OMNI_TEST_FAKE_LLM=1` is active in the effective env and the
  scenario is **human-quality** — its name carries the `pipeline-` prefix
  OR any step cites a HUMAN-QUALITY anchor — the verdict is **`invalid`**,
  not `passed` and not `failed`. `invalid` is a distinct status that can
  never be reported as GREEN.
- `--allow-fake` is the **contract-only escape hatch**: it re-admits a
  fallback run ONLY when the scenario's family is all-`agent-user` AND
  **every** step cites an AGENT-SURFACE anchor. An anchor-less step, a
  single HUMAN-QUALITY citation, or an empty step list makes the scenario
  ineligible — the escape hatch is non-vacuous by design.
- Independently, any produced artifact carrying the fake-echo signature is
  `invalid` — positive fake content cannot be waved away, even with
  `--allow-fake`.

`OMNI_TEST_FAKE_PANDOC` and the other module-level fallback seams
(`Omni_Re_Formatter/src/orf/cli.py:221`) fall under the same admissibility
rule: a fallback-active run is not admissible human-quality evidence
regardless of which seam produced the synthetic output. The engine
implements the `OMNI_TEST_FAKE_LLM` check today; the bar binds every
fallback.

**How to check:** a scenario that would produce a human-quality verdict
while a fallback env var is set must report `invalid`; unset the fallback
to obtain real evidence. Citable as `standard:
STANDARDS.md#fallbacks-never-evidence`.

## AGENT-SURFACE

Mission axis 1 (draft D13): validation proves every agent-facing surface —
the live MCP tool registries (`opp.mcp.server`, `ol_mcp.tools`,
`orf.mcp.server`, suite `omni_mcp/server.py`) and the module CLIs — works as
an agent-user would use it: schema-shaped params accepted, structured JSON
returned, clear parseable errors on bad input, path-security denial honored,
sane exit codes. Covered by `scenarios/agent-surface/` (one scenario per
live tool) and the coverage audit.

### Tool contract conformance {#tool-contract}

Every agent-facing tool accepts its schema-shaped parameters, executes
against the real surface, and returns a structured result carrying the
expected keys — no dead tools, no shape drift between the live registry and
the shipped behavior. A step enforces this with an `expect` block of
`success: true` plus `data_has: [...]` naming the keys the tool's live
schema declares (from the live registries, NOT the stale AGENTS.md tables —
OPP 9, OL 21, ORF 7, suite `omni_mcp` 2 at baseline).

**How to check:** in-process call of the real module tool function (e.g.
`from ol_mcp.tools import ping` per the AGENTS.md in-process pattern), then
grade `success: true` + key presence against the tool's declared result
shape. Citable as `standard: STANDARDS.md#tool-contract`.

### JSON parseability {#json-parseable}

Every tool result and every CLI JSON output parses as valid JSON — an
agent-user's `json.loads` must never fail on the suite's own output. A
response that cannot be parsed is a contract break regardless of content.

**How to check:** `json.loads` on the captured output inside the step; a
`JSONDecodeError` fails the step. Citable as `standard:
STANDARDS.md#json-parseable`.

### Error clarity {#error-clarity}

Failures are reported as clear, parseable, agent-readable error messages
that name the failing tool and the offending parameter — never raw
stack-trace soup. An agent-user must be able to act on the message without
reading the engine source.

**How to check:** invoke the tool with a deliberately bad parameter (missing
arg / bad path per tool family); expect an error payload that names the
tool + reason and does NOT contain a `Traceback (most recent call last)`
frame. Citable as `standard: STANDARDS.md#error-clarity`.

### Path security {#path-security}

Path-taking tools deny access outside the configured allowlist
(`MCP_ALLOWED_DIRECTORIES`, with per-module overrides `OPP_MCP_ALLOWED_DIRS`
and `ORF_MCP_ALLOWED_DIRS`); an out-of-allowlist path MUST be rejected with
a clear denial, never silently accepted. OPP is fail-closed — an unset
allowlist means denial.

**How to check:** call a path-taking tool (e.g. OPP `extract_document`) with
a path outside the declared allowlist; expect a denial error naming the
path. Citable as `standard: STANDARDS.md#path-security`.

### Exit codes {#exit-codes}

CLI commands exit 0 on success and a nonzero code on failure, with the
failure reason on stderr — so scripts and agents can branch on the code.
The regression seed (T2 PDF→XLIFF guard) locks a nonzero-exit contract:
`opp sample.pdf --target-format xlf --source-lang en --target-lang zh`
exits 1 with `XLIFF not supported for PDF` on stderr (`opp/pipeline.py:131`).

**How to check:** `expect: {exit_code: 0}` on success paths;
`expect: {exit_code: 1, stderr_has: [...]}` on guarded failure paths.
Citable as `standard: STANDARDS.md#exit-codes`.

## HUMAN-QUALITY

Mission axis 2 (draft D9 + D12): a green end-to-end pipeline run must prove
the translated document meets the end-user bar. Thresholds below are copied
verbatim from the gate implementations in `scripts/omo_loop.py` (Q1-Q6,
lines 191-299) — the scenario asserts the SAME values the L3 loop gates on.
Covered by `scenarios/pipeline/` (real LLM; `requires_env`-gated →
`unconfigured` in key-less CI, GREEN in nightly).

### LQA threshold {#lqa-threshold}

The average LLM-judged translation quality score must be **≥ 4.0/5 on the
0-5 scale** (from `_gate_q2_lqa`: `pass_threshold_5 = 4.0`,
`scripts/omo_loop.py:349`). Scores come from OL's `JudgeService` over the
first ≤ 50 scorable trans-units of the translated XLIFF; whitespace-only
targets (failed translations) are skipped; the average of `judge_overall_score`
values (0-1 scale, rescored to /5) must meet the threshold
(`scripts/omo_loop.py:386-388`).

**How to check:** OL JudgeService via `ol_lqa.judge.JudgeService` on the
translated XLIFF pairs; `avg_5 >= 4.0` passes. Citable as `standard:
STANDARDS.md#lqa-threshold`.

### Paragraph ratio {#para-ratio}

The output paragraph count must be within **±5% of the source**: ratio
`out_n / src_n` in the closed interval **[0.95, 1.05]** (from
`_gate_q6_roundtrip`, `scripts/omo_loop.py:270-271`). A ratio outside the
band means the translation added or dropped structure.

**How to check:** count paragraphs via python-docx on source and output,
compute `out_n / src_n`, require `0.95 <= ratio <= 1.05`. Citable as
`standard: STANDARDS.md#para-ratio`.

### CJK density {#cjk-density}

The target-language output must have **CJK character ratio < 5%**
(`_gate_q3_glossary`: `ratio < 0.05`, `scripts/omo_loop.py:297`) — CJK
chars are counted with `[\u4e00-\u9fff]` over all paragraph text; up to 5%
is tolerated for brand names and proper nouns that legitimately preserve
source characters. Ratio ≥ 5% means the translation is incomplete.

**How to check:** `len(re.findall(r"[\u4e00-\u9fff]", out_text)) /
len(out_text) < 0.05` over python-docx paragraph text. Citable as
`standard: STANDARDS.md#cjk-density`.

### Punctuation hygiene {#punct-hygiene}

**Zero foreign-language punctuation** in the output (from `_gate_q5_punctuation`,
`scripts/omo_loop.py:241-252`): an English-target output must contain 0
characters from `[\u201c\u201d\u2018\u2019\uff0c\u3002\uff1a\uff1b\uff01\uff1f]`
(Chinese curly quotes, full-width comma/period/colon/semicolon/exclamation/
question); a Chinese-target output must contain 0 ASCII `[,.;:]` in body
text (they should be full-width).

**How to check:** regex scan over python-docx paragraph text per the target
language; any hit fails the step. Citable as `standard:
STANDARDS.md#punct-hygiene`.

### Drawing count {#drawing-count}

The output's drawing count must **equal the source's**: `src_count ==
out_count` (from `_gate_q4_image`, `scripts/omo_loop.py:223`), where counts
are `<w:drawing` occurrences in `word/document.xml` of each DOCX. A
mismatch means images were lost or duplicated in translation; a source with
0 drawings is incomparable (fails, not trivially passes).

**How to check:** `zipfile` read of `word/document.xml`, count
`"<w:drawing"` in source vs output, require equality (both > 0). Citable as
`standard: STANDARDS.md#drawing-count`.

### Opens in python-docx {#opens-docx}

The output DOCX must **open in python-docx with ≥ 1 paragraph** (from
`_gate_q1_functional`, `scripts/omo_loop.py:197-204`) — the functional
floor for any DOCX result: the pipeline exited 0, the file exists, and the
document object is readable and non-empty.

**How to check:** `from docx import Document; doc = Document(path);
len(doc.paragraphs) > 0`. Citable as `standard: STANDARDS.md#opens-docx`.

## Reference: format engines and inputs

Not bars — the structural-invariant facts scenario steps cite per format,
copied from `Omni_Re_Formatter/AGENTS.md:101-120` (16 outputs) and
`Omni_Pre_Processor/AGENTS.md:87` (inputs; count is 14 per OPP
README.md:12 — AGENTS.md's "13 inputs" is stale).

**ORF apply-md output formats (16) and their engines:**

| Format | Engine | Notes |
|--------|--------|-------|
| DOCX | pandoc (via `pypandoc-binary`) | Requires pandoc binary; auto-installed by `pypandoc-binary`. |
| ODT | pandoc | Same pandoc stack. |
| EPUB | pandoc | Same. |
| HTML | `markdown` lib (pure Python) | No pandoc needed. |
| RTF | pandoc | Same. |
| PDF | `weasyprint` (`[weasyprint]` extra) | Falls back to pandoc if available. |
| PPTX | `md2pptx` CLI (E2E-79) | .NET tool; falls back to pandoc when missing. |
| ICML | pandoc | Same. |
| SRT | `srt` lib | Subtitle format. |
| CSV | pandas | Pure Python. |
| XLSX | `openpyxl` (`[office]` extra) | Pure Python. |
| JSON | `json` stdlib | Direct dump. |
| IPYNB | `nbformat` (`[notebook]` extra) | Pure Python. |
| EML | `email` stdlib | Direct construction. |
| MSG | `aspose-email-foss` (`[email-output]` extra, GPLv3) | Commercial library; ORF recommends `.eml` instead. |
| XML | `lxml` | Custom XML serialization. |

**OPP input formats (14):** DOCX, PPTX, PDF, XLSX, CSV, JSON, XML, HTML,
EPUB, EML, MSG, images (OCR), IPYNB, `.url` (YouTube).

**Backfill formats (XLIFF path, 7 LIVE):** DOCX, PPTX, EPUB, HTML, ODT,
PDF, JSON — per the CLI Choice at `orf/commands/apply_xliff.py:26-31`
(not the stale README "5 formats" table); PDF backfill requires
`--skeleton-html` (apply_xliff.py:70-76); JSON uses the `xliff2json`
channel. `skeleton.zip` is produced by OPP only for DOCX/PPTX/EPUB.
