"""cli.py — the validation engine's CLI entrypoint (plan todo 9).

A thin consumer over the engine: argparse flags mapped onto
:func:`omni_mcp.validation.engine.run_scenarios`, plus the contract lint
(``--check``) which runs WITHOUT executing anything.  The console script
``validation`` (root ``pyproject.toml`` [project.scripts]) and the wrapper
``scripts/validation/run_validation.py`` both land here; ``main`` is a
pure function (argv -> exit code) so tests drive it in-process.

Flags (mirror AutoInfo ``run-validation-scenarios.py`` semantics):

- ``--list`` — enumerate scenarios (name, tier, requires_env, step
  count); no execution; exit 0 even for an empty library (guide §7.1
  "lists zero scenarios cleanly").
- ``--scenario <substr>`` — case-insensitive substring match on the
  scenario FILENAME stem (AutoInfo semantics); the matched scenarios run
  by their exact ``name`` via the engine filter.
- ``--tier <1|2|3>`` — run only scenarios whose ``tier`` field matches
  (AutoInfo tier model: 1 = no keys hermetic, 2 = LLM key, 3 =
  paid/external/network; loader default 1).
- ``--dry-run`` — load + validate + print the plan (name, tier,
  requires_env, step count); dispatch nothing; exit 0 (even when a real
  run would fail — it is a dry run).
- ``--verbose`` — per-step detail lines in the verdict table.
- ``--check`` — contract lint without executing: every step falsifiable
  (non-empty ``expect``), no self-echo PASS/FAIL in commands, and every
  ``standard:`` citation resolves to a real ``### Name {#anchor}``
  heading in ``scenarios/STANDARDS.md``.  Exit 1 on any finding.

Exit codes: 0 = no failures (``unconfigured`` / ``partial-pass`` /
``recovered`` / ``passed`` are NOT failures), 1 = any ``failed``
scenario, lint finding, or load error.

Default stdout is the summary + verdict table only; the per-step detail
and full trace live in the persisted run record (``validation-runs/``).

Only Python 3.13 stdlib + PyYAML — no new dependencies (guide §3.6).
"""

from __future__ import annotations

import argparse
import dataclasses
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from omni_mcp.validation.engine import run_scenarios
from omni_mcp.validation.loader import ScenarioError, load_scenarios

#: AutoInfo tier semantics (run-validation-scenarios.py:569-571): 1 = no
#: keys hermetic, 2 = LLM key, 3 = paid/external/network.
TIER_HELP = "run only scenarios at this tier (1=no keys hermetic, 2=LLM key, 3=paid/external/network)"

#: The self-echo anti-pattern (AutoInfo contract lint :515): a command
#: must not print PASS/FAIL itself — the assertion belongs in ``expect``.
#: Bare, double-quoted, and single-quoted forms, ``print(...)`` forms,
#: and the ✅/❌ emoji shortcuts are all rejected; word boundaries keep
#: ``echo passed`` / ``print("failed")`` out of the false-positive zone.
_SELF_ECHO_RE = re.compile(
    r"\becho\s+[\"']?(?:PASS|FAIL)[\"']?\b"
    r"|print\(\s*f?[\"']?(?:PASS|FAIL)[\"']?\b"
    r"|[\u2705\u274c]",
    re.IGNORECASE,
)

#: Citation shape the lint resolves: ``STANDARDS.md#<anchor>`` (D12).
_STANDARD_RE = re.compile(r"^STANDARDS\.md#([a-zA-Z0-9_-]+)$")


@dataclasses.dataclass
class LintFinding:
    """One contract-lint finding: where (file + step) and which rule."""

    #: Scenario file path.
    file: str
    #: 1-based primary step index (0 for scenario-level / cleanup steps).
    step: int
    #: ``yaml`` | ``falsifiable`` | ``self-echo`` | ``standard-anchor``.
    rule: str
    #: Human-readable detail naming the violation.
    detail: str


# ---------------------------------------------------------------------------
# Contract lint (--check): static, nothing executes
# ---------------------------------------------------------------------------


def parse_standard_anchors(standards_path: str | Path) -> set[str]:
    """Extract the anchor ids from ``### Name {#anchor-id}`` headings.

    Returns an empty set when the file is missing — every citation then
    fails resolution as an unknown anchor (the lint names the anchor, so
    the author sees exactly what is unresolvable).
    """
    path = Path(standards_path)
    if not path.is_file():
        return set()
    anchors: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^###\s+.*\{#([a-zA-Z0-9_-]+)\}\s*$", line)
        if m:
            anchors.add(m.group(1))
    return anchors


