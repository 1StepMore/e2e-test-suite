#!/usr/bin/env python3
"""Artifact-assertion version diff: four-class regression across runs
(e2e-test-suite#44, AutoInfo #340 semantics).

Compare two persisted ``artifact-report.json`` files (produced by the
artifact matrix — ``artifact_matrix.py``) and classify the per-artifact
change between the base (older) run and the head (newer) run:

- new              = artifact present only in the head run.
- regressed        = passed -> failed (a P0/P1 bar that used to hold now
  fails — ANY regression makes the exit code 1).
- fixed            = failed -> passed.
- existing-failing = failed -> failed (still failing, not new).
- missing          = artifact present only in the base run — reported
  separately as a note, NEVER one of the four classes.

Classification is artifact-level, driven by the report card's
``passed`` bool per artifact.  Failed-assertion names are carried along
for ``regressed`` / ``existing-failing`` rows so a human can see WHICH
assertion flipped or is still red.

Run from the repo root:

    source .venv_ol/bin/activate
    python scripts/validation/artifact_diff.py \
        validation-runs/<older>/artifact-report.json \
        validation-runs/<newer>/artifact-report.json

Exit codes: 0 = no regressions, no existing-failings; 1 = at least one
``regressed`` OR ``existing-failing``; 2 = usage or input error (missing
file, unparseable JSON, not an artifact-report shape).

Only Python 3.13 stdlib — no new dependencies.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

#: Four-class render order (missing is reported separately, never a class).
_FOUR_CLASSES = ("new", "regressed", "fixed", "existing-failing")


@dataclasses.dataclass(frozen=True)
class ArtifactChange:
    """One per-artifact change between the two artifact reports."""

    artifact: str
    #: ``new`` | ``regressed`` | ``fixed`` | ``existing-failing`` | ``missing``.
    kind: str
    #: Base-run passed state; None when the artifact was absent from base.
    old_passed: bool | None
    #: Head-run passed state; None when the artifact is absent from head.
    new_passed: bool | None
    #: Assertion names that failed in the base run (artifact-level; [] when
    #: the artifact was absent from base or passed there).
    old_failed_assertions: list[str]
    #: Assertion names that failed in the head run ([] when absent/passed).
    new_failed_assertions: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Plain-dict form for JSON persistence."""
        return {
            "artifact": self.artifact,
            "kind": self.kind,
            "old_passed": self.old_passed,
            "new_passed": self.new_passed,
            "old_failed_assertions": self.old_failed_assertions,
            "new_failed_assertions": self.new_failed_assertions,
        }


def _artifact_passed(card_entry: Any) -> bool:
    """The passed state of a report-card entry.

    Tolerates both the current shape (entry has an explicit ``passed``
    bool) and the derived shape (only ``assertions`` present) — in the
    latter case passed == every assertion passed.
    """
    if isinstance(card_entry, dict):
        if "passed" in card_entry and isinstance(card_entry["passed"], bool):
            return card_entry["passed"]
        assertions = card_entry.get("assertions")
        if isinstance(assertions, list):
            if not assertions:
                return True
            return all(
                isinstance(a, dict) and a.get("passed", False) is True
                for a in assertions
            )
    return False


def _failed_assertions(card_entry: Any) -> list[str]:
    """Names of the assertions that failed for an artifact ([] when none).

    An assertion is a dict with ``name`` and ``passed``; anything without
    a name is reported positionally (e.g. ``#0``) so it is never silently
    dropped.
    """
    if not isinstance(card_entry, dict):
        return []
    assertions = card_entry.get("assertions")
    if not isinstance(assertions, list):
        return []
    failed: list[str] = []
    for index, assertion in enumerate(assertions):
        if not isinstance(assertion, dict):
            continue
        if assertion.get("passed") is False:
            name = assertion.get("name")
            failed.append(str(name) if name else f"#{index}")
    return failed


def classify_artifact(old_passed: bool | None, new_passed: bool | None) -> str | None:
    """Four-class + missing for one artifact.

    ``None -> None`` => None (unchanged/absent both runs); ``None ->
    bool`` => ``new``; ``bool -> None`` => ``missing``; ``True ->
    False`` => ``regressed``; ``False -> True`` => ``fixed``;
    ``False -> False`` => ``existing-failing``; ``True -> True`` =>
    None.
    """
    if old_passed is None and new_passed is None:
        return None
    if old_passed is None:
        return "new"
    if new_passed is None:
        return "missing"
    if old_passed and not new_passed:
        return "regressed"
    if not old_passed and new_passed:
        return "fixed"
    if not old_passed and not new_passed:
        return "existing-failing"
    return None


