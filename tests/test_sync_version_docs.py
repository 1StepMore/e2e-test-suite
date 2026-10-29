"""Vacuous-pass guard for scripts/sync_version_docs.py (plan 2026-10-30 PR3 #5).

The 2026-06 v0.9 incident: doc shapes drifted, every pattern matched
nothing, and ``--check`` reported "in sync" while the tables still
advertised the previous release. The guard now fails when an existing
TARGET matches zero patterns. These tests pin that behaviour against tmp
targets (no repo files are touched).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_module(tmp_path: Path, readme_body: str):
    spec = importlib.util.spec_from_file_location(
        "sync_version_docs", ROOT / "scripts" / "sync_version_docs.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Redirect the version sources and the single target into tmp_path.
    versions = {}
    for key in ("suite", "opp", "ol", "orf"):
        p = tmp_path / f"pyproject.{key}.toml"
        p.write_text('[project]\nversion = "1.0.0"\n', encoding="utf-8")
        versions[key] = p
    mod.VERSION_SOURCES = versions
    mod.SUITE_ROOT = tmp_path  # main() calls target.relative_to(SUITE_ROOT)
    readme = tmp_path / "README.md"
    readme.write_text(readme_body, encoding="utf-8")
    mod.TARGETS = [readme]
    return mod


def _run_check(mod, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["sync_version_docs.py", "--check"])
    return mod.main()


def _combined(capsys):
    # ONE readouterr() call — it resets the buffers, so a second call for
    # .err would return empty.
    captured = capsys.readouterr()
    return captured.out + captured.err


def test_check_fails_when_target_matches_no_pattern(tmp_path, monkeypatch, capsys):
    """A target whose shape matches zero patterns must exit 1 with the
    guard message — never a silent 'in sync'."""
    mod = _load_module(tmp_path, "# a doc with no version table at all\n")
    rc = _run_check(mod, monkeypatch)
    combined = _combined(capsys)
    assert rc == 1
    assert "no version pattern matched" in combined
    assert "README.md" in combined


def test_check_detects_stale_version_row(tmp_path, monkeypatch, capsys):
    mod = _load_module(
        tmp_path,
        "| OPP | `Omni_Pre_Processor/` | v0.0.1 |\n"
        "| OL | `Omni_Localizer/` | v0.0.1 |\n"
        "| ORF | `Omni_Re_Formatter/` | v0.0.1 |\n"
        "| Omni_Suite | `./` | v0.0.1 |\n",
    )
    rc = _run_check(mod, monkeypatch)
    combined = _combined(capsys)
    assert rc == 1
    assert "out of date" in combined


def test_check_ok_when_in_sync(tmp_path, monkeypatch, capsys):
    mod = _load_module(
        tmp_path,
        "| OPP | `Omni_Pre_Processor/` | v1.0.0 |\n"
        "| OL | `Omni_Localizer/` | v1.0.0 |\n"
        "| ORF | `Omni_Re_Formatter/` | v1.0.0 |\n"
        "| Omni_Suite | `./` | v1.0.0 |\n",
    )
    rc = _run_check(mod, monkeypatch)
    combined = _combined(capsys)
    assert rc == 0
    assert "in sync" in combined
