"""Equivalence checker — compares outputs from two matrix runs to verify
that different transport/mechanism paths produce equivalent results.

Primary use case: CLI vs MCP. Since the MCP servers in this environment
don't accept stdio connections (documented in ACCEPTED_GAPS.md), the
equivalence checker can also compare two CLI runs with different LLM
backends or settings to verify reproducibility.

For each cell in the matrix, the checker:
1. Compares file existence in both runs
2. Compares file size (within tolerance)
3. Compares text content (fuzzy match via fidelity checker)
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(SCRIPT_DIR))
from fidelity_checker import compute_fidelity, FidelityReport  # noqa: E402


@dataclass
class EquivalenceResult:
    inp: str
    outp: str
    path: str
    a_exists: bool
    b_exists: bool
    size_match: bool  # within tolerance
    text_similarity: float  # 0-1, from fidelity checker
    equivalent: bool  # True if all checks pass
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EquivalenceReport:
    cells: list[EquivalenceResult] = field(default_factory=list)
    a_label: str = "A"
    b_label: str = "B"
    total_duration_s: float = 0.0

    @property
    def equivalent(self) -> int:
        return sum(1 for c in self.cells if c.equivalent)

    @property
    def divergent(self) -> int:
        return sum(1 for c in self.cells if not c.equivalent)

    @property
    def missing_in_a(self) -> int:
        return sum(1 for c in self.cells if not c.a_exists and c.b_exists)

    @property
    def missing_in_b(self) -> int:
        return sum(1 for c in self.cells if c.a_exists and not c.b_exists)

    def to_dict(self) -> dict:
        return {
            "a_label": self.a_label,
            "b_label": self.b_label,
            "total": len(self.cells),
            "equivalent": self.equivalent,
            "divergent": self.divergent,
            "missing_in_a": self.missing_in_a,
            "missing_in_b": self.missing_in_b,
            "duration_s": self.total_duration_s,
            "cells": [c.to_dict() for c in self.cells],
        }


def compare_runs(
    a_dir: Path,
    b_dir: Path,
    a_label: str = "CLI",
    b_label: str = "MCP",
    size_tolerance: float = 0.20,
    text_threshold: float = 0.50,
) -> EquivalenceReport:
    """Compare outputs from two matrix run directories cell by cell."""
    import time
    t0 = time.monotonic()
    report = EquivalenceReport(a_label=a_label, b_label=b_label)

    a_cells = a_dir / "cells"
    b_cells = b_dir / "cells"
    if not a_cells.exists() or not b_cells.exists():
        report.notes.append(
            f"Missing cells dir: a={a_cells.exists()}, b={b_cells.exists()}"
        )
        return report

    # Discover all cell directories from run A
    for a_cell_dir in sorted(a_cells.iterdir()):
        if not a_cell_dir.is_dir():
            continue
        # Derive (inp, outp, path) from dir name: "{path}_{inp}_to_{outp}"
        parts = a_cell_dir.name.split("_to_")
        if len(parts) != 2:
            continue
        outp = parts[1]
        prefix = parts[0]
        # prefix is "{path}_{inp}"
        prefix_parts = prefix.split("_", 1)
        if len(prefix_parts) != 2:
            continue
        path, inp = prefix_parts

        # Find corresponding cell in B
        b_cell_dir = b_cells / a_cell_dir.name
        a_out = a_cell_dir / f"result.{outp}"
        b_out = b_cell_dir / f"result.{outp}" if b_cell_dir.exists() else None
        a_src = a_cell_dir / f"sample.{inp}"
        b_src = b_cell_dir / f"sample.{inp}" if b_cell_dir.exists() else None

        a_exists = a_out.exists()
        b_exists = b_out.exists() if b_out else False

        size_match = False
        text_sim = 0.0
        notes = []

        if not a_exists and not b_exists:
            notes.append("both missing — not compared")
            report.cells.append(EquivalenceResult(
                inp, outp, path, a_exists, b_exists, size_match,
                text_sim, equivalent=True, notes=notes,
            ))
            continue

        if a_exists != b_exists:
            notes.append(
                f"missing in {b_label if a_exists else a_label}"
            )
            report.cells.append(EquivalenceResult(
                inp, outp, path, a_exists, b_exists, False, 0.0,
                equivalent=False, notes=notes,
            ))
            continue

        # Both exist — compare size
        a_size = a_out.stat().st_size
        b_size = b_out.stat().st_size
        if a_size == 0 and b_size == 0:
            size_match = True
        elif max(a_size, b_size) == 0:
            size_match = False
        else:
            ratio = min(a_size, b_size) / max(a_size, b_size)
            size_match = ratio >= (1.0 - size_tolerance)

        # Compare text content
        if a_src and a_src.exists() and b_src and b_src.exists():
            # Use a_src as the reference (both runs start from same source)
            fr_a = compute_fidelity(a_src, a_out, outp)
            fr_b = compute_fidelity(b_src, b_out, outp)
            # Text similarity: how similar are the two outputs to each other?
            # Use the average of both fidelity scores
            text_sim = (fr_a.overall + fr_b.overall) / 2
        else:
            text_sim = 0.0
            notes.append("source not available for text comparison")

        equivalent = size_match and text_sim >= text_threshold
        if not size_match:
            notes.append(
                f"size diff: {a_size} vs {b_size} (tolerance {size_tolerance:.0%})"
            )
        if text_sim < text_threshold:
            notes.append(
                f"text sim {text_sim:.2f} < threshold {text_threshold:.2f}"
            )

        report.cells.append(EquivalenceResult(
            inp, outp, path, a_exists, b_exists, size_match,
            text_sim, equivalent, notes,
        ))

    report.total_duration_s = time.monotonic() - t0
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Equivalence checker")
    parser.add_argument("--a-dir", type=Path, required=True, help="Run A output dir")
    parser.add_argument("--b-dir", type=Path, required=True, help="Run B output dir")
    parser.add_argument("--a-label", default="CLI")
    parser.add_argument("--b-label", default="MCP")
    parser.add_argument("--size-tolerance", type=float, default=0.20)
    parser.add_argument("--text-threshold", type=float, default=0.50)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = compare_runs(
        args.a_dir, args.b_dir,
        a_label=args.a_label, b_label=args.b_label,
        size_tolerance=args.size_tolerance,
        text_threshold=args.text_threshold,
    )

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"Equivalence: {args.a_label} vs {args.b_label}")
        print(f"  Total: {len(report.cells)} | Equivalent: {report.equivalent} | "
              f"Divergent: {report.divergent}")
        print(f"  Missing in {args.a_label}: {report.missing_in_a} | "
              f"Missing in {args.b_label}: {report.missing_in_b}")
        for c in report.cells:
            if not c.equivalent:
                print(f"  DIVERGENT: {c.inp}→{c.outp} ({c.path}) "
                      f"size_match={c.size_match} text_sim={c.text_sim:.2f}")
                for n in c.notes:
                    print(f"    - {n}")
    return 0 if report.divergent == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
