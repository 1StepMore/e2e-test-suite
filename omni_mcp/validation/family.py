"""family.py — the ONE family/anchor classification rule (R-07).

Derived from the original ``validation_report.py`` implementation so that
enforcement (:mod:`omni_mcp.validation.engine`) and reporting
(``scripts/validation/validation_report.py``) share a single rule and can
never drift.  ``scripts/`` is not a package, so the report imports these
symbols FROM here — never the other way round.

Classification is **prefix-first, anchor-fallback**:

- a ``tool-*`` scenario is ``AGENT_USER``;
- a ``pipeline-*`` scenario is ``HUMAN_QUALITY``;
- otherwise the steps' ``standard: STANDARDS.md#<anchor>`` citations
  decide: any HUMAN-QUALITY anchor => ``HUMAN_QUALITY``, else any
  AGENT-SURFACE anchor => ``AGENT_USER``, else the ``AGENT_USER`` default.

Only Python 3.13 stdlib — no new dependencies.
"""

from __future__ import annotations

from typing import Any

AGENT_USER = "agent-user conformance"
HUMAN_QUALITY = "human-quality conformance"

#: STANDARDS.md anchors by family (scenarios/STANDARDS.md §AGENT-SURFACE
#: and §HUMAN-QUALITY) — used when the scenario name has no prefix.
AGENT_SURFACE_ANCHORS = {
    "tool-contract",
    "json-parseable",
    "error-clarity",
    "path-security",
    "exit-codes",
}
HUMAN_QUALITY_ANCHORS = {
    "lqa-threshold",
    "para-ratio",
    "cjk-density",
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


def family_of(name: str, steps: list[dict[str, Any]]) -> tuple[str, str]:
    """Derive the verdict family of a scenario: name prefix, else the
    steps' standard anchors, else the agent-user default.

    Returns ``(family, derivation)`` where derivation is one of
    ``prefix`` / ``standard`` / ``default`` (recorded in report.json so
    the rule that was applied is auditable).
    """
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
