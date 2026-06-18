"""omni-suite — suite-level CLI (Phase C5)."""

from __future__ import annotations

import sys
from pathlib import Path

_VERSION_FILE = Path(__file__).parent.parent / "VERSION"


def main() -> None:
    """Print suite version, or compatibility matrix."""
    if len(sys.argv) > 1 and sys.argv[1] == "--version":
        print(_VERSION_FILE.read_text(encoding="utf-8").strip())
        return
    if len(sys.argv) > 1 and sys.argv[1] == "--compatibility":
        compat = Path(__file__).parent.parent / "COMPATIBILITY.md"
        print(compat.read_text(encoding="utf-8"))
        return
    print("omni-suite — use --version or --compatibility")


if __name__ == "__main__":
    main()
