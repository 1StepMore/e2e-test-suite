"""The one rule for "which files are scenario files" (issue #223 P2.1).

Before this module existed, the recursive-glob rule was re-implemented in
``scripts/doc_inventory.py`` (claim derivation), ``scripts/validation/
coverage_audit.py`` (tool coverage, twice) and ``omni_mcp/validation/
loader.py`` (execution) — and the copies disagreed on dot-directory
filtering. Every suite-side consumer now derives its file set here so the
coverage audit and the doc-truth gate can never disagree about what the
scenario library contains.

``omni_mcp/validation/loader.py`` keeps its own copy on purpose: the MCP
server may be started from an arbitrary working directory, where importing
across into ``scripts.*`` is not guaranteed to resolve. If you change the
rule here, change it there too (a comment at the site says the same).
"""
from __future__ import annotations

from pathlib import Path


def iter_scenario_yamls(scenarios_dir: Path) -> list[Path]:
    """Sorted ``*.yaml`` files under *scenarios_dir*, dot-dirs excluded.

    The canonical scenario-file rule: recursive glob over the scenarios
    root, sorted for deterministic ordering, hidden/dot directories
    (``.git/``, ``.hidden/``) and non-files excluded.
    """
    sd = Path(scenarios_dir)
    if not sd.is_dir():
        return []
    return sorted(
        p
        for p in sd.rglob("*.yaml")
        if p.is_file() and not any(part.startswith(".") for part in p.parts)
    )
