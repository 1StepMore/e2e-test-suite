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

ALL_INPUTS: list[str] = [
    "docx", "pptx", "xlsx",
    "html", "epub", "pdf",
    "csv", "json", "xml",
    "eml", "ipynb",
]

ALL_OUTPUTS: list[str] = [
    "docx", "odt", "epub", "html", "rtf", "pdf",
    "pptx", "icml", "srt",
    "csv", "xlsx", "xml",
    "ipynb", "eml", "json",
]

XLIFF_INPUTS: list[str] = [
    "docx", "pptx", "xlsx", "html", "epub", "eml",
]

XLIFF_OUTPUTS: list[str] = [
    "docx", "pptx", "epub", "html", "odt",
]


def _build_full_matrix() -> list[tuple[str, str, str]]:
    return [(i, o, "md") for i in ALL_INPUTS for o in ALL_OUTPUTS]


def _build_full_xliff_matrix() -> list[tuple[str, str, str]]:
    return [(i, o, "xliff") for i in XLIFF_INPUTS for o in XLIFF_OUTPUTS]


MD_PATH_MATRIX: list[tuple[str, str]] = [(i, o) for i, o, _ in _build_full_matrix()]
XLIFF_PATH_MATRIX: list[tuple[str, str]] = [(i, o) for i, o, _ in _build_full_xliff_matrix()]

FULL_MATRIX: list[tuple[str, str, str]] = (
    _build_full_matrix() + _build_full_xliff_matrix()
)


# Skip rules. Two formats:
#   ("axis", fmt, reason) where axis ∈ {"input", "output"} — skip if that
#     axis's format is `fmt` and the corresponding tool is unavailable.
#   ("input_fmt", "output_fmt", reason) — skip a specific input→output pair
#     (used for ill-defined format combinations where generic MD can't carry
#     the required structure: JSON, XLSX, SRT, etc.).
SKIP_RULES: list[tuple[str, str, str]] = [
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
    # MD→JSON: arbitrary MD has no JSON payload; md2json requires a code
    # block or OPP key=value pairs.
    ("*", "json", "MD→JSON requires JSON code block or OPP key=value source"),
    # MD→SRT: subtitle format requires timestamped cues; generic MD has none.
    ("*", "srt", "MD→SRT requires timestamped cues; no timestamps in fixture"),
    # Cross-format jumps with no logical content mapping (table↔slide).
    ("pptx", "xlsx", "PPTX→XLSX: no table content in slide fixture"),
    ("xlsx", "pptx", "XLSX→PPTX: no slide content in table fixture"),
    # XLIFF path: OPP doesn't produce skeleton.zip for non-DOCX/PPTX inputs.
    ("xliff", "xlsx", "XLIFF: OPP doesn't produce skeleton for XLSX"),
    ("xliff", "html", "XLIFF: OPP doesn't produce skeleton for HTML"),
    ("xliff", "epub", "XLIFF: OPP doesn't produce skeleton for EPUB"),
    ("xliff", "eml", "XLIFF: OPP doesn't produce skeleton for EML"),
    # XLIFF cross-format: ORF converters assume same-format skeleton+output.
    # Only same-format XLIFF cells are supported.
    ("xliff_xfmt", "*", "XLIFF cross-format not supported by ORF converters"),
]


# ---------------------------------------------------------------------------
# Cell execution
# ---------------------------------------------------------------------------

@dataclass
class CellResult:
    inp: str
    outp: str
    path: str  # "md" or "xliff"
    status: str  # "pass", "skip", "fail"
    duration_s: float
    detail: str = ""
    skip_reason: str = ""
    fidelity: float = 0.0
    fidelity_detail: dict = field(default_factory=dict)

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


def _check_skip(inp: str, outp: str, path: str) -> str | None:
    """Return skip reason if the cell should be skipped, else None."""
    for rule in SKIP_RULES:
        axis, fmt, reason = rule
        if axis == "input" and fmt == inp:
            if not AVAILABILITY.get("extract_msg" if fmt == "msg" else
                                    "nbformat" if fmt == "ipynb" else
                                    fmt, True):
                return reason
        elif axis == "output" and fmt == outp:
            if not AVAILABILITY.get("pandoc" if fmt in ("docx", "pdf", "odt", "epub", "rtf", "icml") else
                                    "md2pptx" if fmt == "pptx" else
                                    "aspose_email" if fmt == "msg" else
                                    "weasyprint" if fmt == "pdf" else
                                    True, True):
                return reason
        elif axis == "*" and fmt == outp:
            return reason
        elif axis == inp and fmt == outp:
            return reason
        elif axis == "xliff" and fmt == inp and path == "xliff":
            return reason
        elif axis == "xliff_xfmt" and path == "xliff" and inp != fmt:
            return reason
    return None


