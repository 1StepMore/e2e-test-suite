#!/usr/bin/env python3
"""Coverage audit: which of the LIVE MCP tools are exercised by scenarios.

Run from the repo root (plan todo 17):

    source .venv_ol/bin/activate
    python scripts/validation/coverage_audit.py

Declared-vs-exercised coverage (guide §5.1, draft D13 — the
agent-satisfaction metric: every live tool must be scenario-used, else
``missing`` — an agent-user would hit it blind):

- ``declared``      = the LIVE module MCP tool registries, parsed by
                      IMPORTING them (same in-process pattern as
                      ``omni_mcp/validation/dispatch.py`` and the
                      AGENTS.md "Test via Python (in-process)" section),
                      never hardcoded, never the stale AGENTS.md tables:
                        opp      ``opp.mcp.server._TOOL_SCHEMAS``      (9)
                        ol       ``ol_mcp.tools.TOOL_REGISTRY``       (21)
                        orf      ``orf.mcp.server._TOOL_DISPATCH``     (7)
                        omni_mcp ``omni_mcp.server._TOOL_SCHEMAS``     (4)
                      = 41 tools — this script stays correct because it
                      always reads the live registries.
- ``scenario_used`` = tool names referenced by
                      ``scenarios/agent-surface/tool-<module>-<tool>.yaml``
                      filenames + every ``kind: mcp`` step's ``tool:``
                      anywhere under ``scenarios/**``.
- ``covered``       = declared ∩ scenario_used
- ``missing``       = declared − covered        (exit 1 while non-empty)
- ``phantom``       = scenario_used − declared  (contributes zero; the
                      deliberate error-boundary probe ``_call_tool`` is
                      allowlisted per guide §5.1's legitimate exception)

DRIFT section (draft D11): the frozen contract fixtures
``tests/contract/fixtures/*_mcp_schemas.json`` (+ ``EXPECTED_COUNTS`` at
``tests/contract/test_mcp_schemas.py:49``) are reconciled to the live
module-level surface (opp 9 + ol 21 + orf 7 = 37); the suite
``omni_mcp`` tools (4) stay unpinned by design.  Drift never affects the
exit code; only ``missing`` does.

``--out PATH`` additionally writes a nested, diff-friendly snapshot
``{generated_at, suite_sha, declared, covered, missing, phantom,
totals}`` (todo 26 — ``validation_diff.py`` consumes it when BOTH runs
in a diff carry one).  Exit-code logic is UNCHANGED by ``--out``.

Only Python 3.13 stdlib + PyYAML (guide §3.6).  Deterministic: same
commit, same sets.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

#: Suite root: this module lives at <root>/scripts/validation/coverage_audit.py.
SUITE_ROOT = Path(__file__).resolve().parent.parent.parent

#: Component src dirs (sub-repos keep their packages under ``src/``) —
#: mirrors ``omni_mcp/validation/dispatch.py`` ``_COMPONENT_SRC_DIRS``.
_COMPONENT_SRC_DIRS = (
    SUITE_ROOT / "Omni_Pre_Processor" / "src",
    SUITE_ROOT / "Omni_Localizer" / "src",
    SUITE_ROOT / "Omni_Re_Formatter" / "src",
)

#: Contract fixtures pin MODULE-LEVEL tools only; the suite ``omni_mcp``
#: tools are not pinned there (covered by this audit instead, D13).
_FIXTURE_MODULES = ("opp", "ol", "orf")

#: Deliberate error-boundary probes (guide §5.1 legitimate exception):
#: ``orf.mcp.server._call_tool`` is the real MCP dispatch entry, called by
#: agent-surface scenarios with a typo'd tool name to prove the server
#: answers with a clean agent-readable error.  Allowlisted — never counted
#: as coverage, never reported as phantom.
ERROR_BOUNDARY_TOOLS = frozenset({"_call_tool"})


def _ensure_sys_paths() -> None:
    """Make the suite root and the three component ``src/`` dirs importable
    (idempotent).  The suite has no ``src/`` dir — ``omni_mcp`` lives at the
    repo root — and the sub-repos keep their packages under ``src/``."""
    for entry in (SUITE_ROOT, *_COMPONENT_SRC_DIRS):
        if entry.is_dir() and str(entry) not in sys.path:
            sys.path.insert(0, str(entry))


# ---------------------------------------------------------------------------
# Declared surface — the LIVE registries (never hardcoded)
# ---------------------------------------------------------------------------


def _import_module_tools(module_key: str) -> list[str]:
    """Import the module's real tool registry and return its tool names.

    Per-module registry shape (verified against the live sources):
    - opp / omni_mcp : ``_TOOL_SCHEMAS`` list of dicts carrying ``name``
    - orf            : ``_TOOL_DISPATCH`` dict  name -> callable
    - ol             : ``ol_mcp.tools.TOOL_REGISTRY`` dict name -> entry
    """
    if module_key == "opp":
        from opp.mcp.server import _TOOL_SCHEMAS as schemas
        return sorted(s["name"] for s in schemas)
    if module_key == "ol":
        from ol_mcp.tools import TOOL_REGISTRY as registry
        return sorted(registry)
    if module_key == "orf":
        # ORF's MCP config is fail-CLOSED at import (orf/mcp/config.py
        # raises without MCP_ALLOWED_DIRECTORIES / ORF_MCP_ALLOWED_DIRS —
        # same pattern as tests/validation/test_dispatch.py).  The audit
        # only reads the registry; the allowlist value itself is inert.
        os.environ.setdefault("MCP_ALLOWED_DIRECTORIES", "/tmp")
        from orf.mcp.server import _TOOL_DISPATCH as dispatch
        return sorted(dispatch)
    if module_key == "omni_mcp":
        from omni_mcp.server import _TOOL_SCHEMAS as schemas
        return sorted(s["name"] for s in schemas)
    raise ValueError(f"unknown module key: {module_key!r}")


def load_live_surface() -> dict[str, list[str]]:
    """The declared surface: tool names from the LIVE module registries,
    keyed by module (``opp``, ``ol``, ``orf``, ``omni_mcp``)."""
    _ensure_sys_paths()
    return {key: _import_module_tools(key) for key in ("opp", "ol", "orf", "omni_mcp")}


# ---------------------------------------------------------------------------
# Scenario-used surface — parsed from the committed YAML library
# ---------------------------------------------------------------------------


def load_scenario_used(scenarios_dir: Path) -> tuple[set[str], int]:
    """Tool names the scenarios actually step against.

    Two sources, per plan todo 17:
    1. ``tool-<module>-<tool>.yaml`` filenames (one scenario per agent
       surface tool — D13) → the bare tool name.
    2. Every ``kind: mcp`` step's ``tool:`` reference (e.g.
       ``opp.mcp.server.validate_xliff``) → the final dotted segment.

    Returns ``(scenario_used, scenario_file_count)``.
    """
    used: set[str] = set()
    file_count = 0
    for yf in sorted(scenarios_dir.rglob("*.yaml")):
        file_count += 1
        base = yf.name
        if base.startswith("tool-"):
            rest = base[len("tool-"):].removesuffix(".yaml")
            _module, _, tool = rest.partition("-")
            if tool:
                used.add(tool)
        try:
            data = yaml.safe_load(yf.read_text(encoding="utf-8"))
        except Exception:
            # A malformed scenario YAML must not sink the audit; the
            # contract lint (--check) is the loud gate for bad YAML.
            continue
        if not isinstance(data, dict):
            continue
        for step in data.get("steps") or []:
            if isinstance(step, dict) and step.get("kind") == "mcp":
                tool_ref = step.get("tool")
                if isinstance(tool_ref, str) and tool_ref:
                    used.add(tool_ref.rsplit(".", 1)[-1])
    return used, file_count


# ---------------------------------------------------------------------------
# DRIFT — frozen contract fixtures vs live surface (D11, finding only)
# ---------------------------------------------------------------------------


def parse_fixture_counts(fixtures_dir: Path) -> dict[str, int]:
    """Tool counts pinned by the frozen contract fixtures
    (``tests/contract/fixtures/{opp,ol,orf}_mcp_schemas.json``)."""
    counts: dict[str, int] = {}
    for module in _FIXTURE_MODULES:
        fixture = fixtures_dir / f"{module}_mcp_schemas.json"
        if not fixture.exists():
            continue
        data = json.loads(fixture.read_text(encoding="utf-8"))
        counts[module] = len(data) if isinstance(data, list) else 0
    return counts


def parse_expected_counts(module_path: Path) -> dict[str, int]:
    """``EXPECTED_COUNTS`` from ``tests/contract/test_mcp_schemas.py`` via
    a static AST parse (deterministic; no test-module import)."""
    if not module_path.exists():
        return {}
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "EXPECTED_COUNTS":
                    value = ast.literal_eval(node.value)
                    if isinstance(value, dict):
                        return {str(k): int(v) for k, v in value.items()}
    return {}


def compute_drift(fixture_counts: dict[str, int], surface: dict[str, list[str]]) -> dict[str, Any]:
    """Per-module frozen-vs-live deltas plus totals.

    The suite ``omni_mcp`` tools are not pinned in the contract fixtures
    (module-level only) — they are reported as unpinned, not compared.
    """
    drift: dict[str, Any] = {}
    for module in _FIXTURE_MODULES:
        frozen = fixture_counts.get(module, 0)
        live = len(surface.get(module, []))
        drift[module] = {"frozen": frozen, "live": live, "delta": live - frozen}
    totals = {
        "frozen": sum(drift[m]["frozen"] for m in _FIXTURE_MODULES),
        "live_module": sum(drift[m]["live"] for m in _FIXTURE_MODULES),
        "live_suite": len(surface.get("omni_mcp", [])),
    }
    totals["live_total"] = totals["live_module"] + totals["live_suite"]
    drift["totals"] = totals
    return drift


# ---------------------------------------------------------------------------
# The audit
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class CoverageReport:
    """Everything derived from the two surfaces (guide §5.1 sets)."""

    declared: dict[str, list[str]]
    scenario_used: set[str]
    covered: dict[str, list[str]]
    missing: dict[str, list[str]]
    phantom: list[str]
    error_boundary_probes: list[str]
    drift: dict[str, Any]
    scenario_count: int
    scenario_files: int


def compute_coverage(
    root: Path,
    *,
    scenarios_dir: Path | None = None,
    fixtures_dir: Path | None = None,
    expected_counts_file: Path | None = None,
) -> CoverageReport:
    """Declared vs exercised over the committed sources under *root*.

    Parameters may be overridden for tests/synthetic inputs; defaults
    resolve against the real repo layout.
    """
    scenarios_dir = scenarios_dir or root / "scenarios"
    fixtures_dir = fixtures_dir or root / "tests" / "contract" / "fixtures"
    expected_counts_file = expected_counts_file or root / "tests" / "contract" / "test_mcp_schemas.py"

    declared = load_live_surface()
    declared_all = {tool for tools in declared.values() for tool in tools}

    scenario_used, scenario_files = load_scenario_used(scenarios_dir)
    error_boundary = sorted(scenario_used & ERROR_BOUNDARY_TOOLS)
    scenario_used = scenario_used - ERROR_BOUNDARY_TOOLS

    covered = {m: sorted(set(tools) & scenario_used) for m, tools in declared.items()}
    missing = {m: sorted(set(tools) - scenario_used) for m, tools in declared.items()}
    phantom = sorted(scenario_used - declared_all)

    fixture_counts = parse_fixture_counts(fixtures_dir)
    expected_counts = parse_expected_counts(expected_counts_file)
    drift = compute_drift(fixture_counts, declared)
    drift["expected_counts_file"] = (
        str(expected_counts_file.relative_to(root)) if expected_counts_file.is_relative_to(root)
        else str(expected_counts_file)
    )
    drift["expected_counts"] = expected_counts

    return CoverageReport(
        declared=declared,
        scenario_used=scenario_used,
        covered=covered,
        missing=missing,
        phantom=phantom,
        error_boundary_probes=error_boundary,
        drift=drift,
        scenario_count=len(scenario_used),
        scenario_files=scenario_files,
    )


def render(report: CoverageReport) -> str:
    """Human-readable table: covered / missing / phantom / DRIFT."""
    lines: list[str] = []
    declared_total = sum(len(t) for t in report.declared.values())
    covered_total = sum(len(t) for t in report.covered.values())
    missing_total = sum(len(t) for t in report.missing.values())
    lines.append("Coverage audit — declared vs exercised (guide §5.1, D13)")
    lines.append(
        f"  scenario files: {report.scenario_files}  |  distinct tool names referenced: "
        f"{report.scenario_count} (of {declared_total} declared module-tool slots — "
        f"ping/get_capabilities/translate_file are declared in multiple modules)"
    )
    lines.append("")
    lines.append(f"  {'module':<12} {'declared':>8} {'covered':>8} {'missing':>8}")
    lines.append(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*8}")
    for module in ("opp", "ol", "orf", "omni_mcp"):
        lines.append(
            f"  {module:<12} {len(report.declared[module]):>8} "
            f"{len(report.covered[module]):>8} {len(report.missing[module]):>8}"
        )
    lines.append(
        f"  {'TOTAL':<12} {declared_total:>8} {covered_total:>8} {missing_total:>8}"
    )
    lines.append("")
    if missing_total:
        lines.append(f"  MISSING ({missing_total}) — declared but never scenario-used (an agent-user would hit it blind):")
        for module in ("opp", "ol", "orf", "omni_mcp"):
            for tool in report.missing[module]:
                lines.append(f"    {module}: {tool}")
    else:
        lines.append("  MISSING: 0 — every declared tool is scenario-used.")
    lines.append("")
    lines.append(f"  PHANTOM ({len(report.phantom)}) — scenario names no live tool (contributes zero coverage):")
    for tool in report.phantom:
        lines.append(f"    {tool}")
    if report.error_boundary_probes:
        lines.append(
            f"  allowlisted error-boundary probes (guide §5.1): {', '.join(report.error_boundary_probes)}"
        )
    lines.append("")
    # DRIFT — frozen contract fixtures vs live surface (D11 finding, todo 21)
    d = report.drift
    lines.append("DRIFT — frozen contract fixtures vs LIVE module surface (D11, finding only)")
    lines.append(f"  EXPECTED_COUNTS read from {d['expected_counts_file']}: "
                 f"{d['expected_counts'] or '(unreadable)'}")
    lines.append(f"  {'module':<12} {'frozen':>8} {'live':>8} {'delta':>8}")
    lines.append(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*8}")
    for module in _FIXTURE_MODULES:
        row = d[module]
        lines.append(f"  {module:<12} {row['frozen']:>8} {row['live']:>8} {row['delta']:+8d}")
    t = d["totals"]
    lines.append(
        f"  {'TOTAL':<12} {t['frozen']:>8} {t['live_module']:>8} "
        f"{t['live_module'] - t['frozen']:+8d}"
    )
    lines.append(
        f"  suite omni_mcp tools unpinned in contract fixtures: {t['live_suite']} "
        f"({', '.join(report.declared['omni_mcp'])})."
    )
    lines.append("")
    verdict = (
        f"  VERDICT: {covered_total}/{declared_total} covered, "
        f"{missing_total} missing"
    )
    if missing_total:
        verdict += " -> FAIL (missing > 0), exit 1"
    else:
        verdict += " -> PASS, exit 0"
    lines.append(verdict)
    lines.append(
        f"  DRIFT finding: frozen fixtures pin {t['frozen']} module-level tools vs live "
        f"{t['live_module']} (+{t['live_suite']} suite tools unpinned) = {t['live_total']} "
        f"live tools total; suite tools are unpinned by design."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Snapshot (todo 26) — the nested, diff-friendly coverage.json
# ---------------------------------------------------------------------------


def _suite_git_sha(root: Path) -> str:
    """The suite git HEAD sha (``git rev-parse`` at the suite root);
    ``"unknown"`` when git is unavailable — never raises."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def build_snapshot(report: CoverageReport) -> dict[str, Any]:
    """The persisted coverage snapshot (``--out`` shape, diff-friendly):
    ``{generated_at, suite_sha, declared, covered, missing, phantom,
    totals}`` — per-module lists under the first four, ``phantom`` a flat
    list, ``totals`` the declared/covered/missing counts."""
    totals = {
        "declared": sum(len(t) for t in report.declared.values()),
        "covered": sum(len(t) for t in report.covered.values()),
        "missing": sum(len(t) for t in report.missing.values()),
    }
    return {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "suite_sha": _suite_git_sha(SUITE_ROOT),
        "declared": {k: list(v) for k, v in report.declared.items()},
        "covered": {k: list(v) for k, v in report.covered.items()},
        "missing": {k: list(v) for k, v in report.missing.items()},
        "phantom": list(report.phantom),
        "totals": totals,
    }


