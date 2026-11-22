#!/usr/bin/env python3
"""agent-ready/v1 — the one machine contract for "can an agent start work here".

Unifies the scattered readiness/deps checks (check_readiness.py, check_deps.sh,
autonomy.py selfcheck) behind ONE JSON contract + ONE exit-code set, so an
agent never has to parse prose to learn whether it can start (suite#379):

    python scripts/check_readiness.py --agent-ready
    # or directly: python scripts/agent/agent_ready.py

Schema (see tests/test_agent_ready.py for the machine-checked shape)::

    {
      "schema": "agent-ready/v1",
      "ok": false,
      "status": "ok" | "blocked",
      "checks": [
        {"id": "llm", "status": "ok"|"blocked", "code": "ok"|"blocked:no-llm-key",
         "detail": str, "ladder": [{"step", "probe", "result"}], "remedy": str},
        {"id": "venv", "status": ..., "code": "ok"|"blocked:no-venv", ...},
        {"id": "deps", "status": ..., "code": "ok"|"blocked:missing-dep", ...}
      ],
      "next_action": str
    }

Exit codes (the machine-judgeable part; no log scraping):
    0  all green
    2  only blocker is ``blocked:no-llm-key``
    3  only blocker is ``blocked:missing-dep``
    4  any other blocked (``blocked:no-venv``) or a mix of blockers

Model ladder (implemented here, NOT prose — suite#379):
    1. harness-injected default model: OMNI_AGENT_LLM_{BASE_URL,API_KEY,MODEL}
       — the seam a harness uses to hand its own model to a repo subprocess.
    2. machine-local OpenAI-compatible endpoint/credentials: OPENAI_{BASE_URL,
       API_KEY,MODEL}; plus every ``${VAR}`` provider credential declared by
       the module configs (config-driven — vendor names live in the configs,
       never here; presence-only probe, values never read or echoed).
    3. neither → ``blocked:no-llm-key`` + remedy; what the human provides
       (free tier or paid) is their decision, never a code default.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

SCHEMA = "agent-ready/v1"
SUITE_ROOT = Path(__file__).resolve().parents[2]

HARNESS_LLM_ENV = ("OMNI_AGENT_LLM_BASE_URL", "OMNI_AGENT_LLM_API_KEY", "OMNI_AGENT_LLM_MODEL")
OPENAI_COMPAT_ENV = ("OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL")

# Suite modules whose importability defines a usable interpreter
# (same probe set as scripts/nightly_gap.py REQUIRED_MODULES).
SUITE_MODULES = ("opp.cli", "orf", "ol_pool")

# External deps the matrix's SKIP rules probe (see NIGHTLY.md dependency table).
PY_DEPS = ("weasyprint", "nbformat")

_PROVIDER_ENV_RE = re.compile(r"api_key:\s*\$\{([A-Z][A-Z0-9_]*)\}")


# ---------------------------------------------------------------------------
# Ladder probes (step 1 / step 2).  Presence-only: never read or echo values.
# ---------------------------------------------------------------------------
def probe_harness_llm(env: dict) -> dict:
    """Step 1 — harness-injected default model seam."""
    hit = all(env.get(n) for n in HARNESS_LLM_ENV)
    return {"step": 1, "probe": "harness-default", "result": "ok" if hit else "absent"}


def _config_provider_env_names() -> list[str]:
    """Env var names declared by module configs' ``api_key: ${VAR}`` entries.

    Config-driven by design: the vendor names live in the configs (which the
    suite already ships), this code only learns the *names* — so no vendor is
    hardcoded here and a config change flows through automatically.
    """
    names: list[str] = []
    for cfg in sorted(SUITE_ROOT.glob("Omni_*/config/*.yaml")):
        try:
            text = cfg.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in _PROVIDER_ENV_RE.finditer(text):
            name = m.group(1)
            if name not in names:
                names.append(name)
    return names


def probe_openai_compatible(env: dict) -> dict:
    """Step 2a — machine-local OpenAI-compatible endpoint/credentials."""
    hit = all(env.get(n) for n in OPENAI_COMPAT_ENV)
    return {"step": 2, "probe": "env:OPENAI_COMPATIBLE", "result": "ok" if hit else "absent"}


def probe_suite_config(env: dict) -> dict:
    """Step 2b — credentials declared by the module configs (presence-only)."""
    names = _config_provider_env_names()
    if not names:
        return {"step": 2, "probe": "suite-config", "result": "unknown"}
    hit = [n for n in names if env.get(n)]
    result = "ok" if hit else "absent"
    return {"step": 2, "probe": "suite-config", "result": result,
            "detail": f"present: {sorted(hit)}" if hit else f"declared: {names}"}


def llm_check(env: dict) -> dict:
    """Run the ladder in order; first hit wins, ask-human is the last resort."""
    ladder = [probe_harness_llm(env), probe_openai_compatible(env), probe_suite_config(env)]
    hit = next((e for e in ladder if e["result"] == "ok"), None)
    if hit is not None:
        ladder.append({"step": 3, "probe": "ask-human", "result": "not-needed"})
        return {"id": "llm", "status": "ok", "code": "ok",
                "detail": f"model access via ladder step {hit['step']} ({hit['probe']})",
                "ladder": ladder, "remedy": ""}
    ladder.append({"step": 3, "probe": "ask-human", "result": "required"})
    return {"id": "llm", "status": "blocked", "code": "blocked:no-llm-key",
            "detail": "no usable model on any ladder step",
            "ladder": ladder,
            "remedy": "provide base_url + key + model via the harness seam "
                      f"({HARNESS_LLM_ENV[0]}/{HARNESS_LLM_ENV[1]}/{HARNESS_LLM_ENV[2]}) "
                      "or OpenAI-compatible env, or ask the human at the screen"}


# ---------------------------------------------------------------------------
# Interpreter (venv) check — same import oracle as nightly_gap.py's preflight.
# ---------------------------------------------------------------------------
def _default_interpreter_candidates() -> list[str]:
    cands: list[str] = []
    venv_ol = SUITE_ROOT / ".venv_ol" / "bin" / "python"
    venv_win = SUITE_ROOT / ".venv_win" / "Scripts" / "python.exe"
    if os.name == "nt":
        cands += [str(venv_win), str(venv_ol)]
    else:
        cands += [str(venv_ol)]
    cands.append(sys.executable)
    return cands


def interpreter_check(run_probe: Callable[[str], tuple[int, str]] | None = None) -> dict:
    """A usable interpreter = imports the three suite modules (fail-closed:
    an interpreter missing them turns every matrix cell into a fake red,
    nightly_gap.py anti-cheating rule 2 — same oracle here)."""
    if run_probe is None:
        run_probe = _run_module_probe

    tried: list[dict] = []
    for cand in _default_interpreter_candidates():
        rc, out = run_probe(cand)
        tried.append({"interpreter": cand, "result": "ok" if rc == 0 else "absent"})
        if rc == 0:
            return {"id": "venv", "status": "ok", "code": "ok",
                    "detail": f"usable interpreter: {cand}",
                    "tried": tried, "remedy": ""}
    return {"id": "venv", "status": "blocked", "code": "blocked:no-venv",
            "detail": "no interpreter imports " + ", ".join(SUITE_MODULES),
            "tried": tried,
            "remedy": "create the suite venv: bash scripts/setup_dev.sh "
                      "(POSIX/WSL) or scripts/setup_dev.ps1 (Windows)"}


def _run_module_probe(interpreter: str) -> tuple[int, str]:
    """Run ``import`` probe for the suite modules under ``interpreter``."""
    code = "import importlib; import sys; " + "; ".join(
        f"importlib.import_module({m!r})" for m in SUITE_MODULES)
    try:
        r = subprocess.run(  # noqa: S603
            [interpreter, "-c", code], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, repr(exc)
    return r.returncode, (r.stderr or "")[-200:]


# ---------------------------------------------------------------------------
# External deps check (the matrix's environment-class skip sources).
# ---------------------------------------------------------------------------
def _default_deps_probe(interpreter: str | None = None) -> tuple[list[str], list[str]]:
    """Return (missing, present).  pandoc: PATH first, then the pypandoc
    wheel binary (AGENTS.md: pandoc auto-installs via pypandoc-binary)."""
    missing: list[str] = []
    present: list[str] = []

    if shutil.which("pandoc") or _pypandoc_pandoc(interpreter):
        present.append("pandoc")
    else:
        missing.append("pandoc")

    if interpreter:
        code = ("import importlib; import sys; "
                + "; ".join(f"importlib.import_module({m!r})" for m in PY_DEPS)
                + "; print('DEPS_OK')")
        try:
            r = subprocess.run(  # noqa: S603
                [interpreter, "-c", code], capture_output=True, text=True, timeout=120)
            if r.returncode == 0 and "DEPS_OK" in (r.stdout or ""):
                present += list(PY_DEPS)
            else:
                missing += list(PY_DEPS)
        except (OSError, subprocess.TimeoutExpired):
            missing += list(PY_DEPS)
    else:
        for mod in PY_DEPS:
            try:
                __import__(mod)
                present.append(mod)
            except ImportError:
                missing.append(mod)

    return missing, present


def _pypandoc_pandoc(interpreter: str | None) -> str:
    """pypandoc's bundled pandoc binary path, '' when unavailable.

    ``pypandoc.get_pandoc_path()`` reports the *extensionless* name even on
    Windows, where the wheel actually ships ``pandoc.exe``. Checking only the
    reported path is therefore always false there and made this probe report a
    missing pandoc on every native Windows host. Try the ``.exe`` sibling too;
    on POSIX the sibling is absent and behaviour is unchanged.
    """
    code = (
        "import os, pypandoc\n"
        "p = pypandoc.get_pandoc_path()\n"
        "cands = (p, p + '.exe') if p else ()\n"
        "hit = next((c for c in cands if os.path.isfile(c)), '')\n"
        "print(hit)\n"
    )
    try:
        if interpreter:
            r = subprocess.run(  # noqa: S603
                [interpreter, "-c", code], capture_output=True, text=True, timeout=120)
            return (r.stdout or "").strip() if r.returncode == 0 else ""
        import pypandoc
        p = pypandoc.get_pandoc_path()
        for cand in (p, p + ".exe") if p else ():
            if os.path.isfile(cand):
                return cand
        return ""
    except Exception:  # noqa: BLE001 — any pypandoc/OS failure means "no bundled pandoc"
        return ""


def deps_check(interpreter: str | None = None,
               probe: Callable[[str | None], tuple[list[str], list[str]]] | None = None) -> dict:
    """pandoc + weasyprint + nbformat — the matrix's env-class skip sources."""
    if probe is None:
        probe = _default_deps_probe
    missing, present = probe(interpreter)
    if missing:
        return {"id": "deps", "status": "blocked", "code": "blocked:missing-dep",
                "detail": f"missing: {missing}; present: {present}",
                "remedy": "install the missing deps "
                          "(pip install pypandoc-binary weasyprint nbformat)"}
    return {"id": "deps", "status": "ok", "code": "ok",
            "detail": f"present: {present}", "remedy": ""}


