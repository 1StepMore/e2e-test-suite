#!/usr/bin/env python3
"""The artifact-assertion matrix (issue e2e-test-suite#44).

NEW artifact-assertion matrix wired into the validation CLI (issue #44
acceptance: P0/P1 assertion failures drive a NONZERO exit).  This module
consumes the sibling ``artifact_assertions.py`` module (its
``run_assertions(artifacts_dir, module) -> list[AssertionResult]`` — each
result carrying ``name`` / ``passed`` / ``issue`` / ``severity``
(``"P0"``|``"P1"``) / ``module`` / ``artifact`` / ``detail`` plus
``to_dict()``) and aggregates it into a report card.

Report shape:

.. code-block:: json

   {
     "matrix_type": "artifact",
     "module": "<module>",
     "run_id": "<run dir name>",
     "timestamp": "<iso>",
     "artifacts_dir": "<as given>",
     "report_card": {
       "<artifact basename>": {
         "passed": true/false,
         "assertions": [ {name, passed, issue, severity, module, artifact, detail}, ... ]
       }
     },
     "counts": {"artifacts": N, "assertions": N, "passed": N, "failed": N,
                "p0_failed": N, "p1_failed": N}
   }

An artifact's ``passed`` is true only when ALL of its assertions passed;
``counts.p0_failed`` / ``p1_failed`` count FAILED assertions by severity.

``artifact_assertions`` is imported lazily (it may not exist yet while the
sibling agent is still writing it) so this module's ``--help`` and the
validation CLI's ``--help``/``--check``/``--list`` never crash on a missing
sibling module.

Usage:
    python scripts/validation/artifact_matrix.py <artifacts_dir> \\
        --module {opp,ol,orf,suite,all} --out <path>
"""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

SUITE_ROOT = Path(__file__).resolve().parents[2]
_ASSERTIONS_REL = "scripts/validation/artifact_assertions.py"

#: Known modules (mirrors the scenario library module names).  ``all`` is
#: accepted so a delivery package covering every module can be asserted in
#: one call.
_KNOWN_MODULES = ("opp", "ol", "orf", "suite", "all")


def _load_assertions() -> Any:
    """Lazily import ``scripts/validation/artifact_assertions.py`` by path.

    ``scripts/`` has no package ``__init__``, so a plain import cannot
    resolve; importlib by absolute path keeps the dependency out of the
    ``--help`` hot path.  Raises ImportError with a clear message when the
    sibling module is not present yet.
    """
    target = SUITE_ROOT / _ASSERTIONS_REL
    if not target.is_file():
        raise ImportError(
            f"artifact_assertions module not found at {target} — the "
            "artifact-assertion matrix cannot run until it exists"
        )
    spec = importlib.util.spec_from_file_location("artifact_assertions", target)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {target}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["artifact_assertions"] = module
    spec.loader.exec_module(module)
    return module


def _result_dict(result: Any) -> dict[str, Any]:
    """Normalise one assertion result into the report dict shape.

    Prefers ``to_dict()`` when present (the AssertionResult contract);
    falls back to attribute access so a duck-typed result still works.
    The ``passed`` field is coerced to a REAL bool: the sibling
    ``_html_has_structure`` assertion can short-circuit ``ok`` to a
    ``re.Match`` object (``a and b`` yields the second operand), so
    ``bool(match)`` is applied to keep the JSON report serializable
    (issue #44 acceptance: a clean artifact must not trip serialization).
    """
    if isinstance(result, dict):
        d = dict(result)
    else:
        to_dict = getattr(result, "to_dict", None)
        if callable(to_dict):
            d = to_dict()
            if not isinstance(d, dict):
                d = {}
        else:
            d = {}
        if not d:
            d = {
                "name": getattr(result, "name", "?"),
                "passed": bool(getattr(result, "passed", False)),
                "issue": getattr(result, "issue", ""),
                "severity": getattr(result, "severity", "P1"),
                "module": getattr(result, "module", ""),
                "artifact": getattr(result, "artifact", ""),
                "detail": getattr(result, "detail", ""),
            }
    d["passed"] = bool(d.get("passed", False))
    return d


class _ExtractedArtifacts:
    """Owns a temp extraction (for a delivery .zip) and cleans it up.

    Context-managed so callers release the temp dir deterministically.
    For a plain directory, ``path`` is the dir itself and no cleanup
    happens.
    """

    def __init__(self, path: Path, tmp: tempfile.TemporaryDirectory[str] | None):
        self.path = path
        self._tmp = tmp

    def __enter__(self) -> Path:
        return self.path

    def __exit__(self, *exc: Any) -> None:
        if self._tmp is not None:
            self._tmp.cleanup()
        return None


def _resolve_artifacts_dir(artifacts_dir: str | Path) -> _ExtractedArtifacts:
    """A ``_ExtractedArtifacts`` (dir to assert + optional temp cleanup).

    A ``.zip`` (delivery package) is unzipped into a fresh temp dir; the
    extracted ``01-RAW/`` subdir is asserted when present (the
    delivery-package layout: real artifacts live under 01-RAW/), else the
    whole extraction.  A plain directory is returned untouched.
    """
    p = Path(artifacts_dir)
    if p.is_dir():
        return _ExtractedArtifacts(p, None)
    if p.is_file() and p.suffix.lower() == ".zip":
        tmp = tempfile.TemporaryDirectory(prefix="omni-artifacts-")
        staging = Path(tmp.name)
        with zipfile.ZipFile(p) as zf:
            zf.extractall(staging)
        target = staging / "01-RAW"
        if not target.is_dir():
            target = staging
        return _ExtractedArtifacts(target, tmp)
    raise ValueError(f"artifacts path not found (or not a dir/zip): {p}")


