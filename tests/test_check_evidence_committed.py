"""Tests for scripts/check_evidence_committed.py (suite#410 evidence protocol).

The protocol's canonical checker lives outside this repo; this repo-local
equivalent must enforce the same hard rule: a ``verdict=pass`` without a
non-empty, on-disk evidence file is a failure, not a pass.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_evidence_committed as cec  # noqa: E402


def _write_manifest(repo: Path, cells: list[dict]) -> None:
    d = repo / "docs" / "dev" / "validation-evidence"
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(
        json.dumps({"matrix": "test", "cells": cells}, indent=1), encoding="utf-8"
    )


def _write_evidence(repo: Path, rel: str, body: str = "evidence body\n") -> None:
    p = repo / "docs" / "dev" / "validation-evidence" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def test_valid_cell_passes(tmp_path):
    _write_evidence(tmp_path, "m/d/c/evidence.md")
    _write_manifest(tmp_path, [
        {"cell": "c", "quality": {"verdict": "pass", "evidence": "m/d/c/evidence.md"}},
    ])
    code, errors, _ = cec.check(tmp_path)
    assert code == 0 and errors == []


def test_pass_without_evidence_fails(tmp_path):
    _write_manifest(tmp_path, [{"cell": "c", "quality": {"verdict": "pass"}}])
    code, errors, _ = cec.check(tmp_path)
    assert code == 1
    assert any("without quality.evidence" in e for e in errors)


def test_missing_evidence_file_fails(tmp_path):
    _write_manifest(tmp_path, [
        {"cell": "c", "quality": {"verdict": "pass", "evidence": "m/d/c/nope.md"}},
    ])
    code, errors, _ = cec.check(tmp_path)
    assert code == 1
    assert any("evidence file missing" in e for e in errors)


def test_empty_evidence_file_fails(tmp_path):
    _write_evidence(tmp_path, "m/d/c/evidence.md", body="")
    _write_manifest(tmp_path, [
        {"cell": "c", "quality": {"verdict": "pass", "evidence": "m/d/c/evidence.md"}},
    ])
    code, errors, _ = cec.check(tmp_path)
    assert code == 1
    assert any("is empty" in e for e in errors)


def test_evidence_escaping_evidence_root_fails(tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("x", encoding="utf-8")
    _write_manifest(tmp_path, [
        {"cell": "c", "quality": {"verdict": "pass", "evidence": "../../../outside.md"}},
    ])
    code, errors, _ = cec.check(tmp_path)
    assert code == 1
    assert any("escapes" in e for e in errors)


def test_missing_artifact_fails(tmp_path):
    _write_evidence(tmp_path, "m/d/c/evidence.md")
    _write_manifest(tmp_path, [
        {
            "cell": "c",
            "quality": {"verdict": "not-applicable", "evidence": "m/d/c/evidence.md"},
            "artifacts": ["m/d/c/gone.txt"],
        },
    ])
    code, errors, _ = cec.check(tmp_path)
    assert code == 1
    assert any("artifact missing" in e for e in errors)


def test_missing_manifest_is_exit_2(tmp_path):
    code, errors, _ = cec.check(tmp_path)
    assert code == 2
    assert any("manifest not found" in e for e in errors)


def test_malformed_manifest_is_exit_2(tmp_path):
    d = tmp_path / "docs" / "dev" / "validation-evidence"
    d.mkdir(parents=True)
    (d / "manifest.json").write_text("{not json", encoding="utf-8")
    code, _errors, _ = cec.check(tmp_path)
    assert code == 2


def test_not_applicable_without_evidence_is_allowed(tmp_path):
    """Non-pass verdicts do not require evidence (they make no quality claim)."""
    _write_manifest(tmp_path, [{"cell": "c", "quality": {"verdict": "not-applicable"}}])
    code, errors, _ = cec.check(tmp_path)
    assert code == 0 and errors == []


@pytest.mark.parametrize("verdict", ["fail", "skip", "unknown"])
def test_non_pass_verdicts_never_require_evidence(tmp_path, verdict):
    _write_manifest(tmp_path, [{"cell": "c", "quality": {"verdict": verdict}}])
    code, errors, _ = cec.check(tmp_path)
    assert code == 0 and errors == []
