"""family.py — the ONE family/anchor classification rule (R-07).

Derived from the original ``validation_report.py`` implementation so that
enforcement (:mod:`omni_mcp.validation.engine`) and reporting
(``scripts/validation/validation_report.py``) share a single rule and can
never drift.  ``scripts/`` is not a package, so the report imports these
symbols FROM here — never the other way round.

Precedence (issue #205): **override -> declared ``level`` -> prefix ->
anchor -> default**.

- an explicit, lint-justified ``family_override`` (a scenario whose
  contract is agent-user but which cites a human-quality anchor as an
  *instrument*) wins;
- otherwise the scenario's declared ``level:`` is authoritative — it is
  what the scenario is FOR, and both enforcement
  (``engine._fake_llm_reason``) and reporting read it;
- the prefix/anchor derivation is the **fallback** for records that carry
  no ``level`` (older ``scenarios.json``) and the **cross-check** the
  contract lint compares ``level`` against:
  - a ``tool-*`` scenario derives ``AGENT_USER``;
  - a ``pipeline-*`` scenario derives ``HUMAN_QUALITY``;
  - otherwise the steps' ``standard: STANDARDS.md#<anchor>`` citations
    decide: any HUMAN-QUALITY anchor => ``HUMAN_QUALITY``, else any
    AGENT-SURFACE anchor => ``AGENT_USER``, else the ``AGENT_USER``
    default.

Only Python 3.13 stdlib — no new dependencies.
"""

from __future__ import annotations

from typing import Any

AGENT_USER = "agent-user conformance"
HUMAN_QUALITY = "human-quality conformance"

#: The two ``level:`` values a scenario may declare (loader.LEVELS mirrors
#: this pair; duplicated as literals to keep this module import-free).
LEVEL_AGENT_USER = "agent-user"
LEVEL_HUMAN_QUALITY = "human-quality"

#: ``level:`` / ``family_override:`` value -> verdict family.
_LEVEL_TO_FAMILY: dict[str, str] = {
    LEVEL_AGENT_USER: AGENT_USER,
    LEVEL_HUMAN_QUALITY: HUMAN_QUALITY,
}

#: STANDARDS.md anchors by family (scenarios/STANDARDS.md §AGENT-SURFACE
#: and §HUMAN-QUALITY) — used when the scenario name has no prefix.
AGENT_SURFACE_ANCHORS = {
    "tool-contract",
    "json-parseable",
    "error-clarity",
    "path-security",
    "exit-codes",
    # Process-gating anchor: describes how a scenario is configured/run,
    # not what output quality it proves (STANDARDS.md §Scenario gating).
    "env-gate-semantics",
}
HUMAN_QUALITY_ANCHORS = {
    # Evidence-admissibility anchor: it governs whether a human-quality
    # verdict is admissible at all (STANDARDS.md §Evidence admissibility).
    "fallbacks-never-evidence",
    "lqa-threshold",
    "para-ratio",
    "cjk-density",
    "untranslated-units",
    "punct-hygiene",
    "drawing-count",
    "opens-docx",
}


def _anchor_of(standard: Any) -> str | None:
    """The anchor id of a ``STANDARDS.md#<anchor>`` citation, else None."""
    if not standard:
        return None
    s = str(standard)
    if "#" in s:
        return s.split("#", 1)[1].strip()
    return s.strip() or None


def family_of(
    name: str,
    steps: list[dict[str, Any]],
    *,
    level: str | None = None,
    override: str | None = None,
) -> tuple[str, str]:
    """Derive the verdict family of a scenario.

    Returns ``(family, derivation)`` with derivation one of ``override`` /
    ``level`` / ``prefix`` / ``standard`` / ``default`` (recorded in
    report.json so the applied rule stays auditable).

    Call with ``(name, steps)`` only to get the *derived* family the lint
    compares a declared ``level`` against.
    """
    if override in _LEVEL_TO_FAMILY:
        return _LEVEL_TO_FAMILY[override], "override"
    if level in _LEVEL_TO_FAMILY:
        return _LEVEL_TO_FAMILY[level], "level"
    if name.startswith("tool-"):
        return AGENT_USER, "prefix"
    if name.startswith("pipeline-"):
        return HUMAN_QUALITY, "prefix"
    anchors = [_anchor_of(s.get("standard")) for s in steps]
    for a in anchors:
        if a in HUMAN_QUALITY_ANCHORS:
            return HUMAN_QUALITY, "standard"
    for a in anchors:
        if a in AGENT_SURFACE_ANCHORS:
            return AGENT_USER, "standard"
    return AGENT_USER, "default"


def derived_level(name: str, steps: list[dict[str, Any]]) -> str:
    """The ``level`` implied by the prefix/anchor derivation (lint cross-check)."""
    family, _ = family_of(name, steps)
    return LEVEL_HUMAN_QUALITY if family == HUMAN_QUALITY else LEVEL_AGENT_USER


def has_human_quality_anchor(steps: list[dict[str, Any]]) -> bool:
    """True when ANY step cites a HUMAN-QUALITY anchor — the anchor half
    of R-07's OR condition (a non-pipeline scenario can still be quality
    evidence)."""
    return any(
        _anchor_of(s.get("standard")) in HUMAN_QUALITY_ANCHORS for s in steps
    )


def all_steps_agent_surface(steps: list[dict[str, Any]]) -> bool:
    """True only when EVERY step cites an AGENT-SURFACE anchor.

    The ``--allow-fake`` contract-only escape hatch is non-vacuous by
    design: an anchor-less step — or any HUMAN-QUALITY citation — makes the
    scenario ineligible.  An empty step list is ineligible too.
    """
    if not steps:
        return False
    return all(
        _anchor_of(s.get("standard")) in AGENT_SURFACE_ANCHORS for s in steps
    )
