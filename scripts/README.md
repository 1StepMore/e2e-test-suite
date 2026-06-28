# Scripts — Omni Suite Dev Utilities

A collection of developer utilities for the Omni Suite pipeline.

| Script | Purpose | When to use |
|--------|---------|-------------|
| `bumpversion.py` | Bump version across OPP, OL, ORF simultaneously (patch or minor). | Before a release to keep all submodule versions in sync. |
| `check_readiness.py` | Production-readiness checker. Auto-verifies all 🔧 items from PRODUCTION_READINESS.md and reports pass/fail per version (V1..V11). | Before a production deployment or release cut. |
| `corpus_generator.py` | Generate a real-world document corpus with tables, images, complex formatting. Lives in `test_corpus/` at the suite root (idempotent). | When you need realistic test documents for matrix or regression testing. |
| `equivalence_checker.py` | Compare outputs from two matrix runs (e.g. CLI vs MCP) to verify equivalent results. | After changing a transport layer (CLI/MCP) to confirm output parity. |
| `fidelity_checker.py` | Content fidelity checker for the format matrix. Compares source/output text, tables, and image counts, computing preservation scores. | During matrix verification to quantify output quality. |
| `format_matrix_verifier.py` | Engine of the Omni Suite self-driven loop. Iterates the realistic input × output × transport matrix, exercises each cell end-to-end, and reports a markdown matrix table. | Full pipeline format-matrix regression testing. |
| `install_md2pptx.sh` | Clone `MartinPacker/md2pptx` to a stable path, make it executable, symlink to `~/.local/bin`. Idempotent. | One-time setup for MD → PPTX conversion support. |
| `mcp_matrix_verifier.py` | Runs the same 195 cells as the CLI matrix but via MCP tool calls instead of subprocess CLI invocations. | Testing MCP server integration and comparing against CLI baseline. |
| `omo_loop.py` | L3 OMO loop wrapper for Omni Suite. Runs OPP→OL→ORF pipeline, checks 5-6 cheap gates, accumulates consecutive green cycles, and diagnoses red cycles. | Automated iterative improvement / self-driven loop. |
| `phase1_runner.py` | Phase 1 comprehensive format matrix test runner. Tests OPP→OL→ORF across all input formats, output formats, language pairs, and pipeline paths. | Batch pipeline verification across the full format matrix. |
| `setup_dev.sh` | Omni Suite dev environment setup. Detects OS + Python version, creates/activates shared venv, installs all modules in editable mode, copies `.env.example`, verifies pandoc. | First-time setup on a new machine or after a fresh clone. |
| `sync_shallow.sh` | **DEPRECATED** — stub that errors with a clear message. Previously synced git submodules; OPP/OL/ORF are now regular top-level directories. | Should not be used; kept for reference. |
| `sync_version_docs.py` | Sync version tables in top-level docs (README, AGENTS, COMPATIBILITY) from `pyproject.toml`. Single source of truth. | After version bumps, to keep documentation in sync. |
| `test_setup_dev_layout.sh` | Tests for `setup_dev.sh` WORKSPACE_ROOT layout detection (e2e#18). Verifies child layout and standalone layout detection. | After modifying `setup_dev.sh` to verify layout detection still works. |
| `validate_docx_rids.py` | Validate that all `<w:drawing>` rId references exist in `<Relationships>` for a given DOCX file. | Debugging broken image references in DOCX output. |
| `verify_mcp.py` | MCP smoke test orchestrator. Runs the comprehensive MCP smoke test suite and reports per-module results. | After MCP server changes to confirm all tools respond correctly. |
| `verify_usability.py` | Thin pytest orchestrator for usability verification. Runs focused test suites per module, reports a pass/fail matrix. Exits 0 only if ALL groups pass. | Quick sanity check that all modules are basically functional. |

> **Note**: The `turnkey/` subdirectory contains additional deployment/automation scripts.
