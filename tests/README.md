# Omni_Suite E2E Tests

End-to-end tests for the complete OPP → OL → ORF localization pipeline.

## Overview

This directory contains integration and E2E tests that verify the complete workflow across all three components:

```
┌────────────────────────────────────────────────────────────────────────┐
│                     OMNI LOCALIZATION SUITE                             │
│                                                                        │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐               │
│  │     OPP     │───▶│     OL      │───▶│     ORF      │               │
│  │  (提取)     │    │   (翻译)    │    │   (回写)    │               │
│  └─────────────┘    └─────────────┘    └─────────────┘               │
│                                                                        │
│  Step 1: OPP        Step 2: OL            Step 3: ORF                  │
│  Extract →          Translate →           Backfill →                  │
│  MD + XLIFF +       MD + XLIFF            DOCX/PPTX                   │
│  skeleton.zip                                                    │
└────────────────────────────────────────────────────────────────────────┘
```

## Test Structure

```
tests/
├── conftest.py           # Shared fixtures and configuration
├── pytest.ini            # Pytest settings
├── test_e2e_pipeline.py  # Main E2E test suite
└── README.md            # This file
```

## Running Tests

### Run All Tests
```bash
cd <project-root>
pytest tests/ -v
```

### Run Only E2E Tests
```bash
pytest tests/ -v -m e2e
```

### Run Specific Component Tests
```bash
# OPP only
pytest tests/ -v -m requires_opp

# OL only
pytest tests/ -v -m requires_ol

# ORF only
pytest tests/ -v -m requires_orf
```

### Run with Coverage
```bash
pytest tests/ -v --cov=. --cov-report=term-missing
```

## Test Categories

### TestOmniPipelinePrerequisites
Verifies all three components (OPP, OL, ORF) can be imported and are available for testing.

### TestOPPExtraction
Tests OPP document extraction:
- DOCX to MD/XLIFF/skeleton/manifest
- Paragraph preservation
- Table extraction

### TestOPPToOLIntegration
Tests OPP → OL integration using mock translator:
- MD translation with frontmatter
- XLIFF translation with target-language attribute

### TestOLToORFIntegration
Tests OL → ORF integration:
- MD to DOCX conversion
- XLIFF to DOCX backfill

### TestMDChannelWorkflow
Tests complete MD-based workflow:
```
OPP (extract MD) → OL (translate MD) → ORF (MD → DOCX)
```

### TestXLIFFChannelWorkflow
Tests complete XLIFF-based workflow:
```
OPP (extract XLIFF + skeleton) → OL (translate XLIFF) → ORF (XLIFF backfill)
```

### TestFullPipeline
Tests complete pipeline with all three components using mock services.

### TestErrorHandling
Tests error cases:
- Missing input files
- Corrupted files
- Empty content
- Missing skeleton

### TestPipelinePerformance
Tests performance characteristics.

## Fixtures

### Sample Documents
- `sample_docx_path`: Creates a realistic DOCX with headings, paragraphs, tables
- `sample_pptx_path`: Creates a PPTX with title and content slides

### OPP Fixtures
- `opp_pipeline`: OPPPipeline instance with resource directory
- `opp_extraction_result`: Runs OPP on sample DOCX, returns output paths

### Mock OL Fixtures
- `mock_ol_translator`: MockOLTranslator that simulates translation

### Validation Fixtures
- `validate_docx_structure`: Validates DOCX ZIP structure and document.xml
- `validate_xliff_structure`: Validates XLIFF XML structure
- `validate_manifest`: Validates manifest.json structure

## Mock OL Translator

The `MockOLTranslator` class simulates LLM-based translation by:
- Adding `[→zh]` markers to H1 headings in MD files
- Adding `[ZH]` prefix to trans-unit targets in XLIFF
- Adding YAML frontmatter with translation metadata
- Preserving all original structure and formatting

This allows testing of the complete pipeline without requiring actual LLM API calls.

## Markers

| Marker | Description |
|--------|-------------|
| `e2e` | End-to-end tests exercising the complete OPP→OL→ORF pipeline |
| `slow` | Tests that take significant time to run |
| `requires_opp` | Tests that require the OPP component |
| `requires_ol` | Tests that require the OL component |
| `requires_orf` | Tests that require the ORF component |

## CI/CD

For CI environments:
```bash
pytest tests/ -v -m e2e -c pytest.ini:ci
```

## Development

For local development:
```bash
pytest tests/ -v -c pytest.ini:dev
```

## Writing New Tests

When adding new E2E tests:

1. Use the shared fixtures from `conftest.py`
2. Mark tests with appropriate `@pytest.mark` decorators
3. Follow the naming convention: `test_<what>_<scenario>`
4. Include docstrings explaining what is being tested
5. Use `assert` statements with clear error messages

Example:
```python
@pytest.mark.e2e
@pytest.mark.requires_opp
def test_my_new_feature(self, opp_pipeline, sample_docx_path, tmp_path):
    """Test description explaining what is verified."""
    # Arrange
    output_dir = tmp_path / "test_output"
    output_dir.mkdir(exist_ok=True)

    # Act
    result = opp_pipeline.process_file(...)

    # Assert
    assert result is not None
    assert len(result.errors) == 0
```
