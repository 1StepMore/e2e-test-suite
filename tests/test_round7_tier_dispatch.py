"""Round 7 tests — verify the tier-dispatch reuse architecture works
without breaking existing behavior.

Coverage:
- tests/e2e_runner.py: --input, --source-lang, --target-lang flags
  accepted (default = backward compatible)
- scripts/omo_loop.py: --tier {1,2,3,4,5} CLI flag accepted
- Tier 1 = default behavior unchanged
- Tier 2 = e2e_runner.py invocation wiring (mock subprocess)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


_SUITE_ROOT = Path(__file__).resolve().parents[1]
_E2E_RUNNER = _SUITE_ROOT / "tests" / "e2e_runner.py"
_OMO_LOOP = _SUITE_ROOT / "scripts" / "omo_loop.py"
_PHASE1 = _SUITE_ROOT / "scripts" / "phase1_runner.py"


def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a command and return CompletedProcess."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


class TestE2ERunnerCLIArgs:
    """tests/e2e_runner.py: --input, --source-lang, --target-lang."""

    def test_help_shows_new_flags(self):
        """--input/--source-lang/--target-lang must appear in --help."""
        result = _run([sys.executable, str(_E2E_RUNNER), "--help"])
        assert "--input INPUT" in result.stdout, (
            f"--input flag missing from e2e_runner.py help:\n{result.stdout}"
        )
        assert "--source-lang" in result.stdout, "--source-lang missing"
        assert "--target-lang" in result.stdout, "--target-lang missing"

    def test_main_signature_accepts_lang_params(self):
        """main() must accept input_path, source_lang, target_lang kwargs."""
        # Import with PYTHONPATH set so tests/ can resolve component imports
        import os
        env = os.environ.copy()
        env["PYTHONPATH"] = ":".join([
            str(_SUITE_ROOT / "Omni_Pre_Processor" / "src"),
            str(_SUITE_ROOT / "Omni_Localizer" / "src"),
            str(_SUITE_ROOT / "Omni_Re_Formatter" / "src"),
        ])
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, 'tests'); "
             "import e2e_runner; "
             "import inspect; sig = inspect.signature(e2e_runner.main); "
             "assert 'source_lang' in sig.parameters; "
             "assert 'target_lang' in sig.parameters; "
             "assert 'input_path' in sig.parameters; "
             "print('OK')"],
            capture_output=True, text=True, env=env, cwd=str(_SUITE_ROOT),
            timeout=15,
        )
        assert result.returncode == 0, (
            f"e2e_runner.main() signature test failed:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


class TestOmoLoopTierDispatch:
    """scripts/omo_loop.py: --tier CLI dispatch."""

    def test_help_shows_tier_flag(self):
        result = _run([sys.executable, str(_OMO_LOOP), "--help"])
        assert "--tier {1,2,3,4,5}" in result.stdout, (
            f"--tier missing from omo_loop.py help:\n{result.stdout}"
        )

    def test_tier_2_invokes_e2e_runner(self, monkeypatch):
        """Tier 2 should call tests/e2e_runner.py with --input + langs."""
        from scripts.omo_loop import _run_tier_2

        # Mock subprocess.run to capture the cmd
        captured = {}
        def mock_run(cmd, env=None, **kwargs):
            captured["cmd"] = cmd
            captured["env"] = env
            class R: returncode = 0
            return R()
        monkeypatch.setattr("subprocess.run", mock_run)

        # Build a fake args namespace
        from argparse import Namespace
        args = Namespace(
            input=Path("/tmp/fake.docx"),
            source_lang="en",
            target_lang="zh",
            config=None,
            use_mock=False,
        )
        _run_tier_2(args)
        cmd = captured["cmd"]
        # Must include e2e_runner.py
        assert any("e2e_runner.py" in c for c in cmd), f"e2e_runner.py missing: {cmd}"
        # Must include --input + --source-lang + --target-lang
        assert "--input" in cmd and "/tmp/fake.docx" in cmd, f"--input missing: {cmd}"
        assert "--source-lang" in cmd and "en" in cmd, f"--source-lang missing: {cmd}"
        assert "--target-lang" in cmd and "zh" in cmd, f"--target-lang missing: {cmd}"

    def test_tier_3_invokes_phase1_p1(self, monkeypatch):
        """Tier 3 should call phase1_runner.py with --tier P1."""
        from scripts.omo_loop import _run_tier_3

        captured = {}
        def mock_run(cmd, env=None, **kwargs):
            captured["cmd"] = cmd
            class R: returncode = 0
            return R()
        monkeypatch.setattr("subprocess.run", mock_run)

        from argparse import Namespace
        args = Namespace(
            input=Path("/tmp/fake.docx"),
            source_lang="zh",
            target_lang="en",
        )
        _run_tier_3(args)
        cmd = captured["cmd"]
        assert any("phase1_runner.py" in c for c in cmd), f"phase1_runner.py missing: {cmd}"
        assert "--tier" in cmd and "P1" in cmd, f"--tier P1 missing: {cmd}"

    def test_tier_4_invokes_phase1_p2(self, monkeypatch):
        """Tier 4 should call phase1_runner.py with --tier P2."""
        from scripts.omo_loop import _run_tier_4

        captured = {}
        def mock_run(cmd, env=None, **kwargs):
            captured["cmd"] = cmd
            class R: returncode = 0
            return R()
        monkeypatch.setattr("subprocess.run", mock_run)

        from argparse import Namespace
        args = Namespace(input=Path("/tmp/fake.docx"), source_lang="zh", target_lang="en")
        _run_tier_4(args)
        cmd = captured["cmd"]
        assert "P2" in cmd, f"--tier P2 missing: {cmd}"

    def test_tier_5_runs_three_modules(self, monkeypatch):
        """Tier 5 should run pytest on module-specific test files.

        Round 11 v2: switched from run_test.sh to pytest. run_test.sh
        --module is not actually module-only (assumes OPP ran first),
        so Tier 5 now invokes the per-module pytest suites directly.
        """
        from scripts.omo_loop import _run_tier_5

        calls = []
        def mock_run(cmd, env=None, **kwargs):
            calls.append(cmd)
            class R: returncode = 0
            return R()
        monkeypatch.setattr("subprocess.run", mock_run)

        from argparse import Namespace
        args = Namespace(input=Path("/tmp/fake.docx"), source_lang="zh", target_lang="en")
        _run_tier_5(args)
        assert len(calls) == 6, f"Expected 6 pytest runs; got {len(calls)}"
        for cmd in calls:
            assert "pytest" in cmd, f"Not a pytest call: {cmd}"
        flat = " ".join(" ".join(c) for c in calls)
        assert "test_e2e_opp_all_formats.py" in flat
        assert "test_e2e_opp_cli.py" in flat
        assert "test_e2e_ol_cli.py" in flat
        assert "test_e2e_ol_mcp.py" in flat
        assert "test_e2e_orf_cli.py" in flat
        assert "test_e2e_orf_mcp.py" in flat