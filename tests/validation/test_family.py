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

from pathlib import Path

from omni_mcp.validation.family import (
    AGENT_SURFACE_ANCHORS,
    AGENT_USER,
    HUMAN_QUALITY,
    HUMAN_QUALITY_ANCHORS,
    _anchor_of,
    all_steps_agent_surface,
    derived_level,
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


def test_fallbacks_never_evidence_is_human_quality_anchor():
    steps = [{"standard": "STANDARDS.md#fallbacks-never-evidence"}]
    assert family_of("some-unknown-name", steps) == (HUMAN_QUALITY, "standard")


def test_agent_surface_anchor_derives_agent_user():
    steps = [{"standard": "STANDARDS.md#exit-codes"}]
    assert family_of("some-unknown-name", steps) == (AGENT_USER, "standard")


def test_env_gate_semantics_is_agent_surface_anchor():
    steps = [{"standard": "STANDARDS.md#env-gate-semantics"}]
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
        "env-gate-semantics",
    }
    assert HUMAN_QUALITY_ANCHORS == {
        "fallbacks-never-evidence",
        "lqa-threshold",
        "para-ratio",
        "cjk-density",
        "untranslated-units",
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
    """Load the report module through the scripts package (issue #223 P2.1)."""
    from scripts.validation import validation_report

    return validation_report


def test_report_uses_the_package_family_of():
    report = _load_report_module()
    # Identity, not equality: the report re-exports the ONE shared rule the
    # engine enforces, so reporting and enforcement can never drift.
    assert report.family_of is family_of
    assert report.AGENT_USER == AGENT_USER
    assert report.HUMAN_QUALITY == HUMAN_QUALITY
    assert report.AGENT_SURFACE_ANCHORS == AGENT_SURFACE_ANCHORS
    assert report.HUMAN_QUALITY_ANCHORS == HUMAN_QUALITY_ANCHORS


# ---------------------------------------------------------------------------
# Issue #205 — the declared level is authoritative, override is the escape
# hatch, and the derivation stays available as the lint cross-check
# ---------------------------------------------------------------------------


def test_untranslated_units_is_human_quality_anchor():
    steps = [{"standard": "STANDARDS.md#untranslated-units"}]
    assert family_of("md-not-pipeline-named", steps) == (HUMAN_QUALITY, "standard")
    assert has_human_quality_anchor(steps) is True


def test_declared_level_beats_the_name_prefix():
    assert family_of("tool-opp-x", [], level="human-quality") == (
        HUMAN_QUALITY,
        "level",
    )
    assert family_of("pipeline-x", [], level="agent-user") == (AGENT_USER, "level")


def test_family_override_beats_declared_level():
    assert family_of(
        "pipeline-x", [], level="human-quality", override="agent-user"
    ) == (AGENT_USER, "override")


def test_derivation_ignores_level_and_override():
    # Called without level/override, family_of is the DERIVED family the
    # lint compares `level` against — the prefix rule must still apply.
    assert family_of("pipeline-x", []) == (HUMAN_QUALITY, "prefix")
    assert family_of("tool-opp-x", []) == (AGENT_USER, "prefix")


def test_derived_level_maps_family_back_to_the_level_vocabulary():
    assert derived_level("pipeline-x", []) == "human-quality"
    assert derived_level("tool-opp-x", []) == "agent-user"
    steps = [{"standard": "STANDARDS.md#drawing-count"}]
    assert derived_level("some-name", steps) == "human-quality"
