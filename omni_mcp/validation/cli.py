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
``recovered`` / ``passed`` are NOT failures), 1 = any ``failed`` or
``invalid`` scenario, lint finding, or load error.  ``invalid`` is R-07's
fake-LLM inadmissible-evidence verdict and is never a pass.

- ``--repo {opp,ol,orf,suite,all}`` — select scenario source directory(ies)
  by component.  ``all`` merges from all four dirs.

Default stdout is the summary + verdict table only; the per-step detail
and full trace live in the persisted run record (``validation-runs/``).

Only Python 3.13 stdlib + PyYAML — no new dependencies (guide §3.6).
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import re
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from omni_mcp.validation.engine import run_scenarios
from omni_mcp.validation.loader import LEVELS, ScenarioError, load_scenarios

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
    #: ``yaml`` | ``falsifiable`` | ``self-echo`` | ``standard-anchor`` |
    #: ``known-gap-location`` | ``level``.
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
    command = step.get("command")
    command = command if isinstance(command, str) else ""
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
    4. **known-gap-location** — a ``known_gap: true`` scenario must live
       under a ``known-gaps/`` directory, and every scenario under
       ``known-gaps/`` must declare ``known_gap: true`` (T-17: a weakened
       bar is never silently left in the pass-bar library).
    5. **level** — every scenario declares ``level`` ∈ ``LEVELS``
       (``agent-user`` | ``human-quality``); a missing or unknown level is
       a finding, never silently defaulted (T-19).

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
        in_known_gaps = "known-gaps" in yaml_path.parts
        is_known_gap = data.get("known_gap") is True
        if is_known_gap and not in_known_gaps:
            findings.append(
                LintFinding(
                    str(yaml_path), 0, "known-gap-location",
                    "known_gap: true scenario must live under a known-gaps/ "
                    "directory (never in the pass-bar library)",
                )
            )
        if in_known_gaps and not is_known_gap:
            findings.append(
                LintFinding(
                    str(yaml_path), 0, "known-gap-location",
                    "scenario under known-gaps/ must declare known_gap: true "
                    "(or leave the directory)",
                )
            )
        level = data.get("level")
        if level is None:
            findings.append(
                LintFinding(
                    str(yaml_path), 0, "level",
                    "missing 'level' — every scenario must declare the user "
                    "level it serves: 'agent-user' or 'human-quality' (T-19; C-01)",
                )
            )
        elif level not in LEVELS:
            findings.append(
                LintFinding(
                    str(yaml_path), 0, "level",
                    f"unknown 'level' {level!r} — must be one of {sorted(LEVELS)} "
                    "(agent-user = conformance, human-quality = result quality)",
                )
            )
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
    scenarios_dirs: str | Path | Sequence[str | Path],
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
        dirs_list: list[str | Path] = (
            [scenarios_dirs]
            if isinstance(scenarios_dirs, (str, Path))
            else list(scenarios_dirs)
        )
        all_stems: set[str] = set()
        for d in dirs_list:
            for p in _discover_files(d):
                if scenario_substr.lower() in p.stem.lower():
                    all_stems.add(_name_of(p))
        stem_names = all_stems
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
    order = ("passed", "failed", "invalid", "unconfigured", "partial-pass", "recovered", "known-gap")
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


_REPO_DIR_MAP: dict[str, list[str]] = {
    "suite": ["scenarios"],
    "opp": ["Omni_Pre_Processor/scenarios"],
    "ol": ["Omni_Localizer/scenarios"],
    "orf": ["Omni_Re_Formatter/scenarios"],
    "all": [
        "scenarios",
        "Omni_Pre_Processor/scenarios",
        "Omni_Localizer/scenarios",
        "Omni_Re_Formatter/scenarios",
    ],
}

REPO_HELP = "scenario source repo(s): suite (default), opp, ol, orf, or all"


