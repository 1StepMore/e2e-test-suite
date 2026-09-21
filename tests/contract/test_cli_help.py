"""CLI --help contract tests (Section 7.5).

Per plan Section 7.5, the CLI --help output of each module must be stable:
public CLI surface in minor versions, frozen in major versions. Any change
must be accompanied by a major version bump.

The fixtures in `tests/contract/fixtures/` are the current baseline. If a
test fails, the CLI surface has changed and either:
  1. The change is intentional — regenerate fixtures and document the change
  2. The change is accidental — revert the change

The fixtures are rendered through `.venv_ol/bin/python -m <module> --help`,
so they encode the uv.lock-pinned typer/click rendering (e.g. typer 0.24.2
renders `[OPTIONS] [COMMAND] [ARGS]`, 0.27.x renders `[OPTIONS] COMMAND`).
Regenerate only from a venv synced to uv.lock, or the oracle drifts from the
runtime (issue e2e#58).

Run with:
    pytest tests/contract/test_cli_help.py -v
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

SUITE_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
VENV_PYTHON = SUITE_ROOT / ".venv_ol" / "bin" / "python"
PYTHONPATH_SEP = ";" if sys.platform == "win32" else ":"

# Common log noise from the OPP/ORF CLI that pollutes stdout/stderr.
# We strip these before comparison because they include timestamps.
_LOG_NOISE_PATTERNS = [
    re.compile(r"^\[INFO\] Log file: .+$", re.MULTILINE),
    re.compile(r"^\[DEBUG\] .+$", re.MULTILINE),
    re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} .+$", re.MULTILINE),
    re.compile(r"\x1b\[[0-9;]*[A-Za-z]"),
    # PyMuPDF emits a one-line fitz deprecation warning on import (version
    # dependent); strip it — it is env noise, not CLI help content.
    re.compile(r"^warning: The `fitz` API is deprecated[^\n]*\n", re.MULTILINE),
]


def _normalize(text: str) -> str:
    for pattern in _LOG_NOISE_PATTERNS:
        text = pattern.sub("", text)
    text = text.replace("\r\n", "\n")
    return text.rstrip() + "\n"


def _run_help(module: str, src_path: str, label: str) -> str:
    """Run `python -m <module> --help` and return normalized stdout."""
    env = os.environ.copy()
    env["OMNI_TEST_FAKE_LLM"] = "1"
    env["OMNI_TEST_FAKE_PANDOC"] = "1"
    env["PYTHONPATH"] = PYTHONPATH_SEP.join(
        filter(None, [env.get("PYTHONPATH", ""), str(SUITE_ROOT / src_path)])
    )
    result = subprocess.run(
        [str(VENV_PYTHON), "-m", module, "--help"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(SUITE_ROOT),
        timeout=30,
    )
    output = result.stdout or ""
    if not output and result.stderr:
        output = result.stderr
    return _normalize(output)


def test_opp_help_contract():
    """OPP CLI --help must match the frozen fixture."""
    fixture = FIXTURES_DIR / "opp_help.txt"
    assert fixture.exists(), f"Missing fixture: {fixture}"
    expected = _normalize(fixture.read_text(encoding="utf-8"))
    actual = _run_help("opp.cli", "Omni_Pre_Processor/src", "opp")
    if actual != expected:
        diff_path = fixture.with_suffix(".actual.txt")
        diff_path.write_text(actual, encoding="utf-8")
        pytest.fail(
            f"OPP CLI --help output changed. Diff saved to {diff_path}.\n"
            f"If intentional, run: cp {diff_path} {fixture}"
        )


def test_ol_help_contract():
    """OL CLI --help must match the frozen fixture."""
    fixture = FIXTURES_DIR / "ol_help.txt"
    assert fixture.exists(), f"Missing fixture: {fixture}"
    expected = _normalize(fixture.read_text(encoding="utf-8"))
    actual = _run_help("ol_cli", "Omni_Localizer/src", "ol")
    if actual != expected:
        diff_path = fixture.with_suffix(".actual.txt")
        diff_path.write_text(actual, encoding="utf-8")
        pytest.fail(
            f"OL CLI --help output changed. Diff saved to {diff_path}.\n"
            f"If intentional, run: cp {diff_path} {fixture}"
        )


def test_orf_help_contract():
    """ORF CLI --help must match the frozen fixture."""
    fixture = FIXTURES_DIR / "orf_help.txt"
    assert fixture.exists(), f"Missing fixture: {fixture}"
    expected = _normalize(fixture.read_text(encoding="utf-8"))
    actual = _run_help("orf.cli", "Omni_Re_Formatter/src", "orf")
    if actual != expected:
        diff_path = fixture.with_suffix(".actual.txt")
        diff_path.write_text(actual, encoding="utf-8")
        pytest.fail(
            f"ORF CLI --help output changed. Diff saved to {diff_path}.\n"
            f"If intentional, run: cp {diff_path} {fixture}"
        )


def test_opp_help_lists_supported_input_formats():
    """OPP --help must document DOCX, PPTX, PDF, HTML, EPUB support.

    This is a content check (not a literal contract) so the test stays
    stable when argparse formatting changes.
    """
    actual = _run_help("opp.cli", "Omni_Pre_Processor/src", "opp")
    for fmt in ("DOCX", "PPTX", "PDF", "HTML", "EPUB"):
        assert fmt in actual, f"OPP --help missing format mention: {fmt}"


def test_orf_help_lists_apply_md_subcommand():
    """ORF --help must document the apply-md and apply-xliff subcommands."""
    actual = _run_help("orf.cli", "Omni_Re_Formatter/src", "orf")
    for sub in ("apply-md", "apply-xliff", "convert-batch", "info"):
        assert sub in actual, f"ORF --help missing subcommand: {sub}"


def test_ol_help_lists_translate_subcommands():
    """OL --help must document the translate-md/translate-xliff subcommands."""
    actual = _run_help("ol_cli", "Omni_Localizer/src", "ol")
    for sub in ("translate-md", "translate-xliff", "translate-batch", "extract-warnings"):
        assert sub in actual, f"OL --help missing subcommand: {sub}"