# ---------------------------------------------------------------------------
# Loading — the artifact-report JSON schema (artifact_matrix.py)
# ---------------------------------------------------------------------------


def _meta(report: dict[str, Any]) -> dict[str, str]:
    """The identifying metadata of an artifact report (for headers)."""
    module = report.get("module")
    return {
        "run_id": str(report.get("run_id") or "(unknown run)"),
        "module": str(module) if module else "(unknown module)",
        "timestamp": str(report.get("timestamp") or ""),
    }


def _report_card(report: dict[str, Any]) -> dict[str, Any]:
    """The report card of an artifact report, validated.

    Raises ValueError (mapped to exit 2 in main) when the shape is not an
    artifact-report: a ``matrix_type == "artifact"`` marker, and a dict
    card when present.
    """
    if not isinstance(report, dict):
        raise ValueError("not an artifact-report JSON (expected an object)")
    if report.get("matrix_type") != "artifact":
        raise ValueError(
            "not an artifact-report JSON (missing matrix_type == 'artifact')"
        )
    card = report.get("report_card")
    if card is None:
        return {}
    if not isinstance(card, dict):
        raise ValueError(
            "not an artifact-report JSON (report_card must be an object, "
            f"got {type(card).__name__})"
        )
    return card


def load_artifact_report(path: Path) -> dict[str, Any]:
    """Read and validate an ``artifact-report.json`` file."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except json.JSONDecodeError as exc:
        raise ValueError(f"unparseable artifact report {path}: {exc}") from exc
    # _report_card validates the top-level object + card shape.
    _report_card(payload)
    return payload


# ---------------------------------------------------------------------------
# The diff
# ---------------------------------------------------------------------------


def _module_mismatch(base: dict[str, Any], head: dict[str, Any]) -> str | None:
    """Non-empty note when the two reports differ in module.

    On a mismatch every head artifact is treated as ``new`` and every
    base-only artifact as ``missing`` (diffing across modules would
    otherwise report false regressions for artifacts that simply moved
    between modules).
    """
    base_module = str(base.get("module") or "(unknown module)")
    head_module = str(head.get("module") or "(unknown module)")
    if base_module != head_module:
        return (
            f"module mismatch: base={base_module!r}, head={head_module!r} — "
            "artifacts are NOT comparable across modules; every head-only "
            "artifact counted as new, every base-only artifact as missing"
        )
    return None


def diff_artifact_reports(base: dict[str, Any], head: dict[str, Any]) -> dict[str, Any]:
    """Compare two artifact-report JSON dicts (same module expected).

    Returns::

        {
          "base": {"run_id", "module", "timestamp"},
          "head": {"run_id", "module", "timestamp"},
          "changes": [ArtifactChange.to_dict() ...] sorted
                     (regressed, existing-failing, fixed, new, missing)
                     then artifact name,
          "counts": {"regressed": N, "existing-failing": N, "fixed": N,
                     "new": N, "missing": N},
          "note": ""   # e.g. module mismatch / no changes
        }

    On a module mismatch, every head artifact is classified ``new`` and
    every base-only artifact ``missing`` (regression/fix/existing-failing
    are meaningless across modules); the note records the mismatch.
    """
    base_card = _report_card(base)
    head_card = _report_card(head)
    note = _module_mismatch(base, head)

    changes: list[ArtifactChange] = []
    # All artifacts of both runs, in one name space.
    for artifact in sorted(set(base_card) | set(head_card)):
        base_entry = base_card.get(artifact)
        head_entry = head_card.get(artifact)
        old_passed = _artifact_passed(base_entry) if artifact in base_card else None
        new_passed = _artifact_passed(head_entry) if artifact in head_card else None
        # Module mismatch: only presence classes are meaningful.
        if note:
            kind = "new" if old_passed is None else "missing"
        else:
            kind = classify_artifact(old_passed, new_passed)
        if kind is None:
            continue
        changes.append(
            ArtifactChange(
                artifact=artifact,
                kind=kind,
                old_passed=old_passed,
                new_passed=new_passed,
                old_failed_assertions=(
                    _failed_assertions(base_entry) if artifact in base_card else []
                ),
                new_failed_assertions=(
                    _failed_assertions(head_entry) if artifact in head_card else []
                ),
            )
        )

    # Render order: the four classes, then "missing" (never a class).
    _SORT_KINDS = (*_FOUR_CLASSES, "missing")
    changes.sort(key=lambda c: (_SORT_KINDS.index(c.kind), c.artifact))
    counts = {cls: 0 for cls in _SORT_KINDS}
    for change in changes:
        counts[change.kind] = counts.get(change.kind, 0) + 1

    if not changes and not note:
        note = "no changes — report cards identical"
    return {
        "base": _meta(base),
        "head": _meta(head),
        "changes": [change.to_dict() for change in changes],
        "counts": counts,
        "note": note,
    }


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def _report_line(label: str, meta: dict[str, str]) -> str:
    stamp = f"  @ {meta['timestamp']}" if meta["timestamp"] else ""
    return (
        f"  {label}: {meta['module']} run {meta['run_id']}{stamp}"
    )


def render(diff_result: dict[str, Any]) -> str:
    """The artifact-diff summary (per-artifact lines + four-class counts)."""
    lines: list[str] = []
    lines.append("Artifact-assertion diff (four-class) — base -> head")
    lines.append(_report_line("base", diff_result["base"]))
    lines.append(_report_line("head", diff_result["head"]))
    if diff_result["note"]:
        lines.append(f"  note: {diff_result['note']}")
    lines.append("")
    if not diff_result["changes"]:
        lines.append("CHANGES: none — artifact report cards identical")
    else:
        lines.append("CHANGES:")
        for change in diff_result["changes"]:
            old = str(change["old_passed"]) if change["old_passed"] is not None else "-"
            new = str(change["new_passed"]) if change["new_passed"] is not None else "-"
            lines.append(
                f"  {change['artifact']}: {old} -> {new} ({change['kind']})"
            )
            if change["kind"] in ("regressed", "existing-failing"):
                failing = change["new_failed_assertions"]
                if failing:
                    lines.append(f"      failing assertions: {', '.join(failing)}")
    lines.append("")
    lines.append("  class              count")
    lines.append("  -----------------  -----")
    for cls in _FOUR_CLASSES:
        lines.append(f"  {cls:<17} {diff_result['counts'].get(cls, 0)}")
    lines.append("")
    missing = diff_result["counts"].get("missing", 0)
    if missing:
        lines.append(
            f"  NOTE: {missing} artifact(s) missing from the head run — "
            "missing is NOT one of the four classes, does not affect the "
            "exit code"
        )
    lines.append("")
    regressed = diff_result["counts"].get("regressed", 0)
    existing_failing = diff_result["counts"].get("existing-failing", 0)
    if regressed or existing_failing:
        lines.append(
            f"VERDICT: {regressed} regressed, {existing_failing} "
            "existing-failing -> FAIL (exit 1)"
        )
    else:
        lines.append(
            "VERDICT: no regressions, no existing-failings -> PASS (exit 0)"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry: print the artifact diff; exit 1 on any regression or
    existing-failing, 2 on input errors.  ``main`` is a pure function
    (argv -> exit code) so tests drive it in-process."""
    parser = argparse.ArgumentParser(
        prog="artifact_diff.py",
        description=(
            "Artifact-assertion version diff: compare two artifact-report "
            "JSON files (base < head) and classify every artifact into "
            "new / regressed / fixed / existing-failing (+ a missing "
            "note). Exit 1 when regressed > 0 OR existing-failing > 0."
        ),
    )
    parser.add_argument(
        "base",
        metavar="BASE-ARTIFACT-REPORT.json",
        help="the older run's artifact-report.json",
    )
    parser.add_argument(
        "head",
        metavar="HEAD-ARTIFACT-REPORT.json",
        help="the newer run's artifact-report.json",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # --help (0) / usage error (2): keep main() pure
        return exc.code if isinstance(exc.code, int) else 0
    try:
        base_report = load_artifact_report(Path(args.base))
        head_report = load_artifact_report(Path(args.head))
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    diff_result = diff_artifact_reports(base_report, head_report)
    print(render(diff_result))
    counts = diff_result["counts"]
    return 1 if (counts["regressed"] > 0 or counts["existing-failing"] > 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
