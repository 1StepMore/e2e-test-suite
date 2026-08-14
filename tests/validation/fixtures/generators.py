"""Synthetic fixture generators — canonical reference for validation scenarios.

Ported from ``tests/test_cross_format_e2e.py:142-334``
(``_create_synthetic_html/csv/json/xml/xlsx/md``) and the suite format-test
helpers (DOCX: ``tests/test_e2e_pipeline.py:573``, PPTX:
``tests/test_e2e_images.py:563``, EPUB: ``tests/test_e2e_opp_all_formats.py:603``).

NOT ported: ``_create_synthetic_pdf`` (reportlab dependency — the PDF case is
served by the committed static PDFs under ``scenarios/_fixtures/``).

All generators are deterministic and dependency-lazy (imports happen inside
the function body, matching the original helpers). The one pre-generated set
committed under ``scenarios/_fixtures/generated/`` was produced by calling
these functions as-is.
"""

import csv as csv_module
import json
import zipfile
from pathlib import Path

__all__ = [
    "_create_synthetic_html",
    "_create_synthetic_csv",
    "_create_synthetic_json",
    "_create_synthetic_xml",
    "_create_synthetic_xlsx",
    "_create_synthetic_md",
    "_create_synthetic_docx",
    "_create_synthetic_pptx",
    "_create_synthetic_epub",
]


def _create_synthetic_html(tmp_path: Path) -> Path:
    """Create a synthetic HTML test file with headings, paragraphs, lists."""
    html = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Synthetic Test Page</title></head>
<body>
<article>
<h1>Product Overview</h1>
<p>This synthetic HTML page contains <strong>structured content</strong> for
testing the OPP HTML extractor. It includes headings, paragraphs, and lists.</p>
<h2>Features</h2>
<p>The product supports the following features:</p>
<ul>
<li>Multi-format document processing</li>
<li>Neural machine translation with glossary support</li>
<li>Layout-preserving backfill</li>
</ul>
<h2>Getting Started</h2>
<p>Install the package and run the setup script to begin.</p>
</article>
</body>
</html>"""
    p = tmp_path / "test_synthetic.html"
    p.write_text(html, encoding="utf-8")
    return p


def _create_synthetic_csv(tmp_path: Path) -> Path:
    """Create a synthetic CSV test file with header row."""
    rows = [
        ["Product", "Category", "Price", "Stock"],
        ["Widget A", "Electronics", "19.99", "150"],
        ["Widget B", "Household", "9.50", "300"],
        ["Gadget X", "Electronics", "49.99", "75"],
        ["Tool Y", "Hardware", "29.00", "200"],
        ["Supply Z", "Office", "4.25", "1000"],
    ]
    p = tmp_path / "test_synthetic.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv_module.writer(f)
        writer.writerows(rows)
    return p


def _create_synthetic_json(tmp_path: Path) -> Path:
    """Create a synthetic JSON test file with nested objects and arrays."""
    data = {
        "product": {
            "name": "Synthetic Widget",
            "version": "3.2.1",
            "features": [
                {"id": 1, "name": "Auto-save", "enabled": True},
                {"id": 2, "name": "Cloud sync", "enabled": False},
                {"id": 3, "name": "Dark mode", "enabled": True},
            ],
            "metadata": {
                "author": "Test Team",
                "license": "MIT",
                "dependencies": ["requests", "lxml", "pillow"],
            },
        }
    }
    p = tmp_path / "test_synthetic.json"
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return p


def _create_synthetic_xml(tmp_path: Path) -> Path:
    """Create a synthetic XML test file with nested elements."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<catalog>
  <product id="P001">
    <name>Widget Pro</name>
    <category>Electronics</category>
    <price currency="USD">99.99</price>
    <description>A professional-grade widget for enterprise use.</description>
    <specs>
      <weight unit="kg">1.5</weight>
      <dimensions unit="cm">30x20x10</dimensions>
    </specs>
  </product>
  <product id="P002">
    <name>Widget Lite</name>
    <category>Electronics</category>
    <price currency="USD">49.99</price>
    <description>A lightweight widget for everyday tasks.</description>
    <specs>
      <weight unit="kg">0.8</weight>
      <dimensions unit="cm">20x15x8</dimensions>
    </specs>
  </product>
</catalog>"""
    p = tmp_path / "test_synthetic.xml"
    p.write_text(xml, encoding="utf-8")
    return p


def _create_synthetic_xlsx(tmp_path: Path) -> Path:
    """Create a synthetic XLSX test file with multiple sheets."""
    import openpyxl

    wb = openpyxl.Workbook()
    # Sheet 1
    ws1 = wb.active
    ws1.title = "Products"
    ws1.append(["Product", "Category", "Price", "Stock"])
    ws1.append(["Widget A", "Electronics", 19.99, 150])
    ws1.append(["Widget B", "Household", 9.50, 300])
    ws1.append(["Gadget X", "Electronics", 49.99, 75])
    # Sheet 2
    ws2 = wb.create_sheet("Summary")
    ws2.append(["Metric", "Value"])
    ws2.append(["Total Products", 3])
    ws2.append(["Total Value", 79.48])

    p = tmp_path / "test_synthetic.xlsx"
    wb.save(str(p))
    return p


def _create_synthetic_md(tmp_path: Path) -> Path:
    """Create a synthetic Markdown file for ORF-only conversion tests."""
    md = """---
