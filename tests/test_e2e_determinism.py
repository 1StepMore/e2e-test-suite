"""Determinism: the same OPP input extracts to the same bytes every time.

Rebuilt after e2e-test-suite#102 (11 e2e files existed only on one machine and
were never committed, so CI never ran them).

Determinism matters downstream, not just aesthetically: OPP's trans-unit
``id`` and ``resname`` are the join keys ORF uses to put a translated segment
back into the right place in the source document. Run-to-run drift in those
fields silently misplaces text rather than failing loudly, so it is worth a
test that runs the extraction twice and compares.

Scope note, and a documented non-determinism: the ``*.md`` and ``*.xlf``
artifacts are byte-stable, but ``*_manifest.json`` is deliberately NOT — it
carries a fresh ``request_id`` (uuid4) and ``generated_at`` (wall clock) on
every run. That is provenance metadata, not a contract, so
``TestDeterminismScope`` pins the split explicitly rather than pretending the
manifest is reproducible or pretending the divergence does not exist.

The two runs are produced once by the module-scoped :func:`twin_runs` fixture
and shared by every test, because "the same input, twice" is the same
experiment whether the assertion is about bytes, ids, or resnames.

Hermetic: no API keys, no network, no LLM.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.requires_opp,
]

_XLIFF_NS = "urn:oasis:names:tc:xliff:document:1.2"

#: Anything that looks like a generated identifier or a clock reading. If one
#: of these shows up in an id/resname, the value is not reproducible and the
#: downstream join key is unstable.
_VOLATILE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "uuid",
        re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I),
    ),
    ("iso-8601 timestamp", re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")),
    ("epoch-looking integer", re.compile(r"^1[6-9]\d{8,}$")),
)

#: The two manifest fields that are per-run provenance rather than contract.
_VOLATILE_MANIFEST_KEYS = frozenset({"request_id", "generated_at"})

#: The coordinate contract in CONTRACT.md: paragraphs are ``para_index_N`` and
#: table cells are ``table_{t}_r{r}_c{c}`` (OPP#80, per-paragraph table cells).
_COORDINATE_RESNAME = re.compile(r"^(?:para_index_\d+|table_\d+_r\d+_c\d+)$")


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _run_opp(docx_path: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
    """Extract once via the shipped OPP CLI.

    ``cwd`` is the output dir because OPP creates ``logs/`` relative to the
    process cwd at import time — keeping the repo tree free of test residue.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [
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
            str(docx_path),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=str(output_dir),
    )


def _trans_units(xlf_path: Path) -> list[tuple[str, str, str]]:
    """Return ``(id, resname, source)`` for every trans-unit, in document order."""
    root = ET.fromstring(xlf_path.read_text(encoding="utf-8"))
    units: list[tuple[str, str, str]] = []
    for unit in root.iter(f"{{{_XLIFF_NS}}}trans-unit"):
        source = unit.find(f"{{{_XLIFF_NS}}}source")
        units.append(
            (
                unit.get("id", ""),
                unit.get("resname", ""),
                (source.text or "") if source is not None else "",
            )
        )
    return units


def _volatile_hits(value: str) -> list[str]:
    """Return the names of every volatility pattern that matches ``value``."""
    return [name for name, pattern in _VOLATILE_PATTERNS if pattern.search(value)]


