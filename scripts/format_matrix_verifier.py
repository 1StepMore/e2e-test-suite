"""Format Matrix Verifier — engine of the Omni Suite self-driven loop.

Iterates the realistic input × output × transport matrix and exercises
each cell end-to-end. Reports a markdown matrix table; exits 0 if all
non-skipped cells pass.

Cells that require missing CLI binaries (md2pptx, pandoc, aspose)
auto-skip with a clear reason.

This is the "T" gate in the convergence loop: if any cell fails,
the orchestrator (or MVA bug-fix) takes over.

Usage:
    python scripts/format_matrix_verifier.py                  # CLI
    python scripts/format_matrix_verifier.py --json          # JSON output
    python scripts/format_matrix_verifier.py --suite-root .  # custom root
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Availability gates
# ---------------------------------------------------------------------------

def _which(name: str) -> bool:
    return shutil.which(name) is not None


def _can_import(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


AVAILABILITY = {
    "pandoc": _which("pandoc"),
    "md2pptx": _which("md2pptx"),
    "weasyprint": _can_import("weasyprint"),
    "aspose_email": _can_import("aspose.email"),
    "extract_msg": _can_import("extract_msg"),
    "nbformat": _can_import("nbformat"),
}


# ---------------------------------------------------------------------------
# Matrix definition
# ---------------------------------------------------------------------------

# Realistic input × output combinations (subset of the full 16×16 grid).
# Excludes silly combinations (e.g. XLSX→EPUB) and format pairs that
# don't have a clean translation path.
# Format: (input_format, output_format) — both via MD path
MD_PATH_MATRIX: list[tuple[str, str]] = [
    ("docx", "docx"),
    ("docx", "html"),
    ("docx", "pdf"),
    ("docx", "csv"),
    ("docx", "xlsx"),
    ("docx", "xml"),
    ("docx", "ipynb"),
    ("docx", "eml"),
    ("docx", "srt"),
    ("docx", "odt"),
    ("docx", "epub"),
    ("docx", "rtf"),
    ("docx", "icml"),
    ("docx", "json"),
    ("pptx", "pptx"),  # skipped if md2pptx missing
    ("html", "html"),
    ("html", "docx"),
    ("html", "pdf"),
    ("csv", "csv"),
    ("csv", "xlsx"),
    ("csv", "json"),
    ("json", "json"),
    ("json", "xml"),
    ("xml", "xml"),
    ("xml", "json"),
    ("eml", "eml"),
    ("eml", "html"),
    ("xlsx", "xlsx"),
    ("xlsx", "csv"),
    ("epub", "epub"),
    ("epub", "html"),
    ("epub", "docx"),
    ("epub", "pdf"),
    ("ipynb", "ipynb"),
    ("ipynb", "html"),
    ("ipynb", "docx"),
    ("ipynb", "pdf"),
]


# Skips the input format that requires missing CLI.
SKIP_RULES: list[tuple[str, str, str]] = [
    # (input_or_output, format, reason_when_skipped)
    ("output", "pptx", "md2pptx CLI not installed"),
    ("output", "docx", "pandoc not installed"),
    ("output", "pdf", "pandoc/weasyprint not installed"),
    ("output", "odt", "pandoc not installed"),
    ("output", "epub", "pandoc not installed"),
    ("output", "rtf", "pandoc not installed"),
    ("output", "icml", "pandoc not installed"),
    ("input", "msg", "extract-msg not installed"),
    ("output", "msg", "aspose-email-foss not installed"),
    ("input", "ipynb", "nbformat not installed"),
]


# ---------------------------------------------------------------------------
# Cell execution
# ---------------------------------------------------------------------------

@dataclass
class CellResult:
    inp: str
    outp: str
    status: str  # "pass", "skip", "fail"
    duration_s: float
    detail: str = ""
    skip_reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MatrixResult:
    cells: list[CellResult] = field(default_factory=list)
    total_duration_s: float = 0.0

    @property
    def passed(self) -> int:
        return sum(1 for c in self.cells if c.status == "pass")

    @property
    def skipped(self) -> int:
        return sum(1 for c in self.cells if c.status == "skip")

    @property
    def failed(self) -> int:
        return sum(1 for c in self.cells if c.status == "fail")

    def to_dict(self) -> dict:
        return {
            "total": len(self.cells),
            "passed": self.passed,
            "skipped": self.skipped,
            "failed": self.failed,
            "duration_s": self.total_duration_s,
            "cells": [c.to_dict() for c in self.cells],
        }


def _check_skip(inp: str, outp: str) -> str | None:
    """Return skip reason if the cell should be skipped, else None."""
    for axis, fmt, reason in SKIP_RULES:
        if axis == "input" and fmt == inp:
            if not AVAILABILITY.get("extract_msg" if fmt == "msg" else
                                    "nbformat" if fmt == "ipynb" else
                                    fmt, True):
                return reason
        if axis == "output" and fmt == outp:
            if not AVAILABILITY.get("pandoc" if fmt in ("docx", "pdf", "odt", "epub", "rtf", "icml") else
                                    "md2pptx" if fmt == "pptx" else
                                    "aspose_email" if fmt == "msg" else
                                    "weasyprint" if fmt == "pdf" else
                                    True, True):
                return reason
    return None


def _run_one_cell(suite_root: Path, inp: str, outp: str, tmp_root: Path) -> CellResult:
    """Run a single input→output cell end-to-end via the MD path.

    Steps:
    1. Create a tiny fixture of the input format
    2. OPP extracts to MD
    3. OL translates MD (FAKE_LLM)
    4. ORF backfills MD to output format
    """
    t0 = time.monotonic()
    skip = _check_skip(inp, outp)
    if skip:
        return CellResult(inp, outp, "skip", 0.0, skip_reason=skip)

    # Fixtures: each input format needs a small source file
    cell_dir = tmp_root / f"{inp}_to_{outp}"
    cell_dir.mkdir(parents=True, exist_ok=True)
    src = cell_dir / f"sample.{inp}"
    _write_minimal_fixture(inp, src)
    if not src.exists():
        return CellResult(inp, outp, "skip", 0.0, skip_reason=f"no fixture for {inp}")

    env = os.environ.copy()
    env["OMNI_TEST_FAKE_LLM"] = "1"
    env["OMNI_TEST_FAKE_PANDOC"] = "1"
    env["PYTHONPATH"] = ":".join(filter(None, [
        env.get("PYTHONPATH", ""),
        str(suite_root / "Omni_Pre_Processor" / "src"),
        str(suite_root / "Omni_Localizer" / "src"),
        str(suite_root / "Omni_Re_Formatter" / "src"),
        str(suite_root / ".venv_ol" / "lib" / "python3.13" / "site-packages"),
    ]))

    py = suite_root / ".venv_ol" / "bin" / "python"
    if not py.exists():
        py = Path(sys.executable)

    try:
        # Step 1: OPP extract
        md_out = cell_dir / "out.md"
        r1 = subprocess.run(
            [str(py), "-m", "opp.cli", str(src), "--target-format", "md",
             "--source-lang", "en", "--target-lang", "zh",
             "--output-dir", str(cell_dir)],
            capture_output=True, text=True, env=env, cwd=str(suite_root / "Omni_Pre_Processor"),
            timeout=120,
        )
        if r1.returncode != 0:
            return CellResult(inp, outp, "fail", time.monotonic() - t0,
                              detail=f"OPP: {r1.stderr[:200]}")
        # OPP names the output file after the source stem
        md_out = cell_dir / f"{src.stem}.md"
        if not md_out.exists():
            return CellResult(inp, outp, "fail", time.monotonic() - t0,
                              detail=f"OPP: no .md output at {md_out}")

        # Step 2: OL translate (FAKE_LLM)
        ol_dir = cell_dir / "ol"
        ol_dir.mkdir(exist_ok=True)
        r2 = subprocess.run(
            [str(py), "-m", "ol_cli", "translate-md", str(md_out),
             "-s", "en", "-t", "zh", "-o", str(ol_dir),
             "-c", str(suite_root / "Omni_Localizer" / "config" / "default.yaml")],
            capture_output=True, text=True, env=env,
            cwd=str(suite_root / "Omni_Localizer"),
            timeout=120,
        )
        if r2.returncode != 0:
            return CellResult(inp, outp, "fail", time.monotonic() - t0,
                              detail=f"OL: {r2.stderr[:200]}")
        # OL may name output <stem>.md (the original) or _translated_<stem>.md
        ol_md = ol_dir / f"{md_out.name}"
        if not ol_md.exists():
            return CellResult(inp, outp, "fail", time.monotonic() - t0,
                              detail=f"OL: no translated output at {ol_md}")

        # Step 3: ORF backfill
        orf_out = cell_dir / f"result.{outp}"
        r3 = subprocess.run(
            [str(py), "-m", "orf.cli", "apply-md", str(ol_md),
             "--target-format", outp, "--output", str(orf_out)],
            capture_output=True, text=True, env=env,
            cwd=str(suite_root / "Omni_Re_Formatter"),
            timeout=120,
        )
        if r3.returncode != 0:
            return CellResult(inp, outp, "fail", time.monotonic() - t0,
                              detail=f"ORF: {r3.stderr[:200]}")
        if not orf_out.exists():
            return CellResult(inp, outp, "fail", time.monotonic() - t0,
                              detail=f"ORF: no output at {orf_out}")

    except subprocess.TimeoutExpired:
        return CellResult(inp, outp, "fail", time.monotonic() - t0, detail="timeout")
    except Exception as e:
        return CellResult(inp, outp, "fail", time.monotonic() - t0,
                          detail=f"{type(e).__name__}: {e}")

    return CellResult(inp, outp, "pass", time.monotonic() - t0)


def _write_minimal_fixture(inp: str, dest: Path) -> None:
    """Write a minimal valid file of the given input format."""
    if inp == "docx":
        # Use python-docx if available
        try:
            from docx import Document
            d = Document()
            d.add_heading("Test", level=1)
            d.add_paragraph("Hello, world.")
            d.save(str(dest))
            return
        except ImportError:
            pass
    if inp == "pptx":
        try:
            from pptx import Presentation
            p = Presentation()
            slide = p.slides.add_slide(p.slide_layouts[0])
            slide.shapes.title.text = "Test"
            p.save(str(dest))
            return
        except ImportError:
            pass
    if inp == "xlsx":
        try:
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws["A1"] = "Hello"
            wb.save(str(dest))
            return
        except ImportError:
            pass
    if inp == "html":
        dest.write_text(
            "<!DOCTYPE html><html><body><h1>Test</h1>"
            "<p>Hello, world.</p></body></html>", encoding="utf-8"
        )
        return
    if inp == "csv":
        dest.write_text("col1,col2\na,b\nc,d\n", encoding="utf-8")
        return
    if inp == "json":
        dest.write_text('{"greeting": "Hello", "items": [1, 2, 3]}', encoding="utf-8")
        return
    if inp == "xml":
        dest.write_text(
            '<?xml version="1.0"?><root><item>Hello</item></root>',
            encoding="utf-8",
        )
        return
    if inp == "eml":
        dest.write_text(
            "From: test@example.com\n"
            "To: user@example.com\n"
            "Subject: Test\n"
            "Content-Type: text/plain\n\n"
            "Hello, world.\n",
            encoding="utf-8",
        )
        return
    if inp == "ipynb":
        try:
            import nbformat as nbf
            nb = nbf.v4.new_notebook()
            nb.cells.append(nbf.v4.new_code_cell(source="print('Hello')"))
            nbf.write(nb, str(dest))
            return
        except ImportError:
            pass
    if inp == "epub":
        # Build a minimal valid EPUB via zipfile
        import zipfile
        mimetype = b"application/epub+zip"
        container = (
            b"<?xml version='1.0' encoding='UTF-8'?>\n"
            b"<container version='1.0' "
            b"xmlns='urn:oasis:names:tc:opendocument:xmlns:container'>\n"
            b"<rootfiles><rootfile full-path='OEBPS/content.opf' "
            b"media-type='application/oebps-package+xml'/></rootfiles>\n"
            b"</container>"
        )
        opf = (
            b"<?xml version='1.0' encoding='UTF-8'?>\n"
            b"<package xmlns='http://www.idpf.org/2007/opf' version='3.0' "
            b"xmlns:dc='http://purl.org/dc/elements/1.1/'>\n"
            b"<metadata><dc:title>Test</dc:title></metadata>\n"
            b"<manifest>"
            b"<item id='c1' href='c1.xhtml' media-type='application/xhtml+xml'/>"
            b"</manifest>\n"
            b"<spine><itemref idref='c1'/></spine>\n"
            b"</package>"
        )
        ch = (
            b"<?xml version='1.0' encoding='UTF-8'?>\n"
            b"<html xmlns='http://www.w3.org/1999/xhtml'>"
            b"<body><h1>Test</h1><p>Hello.</p></body></html>"
        )
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("mimetype", mimetype, compress_type=zipfile.ZIP_STORED)
            zf.writestr("META-INF/container.xml", container)
            zf.writestr("OEBPS/content.opf", opf)
            zf.writestr("OEBPS/c1.xhtml", ch)
        return
    # Fallback: write a small text file (will fail format detection but
    # gives a clear error)
    dest.write_text("placeholder", encoding="utf-8")


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _render_markdown(result: MatrixResult) -> str:
    lines = [
        "# Format Matrix Verifier",
        "",
        f"**Cells**: {len(result.cells)} | "
        f"**Pass**: {result.passed} | "
        f"**Skip**: {result.skipped} | "
        f"**Fail**: {result.failed} | "
        f"**Duration**: {result.total_duration_s:.1f}s",
        "",
        "| Input | Output | Status | Time | Detail |",
        "|-------|--------|--------|------|--------|",
    ]
    for c in result.cells:
        d = c.detail or c.skip_reason
        lines.append(
            f"| {c.inp} | {c.outp} | {c.status.upper()} | "
            f"{c.duration_s:.1f}s | {d[:50]} |"
        )
    lines.append("")
    if result.failed:
        lines.append(f"## ❌ {result.failed} cell(s) failed")
    else:
        lines.append("## ✅ All non-skipped cells pass")
    return "\n".join(lines)


def _render_json(result: MatrixResult) -> str:
    return json.dumps(result.to_dict(), indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--suite-root", type=Path, default=Path.cwd())
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="Where to write the per-cell artifacts. Default: test_artifacts/format_matrix/<timestamp>")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of markdown")
    parser.add_argument("--subset", type=str, default=None,
                        help="Only run cells whose input matches this glob (e.g. 'docx')")
    parser.add_argument("--timeout", type=int, default=120, help="Per-cell timeout (seconds)")
    args = parser.parse_args()

    import tempfile
    suite_root: Path = args.suite_root.resolve()
    out_dir: Path = args.out_dir or (
        suite_root / "test_artifacts" / "format_matrix"
        / time.strftime("%Y%m%d-%H%M%S")
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_root = out_dir / "cells"
    tmp_root.mkdir(exist_ok=True)

    result = MatrixResult()
    t0 = time.monotonic()
    cells = MD_PATH_MATRIX
    if args.subset:
        import fnmatch
        cells = [(i, o) for i, o in cells if fnmatch.fnmatch(i, args.subset)]
    for inp, outp in cells:
        c = _run_one_cell(suite_root, inp, outp, tmp_root)
        result.cells.append(c)
        print(f"  {c.inp} → {c.outp}: {c.status.upper()} ({c.duration_s:.1f}s)"
              f"{'  ' + c.detail if c.detail else ''}"
              f"{'  [' + c.skip_reason + ']' if c.skip_reason else ''}",
              flush=True)
    result.total_duration_s = time.monotonic() - t0

    md_path = out_dir / "matrix.md"
    md_path.write_text(_render_markdown(result), encoding="utf-8")
    if args.json:
        json_path = out_dir / "matrix.json"
        json_path.write_text(_render_json(result), encoding="utf-8")
        print(f"\nJSON: {json_path}")
    print(f"\nReport: {md_path}")
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
