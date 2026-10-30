#!/usr/bin/env python3
"""Sync version tables in top-level docs from pyproject.toml.

Single source of truth: each submodule's `pyproject.toml` + the suite's
own `pyproject.toml`. This script rewrites the version numbers in:

- README.md (env table + Pinned combo line)
- AGENTS.md (Current Versions table + Pinned combo line)
- docs/ARCHITECTURE.md (Current version table)
- PROJECT_STATUS.md (Current versions table)

(COMPATIBILITY.md was dropped 2026-10-30 — append-only history matrix,
no syncable shape; see the comment on TARGETS.)

Run directly: `python scripts/sync_version_docs.py`
Pre-commit: see `.pre-commit-config.yaml` `omni-version-docs-sync` hook.

Idempotent: re-running with no version changes is a no-op (no file writes).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SUITE_ROOT = Path(__file__).resolve().parent.parent

# Targets — the four pyproject.toml files that own the version numbers.
VERSION_SOURCES = {
    "suite": SUITE_ROOT / "pyproject.toml",
    "opp": SUITE_ROOT / "Omni_Pre_Processor" / "pyproject.toml",
    "ol": SUITE_ROOT / "Omni_Localizer" / "pyproject.toml",
    "orf": SUITE_ROOT / "Omni_Re_Formatter" / "pyproject.toml",
}

# Files we touch, with the patterns we update inside each.
TARGETS: list[Path] = [
    SUITE_ROOT / "README.md",
    SUITE_ROOT / "AGENTS.md",
    # COMPATIBILITY.md removed from TARGETS 2026-10-30 (plan PR3 #5): its
    # syncable shape (the `# X.Y.Z` example commands) no longer exists — the
    # file is now an append-only compatibility MATRIX whose rows are
    # historical records that must NOT be rewritten by a version sync. With
    # no pattern matching it, the old TARGETS entry was a permanent vacuous
    # pass; the new zero-match guard in main() would have failed on it.
    # #215 P0.1: both files advertised versions two releases stale because
    # they were outside this gate. Keep them inside it (rather than deleting
    # the tables) so the quick-context views stay truthful.
    SUITE_ROOT / "docs" / "ARCHITECTURE.md",
    SUITE_ROOT / "PROJECT_STATUS.md",
]


def read_version(pyproject_path: Path) -> str:
    """Read the `version = "X.Y.Z"` line from a pyproject.toml."""
    for line in pyproject_path.read_text(encoding="utf-8").splitlines():
        if re.match(r"^version\s*=", line):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise ValueError(f"version not found in {pyproject_path}")


def _semver_pattern() -> re.Pattern[str]:
    # Match a bare X.Y.Z (no leading/trailing word chars) so we don't
    # accidentally touch strings like "v0.6.3+ in OPP main".
    return re.compile(r"(?<![A-Za-z0-9_])(\d+\.\d+\.\d+)(?![A-Za-z0-9_])")


def _replacements(v: dict[str, str]) -> list[tuple[re.Pattern[str], str]]:
    """Return the regex-substitution pairs to apply to every doc target.

    The patterns are ordered: most-specific first, so e.g. the
    "Pinned combo" lines get rewritten before any bare-version
    regex would touch one of the four numbers inside them.
    """
    return [
        # README.md env table — bold version in each component row.
        # Pattern keeps the surrounding `** ... **` markers and the
        # subsequent ` @ <sha>` (whatever SHA the human pasted).
        (re.compile(
            r"(\| OPP \| `Omni_Pre_Processor` \| \*\*)\d+\.\d+\.\d+(\*\* @ `[^`]+` \|)"
        ), rf"\g<1>{v['opp']}\g<2>"),
        (re.compile(
            r"(\| OL \| `Omni_Localizer` \| \*\*)\d+\.\d+\.\d+(\*\* @ `[^`]+` \|)"
        ), rf"\g<1>{v['ol']}\g<2>"),
        (re.compile(
            r"(\| ORF \| `Omni_Re_Formatter` \| \*\*)\d+\.\d+\.\d+(\*\* @ `[^`]+` \|)"
        ), rf"\g<1>{v['orf']}\g<2>"),
        (re.compile(
            r"(\| Suite \| `\.\` \| \*\*)\d+\.\d+\.\d+(\*\* @ `[^`]+` \|)"
        ), rf"\g<1>{v['suite']}\g<2>"),

        # README.md "Pinned combo: opp X + ol Y + orf Z + suite W" line.
        (re.compile(
            r"(\*\*Pinned combo\*\*: opp )\d+\.\d+\.\d+"
            r"( \+ ol )\d+\.\d+\.\d+"
            r"( \+ orf )\d+\.\d+\.\d+"
            r"( \+ suite )\d+\.\d+\.\d+"
        ), rf"\g<1>{v['opp']}\g<2>{v['ol']}\g<3>{v['orf']}\g<4>{v['suite']}"),

        # AGENTS.md "Current Versions" table — version is the second column
        # in each row, between the component name and the human-curated note.
        (re.compile(
            r"(\| Omni_Suite \(this repo\) \| )\d+\.\d+\.\d+( \| )"
        ), rf"\g<1>{v['suite']}\g<2>"),
        (re.compile(
            r"(\| Omni_Pre_Processor \| )\d+\.\d+\.\d+( \| )"
        ), rf"\g<1>{v['opp']}\g<2>"),
        (re.compile(
            r"(\| Omni_Localizer \| )\d+\.\d+\.\d+( \| )"
        ), rf"\g<1>{v['ol']}\g<2>"),
        (re.compile(
            r"(\| Omni_Re_Formatter \| )\d+\.\d+\.\d+( \| )"
        ), rf"\g<1>{v['orf']}\g<2>"),

        # AGENTS.md "Pinned combo (last tested)" line.
        (re.compile(
            r"(\*\*Pinned combo \(last tested\)\*\*: opp )\d+\.\d+\.\d+"
            r"( \+ ol )\d+\.\d+\.\d+"
            r"( \+ orf )\d+\.\d+\.\d+"
            r"( \+ suite )\d+\.\d+\.\d+"
        ), rf"\g<1>{v['opp']}\g<2>{v['ol']}\g<3>{v['orf']}\g<4>{v['suite']}"),

        # COMPATIBILITY.md "How to check installed versions" — the
        # `# X.Y.Z` comment after each `python -c "..."` command.
        (re.compile(
            r'(python -c "import ol; print\(\'OL\', ol\.__version__\)"\s+# )\d+\.\d+\.\d+'
        ), rf"\g<1>{v['ol']}"),
        (re.compile(
            r'(python -c "import opp; print\(\'OPP\', opp\.__version__\)"\s+# )\d+\.\d+\.\d+'
        ), rf"\g<1>{v['opp']}"),
        (re.compile(
            r'(python -c "import orf; print\(\'ORF\', orf\.__version__\)"\s+# )\d+\.\d+\.\d+'
        ), rf"\g<1>{v['orf']}"),
        (re.compile(
            r"(omni-suite --version\s+# )\d+\.\d+\.\d+"
        ), rf"\g<1>{v['suite']}"),

        # --- Current doc shapes (v-prefixed rows, no SHA column) -------------
        # The patterns above target an older `**X.Y.Z** @ \`sha\`` table layout.
        # The docs were since restructured to `vX.Y.Z` rows with no SHA column
        # and no "Pinned combo" line. Without these, every replacement above
        # matched nothing and --check reported "in sync" while the tables still
        # advertised the previous release.
        #
        # README.md 环境说明 table: | OPP | `Omni_Pre_Processor/` | v0.9.1 |
        (re.compile(
            r"(\| OPP \| `Omni_Pre_Processor/` \| v)\d+\.\d+\.\d+( \|)"
        ), rf"\g<1>{v['opp']}\g<2>"),
        (re.compile(
            r"(\| OL \| `Omni_Localizer/` \| v)\d+\.\d+\.\d+( \|)"
        ), rf"\g<1>{v['ol']}\g<2>"),
        (re.compile(
            r"(\| ORF \| `Omni_Re_Formatter/` \| v)\d+\.\d+\.\d+( \|)"
        ), rf"\g<1>{v['orf']}\g<2>"),
        (re.compile(
            r"(\| Omni_Suite \| `\./` \| v)\d+\.\d+\.\d+( \|)"
        ), rf"\g<1>{v['suite']}\g<2>"),

        # AGENTS.md "Current Versions" table: | OPP | v0.9.1 | <note> |
        (re.compile(
            r"(\| Omni_Suite \| v)\d+\.\d+\.\d+( \|)"
        ), rf"\g<1>{v['suite']}\g<2>"),
        (re.compile(
            r"(\| OPP \| v)\d+\.\d+\.\d+( \|)"
        ), rf"\g<1>{v['opp']}\g<2>"),
        (re.compile(
            r"(\| OL \| v)\d+\.\d+\.\d+( \|)"
        ), rf"\g<1>{v['ol']}\g<2>"),
        (re.compile(
            r"(\| ORF \| v)\d+\.\d+\.\d+( \|)"
        ), rf"\g<1>{v['orf']}\g<2>"),

        # docs/ARCHITECTURE.md "Current version" table.
        # | OPP | 0.10.0 | `1StepMore/Omni_Pre_Processor` | ...
        (re.compile(
            r"(\| OPP \| )\d+\.\d+\.\d+( \| `1StepMore/Omni_Pre_Processor` \|)"
        ), rf"\g<1>{v['opp']}\g<2>"),
        (re.compile(
            r"(\| OL \| )\d+\.\d+\.\d+( \| `1StepMore/Omni_Localizer` \|)"
        ), rf"\g<1>{v['ol']}\g<2>"),
        (re.compile(
            r"(\| ORF \| )\d+\.\d+\.\d+( \| `1StepMore/Omni_Re_Formatter` \|)"
        ), rf"\g<1>{v['orf']}\g<2>"),
        (re.compile(
            r"(\| omni-suite \| )\d+\.\d+\.\d+( \|)"
        ), rf"\g<1>{v['suite']}\g<2>"),

        # PROJECT_STATUS.md "Current versions" table.
        # | OPP | **0.10.0** | Active | ...
        (re.compile(
            r"(\| OPP \| \*\*)\d+\.\d+\.\d+(\*\* \| Active \|)"
        ), rf"\g<1>{v['opp']}\g<2>"),
        (re.compile(
            r"(\| OL \| \*\*)\d+\.\d+\.\d+(\*\* \| Active \|)"
        ), rf"\g<1>{v['ol']}\g<2>"),
        (re.compile(
            r"(\| ORF \| \*\*)\d+\.\d+\.\d+(\*\* \| Active \|)"
        ), rf"\g<1>{v['orf']}\g<2>"),
        (re.compile(
            r"(\| Suite \| \*\*)\d+\.\d+\.\d+(\*\* \| Active \|)"
        ), rf"\g<1>{v['suite']}\g<2>"),

        # Summary lines: "v0.9.1 · v0.7.1 · v0.4.17 · v0.4.0" (OPP · OL · ORF · Suite)
        (re.compile(
            r"(?<![\d.])v\d+\.\d+\.\d+ · v\d+\.\d+\.\d+ · v\d+\.\d+\.\d+ · v\d+\.\d+\.\d+"
        ), f"v{v['opp']} · v{v['ol']} · v{v['orf']} · v{v['suite']}"),
    ]


def _apply(
    path: Path, replacements: list[tuple[re.Pattern[str], str]], *, dry_run: bool = False
) -> tuple[int, int]:
    """Return ``(real_changes, pattern_matches)`` for one target file.

    ``real_changes`` counts substitutions that produce a real diff (a
    pattern matching an already-current value is a no-op write, not a
    change).  ``pattern_matches`` counts every regex hit regardless of
    whether it changed anything — the vacuous-pass guard in ``main``
    needs this: when a doc's shape drifts so far that ZERO patterns
    match, ``--check`` used to report "in sync" while the tables
    advertised whatever they contained (the 2026-06 v0.9 incident
    described in ``_replacements``).

    If *dry_run* is True the file is never written to.
    """
    content = path.read_text(encoding="utf-8")
    new = content
    real_changes = 0
    matched = 0
    for pattern, replacement in replacements:
        # Compare per-pattern so we only credit substitutions where the
        # replacement differs from the matched text.
        def _count(m: re.Match[str], replacement: str = replacement) -> str:
            nonlocal real_changes, matched
            matched += 1
            expanded = m.expand(replacement)
            if m.group(0) != expanded:
                real_changes += 1
            return expanded

        new = pattern.sub(_count, new)
    if new != content and not dry_run:
        path.write_text(new, encoding="utf-8")
    return real_changes, matched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="Exit non-zero if any doc would change. Used by pre-commit.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report what would change without writing. Exits 1 if changes are needed.",
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Same as --check (alias).",
    )
    args = parser.parse_args()

    versions = {key: read_version(path) for key, path in VERSION_SOURCES.items()}
    print(f"Detected versions: {versions}")

    replacements = _replacements(versions)
    total_subs = 0
    changed_files: list[str] = []
    vacuous: list[str] = []
    for target in TARGETS:
        if not target.exists():
            print(f"WARNING: {target} does not exist, skipping", file=sys.stderr)
            continue
        n, matched = _apply(target, replacements, dry_run=args.dry_run)
        if matched == 0:
            vacuous.append(str(target.relative_to(SUITE_ROOT)))
        if n > 0:
            changed_files.append(f"{target.relative_to(SUITE_ROOT)} ({n} substitutions)")
            total_subs += n

    if vacuous:
        # Vacuous-pass guard (plan 2026-10-30): a target whose shape drifted
        # so far that NO version pattern matches must fail loudly instead of
        # reporting "in sync". Update _replacements() when this fires.
        print(
            "ERROR: no version pattern matched the following target(s) — "
            "doc shape drifted past this gate; update _replacements():",
            file=sys.stderr,
        )
        for line in vacuous:
            print(f"  - {line}", file=sys.stderr)
        return 1

    if args.dry_run:
        if changed_files:
            print("DRY-RUN: would update the following files:", file=sys.stderr)
            for line in changed_files:
                print(f"  - {line}", file=sys.stderr)
            return 1
        print("DRY-RUN: no changes needed.")
        return 0

    if args.check or args.validate:
        if changed_files:
            print("ERROR: version docs are out of date:", file=sys.stderr)
            for line in changed_files:
                print(f"  - {line}", file=sys.stderr)
            print("Run: python scripts/sync_version_docs.py", file=sys.stderr)
            return 1
        print("OK: version docs in sync with pyproject.toml")
        return 0

    if changed_files:
        print(f"Updated {len(changed_files)} file(s), {total_subs} total substitutions:")
        for line in changed_files:
            print(f"  - {line}")
    else:
        print("No changes (all docs already in sync).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
