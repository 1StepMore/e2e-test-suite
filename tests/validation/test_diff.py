"""Tests for scripts/validation/validation_diff.py (plan todo 19).

The run-to-run diff compares two persisted runs (guide §5.4): per-scenario
verdict changes (passed-like -> failed = REGRESSION, exit 1; unconfigured
-> passed-like = improvement; new/missing scenarios) plus a coverage
delta from ``coverage.json`` when both runs carry one (todo 26 adds the
committed snapshot — until then the section is omitted gracefully with a
note).  It NEVER compares artifact contents, only verdicts + coverage
(plan todo 19: "Must NOT compare content of artifacts").

The one-argument form (``<newer>`` alone) anchors the previous run on
``validation-runs/latest.txt`` (plan adopted-default); when latest.txt
already names the passed run — the normal state right after a fresh run,
since the engine refreshes the pointer on every persist — the diff falls
back to the next-older run dir (what latest.txt would have named had the
new run not updated it).

RED-first discipline: every test drives ``compute_diff`` / ``main()``
with explicit tmp run dirs where a failure is simulated; no real
``validation-runs/`` state is touched.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SUITE_ROOT = Path(__file__).resolve().parent.parent.parent

_DIFF_PATH = SUITE_ROOT / "scripts" / "validation" / "validation_diff.py"


def _load_diff():
    """Import scripts/validation/validation_diff.py from its file path."""
    spec = importlib.util.spec_from_file_location("validation_diff", _DIFF_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["validation_diff"] = mod
    spec.loader.exec_module(mod)
    return mod


diff = _load_diff()


def _write_run(
    runs_dir: Path, ts: str, verdicts: dict[str, str], *, run_meta: dict | None = None
) -> Path:
    """A minimal persisted run: <runs_dir>/<ts>/scenarios.json with the
    engine's payload shape (run_id/timestamp/trace_id/scenarios[].status)."""
    d = runs_dir / ts
    d.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": ts,
        "timestamp": f"2026-08-14T{ts[-6:-4]}:{ts[-4:-2]}:{ts[-2:]}",
        "trace_id": f"trace-{ts}",
        "scenarios": [
            {
                "name": name,
                "status": status,
                "summary": f"{status} — test",
                "missing_env": [],
                "steps": [],
                "cleanup": [],
                "trace_id": f"trace-{ts}",
            }
            for name, status in verdicts.items()
        ],
    }
    if run_meta is not None:
        payload["run_meta"] = run_meta
    (d / "scenarios.json").write_text(json.dumps(payload), encoding="utf-8")
    return d


def _write_coverage(run_dir: Path, covered: dict[str, int], missing: list[str]) -> None:
    """A coverage.json of the shape todo 26's committed snapshot will use:
    per-module covered counts + a missing list."""
    (run_dir / "coverage.json").write_text(
        json.dumps({"covered": covered, "missing": missing}), encoding="utf-8"
    )


@pytest.fixture()
def runs(tmp_path: Path):
    """Two runs with identical verdicts (older < newer by dir name)."""
    older = _write_run(tmp_path, "20260814-100000", {"a": "passed", "b": "unconfigured"})
    newer = _write_run(tmp_path, "20260814-200000", {"a": "passed", "b": "unconfigured"})
    return tmp_path, older, newer


# ---------------------------------------------------------------------------
# Happy path — identical verdicts -> no regressions, exit 0 (plan QA)
# ---------------------------------------------------------------------------


def test_identical_runs_no_changes_exit_0(runs):
    """Happy: identical verdicts -> no verdict changes, no regressions,
    ``main`` exits 0."""
    tmp_path, older, newer = runs
    report = diff.compute_diff(diff.load_run(older), diff.load_run(newer))
    assert report.regressions == []
    assert report.changes == []
    out = diff.render(report)
    assert "no regressions" in out
    assert diff.main([str(older), str(newer)]) == 0


def test_identical_runs_absolute_paths_printed(runs):
    """The table names both runs (run_id + scenario counts)."""
    tmp_path, older, newer = runs
    out = diff.render(diff.compute_diff(diff.load_run(older), diff.load_run(newer)))
    assert "20260814-100000" in out and "20260814-200000" in out


# ---------------------------------------------------------------------------
# Failure path — passed -> failed is a REGRESSION, exit 1 (plan QA)
# ---------------------------------------------------------------------------


