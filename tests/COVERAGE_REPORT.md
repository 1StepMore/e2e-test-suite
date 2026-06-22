# Omni Suite E2E Test Coverage Report

Generated: 2026-05-28
Goal: 100% coverage of OPP → OL → ORF pipeline

---

## Current Test Coverage Summary

| Component | Unit Tests | E2E Tests | Total |
|-----------|-----------|-----------|-------|
| OPP (Omni Pre-Processor) | 632 | 20 | 652 |
| OL (Omni Localizer) | 481 (6 collection errors) | 16 | 497 |
| ORF (Omni Re-Formatter) | 318 | 20 | 338 |
| **Total** | **1431** | **56** | **1487** |

---

## Coverage Matrix

### OPP - Omni Pre-Processor

| Input Format | Unit Tests | E2E Test | Status |
|--------------|------------|-----------|--------|
| DOCX | ✓ test_docx_extractor.py | ✓ test_e2e_pipeline.py | ✅ |
| PPTX | ✓ test_pptx_extractor.py | ✓ test_e2e_pipeline.py | ✅ |
| PDF | ✓ test_pdf_extractor.py | ✓ test_e2e_pipeline.py | ✅ |
| XLSX | ✓ test_xlsx_extractor.py | ❌ | 🔴 |
| CSV | ✓ test_csv_extractor.py | ❌ | 🔴 |
| JSON | ✓ test_json_extractor.py | ❌ | 🔴 |
| XML | ✓ test_xml_extractor.py | ❌ | 🔴 |
| HTML | ✓ test_html_extractor.py | ❌ | 🔴 |
| EPUB | ✓ test_epub_extractor.py | ❌ | 🔴 |
| EML (Email) | ✓ test_email_extractor.py | ❌ | 🔴 |
| MSG (Outlook) | ✓ test_email_extractor.py | ❌ | 🔴 |
| Image OCR | ✓ test_image_ocr_extractor.py | ❌ | 🔴 |
| IPYNB | ✓ test_ipynb_extractor.py | ❌ | 🔴 |
| YouTube URL | ✓ test_youtube_extractor.py | ❌ | 🔴 |
| Audio | ✓ test_audio_extractor.py | ❌ | 🔴 |

| Output Format | Unit Tests | E2E Test | Status |
|---------------|------------|-----------|--------|
| Markdown | ✓ test_md_generator.py | ✓ test_e2e_pipeline.py | ✅ |
| XLIFF 1.2/2.0 | ✓ test_xliff_generator.py | ✓ test_e2e_pipeline.py | ✅ |

| Features | Unit Tests | E2E Test | Status |
|----------|------------|-----------|--------|
| CLI | ✓ test_cli.py | ❌ | 🔴 |
| MCP Server | ✓ test_server.py (mcp/) | ❌ | 🔴 |
| Batch Processing | ✓ test_cli.py | ❌ | 🔴 |
| Skeleton Preservation | ✓ test_skeleton_preservation.py | ✓ test_e2e_pipeline.py | ✅ |
| Manifest Generation | ✓ test_manifest_generation.py | ✓ test_e2e_pipeline.py | ✅ |
| Inline Formatting | ✓ test_integration_inline.py | ✓ test_e2e_pipeline.py | ✅ |
| Image Handling | ✓ test_resource_manager.py | ✓ test_e2e_images.py | ✅ |
| Auto-detection | ✓ test_auto_detector.py | ❌ | 🔴 |
| Error Handling | ✓ test_error_handler.py | ✓ test_e2e_pipeline.py | ✅ |

### OL - Omni Localizer

| Input Format | Unit Tests | E2E Test | Status |
|--------------|------------|-----------|--------|
| Markdown | ✓ test_md_shield.py, test_md_repair_*.py | ✓ test_e2e_pipeline.py | ✅ |
| XLIFF | ✓ test_xliff_shield.py, test_xliff_repair_*.py | ✓ test_e2e_pipeline.py | ✅ |

| Output Format | Unit Tests | E2E Test | Status |
|---------------|------------|-----------|--------|
| Translated MD (with frontmatter) | ✓ test_frontmatter.py | ✓ test_e2e_pipeline.py | ✅ |
| Translated XLIFF | ✓ test_xliff_parser.py | ✓ test_e2e_pipeline.py | ✅ |

