#!/usr/bin/env python3
"""The director report (guide §5, plan todo 18): two verdict families.

Consumes a persisted ``validation-runs/<ts>/scenarios.json`` run and
emits ``report.md`` + ``report.json`` in the same run directory.

The report renders TWO verdict families side by side (draft D13):

- **agent-user conformance** — every agent-facing surface works as an
  agent would use it: agent-surface scenarios (name prefix ``tool-``)
  plus anything citing an AGENT-SURFACE standard anchor
  (``tool-contract``, ``json-parseable``, ``error-clarity``,
  ``path-security``, ``exit-codes``).
- **human-quality conformance** — the pipeline's output satisfies human
  end-users: pipeline scenarios (name prefix ``pipeline-``) plus anything
  citing an HUMAN-QUALITY standard anchor (``lqa-threshold``,
  ``para-ratio``, ``cjk-density``, ``punct-hygiene``, ``drawing-count``,
  ``opens-docx``).

IMPORTANT (plan todo 18): the persisted scenarios.json has NO ``category``
field — the family is derived from the scenario NAME PREFIX first, else
from the steps' ``standard: STANDARDS.md#<anchor>`` citations, else the
agent-user default.  Both family headings ALWAYS render, even when a
family has zero scenarios in the run.

Other report rules:

- The report also carries a per-repo **report card** (AutoInfo matrix
  style): a matrix keyed by ``run_meta.repos`` plus always ``suite``,
  each cell holding version + sha + per-scenario verdicts.  Scenario
  names map to a repo by prefix (``tool-opp-*`` → opp, …); anything
  else lands in the ``suite`` cell.  ``report.json`` carries it as
  ``report_card`` and ``report.md`` renders it as a ``## Report card``
  section.
- ``unconfigured`` scenarios (no LLM keys) render as a DISTINCT status —
  never GREEN, never RED-as-failure, never in blockers — with
  ``missing_env`` shown.
- Blockers are findings only: every failed scenario is a finding citing
  the standard it violated; NO fix suggestions, no "should change", no
  recommendations.
- Regression failures resolve from ``scenarios/regression/*.yaml`` by
  name (``regression: true`` + ``regression_issue``), overridable with
  ``--scenarios-dir`` for tests.
- Every step renders the D12 six-field evidence line
  ``checked {surface} against {standard} → {actual}``.

Usage:
    python scripts/validation/validation_report.py [validation-runs/<ts>/scenarios.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# R-07: the shared rule lives in omni_mcp.validation.family (scripts/ is not
# a package, so the dependency points INTO it). Anchor sets are re-exports.
from omni_mcp.validation.family import (  # noqa: F401
    AGENT_SURFACE_ANCHORS,
    AGENT_USER,
    HUMAN_QUALITY,
    HUMAN_QUALITY_ANCHORS,
    family_of,
)

GREEN_STATUSES = {"passed", "recovered"}

#: Repo name → the scenario-name prefixes that route a scenario to that
#: repo's report-card cell (per-repo validation delivery, OPP#58).  The
#: suite cell catches ``pipeline-``/``regression-``/``tool-omni_mcp-``
#: and everything else.
_REPO_PREFIXES: dict[str, tuple[str, ...]] = {
    "opp": ("tool-opp-", "opp-"),
    "ol": ("tool-ol-", "ol-"),
    "orf": ("tool-orf-", "orf-"),
    "suite": ("pipeline-", "regression-", "tool-omni_mcp-"),
}


# ---------------------------------------------------------------------------
# Repo routing (family/anchor classification imported from the package)
# ---------------------------------------------------------------------------


def _repo_of_scenario(name: str) -> tuple[str, str]:
    """The report-card repo for a scenario name, plus its derivation.

    ``tool-opp-*`` / ``tool-ol-*`` / ``tool-orf-*`` and ``opp-`` /
    ``ol-`` / ``orf-`` prefixed names route to that repo (``prefix``);
    ``pipeline-`` / ``regression-`` / ``tool-omni_mcp-`` and anything
    else route to ``suite`` (``prefix`` / ``default``).  Never errors.
    """
    name = name if isinstance(name, str) else ""
    for repo, prefixes in _REPO_PREFIXES.items():
        for prefix in prefixes:
            if name.startswith(prefix):
                return repo, "prefix"
    return "suite", "default"


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def _actual_summary(actual: Any, limit: int = 100) -> str:
    """A compact one-line rendering of a step's ``actual`` for the
    evidence line and the blockers: built from known keys only (never a
    raw dump), truncated, pipe/newline-safe."""
    if not isinstance(actual, dict):
        text = json.dumps(actual, ensure_ascii=False) if not isinstance(actual, str) else actual
        return text[:limit] + ("…" if len(text) > limit else "")
    parts: list[str] = []
    if "exit_code" in actual:
        parts.append(f"exit={actual['exit_code']}")
    if "success" in actual:
        parts.append(f"success={str(actual['success']).lower()}")
    for key in ("error", "stderr", "reason", "detail"):
        val = actual.get(key)
        if val:
            parts.append(f"{key}={str(val)[:60]}")
            break
    if not parts and "data" in actual:
        parts.append(f"data={json.dumps(actual['data'], ensure_ascii=False)[:60]}")
    text = ", ".join(parts) if parts else json.dumps(actual, ensure_ascii=False)
    return text[:limit] + ("…" if len(text) > limit else "")


def _verdict_marker(status: str) -> str:
    """The status marker: GREEN / RED / UNCONFIGURED / INVALID /
    PARTIAL-PASS / RECOVERED.  ``unconfigured`` is its own distinct status
    — never GREEN, never RED-as-failure; ``invalid`` (fake-LLM
    inadmissible evidence) never renders GREEN."""
    if status == "unconfigured":
        return "UNCONFIGURED"
    if status == "invalid":
        return "INVALID"
    if status == "failed":
        return "RED"
    if status == "partial-pass":
        return "PARTIAL-PASS"
    if status == "known-gap":
        return "KNOWN-GAP"
    if status == "recovered":
        return "GREEN (recovered)"
    return "GREEN"


# ---------------------------------------------------------------------------
# Regression metadata — resolved from scenarios/regression/*.yaml
# ---------------------------------------------------------------------------


def load_regression_meta(scenarios_dir: str | Path) -> dict[str, dict[str, Any]]:
    """Name → regression metadata (``regression``, ``regression_issue``)
    from ``scenarios_dir/regression/*.yaml``.  Empty when the dir has no
    regression scenarios; ``--scenarios-dir`` overrides the repo default
    so tests can point at synthetic yaml."""
    import yaml  # PyYAML — the suite's only allowed extra dependency

    meta: dict[str, dict[str, Any]] = {}
    reg_dir = Path(scenarios_dir) / "regression"
    if not reg_dir.is_dir():
        return meta
    for yf in sorted(reg_dir.glob("*.yaml")):
        try:
            doc = yaml.safe_load(yf.read_text(encoding="utf-8")) or {}
        except Exception:
            continue  # a malformed regression yaml must not sink the report
        name = doc.get("name")
        if not name:
            continue
        meta[name] = {
            "regression": bool(doc.get("regression", False)),
            "regression_issue": doc.get("regression_issue", ""),
        }
    return meta


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------


def _build_report(
    payload: dict[str, Any], scenarios_dir: str | Path
) -> dict[str, Any]:
    """Derive the report structure (json half) from the run payload."""
    scenarios = payload.get("scenarios", [])
    regression_meta = load_regression_meta(scenarios_dir)
    verdict_counts: dict[str, int] = {}
    families: dict[str, dict[str, Any]] = {
        AGENT_USER: {"scenarios": 0, "passed": 0, "failed": 0, "unconfigured": 0, "other": 0},
        HUMAN_QUALITY: {"scenarios": 0, "passed": 0, "failed": 0, "unconfigured": 0, "other": 0},
    }
    blockers: list[dict[str, Any]] = []
    regression_failures: list[dict[str, Any]] = []
    rendered: list[dict[str, Any]] = []

    for sc in scenarios:
        name = sc.get("name", "?")
        status = sc.get("status", "unknown")
        verdict_counts[status] = verdict_counts.get(status, 0) + 1
        family, derivation = family_of(name, sc.get("steps", []))
        families[family]["scenarios"] += 1
        if status in GREEN_STATUSES:
            families[family]["passed"] += 1
        elif status == "failed":
            families[family]["failed"] += 1
        elif status == "unconfigured":
            families[family]["unconfigured"] += 1
        else:
            families[family]["other"] += 1

        step_rows = []
        for st in sc.get("steps", []):
            actual = st.get("actual")
            evidence = (
                f"checked `{st.get('surface', '?')}` against "
                f"`{st.get('standard', '?')}` → {_actual_summary(actual)}"
            )
            step_rows.append(
                {
                    "step_index": st.get("step_index"),
                    "name": st.get("name"),
                    "kind": st.get("kind"),
                    "surface": st.get("surface"),
                    "real_call": st.get("real_call"),
                    "expect": st.get("expect"),
                    "actual": actual,
                    "artifact_to_show": st.get("artifact_to_show"),
                    "standard": st.get("standard"),
                    "duration_seconds": st.get("duration_seconds"),
                    "passed": st.get("passed"),
                    "status": st.get("status"),
                    "evidence_line": evidence,
                }
            )

        entry: dict[str, Any] = {
            "name": name,
            "family": family,
            "family_derivation": derivation,
            "status": status,
            "summary": sc.get("summary", ""),
            "missing_env": sc.get("missing_env", []),
            "steps": step_rows,
            "cleanup": sc.get("cleanup", []),
            "trace_id": sc.get("trace_id"),
            "known_gap": bool(sc.get("known_gap", False)),
        }

        if status == "failed":
            for st in sc.get("steps", []):
                if st.get("status") != "failed" and st.get("passed") is not False:
                    continue
                blocker = {
                    "name": name,
                    "family": family,
                    "summary": sc.get("summary", ""),
                    "standard": st.get("standard"),
                    "step_index": st.get("step_index"),
                    "step_name": st.get("name"),
                    "surface": st.get("surface"),
                    "real_call": st.get("real_call"),
                    "actual": _actual_summary(st.get("actual")),
                }
                blockers.append(blocker)
                entry.setdefault("blocked_by", []).append(blocker)

        meta = regression_meta.get(name)
        if meta and meta.get("regression"):
            if status == "failed":
                regression_failures.append(
                    {
                        "name": name,
                        "family": family,
                        "regression_issue": meta.get("regression_issue", ""),
                        "status": status,
                        "summary": sc.get("summary", ""),
                    }
                )
            entry["regression"] = True
            entry["regression_issue"] = meta.get("regression_issue", "")
        rendered.append(entry)

    return {
        "run_id": payload.get("run_id"),
        "timestamp": payload.get("timestamp"),
        "trace_id": payload.get("trace_id"),
        "scenarios": rendered,
        "families": families,
        "verdict_counts": verdict_counts,
        "blockers": blockers,
        "regression_failures": regression_failures,
        "report_card": _build_report_card(payload, rendered),
    }


def _render_report_card_md(report_card: dict[str, Any]) -> str:
    """The ``## Report card`` markdown section: one table row per repo
    cell with version, 8-char sha, scenario count and the
    passed/failed/unconfigured verdict counts."""
    lines: list[str] = []
    lines.append("## Report card")
    lines.append("")
    lines.append("| Repo | Version | SHA | Scenarios | Passed | Failed | Unconfigured |")
    lines.append("|------|---------|-----|-----------|--------|--------|--------------|")
    matrix = report_card.get("matrix", {})
    for repo in sorted(matrix):
        cell = matrix[repo]
        counts = cell.get("verdicts", {})
        lines.append(
            f"| {repo} | {cell.get('version', 'unknown')} | "
            f"{(cell.get('sha', 'unknown') or 'unknown')[:8]} | "
            f"{cell.get('scenarios', 0)} | "
            f"{counts.get('passed', 0)} | {counts.get('failed', 0)} | "
            f"{counts.get('unconfigured', 0)} |"
        )
    lines.append("")
    return "\n".join(lines)


def _build_report_card(
    payload: dict[str, Any], rendered_scenarios: list[dict[str, Any]]
) -> dict[str, Any]:
    """The per-repo report card (AutoInfo matrix style): one cell per repo
    in ``run_meta.repos`` plus ALWAYS ``suite``.

    Each cell carries ``version``/``sha`` (from run_meta —
    ``suite_version``/``suite_sha`` for suite, ``run_meta[repo]``
    ``version``/``sha`` for components; ``"unknown"`` fallback, never
    errors), ``scenarios`` (count), ``verdicts`` (status → count) and
    ``scenarios_list`` (one entry per scenario in the cell).
    """
    run_meta = payload.get("run_meta") or {}
    repos = list(run_meta.get("repos") or [])
    if "suite" not in repos:
        repos.append("suite")

    cells: dict[str, dict[str, Any]] = {}
    for repo in repos:
        if repo == "suite":
            version = run_meta.get("suite_version", "unknown")
            sha = run_meta.get("suite_sha", "unknown")
        else:
            entry = run_meta.get(repo) or {}
            version = entry.get("version", "unknown")
            sha = entry.get("sha", "unknown")
        cells[repo] = {
            "version": version,
            "sha": sha,
            "scenarios": 0,
            "verdicts": {},
            "scenarios_list": [],
        }

    for sc in rendered_scenarios:
        repo, derivation = _repo_of_scenario(sc["name"])
        cell = cells.setdefault(
            repo,
            {
                "version": (run_meta.get(repo) or {}).get("version", "unknown")
                if repo != "suite"
                else run_meta.get("suite_version", "unknown"),
                "sha": (run_meta.get(repo) or {}).get("sha", "unknown")
                if repo != "suite"
                else run_meta.get("suite_sha", "unknown"),
                "scenarios": 0,
                "verdicts": {},
                "scenarios_list": [],
            },
        )
        cell["scenarios"] += 1
        status = sc["status"]
        cell["verdicts"][status] = cell["verdicts"].get(status, 0) + 1
        cell["scenarios_list"].append(
            {
                "name": sc["name"],
                "status": status,
                "family": sc["family"],
                "repo": repo,
                "repo_derivation": derivation,
            }
        )

    return {"repos": repos, "matrix": cells}


def _render_markdown(report_data: dict[str, Any]) -> str:
    """Render the report_data into the guide §5 director report layout:
    verdict summary, executive summary, regression failures, blockers
    (findings only), per-step trace with evidence lines."""
    run_id = report_data["run_id"]
    trace_id = report_data["trace_id"]
    counts = report_data["verdict_counts"]
    total = sum(counts.values())
    passed = counts.get("passed", 0) + counts.get("recovered", 0)
    failed = counts.get("failed", 0)
    unconfigured = counts.get("unconfigured", 0)

    lines: list[str] = []
    lines.append(f"# Validation Director Report — {run_id}")
    lines.append("")
    lines.append(f"> Run `{run_id}` | trace_id `{trace_id}` | scenarios: {total} "
                 f"(passed={passed}, failed={failed}, unconfigured={unconfigured})")
    lines.append("")

    # --- Verdict summary -------------------------------------------------
    lines.append("## Verdict summary")
    lines.append("")
    lines.append("| Verdict | Count |")
    lines.append("|---------|-------|")
    for status in ("passed", "recovered", "partial-pass", "failed", "unconfigured"):
        if counts.get(status):
            lines.append(f"| {status} | {counts[status]} |")
    for status in sorted(set(counts) - {"passed", "recovered", "partial-pass", "failed", "unconfigured"}):
        lines.append(f"| {status} | {counts[status]} |")
    lines.append("")

    # --- Report card (per-repo matrix, OPP#58) --------------------------
    lines.append(_render_report_card_md(report_data["report_card"]))
    lines.append("")

    for family in (AGENT_USER, HUMAN_QUALITY):
        fam = report_data["families"][family]
        members = [s for s in report_data["scenarios"] if s["family"] == family]
        lines.append(f"### {family}")
        lines.append("")
        lines.append("| Scenario | Verdict | Steps |")
        lines.append("|----------|---------|-------|")
        if not members:
            lines.append("| _(no scenarios in this run)_ | — | — |")
        for s in members:
            marker = _verdict_marker(s["status"])
            if s["status"] == "unconfigured":
                detail = f"{marker} (missing env: {', '.join(s['missing_env']) or '—'})"
            else:
                detail = f"{marker} — {s['summary']}"
            lines.append(f"| `{s['name']}` | {detail} | {len(s['steps'])} |")
        lines.append("")
        if fam["unconfigured"]:
            lines.append(f"_This family includes {fam['unconfigured']} unconfigured "
                         "scenario(s) — not run (missing env keys), not a failure._")
            lines.append("")

    # --- Executive summary ----------------------------------------------
    lines.append("## Executive summary")
    lines.append("")
    if failed:
        lines.append(f"{failed} scenario(s) failed, {unconfigured} unconfigured, "
                     f"{passed} passed. Failures are listed as findings under "
                     "Blockers with the standard each violated; the per-step "
                     "trace below shows every check with its evidence "
                     "(surface / standard / actual).")
    elif unconfigured:
        lines.append(f"All configured scenario(s) passed ({passed}); {unconfigured} "
                     "scenario(s) were unconfigured (missing env keys — see the "
                     "family tables), so the human-quality bar was not exercised "
                     "in this run.")
    else:
        known_gap_count = counts.get("known-gap", 0)
        if known_gap_count:
            lines.append(
                f"All {passed} non-known-gap scenario(s) passed; "
                f"{known_gap_count} known-gap scenario(s) excluded from the "
                "pass bar (published bar not met; see ACCEPTED_GAPS.md)."
            )
        else:
            lines.append(f"All {passed} scenario(s) passed.")
    lines.append("")

    # --- Regression failures --------------------------------------------
    lines.append("## Regression failures")
    lines.append("")
    reg_failures = report_data["regression_failures"]
    if not reg_failures:
        lines.append("(no regression failures in this run)")
    else:
        for rf in reg_failures:
            issue = rf.get("regression_issue", "")
            issue_ref = f"(#{issue})" if issue and not issue.startswith("#") else f"({issue})" if issue else ""
            lines.append(f"- `{rf['name']} {issue_ref}` — {rf['status']} ({rf['family']}): {rf['summary']}")
    lines.append("")

    # --- Blockers (findings only — no fixes, no suggestions) -------------
    lines.append("## Blockers")
    lines.append("")
    blockers = report_data["blockers"]
    if not blockers:
        lines.append("(no failing scenarios in this run)")
    else:
        lines.append("_Findings only — each blocker names the scenario, the "
                     "step, and the standard it violated._")
        lines.append("")
        for b in blockers:
            lines.append(f"- `{b['name']}` ({b['family']}) — step {b['step_index']} "
                         f"`{b['step_name']}` violated `{b['standard']}`: {b['actual']}")
    lines.append("")

    # --- Per-step trace (evidence lines) ---------------------------------
    lines.append("## Per-step trace")
    lines.append("")
    lines.append("Every check of every scenario, as `checked {surface} against "
                 "{standard} → {actual}` (D12 six-field evidence).")
    lines.append("")
    for family in (AGENT_USER, HUMAN_QUALITY):
        members = [s for s in report_data["scenarios"] if s["family"] == family]
        lines.append(f"### {family}")
        lines.append("")
        if not members:
            lines.append("_(no scenarios in this run)_")
            lines.append("")
            continue
        for s in members:
            lines.append(f"- **`{s['name']}`** — {_verdict_marker(s['status'])}")
            if s["status"] == "unconfigured":
                lines.append(f"  - (not executed — unconfigured, missing env: "
                             f"{', '.join(s['missing_env']) or '—'})")
            for st in s["steps"]:
                lines.append(f"  - {st['evidence_line']}")
            for cl in s.get("cleanup", []):
                lines.append(f"  - cleanup step {cl.get('step_index', 0)} `{cl.get('name', '?')}` "
                             f"checked `{cl.get('surface', '?')}` against "
                             f"`{cl.get('standard', '?')}` → {_actual_summary(cl.get('actual'))}")
        lines.append("")
    lines.append("Generated by `python scripts/validation/validation_report.py`.")
    lines.append("")
    return "\n".join(lines)


def generate(
    scenarios_json: str | Path, scenarios_dir: str | Path = "scenarios"
) -> tuple[str, dict[str, Any]]:
    """Build (markdown, report_dict) from a persisted run's scenarios.json.

    Raises SystemExit with a clear message when the input is missing or
    unparseable — the report never silently renders an empty run.
    """
    src = Path(scenarios_json)
    if not src.exists():
        raise SystemExit(f"scenarios.json not found: {src}")
    try:
        payload = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"unparseable scenarios.json at {src}: {exc}") from exc
    data = _build_report(payload, scenarios_dir)
    return _render_markdown(data), data


def write_report(
    scenarios_json: str | Path, scenarios_dir: str | Path = "scenarios"
) -> Path:
    """Write report.md + report.json next to the input scenarios.json.

    Returns the report.md path.
    """
    md_text, data = generate(scenarios_json, scenarios_dir)
    run_dir = Path(scenarios_json).resolve().parent
    md_path = run_dir / "report.md"
    md_path.write_text(md_text, encoding="utf-8")
    (run_dir / "report.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Director report for a persisted validation run (two verdict families)"
    )
    parser.add_argument(
        "scenarios_json",
        nargs="?",
        default="",
        help="Path to validation-runs/<ts>/scenarios.json (default: newest run from latest.txt)",
    )
    parser.add_argument(
        "--scenarios-dir",
        default="scenarios",
        help="Repo scenarios dir (for regression metadata resolution; overridable in tests)",
    )
    args = parser.parse_args(argv)

    scenarios_json = args.scenarios_json
    if not scenarios_json:
        latest = Path("validation-runs") / "latest.txt"
        if latest.exists():
            scenarios_json = str(Path("validation-runs") / latest.read_text().strip() / "scenarios.json")
        else:
            parser.error("no scenarios.json given and no validation-runs/latest.txt pointer")
    out = write_report(scenarios_json, args.scenarios_dir)
    print(f"REPORT: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
