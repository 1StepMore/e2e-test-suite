"""Tests for omni_mcp.validation.grader (guide §3.1 phase 3 assert, §3.3
``evaluate_expect``).

The grader is the assertion layer: it grades one step's ``expect`` block
against the ``actual`` dict the dispatch phase captured (the StepResult
field contract — dispatch.py docstring).  Each check type grades
independently and every check must hold for the step to pass (guide §2.3:
"All assertions in a block are conjoined").  A step with an empty expect
block is not falsifiable and fails outright (mirrors AutoInfo contract
lint: run-validation-scenarios.py:506-537 "must be falsifiable").

The grader is pure logic: no I/O, no dispatch — the engine (todo 8)
composes it with the adapters.  Unknown expect keys fail their check
rather than being ignored (falsifiable discipline, typo protection).
"""

import re

import pytest

from omni_mcp.validation.grader import CheckResult, GradeResult, grade_step

# ---------------------------------------------------------------------------
# Falsifiability — empty expect never passes (guide §2.3, AutoInfo lint)
# ---------------------------------------------------------------------------


def test_empty_expect_fails_falsifiable():
    """An empty expect block cannot be graded: the step is not falsifiable,
    so it must fail — never auto-pass (defense in depth; the loader already
    rejects such steps at load time)."""
    result = grade_step({}, {"success": True, "exit_code": 0})

    assert result.passed is False
    assert result.checks == []
    assert "falsifiable" in result.reason


def test_none_expect_fails_falsifiable():
    """None expect (e.g. a step dict missing 'expect') fails the same way."""
    result = grade_step(None, {"success": True})

    assert result.passed is False
    assert "falsifiable" in result.reason


def test_non_dict_expect_fails_falsifiable():
    """A non-dict expect (list/str) is not a valid assertion block."""
    result = grade_step(["success"], {"success": True})

    assert result.passed is False
    assert "falsifiable" in result.reason


def test_non_dict_actual_never_crashes():
    """The actual dict is dispatch-shaped, but a degenerate value must fail
    the checks, not raise."""
    result = grade_step({"exit_code": 0}, None)

    assert result.passed is False
    assert result.checks[0].actual is None


# ---------------------------------------------------------------------------
# success — boolean envelope compare (guide §2.3)
# ---------------------------------------------------------------------------


def test_success_true_matches():
    result = grade_step({"success": True}, {"success": True, "data": {}})

    assert result.passed is True
    assert result.checks[0].passed is True


def test_success_mismatch_fails():
    result = grade_step({"success": True}, {"success": False, "error": "boom"})

    assert result.passed is False
    assert result.checks[0].passed is False
    assert result.checks[0].actual is False
    assert "success" in result.reason


def test_success_missing_actual_key_fails():
    """No success key in actual -> treated as absent -> mismatch."""
    result = grade_step({"success": True}, {"exit_code": 0})

    assert result.passed is False
    assert result.checks[0].actual is None


def test_success_non_bool_expected_fails():
    """'success: "true"' is a typo in waiting — the check must fail with a
    clear message instead of guessing."""
    result = grade_step({"success": "true"}, {"success": True})

    assert result.passed is False
    assert "boolean" in result.reason


# ---------------------------------------------------------------------------
# exit_code — exact int compare against actual["exit_code"] (guide §2.3)
# ---------------------------------------------------------------------------


def test_exit_code_zero_pass():
    """Acceptance: grader of ``{"exit_code": 0}`` against exit 0 -> pass."""
    result = grade_step({"exit_code": 0}, {"exit_code": 0, "stdout": "", "stderr": ""})

    assert result.passed is True
    assert result.checks[0].passed is True
    assert result.checks[0].expected == 0
    assert result.checks[0].actual == 0


def test_exit_code_mismatch_fails_records_actual():
    """Acceptance: ``{"exit_code": 0}`` against exit 1 -> fail with
    actual=1 recorded and a human-readable reason."""
    result = grade_step({"exit_code": 0}, {"exit_code": 1, "stdout": "", "stderr": ""})

    assert result.passed is False
    assert result.checks[0].passed is False
    assert result.checks[0].expected == 0
    assert result.checks[0].actual == 1
    assert "check 'exit_code': expected 0, actual 1" in result.reason


def test_exit_code_timeout_none_fails():
    """Dispatch records exit_code None on timeout — 0 != None -> fail."""
    result = grade_step(
        {"exit_code": 0},
        {"success": False, "timeout": True, "exit_code": None},
    )

    assert result.passed is False
    assert result.checks[0].actual is None


def test_exit_code_missing_actual_key_fails():
    result = grade_step({"exit_code": 1}, {"success": True})

    assert result.passed is False


def test_exit_code_wrong_type_fails():
    """'exit_code: "0"' (string) is a YAML quoting typo — fail loudly."""
    result = grade_step({"exit_code": "0"}, {"exit_code": 0})

    assert result.passed is False
    assert "integer" in result.reason


def test_exit_code_bool_expected_fails():
    """bool is an int subclass; exit_code: true would silently mean 1."""
    result = grade_step({"exit_code": True}, {"exit_code": 1})

    assert result.passed is False


