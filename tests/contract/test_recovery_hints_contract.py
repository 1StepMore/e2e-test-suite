"""R-09 contract test — recovery hints in every MCP error envelope.

Planned gap **R-09** in ``.omo/plans/agent-oriented-gap-register.md``:

    Add optional ``recovery: {strategy, hint}`` to every server's error
    envelope; document per code.
    Verify: contract test asserts every declared code maps to a non-empty
    recovery hint.

This test is the RED gate. It is written against a registry API the four
servers do not yet expose:

Per server module (``opp.mcp._errors``, ``ol_mcp._errors``,
``orf.mcp._errors``, ``omni_mcp._errors``)::

    DECLARED_ERROR_CODES: frozenset[str]   # every code the module can emit
    RECOVERY_HINTS: dict[str, RecoveryHint]  # code -> {strategy, hint}
    recovery_for(code) -> {"strategy": str, "hint": str}

And each server's error envelope carries a top-level
``"recovery": {"strategy": ..., "hint": ...}``.

The hint text is **static** — it must never interpolate the exception
message or any caller-controlled data (adversarial: prompt_injection).

Run::

    python -m pytest tests/contract/test_recovery_hints_contract.py -q
"""
from __future__ import annotations

import importlib
import json
from typing import Callable

import pytest

# Server key -> module path that must expose the recovery registry.
_REGISTRY_MODULES = {
    "opp": "opp.mcp._errors",
    "ol": "ol_mcp._errors",
    "orf": "orf.mcp._errors",
    "omni": "omni_mcp._errors",
}

# Canonical recovery-strategy vocabulary. Kept in one place so a strategy
# typo in any server fails this contract immediately.
ALLOWED_STRATEGIES = frozenset({
    "retry",
    "fix_input",
    "use_allowed_path",
    "reduce_input",
    "reissue_with_auth",
    "fallback",
    "configure_environment",
    "report_bug",
    "abort",
})

# Minimum useful hint length — a one-word "retry" is not actionable.
_MIN_HINT_LEN = 15

# Canary injected into exception messages to prove hints are static.
_CANARY = "CANARY_R09_9283746"


def _load_registry(server: str):
    """Import a server's recovery registry, failing loudly if absent."""
    module = importlib.import_module(_REGISTRY_MODULES[server])
    for attr in ("DECLARED_ERROR_CODES", "RECOVERY_HINTS", "recovery_for"):
        assert hasattr(module, attr), (
            f"{server}: {_REGISTRY_MODULES[server]} must expose {attr!r} "
            "(R-09 recovery registry)"
        )
    return module


@pytest.fixture(params=sorted(_REGISTRY_MODULES))
def registry(request):
    return request.param, _load_registry(request.param)


# ── Registry contract ────────────────────────────────────────────────


def test_declared_codes_are_nonempty(registry):
    server, module = registry
    assert module.DECLARED_ERROR_CODES, f"{server}: DECLARED_ERROR_CODES is empty"


def test_every_declared_code_has_a_registered_hint(registry):
    """The plan's verify clause: every declared code maps to a hint."""
    server, module = registry
    missing = sorted(
        code for code in module.DECLARED_ERROR_CODES
        if code not in module.RECOVERY_HINTS
    )
    assert not missing, (
        f"{server}: declared error codes without a recovery hint: {missing}. "
        "Add them to RECOVERY_HINTS."
    )


def test_no_orphan_hints(registry):
    """No dead mapping entries — every hint key must be a declared code."""
    server, module = registry
    orphan = sorted(
        code for code in module.RECOVERY_HINTS
        if code not in module.DECLARED_ERROR_CODES
    )
    assert not orphan, (
        f"{server}: RECOVERY_HINTS has entries that are not declared codes: "
        f"{orphan}. Either declare the code or remove the entry."
    )


