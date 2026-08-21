"""Tests for scripts/validation/coverage_audit.py (plan todo 17).

The coverage audit is the agent-satisfaction metric (draft D13, mission
axis 1): every live MCP tool must be scenario-used, else ``missing`` —
an agent-user would hit it blind.  It also surfaces DRIFT between the
LIVE module registries and the frozen contract fixtures (draft D11:
``tests/contract/fixtures/*_mcp_schemas.json`` + ``EXPECTED_COUNTS`` at
``tests/contract/test_mcp_schemas.py:49``) as a finding, without
modifying those fixtures (todo 21 reconciles them).

The script lives under ``scripts/`` which is not a package (no
``__init__.py``), so the module is loaded from its file path with
importlib — the same "thin wrapper around a real module" convention as
``scripts/validation/run_validation.py``.

RED-first discipline: every test here drives ``compute_coverage`` /
``main()`` with explicit tmp scenario/fixture dirs where a failure is
simulated; the happy test runs against the REAL repo library (after
todo 14 landed all 39 per-tool agent-surface scenarios and todo 20
added the two suite validation tools — 41 declared).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SUITE_ROOT = Path(__file__).resolve().parent.parent.parent

_AUDIT_PATH = SUITE_ROOT / "scripts" / "validation" / "coverage_audit.py"


def _load_audit():
    """Import scripts/validation/coverage_audit.py from its file path."""
    spec = importlib.util.spec_from_file_location("coverage_audit", _AUDIT_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Register before exec so dataclass forward references resolve
    # (``dataclasses`` looks the class module up in sys.modules).
    sys.modules["coverage_audit"] = mod
    spec.loader.exec_module(mod)
    return mod


audit = _load_audit()

#: The four live registry modules the audit must parse (D13).
MODULES = ("opp", "ol", "orf", "omni_mcp")


def _write_scenario(dir_path: Path, filename: str, *, mcp_tool: str | None = None) -> Path:
    """Write a minimal scenario YAML; optionally with a ``kind: mcp`` step."""
    yf = dir_path / filename
    lines = [
        f"name: {filename.removesuffix('.yaml')}",
        'description: "test scenario"',
        "tier: 1",
        "steps:",
    ]
    if mcp_tool is not None:
        lines += [
            "  - name: 'mcp step'",
            "    kind: mcp",
            f"    tool: {mcp_tool}",
            "    arguments: {}",
            "    expect:",
            "      success: true",
        ]
    else:
        lines += [
            "  - name: 'provision'",
            "    kind: python",
            "    command: 'print(1)'",
            "    expect:",
            "      success: true",
        ]
    yf.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return yf


@pytest.fixture()
def full_scenario_dir(tmp_path: Path) -> Path:
    """A tmp scenarios dir with one tool-<module>-<tool>.yaml per LIVE
    declared tool (derived from the registries, never hardcoded)."""
    surface = audit.load_live_surface()
    scn = tmp_path / "agent-surface"
    scn.mkdir(parents=True)
    for module, tools in surface.items():
        for tool in tools:
            _write_scenario(scn, f"tool-{module}-{tool}.yaml")
    return scn


# ---------------------------------------------------------------------------
# Happy path — every declared tool has a scenario (guide §5.1, D13)
# ---------------------------------------------------------------------------


def test_live_surface_is_four_modules_and_nonempty():
    """The audit parses the LIVE registries: opp 9 / ol 21 / orf 7 /
    omni_mcp 4 (41 total at acceptance).  The count derives from the
    registries — the test only pins per-module non-emptiness plus the
    known module keys and the four suite tools."""
    surface = audit.load_live_surface()
    assert set(surface) == set(MODULES)
    for module in MODULES:
        assert len(surface[module]) > 0, f"{module} surface parsed empty"
    assert "translate_file" in surface["omni_mcp"]
    assert "ping" in surface["omni_mcp"]


@pytest.mark.parametrize("module", MODULES)
def test_real_repo_all_declared_tools_covered(module: str):
    """Happy: against the REAL scenario library (todo 14 landed all 39
    per-tool agent-surface scenarios, todo 20 the two suite validation
    tools), every declared tool of every module is scenario-used — zero
    ``missing``, zero ``phantom``."""
    report = audit.compute_coverage(SUITE_ROOT)
    assert report.missing[module] == [], (
        f"{module}: declared but never scenario-used: {report.missing[module]}"
    )
    assert report.covered[module] == sorted(report.declared[module])


def test_real_repo_main_exits_zero():
    """Happy: ``python scripts/validation/coverage_audit.py`` exits 0
    when nothing is missing (acceptance criterion for todo 17)."""
    assert audit.main([]) == 0


# ---------------------------------------------------------------------------
# Failure path — a missing scenario must surface under ``missing`` + exit 1
# ---------------------------------------------------------------------------

_MISSING_CASES = [
    ("opp", "extract_document", "tool-opp-extract_document.yaml"),
    ("ol", "translate_md_text", "tool-ol-translate_md_text.yaml"),
    ("orf", "apply_md", "tool-orf-apply_md.yaml"),
]


@pytest.mark.parametrize("module,tool,filename", _MISSING_CASES)
def test_missing_tool_reported_and_exit_1(
    module: str, tool: str, filename: str, full_scenario_dir: Path
):
    """Failure: delete ONE tool scenario from an otherwise-complete
    library → that tool lands under ``missing`` for its module and the
    audit exits 1 (guide §5.1: missing is the actionable half)."""
    (full_scenario_dir / filename).unlink()
    report = audit.compute_coverage(SUITE_ROOT, scenarios_dir=full_scenario_dir)
    assert tool in report.missing[module]
    assert audit.main(["--scenarios-dir", str(full_scenario_dir)]) == 1


def test_shared_tool_name_missing_in_both_modules(full_scenario_dir: Path):
    """The sets are name-based (guide §5.1): ``translate_file`` is declared
    by BOTH ``ol`` and ``omni_mcp`` — deleting only the suite scenario
    leaves the name covered via OL's, so it surfaces under ``missing`` in
    both modules only when BOTH scenarios are gone."""
    for filename in ("tool-ol-translate_file.yaml", "tool-omni_mcp-translate_file.yaml"):
        (full_scenario_dir / filename).unlink()
    report = audit.compute_coverage(SUITE_ROOT, scenarios_dir=full_scenario_dir)
    assert "translate_file" in report.missing["ol"]
    assert "translate_file" in report.missing["omni_mcp"]
    assert audit.main(["--scenarios-dir", str(full_scenario_dir)]) == 1


def test_missing_scenario_name_is_linked(full_scenario_dir: Path):
    """The report names the uncovered tool, not just a count — an
    agent-user would hit it blind (D13)."""
    (full_scenario_dir / "tool-opp-extract_document.yaml").unlink()
    report = audit.compute_coverage(SUITE_ROOT, scenarios_dir=full_scenario_dir)
    assert "extract_document" in report.missing["opp"]
    assert "extract_document" not in report.covered["opp"]


# ---------------------------------------------------------------------------
# Phantom path — a scenario naming a non-existent tool contributes zero
# ---------------------------------------------------------------------------


def test_phantom_tool_never_counts_as_coverage(tmp_path: Path):
    """Phantom (guide §5.1): a scenario naming a tool no live registry
    declares lands in ``phantom`` — never in ``covered``/``missing``."""
    scn = tmp_path / "agent-surface"
    scn.mkdir(parents=True)
    _write_scenario(scn, "tool-opp-extract_document.yaml", mcp_tool="opp.mcp.server.extract_document")
    _write_scenario(scn, "tool-opp-definitely_not_a_tool.yaml", mcp_tool="opp.mcp.server.definitely_not_a_tool")
    report = audit.compute_coverage(SUITE_ROOT, scenarios_dir=scn)
    assert "definitely_not_a_tool" in report.phantom
    assert "definitely_not_a_tool" not in report.covered["opp"]
    assert "definitely_not_a_tool" not in report.missing["opp"]


def test_error_boundary_probe_is_allowlisted_not_phantom(tmp_path: Path):
    """Guide §5.1 legitimate exception: an explicit error-boundary probe
    (ORF ``_call_tool`` dispatch with a typo'd name) is allowlisted, never
    silently counted as coverage, and never reported as phantom."""
    scn = tmp_path / "agent-surface"
    scn.mkdir(parents=True)
    _write_scenario(scn, "tool-orf-ping.yaml", mcp_tool="orf.mcp.server.ping")
    _write_scenario(scn, "tool-orf-unknown-dispatch.yaml", mcp_tool="orf.mcp.server._call_tool")
    report = audit.compute_coverage(SUITE_ROOT, scenarios_dir=scn)
    assert "_call_tool" in report.error_boundary_probes
    assert "_call_tool" not in report.phantom


# ---------------------------------------------------------------------------
# DRIFT — frozen contract fixtures vs live registries (D11, todo 21 finding)
# ---------------------------------------------------------------------------


def test_drift_real_fixtures_underpin_live_surface():
    """Drift on the REAL frozen fixtures: opp 9 / ol 21 / orf 7 = 37 vs
    live module surface 37 (+4 suite tools unpinned) = 41.  Todo 21
    reconciled the fixtures to the live surface, so module-level drift is
    now 0 — the audit still reads the real files (not a constant) and
    reports the suite unpinned tools as the remaining by-design gap."""
    report = audit.compute_coverage(SUITE_ROOT)
    d = report.drift
    # per-module deltas after todo 21 reconciliation (frozen == live)
    assert d["ol"]["frozen"] == 21 and d["ol"]["live"] == 21
    assert d["opp"]["frozen"] == 9 and d["opp"]["live"] == 9
    assert d["orf"]["frozen"] == 7 and d["orf"]["live"] == 7
    # totals: frozen 37 vs live module-level 37, plus suite 4 unpinned
    assert d["totals"]["frozen"] == 37
    assert d["totals"]["live_module"] == 37
    assert d["totals"]["live_suite"] == 4
    assert d["totals"]["live_total"] == 41


def test_drift_computed_from_files_not_hardcoded(tmp_path: Path):
    """The drift section reads the fixture JSONs and the EXPECTED_COUNTS
    literal from test_mcp_schemas.py — point it at synthetic files and it
    derives those numbers instead of trusting a constant."""
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    for module, count in (("opp", 7), ("ol", 9), ("orf", 6)):
        schemas = [{"name": f"t{i}", "description": "", "inputSchema": {}} for i in range(count)]
        (fixtures / f"{module}_mcp_schemas.json").write_text(
            audit.json.dumps(schemas), encoding="utf-8"
        )
    report = audit.compute_coverage(
        SUITE_ROOT,
        fixtures_dir=fixtures,
        expected_counts_file=tmp_path / "test_mcp_schemas.py",  # absent → EXPECTED_COUNTS read skipped
    )
    assert report.drift["ol"] == {"frozen": 9, "live": 21, "delta": 12}
    assert report.drift["totals"]["frozen"] == 22


def test_expected_counts_literal_parsed_from_test_file():
    """EXPECTED_COUNTS at tests/contract/test_mcp_schemas.py:49 is read
    via a static AST parse (deterministic, no import of the test module).
    After todo 21's reconciliation the literal pins the live 37-tool
    surface: opp 9 / orf 7 / ol 21."""
    counts = audit.parse_expected_counts(
        SUITE_ROOT / "tests" / "contract" / "test_mcp_schemas.py"
    )
    assert counts == {"opp": 9, "orf": 7, "ol": 21}


# ---------------------------------------------------------------------------
# Coverage snapshot (todo 26, OPP#58) — --out, shape, parent-dir creation,
# and the delta the diff tool consumes
# ---------------------------------------------------------------------------


def test_main_out_writes_snapshot_json(tmp_path: Path):
    """main(['--out', path]) writes a snapshot JSON that parses and has a
    totals block; exit code follows the normal missing logic (0 on the
    real repo library)."""
    import json as _json

    out = tmp_path / "coverage.json"
    rc = audit.main(["--out", str(out)])

    assert rc == 0
    assert out.is_file()
    data = _json.loads(out.read_text(encoding="utf-8"))
    assert "totals" in data
    assert data["totals"]["declared"] > 0


def test_build_snapshot_shape(tmp_path: Path):
    """build_snapshot nests the declared/covered/missing per-module sets,
    phantom as a flat list, plus totals — the diff-friendly shape."""
    report = audit.compute_coverage(SUITE_ROOT)
    snap = audit.build_snapshot(report)

    assert set(snap) == {"generated_at", "suite_sha", "declared", "covered", "missing", "phantom", "totals"}
    for key in ("declared", "covered", "missing"):
        assert set(snap[key]) == set(MODULES)
        assert isinstance(snap[key]["opp"], list)
    assert isinstance(snap["phantom"], list)
    assert set(snap["totals"]) == {"declared", "covered", "missing"}
    assert snap["totals"]["declared"] == snap["totals"]["covered"]  # real repo: full coverage
    assert snap["suite_sha"] != "unknown"


def test_write_snapshot_creates_parent_dirs(tmp_path: Path):
    """write_snapshot creates nested parent dirs and returns the path."""
    report = audit.compute_coverage(SUITE_ROOT)
    deep = tmp_path / "a" / "b" / "c" / "coverage.json"

    written = audit.write_snapshot(report, deep)

    assert written == deep
    assert deep.is_file()


def test_coverage_delta_diffs_snapshots(tmp_path: Path):
    """compute_coverage_delta between two snapshot-carrying runs returns
    the delta — numeric counts diff arithmetically, list membership by
    added/removed (validation_diff consumes this)."""
    import importlib.util
    import sys as _sys

    diff_spec = importlib.util.spec_from_file_location(
        "validation_diff", SUITE_ROOT / "scripts" / "validation" / "validation_diff.py"
    )
    diff_mod = importlib.util.module_from_spec(diff_spec)
    assert diff_spec.loader is not None
    _sys.modules["validation_diff"] = diff_mod
    diff_spec.loader.exec_module(diff_mod)

    older = tmp_path / "20260814-100000"
    newer = tmp_path / "20260814-200000"
    older.mkdir(parents=True)
    newer.mkdir(parents=True)
    (older / "coverage.json").write_text(
        '{"declared": {"opp": 9}, "covered": {"opp": 9}, "missing": {"opp": []}, '
        '"phantom": [], "totals": {"declared": 9, "covered": 9, "missing": 0}}',
        encoding="utf-8",
    )
    (newer / "coverage.json").write_text(
        '{"declared": {"opp": 9}, "covered": {"opp": 8}, "missing": {"opp": ["extract_document"]}, '
        '"phantom": [], "totals": {"declared": 9, "covered": 8, "missing": 1}}',
        encoding="utf-8",
    )

    delta, note = diff_mod.compute_coverage_delta(older, newer)

    assert delta is not None
    assert delta["totals.covered"] == {"older": 9, "newer": 8, "delta": -1}
    assert delta["missing.opp"]["added"] == ["extract_document"]
