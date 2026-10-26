"""engine.py — the validation orchestrator: guide §3 phases 1-6 in order.

Load (``loader.load_scenarios``) -> dispatch (``dispatch_step``) -> grade
(``grade_step``) -> aggregate -> trace -> persist.  The engine returns a
:class:`RunResult` (structured data only); exit-code mapping is the CLI's
job (todo 9).

Adopted defaults (draft ``.omo/drafts/validation-framework.md``, task 8):

- **trace_id: one per RUN** (guide §3.1 phase 5 "one UUID per run,
  threaded into every artifact the run produces").  Every scenario, step,
  recovery record, and cleanup record of the run shares it.
- **arguments echo**: mcp steps echo their ``arguments`` dict; cli/python
  steps echo ``{"command": <command line>}`` (their call spec IS the
  command line; dispatch already echoes the exact invocation in
  ``real_call``).
- **cleanup records carry step_index 0**: they are not part of the graded
  sequence (guide §2.6 best-effort, never affect the verdict).  Recovery
  records carry the primary step's step_index and are nested under the
  primary record's ``recovery`` key.
- **env gate checks the EFFECTIVE environment**: the explicit ``env``
  parameter when given (exactly what dispatch will run the steps with —
  ``build_cli_env`` semantics in dispatch.py), else ``os.environ``.  A var
  present but empty counts as missing (empty counts as missing).
  The gate is two-layered: ``requires_env`` is **AND** (every var must
  resolve); ``requires_env_any``, when declared, is an **OR** group that
  overrides the AND list the moment ONE of its vars resolves.  An OR group
  with no resolving var fails **closed** — the scenario is ``unconfigured``
  even when ``requires_env`` is empty, so a keyless user never reaches a
  real LLM call.  An absent or empty ``requires_env_any`` is byte-identical
  to the old AND-only gate.  (The suite declares no HTTP surface, so the
  unused ``requires_http`` field was removed — T-21.)
- **verdict derivation order** (guide §3.3 aggregate): env gate ->
  all primary steps green (``recovered`` if any step was recovered, else
  ``passed``) -> partial-pass policy (``min_passing`` OR ``pass_ratio``,
  the partial-pass bar) -> ``failed``.  ``unconfigured`` comes ONLY from
  the gate, never from an output check.  The R-07 fake guard then overrides
  to ``invalid`` when ``OMNI_TEST_FAKE_LLM=1`` is active and the scenario is
  human-quality evidence (or a produced artifact carries the fake echo).
- **recovery is one level deep** (guide §2.6): recovery steps never run
  their own recovery; cleanup steps run without recovery.
- **persist stamp** ``%Y%m%d-%H%M%S``; a same-second collision gets a
  short random suffix so runs are immutable ("written once", guide §3.1
  phase 6).  ``latest.txt`` holds the run dir NAME — join it with the
  runs dir to read the run.

Only Python 3.13 stdlib — no new dependencies (guide §3.6).
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import os
import re
import subprocess
import time
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from omni_mcp.validation.dispatch import StepResult, dispatch_step
from omni_mcp.validation.family import (
    HUMAN_QUALITY,
    all_steps_agent_surface,
    family_of,
)
from omni_mcp.validation.grader import grade_step
from omni_mcp.validation.loader import load_scenarios

_FAKE_LLM_ENV = "OMNI_TEST_FAKE_LLM"

#: The ``_FakeModelPool`` echo signature: a bracketed target language code
#: at the start of a line (``[zh] ...``, ``[xx] ...``).  MULTILINE so a
#: marker on any line trips it, not only the first (OL's E2E-65 strip does
#: not remove ``[xx] ``).
_FAKE_ECHO_RE = re.compile(r"^\[[A-Za-z][A-Za-z0-9_-]*\] ", re.MULTILINE)

#: The rate-limit-exhaustion signature (issue #194): litellm's
#: ``RateLimitError`` or a bare HTTP ``429`` in a step's captured output.
#: Case-insensitive so a ``ratelimiterror`` in a lowercase traceback still
#: matches; ``\b429\b`` keeps ``14290`` out.
_RATE_LIMIT_RE = re.compile(r"RateLimitError|\b429\b", re.IGNORECASE)


@dataclasses.dataclass
class ScenarioResult:
    """The per-scenario half of a run record (phase 4 aggregate + phase 5
    trace): the verdict plus every step's full trace."""

    #: Unique identifier (the scenario's ``name`` field).
    name: str
    #: ``passed`` | ``failed`` | ``unconfigured`` | ``recovered`` |
    #: ``partial-pass`` | ``invalid`` | ``known-gap`` (T-17 — a scenario
    #: marked ``known_gap: true``; never a pass, never a failure).
    status: str
    #: Human-readable one-line summary for the director report.
    summary: str
    #: Missing env vars when ``unconfigured``; ``[]`` when the scenario was
    #: configured (guide §4.2: reason attached, never silent, never
    #: pass/fail).  Carries the unmet ``requires_env`` (AND) vars plus, when
    #: a declared ``requires_env_any`` OR group is unsatisfied, its member
    #: names — the report renders them as the missing prerequisites.
    missing_env: list[str]
    #: Per-step trace records (phase 5): step_index / duration_seconds /
    #: arguments / trace_id / surface / real_call / expect / actual /
    #: grade / recovery.
    steps: list[dict[str, Any]]
    #: Best-effort cleanup step records (step_index 0; never graded into
    #: the verdict — guide §2.6).
    cleanup: list[dict[str, Any]]
    #: The run-wide trace id (shared by every record of the run).
    trace_id: str
    #: T-17: a ``known_gap: true`` scenario asserts a bar the pipeline
    #: cannot yet meet.  Its status is ``known-gap`` and it is excluded
    #: from the pass bar (never drives a nonzero exit, never a blocker).
    known_gap: bool = False
    #: Issue #205: the scenario's declared ``level`` is the authoritative
    #: verdict family.  Persisted so the report reads the rule the engine
    #: enforced instead of re-deriving it from the name.
    level: str | None = None
    #: Issue #205: a lint-justified escape hatch for level != derived family.
    family_override: str | None = None
    #: Issue #205: why the override exists (the lint requires it).
    family_override_reason: str | None = None
    #: Issue #206: waived steps that PASSED this run — the known_gap is
    #: closed and the waiver should be removed.  Empty when nothing closed.
    gap_closed: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class RunResult:
    """The full run record (guide §3.1 phase 6): trace id, timestamp, and
    every scenario result.  ``run_id`` / ``run_dir`` are set by
    :func:`persist_run`."""

    #: One UUID per run, threaded into every step and artifact.
    trace_id: str
    #: ISO-8601 timestamp of when the run was assembled.
    timestamp: str
    #: Scenario results, in load order.
    scenarios: list[ScenarioResult]
    #: Name of the run directory once persisted (else None).
    run_id: str | None = None
    #: Absolute/relative path of the run directory once persisted (else None).
    run_dir: str | None = None
    #: Component versions + git SHAs for the run (populated by collect_run_meta).
    run_meta: dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# run_meta: component versions + git SHAs
