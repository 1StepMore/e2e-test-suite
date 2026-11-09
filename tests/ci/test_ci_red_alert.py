"""Unit tests for scripts/ci_red_alert.py decision core (suite#274/#275).

The gh-bound plumbing is excluded; these pin the pure decisions: title
dedupe, 24h throttle + same-run idempotence, environment-red classification,
and the evidence-gated auto-close (labels / merged PR / green run).
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ci_red_alert.py"
_spec = importlib.util.spec_from_file_location("ci_red_alert", _SCRIPT)
ci_red_alert = importlib.util.module_from_spec(_spec)
sys.modules["ci_red_alert"] = ci_red_alert
_spec.loader.exec_module(ci_red_alert)

NOW = datetime(2026, 11, 10, 1, 0, 0, tzinfo=UTC)


def _ts(delta_minutes: float) -> str:
    return (NOW - timedelta(minutes=delta_minutes)).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# dedupe
# ---------------------------------------------------------------------------

def test_red_title_is_the_dedup_key():
    assert ci_red_alert.red_title("fidelity", "main") == "[CI红] fidelity @ main"


def test_pick_open_issue_matches_exact_title_and_skips_prs():
    issues = [
        {"number": 1, "title": "[CI红] fidelity @ main", "pull_request": {"url": "x"}},
        {"number": 2, "title": "[CI红] fidelity @ main"},
        {"number": 3, "title": "[CI红] Validation Framework @ main"},
        {"number": 4, "title": "[CI红] fidelity @ some-branch"},
    ]
    picked = ci_red_alert.pick_open_issue(issues, "fidelity", "main")
    assert picked is not None and picked["number"] == 2


def test_pick_open_issue_returns_none_when_absent():
    assert ci_red_alert.pick_open_issue([{"number": 9, "title": "unrelated"}], "fidelity", "main") is None


# ---------------------------------------------------------------------------
# 24h throttle + same-run idempotence
# ---------------------------------------------------------------------------

def _bot_comment(minutes_ago: float, body: str) -> dict:
    return {"id": 100, "body": body, "created_at": _ts(minutes_ago)}


MARKER = ci_red_alert.ALERT_MARKER


def test_same_run_recorded_once():
    comments = [_bot_comment(30, f"{MARKER}\n- run `42` — job x — url\n")]
    action, cid, reason = ci_red_alert.throttle_decision(comments, 42, NOW)
    assert action == "skip" and cid == 100 and "already recorded" in reason


def test_within_24h_merges_into_existing_comment():
    comments = [_bot_comment(3 * 60, f"{MARKER}\n- run `41` — job x — url\n")]
    action, cid, _ = ci_red_alert.throttle_decision(comments, 42, NOW)
    assert action == "edit" and cid == 100


def test_after_24h_posts_new_comment():
    comments = [_bot_comment(25 * 60, f"{MARKER}\n- run `41` — job x — url\n")]
    action, cid, _ = ci_red_alert.throttle_decision(comments, 42, NOW)
    assert action == "comment" and cid is None


def test_human_comments_do_not_count_toward_throttle():
    comments = [{"id": 7, "body": "looks bad, investigating", "created_at": _ts(10)}]
    action, _, _ = ci_red_alert.throttle_decision(comments, 42, NOW)
    assert action == "comment"


def test_append_run_id_extends_body():
    body = f"{MARKER}\n- run `41` — job x — url\n"
    out = ci_red_alert.append_run_id(body, 42, "http://run/42", "job y")
    assert "run `41`" in out and "run `42`" in out and out.count(MARKER) == 1


# ---------------------------------------------------------------------------
# environment-red classification
# ---------------------------------------------------------------------------

def test_classify_environment_red_on_401_token():
    kind, sigs = ci_red_alert.classify_failure("...Error: 401 Invalid bearer token...")
    assert kind == "environment" and any("bearer" in s for s in sigs)


def test_classify_environment_red_on_throttle_and_unconfigured():
    kind, sigs = ci_red_alert.classify_failure("RATE_LIMITED: Rate limit exceeded.")
    assert kind == "environment"
    kind2, _ = ci_red_alert.classify_failure("MCPNotConfiguredError: MCP_ALLOWED_DIRECTORIES")
    assert kind2 == "environment"


def test_classify_code_red_is_the_default():
    kind, sigs = ci_red_alert.classify_failure("AssertionError: expected 3 paragraphs\nFAILED tests/x.py::test_y")
    assert kind == "code" and sigs == []


def test_classify_ignores_401_inside_larger_numbers():
    kind, _ = ci_red_alert.classify_failure("row 14013 mismatch")
    assert kind == "code"


# ---------------------------------------------------------------------------
# auto-close gate
# ---------------------------------------------------------------------------

def _issue(number=10, labels=None, created_minutes_ago=60 * 24 * 3):
    return {
        "number": number,
        "title": "[CI红] fidelity @ main",
        "labels": [{"name": lab} for lab in (labels or [])],
        "created_at": _ts(created_minutes_ago),
    }


def _pr(number, merged_minutes_ago, body):
    return {"number": number, "merged_at": _ts(merged_minutes_ago), "body": body}


GREEN = {"id": 500, "created_at": _ts(30)}


def test_autoclose_happy_path():
    ok, reason = ci_red_alert.close_decision(
        _issue(), [], [_pr(283, 60, "Closes #10 — the fix")], GREEN
    )
    assert ok and "#283" in reason and "500" in reason


def test_autoclose_never_with_protected_labels():
    for label in sorted(ci_red_alert.NEVER_AUTOCLOSE_LABELS):
        ok, reason = ci_red_alert.close_decision(
            _issue(labels=[label]), [], [_pr(283, 60, "Closes #10")], GREEN
        )
        assert not ok and label in reason


def test_autoclose_blocked_without_merged_pr():
    ok, reason = ci_red_alert.close_decision(_issue(), [], [], GREEN)
    assert not ok and "(a)" in reason


def test_autoclose_blocked_when_pr_merged_before_issue():
    ok, reason = ci_red_alert.close_decision(
        _issue(created_minutes_ago=10), [], [_pr(283, 60, "Closes #10")], GREEN
    )
    assert not ok and "(a)" in reason


def test_autoclose_blocked_when_green_run_predates_issue():
    old_green = {"id": 1, "created_at": _ts(60 * 24 * 10)}
    ok, reason = ci_red_alert.close_decision(
        _issue(), [], [_pr(283, 60, "fixes #10")], old_green
    )
    assert not ok and "(b)" in reason


def test_autoclose_requires_close_keyword_not_plain_mention():
    ok, _ = ci_red_alert.close_decision(
        _issue(), [], [_pr(283, 60, "related to #10, not closing")], GREEN
    )
    assert not ok


def test_autoclose_ignores_wrong_issue_number():
    ok, _ = ci_red_alert.close_decision(
        _issue(), [], [_pr(283, 60, "Closes #999")], GREEN
    )
    assert not ok


# ---------------------------------------------------------------------------
# issue body contract
# ---------------------------------------------------------------------------

def test_issue_body_carries_required_fields():
    body = ci_red_alert.build_issue_body(
        "fidelity", "main", 42589215258, "http://run", "a1c2c89",
        ci_red_alert.MONITORED_WORKFLOW_CRONS["fidelity"],
        "Fidelity nightly (Score candidate)", "Traceback ...",
    )
    assert "run: `42589215258`" in body
    assert "head sha: `a1c2c89`" in body
    assert "`0 2 * * 1" in body
    assert "Score candidate" in body
    assert "[CI红] fidelity @ main" in body
    assert MARKER in body


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
