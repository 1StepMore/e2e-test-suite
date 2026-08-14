"""dispatch.py — phase 2 of the validation engine: the adapter strategy
(guide §3.1 phase 2, §3.2 surface adapters).

One step -> one REAL call on a surface, never a mock (guide §4.1):

- ``kind: cli``    -> subprocess against the real module CLIs (``opp``,
                      ``ol``, ``orf``, ``omni-mcp`` console scripts in
                      ``.venv_ol/bin/``), capturing stdout / stderr / exit
                      code
- ``kind: mcp``    -> in-process call of the REAL module tool functions
                      (``opp.mcp.server.*``, ``ol_mcp.tools.*``,
                      ``orf.mcp.server.*`` — the same functions the MCP
                      servers expose; AGENTS.md in-process pattern, D13),
                      so a scenario's ``tool`` maps 1:1 to the live surface
- ``kind: python`` -> subprocess python snippet in the suite venv

Every :class:`StepResult` carries the five-part evidence contract
(guide §1 template, D12): ``surface`` / ``real_call`` / ``expect`` /
``actual`` / ``artifact_to_show``, plus the ``standard`` citation and the
wall-clock ``duration_seconds``.

Strict no-mocks hygiene (D4): the subprocess env is inherited from the
parent with nothing added — ``OMNI_TEST_FAKE_LLM`` is NEVER injected, and
path allowlists (``OPP_ALLOWED_DIRECTORIES`` / ``MCP_ALLOWED_DIRECTORIES``)
are only honored when the caller supplies them via the ``env`` parameter
(a scenario declares such needs itself; dispatch adds nothing on its own).

Only Python 3.13 stdlib — no new dependencies (guide §3.6).
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import json
import os
import shlex
import subprocess
import sys
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

#: Suite root: this module lives at <root>/omni_mcp/validation/dispatch.py.
SUITE_ROOT = Path(__file__).resolve().parent.parent.parent

#: The suite venv console-script dir (opp, ol, orf, omni-mcp live here).
VENV_BIN = SUITE_ROOT / ".venv_ol" / "bin"

#: Component src dirs, added to sys.path before importing module tool
#: functions in-process (mirrors tests/conftest.py ``setup_component_paths``
#: — the sub-repos keep their packages under ``src/``).
_COMPONENT_SRC_DIRS = (
    SUITE_ROOT / "Omni_Pre_Processor" / "src",
    SUITE_ROOT / "Omni_Localizer" / "src",
    SUITE_ROOT / "Omni_Re_Formatter" / "src",
)

#: Default per-step wall-clock cap when the step omits ``timeout_seconds``
#: (guide §2.4: "project default ceiling").
DEFAULT_TIMEOUT_SECONDS = 120.0


class DispatchError(ValueError):
    """A step named a surface the dispatcher cannot reach (guide §3.2:
    "A step that names an undeclared surface fails with a clear reason
    instead of fabricating a result").

    The message always names the offending tool / kind / command — the
    ``#error-clarity`` standard (STANDARDS.md).
    """


def suite_python() -> str:
    """Absolute path of the suite venv interpreter used for python-kind
    snippets and console-script resolution."""
    return str(VENV_BIN / "python")


def build_cli_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """The env passed to dispatched subprocesses.

    Inherits the parent env *as-is* and adds nothing except the suite venv
    bin dir on ``PATH`` so bare console names (``opp``, ``ol``, ``orf``,
    ``omni-mcp``) resolve to the real scripts.  NEVER injects
    ``OMNI_TEST_FAKE_LLM`` or path allowlists (D4); what the parent set is
    the parent's decision — the dispatcher only guarantees it never adds
    them itself.  If the caller supplies an explicit *env*, it is copied
    and treated identically.
    """
    out = dict(os.environ if env is None else env)
    if VENV_BIN.is_dir():
        path = out.get("PATH", "")
        out["PATH"] = f"{VENV_BIN}{os.pathsep}{path}" if path else str(VENV_BIN)
    return out


@contextlib.contextmanager
def _patched_environ(env: dict[str, str] | None) -> Iterator[None]:
    """Temporarily apply *env* to ``os.environ`` for the duration of an
    in-process mcp call, restoring the previous values afterwards.

    In-process module tool functions read ``os.environ`` directly (ORF's
    MCP tools are fail-CLOSED on ``MCP_ALLOWED_DIRECTORIES``), so a caller
    that declares such needs passes them through ``env`` — this is how the
    mcp adapter honors them without persisting anything.
    """
    if not env:
        yield
        return
    saved: dict[str, str | None] = {}
    for key, value in env.items():
        saved[key] = os.environ.get(key)
        os.environ[key] = value
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


# ---------------------------------------------------------------------------
# Result envelope
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class StepResult:
    """What every adapter hands back: the five-part evidence contract
    (guide §1) plus the D12 ``standard`` citation and wall-clock duration.

    Fields are the contract for the grader (todo 7) and the engine
    (todo 8) — keep them stable.
    """

    #: Which surface was called: ``cli: <command>`` / ``mcp: <tool>`` /
    #: ``python: <snippet>``.
    surface: str
    #: The literal invocation (exact command line, or ``tool(args)``).
    real_call: str
    #: Echo of the step's ``expect`` block (the asserted half).
    expect: dict[str, Any]
    #: What the live response really contained: ``success`` plus
    #: surface-shaped keys (exit_code/stdout/stderr for cli+python,
    #: data for mcp, timeout/error on failure).
    actual: dict[str, Any]
    #: Path of the first declared ``collect_artifacts`` entry, else None
    #: (the artifact-to-show half of the evidence contract).
    artifact_to_show: str | None
    #: The D12 ``standard`` citation (e.g. ``STANDARDS.md#exit-codes``),
    #: echoed from the step; None when the step cites none.
    standard: str | None
    #: Wall-clock duration of the real call in seconds.
    duration_seconds: float

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable form for the run record (phase 6 persist)."""
        return dataclasses.asdict(self)


def _make_result(
    step: dict[str, Any],
    surface: str,
    real_call: str,
    actual: dict[str, Any],
    duration_seconds: float,
) -> StepResult:
    artifacts = step.get("collect_artifacts") or []
    artifact = None
    if artifacts and isinstance(artifacts[0], dict):
        artifact = artifacts[0].get("path")
    return StepResult(
        surface=surface,
        real_call=real_call,
        expect=dict(step.get("expect") or {}),
        actual=actual,
        artifact_to_show=artifact,
        standard=step.get("standard"),
        duration_seconds=round(duration_seconds, 3),
    )


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------


def _run_cli_step(step: dict[str, Any], env: dict[str, str] | None) -> StepResult:
    """SubprocessAdapter: run the exact command line, capture everything."""
    command = step["command"]
    timeout = float(step.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)
    proc_env = build_cli_env(env)
    start = time.monotonic()
    try:
        proc = subprocess.run(
            shlex.split(command),
            capture_output=True,
            text=True,
            env=proc_env,
            timeout=timeout,
        )
        actual: dict[str, Any] = {
            "success": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
        }
    except subprocess.TimeoutExpired as exc:
        actual = {
            "success": False,
            "timeout": True,
            "error": f"timed out after {timeout}s",
            "exit_code": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }
    except FileNotFoundError:
        actual = {
            "success": False,
            "error": f"command not found: {command!r}",
        }
    return _make_result(
        step, f"cli: {command}", command, actual, time.monotonic() - start
    )


def _run_python_step(step: dict[str, Any], env: dict[str, str] | None) -> StepResult:
    """Run the python snippet as a subprocess in the suite venv."""
    snippet = step["command"]
    timeout = float(step.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)
    proc_env = build_cli_env(env)
    interpreter = suite_python()
    start = time.monotonic()
    try:
        proc = subprocess.run(
            [interpreter, "-c", snippet],
            capture_output=True,
            text=True,
            env=proc_env,
            timeout=timeout,
        )
        actual: dict[str, Any] = {
            "success": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "python": interpreter,
        }
    except subprocess.TimeoutExpired as exc:
        actual = {
            "success": False,
            "timeout": True,
            "error": f"timed out after {timeout}s",
            "exit_code": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "python": interpreter,
        }
    return _make_result(
        step, f"python: {snippet}", f"python -c {snippet}", actual,
        time.monotonic() - start,
    )


def _ensure_component_src_paths() -> None:
    """Idempotently add the three component ``src/`` dirs to ``sys.path``
    so in-process module imports resolve to the REAL sub-repo sources
    (mirrors tests/conftest.py ``setup_component_paths``)."""
    for src_dir in _COMPONENT_SRC_DIRS:
        if src_dir.is_dir() and str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))


