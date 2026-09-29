"""Regression lock: the active LLM env contract is the canonical pair.

OL ``config/default.yaml`` carries two provider keys, the only real-LLM
credentials the suite reads:

* ``AMD_API_KEY``   — priority 1 (``DeepSeek-V4.1-Flash``, AMD Radeon)
* ``ZHIPU_API_KEY`` — priority 2 (``glm-4.7-flash``)

``NVIDIA_NIM_API_KEY`` was the priority-3 provider (``minimaxai/minimax-m3``)
until NVIDIA returned HTTP 410 Gone (EOL 2026-09-09); it is gone upstream and
must not linger in any suite surface. ``ARK_API_KEY`` was demoted then removed
earlier for the same reason — the pool shrinks to the providers that actually
answer.

Two coupled *active* surfaces must agree with that pool, or the real-LLM
gates silently rot while every other test stays green:

1. ``omni_suite.cli._validate_env`` — the suite CLI's production env gate.
   It must accept every canonical key and must keep failing closed when no
   canonical key is present. A retired provider key (including the removed
   ``ARK_API_KEY`` and ``NVIDIA_NIM_API_KEY``) must NOT satisfy the gate.
2. The real-LLM CI workflows (``validation.yml`` nightly, ``e2e-tests.yml``,
   ``fidelity.yml``) must expose the same canonical keys and must not gate on
   retired providers (Agnes / OpenCode Go / MiniMax / Baidu / NVIDIA NIM /
   OpenAI).

The gate lesson matters as much as the key list: the suite's OL-driven
scenarios used to list the whole provider pool in ``requires_env`` (AND), so a
user holding only one provider account was gated out to ``unconfigured``. They
now declare their provider pair in ``requires_env_any`` (the engine's OR gate,
PR-A) — ONE key configures them, and a declared-but-unsatisfied OR group still
fails closed. This module locks the pool *and* the OR shape.

Behavior-first: the CLI cases drive the real gate function, the workflow cases
read the active workflow files, and the scenario case reads the real scenario
YAML.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

SUITE_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = SUITE_ROOT / ".github" / "workflows"
SCENARIOS = SUITE_ROOT / "scenarios"

# The canonical OL model-pool provider keys (single source of truth:
# Omni_Localizer/config/default.yaml).
CANONICAL_KEYS = ("AMD_API_KEY", "ZHIPU_API_KEY")

# Providers retired by the migration — a workflow or the CLI gate must not
# treat any of these as the active credential.
RETIRED_KEYS = (
    "ARK_API_KEY",
    "NVIDIA_NIM_API_KEY",
    "AGNES_API_KEY",
    "OPENCODE_GO_KEY",
    "OPENCODE_GO_BASE_URL",
    "MINIMAX_API_KEY",
    "MINIMAX_BASE_URL",
    "BAIDU_API_KEY",
    "BAIDU_BASE_URL",
    "BAIDU_SECRET_KEY",
    "OPENAI_API_KEY",
)

# Word-boundary token scan: avoids matching a retired name embedded inside a
# longer identifier (e.g. ``OMNI_OPENAI_API_KEY`` does not match
# ``OPENAI_API_KEY`` because ``_`` is a word character).
_ENV_TOKEN = re.compile(r"\b([A-Z][A-Z0-9_]{2,})\b")

REAL_LLM_WORKFLOWS = ("validation.yml", "e2e-tests.yml", "fidelity.yml")


def _clear_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every known provider key so the gate sees a clean slate.

    ``tests/conftest.py`` installs dummy provider keys at import time; wipe
    both canonical and retired names so each test controls the full set.
    """
    for key in (*CANONICAL_KEYS, *RETIRED_KEYS):
        monkeypatch.delenv(key, raising=False)