# ---------------------------------------------------------------------------

_SUITE_ROOT = Path(__file__).resolve().parents[2]  # Omni_Suite/

_COMPONENT_DIRS: dict[str, Path] = {
    "opp": _SUITE_ROOT / "Omni_Pre_Processor",
    "ol": _SUITE_ROOT / "Omni_Localizer",
    "orf": _SUITE_ROOT / "Omni_Re_Formatter",
}


def _read_version_file(path: Path) -> str:
    try:
        raw = path.read_text(encoding="utf-8").strip()
        for line in raw.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    except Exception:
        pass
    return "unknown"


def _read_toml_version(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("version") and "=" in stripped:
                val = stripped.split("=", 1)[1].strip().strip('"').strip("'")
                return val
    except Exception:
        pass
    return "unknown"


def _git_sha(repo_dir: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def collect_run_meta(repos: list[str]) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    try:
        meta["suite_version"] = _read_version_file(_SUITE_ROOT / "VERSION")
        meta["suite_sha"] = _git_sha(_SUITE_ROOT)
    except Exception:
        pass

    for repo in repos:
        if repo == "suite":
            continue
        comp_dir = _COMPONENT_DIRS.get(repo)
        if comp_dir is None:
            continue
        entry: dict[str, Any] = {}
        try:
            entry["version"] = _read_toml_version(comp_dir / "pyproject.toml")
        except Exception:
            entry["version"] = "unknown"
        try:
            entry["sha"] = _git_sha(comp_dir)
        except Exception:
            entry["sha"] = "unknown"
        meta[repo] = entry

    if "suite_version" not in meta:
        meta["suite_version"] = "unknown"
    if "suite_sha" not in meta:
        meta["suite_sha"] = "unknown"
    meta["repos"] = [r for r in repos if r != "suite"]
    return meta


# ---------------------------------------------------------------------------
# Phase 4 gate: unconfigured before any dispatch (guide §2.5, §4.2)
# ---------------------------------------------------------------------------


def _effective_env(env: dict[str, str] | None) -> Mapping[str, str]:
    """The environment the gate and the dispatched steps share: the
    explicit *env* when given, else the parent ``os.environ``.

    Returns ``Mapping`` (not ``dict``): ``os.environ`` is a
    ``MutableMapping`` view, not a ``dict``, and every caller here only
    reads.  Annotating it as ``dict`` was a lie mypy rejected.
    """
    return env if env is not None else os.environ


def _missing_env(scenario: dict[str, Any], env: dict[str, str] | None) -> list[str]:
    """Env prerequisites absent from the effective env, under the two-layer
    gate.

    ``requires_env`` is **AND**: every listed var must resolve.  When
    ``requires_env_any`` is declared it is an **OR** group that overrides
    the AND list as soon as ONE of its vars resolves — the scenario is
    configured even if some ``requires_env`` vars are missing (an "any of"
    escape hatch for users holding a single provider key).

    When the OR group is declared and NONE of its vars resolve, the result
    is **fail-closed**: the list is non-empty even if ``requires_env`` is
    empty or absent, so the scenario stays ``unconfigured`` and never
    reaches dispatch.  The returned names are the unmet AND vars followed by
    the OR group's members — plain variable names, so the report's
    "missing env var(s)" line renders them without a sentinel.

    A var present but empty counts as missing for both layers
    (a prerequisite that exists but is unusable is
    still a missing prerequisite).  An absent or empty
    ``requires_env_any`` returns exactly the AND-only list (unchanged
    behaviour).
    """
    effective = _effective_env(env)
    missing_and = [v for v in scenario.get("requires_env", []) if not effective.get(v)]
    or_group = scenario.get("requires_env_any", [])
    if not or_group:
        return missing_and
    if any(effective.get(v) for v in or_group):
        return []  # OR group satisfied: configured despite any missing AND vars
    # Fail-closed: no OR member resolved.  Report the AND list (when unmet)
    # plus every OR member so the operator sees which group was unmet.
    return list(dict.fromkeys(missing_and + list(or_group)))


# ---------------------------------------------------------------------------
# R-07: family/anchor-classified fake-invalid
# ---------------------------------------------------------------------------


def _fake_marker_path(steps: list[dict[str, Any]]) -> str | None:
    """The first declared artifact whose whole text carries the
    ``_FakeModelPool`` echo signature, else None.

    Whole-artifact scan: every ``collect_artifacts`` path is read in full
    and searched line-by-line (``re.MULTILINE``) — a marker on a non-first
    line still trips it.  Unreadable paths are skipped, never fatal.
    """
    for step in steps:
        for artifact in step.get("collect_artifacts") or []:
            path = artifact.get("path") if isinstance(artifact, dict) else None
            if not path:
                continue
            try:
                text = Path(path).read_text(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                continue
            if _FAKE_ECHO_RE.search(text):
                return str(path)
    return None


def _fake_llm_reason(
    scenario: dict[str, Any], env: dict[str, str] | None, allow_fake: bool
) -> str | None:
    """Why a fake-active scenario's verdict must be ``invalid``, else None.

    Fires only when ``OMNI_TEST_FAKE_LLM=1`` is active in the effective
    env.  A human-quality scenario (name family OR any HUMAN-QUALITY anchor
    citation) is invalid regardless of flags; ``--allow-fake`` re-admits it
    only when EVERY step cites an AGENT-SURFACE anchor (anchor-less is
    ineligible, non-vacuous).  Independently, a produced artifact carrying
    the fake echo signature is invalid — positive fake content cannot be
    waved away.
    """
    if _effective_env(env).get(_FAKE_LLM_ENV) != "1":
        return None
    steps = scenario.get("steps", [])
    family, derivation = family_of(
        scenario["name"],
        steps,
        level=scenario.get("level"),
        override=scenario.get("family_override"),
    )
    human_quality = family == HUMAN_QUALITY
    if human_quality and not (allow_fake and all_steps_agent_surface(steps)):
        return (
            "OMNI_TEST_FAKE_LLM=1 is active and this scenario is "
            "human-quality evidence — fake output is never admissible "
            f"(family={family}, derivation={derivation})"
        )
    marker = _fake_marker_path(steps)
    if marker is not None:
        return (
            "OMNI_TEST_FAKE_LLM=1 is active and artifact "
            f"{marker!r} carries the `[<tgt>] ` fake-echo signature"
        )
    return None


# ---------------------------------------------------------------------------
# Phases 2 + 3 + 5, one step: dispatch, grade, trace (guide §3.3)
# ---------------------------------------------------------------------------


def _step_arguments(step: dict[str, Any]) -> dict[str, Any]:
    """Echo of the step's call spec for the trace record.

    mcp steps echo their ``arguments`` dict; cli/python steps echo
    ``{"command": ...}`` (their call spec is the command line).
    """
    if step.get("kind") == "mcp":
        return dict(step.get("arguments") or {})
    return {"command": step["command"]}


def _is_throttled(actual: dict[str, Any]) -> bool:
    """Whether a step's actual block names rate-limit exhaustion (#194).

    cli/python steps put the router log in ``stderr``; in-process mcp steps
    carry the exception text in ``error``; ``stdout`` is included because an
    MCP wrapper may print the exception there.  ``actual["throttled"]`` is
    honoured as a direct signal too, so a future dispatcher-side classifier
    needs no engine change.
    """
    if actual.get("throttled") is True:
        return True
    return any(
        isinstance(actual.get(field), str) and _RATE_LIMIT_RE.search(actual[field])
        for field in ("stderr", "error", "stdout")
    )


def _step_status(
    known_gap: bool,
    passed: bool,
    timed_out: bool = False,
    throttled: bool = False,
    stalled: bool = False,
) -> str:
    """The per-step status: ``passed`` | ``known-gap`` | ``throttled`` |
    ``stalled`` | ``timeout`` | ``failed``.

    A timed-out step keeps ``passed`` False (it still drives the scenario
    verdict exactly as a failure would), but its status is ``timeout`` — a
    distinct presentation from an assertion failure, so the record and the
    report separate "we ran out of wall-clock" from "the output was wrong"
    (issue #176).  A 429 that exhausted the retry chain is ``throttled``
    (the actionable cause), and a subprocess silent past the stall cap is
    ``stalled`` (issue #194); both still count as failures for the scenario
    verdict, but are distinct in the record and the report.  Known-gap wins
    over all of them so a weakened bar stays excluded from the pass bar.
    """
    if passed:
        return "passed"
    if known_gap:
        return "known-gap"
    if throttled:
        return "throttled"
    if stalled:
        return "stalled"
    return "timeout" if timed_out else "failed"


def _execute_step(
    step: dict[str, Any],
    env: dict[str, str] | None,
    trace_id: str,
    index: int,
    *,
    with_recovery: bool = True,
    step_timeout: float | None = None,
) -> dict[str, Any]:
    """Dispatch one step to its real surface, grade the expect block, and
    decorate the record with the trace fields (guide §3.1 phases 2, 3, 5).

    On a failed primary with declared ``recovery_steps`` (and
    *with_recovery*), each recovery step runs in order; the first passing
    recovery call flips the record to ``status: recovered`` (``passed``
    True for verdict purposes) while the primary's RED grade stays in the
    record (guide §2.6: "Recovery never erases RED").  Timeouts arrive as
    failed steps from dispatch (``actual.timeout``) and propagate as-is —
    no extra handling (dispatch.py envelopes, guide §3.3).

    *index* is the 1-based step position; recovery records carry the
    primary's index, cleanup records use 0 (documented in the module
    docstring).  *step_timeout* (the ``--step-timeout`` cap) is forwarded to
    the ``cli``/``python`` adapters (issue #176).
    """
    try:
        sr = dispatch_step(step, env, step_timeout)
    except Exception as exc:  # undeclared surface etc. — fail loudly, never fake
        sr = StepResult(
            surface=f"{step.get('kind')}: (dispatch error)",
            real_call=str(step),
            expect=dict(step.get("expect") or {}),
            actual={"success": False, "error": str(exc)},
            artifact_to_show=None,
            standard=step.get("standard"),
            duration_seconds=0.0,
        )
    grade = grade_step(step.get("expect"), sr.actual)
    known_gap = bool(step.get("known_gap"))
    timed_out = bool(sr.actual.get("timeout"))
    throttled = not grade.passed and _is_throttled(sr.actual)
    stalled = not grade.passed and bool(sr.actual.get("stalled"))
    record: dict[str, Any] = {
        "step_index": index,
        "name": step.get("name") or ("cleanup step" if index == 0 else f"step {index}"),
        "kind": step.get("kind"),
        "surface": sr.surface,
        "real_call": sr.real_call,
        "expect": sr.expect,
        "actual": sr.actual,
        "artifact_to_show": sr.artifact_to_show,
        "standard": sr.standard,
        "arguments": _step_arguments(step),
        "duration_seconds": sr.duration_seconds,
        "trace_id": trace_id,
        "passed": grade.passed,
        "known_gap": known_gap,
        "timed_out": timed_out,
        "throttled": throttled,
        "stalled": stalled,
        "status": _step_status(
            known_gap, grade.passed, timed_out, throttled, stalled
        ),
        "grade": dataclasses.asdict(grade),
        "recovery": [],
        "recovery_status": None,
    }
    if with_recovery and not grade.passed and step.get("recovery_steps"):
        for rstep in step["recovery_steps"]:
            rrec = _execute_step(
                rstep, env, trace_id, index, with_recovery=False,
                step_timeout=step_timeout,
            )
            record["recovery"].append(rrec)
            if rrec["passed"]:
                record["status"] = "recovered"
                record["passed"] = True
                record["recovery_status"] = "passed"
                break
        else:
            record["recovery_status"] = "failed"
    return record


# ---------------------------------------------------------------------------
# Phase 4: aggregate — derive the scenario verdict (guide §3.3)
# ---------------------------------------------------------------------------


def _aggregate(scenario: dict[str, Any], records: list[dict[str, Any]]) -> str:
    """Derive the scenario status from the step records.

    Order (module docstring): all green -> ``recovered`` if any step was
    recovered else ``passed``; otherwise the partial-pass policy
    (``min_passing`` count or ``pass_ratio`` fraction of succeeded steps,
    OR — the partial-pass bar) -> ``partial-pass`` when the bar is met,
    else ``failed``.  ``unconfigured`` is never produced here — it comes
    only from the pre-dispatch gate.
    """
    graded = [r for r in records if not r.get("known_gap")]
    if records and not graded:
        return "invalid"
    failed = [r for r in records if not r["passed"] and not r.get("known_gap")]
    if not failed:
        return "recovered" if any(r["status"] == "recovered" for r in records) else "passed"
    succeeded = len(graded) - len(failed)
    total = len(graded)
    bar_ok = False
    min_passing = scenario.get("min_passing")
    pass_ratio = scenario.get("pass_ratio")
    if min_passing is not None and succeeded >= min_passing:
        bar_ok = True
    if not bar_ok and pass_ratio is not None and total > 0:
        bar_ok = (succeeded / total) >= pass_ratio
    return "partial-pass" if bar_ok else "failed"


def _gap_closed_suffix(records: list[dict[str, Any]]) -> str:
    closed = [
        str(r.get("name") or f"step {r.get('step_index')}")
        for r in records
        if r.get("known_gap") and r.get("passed")
    ]
    if not closed:
        return ""
    return (
        f"; GAP CLOSED: {len(closed)} waived step(s) now pass "
        f"({', '.join(closed)}) — remove the waiver (issue #206)"
    )


def _summary(
    scenario: dict[str, Any],
    status: str,
    records: list[dict[str, Any]],
    missing: list[str],
    *,
    reason: str = "",
) -> str:
    if status == "unconfigured":
        message = f"unconfigured — missing env var(s): {', '.join(missing)}"
        or_group = scenario.get("requires_env_any") or []
        if or_group:
            message += f" (satisfied by any ONE of: {', '.join(or_group)})"
        return message
    if reason:
        return f"{status} — {reason}{_gap_closed_suffix(records)}"
    passed = sum(1 for r in records if r["passed"])
    gap_steps = sum(1 for r in records if r.get("known_gap"))
    timeout_steps = sum(1 for r in records if r.get("timed_out"))
    throttled_steps = sum(1 for r in records if r.get("throttled"))
    stalled_steps = sum(1 for r in records if r.get("stalled"))
    suffix = f", {gap_steps} known-gap step(s)" if gap_steps else ""
    timeout_suffix = f", {timeout_steps} timed out" if timeout_steps else ""
    throttled_suffix = f", {throttled_steps} throttled" if throttled_steps else ""
    stalled_suffix = f", {stalled_steps} stalled" if stalled_steps else ""
    return (
        f"{status} — {len(records)} step(s), {passed} passed"
        f"{timeout_suffix}{throttled_suffix}{stalled_suffix}{suffix}"
        f"{_gap_closed_suffix(records)}"
    )


def _run_one(
    scenario: dict[str, Any],
    env: dict[str, str] | None,
    trace_id: str,
    allow_fake: bool = False,
    step_timeout: float | None = None,
) -> ScenarioResult:
    """Run one scenario: gate, main steps, recovery, cleanup, aggregate.

    After aggregation the R-07 fake guard may override the verdict to
    ``invalid`` (human-quality evidence under fake, or a produced artifact
    carrying the fake echo signature).
    """
    missing = _missing_env(scenario, env)
    if missing:
        # unconfigured never passes, never fails, never half-runs (guide
        # §4.2): recorded with the missing env list and an empty step list.
        return ScenarioResult(
            name=scenario["name"],
            status="unconfigured",
            summary=_summary(scenario, "unconfigured", [], missing),
            missing_env=missing,
            steps=[],
            cleanup=[],
            trace_id=trace_id,
            known_gap=bool(scenario.get("known_gap")),
            level=scenario.get("level"),
            family_override=scenario.get("family_override"),
            family_override_reason=scenario.get("family_override_reason"),
        )
    records = [
        _execute_step(s, env, trace_id, i, step_timeout=step_timeout)
        for i, s in enumerate(scenario["steps"], 1)
    ]
    status = _aggregate(scenario, records)
    cleanup = [
        _execute_step(c, env, trace_id, 0, with_recovery=False,
                      step_timeout=step_timeout)
        for c in scenario.get("cleanup_steps", [])
    ]
    fake_reason = _fake_llm_reason(scenario, env, allow_fake)
    known_gap = bool(scenario.get("known_gap"))
    reason = fake_reason or ""
    if fake_reason is not None:
        status = "invalid"
    elif known_gap:
        status = "known-gap"
        reason = (
            "known gap — published bar not met; excluded from the pass bar "
            "(see ACCEPTED_GAPS.md)"
        )
    elif status == "invalid":
        reason = (
            "every graded step is waived by known_gap — a waiver may not "
            "cover the whole scenario verdict; add a non-waived step or "
            "remove the waiver (issue #206)"
        )
    gap_closed = [
        str(r.get("name") or f"step {r.get('step_index')}")
        for r in records
        if r.get("known_gap") and r.get("passed")
    ]
    return ScenarioResult(
        name=scenario["name"],
        status=status,
        summary=_summary(scenario, status, records, [], reason=reason),
        missing_env=[],
        steps=records,
        cleanup=cleanup,
        trace_id=trace_id,
        known_gap=known_gap,
        gap_closed=gap_closed,
        level=scenario.get("level"),
        family_override=scenario.get("family_override"),
        family_override_reason=scenario.get("family_override_reason"),
    )


# ---------------------------------------------------------------------------
# Phase 6: persist — immutable timestamped run + latest.txt pointer
# ---------------------------------------------------------------------------


#: Bytes decoded by :func:`_sanitize_for_json` are truncated to this many
#: characters so a stray binary blob cannot bloat ``scenarios.json``
#: (mirrors ``dispatch.py::_decode_output`` / ``_snip``).
_MAX_SANITIZED_BYTES = 160


def _sanitize_for_json(
    value: Any, path: str = "", problems: list[str] | None = None
) -> Any:
    """Recursively coerce *value* into a JSON-serialisable structure.

    Never raises.  ``bytes`` / ``bytearray`` decode to a string
    (``errors="replace"``, truncated to :data:`_MAX_SANITIZED_BYTES`);
    ``dict`` / ``list`` / ``tuple`` recurse; any other object falls back to
    ``str(obj)`` (same spirit as ``dispatch.py::_snip``'s ``default=str``).
    The coerced *path* of every degraded field is appended to *problems* so
    a caller can name the exact offending field
    (``scenarios[3].steps[2].actual.stdout``) when reporting.

    This is the "the record is always writable" backstop
    (e2e-test-suite#184): one stray field degrades to a string instead of
    invalidating an entire 80-minute run.
    """
    if problems is None:
        problems = []
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (bytes, bytearray)):
        text = bytes(value).decode("utf-8", errors="replace")
        if len(text) > _MAX_SANITIZED_BYTES:
            text = text[:_MAX_SANITIZED_BYTES] + "..."
        problems.append(path)
        return text
    if isinstance(value, Mapping):
        out: dict[Any, Any] = {}
        for key, item in value.items():
            if isinstance(key, (bytes, bytearray)):
                safe_key: Any = bytes(key).decode("utf-8", errors="replace")
            else:
                safe_key = key if isinstance(key, str) else str(key)
            child = f"{path}.{safe_key}" if path else str(safe_key)
            out[safe_key] = _sanitize_for_json(item, child, problems)
        return out
    if isinstance(value, (list, tuple, Sequence)) and not isinstance(value, str):
        return [
            _sanitize_for_json(item, f"{path}[{index}]", problems)
            for index, item in enumerate(value)
        ]
    problems.append(path)
    return str(value)


def persist_run(run: RunResult, runs_dir: str | Path = "validation-runs") -> Path:
    """Write the run record and refresh the latest pointer (guide §3.1
    phase 6).

    Writes ``<runs_dir>/<ts>/scenarios.json`` (ts = ``%Y%m%d-%H%M%S``,
    sortable) containing the full run record — per-scenario verdict,
    per-step trace + GradeResult, and env status (``missing_env``) — then
    refreshes ``<runs_dir>/latest.txt`` with the run directory name.
    Creates *runs_dir* when missing.  A same-second collision gets a short
    random suffix instead of overwriting: runs are immutable, written
    once.

    Returns the run directory that was written.
    """
    base = Path(runs_dir)
    base.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    run_dir = base / stamp
    if run_dir.exists():
        run_dir = base / f"{stamp}-{uuid.uuid4().hex[:6]}"
    run_dir.mkdir(parents=True, exist_ok=True)
    run.run_id = run_dir.name
    run.run_dir = str(run_dir)
    payload = {
        "run_id": run.run_id,
        "timestamp": run.timestamp,
        "trace_id": run.trace_id,
        "scenarios": [s.to_dict() for s in run.scenarios],
        "run_meta": run.run_meta,
    }
    problems: list[str] = []
    safe_payload = _sanitize_for_json(payload, "", problems)
    try:
        text = json.dumps(safe_payload, ensure_ascii=False, indent=2)
    except (TypeError, ValueError) as exc:
        location = (
            f" — offending field paths: {', '.join(sorted(set(problems)))}"
            if problems
            else ""
        )
        raise TypeError(
            f"persist_run could not serialise run record{location}: {exc}"
        ) from exc
    (run_dir / "scenarios.json").write_text(
        text, encoding="utf-8", errors="replace"
    )
    (base / "latest.txt").write_text(run_dir.name, encoding="utf-8")
    return run_dir


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def _select(
    loaded: list[dict[str, Any]], filters: list[str] | str | None
) -> list[dict[str, Any]]:
    """Apply the scenario-name filter (None = run all).  Unknown names
    match nothing — the CLI adds its own name validation (todo 9)."""
    if filters is None:
        return loaded
    if isinstance(filters, str):
        filters = [filters]
    wanted = set(filters)
    return [s for s in loaded if s["name"] in wanted]


def _dirs_to_repo_keys(dirs: list[str | Path]) -> list[str]:
    keys: list[str] = ["suite"]
    dir_strs = [str(Path(d)) for d in dirs]
    repo_map = {
        "opp": "Omni_Pre_Processor/scenarios",
        "ol": "Omni_Localizer/scenarios",
        "orf": "Omni_Re_Formatter/scenarios",
    }
    for key, expected in repo_map.items():
        if any(expected in d for d in dir_strs):
            keys.append(key)
    return keys


def run_scenarios(
    scenarios_dir: str | Path | Sequence[str | Path] = "scenarios",
    filters: list[str] | str | None = None,
    env: dict[str, str] | None = None,
    *,
    runs_dir: str | Path = "validation-runs",
    persist: bool = True,
    run_meta: dict[str, Any] | None = None,
    allow_fake: bool = False,
    step_timeout: float | None = None,
) -> RunResult:
    """Run every (filtered) scenario: load -> dispatch -> grade ->
    aggregate -> trace -> persist (guide §3.1 six phases).

    Parameters
    ----------
    scenarios_dir
        Scenario library directory (or list of directories); recursively
        globbed for ``*.yaml`` (phase 1, loader.py).  When a list is given,
        scenarios from each directory are concatenated in order.
    filters
        Optional scenario-name filter: a single name string or a list of
        names; None runs everything.
    env
        Optional explicit environment for the run.  It gates
        ``requires_env`` AND is what dispatched steps run with (dispatch
        passes it through; nothing is injected — D4).  When None, the
        parent ``os.environ`` is used for both.
    runs_dir
        Where persisted run directories live (phase 6).
    persist
        When True (default), persist the run record and refresh
        ``latest.txt`` before returning.
    run_meta
        Optional explicit run metadata dict.  When None, auto-collected
        from component versions and git SHAs.
    allow_fake
        The R-07 contract-only escape hatch.  When ``OMNI_TEST_FAKE_LLM=1``
        is active, a human-quality scenario is ``invalid`` regardless of
        this flag — ``True`` re-admits it only when EVERY step cites an
        AGENT-SURFACE anchor (anchor-less is ineligible).  A produced
        artifact carrying the fake echo signature is always invalid.
    step_timeout
        Optional explicit per-step wall-clock cap for ``cli``/``python``
        steps (the ``--step-timeout`` option, issue #176).  When None the
        dispatcher honours ``OMNI_VALIDATION_STEP_TIMEOUT_S`` from the
        effective *env*, else each step's own ``timeout_seconds``, else the
        120s default.  It only changes how long a step WAITS — never an
        assertion, threshold, known-gap or verdict.

    Returns
    -------
    RunResult
        The full run record: per-scenario verdict, per-step trace, env
        status, trace_id.  Exit-code mapping is the CLI's job (todo 9).

    Raises
    ------
    ScenarioError
        For the first malformed scenario file, before any step runs —
        load-time rejection is loud by design (loader.py, guide §2.4).
    """
    dirs: list[str | Path] = (
        [scenarios_dir]
        if isinstance(scenarios_dir, (str, Path))
        else list(scenarios_dir)
    )
    loaded: list[dict[str, Any]] = []
    for d in dirs:
        loaded.extend(load_scenarios(d))
    selected = _select(loaded, filters)
    trace_id = str(uuid.uuid4())  # one UUID per run, threaded everywhere
    results = [
        _run_one(s, env, trace_id, allow_fake, step_timeout) for s in selected
    ]
    run = RunResult(
        trace_id=trace_id,
        timestamp=datetime.datetime.now().isoformat(timespec="seconds"),
        scenarios=results,
    )
    if run_meta is not None:
        run.run_meta = run_meta
    else:
        try:
            repo_keys = _dirs_to_repo_keys(dirs)
            run.run_meta = collect_run_meta(repo_keys)
        except Exception:
            run.run_meta = {}
    if persist:
        persist_run(run, runs_dir)
    return run
