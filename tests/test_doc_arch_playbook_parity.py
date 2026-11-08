"""Cross-repo parity for the agent-era documentation playbook (e2e#254).

Six repositories carry ``docs/dev/agent-era-doc-architecture.md``
byte-identical (canonical copy: AutoInfo; protocol: e2e-test-suite#254,
playbook §7). This repo can see its own copy plus the three nested module
checkouts (OPP/OL/ORF — gitignored working copies) — those four must be
byte-identical. AutoInfo/AutoMedia are not reachable from here; each pins
its own copy via its ``scripts/doc_inventory.py`` ``DOC_ARCH_SHA256``.

Drift defense in depth:
* each repo's ``doc_inventory --check`` pins the copy's hash against a
  constant (suite gate 15; OPP/OL/ORF equivalent, strict missing=FAIL);
* this test pins the suite copy's hash and, whenever module checkouts are
  visible, fails on any copy that is missing or differs.

Change rule: a playbook revision is a six-repo sync plus six pin bumps —
edit the canonical copy, re-sync, bump every pin together.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import scripts.doc_inventory as di

ROOT = Path(__file__).resolve().parents[1]

PLAYBOOK = Path("docs") / "dev" / "agent-era-doc-architecture.md"

#: Same reachability markers as the doc_inventory shared resolution block.
MODULE_MARKERS = {
    "opp": ("Omni_Pre_Processor", "Omni_Pre_Processor/src/opp"),
    "ol": ("Omni_Localizer", "Omni_Localizer/src/ol_md"),
    "orf": ("Omni_Re_Formatter", "Omni_Re_Formatter/src/orf"),
}


def test_suite_playbook_copy_matches_pinned_hash():
    """The suite's own copy must exist and match DOC_ARCH_SHA256 (runs in
    every checkout, CI included — no module repos needed)."""
    path = ROOT / PLAYBOOK
    assert path.is_file(), (
        f"{PLAYBOOK} missing: the six-repo synced playbook (e2e-test-suite#254) "
        "must exist in this repo — sync it from the canonical copy (AutoInfo)"
    )
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual == di.DOC_ARCH_SHA256, (
        f"{PLAYBOOK} drifted from DOC_ARCH_SHA256 (got {actual}). "
        "跨仓同步副本与钉住版本不同，改版需六仓同传: edit the canonical copy "
        "(AutoInfo), re-sync all six repositories, bump every pin together — "
        "see https://github.com/1StepMore/e2e-test-suite/issues/254"
    )


def test_playbook_copies_byte_identical_across_checkouts():
    """Every visible module checkout must carry the playbook byte-identical
    to the suite's copy. Skips entirely on a fresh clone (no module
    checkouts — e.g. CI); a visible checkout WITHOUT the copy is a failure
    (the wave has not landed there), not a skip."""
    suite_path = ROOT / PLAYBOOK
    assert suite_path.is_file(), f"{PLAYBOOK} missing in the suite repo"
    suite_bytes = suite_path.read_bytes()

    visible = {
        name: (ROOT / dirname)
        for name, (dirname, marker) in MODULE_MARKERS.items()
        if (ROOT / marker).is_dir()
    }
    if not visible:
        pytest.skip(
            "no module checkouts in this workspace (fresh clone / CI) — "
            "nothing to compare; per-repo hash pins still guard each copy"
        )

    problems: list[str] = []
    for name, checkout in sorted(visible.items()):
        copy = checkout / PLAYBOOK
        if not copy.is_file():
            problems.append(
                f"{name}: checkout visible at {checkout} but {PLAYBOOK} is "
                "missing — the six-repo wave has not landed there "
                "(e2e-test-suite#254)"
            )
            continue
        if copy.read_bytes() != suite_bytes:
            problems.append(
                f"{name}: playbook copy at {copy} differs from the suite copy "
                "— a revision must be synced to all six repositories "
                "(e2e-test-suite#254)"
            )
    assert not problems, "\n".join(problems)
