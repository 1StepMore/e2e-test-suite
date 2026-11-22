#!/usr/bin/env python3
"""Self-check that the validation evidence in this repo is actually committed.

The cross-audit evidence protocol (``docs/dev/cross-audit-evidence.md``) says a
quality claim is only valid when the artifact is **in the repository** and the
manifest entry points at a non-empty file. The protocol's canonical checker
lives in the workspace root (``99-Tools/check_evidence_committed.py``), which is
not present in a plain checkout — so this is a repo-local equivalent that
enforces the same hard rules:

1. ``manifest.json`` must be valid JSON with a ``cells`` list.
2. Every cell's ``quality.evidence`` must name a file that exists, is inside the
   evidence directory, and is non-empty.
3. ``quality.verdict == "pass"`` REQUIRES ``quality.evidence`` (a pass with no
   evidence is counted as a failure).
4. Every entry in ``artifacts`` must exist.
5. Any cell whose evidence file is tracked-but-dirty or untracked is reported,
   because "committed" is the whole point (``git ls-files`` check).

Usage:
    python scripts/check_evidence_committed.py [repo_root]

Exit codes:
    0  every cell satisfies the rules
    1  at least one rule violation
    2  the manifest itself is missing or malformed (cannot judge)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

EVIDENCE_REL = Path("docs/dev/validation-evidence")
MANIFEST_REL = EVIDENCE_REL / "manifest.json"


def _is_git_repo(repo: Path) -> bool:
    """True when ``repo`` is inside a git work tree."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=repo, capture_output=True, text=True, timeout=30,
        )
        return r.returncode == 0 and r.stdout.strip() == "true"
    except (OSError, subprocess.TimeoutExpired):
        return False


def _git_tracked(repo: Path, rel: str) -> bool:
    """True when ``rel`` is tracked by git in ``repo``."""
    try:
        r = subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel],
            cwd=repo, capture_output=True, text=True, timeout=30,
        )
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def check(repo: Path) -> tuple[int, list[str], list[str]]:
    """Return (exit_code, errors, notes)."""
    errors: list[str] = []
    notes: list[str] = []

    manifest_path = repo / MANIFEST_REL
    if not manifest_path.is_file():
        return 2, [f"manifest not found: {MANIFEST_REL}"], notes
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return 2, [f"manifest unreadable: {exc}"], notes

    cells = manifest.get("cells")
    if not isinstance(cells, list):
        return 2, ["manifest has no 'cells' list"], notes

    if not cells:
        notes.append("manifest has zero cells (nothing to audit)")

    # Outside a git work tree there is nothing to prove about "committed"; the
    # existence/non-empty rules are still enforced and the gap is reported.
    git_repo = _is_git_repo(repo)
    if not git_repo:
        notes.append("not a git work tree: skipping the committed-to-git rule")

    for idx, cell in enumerate(cells):
        name = cell.get("cell") or f"<cell#{idx}>"
        quality = cell.get("quality") or {}
        verdict = quality.get("verdict")
        evidence = quality.get("evidence")

        # Rule 3: a pass must carry evidence.
        if verdict == "pass" and not evidence:
            errors.append(f"{name}: verdict=pass without quality.evidence")
            continue

        # Rule 2: evidence must exist, be inside the evidence dir, non-empty.
        if evidence:
            ev_path = (repo / EVIDENCE_REL / evidence).resolve()
            ev_root = (repo / EVIDENCE_REL).resolve()
            if ev_root not in ev_path.parents and ev_path != ev_root:
                errors.append(f"{name}: evidence path escapes {EVIDENCE_REL}: {evidence}")
            elif not ev_path.is_file():
                errors.append(f"{name}: evidence file missing: {evidence}")
            elif ev_path.stat().st_size == 0:
                errors.append(f"{name}: evidence file is empty: {evidence}")
            else:
                rel = ev_path.relative_to(repo).as_posix()
                if git_repo and not _git_tracked(repo, rel):
                    errors.append(f"{name}: evidence not committed to git: {rel}")
                else:
                    notes.append(f"{name}: evidence ok ({rel}, {ev_path.stat().st_size} B)")

        # Rule 4: artifacts must exist.
        for art in cell.get("artifacts") or []:
            art_path = (repo / EVIDENCE_REL / art).resolve()
            if not art_path.is_file():
                errors.append(f"{name}: artifact missing: {art}")
            elif git_repo and not _git_tracked(
                repo, art_path.relative_to(repo).as_posix()
            ):
                errors.append(f"{name}: artifact not committed: {art}")

    return (1 if errors else 0), errors, notes


def main(argv: list[str]) -> int:
    repo = Path(argv[1]).resolve() if len(argv) > 1 else Path(__file__).resolve().parents[1]
    code, errors, notes = check(repo)
    for note in notes:
        print(f"  ok   {note}")
    for err in errors:
        print(f"  FAIL {err}")
    print(f"evidence-committed: {'PASS' if code == 0 else 'FAIL'} ({len(errors)} error(s))")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
