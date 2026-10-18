"""Tests for the ``bench`` header line in ``scripts/nightly_gap.py`` (issue #186).

The gap report must answer, in its own body, *which tree the matrix measured* —
without the reader having to open ``base.json``.
"""
import json
import subprocess

import scripts.nightly_gap as ng


def test_bench_line_reads_base_json_with_after_sha(tmp_path):
    base = tmp_path / "base.json"
    base.write_text(json.dumps({
        "repos": [
            {"name": "AutoInfo", "branch": "main", "before": "aaa",
             "after": "bbb", "mode": "ff"},
            {"name": "e2e-test-suite", "branch": "main", "before": "ccc",
             "after": "ccc", "mode": "current"},
        ]
    }), encoding="utf-8")

    line = ng.bench_line(base)

    assert line.startswith("- bench：")
    assert "AutoInfo=main@bbb" in line          # `after` (被测的树) 优先于 before
    assert "e2e-test-suite=main@ccc" in line
    assert " · " in line


def test_bench_line_writes_unknown_for_missing_values(tmp_path):
    base = tmp_path / "base.json"
    base.write_text(json.dumps({"repos": [
        {"name": "AutoInfo", "branch": None, "before": None, "after": None,
         "mode": "WRONG_BRANCH"},
    ]}), encoding="utf-8")

    line = ng.bench_line(base)

    assert "AutoInfo=<unknown>@<unknown>" in line


def test_bench_line_falls_back_to_live_git(tmp_path, monkeypatch):
    repo = tmp_path / "somerepo"
    subprocess.run(["git", "init", "-b", "main", str(repo)],
                   check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "b@e.invalid"],
                   check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "bench-test"],
                   check=True, capture_output=True, text=True)
    (repo / "f.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "f.txt"],
                   check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "seed"],
                   check=True, capture_output=True, text=True)
    monkeypatch.setattr(ng, "DEFAULT_REPOS", [str(repo)])

    line = ng.bench_line(tmp_path / "missing.json")   # 账本缺失 → 现读 git

    assert "somerepo=main@" in line


def test_bench_line_unknown_when_no_repos(tmp_path, monkeypatch):
    monkeypatch.setattr(ng, "DEFAULT_REPOS", [])

    line = ng.bench_line(tmp_path / "missing.json")

    assert line == "- bench：<unknown>"


def test_bench_line_survives_malformed_base_json(tmp_path, monkeypatch):
    base = tmp_path / "base.json"
    base.write_text("{ not json", encoding="utf-8")
    monkeypatch.setattr(ng, "DEFAULT_REPOS", [])

    line = ng.bench_line(base)

    assert line == "- bench：<unknown>"
