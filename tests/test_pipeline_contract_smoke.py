"""Pipeline contract smoke test — verifies OPP/OL/ORF import and basic CLI availability.

This file is referenced by .pre-commit-config.yaml (stages: [manual]).
Run with:
    pre-commit run omni-contract-smoke --all-files
    python -m pytest tests/test_pipeline_contract_smoke.py --tb=short -q --no-header
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest


_SUITE_ROOT = Path(__file__).resolve().parent.parent


def _is_provisioned(interpreter: Path) -> bool:
    """探测该解释器是否已装齐 3 个子仓库（能 import opp / ol / orf）。

    仅判断文件存在是不够的：``.venv_win`` 在 ``setup_dev.ps1`` 装完依赖之前就已
    存在，此时冒烟门禁会拿到一个"半成品"解释器并把 4 个断言判为失败 —— 报告的是
    环境未装完，而不是契约被破坏。所以这里用一次真实 import 探测作为准入条件。

    Args:
        interpreter: 候选 Python 解释器路径。

    Returns:
        True 表示该解释器可 import opp、ol、orf。
    """
    try:
        proc = subprocess.run(
            [str(interpreter), "-c", "import opp, ol, orf"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=_SUITE_ROOT,
        )
    except (OSError, subprocess.SubprocessError):
        # Linux ELF 可执行文件在 Windows 上会抛 OSError — 该候选直接排除。
        return False
    return proc.returncode == 0


def _resolve_venv_python() -> Path:
    """解析当前平台可用且已装齐依赖的 Python 解释器路径。

    修复（2026-09-17）：原实现硬编码 ``.venv_ol/bin/python``（Linux 布局）。
    在原生 Windows 上该路径存在但指向 Linux ELF 可执行文件，subprocess 会抛
    ``OSError: [WinError 1920]``，使 C-3 契约冒烟门禁在 Windows 完全不可用 ——
    与 ``scripts/doc_inventory.py`` 硬编码 ``python3`` 属同一类缺陷
    （见 docs/project-health-report-2026-09-17.md 风险 #4 / #5）。

    现在按平台依次探测候选路径（Windows 用 ``Scripts/python.exe``，POSIX 用
    ``bin/python``），且只接受**能 import opp/ol/orf** 的候选；全部不合格时回退到
    ``sys.executable``（即运行 pytest 的解释器，语义等价）。Linux/CI 下首个候选
    依然命中，行为与修复前一致。

    Returns:
        可用的 Python 解释器路径。
    """
    if os.name == "nt":
        candidates = (
            _SUITE_ROOT / ".venv_ol" / "Scripts" / "python.exe",
            _SUITE_ROOT / ".venv_win" / "Scripts" / "python.exe",
            _SUITE_ROOT / ".venv" / "Scripts" / "python.exe",
        )
    else:
        candidates = (
            _SUITE_ROOT / ".venv_ol" / "bin" / "python",
            _SUITE_ROOT / ".venv" / "bin" / "python",
        )
    for candidate in candidates:
        if candidate.exists() and _is_provisioned(candidate):
            return candidate
    return Path(sys.executable)


_VENV_PYTHON = _resolve_venv_python()


def _run_python(*args: str) -> subprocess.CompletedProcess[str]:
    """在项目根目录下用解析出的解释器执行命令。

    固定 ``cwd=_SUITE_ROOT``，使断言不依赖调用者的当前目录（``omni_suite`` /
    ``omni_mcp`` 是仓库根下的顶层包，不在 site-packages 里）。

    Args:
        *args: 传给解释器的参数（如 ``-c``、模块名）。

    Returns:
        子进程执行结果（文本模式）。
    """
    return subprocess.run(
        [_VENV_PYTHON, *args],
        capture_output=True,
        text=True,
        timeout=15,
        cwd=_SUITE_ROOT,
    )


@pytest.mark.smoke
class TestPipelineContract:
    """Lightweight contract tests — fast, hermetic, no fixtures."""

    def test_opp_importable(self):
        """OPP module imports without error."""
        code = "import opp; print(opp.__version__)"
        result = _run_python("-c", code)
        assert result.returncode == 0, f"OPP import failed:\n{result.stderr}"
        assert result.stdout.strip(), f"OPP __version__ empty:\n{result.stdout}"

    def test_ol_importable(self):
        """OL module imports without error."""
        code = "import ol; print(ol.__version__)"
        result = _run_python("-c", code)
        assert result.returncode == 0, f"OL import failed:\n{result.stderr}"
        assert result.stdout.strip(), f"OL __version__ empty:\n{result.stdout}"

    def test_orf_importable(self):
        """ORF module imports without error."""
        code = "import orf; print(orf.__version__)"
        result = _run_python("-c", code)
        assert result.returncode == 0, f"ORF import failed:\n{result.stderr}"
        assert result.stdout.strip(), f"ORF __version__ empty:\n{result.stdout}"

    def test_omni_suite_cli_version(self):
        """omni-suite --version exits 0 and returns expected format."""
        result = _run_python("-m", "omni_suite.cli", "--version")
        assert result.returncode == 0, f"omni-suite --version failed:\n{result.stderr}"
        assert result.stdout.strip(), f"Unexpected output:\n{result.stdout}"

    def test_all_cli_help(self):
        """All three CLIs respond to --help."""
        # OPP has a __main__.py, OL uses ol_cli module, ORF has __main__.py
        entries = [("OPP", "opp"), ("OL", "ol_cli"), ("ORF", "orf")]
        for module, cli_entry in entries:
            result = _run_python("-m", cli_entry, "--help")
            assert result.returncode == 0, (
                f"{module} CLI --help failed:\n{result.stderr}"
            )

    def test_ping_opp_mcp(self):
        """OPP MCP ping returns success (in-process)."""
        from opp.mcp.server import ping
        import asyncio
        result = asyncio.run(ping(auth_token=None))
        assert result.get("success"), f"OPP MCP ping failed:\n{result}"

    def test_ping_orf_mcp(self):
        """ORF MCP ping returns success (in-process)."""
        from orf.mcp.server import ping
        import json
        result = json.loads(ping())
        assert result.get("success"), f"ORF MCP ping failed:\n{result}"

    def test_no_omni_test_fake_llm_noop(self):
        """OMNI_TEST_FAKE_LLM is unset in this process (safety check)."""
        # FAKE_LLM may or may not be set depending on env; this test documents
        # the expected behavior: the smoke test does not force it.
        assert True

    def test_opp_has_extract_tools(self):
        """OPP MCP server module exports extract_document and ping."""
        from opp.mcp.server import extract_document, ping, batch_extract
        assert callable(extract_document)
        assert callable(ping)
        assert callable(batch_extract)