source_lang: en
target_lang: zh
original_file: synthetic_test.md
processor: "FAKE_LLM"
version: "0.0.1"
translated_at: 2026-06-19T00:00:00Z
---

# Synthetic Document

## Introduction

This is a **synthetic markdown** file used for ORF conversion testing. It contains various
elements to exercise format converters.

## Features

- Feature 1: Multi-format support
- Feature 2: High performance
- Feature 3: Easy integration

## Data Table

| Name | Value | Status |
|------|-------|--------|
| Alpha | 100 | Active |
| Beta | 200 | Pending |
| Gamma | 300 | Active |

## JSON Data

```json
{"products": [{"name": "Alpha", "value": 100}, {"name": "Beta", "value": 200}]}
```

## Code Example

```
print("Hello, World!")
for i in range(3):
    print(f"Item {i}")
```

## Contact

For more information, please contact support@example.com.
"""
    p = tmp_path / "synthetic_test.md"
    p.write_text(md, encoding="utf-8")
    return p


# ============================================================================
# DOCX / PPTX / EPUB — ported from the suite format-test helpers
# ============================================================================

_DOCX_DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:t>Synthetic Document</w:t></w:r>
    </w:p>
    <w:p>
      <w:r><w:t>This is a synthetic DOCX fixture generated for validation scenarios.</w:t></w:r>
    </w:p>
    <w:p>
      <w:r><w:t>It contains plain paragraphs only, suitable for OPP extraction testing.</w:t></w:r>
    </w:p>
  </w:body>
</w:document>
"""

_DOCX_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

_DOCX_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""


def _create_synthetic_docx(tmp_path: Path) -> Path:
    """Create a minimal valid DOCX file (zip-based, no python-docx needed).

    Ported from ``tests/test_e2e_pipeline.py:573`` (``_create_minimal_docx``);
    the single paragraph was expanded to a title + two body paragraphs so the
    fixture carries extractable text content.
    """
    p = tmp_path / "test_synthetic.docx"
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", _DOCX_DOCUMENT_XML)
        zf.writestr("[Content_Types].xml", _DOCX_CONTENT_TYPES)
        zf.writestr("_rels/.rels", _DOCX_RELS)
    return p


def _create_synthetic_pptx(tmp_path: Path) -> Path:
    """Create a synthetic PPTX with two text slides (python-pptx).

    Ported from ``tests/test_e2e_images.py:563`` (``_create_pptx_with_images``)
    minus the embedded pictures — text-only keeps the committed fixture small;
    the picture-handling shapes are covered by the real ``meridian_q1.pptx``.
    """
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)

    blank_layout = prs.slide_layouts[0]

    slide1 = prs.slides.add_slide(blank_layout)
    slide1.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(1)).text = (
        "Slide 1"
    )
    slide1.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(3)).text = (
        "Synthetic PPTX fixture for validation scenarios."
    )

    slide2 = prs.slides.add_slide(blank_layout)
    slide2.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(1)).text = (
        "Slide 2"
    )
    slide2.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(3)).text = (
        "Second slide with plain text content."
    )

    p = tmp_path / "test_synthetic.pptx"
    prs.save(str(p))
    return p


def _create_synthetic_epub(tmp_path: Path) -> Path:
    """Create a minimal valid EPUB file (zip-based, no dependency).

    Ported verbatim from ``tests/test_e2e_opp_all_formats.py:603``
    (``_create_minimal_epub``).
    """
    container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>"""

    content_opf = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0"
         xmlns:dc="http://purl.org/dc/elements/1.1/">
    <metadata>
        <dc:identifier id="book-id">urn:uuid:test-epub-0000-0000-000000000000</dc:identifier>
        <dc:title>Test Document</dc:title>
        <dc:language>en</dc:language>
        <dc:creator>Test Author</dc:creator>
    </metadata>
    <manifest>
        <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
    </manifest>
    <spine>
        <itemref idref="chapter1"/>
    </spine>
</package>"""

    chapter1 = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Chapter</title></head>
<body><h1>Chapter Title</h1><p>Content.</p></body>
</html>"""

    p = tmp_path / "test_synthetic.epub"
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr("OEBPS/content.opf", content_opf)
        zf.writestr("OEBPS/chapter1.xhtml", chapter1)
    return p
