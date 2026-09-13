"""R-01 regression: pipeline checkpoint/resume surface.

Gap register R-01 (``.omo/plans/agent-oriented-gap-register.md`` §4.2) fixes
the missing suite-level resume surface:

1. A mid-stage failure must persist a run manifest with per-stage status and
   report ``{status: partial, completed: N, resume_hint}`` so an agent can
   recover without guessing.
2. ``--resume-from <stage>`` (stage in {opp, ol, orf}) reuses existing
   intermediate artifacts for every stage *before* ``<stage>`` and continues.
3. When those intermediates are absent (or the manifest is stale), the run
   falls back to a full pipeline instead of faking a resume.

The fast tests drive ``cli._run_pipeline`` with the subprocess seam patched so
stage ordering is observable without spinning up OPP/OL/ORF. No full pipeline
is executed — path/state logic is asserted directly.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from omni_suite import cli

SUITE_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DOCX = SUITE_ROOT / "tests" / "production" / "small_fixture.docx"
PIPELINE_TMP_ROOT = Path("/tmp/omni-suite-pipeline")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stage_of(cmd: list[str]) -> str:
    """Classify a pipeline subprocess command as opp/ol/orf."""
    if len(cmd) > 1 and cmd[1] == "translate-md":
        return "ol"
    if len(cmd) > 1 and cmd[1] == "apply-md":
        return "orf"
    return "opp"


class FakeRunner:
    """Stand-in for ``subprocess.run`` that fabricates intermediate artifacts.

    Records the stage of every invocation so a test can prove which stages
    actually ran. Optionally raises ``CalledProcessError`` for one stage to
    simulate a mid-pipeline failure.
    """

    def __init__(self, stem: str, fail_stage: str | None = None) -> None:
        self.stem = stem
        self.fail_stage = fail_stage
        self.kinds: list[str] = []

    def __call__(self, cmd, **kwargs):  # noqa: ANN001 - mirrors subprocess.run
        cmd = [str(c) for c in cmd]
        stage = _stage_of(cmd)
        self.kinds.append(stage)
        if stage == self.fail_stage:
            raise subprocess.CalledProcessError(1, cmd, output="", stderr="boom")
        if stage == "opp":
            out_dir = Path(cmd[cmd.index("--output-dir") + 1])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{self.stem}.md").write_text("source md", encoding="utf-8")
        elif stage == "ol":
            out_dir = Path(cmd[cmd.index("-o") + 1])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{self.stem}.md").write_text("translated md", encoding="utf-8")
        elif stage == "orf":
            out = Path(cmd[cmd.index("-o") + 1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"PK-fake-docx")
        return subprocess.CompletedProcess(cmd, 0, "", "")


def _partial_payload(stdout: str) -> dict:
    """Extract the last JSON object printed on stdout."""
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"no JSON object on stdout:\n{stdout}")


def _invoke(args: list[str], monkeypatch, runner: FakeRunner) -> int:
    """Run ``cli._run_pipeline`` with subprocess.run patched; return exit code.

    ``stdout``/``stderr`` are captured by ``capsys`` in the test body.
    """
    monkeypatch.setattr(cli.subprocess, "run", runner)
    try:
        cli._run_pipeline(args)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0
    return 0


@pytest.fixture
def run_id() -> str:
    rid = f"r01-unit-{uuid.uuid4().hex[:10]}"
    yield rid
    shutil.rmtree(PIPELINE_TMP_ROOT / rid, ignore_errors=True)


def _base_args(run_id: str, out: Path, *extra: str) -> list[str]:
    return [
        str(FIXTURE_DOCX),
        "--fake-llm",
        "--target-format",
        "docx",
        "--run-id",
        run_id,
        "--output",
        str(out),
        *extra,
    ]


# ---------------------------------------------------------------------------
# Unit tests — fast, hermetic, subprocess seam patched
# ---------------------------------------------------------------------------

class TestPartialReporting:
    def test_mid_stage_failure_reports_partial_and_resume_hint(
        self, monkeypatch, capsys, run_id, tmp_path
    ):
        runner = FakeRunner(FIXTURE_DOCX.stem, fail_stage="orf")
        rc = _invoke(_base_args(run_id, tmp_path / "out.docx"), monkeypatch, runner)
        assert rc == 1

        payload = _partial_payload(capsys.readouterr().out)
        assert payload["status"] == "partial"
        assert payload["completed"] == 2
        assert "--resume-from orf" in payload["resume_hint"]

        manifest = json.loads(
            (PIPELINE_TMP_ROOT / run_id / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["status"] == "partial"
        assert manifest["failed_stage"] == "orf"
        assert manifest["stages"]["opp"]["status"] == "complete"
        assert manifest["stages"]["ol"]["status"] == "complete"
        assert manifest["stages"]["orf"]["status"] == "failed"

    def test_failure_at_ol_reports_completed_one(
        self, monkeypatch, capsys, run_id, tmp_path
    ):
        runner = FakeRunner(FIXTURE_DOCX.stem, fail_stage="ol")
        rc = _invoke(_base_args(run_id, tmp_path / "out.docx"), monkeypatch, runner)
        assert rc == 1

        payload = _partial_payload(capsys.readouterr().out)
        assert payload["status"] == "partial"
        assert payload["completed"] == 1
        assert "--resume-from ol" in payload["resume_hint"]


class TestResume:
    def test_resume_from_orf_skips_opp_and_ol(
        self, monkeypatch, capsys, run_id, tmp_path
    ):
        out = tmp_path / "out.docx"
        # First run dies at ORF, leaving opp + ol intermediates on disk.
        rc = _invoke(
            _base_args(run_id, out), monkeypatch,
            FakeRunner(FIXTURE_DOCX.stem, fail_stage="orf"),
        )
        assert rc == 1
        capsys.readouterr()

        # Resume starts at ORF: opp + ol must NOT be re-run.
        resume_runner = FakeRunner(FIXTURE_DOCX.stem)
        rc = _invoke(
            _base_args(run_id, out, "--resume-from", "orf"),
            monkeypatch, resume_runner,
        )
        assert rc == 0

        assert resume_runner.kinds == ["orf"], resume_runner.kinds
        manifest = json.loads(
            (PIPELINE_TMP_ROOT / run_id / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["status"] == "complete"
        assert manifest["stages"]["opp"]["status"] == "reused"
        assert manifest["stages"]["ol"]["status"] == "reused"
        assert manifest["stages"]["orf"]["status"] == "complete"
        assert out.exists()

    def test_resume_falls_back_to_full_run_without_intermediates(
        self, monkeypatch, capsys, run_id, tmp_path
    ):
        # No prior run: --resume-from must not pretend; run all three stages.
        runner = FakeRunner(FIXTURE_DOCX.stem)
        rc = _invoke(
            _base_args(run_id, tmp_path / "out.docx", "--resume-from", "orf"),
            monkeypatch, runner,
        )
        assert rc == 0
        assert runner.kinds == ["opp", "ol", "orf"], runner.kinds

    def test_stale_manifest_without_intermediates_falls_back(
        self, monkeypatch, capsys, run_id, tmp_path
    ):
        # Manifest claims opp/ol are done, but the artifacts were deleted.
        run_dir = PIPELINE_TMP_ROOT / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "input_file": str(FIXTURE_DOCX),
                    "status": "partial",
                    "failed_stage": "orf",
                    "stages": {
                        "opp": {"status": "complete"},
                        "ol": {"status": "complete"},
                        "orf": {"status": "failed"},
                    },
                }
            ),
            encoding="utf-8",
        )
        runner = FakeRunner(FIXTURE_DOCX.stem)
        rc = _invoke(
            _base_args(run_id, tmp_path / "out.docx", "--resume-from", "orf"),
            monkeypatch, runner,
        )
        assert rc == 0
        assert runner.kinds == ["opp", "ol", "orf"], runner.kinds

    def test_repeated_failure_can_be_resumed_again(
        self, monkeypatch, capsys, run_id, tmp_path
    ):
        out = tmp_path / "out.docx"
        rc = _invoke(
            _base_args(run_id, out), monkeypatch,
            FakeRunner(FIXTURE_DOCX.stem, fail_stage="orf"),
        )
        assert rc == 1
        capsys.readouterr()
        # Resume, but ORF fails again: hint must still point at orf.
        rc = _invoke(
            _base_args(run_id, out, "--resume-from", "orf"), monkeypatch,
            FakeRunner(FIXTURE_DOCX.stem, fail_stage="orf"),
        )
        assert rc == 1
        payload = _partial_payload(capsys.readouterr().out)
        assert payload["status"] == "partial"
        assert payload["completed"] == 2
        assert "--resume-from orf" in payload["resume_hint"]

    def test_invalid_resume_stage_is_rejected(self, monkeypatch, run_id, tmp_path):
        rc = _invoke(
            _base_args(run_id, tmp_path / "out.docx", "--resume-from", "bogus"),
            monkeypatch, FakeRunner(FIXTURE_DOCX.stem),
        )
        assert rc == 2
