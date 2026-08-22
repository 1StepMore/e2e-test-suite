"""Tests for scripts/validation/artifact_diff.py (e2e-test-suite#44).

The artifact-assertion version diff compares two persisted
``artifact-report.json`` files (base = older run, head = newer run) and
classifies every per-artifact change:

- new              = present only in head
- regressed        = passed -> failed (drives exit 1)
- fixed            = failed -> passed
- existing-failing = failed -> failed (drives exit 1)
- missing          = present only in base (never one of the four classes,
                     reported separately as a note)

Exit codes from ``main``: 0 = no regressions / existing-failings; 1 =
any regressed OR existing-failing; 2 = input error (missing file /
unparseable JSON / not an artifact-report shape).

Hermetic: reports are synthetic dicts / tmp JSON files; the script is
loaded from its file path with importlib (scripts/ is not a package).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SUITE_ROOT = Path(__file__).resolve().parent.parent.parent

_SCRIPT_PATH = SUITE_ROOT / "scripts" / "validation" / "artifact_diff.py"

_FOUR_CLASSES = ("new", "regressed", "fixed", "existing-failing", "missing")


def _load_diff():
    """Import scripts/validation/artifact_diff.py from its file path."""
    spec = importlib.util.spec_from_file_location("artifact_diff", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["artifact_diff"] = mod
    spec.loader.exec_module(mod)
    return mod


adiff = _load_diff()


def _report(module: str, run_id: str, card: dict) -> dict:
    """A synthetic artifact-report dict in the shipped schema."""
    return {
        "matrix_type": "artifact",
        "module": module,
        "run_id": run_id,
        "timestamp": "2026-08-22T12:00:00",
        "report_card": card,
        "counts": {"artifacts": len(card), "assertions": 0, "passed": 0,
                   "failed": 0, "p0_failed": 0, "p1_failed": 0},
    }


def _card_entry(passed: bool, name: str = "x") -> dict:
    """A report-card entry with an explicit passed bool (the shipped shape)."""
    return {"passed": passed, "assertions": [
        {"name": name, "passed": passed, "issue": "e2e#44", "severity": "P0",
         "module": "suite", "artifact": "x", "detail": "clean" if passed else "polluted"},
    ]}


def _write_report(path: Path, report: dict) -> Path:
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# classify_artifact — the full truth table
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "old,new,expected",
    [
        (None, None, None),     # absent both runs -> not a change
        (None, True, "new"),
        (None, False, "new"),
        (True, None, "missing"),
        (False, None, "missing"),
        (True, False, "regressed"),
        (False, True, "fixed"),
        (False, False, "existing-failing"),
        (True, True, None),     # unchanged pass -> not a change
    ],
)
def test_classify_artifact_truth_table(old, new, expected):
    assert adiff.classify_artifact(old, new) == expected


# ---------------------------------------------------------------------------
# diff_artifact_reports — the four classes + missing
# ---------------------------------------------------------------------------


def test_diff_artifact_reports_all_classes(tmp_path):
    """A synthetic base/head pair producing all four classes plus missing;
    counts carry all 5 keys; changes sorted by the render order."""
    base = _report("suite", "base", {
        "gone.md": _card_entry(True),
        "regressed.md": _card_entry(True),
        "fixed.md": _card_entry(False),
        "existing.md": _card_entry(False),
    })
    head = _report("suite", "head", {
        "new.md": _card_entry(True),
        "regressed.md": _card_entry(False),
        "fixed.md": _card_entry(True),
        "existing.md": _card_entry(False),
    })

    diff = adiff.diff_artifact_reports(base, head)

    assert {c["kind"] for c in diff["changes"]} == {
        "new", "regressed", "fixed", "existing-failing", "missing"
    }
    assert {c["artifact"] for c in diff["changes"]} == {
        "gone.md", "regressed.md", "fixed.md", "existing.md", "new.md"
    }
    by_kind = {c["kind"]: c["artifact"] for c in diff["changes"]}
    assert by_kind["new"] == "new.md"
    assert by_kind["regressed"] == "regressed.md"
    assert by_kind["fixed"] == "fixed.md"
    assert by_kind["existing-failing"] == "existing.md"
    assert by_kind["missing"] == "gone.md"

    counts = diff["counts"]
    assert set(counts) == set(_FOUR_CLASSES)
    assert counts == {
        "new": 1, "regressed": 1, "fixed": 1, "existing-failing": 1, "missing": 1,
    }

    kinds = [c["kind"] for c in diff["changes"]]
    assert kinds == ["new", "regressed", "fixed", "existing-failing", "missing"]

    # failed-assertion names carried on regressed / existing-failing rows.
    regressed = next(c for c in diff["changes"] if c["kind"] == "regressed")
    assert regressed["new_failed_assertions"] == ["x"]
    assert regressed["old_failed_assertions"] == []


def test_diff_artifact_reports_sorts_regressed_before_existing(tmp_path):
    """Sorting is by (class order, artifact): 'zebras.md' (regressed) sorts
    before 'aardvark.md' (existing-failing)."""
    base = _report("suite", "base", {"zebras.md": _card_entry(True), "aardvark.md": _card_entry(False)})
    head = _report("suite", "head", {"zebras.md": _card_entry(False), "aardvark.md": _card_entry(False)})

    diff = adiff.diff_artifact_reports(base, head)

    assert [c["kind"] for c in diff["changes"]] == ["regressed", "existing-failing"]
    assert [c["artifact"] for c in diff["changes"]] == ["zebras.md", "aardvark.md"]


def test_diff_artifact_reports_identical_cards_no_changes(tmp_path):
    """Two identical cards -> no changes and a 'no changes' note."""
    base = _report("suite", "base", {"a.md": _card_entry(True)})
    head = _report("suite", "head", {"a.md": _card_entry(True)})

    diff = adiff.diff_artifact_reports(base, head)

    assert diff["changes"] == []
    assert diff["counts"] == {cls: 0 for cls in _FOUR_CLASSES}
    assert diff["note"] == "no changes — report cards identical"


def test_diff_artifact_reports_module_mismatch_presence_only(tmp_path):
    """A module mismatch (base opp, head orf) -> note set; every head
    artifact classified new, every base artifact missing (presence-only —
    no false regressions, even for artifacts present in BOTH runs)."""
    base = _report("opp", "base", {
        "shared.md": _card_entry(True),
        "opp_only.md": _card_entry(True),
    })
    head = _report("orf", "head", {
        "shared.md": _card_entry(False),  # NOT a regression across modules
        "orf_only.md": _card_entry(False),
    })

    diff = adiff.diff_artifact_reports(base, head)

    assert "module mismatch" in (diff["note"] or "")
    assert "base='opp'" in diff["note"]
    by_kind = {c["artifact"]: c["kind"] for c in diff["changes"]}
    assert by_kind["shared.md"] == "missing"  # present in base -> missing
    assert by_kind["opp_only.md"] == "missing"
    assert by_kind["orf_only.md"] == "new"
    assert diff["counts"] == {
        "new": 1, "regressed": 0, "fixed": 0, "existing-failing": 0, "missing": 2,
    }


# ---------------------------------------------------------------------------
# main() — exit codes
# ---------------------------------------------------------------------------


def test_main_regressed_and_existing_exit_1(tmp_path):
    """regressed + existing-failing present -> exit 1."""
    base = _write_report(tmp_path / "base.json", _report("suite", "base", {
        "reg.md": _card_entry(True), "exist.md": _card_entry(False),
    }))
    head = _write_report(tmp_path / "head.json", _report("suite", "head", {
        "reg.md": _card_entry(False), "exist.md": _card_entry(False),
    }))
    assert adiff.main([str(base), str(head)]) == 1


def test_main_new_fixed_missing_only_exit_0(tmp_path):
    """Only new/fixed/missing present (no regressions, no existing-failings)
    -> exit 0."""
    base = _write_report(tmp_path / "base.json", _report("suite", "base", {
        "fixed.md": _card_entry(False), "gone.md": _card_entry(True),
    }))
    head = _write_report(tmp_path / "head.json", _report("suite", "head", {
        "fixed.md": _card_entry(True), "new.md": _card_entry(True),
    }))
    assert adiff.main([str(base), str(head)]) == 0


def test_main_identical_exit_0(tmp_path):
    """Identical reports -> exit 0."""
    base = _write_report(tmp_path / "base.json", _report("suite", "base", {"a.md": _card_entry(True)}))
    head = _write_report(tmp_path / "head.json", _report("suite", "head", {"a.md": _card_entry(True)}))
    assert adiff.main([str(base), str(head)]) == 0


def test_main_missing_file_exit_2(tmp_path):
    """A nonexistent input file -> exit 2."""
    base = _write_report(tmp_path / "base.json", _report("suite", "base", {}))
    rc = adiff.main([str(base), str(tmp_path / "nope.json")])
    assert rc == 2


def test_main_unparseable_json_exit_2(tmp_path):
    """An input that is not valid JSON -> exit 2."""
    base = _write_report(tmp_path / "base.json", _report("suite", "base", {}))
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json", encoding="utf-8")
    assert adiff.main([str(base), str(bad)]) == 2


def test_main_not_an_artifact_report_exit_2(tmp_path):
    """An input that parses but is not an artifact-report shape -> exit 2."""
    base = _write_report(tmp_path / "base.json", _report("suite", "base", {}))
    wrong = tmp_path / "wrong.json"
    wrong.write_text('{"hello": "world"}', encoding="utf-8")
    assert adiff.main([str(base), str(wrong)]) == 2
