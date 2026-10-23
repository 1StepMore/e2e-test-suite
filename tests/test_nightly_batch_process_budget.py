"""Tests for the AutoInfo process-budget capability probe (AutoInfo#596).

The suite must adopt AutoInfo's total-budget flags without breaking on a
checkout that predates them, so the ``ai-process`` step emits those flags only
when ``nightly_process.py --help`` advertises them.
"""
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HELPER = REPO / "scripts" / "lib" / "nightly_budget_args.sh"
BATCH = REPO / "scripts" / "nightly_batch.sh"

MODERN_HELP = """usage: nightly_process.py [-h] [--min-backlog N] [--max-seconds N]
                          [--batch-size N] [--seconds-per-item F]
                          [--newest-first]
"""

LEGACY_HELP = """usage: nightly_process.py [-h] [--min-backlog N] [--timeout N]
"""


def _emitted(help_text: str, *values: object) -> list[str]:
    script = f'. "{HELPER}"\nnightly_budget_args "$@"\n'
    completed = subprocess.run(
        ["bash", "-c", script, "bash", help_text, *map(str, values)],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.split()


def test_modern_help_derives_the_budget_when_no_batch_is_given():
    """max-seconds is the budget; batch size 0 leaves per-domain derivation to
    AutoInfo, so no --batch-size is emitted."""
    assert _emitted(MODERN_HELP, 1800, 0, 40) == [
        "--max-seconds",
        "1800",
        "--newest-first",
        "--seconds-per-item",
        "40",
    ]


def test_an_explicit_batch_is_forwarded():
    assert _emitted(MODERN_HELP, 1800, 25, 40) == [
        "--max-seconds",
        "1800",
        "--newest-first",
        "--batch-size",
        "25",
        "--seconds-per-item",
        "40",
    ]


def test_a_pre_596_checkout_gets_no_flags():
    """A wrapper without the budget flags must keep working unchanged."""
    assert _emitted(LEGACY_HELP, 1800, 0, 40) == []


def test_partial_support_still_emits_the_core_budget():
    """--seconds-per-item is optional; --max-seconds/--newest-first are the
    contract the suite depends on."""
    help_text = MODERN_HELP.replace("[--seconds-per-item F]", "")
    assert _emitted(help_text, 1800, 0, 40) == [
        "--max-seconds",
        "1800",
        "--newest-first",
    ]


def test_batch_entrypoint_probes_before_the_process_step():
    """Wiring guard: the help probe + flag expansion must feed the ai-process
    run_step, not be defined and forgotten."""
    source = BATCH.read_text(encoding="utf-8")

    assert "lib/nightly_budget_args.sh" in source
    probe_at = source.index("nightly_budget_args")
    process_at = source.index("run_step ai-process")
    assert probe_at < process_at
    assert "proc_budget" in source[probe_at:process_at]
