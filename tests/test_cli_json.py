"""``omni-suite --json``: the CLI's machine-readable channel (issue #103).

An agent driving the suite has two reliable channels: the exit code and
something it can parse. Exit codes were already a deliberate taxonomy, so these
tests pin the second one and, just as importantly, pin that the human channel
did not move:

* every ``--json`` run puts exactly one JSON envelope on stdout;
* both success and failure paths answer with an envelope, and the exit code is
  exactly the one the same command produced without ``--json``;
* the human text (progress, warnings, usage) lands on stderr;
* the same command without ``--json`` is byte-identical to before the flag
  existed — asserted two ways, because a static golden of ``--version`` alone
  would pin the *version numbers* and go stale on every legitimate bump: a
  golden snapshot of the pre-change bytes, plus mode parity (the stderr of a
  ``--json`` run IS the stdout of the plain run, byte for byte) for the
  renderers this change rewrote (``status``, ``check --quick``, usage).
"""
from __future__ import annotations

import functools
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

SUITE_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DOCX = SUITE_ROOT / "tests" / "production" / "small_fixture.docx"
GOLDEN_VERSION = SUITE_ROOT / "tests" / "golden" / "cli" / "version.stdout"
PIPELINE_TMP_ROOT = Path("/tmp/omni-suite-pipeline")


