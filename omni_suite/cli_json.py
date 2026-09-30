"""Machine-readable output mode for the suite CLI (``omni-suite --json``).

An agent driving ``omni-suite`` has exactly two reliable channels: the exit
code and something it can parse. Exit codes are already a deliberate taxonomy
(``STANDARDS.md#exit-codes``); this module supplies the second one by owning
the *stream ownership* of a ``--json`` run:

* **stdout carries one JSON object and nothing else.** Every human line the CLI
  prints — progress, warnings, usage, the "Intermediate files kept at" note —
  is redirected to stderr, so the 80+ existing ``print()`` calls keep working
  unchanged.
* **Stage subprocesses are pinned to the stderr fd.** A child inherits fd 1, so
  redirecting ``sys.stdout`` is not enough: OPP/OL/ORF would otherwise write
  straight into the JSON stream.

The envelope mirrors the suite's MCP envelope (``omni_mcp/_errors.py``,
``docs/agent-pipeline-guide.md`` §5) so an agent parses one shape everywhere::

    {"success": true,  "error": null, "error_code": null, "message": null,
     "command": "status", "exit_code": 0, "content": {...}}

    {"success": false, "error": {"code": "...", "message": "..."},
     "error_code": "...", "message": "...", "command": "pipeline",
     "exit_code": 2, "content": {...}}

``error`` is always present (``null`` on success) so a client can index it
without branching; ``error_code``/``message`` are the flat aliases the MCP
surface documents. ``success`` mirrors the exit code — it reports *did the
command succeed*, never a detail of the payload (``check`` exits 0 even when a
module's suite failed; that verdict lives in ``content``).

Nothing here touches exit codes or non-``--json`` output: every method is a
no-op while the mode is inactive.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from collections.abc import Callable, Iterator, Sequence
from typing import Any, NoReturn, TextIO

#: The top-level switch, accepted before or after the subcommand.
JSON_FLAG = "--json"


def split_json_flag(argv: Sequence[str]) -> tuple[bool, list[str]]:
    """Split :data:`JSON_FLAG` out of *argv*.

    Returns ``(requested, remaining)``. The flag is top-level — ``omni-suite
    --json pipeline x`` is the documented form — but is also accepted after the
    subcommand, because no subcommand has a ``--json`` option of its own to
    collide with and an agent must not be punished for the flag's position.
    """
    remaining = [arg for arg in argv if arg != JSON_FLAG]
    return len(remaining) != len(argv), remaining


def _stderr_fd() -> int:
    """fd 2 as an int, so a captured or closed ``sys.stderr`` cannot break a spawn."""
    try:
        return sys.stderr.fileno()
    except (AttributeError, OSError, ValueError):
        return 2


class JsonOutput:
    """Owns the stream split and the envelope for one CLI invocation.

    Inactive by default: every method keeps the pre-``--json`` behaviour, so
    the CLI needs no ``if json_mode`` branches at its print sites.
    """

    def __init__(self) -> None:
        self.active = False
        self._command = ""
        self._stdout: TextIO = sys.stdout

    def reset(self, *, active: bool, command: str) -> None:
        """Start an invocation; remembers the real stdout to write the envelope to."""
        self.active = active
        self._command = command
        self._stdout = sys.stdout

    @contextlib.contextmanager
    def human_output_on_stderr(self) -> Iterator[None]:
        """Route every ``print()`` in the block to stderr (inactive: unchanged)."""
        if not self.active:
            yield
            return
        original = sys.stdout
        sys.stdout = sys.stderr
        try:
            yield
        finally:
            sys.stdout = original

    def human(self, emit: Callable[[], None]) -> str:
        """Run *emit* — which prints human text — and return exactly that text.

        Active: the text is captured, replayed on stderr, and returned for the
        envelope. Inactive: *emit* prints straight to stdout and the text is
        still returned, so a caller can build a payload either way.
        """
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            emit()
        text = buffer.getvalue()
        print(text, end="", file=sys.stderr if self.active else self._stdout)
        return text

    def success(self, content: dict[str, Any] | None = None) -> None:
        """Write the success envelope on the real stdout (inactive: no-op)."""
        if not self.active:
            return
        self._write(
            success=True,
            error=None,
            exit_code=0,
            content=content,
        )

    def failure(
        self,
        exit_code: int,
        code: str,
        message: str,
        content: dict[str, Any] | None = None,
    ) -> NoReturn:
        """Write the error envelope on the real stdout, then exit *exit_code*.

        Every ``sys.exit`` in the CLI routes through here, so a ``SystemExit``
        that escapes command dispatch always has an envelope waiting on stdout.
        The exit code is the caller's: this method never renumbers it.
        """
        if self.active:
            self._write(
                success=False,
                error={"code": code, "message": message},
                exit_code=exit_code,
                content=content,
            )
        raise SystemExit(exit_code)

    def stage_stdout(self) -> dict[str, Any]:
        """``subprocess.run`` kwargs pinning a stage CLI's stdout to stderr.

        Empty while inactive, so the call sites stay byte-identical.
        """
        return {"stdout": _stderr_fd()} if self.active else {}

    def _write(
        self,
        *,
        success: bool,
        error: dict[str, str] | None,
        exit_code: int,
        content: dict[str, Any] | None,
    ) -> None:
        code = error["code"] if error else None
        message = error["message"] if error else None
        envelope = {
            "success": success,
            "error": error,
            "error_code": code,
            "message": message,
            "command": self._command,
            "exit_code": exit_code,
            "content": content or {},
        }
        print(json.dumps(envelope, ensure_ascii=False), file=self._stdout)
        self._stdout.flush()
