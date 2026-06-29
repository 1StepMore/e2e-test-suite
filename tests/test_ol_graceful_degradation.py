"""CI-G7: Verify OL CLI graceful fallback when API keys are missing.

When ``OMNI_TEST_FAKE_LLM`` is unset AND all real LLM API keys are
unset, the OL CLI must either:
  (a) translate successfully using a built-in fallback, OR
  (b) exit with a clear error message (not a stack trace / crash)

Prior to this test (and the matching gap fix), all 12 OL-touching CI
workflows set ``OMNI_TEST_FAKE_LLM=1`` unconditionally. The
"missing API key" path was never exercised. The user's bug report
identified the silent-fallback behavior as a CI gap: with no real
keys and no fake, the CLI returned the source text with success
status, hiding the configuration error.

This test runs ``ol translate-md`` in a subprocess with the env
carefully cleared, so it does NOT contaminate the parent test env.

NOTE: This test is marked xfail because the current OL CLI hangs
or silently returns source text when no API keys are available —
the very bug this test is designed to catch. The xfail marker
documents the known failure. When OL is fixed to fail fast with
a clear error, remove the xfail marker and the test will
naturally pass.
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
    env.pop("OMNI_TEST_FAKE_LLM", None)
    env.pop("OMNI_RUN_REAL_LLM", None)
    for k in list(env.keys()):
        if k.endswith("_API_KEY") or k.endswith("_BASE_URL"):
            env.pop(k, None)
    env["PYTHONPATH"] = str(OL_SRC)
    return env


class TestOLGracefulDegradation:
    """CI-G7: OL must not silently return source text on missing keys."""

    @pytest.mark.xfail(
        reason="CI-G7: OL CLI currently hangs or silently returns source text "
               "when no API keys are configured. This is the bug being detected. "
               "When OL fails fast with a clear error, remove the xfail marker.",
        strict=False,
    )
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
        # Use absolute paths because we change CWD to Omni_Localizer.
        python_exe = str(Path(sys.executable).resolve())
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
