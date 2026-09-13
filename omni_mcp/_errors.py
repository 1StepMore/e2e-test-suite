"""omni-mcp error envelope + recovery hints (R-09).

Single source of truth for the suite-level error envelope. ``server.py``
and ``orchestrator.py`` both delegate here so every omni-mcp error carries
``{strategy, hint}`` recovery text.

Hints are static constants: never interpolate the exception message or
caller-controlled data (prompt-injection safety). Contract-tested by
tests/contract/test_recovery_hints_contract.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RecoveryHint:
    """A recoverability hint attached to a stable error code."""

    strategy: str
    hint: str


RECOVERY_HINTS: dict[str, RecoveryHint] = {
    "AUTH_FAILED": RecoveryHint(
        "reissue_with_auth",
        "Re-issue the call with the shared_secret matching the server's "
        "MCP_SHARED_SECRET environment variable.",
    ),
    "OMNI_PATH_DENIED": RecoveryHint(
        "use_allowed_path",
        "Set MCP_ALLOWED_DIRECTORIES (or OMNI_MCP_ALLOWED_DIRS) to include the "
        "path, or use a path already inside it, then re-issue.",
    ),
    "FILE_NOT_FOUND": RecoveryHint(
        "fix_input",
        "Verify the source document path exists at the suite entry point, then "
        "re-issue.",
    ),
    "CLI_NOT_FOUND": RecoveryHint(
        "configure_environment",
        "Install the OPP/OL/ORF packages (or fix PATH) so the CLI entry point "
        "resolves, then re-issue.",
    ),
    "CLI_TIMEOUT": RecoveryHint(
        "retry",
        "Retry, or raise the stage timeout for a large document.",
    ),
    "CLI_EMPTY_OUTPUT": RecoveryHint(
        "report_bug",
        "A pipeline stage CLI returned empty output; check server logs and file "
        "a bug report.",
    ),
    "CLI_PARSE_ERROR": RecoveryHint(
        "report_bug",
        "A pipeline stage CLI emitted unparseable output; check server logs and "
        "file a bug report.",
    ),
    "OPP_FAILED": RecoveryHint(
        "fix_input",
        "Read the OPP error in the message; fix the input document or extraction "
        "settings, then retry.",
    ),
    "OPP_NO_MD": RecoveryHint(
        "fix_input",
        "OPP produced no Markdown; verify the input format supports the MD path, "
        "then retry.",
    ),
    "OPP_NO_XLIFF": RecoveryHint(
        "fallback",
        "OPP cannot produce XLIFF for this input (e.g. PDF); switch to the MD "
        "pipeline.",
    ),
    "OL_FAILED": RecoveryHint(
        "retry",
        "Read the OL error in the message; retry once (LLM failures are often "
        "transient), else fix the input.",
    ),
    "OL_NO_OUTPUT": RecoveryHint(
        "report_bug",
        "OL produced no translated output; check server logs and file a bug report.",
    ),
    "INVALID_PIPELINE": RecoveryHint(
        "fix_input",
        "Pass pipeline='md' or pipeline='xliff' (or omit it), then re-issue.",
    ),
    "ORF_FAILED": RecoveryHint(
        "retry",
        "Read the ORF error in the message; retry once, else fix the input or "
        "output format.",
    ),
    "OUTPUT_NOT_FOUND": RecoveryHint(
        "report_bug",
        "The backfill reported success but no output file exists; check server "
        "logs and file a bug report.",
    ),
    "OMNI_INVALID_INPUT": RecoveryHint(
        "fix_input",
        "Validate the arguments against the tool's inputSchema, then re-issue.",
    ),
    "OMNI_VALIDATION_LOAD_ERROR": RecoveryHint(
        "configure_environment",
        "Fix the scenario library (missing or invalid scenario files), then re-issue.",
    ),
    "OMNI_UNKNOWN_TOOL": RecoveryHint(
        "fix_input",
        "Call one of the advertised omni-mcp tools; check the tool name spelling.",
    ),
    "OMNI_INTERNAL_ERROR": RecoveryHint(
        "report_bug",
        "Do not retry blindly; check server logs for the traceback and file a bug report.",
    ),
}

DECLARED_ERROR_CODES: frozenset[str] = frozenset(RECOVERY_HINTS)

_FALLBACK_RECOVERY = RecoveryHint(
    "report_bug",
    "Unknown error code; inspect server logs for the traceback and file a bug report.",
)


def recovery_for(code: str) -> dict[str, str]:
    """Return the ``{strategy, hint}`` recovery envelope for *code*.

    Unknown codes receive a safe ``report_bug`` fallback, so every error
    envelope always carries a recovery object.
    """
    rec = RECOVERY_HINTS.get(code, _FALLBACK_RECOVERY)
    return {"strategy": rec.strategy, "hint": rec.hint}


def error_response(code: str, message: str, **extra: Any) -> dict[str, Any]:
    """Standardized suite-level error response with a recovery hint."""
    resp: dict[str, Any] = {
        "success": False,
        "error": {"code": code, "message": message},
        "error_code": code,
        "message": message,
        "recovery": recovery_for(code),
    }
    resp.update(extra)
    return resp
