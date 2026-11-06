#!/usr/bin/env python3
"""Production-readiness checker for Omni Suite.

Auto-verifies all 🔧 items from PRODUCTION_READINESS.md.
Reports pass/fail per version (V1..V11) and outputs an overall score.

Usage:
    python scripts/check_readiness.py              # quick score
    python scripts/check_readiness.py --verbose     # detailed per-item output
    python scripts/check_readiness.py --json        # machine-readable JSON
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

SUITE_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = SUITE_ROOT / "VERSION"
COMPAT_FILE = SUITE_ROOT / "COMPATIBILITY.md"
MODULES = {
    "OPP": SUITE_ROOT / "Omni_Pre_Processor",
    "OL": SUITE_ROOT / "Omni_Localizer",
    "ORF": SUITE_ROOT / "Omni_Re_Formatter",
}
MCP_ENTRY_POINTS = {
    "OPP": "opp-mcp-server",
    "OL": "ol-mcp",
    "ORF": "orf-mcp-server",
}
CI_WORKFLOW = SUITE_ROOT / ".github" / "workflows" / "e2e-tests.yml"
PRE_COMMIT_CONFIG = SUITE_ROOT / ".pre-commit-config.yaml"
MAKEFILE = SUITE_ROOT / "Makefile"
SETUP_SCRIPT = SUITE_ROOT / "scripts" / "setup_dev.sh"
PROD_TEST_DIR = SUITE_ROOT / "tests" / "production"
OBSERVABILITY_DIR = SUITE_ROOT / "tests" / "observability"
SECURITY_DIR = SUITE_ROOT / "tests" / "security"
SMOKE_TEST = SUITE_ROOT / "tests" / "test_pipeline_contract_smoke.py"

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except Exception as e:
        return f"<error: {e}>"


def _parse_pyproject_version(pyproject: Path) -> str | None:
    try:
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("version")
    except Exception:
        return None


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 10) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd or SUITE_ROOT)
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        return -1, "", f"binary not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -2, "", f"timed out after {timeout}s"
    except Exception as e:
        return -3, "", str(e)


def _which(name: str) -> bool:
    return shutil.which(name) is not None


def _version_file_suite_version() -> str:
    """Last non-comment, non-empty line of VERSION (first two lines are comments)."""
    return next(
        (
            ln.strip()
            for ln in reversed(_read(VERSION_FILE).splitlines())
            if ln.strip() and not ln.lstrip().startswith("#")
        ),
        "",
    )


def _compat_last_data_row(compat_text: str) -> list[str] | None:
    """Fields of the LAST 5-column data row in COMPATIBILITY.md.

    The matrix is append-only, so the last row is the newest pinned set
    (header ``| Suite | OL | OPP | ORF | Notes |`` is line 3; the first data
    row is line 5 and holds historical versions only).
    """
    last: list[str] | None = None
    for line in compat_text.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        if "Suite" in line or set(stripped) <= set("|-: "):
            continue
        parts = [p.strip() for p in stripped.strip("|").split("|")]
        if len(parts) >= 5 and re.fullmatch(r"[\d.]+", parts[0] or ""):
            last = parts
    return last


_PROVIDER_SDKS = frozenset({"openai", "litellm", "zhipuai"})


def _imports_provider_sdk(tree: ast.AST) -> str | None:
    """Name of the first provider SDK imported at statement level, if any."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in _PROVIDER_SDKS:
                    return alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in _PROVIDER_SDKS:
                return node.module
    return None


