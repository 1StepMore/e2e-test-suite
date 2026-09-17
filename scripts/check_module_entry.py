"""Fail-loud module-entry consistency check (Omni Suite issue #11).

The suite reaches each module through a symlink ``<suite>/<Module>``. When that
symlink points at a *second working directory* whose ``.git`` is a gitdir
pointer FILE (sharing another clone's git dir), the suite silently runs
month-old worktree code — and the venv editable ``.pth`` files may point at the
same stale tree. This gate makes that failure loud and deterministic.

Stdlib only. ``--root DIR`` (default: the suite root) rebases every path.
For each module (``Omni_Pre_Processor``/``opp``, ``Omni_Localizer``/``ol``,
``Omni_Re_Formatter``/``orf``) it:

1. skips (no failure) when the entry is absent — fresh clones have none;
2. fails when the resolved dir lacks ``pyproject.toml`` or ``src/<pkg>``;
3. fails when ``<entry>/.git`` is a FILE (gitdir pointer -> stale-code risk);
4. fails when an editable ``.pth`` in a suite venv resolves to a different
   realpath than the entry;
5. prints entry -> realpath, HEAD sha and tracked-dirty count (dirty is a
   WARNING, never a failure).

Exit 1 if any hard check fails, else 0.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: (suite entry name, package dir under ``src/``) in report order.
MODULES: tuple[tuple[str, str], ...] = (
    ("Omni_Pre_Processor", "opp"),
    ("Omni_Localizer", "ol"),
    ("Omni_Re_Formatter", "orf"),
)

#: Venvs that may hold editable installs of the modules (``.venv_win`` is the
#: Windows bootstrap written by ``scripts/setup_dev.ps1``).
VENV_NAMES = (".venv", ".venv_ol", ".venv_win")

#: Filename/path tokens that map a ``.pth`` to a module.
_MODULE_TOKENS: dict[str, tuple[str, ...]] = {
    "Omni_Pre_Processor": ("omni_pre_processor", "pre_processor", "preprocessor"),
    "Omni_Localizer": ("omni_localizer", "localizer"),
    "Omni_Re_Formatter": ("omni_re_formatter", "re_formatter", "reformatter"),
}

#: ``src/<pkg>`` path fragments used as a last-resort module attribution.
_SRC_TOKENS: dict[str, tuple[str, ...]] = {
    "Omni_Pre_Processor": ("/src/opp",),
    "Omni_Localizer": ("/src/ol",),
    "Omni_Re_Formatter": ("/src/orf",),
}


def read_text(path: Path) -> str:
    """Read a file as UTF-8, tolerating non-UTF-8 bytes."""
    return path.read_text(encoding="utf-8", errors="replace")


def _run_git(entry: Path, *args: str) -> str | None:
    """Return git stdout for ``entry`` or None when git is unusable.

    A synthetic fixture may carry an unreadable ``.git`` (a bare HEAD file);
    any git failure degrades to None instead of raising, so the HEAD/dirty
    probes never turn into a hard failure.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(entry), *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _head_and_dirty(entry: Path) -> tuple[str, int | None]:
    """Return ``(short HEAD sha or 'unavailable', tracked-dirty count or None)``."""
    head = _run_git(entry, "rev-parse", "--short", "HEAD")
    head = head.strip() if head else "unavailable"
    status = _run_git(entry, "status", "--porcelain")
    if status is None:
        return head, None
    dirty = sum(
        1
        for line in status.splitlines()
        if line.strip() and not line.startswith("??")
    )
    return head, dirty


def _iter_pths(root: Path) -> list[Path]:
    """All ``.pth`` files in the suite venvs (missing venvs are skipped).

    Only the layout of the *current* platform is scanned: a POSIX venv keeps its
    packages in ``lib/pythonX.Y/site-packages``, a Windows venv in
    ``Lib/site-packages``. Scanning the foreign layout from the wrong platform
    makes every path inside those ``.pth`` files unusable — a WSL-style
    ``/mnt/d/...`` target reads as ``D:\\mnt\\d\\...`` — which reported 7 bogus
    "points at ..." failures when this gate first ran on Windows.
    """
    pths: list[Path] = []
    for name in VENV_NAMES:
        venv = root / name
        if not venv.is_dir():
            continue
        if os.name == "nt":
            layouts: list[Path] = [venv / "Lib" / "site-packages"]
        else:
            layouts = sorted(venv.glob("lib/python*/site-packages"))
        for site_packages in layouts:
            if site_packages.is_dir():
                pths.extend(sorted(site_packages.glob("*.pth")))
    return pths


