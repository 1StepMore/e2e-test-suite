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
                      so a scenario's ``tool`` maps 1:1 to the live surface.
                      **This is the FAST IN-PROCESS PATH — it does NOT
                      exercise the MCP protocol (X-04 P0 gap), so it is NOT
                      "MCP coverage" by itself.**  Transport-level proof is
                      :func:`run_transport_parity` (below).
- ``kind: python`` -> subprocess python snippet in the suite venv

Every :class:`StepResult` carries the five-part evidence contract
(guide §1 template, D12): ``surface`` / ``real_call`` / ``expect`` /
``actual`` / ``artifact_to_show``, plus the ``standard`` citation and the
wall-clock ``duration_seconds``.

X-04 transport parity (P0): :func:`run_transport_parity` starts each
module's REAL MCP server over stdio (fastmcp :class:`Client` +
``StdioTransport`` against the shipped ``mcp``-library servers) and compares
every tool's protocol response against the in-process call of the same
function — divergence fails.  Coverage audits (``coverage_audit.py``) use
this path as their execution-backed evidence.

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
        for key, previous in saved.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous


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
    """Invoke the tool function with flat kwargs, awaiting async functions.

    Async tool functions (OPP/OL) are awaited via ``asyncio.wait_for`` so
    the per-step timeout applies; sync tool functions (ORF) run in a worker
    thread with the same timeout honored.
    """
    return _run_tool_call(fn, (), dict(arguments or {}), timeout)


def _run_tool_call(fn: Any, args: tuple, kwargs: dict[str, Any], timeout: float) -> Any:
    """Run ``fn(*args, **kwargs)``, awaiting coroutines, honoring *timeout*.

    ``asyncio.run`` can only be used from a thread WITHOUT a running event
    loop — callers inside the parity client's loop must hop via
    ``asyncio.to_thread`` (see :func:`check_tool_parity`).
    """
    if asyncio.iscoroutinefunction(fn):
        return asyncio.run(asyncio.wait_for(fn(*args, **kwargs), timeout=timeout))
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn, *args, **kwargs)
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
    """ToolAdapter: in-process call of the REAL module tool function.

    This is the FAST IN-PROCESS PATH (unit speed).  It calls the same
    functions the MCP servers expose, but does NOT exercise the MCP
    protocol (stdio/schema/auth) — per X-04 (P0) that gap is closed by
    :func:`run_transport_parity`, which the execution-backed coverage
    audit uses.  Do not cite this adapter as "MCP coverage".
    """
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


# ---------------------------------------------------------------------------
# X-04 transport parity (P0): the REAL MCP protocol vs the in-process call
# ---------------------------------------------------------------------------
#
# Every tool of every module is called twice: once in-process (the same
# function the servers expose) and once over the REAL MCP stdio protocol
# (fastmcp Client + StdioTransport against ``python -m <server>``).  The two
# responses must agree under a canonical comparison, else the tool is
# ``diverged`` and the parity suite FAILS — a deliberately broken tool makes
# the execution-backed coverage audit exit 1.
#
# Parity semantics (canonical comparison, ``_canonical_parity_equal``):
# - ``success`` must agree between in-process and protocol.
# - both success -> payloads compared structurally; volatile keys
#   (run_id/trace_id/durations/timestamps) are ignored so the SAME call
#   made twice still compares equal.
# - both error -> any observable error on each side counts as agreement
#   (the server's structured envelope differs from the in-process
#   ``str(exc)`` by design).
#
# Env hygiene: like the contract tests and F3, the parity path supplies the
# standard sandbox allowlist defaults (``/tmp``) when the parent did not set
# them — the servers are fail-CLOSED on those vars.  ``OMNI_TEST_FAKE_LLM``
# is NEVER injected (D4 no-mocks hygiene).

#: Dotted prefix of the live tool functions per module (for in-process calls).
_MODULE_TOOL_PREFIX: dict[str, str] = {
    "opp": "opp.mcp.server",
    "ol": "ol_mcp.tools",
    "orf": "orf.mcp.server",
    "omni_mcp": "omni_mcp.server",
}

