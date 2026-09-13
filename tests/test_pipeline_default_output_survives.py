"""T-02 regression: `omni-suite pipeline` must not delete its own output.

When ``--output`` is omitted the CLI auto-generates the final artifact path. The
bug: that path lived inside the per-run temp dir
(``/tmp/omni-suite-pipeline/<stem>``) which the ``finally`` block removes via
``shutil.rmtree`` — so the path printed at exit
(``✅ Pipeline complete: <path>``) was already gone.

These tests drive the real CLI through subprocess (FAKE_LLM seam) and assert the
*file* exists on disk, not merely that the success banner was printed.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SUITE_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DOCX = SUITE_ROOT / "tests" / "production" / "small_fixture.docx"
PIPELINE_TMP_ROOT = Path("/tmp/omni-suite-pipeline")
_COMPLETE_RE = re.compile(r"Pipeline complete:\s*(?P<path>\S+)")

# Conftest installs these too; pin them here so the subprocess env is
# self-contained regardless of import order.
_DUMMY_KEYS = {
    "ZHIPU_API_KEY": "sk-dummy",
    "AGNES_API_KEY": "sk-dummy",
    "NVIDIA_NIM_API_KEY": "nvapi-dummy",
    "OPENCODE_GO_KEY": "sk-dummy",
}


def _pipeline_env() -> dict[str, str]:
    return {
        **os.environ,
        **_DUMMY_KEYS,
        "OMNI_TEST_FAKE_LLM": "1",
        "OL_CONFIG_PATH": str(
            SUITE_ROOT / "Omni_Localizer" / "config" / "test_universal.yaml"
        ),
    }


def _run_pipeline(*extra_args: str) -> "subprocess.CompletedProcess[str]":
    assert FIXTURE_DOCX.exists(), f"Fixture missing: {FIXTURE_DOCX}"
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "omni_suite",
            "pipeline",
            str(FIXTURE_DOCX),
            "--fake-llm",
            "--target-format",
            "docx",
            *extra_args,
        ],
        capture_output=True,
        text=True,
        cwd=str(SUITE_ROOT),
        env=_pipeline_env(),
        timeout=300,
    )


def _reported_path(stdout: str) -> Path:
    match = _COMPLETE_RE.search(stdout)
    assert match, f"No 'Pipeline complete: <path>' line in stdout:\n{stdout}"
    return Path(match.group("path"))


@pytest.fixture
def clean_pipeline_state():
    """Remove the per-run temp dir and any default artifact before/after a test."""
    stem = FIXTURE_DOCX.stem

    def _cleanup() -> None:
        shutil.rmtree(PIPELINE_TMP_ROOT / stem, ignore_errors=True)
        for leftover in PIPELINE_TMP_ROOT.glob(f"{stem}.result.*"):
            leftover.unlink(missing_ok=True)

    _cleanup()
    yield
    _cleanup()


class TestExplicitOutput:
    """Characterization baseline — already true before the T-02 fix."""

    def test_explicit_output_file_exists_after_exit(
        self, tmp_path: Path, clean_pipeline_state
    ):
        out = tmp_path / "explicit.docx"
        result = _run_pipeline("--output", str(out))
        assert result.returncode == 0, result.stderr
        assert out.exists() and out.stat().st_size > 0, (
            "explicit --output missing after exit\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


class TestDefaultOutput:
    """T-02 — the auto-generated output must survive the temp-dir cleanup."""

    def test_default_output_file_exists_after_exit(self, clean_pipeline_state):
        result = _run_pipeline()  # no --output
        assert result.returncode == 0, (
            f"pipeline failed rc={result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

        reported = _reported_path(result.stdout)

        # Assert the FILE, not the banner: "Pipeline complete" alone proves nothing.
        assert reported.exists(), (
            f"Printed output path was deleted by cleanup: {reported}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert reported.stat().st_size > 0, f"Printed output is empty: {reported}"

        # ...and it must live OUTSIDE the per-run temp dir that cleanup removes.
        temp_dir = (PIPELINE_TMP_ROOT / FIXTURE_DOCX.stem).resolve()
        assert not reported.resolve().is_relative_to(temp_dir), (
            f"reported output {reported} is inside the cleanup temp dir {temp_dir}"
        )
