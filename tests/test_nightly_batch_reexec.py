"""Regression tests for e2e-test-suite#212.

Bash reads a script incrementally from the inode opened at startup. When a
batch run syncs its work tree with ``git checkout main`` mid-run, the file is
replaced (new inode) and the rest of the run keeps reading the OLD branch's
copy — so steps added on main are silently skipped, with exit 0 and no error.

These tests build REAL two-branch git repos under ``tmp_path`` and exercise the
real helper in ``scripts/lib/nightly_reexec.sh``, plus assert the production
entrypoint wires it in after ``preflight`` and before the first step.
"""
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HELPER = REPO / "scripts" / "lib" / "nightly_reexec.sh"
BATCH = REPO / "scripts" / "nightly_batch.sh"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _entry_script(*, with_process: bool) -> str:
    process_step = 'echo "step: ai-process"\n' if with_process else ""
    return f'''#!/usr/bin/env bash
set -uo pipefail
. "{HELPER}"
ORIG_ARGS=("$@")
SELF_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
ENTRY="$SELF_DIR/$(basename "${{BASH_SOURCE[0]}}")"
HASH="$(nightly_file_hash "$ENTRY" || true)"
echo "step: ai-collect"
git -C "$SELF_DIR" checkout -q main
nightly_reexec_if_changed "$ENTRY" "$HASH" ${{ORIG_ARGS[@]+"${{ORIG_ARGS[@]}}"}}
{process_step}echo "step: ai"
'''


def _make_two_branch_repo(tmp_path: Path) -> Path:
    """main has ``ai-process``; branch ``old`` does not. Returns on ``old``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "nightly@example.invalid")
    _git(repo, "config", "user.name", "nightly-reexec-test")

    (repo / "entry.sh").write_text(_entry_script(with_process=True), encoding="utf-8")
    _git(repo, "add", "entry.sh")
    _git(repo, "commit", "-qm", "main: add ai-process")

    _git(repo, "checkout", "-qb", "old")
    (repo / "entry.sh").write_text(_entry_script(with_process=False), encoding="utf-8")
    _git(repo, "add", "entry.sh")
    _git(repo, "commit", "-qm", "old: no ai-process")
    return repo


def _run_entry(repo: Path) -> str:
    return subprocess.run(
        ["bash", "entry.sh"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _branch(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_branch_switch_mid_run_executes_the_new_entrypoint(tmp_path):
    """The reported bug, reproduced: without the helper the old copy finishes
    and ``ai-process`` never runs. With it, the post-switch copy takes over."""
    repo = _make_two_branch_repo(tmp_path)

    out = _run_entry(repo)

    assert "step: ai-process" in out
    assert _branch(repo) == "main"


def test_unchanged_entrypoint_is_not_re_executed(tmp_path):
    """Already on main: the sync is a no-op, the hash matches, so the script
    must NOT restart itself (``ai-collect`` appears exactly once)."""
    repo = _make_two_branch_repo(tmp_path)
    _git(repo, "checkout", "-q", "main")

    out = _run_entry(repo)

    assert out.count("step: ai-collect") == 1
    assert "step: ai-process" in out


def test_batch_entrypoint_reexecs_after_preflight_before_first_step():
    """Wiring guard: the re-exec must sit between the sync (``preflight``) and
    the first ``run_step``, and argv must be captured before parsing shifts it."""
    source = BATCH.read_text(encoding="utf-8")

    assert "lib/nightly_reexec.sh" in source
    reexec_at = source.index("nightly_reexec_if_changed")
    assert source.index("\npreflight\n") < reexec_at
    assert reexec_at < source.index("run_step ai-collect")
    assert source.index('ORIG_ARGS=("$@")') < source.index("while [ $# -gt 0 ]")
