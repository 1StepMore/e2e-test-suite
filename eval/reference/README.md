# QA Reference Set (Phase D1)

## Purpose
20 source documents with reference LLM translations, used to
calibrate the multi-judge LQA system (Phase D3).

## Structure
Each subdirectory contains one document:
- `{doc_id}_source.{ext}` — original document
- `{doc_id}_reference.{ext}` — reference LLM translation

## Document categories (20 docs total)
| Category | Lang pair | Count | Format |
|----------|-----------|-------|--------|
| legal_zh_en | zh→en | 3 | docx |
| legal_en_zh | en→zh | 2 | docx |
| product_catalog_zh | zh→en | 3 | md |
| literature_en | en→zh | 2 | docx |
| technical_doc_en | en→zh | 2 | md |
| email_mixed | mixed | 2 | eml |
| notebook_en | en→zh | 2 | ipynb |
| csv_zh | zh→en | 2 | csv |
| xml_en | en→zh | 2 | xml |
| **Total** | | **20** | |

## Reference LLM
- Currently: highest-priority model in the pool
- Held out from active translation pool (self-referential
  calibration prevention)
- Re-calibrate if reference model changes

## Building the reference set
1. Source documents: collect from public domain or synthetic
2. Run through OL with reference LLM (held out from pool)
3. Store translations as reference
4. Run multi-judge on reference set
5. Compute calibration metrics (Spearman, inter-judge)

## Status
[ ] Sources collected (20/20)
[ ] Reference translations generated (0/20)
[ ] Multi-judge run (0/20)
[ ] Calibration thresholds met (Spearman ≥ 0.7, agreement ≥ 60%)
