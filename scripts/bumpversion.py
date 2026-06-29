#!/usr/bin/env python3
"""Bump version across OPP, OL, ORF simultaneously, or aggregate release notes.

Usage:
    python scripts/bumpversion.py                  # patch bump (0.6.1 → 0.6.2)
    python scripts/bumpversion.py minor            # minor bump (0.6.1 → 0.7.0)
    python scripts/bumpversion.py major            # major bump (0.6.1 → 1.0.0)

    python scripts/bumpversion.py --release-notes  # print aggregated release notes
    python scripts/bumpversion.py --release-notes --from 2026-06 --to 2026-06
    python scripts/bumpversion.py --release-notes --write /tmp/notes.md

Effects (bump mode):
    1. Reads pyproject.toml from each of the 3 modules
    2. Increments the version field in all three
    3. Writes back and prints the new versions

Post-bump checklist:
    - [ ] Run `tests/integration/test_version_compat.py`
    - [ ] Update VERSION_COMPATIBILITY.md with the new row
    - [ ] `git commit -m "bump: version X.Y.Z"` in each submodule
    - [ ] Tag each submodule
    - [ ] Update submodule SHAs in root repo
"""
from __future__ import annotations

import argparse
import re
import sys
from typing import Any
from pathlib import Path

SUITE_ROOT = Path(__file__).resolve().parent.parent

MODULES: dict[str, Path] = {
    "opp": SUITE_ROOT / "Omni_Pre_Processor" / "pyproject.toml",
    "ol": SUITE_ROOT / "Omni_Localizer" / "pyproject.toml",
    "orf": SUITE_ROOT / "Omni_Re_Formatter" / "pyproject.toml",
}

VERSION_RE = re.compile(r'^version\s*=\s*"(\d+)\.(\d+)\.(\d+)"', re.MULTILINE)

# CHANGELOG file paths for release notes aggregation
CHANGELOG_PATHS: list[tuple[str, Path]] = [
    ("Suite (e2e-test-suite)", SUITE_ROOT / "CHANGELOG.md"),
    ("OPP (Omni_Pre_Processor)", SUITE_ROOT / "Omni_Pre_Processor" / "CHANGELOG.md"),
    ("OL (Omni_Localizer)", SUITE_ROOT / "Omni_Localizer" / "CHANGELOG.md"),
    ("ORF (Omni_Re_Formatter)", SUITE_ROOT / "Omni_Re_Formatter" / "CHANGELOG.md"),
]


def bump_one(path: Path, level: str) -> str:
    """Read, bump, write pyproject.toml. Return the new version string."""
    content = path.read_text(encoding="utf-8")
    match = VERSION_RE.search(content)
    if not match:
        print(f"  ⚠️  No version found in {path.name} — skipping", file=sys.stderr)
        return "?"

    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if level == "major":
        major += 1
        minor = 0
        patch = 0
    elif level == "minor":
        minor += 1
        patch = 0
    else:  # patch
        patch += 1

    new_ver = f"{major}.{minor}.{patch}"
    new_content = VERSION_RE.sub(lambda m: f'version = "{new_ver}"', content)
    _ = path.write_text(new_content, encoding="utf-8")
    return new_ver


# ---------------------------------------------------------------------------
# Release notes aggregation
# ---------------------------------------------------------------------------

# Regex patterns for various CHANGELOG header formats.
# Root format:         ## 0.2.0 — 2026-06-20
# Sub-repo bracket:    ## [0.7.3] - 2026-06-25
# ORF paren format:    ## v0.4.16 (2026-06-28)
# Date-only (root):    ## 2026-06-12
_DATE_SUFFIX_RE = re.compile(r"\s*\(.*?\)\s*$")

_HEADER_PATTERNS = [
    # Root versioned: ## X.Y.Z — YYYY-MM-DD
    re.compile(r"^## (\d+\.\d+\.\d+)\s*[—–-]\s*(\d{4}-\d{2}-\d{2})$"),
    # Sub-repo bracket: ## [X.Y.Z] - YYYY-MM-DD
    re.compile(r"^## \[(\d+\.\d+\.\d+)\]\s*[-–]\s*(\d{4}-\d{2}-\d{2})$"),
    # ORF paren: ## vX.Y.Z (YYYY-MM-DD)
    re.compile(r"^## v?(\d+\.\d+\.\d+)\s*\((\d{4}-\d{2}-\d{2})\)$"),
    # Date-only: ## YYYY-MM-DD
    re.compile(r"^## (\d{4}-\d{2}-\d{2})$"),
]


def _parse_header(header: str) -> dict[str, Any] | None:
    """Parse a ## header into {version, date, header}.

    Returns None for non-versioned sections (e.g. "## Unreleased").
    """
    stripped = _DATE_SUFFIX_RE.sub("", header).strip()
    for pat in _HEADER_PATTERNS:
        m = pat.match(stripped)
        if m:
            groups = m.groups()
            if len(groups) == 2:
                return {"version": groups[0], "date": groups[1], "header": header}
            else:
                return {"version": None, "date": groups[0], "header": header}
    return None