def _mark_xfail_calls_without_reason(tree: ast.AST) -> int:
    """Count ``pytest.mark.xfail`` marker usages lacking ``reason=``.

    Walks the AST (so docstrings/comments never match) and covers both
    decorator positions and module-level ``pytestmark`` assignments.
    """
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        parts: list[str] = []
        func: ast.AST = node.func
        while isinstance(func, ast.Attribute):
            parts.append(func.attr)
            func = func.value
        if isinstance(func, ast.Name):
            parts.append(func.id)
        # parts is innermost-first: ["xfail", "mark", "pytest"] for pytest.mark.xfail
        if parts[:2] != ["xfail", "mark"]:
            continue
        if any(kw.arg == "reason" for kw in node.keywords):
            continue
        count += 1
    # Bare ``@pytest.mark.xfail`` decorators (no call parentheses) carry no
    # reason by construction — count each of them too.
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Attribute) or dec.attr != "xfail":
                    continue
                inner = dec.value
                if isinstance(inner, ast.Attribute) and inner.attr == "mark":
                    count += 1
    return count


# ---------------------------------------------------------------------------
# Check results collector
# ---------------------------------------------------------------------------

class CheckResult:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []
        self.version_passes: dict[str, int] = {}
        self.version_fails: dict[str, int] = {}

    def ok(self, vid: str, label: str, detail: str = "") -> None:
        self.items.append({"id": vid, "label": label, "status": "pass", "detail": detail})
        self.version_passes[vid.split(".")[0]] = self.version_passes.get(vid.split(".")[0], 0) + 1

    def fail(self, vid: str, label: str, detail: str = "") -> None:
        self.items.append({"id": vid, "label": label, "status": "fail", "detail": detail})
        self.version_fails[vid.split(".")[0]] = self.version_fails.get(vid.split(".")[0], 0) + 1

    def skip(self, vid: str, label: str, detail: str = "") -> None:
        self.items.append({"id": vid, "label": label, "status": "skip", "detail": detail})

    def report(self, verbose: bool = False) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append("  Omni Suite — Production-Readiness Check")
        lines.append("=" * 60)

        current_version = ""
        for item in self.items:
            vid = item["id"]
            version = vid.split(".")[0]
            if version != current_version:
                vname = {"1": "V1 — Version", "2": "V2 — Module", "3": "V3 — FAKE_LLM",
                         "4": "V4 — Test Infra", "5": "V5 — CI/CD", "6": "V6 — Production",
                         "7": "V7 — Security", "8": "V8 — Observability",
                         "9": "V9 — Format Compat", "10": "V10 — Error Handling",
                         "11": "V11 — Documentation"}.get(version, f"V{version}")
                current_version = version

            icon = PASS if item["status"] == "pass" else FAIL if item["status"] == "fail" else SKIP
            line = f"  {icon} {vid} {item['label']}"
            if verbose and item["detail"]:
                line += f"\n       {item['detail']}"
            lines.append(line)

        lines.append("")
        lines.append("-" * 60)
        lines.append("  Summary")
        lines.append("-" * 60)

        all_versions = sorted(set(v.split(".")[0] for v in [i["id"] for i in self.items]))
        total_pass = 0
        total_fail = 0
        total_skip = 0

        for ver in all_versions:
            p = self.version_passes.get(ver, 0)
            f = self.version_fails.get(ver, 0)
            vname = {"1": "V1 Version", "2": "V2 Module", "3": "V3 FAKE_LLM",
                     "4": "V4 Test Infra", "5": "V5 CI/CD", "6": "V6 Production",
                     "7": "V7 Security", "8": "V8 Observability",
                     "9": "V9 Format Compat", "10": "V10 Error Handling",
                     "11": "V11 Documentation"}.get(ver, f"V{ver}")
            icon = PASS if f == 0 else FAIL
            lines.append(f"  {icon} {vname}: {p} pass, {f} fail")
            total_pass += p
            total_fail += f

        skips = sum(1 for i in self.items if i["status"] == "skip")
        total_skip = skips

        lines.append("")
        score, label = self._score()
        lines.append(f"  Score: {score} — {label}")
        lines.append(f"  Total: {total_pass} pass, {total_fail} fail, {total_skip} skip")

        if total_fail > 0:
            lines.append("")
            lines.append("  ❌ Blocking items (V1-V3):")
            for item in self.items:
                vid = item["id"]
                version = vid.split(".")[0]
                if item["status"] == "fail" and version in ("1", "2", "3"):
                    lines.append(f"    {FAIL} {vid} {item['label']}: {item['detail']}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def _score(self) -> tuple[str, str]:
        v1_fails = self.version_fails.get("1", 0)
        v2_fails = self.version_fails.get("2", 0)
        v3_fails = self.version_fails.get("3", 0)

        if v1_fails > 0 or v2_fails > 0 or v3_fails > 0:
            return "🔴", "Not Ready (V1-V3 blocking failures)"

        total_fail = sum(self.version_fails.values())
        if total_fail == 0:
            return "🏆", "Certified — All checks pass!"
        return "🟡", f"Needs Work ({total_fail} non-blocking failures)"


# ---------------------------------------------------------------------------
# V1 — Version Consistency
# ---------------------------------------------------------------------------

def check_v1(r: CheckResult) -> None:
    """Version consistency checks."""
    suite_version = _version_file_suite_version()
    compat_text = _read(COMPAT_FILE)

    # 1.1 Suite VERSION matches COMPATIBILITY.md — the LAST data row is the
    # newest pinned set (the matrix is append-only; row 5 is historical).
    row = _compat_last_data_row(compat_text)
    if row:
        compat_suite = row[0]
        if suite_version == compat_suite:
            r.ok("1.1", f"Suite VERSION ({suite_version}) matches COMPATIBILITY.md")
        else:
            r.fail("1.1", "Suite VERSION mismatch", f"VERSION says {suite_version}, COMPATIBILITY.md says {compat_suite}")
    else:
        r.fail("1.1", "Cannot parse COMPATIBILITY.md", "No version table found")

    # 1.2 Submodule versions match COMPATIBILITY.md (same last-row rule;
    # column layout per the line-3 header: Suite | OL | OPP | ORF | Notes).
    compat_cols = {}
    if row and len(row) >= 4:
        compat_cols = {"OPP": row[2], "OL": row[1], "ORF": row[3]}

    for name, mod_path in MODULES.items():
        pyproject = mod_path / "pyproject.toml"
        actual = _parse_pyproject_version(pyproject)
        expected = compat_cols.get(name, "")
        if actual is None:
            r.fail("1.2", f"{name} version unreadable", f"pyproject.toml not found or invalid: {pyproject}")
        elif expected and actual != expected:
            r.fail("1.2", f"{name} version mismatch", f"pyproject says {actual}, COMPATIBILITY.md says {expected}")
        else:
            r.ok("1.2", f"{name} version consistent ({actual})")

    # 1.3 Module __version__ attribute
    for name, mod_path in MODULES.items():
        pyproject = mod_path / "pyproject.toml"
        expected = _parse_pyproject_version(pyproject)
        if expected:
            src_dir = mod_path / "src"
            init_files = list(src_dir.rglob("__init__.py"))
            found_version = None
            for init_f in init_files:
                content = _read(init_f)
                m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
                if m:
                    found_version = m.group(1)
                    break
            if found_version and found_version != expected:
                r.fail("1.3", f"{name} __version__ mismatch", f"__init__.py says {found_version}, pyproject says {expected}")
            elif found_version:
                r.ok("1.3", f"{name} __version__ ({found_version}) matches pyproject")

    # 1.5 setup_dev.sh version assertion
    setup_text = _read(SETUP_SCRIPT)
    if "COMPATIBILITY.md" in setup_text or "version" in setup_text.lower():
        r.ok("1.5", "setup_dev.sh references version assertion")
    else:
        r.fail("1.5", "setup_dev.sh version assertion", "No reference to COMPATIBILITY.md or version checking found")


# ---------------------------------------------------------------------------
# V2 — Module Integrity
# ---------------------------------------------------------------------------

def check_v2(r: CheckResult) -> None:
    """Module integrity checks."""
    # Import probes get timeout=60: a cold `import opp` measures ~15.5s under
    # WSL (.venv_ol), which the 10s default turns into a permanent false red.
    probe_timeout = 60

    # 2.1 Module importability
    for name in MODULES:
        mod_name = {"OPP": "opp", "OL": "ol", "ORF": "orf"}[name]
        rc, out, err = _run([sys.executable, "-c", f"import {mod_name}; print('ok')"], timeout=probe_timeout)
        if rc == 0 and out.strip() == "ok":
            r.ok("2.1", f"{name} is importable")
        else:
            r.fail("2.1", f"{name} import failed", err[:200] if err else out[:200])

    # 2.2 CLI --help (each attempt imports the package, so same timeout)
    venv_bin = SUITE_ROOT / ".venv_ol" / "bin"
    for name in MODULES:
        cli = name.lower()
        rc, out, err = _run([cli, "--help"], timeout=probe_timeout)
        if rc == 0 and "usage" in out.lower():
            r.ok("2.2", f"{name} CLI --help works")
            continue
        # 1st fallback: python -m  (works for opp, orf)
        mod = {"OPP": "opp", "OL": "ol", "ORF": "orf"}[name]
        rc, out, err = _run([sys.executable, "-m", mod, "--help"], timeout=probe_timeout)
        if rc == 0 and "usage" in out.lower():
            r.ok("2.2", f"{name} CLI --help works (python -m)")
            continue
        # 2nd fallback: venv binary path (needed for OL which has no __main__.py)
        venv_cli = venv_bin / cli
        if venv_cli.exists():
            rc, out, err = _run([str(venv_cli), "--help"], timeout=probe_timeout)
            if rc == 0 and "usage" in out.lower():
                r.ok("2.2", f"{name} CLI --help works (venv)")
                continue
        r.fail("2.2", f"{name} CLI --help failed", err[:200] if err else out[:200])

    # 2.5 omni-suite status
    # Try python -m first (always works when venv is active, avoids PATH issues)
    rc, out, err = _run([sys.executable, "-m", "omni_suite", "status"])
    if rc == 0 and "OPP" in out and "OL" in out and "ORF" in out:
        r.ok("2.5", "omni-suite status shows all 3 modules")
    else:
        # Fallback: direct binary
        rc, out, err = _run(["omni-suite", "status"])
        if rc == 0 and "OPP" in out and "OL" in out and "ORF" in out:
            r.ok("2.5", "omni-suite status shows all 3 modules (binary)")
        else:
            r.fail("2.5", "omni-suite status failed", err[:200] if err else out[:200])

    # 2.7 Entry points exist
    root_pyproject = SUITE_ROOT / "pyproject.toml"
    try:
        with open(root_pyproject, "rb") as f:
            root_data = tomllib.load(f)
        scripts = root_data.get("project", {}).get("scripts", {})
        if "omni-suite" in scripts:
            r.ok("2.7", "omni-suite entry point defined")
        else:
            r.fail("2.7", "omni-suite entry point missing")
    except Exception:
        r.fail("2.7", "Cannot read root pyproject.toml")

    for name, mod_path in MODULES.items():
        pyproject = mod_path / "pyproject.toml"
        try:
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            scripts = data.get("project", {}).get("scripts", {})
            expected_entry = MCP_ENTRY_POINTS[name]
            has_mcp = any(expected_entry in k for k in scripts)
            has_cli = any(name.lower() == k or k.startswith(name.lower() + " ") for k in scripts)
            if has_mcp and has_cli:
                r.ok("2.7", f"{name} entry points present")
            else:
                missing = []
                if not has_cli:
                    missing.append("CLI")
                if not has_mcp:
                    missing.append("MCP")
                r.fail("2.7", f"{name} missing entry points", f"Missing: {', '.join(missing)}")
        except Exception as e:
            r.fail("2.7", f"{name} pyproject.toml unreadable", str(e)[:100])


# ---------------------------------------------------------------------------
# V3 — FAKE_LLM Seam
# ---------------------------------------------------------------------------

def check_v3(r: CheckResult) -> None:
    """FAKE_LLM seam integrity."""
    # 3.1 FAKE_LLM environment variable handling — the seam lives across the
    # OL source tree (cli/_shared.py, cli/cache.py, ...), not only ol_cli.py.
    ol_src = MODULES["OL"] / "src"
    ol_py_files = sorted(ol_src.rglob("*.py")) if ol_src.exists() else []
    seam_hits = [f for f in ol_py_files if "OMNI_TEST_FAKE_LLM" in _read(f)]
    if seam_hits:
        r.ok("3.1", f"OL FAKE_LLM seam exists in source ({len(seam_hits)} files)")
    else:
        r.fail("3.1", "OL FAKE_LLM seam not found", f"Scanned {len(ol_py_files)} .py files under {ol_src}")

    # 3.3 FAKE_PANDOC seam
    orf_files = list(MODULES["ORF"].rglob("*.py"))
    fake_pandoc_found = False
    for f in orf_files:
        if "OMNI_TEST_FAKE_PANDOC" in _read(f):
            fake_pandoc_found = True
            break
    if fake_pandoc_found:
        r.ok("3.3", "ORF FAKE_PANDOC seam exists")
    else:
        r.fail("3.3", "ORF FAKE_PANDOC seam not found")

    # 3.4 No test bypasses FAKE_LLM seam unsafely.
    # Real bypass = a test that leans on the FAKE_LLM seam while importing a
    # provider SDK directly (openai/litellm/zhipuai) — the env var never
    # reaches those calls. Function names/comments mentioning "real_llm"
    # (e.g. the canonical-key contract tests) are NOT bypasses.
    test_files = list((SUITE_ROOT / "tests").rglob("test_*.py"))
    bypass_found = False
    for f in test_files:
        content = _read(f)
        if "OMNI_TEST_FAKE_LLM" not in content:
            continue
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue
        sdk = _imports_provider_sdk(tree)
        if sdk:
            bypass_found = True
            r.fail("3.4", "Possible FAKE_LLM bypass", f"{f.name}: sets OMNI_TEST_FAKE_LLM while importing provider SDK '{sdk}' directly")
    if not bypass_found:
        r.ok("3.4", "No unsafe FAKE_LLM bypasses detected")

    # 3.6 Nightly tests skip gracefully without API keys
    nightly_file = SUITE_ROOT / "tests" / "test_e2e_real_llm.py"
    if nightly_file.exists():
        content = _read(nightly_file)
        has_skipif = "@pytest.mark.skipif" in content or "pytest.skip" in content
        if has_skipif:
            r.ok("3.6", "Nightly tests have skip guards")
        else:
            r.fail("3.6", "Nightly tests missing skip guards")


# ---------------------------------------------------------------------------
# V4 — Test Infrastructure
# ---------------------------------------------------------------------------

def check_v4(r: CheckResult) -> None:
    """Test infrastructure checks."""
    conftest = SUITE_ROOT / "tests" / "conftest.py"

    # 4.1 Markers registered
    content = _read(conftest)
    marker_count = content.count("addinivalue_line")
    if marker_count >= 8:
        r.ok("4.1", f"{marker_count} pytest markers registered in conftest.py")
    else:
        r.fail("4.1", f"Only {marker_count} markers registered", "Expected at least 8")

    # 4.2 Contract smoke test exists
    if SMOKE_TEST.exists():
        r.ok("4.2", "test_pipeline_contract_smoke.py exists")
    else:
        r.fail("4.2", "test_pipeline_contract_smoke.py MISSING", "Referenced in Makefile & pre-commit but not created")

    # 4.3 Each module has tests/
    for name, mod_path in MODULES.items():
        test_dir = mod_path / "tests"
        py_files = list(test_dir.rglob("test_*.py")) if test_dir.exists() else []
        if py_files:
            r.ok("4.3", f"{name} has {len(py_files)} test files")
        else:
            r.fail("4.3", f"{name} missing test files", f"{test_dir} has no test_*.py files")

    # 4.5 xfail without reason — AST-based: docstrings/comments containing the
    # literal text (test_phase7_root_test_isolation.py) must not match, and
    # multi-line decorator calls must still resolve their reason= keyword.
    skip_without_reason = 0
    for f in list((SUITE_ROOT / "tests").rglob("*.py")):
        try:
            tree = ast.parse(_read(f))
        except SyntaxError:
            continue
        skip_without_reason += _mark_xfail_calls_without_reason(tree)
    if skip_without_reason == 0:
        r.ok("4.5", "No xfail markers without reason")
    else:
        r.fail("4.5", f"{skip_without_reason} xfail markers missing reason=")

    # 4.8 Fixture documents present
    fixture_paths = [
        SUITE_ROOT / "scenarios" / "_fixtures" / "meridian_robotics.docx",
        SUITE_ROOT / "scenarios" / "_fixtures" / "meridian_q1.pptx",
    ]
    for fp in fixture_paths:
        if fp.exists() and fp.stat().st_size > 0:
            r.ok("4.8", f"Fixture present: {fp.name} ({fp.stat().st_size / 1024:.0f} KB)")


# ---------------------------------------------------------------------------
# V5 — CI/CD
# ---------------------------------------------------------------------------

def check_v5(r: CheckResult) -> None:
    """CI/CD checks."""
    # 5.1 Workflow YAML exists
    if CI_WORKFLOW.exists():
        r.ok("5.1", "GitHub Actions workflow exists")
    else:
        r.fail("5.1", "GitHub Actions workflow missing")

    # 5.2 Pre-commit config exists
    if PRE_COMMIT_CONFIG.exists():
        content = _read(PRE_COMMIT_CONFIG)
        hook_count = content.count("- repo:")
        if hook_count >= 3:
            r.ok("5.2", f"Pre-commit config with {hook_count} repos")
        else:
            r.fail("5.2", f"Only {hook_count} hook repos in pre-commit config", "Expected at least 3")
    else:
        r.fail("5.2", "Pre-commit config missing")

    # 5.3 Gitleaks configured
    if PRE_COMMIT_CONFIG.exists():
        content = _read(PRE_COMMIT_CONFIG)
        if "gitleaks" in content:
            r.ok("5.3", "Gitleaks hook configured")
        else:
            r.fail("5.3", "Gitleaks hook not found")

    # 5.4 Makefile targets
    if MAKEFILE.exists():
        content = _read(MAKEFILE)
        for target in ["test:", "smoke:", "lint:", "clean:"]:
            if target not in content:
                r.fail("5.4", f"Makefile missing target: {target}", "Expected test:, smoke:, lint:, clean:")
                break
        else:
            r.ok("5.4", "Makefile has all required targets (test, smoke, lint, clean)")
    else:
        r.fail("5.4", "Makefile missing")

    # 5.5 CI workflow has timeout
    ci_content = ""
    if CI_WORKFLOW.exists():
        ci_content = _read(CI_WORKFLOW)
        if "timeout-minutes" in ci_content:
            r.ok("5.5", "CI workflow has timeout configured")
        else:
            r.fail("5.5", "CI workflow missing timeout-minutes")

    # 5.6 Nightly depends on CI
    if CI_WORKFLOW.exists() and "needs:" in ci_content:
        r.ok("5.6", "Nightly job depends on CI passing")
    else:
        r.fail("5.6", "Nightly job does not require CI to pass")


# ---------------------------------------------------------------------------
# V6 — Production Tests
# ---------------------------------------------------------------------------

def check_v6(r: CheckResult) -> None:
    """Production test checks."""
    prod_tests = {
        "E1 (50MB)": PROD_TEST_DIR / "test_e1_50mb.py",
        "E2 (load)": PROD_TEST_DIR / "test_e2_load.py",
        "E3 (throughput)": PROD_TEST_DIR / "test_e3_throughput.py",
    }

    for label, path in prod_tests.items():
        if path.exists():
            content = _read(path)
            has_skip_env = "SKIP_ENV" in content
            r.ok("6.7" if has_skip_env else "6.x", f"{label} exists{' with SKIP_ENV' if has_skip_env else ''}")
        else:
            r.fail("6.x", f"{label} test missing", f"{path} not found")

    # E1 fixture check
    e1_fixture_env = os.environ.get("OMNI_E1_FIXTURE_PATH", "")
    e1_default = Path("/tmp/omni_e1_fixture.docx")
    if e1_fixture_env and Path(e1_fixture_env).exists():
        r.ok("6.2", "E1 fixture found (from environment)")
    elif e1_default.exists():
        r.ok("6.2", f"E1 default fixture found ({e1_default.stat().st_size / 1024 / 1024:.0f} MB)")
    else:
        # Environment item, not a product defect: the 50MB fixture is
        # generated locally on demand (OMNI_E1_FIXTURE_PATH / /tmp), so its
        # absence is a SKIP[missing-fixture], never a blocking red.
        r.skip("6.2", "E1 fixture not found", "[missing-fixture] Run tests/production/generate_50mb_fixture.py first")

    # E2 memory check config
    e2_content = _read(PROD_TEST_DIR / "test_e2_load.py") if (PROD_TEST_DIR / "test_e2_load.py").exists() else ""
    if "heap_growth_mb < 500" in e2_content:
        r.ok("6.4", "E2 memory growth threshold configured (500 MB)")


# ---------------------------------------------------------------------------
# V7 — Security
# ---------------------------------------------------------------------------

def check_v7(r: CheckResult) -> None:
    """Security checks."""
    # 7.1 Hardcoded keys test exists
    key_test = SECURITY_DIR / "test_no_hardcoded_keys.py"
    if key_test.exists():
        r.ok("7.1", "Hardcoded keys test exists")
    else:
        r.fail("7.1", "Hardcoded keys test missing")

    # 7.2 Path traversal tests exist
    traversal_tests = list(SECURITY_DIR.glob("*traversal*"))
    if traversal_tests:
        r.ok("7.2", f"Path traversal tests exist ({len(traversal_tests)} files)")
    else:
        r.fail("7.2", "Path traversal tests missing")

    # 7.5 OPP_ALLOWED_DIRECTORIES configured
    opp_mcp_files = list(MODULES["OPP"].rglob("*.py"))
    allowed_dirs_found = any("OPP_ALLOWED_DIRECTORIES" in _read(f) for f in opp_mcp_files)
    if allowed_dirs_found:
        r.ok("7.5", "OPP_ALLOWED_DIRECTORIES configured")
    else:
        r.fail("7.5", "OPP MCP path restriction not found", "OPP_ALLOWED_DIRECTORIES env var not referenced")


# ---------------------------------------------------------------------------
# V8 — Observability
# ---------------------------------------------------------------------------

def check_v8(r: CheckResult) -> None:
    """Observability checks."""
    if OBSERVABILITY_DIR.exists():
        obs_files = list(OBSERVABILITY_DIR.glob("*.py"))
        file_count = len(obs_files)
        r.ok("8.x", f"Observability tests: {file_count} test files")
        for f in obs_files:
            name = f.stem.replace("test_", "")
            r.ok("8.x", f"  Obs test: {name}")
    else:
        r.fail("8.x", "Observability test directory missing")

    # 8.3 MCP ping exists (check through import)
    try:
        import omni_metrics  # noqa
        r.ok("8.4", "omni_metrics module exists")
    except ImportError:
        r.skip("8.4", "omni_metrics not importable", "Metrics may not be installed")


# ---------------------------------------------------------------------------
# V9 — Cross-Format
# ---------------------------------------------------------------------------

def check_v9(r: CheckResult) -> None:
    """Cross-format compatibility checks."""
    # Check for format coverage in phase1_runner
    runner = SUITE_ROOT / "scripts" / "phase1_runner.py"
    if runner.exists():
        content = _read(runner)
        format_count = content.count(".format") + content.count("_format")
        r.ok("9.x", f"Phase 1 runner references formats ({format_count}x)")


# ---------------------------------------------------------------------------
# V10 — Error Handling
# ---------------------------------------------------------------------------

def check_v10(r: CheckResult) -> None:
    """Error handling checks."""
    # 10.1 Missing input file
    rc, out, err = _run([sys.executable, "-m", "opp", "/nonexistent/file.docx", "--target-format", "md"])
    if rc != 0:
        r.ok("10.1", "OPP handles missing input (non-zero exit)")
    else:
        r.fail("10.1", "OPP returned 0 for missing input")

    # 10.6 Check for subprocess return code propagation
    suite_cli = SUITE_ROOT / "omni_suite" / "cli.py"
    cli_content = _read(suite_cli)
    if "check=True" in cli_content:
        r.ok("10.6", "Subprocess failures propagate via check=True")
    else:
        r.fail("10.6", "Subprocess failures may not propagate")

    # 10.5 Bare except blocks — scan only source directories, skip venvs/caches
    bare_excepts = 0
    source_dirs = ["omni_suite", "omn_metrics", "Omni_Pre_Processor/src", "Omni_Localizer/src", "Omni_Re_Formatter/src", "scripts", "tests"]
    for src_dir in source_dirs:
        full_path = SUITE_ROOT / src_dir
        if full_path.exists():
            for py_file in full_path.rglob("*.py"):
                content = _read(py_file)
                for _m in re.finditer(r"^\s*except\s*:", content, re.MULTILINE):
                    bare_excepts += 1
    if bare_excepts == 0:
        r.ok("10.5", "No bare except: blocks found")
    else:
        r.fail("10.5", f"{bare_excepts} bare except: blocks found", "Should have logging or be specific")


# ---------------------------------------------------------------------------
# V11 — Documentation
# ---------------------------------------------------------------------------

def check_v11(r: CheckResult) -> None:
    """Documentation checks."""
    readme = SUITE_ROOT / "README.md"
    if readme.exists() and readme.stat().st_size > 100:
        r.ok("11.1", f"README.md exists ({readme.stat().st_size / 1024:.0f} KB)")
    else:
        r.fail("11.1", "README.md missing or too small")

    for name, mod_path in MODULES.items():
        for doc_name in ["README.md", "AGENTS.md", "SKILL.md"]:
            doc = mod_path / doc_name
            if doc.exists():
                r.ok("11.x", f"{name} {doc_name} exists")
                break
        else:
            r.skip("11.x", f"{name} no AGENTS.md/SKILL.md", "Not required but recommended")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_checks(verbose: bool = False) -> CheckResult:
    r = CheckResult()

    for name, fn in [
        ("V1 Version", check_v1),
        ("V2 Module Integrity", check_v2),
        ("V3 FAKE_LLM", check_v3),
        ("V4 Test Infra", check_v4),
        ("V5 CI/CD", check_v5),
        ("V6 Production", check_v6),
        ("V7 Security", check_v7),
        ("V8 Observability", check_v8),
        ("V9 Format Compat", check_v9),
        ("V10 Error Handling", check_v10),
        ("V11 Documentation", check_v11),
    ]:
        if verbose:
            print(f"  Running {name}...", flush=True)
        fn(r)

    return r


def main() -> int:
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    as_json = "--json" in sys.argv

    r = run_checks(verbose)

    if as_json:
        output = {
            "items": r.items,
            "pass_count": sum(1 for i in r.items if i["status"] == "pass"),
            "fail_count": sum(1 for i in r.items if i["status"] == "fail"),
            "skip_count": sum(1 for i in r.items if i["status"] == "skip"),
            "score": r._score()[0],
            "score_label": r._score()[1],
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(r.report(verbose=verbose))

    fail_count = sum(1 for i in r.items if i["status"] == "fail")
    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
