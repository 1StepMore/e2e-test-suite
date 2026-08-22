"""Tests for scripts/validation/artifact_matrix.py (e2e-test-suite#44).

The artifact-assertion matrix aggregates ``run_assertions`` results into a
report card keyed by artifact basename, persists ``artifact-report.json``,
and its ``main()`` exits 1 when any P0/P1 assertion failed (0 otherwise).
A delivery ``.zip`` input is unzipped into a temp dir and its ``01-RAW/``
subdir asserted when present.

Hermetic: no OPP/OL/ORF CLI, no LLM, no network. The script is loaded from
its file path with importlib (scripts/ is not a package) and pulls in the
sibling ``artifact_assertions.py`` lazily via its own ``_load_assertions``.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

SUITE_ROOT = Path(__file__).resolve().parent.parent.parent

_SCRIPT_PATH = SUITE_ROOT / "scripts" / "validation" / "artifact_matrix.py"

CLEAN_MD = """# Title

Some plain content.

| a | b |
|---|---|
| 1 | 2 |
"""


def _load_matrix():
    """Import scripts/validation/artifact_matrix.py from its file path."""
    spec = importlib.util.spec_from_file_location("artifact_matrix", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["artifact_matrix"] = mod
    spec.loader.exec_module(mod)
    return mod


matrix = _load_matrix()


# ---------------------------------------------------------------------------
# build_artifact_report — clean vs polluted, module='suite' (hard-security)
# ---------------------------------------------------------------------------


def test_build_artifact_report_clean_file_report_card(tmp_path):
    """A clean markdown file -> the report card is keyed by the artifact
    basename; every assertion passed; p0_failed == 0."""
    (tmp_path / "doc.md").write_text(CLEAN_MD, encoding="utf-8")
    report = matrix.build_artifact_report(tmp_path, module="suite", run_dir="run-1")

    assert report["matrix_type"] == "artifact"
    assert report["module"] == "suite"
    assert report["run_id"] == "run-1"
    card = report["report_card"]
    assert list(card) == ["doc.md"]
    entry = card["doc.md"]
    assert entry["passed"] is True
    assert len(entry["assertions"]) == 4  # the hard-security group
    assert all(a["passed"] is True for a in entry["assertions"])
    c = report["counts"]
    assert c["artifacts"] == 1
    assert c["assertions"] == 4
    assert c["passed"] == 4
    assert c["failed"] == 0
    assert c["p0_failed"] == 0
    assert c["p1_failed"] == 0


def test_build_artifact_report_polluted_dir_failed_and_p0(tmp_path):
    """A placeholder leak (P0) -> counts.failed > 0 and p0_failed > 0; the
    artifact entry is marked failed."""
    (tmp_path / "doc.md").write_text("empty: _No data_\n", encoding="utf-8")
    report = matrix.build_artifact_report(tmp_path, module="suite", run_dir="run-1")

    c = report["counts"]
    assert c["failed"] > 0
    assert c["p0_failed"] > 0
    assert report["report_card"]["doc.md"]["passed"] is False


def test_build_artifact_report_unknown_module_raises(tmp_path):
    """An unknown module is a clear ValueError."""
    (tmp_path / "doc.md").write_text(CLEAN_MD, encoding="utf-8")
    with pytest.raises(ValueError):
        matrix.build_artifact_report(tmp_path, module="nope")


def test_build_artifact_report_missing_dir_raises(tmp_path):
    """A nonexistent artifacts path is a clear ValueError — an empty report
    card would silently hide a wrong path."""
    with pytest.raises(ValueError):
        matrix.build_artifact_report(tmp_path / "nope", module="suite")


# ---------------------------------------------------------------------------
# write_artifact_report
# ---------------------------------------------------------------------------


def test_write_artifact_report_writes_parseable_json(tmp_path):
    """write_artifact_report persists artifact-report.json with the full
    report shape (matrix_type/module/run_id/report_card/counts)."""
    (tmp_path / "doc.md").write_text(CLEAN_MD, encoding="utf-8")
    report = matrix.build_artifact_report(tmp_path, module="suite", run_dir="run-7")
    run_dir = tmp_path / "runs"
    run_dir.mkdir()

    out = matrix.write_artifact_report(report, run_dir)

    assert out == run_dir / "artifact-report.json"
    assert out.is_file()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["matrix_type"] == "artifact"
    assert payload["module"] == "suite"
    assert payload["run_id"] == "run-7"
    assert "doc.md" in payload["report_card"]
    assert set(payload["counts"]) == {
        "artifacts", "assertions", "passed", "failed", "p0_failed", "p1_failed",
    }


# ---------------------------------------------------------------------------
# .zip input — the delivery package resolves to 01-RAW/
# ---------------------------------------------------------------------------


def test_build_artifact_report_zip_resolves_01_raw(tmp_path):
    """A delivery .zip (01-RAW/a.txt inside) asserts the 01-RAW subdir — the
    artifact basename 'a.txt' appears in the report card."""
    zip_path = tmp_path / "delivery.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("01-RAW/a.txt", "clean content here")
    report = matrix.build_artifact_report(zip_path, module="suite", run_dir="run-zip")

    assert list(report["report_card"]) == ["a.txt"]
    assert report["counts"]["artifacts"] == 1
    assert report["report_card"]["a.txt"]["passed"] is True


def test_build_artifact_report_zip_without_01_raw_uses_root(tmp_path):
    """A .zip with no 01-RAW/ subdir asserts the whole extraction."""
    zip_path = tmp_path / "flat.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("b.txt", "clean content")
    report = matrix.build_artifact_report(zip_path, module="suite", run_dir="run-zip")

    assert list(report["report_card"]) == ["b.txt"]


def test_build_artifact_report_bad_zip_raises(tmp_path):
    """A corrupt .zip input is a clear error — _resolve_artifacts_dir lets
    the zipfile.BadZipFile propagate (never a silent empty report)."""
    zip_path = tmp_path / "broken.zip"
    zip_path.write_bytes(b"not a zip")
    with pytest.raises(zipfile.BadZipFile):
        matrix.build_artifact_report(zip_path, module="suite")


# ---------------------------------------------------------------------------
# main() — exit codes
# ---------------------------------------------------------------------------


def test_main_polluted_exit_1(tmp_path):
    """P0/P1 assertion failures drive exit 1 from main()."""
    (tmp_path / "doc.md").write_text("secret sk-abcdefghijklmnop1234\n", encoding="utf-8")
    assert matrix.main([str(tmp_path)]) == 1


def test_main_clean_exit_0(tmp_path):
    """A clean artifacts dir -> exit 0."""
    (tmp_path / "doc.md").write_text(CLEAN_MD, encoding="utf-8")
    assert matrix.main([str(tmp_path)]) == 0


def test_main_writes_report_to_out_file(tmp_path):
    """main() with --out <file> writes the report there."""
    (tmp_path / "doc.md").write_text(CLEAN_MD, encoding="utf-8")
    out = tmp_path / "custom" / "artifact-report.json"
    rc = matrix.main([str(tmp_path), "--out", str(out)])

    assert rc == 0
    assert out.is_file()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["counts"]["p0_failed"] == 0


def test_main_missing_dir_exit_1(tmp_path):
    """A nonexistent artifacts dir -> error, exit 1 (not 0)."""
    rc = matrix.main([str(tmp_path / "nope")])
    assert rc == 1
