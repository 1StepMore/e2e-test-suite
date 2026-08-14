"""grader.py — phase 3 of the validation engine: expect grading
(guide §3.1 phase 3 assert, §3.3 ``evaluate_expect``).

The grader is the assertion layer of a step: it grades the step's
``expect`` block against the ``actual`` dict the dispatch phase captured
(the ``StepResult.actual`` field contract — dispatch.py docstring:
``success`` bool plus surface-shaped keys ``exit_code`` / ``stdout`` /
``stderr`` for cli+python, ``data`` for mcp, ``status_code`` for
HTTP-shaped tools, ``timeout``/``error`` on failure).

Every check type grades independently and every check must hold for the
step to pass (guide §2.3: "All assertions in a block are conjoined").
Grading is deliberately generic — booleans, exact int compares, and
substring containment only (guide §3.3), plus a regex form and a
JSONPath-ish dot-path form:

- ``success: true|false``       — boolean compare against ``actual["success"]``
- ``exit_code: N``              — exact int compare against ``actual["exit_code"]``
- ``status_code: N``            — exact int compare against ``actual["status_code"]``
- ``stdout_has`` / ``stderr_has`` — string (substring), list of strings
                                   (all must be present), or ``{"re": "regex"}``
                                   (search match); ``stdout_not_has`` /
                                   ``stderr_not_has`` for negative assertions
- ``data_has: [...]``           — substrings that must all appear in the
                                   JSON-serialized ``actual["data"]``
- ``json_has``                  — JSONPath-ish dot path (e.g.
                                   ``data.translation.text``) resolving to a
                                   truthy value, or ``{"path": "a.b",
                                   "value": X}`` asserting equality

Falsifiable discipline (mirrors AutoInfo contract lint,
``run-validation-scenarios.py:506-537``): an empty / None / non-dict
``expect`` block fails with "step must be falsifiable" — the grader never
auto-passes an ungraded step.  Unknown expect keys fail their check with a
clear message instead of being ignored (typo protection).

The grader is pure logic: no I/O, no dispatch — the engine (todo 8)
composes it with the adapters.  It also never prints PASS/FAIL itself
(no self-echo; the run record carries verdicts).

Only Python 3.13 stdlib — no new dependencies (guide §3.6).
"""

from __future__ import annotations

import dataclasses
import json
import re
from typing import Any

#: The closed set of expect keys the grader understands (guide §2.3
#: assertion table, with the plan-todo-7 adopted forms: substring-or-regex
#: stdout/stderr assertions, negative variants, and dot-path json_has).
_KNOWN_KEYS = frozenset(
    {
        "success",
        "data_has",
        "exit_code",
        "stdout_has",
        "stderr_has",
        "stdout_not_has",
        "stderr_not_has",
        "status_code",
        "json_has",
    }
)


@dataclasses.dataclass
class CheckResult:
    """One graded assertion inside an expect block.

    ``expected`` echoes the expect value as declared; ``actual`` is the
    observed value the check compared against (the captured stdout /
    stderr / data JSON / resolved json path / raw actual value), so the
    run record can show "checked X against standard Y -> actual Z" (D12).
    ``message`` is the human-readable detail when the check failed
    (empty on pass) — it feeds the overall ``GradeResult.reason``.
    """

    #: The expect key this check graded (e.g. ``exit_code``).
    name: str
    #: Whether this single assertion held.
    passed: bool
    #: The declared assertion value.
    expected: Any
    #: The observed value (None when the actual dict lacked the key).
    actual: Any
    #: Human-readable failure detail ("" on pass), e.g.
    #: ``"expected 0, actual 1"``.
    message: str = ""


@dataclasses.dataclass
class GradeResult:
    """The verdict of grading one step's expect block.

    ``passed`` is true only when EVERY check passed AND the expect block
    was a non-empty dict (falsifiable).  ``reason`` is the human-readable
    summary, e.g. ``"check 'exit_code': expected 0, actual 1"``.
    """

    #: Overall verdict: every check passed on a non-empty expect block.
    passed: bool
    #: Per-check grades, in expect-key order (empty for non-falsifiable
    #: blocks — the whole block is rejected, nothing is graded).
    checks: list[CheckResult]
    #: Human-readable summary for the run record / director report.
    reason: str


def _fail(
    name: str, message: str, expected: Any = None, actual: Any = None
) -> CheckResult:
    """A failing check with a human-readable detail (``#error-clarity``)."""
    return CheckResult(
        name=name, passed=False, expected=expected, actual=actual, message=message
    )


def _pass(name: str, expected: Any, actual: Any) -> CheckResult:
    return CheckResult(name=name, passed=True, expected=expected, actual=actual)


