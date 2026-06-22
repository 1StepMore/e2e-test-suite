#!/usr/bin/env python3
"""Bump version across OPP, OL, ORF simultaneously.

Usage:
    python scripts/bumpversion.py           # patch bump (0.6.1 → 0.6.2)
    python scripts/bumpversion.py minor     # minor bump (0.6.1 → 0.7.0)
    python scripts/bumpversion.py major     # major bump (0.6.1 → 1.0.0)

Effects:
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

import re
import sys
from pathlib import Path

SUITE_ROOT = Path(__file__).resolve().parent.parent

MODULES: dict[str, Path] = {
    "opp": SUITE_ROOT / "Omni_Pre_Processor" / "pyproject.toml",
    "ol": SUITE_ROOT / "Omni_Localizer" / "pyproject.toml",
    "orf": SUITE_ROOT / "Omni_Re_Formatter" / "pyproject.toml",
}

VERSION_RE = re.compile(r'^version\s*=\s*"(\d+)\.(\d+)\.(\d+)"', re.MULTILINE)


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
    path.write_text(new_content, encoding="utf-8")
    return new_ver


def main() -> int:
    level = "patch"
    if len(sys.argv) > 1:
        level = sys.argv[1].lower()
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
