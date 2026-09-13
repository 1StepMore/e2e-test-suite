"""T-21 — every field the loader declares is used by at least one scenario.

The loader's closed field sets (``_SCENARIO_FIELDS`` / ``_STEP_FIELDS``) are
the schema contract: every field there is a promise the engine accepts.
A field that appears in the schema but in zero scenario files is dead
surface — it cannot be exercised, so it can silently bit-rot (T-21:
``min_passing`` / ``pass_ratio`` / ``recovery_steps`` were declared and
unused; ``requires_http`` was declared with no HTTP surface at all).

This module pins the invariant from the *raw YAML keys* of the live
scenario libraries — deliberately before the loader applies its
``setdefault`` fills, because a defaulted field (e.g. ``recovery_steps``)
would otherwise look "used" in every loaded scenario even when no author
ever writes it.

Two directions are checked:

1. **Presence** — every optional declared field appears as a raw key in
   at least one scenario across the four libraries.
2. **Removal** — a field with no implementing surface is gone from the
   schema (``requires_http``: the engine has no HTTP dispatch kind), and
   the loader now rejects it as an unknown top-level key.

The R-04 partial-success and R-05-style recovery scenarios added for T-21
are also asserted to genuinely drive the engine feature they declare
(``min_passing``/``pass_ratio`` -> ``partial-pass``; ``recovery_steps``
present on a step), not merely to carry the key.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from omni_mcp.validation.engine import _aggregate
from omni_mcp.validation.loader import (
    _SCENARIO_FIELDS,
    _STEP_FIELDS,
    ScenarioError,
    validate_scenario,
)

#: Repository root (tests/validation/test_field_usage.py -> repo root).
_ROOT = Path(__file__).resolve().parents[2]

#: The four scenario libraries a live run can load (suite + three sub-repos).
_LIBRARY_ROOTS = (
    "scenarios",
    "Omni_Pre_Processor/scenarios",
    "Omni_Localizer/scenarios",
    "Omni_Re_Formatter/scenarios",
)

#: Required fields are present in every scenario by construction, so their
#: "usage" is already proved for the whole library; only optional fields can
#: go unused.  ``name``/``description``/``steps`` are checked by the loader;
#: ``kind``/``expect`` are non-empty on every step.
_REQUIRED_SCENARIO_FIELDS = frozenset({"name", "description", "steps"})
_REQUIRED_STEP_FIELDS = frozenset({"kind", "expect"})

#: The scenario that exercises the R-04 partial-success policy.
_PARTIAL_SUCCESS_SCENARIO = "scenarios/orf-md/orf-md-batch-partial-success.yaml"

#: The scenario that exercises ``recovery_steps`` (failure injection).
_RECOVERY_SCENARIO = "scenarios/orf-md/orf-md-failure-injection-recovery.yaml"


# ---------------------------------------------------------------------------
# Raw-key scan (before loader defaults)
# ---------------------------------------------------------------------------


def _raw_field_usage() -> tuple[set[str], set[str]]:
    """Return (scenario-level keys, step-level keys) used in RAW YAML.

    Recurses into ``recovery_steps`` (nested one level) and ``cleanup_steps``
    so a field written only inside a secondary step still counts as used.
    """
    scenario_keys: set[str] = set()
    step_keys: set[str] = set()

    def walk_steps(steps: object) -> None:
        if not isinstance(steps, list):
            return
        for step in steps:
            if not isinstance(step, dict):
                continue
            step_keys.update(step.keys())
            walk_steps(step.get("recovery_steps"))

    for rel in _LIBRARY_ROOTS:
        base = _ROOT / rel
        if not base.is_dir():
            continue
        for yaml_path in sorted(base.rglob("*.yaml")):
            if any(part.startswith(".") for part in yaml_path.parts):
                continue
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            scenario_keys.update(data.keys())
            walk_steps(data.get("steps"))
            walk_steps(data.get("cleanup_steps"))

    return scenario_keys, step_keys


_RAW_SCENARIO_KEYS, _RAW_STEP_KEYS = _raw_field_usage()

#: Optional declared fields = the ones this test must find a user for.
_UNUSED_SCENARIO_FIELDS = sorted(
    _SCENARIO_FIELDS - _REQUIRED_SCENARIO_FIELDS - _RAW_SCENARIO_KEYS
)
_UNUSED_STEP_FIELDS = sorted(
    _STEP_FIELDS - _REQUIRED_STEP_FIELDS - _RAW_STEP_KEYS
)


def test_at_least_one_scenario_library_was_scanned():
    """Guard: a broken glob would make the presence checks vacuously true."""
    assert _RAW_SCENARIO_KEYS, "no scenario YAML found — the scan is broken"
    assert _RAW_STEP_KEYS, "no step keys found — the scan is broken"


@pytest.mark.parametrize("field", sorted(_SCENARIO_FIELDS - _REQUIRED_SCENARIO_FIELDS))
def test_every_declared_scenario_field_is_used(field: str):
    """Every optional scenario-level field appears in >=1 scenario."""
    assert field in _RAW_SCENARIO_KEYS, (
        f"scenario field {field!r} is declared in loader._SCENARIO_FIELDS but "
        f"used by 0 scenarios — exercise it or remove it (T-21)"
    )


@pytest.mark.parametrize("field", sorted(_STEP_FIELDS - _REQUIRED_STEP_FIELDS))
def test_every_declared_step_field_is_used(field: str):
    """Every optional step-level field appears in >=1 scenario step."""
    assert field in _RAW_STEP_KEYS, (
        f"step field {field!r} is declared in loader._STEP_FIELDS but used by "
        f"0 scenarios — exercise it or remove it (T-21)"
    )


def test_no_unused_declared_fields_remain():
    """Aggregate assertion (the T-21 acceptance in one place)."""
    assert not _UNUSED_SCENARIO_FIELDS, (
        f"unused scenario field(s): {_UNUSED_SCENARIO_FIELDS}"
    )
    assert not _UNUSED_STEP_FIELDS, f"unused step field(s): {_UNUSED_STEP_FIELDS}"


# ---------------------------------------------------------------------------
# requires_http: declared with no implementing surface -> removed
# ---------------------------------------------------------------------------


def test_requires_http_is_removed_from_the_schema():
    """No HTTP dispatch kind exists, so the field was deleted, not exercised."""
    assert "requires_http" not in _SCENARIO_FIELDS


def test_requires_http_is_rejected_as_unknown(tmp_path: Path):
    """The closed field set still rejects the removed key (no silent ignore)."""
    scenario = {
        "name": "no-http",
        "description": "requires_http is no longer part of the schema",
        "requires_http": True,
        "steps": [
            {"kind": "cli", "command": "true", "expect": {"success": True}}
        ],
    }
    with pytest.raises(ScenarioError) as excinfo:
        validate_scenario(scenario, tmp_path / "no-http.yaml")
    assert "requires_http" in str(excinfo.value)


# ---------------------------------------------------------------------------
# The T-21 scenarios genuinely drive the engine features they declare
# ---------------------------------------------------------------------------


def _load_raw(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_partial_success_scenario_exercises_min_passing_or_pass_ratio():
    """The R-04 scenario declares the partial bar AND the engine honors it.

    A scenario whose steps are 2 green / 1 red must grade ``partial-pass``
    from the bar the scenario declares — proving the fields are consumed,
    not decorative.
    """
    raw = _load_raw(_ROOT / _PARTIAL_SUCCESS_SCENARIO)
    assert raw.get("min_passing") or raw.get("pass_ratio"), (
        "the partial-success scenario must declare min_passing and/or pass_ratio"
    )
    records = [
        {"passed": True, "known_gap": False, "status": "passed"},
        {"passed": True, "known_gap": False, "status": "passed"},
        {"passed": False, "known_gap": False, "status": "failed"},
    ]
    assert _aggregate(raw, records) == "partial-pass"


def test_recovery_scenario_declares_recovery_steps_on_a_step():
    """The failure/recovery scenario carries >=1 step with recovery_steps."""
    raw = _load_raw(_ROOT / _RECOVERY_SCENARIO)
    steps = raw.get("steps") or []
    with_recovery = [
        s for s in steps if isinstance(s, dict) and s.get("recovery_steps")
    ]
    assert with_recovery, (
        "the failure/recovery scenario must declare at least one step with "
        "recovery_steps"
    )
