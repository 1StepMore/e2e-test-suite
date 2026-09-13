"""Tests for scripts/check_module_entry.py (Omni Suite issue #11).

Fixtures are synthetic roots built under ``tmp_path`` — no network, no real git
clone. A ``.git`` directory plus a HEAD file is enough for the HEAD/dirty probes
to degrade gracefully, so the tests assert the hard-check contract only.
"""
from pathlib import Path

import scripts.check_module_entry as cme


def _write_module(
    root: Path,
    module_dir: str,
    pkg: str,
    *,
    version: str = "0.1.0",
    gitdir_pointer: bool = False,
) -> Path:
    """Create a clone-like module entry under ``root``.

    With ``gitdir_pointer`` the entry's ``.git`` is a gitdir-pointer FILE (the
    stale-code failure mode); otherwise it is a directory with a HEAD file.
    """
    entry = root / module_dir
    (entry / "src" / pkg).mkdir(parents=True, exist_ok=True)
    (entry / "pyproject.toml").write_text(
        f'[project]\nname = "x"\nversion = "{version}"\n', encoding="utf-8"
    )
    git = entry / ".git"
    if gitdir_pointer:
        git.write_text("gitdir: /nonexistent/.git\n", encoding="utf-8")
    else:
        git.mkdir(parents=True, exist_ok=True)
        (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    return entry


def _write_pth(root: Path, name: str, target: str) -> None:
    """Write a venv editable ``.pth`` pointing at ``target``."""
    site_packages = root / ".venv/lib/python3.13/site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)
    (site_packages / name).write_text(target + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# (a) A clone-like entry passes (absent modules are skipped, not failed).
# ---------------------------------------------------------------------------

def test_passes_on_clone_like_entry(tmp_path):
    _write_module(tmp_path, "Omni_Localizer", "ol")
    assert cme.main(["--root", str(tmp_path)]) == 0


def test_passes_when_no_modules_present(tmp_path):
    """A fresh clone with no module entries is skipped, not failed."""
    assert cme.main(["--root", str(tmp_path)]) == 0


# ---------------------------------------------------------------------------
# (b) A gitdir-pointer .git FILE fails with the ln -sfn hint.
# ---------------------------------------------------------------------------

def test_fails_on_gitdir_pointer_file(tmp_path, capsys):
    _write_module(tmp_path, "Omni_Localizer", "ol", gitdir_pointer=True)
    rc = cme.main(["--root", str(tmp_path)])
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert rc == 1, "a gitdir-pointer .git FILE must fail the entry check"
    assert "ln -sfn ../Omni_Localizer" in combined, (
        f"failure text must print the one-line fix, got: {combined!r}"
    )


# ---------------------------------------------------------------------------
# (c) A mismatched editable .pth fails; a matching one passes.
# ---------------------------------------------------------------------------

def test_fails_on_mismatched_editable_pth(tmp_path, capsys):
    _write_module(tmp_path, "Omni_Localizer", "ol")
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "src").mkdir(parents=True, exist_ok=True)
    _write_pth(
        tmp_path,
        "_editable_impl_omni_localizer.pth",
        str(elsewhere / "src"),
    )
    rc = cme.main(["--root", str(tmp_path)])
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert rc == 1, "an editable .pth pointing elsewhere must fail"
    assert "elsewhere" in combined and "expected" in combined, (
        f"failure text must print both realpaths + expected, got: {combined!r}"
    )


def test_passes_on_matching_editable_pth(tmp_path):
    entry = _write_module(tmp_path, "Omni_Localizer", "ol")
    _write_pth(
        tmp_path,
        "_editable_impl_omni_localizer.pth",
        str(entry / "src"),
    )
    assert cme.main(["--root", str(tmp_path)]) == 0


# ---------------------------------------------------------------------------
# Missing pyproject.toml / src/<pkg> is a hard failure.
# ---------------------------------------------------------------------------

def test_fails_on_missing_pyproject(tmp_path, capsys):
    entry = tmp_path / "Omni_Pre_Processor"
    (entry / "src" / "opp").mkdir(parents=True, exist_ok=True)
    rc = cme.main(["--root", str(tmp_path)])
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert rc == 1, "a missing pyproject.toml must fail the entry check"
    assert "pyproject.toml" in combined, (
        f"failure text must name the missing entry point, got: {combined!r}"
    )
