"""omni-suite — suite-level CLI for the Omni document localization pipeline."""
from __future__ import annotations

import importlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import cli_json, run_manifest

_VERSION_FILE = Path(__file__).parent.parent / "VERSION"
_COMPAT_FILE = Path(__file__).parent.parent / "COMPATIBILITY.md"
_VENV_BIN = Path(__file__).parent.parent / ".venv_ol" / "bin"

# The three sub-repos, in report order. Single source of truth for both
# `check` (which runs their test suites) and `status` (which reads their
# versions).
_MODULE_DIRS: tuple[tuple[str, str], ...] = (
    ("OPP", "Omni_Pre_Processor"),
    ("OL", "Omni_Localizer"),
    ("ORF", "Omni_Re_Formatter"),
)

# MCP-aligned error codes (omni_mcp/_errors.py) for a failing pipeline stage.
_STAGE_ERROR_CODES = {
    "opp": "OPP_FAILED",
    "ol": "OL_FAILED",
    "orf": "ORF_FAILED",
}

#: Machine-readable output mode for this invocation (``omni-suite --json``).
#: Inactive ⇒ every method is a no-op and the CLI behaves exactly as before.
_JSON = cli_json.JsonOutput()

# Canonical LLM provider keys OL uses for translation/judging/restoration —
# the priorities in Omni_Localizer/config/default.yaml
# (DeepSeek-V4.1-Flash, glm-4.7-flash).
_LLM_API_KEYS = [
    "AMD_API_KEY",
    "ZHIPU_API_KEY",
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
        require_llm: If True, exit with error when NO LLM provider key is
                     found (used for 'pipeline' and real translation
                     commands). One canonical key is enough — the remaining
                     entries are fallbacks the router skips.
    """
    # A var set to "" is absent: os.environ.get mirrors how OL resolves the
    # model pool, so one configured provider satisfies the gate and the rest
    # are optional fallbacks (AGENTS.md: "Only set env vars for providers you
    # use.").
    present_keys = [k for k in _LLM_API_KEYS if os.environ.get(k)]
    missing_keys = [k for k in _LLM_API_KEYS if not os.environ.get(k)]

    if not present_keys:
        msg = (
            "⚠️  No LLM provider keys found. Set at least one of:\n"
            f"       {', '.join(_LLM_API_KEYS)}\n"
            "   Copy .env.example → .env and fill in your keys.\n"
            "   For testing, set OMNI_TEST_FAKE_LLM=1 to bypass LLM calls."
        )
        # T-05: agents parse stdout — the warning belongs on stderr.
        print(msg, file=sys.stderr)
        if require_llm:
            _JSON.failure(
                1,
                "OMNI_MISSING_LLM_KEYS",
                "No LLM provider keys found — set at least one of: "
                + ", ".join(_LLM_API_KEYS),
            )
    elif missing_keys:
        # At least one provider is configured; the unset entries are fallbacks
        # the router skips, not a misconfiguration. Names only — never echo
        # resolved key values.
        msg = (
            f"ℹ️  Using {', '.join(present_keys)}; "
            f"{', '.join(missing_keys)} unset (fallbacks, will be skipped)."
        )
        # T-05: agents parse stdout — the note belongs on stderr.
        print(msg, file=sys.stderr)

    missing_optional = [k for k in _OPTIONAL_VARS if not os.environ.get(k)]
    if missing_optional and not os.environ.get("OMNI_TEST_FAKE_LLM"):
        pass  # silence optional warnings — .env.example documents them


def _no_llm_needed(args: list[str]) -> bool:
    """True when a pipeline invocation needs no LLM provider key.

    ``--dry-run`` executes nothing; ``--gates-only`` skips ORF and
    ``--fake-llm`` selects the fake seam — all three satisfy the env gate.
    """
    return "--dry-run" in args or "--gates-only" in args or "--fake-llm" in args


def main() -> None:
    """Entry point: ``omni-suite [--json] <command> [options]``."""
    json_mode, argv = cli_json.split_json_flag(sys.argv[1:])
    _JSON.reset(active=json_mode, command=argv[0] if argv else "--help")
    try:
        with _JSON.human_output_on_stderr():
            content = _dispatch(argv)
    except Exception as exc:
        # The envelope is the only channel an agent has left, so a crash must
        # still answer. Inactive mode re-raises to keep the traceback intact.
        if not _JSON.active:
            raise
        _JSON.failure(1, "OMNI_INTERNAL_ERROR", f"{type(exc).__name__}: {exc}")
    # SystemExit is a BaseException and never reaches here: every failure site
    # emits its own envelope before exiting (see _JSON.failure).
    _JSON.success(content)


def _dispatch(argv: list[str]) -> dict[str, Any]:
    """Route *argv* (already stripped of ``--json``) and return its payload."""
    if not argv or argv[0] in ("--help", "-h"):
        _validate_env(require_llm=False)
        return {"usage": _JSON.human(_print_usage)}
    cmd = argv[0]
    if cmd == "--version":
        return _print_version()
    if cmd == "--versions":
        return _print_versions()
    if cmd == "--compatibility":
        return {
            "compatibility": _JSON.human(
                lambda: print(_COMPAT_FILE.read_text(encoding="utf-8"))
            )
        }
    if cmd in ("pipeline", "translate"):
        remaining = argv[1:]
        # Show help without requiring API keys
        if not remaining or remaining[0] in ("--help", "-h"):
            return _run_pipeline(["--help"])
        # Non-obvious: gates-only/fake-llm run real OPP/OL subprocesses,
        # yet none of the three bypass flags needs an LLM key at this boundary.
        _validate_env(require_llm=not _no_llm_needed(remaining))
        return _run_pipeline(remaining)
    if cmd == "check":
        return _run_check(argv[1:])
    if cmd == "status":
        return _run_status(argv[1:])

    _JSON.human(lambda: print(f"Unknown command: {cmd}"))
    usage = _JSON.human(_print_usage)
    _JSON.failure(
        1, "OMNI_UNKNOWN_COMMAND", f"Unknown command: {cmd}", content={"usage": usage}
    )


def _resolve_tool(name: str) -> str:
    """Prefer the suite venv's tool: pip-installed copies (e.g. ~/.local/bin)
    run without the repo config context and fail on config resolution."""
    venv_tool = _VENV_BIN / name
    if venv_tool.exists():
        return str(venv_tool)
    return shutil.which(name) or name


def _run_pipeline(args: list[str]) -> dict[str, Any]:
    """Orchestrate OPP → OL → ORF on a single file.

    Usage: omni-suite pipeline <file> [--source-lang en] [--target-lang zh] [--target-format docx] [--fake-llm] [--resume-from opp|ol|orf] [--run-id ID] [--output <path>]
    """
    if not args or args[0] in ("--help", "-h"):
        return {
            "usage": _JSON.human(
                lambda: print(
                    "Usage: omni-suite pipeline <file> [--source-lang en] "
                    "[--target-lang zh] [--target-format docx] [--fake-llm] "
                    "[--resume-from opp|ol|orf] [--run-id ID] --output <path>"
                )
            )
        }

    # Parse args
    file_path, kwargs = _parse_pipeline_args(args)
    src = kwargs.get("source-lang", "en")
    tgt = kwargs.get("target-lang", "zh")
    fmt = kwargs.get("target-format", "docx")
    output = kwargs.get("output")
    dry_run = bool(kwargs.get("dry-run"))
    gates_only = bool(kwargs.get("gates-only"))
    keep_intermediate = bool(kwargs.get("keep-intermediate"))
    resume_from = kwargs.get("resume-from")
    run_id = kwargs.get("run-id") or Path(file_path).stem

    if resume_from is True or (resume_from is not None and resume_from not in run_manifest.STAGES):
        message = (
            f"Invalid --resume-from {resume_from!r}; "
            f"expected one of {', '.join(run_manifest.STAGES)}"
        )
        print(f"❌ {message}", file=sys.stderr)
        _JSON.failure(2, "OMNI_INVALID_INPUT", message)

    suite_root = Path(__file__).parent.parent
    opp = _resolve_tool("opp")
    ol = _resolve_tool("ol")
    orf = _resolve_tool("orf")
    env = {**os.environ,
           "OL_CONFIG_PATH": str(suite_root / "Omni_Localizer" / "config" / "test_universal.yaml")}
    if kwargs.get("fake-llm"):
        env["OMNI_TEST_FAKE_LLM"] = "1"

    stem = Path(file_path).stem
    temp_dir = Path("/tmp/omni-suite-pipeline") / run_id
    opp_dir = temp_dir / "opp"
    ol_dir = temp_dir / "ol"
    # T-02: the auto-generated output must NOT live inside temp_dir — the
    # finally block removes that dir, which would delete the artifact we
    # report at exit. Place it as a sibling of the temp dir instead.
    out_path = output or str(temp_dir.parent / f"{stem}.result.{fmt}")

    opp_cmd = [opp, file_path, "--target-format", "both",
               "--source-lang", src, "--target-lang", tgt,
               "--output-dir", str(opp_dir)]

    if dry_run:
        ol_cmd = [ol, "translate-md", str(opp_dir / f"{stem}.md"), "-s", src, "-t", tgt, "-o", str(ol_dir)]
        orf_cmd = [orf, "apply-md", str(ol_dir / f"{stem}.md"), "--target-format", fmt, "-o", out_path]
        print(f"[1/3] OPP would run: {shlex.join(opp_cmd)}")
        print(f"[2/3] OL would run: {shlex.join(ol_cmd)}")
        print(f"[3/3] ORF would run: {shlex.join(orf_cmd)}")
        return {
            "dry_run": True,
            "input": file_path,
            "output": out_path,
            "commands": [shlex.join(c) for c in (opp_cmd, ol_cmd, orf_cmd)],
        }

    # R-01: decide which stages to reuse BEFORE touching the filesystem. A
    # missing intermediate (or a stale manifest whose artifacts were deleted)
    # means the requested resume cannot be honoured — fall back to a full run.
    skip_stages = run_manifest.plan_resume(resume_from, opp_dir, ol_dir)
    resumed = bool(skip_stages)

    manifest_path = temp_dir / run_manifest.MANIFEST_NAME
    prior_manifest = None
    if manifest_path.exists():
        try:
            prior_manifest = run_manifest.RunManifest.load(manifest_path)
        except (OSError, ValueError):
            prior_manifest = None

    manifest = run_manifest.RunManifest(
        run_id=run_id,
        input_file=str(Path(file_path).resolve()),
        temp_dir=str(temp_dir),
        output=str(out_path),
        source_lang=src,
        target_lang=tgt,
        target_format=fmt,
    )
    if prior_manifest is not None:
        manifest.created_at = prior_manifest.created_at
        manifest.stages = prior_manifest.stages

    opp_dir.mkdir(parents=True, exist_ok=True)
    ol_dir.mkdir(exist_ok=True)

    failed = False
    current_stage = "opp"
    manifest.save(manifest_path)

    try:
        # Step 1: OPP extract
        if "opp" in skip_stages:
            print(f"[1/3] OPP reuse existing intermediates ({opp_dir})")
            manifest.mark("opp", run_manifest.REUSED, str(opp_dir))
        else:
            print(f"[1/3] OPP extracting {file_path} → {opp_dir}")
            manifest.mark("opp", run_manifest.RUNNING)
            manifest.save(manifest_path)
            subprocess.run(opp_cmd, check=True, env=env, timeout=120, **_JSON.stage_stdout())
            manifest.mark("opp", run_manifest.COMPLETE, str(opp_dir))
            manifest.save(manifest_path)

        md_file = next(opp_dir.glob("*.md"), None)
        if not md_file:
            raise RuntimeError("OPP did not produce .md output")

        # Step 2: OL translate
        current_stage = "ol"
        if "ol" in skip_stages:
            print(f"[2/3] OL reuse existing intermediates ({ol_dir})")
            manifest.mark("ol", run_manifest.REUSED, str(ol_dir))
        else:
            print(f"[2/3] OL translating {md_file}")
            manifest.mark("ol", run_manifest.RUNNING)
            manifest.save(manifest_path)
            ol_cmd = [ol, "translate-md", str(md_file), "-s", src, "-t", tgt, "-o", str(ol_dir)]
            ol_result = None
            if gates_only:
                ol_result = subprocess.run(ol_cmd, check=True, env=env, timeout=300,
                                           capture_output=True, text=True)
            else:
                subprocess.run(ol_cmd, check=True, env=env, timeout=300,
                               **_JSON.stage_stdout())
            manifest.mark("ol", run_manifest.COMPLETE, str(ol_dir))
            manifest.save(manifest_path)

        ol_md = next(ol_dir.glob("*.md"), None)
        if not ol_md:
            raise RuntimeError("OL did not produce translated output")

        if gates_only:
            manifest.mark("orf", run_manifest.SKIPPED, "gates-only")
            manifest.status = run_manifest.RUN_COMPLETE
            manifest.save(manifest_path)
            print("[gates-only] Skipping ORF backfill — extracting OL quality-gate warnings")
            warnings_run = subprocess.run([ol, "extract-warnings", str(ol_md)],
                                          capture_output=True, text=True,
                                          env=env, timeout=120)
            print(warnings_run.stdout, end="")
            if warnings_run.returncode != 0:
                tail = (ol_result.stdout or "")[-2000:] if ol_result else ""
                if tail.strip():
                    print("--- OL translate-md stdout (tail) ---")
                    print(tail)
                print("(ol extract-warnings unavailable — showing OL stdout tail instead)")
            return _manifest_payload(manifest, gates_only=True, warnings=warnings_run.stdout)

        # Step 3: ORF backfill
        current_stage = "orf"
        print(f"[3/3] ORF backfilling → {out_path}")
        manifest.mark("orf", run_manifest.RUNNING)
        manifest.save(manifest_path)
        subprocess.run([orf, "apply-md", str(ol_md), "--target-format", fmt, "-o", out_path],
                       check=True, env=env, timeout=120, **_JSON.stage_stdout())
        manifest.mark("orf", run_manifest.COMPLETE, out_path)
        manifest.status = run_manifest.RUN_COMPLETE
        manifest.save(manifest_path)

        print(f"✅ Pipeline complete: {out_path}")
        return _manifest_payload(manifest)
    except KeyboardInterrupt:
        failed = True
        manifest.mark(current_stage, run_manifest.FAILED, "interrupted")
        manifest.save(manifest_path)
        _print_partial(manifest)
        print("❌ Interrupted — intermediates kept for --resume-from", file=sys.stderr)
        _JSON.failure(130, "OMNI_INTERRUPTED",
                      "Interrupted — intermediates kept for --resume-from",
                      _manifest_payload(manifest))
    except subprocess.TimeoutExpired:
        failed = True
        manifest.mark(current_stage, run_manifest.FAILED, "timeout")
        manifest.save(manifest_path)
        _print_partial(manifest)
        print("❌ Timeout: a pipeline step exceeded its time limit", file=sys.stderr)
        _JSON.failure(1, "CLI_TIMEOUT",
                      "Timeout: a pipeline step exceeded its time limit",
                      _manifest_payload(manifest))
    except subprocess.CalledProcessError as e:
        failed = True
        manifest.mark(current_stage, run_manifest.FAILED, f"exit {e.returncode}")
        manifest.save(manifest_path)
        _print_partial(manifest)
        print(f"❌ Pipeline step failed: {e}", file=sys.stderr)
        _JSON.failure(1, _STAGE_ERROR_CODES.get(current_stage, "OMNI_INTERNAL_ERROR"),
                      f"Pipeline step failed: {e}", _manifest_payload(manifest))
    except Exception as e:
        failed = True
        manifest.mark(current_stage, run_manifest.FAILED, type(e).__name__)
        manifest.save(manifest_path)
        _print_partial(manifest)
        print(f"❌ Pipeline error: {e}", file=sys.stderr)
        _JSON.failure(1, "OMNI_INTERNAL_ERROR", f"Pipeline error: {e}",
                      _manifest_payload(manifest))

    finally:
        if keep_intermediate or gates_only:
            print(f"Intermediate files kept at: {temp_dir}")
        elif Path(out_path).resolve().is_relative_to(temp_dir.resolve()):
            print(f"Intermediate files kept at: {temp_dir}")
        elif failed or resumed:
            label = "kept for --resume-from" if failed else "kept as run record"
            print(f"Intermediate files {label} at: {temp_dir}",
                  file=sys.stderr if failed else sys.stdout)
        else:
            shutil.rmtree(temp_dir, ignore_errors=True)


def _manifest_payload(
    manifest: run_manifest.RunManifest, **extra: Any
) -> dict[str, Any]:
    """Machine payload for a pipeline run: manifest summary + stage states."""
    return {
        "run": manifest.summary(),
        "input": manifest.input_file,
        "output": manifest.output,
        "stages": {s: st.to_dict() for s, st in manifest.stages.items()},
        **extra,
    }


def _print_partial(manifest) -> None:
    """Machine-readable partial-run report (R-01) — one JSON object on stdout."""
    print(json.dumps(manifest.summary(), ensure_ascii=False))


def _parse_pipeline_args(args: list[str]) -> tuple[str, dict]:
    """Parse key=value or --key value style pipeline args."""
    file_path = args[0]
    kwargs: dict[str, str | bool] = {}
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


def _run_check(args: list[str]) -> dict[str, Any]:
    """Run all 3 module test suites or readiness checks."""
    if "--readiness" in args:
        return _run_readiness_check(args)
    if "--quick" in args:
        return _run_quick_check()
    return _run_module_tests(Path(__file__).parent.parent)


def _run_quick_check() -> dict[str, Any]:
    """Dependency/env probe behind ``check --quick``."""
    pandoc = shutil.which("pandoc")
    weasyprint = _module_available("weasyprint")
    fake_llm = os.environ.get("OMNI_TEST_FAKE_LLM")
    print("Quick check: dependencies and env")
    print(f"  pandoc: {'✅' if pandoc else '❌'} {pandoc or 'not found'}")
    print(f"  weasyprint: {'✅' if weasyprint else '❌ not installed'}")
    print(f"  OMNI_TEST_FAKE_LLM: {'✅' if fake_llm else '❌'} set={bool(fake_llm)}")
    return {
        "quick": True,
        "pandoc": pandoc,
        "weasyprint": weasyprint,
        "fake_llm": bool(fake_llm),
    }


def _run_module_tests(suite_root: Path) -> dict[str, Any]:
    """Run each module's pytest suite; report each summary line.

    Never fails the command: a red module suite is reported in the payload, and
    the exit code stays 0 as it has always been.
    """
    results: list[dict[str, Any]] = []
    for name, rel in _MODULE_DIRS:
        path = suite_root / rel
        if not (path / "tests").exists():
            print(f"  {name}: tests/ not found — skip")
            results.append({"module": name, "status": "skipped"})
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
        results.append({
            "module": name,
            "status": "passed" if passed else "failed",
            "returncode": result.returncode,
            "summary": last,
        })
    return {"modules": results}


def _run_status(args: list[str]) -> dict[str, Any]:
    """Show env, dependency, and version status."""
    modules = _module_versions()
    dependencies = {
        "pandoc": shutil.which("pandoc"),
        "weasyprint": _module_available("weasyprint"),
        "aspose.email": _module_available("aspose.email"),
        "fake_llm": bool(os.environ.get("OMNI_TEST_FAKE_LLM")),
    }
    _print_status(_VERSION_FILE.read_text(encoding="utf-8").strip(), modules, dependencies)
    return {
        "suite": _read_repo_version(_VERSION_FILE),
        "modules": modules,
        "dependencies": dependencies,
    }


def _module_versions() -> dict[str, str]:
    """Each sub-repo's ``pyproject.toml`` version, ``?`` when undiscoverable."""
    suite_root = Path(__file__).parent.parent
    versions = {}
    for name, rel in _MODULE_DIRS:
        pyproject = suite_root / rel / "pyproject.toml"
        version = "?"
        if pyproject.exists():
            for line in pyproject.read_text().splitlines():
                if line.startswith("version ="):
                    version = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        versions[name] = version
    return versions


def _module_available(name: str) -> bool:
    """True when *name* imports — the probe behind the ✅/❌ dependency lines."""
    try:
        importlib.import_module(name)
    except ImportError:
        return False
    return True


def _print_status(
    suite_text: str, modules: dict[str, str], dependencies: dict[str, Any]
) -> None:
    print(f"Omni Suite: {suite_text}")
    print()

    for name, version in modules.items():
        print(f"  {name}: {version}")

    print()
    print("Dependencies:")
    print(f"  pandoc:       {dependencies['pandoc'] or '❌ not found'}")
    print(f"  weasyprint:   {'✅' if dependencies['weasyprint'] else '❌ not installed'}")
    print(f"  aspose.email: {'✅ (.msg available)' if dependencies['aspose.email'] else '❌ not installed (.msg requires)'}")
    print(f"  FAKE_LLM:     {'set' if dependencies['fake_llm'] else 'not set'}")


def _run_readiness_check(args: list[str]) -> dict[str, Any]:
    """Run the production-readiness checker."""
    checker = Path(__file__).parent.parent / "scripts" / "check_readiness.py"
    if not checker.exists():
        print("❌ Production-readiness checker not found at scripts/check_readiness.py")
        _JSON.failure(
            1,
            "CLI_NOT_FOUND",
            "Production-readiness checker not found at scripts/check_readiness.py",
        )
    cmd = [sys.executable, str(checker)]
    if "--verbose" in args or "-v" in args:
        cmd.append("--verbose")
    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent,
                            **_JSON.stage_stdout())
    content = {
        "checker": str(checker),
        "returncode": result.returncode,
        "verbose": len(cmd) > 2,
    }
    if result.returncode != 0:
        _JSON.failure(
            result.returncode,
            "OMNI_READINESS_FAILED",
            f"Production-readiness check failed (exit {result.returncode})",
            content,
        )
    _JSON.success(content)
    sys.exit(0)


