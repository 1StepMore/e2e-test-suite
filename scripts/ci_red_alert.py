"""CI red alert — scheduled-workflow failures become deduped, throttled issues.

suite#274 + #275 (contract in #274 comments): a red nightly used to stay red
for days with nobody watching (validation.yml failed 10-29..11-08 unnoticed;
the 11-09 fidelity red had no issue at all). This script is the mechanism:

- A ``schedule``-triggered run that failed opens ONE issue titled
  ``[CI红] <workflow> @ <branch>`` (dedupe: existing open issue with the same
  title is reused, never duplicated).
- Throttle: the same run id is only ever recorded once; within a 24h window
  per workflow the failures are merged into a single bot comment (edited to
  append run ids).
- Auto-close (on a later green schedule/dispatch run of the same workflow)
  ONLY when evidence is complete: (a) a merged PR references the issue with a
  close keyword, AND (b) at least one green run after the issue was opened —
  the closing comment carries the green run id. Issues labelled ``pinned``,
  ``on-hold`` or ``owner:master`` are never auto-closed.
- Failure classification is recorded: environment gaps (401/invalid key,
  provider throttling, unconfigured fail-closed envs, network unreachable)
  do NOT open issues — they only land in the job summary — otherwise the
  free-tier quota and network noise would flood the tracker.

The gh-bound plumbing (subprocess to the ``gh`` CLI) is isolated in
``GhClient``; every decision function is pure and unit-tested in
``tests/ci/test_ci_red_alert.py``.

Usage:
    python scripts/ci_red_alert.py handle-run --run-id <id> --repo <owner/name>
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta

ALERT_MARKER = "<!-- ci-red-alert bot -->"
#: --dry-run: every decision runs, every tracker write is skipped (local
#: smoke tests must never create/comment/close real issues).
_DRY_RUN = False
ISSUE_TITLE_PREFIX = "[CI红]"
#: Issues with any of these labels are never auto-closed (suite#274 contract).
NEVER_AUTOCLOSE_LABELS = {"pinned", "on-hold", "owner:master"}
#: Workflows monitored via workflow_run (name -> cron, for the issue body).
MONITORED_WORKFLOW_CRONS = {
    "Validation Framework": "0 2 * * * (daily 02:00 UTC)",
    "fidelity": "0 2 * * 1 (weekly Mon 02:00 UTC)",
    "Omni Suite E2E Tests": "0 3 * * 1 (weekly Mon 03:00 UTC)",
}
#: Environment-gap signatures (case-insensitive) in failed-job logs. Any hit
#: means "environment red": no issue, summary only (suite#274 contract §5).
ENV_RED_SIGNATURES = (
    "invalid bearer token",
    "unauthorized",
    "invalid_api_key",
    "authenticationerror",
    "rate limit exceeded",
    "rate_limited",
    "该模型当前访问量过大",
    "circuit breaker",
    "unconfigured",
    "mcpnotconfigurederror",
    "mcp_allowed_directories (or",
    "requires_env",
    "sk-dummy",
    "connection refused",
    "name or service not known",
    "network is unreachable",
    "connection timed out",
    "certificate_verify_failed",
)
#: Matches "Closes #123", "fixes: #123", "Resolves #123" in a PR body.
CLOSE_KEYWORD_RE = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)\b", re.I)
#: Issue-body log excerpt per failed job (readability).
LOG_TAIL_LINES = 80
#: Classification scans deeper than the body excerpt — an environment-gap
#: signature buried mid-log (e.g. tracebacks before the scoring step) must
#: still classify the run as environment red (suite#285 lesson).
LOG_SCAN_LINES = 4000


# ---------------------------------------------------------------------------
# pure decision core (unit-tested)
# ---------------------------------------------------------------------------

def red_title(workflow_name: str, branch: str) -> str:
    """Dedup key made visible: same workflow+branch => same title => one issue."""
    return f"{ISSUE_TITLE_PREFIX} {workflow_name} @ {branch}"


def classify_failure(log_tail: str) -> tuple[str, list[str]]:
    """Classify a failed run from its log tail.

    Returns ("environment", signatures) when any environment-gap signature
    matches, else ("code", []) — the default is code-red so a signature-list
    omission can never silence a real regression.
    """
    haystack = log_tail.lower()
    hits = [sig for sig in ENV_RED_SIGNATURES if sig in haystack]
    # bare 401/403 status words need word boundaries (avoid matching 1401)
    if re.search(r"\b40[13]\b", log_tail):
        hits.append("http 401/403")
    if hits:
        return "environment", hits
    return "code", []


def pick_open_issue(open_issues: list[dict], workflow_name: str, branch: str) -> dict | None:
    """Find the single open red issue for this workflow+branch (dedupe)."""
    want = red_title(workflow_name, branch)
    for issue in open_issues:
        if issue.get("title") == want and "pull_request" not in issue:
            return issue
    return None


def throttle_decision(
    bot_comments: list[dict], run_id: int, now: datetime
) -> tuple[str, int | None, str]:
    """Decide how to record this failed run on an existing issue.

    Returns (action, comment_id, reason) where action is one of
    "skip" (run already recorded on ANY bot comment), "edit" (append run id
    to the recent bot comment), "comment" (24h window elapsed — new bot
    comment). The run-id scan covers every bot comment, newest first: a
    newer marker comment without the run id (e.g. a keep-open note) must not
    shadow the older comment that already records it.
    """
    window = timedelta(hours=24)
    newest_marker: dict | None = None
    for comment in bot_comments:  # newest first
        body = comment.get("body") or ""
        if ALERT_MARKER not in body:
            continue
        if newest_marker is None:
            newest_marker = comment
        if re.search(rf"\brun `{run_id}\b", body) or f"run `{run_id}`" in body:
            return "skip", comment["id"], "run already recorded (same-run throttle)"
    if newest_marker is not None:
        created = _parse_ts(newest_marker.get("created_at"))
        if created is not None and now - created < window:
            return "edit", newest_marker["id"], "within 24h — merge into the existing bot comment"
    return "comment", None, "no recent bot comment — posting one"


def append_run_id(body: str, run_id: int, run_url: str, failed: str) -> str:
    """Add a run line to an existing bot comment body (24h merge)."""
    return body.rstrip() + f"\n- run `{run_id}` — {failed} — {run_url}\n"


def _pr_closes_issue(pr_body: str | None, issue_num: int) -> bool:
    return any(int(n) == issue_num for n in CLOSE_KEYWORD_RE.findall(pr_body or ""))


def close_decision(
    issue: dict,
    labels: list[str],
    merged_prs: list[dict],
    green_run: dict,
) -> tuple[bool, str]:
    """Auto-close gate: labels + (a) merged referencing PR + (b) green run.

    ``green_run`` is the run that triggered this evaluation; (b) additionally
    requires it to postdate the issue (a green run from before the red one
    proves nothing).
    """
    present = {label.get("name", "") for label in issue.get("labels", [])} | set(labels)
    blocked = sorted(present & NEVER_AUTOCLOSE_LABELS)
    if blocked:
        return False, f"never auto-close: protected label(s) {blocked}"
    issue_num = issue["number"]
    created = _parse_ts(issue.get("created_at"))
    referencing = [
        pr
        for pr in merged_prs
        if pr.get("merged_at")
        and _pr_closes_issue(pr.get("body"), issue_num)
        and (created is None or _parse_ts(pr["merged_at"]) is None
             or _parse_ts(pr["merged_at"]) >= created)
    ]
    if not referencing:
        return False, "evidence incomplete: (a) no merged PR referencing this issue"
    green_at = _parse_ts(green_run.get("created_at"))
    if created is not None and green_at is not None and green_at < created:
        return False, "evidence incomplete: (b) green run predates the issue"
    return True, (
        f"fix PR #{referencing[0]['number']} merged + green run "
        f"`{green_run['id']}` after the issue — auto-closing"
    )


def build_issue_body(
    workflow_name: str,
    branch: str,
    run_id: int,
    run_url: str,
    head_sha: str,
    cron: str,
    failed_jobs: str,
    log_tail: str,
) -> str:
    return (
        f"## {ISSUE_TITLE_PREFIX} {workflow_name} @ {branch}\n\n"
        f"- run: `{run_id}` — {run_url}\n"
        f"- head sha: `{head_sha}`\n"
        f"- cron: `{cron}`\n"
        f"- failed jobs/steps: {failed_jobs}\n\n"
        f"### 日志尾部（failed jobs，各 {LOG_TAIL_LINES} 行）\n\n"
        f"```\n{log_tail.strip()}\n```\n\n"
        f"{ALERT_MARKER}\n"
        "由 nightly-alert 自动开启：同一 workflow 的后续失败以评论追加"
        "（24h 内合并为一条）；修复 PR 合并且其后该 workflow 至少一次"
        " schedule/手动跑为绿时自动关闭并附绿跑 run id；"
        "`pinned` / `on-hold` / `owner:master` 的 issue 永不自动关。\n"
    )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _summary(text: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(text)


class GhClient:
    """Thin gh CLI wrapper (subprocess; injectable double in tests)."""

    def __init__(self, repo: str) -> None:
        self.repo = repo

    def _gh(self, *args: str) -> str:
        proc = subprocess.run(
            ["gh", *args], capture_output=True, text=True, encoding="utf-8"
        )
        if proc.returncode != 0:
            raise RuntimeError(f"gh {' '.join(args[:3])}... failed: {proc.stderr[:400]}")
        return proc.stdout

    def run_info(self, run_id: int) -> dict:
        return json.loads(self._gh(
            "api", f"repos/{self.repo}/actions/runs/{run_id}"
        ))

    def failed_jobs(self, run_id: int) -> list[dict]:
        data = json.loads(self._gh(
            "api", f"repos/{self.repo}/actions/runs/{run_id}/jobs?per_page=100"
        ))
        return [j for j in data.get("jobs", []) if j.get("conclusion") == "failure"]

    def job_log_tail(self, job_id: int, lines: int = LOG_TAIL_LINES) -> str:
        return self._job_log(job_id, lines)

    def job_log_scan(self, job_id: int, lines: int = LOG_SCAN_LINES) -> str:
        return self._job_log(job_id, lines)

    def _job_log(self, job_id: int, lines: int) -> str:
        path = f"repos/{self.repo}/actions/jobs/{job_id}/logs"
        # Newer gh refuses to print log bodies carrying terminal escape
        # sequences unless --allow-escape-sequences is passed; older gh
        # doesn't know the flag. Try new-gh first, fall back to plain.
        for args in ([path, "--allow-escape-sequences"], [path]):
            try:
                log = self._gh("api", *args)
            except RuntimeError:
                continue
            return "\n".join(log.splitlines()[-lines:])
        return "(log unavailable)"

    def open_issues(self) -> list[dict]:
        return json.loads(self._gh(
            "api", f"repos/{self.repo}/issues?state=open&per_page=100",
        ))

    def issue_comments(self, issue_number: int) -> list[dict]:
        return json.loads(self._gh(
            "api", f"repos/{self.repo}/issues/{issue_number}/comments?per_page=100"
        ))

    def _write(self, *args: str, result: dict | None = None) -> dict:
        if _DRY_RUN:
            print(f"[dry-run] write skipped: gh {' '.join(args[:3])}...")
            return result or {}
        return json.loads(self._gh(*args))

    def create_issue(self, title: str, body: str, labels: list[str]) -> dict:
        label_args: list[str] = []
        for label in labels:
            label_args += ["-f", f"labels[]={label}"]
        return self._write(
            "api", f"repos/{self.repo}/issues",
            "-f", f"title={title}", "-f", f"body={body}",
            *label_args,
            result={"html_url": f"(dry-run) {title}"},
        )

    def comment(self, issue_number: int, body: str) -> dict:
        return self._write(
            "api", f"repos/{self.repo}/issues/{issue_number}/comments",
            "-f", f"body={body}",
        )

    def edit_comment(self, comment_id: int, body: str) -> None:
        self._write(
            "api", f"repos/{self.repo}/issues/comments/{comment_id}",
            "-f", f"body={body}",
        )

    def close_issue(self, issue_number: int, comment: str) -> None:
        self.comment(issue_number, comment)
        self._write("api", f"repos/{self.repo}/issues/{issue_number}",
                    "-X", "PATCH", "-f", "state=closed")

    def merged_prs(self) -> list[dict]:
        return json.loads(self._gh(
            "api",
            f"repos/{self.repo}/pulls?state=closed&per_page=100&sort=updated&direction=desc",
        ))


# ---------------------------------------------------------------------------
# gh-bound pipeline
# ---------------------------------------------------------------------------

def handle_run(gh: GhClient, run_id: int, replay: bool = False) -> int:
    info = gh.run_info(run_id)
    name = info.get("name") or "(unknown workflow)"
    branch = info.get("head_branch") or "(unknown branch)"
    conclusion = info.get("conclusion")
    event = info.get("event")
    run_url = info.get("html_url", f"https://github.com/{gh.repo}/actions/runs/{run_id}")

    if conclusion == "success":
        return _handle_green(gh, info, name, branch, run_id, run_url)

    if conclusion != "failure":
        _summary(f"nightly-alert: run `{run_id}` conclusion={conclusion} — nothing to do")
        return 0

    if event != "schedule" and not replay:
        _summary(
            f"nightly-alert: run `{run_id}` is `{event}`-triggered, not `schedule` — "
            "only schedule-triggered failures alert (suite#274); manual failures "
            "are triaged by humans."
        )
        return 0
    replay_note = (
        f"- replay: dispatched via nightly-alert (run event was `{event}`; "
        "controlled-failure testing per suite#274 DoD)\n" if replay else ""
    )

    jobs = gh.failed_jobs(run_id)
    failed_desc = "; ".join(
        f"{j.get('name')}"
        + ("(" + ", ".join(
            s.get("name") for s in j.get("steps", [])
            if s.get("conclusion") == "failure"
        ) + ")" if any(s.get("conclusion") == "failure" for s in j.get("steps", [])) else "")
        for j in jobs
    ) or "(no failed job details)"
    tails = "\n\n---\n\n".join(
        f"[job] {j.get('name')}\n{gh.job_log_tail(j['id'])}" for j in jobs
    ) or "(no logs)"

    # Classification sees more than the body excerpt: mid-log signatures count.
    scan = "\n\n---\n\n".join(
        f"[job] {j.get('name')}\n{gh.job_log_scan(j['id'])}" for j in jobs
    )
    kind, signatures = classify_failure(scan)
    if kind == "environment":
        _summary(
            f"nightly-alert: run `{run_id}` ({name} @ {branch}) classified "
            f"**environment red** — signatures: {signatures}. No issue opened "
            "(policy: suite#274/#275 §5 — environment gaps must not flood the "
            "tracker). Triage: provider keys/quota/network."
        )
        return 0

    title = red_title(name, branch)
    open_issues = gh.open_issues()
    existing = pick_open_issue(open_issues, name, branch)
    if existing is None:
        body = build_issue_body(
            name, branch, run_id, run_url, info.get("head_sha", ""),
            MONITORED_WORKFLOW_CRONS.get(name, "(cron unknown)"),
            failed_desc, tails,
        )
        if replay_note:
            body = body.replace(f"{ALERT_MARKER}\n", f"{ALERT_MARKER}\n{replay_note}\n")
        issue = gh.create_issue(title, body, [])
        _summary(f"nightly-alert: opened {issue['html_url']} for run `{run_id}` (code-red)")
        return 0

    num = existing["number"]
    # Same-run idempotence covers the issue BODY too: the open path records
    # the run id there (as `run: \`<id>\``), and only-comment checking would
    # double-record the first replayed failure (suite#287 rehearsal catch).
    issue_body = existing.get("body") or ""
    if f"run `{run_id}`" in issue_body or f"run: `{run_id}`" in issue_body:
        _summary(f"nightly-alert: run `{run_id}` already recorded on #{num} (issue body) — skip")
        return 0
    comments = sorted(
        gh.issue_comments(num),
        key=lambda c: c.get("created_at") or "",
        reverse=True,
    )
    action, comment_id, reason = throttle_decision(comments, run_id, _now_utc())
    one_liner = f"{failed_desc[:120]}"
    if action == "skip":
        _summary(f"nightly-alert: run `{run_id}` already recorded on #{num} — {reason}")
    elif action == "edit":
        body = next(c for c in comments if c["id"] == comment_id)["body"]
        gh.edit_comment(comment_id, append_run_id(body, run_id, run_url, one_liner))
        _summary(f"nightly-alert: merged run `{run_id}` into #{num} comment — {reason}")
    else:
        gh.comment(
            num,
            f"{ALERT_MARKER}\n- run `{run_id}` — {one_liner} — {run_url}\n",
        )
        _summary(f"nightly-alert: appended run `{run_id}` to #{num} — {reason}")
    return 0


def _handle_green(
    gh: GhClient, info: dict, name: str, branch: str, run_id: int, run_url: str
) -> int:
    if name not in MONITORED_WORKFLOW_CRONS:
        return 0
    open_issues = gh.open_issues()
    existing = pick_open_issue(open_issues, name, branch)
    if existing is None:
        _summary(f"nightly-alert: green run `{run_id}`, no open red issue for {name} @ {branch}")
        return 0
    num = existing["number"]
    labels = [lab.get("name", "") for lab in existing.get("labels", [])]
    merged = [pr for pr in gh.merged_prs() if pr.get("merged_at")]
    close, reason = close_decision(existing, labels, merged, info)
    if close:
        gh.close_issue(num, f"自动关闭：{reason}\n绿跑: {run_url}\n")
        _summary(f"nightly-alert: closed #{num} — {reason}")
    else:
        # No ALERT_MARKER here: green-run notes are not failure records and
        # must not participate in the failure-throttle window.
        gh.comment(num, f"绿跑 `{run_id}` 在案，但未满足自动关条件：{reason}。保持开启。\n")
        _summary(f"nightly-alert: kept #{num} open — {reason}")
    return 0


def main(argv: list[str]) -> int:
    global _DRY_RUN
    if not argv or argv[0] != "handle-run":
        print(__doc__)
        return 2
    if "--dry-run" in argv:
        _DRY_RUN = True
        argv = [a for a in argv if a != "--dry-run"]
    positional: list[str] = []
    repo = os.environ.get("GITHUB_REPOSITORY")
    replay = False
    rest = argv[1:]
    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg == "--repo" and i + 1 < len(rest):
            repo = rest[i + 1]
            i += 2
        elif arg == "--run-id" and i + 1 < len(rest):
            positional.insert(0, rest[i + 1])
            i += 2
        elif arg == "--replay":
            replay = True
            i += 1
        else:
            positional.append(arg)
            i += 1
    if not positional or not repo:
        print("FAIL: run id and --repo (or GITHUB_REPOSITORY) required", file=sys.stderr)
        return 2
    return handle_run(GhClient(repo), int(positional[0]), replay=replay)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
