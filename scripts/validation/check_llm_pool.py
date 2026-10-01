#!/usr/bin/env python3
"""Fail fast when the LLM pool has been pruned below its fallback floor.

`Omni_Localizer/config/default.yaml` lists, per role, a priority-1 model on one
provider and a priority-2 model on another. `ol_pool.router.partition_usable_models`
silently drops every model whose provider key is absent from the environment, so
losing one key does not fail loudly — it leaves the role with a single model and
no fallback. A provider-side rate limit then becomes a hard failure, and the
downstream assertions report something unrelated: a source document that was
never translated trips the CJK-density check, because the source was Chinese to
begin with (e2e#125).

This runs OL's own partition function — not a reimplementation — so the floor can
never drift from what the router actually does, and it runs *before* the nightly
scenarios instead of after them.

Exit codes match `scripts/nightly_gap.py`:
  0  every role has at least --min-per-role usable models
  1  some role is below the floor, or lost every model
  2  the pool could not be evaluated (bad config, OL not importable, bad usage)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SUITE_ROOT = Path(__file__).resolve().parents[2]
ROLES = ("translation", "judging", "restoration", "profiling")


def _load_pool(config_path: Path):
    sys.path.insert(0, str(SUITE_ROOT / "Omni_Localizer" / "src"))
    from ol_config.loader import load_config
    from ol_pool.router import partition_usable_models

    config, _glossary = load_config(str(config_path))
    return partition_usable_models(config.llm_pool)


def _key_provenance(before: set[str]) -> dict[str, str]:
    """Classify each provider key as pre-existing or supplied by OL's `.env` autoload.

    `load_config` calls `_load_env_file()`, which `setdefault`s every key in
    `Omni_Localizer/.env` into `os.environ`. On a dev box that file supplies
    keys the process never had, so a partition computed here can look healthy
    for reasons CI will not reproduce. Recording the origin keeps a local pass
    from being read as CI truth.
    """
    added = set(os.environ) - before
    provenance = {}
    for key, origin in (("AMD_API_KEY", "process env"), ("ZHIPU_API_KEY", "process env")):
        if key in before:
            provenance[key] = origin
        elif key in added:
            provenance[key] = "Omni_Localizer/.env (autoloaded)"
        else:
            provenance[key] = "absent"
    return provenance


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="check_llm_pool.py", description=__doc__)
    ap.add_argument(
        "--config",
        type=Path,
        default=None,
        help="OL pool config. Defaults to $OL_CONFIG_PATH, then the canonical "
             "Omni_Localizer/config/default.yaml.",
    )
    ap.add_argument(
        "--min-per-role",
        type=int,
        default=2,
        help="Usable models each role must retain. 2 means a genuine rate-limit "
             "fallback survives losing the other provider's key (default: 2).",
    )
    args = ap.parse_args(argv)
    if args.min_per_role < 1:
        print("--min-per-role must be >= 1", file=sys.stderr)
        return 2

    config_path = args.config or Path(
        os.environ.get("OL_CONFIG_PATH") or SUITE_ROOT / "Omni_Localizer" / "config" / "default.yaml"
    )
    if not config_path.is_file():
        print(f"LLM pool config not found: {config_path}", file=sys.stderr)
        return 2

    before = set(os.environ)
    try:
        usable, skipped = _load_pool(config_path)
    except Exception as exc:  # noqa: BLE001 - report any failure as an env problem
        print(f"could not evaluate the LLM pool from {config_path}: {exc}", file=sys.stderr)
        return 2
    provenance = _key_provenance(before)

    counts = {role: len(usable.get(role, [])) for role in ROLES}
    starved = sorted(role for role, n in counts.items() if n < args.min_per_role)
    payload = {
        "schema": "llm-pool-preflight/1",
        "config": str(config_path),
        "min_per_role": args.min_per_role,
        "usable_per_role": counts,
        "skipped": [
            {"role": role, "provider": model.provider, "model": model.model, "missing_env": missing}
            for role, model, missing in skipped
        ],
        "key_provenance": provenance,
        "verdict": "pass" if not starved else "fail",
    }

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if starved:
        missing_keys = sorted({name for _role, _model, names in skipped for name in names})
        print(
            f"\nFAIL: role(s) {starved} retain fewer than {args.min_per_role} usable "
            f"model(s) — provider rate limits have no fallback.\n"
            f"      Per-role usable: {counts}\n"
            f"      Missing keys: {missing_keys or 'none reported'}",
            file=sys.stderr,
        )
        print(
            "      This is the e2e#125 failure mode: the pipeline scenarios would "
            "fail on a downstream assertion (e.g. CJK density) about a translation "
            "that never happened.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
