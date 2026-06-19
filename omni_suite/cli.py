"""omni-suite — suite-level CLI for the Omni document localization pipeline."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_VERSION_FILE = Path(__file__).parent.parent / "VERSION"
_COMPAT_FILE = Path(__file__).parent.parent / "COMPATIBILITY.md"
_VENV_BIN = Path(__file__).parent.parent / ".venv_ol" / "bin"


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h"):
        _print_usage()
        return
    cmd = sys.argv[1]
    if cmd == "--version":
        print(_VERSION_FILE.read_text(encoding="utf-8").strip())
    elif cmd == "--compatibility":
        print(_COMPAT_FILE.read_text(encoding="utf-8"))
    elif cmd == "pipeline":
        _run_pipeline(sys.argv[2:])
    elif cmd == "check":
        _run_check(sys.argv[2:])
    elif cmd == "status":
        _run_status(sys.argv[2:])
    else:
        print(f"Unknown command: {cmd}")
        _print_usage()
        sys.exit(1)


def _run_pipeline(args: list[str]) -> None:
    """Orchestrate OPP → OL → ORF on a single file.
    
    Usage: omni-suite pipeline <file> [--source-lang en] [--target-lang zh] [--target-format docx] [--output <path>]
    """
    if not args or args[0] in ("--help", "-h"):
        print("Usage: omni-suite pipeline <file> [--source-lang en] [--target-lang zh] [--target-format docx] --output <path>")
        return
    
    # Parse args
    file_path, kwargs = _parse_pipeline_args(args)
    src = kwargs.get("source-lang", "en")
    tgt = kwargs.get("target-lang", "zh")
    fmt = kwargs.get("target-format", "docx")
    output = kwargs.get("output")
    
    suite_root = Path(__file__).parent.parent
    opp = shutil.which("opp") or f"{_VENV_BIN}/opp"
    ol = shutil.which("ol") or f"{_VENV_BIN}/ol"
    orf = shutil.which("orf") or f"{_VENV_BIN}/orf"
    env = {**os.environ, "OMNI_TEST_FAKE_LLM": "1",
           "OL_CONFIG_PATH": str(suite_root / "Omni_Localizer" / "config" / "test_universal.yaml")}
    
    temp_dir = Path("/tmp/omni-suite-pipeline") / Path(file_path).stem
    temp_dir.mkdir(parents=True, exist_ok=True)
    opp_dir = temp_dir / "opp"
    ol_dir = temp_dir / "ol"
    opp_dir.mkdir(exist_ok=True); ol_dir.mkdir(exist_ok=True)
    
    try:
        # Step 1: OPP extract
        print(f"[1/3] OPP extracting {file_path} → {opp_dir}")
        subprocess.run([opp, file_path, "--target-format", "both",
                       "--source-lang", src, "--target-lang", tgt,
                       "--output-dir", str(opp_dir)], check=True, env=env, timeout=120)
        
        md_file = next(opp_dir.glob("*.md"), None)
        if not md_file:
            raise RuntimeError("OPP did not produce .md output")
        
        # Step 2: OL translate
        print(f"[2/3] OL translating {md_file}")
        subprocess.run([ol, "translate-md", str(md_file), "-s", src, "-t", tgt, "-o", str(ol_dir)],
                      check=True, env=env, timeout=300)
        
        ol_md = next(ol_dir.glob("*.md"), None)
        if not ol_md:
            raise RuntimeError("OL did not produce translated output")
        
        # Step 3: ORF backfill
        print(f"[3/3] ORF backfilling → {output or f'{temp_dir}/result.{fmt}'}")
        out_path = output or f"{temp_dir}/result.{fmt}"
        subprocess.run([orf, "apply-md", str(ol_md), "--target-format", fmt, "-o", out_path],
                      check=True, env=env, timeout=120)
        
        print(f"✅ Pipeline complete: {out_path}")
    except subprocess.TimeoutExpired:
        print("❌ Timeout: a pipeline step exceeded its time limit", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"❌ Pipeline step failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Pipeline error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _parse_pipeline_args(args: list[str]) -> tuple[str, dict]:
    """Parse key=value or --key value style pipeline args."""
    file_path = args[0]
    kwargs = {}
    i = 1
    while i < len(args):
        if args[i].startswith("--"):
            key = args[i][2:]
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                kwargs[key] = args[i + 1]
                i += 2
            else:
                kwargs[key] = True
                i += 1
        elif "=" in args[i]:
            k, v = args[i].split("=", 1)
            kwargs[k] = v
            i += 1
        else:
            i += 1
    return file_path, kwargs


def _run_check(args: list[str]) -> None:
    """Run all 3 module test suites and report pass/fail counts."""
    quick = "--quick" in args
    suite_root = Path(__file__).parent.parent
    
    modules = [
        ("OPP", suite_root / "Omni_Pre_Processor"),
        ("OL", suite_root / "Omni_Localizer"),
        ("ORF", suite_root / "Omni_Re_Formatter"),
    ]
    
    if quick:
        print("Quick check: dependencies and env")
        # Check pandoc
        pandoc = shutil.which("pandoc")
        print(f"  pandoc: {'✅' if pandoc else '❌'} {pandoc or 'not found'}")
        # WeasyPrint
        try:
            import weasyprint  # noqa
            print("  weasyprint: ✅")
        except ImportError:
            print("  weasyprint: ❌ not installed")
        # FAKE_LLM
        print(f"  OMNI_TEST_FAKE_LLM: {'✅' if os.environ.get('OMNI_TEST_FAKE_LLM') else '❌'} set={bool(os.environ.get('OMNI_TEST_FAKE_LLM'))}")
        return
    
    for name, path in modules:
        if not (path / "tests").exists():
            print(f"  {name}: tests/ not found — skip")
            continue
        print(f"  Running {name} tests...")
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(path / "tests"), "-q", "--no-header"],
            capture_output=True, text=True, timeout=600, cwd=str(suite_root),
        )
        lines = result.stdout.strip().split("\n")
        last = lines[-1] if lines else "(no output)"
        passed = " passed" in last
        print(f"  {name}: {'✅' if passed else '❌'} {last}")


def _run_status(args: list[str]) -> None:
    """Show env, dependency, and version status."""
    suite_root = Path(__file__).parent.parent
    
    print(f"Omni Suite: {_VERSION_FILE.read_text(encoding='utf-8').strip()}")
    print()
    
    # Module versions
    for name, path in [
        ("OPP", suite_root / "Omni_Pre_Processor"),
        ("OL", suite_root / "Omni_Localizer"),
        ("ORF", suite_root / "Omni_Re_Formatter"),
    ]:
        pyproject = path / "pyproject.toml"
        version = "?"
        if pyproject.exists():
            for line in pyproject.read_text().splitlines():
                if line.startswith("version ="):
                    version = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        print(f"  {name}: {version}")
    
    print()
    print("Dependencies:")
    print(f"  pandoc:       {shutil.which('pandoc') or '❌ not found'}")
    try:
        import weasyprint; del weasyprint; print("  weasyprint:   ✅")
    except ImportError:
        print("  weasyprint:   ❌ not installed")
    try:
        import aspose.email; del aspose.email; print("  aspose.email: ✅ (.msg available)")
    except ImportError:
        print("  aspose.email: ❌ not installed (.msg requires)")
    print(f"  FAKE_LLM:     {'set' if os.environ.get('OMNI_TEST_FAKE_LLM') else 'not set'}")


def _print_usage() -> None:
    print("Usage: omni-suite <command> [options]")
    print("Commands:")
    print("  --version              Print suite version")
    print("  --compatibility        Print version compatibility matrix")
    print("  pipeline <file>        Run OPP→OL→ORF pipeline on a file")
    print("  check [--quick]        Run all module tests or quick-env check")
    print("  status                 Show env, dependency, and version status")