def test_hint_shape_and_quality(registry):
    server, module = registry
    for code in sorted(module.DECLARED_ERROR_CODES):
        rec = module.recovery_for(code)
        assert isinstance(rec, dict), f"{server}.{code}: recovery must be a dict"
        assert set(rec) == {"strategy", "hint"}, (
            f"{server}.{code}: recovery keys must be exactly "
            f"{{'strategy', 'hint'}}, got {sorted(rec)}"
        )
        assert rec["strategy"] in ALLOWED_STRATEGIES, (
            f"{server}.{code}: unknown strategy {rec['strategy']!r}; "
            f"allowed: {sorted(ALLOWED_STRATEGIES)}"
        )
        hint = rec["hint"]
        assert isinstance(hint, str) and hint.strip(), (
            f"{server}.{code}: hint must be a non-empty string"
        )
        assert len(hint) >= _MIN_HINT_LEN, (
            f"{server}.{code}: hint too short to be actionable: {hint!r}"
        )
        assert "{" not in hint and "}" not in hint, (
            f"{server}.{code}: hint must be a static template-free string, "
            f"got {hint!r}"
        )


# ── Envelope contract ────────────────────────────────────────────────


def _opp_envelope(message: str) -> dict:
    module = importlib.import_module("opp.mcp._errors")
    return module._format_error_response(
        module.McpError("OPP_FILE_NOT_FOUND", message)
    )


def _ol_envelope(message: str) -> dict:
    module = importlib.import_module("ol_mcp._errors")

    @module.mcp_error_boundary
    def _boom() -> dict:
        raise ValueError(message)

    return json.loads(_boom())


def _orf_envelope(message: str) -> dict:
    module = importlib.import_module("orf.mcp._errors")
    return module.error_response("PATH_NOT_ALLOWED", message)


def _omni_envelope(message: str) -> dict:
    module = importlib.import_module("omni_mcp._errors")
    return module.error_response("OMNI_INVALID_INPUT", message)


_ENVELOPE_BUILDERS: dict[str, Callable[[str], dict]] = {
    "opp": _opp_envelope,
    "ol": _ol_envelope,
    "orf": _orf_envelope,
    "omni": _omni_envelope,
}


@pytest.mark.parametrize("server", sorted(_ENVELOPE_BUILDERS))
def test_error_envelope_carries_recovery(server):
    resp = _ENVELOPE_BUILDERS[server]("boom")

    assert resp.get("success") is False, f"{server}: expected an error envelope"
    assert "error" in resp and resp["error"].get("code"), (
        f"{server}: error envelope lost its error.code"
    )

    rec = resp.get("recovery")
    assert isinstance(rec, dict), (
        f"{server}: error envelope is missing top-level 'recovery'. "
        f"Top-level keys: {sorted(resp)}"
    )
    assert rec.get("strategy") in ALLOWED_STRATEGIES, (
        f"{server}: recovery.strategy invalid: {rec.get('strategy')!r}"
    )
    assert str(rec.get("hint", "")).strip(), (
        f"{server}: recovery.hint must be non-empty"
    )


@pytest.mark.parametrize("server", sorted(_ENVELOPE_BUILDERS))
def test_envelope_recovery_matches_registry(server):
    resp = _ENVELOPE_BUILDERS[server]("boom")
    code = resp["error"]["code"]
    module = _load_registry(server)
    assert resp["recovery"] == module.recovery_for(code), (
        f"{server}: envelope recovery must equal recovery_for({code!r})"
    )


@pytest.mark.parametrize("server", sorted(_ENVELOPE_BUILDERS))
def test_hint_is_static_not_interpolated(server):
    """Hints are constants — an injected message must never reach the hint."""
    resp_one = _ENVELOPE_BUILDERS[server](_CANARY)
    hint_one = resp_one["recovery"]["hint"]
    assert _CANARY not in hint_one, (
        f"{server}: recovery hint leaked the exception message "
        "(prompt-injection risk)"
    )

    resp_two = _ENVELOPE_BUILDERS[server](_CANARY + "_different")
    assert resp_two["recovery"]["hint"] == hint_one, (
        f"{server}: recovery hint changed with the exception message — "
        "it must be a static constant"
    )
