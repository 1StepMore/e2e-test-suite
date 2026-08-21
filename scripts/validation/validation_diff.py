#!/usr/bin/env python3
"""Run-to-run diff: verdict changes + regression detection (plan todo 19).

Compare two persisted validation runs (guide §5.4) and report what
changed: per-scenario verdict changes plus a coverage delta.  Verdicts
only — NEVER artifact contents (plan todo 19 "Must NOT compare content
of artifacts"), and never a full report (summary table only).

Run from the repo root:

    source .venv_ol/bin/activate
    python scripts/validation/validation_diff.py validation-runs/<older> validation-runs/<newer>

One-argument form (adopted default from the draft decision ledger):

    python scripts/validation/validation_diff.py validation-runs/<newer>

anchors the previous run on ``validation-runs/latest.txt``.  Because the
engine refreshes the pointer on every persist, latest.txt usually names
the run being passed itself right after a fresh run; in that case the
diff falls back to the next-older run dir — exactly what latest.txt
would have named had the new run not updated it.

Verdict-change classification (engine verdicts: passed | failed |
unconfigured | recovered | partial-pass, omni_mcp/validation/engine.py):

- REGRESSION  = passed-like -> failed.  Passed-like is ``passed``,
  ``recovered`` (passed for verdict purposes, guide §3.3) and
  ``partial-pass`` (its min_passing/pass_ratio bar was met).  ANY
  regression makes the exit code 1.
- improvement = unconfigured -> passed-like (env got configured).
- new         = scenario present only in the newer run.
- missing     = scenario present only in the older run.
- changed     = any other verdict change (e.g. passed -> unconfigured:
  never a failure per guide §4.2, so never a regression).

Four-class VERSION REGRESSION mode (OPP#58): ``--against-version
VERSION`` or ``--base-sha SHA`` selects the base run by its ``run_meta``
(suite/component version or git sha; run-id/timestamp prefix counts for
the version selector) and classifies every scenario into
``new`` / ``regressed`` / ``fixed`` / ``existing-failing``:

- new             = scenario present only in the newer (head) run.
- regressed       = passed-like -> failed.
- fixed           = failed -> passed-like.
- existing-failing = failed -> failed.

``missing`` (present only in the base) is reported separately as a
``missing-from-head`` note — never one of the four classes.  Exit code
contract: 1 when ``regressed > 0`` OR ``existing-failing > 0``, else 0.
The two selectors are mutually exclusive (exit 2 when both given), and
each picks the NEWEST matching run OLDER than the head (exit 2 when
none).

Coverage delta: read from ``<run>/coverage.json`` when the run carries
one (todo 26 commits the snapshot; the engine persists only
``scenarios.json`` today).  Compared only when BOTH runs carry it,
otherwise the section is omitted gracefully with a note.

Exit codes: 0 = no regressions; 1 = at least one REGRESSION; 2 = usage
or input error (missing run, unreadable record, no previous anchor).

Only Python 3.13 stdlib (guide §3.6) — no new dependencies.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

#: Suite root: this module lives at <root>/scripts/validation/validation_diff.py.
SUITE_ROOT = Path(__file__).resolve().parent.parent.parent

#: Default run-records directory (same convention as the engine's
#: ``persist_run`` and the CLI's ``--runs-dir``).
RUNS_DIR = SUITE_ROOT / "validation-runs"

#: Verdicts that count as "passed-like" for regression detection (guide
#: §3.3: ``recovered`` is passed for verdict purposes; ``partial-pass``
#: met its min_passing/pass_ratio bar).
_PASS_LIKE = frozenset({"passed", "recovered", "partial-pass"})

#: Verdict-change kinds, in render order.
_KINDS = ("REGRESSION", "improvement", "new", "missing", "changed")


@dataclasses.dataclass(frozen=True)
class RunRecord:
    """The verdict half of a persisted run (scenarios.json)."""

    run_id: str
    timestamp: str
    #: scenario name -> verdict (passed | failed | unconfigured |
    #: recovered | partial-pass).
    verdicts: dict[str, str]
    #: The persisted ``run_meta`` block (suite/component versions + git
    #: SHAs + the ``repos`` list) — the four-class version-regression
    #: base selector matches against it.
    run_meta: dict[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def totals(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for status in self.verdicts.values():
            counts[status] = counts.get(status, 0) + 1
        return counts


@dataclasses.dataclass(frozen=True)
class VerdictChange:
    """One per-scenario verdict change between the two runs."""

    name: str
    #: ``REGRESSION`` | ``improvement`` | ``new`` | ``missing`` | ``changed``.
    kind: str
    #: Older-run verdict; None for a ``new`` scenario.
    old: str | None
    #: Newer-run verdict; None for a ``missing`` scenario.
    new: str | None


@dataclasses.dataclass
class RunDiff:
    """Everything the diff derives: changes, regressions, coverage."""

    base: RunRecord
    head: RunRecord
    #: All verdict changes, ordered REGRESSION -> improvement -> new ->
    #: missing -> changed (stable by scenario name within a kind).
    changes: list[VerdictChange]
    #: The REGRESSION subset (drives the exit code).
    regressions: list[VerdictChange]
    #: Coverage delta dict when BOTH runs carry coverage.json, else None.
    coverage_delta: dict[str, Any] | None
    #: Human note for the coverage section when it cannot be computed.
    coverage_note: str

    @property
    def by_kind(self) -> dict[str, list[VerdictChange]]:
        grouped: dict[str, list[VerdictChange]] = {k: [] for k in _KINDS}
        for change in self.changes:
            grouped[change.kind].append(change)
        return grouped


# ---------------------------------------------------------------------------
# Loading — the persisted run schema (omni_mcp/validation/engine.py)
# ---------------------------------------------------------------------------


def load_run(run_dir: Path) -> RunRecord:
    """Read a persisted run: ``<run_dir>/scenarios.json`` payload
    ``{run_id, timestamp, trace_id, scenarios: [{name, status, ...}]}``."""
    record = Path(run_dir) / "scenarios.json"
    if not record.is_file():
        raise FileNotFoundError(
            f"not a validation run: {Path(run_dir)} (no scenarios.json)"
        )
    try:
        payload = json.loads(record.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"unreadable run record {record}: {exc}") from exc
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list):
        raise ValueError(f"run record {record} has no scenarios list")
    verdicts: dict[str, str] = {}
    for entry in scenarios:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise ValueError(f"malformed scenario entry in {record}: {entry!r}")
        verdicts[entry["name"]] = str(entry.get("status") or "unknown")
    run_meta = payload.get("run_meta")
    if not isinstance(run_meta, dict):
        run_meta = {}
    return RunRecord(
        run_id=str(payload.get("run_id") or Path(run_dir).name),
        timestamp=str(payload.get("timestamp") or ""),
        verdicts=verdicts,
        run_meta=run_meta,
    )


def load_coverage(run_dir: Path) -> dict[str, Any] | None:
    """``<run_dir>/coverage.json`` when the run carries one, else None.

    The engine persists only ``scenarios.json``; the committed coverage
    snapshot arrives in todo 26.  Shape is deliberately unspecified here
    — the delta section only needs two comparable dicts.
    """
    file = Path(run_dir) / "coverage.json"
    if not file.is_file():
        return None
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"unreadable coverage file {file}: {exc}") from exc
    return data if isinstance(data, dict) else {"_raw": data}


def resolve_run_dir(arg: str, runs_dir: Path) -> Path:
    """Resolve a run argument: an existing dir as given, else a bare run
    ID joined with *runs_dir* (AutoInfo-style ``20260814-200733``)."""
    as_given = Path(arg)
    if as_given.is_dir():
        return as_given
    joined = Path(runs_dir) / arg
    if joined.is_dir():
        return joined
    raise FileNotFoundError(
        f"unknown run {arg!r} — not a directory under {Path(runs_dir)} "
        "(available runs: "
        + ", ".join(sorted(p.name for p in Path(runs_dir).iterdir() if p.is_dir()))
        + ")"
    )


def latest_anchor(runs_dir: Path) -> Path:
    """The run dir named by ``<runs_dir>/latest.txt`` (engine persist
    pointer; adopted default as the previous-run anchor)."""
    pointer = Path(runs_dir) / "latest.txt"
    if not pointer.is_file():
        raise FileNotFoundError(
            f"no previous-run anchor: {pointer} missing — pass both run "
            "dirs explicitly"
        )
    name = pointer.read_text(encoding="utf-8").strip()
    if not name:
        raise FileNotFoundError(f"empty previous-run anchor: {pointer}")
    anchor = Path(runs_dir) / name
    if not anchor.is_dir():
        raise FileNotFoundError(
            f"previous-run anchor {pointer} names {name!r}, but no such "
            "run dir exists"
        )
    return anchor


def next_older_run(runs_dir: Path, head: Path) -> Path:
    """The run dir immediately older than *head* by name (the run
    latest.txt would have named had the new run not refreshed it)."""
    head_name = Path(head).name
    older = sorted(
        p for p in Path(runs_dir).iterdir() if p.is_dir() and p.name < head_name
    )
    if not older:
        raise FileNotFoundError(
            f"no run older than {head_name!r} to diff against — pass both "
            "run dirs explicitly"
        )
    return older[-1]


# ---------------------------------------------------------------------------
# The diff
# ---------------------------------------------------------------------------


def _classify(old: str | None, new: str | None) -> str | None:
    """The verdict-change kind for one scenario; None when unchanged."""
    if old == new:
        return None
    if old is None:
        return "new"
    if new is None:
        return "missing"
    if old in _PASS_LIKE and new == "failed":
        return "REGRESSION"
    if old == "unconfigured" and new in _PASS_LIKE:
        return "improvement"
    return "changed"


def classify_four_class(old: str | None, new: str | None) -> str | None:
    """The four-class VERSION REGRESSION class for one scenario.

    ``new`` when the scenario only exists in the head run; ``missing``
    (reported separately, never a class) when only in the base;
    ``regressed`` passed-like -> failed; ``fixed`` failed -> passed-like;
    ``existing-failing`` failed -> failed; else None.
    """
    if old is None:
        return "new"
    if new is None:
        return "missing"
    if old in _PASS_LIKE and new == "failed":
        return "regressed"
    if old == "failed" and new in _PASS_LIKE:
        return "fixed"
    if old == "failed" and new == "failed":
        return "existing-failing"
    return None


#: The four classes, in render order.
_FOUR_CLASSES = ("new", "regressed", "fixed", "existing-failing")


def _run_meta_strings(run: RunRecord) -> list[str]:
    """Every string value in the run's ``run_meta`` (suite/component
    versions, shas, ``repos`` entries)."""
    values: list[str] = []
    for value in run.run_meta.values():
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, dict):
            for v in value.values():
                if isinstance(v, str):
                    values.append(v)
    return values


def _run_meta_shas(run: RunRecord) -> list[str]:
    """The sha values in the run's ``run_meta`` (``suite_sha`` and each
    component's ``sha``)."""
    shas: list[str] = []
    for key, value in run.run_meta.items():
        if key == "suite_sha" and isinstance(value, str):
            shas.append(value)
        elif isinstance(value, dict):
            for k, v in value.items():
                if k == "sha" and isinstance(v, str):
                    shas.append(v)
    return shas