# ---------------------------------------------------------------------------
# stdout_has / stderr_has — substring, list, regex, negative forms
# ---------------------------------------------------------------------------


def test_stdout_has_substring_pass():
    result = grade_step(
        {"stdout_has": "registered"}, {"success": True, "stdout": "user registered", "stderr": ""}
    )

    assert result.passed is True
    assert result.checks[0].passed is True


def test_stdout_has_substring_fail():
    result = grade_step(
        {"stdout_has": "registered"}, {"success": True, "stdout": "user created", "stderr": ""}
    )

    assert result.passed is False
    assert result.checks[0].actual == "user created"
    assert "registered" in result.reason


def test_stdout_has_list_all_required():
    """A list means ALL substrings must be present (guide §2.3 conjoined)."""
    result = grade_step(
        {"stdout_has": ["registered", "new@example.dev"]},
        {"stdout": "user registered at new@example.dev", "stderr": ""},
    )

    assert result.passed is True


def test_stdout_has_list_one_missing_fails():
    result = grade_step(
        {"stdout_has": ["registered", "new@example.dev"]},
        {"stdout": "user registered", "stderr": ""},
    )

    assert result.passed is False
    assert result.checks[0].passed is False


def test_stdout_has_regex_form():
    """``{"re": "regex"}`` form: pattern must search-match stdout."""
    result = grade_step(
        {"stdout_has": {"re": r"error \d+: \w+"}},
        {"stdout": "error 42: boom", "stderr": ""},
    )

    assert result.passed is True


def test_stdout_has_regex_no_match_fails():
    result = grade_step(
        {"stdout_has": {"re": r"error \d+"}},
        {"stdout": "all good", "stderr": ""},
    )

    assert result.passed is False
    assert "regex" in result.reason


def test_stdout_has_invalid_regex_fails_with_message():
    """A broken pattern must fail the check with the reason, not raise."""
    result = grade_step({"stdout_has": {"re": "("}}, {"stdout": "anything", "stderr": ""})

    assert result.passed is False
    assert "invalid" in result.reason.lower() or "regex" in result.reason


def test_stdout_has_unsupported_form_fails():
    """A dict without 're' (e.g. a typo key) is an unsupported form."""
    result = grade_step({"stdout_has": {"contains": "x"}}, {"stdout": "x", "stderr": ""})

    assert result.passed is False
    assert "stdout_has" in result.reason


def test_stderr_has_substring_pass_and_fail():
    ok = grade_step(
        {"stderr_has": "XLIFF not supported"}, {"success": False, "stderr": "XLIFF not supported for PDF", "stdout": ""}
    )
    bad = grade_step(
        {"stderr_has": "XLIFF not supported"}, {"success": False, "stderr": "unrelated error", "stdout": ""}
    )

    assert ok.passed is True
    assert bad.passed is False


def test_stdout_not_has_negative_assertion():
    """stdout_not_has passes only when the substring is absent."""
    ok = grade_step({"stdout_not_has": "panic"}, {"stdout": "all good", "stderr": ""})
    bad = grade_step({"stdout_not_has": "panic"}, {"stdout": "kernel panic", "stderr": ""})

    assert ok.passed is True
    assert bad.passed is False


def test_stderr_not_has_negative_assertion():
    ok = grade_step({"stderr_not_has": "Traceback"}, {"stdout": "", "stderr": "warn only"})
    bad = grade_step({"stderr_not_has": "Traceback"}, {"stdout": "", "stderr": "Traceback (most recent call last)"})

    assert ok.passed is True
    assert bad.passed is False


# ---------------------------------------------------------------------------
# data_has — substrings in the JSON-serialized data payload (guide §2.3)
# ---------------------------------------------------------------------------


def test_data_has_substring_in_json_dump():
    result = grade_step(
        {"data_has": ["translation"]},
        {"success": True, "data": {"translation": {"text": "你好"}}},
    )

    assert result.passed is True


def test_data_has_list_all_must_appear():
    result = grade_step(
        {"data_has": ["translation", "你好"]},
        {"success": True, "data": {"translation": {"text": "你好"}}},
    )

    assert result.passed is True


def test_data_has_missing_substring_fails():
    result = grade_step(
        {"data_has": ["translation"]},
        {"success": True, "data": {"scenarios": ["a"]}},
    )

    assert result.passed is False
    assert result.checks[0].passed is False


def test_data_has_missing_data_key_fails():
    """No data in actual -> json.dumps(None)="null" -> substring absent."""
    result = grade_step({"data_has": ["anything"]}, {"success": True})

    assert result.passed is False


def test_data_has_non_string_entry_fails():
    result = grade_step({"data_has": [42]}, {"success": True, "data": {"42": 1}})

    assert result.passed is False


# ---------------------------------------------------------------------------
# status_code — exact int compare (HTTP-shaped tools; adapter deferred)
# ---------------------------------------------------------------------------


def test_status_code_match():
    result = grade_step(
        {"status_code": 200}, {"success": True, "status_code": 200}
    )

    assert result.passed is True


