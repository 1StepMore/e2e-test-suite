# Golden File Infrastructure — xliff2docx Regression Testing

This directory stores golden (reference) files for xliff2docx regression tests.
Golden files are the expected output that tests compare against to detect
regressions after code changes.

## How to Capture

Run tests with `--golden-capture` to generate golden files from the current
output:

```bash
pytest tests/ --golden-capture
```

This copies each test's actual output to `tests/golden/xliff2docx/` for future
comparison. The golden files are named after the test that produced them.

## How to Verify

Golden verification is **on by default**. Running tests normally compares actual
output against the stored golden files:

```bash
pytest tests/
```

If output differs from the golden reference, the test fails with a descriptive
error message.

To explicitly request verification:

```bash
pytest tests/ --golden-verify
```

To skip verification (useful during development or when intentionally changing
output without recapturing yet):

```bash
pytest tests/ --no-golden-verify
```

## Comparison Modes

Tests choose a comparison mode when calling `assert_golden_identical()`:

| Mode | Comparison | Use Case |
|------|-----------|----------|
| `byte` | SHA-256 hash (strict) | Binary files, exact reproducibility |
| `paragraph` | Paragraph count | Text/MD files, structural consistency |
| `docx-paragraph` | DOCX paragraph-level text | DOCX output, semantic comparison |

- **`byte` mode** is the strictest — any bit-level change triggers failure.
  Use this for verifying bit-exact reproducibility of binary outputs.
- **`docx-paragraph` mode** is semantic — it compares paragraph text content
  via python-docx, ignoring formatting differences that don't affect meaning.
  Use this when the exact formatting engine (pandoc version, etc.) may vary.
- **`paragraph` mode** is lightweight — it only checks structural consistency
  (same number of paragraphs). Use this for quick smoke tests.

## When to Recapture

Recapture golden files after **intentional, verified changes** to the output:

1. Make your code changes
2. Run tests with `--golden-capture` to update golden files:
   ```bash
   pytest tests/ --golden-capture
   ```
3. Review the captured golden files to confirm they match expectations
4. Commit both the code changes and the updated golden files together

**Do NOT recapture** when tests fail due to bugs — fix the bug first, then
verify the output is correct before recapturing.

## Golden File Cleanup

If a test is removed or renamed, its associated golden file becomes orphaned.
Remove orphaned golden files manually:

```bash
# List golden files (expect one per active test)
ls tests/golden/xliff2docx/*.docx
```

## Directory Structure

```
tests/golden/
└── xliff2docx/
    ├── README.md         # This file
    ├── .gitkeep          # Placeholder to track directory in git
    └── *.docx            # Golden DOCX files (captured via --golden-capture)
```