def find_base_by_version(runs_dir: Path, head_dir: Path, version: str) -> Path:
    """The NEWEST run dir under *runs_dir* strictly OLDER than *head_dir*
    whose ``run_meta`` ANY string value equals *version* (a component
    version, the suite version), OR whose run_id/timestamp startswith
    *version*.

    Raises FileNotFoundError with a clear message when no run matches.
    """
    head_name = Path(head_dir).name
    candidates = sorted(
        p for p in Path(runs_dir).iterdir()
        if p.is_dir() and p.name < head_name and p != Path(head_dir)
    )
    for candidate in reversed(candidates):
        try:
            run = load_run(candidate)
        except (FileNotFoundError, ValueError):
            continue
        if (
            version in _run_meta_strings(run)
            or run.run_id.startswith(version)
            or run.timestamp.startswith(version)
        ):
            return candidate
    raise FileNotFoundError(
        f"no run older than {head_name!r} matches --against-version "
        f"{version!r} (no run_meta value equals it, no run_id/timestamp prefix)"
    )


def find_base_by_sha(runs_dir: Path, head_dir: Path, sha: str) -> Path:
    """The NEWEST run dir strictly OLDER than *head_dir* whose ``run_meta``
    ANY sha value startswith *sha*.

    Raises FileNotFoundError with a clear message when no run matches.
    """
    head_name = Path(head_dir).name
    candidates = sorted(
        p for p in Path(runs_dir).iterdir()
        if p.is_dir() and p.name < head_name and p != Path(head_dir)
    )
    for candidate in reversed(candidates):
        try:
            run = load_run(candidate)
        except (FileNotFoundError, ValueError):
            continue
        if any(v.startswith(sha) for v in _run_meta_shas(run)):
            return candidate
    raise FileNotFoundError(
        f"no run older than {head_name!r} matches --base-sha {sha!r}"
    )


