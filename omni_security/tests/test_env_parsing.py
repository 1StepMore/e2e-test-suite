"""Allowlist-string and extension-env-var parsing must match the four copies."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from omni_security import parse_allowed_dirs, resolve_allowed_extensions


class TestParseAllowedDirs:
    def test_blank_value_yields_an_empty_list(self):
        assert parse_allowed_dirs("") == []
        assert parse_allowed_dirs("   ") == []

    def test_separator_free_value_is_a_single_element(self, tmp_path: Path):
        assert parse_allowed_dirs(str(tmp_path)) == [tmp_path]

    def test_comma_and_platform_separator_are_both_supported(self, tmp_path: Path):
        alpha = tmp_path / "alpha"
        beta = tmp_path / "beta"
        alpha.mkdir()
        beta.mkdir()

        assert parse_allowed_dirs(f"{alpha},{beta}") == [alpha, beta]
        assert parse_allowed_dirs(os.pathsep.join([str(alpha), str(beta)])) == [alpha, beta]

    def test_whitespace_and_empty_fragments_are_dropped(self, tmp_path: Path):
        alpha = tmp_path / "alpha"
        beta = tmp_path / "beta"
        alpha.mkdir()
        beta.mkdir()

        assert parse_allowed_dirs(f"  {alpha} ,, {beta}  ") == [alpha, beta]

    @pytest.mark.skipif(os.name != "nt", reason="drive-letter semantics are Windows-only")
    def test_windows_drive_letter_is_not_split(self):
        assert parse_allowed_dirs(r"C:\work") == [Path(r"C:\work")]
        assert parse_allowed_dirs(r"C:\docs;C:\out") == [
            Path(r"C:\docs"),
            Path(r"C:\out"),
        ]


class TestResolveAllowedExtensions:
    DEFAULT: set[str] = {".md", ".txt"}

    def test_unset_env_returns_the_default_object(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("MCP_ALLOWED_EXTENSIONS", raising=False)
        assert resolve_allowed_extensions(self.DEFAULT) is self.DEFAULT

    def test_whitespace_only_env_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("MCP_ALLOWED_EXTENSIONS", "   ")
        assert resolve_allowed_extensions(self.DEFAULT) == self.DEFAULT

    def test_dotted_value_is_kept(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("MCP_ALLOWED_EXTENSIONS", ".md,.txt")
        assert resolve_allowed_extensions(self.DEFAULT) == {".md", ".txt"}

    def test_undotted_value_gets_a_leading_dot(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("MCP_ALLOWED_EXTENSIONS", "md,txt")
        assert resolve_allowed_extensions(self.DEFAULT) == {".md", ".txt"}

    def test_whitespace_and_empty_fragments_are_dropped(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("MCP_ALLOWED_EXTENSIONS", " .md ,, .txt ")
        assert resolve_allowed_extensions(self.DEFAULT) == {".md", ".txt"}

    def test_custom_env_var_name_is_honoured(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("OMNI_CUSTOM_EXTENSIONS", "zzz")
        assert resolve_allowed_extensions(
            self.DEFAULT, env_var="OMNI_CUSTOM_EXTENSIONS"
        ) == {".zzz"}
