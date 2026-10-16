"""Tests for scripts/nightly_sync.py branch guard (issue #170).

Regression: when the work tree sat on a non-main feature branch whose history
made ``origin/main`` an ancestor, ``git merge --ff-only origin/main`` returned 0
with "Already up to date." and the script reported ``mode="current"`` — the
ledger claimed the gap matrix was measured on main when it was not.

These tests build REAL git repos under ``tmp_path`` with a LOCAL bare origin
(a directory path), so they need no network and no reachable real remote.
"""
import subprocess

import scripts.nightly_sync as ns


def _git(repo: str, *args: str) -> None:
    subprocess.run(
        ["git", "-C", repo, *args],
        check=True,
        capture_output=True,
        text=True,
    )


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