| Features | Unit Tests | E2E Test | Status |
|----------|------------|-----------|--------|
| 4-Layer Repair (MD) | ✓ test_md_repair_level*.py | ❌ | 🔴 |
| 4-Layer Repair (XLIFF) | ✓ test_xliff_repair_level*.py | ❌ | 🔴 |
| Content Shielding | ✓ test_md_shield.py, test_xliff_shield.py | ✓ test_e2e_pipeline.py | ✅ |
| LLM Routing (LiteLLM) | ✓ test_model_pool_failover.py | ❌ | 🔴 |
| TM Integration | ✓ test_tm_service.py | ❌ | 🔴 |
| Glossary | ✓ test_glossary_loader.py, test_term_extractor.py | ❌ | 🔴 |
| Judging (LQA) | ✓ test_lqa_judge.py, test_lqa_comet.py | ❌ | 🔴 |
| CLI | ✓ test_ol_cli.py, test_cli_batch.py | ❌ | 🔴 |
| MCP Server | ✓ test_ol_mcp.py | ❌ | 🔴 |
| Batch Processing | ✓ test_batch_processor.py | ❌ | 🔴 |
| Checkpoint/Resume | ✓ test_checkpoint.py, test_checkpoint_resume.py | ❌ | 🔴 |
| OpenCode Skill | ✓ test_opencode_skill.py | ❌ | 🔴 |
| Hermes Skill | ✓ test_hermes_skill.py | ❌ | 🔴 |

### ORF - Omni Re-Formatter

| Input | Unit Tests | E2E Test | Status |
|-------|------------|-----------|--------|
| MD + skeleton.zip | ✓ test_md2docx_channel.py etc. | ✓ test_e2e_pipeline.py | ✅ |
| XLIFF + skeleton.zip | ✓ test_xliff2docx_channel.py etc. | ✓ test_e2e_pipeline.py | ✅ |
| ImagePlacement JSON | ✓ test_image_manager.py | ✓ test_e2e_images.py | ✅ |
| Manifest.json | ✓ test_manifest_parser.py | ✓ test_e2e_pipeline.py | ✅ |

| Output Format | Unit Tests | E2E Test | Status |
|---------------|------------|-----------|--------|
| DOCX (MD) | ✓ test_md2docx_channel.py | ✓ test_e2e_pipeline.py | ✅ |
| PPTX (MD) | ✓ test_md2pptx_channel.py | ❌ | 🔴 |
| EPUB (MD) | ✓ test_md2epub_channel.py | ❌ | 🔴 |
| HTML (MD) | ✓ test_md2html_channel.py | ❌ | 🔴 |
| ODT (MD) | ✓ test_md2odt_channel.py | ❌ | 🔴 |
| PDF (MD) | ✓ test_md2pdf_channel.py | ❌ | 🔴 |
| RTF (MD) | ✓ test_md2rtf_channel.py | ❌ | 🔴 |
| ICML (MD) | ✓ test_md2icml_channel.py | ❌ | 🔴 |
| SRT (MD) | ✓ test_md2srt_channel.py | ❌ | 🔴 |
| XLSX (MD) | ✓ test_md2xlsx_channel.py | ❌ | 🔴 |
| CSV (MD) | ✓ test_md2csv_channel.py | ❌ | 🔴 |
| JSON (MD) | ✓ test_md2json_channel.py | ❌ | 🔴 |
| DOCX (XLIFF) | ✓ test_xliff2docx_channel.py | ✓ test_e2e_pipeline.py | ✅ |
| PPTX (XLIFF) | ✓ test_xliff2pptx_channel.py | ❌ | 🔴 |
| EPUB (XLIFF) | ✓ test_xliff2epub_channel.py | ❌ | 🔴 |
| HTML (XLIFF) | ✓ test_xliff2html_channel.py | ❌ | 🔴 |
| ODF (XLIFF) | ✓ test_xliff2odf_channel.py | ❌ | 🔴 |

