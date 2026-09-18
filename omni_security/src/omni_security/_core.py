"""The canonical path-validation engine.

One function — :func:`validate_path` — reproduces the policy every in-tree copy
applies. The copies differ only in three axes, exposed as parameters so a thin
wrapper never changes observable behaviour:

* ``extension_check_position`` — OPP's shared core has no allowed-extension
  whitelist (``skip``); OL and ORF apply theirs *before* the existence check,
  while OPP's MCP wrapper applies it *after* it;
* ``directory_handling`` — ORF accepts a directory that has no allowed
  extension (``allow_if_no_extension``), OPP and OL reject it;
* ``skip_extension_check`` — OL's pipeline tools bypass the whitelist entirely.

:func:`validate_path_result` wraps the raising engine in the
``ValidationResult`` shape OL/ORF return, rendering each family's messages via
``message_style``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ._constants import BLOCKED_EXTENSIONS, SYSTEM_DIRS
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
    MessageStyle,
    PathValidationError,
)

#: Where the allowed-extension whitelist is applied relative to the existence
#: check. ``"skip"`` means the caller has no whitelist.
ExtensionCheckPosition = Literal["skip", "before_existence", "after_existence"]

#: What to do when the extension whitelist rejects a path that is a directory
#: with no extension.
DirectoryHandling = Literal["reject", "allow_if_no_extension"]


@dataclass
class ValidationResult:
    """Result of path validation (shape shared with the module copies).

    Attributes:
        success: True if the path passed all validation checks.
        error: Error message if validation failed, None otherwise.
        resolved_path: The resolved ``Path`` if successful, None otherwise.
    """

    success: bool
    error: str | None = None
    resolved_path: Path | None = None


def system_dir_denial(
    resolved: Path,
    system_dirs: set[str] = SYSTEM_DIRS,
) -> str | None:
    """Return the ``system_dirs`` entry *resolved* falls under, else ``None``.

    Uses the same ``Path.parts`` prefix comparison as every in-tree copy: a
    candidate must have at least as many parts as the system directory and match
    it component for component. POSIX system dirs therefore never match a
    Windows path and ``C:\\Windows`` never matches on POSIX — that asymmetry is
    the contract, not a bug.

    Args:
        resolved: An already-resolved target path.
        system_dirs: The blacklist to test against.

    Returns:
        The matched directory literal (for the error message), or ``None``.
    """
    resolved_parts = resolved.parts
    for sys_dir in system_dirs:
        sys_parts = Path(sys_dir).parts
        if len(resolved_parts) < len(sys_parts):
            continue
        if resolved_parts[: len(sys_parts)] == sys_parts:
            return sys_dir
    return None


def validate_path(
    path_str: str,
    allowed_dirs: Sequence[Path],
    max_file_size_bytes: int | None = None,
    allow_missing: bool = False,
    allowed_extensions: set[str] | None = None,
    skip_extension_check: bool = False,
    system_dirs: set[str] = SYSTEM_DIRS,
    blocked_extensions: set[str] = BLOCKED_EXTENSIONS,
    extension_check_position: ExtensionCheckPosition = "skip",
    directory_handling: DirectoryHandling = "reject",
) -> Path:
    """Validate *path_str* and return the resolved ``Path``.

    The parameter surface is the caller-compatibility contract: pass the
    defaults to reproduce OPP's shared core, ``extension_check_position`` plus
    ``allowed_extensions`` for OL, and add
    ``directory_handling="allow_if_no_extension"`` for ORF.

    Args:
        path_str: The user-supplied path string.
        allowed_dirs: Directory allowlist (each resolved before comparison).
        max_file_size_bytes: If set, reject files larger than this.
        allow_missing: If True, skip the existence check (for output paths).
        allowed_extensions: Whitelist, required when the check is not skipped.
        skip_extension_check: If True, bypass the whitelist entirely.
        system_dirs: System-directory blacklist.
        blocked_extensions: Executable-extension blacklist.
        extension_check_position: When the whitelist runs, if at all.
        directory_handling: Whether the whitelist accepts a no-extension dir.

    Returns:
        The resolved, validated path.

    Raises:
        PathValidationError: On the first failing check, carrying a
            machine-readable ``reason`` and the context for every message family.
        ValueError: When a whitelist position is requested without
            ``allowed_extensions``.
    """
    effective_position: ExtensionCheckPosition = (
        "skip" if skip_extension_check else extension_check_position
    )
    if effective_position != "skip" and allowed_extensions is None:
        raise ValueError(
            "allowed_extensions is required when extension_check_position is not 'skip'"
        )

    # 1. Parse the path.
    try:
        candidate = Path(path_str)
    except (ValueError, OSError) as exc:
        raise PathValidationError(
            REASON_INVALID_PATH_FORMAT, path=path_str, error=exc
        ) from exc

    # 2. Reject path traversal.
    if ".." in candidate.parts:
        raise PathValidationError(REASON_PATH_TRAVERSAL, path=path_str)

    # 3. Resolve the path (follows symlinks).
    try:
        resolved = candidate.resolve()
    except (ValueError, OSError) as exc:
        raise PathValidationError(
            REASON_CANNOT_RESOLVE, path=path_str, error=exc
        ) from exc

    # 4. Reject system directories.
    matched_system_dir = system_dir_denial(resolved, system_dirs)
    if matched_system_dir is not None:
        raise PathValidationError(
            REASON_SYSTEM_DIR, path=path_str, system_dir=matched_system_dir
        )

    # 5. Resolve the allowlist, then require containment.
    resolved_allowed = [Path(directory).resolve() for directory in allowed_dirs]
    if not _within(resolved, resolved_allowed):
        raise PathValidationError(
            REASON_OUTSIDE_ALLOWLIST, path=path_str, allowed_dirs=resolved_allowed
        )

    # 6. Re-check a symlink target. Resolution already folded an escaping link
    #    into the containment check above, so this only differs across a TOCTOU
    #    change of target — kept because all four copies carry it.
    if candidate.is_symlink():
        try:
            link_target = candidate.resolve()
            if not _within(link_target, resolved_allowed):
                raise PathValidationError(REASON_SYMLINK_ESCAPE, path=path_str)
        except (ValueError, OSError) as exc:
            raise PathValidationError(
                REASON_SYMLINK_INACCESSIBLE, path=path_str, error=exc
            ) from exc

    # 7. Reject blocked executable extensions.
    suffix = candidate.suffix
    if suffix.lower() in blocked_extensions:
        raise PathValidationError(
            REASON_BLOCKED_EXTENSION, path=path_str, extension=suffix
        )

    # 8. Apply the allowed-extension whitelist before the existence check
    #    (OL/ORF), including ORF's no-extension-directory shortcut.
    if effective_position == "before_existence" and not _extension_allowed(
        suffix, allowed_extensions
    ):
        if directory_handling == "allow_if_no_extension" and resolved.is_dir():
            return resolved
        raise PathValidationError(
            REASON_DISALLOWED_EXTENSION, path=path_str, extension=suffix
        )

    # 9. Existence check.
    if not resolved.exists():
        if allow_missing:
            return resolved
        raise PathValidationError(REASON_FILE_MISSING, path=path_str)

    # 10. Must be a file, not a directory.
    if not resolved.is_file():
        raise PathValidationError(REASON_NOT_A_FILE, path=path_str)

    # 11. Optional size check.
    if max_file_size_bytes is not None:
        try:
            file_size = resolved.stat().st_size
        except OSError as exc:
            raise PathValidationError(
                REASON_STAT_FAILED, path=path_str, error=exc
            ) from exc
        if file_size > max_file_size_bytes:
            raise PathValidationError(
                REASON_FILE_TOO_LARGE,
                path=path_str,
                file_size=file_size,
                max_file_size=max_file_size_bytes,
            )

    # 12. Apply the whitelist after the existence check (OPP's MCP wrapper).
    if effective_position == "after_existence" and not _extension_allowed(
        suffix, allowed_extensions
    ):
        if directory_handling == "allow_if_no_extension" and resolved.is_dir():
            return resolved
        raise PathValidationError(
            REASON_DISALLOWED_EXTENSION, path=path_str, extension=suffix
        )

    return resolved


def validate_path_result(
    path_str: str,
    allowed_dirs: Sequence[Path],
    max_file_size_bytes: int | None = None,
    allow_missing: bool = False,
    allowed_extensions: set[str] | None = None,
    skip_extension_check: bool = False,
    system_dirs: set[str] = SYSTEM_DIRS,
    blocked_extensions: set[str] = BLOCKED_EXTENSIONS,
    extension_check_position: ExtensionCheckPosition = "skip",
    directory_handling: DirectoryHandling = "reject",
    message_style: MessageStyle = "opp",
) -> ValidationResult:
    """Non-raising :func:`validate_path` for the ``ValidationResult`` callers.

    Args:
        path_str: See :func:`validate_path`.
        allowed_dirs: See :func:`validate_path`.
        max_file_size_bytes: See :func:`validate_path`.
        allow_missing: See :func:`validate_path`.
        allowed_extensions: See :func:`validate_path`.
        skip_extension_check: See :func:`validate_path`.
        system_dirs: See :func:`validate_path`.
        blocked_extensions: See :func:`validate_path`.
        extension_check_position: See :func:`validate_path`.
        directory_handling: See :func:`validate_path`.
        message_style: Which family's wording to render into ``error``.

    Returns:
        ``ValidationResult(success=True, resolved_path=...)`` or
        ``ValidationResult(success=False, error=...)``.
    """
    try:
        resolved = validate_path(
            path_str,
            allowed_dirs,
            max_file_size_bytes=max_file_size_bytes,
            allow_missing=allow_missing,
            allowed_extensions=allowed_extensions,
            skip_extension_check=skip_extension_check,
            system_dirs=system_dirs,
            blocked_extensions=blocked_extensions,
            extension_check_position=extension_check_position,
            directory_handling=directory_handling,
        )
    except PathValidationError as exc:
        return ValidationResult(success=False, error=exc.render(message_style))
    return ValidationResult(success=True, resolved_path=resolved)


def _within(path: Path, directories: Sequence[Path]) -> bool:
    """True when *path* is contained in any of *directories*."""
    return any(path.is_relative_to(directory) for directory in directories)


def _extension_allowed(suffix: str, allowed_extensions: set[str] | None) -> bool:
    """True when *suffix* is on the whitelist; ``None`` means "no whitelist"."""
    if allowed_extensions is None:
        return True
    return suffix.lower() in allowed_extensions