def _run(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    """Invoke the real CLI through its shipped ``python -m`` entry point."""
    return subprocess.run(
        [sys.executable, "-m", "omni_suite", *args],
        capture_output=True,
        text=True,
        cwd=str(SUITE_ROOT),
        env={**os.environ, "OMNI_TEST_FAKE_LLM": ""},
        timeout=timeout,
    )


@functools.cache
def _plain(*args: str) -> subprocess.CompletedProcess[str]:
    """Cached plain-mode run for the parity checks — all of them are pure reads."""
    return _run(*args)


def _envelope(result: subprocess.CompletedProcess[str]) -> dict:
    """Parse stdout as the one JSON envelope it must contain.

    ``json.loads`` alone already rejects trailing non-JSON text; the line
    assertions state that contract explicitly so a reader knows a multi-line or
    pretty-printed stream would be a regression, not a style choice.
    """
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1, f"stdout must be one JSON line, got {len(lines)}:\n{result.stdout}"
    assert lines[0].startswith("{") and lines[0].endswith("}"), (
        f"stdout must be JSON only:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return json.loads(lines[0])


def _version_file_value() -> str:
    """The first non-comment line of ``VERSION`` — the value ``--versions`` prints."""
    for line in (SUITE_ROOT / "VERSION").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    raise AssertionError("VERSION file has no value line")


class TestVersionEnvelope:
    """``--json --version`` → parseable envelope, exit 0."""

    def test_version_stdout_is_json_and_exits_zero(self):
        result = _run("--json", "--version")

        assert result.returncode == 0, result.stderr
        payload = _envelope(result)
        assert payload["success"] is True
        assert payload["error"] is None
        assert payload["exit_code"] == 0
        assert payload["command"] == "--version"
        assert payload["content"]["version"] == _version_file_value()

    def test_version_human_text_moved_to_stderr(self):
        result = _run("--json", "--version")

        _envelope(result)  # stdout is the envelope line and nothing else
        assert "Suite version" in result.stderr, result.stderr


class TestSuccessEnvelope:
    """``--json status`` / ``check --quick`` → JSON-only stdout, same exit code."""

    def test_status_stdout_is_json_only(self):
        result = _run("--json", "status")

        payload = _envelope(result)
        assert payload["success"] is True
        assert payload["command"] == "status"
        assert set(payload["content"]["modules"]) == {"OPP", "OL", "ORF"}
        assert "pandoc" in payload["content"]["dependencies"]

    def test_status_exit_code_matches_plain_invocation(self):
        assert _run("--json", "status").returncode == _plain("status").returncode == 0

    def test_check_quick_stdout_is_json_only(self):
        result = _run("--json", "check", "--quick")

        payload = _envelope(result)
        assert payload["success"] is True
        assert payload["content"]["quick"] is True
        assert _plain("check", "--quick").returncode == result.returncode == 0

    def test_human_text_is_on_stderr_not_stdout(self):
        result = _run("--json", "status")

        assert "Omni Suite:" in result.stderr, result.stderr
        assert "Dependencies:" in result.stderr, result.stderr
        assert "Dependencies:" not in result.stdout
        assert "Omni Suite:" not in result.stdout


class TestFailureEnvelope:
    """Failure paths answer with an envelope and an unchanged exit code."""

    def test_unknown_command_envelope_and_exit_1(self):
        plain = _plain("nonexistent-command")
        result = _run("--json", "nonexistent-command")

        assert result.returncode == plain.returncode == 1
        payload = _envelope(result)
        assert payload["success"] is False
        assert payload["error"]["code"] == "OMNI_UNKNOWN_COMMAND"
        assert "nonexistent-command" in payload["error"]["message"]
        assert payload["exit_code"] == 1
        assert payload["error_code"] == payload["error"]["code"]

    def test_invalid_resume_from_envelope_and_exit_2(self):
        assert FIXTURE_DOCX.exists(), f"Fixture missing: {FIXTURE_DOCX}"
        plain = _plain("pipeline", str(FIXTURE_DOCX), "--dry-run", "--resume-from", "bogus")
        result = _run(
            "--json", "pipeline", str(FIXTURE_DOCX), "--dry-run", "--resume-from", "bogus"
        )

        assert result.returncode == plain.returncode == 2
        payload = _envelope(result)
        assert payload["success"] is False
        assert payload["error"]["code"] == "OMNI_INVALID_INPUT"
        assert "--resume-from" in payload["error"]["message"]
        assert payload["exit_code"] == 2

    def test_failing_stage_envelope_keeps_exit_1_and_manifest(self, tmp_path):
        """A stage subprocess fails: the envelope carries the partial-run state."""
        run_id = f"cli-json-{uuid.uuid4().hex[:10]}"
        try:
            result = _run(
                "--json", "pipeline", str(tmp_path / "does-not-exist.docx"),
                "--gates-only", "--run-id", run_id,
            )

            assert result.returncode == 1
            payload = _envelope(result)
            assert payload["success"] is False
            assert payload["error"]["code"] == "OPP_FAILED"
            assert payload["content"]["run"]["status"] == "partial"
            assert payload["content"]["stages"]["opp"]["status"] == "failed"
            assert "Pipeline step failed:" in result.stderr, result.stderr
        finally:
            shutil.rmtree(PIPELINE_TMP_ROOT / run_id, ignore_errors=True)

    def test_stage_cli_stdout_does_not_leak_into_the_envelope(self, tmp_path):
        """A real 3-stage run: the child CLIs print, stdout must stay pure JSON.

        OPP/OL/ORF inherit fd 1, so without the stderr pinning in
        ``JsonOutput.stage_stdout`` their progress would corrupt the envelope —
        this is the regression that only a real spawn can catch.
        """
        run_id = f"cli-json-{uuid.uuid4().hex[:10]}"
        try:
            result = _run(
                "--json", "pipeline", str(FIXTURE_DOCX), "--fake-llm",
                "--target-format", "docx", "--output", str(tmp_path / "out.docx"),
                "--run-id", run_id, timeout=300,
            )

            assert result.returncode == 0, result.stderr
            payload = _envelope(result)
            assert payload["content"]["run"]["status"] == "complete"
            assert payload["content"]["output"] == str(tmp_path / "out.docx")
            assert (tmp_path / "out.docx").exists()
            # ORF prints "[INFO] Converting …" on its own stdout — human channel.
            assert "Pipeline complete" in result.stderr, result.stderr
        finally:
            shutil.rmtree(PIPELINE_TMP_ROOT / run_id, ignore_errors=True)


class TestNonRegression:
    """Without ``--json`` the output is byte-identical to the pre-change CLI."""

    def test_version_stdout_matches_golden_snapshot(self, request):
        result = _run("--version")

        if request.config.getoption("--golden-capture"):
            GOLDEN_VERSION.parent.mkdir(parents=True, exist_ok=True)
            GOLDEN_VERSION.write_text(result.stdout, encoding="utf-8")
        assert GOLDEN_VERSION.exists(), (
            f"missing golden {GOLDEN_VERSION}; regenerate with "
            "`pytest tests/test_cli_json.py --golden-capture`"
        )
        assert result.stdout == GOLDEN_VERSION.read_text(encoding="utf-8")

    def test_version_stdout_is_the_version_file_verbatim(self):
        expected = (SUITE_ROOT / "VERSION").read_text(encoding="utf-8").strip() + "\n"

        assert _run("--version").stdout == expected

    def test_status_stderr_equals_plain_stdout(self):
        assert _run("--json", "status").stderr == _run("status").stdout

    def test_check_quick_stderr_equals_plain_stdout(self):
        assert _run("--json", "check", "--quick").stderr == _run("check", "--quick").stdout

    def test_help_stderr_equals_plain_stdout(self):
        assert _run("--json", "--help").stderr == _run("--help").stdout