#: stdio launch spec per module: ``python -m <server>`` from the suite root
#: (every module package is importable there — editable installs + cwd).
_MCP_SERVER_LAUNCH: dict[str, dict[str, Any]] = {
    "omni_mcp": {"args": ["-u", "-m", "omni_mcp"], "cwd": SUITE_ROOT},
    "opp": {"args": ["-u", "-m", "opp.mcp.server"], "cwd": SUITE_ROOT},
    "ol": {"args": ["-u", "-m", "ol_mcp"], "cwd": SUITE_ROOT},
    "orf": {"args": ["-u", "-m", "orf.mcp.server"], "cwd": SUITE_ROOT},
}

#: Sandbox allowlist defaults the parity path supplies when unset (mirrors
#: tests/conftest.py + F3's ``MCP_ALLOWED_DIRECTORIES=/tmp``).
_PARITY_ALLOWLIST_DEFAULTS: dict[str, str] = {
    "MCP_ALLOWED_DIRECTORIES": "/tmp",
    "OPP_MCP_ALLOWED_DIRS": "/tmp",
    "ORF_MCP_ALLOWED_DIRS": "/tmp",
    "OL_MCP_ALLOWED_DIRS": "/tmp",
}

#: Response fields that legitimately differ between two runs of the SAME
#: call (run ids, timestamps, wall-clock durations) — ignored when comparing
#: success payloads.
_VOLATILE_KEYS: frozenset[str] = frozenset({
    "run_id", "trace_id", "runs_dir", "run_dir", "timestamp",
    "duration_seconds", "generated_at", "started_at", "finished_at",
})


def parity_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """The env for parity servers + in-process parity calls.

    Inherits the parent (or explicit *env*) as-is and adds the sandbox
    allowlist defaults ONLY when unset.  Never injects ``OMNI_TEST_FAKE_LLM``
    or path values other than the standard ``/tmp`` sandbox.
    """
    out = dict(os.environ if env is None else env)
    for key, value in _PARITY_ALLOWLIST_DEFAULTS.items():
        out.setdefault(key, value)
    return out


