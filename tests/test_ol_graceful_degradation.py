"""CI-G7: Verify OL CLI graceful fallback when API keys are missing.

When ``OMNI_TEST_FAKE_LLM`` is unset AND all real LLM API keys are
unset, the OL CLI must either:
  (a) translate successfully using a built-in fallback, OR
  (b) exit with a clear error message (not a stack trace / crash)

History: prior to this fix, all 12 OL-touching CI workflows set
``OMNI_TEST_FAKE_LLM=1`` unconditionally, so the "missing API key"
path was never exercised. The actual behavior was:
  1. ``import litellm`` takes ~30s on cold start
  2. ModelPool's Router init fails on the missing ``${VAR}`` refs
  3. The exception is caught → ``_test_mode = True``
  4. ``ModelPool.translate()`` returns the literal string "placeholder"
  5. CLI exits 0 with the source MD overwritten by "placeholder"

The fix (``precheck_api_keys()`` in ``cli/_shared.py``) scans the
config YAML for ``${VAR}`` placeholders and exits non-zero with
a clear, actionable error BEFORE any expensive LLM work — bypassing
the 30s litellm import entirely. This test pins the contract.

This test runs ``ol translate-md`` in a subprocess with the env
carefully cleared, so it does NOT contaminate the parent test env.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

SUITE_ROOT = Path(__file__).resolve().parent.parent
OL_SRC = SUITE_ROOT / "Omni_Localizer" / "src"


def _build_input_md(tmp_path: Path) -> Path:
    md = tmp_path / "g7_input.md"
    md.write_text(
        "---\n"
        "source_lang: en\n"
        "target_lang: zh\n"
        "---\n"
        "\n"
        "# Hello\n"
        "\n"
        "This is a short test sentence for the missing-API-key path.\n",
        encoding="utf-8",
    )
    return md


def _clean_env() -> dict[str, str]:
    """Return an env dict with all *_API_KEY unset and FAKE_LLM disabled."""
    env = os.environ.copy()
    for k in ("OMNI_TEST_FAKE_LLM", "OMNI_RUN_REAL_LLM", "OPENCODE_GO_KEY", "OPENCODE_GO_BASE_URL"):
        env.pop(k, None)
    for k in list(env.keys()):
        if k.endswith("_API_KEY") or k.endswith("_BASE_URL"):
            env.pop(k, None)
    env["PYTHONPATH"] = str(OL_SRC)
    return env


class TestOLGracefulDegradation:
    """CI-G7: OL must not silently return source text on missing keys."""

    def test_ol_cli_does_not_silently_succeed_without_keys(self, tmp_path: Path):
        """Run ``ol translate-md`` with no API keys and no FAKE_LLM.

        Acceptance: the CLI either (a) succeeds with a translated output
        (i.e. some fallback path is wired up), OR (b) exits non-zero
        with a clear error in stderr.

        What MUST NOT happen: silent success returning the unmodified
        source text, or a hang >15s.
        """
        input_md = _build_input_md(tmp_path)
        output_dir = tmp_path / "out"
        output_dir.mkdir()

        env = _clean_env()
        # Do NOT call .resolve() here — the venv is a symlink and
        # resolving past the symlink bypasses pyvenv.cfg, leaving
        # the subprocess Python without the venv's site-packages
        # (typer, litellm, etc.). The symlink form is what triggers
        # pyvenv.cfg processing and the site-packages bootstrap.
        python_exe = str(Path(sys.executable).absolute())
        cmd = [
            python_exe,
            "-m",
            "ol_cli",
            "translate-md",
            str(input_md),
            "-s", "en",
            "-t", "zh",
            "-o", str(output_dir),
        ]

        try:
            proc = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
                cwd=str(SUITE_ROOT / "Omni_Localizer"),
            )
        except subprocess.TimeoutExpired:
            try:
                import psutil  # type: ignore
                for p in psutil.process_iter(["cmdline"]):
                    if p.info["cmdline"] and any(
                        "ol_cli" in c for c in p.info["cmdline"]
                    ):
                        p.kill()
            except ImportError:
                subprocess.run(
                    ["pkill", "-9", "-f", "ol_cli"],
                    check=False,
                    capture_output=True,
                )
            raise AssertionError(
                "CI-G7: ol translate-md hung >15s with no API keys. "
                "CLI should fail fast with a clear error, not hang."
            )

        output_md = output_dir / "g7_input.md"
        if proc.returncode == 0:
            if output_md.exists():
                content = output_md.read_text(encoding="utf-8")
                if "placeholder" in content.lower():
                    raise AssertionError(
                        "CI-G7: ol translate-md silently returned the LLM "
                        f"'placeholder' string (Router init failed + test_mode "
                        f"path) with exit=0. stderr:\n{proc.stderr!r}"
                    )
                if "Hello" in content and "你好" not in content:
                    raise AssertionError(
                        "CI-G7: ol translate-md silently returned source "
                        f"text with exit=0 when API keys were missing. "
                        f"Output:\n{content!r}\n"
                        f"stderr:\n{proc.stderr!r}"
                    )
        else:
            assert "API" in proc.stderr or "key" in proc.stderr.lower() or \
                   "config" in proc.stderr.lower() or \
                   "FAKE_LLM" in proc.stderr or \
                   "ValueError" in proc.stderr, (
                f"CI-G7: ol translate-md failed with exit={proc.returncode} "
                f"but stderr lacks a clear error. stderr:\n{proc.stderr!r}"
            )

    def test_sigint_exit_code_3(self, tmp_path: Path):
        """Process-level test: SIGINT during translate-batch → exit code 3 (INTERRUPTED).

        Verifies that Ctrl+C during a batch translation triggers the signal handler
        and the process exits with ExitCode.INTERRUPTED (3) instead of hanging or
        silently succeeding.

        Also documents the expected behaviour for:
        - SIGTERM: currently NOT handled (default terminate behaviour)
        - Network loss: manifests as per-unit Exceptions → fallback to source
        - Mid-pipeline crash: no recovery — partial output on disk
        """
        batch_dir = tmp_path / "batch"
        batch_dir.mkdir()
        for i in range(3):
            p = batch_dir / f"ch{i}.md"
            p.write_text(
                "# Chapter {0}\n\n"
                "This is a long paragraph to ensure the translator has enough "
                "work to do before SIGINT arrives.\n\n"
                "## Section {0}.1\n\n"
                "Another paragraph to keep the processor busy.\n\n"
                "## Section {0}.2\n\n"
                "Yet more text to ensure the batch enqueue loop is active.\n".format(i),
                encoding="utf-8",
            )

        env = os.environ.copy()
        env["OMNI_TEST_FAKE_LLM"] = "1"
        env["OMNI_RUN_REAL_LLM"] = ""
        env["PYTHONPATH"] = str(OL_SRC)
        for k in list(env.keys()):
            if k.endswith("_API_KEY") or k.endswith("_KEY") or k.endswith("_BASE_URL"):
                env.pop(k)

        out_dir = tmp_path / "out"
        out_dir.mkdir()

        proc = subprocess.Popen(
            [sys.executable, "-m", "ol_cli", "translate-batch",
             str(batch_dir), "-s", "en", "-t", "zh", "-o", str(out_dir)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(SUITE_ROOT / "Omni_Localizer"),
        )

        # Cold-start import takes ~6s. During import the Python-level
        # signal handler cannot run (CPython is in C-level import code),
        # so we wait for import to complete before sending SIGINT.
        # The batch then has a ~0.6s processing window for 5 small files.
        t0 = time.monotonic()
        rc = None
        while time.monotonic() - t0 < 15:
            if proc.poll() is not None:
                rc = proc.returncode
                break
            # Start sending SIGINT after 6s (import should be done)
            if time.monotonic() - t0 > 6.0:
                proc.send_signal(signal.SIGINT)
            time.sleep(0.25)

        if rc is None:
            proc.kill()
            proc.wait(timeout=2)
            pytest.fail("Process did not exit within 15s after SIGINT")

        stdout_text = proc.stdout.read().decode() if proc.stdout else ""
        stderr_text = proc.stderr.read().decode() if proc.stderr else ""

        assert rc == 3, (
            f"Expected exit code 3 (INTERRUPTED), got {rc}\n"
            f"stdout (last 1000 chars): {stdout_text[-1000:]}\n"
            f"stderr (last 2000 chars): {stderr_text[-2000:]}"
        )
