"""omni-suite — suite-level CLI for the Omni document localization pipeline."""
from __future__ import annotations

import importlib.metadata
import os
import shutil
import subprocess
import sys
from pathlib import Path

_VERSION_FILE = Path(__file__).parent.parent / "VERSION"
_COMPAT_FILE = Path(__file__).parent.parent / "COMPATIBILITY.md"
_VENV_BIN = Path(__file__).parent.parent / ".venv_ol" / "bin"

# LLM provider keys that OL uses for translation/judging/restoration
_LLM_API_KEYS = [
    "ZHIPU_API_KEY",
    "AGNES_API_KEY",
    "NVIDIA_NIM_API_KEY",
    "OPENCODE_GO_KEY",
]

# Optional but commonly expected env vars
_OPTIONAL_VARS = [
    "OL_CONFIG_PATH",
    "OL_LOG_LEVEL",
    "OPP_LOG_LEVEL",
    "ORF_LOG_LEVEL",
    "OMNI_CACHE_DIR",
    "OMNI_LOG_FORMAT",
    "MCP_SHARED_SECRET",
    "MCP_ALLOWED_DIRECTORIES",
    "OPP_MCP_ALLOWED_DIRS",
    "ORF_MCP_ALLOWED_DIRS",
    "OL_ALLOWED_DIRECTORIES",
]


def _validate_env(require_llm: bool = False) -> None:
    """Warn or error on missing environment variables.

    Args:
        require_llm: If True, exit with error when no LLM key is found
                     (used for 'pipeline' and real translation commands).
    """
    missing_keys: list[str] = []
    for key in _LLM_API_KEYS:
        if not os.environ.get(key):
            missing_keys.append(key)

    if missing_keys:
        all_missing = len(missing_keys) == len(_LLM_API_KEYS)
        if all_missing:
            msg = (
                "⚠️  No LLM provider keys found. Set at least one of:\n"
                f"       {', '.join(_LLM_API_KEYS)}\n"
                "   Copy .env.example → .env and fill in your keys.\n"
                "   For testing, set OMNI_TEST_FAKE_LLM=1 to bypass LLM calls."
            )
        else:
            missing_list = ", ".join(missing_keys)
            msg = f"⚠️  Some LLM provider keys are unset: {missing_list}"
        if require_llm:
            print(msg, file=sys.stderr)
            sys.exit(1)
        print(msg)

    missing_optional = [k for k in _OPTIONAL_VARS if not os.environ.get(k)]
    if missing_optional and not os.environ.get("OMNI_TEST_FAKE_LLM"):
        pass  # silence optional warnings — .env.example documents them


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h"):
        _validate_env(require_llm=False)
        _print_usage()
        return
    cmd = sys.argv[1]
    if cmd == "--version":
        print(_VERSION_FILE.read_text(encoding="utf-8").strip())
    elif cmd == "--versions":
        _print_versions()
    elif cmd == "--compatibility":
        print(_COMPAT_FILE.read_text(encoding="utf-8"))
    elif cmd == "pipeline":
        _validate_env(require_llm=True)
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
        print("Usage: omni-suite pipeline <file> [--source-lang en] [--target-lang zh] [--target-format docx] [--fake-llm] --output <path>")
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
    env = {**os.environ,
           "OL_CONFIG_PATH": str(suite_root / "Omni_Localizer" / "config" / "test_universal.yaml")}
    if kwargs.get("fake-llm"):
        env["OMNI_TEST_FAKE_LLM"] = "1"

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
    """Run all 3 module test suites or readiness checks."""
    readiness = "--readiness" in args
    quick = "--quick" in args
    suite_root = Path(__file__).parent.parent

    if readiness:
        _run_readiness_check(args)
        return

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


def _run_readiness_check(args: list[str]) -> None:
    """Run the production-readiness checker."""
    checker = Path(__file__).parent.parent / "scripts" / "check_readiness.py"
    if not checker.exists():
        print("❌ Production-readiness checker not found at scripts/check_readiness.py")
        sys.exit(1)
    cmd = [sys.executable, str(checker)]
    if "--verbose" in args or "-v" in args:
        cmd.append("--verbose")
    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
    sys.exit(result.returncode)


_DISTRIBUTIONS = [
    ("omni-suite", "omni-suite"),
    ("opp", "omni-pre-processor"),
    ("ol", "omni-localizer"),
    ("orf", "omni-re-formatter"),
]


def _print_versions() -> None:
    """Print all 4 component versions from importlib.metadata."""
    for label, dist in _DISTRIBUTIONS:
        try:
            ver = importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            ver = "N/A (not installed)"
        print(f"{label}: {ver}")


def _print_usage() -> None:
    print("Usage: omni-suite <command> [options]")
    print("Commands:")
    print("  --version              Print suite version")
    print("  --versions             Print all component versions")
    print("  --compatibility        Print version compatibility matrix")
    print("  pipeline <file>        Run OPP→OL→ORF pipeline on a file")
    print("    --fake-llm           Use fake LLM mode (bypasses API keys)")
    print("  check [--quick|--readiness[ --verbose]]")
    print("                         Run all module tests, quick-env check,")
    print("                         or production-readiness check")
    print("  status                 Show env, dependency, and version status")


if __name__ == "__main__":
    main()
