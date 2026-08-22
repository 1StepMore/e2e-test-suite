---
name: omni-deep-modules
description: Omni Suite deep-module refactoring practice (from the 七阶段 methodology, Ousterhout's Philosophy of Software Design). Load when refactoring Omni_Pre_Processor/src/opp/, Omni_Localizer/src/, or Omni_Re_Formatter/src/orf/, adding a feature that crosses multiple modules, or reviewing module shape — find shallow module clusters, merge into deep modules, lock behavior with module-boundary integration tests.
author: Omni Suite
version: 1.0.0
---

# Omni Suite Deep Modules Skill

> **Deep module** = small public interface + large hidden implementation
> (John Ousterhout). Agents cannot "remember" the codebase — every session
> rebuilds the map. Deep modules let an agent read the interface and navigate
> without tracing import/export chains. Shallow modules (interface ≈
> implementation, lots of thin glue) make agents get lost and make changes
> accidentally break structure.
>
> **Why now (human side)**: in the AI era the human's cognitive load is
> *rising* — the agent changes code constantly, so the "internal code map"
> you maintain in your head keeps invalidating. Deep modules lower that
> load: remember the interface, not the implementation map.

## When to load

- Refactoring `Omni_Pre_Processor/src/opp/`, `Omni_Localizer/src/`, or
  `Omni_Re_Formatter/src/orf/` — especially merging "small, scattered,
  coupled" module groups.
- Adding a feature that touches 2+ existing modules (check whether the new
  code should be one deep module instead of three thin ones).
- Reviewing module shape before a large change (the AX-first lens: module
  shape IS agent experience).
- Writing the module-sketch section of a plan/PRD.

## Module map (verified 2026-08)

Interface truth lives in the SOURCE + `docs/agent-pipeline-guide.md` +
per-module `AGENTS.md` structure sections (NOT the tool counts — see
"Known drift"). The generated inventory `docs/dev/doc-inventory.md`
(regenerate: `python3 scripts/doc_inventory.py`; verify:
`python3 scripts/doc_inventory.py --check`) is the doc freshness signal.

### OPP — Omni_Pre_Processor/src/opp/

- **DEEP exemplars**: `extractors/docx.py` (603L, 3 public methods),
  `extractors/html/__init__.py` (546L dual-path), `extractors/pdf.py`
  (428L), `pipeline.py` (517L — `OPPPipeline` = 7 public methods over the
  15-extractor registry; the natural module boundary), `markdown/generator.py`
  (347L, 2 public methods), `xliff/generator.py` (466L), `mcp/security.py`
  (`PathValidator`, 166L).
- **SHALLOW clusters**: `commands/mcp.py` (27L pure delegator),
  `extractors/{ipynb,audio,youtube,xlsx}.py` (79–131L thin wrappers over
  third-party libs), `mcp/tools/{ping,save_skeleton,detect_format,get_capabilities}.py`,
  `contracts/*.py` (Pydantic data shapes, zero behavior), `channels/*.py`
  (36–85L UNUSED legacy formatters not wired into the pipeline).
- **MCP surface**: 9 tools registered in `mcp/server.py` `_TOOL_SCHEMAS`
  (docs say 7 — drift). Boundary tests: `tests/mcp/` (9 files) +
  `tests/extractors/` (4 files) + `scenarios/*.yaml` (6 tier-1; run via
  `python scripts/validation/run_validation.py --repo opp --tier 1`).
- **Interface truth**: `Omni_Pre_Processor/docs/API.md` +
  `Omni_Pre_Processor/docs/ARCHITECTURE.md` (NOT the
  stale AGENTS.md tool counts).

### OL — Omni_Localizer/src/

- **DEEP exemplars**: `ol_pool/router.py` (1084L — `ModelPool` public
  surface = 3 async methods translate/judge/profile + metrics +
  get_instance; THE canonical exemplar), `ol_lqa/quality_gates.py` (651L —
  `run_quality_gates` orchestrator over 8 gates), `ol_tm/service.py`
  (`TMService`, 292L), `ol_terminology/glossary_class.py` (`Glossary`
  227L, 4 public methods), `ol_xliff/parser.py` (366L),
  `ol_mcp/translate_file.py` (281L OPP→OL→ORF subprocess orchestration).
- **SHALLOW**: `ol_mcp/*.py` per-tool wrappers (INTENTIONAL thin facade
  over ol_pool/ol_md/ol_terminology/ol_tm — the module-boundary
  integration-test boundary), `ol_md/repair/level1.py` (17L) +
  `level4.py` (39L), `ol_routing/router.py` (49L legacy superseded by
  litellm Router), `ol_cli.py` (183L aggregator).
- **Pipeline stages (6)**: shield (`ol_md/shield.py`) → translate
  (`ol_pool/router.py`) → repair (`ol_md/pipeline.py` + `repair/level1..4.py`;
  XLIFF twin `ol_xliff/`) → unshield → postproc (`ol_post/punctuation.py`)
  → quality gates (`ol_lqa/quality_gates.py`).
- **MCP surface**: 21 tools via `TOOL_REGISTRY` + `_register_tool`
  decorator in `ol_mcp/tools.py` (724L). Tests flat but named per module
  boundary: `test_model_pool_*.py`, `test_md_repair_level*.py`,
  `test_quality_gates.py`, `test_ol_mcp*.py`.
- **Interface truth**: AGENTS.md 21-tool table + 6-stage diagram + 8
  quality-gate table; `docs/ARCHITECTURE.md` §1 module map. Scenarios:
  5 tier-2 in `scenarios/` (real LLM keys).

### ORF — Omni_Re_Formatter/src/orf/

- **DEEP exemplars**: `channels/xliff2docx/` (package facade —
  `XLIFF2DOCXConverter` over 773L + 5 submodules parser/matcher/images/
  writer/styles; the cleanest Ousterhout exemplar), `channels/md2docx.py`
  (470L, 3-method surface), `skeleton/inline_formatting.py` (616L shared
  inline engine), `mcp/security.py` (`PathValidator`).
- **SHALLOW**: `agents/specialists/*.py` (4 × 62–75L if/elif dispatch;
  `FormatSpecialist` claims 16 formats but converts only 3 —
  behavior/declaration mismatch), `mcp/tools/{ping,batch_convert,detect_format,info,get_capabilities}.py`
  (27–183L), `mcp/auth.py` (24L), `converters/options.py` (pure data).
- **REFACTOR TARGETS**: `channels/xliff2pptx.py` (704L monolith → split
  like xliff2docx), `foreman.py decompose_job()` is a stub returning
  `[job]`, duplicated format→module dispatch across 5+ files
  (`commands/apply_md.py`, `get_capabilities.py`, `foreman.py
  route_to_specialist`, `FormatSpecialist.convert`, `security.py
  ALLOWED_EXTENSIONS`).
- **MCP surface**: 7 tools in `mcp/server.py` (docs say 6 — drift).
  Foreman/Specialist agent layer NOT on the MCP/CLI hot path (MCP tools
  call CLI subprocess via `mcp/common.py run_cli_command`).
- **Boundary tests**: `test_*_channel.py` per channel +
  `test_orf_mcp_server.py` + `test_mcp_apply_md_xliff_parity.py` +
  `scenarios/` (6 tier-1). Interface truth: AGENTS.md +
  `scenarios/STANDARDS.md` format-engine table (with "registry > docs"
  caveat).

### Known drift to flag (don't treat stale docs as truth)

- OPP `pipeline.py:66` registers `PDF2HTMLExtractor` for
  `FormatType.PDF` (`extractors/pdf.py` shadowed); OPP AGENTS.md layout
  tree mentions `channels/md_bus.py`, `parsers/` that don't exist.
- ORF AGENTS.md "MCP tools (6 total)" and suite docs ("34 tools",
  "7 + 8 + 6 = 21") are stale — source truth is **OPP 9 / OL 21 / ORF 7
  = 37**. `python3 scripts/doc_inventory.py --check` enforces this.

## Procedure

Aligned with the methodology's 5-step "improved code-base architecture"
(预防: PRD-stage module sketch — new code starts deep; 治疗: this procedure
— fix existing bad modules):

1. **Explore for friction points** (explore mode, targeted area or
   full-library scan). Record: how many small files must you jump to
   understand one concept? Which modules have interface ≈ implementation
   (shallow)? Which pure functions were extracted "for testability" but the
   bug lives at the call site? Which coupled modules carry integration risk?
2. **List candidates WITHOUT designing interfaces.** Circle clusters that
   *share a concept and are coupled*. Do not design interfaces yet — that
   comes after the user picks.
3. **User selects one candidate** (B3 decides).
4. **Parallel divergent interface design.** Spawn multiple subagents to
   independently produce **maximally divergent** interface proposals —
   diversity is the point (you can mix the best parts later). The
   convergence is a human judgment call, not a merge of the first two.
5. **Recommend / mix → refactor RFC.** Land the chosen interface as a
   GitHub issue/RFC → Kanban breakdown with blocking links (methodology
   stage 5: one issue = one verifiable commit).
6. **Merge into the deep module.** Combine the cluster behind ONE small
   interface. Omni's interface truth: `docs/agent-pipeline-guide.md` (MCP
   tool signatures), `CONTRACT.md` (OPP→OL→ORF handoff), per-module
   `AGENTS.md` structure sections. Watch-lists: OPP `commands/` +
   `extractors/` thin wrappers + UNUSED `channels/*.py` (candidates to
   remove or wire, not to deepen); OL `ol_mcp/*.py` (deliberately thin
   facade — keep thin *by design*, lock at the TOOL_REGISTRY boundary);
   ORF duplicated format→module dispatch across `commands/apply_md.py`,
   `get_capabilities.py`, `foreman.py route_to_specialist`,
   `FormatSpecialist.convert`, `security.py ALLOWED_EXTENSIONS` (consolidate
   the dispatch, not the channels). Good exemplars already deep: the
   OPP/OL/ORF DEEP lists above.
