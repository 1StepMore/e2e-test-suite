#!/usr/bin/env python3
"""Build a human-review delivery zip from a persisted validation run.

Usage:
    python scripts/validation/make_delivery_package.py [validation-runs/<ts>] [--out-dir 04-Output/artifacts/deliverables/omni-suite] [--tag <label>]

With no positional run dir, the newest run is read from
``validation-runs/latest.txt``.  The zip
``omni-suite-validation-<run_id>[-<tag>].zip`` lands in the out-dir and
contains:

- ``manifest.json`` — run identity, per-status counts, and the artifact
  registry (one entry per step that declared ``collect_artifacts``).
- ``01-RAW/`` — copies of the REAL artifact files (the produced
  .md/.xlf/.html/.json… from ``collect_artifacts``) that exist.  A
  basename collision across scenarios gets a ``scenario-name_`` prefix.
- ``02-PROCESSED/`` — ``validation-report.md`` + ``report.json`` (the
  director report), ``run_meta.json`` (the run_meta alone), and
  ``verdict-summary.md`` (scenario -> status table).
- ``03-MISSING/`` — one note file per declared artifact that is genuinely
  missing (never fails the delivery).

Relative artifact paths resolve against the suite root.  Only the out-dir
is ever written.  Exit 0 on success, 1 on a missing or empty run.
"""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

SUITE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = str(SUITE_ROOT / "04-Output" / "artifacts" / "deliverables" / "omni-suite")

_REPORT_PATH = SUITE_ROOT / "scripts" / "validation" / "validation_report.py"