def _resolve_tool(tool: str) -> Any:
    """Resolve ``<module>.<function>`` (e.g. ``ol_mcp.tools.ping``) to the
    live callable.

    Raises
    ------
    DispatchError
        Naming the full tool reference when the module cannot be imported
        or the function does not exist (feeds ``#error-clarity``).
    """
    module_name, _, func_name = tool.rpartition(".")
    if not module_name or not func_name:
        raise DispatchError(
            f"invalid mcp tool reference {tool!r} — expected '<module>.<function>'"
        )
    _ensure_component_src_paths()
    try:
        module = __import__(module_name, fromlist=[func_name])
    except Exception as exc:  # ImportError and friends
        raise DispatchError(
            f"cannot import module for tool {tool!r}: {exc}"
        ) from exc
    fn = getattr(module, func_name, None)
    if fn is None:
        raise DispatchError(
            f"mcp tool {tool!r} not found — module {module_name!r} has no "
            f"function {func_name!r}"
        )
    return fn


def _call_tool(fn: Any, arguments: dict[str, Any], timeout: float) -> Any:
    """Invoke the tool function, awaiting async functions.

    Async tool functions (OPP/OL) are awaited via ``asyncio.wait_for`` so
    the per-step timeout applies; sync tool functions (ORF) run in a worker
    thread with the same timeout honored.
    """
    if asyncio.iscoroutinefunction(fn):
        return asyncio.run(asyncio.wait_for(fn(**arguments), timeout=timeout))
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn, **arguments)
        return future.result(timeout=timeout)


