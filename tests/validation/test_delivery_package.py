"""Tests for scripts/validation/make_delivery_package.py (--deliver).

The delivery package is the human-review zip built from a persisted run:
``manifest.json`` + ``01-RAW/`` (real artifact copies) +
``02-PROCESSED/`` (director report + run_meta + verdict summary) +
``03-MISSING/`` (notes per genuinely-missing declared artifact — never a
failure).  Relative artifact paths resolve against the suite root.

Constraints under test:

- The manifest carries ``counts`` (per-status scenario counts),
  ``artifacts`` (each with ``exists``), and ``run_meta``.
- Missing declared artifacts land in ``03-MISSING/`` and are listed in
  ``missing_artifacts`` — the delivery still succeeds (exit 0).
- Only the out-dir is written by the build; the staging tree is a tempdir.

RED-first discipline: every test builds a synthetic run payload (matching
the engine's persisted shape ``{run_id, timestamp, trace_id, scenarios:
[{name, status, steps: [{artifact_to_show, ...}]}], run_meta}``) with REAL
small artifact files, so copies genuinely land in ``01-RAW/``.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

SUITE_ROOT = Path(__file__).resolve().parent.parent.parent

_PACKAGE_PATH = SUITE_ROOT / "scripts" / "validation" / "make_delivery_package.py"


def _load_package():
    """Import scripts/validation/make_delivery_package.py from its file
    path (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location("make_delivery_package", _PACKAGE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["make_delivery_package"] = mod
    spec.loader.exec_module(mod)
    return mod


pkg = _load_package()


def _step(artifact: str | None) -> dict:
    return {
        "step_index": 1,
        "name": "produce artifact",
        "kind": "cli",
        "surface": "cli: true",
        "real_call": "true",
        "expect": {"success": True},
        "actual": {"success": True},
        "artifact_to_show": artifact,
        "standard": None,
        "arguments": {"command": "true"},
        "duration_seconds": 0.01,
        "trace_id": "trace-1",
        "passed": True,
        "status": "passed",
        "grade": {"passed": True, "checks": [], "reason": "ok"},
        "recovery": [],
        "recovery_status": None,
    }


def _scenario(name: str, status: str, artifact: str | None = None) -> dict:
    return {
        "name": name,
        "status": status,
        "summary": f"{status} — 1 step",
        "missing_env": [],
        "steps": [_step(artifact)],
        "cleanup": [],
        "trace_id": "trace-1",
    }


def _run_payload(scenarios: list[dict]) -> dict:
    return {
        "run_id": "20260822-120000",
        "timestamp": "2026-08-22T12:00:00",
        "trace_id": "trace-1",
        "scenarios": scenarios,
        "run_meta": {
            "suite_version": "0.4.0",
            "suite_sha": "abcd1234",
            "opp": {"version": "0.9.1", "sha": "beef0001"},
            "repos": ["opp"],
        },
    }


def _write_run(tmp_path: Path, payload: dict) -> Path:
    """A persisted run dir: <tmp>/<run_id>/scenarios.json."""
    run_dir = tmp_path / payload["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "scenarios.json").write_text(json.dumps(payload), encoding="utf-8")
    return run_dir


def _read_zip(zip_path: Path) -> dict[str, str]:
    """zip member name -> decoded text content."""
    with zipfile.ZipFile(zip_path) as zf:
        return {n: zf.read(n).decode("utf-8") for n in zf.namelist()}


# ---------------------------------------------------------------------------
# Happy path — manifest + 01-RAW + 02-PROCESSED with real artifact copies
# ---------------------------------------------------------------------------


def test_build_delivery_zip_structure(tmp_path: Path):
    """build_delivery produces the zip with manifest.json, 01-RAW/,
    02-PROCESSED/ (report, run_meta.json, verdict-summary.md) and the
    real artifact copied into 01-RAW/."""
    artifact = tmp_path / "artifact.md"
    artifact.write_text("# Translated", encoding="utf-8")
    payload = _run_payload([_scenario("tool-opp-extract_document", "passed", str(artifact))])
    run_dir = _write_run(tmp_path, payload)
    out_dir = tmp_path / "deliverables"

    zip_path = pkg.build_delivery(run_dir, out_dir=out_dir)

    assert zip_path.is_file()
    assert zip_path.name == "omni-suite-validation-20260822-120000.zip"
    members = _read_zip(zip_path)
    assert set(members) >= {
        "manifest.json",
        "01-RAW/artifact.md",
        "02-PROCESSED/run_meta.json",
        "02-PROCESSED/verdict-summary.md",
    }
    assert members["01-RAW/artifact.md"] == "# Translated"  # the REAL copy
    assert "02-PROCESSED/report.json" in members or "02-PROCESSED/validation-report.md" in members
    assert "03-MISSING/" not in members  # nothing missing in the happy path


def test_build_delivery_manifest_fields(tmp_path: Path):
    """The manifest carries run identity, per-status counts, the artifact
    registry (with exists) and the run_meta."""
    artifact = tmp_path / "out.xlf"
    artifact.write_text("<xliff/>", encoding="utf-8")
    payload = _run_payload(
        [
            _scenario("tool-opp-extract_document", "passed", str(artifact)),
            _scenario("pipeline-docx-md-docx", "unconfigured"),
        ]
    )
    run_dir = _write_run(tmp_path, payload)

    zip_path = pkg.build_delivery(run_dir, out_dir=tmp_path / "out")
    manifest = json.loads(_read_zip(zip_path)["manifest.json"])

    assert manifest["run_id"] == "20260822-120000"
    assert manifest["trace_id"] == "trace-1"
    assert manifest["counts"] == {"passed": 1, "unconfigured": 1}
    assert manifest["run_meta"]["suite_version"] == "0.4.0"
    assert manifest["run_meta"]["opp"]["version"] == "0.9.1"
    assert len(manifest["artifacts"]) == 1
    entry = manifest["artifacts"][0]
    assert entry["scenario"] == "tool-opp-extract_document"
    assert entry["exists"] is True
    assert entry["artifact_path"] == str(artifact.resolve())  # relative resolved
    assert entry["raw_path"] == "01-RAW/out.xlf"
    assert manifest["missing_artifacts"] == []


def test_build_delivery_tag_suffixes_zip_name(tmp_path: Path):
    """A tag is sanitized and appended: omni-suite-validation-<run_id>-<tag>.zip."""
    payload = _run_payload([_scenario("tool-opp-extract_document", "passed")])
    run_dir = _write_run(tmp_path, payload)

    zip_path = pkg.build_delivery(run_dir, out_dir=tmp_path / "out", tag="v0.4.0")

    assert zip_path.name == "omni-suite-validation-20260822-120000-v0.4.0.zip"


def test_build_delivery_02_processed_contents(tmp_path: Path):
    """02-PROCESSED holds run_meta.json (the run_meta alone) and
    verdict-summary.md (scenario -> status table)."""
    payload = _run_payload([_scenario("tool-opp-extract_document", "passed")])
    run_dir = _write_run(tmp_path, payload)

    zip_path = pkg.build_delivery(run_dir, out_dir=tmp_path / "out")
    members = _read_zip(zip_path)

    run_meta = json.loads(members["02-PROCESSED/run_meta.json"])
    assert run_meta["suite_version"] == "0.4.0"
    summary = members["02-PROCESSED/verdict-summary.md"]
    assert "tool-opp-extract_document" in summary
    assert "passed" in summary


# ---------------------------------------------------------------------------
# Missing artifacts — 03-MISSING notes, never a failure
# ---------------------------------------------------------------------------


def test_build_delivery_missing_artifact_lands_in_03_missing(tmp_path: Path):
    """A declared artifact path that doesn't exist lands in 03-MISSING/
    with a note and is listed in manifest.missing_artifacts — the build
    still succeeds (the zip exists)."""
    payload = _run_payload([_scenario("tool-opp-extract_document", "passed", str(tmp_path / "gone" / "no.md"))])
    run_dir = _write_run(tmp_path, payload)

    zip_path = pkg.build_delivery(run_dir, out_dir=tmp_path / "out")

    assert zip_path.is_file()
    members = _read_zip(zip_path)
    assert "03-MISSING/" in members  # the member is a dir entry (or note)
    assert any(n.startswith("03-MISSING/missing-") and n.endswith(".txt") for n in members)
    note_names = sorted(n for n in members if n.startswith("03-MISSING/missing-"))
    assert len(note_names) == 1
    assert str(tmp_path / "gone" / "no.md") in members[note_names[0]]
    manifest = json.loads(members["manifest.json"])
    assert len(manifest["missing_artifacts"]) == 1
    entry = manifest["missing_artifacts"][0]
    assert entry["exists"] is False
    assert entry["scenario"] == "tool-opp-extract_document"
    assert manifest["artifacts"] == []  # nothing made it into 01-RAW


def test_build_delivery_mixed_existing_and_missing(tmp_path: Path):
    """Existing artifacts copy into 01-RAW/, missing ones get 03-MISSING
    notes — both lists populated in one manifest."""
    present = tmp_path / "present.md"
    present.write_text("ok", encoding="utf-8")
    payload = _run_payload(
        [
            _scenario("tool-opp-extract_document", "passed", str(present)),
            _scenario("tool-orf-apply_md", "failed", str(tmp_path / "nope.md")),
        ]
    )
    run_dir = _write_run(tmp_path, payload)

    zip_path = pkg.build_delivery(run_dir, out_dir=tmp_path / "out")
    members = _read_zip(zip_path)
    manifest = json.loads(members["manifest.json"])

    assert "01-RAW/present.md" in members
    assert len(manifest["artifacts"]) == 1
    assert len(manifest["missing_artifacts"]) == 1
    assert manifest["missing_artifacts"][0]["scenario"] == "tool-orf-apply_md"


# ---------------------------------------------------------------------------
# Relative artifact paths resolve against the suite root
# ---------------------------------------------------------------------------


def test_build_delivery_relative_artifact_resolves_against_suite_root(tmp_path: Path, monkeypatch):
    """A RELATIVE artifact_to_show resolves against the suite root — the
    test writes a real file at <suite_root>/<relative> and the delivery
    copies it (exists -> True, lands in 01-RAW)."""
    monkeypatch.chdir(tmp_path)  # cwd must not affect resolution
    rel = Path("scenarios/_fixtures/relative-artifact-test.md")
    real = SUITE_ROOT / rel
    real.parent.mkdir(parents=True, exist_ok=True)
    real.write_text("relative artifact content", encoding="utf-8")
    try:
        payload = _run_payload([_scenario("tool-opp-extract_document", "passed", str(rel))])
        run_dir = _write_run(tmp_path, payload)
        zip_path = pkg.build_delivery(run_dir, out_dir=tmp_path / "out")
        members = _read_zip(zip_path)
        manifest = json.loads(members["manifest.json"])

        assert manifest["artifacts"][0]["exists"] is True
        assert manifest["artifacts"][0]["artifact_path"] == str(real.resolve())
        assert "01-RAW/relative-artifact-test.md" in members
    finally:
        real.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Input validation — a missing/empty run is a clear error
# ---------------------------------------------------------------------------


def test_build_delivery_missing_run_dir_raises(tmp_path: Path):
    """A run dir without scenarios.json -> ValueError (clear error), never
    a half-built zip."""
    with pytest.raises(ValueError):
        pkg.build_delivery(tmp_path / "nope", out_dir=tmp_path / "out")


def test_build_delivery_empty_run_raises(tmp_path: Path):
    """A run holding zero scenarios cannot be delivered -> ValueError."""
    payload = _run_payload([])
    run_dir = _write_run(tmp_path, payload)
    with pytest.raises(ValueError):
        pkg.build_delivery(run_dir, out_dir=tmp_path / "out")


def test_main_delivery_missing_run_exits_1(tmp_path: Path, capsys):
    """main() on a missing run -> clear stderr error, exit 1."""
    rc = pkg.main([str(tmp_path / "nope"), "--out-dir", str(tmp_path / "out")])
    assert rc == 1
    assert "scenarios.json" in capsys.readouterr().err


def test_build_delivery_basename_collision_prefixed(tmp_path: Path):
    """Two scenarios declaring artifacts with the SAME basename get the
    scenario-name_ prefix in 01-RAW — nothing overwritten."""
    a = tmp_path / "a" / "artifact.md"
    b = tmp_path / "b" / "artifact.md"
    a.parent.mkdir()
    b.parent.mkdir()
    a.write_text("A", encoding="utf-8")
    b.write_text("B", encoding="utf-8")
    payload = _run_payload(
        [
            _scenario("tool-opp-extract_document", "passed", str(a)),
            _scenario("tool-ol-translate_md_text", "passed", str(b)),
        ]
    )
    run_dir = _write_run(tmp_path, payload)

    zip_path = pkg.build_delivery(run_dir, out_dir=tmp_path / "out")
    members = _read_zip(zip_path)

    assert "01-RAW/artifact.md" in members
    # the FIRST artifact keeps the plain basename; the second (collision)
    # gets the scenario-name_ prefix
    assert "01-RAW/tool-ol-translate_md_text_artifact.md" in members
    assert members["01-RAW/artifact.md"] == "A"
    assert members["01-RAW/tool-ol-translate_md_text_artifact.md"] == "B"