def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten nested dicts to dotted key paths (todo 26's snapshot will
    nest per-module sections, e.g. ``covered.ol``)."""
    flat: dict[str, Any] = {}
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(_flatten(value, path))
        else:
            flat[path] = value
    return flat


def compute_coverage_delta(
    base: Path, head: Path
) -> tuple[dict[str, Any] | None, str]:
    """Coverage delta when BOTH runs carry ``coverage.json``.

    Numeric values diff arithmetically; list values diff by membership
    (added / removed).  Keys present in only one side are reported as
    such, never silently dropped.
    """
    base_cov = load_coverage(base)
    head_cov = load_coverage(head)
    if base_cov is None and head_cov is None:
        return None, (
            "coverage delta skipped — neither run carries coverage.json "
            "(todo 26 adds the committed snapshot; the engine persists "
            "only scenarios.json)"
        )
    if base_cov is None:
        return None, f"coverage delta skipped — older run has no coverage.json ({Path(base).name})"
    if head_cov is None:
        return None, f"coverage delta skipped — newer run has no coverage.json ({Path(head).name})"

    base_flat = _flatten(base_cov)
    head_flat = _flatten(head_cov)
    delta: dict[str, Any] = {}
    for key in sorted(set(base_flat) | set(head_flat)):
        b, h = base_flat.get(key), head_flat.get(key)
        if isinstance(b, (int, float)) and isinstance(h, (int, float)):
            delta[key] = {"older": b, "newer": h, "delta": h - b}
        elif isinstance(b, list) and isinstance(h, list):
            bs, hs = set(b), set(h)
            added = sorted(hs - bs)
            removed = sorted(bs - hs)
            if added or removed:
                delta[key] = {"added": added, "removed": removed}
        elif b != h:
            delta[key] = {"older": b, "newer": h}
    return (delta if delta else {}), "coverage.json present in both runs"


def compute_diff(base: RunRecord, head: RunRecord) -> RunDiff:
    """Per-scenario verdict changes + regressions (guide §5.4)."""
    names = sorted(set(base.verdicts) | set(head.verdicts))
    changes: list[VerdictChange] = []
    for name in names:
        old = base.verdicts.get(name)
        new = head.verdicts.get(name)
        kind = _classify(old, new)
        if kind is not None:
            changes.append(VerdictChange(name=name, kind=kind, old=old, new=new))
    changes.sort(key=lambda c: (_KINDS.index(c.kind), c.name))
    regressions = [c for c in changes if c.kind == "REGRESSION"]
    return RunDiff(
        base=base,
        head=head,
        changes=changes,
        regressions=regressions,
        coverage_delta=None,
        coverage_note="",
    )


# ---------------------------------------------------------------------------
# Render — summary table only (never a full report)
# ---------------------------------------------------------------------------


def _run_line(record: RunRecord) -> str:
    totals = record.totals
    parts = ", ".join(f"{totals.get(s, 0)} {s}" for s in ("passed", "failed", "unconfigured"))
    return f"  {record.run_id}  ({len(record.verdicts)} scenario(s): {parts})"


def _coverage_line(delta: dict[str, Any] | None, note: str) -> str:
    if delta is None:
        return f"  coverage delta: {note}"
    lines = ["  coverage delta (both runs carry coverage.json):"]
    if not delta:
        lines.append("    identical coverage — no delta")
    for key, change in sorted(delta.items()):
        if "delta" in change:
            lines.append(f"    {key}: {change['older']} -> {change['newer']} "
                         f"({change['delta']:+d})")
        elif "added" in change:
            lines.append(
                f"    {key}: removed {change['removed'] or '(none)'}, "
                f"added {change['added'] or '(none)'}"
            )
        else:
            lines.append(f"    {key}: {change['older']!r} -> {change['newer']!r}")
    return "\n".join(lines)


def render(diff_result: RunDiff, base_note: str = "", head_note: str = "") -> str:
    """The verdict-change table + coverage section (summary only)."""
    lines: list[str] = []
    lines.append("Run diff — base -> head (guide §5.4)")
    lines.append(_run_line(diff_result.base))
    lines.append(_run_line(diff_result.head))
    if base_note:
        lines.append(f"  base note: {base_note}")
    if head_note:
        lines.append(f"  head note: {head_note}")
    lines.append("")
    lines.append("VERDICT CHANGES:")
    if not diff_result.changes:
        lines.append("  none — verdicts identical across runs")
    else:
        lines.append(f"  {'scenario':<36} {'older':<14} {'newer':<14} change")
        for change in diff_result.changes:
            lines.append(
                f"  {change.name:<36} {str(change.old or '-'):<14} "
                f"{str(change.new or '-'):<14} {change.kind}"
            )
    lines.append("")
    grouped = diff_result.by_kind
    for kind in _KINDS:
        rows = grouped[kind]
        if kind == "REGRESSION":
            label = f"REGRESSIONS ({len(rows)}) — passed-like -> failed:"
        elif kind == "improvement":
            label = f"IMPROVEMENTS ({len(rows)}) — unconfigured -> passed-like:"
        else:
            label = f"{kind.capitalize()} scenarios ({len(rows)}):"
        lines.append(label + (" none" if not rows else ""))
        for change in rows:
            lines.append(f"    {change.name}: {change.old or '-'} -> {change.new or '-'}")
    lines.append("")
    lines.append(_coverage_line(diff_result.coverage_delta, diff_result.coverage_note))
    lines.append("")
    if diff_result.regressions:
        lines.append(
            f"VERDICT: {len(diff_result.regressions)} regression(s) -> FAIL (exit 1)"
        )
    else:
        lines.append("VERDICT: no regressions -> PASS (exit 0)")
    return "\n".join(lines)


def _run_version(run: RunRecord) -> str:
    """A short ``repo=version`` summary of the run's run_meta for the
    four-class header (base/head versions from run_meta)."""
    parts: list[str] = []
    if run.run_meta:
        for key in ("suite", *sorted(run.run_meta.get("repos") or [])):
            if key == "suite":
                version = run.run_meta.get("suite_version")
                if version:
                    parts.append(f"suite={version}")
            else:
                entry = run.run_meta.get(key)
                if isinstance(entry, dict) and entry.get("version"):
                    parts.append(f"{key}={entry['version']}")
    return ", ".join(parts) if parts else "(no run_meta versions)"


def render_version_regression(
    base: RunRecord, head: RunRecord, selector: str
) -> tuple[str, int]:
    """The four-class VERSION REGRESSION section.

    Returns ``(text, exit_code)`` — exit 1 when ``regressed > 0`` OR
    ``existing-failing > 0``, else 0.  ``selector`` names the base-selection
    rule for the header (e.g. ``against-version 0.4.0``).
    """
    classes: dict[str, list[tuple[str, str | None, str | None]]] = {
        c: [] for c in _FOUR_CLASSES
    }
    missing_from_head: list[str] = []
    for name in sorted(set(base.verdicts) | set(head.verdicts)):
        old = base.verdicts.get(name)
        new = head.verdicts.get(name)
        cls = classify_four_class(old, new)
        if cls == "missing":
            missing_from_head.append(name)
        elif cls is not None:
            classes[cls].append((name, old, new))

    lines: list[str] = []
    lines.append("VERSION REGRESSION (four-class) — base -> head")
    lines.append(f"  base:  {base.run_id}  ({_run_version(base)})")
    lines.append(f"  head:  {head.run_id}  ({_run_version(head)})")
    lines.append(f"  base selection: {selector}")
    lines.append("")
    lines.append("  class                          count")
    lines.append("  ------------------------------  -----")
    for cls in _FOUR_CLASSES:
        rows = classes[cls]
        lines.append(f"  {cls:<30} {len(rows)}")
        for name, old, new in rows:
            lines.append(f"    {name}: {old or '-'} -> {new or '-'} ({cls})")
    lines.append("")
    if missing_from_head:
        lines.append(
            f"  missing-from-head ({len(missing_from_head)}) — present in the base "
            "run only (not one of the four classes):"
        )
        for name in missing_from_head:
            lines.append(f"    {name}")
    lines.append("")
    regressed = len(classes["regressed"])
    existing_failing = len(classes["existing-failing"])
    if regressed or existing_failing:
        lines.append(
            f"VERDICT: {regressed} regressed, {existing_failing} existing-failing "
            "-> FAIL (exit 1)"
        )
    else:
        lines.append("VERDICT: no regressions, no existing-failings -> PASS (exit 0)")
    lines.append("")
    return "\n".join(lines), 1 if (regressed or existing_failing) else 0


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry: print the diff; exit 1 on any REGRESSION, 2 on input
    errors.  ``main`` is a pure function (argv -> exit code) so tests
    drive it in-process."""
    parser = argparse.ArgumentParser(
        prog="validation_diff.py",
        description=(
            "Diff two validation runs: per-scenario verdict changes + "
            "regression detection (guide §5.4). With <newer> alone the "
            "previous run anchors on validation-runs/latest.txt."
        ),
    )
    parser.add_argument(
        "older", metavar="OLDER-RUN", nargs="?",
        help="the older run dir (or bare run id under validation-runs/)",
    )
    parser.add_argument(
        "newer", metavar="NEWER-RUN", nargs="?",
        help="the newer run dir (default with a single positional: that "
        "positional IS the newer run, anchored on latest.txt)",
    )
    parser.add_argument(
        "--runs-dir", type=Path, default=RUNS_DIR,
        help="run records directory (default: <repo>/validation-runs)",
    )
    parser.add_argument(
        "--against-version", metavar="VERSION", default=None,
        help="four-class VERSION REGRESSION mode: select the base run by "
        "run_meta version / run-id prefix (mutually exclusive with --base-sha)",
    )
    parser.add_argument(
        "--base-sha", metavar="SHA", default=None,
        help="four-class VERSION REGRESSION mode: select the base run by a "
        "run_meta sha prefix (mutually exclusive with --against-version)",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # --help (0) / usage error (2): keep main() pure
        return exc.code if isinstance(exc.code, int) else 0
    # Positional contract (plan acceptance): `validation_diff.py <older>
    # <newer>`; a SINGLE positional is the NEWER run, anchored on the
    # latest.txt previous-run pointer.
    if args.older is None and args.newer is None:
        print("ERROR: pass at least one run dir (validation_diff.py <older> <newer>)",
              file=sys.stderr)
        return 2
    if args.newer is None:
        args.newer, args.older = args.older, None
    if args.against_version is not None and args.base_sha is not None:
        print("ERROR: --against-version and --base-sha are mutually exclusive "
              "(pass one base selector)", file=sys.stderr)
        return 2

    runs_dir = args.runs_dir
    try:
        head_dir = resolve_run_dir(args.newer, runs_dir)
        base_note = ""
        selector = ""
        if args.against_version is not None:
            base_dir = find_base_by_version(runs_dir, head_dir, args.against_version)
            base_note = f"base selected by --against-version {args.against_version}"
            selector = f"--against-version {args.against_version}"
        elif args.base_sha is not None:
            base_dir = find_base_by_sha(runs_dir, head_dir, args.base_sha)
            base_note = f"base selected by --base-sha {args.base_sha}"
            selector = f"--base-sha {args.base_sha}"
        elif args.older is None:
            anchor = latest_anchor(runs_dir)
            if anchor.resolve() == head_dir.resolve():
                base_dir = next_older_run(runs_dir, head_dir)
                base_note = (
                    f"latest.txt names {head_dir.name} itself (fresh-run "
                    "state) — using next-older run"
                )
            else:
                base_dir = anchor
                base_note = "previous-run anchor from latest.txt"
        else:
            base_dir = resolve_run_dir(args.older, runs_dir)
        base = load_run(base_dir)
        head = load_run(head_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if selector:
        text, exit_code = render_version_regression(base, head, selector)
        print(text)
        return exit_code

    result = compute_diff(base, head)
    result.coverage_delta, result.coverage_note = compute_coverage_delta(base_dir, head_dir)
    print(render(result, base_note=base_note))
    return 1 if result.regressions else 0


if __name__ == "__main__":
    raise SystemExit(main())