def _resolve_fixture(inp: str, dest: Path, corpus_mode: str, suite_root: Path) -> bool:
    """Write or copy the input fixture. Returns True on success."""
    if corpus_mode == "real":
        corpus = suite_root / "test_corpus" / f"complex.{inp}"
        if corpus.exists():
            import shutil
            shutil.copy2(corpus, dest)
            return dest.exists()
    _write_minimal_fixture(inp, dest)
    return dest.exists()


def _run_one_cell(
    suite_root: Path, inp: str, outp: str, path: str, tmp_root: Path,
    corpus_mode: str = "minimal", fidelity_enabled: bool = False,
) -> CellResult:
    """Run a single input→output cell end-to-end via the chosen path.

    MD path:
    1. OPP extracts input → MD
    2. OL translates MD (FAKE_LLM) → translated MD
    3. ORF backfills translated MD → output

    XLIFF path:
    1. OPP extracts input → XLIFF + skeleton.zip
    2. OL translates XLIFF → translated XLIFF
    3. ORF backfills translated XLIFF + skeleton → output
    """
    t0 = time.monotonic()
    skip = _check_skip(inp, outp, path)
    if skip:
        return CellResult(inp, outp, path, "skip", 0.0, skip_reason=skip)

    cell_dir = tmp_root / f"{path}_{inp}_to_{outp}"
    cell_dir.mkdir(parents=True, exist_ok=True)
    src = cell_dir / f"sample.{inp}"
    if not _resolve_fixture(inp, src, corpus_mode, suite_root):
        return CellResult(inp, outp, path, "skip", 0.0, skip_reason=f"no fixture for {inp}")

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

    if path == "md":
        result = _run_md_path(py, env, suite_root, src, cell_dir, inp, outp, t0)
    elif path == "xliff":
        result = _run_xliff_path(py, env, suite_root, src, cell_dir, inp, outp, t0)
    else:
        return CellResult(inp, outp, path, "fail", time.monotonic() - t0,
                          detail=f"unknown path: {path}")

    if fidelity_enabled and result.status == "pass":
        orf_out = cell_dir / f"result.{outp}"
        if orf_out.exists():
            try:
                from fidelity_checker import compute_fidelity
                fr = compute_fidelity(src, orf_out, outp)
                result.fidelity = fr.overall
                result.fidelity_detail = fr.to_dict()
            except Exception as e:
                result.detail = f"{result.detail}  [fidelity error: {e}]".strip()

    return result


def _run_md_path(py, env, suite_root, src, cell_dir, inp, outp, t0) -> CellResult:
    """MD intermediate path: input → MD → translated MD → output."""
    try:
        r1 = subprocess.run(
            [str(py), "-m", "opp.cli", str(src), "--target-format", "md",
             "--source-lang", "en", "--target-lang", "zh",
             "--output-dir", str(cell_dir)],
            capture_output=True, text=True, env=env,
            cwd=str(suite_root / "Omni_Pre_Processor"),
            timeout=120,
        )
        if r1.returncode != 0:
            return CellResult(inp, outp, "md", "fail", time.monotonic() - t0,
                              detail=f"OPP: {r1.stderr[:200]}")
        md_out = cell_dir / f"{src.stem}.md"
        if not md_out.exists():
            return CellResult(inp, outp, "md", "fail", time.monotonic() - t0,
                              detail=f"OPP: no .md at {md_out}")

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
            return CellResult(inp, outp, "md", "fail", time.monotonic() - t0,
                              detail=f"OL: {r2.stderr[:200]}")
        ol_md = ol_dir / f"{md_out.name}"
        if not ol_md.exists():
            return CellResult(inp, outp, "md", "fail", time.monotonic() - t0,
                              detail=f"OL: no translated output at {ol_md}")

        orf_out = cell_dir / f"result.{outp}"
        r3 = subprocess.run(
            [str(py), "-m", "orf.cli", "apply-md", str(ol_md),
             "--target-format", outp, "--output", str(orf_out)],
            capture_output=True, text=True, env=env,
            cwd=str(suite_root / "Omni_Re_Formatter"),
            timeout=120,
        )
        if r3.returncode != 0:
            return CellResult(inp, outp, "md", "fail", time.monotonic() - t0,
                              detail=f"ORF: {r3.stderr[:200]}")
        if not orf_out.exists():
            return CellResult(inp, outp, "md", "fail", time.monotonic() - t0,
                              detail=f"ORF: no output at {orf_out}")

    except subprocess.TimeoutExpired:
        return CellResult(inp, outp, "md", "fail", time.monotonic() - t0, detail="timeout")
    except Exception as e:
        return CellResult(inp, outp, "md", "fail", time.monotonic() - t0,
                          detail=f"{type(e).__name__}: {e}")

    return CellResult(inp, outp, "md", "pass", time.monotonic() - t0)