def _load_script(name: str, rel_path: str) -> Any:
    """Lazily load a ``scripts/validation`` module by path.

    ``scripts/`` has no package ``__init__``, so a plain import cannot
    resolve from ``omni_mcp``; importlib by absolute path keeps the
    post-run extras (report card, delivery package) out of ``--help`` /
    ``--check`` / ``--list`` hot paths.  Raises ImportError when the
    target file is missing.
    """
    target = Path(__file__).resolve().parents[2] / rel_path
    spec = importlib.util.spec_from_file_location(name, target)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {target}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
        "--allow-fake",
        action="store_true",
        help="R-07 contract-only escape hatch: with OMNI_TEST_FAKE_LLM=1 active, "
        "re-admit a human-quality-family scenario ONLY when every step cites an "
        "AGENT-SURFACE anchor (anchor-less is ineligible); human-quality anchors "
        "and fake-echo artifacts stay invalid",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="per-step detail in the summary"
    )
    parser.add_argument(
        "--check", action="store_true", help="contract lint (falsifiable, no self-echo PASS/FAIL, standard anchors, known-gap location, declared user level) without executing"
    )
    parser.add_argument("--tier", type=int, choices=[1, 2, 3], default=None, help=TIER_HELP)
    parser.add_argument(
        "--repo",
        choices=["opp", "ol", "orf", "suite", "all"],
        default=None,
        help=REPO_HELP,
    )
    parser.add_argument(
        "--matrix", action="store_true",
        help="after the run, build the director report (report.md + report.json "
        "with the per-repo report_card) in the run dir and print MATRIX: <path>; "
        "with --artifacts, build the ARTIFACT-assertion matrix instead "
        "(artifact-report.json) and print ARTIFACT MATRIX: <path>",
    )
    parser.add_argument(
        "--artifacts",
        metavar="PATH",
        default=None,
        help="run the artifact-assertion matrix on produced artifacts (a "
        "directory or delivery .zip; 01-RAW/ preferred) — implies --matrix; "
        "P0/P1 assertion failures drive a nonzero exit (issue #44)",
    )
    parser.add_argument(
        "--deliver", action="store_true",
        help="after the run, build the human-review delivery zip in "
        "04-Output/artifacts/deliverables/omni-suite/ and print DELIVERY: <zip>",
    )
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

    if args.repo is not None:
        dirs = _REPO_DIR_MAP[args.repo]
    else:
        dirs = [args.scenarios_dir]

    if args.check:
        all_findings: list[LintFinding] = []
        for d in dirs:
            all_findings.extend(lint_scenarios(d))
        if all_findings:
            print(f"Contract check: {len(all_findings)} finding(s)")
            for f in all_findings:
                print(f"  [x] {f.file}: step {f.step} [{f.rule}] {f.detail}")
            return 1
        print(
            "Contract check: clean — every step falsifiable, no self-echo "
            "PASS/FAIL, standard citations resolve to STANDARDS.md anchors, "
            "known-gap scenarios isolated under known-gaps/, every scenario "
            "declares an approved user level"
        )
        return 0

    # --artifacts without --matrix is treated as --matrix --artifacts (issue
    # #44 acceptance uses `validation --matrix --module opp --artifacts <dir>`).
    if args.artifacts is not None:
        args.matrix = True

    try:
        loaded: list[dict[str, Any]] = []
        for d in dirs:
            loaded.extend(load_scenarios(d))
    except ScenarioError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.list:
        names, _empty = _select_names(
            loaded, dirs, args.scenario, args.tier, args.category,
            None if args.artifacts else args.module,
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
        loaded, dirs, args.scenario, args.tier, args.category,
        None if args.artifacts else args.module,
    )
    for flt in empty_filters:
        print(f"WARNING: no scenarios match {flt}")
    if empty_filters:
        return 0

    if not names:
        dir_label = ", ".join(dirs) if len(dirs) > 1 else dirs[0]
        print(f"no scenarios found in {dir_label} (nothing to run)")
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
        run = run_scenarios(
            dirs,
            filters=filters,
            runs_dir=args.runs_dir,
            allow_fake=args.allow_fake,
        )
    except ScenarioError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        f"Run {run.run_id} — trace {run.trace_id}  "
        f"(details: {run.run_dir})"
    )
    _print_verdict_table(run.scenarios, args.verbose)

    matrix_exit_code: int | None = None  # set when the artifact matrix runs
    if args.matrix:
        if args.artifacts is not None:
            try:
                _amod = _load_script(
                    "artifact_matrix", "scripts/validation/artifact_matrix.py"
                )
                module = args.module or args.repo or "suite"
                report = _amod.build_artifact_report(
                    args.artifacts, module, run.run_dir
                )
                report_path = _amod.write_artifact_report(report, run.run_dir)
                print(f"ARTIFACT MATRIX: {report_path}")
                counts = report.get("counts") or {}
                p0 = int(counts.get("p0_failed") or 0)
                p1 = int(counts.get("p1_failed") or 0)
                print(
                    f"  artifact assertions: {counts.get('artifacts', 0)} "
                    f"artifact(s), {counts.get('assertions', 0)} assertion(s), "
                    f"{counts.get('passed', 0)} passed, {counts.get('failed', 0)} "
                    f"failed (P0: {p0}, P1: {p1})"
                )
                if p0 + p1 > 0:
                    matrix_exit_code = 1
            except Exception as exc:  # artifact matrix must not fail the run
                print(
                    f"WARNING: artifact matrix failed: {exc}", file=sys.stderr
                )
        else:
            try:
                _report_mod = _load_script(
                    "validation_report", "scripts/validation/validation_report.py"
                )
                report_scenarios_dir = args.scenarios_dir if args.repo is None else dirs[0]
                run_dir = run.run_dir
                if run_dir is None:
                    raise RuntimeError("run directory was not persisted")
                _report_mod.write_report(
                    str(Path(run_dir) / "scenarios.json"), report_scenarios_dir
                )
                print(f"MATRIX: {Path(run_dir) / 'report.md'}")
            except Exception as exc:  # report generation must not fail the run
                print(f"WARNING: report generation failed: {exc}", file=sys.stderr)

    if args.deliver:
        try:
            _delivery_mod = _load_script(
                "make_delivery_package", "scripts/validation/make_delivery_package.py"
            )
            zip_path = _delivery_mod.build_delivery(
                run.run_dir,
                "04-Output/artifacts/deliverables/omni-suite",
                tag=None,
            )
            print(f"DELIVERY: {zip_path}")
        except Exception as exc:  # delivery must not fail the run either
            print(f"WARNING: delivery package failed: {exc}", file=sys.stderr)

    scenario_failures = any(
        r.status in ("failed", "invalid") and not getattr(r, "known_gap", False)
        for r in run.scenarios
    )
    # With --artifacts the ARTIFACT matrix drives the exit code (any P0/P1
    # failure -> 1); the scenario verdicts still print but do not override it.
    if matrix_exit_code is not None:
        return matrix_exit_code
    return 1 if scenario_failures else 0