# ─────────────────────────────────────────────────────────────────────
# Fixtures — one DOCX, extracted twice, shared by every test below
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def determinism_docx(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A small controlled DOCX: 2 headings, 2 paragraphs, one 2x2 table.

    Built locally rather than reusing ``conftest.sample_docx_path`` because this
    needs module scope (the extraction pair is shared), and because a
    determinism test wants a fixed, minimal input whose expected trans-unit
    count it fully controls.
    """
    from docx import Document

    doc = Document()
    doc.add_heading("Calibration Manual", level=1)
    doc.add_heading("Preflight Checks", level=2)
    doc.add_paragraph("Verify the sensor is seated before applying power.")
    doc.add_paragraph("Then run the three-step calibration sequence.")
    table = doc.add_table(rows=2, cols=2)
    table.style = "Table Grid"
    table.rows[0].cells[0].text = "Setting"
    table.rows[0].cells[1].text = "Default"
    table.rows[1].cells[0].text = "Timeout"
    table.rows[1].cells[1].text = "30 seconds"

    docx_path = tmp_path_factory.mktemp("input") / "calibration.docx"
    doc.save(str(docx_path))
    return docx_path


@pytest.fixture(scope="module")
def twin_runs(
    tmp_path_factory: pytest.TempPathFactory, determinism_docx: Path
) -> tuple[Path, Path]:
    """Extract the same DOCX twice into two sibling directories.

    Two real subprocess invocations, roughly a second apart in wall-clock time,
    which is enough for any clock- or uuid-derived value to differ if it were
    going to. No sleeps and no frozen clock: the point is to observe real
    non-determinism, not to manufacture it.
    """
    base = tmp_path_factory.mktemp("determinism")
    runs = (base / "run_1", base / "run_2")
    for out in runs:
        result = _run_opp(determinism_docx, out)
        assert result.returncode == 0, f"OPP CLI run into {out} failed: {result.stderr}"
    return runs


# ─────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────


class TestExtractionIsReproducible:
    """Two extractions of the same input produce the same artifacts."""

    def test_markdown_is_byte_identical(self, twin_runs: tuple[Path, Path]) -> None:
        """The extracted markdown is byte-for-byte the same across two runs."""
        first, second = twin_runs
        first_text = (first / "calibration.md").read_text(encoding="utf-8")
        second_text = (second / "calibration.md").read_text(encoding="utf-8")

        assert first_text.strip(), "first run produced empty markdown"
        assert first_text == second_text, (
            f"markdown drifted between identical extractions: "
            f"{len(first_text)} vs {len(second_text)} chars"
        )

    def test_xliff_file_is_byte_identical(self, twin_runs: tuple[Path, Path]) -> None:
        """The whole ``.xlf`` file matches, so nothing hidden in it drifts either."""
        first, second = twin_runs
        first_xlf = (first / "calibration.xlf").read_text(encoding="utf-8")
        second_xlf = (second / "calibration.xlf").read_text(encoding="utf-8")

        assert first_xlf == second_xlf, "the XLIFF file drifted between runs"

    def test_trans_unit_ids_and_resnames_are_identical(self, twin_runs: tuple[Path, Path]) -> None:
        """The ``(id, resname)`` join keys are identical across two runs."""
        first, second = twin_runs
        first_units = _trans_units(first / "calibration.xlf")
        second_units = _trans_units(second / "calibration.xlf")

        assert len(first_units) > 1, (
            f"only {len(first_units)} trans-unit(s); the comparison would be vacuous"
        )
        first_keys = [(unit_id, resname) for unit_id, resname, _ in first_units]
        second_keys = [(unit_id, resname) for unit_id, resname, _ in second_units]

        assert first_keys == second_keys, (
            f"XLIFF join keys drifted between identical extractions:\n"
            f"  run 1: {first_keys}\n  run 2: {second_keys}"
        )

    def test_xliff_source_text_is_identical(self, twin_runs: tuple[Path, Path]) -> None:
        """The extracted ``<source>`` text is identical across two runs.

        Separate from the id/resname check because source text is what a
        translator actually reads, and nondeterminism there would change the
        translation input while leaving the join keys intact.
        """
        first, second = twin_runs
        first_sources = [source for _, _, source in _trans_units(first / "calibration.xlf")]
        second_sources = [source for _, _, source in _trans_units(second / "calibration.xlf")]

        assert first_sources, "no <source> text to compare"
        assert first_sources == second_sources, (
            f"XLIFF <source> text drifted: {first_sources} vs {second_sources}"
        )


class TestDeterminismScope:
    """What is reproducible, and what is deliberately not."""

    def test_join_keys_carry_no_timestamp_or_uuid(self, twin_runs: tuple[Path, Path]) -> None:
        """No ``id`` or ``resname`` contains a uuid, timestamp, or epoch.

        The direct form of the determinism requirement: comparing two runs
        would not catch a uuid4 leak if the two runs happened to be compared
        after the key was already pinned somewhere, and a uuid in an ``id`` is
        reproducible-looking in a diff while being unique per run.
        """
        first, _ = twin_runs
        units = _trans_units(first / "calibration.xlf")
        assert units, "no trans-units to inspect"

        offenders: list[str] = []
        for unit_id, resname, _ in units:
            for field, value in (("id", unit_id), ("resname", resname)):
                offenders.extend(
                    f"{field}={value!r} matches {pattern_name!r}"
                    for pattern_name in _volatile_hits(value)
                )

        assert not offenders, "non-reproducible values leaked into XLIFF keys: " + "; ".join(
            offenders
        )

    def test_resnames_follow_the_documented_coordinate_contract(
        self, twin_runs: tuple[Path, Path]
    ) -> None:
        """Every ``resname`` is ``para_index_N`` or ``table_{t}_r{r}_c{c}``.

        CONTRACT.md defines the per-paragraph table-cell coordinate (OPP#80).
        Reproducibility alone would be satisfied by a stable but meaningless
        key, so this pins the key's *shape* too.
        """
        first, _ = twin_runs
        resnames = [resname for _, resname, _ in _trans_units(first / "calibration.xlf")]
        assert resnames, "no trans-units to inspect"

        offenders = [name for name in resnames if not _COORDINATE_RESNAME.match(name)]
        assert not offenders, (
            f"resname(s) do not match the CONTRACT.md coordinate form: {offenders} "
            f"(all: {resnames})"
        )

    def test_manifest_divergence_is_confined_to_provenance_fields(
        self, twin_runs: tuple[Path, Path]
    ) -> None:
        """``*_manifest.json`` differs only in ``request_id`` and ``generated_at``.

        The filename of this module says "determinism"; the honest scope is the
        *artifacts*, and the manifest is the one artifact carrying per-run
        provenance. This test exists so the divergence is a pinned, explained
        property rather than a surprise somebody later "fixes" by deleting the
        metadata — or assumes is a bug and files against it.

        It asserts both halves: the two provenance fields genuinely differ (so
        the exclusion below is not hiding a real regression), and everything
        else matches once the per-run output paths are normalised away.
        """
        first, second = twin_runs
        first_manifest = json.loads(
            (first / "calibration_manifest.json").read_text(encoding="utf-8")
        )
        second_manifest = json.loads(
            (second / "calibration_manifest.json").read_text(encoding="utf-8")
        )

        assert first_manifest.get("request_id") != second_manifest.get("request_id"), (
            "manifest request_id is identical across runs; it is a fresh uuid4 per "
            "run, so identical values mean provenance is being copied, not generated"
        )
        assert first_manifest.get("generated_at") != second_manifest.get("generated_at"), (
            "manifest generated_at is identical across runs; expected wall-clock time"
        )

        def _normalise(manifest: dict, run_dir: Path) -> dict:
            """Drop the two provenance fields and the run-specific path prefix."""
            stable = {k: v for k, v in manifest.items() if k not in _VOLATILE_MANIFEST_KEYS}
            return json.loads(json.dumps(stable).replace(str(run_dir), "<RUN_DIR>"))

        first_stable = _normalise(first_manifest, first)
        second_stable = _normalise(second_manifest, second)
        assert first_stable == second_stable, (
            "manifest fields other than request_id/generated_at drifted:\n"
            f"  run 1: {first_stable}\n  run 2: {second_stable}"
        )
