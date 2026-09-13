"""Tests for omni_mcp.validation.family (R-07 shared family derivation).

``family_of`` and the five symbols it references were extracted from
``scripts/validation/validation_report.py`` into the real package
``omni_mcp.validation.family`` so BOTH enforcement (``engine.py``) and
reporting (``scripts/validation/validation_report.py``) import the same
rule — never a cross-package import from ``scripts/`` (which is not a
package).

These tests lock the extraction: the prefix-first / anchor-fallback rule,
the anchor id parsing, and the two anchor helpers the engine uses to make
its fake-invalid decision.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from omni_mcp.validation.family import (
    AGENT_SURFACE_ANCHORS,
    AGENT_USER,
    HUMAN_QUALITY,
    HUMAN_QUALITY_ANCHORS,
    _anchor_of,
    all_steps_agent_surface,
    family_of,
    has_human_quality_anchor,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# family_of — prefix first, then anchors, else the agent-user default
# ---------------------------------------------------------------------------


def test_tool_prefix_is_agent_user_by_prefix():
    assert family_of("tool-opp-extract", []) == (AGENT_USER, "prefix")


def test_pipeline_prefix_is_human_quality_by_prefix():
    assert family_of("pipeline-docx-md-docx", []) == (HUMAN_QUALITY, "prefix")


def test_human_quality_anchor_wins_over_default():
    steps = [{"standard": "STANDARDS.md#lqa-threshold"}]
    assert family_of("some-unknown-name", steps) == (HUMAN_QUALITY, "standard")


def test_agent_surface_anchor_derives_agent_user():
    steps = [{"standard": "STANDARDS.md#exit-codes"}]
    assert family_of("some-unknown-name", steps) == (AGENT_USER, "standard")


def test_human_quality_anchor_beats_agent_surface_anchor():
    # Any HUMAN-QUALITY anchor classifies the scenario human-quality, even
    # when other steps cite AGENT-SURFACE anchors.
    steps = [
        {"standard": "STANDARDS.md#exit-codes"},
        {"standard": "STANDARDS.md#cjk-density"},
    ]
    assert family_of("mixed", steps) == (HUMAN_QUALITY, "standard")


def test_no_prefix_no_anchor_is_agent_user_default():
    assert family_of("plain-scenario", []) == (AGENT_USER, "default")


def test_prefix_beats_anchor_fallback():
    # The prefix is the primary rule; anchors only apply without a prefix.
    steps = [{"standard": "STANDARDS.md#lqa-threshold"}]
    assert family_of("tool-opp-x", steps) == (AGENT_USER, "prefix")


# ---------------------------------------------------------------------------
# _anchor_of
# ---------------------------------------------------------------------------


def test_anchor_of_splits_on_hash():
    assert _anchor_of("STANDARDS.md#exit-codes") == "exit-codes"


def test_anchor_of_returns_bare_when_no_hash():
    assert _anchor_of("exit-codes") == "exit-codes"


def test_anchor_of_none_and_empty():
    assert _anchor_of(None) is None
    assert _anchor_of("") is None


# ---------------------------------------------------------------------------
# Anchor sets + engine helpers
# ---------------------------------------------------------------------------


def test_anchor_sets_are_disjoint_and_complete():
    assert AGENT_SURFACE_ANCHORS == {
        "tool-contract",
        "json-parseable",
        "error-clarity",
        "path-security",
        "exit-codes",
    }
    assert HUMAN_QUALITY_ANCHORS == {
        "lqa-threshold",
        "para-ratio",
        "cjk-density",
        "punct-hygiene",
        "drawing-count",
        "opens-docx",
    }
    assert AGENT_SURFACE_ANCHORS.isdisjoint(HUMAN_QUALITY_ANCHORS)


def test_has_human_quality_anchor_true_when_any_step_cites_one():
    steps = [
        {"standard": "STANDARDS.md#exit-codes"},
        {"standard": "STANDARDS.md#para-ratio"},
    ]
    assert has_human_quality_anchor(steps) is True


def test_has_human_quality_anchor_false_for_agent_surface_only():
    steps = [{"standard": "STANDARDS.md#exit-codes"}, {"standard": None}]
    assert has_human_quality_anchor(steps) is False


def test_all_steps_agent_surface_requires_every_step():
    steps = [
        {"standard": "STANDARDS.md#exit-codes"},
        {"standard": "STANDARDS.md#tool-contract"},
    ]
    assert all_steps_agent_surface(steps) is True


def test_all_steps_agent_surface_anchorless_is_ineligible():
    steps = [{"standard": "STANDARDS.md#exit-codes"}, {"standard": None}]
    assert all_steps_agent_surface(steps) is False


def test_all_steps_agent_surface_non_vacuous_for_empty_steps():
    assert all_steps_agent_surface([]) is False


def test_all_steps_agent_surface_human_quality_anchor_is_ineligible():
    steps = [{"standard": "STANDARDS.md#lqa-threshold"}]
    assert all_steps_agent_surface(steps) is False


# ---------------------------------------------------------------------------
# Reporting imports the package, never the other way round
# ---------------------------------------------------------------------------


def _load_report_module():
    """Load ``scripts/validation/validation_report.py`` by absolute path
    (``scripts/`` is not a package — same mechanism cli.py uses)."""
    spec = importlib.util.spec_from_file_location(
        "validation_report_under_test",
        _REPO_ROOT / "scripts" / "validation" / "validation_report.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_report_uses_the_package_family_of():
    report = _load_report_module()
    # Identity, not equality: the report re-exports the ONE shared rule the
    # engine enforces, so reporting and enforcement can never drift.
    assert report.family_of is family_of
    assert report.AGENT_USER == AGENT_USER
    assert report.HUMAN_QUALITY == HUMAN_QUALITY
    assert report.AGENT_SURFACE_ANCHORS == AGENT_SURFACE_ANCHORS
    assert report.HUMAN_QUALITY_ANCHORS == HUMAN_QUALITY_ANCHORS