def _pth_targets(pth: Path) -> list[Path]:
    """Path lines referenced by a ``.pth`` file (import lines are ignored)."""
    targets: list[Path] = []
    for line in read_text(pth).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("import "):
            continue
        target = Path(line)
        if not target.is_absolute():
            target = pth.parent / target
        targets.append(target)
    return targets


def _module_for_pth(pth: Path, target: Path) -> str | None:
    """Attribute a ``.pth`` (by filename, path components, then src/pkg)."""
    name = pth.name.lower().replace("-", "_")
    for module, tokens in _MODULE_TOKENS.items():
        if any(tok in name for tok in tokens):
            return module
    parts = {part.lower() for part in target.parts}
    for module, tokens in _MODULE_TOKENS.items():
        if any(tok in parts for tok in tokens):
            return module
    target_s = target.as_posix().lower()
    for module, tokens in _SRC_TOKENS.items():
        if any(tok in target_s for tok in tokens):
            return module
    return None


def run_check(root: Path) -> list[str]:
    """Run the per-module entry checks; return hard failures (dirty is warning)."""
    failures: list[str] = []
    print(f"check_module_entry (root: {root})")
    pths = _iter_pths(root)

    for module_dir, pkg in MODULES:
        entry = root / module_dir
        if not entry.is_dir():
            print(f"skip: {module_dir} entry not present")
            continue

        real = entry.resolve()
        print(f"{module_dir}: entry={entry} -> realpath={real}")

        # 2. Resolved dir must carry pyproject.toml + src/<pkg>.
        missing: list[str] = []
        if not (real / "pyproject.toml").is_file():
            missing.append("pyproject.toml")
        if not (real / "src" / pkg).is_dir():
            missing.append(f"src/{pkg}")
        if missing:
            msg = f"{module_dir}: {real} is missing entry point(s): {', '.join(missing)}"
            failures.append(msg)
            print(f"  FAIL: {msg}")

        # 3. .git must be a directory, not a gitdir-pointer FILE.
        git = entry / ".git"
        if git.is_file():
            pointer = read_text(git).strip()
            msg = (
                f"{module_dir}: {git} is a FILE (gitdir pointer: {pointer}) — a "
                f"second working directory sharing another clone's .git (stale-"
                f"code risk)"
            )
            failures.append(msg)
            print(f"  FAIL: {msg}")
            print(f"  fix: ln -sfn ../{module_dir} {root / module_dir}")

        # 4. Editable .pth files must resolve to this entry's src dir.
        expected = real / "src"
        for pth in pths:
            for target in _pth_targets(pth):
                if _module_for_pth(pth, target) != module_dir:
                    continue
                resolved = target.resolve()
                if resolved not in (real, expected):
                    msg = (
                        f"{module_dir}: {pth.name} points at {resolved}, expected "
                        f"{expected} (entry realpath {real})"
                    )
                    failures.append(msg)
                    print(f"  FAIL: {msg}")

        # 5. Report HEAD + tracked-dirty count (warning only).
        head, dirty = _head_and_dirty(entry)
        if dirty is None:
            print(f"  HEAD {head}  dirty unavailable")
        else:
            print(f"  HEAD {head}  dirty {dirty}")
            if dirty > 0:
                print(f"  WARNING: {dirty} tracked change(s) in the module worktree")

    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail-loud module-entry consistency check (suite symlink "
        "resolves to the right clone, no gitdir-pointer second worktree, venv "
        "editable pth matches)."
    )
    parser.add_argument(
        "--root", default=str(ROOT), help="Suite root (default: repo root)."
    )
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    failures = run_check(root)
    print()
    if failures:
        print(f"check FAILED ({len(failures)} issue(s)):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("check passed: module entries resolve to their clones.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