def _run_xliff_path(py, env, suite_root, src, cell_dir, inp, outp, t0) -> CellResult:
    """XLIFF intermediate path: input → XLIFF+skeleton → translated XLIFF → output."""
    try:
        r1 = subprocess.run(
            [str(py), "-m", "opp.cli", str(src), "--target-format", "both",
             "--source-lang", "en", "--target-lang", "zh",
             "--output-dir", str(cell_dir)],
            capture_output=True, text=True, env=env,
            cwd=str(suite_root / "Omni_Pre_Processor"),
            timeout=120,
        )
        if r1.returncode != 0:
            return CellResult(inp, outp, "xliff", "fail", time.monotonic() - t0,
                              detail=f"OPP: {r1.stderr[:200]}")
        xlf_path = cell_dir / f"{src.stem}.xlf"
        skeleton_path = cell_dir / f"{src.stem}.skeleton.zip"
        if not xlf_path.exists():
            return CellResult(inp, outp, "xliff", "fail", time.monotonic() - t0,
                              detail=f"OPP: no .xlf at {xlf_path}")
        if not skeleton_path.exists():
            return CellResult(inp, outp, "xliff", "fail", time.monotonic() - t0,
                              detail=f"OPP: no skeleton at {skeleton_path}")

        ol_dir = cell_dir / "ol"
        ol_dir.mkdir(exist_ok=True)
        r2 = subprocess.run(
            [str(py), "-m", "ol_cli", "translate-xliff", str(xlf_path),
             "-s", "en", "-t", "zh", "-o", str(ol_dir),
             "-c", str(suite_root / "Omni_Localizer" / "config" / "default.yaml")],
            capture_output=True, text=True, env=env,
            cwd=str(suite_root / "Omni_Localizer"),
            timeout=120,
        )
        if r2.returncode != 0:
            return CellResult(inp, outp, "xliff", "fail", time.monotonic() - t0,
                              detail=f"OL: {r2.stderr[:200]}")
        ol_xlf = ol_dir / xlf_path.name
        if not ol_xlf.exists():
            ol_xlf = ol_dir / f"{src.stem}.xlf"
        if not ol_xlf.exists():
            return CellResult(inp, outp, "xliff", "fail", time.monotonic() - t0,
                              detail=f"OL: no translated .xlf in {ol_dir}")

        orf_out = cell_dir / f"result.{outp}"
        r3 = subprocess.run(
            [str(py), "-m", "orf.cli", "apply-xliff", str(skeleton_path),
             "--xliff", str(ol_xlf),
             "--output", str(orf_out),
             "--format", outp, "--force"],
            capture_output=True, text=True, env=env,
            cwd=str(suite_root / "Omni_Re_Formatter"),
            timeout=120,
        )
        if r3.returncode != 0:
            return CellResult(inp, outp, "xliff", "fail", time.monotonic() - t0,
                              detail=f"ORF: {r3.stderr[:200]}")
        if not orf_out.exists():
            return CellResult(inp, outp, "xliff", "fail", time.monotonic() - t0,
                              detail=f"ORF: no output at {orf_out}")

    except subprocess.TimeoutExpired:
        return CellResult(inp, outp, "xliff", "fail", time.monotonic() - t0, detail="timeout")
    except Exception as e:
        return CellResult(inp, outp, "xliff", "fail", time.monotonic() - t0,
                          detail=f"{type(e).__name__}: {e}")

    return CellResult(inp, outp, "xliff", "pass", time.monotonic() - t0)


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
    if inp == "pdf":
        # Minimal valid single-page PDF (no external deps).
        dest.write_bytes(
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
            b"/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj\n"
            b"4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
            b"5 0 obj<</Length 44>>stream\n"
            b"BT /F1 12 Tf 100 700 Td (Hello, world.) Tj ET\n"
            b"endstream endobj\n"
            b"xref\n0 6\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000056 00000 n \n"
            b"0000000103 00000 n \n"
            b"0000000211 00000 n \n"
            b"0000000262 00000 n \n"
            b"trailer<</Size 6/Root 1 0 R>>\n"
            b"startxref\n356\n%%EOF\n"
        )
        return
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
        # Fixed timestamp (2020-01-01 00:00:00) for deterministic ZIP metadata.
        # Without this, zipfile embeds the current time and the fixture differs
        # between runs, breaking equivalence checks.
        fixed_dt = (2020, 1, 1, 0, 0, 0)
        def _zi(name: str) -> zipfile.ZipInfo:
            zi = zipfile.ZipInfo(name)
            zi.date_time = fixed_dt
            zi.compress_type = zipfile.ZIP_DEFLATED
            return zi
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(_zi("mimetype"), mimetype, compress_type=zipfile.ZIP_STORED)
            zf.writestr(_zi("META-INF/container.xml"), container)
            zf.writestr(_zi("OEBPS/content.opf"), opf)
            zf.writestr(_zi("OEBPS/c1.xhtml"), ch)
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
        "| Path | Input | Output | Status | Time | Detail |",
        "|-------|-------|--------|--------|------|--------|",
    ]
    for c in result.cells:
        d = c.detail or c.skip_reason
        lines.append(
            f"| {c.path} | {c.inp} | {c.outp} | {c.status.upper()} | "
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
                        help="Comma-separated input formats to test (e.g. 'docx,pptx'). "
                             "Default: full matrix.")
    parser.add_argument("--path-filter", choices=["md", "xliff", "both"], default="both",
                        help="Which path(s) to test. Default: both.")
    parser.add_argument("--timeout", type=int, default=120, help="Per-cell timeout (seconds)")
    parser.add_argument("--parallel", type=int, default=1,
                        help="Run N cells concurrently (thread pool). Default: 1 (sequential).")
    parser.add_argument("--corpus", choices=["minimal", "real"], default="minimal",
                        help="Fixture source: 'minimal' = hand-crafted tiny files; "
                             "'real' = test_corpus/ with tables, images, complex formatting.")
    parser.add_argument("--fidelity", action="store_true",
                        help="Compute content fidelity scores (text/table/image preservation) "
                             "after each successful cell. Requires --corpus real for meaningful scores.")
    args = parser.parse_args()

    import tempfile
    suite_root: Path = args.suite_root.resolve()
    if args.out_dir is None:
        out_dir = suite_root / "test_artifacts" / "format_matrix" / time.strftime("%Y%m%d-%H%M%S")
    else:
        out_dir = args.out_dir.resolve() if args.out_dir.is_absolute() else (Path.cwd() / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_root = out_dir / "cells"
    tmp_root.mkdir(exist_ok=True)

    result = MatrixResult()
    t0 = time.monotonic()
    cells = list(FULL_MATRIX)
    if args.path_filter == "md":
        cells = [c for c in cells if c[2] == "md"]
    elif args.path_filter == "xliff":
        cells = [c for c in cells if c[2] == "xliff"]
    if args.subset:
        wanted = {s.strip() for s in args.subset.split(",") if s.strip()}
        cells = [c for c in cells if c[0] in wanted]

    if args.parallel <= 1:
        for inp, outp, path in cells:
            c = _run_one_cell(suite_root, inp, outp, path, tmp_root,
                              corpus_mode=args.corpus, fidelity_enabled=args.fidelity)
            result.cells.append(c)
            fid_str = f"  fid={c.fidelity:.2f}" if c.fidelity else ""
            print(f"  {c.inp} → {c.outp}: {c.status.upper()} ({c.duration_s:.1f}s){fid_str}"
                  f"{'  ' + c.detail if c.detail else ''}"
                  f"{'  [' + c.skip_reason + ']' if c.skip_reason else ''}",
                  flush=True)
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=args.parallel) as pool:
            futures = {
                pool.submit(_run_one_cell, suite_root, inp, outp, path, tmp_root,
                            args.corpus, args.fidelity): (inp, outp, path)
                for inp, outp, path in cells
            }
            cell_results: dict[tuple[str, str, str], CellResult] = {}
            for fut in as_completed(futures):
                inp, outp, path = futures[fut]
                try:
                    c = fut.result()
                except Exception as e:
                    c = CellResult(inp, outp, path, "fail", 0.0, detail=f"runner exception: {e}")
                cell_results[(inp, outp, path)] = c
                print(f"  {c.inp} → {c.outp}: {c.status.upper()} ({c.duration_s:.1f}s)"
                      f"{'  ' + c.detail if c.detail else ''}"
                      f"{'  [' + c.skip_reason + ']' if c.skip_reason else ''}",
                      flush=True)
            for inp, outp, path in cells:
                if (inp, outp, path) in cell_results:
                    result.cells.append(cell_results[(inp, outp, path)])
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
