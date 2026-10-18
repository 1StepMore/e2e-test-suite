"""Tests for scripts/nightly_sync.py branch guard (issue #170).

Regression: when the work tree sat on a non-main feature branch whose history
made ``origin/main`` an ancestor, ``git merge --ff-only origin/main`` returned 0
with "Already up to date." and the script reported ``mode="current"`` — the
ledger claimed the gap matrix was measured on main when it was not.

These tests build REAL git repos under ``tmp_path`` with a LOCAL bare origin
(a directory path), so they need no network and no reachable real remote.
"""
import subprocess
from pathlib import Path

import scripts.nightly_sync as ns


def _git(repo: str, *args: str) -> None:
    subprocess.run(
        ["git", "-C", repo, *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _rev(repo: str) -> str:
    return subprocess.run(
        ["git", "-C", repo, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _advance_origin_main(tmp_path, origin: Path) -> None:
    """Push one new commit to ``origin/main`` through a throwaway clone."""
    bump = tmp_path / "bump"
    subprocess.run(
        ["git", "clone", str(origin), str(bump)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(str(bump), "config", "user.email", "nightly@example.invalid")
    _git(str(bump), "config", "user.name", "nightly-sync-test")
    (bump / "new.txt").write_text("new\n", encoding="utf-8")
    _git(str(bump), "add", "new.txt")
    _git(str(bump), "commit", "-m", "advance main")
    _git(str(bump), "push", "origin", "main")


def _make_repo(tmp_path) -> str:
    """Build a local origin (bare) + a clone on ``main`` with one commit.

    Returns the clone's path. All remotes are local filesystem paths.
    """
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(origin)],
        check=True,
        capture_output=True,
        text=True,
    )

    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(str(repo), "config", "user.email", "nightly@example.invalid")
    _git(str(repo), "config", "user.name", "nightly-sync-test")

    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(str(repo), "add", "seed.txt")
    _git(str(repo), "commit", "-m", "seed")
    _git(str(repo), "remote", "add", "origin", str(origin))
    _git(str(repo), "push", "-u", "origin", "main")
    return str(repo)


def test_on_main_reports_current(tmp_path):
    """On main with origin/main == HEAD: fetch+ff-only merge is a no-op."""
    repo = _make_repo(tmp_path)

    record = ns.sync_repo(repo, timeout=60)

    assert record["mode"] == "current"
    assert record["branch"] == "main"
    assert record["before"] == record["after"]


def test_feature_branch_reports_wrong_branch_and_is_stale(tmp_path):
    """On a feature branch (origin/main is its ancestor) the old code said
    "current"; it must now be WRONG_BRANCH and show up in ``stale``."""
    repo = _make_repo(tmp_path)
    _git(repo, "checkout", "-b", "feature/x")

    record = ns.sync_repo(repo, timeout=60)

    assert record["mode"] == "WRONG_BRANCH"
    assert record["branch"] == "feature/x"

    report = ns.build_report([repo], timeout=60)
    assert any(r["name"] == "repo" and r["mode"] == "WRONG_BRANCH"
               for r in report["repos"])
    assert "repo" in report["stale"]
    # 默认（未开 --switch-branch）行为逐字段不变：from_branch 保持 None。
    assert record["from_branch"] is None


def test_switch_branch_clean_feature_switches_to_main(tmp_path):
    """--switch-branch + clean tree on a feature branch: checkout main, then
    fetch/merge; mode=SWITCHED, from_branch recorded, after advanced."""
    repo = _make_repo(tmp_path)
    _git(repo, "checkout", "-b", "feature/x")
    before = _rev(repo)
    _advance_origin_main(tmp_path, tmp_path / "origin.git")

    record = ns.sync_repo(repo, timeout=60, switch_branch=True)

    assert record["mode"] == "SWITCHED"
    assert record["branch"] == "main"
    assert record["from_branch"] == "feature/x"
    assert record["after"] != before
    assert record["after"] is not None

    report = ns.build_report([repo], timeout=60, switch_branch=True)
    assert "repo" not in report["stale"]


def test_switch_branch_dirty_is_skipped(tmp_path):
    """--switch-branch + dirty tree: never switch, mode=DIRTY_SKIPPED, stale."""
    repo = _make_repo(tmp_path)
    _git(repo, "checkout", "-b", "feature/x")
    before = _rev(repo)
    _advance_origin_main(tmp_path, tmp_path / "origin.git")
    (Path(repo) / "seed.txt").write_text("dirty\n", encoding="utf-8")

    record = ns.sync_repo(repo, timeout=60, switch_branch=True)

    assert record["mode"] == "DIRTY_SKIPPED"
    assert record["branch"] == "feature/x"
    assert record["after"] == record["before"] == before

    report = ns.build_report([repo], timeout=60, switch_branch=True)
    assert "repo" in report["stale"]


def test_switch_branch_detached_head_stays_wrong_branch(tmp_path):
    """A detached HEAD has no branch to attribute → still WRONG_BRANCH, no switch."""
    repo = _make_repo(tmp_path)
    _git(repo, "checkout", "--detach", "HEAD")

    record = ns.sync_repo(repo, timeout=60, switch_branch=True)

    assert record["mode"] == "WRONG_BRANCH"
    assert record["from_branch"] is None
