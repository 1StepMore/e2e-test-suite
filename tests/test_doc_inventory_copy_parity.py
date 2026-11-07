"""The three module ``doc_inventory.py`` copies must share one cross-repo block.

OPP, OL and ORF each own a copy of ``scripts/doc_inventory.py`` (separate git
repos; no shared package is installable from all three). The cross-repo
resolution logic therefore lives in a byte-identical block delimited by the
BEGIN/END markers, and this test fails the moment one copy drifts.

Change rule: edit the block in every copy that is checked out, then re-run the
three ``--check`` gates. See ``docs/dev/doc-inventory-copies.md``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

COPIES = {
    "ol": ROOT / "Omni_Localizer" / "scripts" / "doc_inventory.py",
    "opp": ROOT / "Omni_Pre_Processor" / "scripts" / "doc_inventory.py",
    "orf": ROOT / "Omni_Re_Formatter" / "scripts" / "doc_inventory.py",
}

BEGIN = "# ── BEGIN SHARED CROSS-REPO RESOLUTION"
END = "# ── END SHARED CROSS-REPO RESOLUTION"


def _block_lines(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    begin = [i for i, line in enumerate(lines) if line.startswith(BEGIN)]
    end = [i for i, line in enumerate(lines) if line.startswith(END)]
    assert len(begin) == 1, f"{path}: expected exactly one BEGIN marker, found {len(begin)}"
    assert len(end) == 1, f"{path}: expected exactly one END marker, found {len(end)}"
    assert begin[0] < end[0], f"{path}: END marker precedes BEGIN marker"
    return lines[begin[0]: end[0] + 1]


def test_doc_inventory_checked_copy_parity():
    present = {name: path for name, path in COPIES.items() if path.is_file()}
    if len(present) < 2:
        pytest.skip(
            "module checkouts not present in this workspace: "
            + ", ".join(sorted(set(COPIES) - set(present)))
        )

    blocks = {name: _block_lines(path) for name, path in present.items()}
    reference_name, reference = next(iter(blocks.items()))
    for name, block in blocks.items():
        if block == reference:
            continue
        first_diff = next(
            (
                f"line {offset + 1}: {reference[offset]!r} != {block[offset]!r}"
                for offset in range(min(len(reference), len(block)))
                if reference[offset] != block[offset]
            ),
            f"block length differs: {len(reference)} != {len(block)}",
        )
        pytest.fail(
            f"doc_inventory cross-repo block drifted: {reference_name} vs {name}: {first_diff}. "
            "Edit the block in every copy and re-run each module's "
            "`python scripts/doc_inventory.py --check`."
        )

    assert len(reference) > 100, f"shared block looks truncated ({len(reference)} lines)"