# ---------------------------------------------------------------------------
# Report assembly + exit codes.
# ---------------------------------------------------------------------------
def build_report(env: dict | None = None,
                 interpreter_probe: Callable[[str], tuple[int, str]] | None = None,
                 deps_probe: Callable[[str | None], tuple[list[str], list[str]]] | None = None,
                 ) -> tuple[dict, int]:
    """Build the agent-ready/v1 payload and its contract exit code.

    ``interpreter_probe`` / ``deps_probe`` are injectable so tests can stub
    the environment without faking files on disk.
    """
    env = os.environ if env is None else env

    checks: list[dict] = [llm_check(env)]

    venv = interpreter_check(run_probe=interpreter_probe)
    checks.append(venv)

    interpreter = None
    if venv["status"] == "ok":
        # detail shape: "usable interpreter: <path>" (contract-owned prefix)
        interpreter = venv["detail"].split("usable interpreter: ", 1)[1]
    checks.append(deps_check(interpreter=interpreter, probe=deps_probe))

    blocked = {c["id"]: c["code"] for c in checks if c["status"] == "blocked"}
    codes = set(blocked.values())

    if not blocked:
        exit_code = 0
        status = "ok"
        next_action = "none"
    elif codes == {"blocked:no-llm-key"}:
        exit_code = 2
        status = "blocked"
        next_action = "provide base_url + key + model"
    elif codes == {"blocked:missing-dep"}:
        exit_code = 3
        status = "blocked"
        next_action = "install missing deps (see checks[deps].remedy)"
    else:  # no-venv or any mixed combination
        exit_code = 4
        status = "blocked"
        next_action = "fix environment first (see blocked checks' remedy)"

    report = {
        "schema": SCHEMA,
        "ok": not blocked,
        "status": status,
        "checks": checks,
        "next_action": next_action,
    }
    return report, exit_code


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="agent_ready.py")
    ap.add_argument("--compact", action="store_true", help="one-line JSON")
    args = ap.parse_args(argv)

    report, code = build_report()
    print(json.dumps(report, indent=None if args.compact else 2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
