"""Generate a real-world document corpus with tables, images, complex formatting.

The corpus lives in test_corpus/ at the suite root and is generated idempotently.
Each document is more than a 'Hello, world.' — it has multiple sections, tables,
images, and formatting so the matrix can measure content preservation, not just
file existence.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parent.parent / "test_corpus"


def _png_bytes(width: int = 10, height: int = 10, color: str = "red") -> bytes:
    """Generate a small valid PNG using Pillow. Returns raw PNG bytes."""
    from PIL import Image
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _ensure_corpus_dir() -> Path:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    return CORPUS_DIR


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------

def generate_docx(dest: Path) -> None:
    """5 sections, 3 tables, 2 images, headings, lists, formatting."""
    from docx import Document
    from docx.shared import Inches, Pt

    d = Document()
    d.add_heading("Annual Report 2026", level=0)
    d.add_paragraph(
        "This is a complex document used by the Omni Suite format matrix "
        "to verify content preservation across the OPP/OL/ORF pipeline."
    )

    d.add_heading("Executive Summary", level=1)
    d.add_paragraph(
        "The Omni Suite delivers end-to-end document localization. "
        "This report covers the fiscal year results."
    )

    d.add_heading("Financial Highlights", level=2)
    table = d.add_table(rows=4, cols=3)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text = "Quarter"
    hdr[1].text = "Revenue"
    hdr[2].text = "Growth"
    for i, (q, r, g) in enumerate([
        ("Q1", "$1.2M", "+12%"),
        ("Q2", "$1.5M", "+25%"),
        ("Q3", "$1.8M", "+20%"),
    ], start=1):
        c = table.rows[i].cells
        c[0].text = q
        c[1].text = r
        c[2].text = g

    d.add_paragraph("")  # spacer
    d.add_picture(io.BytesIO(_png_bytes()), width=Inches(2))

    d.add_heading("Methodology", level=1)
    p = d.add_paragraph()
    p.add_run("Bold text. ").bold = True
    p.add_run("Italic text. ").italic = True
    p.add_run("Plain text.")

    d.add_heading("Team Distribution", level=2)
    table2 = d.add_table(rows=4, cols=2)
    table2.style = "Table Grid"
    table2.rows[0].cells[0].text = "Region"
    table2.rows[0].cells[1].text = "Headcount"
    for i, (region, count) in enumerate([
        ("Americas", "12"),
        ("EMEA", "8"),
        ("APAC", "15"),
    ], start=1):
        table2.rows[i].cells[0].text = region
        table2.rows[i].cells[1].text = count

    d.add_heading("Action Items", level=1)
    for action in [
        "Expand OPP coverage to MSG format",
        "Add IPYNB to ORF output targets",
        "Improve PDF→DOCX fidelity",
    ]:
        d.add_paragraph(action, style="List Bullet")

    d.add_heading("Numbered Roadmap", level=2)
    for step in [
        "Phase 1: Extract",
        "Phase 2: Translate",
        "Phase 3: Backfill",
    ]:
        d.add_paragraph(step, style="List Number")

    d.add_picture(io.BytesIO(_png_bytes()), width=Inches(1.5))

    d.save(str(dest))


# ---------------------------------------------------------------------------
# PPTX
# ---------------------------------------------------------------------------

def generate_pptx(dest: Path) -> None:
    """5 slides with titles, bullets, 1 table, 1 image."""
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    layout = prs.slide_layouts[1]  # Title + Content

    # Slide 1: Title
    s1 = prs.slides.add_slide(prs.slide_layouts[0])
    s1.shapes.title.text = "Omni Suite Roadmap"
    s1.placeholders[1].text = "Q1 2026"

    # Slide 2: Bullet list
    s2 = prs.slides.add_slide(layout)
    s2.shapes.title.text = "Goals"
    body = s2.placeholders[1]
    tf = body.text_frame
    tf.text = "Full format matrix coverage"
    p = tf.add_paragraph()
    p.text = "MCP and CLI parity"
    p = tf.add_paragraph()
    p.text = "Fidelity testing on real corpus"

    # Slide 3: Table
    s3 = prs.slides.add_slide(layout)
    s3.shapes.title.text = "Progress by Module"
    rows, cols = 4, 2
    tbl_shape = s3.shapes.add_table(rows, cols, Inches(1), Inches(2), Inches(8), Inches(3))
    tbl = tbl_shape.table
    tbl.cell(0, 0).text = "Module"
    tbl.cell(0, 1).text = "Status"
    data = [("OPP", "100%"), ("OL", "98%"), ("ORF", "95%")]
    for i, (m, st) in enumerate(data, start=1):
        tbl.cell(i, 0).text = m
        tbl.cell(i, 1).text = st

    # Slide 4: Image
    s4 = prs.slides.add_slide(layout)
    s4.shapes.title.text = "Architecture"
    s4.shapes.add_picture(io.BytesIO(_png_bytes()), Inches(3), Inches(2), Inches(2), Inches(2))

    # Slide 5: Summary
    s5 = prs.slides.add_slide(layout)
    s5.shapes.title.text = "Next Steps"
    tf = s5.placeholders[1].text_frame
    tf.text = "Ship full matrix verifier"
    p = tf.add_paragraph()
    p.text = "Add MCP coverage"

    prs.save(str(dest))


# ---------------------------------------------------------------------------
# PDF (via weasyprint from HTML for full CSS control)
# ---------------------------------------------------------------------------

def generate_pdf(dest: Path) -> None:
    """3 pages with text, headings, table, image, lists."""
    html = f"""
    <html><head><style>
        body {{ font-family: sans-serif; margin: 40px; }}
        h1 {{ color: #003366; }}
        h2 {{ color: #006699; }}
        table {{ border-collapse: collapse; width: 100%; }}
        td, th {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
        .page-break {{ page-break-after: always; }}
    </style></head>
    <body>
        <h1>Technical Specification</h1>
        <p>This document describes the Omni Suite architecture and
        the role of each component in the localization pipeline.</p>

        <h2>Architecture Overview</h2>
        <p>The pipeline consists of three stages: extraction, translation,
        and backfill. Each stage is implemented as a standalone module
        with its own CLI and MCP server.</p>

        <table>
            <tr><th>Stage</th><th>Module</th><th>Output</th></tr>
            <tr><td>1</td><td>OPP</td><td>MD + XLIFF + skeleton</td></tr>
            <tr><td>2</td><td>OL</td><td>Translated MD/XLIFF</td></tr>
            <tr><td>3</td><td>ORF</td><td>DOCX/PPTX/PDF/...</td></tr>
        </table>

        <div class="page-break"></div>
        <h1>Component Details</h1>

        <h2>OPP — Omni Pre Processor</h2>
        <p>Extracts content from 12 input formats including DOCX, PPTX,
        PDF, XLSX, HTML, EML, and others.</p>

        <h2>OL — Omni Localizer</h2>
        <p>Translates MD or XLIFF intermediates using configurable LLM
        backends with shield/repair/unshield pipeline.</p>

        <h2>ORF — Omni Re Formatter</h2>
        <p>Backfills translated content into 16 target formats using
        pandoc, weasyprint, and pure-Python renderers.</p>

        <ul>
            <li>Full format matrix verified</li>
            <li>MCP and CLI parity</li>
            <li>Fidelity-tested on real corpus</li>
        </ul>

        <div class="page-break"></div>
        <h1>Performance Metrics</h1>

        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Avg cell runtime (CLI)</td><td>15s</td></tr>
            <tr><td>Avg cell runtime (MCP)</td><td>18s</td></tr>
            <tr><td>Text preservation</td><td>99%</td></tr>
            <tr><td>Table preservation</td><td>100%</td></tr>
        </table>

        <h2>Conclusion</h2>
        <p>The system is production-ready for the verified path set.</p>
    </body>
    </html>
    """
    from weasyprint import HTML
    HTML(string=html).write_pdf(str(dest))


# ---------------------------------------------------------------------------
# XLSX
# ---------------------------------------------------------------------------

def generate_xlsx(dest: Path) -> None:
    """2 sheets, headers, 10 rows, formulas, formatting."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Sales"

    headers = ["Quarter", "Region", "Product", "Units", "Revenue"]
    for col, h in enumerate(headers, start=1):
        cell = ws1.cell(row=1, column=col, value=h)
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="DDDDDD")

    rows = [
        ("Q1", "Americas", "Widget", 100, 5000),
        ("Q1", "EMEA", "Widget", 80, 4000),
        ("Q1", "APAC", "Gadget", 120, 7200),
        ("Q2", "Americas", "Widget", 130, 6500),
        ("Q2", "EMEA", "Gadget", 90, 5400),
        ("Q2", "APAC", "Widget", 110, 5500),
        ("Q3", "Americas", "Gadget", 140, 8400),
        ("Q3", "EMEA", "Widget", 95, 4750),
        ("Q3", "APAC", "Gadget", 150, 9000),
    ]
    for r, row in enumerate(rows, start=2):
        for c, val in enumerate(row, start=1):
            ws1.cell(row=r, column=c, value=val)
    ws1.cell(row=11, column=4, value="=SUM(D2:D10)")
    ws1.cell(row=11, column=5, value="=SUM(E2:E10)")

    ws2 = wb.create_sheet("Inventory")
    inv_headers = ["SKU", "Name", "Stock", "Reorder"]
    for col, h in enumerate(inv_headers, start=1):
        cell = ws2.cell(row=1, column=col, value=h)
        cell.font = Font(bold=True)
    inv = [
        ("A001", "Widget Standard", 500, 100),
        ("A002", "Widget Premium", 200, 50),
        ("B001", "Gadget Mini", 800, 200),
    ]
    for r, row in enumerate(inv, start=2):
        for c, val in enumerate(row, start=1):
            ws2.cell(row=r, column=c, value=val)

    wb.save(str(dest))


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def generate_html(dest: Path) -> None:
    """Semantic HTML with h1-h3, table, image, lists."""
    img_data_uri = f"data:image/png;base64,{__import__('base64').b64encode(_png_bytes()).decode()}"
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Product Catalog</title></head>
<body>
    <h1>Product Catalog 2026</h1>
    <p>Welcome to our annual product catalog. Browse our offerings below.</p>

    <h2>Electronics</h2>
    <h3>Smartphones</h3>
    <ul>
        <li>Model X — 6.5" display, 128GB</li>
        <li>Model Y — 6.1" display, 256GB</li>
        <li>Model Z — 5.8" display, 64GB</li>
    </ul>

    <h3>Laptops</h3>
    <ol>
        <li>UltraBook 13 — 13" Retina</li>
        <li>ProBook 15 — 15" 4K</li>
        <li>GameBook 17 — 17" 144Hz</li>
    </ol>

    <h2>Pricing</h2>
    <table border="1">
        <tr><th>Product</th><th>Price</th><th>Stock</th></tr>
        <tr><td>Model X</td><td>$699</td><td>In stock</td></tr>
        <tr><td>Model Y</td><td>$899</td><td>Limited</td></tr>
        <tr><td>UltraBook 13</td><td>$1299</td><td>In stock</td></tr>
        <tr><td>ProBook 15</td><td>$1899</td><td>Pre-order</td></tr>
        <tr><td>GameBook 17</td><td>$2499</td><td>In stock</td></tr>
    </table>

    <h2>About Us</h2>
    <p><strong>Established 2010.</strong> We design and manufacture consumer
    electronics with a focus on <em>quality</em> and <em>affordability</em>.</p>

    <p><img src="{img_data_uri}" alt="logo" width="100"></p>
</body>
</html>"""
    dest.write_text(html, encoding="utf-8")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def generate_all(force: bool = False) -> list[Path]:
    """Generate the full corpus. Idempotent unless force=True."""
    out = _ensure_corpus_dir()
    generators = [
        ("complex.docx", generate_docx),
        ("complex.pptx", generate_pptx),
        ("complex.pdf", generate_pdf),
        ("complex.xlsx", generate_xlsx),
        ("complex.html", generate_html),
    ]
    written = []
    for name, gen in generators:
        path = out / name
        if not path.exists() or force:
            gen(path)
            written.append(path)
    return written


if __name__ == "__main__":
    force = "--force" in sys.argv
    files = generate_all(force=force)
    if files:
        print(f"Generated {len(files)} corpus files:")
        for f in files:
            print(f"  {f} ({f.stat().st_size} bytes)")
    else:
        print("Corpus already exists (use --force to regenerate).")
        for f in sorted(CORPUS_DIR.iterdir()):
            print(f"  {f} ({f.stat().st_size} bytes)")
