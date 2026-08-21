"""Tests for scripts/validation/validation_report.py (plan todo 18).

The director report (guide §5) consumes a persisted
``validation-runs/<ts>/scenarios.json`` run and emits ``report.md`` +
``report.json`` with TWO verdict families side by side (draft D13):
**agent-user conformance** (agent-surface scenarios, name prefix
``tool-``, AGENT-SURFACE anchors) and **human-quality conformance**
(pipeline scenarios, name prefix ``pipeline-``, HUMAN-QUALITY anchors).

Constraints under test (plan todo 18):

- The persisted scenarios.json has NO ``category`` field — the family is
  derived from the scenario name prefix, else from the steps'
  ``standard: STANDARDS.md#<anchor>`` citations, else a default.
- BOTH family headings always render, even when a family has zero
  scenarios in the run.
- ``unconfigured`` pipeline scenarios (no LLM keys) render as a distinct
  status — never GREEN, never RED-as-failure, never in blockers — with
  ``missing_env`` shown.
- Blockers are findings only: every failed scenario is a finding citing
  the standard it violated, with NO fix-suggestion language.
- Regression failures resolve from ``scenarios/regression/*.yaml`` by
  name (``regression: true`` + ``regression_issue``), overridable.
- Missing input → a clear error, not a silent empty report.

The script lives under ``scripts/`` which is not a package, so it is
loaded from its file path with importlib — the same convention as
``tests/validation/test_coverage_audit.py``.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SUITE_ROOT = Path(__file__).resolve().parent.parent.parent

_REPORT_PATH = SUITE_ROOT / "scripts" / "validation" / "validation_report.py"

FORBIDDEN_BLOCKER_WORDS = ("fix", "should", "recommend")


def _load_report():
    """Import scripts/validation/validation_report.py from its file path."""
    spec = importlib.util.spec_from_file_location("validation_report", _REPORT_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["validation_report"] = mod
    spec.loader.exec_module(mod)
    return mod


report = _load_report()

AGENT_USER = "agent-user conformance"
HUMAN_QUALITY = "human-quality conformance"


# ---------------------------------------------------------------------------
# Synthetic run payloads
# ---------------------------------------------------------------------------


def _step(index: int, name: str, standard: str, *, passed: bool, actual: dict) -> dict:
    return {
        "step_index": index,
        "name": name,
        "kind": "mcp",
        "surface": f"mcp: omni_mcp.server.{name.split()[0]}",
        "real_call": f'call_tool("{name}")',
        "expect": {"success": passed},
        "actual": actual,
        "artifact_to_show": None,
        "standard": standard,
        "arguments": {},
        "duration_seconds": 0.01,
        "trace_id": "trace-1",
        "passed": passed,
        "status": "passed" if passed else "failed",
        "grade": {"passed": passed, "detail": "ok" if passed else "check failed"},
        "recovery": [],
        "recovery_status": None,
    }


def _scenario(
    name: str,
    status: str,
    *,
    steps: list[dict] | None = None,
    missing_env: list[str] | None = None,
    summary: str | None = None,
) -> dict:
    return {
        "name": name,
        "status": status,
        "summary": summary or f"{status} — {len(steps or [])} step(s)",
        "missing_env": missing_env or [],
        "steps": steps or [],
        "cleanup": [],
        "trace_id": "trace-1",
    }


def _run_payload(scenarios: list[dict], *, run_meta: dict | None = None) -> dict:
    payload = {
        "run_id": "20260101-000000",
        "timestamp": "2026-01-01T00:00:00",
        "trace_id": "trace-1",
        "scenarios": scenarios,
    }
    if run_meta is not None:
        payload["run_meta"] = run_meta
    return payload


def _write_run(tmp_path: Path, payload: dict) -> Path:
    f = tmp_path / "scenarios.json"
    f.write_text(json.dumps(payload), encoding="utf-8")
    return f


def _happy_payload() -> dict:
    return _run_payload(
        [
            _scenario(
                "tool-omni_mcp-ping",
                "passed",
                steps=[
                    _step(
                        1,
                        "ping returns module and version",
                        "STANDARDS.md#tool-contract",
                        passed=True,
                        actual={"success": True, "data": {"module": "omni-mcp"}},
                    ),
                    _step(
                        2,
                        "ping rejects an unexpected argument cleanly",
                        "STANDARDS.md#error-clarity",
                        passed=True,
                        actual={"success": False, "error": "unexpected argument 'bogus'"},
                    ),
                ],
            ),
            _scenario(
                "pipeline-docx-md-docx",
                "unconfigured",
                missing_env=["OPENAI_API_KEY", "ZHIPU_API_KEY"],
            ),
        ]
    )


# ---------------------------------------------------------------------------
# Happy path — both families, evidence lines, distinct unconfigured (D13)
# ---------------------------------------------------------------------------


def test_happy_both_family_headings_present(tmp_path: Path):
    """A run with an agent-surface scenario (passed) and a pipeline
    scenario (unconfigured) renders BOTH family headings, even though one
    family has no passing scenario."""
    md, _ = report.generate(_write_run(tmp_path, _happy_payload()))
    assert f"## {AGENT_USER}" in md
    assert f"## {HUMAN_QUALITY}" in md


def test_happy_family_headings_render_when_family_empty(tmp_path: Path):
    """D13: BOTH headings always render — a run with only tool- scenarios
    still shows the human-quality conformance heading (and vice versa)."""
    only_tools = _run_payload([_scenario("tool-omni_mcp-ping", "passed", steps=[])])
    md, _ = report.generate(_write_run(tmp_path, only_tools))
    assert f"## {HUMAN_QUALITY}" in md
    only_pipeline = _run_payload([_scenario("pipeline-docx-md-docx", "unconfigured")])
    md2, _ = report.generate(_write_run(tmp_path, only_pipeline))
    assert f"## {AGENT_USER}" in md2


def test_happy_per_step_evidence_lines(tmp_path: Path):
    """Every step renders the D12 six-field evidence line
    'checked X against Y → Z'."""
    md, _ = report.generate(_write_run(tmp_path, _happy_payload()))
    assert "checked `mcp: omni_mcp.server.ping` against `STANDARDS.md#tool-contract` →" in md
    assert "checked `mcp: omni_mcp.server.ping` against `STANDARDS.md#error-clarity` →" in md
    assert "→" in md


def test_happy_pipeline_unconfigured_rendered_distinct(tmp_path: Path):
    """unconfigured is a distinct status: never GREEN, never RED, never in
    blockers — and shows the missing env vars."""
    md, data = report.generate(_write_run(tmp_path, _happy_payload()))
    assert "UNCONFIGURED" in md
    assert "OPENAI_API_KEY" in md and "ZHIPU_API_KEY" in md
    assert "GREEN" not in md.split("## human-quality")[1].split("## ")[0] or "UNCONFIGURED" in md
    pipeline_block = data["families"][HUMAN_QUALITY]
    assert pipeline_block["unconfigured"] == 1
    assert pipeline_block["failed"] == 0
    assert all(b["name"] != "pipeline-docx-md-docx" for b in data["blockers"])


def test_happy_json_shape(tmp_path: Path):
    """report.json mirrors the run plus the derived verdict structure."""
    _, data = report.generate(_write_run(tmp_path, _happy_payload()))
    assert data["run_id"] == "20260101-000000"
    assert data["trace_id"] == "trace-1"
    assert set(data["families"]) == {AGENT_USER, HUMAN_QUALITY}
    by_name = {s["name"]: s for s in data["scenarios"]}
    assert by_name["tool-omni_mcp-ping"]["family"] == AGENT_USER
    assert by_name["pipeline-docx-md-docx"]["family"] == HUMAN_QUALITY
    assert by_name["tool-omni_mcp-ping"]["steps"][0]["evidence_line"].startswith("checked ")
    assert data["verdict_counts"]["passed"] == 1
    assert data["verdict_counts"]["unconfigured"] == 1
    assert data["blockers"] == []


# ---------------------------------------------------------------------------
# Failure path — RED in the right family, blocker WITHOUT fix text
# ---------------------------------------------------------------------------


def test_failure_red_in_agent_user_family_and_blocker(tmp_path: Path):
    """One failing agent-surface scenario → RED under agent-user
    conformance and listed as a blocker citing the violated standard."""
    failing = _scenario(
        "tool-opp-extract_document",
        "failed",
        steps=[
            _step(
                1,
                "extract outside allowlist denied",
                "STANDARDS.md#path-security",
                passed=False,
                actual={"success": False, "error": "path not in allowlist"},
            )
        ],
    )
    md, data = report.generate(_write_run(tmp_path, _run_payload([failing])))
    family_section = md.split(f"## {AGENT_USER}")[1].split("## ")[0]
    assert "RED" in family_section
    assert "tool-opp-extract_document" in family_section
    assert len(data["blockers"]) == 1
    blocker = data["blockers"][0]
    assert blocker["name"] == "tool-opp-extract_document"
    assert blocker["family"] == AGENT_USER
    assert blocker["standard"] == "STANDARDS.md#path-security"
    assert data["families"][AGENT_USER]["failed"] == 1


@pytest.mark.parametrize("word", FORBIDDEN_BLOCKER_WORDS)
def test_failure_blocker_contains_no_fix_language(tmp_path: Path, word: str):
    """Blockers are findings only (plan todo 18): no fix suggestions, no
    'should change', no recommendations — in md or json."""
    failing = _scenario(
        "tool-omni_mcp-ping",
        "failed",
        steps=[_step(1, "ping fails", "STANDARDS.md#tool-contract", passed=False, actual={"success": False, "error": "boom"})],
    )
    md, data = report.generate(_write_run(tmp_path, _run_payload([failing])))
    blockers_md = md.split("## Blockers")[1].split("## Per-step")[0]
    assert word not in blockers_md.lower()
    assert word not in json.dumps(data["blockers"]).lower()


# ---------------------------------------------------------------------------
# Family derivation — standard anchors when the name has no prefix
# ---------------------------------------------------------------------------


def test_family_derived_from_human_quality_anchor(tmp_path: Path):
    """A non-tool-/pipeline- named scenario citing an HUMAN-QUALITY anchor
    lands in human-quality conformance (name prefix is not the only rule)."""
    sc = _scenario(
        "nightly-lqa",
        "passed",
        steps=[_step(1, "judge quality", "STANDARDS.md#lqa-threshold", passed=True, actual={"success": True})],
    )
    _, data = report.generate(_write_run(tmp_path, _run_payload([sc])))
    assert data["scenarios"][0]["family"] == HUMAN_QUALITY
    assert data["scenarios"][0]["family_derivation"] == "standard"


def test_family_derived_from_agent_surface_anchor(tmp_path: Path):
    """A regression-named scenario (t2-...) citing STANDARDS.md#exit-codes
    lands in agent-user conformance."""
    sc = _scenario(
        "t2-pdf-xliff-guard",
        "failed",
        steps=[_step(1, "OPP refuses PDF->XLIFF", "STANDARDS.md#exit-codes", passed=False, actual={"success": False, "error": "exit 0", "exit_code": 0})],
    )
    _, data = report.generate(_write_run(tmp_path, _run_payload([sc])))
    assert data["scenarios"][0]["family"] == AGENT_USER
    assert data["scenarios"][0]["family_derivation"] == "standard"


# ---------------------------------------------------------------------------
# Regression failures — resolved from scenarios/regression/*.yaml
# ---------------------------------------------------------------------------


def _regression_dir(tmp_path: Path) -> Path:
    d = tmp_path / "scenarios" / "regression"
    d.mkdir(parents=True)
    (d / "t2-pdf-xliff-guard.yaml").write_text(
        "name: t2-pdf-xliff-guard\nregression: true\nregression_issue: '#T2'\n",
        encoding="utf-8",
    )
    return d.parent


def test_regression_failure_section_lists_failed_regression(tmp_path: Path):
    """A failed scenario whose regression metadata resolves from the
    regression dir appears in the Regression failures section with its
    issue reference."""
    failing = _scenario(
        "t2-pdf-xliff-guard",
        "failed",
        steps=[_step(1, "OPP refuses PDF->XLIFF", "STANDARDS.md#exit-codes", passed=False, actual={"success": False, "exit_code": 0})],
    )
    md, data = report.generate(
        _write_run(tmp_path, _run_payload([failing])),
        scenarios_dir=_regression_dir(tmp_path),
    )
    assert "## Regression failures" in md
    assert "t2-pdf-xliff-guard" in md.split("## Regression failures")[1].split("## ")[0]
    assert data["regression_failures"][0]["regression_issue"] == "#T2"


def test_regression_passed_is_not_a_failure(tmp_path: Path):
    """A regression scenario that PASSED (guard held) is not a regression
    failure — the section notes none."""
    passing = _scenario(
        "t2-pdf-xliff-guard",
        "passed",
        steps=[_step(1, "OPP refuses PDF->XLIFF", "STANDARDS.md#exit-codes", passed=True, actual={"success": False, "exit_code": 1})],
    )
    md, data = report.generate(
        _write_run(tmp_path, _run_payload([passing])),
        scenarios_dir=_regression_dir(tmp_path),
    )
    assert data["regression_failures"] == []
    assert "(no regression failures" in md


def test_regression_metadata_missing_is_not_a_regression(tmp_path: Path):
    """A failed scenario NOT declared in scenarios/regression/*.yaml is a
    plain blocker, not a regression failure."""
    failing = _scenario(
        "tool-omni_mcp-ping",
        "failed",
        steps=[_step(1, "ping fails", "STANDARDS.md#tool-contract", passed=False, actual={"success": False})],
    )
    _, data = report.generate(
        _write_run(tmp_path, _run_payload([failing])),
        scenarios_dir=_regression_dir(tmp_path),
    )
    assert data["regression_failures"] == []
    assert len(data["blockers"]) == 1


# ---------------------------------------------------------------------------
# write_report / CLI behavior — files land next to the input
# ---------------------------------------------------------------------------


def test_write_report_creates_md_and_json_next_to_input(tmp_path: Path):
    """write_report produces report.md AND report.json in the same dir as
    the scenarios.json input."""
    src = _write_run(tmp_path, _happy_payload())
    out = report.write_report(src)
    assert out == tmp_path / "report.md"
    assert out.exists()
    assert (tmp_path / "report.json").exists()
    md_text = out.read_text(encoding="utf-8")
    assert f"## {AGENT_USER}" in md_text and f"## {HUMAN_QUALITY}" in md_text
    data = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert data["run_id"] == "20260101-000000"


def test_missing_input_raises_clear_error(tmp_path: Path):
    """A missing scenarios.json yields a clear error naming the path —
    never a silent empty report."""
    missing = tmp_path / "nope" / "scenarios.json"
    with pytest.raises(SystemExit) as exc:
        report.generate(missing)
    assert "scenarios.json" in str(exc.value)


def test_unparseable_input_raises_clear_error(tmp_path: Path):
    """Broken JSON yields a clear error, not a stack trace in the report."""
    bad = tmp_path / "scenarios.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        report.generate(bad)
    assert str(exc.value)


# ---------------------------------------------------------------------------
# Per-repo report card (OPP#58) — matrix keyed by run_meta.repos + suite
# ---------------------------------------------------------------------------


def _report_card_payload() -> dict:
    """A synthetic run with run_meta repos ['opp'] and scenarios that map
    to opp (tool-opp-*) and suite (pipeline-*)."""
    return _run_payload(
        [
            _scenario("tool-opp-extract_document", "passed"),
            _scenario("pipeline-docx-md-docx", "unconfigured"),
        ],
        run_meta={
            "suite_version": "0.4.0",
            "suite_sha": "abcd1234",
            "opp": {"version": "0.9.1", "sha": "beef0001"},
            "repos": ["opp"],
        },
    )


def test_repo_of_prefix_mappings():
    """_repo_of_scenario routes by name prefix: tool-opp-*/opp-* → opp,
    tool-ol-*/ol-* → ol, tool-orf-*/orf-* → orf, and pipeline-* /
    tool-omni_mcp-* → suite.  Anything else defaults to suite."""
    cases = {
        "tool-opp-extract_document": ("opp", "prefix"),
        "opp-csv-extract": ("opp", "prefix"),
        "tool-ol-judge_text": ("ol", "prefix"),
        "ol-edge-empty-input": ("ol", "prefix"),
        "tool-orf-apply_md": ("orf", "prefix"),
        "orf-backfill-html": ("orf", "prefix"),
        "pipeline-docx-md-docx": ("suite", "prefix"),
        "tool-omni_mcp-ping": ("suite", "prefix"),
    }
    for name, expected in cases.items():
        assert report._repo_of_scenario(name) == expected, name


def test_repo_of_unmapped_name_defaults_to_suite():
    """A name with no known prefix (e.g. nightly-lqa) lands in the suite
    cell with the 'default' derivation — never an error."""
    assert report._repo_of_scenario("nightly-lqa") == ("suite", "default")


def test_report_card_matrix_keyed_by_suite_and_run_meta_repos(tmp_path: Path):
    """report.json's report_card.matrix has a cell per run_meta repo PLUS
    always suite, each with version/sha/scenarios/verdicts/scenarios_list."""
    _, data = report.generate(_write_run(tmp_path, _report_card_payload()))

    rc = data["report_card"]
    assert set(rc["matrix"]) == {"opp", "suite"}
    opp = rc["matrix"]["opp"]
    assert opp["version"] == "0.9.1" and opp["sha"] == "beef0001"
    assert opp["scenarios"] == 1
    assert opp["verdicts"] == {"passed": 1}
    assert opp["scenarios_list"][0]["name"] == "tool-opp-extract_document"
    assert opp["scenarios_list"][0]["repo"] == "opp"
    assert opp["scenarios_list"][0]["repo_derivation"] == "prefix"
    suite = rc["matrix"]["suite"]
    assert suite["version"] == "0.4.0" and suite["sha"] == "abcd1234"
    assert suite["scenarios"] == 1
    assert suite["verdicts"] == {"unconfigured": 1}


def test_report_card_matrix_repo_unknown_version_fallback(tmp_path: Path):
    """A run_meta missing a repo key still yields the matrix with an
    'unknown' version/sha — never an error."""
    payload = _run_payload(
        [_scenario("tool-opp-extract_document", "passed")],
        run_meta={"repos": ["opp"], "suite_version": "0.4.0"},
    )
    _, data = report.generate(_write_run(tmp_path, payload))
    opp = data["report_card"]["matrix"]["opp"]
    assert opp["version"] == "unknown" and opp["sha"] == "unknown"
    assert opp["scenarios"] == 1


def test_report_markdown_has_report_card_section(tmp_path: Path):
    """report.md renders a ``## Report card`` section with one table row
    per repo cell."""
    md, _ = report.generate(_write_run(tmp_path, _report_card_payload()))
    assert "## Report card" in md
    assert "| Repo | Version | SHA | Scenarios |" in md
    assert "| opp | 0.9.1 |" in md
    assert "| suite | 0.4.0 |" in md