_VERSION_SOURCES = [
    ("omni-suite", _VERSION_FILE),
    ("opp", Path(__file__).parent.parent / "Omni_Pre_Processor" / "pyproject.toml"),
    ("ol", Path(__file__).parent.parent / "Omni_Localizer" / "pyproject.toml"),
    ("orf", Path(__file__).parent.parent / "Omni_Re_Formatter" / "pyproject.toml"),
]


def _read_repo_version(path: Path) -> str:
    """Read a component version from a repo ``VERSION`` or ``pyproject.toml``.

    Installed importlib metadata goes stale whenever a version is bumped
    without reinstalling; the repo files are the source of truth (T-05).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return "N/A (not found)"
    if path.name == "VERSION":
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                return stripped
        return "N/A (not found)"
    for line in text.splitlines():
        if line.startswith("version ="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return "N/A (not found)"


def _print_version() -> dict[str, Any]:
    """Print the suite version file, exactly as ``--version`` always has."""
    text = _JSON.human(
        lambda: print(_VERSION_FILE.read_text(encoding="utf-8").strip())
    )
    return {"version": _read_repo_version(_VERSION_FILE), "text": text}


def _print_versions() -> dict[str, Any]:
    """Print all 4 component versions from the repo source of truth."""
    versions = {label: _read_repo_version(path) for label, path in _VERSION_SOURCES}

    def emit() -> None:
        for label, value in versions.items():
            print(f"{label}: {value}")

    _JSON.human(emit)
    return {"versions": versions}


def _print_usage() -> None:
    print("Usage: omni-suite <command> [options]")
    print("")
    print("Commands:")
    print("  --version              Print suite version")
    print("  --versions             Print all component versions")
    print("  --compatibility        Print version compatibility matrix")
    print("  translate|pipeline <file>")
    print("                         Run OPP→OL→ORF pipeline on a file")
    print("    --source-lang LANG   Source language (default: en)")
    print("    --target-lang LANG   Target language (default: zh)")
    print("    --target-format FMT  Output format (default: docx)")
    print("                         Supports any of ORF's 16 formats")
    print("    --fake-llm           Use fake LLM mode (bypasses API keys)")
    print("    --output PATH        Output file path (auto-generated if omitted)")
    print("    --dry-run            Print the 3 pipeline commands and exit")
    print("                         (executes nothing, creates no files)")
    print("    --gates-only         Run OPP+OL (incl. 8 quality gates) and")
    print("                         print extract-warnings; skips ORF backfill")
    print("    --resume-from STAGE  Resume a partial run (opp|ol|orf): reuse")
    print("                         intermediates of prior stages and continue")
    print("    --run-id ID          Run directory name under /tmp/omni-suite-pipeline")
    print("                         (default: input file stem); targets a prior run")
    print("    --keep-intermediate  Keep /tmp/omni-suite-pipeline/<stem> after run")
    print("")
    print("  Pipeline path selection:")
    print("    MD path (default):   omni-suite translate <file> --target-format <fmt>")
    print("                         Uses OPP→OL(translate-md)→ORF(apply-md).")
    print("                         Best for text-first output in any of 16 formats.")
    print("                         See --target-format for supported formats.")
    print("    XLIFF path (manual): opp <file> --target-format xlf ...")
    print("                         Then: ol translate-xliff ...")
    print("                         Then: orf apply-xliff ...")
    print("                         Best for exact original layout preservation.")
    print("")
    print("  check [--quick|--readiness[ --verbose]]")
    print("                         Run all module tests, quick-env check,")
    print("                         or production-readiness check")
    print("  status                 Show env, dependency, and version status")


if __name__ == "__main__":
    main()
