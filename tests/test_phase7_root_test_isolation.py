"""Tests for Phase 7 test isolation and CI fixes (P7-T1, T2, T3, T4)."""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestP7T1OppSkipsConvertedToXfail:
    """OPP tests with known broken state should use @pytest.mark.xfail, not pytest.skip()."""

    def test_email_extractor_msg_tests_use_xfail(self):
        test_file = REPO_ROOT / "Omni_Pre_Processor" / "tests" / "test_email_extractor.py"
        if not test_file.exists():
            pytest.skip(f"File not found (sub-repo not cloned?): {test_file}")

        content = test_file.read_text(encoding="utf-8")
        assert "@pytest.mark.xfail" in content, (
            "test_email_extractor.py: MSG tests should use @pytest.mark.xfail"
        )
        lines = content.splitlines()
        skip_lines = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if "importorskip" in stripped:
                continue
            if "pytest.skip(" in stripped and not stripped.startswith("#"):
                skip_lines.append(f"  line {i}: {stripped}")
        assert not skip_lines, (
            "test_email_extractor.py still uses pytest.skip():\n"
            + "\n".join(skip_lines)
        )

    def test_audio_extractor_integration_uses_xfail(self):
        test_file = REPO_ROOT / "Omni_Pre_Processor" / "tests" / "test_audio_extractor.py"
        if not test_file.exists():
            pytest.skip(f"File not found (sub-repo not cloned?): {test_file}")

        content = test_file.read_text(encoding="utf-8")
        assert "@pytest.mark.xfail" in content, (
            "test_audio_extractor.py: integration test should use @pytest.mark.xfail"
        )
        lines = content.splitlines()
        skip_lines = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if "importorskip" in stripped:
                continue
            if "pytest.skip(" in stripped and not stripped.startswith("#"):
                skip_lines.append(f"  line {i}: {stripped}")
        assert not skip_lines, (
            "test_audio_extractor.py still uses pytest.skip():\n"
            + "\n".join(skip_lines)
        )

    def test_contracts_module_level_skip_uses_xfail(self):
        test_file = REPO_ROOT / "Omni_Pre_Processor" / "tests" / "test_opp_ol_orf_contracts.py"
        if not test_file.exists():
            pytest.skip(f"File not found (sub-repo not cloned?): {test_file}")

        content = test_file.read_text(encoding="utf-8")
        assert "pytestmark" in content and "xfail" in content, (
            "test_opp_ol_orf_contracts.py: module-level pytest.skip() should be "
            "replaced with pytestmark = pytest.mark.xfail(...)"
        )
        assert "pytest.skip(" not in content.split("def ")[0], (
            "test_opp_ol_orf_contracts.py: module-level pytest.skip() still present"
        )

    def test_security_windows_test_uses_xfail(self):
        test_file = REPO_ROOT / "Omni_Pre_Processor" / "tests" / "mcp" / "test_security.py"
        if not test_file.exists():
            pytest.skip(f"File not found (sub-repo not cloned?): {test_file}")

        content = test_file.read_text(encoding="utf-8")
        assert "@pytest.mark.xfail" in content, (
            "test_security.py: test_system_dirs_blocked should use @pytest.mark.xfail"
        )
        assert "@pytest.mark.skipif" not in content, (
            "test_security.py: @pytest.mark.skipif should be converted to @pytest.mark.xfail"
        )


def test_p7_t2_e2e_tests_yml_no_baudu_typo():
    workflow = REPO_ROOT / ".github" / "workflows" / "e2e-tests.yml"
    content = workflow.read_text(encoding="utf-8")
    assert "BAUDU" not in content, (
        f"{workflow} contains 'BAUDU' typo (should be 'BAIDU')."
    )


def test_p7_t3_test_ci_no_submodules_includes_all_workflows():
    test_file = REPO_ROOT / "tests" / "test_ci_no_submodules.py"
    content = test_file.read_text(encoding="utf-8")
    required = ["contract-tests", "e2e-tests", "doctor", "hardening-tests", "fidelity"]
    missing = [wf for wf in required if wf not in content]
    assert not missing, (
        f"test_ci_no_submodules.py is missing workflows: {missing}. "
        "All 5 CI workflows should be checked."
    )


def test_p7_t4_e2e_tests_venv_ol_symlink_after_uv_sync():
    workflow = REPO_ROOT / ".github" / "workflows" / "e2e-tests.yml"
    content = workflow.read_text(encoding="utf-8")

    uv_sync_positions = [m.start() for m in re.finditer(r"uv sync", content)]
    symlink_positions = [m.start() for m in re.finditer(r"ln -s \.venv \.venv_ol", content)]

    if not uv_sync_positions:
        pytest.skip("No 'uv sync' found in e2e-tests.yml")
    if not symlink_positions:
        pytest.skip("No 'ln -s .venv .venv_ol' found in e2e-tests.yml")

    for syn_pos in symlink_positions:
        preceding_syncs = [p for p in uv_sync_positions if p < syn_pos]
        assert preceding_syncs, (
            f"e2e-tests.yml: '.venv_ol' symlink at char {syn_pos} has no "
            "preceding 'uv sync'. Symlink must come after uv sync."
        )
        nearest_sync = preceding_syncs[-1]
        sync_line = content[:nearest_sync].count("\n") + 1
        symlink_line = content[:syn_pos].count("\n") + 1
        assert syn_pos > nearest_sync, (
            f"e2e-tests.yml: '.venv_ol' symlink (line ~{symlink_line}) "
            f"is BEFORE 'uv sync' (line ~{sync_line}). "
            "Symlink must be created after uv sync."
        )