def build_artifact_report(
    artifacts_dir: str | Path, module: str = "suite", run_dir: str | Path = "."
) -> dict[str, Any]:
    """Run the artifact assertions and aggregate them into a report card.

    ``artifacts_dir`` may be a directory or a delivery ``.zip`` (unzipped
    into a temp dir; ``01-RAW/`` preferred).  ``module`` selects the
    assertion set (``suite`` default).  Returns the report dict (see the
    module docstring for the shape); ``run_id`` is the ``run_dir`` basename.
    """
    if module not in _KNOWN_MODULES:
        raise ValueError(
            f"unknown module {module!r} — expected one of {', '.join(_KNOWN_MODULES)}"
        )
    with _resolve_artifacts_dir(artifacts_dir) as target:
        assertions_mod = _load_assertions()
        results = assertions_mod.run_assertions(target, module)

    card: dict[str, dict[str, Any]] = {}
    for r in results:
        d = _result_dict(r)
        artifact = d.get("artifact") or Path(artifacts_dir).name or "?"
        # The report card is keyed by ARTIFACT BASENAME (issue #44); strip a
        # full/relative path if the sibling module reported one.
        if isinstance(artifact, str) and ("/" in artifact or "\\" in artifact):
            artifact = Path(artifact).name or artifact
        entry = card.setdefault(artifact, {"passed": True, "assertions": []})
        entry["assertions"].append(d)
        if not d.get("passed", False):
            entry["passed"] = False

    all_assertions: list[dict[str, Any]] = []
    for entry in card.values():
        all_assertions.extend(entry["assertions"])
    failed = [d for d in all_assertions if not d.get("passed", False)]

    counts = {
        "artifacts": len(card),
        "assertions": len(all_assertions),
        "passed": len(all_assertions) - len(failed),
        "failed": len(failed),
        "p0_failed": sum(1 for d in failed if d.get("severity") == "P0"),
        "p1_failed": sum(1 for d in failed if d.get("severity") == "P1"),
    }

    return {
        "matrix_type": "artifact",
        "module": module,
        "run_id": Path(run_dir).name,
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "artifacts_dir": str(artifacts_dir),
        "report_card": card,
        "counts": counts,
    }


def write_artifact_report(report: dict[str, Any], run_dir: str | Path) -> Path:
    """Write ``artifact-report.json`` (pretty) into ``run_dir``; returns the path."""
    rd = Path(run_dir)
    rd.mkdir(parents=True, exist_ok=True)
    out = rd / "artifact-report.json"
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out


def _print_table(report: dict[str, Any]) -> None:
    """A compact per-artifact pass/fail table plus the totals line."""
    card = report["report_card"]
    for artifact in sorted(card):
        entry = card[artifact]
        mark = "PASS" if entry["passed"] else "FAIL"
        failures = [a for a in entry["assertions"] if not a.get("passed", False)]
        if entry["passed"]:
            print(f"  {artifact:<24} {mark}  ({len(entry['assertions'])} assertion(s))")
        else:
            first = failures[0]
            print(
                f"  {artifact:<24} {mark}  "
                f"({len(failures)}/{len(entry['assertions'])} failing — "
                f"[{first.get('severity')}] {first.get('name')}: "
                f"{first.get('issue') or first.get('detail') or 'failed'})"
            )
    c = report["counts"]
    print(
        "Totals: {artifacts} artifact(s), {assertions} assertion(s), "
        "{passed} passed, {failed} failed "
        "(P0: {p0_failed}, P1: {p1_failed})".format(**c)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="artifact_matrix",
        description=(
            "Run the artifact-assertion matrix on produced artifacts "
            "(dir or delivery .zip) and write artifact-report.json"
        ),
    )
    parser.add_argument(
        "artifacts_dir",
        help="directory of produced artifacts, or a delivery package .zip "
        "(unzipped into a temp dir; 01-RAW/ preferred)",
    )
    parser.add_argument(
        "--module",
        choices=list(_KNOWN_MODULES),
        default="suite",
        help="module whose assertion set runs (default: suite)",
    )
    parser.add_argument(
        "--out",
        default="artifact-report.json",
        help="output path for the artifact report (default: artifact-report.json)",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # --help (0) / usage error (2): keep main() pure
        return exc.code if isinstance(exc.code, int) else 0

    try:
        report = build_artifact_report(args.artifacts_dir, args.module)
        out_path = Path(args.out).resolve()
        if out_path.suffix:  # an explicit file path
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            out = out_path
        else:  # a directory — write artifact-report.json into it
            out = write_artifact_report(report, out_path)
    except (ImportError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"ARTIFACT MATRIX: {out}")
    _print_table(report)
    c = report["counts"]
    return 1 if (c["p0_failed"] + c["p1_failed"]) > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
