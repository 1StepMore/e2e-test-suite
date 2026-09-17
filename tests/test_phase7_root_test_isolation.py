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

    def test_security_platform_scoping_is_explicit(self):
        """test_security.py 的平台门必须「显式限定 + 有反向补位用例」。

        2026-07-03 的 P7-T1 追求「失败可见」，把 ``skipif(os.name == "nt")`` 换成
        了 ``xfail(os.name != "nt")`` —— 但方向写反了。该用例的参数全是 POSIX
        目录（``/etc``/``/usr``/``/var``/``/System``/``/Library``，见
        ``opp/utils/security.py`` 的 SYSTEM_DIRS），它们在 POSIX 上**本就该通过**，
        于是 marker 在 POSIX 上把通过标成 XPASS（默认 strict=False 不计失败，只是
        噪音），在 Windows 上反而失效。OPP 已于 2026-09-17（commit 3f92ee0）改为
        平台反向跳过，并保留 ``test_windows_paths_on_unix`` 覆盖 Windows 盘符形态。

        本用例从此守真正的不变量，而不是 marker 的名字：
        (1) 方向写反的平台 xfail 不得回归；(2) 被跳过的平台必须有补位用例 ——
        即 P7-T1 真正要防的「用跳过把覆盖悄悄抹掉」，而不是「必须叫 xfail」。
        """
        test_file = REPO_ROOT / "Omni_Pre_Processor" / "tests" / "mcp" / "test_security.py"
        if not test_file.exists():
            pytest.skip(f"File not found (sub-repo not cloned?): {test_file}")

        content = test_file.read_text(encoding="utf-8")
        # 只检查**生效的 marker 行**：OPP 的 docstring 会引用旧写法作为说明
        # （"这里原本是 xfail(os.name != "nt", ...)"），按整文件子串匹配会误伤。
        marker_lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip().startswith("@pytest.mark.xfail")
        ]
        assert not any('os.name != "nt"' in line for line in marker_lines), (
            "test_security.py: 方向写反的平台 xfail 回归了 —— POSIX 参数在 POSIX 上"
            "本应通过（恒 XPASS），而 Windows 上 marker 失效。\n"
            + "\n".join(marker_lines)
        )
        assert "def test_windows_paths_on_unix" in content, (
            "test_security.py: POSIX 目录用例在 Windows 上被跳过，必须保留 "
            "test_windows_paths_on_unix 覆盖 Windows 盘符形态 —— 跳过不等于放弃覆盖。"
        )
        if "@pytest.mark.skipif" in content:
            assert 'os.name == "nt"' in content, (
                "test_security.py: skipif 必须是显式的平台限定（os.name == \"nt\"），"
                "不得无条件跳过。"
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
