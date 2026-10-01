"""Concurrency: extractions sharing one output directory do not corrupt each other.

Rebuilt after e2e-test-suite#102 (11 e2e files existed only on one machine and
were never committed, so CI never ran them).

The pipeline is routinely driven from an agent that fans several documents out
at once, so "run two extractions into the same ``--output-dir``" is a real
usage shape, not a synthetic one. This file exercises it with real OS
processes: one ``threading.Barrier`` releases all workers at the same instant
so their writes genuinely overlap, and there are no sleeps anywhere — a sleep
would only prove that the test can wait, not that the code is race-safe.

What is asserted is deliberately modest, because the honest guarantee is
modest: nothing raises, every invocation exits 0, and every artifact that
exists afterwards parses. It does *not* claim atomicity of OPP's writes; a
truncated ``.md`` would be caught by the parse checks, but the tests do not
manufacture a mid-write interleaving to look for one.

Hermetic: no API keys, no network, no LLM.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.requires_opp,
]

_XLIFF_NS = "urn:oasis:names:tc:xliff:document:1.2"

#: Enough workers to make an overlap the normal case rather than a lucky one.
#: Kept small so the file stays cheap: each worker is a full interpreter start.
_WORKERS = 4


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _build_docx(path: Path, index: int) -> Path:
    """A distinct small DOCX per index: a heading, a paragraph, and a 2x2 table.

    Distinct *content* matters as much as distinct filenames — if every worker
    produced identical bytes, a corrupted artifact would be indistinguishable
    from a correct one.
    """
    from docx import Document

    doc = Document()
    doc.add_heading(f"Module {index}", level=1)
    doc.add_paragraph(f"Calibration notes for module {index} of the fleet.")
    table = doc.add_table(rows=2, cols=2)
    table.style = "Table Grid"
    table.rows[0].cells[0].text = "Channel"
    table.rows[0].cells[1].text = "Reading"
    table.rows[1].cells[0].text = f"ch{index}"
    table.rows[1].cells[1].text = f"{index * 12} V"

    doc.save(str(path))
    return path


def _subprocess_env(cache_dir: Path) -> dict[str, str]:
    """Isolate OPP's on-disk cache so parallel runs cannot share cache state."""
    env = os.environ.copy()
    env["OMNI_CACHE_DIR"] = str(cache_dir)
    return env


def _extract(
    docx_path: Path,
    output_dir: Path,
    env: dict[str, str],
    resource_dir: Path | None = None,
    barrier: threading.Barrier | None = None,
) -> subprocess.CompletedProcess[str]:
    """One OPP CLI extraction, optionally released in lockstep with the others.

    ``cwd`` is the output dir because OPP creates ``logs/`` relative to the
    process cwd at import time — so the dir has to exist before the spawn, not
    just before the run.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    if resource_dir is not None:
        resource_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "opp",
        "--target-format",
        "both",
        "--source-lang",
        "en",
        "--target-lang",
        "zh",
        "--output-dir",
        str(output_dir),
    ]
    if resource_dir is not None:
        cmd += ["--resource-dir", str(resource_dir)]
    cmd.append(str(docx_path))

    if barrier is not None:
        barrier.wait(timeout=60)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=180,
        cwd=str(output_dir),
        env=env,
    )


def _run_all(
    inputs: list[Path],
    output_dir: Path,
    resource_dir: Path | None = None,
) -> list[subprocess.CompletedProcess[str]]:
    """Run ``len(inputs)`` extractions concurrently, released by one barrier.

    ``ThreadPoolExecutor`` here is a process launcher, not shared state: each
    worker only calls ``subprocess.run``, so there is no interpreter-level
    sharing to accidentally serialize the work.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    if resource_dir is not None:
        resource_dir.mkdir(parents=True, exist_ok=True)
    env = _subprocess_env(output_dir / ".cache")
    barrier = threading.Barrier(len(inputs))

    with ThreadPoolExecutor(max_workers=len(inputs)) as pool:
        futures = [
            pool.submit(_extract, docx, output_dir, env, resource_dir, barrier) for docx in inputs
        ]
        # ``.result()`` re-raises anything a worker threw, so a crash in one
        # extraction fails the test instead of being silently counted.
        return [future.result() for future in futures]


def _trans_unit_count(xlf_path: Path) -> int:
    root = ET.fromstring(xlf_path.read_text(encoding="utf-8"))
    return len(list(root.iter(f"{{{_XLIFF_NS}}}trans-unit")))


def _assert_artifacts_parse(output_dir: Path, stem: str) -> None:
    """Every artifact for ``stem`` exists and parses.

    "Exists and parses" is the whole claim: a concurrent run that produced a
    half-written markdown file or malformed XLIFF would fail right here.
    """
    md_path = output_dir / f"{stem}.md"
    assert md_path.is_file(), f"{md_path} missing"
    md_text = md_path.read_text(encoding="utf-8")
    assert md_text.strip(), f"{md_path} is empty"

    xlf_path = output_dir / f"{stem}.xlf"
    assert xlf_path.is_file(), f"{xlf_path} missing"
    count = _trans_unit_count(xlf_path)
    assert count > 0, f"{xlf_path} parsed but holds no trans-units"

    manifest_path = output_dir / f"{stem}_manifest.json"
    assert manifest_path.is_file(), f"{manifest_path} missing"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    reported = manifest["extraction"]["outputs"]["xliff"]["trans_unit_count"]
    assert reported == count, (
        f"{manifest_path} reports {reported} trans-units but {xlf_path} holds {count} "
        "— the manifest and the XLIFF were written by different, interleaved runs"
    )

    skeleton = output_dir / f"{stem}.skeleton.zip"
    assert skeleton.is_file(), f"{skeleton} missing"