| Features | Unit Tests | E2E Test | Status |
|----------|------------|-----------|--------|
| CLI | ✓ test_cli_phase2.py | ❌ | 🔴 |
| MCP Server | ✓ test_orf_mcp_server.py | ❌ | 🔴 |
| Batch Convert | ✓ test_cli_phase2.py | ❌ | 🔴 |
| Skeleton Backfill | ✓ test_xliff2docx_channel.py | ✓ test_e2e_pipeline.py | ✅ |
| Image Injection | ✓ test_image_manager.py | ✓ test_e2e_images.py | ✅ |
| Foreman/Specialist Agent | ✓ test_e2e_omni_pipeline.py | ❌ | 🔴 |
| HITL Approval | ✓ test_e2e_omni_pipeline.py | ❌ | 🔴 |
| Cloud (S3/Azure) | ✓ test_cloud_clients.py | ❌ | 🔴 |
| AI Layout Correction | ✓ test_layout_analyzer.py, test_overflow_corrector.py | ❌ | 🔴 |

---

## Missing E2E Coverage (Priority Order)

### 🔴 Critical - P0 (Must have for 100%)

1. **OPP: All input formats** - PPTX, PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, Image, IPYNB, YouTube, Audio
2. **OL: Real LLM integration test** - Model pool failover, TM, glossary, judging
3. **ORF: All output formats** - PPTX, EPUB, HTML, ODT, PDF, RTF, ICML, SRT, XLSX, CSV, JSON, XML, EML, MSG

### 🟡 Important - P1 (Should have)

4. **CLI tests for all components** - OPP/OL/ORF command-line interfaces
5. **MCP Server tests** - OPP MCP, OL MCP, ORF MCP
6. **Batch processing tests** - OL batch translate

### 🟢 Nice to have - P2

7. **Agent orchestration tests** - Foreman/Specialist
8. **Cloud integration tests** - S3/Azure
9. **Performance tests** - Large files, timeouts

---

## Full E2E Test Files Required

```
tests/
├── test_e2e_opp_all_formats.py      # PPTX, PDF, XLSX, CSV, JSON, XML, HTML, EPUB, EML, MSG, Image, IPYNB, YouTube, Audio
├── test_e2e_opp_cli.py             # OPP CLI
├── test_e2e_opp_mcp.py             # OPP MCP Server
├── test_e2e_ol_llm_integration.py   # Real LLM, TM, glossary, judging
├── test_e2e_ol_cli.py              # OL CLI
├── test_e2e_ol_mcp.py              # OL MCP Server
├── test_e2e_ol_batch.py             # OL batch processing
├── test_e2e_orf_all_formats.py      # PPTX, EPUB, HTML, ODT, PDF, RTF, ICML, SRT, XLSX, CSV, JSON, XML, EML, MSG
├── test_e2e_orf_cli.py             # ORF CLI
├── test_e2e_orf_mcp.py             # ORF MCP Server
├── test_e2e_orf_agents.py          # Foreman/Specialist
├── test_e2e_cloud.py               # S3/Azure
├── test_e2e_performance.py         # Large files, timeouts
└── test_e2e_pipeline.py            # ✅ Existing (core workflow)
└── test_e2e_images.py             # ✅ Existing (image positions)
```

---

## Recommended Test Count for 100% Coverage

| Category | Test Count |
|----------|-----------|
| OPP formats (13 input + 2 output) | ~150 tests |
| OPP CLI/MCP/Batch | ~50 tests |
| OL translation (MD + XLIFF) | ~80 tests |
| OL features (TM, glossary, judging) | ~60 tests |
| OL CLI/MCP/Batch | ~40 tests |
| ORF formats (17 output) | ~170 tests |
| ORF CLI/MCP/Agents | ~50 tests |
| Cross-component E2E | ~100 tests |
| Performance/Edge cases | ~50 tests |
| **Total** | **~750 E2E tests** |

---

## Next Steps

1. **Add test_e2e_opp_all_formats.py** - Cover all 13 input formats
2. **Add test_e2e_orf_all_formats.py** - Cover all 17 output formats
3. **Add CLI and MCP tests** for all components
4. **Verify with coverage report** - Ensure all code paths hit