def call_tool_in_process(
    module: str,
    tool: str,
    arguments: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Call the live tool function in-process (the parity reference half).

    Handles every module's call convention:
    - OL tools take a single Pydantic model (``TOOL_REGISTRY`` entry) —
      the flat *arguments* dict is validated into the model; the
      no-model tools (ping/get_capabilities) take flat kwargs.
    - OPP/ORF/omni_mcp tools take flat kwargs.

    Returns the dispatch-shaped ``actual`` dict (``{"success", "data"}`` or
    ``{"success": False, "error": ...}``) — never raises.
    """
    _ensure_component_src_paths()
    arguments = dict(arguments or {})
    try:
        with _patched_environ(parity_env(env)):
            if module == "ol":
                from ol_mcp.tools import TOOL_REGISTRY
                if tool not in TOOL_REGISTRY:
                    return {"success": False, "error": f"unknown OL tool {tool!r}"}
                fn, model, _desc = TOOL_REGISTRY[tool]
                if model is not None:
                    params = model.model_validate(arguments)
                    raw = _run_tool_call(fn, (params,), {}, timeout)
                else:
                    raw = _run_tool_call(fn, (), arguments, timeout)
            else:
                prefix = _MODULE_TOOL_PREFIX.get(module)
                if prefix is None:
                    return {
                        "success": False,
                        "error": f"unknown module {module!r} for in-process call",
                    }
                fn = _resolve_tool(f"{prefix}.{tool}")
                raw = _run_tool_call(fn, (), arguments, timeout)
        return _normalize_tool_output(raw)
    except TimeoutError:
        return {
            "success": False,
            "timeout": True,
            "error": f"timed out after {timeout}s",
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _content_text(result: Any) -> str:
    """Concatenate the TextContent parts of an MCP CallToolResult."""
    parts: list[str] = []
    for part in getattr(result, "content", None) or []:
        text = getattr(part, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def _protocol_response(result: Any) -> dict[str, Any]:
    """Normalize an MCP ``CallToolResult`` into a comparable dict.

    Shape: ``{"success", "is_error", "payload", "error"}`` — payload is the
    parsed JSON envelope when the server returned one (TextContent JSON),
    else the raw text.
    """
    if getattr(result, "isError", False):
        text = _content_text(result)
        return {
            "success": False,
            "is_error": True,
            "payload": text,
            "error": text or "MCP tool error",
        }
    text = _content_text(result)
    try:
        parsed = json.loads(text) if text else None
    except (TypeError, ValueError):
        parsed = text
    if isinstance(parsed, dict):
        return {
            "success": bool(parsed.get("success", True)),
            "is_error": False,
            "payload": parsed,
            "error": None,
        }
    return {
        "success": parsed is not None,
        "is_error": False,
        "payload": parsed,
        "error": None,
    }


def _json_equivalent(a: Any, b: Any) -> bool:
    """Structural JSON equality, skipping ``_VOLATILE_KEYS`` at any depth.

    Dicts must share the same (non-volatile) key sets with equal values;
    lists must have equal length with pairwise-equal items; scalars compare
    directly.
    """
    if a is None or b is None:
        return a is b
    if isinstance(a, dict) and isinstance(b, dict):
        ka = {k for k in a if k not in _VOLATILE_KEYS}
        kb = {k for k in b if k not in _VOLATILE_KEYS}
        if ka != kb:
            return False
        return all(_json_equivalent(a[k], b[k]) for k in ka)
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        return all(_json_equivalent(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, dict) or isinstance(b, dict) or isinstance(a, list) or isinstance(b, list):
        return False
    return a == b


def _snip(value: Any, limit: int = 160) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)
    return text if len(text) <= limit else text[:limit] + "..."


def _canonical_parity_equal(
    in_process: dict[str, Any], protocol: dict[str, Any]
) -> tuple[bool, str]:
    """Whether the in-process and protocol responses are parity-equal.

    Returns ``(equal, detail)``; *detail* names the divergence when unequal.
    See the module-section comment for the exact semantics.
    """
    in_success = bool(in_process.get("success"))
    proto_success = bool(protocol.get("success"))
    if in_success != proto_success:
        return False, (
            f"success divergence: in-process={in_success} protocol={proto_success}"
        )
    if not in_success:
        in_err = bool(in_process.get("error")) or (
            isinstance(in_process.get("data"), dict)
            and bool(in_process["data"].get("error"))
        )
        proto_err = (
            bool(protocol.get("error"))
            or bool(protocol.get("is_error"))
            or (
                isinstance(protocol.get("payload"), dict)
                and bool(protocol["payload"].get("error"))
            )
        )
        if not (in_err and proto_err):
            return False, "error-shape divergence: one side reports no error"
        return True, ""
    if _json_equivalent(in_process.get("data"), protocol.get("payload")):
        return True, ""
    return False, (
        f"payload divergence: in-process={_snip(in_process.get('data'))} "
        f"protocol={_snip(protocol.get('payload'))}"
    )


@dataclasses.dataclass
class ParityResult:
    """One tool's parity check: in-process vs protocol response."""

    #: Module key (opp/ol/orf/omni_mcp).
    module: str
    #: Tool name.
    tool: str
    #: The arguments both calls ran with.
    arguments: dict[str, Any]
    #: Dispatch-shaped in-process ``actual`` (success/data or error).
    in_process: dict[str, Any]
    #: Normalized protocol response (``_protocol_response`` shape).
    protocol: dict[str, Any]
    #: True when the canonical comparison agrees.
    equal: bool
    #: Human-readable divergence reason when ``not equal``, else "".
    detail: str
    #: Wall-clock duration of both calls.
    duration_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class ParityReport:
    """The full transport-parity result across every checked tool."""

    results: list[ParityResult]
    #: module -> startup/launch error when a server could not be reached.
    server_errors: dict[str, str]

    def passed(self) -> int:
        """How many tools' parity checks agreed."""
        return sum(1 for r in self.results if r.equal)

    def diverged(self) -> list[ParityResult]:
        """The tools whose in-process and protocol responses diverged."""
        return [r for r in self.results if not r.equal]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tools_checked": len(self.results),
            "passed": self.passed(),
            "diverged": [r.to_dict() for r in self.diverged()],
            "server_errors": dict(self.server_errors),
            "results": [r.to_dict() for r in self.results],
        }


