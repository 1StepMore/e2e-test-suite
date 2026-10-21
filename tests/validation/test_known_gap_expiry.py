"""Issue #206 — known_gap waivers must expire, cannot cover a whole
scenario, and report closure when the waived bar starts passing.
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

from omni_mcp.validation.cli import lint_scenarios
from omni_mcp.validation.engine import _aggregate, run_scenarios


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def _env() -> dict[str, str]:
    return {"PATH": os.environ.get("PATH", "")}


def _record(passed: bool, known_gap: bool) -> dict[str, object]:
    return {
        "name": "step",
        "passed": passed,
        "known_gap": known_gap,
        "status": "passed" if passed else "failed",
    }


def test_all_waived_and_failing_is_never_passed():
    records = [_record(False, True), _record(False, True)]

    assert _aggregate({}, records) == "invalid"


def test_one_non_waived_failure_still_fails():
    records = [_record(False, True), _record(False, False)]

    assert _aggregate({}, records) == "failed"


def test_waived_failure_beside_a_pass_is_passed():
    records = [_record(False, True), _record(True, False)]

    assert _aggregate({}, records) == "passed"


def test_waiver_without_recheck_by_is_a_lint_finding(tmp_path):
    _write(
        tmp_path,
        "no-date.yaml",
        """
        name: plain-sample
        description: "waiver without an expiry"
        level: agent-user
        steps:
          - name: "waived"
            kind: cli
            command: "true"
            known_gap: true
            expect:
              exit_code: 0
          - name: "graded"
            kind: cli
            command: "true"
            expect:
              exit_code: 0
        """,
    )

    findings = lint_scenarios(tmp_path)

    assert [f.rule for f in findings] == ["known-gap-recheck"]


def test_past_recheck_by_is_a_lint_finding(tmp_path):
    _write(
        tmp_path,
        "expired.yaml",
        """
        name: plain-sample
        description: "expired waiver"
        level: agent-user
        steps:
          - name: "waived"
            kind: cli
            command: "true"
            known_gap: true
            recheck_by: "2026-01-01"
            expect:
              exit_code: 0
          - name: "graded"
            kind: cli
            command: "true"
            expect:
              exit_code: 0
        """,
    )

    findings = lint_scenarios(tmp_path)

    assert [f.rule for f in findings] == ["known-gap-recheck"]
    assert "has passed" in findings[0].detail


def test_future_recheck_by_is_clean(tmp_path):
    _write(
        tmp_path,
        "ok.yaml",
        """
        name: plain-sample
        description: "live waiver"
        level: agent-user
        steps:
          - name: "waived"
            kind: cli
            command: "true"
            known_gap: true
            recheck_by: "2099-12-31"
            expect:
              exit_code: 0
          - name: "graded"
            kind: cli
            command: "true"
            expect:
              exit_code: 0
        """,
    )

    assert lint_scenarios(tmp_path) == []


def test_waiving_every_step_is_a_lint_finding(tmp_path):
    _write(
        tmp_path,
        "all-waived.yaml",
        """
        name: plain-sample
        description: "the waiver covers the whole verdict"
        level: agent-user
        steps:
          - name: "waived"
            kind: cli
            command: "true"
            known_gap: true
            recheck_by: "2099-12-31"
            expect:
              exit_code: 0
        """,
    )

    findings = lint_scenarios(tmp_path)

    assert [f.rule for f in findings] == ["known-gap-coverage"]


def test_passing_waived_step_reports_gap_closed(tmp_path):
    _write(
        tmp_path,
        "closed.yaml",
        """
        name: plain-sample
        description: "the waived bar now passes"
        level: agent-user
        steps:
          - name: "waived bar"
            kind: cli
            command: "true"
            known_gap: true
            recheck_by: "2099-12-31"
            expect:
              exit_code: 0
          - name: "graded"
            kind: cli
            command: "true"
            expect:
              exit_code: 0
        """,
    )

    result = run_scenarios(tmp_path, env=_env(), persist=False).scenarios[0]

    assert result.status == "passed"
    assert result.gap_closed == ["waived bar"]
    assert "GAP CLOSED" in result.summary
