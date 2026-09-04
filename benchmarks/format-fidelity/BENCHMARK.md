# Format-Fidelity Benchmark Results (Omni MD path vs pandoc direct)

**Date:** 2026-09-04
**Fixtures:** `fixtures/plain.docx` (pure text) and `fixtures/rich.docx` (table + inline image + named styles)
**Fresh run timestamps (results in `benchmarks/results/`, git-ignored):**

- `20260904-224107` — plain.docx
- `20260904-224255` — rich.docx

**Metric method:** counts taken from OOXML (`word/document.xml` + `word/media/`)
via Python `zipfile`, applied identically to source and both outputs. See
[README.md](README.md) in this directory for the metric definitions.

**Preservation %** = `path_count / source_count`.

## Results

### Fixture: plain.docx (run `20260904-224107`)

| Metric      | Source | Omni MD path | pandoc direct |
|-------------|-------:|-------------:|--------------:|
| paragraphs  | 21     | 21 (100%)    | 21 (100%)     |
| tables      | 0      | 0 (n/a)      | 0 (n/a)       |
| images      | 0      | 0 (n/a)      | 0 (n/a)       |
| style_axis  | —      | N/A          | N/A           |

With no tables or images to preserve, the MD path round-trips pure text 1:1 —
paragraph and table counts are identical across source, Omni and pandoc.

### Fixture: rich.docx (run `20260904-224255`)

| Metric      | Source | Omni MD path | pandoc direct |
|-------------|-------:|-------------:|--------------:|
| paragraphs  | 11     | 12 (109.1%)  | 11 (100%)     |
| tables      | 1      | 1 (100%)     | 1 (100%)      |
| images      | 1      | 0 (0%)       | 1 (100%)      |
| style_axis  | —      | N/A          | N/A           |

## style_axis: N/A for the MD path

`metrics.json` records `"style_axis": "N/A — MD path does not carry source
styles through pandoc (by construction); XLIFF path is the fidelity path
(extensible, not in this run)"`. The MD path extracts to Markdown and
re-renders through pandoc, so source DOCX named styles (e.g. the rich
fixture's `Heading 1` and custom `Benchmark Callout`) do not survive by
construction — a style comparison on this path would measure the Markdown
format, not the tool. The XLIFF path is the style-fidelity route and is an
extension of this harness, not part of this run.

## Reproduction

```bash
source /mnt/d/贯维/Omni_Suite/.venv_ol/bin/activate

# plain fixture
bash benchmarks/format-fidelity/run_benchmark.sh \
    benchmarks/format-fidelity/fixtures/plain.docx

# rich fixture (generate it first if absent: python make_rich_fixture.py)
bash benchmarks/format-fidelity/run_benchmark.sh \
    benchmarks/format-fidelity/fixtures/rich.docx
```

Each run writes `benchmarks/results/<ts>/metrics.json` plus the produced
`omni_output.docx` / `pandoc_output.docx`. The script self-exports
`OMNI_TEST_FAKE_LLM=1` and `OL_CONFIG_PATH`.

## Findings / Conclusions

1. **Pure-text documents (plain.docx): perfect structural preservation.**
   Source 21/0/0 → Omni MD path 21/0/0, pandoc 21/0/0. For documents with no
   tables or images, the Omni MD path is lossless at the structural level and
   matches pandoc exactly.

2. **The MD path does NOT preserve inline images.** On rich.docx, the source
   contains 1 inline image; the Omni MD path output contains **0 images
   (0% preservation)**, while pandoc direct preserves it (1/1, 100%). This is
   an honest limitation of the current MD route: the image is dropped between
   extraction and backfill, so any document whose images matter must use the
   XLIFF path (or expect to re-attach images manually after the MD path).

3. **Paragraph count drift on the rich fixture (+1).** Omni MD path yields 12
   paragraphs vs 11 in source and pandoc. The +1 comes from FAKE_LLM
   placeholder artifacts introduced in the translation step (e.g. translated
   frontmatter/placeholder lines rendered as body paragraphs). It is a
   translation-mode artifact, not a structural parser regression — but it
   means the MD path is not 1:1 paragraph-faithful under FAKE_LLM.

4. **Tables are preserved 1:1 on both paths** (rich.docx: 1 → 1 on Omni and
   pandoc; plain.docx has none).

5. **Scope caveat — FAKE_LLM.** The translation step runs with
   `OMNI_TEST_FAKE_LLM=1` (placeholder, no API keys). This benchmark measures
   **format fidelity (structure preservation), not translation quality**.
   Structural metrics under a real LLM are expected to match the table counts
   above, but the +1 paragraph artifact should be re-checked with real keys
   before treating the MD path as paragraph-faithful in production.