# ─────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────


class TestConcurrentExtraction:
    """Parallel extractions into one output directory stay independent."""

    def test_distinct_inputs_into_shared_output_dir(self, tmp_path: Path) -> None:
        """N different documents extracted concurrently into one directory.

        All workers are released together, so the interleaving of their writes
        is real. Nothing may raise, every exit code must be 0, and each
        document's own artifact set must be complete and self-consistent.
        """
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        inputs = [_build_docx(src_dir / f"module_{index}.docx", index) for index in range(_WORKERS)]
        output_dir = tmp_path / "shared_out"

        results = _run_all(inputs, output_dir)

        for index, result in enumerate(results):
            assert result.returncode == 0, (
                f"worker {index} failed (rc={result.returncode}): {result.stderr[-800:]}"
            )
        for docx in inputs:
            _assert_artifacts_parse(output_dir, docx.stem)

    def test_same_input_into_shared_output_dir(self, tmp_path: Path) -> None:
        """The same document extracted N times concurrently yields one sound result.

        This is the harsher case: every worker writes the *same* filenames, so
        a torn write would be the only visible symptom. The result must equal
        a solo run of the same input, which is the check a reader actually
        cares about — the output is indistinguishable from an uncontended run.
        """
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        docx = _build_docx(src_dir / "shared_subject.docx", 0)

        # Reference: one uncontended run into its own directory.
        reference_dir = tmp_path / "solo_out"
        solo = _extract(docx, reference_dir, _subprocess_env(tmp_path / "solo_cache"))
        assert solo.returncode == 0, f"solo reference run failed: {solo.stderr[-800:]}"
        reference_md = (reference_dir / "shared_subject.md").read_text(encoding="utf-8")
        reference_units = _trans_unit_count(reference_dir / "shared_subject.xlf")
        assert reference_units > 0, "reference run produced no trans-units"

        # Contended: the same input, N workers, one shared output directory.
        shared_dir = tmp_path / "contended_out"
        inputs = [docx] * _WORKERS
        results = _run_all(inputs, shared_dir)
        for index, result in enumerate(results):
            assert result.returncode == 0, (
                f"contended worker {index} failed (rc={result.returncode}): {result.stderr[-800:]}"
            )

        _assert_artifacts_parse(shared_dir, "shared_subject")
        assert (shared_dir / "shared_subject.md").read_text(encoding="utf-8") == reference_md, (
            "contended markdown differs from the uncontended run"
        )
        assert _trans_unit_count(shared_dir / "shared_subject.xlf") == reference_units, (
            "contended XLIFF holds a different number of trans-units than the "
            "uncontended run — a worker was overwritten mid-write"
        )

    def test_shared_output_dir_and_shared_resource_dir(self, tmp_path: Path) -> None:
        """Concurrent runs sharing ``--output-dir`` *and* ``--resource-dir`` stay sound.

        The resource directory is the other shared-writer surface: OPP stores
        extracted media there, so two runs pointed at one resource dir are
        writing into each other's namespace.
        """
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        inputs = [
            _build_docx(src_dir / f"asset_{index}.docx", index + 100) for index in range(_WORKERS)
        ]
        output_dir = tmp_path / "shared_out"
        resource_dir = tmp_path / "shared_resources"

        results = _run_all(inputs, output_dir, resource_dir=resource_dir)

        for index, result in enumerate(results):
            assert result.returncode == 0, (
                f"worker {index} failed (rc={result.returncode}): {result.stderr[-800:]}"
            )
        for docx in inputs:
            _assert_artifacts_parse(output_dir, docx.stem)
            manifest = json.loads(
                (output_dir / f"{docx.stem}_manifest.json").read_text(encoding="utf-8")
            )
            # Whichever run won the race must still have written a manifest that
            # points into the shared resource dir, not into a per-run one.
            assert manifest["resources"]["storage_dir"].endswith("shared_resources"), (
                f"{docx.stem} manifest points at "
                f"{manifest['resources']['storage_dir']}, not the shared resource dir"
            )

    def test_every_source_document_produced_its_own_artifact_set(self, tmp_path: Path) -> None:
        """No run clobbers a sibling's outputs: N inputs, N complete sets.

        Guards the failure mode the other tests cannot see: a run that exits 0
        while writing its output under the *wrong* stem, which would still
        satisfy a per-run "my files exist" check.
        """
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        inputs = [
            _build_docx(src_dir / f"unique_{index}.docx", index + 200) for index in range(_WORKERS)
        ]
        output_dir = tmp_path / "shared_out"

        results = _run_all(inputs, output_dir)
        assert all(result.returncode == 0 for result in results), (
            "at least one concurrent extraction exited non-zero: "
            + "; ".join(str(r.returncode) for r in results)
        )

        stems = {docx.stem for docx in inputs}
        produced = {path.stem for path in output_dir.glob("*.md")}
        assert produced == stems, (
            f"expected markdown for exactly {sorted(stems)}, found {sorted(produced)}"
        )
        for docx in inputs:
            md_text = (output_dir / f"{docx.stem}.md").read_text(encoding="utf-8")
            assert docx.stem.split("_")[-1] in md_text, (
                f"{docx.stem}.md does not mention its own module number — "
                "an artifact carries another run's content"
            )
