"""``omni_security`` — the one canonical Omni path-security policy.

A leaf library: it imports only the standard library and must never import
``opp``, ``ol_mcp``, ``orf``, ``omni_mcp`` or ``omni_suite``. The module
validators and the suite orchestrator consume it, so the policy — and the exact
rejection wording — lives in exactly one place.
"""

from ._constants import BLOCKED_EXTENSIONS, SYSTEM_DIRS
from ._core import (
    ValidationResult,
    system_dir_denial,
    validate_path,
    validate_path_result,
)
from ._env import parse_allowed_dirs, resolve_allowed_extensions
from ._errors import (
    REASON_BLOCKED_EXTENSION,
    REASON_CANNOT_RESOLVE,
    REASON_DISALLOWED_EXTENSION,
    REASON_FILE_MISSING,
    REASON_FILE_TOO_LARGE,
    REASON_INVALID_PATH_FORMAT,
    REASON_NOT_A_FILE,
    REASON_OUTSIDE_ALLOWLIST,
    REASON_PATH_TRAVERSAL,
    REASON_STAT_FAILED,
    REASON_SYMLINK_ESCAPE,
    REASON_SYMLINK_INACCESSIBLE,
    REASON_SYSTEM_DIR,
    OmniSecurityError,
    PathValidationError,
)

__all__ = [
    "BLOCKED_EXTENSIONS",
    "SYSTEM_DIRS",
    "OmniSecurityError",
    "PathValidationError",
    "REASON_BLOCKED_EXTENSION",
    "REASON_CANNOT_RESOLVE",
    "REASON_DISALLOWED_EXTENSION",
    "REASON_FILE_MISSING",
    "REASON_FILE_TOO_LARGE",
    "REASON_INVALID_PATH_FORMAT",
    "REASON_NOT_A_FILE",
    "REASON_OUTSIDE_ALLOWLIST",
    "REASON_PATH_TRAVERSAL",
    "REASON_STAT_FAILED",
    "REASON_SYMLINK_ESCAPE",
    "REASON_SYMLINK_INACCESSIBLE",
    "REASON_SYSTEM_DIR",
    "ValidationResult",
    "parse_allowed_dirs",
    "resolve_allowed_extensions",
    "system_dir_denial",
    "validate_path",
    "validate_path_result",
]
