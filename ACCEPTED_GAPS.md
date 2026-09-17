# Accepted Gaps — Omni Suite

This file documents consciously accepted tradeoffs and known limitations.
Anything NOT listed here is expected to have an automated invariant (test or CI gate).

---

| Category | Gap | Reason | Accepted |
|----------|-----|--------|----------|
| OPP | PDF → XLIFF generation is intentionally blocked | PDF extraction produces no meaningful structural units for XLIFF. OPP raises ValueError with clear message. | 2026-06-20 |
| OPP | IPYNB (Jupyter Notebook) format not supported | Requires `nbformat` optional dependency. Marked xfail in tests. | 2026-06-20 |
| OPP | MSG (Outlook) extraction requires `extract-msg` pip package | Optional dependency. Tests skip gracefully when not installed. | 2026-06-20 |
| ORF | md2pptx CLI required for PPTX output from MD | Third-party tool, not always available. Tests skip gracefully. | 2026-06-20 |
| ORF | MD → MSG requires `aspose-email-foss` (GPLv3) | Commercial dependency. Use `.eml` format instead (fully supported). | 2026-06-20 |
| Testing | Real LLM tests (`test_e2e_real_llm.py`) excluded from CI gate | Require real API keys and network access. Run on separate nightly schedule. | 2026-06-20 |
| Testing | Observability, security, cross-format E2E tests slow (>5 min each) | Only run in full CI suite; not included in quick usability verifier. | 2026-06-20 |
| CLI | OL `--output-dir` has literal `--output-dir` as default placeholder | Known Typer display artifact. CLI silently writes to `--output-dir/<file>`. | 2026-06-20 |
| MCP | OPP/ORF MCP servers do not respond to stdio JSON-RPC even with `transport="stdio"` | **FIXED in `c6197f8`**: `scripts/mcp_bridge.py` implements a minimal MCP stdio server using raw JSON-RPC over stdin/stdout (no `mcp` library needed). Each MCP tool wraps the working CLI subprocess. The `mcp_matrix_verifier.py` uses the bridge via `asyncio.create_subprocess_exec` + raw stdio JSON-RPC. Verified: bridge responds to `initialize`, `ping`, and `tools/call` correctly. The FastMCP 3.4.2 stdio bug is bypassed entirely. | 2026-06-21 |
| MCP | CLI-vs-MCP equivalence not yet measured | Depends on the stdio gap above. Once MCP servers respond to stdio, `scripts/equivalence_checker.py` can compare CLI and MCP outputs cell-by-cell. Currently verifies CLI-vs-CLI determinism (passes: two runs with FAKE_LLM produce byte-identical outputs). | 2026-06-21 |
| Fidelity | FAKE_LLM replaces text completely, so fidelity scores against the original source are very low (0.01-0.60) for most formats | Fidelity is measured against the source, but the pipeline includes a translation step. With a real LLM that preserves content, scores would be higher. The infrastructure is in place; scores are meaningful when a real LLM is used. | 2026-06-21 |
| OPP | EPUB extraction is non-deterministic (8/8 `epub→*` cells produce different MD5 between runs) | **PARTIALLY FIXED in `f7d3316`**: `book.get_items()` sorted by name in `_extract_cover()`. Remaining non-determinism may exist in `_parse_html_elements` (HTML element iteration). **Root cause**: `ebooklib` returns items in non-deterministic order. **Affects**: all `epub→*` MD-path cells. **Impact**: equivalence check fails for these cells until full fix. | 2026-06-21 |

## Format Matrix Gaps (discovered 2026-06-21)

The full format matrix verifier (`scripts/format_matrix_verifier.py`) tests 195 cells
(11 inputs × 15 outputs MD path + 6 inputs × 5 outputs XLIFF path). 64 cells are
intentionally skipped for the reasons below; 131 pass; 0 fail.

| Path | Gap | Reason | Skip count |
|------|-----|--------|------------|
| MD | MD → JSON requires JSON code block or OPP key=value source | Generic prose MD has no JSON payload; md2json only handles structured input. | 11 |
| MD | MD → SRT requires timestamped cues | Subtitle format needs `00:00:00,000 --> 00:00:01,000` cues; generic MD has none. | 11 |
| MD | PPTX → XLSX / XLSX → PPTX | No logical content mapping between slides and tables; fixtures have neither. | 2 |
| MD | md2pptx CLI not installed | Third-party tool; 15 cells (one per input format). | 15 |
| XLIFF | OPP doesn't produce skeleton.zip for xlsx/html/epub/eml inputs | OPP's skeleton serializer only supports the 3 main office formats; web/email/text formats have no skeleton. | 20 |
| XLIFF | Cross-format XLIFF (e.g. PPTX→DOCX) not supported by ORF converters | ORF xliff2docx/pptx/etc. converters assume same-format skeleton. `--force` bypasses validation but converters still crash. Returns clear error after fix in `Omni_Re_Formatter@12f9769`. | 5 |
| XLIFF | `odf` is not a real ORF output format | Typo; ORF supports `odt` (OpenDocument Text), not `odf`. Renamed in `XLIFF_OUTPUTS`. | 0 (was 6 in earlier run) |
| Fixture | Hand-crafted minimal PDF | OPP can extract from any valid PDF; we use a 1-page hand-crafted PDF for matrix fixtures. | n/a |

