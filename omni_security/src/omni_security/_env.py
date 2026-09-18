"""Environment-variable parsing shared by the path-policy callers.

Both helpers reproduce the contract the four in-tree copies converged on in
ADR 0007 (2026-09-17). Keep them byte-for-byte compatible with
``opp.mcp.config._parse_allowed_dirs``, ``ol_mcp.security._parse_allowed_dirs``,
``orf.mcp.config._parse_allowed_dirs`` and
``omni_mcp.orchestrator._split_allowlist``.
"""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_EXTENSIONS_ENV_VAR = "MCP_ALLOWED_EXTENSIONS"


def parse_allowed_dirs(value: str) -> list[Path]:
    """Split an allowlist string into ``Path`` objects.

    Contract: split on ``os.pathsep`` (POSIX ``":"``, Windows ``";"``), then on
    comma; strip each fragment; drop empties. A separator-free value is a
    single-element list. Never split on a hard-coded ``":"`` — on Windows that
    would cut drive letters (``C:\\work`` into ``C`` plus ``\\work``) and
    silently disable the allowlist.

    Args:
        value: Raw environment-variable value.

    Returns:
        One ``Path`` per non-empty fragment; ``[]`` for a blank value.
    """
    if not value or not value.strip():
        return []
    parts: list[str] = []
    for chunk in value.split(os.pathsep):
        parts.extend(chunk.split(","))
    return [Path(part.strip()) for part in parts if part.strip()]


def resolve_allowed_extensions(
    default: set[str],
    env_var: str = _DEFAULT_EXTENSIONS_ENV_VAR,
) -> set[str]:
    """Return *default*, or the ``env_var`` override when it is non-blank.

    Leading dots are optional (``txt`` normalises to ``.txt``). A blank or
    whitespace-only value means "unset" and yields *default* unchanged — never
    an empty set, which would reject every path.

    Args:
        default: The caller's built-in whitelist.
        env_var: Environment variable holding the comma-separated override.

    Returns:
        The effective whitelist, every member carrying a leading dot.
    """
    raw = os.environ.get(env_var, "").strip()
    if not raw:
        return default
    return {
        ext if ext.startswith(".") else f".{ext}"
        for ext in (part.strip() for part in raw.split(","))
        if ext
    }