def _load_report_module() -> Any:
    """Import scripts/validation/validation_report.py from its file path
    (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location("validation_report", _REPORT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["validation_report"] = mod
    spec.loader.exec_module(mod)
    return mod


def _resolve_run_dir(run_arg: str | None) -> Path:
    """The run dir to package: the positional arg, else the newest run
    from ``validation-runs/latest.txt``.  Raises ValueError when neither
    resolves."""
    if run_arg:
        return Path(run_arg)
    latest = SUITE_ROOT / "validation-runs" / "latest.txt"
    if latest.is_file():
        name = latest.read_text(encoding="utf-8").strip()
        if name:
            return SUITE_ROOT / "validation-runs" / name
    raise ValueError("no run dir given and no validation-runs/latest.txt pointer")


def _load_payload(run_dir: Path) -> dict[str, Any]:
    """The run's scenarios.json; raises ValueError when missing,
    unparseable, or holding zero scenarios (an empty run cannot be
    delivered)."""
    src = run_dir / "scenarios.json"
    if not src.is_file():
        raise ValueError(f"scenarios.json not found: {src}")
    try:
        payload = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"unparseable scenarios.json at {src}: {exc}") from exc
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError(f"run {run_dir.name} is empty (no scenarios)")
    return payload


def _sanitize(name: str) -> str:
    """A zip-safe filename fragment from a scenario name or tag."""
    return re.sub(r"[^\w.-]+", "_", name).strip("_") or "entry"


def _collect_artifacts(
    payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """``(existing, missing)`` artifact entries: one per step that
    declared ``collect_artifacts`` (its persisted ``artifact_to_show``),
    relative paths resolved against the suite root, ``exists`` recorded
    after resolving."""
    existing: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for sc in payload.get("scenarios", []):
        name = sc.get("name", "?")
        for st in sc.get("steps", []):
            declared = st.get("artifact_to_show")
            if not declared:
                continue
            p = Path(declared)
            if not p.is_absolute():
                p = SUITE_ROOT / p
            entry: dict[str, Any] = {
                "scenario": name,
                "step_index": st.get("step_index"),
                "artifact_path": str(p),
                "exists": p.is_file(),
            }
            (existing if entry["exists"] else missing).append(entry)
    return existing, missing


def _copy_raw(entries: list[dict[str, Any]], raw_dir: Path) -> None:
    """Copy each existing artifact into 01-RAW/, preserving basenames and
    prefixing ``scenario-name_`` on collision (then ``scenario_step_``)."""
    used: set[str] = set()
    for entry in entries:
        src = Path(entry["artifact_path"])
        base = src.name
        if base in used:
            base = f"{_sanitize(entry['scenario'])}_{src.name}"
        if base in used:
            base = f"{_sanitize(entry['scenario'])}_{entry['step_index']}_{src.name}"
        used.add(base)
        shutil.copy2(src, raw_dir / base)
        entry["raw_path"] = f"01-RAW/{base}"


def _verdict_summary_md(payload: dict[str, Any]) -> str:
    """A short scenario -> status table for 02-PROCESSED/."""
    lines = ["# Validation run — verdict summary", ""]
    lines.append(f"> Run `{payload.get('run_id')}` | trace_id `{payload.get('trace_id')}`")
    lines.append("")
    lines.append("| Scenario | Status |")
    lines.append("|----------|--------|")
    for sc in payload.get("scenarios", []):
        lines.append(f"| `{sc.get('name')}` | {sc.get('status')} |")
    lines.append("")
    return "\n".join(lines)


def build_delivery(
    run_dir: str | Path,
    out_dir: str | Path = DEFAULT_OUT_DIR,
    tag: str | None = None,
    scenarios_dir: str | Path = "scenarios",
) -> Path:
    """Build the delivery zip for a persisted run; returns the zip path.

    Raises ValueError on a missing/empty run.  Only *out_dir* is written
    (the zip); the staging tree lives in the system temp dir.
    """
    run_dir = Path(run_dir)
    payload = _load_payload(run_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    existing, missing = _collect_artifacts(payload)
    counts: dict[str, int] = {}
    for sc in payload.get("scenarios", []):
        status = sc.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1

    staging = Path(tempfile.mkdtemp(prefix="omni-delivery-"))
    try:
        raw_dir = staging / "01-RAW"
        raw_dir.mkdir()
        _copy_raw(existing, raw_dir)

        processed = staging / "02-PROCESSED"
        processed.mkdir()
        report = _load_report_module()
        try:
            md_text, report_data = report.generate(run_dir / "scenarios.json", scenarios_dir)
            (processed / "validation-report.md").write_text(md_text, encoding="utf-8")
            (processed / "report.json").write_text(
                json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except SystemExit as exc:
            note = f"report generation failed: {exc}"
            (processed / "validation-report.md").write_text(f"# Report\n\n{note}\n", encoding="utf-8")
            (processed / "report.json").write_text(json.dumps({"error": note}), encoding="utf-8")
        (processed / "run_meta.json").write_text(
            json.dumps(payload.get("run_meta") or {}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (processed / "verdict-summary.md").write_text(_verdict_summary_md(payload), encoding="utf-8")

        if missing:
            missing_dir = staging / "03-MISSING"
            missing_dir.mkdir()
            for entry in missing:
                note = missing_dir / (
                    f"missing-{_sanitize(entry['scenario'])}-step{entry['step_index']}.txt"
                )
                note.write_text(
                    f"declared collect_artifacts path not found:\n{entry['artifact_path']}\n",
                    encoding="utf-8",
                )

        manifest = {
            "run_id": payload.get("run_id"),
            "timestamp": payload.get("timestamp"),
            "trace_id": payload.get("trace_id"),
            "tag": tag,
            "run_meta": payload.get("run_meta") or {},
            "counts": counts,
            "artifacts": existing,
            "missing_artifacts": missing,
            "generated_by": "omni-suite make_delivery_package.py",
            "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        run_id = payload.get("run_id") or run_dir.name
        zip_base = f"omni-suite-validation-{_sanitize(run_id)}"
        if tag:
            zip_base += f"-{_sanitize(tag)}"
        zip_path = out_dir / f"{zip_base}.zip"
        shutil.make_archive(str(zip_path.with_suffix("")), "zip", root_dir=str(staging))
        return zip_path
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a human-review delivery zip from a persisted validation run"
    )
    parser.add_argument(
        "run_dir",
        nargs="?",
        default=None,
        help="validation-runs/<ts> (default: newest run from validation-runs/latest.txt)",
    )
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUT_DIR,
        help="delivery zip destination directory",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="optional label appended to the zip name (omni-suite-validation-<run_id>-<tag>.zip)",
    )
    parser.add_argument(
        "--scenarios-dir",
        default="scenarios",
        help="scenario library dir used for report regression metadata",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0
    try:
        run_dir = _resolve_run_dir(args.run_dir)
        zip_path = build_delivery(
            run_dir, out_dir=args.out_dir, tag=args.tag, scenarios_dir=args.scenarios_dir
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"DELIVERY: {zip_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