def _normalize_tool_output(raw: Any) -> dict[str, Any]:
    """Shape the raw tool return into the ``actual`` block.

    dict  -> ``{"success": raw.get("success", True), "data": raw}``
    str   -> JSON-parsed when possible (module tools return JSON strings),
             else wrapped as-is
    other -> wrapped as ``{"success": True, "data": raw}``
    """
    if isinstance(raw, dict):
        return {"success": raw.get("success", True), "data": raw}
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return {"success": True, "data": raw}
        if isinstance(parsed, dict):
            return {"success": parsed.get("success", True), "data": parsed}
        return {"success": True, "data": parsed}
    return {"success": True, "data": raw}


def _run_mcp_step(step: dict[str, Any], env: dict[str, str] | None) -> StepResult:
    """ToolAdapter: in-process call of the REAL module tool function."""
    tool = step["tool"]
    arguments = dict(step.get("arguments") or {})
    timeout = float(step.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)
    fn = _resolve_tool(tool)
    start = time.monotonic()
    try:
        with _patched_environ(env):
            raw = _call_tool(fn, arguments, timeout)
        actual = _normalize_tool_output(raw)
    except TimeoutError:
        actual = {"success": False, "timeout": True, "error": f"timed out after {timeout}s"}
    except Exception as exc:
        actual = {"success": False, "error": str(exc)}
    real_call = f"{tool}({json.dumps(arguments, sort_keys=True)})" if arguments else f"{tool}()"
    return _make_result(
        step, f"mcp: {tool}", real_call, actual, time.monotonic() - start
    )


# ---------------------------------------------------------------------------
# Dispatch table (strategy pattern, guide §3.2)
# ---------------------------------------------------------------------------


def dispatch_step(
    step: dict[str, Any], env: dict[str, str] | None = None
) -> StepResult:
    """Turn one step into one real call on the surface it names.

    The step dict is the loader-validated shape (loader.py): ``kind``
    selects the adapter, ``tool``/``arguments`` or ``command`` carry the
    call spec, ``expect``/``timeout_seconds``/``collect_artifacts``/
    ``standard`` shape the evidence record.

    Parameters
    ----------
    step
        A validated step dict (see loader.py ``KINDS``).
    env
        Optional explicit environment for the dispatched call.  When None,
        the parent env is inherited.  Injected values (FAKE_LLM, path
        allowlists) are NEVER added by the dispatcher itself (D4); the
        caller may pass them only when the scenario declares the need.

    Raises
    ------
    DispatchError
        For an undeclared kind or an unresolvable mcp tool, naming the
        offending surface (guide §3.2, ``#error-clarity``).
    """
    kind = step.get("kind")
    if kind == "cli":
        return _run_cli_step(step, env)
    if kind == "python":
        return _run_python_step(step, env)
    if kind == "mcp":
        return _run_mcp_step(step, env)
    raise DispatchError(
        f"no adapter for step kind {kind!r} — known kinds: mcp, cli, python"
    )
