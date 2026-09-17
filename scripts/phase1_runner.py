#!/usr/bin/env python3
"""Phase 1: Comprehensive format matrix test runner for Omni Suite.

Tests the OPP→OL→ORF pipeline across all input formats, output formats,
language pairs, and pipeline paths. Reports GREEN/RED per combination.

Usage:
    python scripts/phase1_runner.py --tier P0     # DOCX core (4 paths × 2 langs)
    python scripts/phase1_runner.py --tier P1     # Per-input primary via MD
    python scripts/phase1_runner.py --fixture docx # Single input format
    python scripts/phase1_runner.py --mock-llm    # Use mock LLM for testing
    python scripts/phase1_runner.py --dry-run     # Print matrix only
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

_SUITE_ROOT = Path(__file__).resolve().parents[1]
_VENV_PYTHON = _SUITE_ROOT / ".venv_ol" / "bin" / "python"
_OL_SRC = _SUITE_ROOT / "Omni_Localizer" / "src"
_OPP_SRC = _SUITE_ROOT / "Omni_Pre_Processor" / "src"
_ORF_SRC = _SUITE_ROOT / "Omni_Re_Formatter" / "src"
_DEFAULT_CONFIG = _SUITE_ROOT / "Omni_Localizer" / "config" / "local.yaml"
_FIXTURES_DIR = _SUITE_ROOT / "test_fixtures"
_RESULTS_DIR = _SUITE_ROOT / "test_artifacts" / "phase1_runs"
_ENV = {**os.environ,
        "PYTHONPATH": f"{_OL_SRC}:{_OPP_SRC}:{_ORF_SRC}",
        "PATH": str(_VENV_PYTHON.parent) + ":" + os.environ.get("PATH", "")}

# =========================================================================
# Matrix Definition
# =========================================================================

# Input format → (zh_fixture, en_fixture, has_skeleton)
INPUT_FORMATS: dict[str, tuple[str, str, bool]] = {
    "docx": ("haier_ch2_zh.docx", "sherlock_holmes.docx", True),
    "pptx": ("haier.pptx", "sherlock_holmes.pptx", True),
    "epub": ("haier.epub", "sherlock_holmes.epub", False),
    "html": ("haier.html", "sherlock_holmes.html", False),
    "pdf":  ("haier.pdf", "sherlock_holmes.pdf", False),
    "xlsx": ("haier_catalog.xlsx", "sherlock_catalog.xlsx", False),
    "csv":  ("haier_catalog.csv", "sherlock_catalog.csv", False),
    "json": ("haier_catalog.json", "sherlock_catalog.json", False),
    "xml":  ("haier.xml", "sherlock_holmes.xml", False),
    "ipynb":("haier_analysis.ipynb", "sherlock_analysis.ipynb", False),
    "eml":  ("haier_report.eml", "sherlock_report.eml", False),
}

ALL_OUTPUT_FORMATS = [
    "docx", "odt", "epub", "html", "rtf", "pdf",
    "icml", "srt",
    "xlsx", "csv", "json", "xml",
    "ipynb", "eml", "msg",
]

XLIFF_PATH_OUTPUTS = ["docx", "pptx", "epub", "html"]  # 2026-06-17 OPT-09: removed odt (XLIFF backfill is format-preserving)

# 2026-06-17 round 6 (FIX-#16): promoted to module-level for testability.
XLIFF_OUTPUTS_BY_INPUT: dict[str, list[str]] = {
    "docx": ["docx"],
    "pptx": ["pptx"],
}

MD_PATH_OUTPUTS = list(ALL_OUTPUT_FORMATS)


@dataclass
class TestCase:
    tier: str
    input_format: str
    fixture_path: str
    source_lang: str
    target_lang: str
    path_type: str        # "cli-md", "cli-xliff"
    output_formats: list[str]
    description: str = ""


def resolve_fixture(inp_fmt: str, lang: str) -> str:
    """Resolve fixture file path for given format + language."""
    zh_name, en_name, _ = INPUT_FORMATS[inp_fmt]
    name = zh_name if lang == "zh" else en_name
    if inp_fmt == "docx" and lang == "zh":
        # The committed suite fixture wins over the local test_fixtures/zh/ copy.
        p = _SUITE_ROOT / "scenarios" / "_fixtures" / name
        if p.exists():
            return str(p)
    return str(_FIXTURES_DIR / lang / name)


def build_matrix() -> list[TestCase]:
    cases: list[TestCase] = []

    # P0: DOCX core (2 paths × 2 langs, CLI only for now)
    for src, tgt in [("zh", "en"), ("en", "zh")]:
        for path_type in ["cli-md", "cli-xliff"]:
            cases.append(TestCase("P0", "docx", resolve_fixture("docx", src),
                         src, tgt, path_type, ["docx"],
                         f"P0 DOCX core {path_type} {src}→{tgt}"))

    # P1: Per-input primary format via MD path. Round 10: pptx is
    # back in scope (ORF's apply-md now exposes pptx via MD2PPTXConverter).
    for inp_fmt in [f for f in INPUT_FORMATS if f != "docx"]:
        for src, tgt in [("zh", "en"), ("en", "zh")]:
            cases.append(TestCase("P1", inp_fmt, resolve_fixture(inp_fmt, src),
                         src, tgt, "cli-md", [inp_fmt],
                         f"P1 {inp_fmt}→{inp_fmt} MD {src}→{tgt}"))

    # P2: XLIFF backfill is format-preserving — skeleton must match the
    # output format, so docx→odt is invalid. Removed 2026-06-17 (OPT-09).
    # The matrix now references the module-level XLIFF_OUTPUTS_BY_INPUT
    # constant (FIX-#16) so tests can import it directly.
    for inp_fmt, outputs in XLIFF_OUTPUTS_BY_INPUT.items():
        for src, tgt in [("zh", "en"), ("en", "zh")]:
            for path_type in ["cli-xliff"]:
                cases.append(TestCase("P2", inp_fmt, resolve_fixture(inp_fmt, src),
                             src, tgt, path_type, outputs,
                             f"P2 {inp_fmt} XLIFF→{'+'.join(outputs)} {src}→{tgt}"))

    # P3: DOCX → outputs via MD path (filter out formats DOCX can't contain)
    docx_compatible = [f for f in ALL_OUTPUT_FORMATS
                       if f not in ("json", "eml", "msg", "icml", "srt")]
    for src, tgt in [("zh", "en"), ("en", "zh")]:
        cases.append(TestCase("P3", "docx", resolve_fixture("docx", src),
                     src, tgt, "cli-md", docx_compatible,
                     f"P3 DOCX→all MD {src}→{tgt}"))

    return cases


# =========================================================================
# Pipeline Steps
# =========================================================================

def _run(cmd: list[str], label: str, timeout: int = 600) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env=_ENV, cwd=str(_SUITE_ROOT),
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{label} timed out after {timeout}s")

    if result.returncode != 0:
        err = result.stderr[-1500:] if result.stderr else "(no stderr)"
        out_tail = result.stdout[-500:] if result.stdout else ""
        raise RuntimeError(f"{label} failed (exit={result.returncode}): {err}\n{out_tail}")

    return result


def step_opp(input_path: Path, source_lang: str, target_lang: str,
             output_dir: Path, target_format: str = "xlf") -> Path:
    opp_out = output_dir / "opp_out"
    opp_out.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(_VENV_PYTHON), "-m", "opp",
        "--target-format", target_format,
        "--source-lang", source_lang,
        "--target-lang", target_lang,
        "--output-dir", str(opp_out),
        "--no-cache", str(input_path),
    ]
    _run(cmd, "OPP", timeout=120)
    return opp_out


def step_ol_md(md_path: Path, source_lang: str, target_lang: str,
               output_dir: Path, config: Path | None = None) -> Path:
    ol_out = output_dir / "ol_out"
    ol_out.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(_VENV_PYTHON), "-m", "ol_cli", "translate-md",
        str(md_path), "--source-lang", source_lang,
        "--target-lang", target_lang,
        "-o", str(ol_out), "--json", "--no-cache",
    ]
    if config and config.exists():
        cmd.extend(["--config", str(config)])
    _run(cmd, "OL-MD", timeout=3600)
    return ol_out


def step_ol_xliff(xliff_path: Path, source_lang: str, target_lang: str,
                  output_dir: Path, config: Path | None = None) -> Path:
    ol_out = output_dir / "ol_out"
    ol_out.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(_VENV_PYTHON), "-m", "ol_cli", "translate-xliff",
        str(xliff_path), "--source-lang", source_lang,
        "--target-lang", target_lang,
        "-o", str(ol_out), "--json", "--no-cache",
    ]
    if config and config.exists():
        cmd.extend(["--config", str(config)])
    _run(cmd, "OL-XLIFF", timeout=3600)
    return ol_out


# ── MCP path: start OL MCP server (stdio JSON-RPC), call tools, write output ──
def _mcp_call(tool_name: str, arguments: dict, config: Path | None,
              timeout: int = 3600) -> str:
    """Start the OL MCP server, call a tool via stdio MCP, return text.

    Uses the MCP client library for proper protocol handling (initialize
    handshake, notification sequencing). The server stays alive for the
    duration of the call and is terminated on return.
    """
    import asyncio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = os.environ.copy()
    if config and config.exists():
        env["OL_CONFIG_PATH"] = str(config)

    async def _do_call():
        params = StdioServerParameters(
            command=str(_VENV_PYTHON),
            args=["-m", "ol_mcp"],
            env=env,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments={"params": arguments})
                if result.isError:
                    raise RuntimeError(f"MCP tool error: {result.content}")
                content = result.content
                if isinstance(content, list) and content:
                    return getattr(content[0], "text", str(content[0]))
                return str(content)

    try:
        return asyncio.run(asyncio.wait_for(_do_call(), timeout=timeout))
    except Exception as e:
        # Unwrap ExceptionGroup from anyio TaskGroup to see the actual cause
        if hasattr(e, "exceptions"):
            for sub in e.exceptions:
                import traceback
                traceback.print_exception(type(sub), sub, sub.__traceback__)
            raise sub from e
        raise


def step_ol_mcp_md(md_path: Path, source_lang: str, target_lang: str,
                   output_dir: Path, config: Path | None = None) -> Path:
    ol_out = output_dir / "ol_out"
    ol_out.mkdir(parents=True, exist_ok=True)
    arguments = {
        "content": md_path.read_text(encoding="utf-8"),
        "source_lang": source_lang,
        "target_lang": target_lang,
        "add_frontmatter": True,
    }
    if config and config.exists():
        arguments["config_path"] = str(config)
    text = _mcp_call("translate_md_text", arguments, config, timeout=1800)
    import json as _json
    try:
        result = _json.loads(text)
        translated_text = result.get("translated", text)
    except (_json.JSONDecodeError, TypeError):
        translated_text = text
    output_file = ol_out / md_path.name
    output_file.write_text(translated_text, encoding="utf-8")
    return ol_out


def step_ol_mcp_xliff(xliff_path: Path, source_lang: str, target_lang: str,
                      output_dir: Path, config: Path | None = None) -> Path:
    ol_out = output_dir / "ol_out"
    ol_out.mkdir(parents=True, exist_ok=True)
    output_path = ol_out / xliff_path.name
    arguments = {
        "input_path": str(xliff_path),
        "output_path": str(output_path),
        "source_lang": source_lang,
        "target_lang": target_lang,
    }
    if config and config.exists():
        arguments["config_path"] = str(config)
    _mcp_call("translate_xliff", arguments, config, timeout=3600)
    return ol_out


def step_orf_apply_md(md_path: Path, target_format: str,
                      output_dir: Path, stem: str) -> Path:
    orf_out = output_dir / "orf_out"
    orf_out.mkdir(parents=True, exist_ok=True)
    output_path = (orf_out / f"{stem}.{target_format}").resolve()
    cmd = [
        str(_VENV_PYTHON), "-m", "orf", "apply-md",
        str(md_path.resolve()), "--target-format", target_format,
        "--output", str(output_path),
    ]
    _run(cmd, f"ORF-MD→{target_format}", timeout=120)
    return output_path


def step_orf_apply_xliff(input_path: Path, xliff_path: Path,
                         target_format: str, output_dir: Path, stem: str,
                         images_json: Path | None = None) -> Path:
    orf_out = output_dir / "orf_out"
    orf_out.mkdir(parents=True, exist_ok=True)
    output_path = (orf_out / f"{stem}.{target_format}").resolve()
    cmd = [
        str(_VENV_PYTHON), "-m", "orf", "apply-xliff",
        str(input_path.resolve()), "--xliff", str(xliff_path.resolve()),
        "--output", str(output_path), "--format", target_format,
    ]
    if images_json and images_json.exists():
        cmd.extend(["--images-json", str(images_json)])
    _run(cmd, f"ORF-XLIFF→{target_format}", timeout=120)
    return output_path


# =========================================================================
# Verification
# =========================================================================

def verify_output(output_path: Path) -> list[str]:
    errors: list[str] = []
    if not output_path.exists():
        errors.append(f"Output does not exist: {output_path}")
        return errors

    ext = output_path.suffix.lower()
    if ext == ".csv":
        return errors

    if output_path.stat().st_size == 0:
        errors.append(f"Output is empty: {output_path}")
        return errors

    ext = output_path.suffix.lower()
    try:
        if ext == ".docx":
            import zipfile
            with zipfile.ZipFile(output_path) as z:
                if "word/document.xml" not in z.namelist():
                    errors.append("DOCX missing word/document.xml")
        elif ext == ".epub":
            import zipfile
            with zipfile.ZipFile(output_path) as z:
                if "META-INF/container.xml" not in z.namelist():
                    errors.append("EPUB missing container.xml")
        elif ext == ".pdf":
            with open(output_path, "rb") as f:
                if f.read(5) != b"%PDF-":
                    errors.append("PDF missing header")
        elif ext == ".html":
            text = output_path.read_text("utf-8", errors="replace")
            if "<html" not in text.lower():
                errors.append("HTML missing <html> tag")
        elif ext == ".xml":
            text = output_path.read_text("utf-8", errors="replace")
            if not text.strip().startswith("<"):
                errors.append("XML malformed")
        elif ext == ".json":
            json.loads(output_path.read_text("utf-8"))
        elif ext == ".csv":
            pass
        elif ext == ".xlsx":
            import zipfile
            with zipfile.ZipFile(output_path) as z:
                if "xl/workbook.xml" not in z.namelist():
                    errors.append("XLSX missing workbook.xml")
        elif ext == ".ipynb":
            nb = json.loads(output_path.read_text("utf-8"))
            if "cells" not in nb:
                errors.append("IPYNB missing cells")
        elif ext == ".pptx":
            import zipfile
            with zipfile.ZipFile(output_path) as z:
                if "ppt/presentation.xml" not in z.namelist():
                    errors.append("PPTX missing presentation.xml")
    except Exception as e:
        errors.append(f"Validation failed for {ext}: {e}")

    return errors


def find_file_by_ext(directory: Path, extension: str, stem: str | None = None) -> Path | None:
    for f in directory.iterdir():
        if f.suffix == f".{extension}":
            if stem and stem not in f.stem:
                continue
            return f
    return None


# =========================================================================
# Run Test Case
# =========================================================================

@dataclass
class TestResult:
    case: TestCase
    passed: bool
    duration_s: float
    errors: list[str] = field(default_factory=list)
    output_files: list[Path] = field(default_factory=list)
    lqa_score: float | None = None


def run_test_combo(case: TestCase, run_dir: Path) -> TestResult:
    start = time.time()
    errors: list[str] = []
    output_files: list[Path] = []
    lqa_score: float | None = None

    fixture = Path(case.fixture_path)
    if not fixture.exists():
        return TestResult(case, False, time.time() - start,
                          errors=[f"Fixture not found: {fixture}"])

    stem = fixture.stem
    config = _DEFAULT_CONFIG

    try:
        # STEP 1: OPP
        if case.path_type in ("cli-md", "mcp-md"):
            opp_out = step_opp(fixture, case.source_lang, case.target_lang, run_dir, "md")
            md_path = find_file_by_ext(opp_out, "md", stem)
            if not md_path:
                errors.append(f"OPP MD output not found for {stem}")
        else:
            opp_out = step_opp(fixture, case.source_lang, case.target_lang, run_dir, "xlf")
            xliff_path = find_file_by_ext(opp_out, "xlf", stem)
            if not xliff_path:
                errors.append(f"OPP XLIFF output not found for {stem}")

        if errors:
            return TestResult(case, False, time.time() - start, errors=errors)

        # STEP 2: OL
        if case.path_type in ("cli-md", "mcp-md"):
            if case.path_type == "mcp-md":
                ol_out = step_ol_mcp_md(md_path, case.source_lang, case.target_lang, run_dir, config)
            else:
                ol_out = step_ol_md(md_path, case.source_lang, case.target_lang, run_dir, config)
            translated = find_file_by_ext(ol_out, "md")
            if not translated:
                for f in ol_out.iterdir():
                    if f.suffix in (".md", ".markdown"):
                        translated = f; break
            if not translated:
                errors.append("OL MD output not found")
                return TestResult(case, False, time.time() - start, errors=errors)
        else:
            if case.path_type == "mcp-xliff":
                ol_out = step_ol_mcp_xliff(xliff_path, case.source_lang, case.target_lang, run_dir, config)
            else:
                ol_out = step_ol_xliff(xliff_path, case.source_lang, case.target_lang, run_dir, config)
            translated = find_file_by_ext(ol_out, "xlf")
            if not translated:
                errors.append("OL XLIFF output not found")
                return TestResult(case, False, time.time() - start, errors=errors)

        # LQA from JSON report
        lqa_file = find_file_by_ext(ol_out, "json", "lqa")
        if lqa_file:
            try:
                data = json.loads(lqa_file.read_text("utf-8"))
                lqa_score = data.get("score", data.get("overall"))
                if isinstance(lqa_score, (int, float)):
                    lqa_score = float(lqa_score)
            except Exception:
                pass

        # STEP 3: ORF
        images_json = opp_out / f"{stem}_images.json"

        for out_fmt in case.output_formats:
            try:
                if case.path_type in ("cli-md", "mcp-md"):
                    out_path = step_orf_apply_md(translated, out_fmt, run_dir, stem)
                else:
                    out_path = step_orf_apply_xliff(
                        fixture, translated, out_fmt, run_dir, stem, images_json)
                output_files.append(out_path)
                verr = verify_output(out_path)
                if verr:
                    errors.append(f"{out_fmt}: {'; '.join(verr)}")
            except RuntimeError as e:
                errors.append(f"{out_fmt}: {str(e)[:200]}")
            except Exception as e:
                errors.append(f"{out_fmt}: Unexpected: {e}")

    except RuntimeError as e:
        errors.append(str(e)[:300])
    except Exception as e:
        errors.append(f"Pipeline error: {e}")

    return TestResult(case, len(errors) == 0, time.time() - start, errors, output_files, lqa_score)


# =========================================================================
# Report
# =========================================================================

def print_report(results: list[TestResult], run_id: str, tier_filter: str | None = None):
    tier_results = [r for r in results if tier_filter is None or r.case.tier == tier_filter]
    if not tier_results:
        print("No results.")
        return

    passed = [r for r in tier_results if r.passed]
    failed = [r for r in tier_results if not r.passed]

    print(f"\n{'='*70}")
    title = f"Phase 1{' [' + tier_filter + ']' if tier_filter else ''}"
    print(f"  {title}  |  Run: {run_id}")
    print(f"{'='*70}")
    print(f"  Total: {len(tier_results)}  |  ✅ GREEN: {len(passed)}  |  ❌ RED: {len(failed)}")
    print(f"{'='*70}")

    if failed:
        print("\n  ❌ FAILURES:")
        for r in failed:
            print(f"    [{r.case.tier}] {r.case.description}  ({r.duration_s:.0f}s)")
            for e in r.errors[:3]:
                for line in e.split('\n')[:2]:
                    print(f"      ⚠  {line[:150]}")
    if passed:
        print("\n  ✅ PASSED:")
        for r in passed[:25]:
            lqa = f" LQA={r.lqa_score:.2f}" if r.lqa_score else ""
            print(f"    [{r.case.tier}] {r.case.description} ({r.duration_s:.0f}s{lqa})")
        if len(passed) > 25:
            print(f"    ... +{len(passed)-25} more")

    print(f"\n  Report: {_RESULTS_DIR / run_id / 'report.json'}\n")


# =========================================================================
# Main
# =========================================================================

def main():
    parser = argparse.ArgumentParser(description="Phase 1 format matrix test runner")
    parser.add_argument("--tier", choices=["P0", "P1", "P2", "P3"], help="Run specific tier")
    parser.add_argument("--fixture", choices=list(INPUT_FORMATS.keys()), help="Run specific input format")
    parser.add_argument("--source-lang", choices=["zh", "en"], default=None,
        help="Filter by source language (default: both directions).")
    parser.add_argument("--target-lang", choices=["zh", "en"], default=None,
        help="Filter by target language (default: both directions).")
    parser.add_argument("--dry-run", action="store_true", help="Print matrix only")
    parser.add_argument("--run-id", default=None, help="Custom run identifier")
    args = parser.parse_args()

    cases = build_matrix()
    if args.tier:
        cases = [c for c in cases if c.tier == args.tier]
    if args.fixture:
        cases = [c for c in cases if c.input_format == args.fixture]
    if args.source_lang:
        cases = [c for c in cases if c.source_lang == args.source_lang]
    if args.target_lang:
        cases = [c for c in cases if c.target_lang == args.target_lang]

    if not cases:
        print("No test cases match filters.")
        return

    if args.dry_run:
        print(f"\nTest Matrix ({len(cases)} cases):")
        print("=" * 70)
        for c in cases:
            outs = ",".join(c.output_formats[:4])
            more = f"+{len(c.output_formats)-4}" if len(c.output_formats) > 4 else ""
            print(f"  [{c.tier}] {c.description} → [{outs}{more}]")
        print(f"\nTotal: {len(cases)}")
        return

    run_id = args.run_id or datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    run_dir = _RESULTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nPhase 1 Runner — {run_id}")
    print(f"Test cases: {len(cases)}")
    print(f"Run dir: {run_dir}\n")

    results: list[TestResult] = []
    for i, case in enumerate(cases, 1):
        label = f"[{i}/{len(cases)}] {case.description}"
        print(f"  {label} ... ", end="", flush=True)
        try:
            result = run_test_combo(
                case, run_dir / f"{case.tier}_{case.input_format}_{case.source_lang}2{case.target_lang}_{case.path_type}")
        except Exception as e:
            result = TestResult(case, False, 0, errors=[str(e)])
        status = "✅ GREEN" if result.passed else "❌ RED"
        print(f"{status} ({result.duration_s:.0f}s)")
        if result.errors:
            for e in result.errors[:2]:
                for line in e.split('\n')[:2]:
                    print(f"       {line[:120]}")
        results.append(result)

    print_report(results, run_id, args.tier)

    report_data = [{
        "tier": r.case.tier, "input_format": r.case.input_format,
        "source_lang": r.case.source_lang, "target_lang": r.case.target_lang,
        "path": r.case.path_type, "passed": r.passed,
        "duration_s": round(r.duration_s, 1),
        "errors": r.errors, "lqa_score": r.lqa_score,
        "output_files": [str(p) for p in r.output_files],
    } for r in results]
    report_path = run_dir / "report.json"
    report_path.write_text(json.dumps(report_data, ensure_ascii=False, indent=2))
    print(f"Report saved: {report_path}")

    sys.exit(0 if all(r.passed for r in results) else 1)


if __name__ == "__main__":
    main()