7. **Lock behavior at the module boundary + verify + sync.** Integration
   tests exercising the module's public interface (input → observable
   output/effect), NOT unit tests per merged internal function. The
   MCP/CLI tool surface is the ultimate boundary test: a tool call asserting
   on `{success, data}`. Then: full suite green (per-module `make test`, or
   suite `make test`), `lsp_diagnostics` clean, doc layer synced
   (`docs/agent-pipeline-guide.md` / per-module `AGENTS.md` if the interface
   changed) + inventory (`python3 scripts/doc_inventory.py` then
   `python3 scripts/doc_inventory.py --check`).

## Guardrails

- **⚠️ The testability-extraction trap (LLM's most common bad refactor).**
  LLMs habitually say "let's extract this so it's testable" and pull out a
  pure function — but the real bug usually lives at the **call site** (how
  the frontend calls the backend, how the backend calls the CLI). Extracted
  small functions are shallow modules; the tests then lock the *shape*, not
  the *behavior*. Detection heuristic: **if after extraction you still need
  a pile of mocks to test it, you extracted wrong** — the direction should
  be the opposite: wrap the whole flow into one big service (a deep module),
  not peel off a testable fragment.
- **Never merge for merging's sake.** A module is shallow only if its
  interface fails to hide complexity from callers. Small
  single-responsibility modules that are easy to navigate are fine — the
  pathology is *scattered, coupled, thin* clusters. OPP's thin
  `extractors/{ipynb,audio,youtube,xlsx}.py` wrappers are fine as-is (they
  hide third-party libs behind `ExtractorBase`).
- **Preserve the public contract.** MCP tool names, parameters, and the
  error envelope are stability-bound (`docs/API_STABILITY.md`,
  `docs/ERROR_CODES.md`, `CONTRACT.md`) — internal merges must not change
  them.
- **Tests first for refactors** (characterization): pin current observable
  behavior with boundary tests BEFORE merging; keep them green throughout.
- **Deep-module tests prefer the boundary**, not internals — per the
  methodology, read tests instead of implementations (gray-box view).

## Relationship to other skills

- `omni-docmap` — after any refactor that changes a documented interface,
  follow its code-to-doc dependency map (Part B impact matrix). Regenerate
  + check the inventory: `python3 scripts/doc_inventory.py` then
  `python3 scripts/doc_inventory.py --check`.
- `omni-validation` — add/update a validation scenario when the merge
  changes observable behavior
  (`python scripts/validation/run_validation.py --repo {opp,ol,orf} --tier 1`),
  and run `python scripts/validation/coverage_audit.py` so every live MCP
  tool stays scenario-exercised.
- `omni-issue-pr` — one issue = one verifiable commit; land refactors as
  RFC issues with blocking links.
