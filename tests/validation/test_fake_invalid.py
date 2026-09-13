"""R-07 — family/anchor-classified FAKE_LLM hard-invalid (engine enforcement).

Given ``OMNI_TEST_FAKE_LLM=1`` is active in the effective env,
When a scenario is human-quality (name family ``pipeline-*`` OR any step
     cites a HUMAN-QUALITY anchor) or produces an artifact carrying the
     ``_FakeModelPool`` echo signature ``^[<tgt>] `` (whole-artifact,
     per-line scan),
Then the scenario verdict is ``invalid`` — never ``passed``.

``--allow-fake`` is the restricted contract-only escape hatch: it may only
re-admit a scenario when EVERY step cites an AGENT-SURFACE anchor.  An
anchor-less step (or a HUMAN-QUALITY citation) is ineligible, so the escape
is non-vacuous.

The baseline these tests pin: before R-07, a ``pipeline-*`` scenario with
``OMNI_TEST_FAKE_LLM=1`` read ``passed``.
"""

from __future__ import annotations

import importlib.util
import os
import textwrap
from pathlib import Path

from omni_mcp.validation.engine import run_scenarios

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _write(tmp_path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def _fake_env() -> dict[str, str]:
    """The effective env for a fake-active run (PATH kept so bare CLI
    commands resolve inside the dispatched subprocess)."""
    return {
        "OMNI_TEST_FAKE_LLM": "1",
        "PATH": os.environ.get("PATH", ""),
    }


def _no_fake_env() -> dict[str, str]:
    return {"PATH": os.environ.get("PATH", "")}


#: Human-quality by NAME PREFIX, anchor-less (so ``--allow-fake`` is
#: ineligible — the non-vacuous case).
PIPELINE_ANCHORLESS = """
name: pipeline-synthetic
description: "human-quality by name prefix, no anchor citations"
steps:
  - name: "contract-ish cli step"
    kind: cli
    command: "true"
    expect:
      success: true
"""


# ---------------------------------------------------------------------------
# Family rule: pipeline-* is human-quality
# ---------------------------------------------------------------------------


def test_pipeline_fake_is_invalid(tmp_path):
    """Baseline (pre-R-07): this read ``passed``.  Fake active => invalid."""
    _write(tmp_path, "p.yaml", PIPELINE_ANCHORLESS)
    sc = run_scenarios(
        tmp_path, env=_fake_env(), persist=False
    ).scenarios[0]
    assert sc.status == "invalid"
    assert sc.status != "passed"


def test_anchorless_pipeline_fake_is_invalid(tmp_path):
    """The non-vacuous case: an anchor-less pipeline-* scenario is still
    caught by the family rule (--allow-fake cannot be vacuous)."""
    _write(tmp_path, "p.yaml", PIPELINE_ANCHORLESS)
    sc = run_scenarios(
        tmp_path, env=_fake_env(), persist=False, allow_fake=True
    ).scenarios[0]
    assert sc.status == "invalid"


def test_pipeline_without_fake_is_passed(tmp_path):
    """Control: no fake in the effective env — the same scenario passes."""
    _write(tmp_path, "p.yaml", PIPELINE_ANCHORLESS)
    sc = run_scenarios(
        tmp_path, env=_no_fake_env(), persist=False
    ).scenarios[0]
    assert sc.status == "passed"


# ---------------------------------------------------------------------------
# Anchor rule: any HUMAN-QUALITY citation => human-quality
# ---------------------------------------------------------------------------

LQA_ANCHOR_SCENARIO = """
name: tool-lqa-check
description: "agent-surface prefix but a HUMAN-QUALITY anchor citation"
steps:
  - name: "read a quality metric"
    kind: cli
    command: "true"
    standard: STANDARDS.md#lqa-threshold
    expect:
      success: true
"""


def test_human_quality_anchor_fake_is_invalid(tmp_path):
    _write(tmp_path, "lqa.yaml", LQA_ANCHOR_SCENARIO)
    sc = run_scenarios(
        tmp_path, env=_fake_env(), persist=False
    ).scenarios[0]
    assert sc.status == "invalid"


def test_human_quality_anchor_not_rescued_by_allow_fake(tmp_path):
    """--allow-fake requires EVERY step to cite an AGENT-SURFACE anchor;
    a HUMAN-QUALITY citation makes the scenario ineligible."""
    _write(tmp_path, "lqa.yaml", LQA_ANCHOR_SCENARIO)
    sc = run_scenarios(
        tmp_path, env=_fake_env(), persist=False, allow_fake=True
    ).scenarios[0]
    assert sc.status == "invalid"


# ---------------------------------------------------------------------------
# --allow-fake escape hatch: all-AGENT-SURFACE only
# ---------------------------------------------------------------------------

CONTRACT_ONLY_PIPELINE = """
name: pipeline-contract-only
description: "human-quality family name, every step cites an AGENT-SURFACE anchor"
steps:
  - name: "contract check"
    kind: cli
    command: "true"
    standard: STANDARDS.md#exit-codes
    expect:
      success: true
"""


def test_allow_fake_readmits_all_agent_surface(tmp_path):
    _write(tmp_path, "c.yaml", CONTRACT_ONLY_PIPELINE)
    sc = run_scenarios(
        tmp_path, env=_fake_env(), persist=False, allow_fake=True
    ).scenarios[0]
    assert sc.status == "passed"


def test_without_allow_fake_contract_only_is_invalid(tmp_path):
    _write(tmp_path, "c.yaml", CONTRACT_ONLY_PIPELINE)
    sc = run_scenarios(
        tmp_path, env=_fake_env(), persist=False
    ).scenarios[0]
    assert sc.status == "invalid"


def test_agent_surface_scenario_under_fake_is_not_invalid(tmp_path):
    """Pure agent-surface scenarios are not quality evidence — fake does
    not invalidate them (no --allow-fake needed)."""
    _write(tmp_path, "a.yaml", """
name: tool-opp-extract
description: "pure agent-surface scenario"
steps:
  - name: "contract check"
    kind: cli
    command: "true"
    standard: STANDARDS.md#tool-contract
    expect:
      success: true
""")
    sc = run_scenarios(
        tmp_path, env=_fake_env(), persist=False
    ).scenarios[0]
    assert sc.status == "passed"


# ---------------------------------------------------------------------------
# Positive whole-artifact fake-marker check (non-first line)
# ---------------------------------------------------------------------------

FAKE_ARTIFACT_SCENARIO = """
name: tool-fake-artifact
description: "agent-surface scenario whose artifact carries the [xx] echo"
steps:
  - name: "write a fake-looking artifact"
    kind: python
    command: >-
      open(r'{artifact}', 'w', encoding='utf-8').write(
      'a clean first line\\n[xx] fake translation echo\\n')
    collect_artifacts:
      - path: {artifact}
    standard: STANDARDS.md#tool-contract
    expect:
      success: true
"""


def test_artifact_fake_marker_on_non_first_line_is_invalid(tmp_path):
    """The marker sits on line 2 — only a MULTILINE / per-line scan finds
    it.  Family is agent-surface, so ONLY the artifact rule can fire."""
    artifact = tmp_path / "out.md"
    body = FAKE_ARTIFACT_SCENARIO.format(artifact=artifact)
    _write(tmp_path, "f.yaml", body)
    sc = run_scenarios(
        tmp_path, env=_fake_env(), persist=False
    ).scenarios[0]
    assert sc.status == "invalid"


def test_artifact_fake_marker_not_suppressed_by_allow_fake(tmp_path):
    """Positive fake content is unambiguous evidence — the contract-only
    escape hatch cannot wave it away."""
    artifact = tmp_path / "out.md"
    body = FAKE_ARTIFACT_SCENARIO.format(artifact=artifact)
    _write(tmp_path, "f.yaml", body)
    sc = run_scenarios(
        tmp_path, env=_fake_env(), persist=False, allow_fake=True
    ).scenarios[0]
    assert sc.status == "invalid"


def test_artifact_marker_without_fake_is_not_invalid(tmp_path):
    """Control: the marker is only a fake signal when fake is active."""
    artifact = tmp_path / "out.md"
    body = FAKE_ARTIFACT_SCENARIO.format(artifact=artifact)
    _write(tmp_path, "f.yaml", body)
    sc = run_scenarios(
        tmp_path, env=_no_fake_env(), persist=False
    ).scenarios[0]
    assert sc.status == "passed"


def test_clean_artifact_under_fake_is_not_invalid(tmp_path):
    """Control: a human-read artifact without the echo signature does not
    trip the marker check (the scenario is agent-surface)."""
    artifact = tmp_path / "out.md"
    body = FAKE_ARTIFACT_SCENARIO.format(artifact=artifact).replace(
        "[xx] fake translation echo", "a real translated line"
    )
    _write(tmp_path, "f.yaml", body)
    sc = run_scenarios(
        tmp_path, env=_fake_env(), persist=False
    ).scenarios[0]
    assert sc.status == "passed"


# ---------------------------------------------------------------------------
# Invalid is a distinct, honest verdict
# ---------------------------------------------------------------------------


def test_invalid_summary_names_fake_llm(tmp_path):
    _write(tmp_path, "p.yaml", PIPELINE_ANCHORLESS)
    sc = run_scenarios(tmp_path, env=_fake_env(), persist=False).scenarios[0]
    assert sc.status == "invalid"
    assert "fake" in sc.summary.lower()
    assert "invalid" in sc.summary.lower()


def test_invalid_does_not_run_into_failed(tmp_path):
    """invalid must not be conflated with failed or passed."""
    _write(tmp_path, "p.yaml", PIPELINE_ANCHORLESS)
    sc = run_scenarios(tmp_path, env=_fake_env(), persist=False).scenarios[0]
    assert sc.status not in ("passed", "failed", "unconfigured")


def _load_report_module():
    spec = importlib.util.spec_from_file_location(
        "validation_report_under_test_r07",
        _REPO_ROOT / "scripts" / "validation" / "validation_report.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_invalid_does_not_render_green_in_report():
    """The director report must render invalid distinctly — never GREEN."""
    report = _load_report_module()
    assert report._verdict_marker("invalid") == "INVALID"
    assert "INVALID" not in report.GREEN_STATUSES
