#!/usr/bin/env python3
"""Sync version tables in top-level docs from pyproject.toml.

Single source of truth: each submodule's `pyproject.toml` + the suite's
own `pyproject.toml`. This script rewrites the version numbers in:

- README.md (env table + Pinned combo line)
- AGENTS.md (Current Versions table + Pinned combo line)
- COMPATIBILITY.md ("How to check installed versions" example commands)

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
    SUITE_ROOT / "COMPATIBILITY.md",
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
    ]


def _apply(path: Path, replacements: list[tuple[re.Pattern[str], str]]) -> int:
    """Return the number of substitutions that actually changed text.

    `subn` reports matches even when the replacement string equals the
    matched substring (a no-op write). For the --check mode we need
    only the count of substitutions that produce a real diff.
    """
    content = path.read_text(encoding="utf-8")
    new = content
    real_changes = 0
    for pattern, replacement in replacements:
        # Compare per-pattern so we only credit substitutions where the
        # replacement differs from the matched text.
        def _count(m: re.Match[str]) -> str:
            nonlocal real_changes
            if m.group(0) != replacement:
                real_changes += 1
            return replacement

        new = pattern.sub(_count, new)
    if new != content:
        path.write_text(new, encoding="utf-8")
    return real_changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="Exit non-zero if any doc would change. Used by pre-commit.",
    )
    args = parser.parse_args()

    versions = {key: read_version(path) for key, path in VERSION_SOURCES.items()}
    print(f"Detected versions: {versions}")

    replacements = _replacements(versions)
    total_subs = 0
    changed_files: list[str] = []
    for target in TARGETS:
        if not target.exists():
            print(f"WARNING: {target} does not exist, skipping", file=sys.stderr)
            continue
        n = _apply(target, replacements)
        if n > 0:
            changed_files.append(f"{target.relative_to(SUITE_ROOT)} ({n} substitutions)")
            total_subs += n

    if args.check:
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
