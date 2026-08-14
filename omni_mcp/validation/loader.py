"""loader.py — phase 1 of the validation engine: scenario discovery + schema
validation (guide §2 schema, §3 load phase; AutoInfo reference
``src/autoinfo/mcp/validation.py:781-872``).

The loader is the contract (guide §2.4): a scenario that reaches the
executor was already validated; one that fails validation is rejected at
load time, before any real call runs.  Rejection is loud by design — a
malformed scenario raises :class:`ScenarioError` naming the file and the
rule violated, never silently skipped, never counted as coverage.

Discovery is a recursive glob over ``scenarios/**/*.yaml`` (dot-dirs
skipped): new files are picked up with zero registration.  The glob is the
registration mechanism (guide §3.1 phase 1).

Only Python 3.13 stdlib + PyYAML — no other dependencies (guide §3.6).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Closed field sets (guide §2.4: "an unrecognized key is a typo in waiting,
# and the loader should reject it rather than guess").
# ---------------------------------------------------------------------------

#: Allowed top-level scenario fields: the guide §2.1 header + §2.4 defaults,
#: plus the D12 additions (``instructions``, per-step ``standard`` citations)
#: and the regression pair (guide §2.1).
_SCENARIO_FIELDS = frozenset(
    {
        "name",              # required — unique identifier
        "description",       # required — what the scenario proves
        "steps",             # required — non-empty list of steps
        "category",          # optional — grouping label (default "general")
        "requires_env",      # optional — list of env var names
        "requires_http",     # optional — flag: needs a live HTTP service
        "min_passing",       # optional — partial-pass: int count
        "pass_ratio",        # optional — partial-pass: float fraction
        "regression",        # optional — marks a regression scenario
        "regression_issue",  # optional — bug reference pinned (required with regression)
        "instructions",      # optional (D12) — human-readable "what to do"
        "cleanup_steps",     # optional — steps run best-effort after the main steps
        "tier",              # optional (plan todo 9) — AutoInfo tier model:
                             # 1 = no keys hermetic, 2 = LLM key,
                             # 3 = paid/external/network (default 1)
    }
)

#: Allowed per-step fields (guide §2.2 + §2.4 + D12).  ``expect`` is the
#: mandatory heart of every step; ``standard`` is an opaque citation string
#: (D12), resolved against STANDARDS.md anchors by the contract lint (todo 9).
_STEP_FIELDS = frozenset(
    {
        "name",               # optional — human-readable label
        "kind",               # required — surface selector: mcp | cli | python
        "tool",               # mcp kind — the named tool
        "arguments",          # mcp kind — parameters (default {})
        "command",            # cli/python kind — the exact command line
        "expect",             # required — the assertions the response must satisfy
        "timeout_seconds",    # optional — hard wall-clock cap for this step
        "recovery_steps",     # optional — steps run only after the primary fails
        "collect_artifacts",  # optional — files/payloads the step proves exist
        "standard",           # optional (D12) — STANDARDS.md#<anchor> citation
        "instructions",       # optional (D12) — per-step "what to check" text
    }
)

#: The closed set of surface kinds this suite's engine can dispatch
#: (plan todo 6: cli → subprocess, mcp → in-process real module tool
#: function, python → subprocess python snippet).  HTTP is deferred.
KINDS = ("mcp", "cli", "python")


class ScenarioError(ValueError):
    """A scenario file failed validation at load time.

    Carries the offending file path and the human-readable rule that was
    violated, so the message reads e.g. ``scenarios/opp/bad.yaml: step 2
    missing 'expect'``.
    """

    def __init__(self, path: str | Path, rule: str) -> None:
        self.path = str(path)
        self.rule = rule
        super().__init__(f"{self.path}: {rule}")


# ---------------------------------------------------------------------------
# Step-level validation
# ---------------------------------------------------------------------------


def _validate_collect_artifacts(
    artifacts: Any, path: str | Path, where: str
) -> None:
    if artifacts is None:
        return
    if not isinstance(artifacts, list):
        raise ScenarioError(path, f"{where} 'collect_artifacts' must be a list")
    for i, entry in enumerate(artifacts, 1):
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ScenarioError(
                path,
                f"{where} 'collect_artifacts' entry {i} must be a mapping "
                f"with a 'path' string",
            )


def _validate_step(step: Any, path: str | Path, where: str) -> None:
    """Validate one step dict (guide §2.2/§2.4).  *where* names the step in
    the error message, e.g. ``step 2`` or ``cleanup step 1``."""
    if not isinstance(step, dict):
        raise ScenarioError(path, f"{where} must be a mapping, got {type(step).__name__}")

    unknown = set(step) - _STEP_FIELDS
    if unknown:
        raise ScenarioError(
            path,
            f"{where} has unknown field(s): {', '.join(sorted(unknown))} "
            f"(allowed: {', '.join(sorted(_STEP_FIELDS))})",
        )

    # kind: the surface selector — required per step (guide §2.4).
    kind = step.get("kind")
    if kind is None:
        raise ScenarioError(
            path, f"{where} missing 'kind' (must be one of mcp|cli|python)"
        )
    if kind not in KINDS:
        raise ScenarioError(
            path,
            f"{where} has invalid 'kind' {kind!r} (must be one of mcp|cli|python)",
        )

    # expect: the mandatory heart of every step (guide §2.2).  A missing or
    # empty block cannot be graded — the step is not falsifiable, so it is
    # invalid at load time (mirrors AutoInfo contract lint).
    expect = step.get("expect")
    if not isinstance(expect, dict) or not expect:
        raise ScenarioError(path, f"{where} missing 'expect' (every step must be falsifiable)")

    # Call spec by kind: mcp names a tool, cli/python a command (guide §2.2).
    if kind == "mcp":
        if not isinstance(step.get("tool"), str) or not step["tool"]:
            raise ScenarioError(path, f"{where} of kind 'mcp' missing 'tool'")
        step.setdefault("arguments", {})
    else:
        if not isinstance(step.get("command"), str) or not step["command"]:
            raise ScenarioError(path, f"{where} of kind {kind!r} missing 'command'")

    timeout = step.get("timeout_seconds")
    if timeout is not None and (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or timeout <= 0
    ):
        raise ScenarioError(
            path, f"{where} 'timeout_seconds' must be a positive number, got {timeout!r}"
        )

    standard = step.get("standard")
    if standard is not None and not isinstance(standard, str):
        raise ScenarioError(
            path,
            f"{where} 'standard' must be a string citation (e.g. "
            f"STANDARDS.md#exit-codes), got {standard!r}",
        )

    instructions = step.get("instructions")
    if instructions is not None and not isinstance(instructions, str):
        raise ScenarioError(
            path, f"{where} 'instructions' must be a string, got {instructions!r}"
        )

    _validate_collect_artifacts(step.get("collect_artifacts"), path, where)

    # Secondary steps are steps too: recovery steps run only after the
    # primary fails; their own expect decides whether the recovery worked
    # (guide §2.2).  Same closed schema, empty lists allowed.
    if "recovery_steps" in step:
        _validate_steps(
            step["recovery_steps"], path, f"{where} recovery step", require_non_empty=False
        )
        step.setdefault("recovery_steps", [])
    else:
        step["recovery_steps"] = []


def _validate_steps(
    steps: Any,
    path: str | Path,
    where: str,
    require_non_empty: bool = True,
) -> None:
    """Validate a list of steps.  *where* is the singular label, e.g.
    ``step`` (top-level) or ``cleanup step``."""
    if not isinstance(steps, list):
        raise ScenarioError(path, f"{where}s must be a list, got {type(steps).__name__}")
    if require_non_empty and not steps:
        raise ScenarioError(
            path,
            f"{where}s must be a non-empty list (a scenario with no steps is a "
            f"declaration, not a proof — guide §2.1)",
        )
    for i, step in enumerate(steps, 1):
        _validate_step(step, path, f"{where} {i}")


# ---------------------------------------------------------------------------
# Scenario-level validation + defaults
# ---------------------------------------------------------------------------


def validate_scenario(scenario: dict[str, Any], path: str | Path) -> dict[str, Any]:
    """Validate one scenario dict against the guide §2 schema.

    Returns the scenario with defaults applied — the same dict the executor
    consumes (category ``general``, ``requires_env`` ``[]``,
    ``requires_http`` ``False``, ``tier`` 1, ``cleanup_steps`` ``[]``,
    per-step ``arguments``/``recovery_steps`` ``{}``/``[]``).

    Raises
    ------
    ScenarioError
        Naming *path* and the violated rule.  Unknown top-level fields are
        rejected (guide §2.4); ``regression: true`` requires
        ``regression_issue`` (guide §2.1); ``min_passing`` / ``pass_ratio``
        are validated at load time (guide §2.7).
    """
    path = Path(path)
    if not isinstance(scenario, dict):
        raise ScenarioError(
            path, f"scenario must be a YAML mapping, got {type(scenario).__name__}"
        )

    unknown = set(scenario) - _SCENARIO_FIELDS
    if unknown:
        raise ScenarioError(
            path,
            f"unknown top-level field(s): {', '.join(sorted(unknown))} "
            f"(allowed: {', '.join(sorted(_SCENARIO_FIELDS))})",
        )

    for field in ("name", "description"):
        if not isinstance(scenario.get(field), str) or not scenario[field].strip():
            raise ScenarioError(path, f"missing required field '{field}'")

    if "steps" not in scenario:
        raise ScenarioError(path, "missing required field 'steps'")
    _validate_steps(scenario["steps"], path, "step")

    # Optional header fields — type-checked, then defaults applied.
    requires_env = scenario.get("requires_env")
    if requires_env is not None:
        if not isinstance(requires_env, list) or any(
            not isinstance(v, str) for v in requires_env
        ):
            raise ScenarioError(
                path,
                f"'requires_env' must be a list of strings, got {requires_env!r}",
            )
    scenario.setdefault("requires_env", [])

    requires_http = scenario.get("requires_http")
    if requires_http is not None and not isinstance(requires_http, bool):
        raise ScenarioError(
            path, f"'requires_http' must be a boolean flag, got {requires_http!r}"
        )
    scenario.setdefault("requires_http", False)

    category = scenario.get("category")
    if category is not None and not isinstance(category, str):
        raise ScenarioError(path, f"'category' must be a string, got {category!r}")
    scenario.setdefault("category", "general")

    instructions = scenario.get("instructions")
    if instructions is not None and not isinstance(instructions, str):
        raise ScenarioError(path, f"'instructions' must be a string, got {instructions!r}")

    # AutoInfo tier model (plan todo 9): 1 = no keys hermetic, 2 = LLM
    # key, 3 = paid/external/network.  Optional with default 1 — the CLI
    # ``--tier`` filter runs only scenarios whose tier matches.
    tier = scenario.get("tier")
    if tier is not None and (
        isinstance(tier, bool)
        or not isinstance(tier, int)
        or tier not in (1, 2, 3)
    ):
        raise ScenarioError(
            path,
            f"'tier' must be an integer in 1|2|3 (1=no keys hermetic, "
            f"2=LLM key, 3=paid/external/network), got {tier!r}",
        )
    scenario.setdefault("tier", 1)

    # Partial-pass policy (guide §2.7): validated at load time.
    min_passing = scenario.get("min_passing")
    if min_passing is not None and (
        isinstance(min_passing, bool)
        or not isinstance(min_passing, int)
        or min_passing <= 0
    ):
        raise ScenarioError(
            path, f"'min_passing' must be a positive integer, got {min_passing!r}"
        )
    pass_ratio = scenario.get("pass_ratio")
    if pass_ratio is not None and (
        isinstance(pass_ratio, bool)
        or not isinstance(pass_ratio, float)
        or not (0 < pass_ratio <= 1)
    ):
        raise ScenarioError(
            path, f"'pass_ratio' must be a float in (0, 1], got {pass_ratio!r}"
        )

    # Regression pair (guide §2.1): ``regression: true`` pins a bug reference.
    regression = scenario.get("regression")
    if regression is not None and not isinstance(regression, bool):
        raise ScenarioError(path, f"'regression' must be a boolean, got {regression!r}")
    if regression and not isinstance(scenario.get("regression_issue"), str):
        raise ScenarioError(
            path,
            "'regression: true' requires 'regression_issue' naming the pinned "
            "bug reference (e.g. \"#104\")",
        )
    regression_issue = scenario.get("regression_issue")
    if regression_issue is not None and not isinstance(regression_issue, str):
        raise ScenarioError(
            path, f"'regression_issue' must be a string, got {regression_issue!r}"
        )

    cleanup_steps = scenario.get("cleanup_steps")
    if cleanup_steps is not None:
        _validate_steps(
            cleanup_steps, path, "cleanup step", require_non_empty=False
        )
    scenario.setdefault("cleanup_steps", [])

    return scenario


# ---------------------------------------------------------------------------
# Phase 1: load — recursive glob over the scenarios directory
# ---------------------------------------------------------------------------


def load_scenarios(scenarios_dir: str | Path = "scenarios") -> list[dict[str, Any]]:
    """Discover and validate every ``*.yaml`` scenario under *scenarios_dir*.

    Recursive glob (guide §3.1 phase 1): a YAML file dropped anywhere in the
    tree is picked up with zero registration.  Dot-directories are skipped,
    files are processed in sorted order for deterministic runs, and an empty
    or missing directory yields ``[]`` (the ``scenarios/`` library has no
    YAML until Wave 3).

    Returns
    -------
    list[dict]
        Validated scenario dicts with defaults applied (see
        :func:`validate_scenario`).

    Raises
    ------
    ScenarioError
        For the first malformed file, naming the file path and the rule
        violated — never silently skipped, never counted as coverage.
    """
    sd = Path(scenarios_dir)
    scenarios: list[dict[str, Any]] = []
    if not sd.is_dir():
        return scenarios

    for yaml_path in sorted(sd.rglob("*.yaml")):
        # Skip dot-dirs (.git/, .hidden/, ...) — they are not scenario libraries.
        if any(part.startswith(".") for part in yaml_path.parts):
            continue
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            raise ScenarioError(yaml_path, f"failed to parse YAML: {exc}") from exc
        if data is None:
            raise ScenarioError(yaml_path, "empty YAML file — expected a scenario mapping")
        scenarios.append(validate_scenario(data, yaml_path))

    return scenarios