def _split_into_sections(content: str) -> list[dict[str, Any]]:
    """Split CHANGELOG content into parsed sections.

    Each section has keys: version (str|None), date (str), header (str), body (str).
    """
    parts = re.split(r"^(## .*)$", content, flags=re.MULTILINE)
    sections: list[dict[str, Any]] = []
    for i in range(1, len(parts), 2):
        header = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        parsed = _parse_header(header)
        if parsed is not None:
            parsed["body"] = body
            sections.append(parsed)
    return sections


def _parse_date_ym(date_str: str) -> tuple[int, int]:
    """Extract (year, month) from YYYY-MM-DD string."""
    parts = date_str.split("-")
    return int(parts[0]), int(parts[1])


def _filter_by_month(
    sections: list[dict[str, Any]],
    from_month: str | None,
    to_month: str | None,
) -> list[dict[str, Any]]:
    """Keep only sections whose date falls within the month range."""
    if not from_month and not to_month:
        return sections

    fy = fm = 0
    ty = tm = 9999
    if from_month:
        fy = int(from_month[:4])
        fm = int(from_month[5:])
    if to_month:
        ty = int(to_month[:4])
        tm = int(to_month[5:])

    result: list[dict[str, Any]] = []
    for sec in sections:
        y, m = _parse_date_ym(sec["date"])
        if from_month and (y, m) < (fy, fm):
            continue
        if to_month and (y, m) > (ty, tm):
            continue
        result.append(sec)
    return result


def aggregate_release_notes(from_month: str | None = None, to_month: str | None = None) -> str:
    """Aggregate release notes from all 4 CHANGELOG.md files within a date range.

    Args:
        from_month: Optional "YYYY-MM" — include entries from this month onwards.
        to_month: Optional "YYYY-MM" — include entries up to this month.

    Returns:
        A markdown string with per-repo release-note blocks.
    """
    lines: list[str] = ["# Omni Suite — Cross-Repo Release Notes", ""]

    for repo_name, changelog_path in CHANGELOG_PATHS:
        if not changelog_path.exists():
            continue

        content = changelog_path.read_text(encoding="utf-8")
        sections = _split_into_sections(content)
        filtered = _filter_by_month(sections, from_month, to_month)

        if not filtered:
            continue

        lines.append(f"## {repo_name}")
        lines.append("")
        for sec in filtered:
            lines.append(sec["header"])
            lines.append("")
            if sec["body"]:
                lines.append(sec["body"])
                lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Bump version across OPP, OL, ORF simultaneously, "
            "or aggregate release notes from CHANGELOG.md files."
        ),
    )
    _ = parser.add_argument(
        "level",
        nargs="?",
        default="patch",
        choices=["major", "minor", "patch"],
        help="Version bump level (default: patch)",
    )
    _ = parser.add_argument(
        "--release-notes",
        action="store_true",
        help="Print aggregated release notes from all 4 CHANGELOG.md files",
    )
    _ = parser.add_argument(
        "--write",
        type=str,
        default=None,
        help="When combined with --release-notes, write output to PATH instead of stdout",
    )
    _ = parser.add_argument(
        "--from",
        type=str,
        default=None,
        dest="from_month",
        metavar="YYYY-MM",
        help="Filter entries from this month onwards (e.g. 2026-06)",
    )
    _ = parser.add_argument(
        "--to",
        type=str,
        default=None,
        dest="to_month",
        metavar="YYYY-MM",
        help="Filter entries up to this month (e.g. 2026-06)",
    )
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()

    # -- Release notes mode
    if args.release_notes:
        notes = aggregate_release_notes(args.from_month, args.to_month)
        if args.write:
            out_path = Path(args.write)
            _ = out_path.parent.mkdir(parents=True, exist_ok=True)
            _ = out_path.write_text(notes, encoding="utf-8")
            print(f"Release notes written to {out_path.resolve()}")
        else:
            print(notes)
        return 0

    # -- Bump mode
    level = args.level
    if level not in ("major", "minor", "patch"):
        print(f"Usage: {sys.argv[0]} [major|minor|patch]", file=sys.stderr)
        return 1

    print(f"Bumping {level} in all 3 modules...")
    versions: list[str] = []
    for name, path in MODULES.items():
        if not path.exists():
            print(f"  ⚠️  {path} not found — skipping", file=sys.stderr)
            continue
        new_ver = bump_one(path, level)
        versions.append(new_ver)
        print(f"  ✅ {name}: {new_ver}")

    print(f"\nDone. To update VERSION_COMPATIBILITY.md:")
    print(f"  Add row: | {' | '.join(v for v in versions)} | ✅ Tested | {__import__('datetime').date.today().isoformat()} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
