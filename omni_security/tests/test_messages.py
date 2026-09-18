"""Every rejection message is copied verbatim from the in-tree sources.

``str()`` renders OPP's canonical wording; ``render("ol")``/``render("orf")``
render the module variants. Exactly three reasons are worded differently across
the families, and each is pinned here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from omni_security import (
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


def test_error_hierarchy():
    assert issubclass(PathValidationError, OmniSecurityError)
    assert issubclass(OmniSecurityError, Exception)


@pytest.mark.parametrize(
    ("reason", "context", "expected"),
    [
        (
            REASON_INVALID_PATH_FORMAT,
            {"error": ValueError("bad")},
            "Invalid path format: bad",
        ),
        (
            REASON_PATH_TRAVERSAL,
            {"path": "/a/../b.md"},
            "Path traversal detected (.. components are not allowed): /a/../b.md",
        ),
        (REASON_CANNOT_RESOLVE, {"error": OSError("nope")}, "Cannot resolve path: nope"),
        (
            REASON_SYSTEM_DIR,
            {"system_dir": "/etc"},
            "Access to system directory not allowed: /etc",
        ),
        (
            REASON_OUTSIDE_ALLOWLIST,
            {"path": "/x/y.md"},
            "Path not in allowed directories: /x/y.md",
        ),
        (REASON_SYMLINK_ESCAPE, {}, "Symlink points outside allowed directories"),
        (
            REASON_SYMLINK_INACCESSIBLE,
            {"error": OSError("io")},
            "Symlink target is not accessible: io",
        ),
        (
            REASON_BLOCKED_EXTENSION,
            {"extension": ".exe"},
            "File extension '.exe' is blocked",
        ),
        (
            REASON_DISALLOWED_EXTENSION,
            {"extension": ".xyz"},
            "Extension '.xyz' not in allowed set",
        ),
        (REASON_FILE_MISSING, {}, "File does not exist"),
        (REASON_NOT_A_FILE, {}, "Path must be a file, not a directory"),
        (
            REASON_FILE_TOO_LARGE,
            {"file_size": 10, "max_file_size": 5},
            "File size (10 bytes) exceeds limit of 5 bytes",
        ),
        (
            REASON_STAT_FAILED,
            {"error": OSError("denied")},
            "Cannot access file to check size: denied",
        ),
    ],
)
def test_str_is_the_canonical_opp_message(reason, context, expected):
    error = PathValidationError(reason, **context)
    assert str(error) == expected
    assert error.render("opp") == expected


def test_reason_is_machine_readable():
    error = PathValidationError(REASON_OUTSIDE_ALLOWLIST, path="/x")
    assert error.reason == REASON_OUTSIDE_ALLOWLIST
    assert str(error.reason) == "outside_allowlist"


def test_traversal_drops_the_path_suffix_for_ol_and_orf():
    error = PathValidationError(REASON_PATH_TRAVERSAL, path="/a/../b.md")
    assert error.render("ol") == "Path traversal detected (.. components are not allowed)"
    assert error.render("orf") == "Path traversal detected (.. components are not allowed)"


def test_allowlist_lists_directories_for_ol_and_orf():
    error = PathValidationError(
        REASON_OUTSIDE_ALLOWLIST,
        path="/x/y.md",
        allowed_dirs=[Path("/srv/allowed"), Path("/srv/other")],
    )
    expected = "Path is not within allowed directories: /srv/allowed, /srv/other"
    assert error.render("ol") == expected
    assert error.render("orf") == expected


def test_inaccessible_symlink_omits_the_cause_for_ol_and_orf():
    error = PathValidationError(REASON_SYMLINK_INACCESSIBLE, error=OSError("io"))
    assert error.render("ol") == "Symlink target is not accessible"
    assert error.render("orf") == "Symlink target is not accessible"


@pytest.mark.parametrize("style", ["opp", "ol", "orf"])
def test_shared_messages_are_identical_across_families(style):
    assert (
        PathValidationError(REASON_BLOCKED_EXTENSION, extension=".exe").render(style)
        == "File extension '.exe' is blocked"
    )
    assert (
        PathValidationError(REASON_DISALLOWED_EXTENSION, extension=".xyz").render(style)
        == "Extension '.xyz' not in allowed set"
    )
    assert PathValidationError(REASON_FILE_MISSING).render(style) == "File does not exist"
    assert (
        PathValidationError(REASON_NOT_A_FILE).render(style)
        == "Path must be a file, not a directory"
    )
    assert (
        PathValidationError(
            REASON_FILE_TOO_LARGE, file_size=10, max_file_size=5
        ).render(style)
        == "File size (10 bytes) exceeds limit of 5 bytes"
    )