def test_passed_to_failed_is_regression_exit_1(runs):
    """Failure: one scenario flips passed->failed in the newer JSON ->
    REGRESSION row naming the scenario, ``main`` exits 1."""
    tmp_path, older, newer = runs
    payload = json.loads((newer / "scenarios.json").read_text(encoding="utf-8"))
    payload["scenarios"][0]["status"] = "failed"
    (newer / "scenarios.json").write_text(json.dumps(payload), encoding="utf-8")
    report = diff.compute_diff(diff.load_run(older), diff.load_run(newer))
    assert [c.name for c in report.regressions] == ["a"]
    out = diff.render(report)
    assert "REGRESSION" in out and "a" in out
    assert diff.main([str(older), str(newer)]) == 1


@pytest.mark.parametrize("old_status", ["recovered", "partial-pass"])
def test_recovered_and_partial_pass_to_failed_are_regressions(runs, old_status):
    """Verdict semantics (guide §3.3): ``recovered`` and ``partial-pass``
    are passed-like — their flip to ``failed`` is a regression too."""
    tmp_path, older, newer = runs
    payload = json.loads((older / "scenarios.json").read_text(encoding="utf-8"))
    payload["scenarios"][0]["status"] = old_status
    (older / "scenarios.json").write_text(json.dumps(payload), encoding="utf-8")
    payload = json.loads((newer / "scenarios.json").read_text(encoding="utf-8"))
    payload["scenarios"][0]["status"] = "failed"
    (newer / "scenarios.json").write_text(json.dumps(payload), encoding="utf-8")
    report = diff.compute_diff(diff.load_run(older), diff.load_run(newer))
    assert [c.name for c in report.regressions] == ["a"]


def test_failed_to_passed_is_not_a_regression(runs):
    """A fix (failed -> passed) is never a regression; exit stays 0."""
    tmp_path, older, newer = runs
    payload = json.loads((older / "scenarios.json").read_text(encoding="utf-8"))
    payload["scenarios"][0]["status"] = "failed"
    (older / "scenarios.json").write_text(json.dumps(payload), encoding="utf-8")
    assert diff.main([str(older), str(newer)]) == 0


# ---------------------------------------------------------------------------
# New / missing scenario detection (plan todo 19: both directions)
# ---------------------------------------------------------------------------


def test_new_scenario_in_newer_run_reported(runs):
    """A scenario present only in the newer run is listed as NEW."""
    tmp_path, older, newer = runs
    payload = json.loads((newer / "scenarios.json").read_text(encoding="utf-8"))
    payload["scenarios"].append(
        {"name": "c", "status": "passed", "summary": "passed — test",
         "missing_env": [], "steps": [], "cleanup": [], "trace_id": "t"}
    )
    (newer / "scenarios.json").write_text(json.dumps(payload), encoding="utf-8")
    report = diff.compute_diff(diff.load_run(older), diff.load_run(newer))
    kinds = {c.name: c.kind for c in report.changes}
    assert kinds == {"c": "new"}
    assert "c" in diff.render(report)


def test_missing_scenario_in_newer_run_reported(runs):
    """A scenario present only in the older run is listed as MISSING."""
    tmp_path, older, newer = runs
    payload = json.loads((older / "scenarios.json").read_text(encoding="utf-8"))
    payload["scenarios"].append(
        {"name": "c", "status": "passed", "summary": "passed — test",
         "missing_env": [], "steps": [], "cleanup": [], "trace_id": "t"}
    )
    (older / "scenarios.json").write_text(json.dumps(payload), encoding="utf-8")
    report = diff.compute_diff(diff.load_run(older), diff.load_run(newer))
    kinds = {c.name: c.kind for c in report.changes}
    assert kinds == {"c": "missing"}
    assert "c" in diff.render(report)


def test_unconfigured_to_passed_is_improvement(runs):
    """unconfigured -> passed is an improvement row (never a regression);
    exit stays 0."""
    tmp_path, older, newer = runs
    payload = json.loads((newer / "scenarios.json").read_text(encoding="utf-8"))
    payload["scenarios"][1]["status"] = "passed"
    (newer / "scenarios.json").write_text(json.dumps(payload), encoding="utf-8")
    report = diff.compute_diff(diff.load_run(older), diff.load_run(newer))
    kinds = {c.name: c.kind for c in report.changes}
    assert kinds == {"b": "improvement"}
    assert report.regressions == []
    assert diff.main([str(older), str(newer)]) == 0


def test_passed_to_unconfigured_is_other_change_not_regression(runs):
    """passed -> unconfigured is a non-regression change (unconfigured is
    never a failure, guide §4.2) — listed, but exit stays 0."""
    tmp_path, older, newer = runs
    payload = json.loads((newer / "scenarios.json").read_text(encoding="utf-8"))
    payload["scenarios"][0]["status"] = "unconfigured"
    (newer / "scenarios.json").write_text(json.dumps(payload), encoding="utf-8")
    report = diff.compute_diff(diff.load_run(older), diff.load_run(newer))
    assert {c.name: c.kind for c in report.changes} == {"a": "changed"}
    assert diff.main([str(older), str(newer)]) == 0


