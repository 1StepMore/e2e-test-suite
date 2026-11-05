# Accepted Gaps — Omni Suite

This file documents consciously accepted tradeoffs and known limitations.
Anything NOT listed here is expected to have an automated invariant (test or CI gate).

---

| Category | Gap | Reason | Accepted |
|----------|-----|--------|----------|
| OPP | PDF → XLIFF generation is intentionally blocked | PDF extraction produces no meaningful structural units for XLIFF. OPP raises ValueError with clear message. | 2026-06-20 |
| OPP | IPYNB (Jupyter Notebook) format not supported | **OPP IPYNB extractor compatibility defect** (not merely a missing optional dependency); tracked and gated by `scenarios/opp/opp-ipynb-extract.yaml` under `OPP_IPYNB_OK`. | 2026-06-20 |
| OPP | MSG (Outlook) extraction requires `extract-msg` pip package | Optional dependency. Tests skip gracefully when not installed. | 2026-06-20 |
| ORF | md2pptx CLI required for PPTX output from MD | Third-party tool, not always available. Tests skip gracefully. | 2026-06-20 |
| ORF | MD → MSG requires `aspose-email-foss` (GPLv3) | Commercial dependency. Use `.eml` format instead (fully supported). | 2026-06-20 |
| ORF | MSG target fallback returns a `.msg` path while writing a hidden `.eml` (T-15) | `orf apply-md --target-format msg` is Aspose-gated. With Aspose absent it reports success and returns `output_path=.../out.msg` but writes a hidden temporary `.eml`. Recorded as a known gap (`known_gap: true`) and asserted by `scenarios/pipeline/known-gaps/pipeline-md-msg-eml-fallback.yaml`. | 2026-10-18 |
| Testing | Real LLM tests (`test_e2e_real_llm.py`) excluded from CI gate | Require real API keys and network access. Run on separate nightly schedule. | 2026-06-20 |
| Testing | Observability, security, cross-format E2E tests slow (>5 min each) | Only run in full CI suite; not included in quick usability verifier. | 2026-06-20 |
| CLI | OL `--output-dir` has literal `--output-dir` as default placeholder | Known Typer display artifact. CLI silently writes to `--output-dir/<file>`. **The defect still left physical evidence in the suite root on 2026-09-15: a root directory literally named --output-dir/ containing a stray real.md; that directory was removed 2026-10-18.** | 2026-06-20 |
| MCP | OPP/ORF MCP servers do not respond to stdio JSON-RPC even with `transport="stdio"` | **MECHANISM REMOVED — no bridge is involved.** `scripts/mcp_bridge.py` was deleted on 2026-06-22 (`5d163d4`); MCP stdio now runs over the native FastMCP server + `mcp.client.session.ClientSession` (`tests/contract/test_mcp_schemas.py:14`, `:154`). The old raw-JSON-RPC bridge description is historical. | 2026-06-21 (corrected 2026-10-18) |
| MCP | CLI-vs-MCP equivalence is gated at **verdict** level, not at **byte** level | **PARTLY OUTDATED — corrected 2026-10-12.** The original claim ("not yet measured; currently verifies CLI-vs-CLI determinism") no longer holds. `scripts/nightly_gap.py` now runs `format_matrix_verifier.py` and `mcp_matrix_verifier.py` as two independent channels and compares them **per cell** (`per_channel` baseline, DoD ③ "逐格一致"); the 2026-10-10 run reports both channels at `201 / 146 / 55 / 0`, identical. What is still **not** gated is byte-level comparison: `scripts/equivalence_checker.py` compares two runs by MD5 and its docstring scopes that to "two CLI runs" — no CLI↔MCP MD5 pass exists in the nightly gate. | 2026-06-21 (corrected 2026-10-12) |
| Fidelity | FAKE_LLM replaces text completely, so fidelity scores against the original source are very low (0.01-0.60) for most formats | Fidelity is measured against the source, but the pipeline includes a translation step. With a real LLM that preserves content, scores would be higher. The infrastructure is in place; scores are meaningful when a real LLM is used. | 2026-06-21 |
| OPP | EPUB extraction is non-deterministic (8/8 `epub→*` cells produce different MD5 between runs) | **PARTIALLY FIXED in `f7d3316`**: `book.get_items()` sorted by name in `_extract_cover()`. Remaining non-determinism may exist in `_parse_html_elements` (HTML element iteration). **Root cause**: `ebooklib` returns items in non-deterministic order. **Affects**: all `epub→*` MD-path cells. **Impact**: equivalence check fails for these cells until full fix. **2026-11-06: image-list ordering fixed** (`Omni_Pre_Processor/src/opp/extractors/epub.py` sorts `get_items_of_type(ITEM_IMAGE)` by name — same rationale as the cover sort; unit-locked in `tests/test_epub_extractor.py::test_image_extraction_order_is_deterministic`) **and ORF EPUB production made byte-deterministic** (`orf/channels/md2epub.py`: content-hash-derived `SOURCE_DATE_EPOCH` + uuid5 `dc:identifier`, unit proof `Omni_Re_Formatter/tests/test_apply_md_epub_deterministic.py` — two runs in different dirs → identical sha256). **Equivalence re-measurement 2026-11-06** (dual FAKE_LLM matrices + `equivalence_checker.py`): the END-TO-END cells remain MD5-divergent **by design** — OL's per-run frontmatter metadata (`translated_at` / `request_id`) differs each run, so cell-level byte equality is unreachable without removing per-run provenance (deliberate, out of scope). The ORF-writer half of this gap is closed: same input MD → identical EPUB bytes is proven at unit and real-content level. | 2026-06-21 (narrowed 2026-11-06) |

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
| XLIFF | ~~OPP doesn't produce skeleton.zip for xlsx/html/epub/eml inputs~~ → **only EML remains** | Superseded by the per-format rows below: EPUB, HTML and XLSX all produce skeletons now (`OPP#93`/`#94`, `ORF#65`/`#66`). EML has none, by decision — see "No skeleton producer for **EML** input" below. The original claim that OPP's serializer "only supports the 3 main office formats" stopped being true as of 2026-10-05. | 2026-06-21 (superseded 2026-10-05) |
| XLIFF | Cross-format XLIFF (e.g. PPTX→DOCX) not supported by ORF converters | ORF xliff2docx/pptx/etc. converters assume same-format skeleton. ~~`--force` bypasses validation but converters still crash~~ — **不再成立**：`--force` 对骨架格式校验的绕过已于 `Orf_Re_Formatter#64` 移除，跨格式请求**恒定失败**并指向 MD 路径（`orf apply-md`），不再产出任何产物。 | 23（当前 201 格口径；本段其余数字为 2026-06-21 快照，见下方 Count note） |
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
**2026-10-27: both literal bars re-verified by a tier-2 real-key round**
(`pipeline-docx-md-docx` 14/14 passed — LQA 4.85/5, drawings 2->2;
`pipeline-pptx-md-pptx` 11/11 — LQA 4.12/5). The docx scenario's step-level
waivers were removed 2026-10-30 and the epub/pptx LQA waivers 2026-11-06 —
the literal bars are now enforced directly by the pass-bar scenarios.
**2026-11-06 status**: T13-01 CLOSED (nightly 2026-11-01..04 passes Q2 at
4.93-4.95/5). T13-02 CLOSED (root causes split into a CI sequential-path
duplication and a model-mangled-ref loss; both fixed — see the T13-02 row
below and e2e-test-suite#244). The `known-gaps/` twins for both were
removed 2026-11-06; the literal bars are enforced directly.

| Category | Gap | Reason | Accepted |
|----------|-----|--------|----------|
| Quality gate | `#drawing-count` published bar (`src == out`) on image-bearing MD-path outputs | **T13-02 — CLOSED 2026-11-06 (e2e-test-suite#244). Two independent defects, both fixed:** (a) CI 翻倍 src=2 out=4 — CI pins OL concurrency=1; the sequential path ran `repair()` BEFORE `unshield_markdown()` (`Omni_Localizer/src/cli/translate_md.py`, opposite of the documented order), and `is_complete`'s non-strict check matched only the bare key (`ol_md/pipeline.py`), never the `[OL:IMG:xxxx]` marker form → level4 re-appended every original deterministically. Fixed by marker-form completeness + unshield-first order (+ dual-format placeholder recognition in `ol_core/repair/level2.py`). (b) 本地丢图 src=2 out=1 — the model mangled shielded image refs (underscores stripped inside the path, target-language text glued into the URL; poisoned cache entry `~/.omni_cache/ol/ffe2f7d4*.md` frozen 2026-11-05, backed up under `99-Tools/validation-scratch/omni-suite/p0b-poisoned-cache-backup/`) and the scenario-side normalize could not match them. Fixed by the post-unshield image-ref self-check (`ol_md/shield.py restore_image_ref_integrity`); the poisoned cache entries were deleted. Regressions: `tests/test_md_repair_pipeline.py::TestSequentialPathMarkerForm` + `::TestImageRefIntegritySelfCheck` (D1 red→green); OL full suite 1890 passed / 0 failed. Local tier-2 re-verification run `20261106-012511`: 14/14 passed, drawings 2->2 (match), LQA 4.99/5. The known-gaps twins were removed 2026-11-06; the literal bar is asserted and enforced directly in `scenarios/pipeline/pipeline-docx-md-docx.yaml` (Q4). CI nightly confirmation lands over the following nights. Historical root cause of the original 2026-09 duplication: `is_complete()` / `missing` keyed presence on the shield_map **key** (`image_0000`) while the MD channel runs `unshield_markdown()` first, so every entry looked missing and `level4_safe_fallback` re-appended it (verified 2 refs in → 4 out, 12 → 24); fixed in `Omni_Localizer/src/ol_md/pipeline.py` with regression `tests/test_md_repair_pipeline.py::TestShieldValueAwareCompleteness`. | 2026-09-13 (closed 2026-11-06) |
| Quality gate | `#lqa-threshold` published bar (`judge_overall >= 4.0` on /5) unreachable | **T13-01 — CLOSED 2026-11-06: fixed in code 2026-09-17; re-verified 2026-10-27 (LQA 4.85/5, `pipeline-docx-md-docx` 14/14) and by CI nightly 2026-11-01..04 (Q2 passes at 4.93-4.95/5); waivers removed docx 2026-10-30 / epub+pptx 2026-11-06 — the literal bar is enforced directly.** Two compounding causes: (a) `_remap_llm_fields` defaulted every absent rubric field to 0, pushing `terminology_consistency` (0.20) + `format_preservation` (0.15) weight into the normalizing denominator while contributing nothing to the numerator, capping `judge_overall_score` at 3.25/5 on perfect scores; (b) the judge prompt never asked for those two dimensions at all. Fixed in `Omni_Localizer/src/ol_lqa/judge.py` (`_remap_llm_fields`, `EnsembleJudge`) and `Omni_Localizer/src/ol_pool/router.py` (prompt); regression `tests/test_lqa_judge.py::TestPartialFieldRenormalization`. The literal bar is asserted in `pipeline-docx-md-docx.yaml`, `pipeline-docx-md-epub.yaml`, `pipeline-pptx-md-pptx.yaml`; the weakened four-dimension average lived in a `known-gaps/` twin scenario (removed 2026-11-06 once the literal bar held). | 2026-09-13 (closed 2026-11-06) |

| XLIFF | ~~HTML skeleton never reaches the XLIFF path~~ → **RESOLVED 2026-10-05** | **Was a wiring gap, not a capability gap — and it is now closed.** `HtmlExtractor` filled `ExtractionResult.skeleton_html` (a `str`) while the XLIFF gate tested `result.skeleton` (`bytes`), so HTML never got a `<stem>.skeleton.zip`. Fixed by `Omni_Pre_Processor#93` (`7d9b0aa`, produces the zip), with the MCP path's gate taught about HTML in `OPP#95` (`751b22e`) and `OPP#96` (`7e0a639`, skeleton-save failure no longer swallowed). ORF accepts the zip in `Omni_Re_Formatter#65` (`9e1b663`). Verified end to end: `html → html (xliff)` PASSES on both CLI and MCP with one `data-trans-unit-id` anchor per source block, and CLI/MCP skeletons are byte-identical. The stale skip rule was reclaimed in `e2e-test-suite#146` (`e849d52`). | 2026-10-04 (closed 2026-10-05) |
| XLIFF | No skeleton producer for **EML** input (XLSX resolved 2026-10-05) | **Deferred by decision, not an omission.** OPP's `EmailExtractor` produces exactly **one** trans-unit for the whole body (measured: `skeleton=None`, `paragraphs=1`) and mail carries no stylesheet or page geometry — the thing XLIFF exists to preserve. ORF has `md2eml` but no `xliff2eml`, and building one would preserve nothing the MD path does not already. Making this worthwhile first requires splitting the email extractor into multiple trans-units, which is the same low-ROI question one level up. Verified both ends still missing as of `OPP@dec5f85`. Was previously filed as "real capability debt, both ends missing" for XLSX **and** EML; the XLSX half is resolved (`OPP#94` `6c2a5d8` + `ORF#66` `33f2367` + `e2e-test-suite#150` `50776b6` — 5070-byte skeleton measured). **Resolved 2026-10-27**：OPP now emits `<stem>.skeleton.zip` (original bytes + `eml_map.json`) and ORF ships `xliff2eml`; the 6 `eml × *` XLIFF cells are now cross-format debt, not a missing-skeleton gap. | 2026-10-04 (narrowed 2026-10-05, resolved 2026-10-27) |
| ORF | Cross-format XLIFF backfill unsupported | ~~`--force` is best-effort only~~ → **现状已变更**：`--force` 对格式校验的绕过已移除（`Omni_Re_Formatter#64`，merge `baaebc2`）。实跑证其原产出是**改扩展名的源文件**（`cross.pptx` 被 `python-pptx` 拒开、`cross.epub` 缺 `mimetype`），比报错更糟；故跨格式现在恒定失败且**不产出文件**。`--force` 仍被接受以免调用方收到 "no such option"，但语义上只影响缓存检查。真正的跨格式支持是研究级工作（每种目标格式一套骨架模型）。 | 2026-10-05 |

**Count note (XLIFF channel, measured):** The XLIFF matrix is `XLIFF_INPUTS` × `XLIFF_OUTPUTS` = 6 × 6 = **36 cells per transport channel** (`scripts/format_matrix_verifier.py:163-173`). The MCP channel declares the same two sets and delegates every static skip decision to the CLI verifier's `_check_skip`; since e2e-test-suite#234 it also runs the CLI verifier's runtime MD→CSV table guard on the extracted MD (`mcp_matrix_verifier._md_csv_skip` → shared `MD_CSV_TABLE_SKIP_REASON`), so both channels classify identically. The 36 cells decompose as:

| Bucket | Cells | Reason string / rule |
|--------|-------|---------------------|
| Same-format (`docx→docx`, `pptx→pptx`, `xlsx→xlsx`, `html→html`, `epub→epub`) | 5 | — exercised for real |
| `pptx→xlsx`, `xlsx→pptx` | 2 | earlier fixture-content rules (`:215-216`) match **before** the cross-format rule, so these two are *not* booked as cross-format debt |
| **Cross-format** (`inp != outp`, minus the two above) | **29** | `XLIFF cross-format not supported by ORF converters` — computed `inp != outp`; all 29 = 23 non-EML + 6 EML-input, which are cross-format by definition now that the EML skeleton exists |

So `29` needs-cleanup cells per channel, `58` across both — exactly what the 2026-10-10 nightly run reports. **This supersedes the earlier "10 per channel" figure in this note**, which predated the XLIFF output set reaching its current 6 formats; likewise EML's share is **6**, not 4, and those six now sit in the cross-format bucket.

Historical context, unchanged: XLSX and HTML used to account for **8 skip cells per channel** here (4 each) and were both reclaimed once their channels actually shipped (`e2e-test-suite#146`, `#150`). `Omni_Pre_Processor#92` originally measured 19 across XLSX/HTML/EPUB/EML; EPUB's 5 were a **stale skip rule**, not a gap, reclaimed in `e2e-test-suite#140`. EML's 6 are now **cross-format debt like every other mismatched pair** (see its row above): since 2026-10-27 OPP produces the skeleton and ORF ships `xliff2eml`, so the remaining work is the same neutral-model/render stage the other 23 need.

**Why the cross-format bucket is structural, not a guard clause:** every `xliff2*` converter is a *same-container re-injector* — it reads the skeleton by format-specific internal paths (`xliff2pptx._load_pptx_skeleton`, `xliff2epub._load_epub_skeleton` read arbitrary ZIPs verbatim with **no** format check), rewrites text nodes, and repacks the same container. The skeleton *is* the output format. Genuine cross-format therefore needs, per source→target pair, a parse-into-neutral-model / render-into-target-container stage — which is what the MD path (`orf apply-md`, 16 outputs) already is, and why the refusal message points there. The three refusal layers (`apply_xliff.py` extension check `:232-245`, ZIP content check `:247-271`, converter `validate_input` gate `:397-405`) must **stay**: relaxing them does not produce a valid file, it reproduces the pre-`Orf_Re_Formatter#64` behaviour of writing source-format bytes under a target extension.

Note that the information needed to *detect* a mismatch does survive the round trip — OPP records the true source format in the manifest sidecar (`source.format`) — but it is **not** inside `skeleton.zip` (`skeleton.format` is always `"ZIP"`) and `apply-xliff` does not read the manifest. So reading the manifest would buy a better error message, not a conversion.

Both debt classes are deliberately left counted in `gap_units` — `EXEMPT_SKIP_REASONS` in `scripts/nightly_gap.py:65-74` is scoped by contract to fixture-content dependencies and explicitly excludes capability-class skips, so reclassifying them as exempt would hide real debt rather than resolve it. `gap_units` therefore stays above zero while these gaps stand; the rows above are the honest record, not a metric change.

**Isolation mechanics:** a scenario-level `known_gap: true` yields status
`known-gap` (never drives a nonzero exit, never a blocker); a step-level
`known_gap: true` failure is excluded from its scenario's verdict. The
contract lint (`run_validation.py --check`) enforces the location invariant:
`known_gap: true` scenarios live ONLY under a `known-gaps/` directory, and
every scenario under `known-gaps/` declares the flag.