def _is_int(value: Any) -> bool:
    """True for an int that is not a bool (bool is an int subclass; a YAML
    ``exit_code: true`` would silently mean 1 — reject it)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _resolve_path(container: Any, path: str) -> Any:
    """Resolve a dot path (``a.b.c``) against *container*.

    Returns the resolved value, or None when the path cannot be walked
    (missing key / non-dict intermediate / empty path segment).  Dict
    traversal only — dispatch payloads are dict-shaped.
    """
    if not path:
        return None
    current = container
    for segment in path.split("."):
        if segment == "" or not isinstance(current, dict):
            return None
        if segment not in current:
            return None
        current = current[segment]
    return current


def _json_dump(data: Any) -> str:
    """JSON-serialized form of a payload for substring checks (the guide's
    ``json.dumps(output.get("data", ""))`` containment, §3.3)."""
    try:
        return json.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError):
        return repr(data)


def _check_success(expected: Any, actual: dict[str, Any]) -> CheckResult:
    if not isinstance(expected, bool):
        return _fail(
            "success",
            f"expected a boolean (true/false), got {type(expected).__name__}",
            expected=expected,
            actual=actual.get("success"),
        )
    observed = actual.get("success")
    if observed != expected:
        return _fail(
            "success", f"expected {expected}, actual {observed}",
            expected=expected, actual=observed,
        )
    return _pass("success", expected, observed)


def _check_int_compare(key: str, expected: Any, observed: Any) -> CheckResult:
    if not _is_int(expected):
        return _fail(
            key,
            f"expected an integer, got {type(expected).__name__}",
            expected=expected, actual=observed,
        )
    if observed != expected:
        return _fail(
            key, f"expected {expected}, actual {observed}",
            expected=expected, actual=observed,
        )
    return _pass(key, expected, observed)


def _check_exit_code(expected: Any, actual: dict[str, Any]) -> CheckResult:
    return _check_int_compare("exit_code", expected, actual.get("exit_code"))


def _check_status_code(expected: Any, actual: dict[str, Any]) -> CheckResult:
    return _check_int_compare("status_code", expected, actual.get("status_code"))


def _collect_strings(value: Any) -> list[str] | None:
    """Normalize a substring-check value into a list of strings.

    Accepts a plain string (single substring) or a list of strings (all
    must be present).  Returns None when the form is unsupported — the
    caller then emits a failing check naming the form.
    """
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(entry, str) for entry in value):
        return value
    return None


def _check_text_has(
    key: str, value: Any, text: str, stream: str
) -> CheckResult:
    """Grade one stdout/stderr assertion (positive form).

    *text* is the observed stream content (already defaulted to ""), the
    *stream* name for messages.  Handles string / list-of-strings /
    ``{"re": "regex"}`` forms.
    """
    if isinstance(value, dict):
        pattern = value.get("re")
        if isinstance(pattern, str):
            try:
                matches = re.search(pattern, text) is not None
            except re.error as exc:
                return _fail(
                    key, f"invalid regex {pattern!r}: {exc}",
                    expected=value, actual=text,
                )
            if not matches:
                return _fail(
                    key, f"expected {stream} to match regex {pattern!r}, no match",
                    expected=value, actual=text,
                )
            return _pass(key, value, text)
        return _fail(
            key,
            f"unsupported form for {stream} assertion — use a string, a "
            f"list of strings, or {{'re': 'regex'}}, got {value!r}",
            expected=value, actual=text,
        )

    needles = _collect_strings(value)
    if needles is None:
        return _fail(
            key,
            f"unsupported form for {stream} assertion — expected a string "
            f"or a list of strings, got {value!r}",
            expected=value, actual=text,
        )
    for needle in needles:
        if needle not in text:
            return _fail(
                key, f"expected {needle!r} in {stream}, not found",
                expected=value, actual=text,
            )
    return _pass(key, value, text)


def _check_text_not_has(
    key: str, value: Any, text: str, stream: str
) -> CheckResult:
    """Grade a negative stdout/stderr assertion (``*_not_has``)."""
    needles = _collect_strings(value)
    if needles is None:
        return _fail(
            key,
            f"unsupported form for {stream} assertion — expected a string "
            f"or a list of strings, got {value!r}",
            expected=value, actual=text,
        )
    for needle in needles:
        if needle in text:
            return _fail(
                key, f"expected {needle!r} NOT in {stream}, but it was found",
                expected=value, actual=text,
            )
    return _pass(key, value, text)


def _check_data_has(expected: Any, actual: dict[str, Any]) -> CheckResult:
    needles = _collect_strings(expected)
    if needles is None:
        return _fail(
            "data_has",
            f"expected a string or a list of strings, got {expected!r}",
            expected=expected, actual=actual.get("data"),
        )
    dump = _json_dump(actual.get("data"))
    for needle in needles:
        if needle not in dump:
            return _fail(
                "data_has", f"expected {needle!r} in data JSON, not found",
                expected=expected, actual=dump,
            )
    return _pass("data_has", expected, dump)


def _check_json_has(expected: Any, actual: dict[str, Any]) -> CheckResult:
    """Grade the json_has assertion: a dot path resolving to a truthy
    value, or ``{"path": "a.b", "value": X}`` asserting equality."""
    paths: list[tuple[str, Any | None]] = []  # (path, expected_value|None)

    def add(path: str, value: Any | None) -> None:
        paths.append((path, value))

    if isinstance(expected, str):
        add(expected, None)
    elif isinstance(expected, list):
        for entry in expected:
            if isinstance(entry, str):
                add(entry, None)
            elif isinstance(entry, dict) and isinstance(entry.get("path"), str):
                add(entry["path"], entry.get("value"))
            else:
                return _fail(
                    "json_has",
                    "unsupported entry in json_has list — expected path "
                    f"strings or {{'path': ..., 'value': ...}} dicts, got {entry!r}",
                    expected=expected, actual=None,
                )
    elif isinstance(expected, dict):
        unknown = set(expected) - {"path", "value"}
        if unknown or not isinstance(expected.get("path"), str):
            return _fail(
                "json_has",
                f"unsupported form — expected {{'path': 'a.b', 'value': X}}, got {expected!r}",
                expected=expected, actual=None,
            )
        add(expected["path"], expected.get("value"))
    else:
        return _fail(
            "json_has",
            "unsupported form — expected a dot path string or "
            f"{{'path': 'a.b', 'value': X}}, got {expected!r}",
            expected=expected, actual=None,
        )

    for path, wanted in paths:
        resolved = _resolve_path(actual, path)
        if wanted is None:
            if not resolved:
                return _fail(
                    "json_has",
                    f"json path {path!r} did not resolve to a truthy value",
                    expected=expected, actual=resolved,
                )
        elif resolved != wanted:
            return _fail(
                "json_has",
                f"json path {path!r}: expected {wanted!r}, actual {resolved!r}",
                expected=expected, actual=resolved,
            )
    return _pass("json_has", expected, [p for p, _ in paths])


def grade_step(step_expect: Any, actual: dict[str, Any]) -> GradeResult:
    """Grade one step's expect block against the dispatch-captured actual.

    Parameters
    ----------
    step_expect
        The step's ``expect`` block (loader.py guarantees a non-empty dict
        at load time; this function re-checks so the grader itself can
        never auto-pass an ungraded step — defense in depth).
    actual
        The ``StepResult.actual`` dict from dispatch: ``success`` plus
        surface-shaped keys (``exit_code`` / ``stdout`` / ``stderr`` for
        cli+python, ``data`` for mcp, ``status_code`` for HTTP-shaped
        tools, ``timeout`` / ``error`` on failure).

    Returns
    -------
    GradeResult
        ``passed`` true only when every check passed AND the expect block
        was non-empty.  Per-check grades carry the observed values;
        ``reason`` is human-readable, e.g. ``"check 'exit_code': expected
        0, actual 1"``.
    """
    if not isinstance(step_expect, dict) or not step_expect:
        # Not falsifiable — mirrors AutoInfo contract lint
        # ("missing expected block (must be falsifiable)").
        return GradeResult(passed=False, checks=[], reason="step must be falsifiable")

    if not isinstance(actual, dict):
        actual = {}

    checks: list[CheckResult] = []
    for key, expected in step_expect.items():
        if key not in _KNOWN_KEYS:
            checks.append(
                _fail(
                    key,
                    f"unknown expect key {key!r} (typo?) — known keys: "
                    f"{', '.join(sorted(_KNOWN_KEYS))}",
                    expected=expected, actual=None,
                )
            )
            continue
        stdout = str(actual.get("stdout") or "")
        stderr = str(actual.get("stderr") or "")
        if key == "success":
            checks.append(_check_success(expected, actual))
        elif key == "exit_code":
            checks.append(_check_exit_code(expected, actual))
        elif key == "status_code":
            checks.append(_check_status_code(expected, actual))
        elif key == "stdout_has":
            checks.append(_check_text_has(key, expected, stdout, "stdout"))
        elif key == "stderr_has":
            checks.append(_check_text_has(key, expected, stderr, "stderr"))
        elif key == "stdout_not_has":
            checks.append(_check_text_not_has(key, expected, stdout, "stdout"))
        elif key == "stderr_not_has":
            checks.append(_check_text_not_has(key, expected, stderr, "stderr"))
        elif key == "data_has":
            checks.append(_check_data_has(expected, actual))
        elif key == "json_has":
            checks.append(_check_json_has(expected, actual))

    failing = [c for c in checks if not c.passed]
    if failing:
        reason = "; ".join(f"check {c.name!r}: {c.message}" for c in failing)
        return GradeResult(passed=False, checks=checks, reason=reason)

    n = len(checks)
    reason = f"all {n} check{'s' if n != 1 else ''} passed"
    return GradeResult(passed=True, checks=checks, reason=reason)