**Verification:** `OMNI_TEST_FAKE_LLM=1 OMNI_TEST_FAKE_PANDOC=1 .venv_ol/bin/python scripts/format_matrix_verifier.py --out-dir test_artifacts/matrix --path-filter both --parallel 8 --timeout 120`

Expected: **131 PASS, 64 SKIP, 0 FAIL** in ~5-6 min.

## Validation Known Gaps (T-17)

The HUMAN-QUALITY bars in `scenarios/STANDARDS.md` are the published bar.
Two bars could not be met by the shipped pipeline. They were **not** silently
weakened: the pass-bar scenario asserts the LITERAL published threshold,
flagged `known_gap: true` at the step level (recorded, but excluded from the
scenario verdict), and the shipped weakened observation is isolated under
`scenarios/pipeline/known-gaps/` as a `known_gap: true` scenario — excluded
from the pass bar (never GREEN, never a blocker).

**2026-09-17: both root causes are fixed in code.**
T13-01 — `Omni_Localizer/src/ol_lqa/judge.py` no longer pads absent rubric
dimensions with 0 (`_remap_llm_fields` omits them so the weighted average
renormalizes; `EnsembleJudge` skips criteria no judge reported), and the judge
prompt in `Omni_Localizer/src/ol_pool/router.py` now asks for
`terminology_consistency` / `format_preservation`.
T13-02 — `Omni_Localizer/src/ol_md/pipeline.py` `is_complete()` / `missing`
now accept the restored original value as proof of presence, so
`level4_safe_fallback` no longer re-inserts content `unshield_markdown` had
already restored.
Covered by unit regressions in `Omni_Localizer/tests/test_lqa_judge.py` and
`Omni_Localizer/tests/test_md_repair_pipeline.py`.
The step-level `known_gap: true` markers and the `known-gaps/` scenarios are
KEPT until a tier-2 (real-key) run re-verifies the literal bar: dropping them
on hermetic/unit evidence alone would be a false green.

| Category | Gap | Reason | Accepted |
|----------|-----|--------|----------|
| Quality gate | `#drawing-count` published bar (`src == out`) not met on image-bearing MD-path outputs | **T13-02 — FIXED in code 2026-09-17 (pending tier-2 re-verification).** `ol translate-md` duplicated every `![..](..)` image reference: `is_complete()` / `missing` keyed presence on the shield_map **key** (`image_0000`), but the MD channel runs `unshield_markdown()` first, so the text holds the **value** — every entry therefore looked missing and `level4_safe_fallback` re-appended it (verified 2 refs in → 4 out, 12 → 24). Fixed in `Omni_Localizer/src/ol_md/pipeline.py`; regression `tests/test_md_repair_pipeline.py::TestShieldValueAwareCompleteness`. The literal bar is asserted in `scenarios/pipeline/pipeline-docx-md-docx.yaml` (step-level `known_gap: true`); the weakened observation (`out >= src`, no image lost) is isolated in `scenarios/pipeline/known-gaps/pipeline-docx-md-docx-drawing-count.yaml`. | 2026-09-13 |
| Quality gate | `#lqa-threshold` published bar (`judge_overall >= 4.0` on /5) unreachable | **T13-01 — FIXED in code 2026-09-17 (pending tier-2 re-verification).** Two compounding causes: (a) `_remap_llm_fields` defaulted every absent rubric field to 0, pushing `terminology_consistency` (0.20) + `format_preservation` (0.15) weight into the normalizing denominator while contributing nothing to the numerator, capping `judge_overall_score` at 3.25/5 on perfect scores; (b) the judge prompt never asked for those two dimensions at all. Fixed in `Omni_Localizer/src/ol_lqa/judge.py` (`_remap_llm_fields`, `EnsembleJudge`) and `Omni_Localizer/src/ol_pool/router.py` (prompt); regression `tests/test_lqa_judge.py::TestPartialFieldRenormalization`. The literal bar is asserted in `pipeline-docx-md-docx.yaml`, `pipeline-docx-md-epub.yaml`, `pipeline-pptx-md-pptx.yaml` (step-level `known_gap: true`); the weakened four-dimension average is isolated in `scenarios/pipeline/known-gaps/pipeline-docx-md-docx-lqa.yaml`. | 2026-09-13 |

**Isolation mechanics:** a scenario-level `known_gap: true` yields status
`known-gap` (never drives a nonzero exit, never a blocker); a step-level
`known_gap: true` failure is excluded from its scenario's verdict. The
contract lint (`run_validation.py --check`) enforces the location invariant:
`known_gap: true` scenarios live ONLY under a `known-gaps/` directory, and
every scenario under `known-gaps/` declares the flag.