class TestSuiteCliKeyDetector:
    """``omni_suite.cli._validate_env`` — the production LLM env gate."""

    def test_detector_is_exactly_the_canonical_pair(self):
        from omni_suite import cli

        assert tuple(cli._LLM_API_KEYS) == CANONICAL_KEYS

    def test_detector_does_not_recognise_retired_providers(self):
        from omni_suite import cli

        overlap = set(RETIRED_KEYS) & set(cli._LLM_API_KEYS)
        assert not overlap, f"detector still recognises retired keys: {sorted(overlap)}"

    def test_full_canonical_pair_satisfies_the_real_llm_gate(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Setting exactly the canonical pair must open the gate.

        RED before the fix: the detector still expected the retired
        AGNES/OpenCode keys, so the canonical pair alone left keys
        "unset" and the gate exited 1.
        """
        from omni_suite import cli

        _clear_llm_env(monkeypatch)
        for key in CANONICAL_KEYS:
            monkeypatch.setenv(key, "sk-regression-test")

        cli._validate_env(require_llm=True)  # must not raise SystemExit

    def test_no_canonical_key_fails_closed(self, monkeypatch: pytest.MonkeyPatch):
        from omni_suite import cli

        _clear_llm_env(monkeypatch)
        with pytest.raises(SystemExit) as excinfo:
            cli._validate_env(require_llm=True)
        assert excinfo.value.code == 1

    def test_retired_provider_keys_alone_do_not_satisfy_the_gate(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Retired keys (Agnes / OpenCode Go) must not open the gate."""
        from omni_suite import cli

        _clear_llm_env(monkeypatch)
        monkeypatch.setenv("AGNES_API_KEY", "sk-stale")
        monkeypatch.setenv("OPENCODE_GO_KEY", "sk-stale")
        with pytest.raises(SystemExit) as excinfo:
            cli._validate_env(require_llm=True)
        assert excinfo.value.code == 1


class TestRealLlmWorkflowEnvContract:
    """Real-LLM CI workflows must gate on the canonical pair only."""

    @pytest.mark.parametrize("filename", REAL_LLM_WORKFLOWS)
    def test_workflow_exports_every_canonical_key(self, filename: str):
        text = (WORKFLOWS / filename).read_text(encoding="utf-8")
        present = set(_ENV_TOKEN.findall(text))
        missing = [key for key in CANONICAL_KEYS if key not in present]
        assert not missing, (
            f"{filename} does not expose canonical LLM env keys: {missing}"
        )

    @pytest.mark.parametrize("filename", REAL_LLM_WORKFLOWS)
    def test_workflow_does_not_gate_on_retired_providers(self, filename: str):
        text = (WORKFLOWS / filename).read_text(encoding="utf-8")
        present = set(_ENV_TOKEN.findall(text))
        stale = [key for key in RETIRED_KEYS if key in present]
        assert not stale, (
            f"{filename} still gates on retired LLM providers: {stale}"
        )


class TestScenarioEnvGateNotAllProviders:
    """No suite scenario may require the whole canonical provider pool.

    The validation engine computes ``missing_env`` (``engine.py:243``) and the
    Phase-4 gate reports ``unconfigured`` *before* any step is dispatched
    (``engine.py:220``). For ``requires_env`` that is AND-semantics: a scenario
    is unrunnable if *any* required var is absent. So a scenario listing every
    canonical provider key in ``requires_env`` gates out any user who does not
    hold every provider account at once — the exact failure that removed
    ``ARK_API_KEY`` (#94) and then had to remove ``AMD_API_KEY`` again after
    commit 10547af.

    Scope of this lock: it forbids the *whole pool* in the AND list. It does
    NOT forbid a disjunction. The 13 OL-driven scenarios declare their
    provider pair in ``requires_env_any`` instead — the engine's OR gate
    (PR-A): a user holding only ONE provider key is configured, and a declared
    but unsatisfied OR group still fails closed. Listing the whole pool in an
    OR group is therefore legitimate and not an offender here.
    """

    def test_no_scenario_requires_every_canonical_provider_key(self):
        offenders: dict[str, list[str]] = {}
        for path in sorted(SCENARIOS.rglob("*.yaml")):
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001 - report, never hide
                pytest.fail(f"{path}: unparseable scenario YAML: {exc!r}")
            requires_env = (data or {}).get("requires_env", []) or []
            if all(key in requires_env for key in CANONICAL_KEYS):
                offenders[str(path.relative_to(SUITE_ROOT))] = list(requires_env)
        assert not offenders, (
            "these scenarios require every canonical provider key, so a user "
            "holding only one provider is gated out to `unconfigured`: "
            f"{sorted(offenders.items())}"
        )
