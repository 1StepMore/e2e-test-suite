"""Regression guard for e2e#56 — Tier-2 inter-test pollution, in-process.

The suite e2e job runs all of ``tests/`` in ONE pytest process. Two pieces of
process-global state made families pass alone but fail combined:

1. MCP token-bucket rate-limit singletons (omni_suite / opp.mcp / ol_mcp /
   orf.mcp rate limiters) are lazily created once per process and never
   reset, so MCP-heavy groups drain the bucket and later groups get
   ``RATE_LIMITED`` instead of the verdict they assert on.
2. Bare ``os.environ`` writes (e.g. the contract doc test's
   ``MCP_ALLOWED_DIRECTORIES=/tmp`` setdefault) outlive their test and
   silently override the lower-precedence allowlist vars later groups
   monkeypatch.

``tests/conftest.py`` ships the autouse ``_isolate_process_state`` fixture
that restores (2) and resets (1) around every test, plus fail-closed-safe
allowlist baselines. This module pins those behaviors in-process, without
spawning subprocesses, via a two-phase leak/verify pair and sys.modules
fakes for the heavy limiter modules.
"""
from __future__ import annotations

import os
import sys
import types


from tests.conftest import _RATE_LIMITER_MODULES, _reset_mcp_process_state

# Baselines conftest.py must establish: every module-specific allowlist set
# (the MCP servers are fail-CLOSED), the unified name left UNSET so tests
# asserting the fail-CLOSED contract can delete the per-module names and
# observe an empty allowlist.
_BASELINE_ALLOWLIST_VARS = (
    "OPP_MCP_ALLOWED_DIRS",
    "OL_MCP_ALLOWED_DIRS",
    "ORF_MCP_ALLOWED_DIRS",
)

_leak_probe: dict[str, str | None] = {}


def test_conftest_allowlist_baselines_are_set_and_unified_name_free():
    """e2e#56: OL/OPP/ORF MCP tools are fail-CLOSED without an allowlist.

    These baselines replace the historical accident where a leaked
    ``MCP_ALLOWED_DIRECTORIES=/tmp`` was the only thing making OL/OPP path
    tools work in the combined run.
    """
    for var in _BASELINE_ALLOWLIST_VARS:
        assert os.environ.get(var), (
            f"{var} baseline missing: conftest.py must setdefault it "
            "(fail-CLOSED MCP servers otherwise refuse to serve)"
        )
    assert not os.environ.get("MCP_ALLOWED_DIRECTORIES"), (
        "MCP_ALLOWED_DIRECTORIES must stay unset at baseline: fail-closed "
        "allowlist tests delete the per-module names and expect an empty "
        "allowlist, and the unified name outranks them all"
    )


def test_env_isolation_stage1_bare_write_leaks():
    """Write an env var the way the contract doc test used to (no monkeypatch).

    The autouse ``_isolate_process_state`` fixture must revert this after the
    test; stage2 verifies it. Record the pre-leak value so stage2 works
    regardless of what the outer environment exports.
    """
    _leak_probe["baseline"] = os.environ.get("MCP_ALLOWED_DIRECTORIES")
    os.environ.setdefault("MCP_ALLOWED_DIRECTORIES", "/tmp")
    assert os.environ["MCP_ALLOWED_DIRECTORIES"] == "/tmp"


def test_env_isolation_stage2_baseline_restored():
    """The bare stage1 write must not have survived into this later test."""
    assert "baseline" in _leak_probe, "stage1 must run before stage2"
    current = os.environ.get("MCP_ALLOWED_DIRECTORIES")
    assert current == _leak_probe["baseline"], (
        f"e2e#56 regression: a bare os.environ write in one test leaked into "
        f"a later test ({current!r} != baseline {_leak_probe['baseline']!r}); "
        "_isolate_process_state must restore os.environ around every test"
    )


def test_rate_limiter_reset_sweeps_all_registered_modules(monkeypatch):
    """_reset_mcp_process_state must clear every limiter module it knows.

    Fakes stand in for the real modules so this stays fast (importing the
    real OL stack costs minutes). OPP holds a per-tool dict; the others a
    single optional bucket.
    """
    fakes: dict[str, types.ModuleType] = {}
    for mod_name in _RATE_LIMITER_MODULES:
        fake = types.ModuleType(mod_name)
        if mod_name == "opp.mcp.rate_limiter":
            fake._buckets = {"__default__": object(), "extract_document": object()}
        else:
            fake._bucket = object()
        fakes[mod_name] = fake
        monkeypatch.setitem(sys.modules, mod_name, fake)

    _reset_mcp_process_state()

    for mod_name, fake in fakes.items():
        if hasattr(fake, "_buckets"):
            assert fake._buckets == {}, mod_name
        else:
            assert fake._bucket is None, mod_name


def test_rate_limiter_reset_skips_unimported_modules(monkeypatch):
    """The reset sweeps sys.modules only — it must never import the heavy
    OL/OPP/ORF stacks itself (that would slow every test's teardown)."""
    for mod_name in _RATE_LIMITER_MODULES:
        if mod_name in sys.modules:
            monkeypatch.delitem(sys.modules, mod_name)
    _reset_mcp_process_state()
    for mod_name in _RATE_LIMITER_MODULES:
        assert mod_name not in sys.modules


def test_rate_limiter_reset_hits_real_modules_when_loaded():
    """When the real limiter modules are loaded (any MCP-touching session),
    the reset must clear their actual state — an attribute rename upstream
    would otherwise silently disable the sweep. Conditional on import state:
    vacuous (no skip) when a group run never imported them.
    """
    for mod_name in _RATE_LIMITER_MODULES:
        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        if mod_name == "opp.mcp.rate_limiter":
            from opp.mcp.rate_limiter import TokenBucket
            mod._buckets["__guard_probe__"] = TokenBucket(rpm=1, burst=1)
            assert mod.check_rate_limit("__guard_probe__")[0] is True
            assert mod.check_rate_limit("__guard_probe__")[0] is False
            _reset_mcp_process_state()
            assert mod._buckets == {}
        elif hasattr(mod, "TokenBucket"):
            mod._bucket = mod.TokenBucket(rpm=1, burst=1)
            assert mod.check_rate_limit()[0] is True
            assert mod.check_rate_limit()[0] is False
            _reset_mcp_process_state()
            assert mod._bucket is None
            ok, _ = mod.check_rate_limit()
            assert ok is True