def write_snapshot(report: CoverageReport, out_path: str | Path) -> Path:
    """Write the coverage snapshot as pretty JSON to *out_path*, creating
    parent directories as needed.  Returns the written path."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(build_snapshot(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out


def main(argv: list[str] | None = None) -> int:
    """CLI entry: print the audit table; exit 1 while any ``missing``."""
    parser = argparse.ArgumentParser(
        prog="coverage_audit.py",
        description="Coverage audit: live MCP tool surface vs scenario usage (guide §5.1).",
    )
    parser.add_argument("--scenarios-dir", type=Path, default=None,
                        help="scenario library root (default: <repo>/scenarios)")
    parser.add_argument("--fixtures-dir", type=Path, default=None,
                        help="contract fixture dir (default: <repo>/tests/contract/fixtures)")
    parser.add_argument("--expected-counts-file", type=Path, default=None,
                        help="test_mcp_schemas.py to read EXPECTED_COUNTS from (default: repo path)")
    parser.add_argument("--out", type=Path, default=None,
                        help="write the coverage snapshot (todo 26 shape) to this path "
                        "after printing the table; exit-code logic unchanged")
    args = parser.parse_args(argv)

    report = compute_coverage(
        SUITE_ROOT,
        scenarios_dir=args.scenarios_dir,
        fixtures_dir=args.fixtures_dir,
        expected_counts_file=args.expected_counts_file,
    )
    print(render(report))
    if args.out is not None:
        snapshot = write_snapshot(report, args.out)
        print(f"SNAPSHOT: {snapshot}")
    missing_total = sum(len(m) for m in report.missing.values())
    return 1 if missing_total > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
