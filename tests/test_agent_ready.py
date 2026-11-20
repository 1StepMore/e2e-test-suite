"""Tests for the agent-ready/v1 machine contract (suite#379).

The five spec cases: all-green / ladder step-1 hit / ladder step-2 hit /
ladder step-3 blocked / exit-code correctness — plus a config-driven probe
test proving no vendor is hardcoded.  Environment and probes are injected;
no test touches real env vars, disk state, or the network.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "agent"))

from agent_ready import (  # noqa: E402
    SCHEMA,
    _config_provider_env_names,
    build_report,
)


def _ok_interpreter(_cand: str) -> tuple[int, str]:
    return (0, "")


def _blocked_interpreter(_cand: str) -> tuple[int, str]:
    return (1, "ModuleNotFoundError")


def _ok_deps(_interpreter) -> tuple[list[str], list[str]]:
    return [], ["pandoc", "weasyprint", "nbformat"]


def _missing_deps(_interpreter) -> tuple[list[str], list[str]]:
    return ["pandoc"], ["weasyprint", "nbformat"]


def _harness_env() -> dict:
    return {
        "OMNI_AGENT_LLM_BASE_URL": "http://harness:1/v1",
        "OMNI_AGENT_LLM_API_KEY": "x",
        "OMNI_AGENT_LLM_MODEL": "m",
    }


def _openai_env() -> dict:
    return {"OPENAI_BASE_URL": "http://local:2/v1", "OPENAI_API_KEY": "x", "OPENAI_MODEL": "m"}


def _report(env, interp=_ok_interpreter, deps=_ok_deps):
    report, code = build_report(env=env, interpreter_probe=interp, deps_probe=deps)
    return report, code


# ── spec case 1: 全绿 ────────────────────────────────────────────────────────
def test_all_green_exit_0():
    report, code = _report(_harness_env())
    assert code == 0
    assert report["schema"] == SCHEMA == "agent-ready/v1"
    assert report["ok"] is True
    assert report["status"] == "ok"
    assert report["next_action"] == "none"
    assert all(c["status"] == "ok" for c in report["checks"])
    assert {c["id"] for c in report["checks"]} == {"llm", "venv", "deps"}


# ── spec case 2: 阶梯①命中（harness 注入） ──────────────────────────────────
def test_ladder_step1_harness_hit():
    report, code = _report(_harness_env())
    llm = next(c for c in report["checks"] if c["id"] == "llm")
    assert code == 0 and llm["status"] == "ok"
    assert llm["ladder"][0] == {"step": 1, "probe": "harness-default", "result": "ok"}
    assert llm["ladder"][-1] == {"step": 3, "probe": "ask-human", "result": "not-needed"}


# ── spec case 3: 阶梯②命中（本机 OpenAI 兼容端点） ───────────────────────────
def test_ladder_step2_openai_hit():
    report, code = _report(_openai_env())
    llm = next(c for c in report["checks"] if c["id"] == "llm")
    assert code == 0 and llm["status"] == "ok"
    by_probe = {e["probe"]: e["result"] for e in llm["ladder"]}
    assert by_probe["harness-default"] == "absent"
    assert by_probe["env:OPENAI_COMPATIBLE"] == "ok"
    assert "step 2" in llm["detail"]


# ── spec case 4: 阶梯③ blocked（ask-human） ─────────────────────────────────
def test_ladder_step3_blocked_ask_human():
    report, code = _report({})
    llm = next(c for c in report["checks"] if c["id"] == "llm")
    assert llm["status"] == "blocked"
    assert llm["code"] == "blocked:no-llm-key"
    assert llm["ladder"][-1] == {"step": 3, "probe": "ask-human", "result": "required"}
    assert "base_url + key + model" in llm["remedy"]
    assert code == 2  # only blocker is no-llm-key
    assert report["next_action"] == "provide base_url + key + model"


# ── spec case 5: 退出码矩阵 ──────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("env", "interp", "deps", "expected"),
    [
        (_harness_env(), _ok_interpreter, _missing_deps, 3),   # only blocker: missing-dep
        (_harness_env(), _blocked_interpreter, _ok_deps, 4),   # no-venv
        (_harness_env(), _blocked_interpreter, _missing_deps, 4),  # mixed
        ({}, _blocked_interpreter, _ok_deps, 4),               # no-llm + no-venv → mixed
        ({}, _ok_interpreter, _missing_deps, 4),               # no-llm + missing-dep → mixed
    ],
)
def test_exit_code_matrix(env, interp, deps, expected):
    _, code = _report(env, interp=interp, deps=deps)
    assert code == expected, f"expected {expected}, got {code}"


# ── config-driven: vendor names come from configs, never from this code ─────
def test_suite_config_probe_is_config_driven():
    names = _config_provider_env_names()
    assert names, "module configs must declare provider credentials"
    assert all(n == n.upper() and "_" in n or n.isupper() for n in names)
    # presence-only: an env carrying one declared name flips the probe
    env = {names[0]: "present"}  # value is never read or echoed
    report, code = build_report(env=env, interpreter_probe=_ok_interpreter, deps_probe=_ok_deps)
    llm = next(c for c in report["checks"] if c["id"] == "llm")
    by_probe = {e["probe"]: e["result"] for e in llm["ladder"]}
    assert by_probe["suite-config"] == "ok"
    assert code == 0
