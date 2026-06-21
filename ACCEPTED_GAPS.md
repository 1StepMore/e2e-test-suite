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
| MCP | OPP/OL/ORF MCP servers do not accept stdio JSON-RPC in this environment | All 3 servers use `fastmcp 3.4.2` and call `_mcp.run()` without `transport="stdio"`. Manual test: server starts, reads stdin, produces no stdout response, exits 0. MCP matrix (`scripts/mcp_matrix_verifier.py`) cannot run end-to-end until servers are patched to explicitly set `transport="stdio"` or the fastmcp default is changed. **Affects**: MCP transport dimension of the 4-dimension matrix (CLI happy-path covered, MCP blocked). | 2026-06-21 |
| MCP | CLI-vs-MCP equivalence not yet measured | Depends on the stdio gap above. Once MCP servers accept stdio, `scripts/equivalence_checker.py` can compare CLI and MCP outputs cell-by-cell. Currently it can only verify CLI-vs-CLI determinism (which passes: two runs with FAKE_LLM produce identical outputs). | 2026-06-21 |
| Fidelity | FAKE_LLM replaces text completely, so fidelity scores against the original source are very low (0.01-0.60) for most formats | Fidelity is measured against the source, but the pipeline includes a translation step. With a real LLM that preserves content, scores would be higher. The infrastructure is in place; scores are meaningful when a real LLM is used. | 2026-06-21 |

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