def test_status_code_mismatch_fails():
    result = grade_step({"status_code": 200}, {"success": False, "status_code": 500})

    assert result.passed is False
    assert result.checks[0].actual == 500
    assert "expected 200, actual 500" in result.reason


def test_status_code_absent_actual_fails():
    """No HTTP adapter yet — actual simply lacks the key -> fail, never pass."""
    result = grade_step({"status_code": 200}, {"success": True})

    assert result.passed is False


def test_status_code_wrong_type_fails():
    result = grade_step({"status_code": "200"}, {"status_code": 200})

    assert result.passed is False


# ---------------------------------------------------------------------------
# json_has — JSONPath-ish dot path (truthy) or {"path", "value"} equality
# ---------------------------------------------------------------------------


def test_json_has_dot_path_truthy():
    result = grade_step(
        {"json_has": "data.translation.text"},
        {"success": True, "data": {"translation": {"text": "你好"}}},
    )

    assert result.passed is True


def test_json_has_path_missing_fails():
    result = grade_step(
        {"json_has": "data.translation.missing"},
        {"success": True, "data": {"translation": {"text": "你好"}}},
    )

    assert result.passed is False


def test_json_has_path_falsy_value_fails():
    """'' / 0 / False / None resolve but are not truthy -> fail."""
    result = grade_step(
        {"json_has": "data.translation.text"},
        {"success": True, "data": {"translation": {"text": ""}}},
    )

    assert result.passed is False


def test_json_has_path_value_equality():
    result = grade_step(
        {"json_has": {"path": "data.translation.text", "value": "你好"}},
        {"success": True, "data": {"translation": {"text": "你好"}}},
    )

    assert result.passed is True


def test_json_has_path_value_mismatch_fails():
    result = grade_step(
        {"json_has": {"path": "data.translation.text", "value": "hello"}},
        {"success": True, "data": {"translation": {"text": "你好"}}},
    )

    assert result.passed is False
    assert "你好" in result.reason or "actual" in result.reason


def test_json_has_list_of_paths():
    result = grade_step(
        {"json_has": ["data.translation.text", "success"]},
        {"success": True, "data": {"translation": {"text": "x"}}},
    )

    assert result.passed is True


def test_json_has_list_one_missing_fails():
    result = grade_step(
        {"json_has": ["data.translation.text", "data.nope"]},
        {"success": True, "data": {"translation": {"text": "x"}}},
    )

    assert result.passed is False


def test_json_has_unsupported_form_fails():
    """A dict without 'path' (typo key) must fail loudly."""
    result = grade_step({"json_has": {"pth": "data.x"}}, {"success": True, "data": {"x": 1}})

    assert result.passed is False
    assert "json_has" in result.reason


def test_json_has_scalar_expect_fails():
    result = grade_step({"json_has": 42}, {"success": True, "data": {}})

    assert result.passed is False


# ---------------------------------------------------------------------------
# Conjunction + structure (guide §2.3: all assertions conjoined)
# ---------------------------------------------------------------------------


def test_all_checks_must_pass_for_step():
    """One failing check among passing ones sinks the step."""
    result = grade_step(
        {"exit_code": 0, "stdout_has": "registered"},
        {"exit_code": 0, "stdout": "user created", "stderr": ""},
    )

    assert result.passed is False
    assert len(result.checks) == 2
    assert result.checks[0].passed is True
    assert result.checks[1].passed is False


def test_multiple_passing_checks_pass_together():
    result = grade_step(
        {"exit_code": 0, "stdout_has": "registered"},
        {"exit_code": 0, "stdout": "user registered", "stderr": ""},
    )

    assert result.passed is True
    assert len(result.checks) == 2


def test_unknown_expect_key_fails():
    """'exit_cod' is a typo for 'exit_code' — fail that check with a clear
    message instead of silently ignoring it (falsifiable discipline)."""
    result = grade_step({"exit_cod": 0}, {"exit_code": 0, "stdout": "", "stderr": ""})

    assert result.passed is False
    assert result.checks[0].name == "exit_cod"
    assert result.checks[0].passed is False
    assert "unknown" in result.reason


def test_reason_joins_all_failing_checks():
    result = grade_step(
        {"exit_code": 0, "success": True},
        {"exit_code": 2, "success": False},
    )

    assert "exit_code" in result.reason
    assert "success" in result.reason


def test_reason_positive_summary():
    result = grade_step({"exit_code": 0}, {"exit_code": 0})

    assert "2 checks passed" in result.reason or "1 check passed" in result.reason


def test_check_result_structure():
    """CheckResult carries name / passed / expected / actual."""
    result = grade_step({"exit_code": 0}, {"exit_code": 1})
    check = result.checks[0]

    assert isinstance(check, CheckResult)
    assert check.name == "exit_code"
    assert check.passed is False
    assert check.expected == 0
    assert check.actual == 1


def test_grade_result_structure():
    result = grade_step({"exit_code": 0}, {"exit_code": 1})

    assert isinstance(result, GradeResult)
    assert result.passed is False
    assert all(isinstance(c, CheckResult) for c in result.checks)
    assert isinstance(result.reason, str)