async def check_tool_parity(
    module: str,
    tool: str,
    arguments: dict[str, Any] | None,
    client: Any,
    env: dict[str, str] | None = None,
    call_timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> ParityResult:
    """One tool: in-process call + protocol call through *client*, compared.

    The in-process call runs via ``asyncio.to_thread`` because it uses
    ``asyncio.run`` internally (cannot run on the parity loop).
    """
    start = time.monotonic()
    in_process = await asyncio.to_thread(
        call_tool_in_process, module, tool, arguments, env, call_timeout
    )
    try:
        async with asyncio.timeout(call_timeout):
            result = await client.call_tool(tool, dict(arguments or {}))
        protocol = _protocol_response(result)
    except TimeoutError:
        protocol = {
            "success": False,
            "is_error": True,
            "payload": None,
            "error": f"protocol call timed out after {call_timeout}s",
        }
    except Exception as exc:
        protocol = {
            "success": False,
            "is_error": True,
            "payload": None,
            "error": f"protocol call failed: {exc}",
        }
    equal, detail = _canonical_parity_equal(in_process, protocol)
    return ParityResult(
        module=module,
        tool=tool,
        arguments=dict(arguments or {}),
        in_process=in_process,
        protocol=protocol,
        equal=equal,
        detail=detail,
        duration_seconds=round(time.monotonic() - start, 3),
    )


async def _run_transport_parity_async(
    module_tools: dict[str, dict[str, dict[str, Any]]],
    env: dict[str, str] | None,
    server_timeout: float,
    call_timeout: float,
) -> ParityReport:
    """Async body of :func:`run_transport_parity` — one server per module."""
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    results: list[ParityResult] = []
    server_errors: dict[str, str] = {}
    full_env = parity_env(env)

    for module, tools in module_tools.items():
        if not tools:
            continue
        launch = _MCP_SERVER_LAUNCH.get(module)
        if launch is None:
            message = f"unknown module {module!r} (no launch spec)"
            server_errors[module] = message
            for tool, arguments in tools.items():
                results.append(
                    ParityResult(module, tool, dict(arguments or {}), {},
                                 {"success": False, "is_error": True,
                                  "payload": None, "error": message},
                                 False, message, 0.0)
                )
            continue
        transport = StdioTransport(
            command=suite_python(),
            args=launch["args"],
            cwd=str(launch["cwd"]),
            env=full_env,
        )
        try:
            async with asyncio.timeout(server_timeout):
                async with Client(transport) as client:
                    for tool, arguments in tools.items():
                        try:
                            pr = await check_tool_parity(
                                module, tool, arguments, client,
                                env=env, call_timeout=call_timeout,
                            )
                        except Exception as exc:  # parity wiring error
                            pr = ParityResult(
                                module, tool, dict(arguments or {}), {},
                                {"success": False, "is_error": True,
                                 "payload": None, "error": str(exc)},
                                False, f"parity error: {exc}", 0.0,
                            )
                        results.append(pr)
        except TimeoutError:
            message = f"server startup timed out after {server_timeout}s"
            server_errors[module] = message
            for tool, arguments in tools.items():
                results.append(
                    ParityResult(module, tool, dict(arguments or {}), {},
                                 {"success": False, "is_error": True,
                                  "payload": None, "error": message},
                                 False, message, 0.0)
                )
        except Exception as exc:
            message = f"server failed: {exc}"
            server_errors[module] = message
            for tool, arguments in tools.items():
                results.append(
                    ParityResult(module, tool, dict(arguments or {}), {},
                                 {"success": False, "is_error": True,
                                  "payload": None, "error": message},
                                 False, message, 0.0)
                )

    return ParityReport(results=results, server_errors=server_errors)


def run_transport_parity(
    module_tools: dict[str, dict[str, dict[str, Any]]],
    env: dict[str, str] | None = None,
    server_timeout: float = 180.0,
    call_timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> ParityReport:
    """X-04 transport-parity suite: every tool over the REAL MCP protocol.

    *module_tools* maps ``module -> {tool: arguments}`` (e.g. the live
    declared surface with each tool's per-tool scenario arguments).  Each
    module's real server is started once over stdio (fastmcp
    ``Client(StdioTransport(...))`` against ``python -m <server>``); every
    tool is called over the protocol AND in-process, and the responses are
    compared canonically (see ``_canonical_parity_equal``).  A tool whose
    responses diverge — or whose server failed to start — lands in
    :meth:`ParityReport.diverged` and makes the execution-backed coverage
    audit exit 1.

    Parameters
    ----------
    module_tools
        ``{module: {tool: arguments}}``; modules are opp/ol/orf/omni_mcp.
    env
        Optional explicit environment (allowlist defaults are added when
        unset; ``OMNI_TEST_FAKE_LLM`` is never injected).
    server_timeout
        Wall-clock cap for one module's server startup + all its calls
        (the OL import chain alone takes ~30-40s).
    call_timeout
        Per-tool cap for the in-process and the protocol call.
    """
    return asyncio.run(
        _run_transport_parity_async(module_tools, env, server_timeout, call_timeout)
    )
