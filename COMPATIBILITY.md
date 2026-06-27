# Omni Suite — Compatibility Matrix

| Suite | OL    | OPP   | ORF   | Notes              |
|-------|-------|-------|-------|--------------------|
| 0.2.0 | 0.4.4 | 0.6.1 | 0.4.3 | Agent onboarding + E2E test health + CI infra |
| 0.2.1 | 0.4.5 | 0.6.2 | 0.4.4 | E2E-07, E2E-14, E2E-15, E2E-64, E2E-65 surgical cherry-picks |
| 0.2.2 | 0.4.5 | 0.6.3 | 0.4.4 | OPP v0.6.3 (stderr handler for verbose mode UX) |
| 0.2.3 | 0.4.6 | 0.6.4 | 0.4.5 | E2E-74/77/78/79/80/81/82/83 — full E2E-74/75/76 + shield/md2pptx/CSV/docling fixes |
| 0.2.4 | 0.5.6 | 0.6.6 | 0.4.5 | 13-issue batch: doc cleanup, OPP#8/9/10, OL#8/9/10/18, ORF#5/12/13 |
| 0.2.5 | 0.5.7 | 0.7.5 | 0.4.10 | Doc cleanup batch: OPP#17, OL#20, ORF#15, e2e#22 |
| 0.2.6 | 0.5.8 | 0.7.7 | 0.4.12 | Pipeline version sync |
| 0.2.7 | 0.5.9 | 0.7.9 | 0.4.15 | PDF→HTML→XLIFF→HTML→PDF pipeline: ORF#17 fix, OPP pdf2html, ORF html2pdf+xliff2pdf |
| 0.2.8 | 0.5.9 | 0.8.0 | 0.4.16 | PDF pipeline polish: OPP#20 (PDF2HTML integration), OPP#21 (skeleton <head>+page-break), OPP#22 (base64 filter), ORF#20 (options.css), ORF#21 (inline skeleton_html + CLI pdf format) |
| 0.2.9 | 0.5.9 | 0.8.1 | 0.4.16 | OPP#24 — PDF image position fix: strip inaccurate <img> coords from PyMuPDF HTML, rebuild with `page.get_image_info()` bbox + `doc.extract_image()` (preserves original encoding) |
| 0.3.0 | 0.5.9 | 0.8.2 | 0.4.16 | OPP#26 — zero body margin/padding + <p> margin in DEFAULT_PDF2HTML_CSS (eliminates +12pt Y image offset) |

## How to check installed versions

```bash
.venv_ol/bin/python -c "import importlib.metadata; print('opp:', importlib.metadata.version('omni-pre-processor')); print('ol:', importlib.metadata.version('omni-localizer')); print('orf:', importlib.metadata.version('omni-re-formatter'))"
cat VERSION
```

## Versioning policy

- Suite version follows semver (MAJOR.MINOR.PATCH)
- Submodule versions move independently
- A Suite release pins the 3 submodule versions tested together
- `setup_dev.sh` asserts submodule versions match this matrix