def _discover_files(scenarios_dir: str | Path) -> list[Path]:
    """Recursive ``*.yaml`` glob, dot-dirs skipped, sorted — the loader's
    discovery rules (loader.py), mirrored so the lint and the
    filename-substring filter see the same file set."""
    sd = Path(scenarios_dir)
    if not sd.is_dir():
        return []
    return sorted(
        p for p in sd.rglob("*.yaml") if not any(part.startswith(".") for part in p.parts)
    )


def _lint_step(
    step: Any,
    yaml_path: Path,
    index: int,
    anchors: set[str],
    findings: list[LintFinding],
    scope: str,
) -> None:
    """Apply the three contract rules to one step dict (raw YAML shape)."""
    if not isinstance(step, dict):
        return  # schema violation — the loader's job at run time
    expect = step.get("expect")
    if not isinstance(expect, dict) or not expect:
        findings.append(
            LintFinding(
                str(yaml_path), index, "falsifiable",
                f"{scope}missing non-empty 'expect' (every step must be falsifiable)",
            )
        )
    command = step.get("command") if isinstance(step.get("command"), str) else ""
    if _SELF_ECHO_RE.search(command):
        findings.append(
            LintFinding(
                str(yaml_path), index, "self-echo",
                f"{scope}command self-echoes PASS/FAIL (assert in 'expect', not "
                f"the command): {command!r}",
            )
        )
    standard = step.get("standard")
    if isinstance(standard, str) and standard:
        m = _STANDARD_RE.match(standard)
        if m is None:
            findings.append(
                LintFinding(
                    str(yaml_path), index, "standard-anchor",
                    f"{scope}malformed citation {standard!r} — expected "
                    "STANDARDS.md#<anchor>",
                )
            )
        elif m.group(1) not in anchors:
            findings.append(
                LintFinding(
                    str(yaml_path), index, "standard-anchor",
                    f"{scope}unknown anchor {standard!r} — no {{#...}} heading "
                    "in STANDARDS.md",
                )
            )


def lint_scenarios(
    scenarios_dir: str | Path,
    standards_path: str | Path | None = None,
) -> list[LintFinding]:
    """Contract-lint every scenario WITHOUT executing (``--check``).

    Three rules (plan todo 9, mirroring AutoInfo contract lint
    ``run-validation-scenarios.py:506-537`` plus the D12 citation rule):

    1. **falsifiable** — every step carries a non-empty ``expect`` block
       (the loader already enforces this at load time; the lint
       re-confirms it against the raw YAML so ``--check`` works without a
       run).
    2. **self-echo** — no command prints PASS/FAIL itself (``echo PASS``,
       ``echo "FAIL"``, ``print("PASS")``, ✅/❌ — the assertion belongs
       in ``expect``).
    3. **standard-anchor** — every ``standard:`` citation is
       ``STANDARDS.md#<anchor>`` and the anchor resolves to a real
       ``### Name {#anchor-id}`` heading in ``STANDARDS.md`` (D12).

    Recovery steps are linted under their primary's step index; cleanup
    steps under index 0.  Findings carry file + step + rule + detail.
    """
    sd = Path(scenarios_dir)
    std_path = Path(standards_path) if standards_path is not None else sd / "STANDARDS.md"
    anchors = parse_standard_anchors(std_path)
    findings: list[LintFinding] = []
    for yaml_path in _discover_files(sd):
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            findings.append(
                LintFinding(str(yaml_path), 0, "yaml", f"failed to parse YAML: {exc}")
            )
            continue
        if not isinstance(data, dict):
            findings.append(
                LintFinding(str(yaml_path), 0, "yaml", "scenario must be a YAML mapping")
            )
            continue
        steps = data.get("steps")
        if not isinstance(steps, list):
            continue  # schema violation — the loader's job at run time
        for i, step in enumerate(steps, 1):
            _lint_step(step, yaml_path, i, anchors, findings, "")
        for i, step in enumerate(steps, 1):
            for j, rstep in enumerate(step.get("recovery_steps") or [], 1):
                _lint_step(rstep, yaml_path, i, anchors, findings, f"recovery step {j} of ")
        for j, cstep in enumerate(data.get("cleanup_steps") or [], 1):
            _lint_step(cstep, yaml_path, 0, anchors, findings, f"cleanup step {j} ")
    return findings


