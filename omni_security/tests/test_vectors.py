"""Shared behavioural vectors and the per-module divergences they must preserve.

The four in-tree copies share one rule set; these tests pin the shared verdicts
and the three intentional divergences (extension-check position, ORF directory
handling, OL's skip switch) so Phase 2B wrappers can stay thin without moving a
single observable.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from omni_security import (
    REASON_BLOCKED_EXTENSION,
    REASON_FILE_MISSING,
    REASON_FILE_TOO_LARGE,
    REASON_NOT_A_FILE,
    REASON_OUTSIDE_ALLOWLIST,
    REASON_PATH_TRAVERSAL,
    REASON_SYSTEM_DIR,
    PathValidationError,
    system_dir_denial,
    validate_path,
    validate_path_result,
)

WHITELIST: set[str] = {".md"}
MAX_BYTES = 5


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    (allowed / "ok.md").write_text("hello")  # exactly 5 bytes
    (allowed / "big.md").write_text("0123456789")  # 10 bytes
    (allowed / "evil.exe").write_bytes(b"MZ")
    (allowed / "subdir").mkdir()
    (outside / "secret.md").write_text("secret")
    if os.name != "nt":
        os.symlink(outside / "secret.md", allowed / "link.md")
    return tmp_path


def _opp_core(path: str, allowed: list[Path]) -> bool:
    return validate_path_result(path, allowed, max_file_size_bytes=MAX_BYTES).success


def _ol(path: str, allowed: list[Path]) -> bool:
    return validate_path_result(
        path,
        allowed,
        max_file_size_bytes=MAX_BYTES,
        allowed_extensions=WHITELIST,
        extension_check_position="before_existence",
    ).success


def _orf(path: str, allowed: list[Path]) -> bool:
    return validate_path_result(
        path,
        allowed,
        max_file_size_bytes=MAX_BYTES,
        allowed_extensions=WHITELIST,
        extension_check_position="before_existence",
        directory_handling="allow_if_no_extension",
    ).success


def _opp_mcp(path: str, allowed: list[Path]) -> bool:
    return validate_path_result(
        path,
        allowed,
        max_file_size_bytes=MAX_BYTES,
        allowed_extensions=WHITELIST,
        extension_check_position="after_existence",
    ).success


CALLERS = {"opp_core": _opp_core, "ol": _ol, "orf": _orf, "opp_mcp": _opp_mcp}

SHARED_VECTORS = (
    ("file_inside_allowlist", "allowed/ok.md", True),
    ("double_dot_traversal", "allowed/../escape.md", False),
    ("blocked_executable_extension", "allowed/evil.exe", False),
    ("outside_allowlist_sibling", "outside/secret.md", False),
    ("missing_file_inside_allowlist", "allowed/ghost.md", False),
    ("oversized_file", "allowed/big.md", False),
)


@pytest.mark.parametrize(
    ("vector_id", "rel", "expected"),
    SHARED_VECTORS,
    ids=[vector[0] for vector in SHARED_VECTORS],
)
def test_shared_vectors_agree_across_all_four_callers(tree, vector_id, rel, expected):
    path = str(tree / rel)
    allowed = [tree / "allowed"]
    verdicts = {name: caller(path, allowed) for name, caller in CALLERS.items()}
    assert set(verdicts.values()) == {expected}, f"[{vector_id}] {verdicts}"


def test_traversal_reason(tree):
    with pytest.raises(PathValidationError) as excinfo:
        validate_path(str(tree / "allowed" / ".." / "escape.md"), [tree / "allowed"])
    assert excinfo.value.reason == REASON_PATH_TRAVERSAL


def test_blocked_extension_reason_names_the_suffix(tree):
    with pytest.raises(PathValidationError) as excinfo:
        validate_path(str(tree / "allowed" / "evil.exe"), [tree / "allowed"])
    assert excinfo.value.reason == REASON_BLOCKED_EXTENSION
    assert excinfo.value.extension == ".exe"


def test_outside_allowlist_reason(tree):
    with pytest.raises(PathValidationError) as excinfo:
        validate_path(str(tree / "outside" / "secret.md"), [tree / "allowed"])
    assert excinfo.value.reason == REASON_OUTSIDE_ALLOWLIST


def test_missing_file_reason(tree):
    with pytest.raises(PathValidationError) as excinfo:
        validate_path(str(tree / "allowed" / "ghost.md"), [tree / "allowed"])
    assert excinfo.value.reason == REASON_FILE_MISSING


def test_oversized_file_reason_carries_the_size_context(tree):
    with pytest.raises(PathValidationError) as excinfo:
        validate_path(
            str(tree / "allowed" / "big.md"),
            [tree / "allowed"],
            max_file_size_bytes=MAX_BYTES,
        )
    assert excinfo.value.reason == REASON_FILE_TOO_LARGE
    assert excinfo.value.file_size == 10
    assert excinfo.value.max_file_size == MAX_BYTES


def test_directory_is_rejected_by_opp_core_reason(tree):
    with pytest.raises(PathValidationError) as excinfo:
        validate_path(str(tree / "allowed" / "subdir"), [tree / "allowed"])
    assert excinfo.value.reason == REASON_NOT_A_FILE


def test_system_directory_is_denied(tree):
    target = "C:/Windows/omni-probe.md" if os.name == "nt" else "/etc/omni-probe.md"
    with pytest.raises(PathValidationError) as excinfo:
        validate_path(target, [tree / "allowed"])
    assert excinfo.value.reason == REASON_SYSTEM_DIR


def test_system_dir_denial_uses_a_component_prefix():
    assert system_dir_denial(Path("/etc/passwd"), system_dirs={"/etc"}) == "/etc"
    assert system_dir_denial(Path("/etcetera/file"), system_dirs={"/etc"}) is None
    assert system_dir_denial(Path("/allowed/etc/file"), system_dirs={"/etc"}) is None


def test_directory_handling_divergence(tree):
    directory = str(tree / "allowed" / "subdir")
    allowed = [tree / "allowed"]

    # OPP: no whitelist, so the directory survives until the is-file check.
    with pytest.raises(PathValidationError) as opp_exc:
        validate_path(directory, allowed)
    assert opp_exc.value.reason == REASON_NOT_A_FILE

    # OL: the whitelist runs before existence and rejects the empty extension.
    ol = validate_path_result(
        directory,
        allowed,
        allowed_extensions=WHITELIST,
        extension_check_position="before_existence",
    )
    assert ol.success is False
    assert ol.error == "Extension '' not in allowed set"

    # ORF: the same rejection is overridden for a no-extension directory.
    orf = validate_path_result(
        directory,
        allowed,
        allowed_extensions=WHITELIST,
        extension_check_position="before_existence",
        directory_handling="allow_if_no_extension",
    )
    assert orf.success is True
    assert orf.resolved_path == (tree / "allowed" / "subdir").resolve()


def test_extension_check_position_divergence_for_missing_output(tree):
    missing = str(tree / "allowed" / "out.weird")
    allowed = [tree / "allowed"]

    # OPP MCP checks the whitelist after existence, so a missing output path
    # with allow_missing=True is accepted regardless of extension.
    opp_mcp = validate_path_result(
        missing,
        allowed,
        allow_missing=True,
        allowed_extensions=WHITELIST,
        extension_check_position="after_existence",
    )
    assert opp_mcp.success is True

    # OL checks before existence, so the same call is rejected.
    ol = validate_path_result(
        missing,
        allowed,
        allow_missing=True,
        allowed_extensions=WHITELIST,
        extension_check_position="before_existence",
    )
    assert ol.success is False
    assert ol.error == "Extension '.weird' not in allowed set"


def test_skip_extension_check_bypasses_the_whitelist(tree):
    weird = tree / "allowed" / "data.weird"
    weird.write_text("x")
    allowed = [tree / "allowed"]

    checked = validate_path_result(
        str(weird),
        allowed,
        allowed_extensions=WHITELIST,
        extension_check_position="before_existence",
    )
    assert checked.success is False

    skipped = validate_path_result(
        str(weird),
        allowed,
        allowed_extensions=WHITELIST,
        extension_check_position="before_existence",
        skip_extension_check=True,
    )
    assert skipped.success is True


def test_allow_missing_returns_the_resolved_path(tree):
    missing = str(tree / "allowed" / "out.md")
    result = validate_path_result(missing, [tree / "allowed"], allow_missing=True)
    assert result.success is True
    assert result.resolved_path == Path(missing).resolve()


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs developer mode")
def test_symlink_pointing_outside_is_denied(tree):
    # Resolution follows the link before containment, so the escape is caught by
    # the allowlist check; the redundant symlink re-check only matters under a
    # TOCTOU target change — the same behaviour as all four copies.
    with pytest.raises(PathValidationError) as excinfo:
        validate_path(str(tree / "allowed" / "link.md"), [tree / "allowed"])
    assert excinfo.value.reason == REASON_OUTSIDE_ALLOWLIST


def test_validate_path_result_renders_the_requested_family(tree):
    outside = str(tree / "outside" / "secret.md")
    allowed = [tree / "allowed"]

    ol = validate_path_result(outside, allowed, message_style="ol")
    expected = f"Path is not within allowed directories: {(tree / 'allowed').resolve()}"
    assert ol.error == expected

    opp = validate_path_result(outside, allowed)
    assert opp.error == f"Path not in allowed directories: {outside}"


def test_whitelist_position_requires_an_extension_set(tree):
    with pytest.raises(ValueError, match="allowed_extensions is required"):
        validate_path(
            str(tree / "allowed" / "ok.md"),
            [tree / "allowed"],
            extension_check_position="before_existence",
        )
