"""Regenerate the Alice ch1 candidate via real LLM (Zhipu, para-by-para).

Used by `make fidelity-nightly`. Requires ZHIPU_API_KEY in .env.
Output: test_artifacts/ol/alice_ch1_zhipu_real.md

suite#279 hardening:
- Paces calls (default 1.1s apart) so OL's local token-bucket limiter
  (ol_mcp/rate_limiter.py, default 60 RPM / burst 10) never rejects a blast
  of paragraph calls — the 2026-11-09 nightly lost paragraphs 11-30 to it.
- Retries throttle-like failures with bounded exponential backoff (same
  policy shape as omni_mcp/validation/engine.py since suite#278). OL surfaces
  both provider 429s AND an open per-role circuit breaker as the generic
  OL_TRANSLATE_FAILED code, so the retry trigger is the message text too —
  an open breaker (ol_pool/router.py: fail_max=5, reset_timeout=60) needs a
  wait longer than the 60s reset window to recover.
- OL_MCP_NOT_CONFIGURED is deterministic (fail-closed missing
  MCP_ALLOWED_DIRECTORIES): abort immediately instead of burning the
  remaining paragraphs.
- A wall-clock budget (FIDELITY_REGEN_BUDGET_SECONDS) bounds the retry
  ladder so backoff can never blow the job timeout; paragraphs past the
  budget are recorded as skipped_budget.
- Writes a regen meta sidecar (translated/total + candidate sha256) next to
  the fidelity result so run_fidelity.py can distinguish "genuinely below
  threshold" from "undersampled by the environment".
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE = REPO_ROOT / "test_corpus" / "real" / "cc0_02_gutenberg_alice_ch1.txt"
OUTPUT = REPO_ROOT / "test_artifacts" / "ol" / "alice_ch1_zhipu_real.md"
META = REPO_ROOT / "tests" / "fidelity" / "results" / "alice_ch1_regen_meta.json"

# Throttle policy (env-overridable for CI and hermetic tests, mirroring the
# OMNI_VALIDATION_THROTTLE_* names used by the validation engine).
THROTTLE_RETRIES = int(os.environ.get("FIDELITY_THROTTLE_RETRIES", "4"))
THROTTLE_BACKOFF = float(os.environ.get("FIDELITY_THROTTLE_BACKOFF_SECONDS", "30"))
THROTTLE_BACKOFF_MAX = float(os.environ.get("FIDELITY_THROTTLE_BACKOFF_MAX_SECONDS", "90"))
# Breaker reset window is 60s (ol_pool/router.py) — never wait less than that
# or the retry lands on the still-open breaker and fails fast.
BREAKER_RESET_SECONDS = float(os.environ.get("FIDELITY_BREAKER_RESET_SECONDS", "65"))
# Wall-clock budget for the whole regen (default 40 min inside the 60-min job).
BUDGET_SECONDS = float(os.environ.get("FIDELITY_REGEN_BUDGET_SECONDS", "2400"))
# Abort after this many consecutive paragraphs exhausted all throttle retries
# with the breaker open — the provider is saturated; grinding on would only
# hit the job timeout (dispatch 42696707838 ran the ladder to 60+ minutes).
ABORT_BREAKER_STREAK = int(os.environ.get("FIDELITY_ABORT_BREAKER_STREAK", "3"))
# Inter-paragraph pacing; the local limiter refills 1 token/s at 60 RPM, so a
# little over 1s between calls keeps the bucket from emptying.
PACE_SECONDS = float(os.environ.get("FIDELITY_PARA_PACE_SECONDS", "1.1"))


def _err_code(rd: dict) -> str:
    err = rd.get("error")
    if isinstance(err, dict):
        return str(err.get("code") or rd.get("error_code") or "?")
    return str(rd.get("error_code") or "?")


def _err_message(rd: dict) -> str:
    err = rd.get("error")
    if isinstance(err, dict):
        return str(err.get("message") or "")
    if isinstance(err, str):
        return err
    return str(rd.get("message") or "")


def _is_breaker_open(rd: dict) -> bool:
    msg = _err_message(rd).lower()
    return "circuit breaker" in msg and "is open" in msg


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass

    if not os.environ.get("ZHIPU_API_KEY"):
        print("FAIL: ZHIPU_API_KEY not set in .env", file=sys.stderr)
        return 1

    zhipu_key = os.environ["ZHIPU_API_KEY"]
    if zhipu_key.startswith("sk-dummy") or zhipu_key.startswith("nvapi-dummy"):
        print(
            "SKIP: ZHIPU_API_KEY is a dummy placeholder (sk-dummy / nvapi-dummy). "
            "Real Zhipu regeneration requires a valid production key. "
            "fidelity-gate still validates the existing test artifact.",
            file=sys.stderr,
        )
        return 0

    sys.path.insert(0, str(REPO_ROOT / "Omni_Localizer" / "src"))
    from ol_mcp.tools import TranslateInput, translate_md_text

    if not SOURCE.exists():
        print(f"FAIL: source not found: {SOURCE}", file=sys.stderr)
        return 1

    raw = SOURCE.read_text(encoding="utf-8")
    parts = raw.split("---", 2)
    body = parts[2].strip() if len(parts) >= 3 and parts[0].strip() == "" else raw
    body = re.sub(r"^#+\s.*$", "", body, flags=re.MULTILINE)
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip() and p.strip() != "Down the Rabbit-Hole"]

    print(f"Translating {len(paragraphs)} paragraphs via Zhipu...")

    stats = {
        "total_paragraphs": len(paragraphs),
        "translated": 0,
        "failed_rate_limited": 0,
        "failed_not_configured": 0,
        "failed_other": 0,
        "skipped_budget": 0,
        "skipped_breaker_abort": 0,
        "throttle_retries_used": 0,
    }
    deadline = time.monotonic() + BUDGET_SECONDS

    async def translate_one(i: int, p: str) -> tuple[str | None, str]:
        """Translate one paragraph. Returns (translated_or_None, outcome_code)."""
        for attempt in range(THROTTLE_RETRIES + 1):  # 1 try + N retries
            r = await translate_md_text(TranslateInput(
                content=p, source_lang="en", target_lang="zh", add_frontmatter=False,
            ))
            rd = json.loads(r) if isinstance(r, str) else r
            if rd.get("success"):
                return rd.get("translated", p), "ok"
            code = _err_code(rd)
            err = rd.get("error", "?")
            if not isinstance(err, str):
                err = json.dumps(err, ensure_ascii=False)
            if code == "OL_MCP_NOT_CONFIGURED":
                # Deterministic config error (fail-closed): every remaining
                # call would fail identically — abort without burning them.
                print(
                    "FAIL: OL MCP is not configured — MCP_ALLOWED_DIRECTORIES is "
                    "missing (fail-CLOSED security policy). Set it in the workflow "
                    "env, e.g. the workspace plus /tmp. See suite#279.",
                    file=sys.stderr,
                )
                return None, "not_configured"
            breaker_open = _is_breaker_open(rd)
            throttled = "RATE_LIMIT" in code or breaker_open
            wait = min(THROTTLE_BACKOFF_MAX, THROTTLE_BACKOFF * (2 ** attempt))
            if breaker_open:
                wait = max(wait, BREAKER_RESET_SECONDS)
            if throttled and attempt < THROTTLE_RETRIES:
                if time.monotonic() + wait > deadline:
                    print(f"  [{i+1}] throttle retry would exceed the regen budget "
                          f"({BUDGET_SECONDS:.0f}s) — giving up on this paragraph",
                          file=sys.stderr)
                    return None, "breaker" if breaker_open else "rate_limited"
                stats["throttle_retries_used"] += 1
                print(f"  [{i+1}] {'breaker open' if breaker_open else 'rate-limited'}, "
                      f"retrying in {wait:.0f}s "
                      f"(attempt {attempt + 1}/{THROTTLE_RETRIES + 1})", file=sys.stderr)
                await asyncio.sleep(wait)
                continue
            print(f"  [{i+1}] failed: {err[:60]}", file=sys.stderr)
            if breaker_open:
                return None, "breaker"
            return None, "rate_limited" if throttled else code
        return None, "rate_limited"

    async def translate_all() -> list[str]:
        results: list[str] = []
        breaker_streak = 0
        for i, p in enumerate(paragraphs):
            if i > 0 and PACE_SECONDS > 0:
                await asyncio.sleep(PACE_SECONDS)
            if time.monotonic() > deadline:
                stats["skipped_budget"] += 1
                results.append(p)
                continue
            translated, outcome = await translate_one(i, p)
            if translated is not None:
                results.append(translated)
                stats["translated"] += 1
                breaker_streak = 0
                if (i + 1) % 5 == 0:
                    print(f"  [{i+1}/{len(paragraphs)}] done")
            elif outcome == "not_configured":
                stats["failed_not_configured"] += 1
                break  # deterministic — remaining paragraphs cannot succeed
            elif outcome in ("rate_limited", "breaker"):
                stats["failed_rate_limited"] += 1
                results.append(p)
                if outcome == "breaker":
                    breaker_streak += 1
                    if breaker_streak >= ABORT_BREAKER_STREAK:
                        remaining = len(paragraphs) - (i + 1)
                        stats["skipped_breaker_abort"] = remaining
                        results.extend(paragraphs[i + 1:])
                        print(
                            f"  ABORT: {breaker_streak} consecutive paragraphs exhausted "
                            f"all throttle retries with the translation breaker open — "
                            f"provider saturated (environment gap, not a quality "
                            f"verdict). Skipping the remaining {remaining} paragraphs; "
                            f"the score step will report unconfigured.",
                            file=sys.stderr,
                        )
                        break
                else:
                    breaker_streak = 0
            else:
                stats["failed_other"] += 1
                results.append(p)
        return results

    started = time.monotonic()
    translated = asyncio.run(translate_all())
    header = "# 爱丽丝梦游仙境 — 第一章\n\n## 兔子洞之旅\n\nDown the Rabbit-Hole\n\n"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(header + "\n\n".join(translated) + "\n", encoding="utf-8")
    chinese = sum(1 for c in OUTPUT.read_text() if "\u4e00" <= c <= "\u9fff")
    print(f"Wrote {OUTPUT} ({chinese} Chinese chars)")

    meta = {
        **stats,
        "pace_seconds": PACE_SECONDS,
        "budget_seconds": BUDGET_SECONDS,
        "throttle_retries": THROTTLE_RETRIES,
        "throttle_backoff_seconds": THROTTLE_BACKOFF,
        "chinese_chars": chinese,
        # Binds the meta to this exact candidate: run_fidelity.py ignores a
        # meta whose sha does not match the candidate being scored.
        "candidate_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "elapsed_seconds": round(time.monotonic() - started, 1),
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    META.parent.mkdir(parents=True, exist_ok=True)
    META.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Regen meta: {META} (translated {stats['translated']}/{stats['total_paragraphs']})")

    return 0 if stats["translated"] == stats["total_paragraphs"] else 1


if __name__ == "__main__":
    sys.exit(main())