# ---------------------------------------------------------------------------
# Selection: filename-substring + tier pre-filters (CLI side)
# ---------------------------------------------------------------------------


def _name_of(path: Path) -> str:
    """The scenario's ``name`` field (fallback: filename stem, mirroring
    AutoInfo ``data.get("name", fpath.stem)``)."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if (
            isinstance(data, dict)
            and isinstance(data.get("name"), str)
            and data["name"].strip()
        ):
            return data["name"]
    except yaml.YAMLError:
        pass  # load_scenarios surfaces the parse error loudly
    return path.stem


def _select_names(
    loaded: list[dict[str, Any]],
    scenarios_dir: str | Path,
    scenario_substr: str | None,
    tier: int | None,
    category: str | None = None,
    module: str | None = None,
) -> tuple[list[str], list[str]]:
    """The scenario names that survive all CLI-side filters.

    Returns ``(names, empty_filters)`` so the caller can warn which filter
    emptied the selection.  ``--scenario`` is a case-insensitive substring
    on the FILENAME stem (AutoInfo semantics); ``--tier`` pre-filters by
    the ``tier`` field; ``--category`` matches the scenario ``category:``
    field exactly; ``--module`` is the per-module convenience selector
    (``opp``/``ol``/``orf``/``suite``) that expands to the module's
    scenario categories plus its ``tool-<module>-*`` agent-surface
    scenarios.  Selection order follows load order (the engine keeps it).
    """
    tier_names: set[str] | None = None
    stem_names: set[str] | None = None
    category_names: set[str] | None = None
    module_names: set[str] | None = None
    empty_filters: list[str] = []
    if tier is not None:
        tier_names = {s["name"] for s in loaded if s.get("tier") == tier}
        if not tier_names:
            empty_filters.append(f"tier {tier}")
    if scenario_substr is not None:
        stem_names = {
            _name_of(p)
            for p in _discover_files(scenarios_dir)
            if scenario_substr.lower() in p.stem.lower()
        }
        if not stem_names:
            empty_filters.append(f"--scenario {scenario_substr!r}")
    if category is not None:
        category_names = {s["name"] for s in loaded if s.get("category") == category}
        if not category_names:
            empty_filters.append(f"--category {category!r}")
    if module is not None:
        module_names = _module_scenario_names(loaded, module)
        if not module_names:
            empty_filters.append(f"--module {module!r}")
    names = [
        s["name"]
        for s in loaded
        if (tier_names is None or s["name"] in tier_names)
        and (stem_names is None or s["name"] in stem_names)
        and (category_names is None or s["name"] in category_names)
        and (module_names is None or s["name"] in module_names)
    ]
    return names, empty_filters


_MODULE_CATEGORIES: dict[str, set[str]] = {
    "opp": {"opp-extraction"},
    "orf": {"orf-md", "orf-xliff"},
    "ol": set(),
    "suite": {"pipeline", "regression"},
}

#: The suite's own agent-surface tool prefix (its 4 MCP tools).
_SUITE_TOOL_PREFIX = "tool-omni_mcp-"


def _module_scenario_names(loaded: list[dict[str, Any]], module: str) -> set[str]:
    """The scenario names belonging to a module: its own categories plus
    the ``tool-<module>-*`` agent-surface scenarios (the suite module's
    tools are the ``tool-omni_mcp-*`` prefix)."""
    cats = _MODULE_CATEGORIES.get(module)
    if cats is None:
        return set()
    names = {s["name"] for s in loaded if s.get("category") in cats}
    prefix = _SUITE_TOOL_PREFIX if module == "suite" else f"tool-{module}-"
    names |= {s["name"] for s in loaded if s["name"].startswith(prefix)}
    return names


# ---------------------------------------------------------------------------
# Output: summary + verdict table (details live in the run record)
# ---------------------------------------------------------------------------


def _print_verdict_table(results: list[Any], verbose: bool) -> None:
    print(f"{'SCENARIO':<34} {'STATUS':<13} SUMMARY")
    for r in results:
        print(f"{r.name:<34} {r.status:<13} {r.summary}")
        if verbose:
            for s in r.steps:
                mark = "recovered" if s["status"] == "recovered" else (
                    "passed" if s["passed"] else "FAIL"
                )
                print(
                    f"    step {s['step_index']}: {mark:<9} "
                    f"{s.get('name') or ''}  {s.get('surface') or ''}"
                )
    totals = Counter(r.status for r in results)
    order = ("passed", "failed", "unconfigured", "partial-pass", "recovered")
    print("Totals: " + ", ".join(f"{totals.get(s, 0)} {s}" for s in order))


def _print_plan(loaded: list[dict[str, Any]], names: list[str]) -> None:
    """Dry-run plan: name, tier, requires_env, step count (load order)."""
    wanted = set(names)
    for s in loaded:
        if s["name"] not in wanted:
            continue
        env = ", ".join(s["requires_env"]) or "-"
        print(
            f"  {s['name']:<30s}  tier={s['tier']}  steps={len(s['steps'])}  "
            f"requires_env=[{env}]"
        )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """The validation CLI.  Returns the exit code (0 = no failures)."""
    parser = argparse.ArgumentParser(
        prog="validation",
        description=(
            "Run the Omni Suite validation scenarios (load -> dispatch -> "
            "grade -> aggregate -> persist) or lint them without executing."
        ),
    )
    parser.add_argument(
        "--list", action="store_true", help="enumerate scenarios (name, tier, requires_env, steps); no execution"
    )
    parser.add_argument(
        "--scenario",
        metavar="SUBSTR",
        default=None,
        help="run only scenarios whose FILENAME contains SUBSTR (case-insensitive)",
    )
    parser.add_argument(
        "--category",
        metavar="CATEGORY",
        default=None,
        help="run only scenarios whose ``category:`` field equals CATEGORY "
        "(e.g. opp-extraction, orf-md, orf-xliff, agent-surface, pipeline, regression)",
    )
    parser.add_argument(
        "--module",
        metavar="MODULE",
        default=None,
        help="per-module validation: run only that module's scenarios "
        "(its categories plus its tool-<module>-* agent-surface scenarios); "
        "known modules: opp, ol, orf, suite",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="load + validate + print the plan; dispatch nothing"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="per-step detail in the summary"
    )
    parser.add_argument(
        "--check", action="store_true", help="contract lint (falsifiable, no self-echo PASS/FAIL, standard anchors) without executing"
    )
    parser.add_argument("--tier", type=int, choices=[1, 2, 3], default=None, help=TIER_HELP)
    parser.add_argument(
        "--scenarios-dir", default="scenarios", help="scenario library directory (default: scenarios)"
    )
    parser.add_argument(
        "--runs-dir", default="validation-runs", help="run records directory (default: validation-runs)"
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # --help (0) / usage error (2): keep main() pure
        return exc.code if isinstance(exc.code, int) else 0

    if args.check:
        findings = lint_scenarios(args.scenarios_dir)
        if findings:
            print(f"Contract check: {len(findings)} finding(s)")
            for f in findings:
                print(f"  [x] {f.file}: step {f.step} [{f.rule}] {f.detail}")
            return 1
        print(
            "Contract check: clean — every step falsifiable, no self-echo "
            "PASS/FAIL, standard citations resolve to STANDARDS.md anchors"
        )
        return 0

    try:
        loaded = load_scenarios(args.scenarios_dir)
    except ScenarioError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.list:
        names, _empty = _select_names(
            loaded, args.scenarios_dir, args.scenario, args.tier, args.category, args.module
        )
        selected = [s for s in loaded if s["name"] in names] if names else loaded
        print(f"Available Scenarios ({len(selected)}):")
        for s in selected:
            env = ", ".join(s["requires_env"]) or "-"
            print(
                f"  {s['name']:<30s}  tier={s['tier']}  steps={len(s['steps'])}  "
                f"requires_env=[{env}]"
            )
        return 0

    names, empty_filters = _select_names(
        loaded, args.scenarios_dir, args.scenario, args.tier, args.category, args.module
    )
    for f in empty_filters:
        print(f"WARNING: no scenarios match {f}")
    if empty_filters:
        return 0

    if not names:
        print(f"no scenarios found in {args.scenarios_dir} (nothing to run)")
        return 0

    if args.dry_run:
        print(
            f"[DRY-RUN] no commands will be executed — {len(names)} scenario(s) "
            "selected (loaded + validated)"
        )
        _print_plan(loaded, names)
        return 0

    filters = (
        None
        if (args.scenario is None and args.tier is None and args.category is None and args.module is None)
        else names
    )
    try:
        run = run_scenarios(args.scenarios_dir, filters=filters, runs_dir=args.runs_dir)
    except ScenarioError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        f"Run {run.run_id} — trace {run.trace_id}  "
        f"(details: {run.run_dir})"
    )
    _print_verdict_table(run.scenarios, args.verbose)
    return 1 if any(r.status == "failed" for r in run.scenarios) else 0
