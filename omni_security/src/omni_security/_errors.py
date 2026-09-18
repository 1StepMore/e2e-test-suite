"""Typed errors for the canonical path-security policy.

:class:`PathValidationError` carries a machine-readable :class:`Reason` plus the
structured context every caller needs to render its own byte-identical message.
``str()`` renders the canonical OPP wording; :meth:`PathValidationError.render`
also renders the OL/ORF variants, which differ for exactly three refusals
(traversal, allowlist containment and an inaccessible symlink target).
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import Literal, assert_never


class OmniSecurityError(Exception):
    """Base class for every error raised by ``omni_security``."""


class Reason(StrEnum):
    """Machine-readable reason a path was rejected."""

    INVALID_PATH_FORMAT = "invalid_path_format"
    PATH_TRAVERSAL = "path_traversal"
    CANNOT_RESOLVE = "cannot_resolve"
    SYSTEM_DIR = "system_dir"
    OUTSIDE_ALLOWLIST = "outside_allowlist"
    SYMLINK_ESCAPE = "symlink_escape"
    SYMLINK_INACCESSIBLE = "symlink_inaccessible"
    BLOCKED_EXTENSION = "blocked_extension"
    DISALLOWED_EXTENSION = "disallowed_extension"
    FILE_MISSING = "file_missing"
    NOT_A_FILE = "not_a_file"
    FILE_TOO_LARGE = "file_too_large"
    STAT_FAILED = "stat_failed"


REASON_INVALID_PATH_FORMAT = Reason.INVALID_PATH_FORMAT
REASON_PATH_TRAVERSAL = Reason.PATH_TRAVERSAL
REASON_CANNOT_RESOLVE = Reason.CANNOT_RESOLVE
REASON_SYSTEM_DIR = Reason.SYSTEM_DIR
REASON_OUTSIDE_ALLOWLIST = Reason.OUTSIDE_ALLOWLIST
REASON_SYMLINK_ESCAPE = Reason.SYMLINK_ESCAPE
REASON_SYMLINK_INACCESSIBLE = Reason.SYMLINK_INACCESSIBLE
REASON_BLOCKED_EXTENSION = Reason.BLOCKED_EXTENSION
REASON_DISALLOWED_EXTENSION = Reason.DISALLOWED_EXTENSION
REASON_FILE_MISSING = Reason.FILE_MISSING
REASON_NOT_A_FILE = Reason.NOT_A_FILE
REASON_FILE_TOO_LARGE = Reason.FILE_TOO_LARGE
REASON_STAT_FAILED = Reason.STAT_FAILED

#: Message family. ``opp`` is canonical (``str()`` uses it); ``ol`` and ``orf``
#: share their wording with each other and differ from OPP only for the three
#: reasons called out in :meth:`PathValidationError.render`.
MessageStyle = Literal["opp", "ol", "orf"]


class PathValidationError(OmniSecurityError):
    """A path failed one of the canonical security checks.

    Attributes:
        reason: Machine-readable :class:`Reason`.
        path: The path string supplied by the caller (used by OPP's wording).
        allowed_dirs: The resolved allowlist the path was checked against.
        system_dir: The :data:`~omni_security.SYSTEM_DIRS` entry that matched.
        extension: The suffix as written (original case) that was rejected.
        error: The underlying ``OSError``/``ValueError`` for I/O-bound reasons.
        file_size: Observed size, set for :attr:`Reason.FILE_TOO_LARGE`.
        max_file_size: Configured cap, set for :attr:`Reason.FILE_TOO_LARGE`.
    """

    reason: Reason
    path: str | None
    allowed_dirs: tuple[Path, ...]
    system_dir: str | None
    extension: str | None
    error: ValueError | OSError | None
    file_size: int | None
    max_file_size: int | None

    def __init__(
        self,
        reason: Reason,
        *,
        path: str | None = None,
        allowed_dirs: Sequence[Path] = (),
        system_dir: str | None = None,
        extension: str | None = None,
        error: ValueError | OSError | None = None,
        file_size: int | None = None,
        max_file_size: int | None = None,
    ) -> None:
        self.reason = reason
        self.path = path
        self.allowed_dirs = tuple(allowed_dirs)
        self.system_dir = system_dir
        self.extension = extension
        self.error = error
        self.file_size = file_size
        self.max_file_size = max_file_size
        super().__init__(self.render("opp"))

    def render(self, style: MessageStyle = "opp") -> str:
        """Render this rejection in *style*'s byte-identical wording.

        Args:
            style: ``"opp"`` (canonical, also used by ``str()``), ``"ol"`` or
                ``"orf"``.

        Returns:
            The exact message the requested family produces for this reason.
        """
        match self.reason:
            case Reason.INVALID_PATH_FORMAT:
                return f"Invalid path format: {self.error}"
            case Reason.PATH_TRAVERSAL:
                if style == "opp":
                    return (
                        "Path traversal detected (.. components are not allowed): "
                        f"{self.path}"
                    )
                return "Path traversal detected (.. components are not allowed)"
            case Reason.CANNOT_RESOLVE:
                return f"Cannot resolve path: {self.error}"
            case Reason.SYSTEM_DIR:
                return f"Access to system directory not allowed: {self.system_dir}"
            case Reason.OUTSIDE_ALLOWLIST:
                if style == "opp":
                    return f"Path not in allowed directories: {self.path}"
                joined = ", ".join(str(directory) for directory in self.allowed_dirs)
                return f"Path is not within allowed directories: {joined}"
            case Reason.SYMLINK_ESCAPE:
                return "Symlink points outside allowed directories"
            case Reason.SYMLINK_INACCESSIBLE:
                if style == "opp":
                    return f"Symlink target is not accessible: {self.error}"
                return "Symlink target is not accessible"
            case Reason.BLOCKED_EXTENSION:
                return f"File extension '{self.extension}' is blocked"
            case Reason.DISALLOWED_EXTENSION:
                return f"Extension '{self.extension}' not in allowed set"
            case Reason.FILE_MISSING:
                return "File does not exist"
            case Reason.NOT_A_FILE:
                return "Path must be a file, not a directory"
            case Reason.FILE_TOO_LARGE:
                return (
                    f"File size ({self.file_size} bytes) exceeds limit of "
                    f"{self.max_file_size} bytes"
                )
            case Reason.STAT_FAILED:
                return f"Cannot access file to check size: {self.error}"
            case _:
                assert_never(self.reason)