# ---------------------------------------------------------------------------
# Coverage delta — only when BOTH runs carry coverage.json (todo 26)
# ---------------------------------------------------------------------------


def test_coverage_delta_when_both_runs_carry_coverage_json(runs):
    """Both runs carry coverage.json -> the delta section shows the
    numeric deltas and the missing-tool membership change."""
    tmp_path, older, newer = runs
    _write_coverage(older, {"opp": 9, "ol": 21}, [])
    _write_coverage(newer, {"opp": 9, "ol": 20}, ["translate_file"])
    delta, note = diff.compute_coverage_delta(older, newer)
    assert delta is not None and delta["covered.ol"] == {"older": 21, "newer": 20, "delta": -1}
    assert delta["missing"]["added"] == ["translate_file"]
    out = diff.render(diff.compute_diff(diff.load_run(older), diff.load_run(newer)))
    assert "coverage" in out


def test_coverage_omitted_gracefully_when_absent(runs):
    """Neither run has coverage.json (the real state until todo 26) ->
    the section is omitted with a note, never an error."""
    tmp_path, older, newer = runs
    report = diff.compute_diff(diff.load_run(older), diff.load_run(newer))
    assert report.coverage_delta is None
    out = diff.render(report)
    assert "coverage" in out


# ---------------------------------------------------------------------------
# One-argument form — latest.txt as the previous-run anchor (adopted default)
# ---------------------------------------------------------------------------


def test_one_arg_uses_latest_txt_as_previous_anchor(tmp_path: Path):
    """``main([<newer>])`` anchors the previous run on latest.txt when it
    names a DIFFERENT run — the plan's adopted default."""
    older = _write_run(tmp_path, "20260814-100000", {"a": "passed"})
    newer = _write_run(tmp_path, "20260814-200000", {"a": "passed"})
    (tmp_path / "latest.txt").write_text(older.name, encoding="utf-8")
    assert diff.main([str(newer)]) == 0
    out = diff.render(
        diff.compute_diff(diff.load_run(older), diff.load_run(newer))
    )
    assert "20260814-100000" in out


def test_one_arg_latest_self_falls_back_to_next_older_run(tmp_path: Path):
    """When latest.txt already names the passed run (fresh-run state —
    the engine refreshes the pointer on every persist), the diff falls
    back to the next-older run instead of diffing a run against itself."""
    _write_run(tmp_path, "20260814-080000", {"a": "passed"})
    older = _write_run(tmp_path, "20260814-100000", {"a": "passed"})
    newer = _write_run(tmp_path, "20260814-200000", {"a": "passed"})
    (tmp_path / "latest.txt").write_text(newer.name, encoding="utf-8")
    assert diff.main([str(newer)]) == 0
    # the older anchor is the run the diff actually compared against
    out = diff.render(
        diff.compute_diff(diff.load_run(older), diff.load_run(newer))
    )
    assert "20260814-100000" in out


def test_one_arg_no_anchor_errors(tmp_path: Path):
    """latest.txt missing -> clear error, nonzero exit (pass both dirs)."""
    newer = _write_run(tmp_path, "20260814-200000", {"a": "passed"})
    assert diff.main([str(newer), "--runs-dir", str(tmp_path)]) != 0


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_missing_run_dir_errors(tmp_path: Path):
    """A nonexistent run dir -> clear error, nonzero exit."""
    assert diff.main([str(tmp_path / "nope"), str(tmp_path / "nope2")]) != 0


def test_bare_run_id_resolved_against_runs_dir(runs):
    """Bare run IDs (dir names) resolve against the runs dir — the
    AutoInfo-style invocation from the plan's acceptance criterion."""
    tmp_path, older, newer = runs
    assert diff.main([older.name, newer.name, "--runs-dir", str(tmp_path)]) == 0


def test_no_run_dir_argument_errors(tmp_path: Path):
    """No run dirs at all -> usage error, nonzero exit."""
    assert diff.main(["--runs-dir", str(tmp_path)]) != 0


# ---------------------------------------------------------------------------
# Four-class VERSION REGRESSION (OPP#58) — new/regressed/fixed/existing-failing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "old,new,expected",
    [
        (None, "passed", "new"),
        ("passed", None, "missing"),
        ("passed", "failed", "regressed"),
        ("failed", "passed", "fixed"),
        ("failed", "failed", "existing-failing"),
        ("passed", "passed", None),
        ("unconfigured", "passed", None),  # not one of the four classes
    ],
)
def test_classify_four_class(old, new, expected):
    """classify_four_class buckets a (old, new) verdict pair into the
    four-class scheme; unchanged pairs classify None."""
    assert diff.classify_four_class(old, new) == expected


def test_compute_four_class_missing_goes_to_missing_list(tmp_path: Path):
    """A scenario present only in the base run is NOT one of the four
    classes — render_version_regression lists it under missing-from-head."""
    base = _write_run(tmp_path, "20260814-100000", {"a": "passed", "gone": "passed"})
    head = _write_run(tmp_path, "20260814-200000", {"a": "passed"})
    base_rec = diff.load_run(base)
    head_rec = diff.load_run(head)
    text, exit_code = diff.render_version_regression(base_rec, head_rec, "test")
    assert exit_code == 0
    assert "missing-from-head (1)" in text
    assert "gone" in text


def _version_runs(tmp_path: Path, base_ver: str = "0.4.0", head_ver: str = "0.5.0"):
    """Three runs: a suite-versioned base, a component-versioned newer
    base, and a head — for --against-version base selection."""
    base_meta = {"suite_version": base_ver, "suite_sha": "abcd1234", "repos": ["suite"]}
    opp_meta = {"suite_version": "0.4.1", "opp": {"version": "0.9.0", "sha": "beef0001"}, "repos": ["opp"]}
    head_meta = {"suite_version": head_ver, "suite_sha": "deadbeef", "repos": ["suite"]}
    base = _write_run(tmp_path, "20260814-100000", {"a": "passed"}, run_meta=base_meta)
    opp = _write_run(tmp_path, "20260814-110000", {"a": "passed"}, run_meta=opp_meta)
    head = _write_run(tmp_path, "20260814-200000", {"a": "failed"}, run_meta=head_meta)
    return base, opp, head


def test_against_version_selects_newest_matching_base(tmp_path: Path):
    """find_base_by_version picks the NEWEST run older than the head whose
    run_meta any-string equals the version — a component version counts."""
    base, opp, head = _version_runs(tmp_path)
    assert diff.find_base_by_version(tmp_path, head, "0.4.1") == opp
    assert diff.find_base_by_version(tmp_path, head, "0.4.0") == base


def test_against_version_exit_1_on_regression(tmp_path: Path):
    """--against-version with a regressed head exits 1 (regressed > 0)."""
    base, _, head = _version_runs(tmp_path)
    assert diff.main(
        [str(head), "--against-version", "0.4.0", "--runs-dir", str(tmp_path)]
    ) == 1


def test_against_version_exit_1_on_existing_failing(tmp_path: Path):
    """A failed->failed scenario counts as existing-failing -> exit 1."""
    base = _write_run(
        tmp_path, "20260814-100000", {"a": "failed"},
        run_meta={"suite_version": "0.4.0", "repos": ["suite"]},
    )
    head = _write_run(
        tmp_path, "20260814-200000", {"a": "failed"},
        run_meta={"suite_version": "0.5.0", "repos": ["suite"]},
    )
    text, exit_code = diff.render_version_regression(
        diff.load_run(base), diff.load_run(head), "--against-version 0.4.0"
    )
    assert exit_code == 1
    assert "existing-failing" in text
    assert diff.main(
        [str(head), "--against-version", "0.4.0", "--runs-dir", str(tmp_path)]
    ) == 1


def test_against_version_no_match_exits_2(tmp_path: Path):
    """--against-version matching no older run -> FileNotFoundError,
    exit 2 (clear error)."""
    head = _write_run(
        tmp_path, "20260814-200000", {"a": "passed"},
        run_meta={"suite_version": "9.9.9", "repos": ["suite"]},
    )
    assert diff.main(
        [str(head), "--against-version", "0.4.0", "--runs-dir", str(tmp_path)]
    ) == 2


def test_base_sha_selects_by_sha_prefix(tmp_path: Path):
    """--base-sha matches any run_meta sha value by prefix — the newest
    older run whose suite/component sha startswith the given prefix."""
    base = _write_run(
        tmp_path, "20260814-100000", {"a": "passed"},
        run_meta={"suite_version": "0.4.0", "suite_sha": "abcd1234", "repos": ["suite"]},
    )
    newer = _write_run(
        tmp_path, "20260814-110000", {"a": "passed"},
        run_meta={"suite_version": "0.4.0", "suite_sha": "abcd5678", "repos": ["suite"]},
    )
    head = _write_run(
        tmp_path, "20260814-200000", {"a": "passed"},
        run_meta={"suite_version": "0.5.0", "suite_sha": "deadbeef", "repos": ["suite"]},
    )
    assert diff.find_base_by_sha(tmp_path, head, "abcd56") == newer
    assert diff.main(
        [str(head), "--base-sha", "abcd56", "--runs-dir", str(tmp_path)]
    ) == 0
