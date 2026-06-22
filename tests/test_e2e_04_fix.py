"""RED test for E2E-04 root cause: ol_terminology.extractor module-level import hangs.

This test verifies that importing ol_terminology.extractor does NOT trigger
sentence-transformers model preload at module load time. The original code
has `from keybert import KeyBERT` at line 7, which hangs in any environment
that doesn't have a pre-downloaded model.

The fix should be either:
1. Move the import inside the function (lazy)
2. Add a try/except that gracefully degrades if KeyBERT is not installed
3. Catch the hang in some way (e.g., timeout on the import)

This test fails with the current code because import times out.
"""
import subprocess
import time
from pathlib import Path



class TestE204ExtractorImport:
    """Verify ol_terminology.extractor doesn't hang at import time."""

    def test_extractor_import_completes_within_10_seconds(self, tmp_path):
        """The import of ol_terminology.extractor must NOT hang on model preload.

        This is the RED test for E2E-04. The original code (extractor.py)
        had `from keybert import KeyBERT` at module level, which triggered
        sentence-transformers model download/preload and hung in any
        environment that doesn't have the model cached.
        """
        script = """
import sys
import time
t0 = time.time()
try:
    import ol_terminology.extractor
    elapsed = time.time() - t0
    print(f"IMPORT_OK elapsed={elapsed:.2f}")
    sys.exit(0)
except Exception as e:
    elapsed = time.time() - t0
    print(f"IMPORT_FAIL elapsed={elapsed:.2f} error={type(e).__name__}: {e}")
    sys.exit(1)
"""
        script_file = tmp_path / "test_extractor_import.py"
        script_file.write_text(script)

        repo_root = Path("/mnt/d/贯维/Omni_Suite")
        venv_python = repo_root / ".venv_ol" / "bin" / "python"
        ol_src = repo_root / "Omni_Localizer" / "src"

        start = time.time()
        result = subprocess.run(
            [
                str(venv_python),
                str(script_file),
            ],
            cwd=str(repo_root),
            env={
                **__import__("os").environ,
                "PYTHONPATH": str(ol_src),
            },
            capture_output=True,
            text=True,
            timeout=10,  # Must complete in 10s; original code hangs >30s
        )
        elapsed = time.time() - start

        # Combine stdout and stderr for diagnostic
        output = (result.stdout + "\n" + result.stderr).strip()

        assert result.returncode == 0, (
            f"ol_terminology.extractor import failed or timed out "
            f"after {elapsed:.1f}s. Output:\n{output}\n"
            f"Root cause: extractor.py previously had 'from keybert import KeyBERT' "
            f"at module top level, which triggered sentence-transformers "
            f"model preload and hung. The fix uses lazy imports via _probe_keybert()."
        )

    def test_ol_cli_translate_xliff_produces_output(self, tmp_path):
        """Running ol translate-xliff on a minimal XLIFF must produce an output file.

        The original E2E-04 bug: CLI exits 0 but produces no output file.
        This is the SURFACE test: invoke the actual CLI, verify output exists.
        """
        # Create a minimal 3-unit XLIFF
        xlf = tmp_path / "test.xlf"
        xlf.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file source-language="en" target-language="zh" datatype="plaintext">
    <body>
      <trans-unit id="1">
        <source>Hello World</source>
        <target state="new"></target>
      </trans-unit>
      <trans-unit id="2">
        <source>Press the button to continue</source>
        <target state="new"></target>
      </trans-unit>
      <trans-unit id="3">
        <source>The quick brown fox</source>
        <target state="new"></target>
      </trans-unit>
    </body>
  </file>
</xliff>
""")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        repo_root = Path("/mnt/d/贯维/Omni_Suite")
        venv_python = repo_root / ".venv_ol" / "bin" / "python"

        result = subprocess.run(
            [
                str(venv_python),
                "-m", "ol_cli",
                "translate-xliff",
                str(xlf),
                "--config", str(repo_root / "Omni_Localizer" / "config" / "default.yaml"),
                "-s", "en", "-t", "zh",
                "-o", str(out_dir),
            ],
            cwd=str(repo_root),
            env={
                **__import__("os").environ,
                "OMNI_TEST_FAKE_LLM": "1",
                "OL_CONFIG_PATH": str(repo_root / "Omni_Localizer" / "config" / "default.yaml"),
                # Dummy API keys to satisfy config validation (FAKE_LLM ignores them)
                "ZHIPU_API_KEY": "sk-dummy",
                "AGNES_API_KEY": "sk-dummy",
                "NVIDIA_NIM_API_KEY": "nvapi-dummy",
                "BAIDU_API_KEY": "sk-dummy",
                "BAIDU_SECRET_KEY": "sk-dummy",
                "OPENAI_API_KEY": "sk-dummy",
                "ANTHROPIC_API_KEY": "sk-dummy",
                "MINIMAX_API_KEY": "sk-dummy",
                "MINIMAX_BASE_URL": "http://localhost:8080/v1",
            },
            capture_output=True,
            text=True,
            timeout=90,
        )

        output_file = out_dir / "test.xlf"
        assert output_file.exists(), (
            f"ol translate-xliff produced no output file at {output_file}. "
            f"Exit code: {result.returncode}. "
            f"Stdout: {result.stdout[:500]}. "
            f"Stderr: {result.stderr[:500]}. "
            f"This is the actual E2E-04 bug (different from report)."
        )

        output_content = output_file.read_text(encoding="utf-8")
        import re
        target_matches = re.findall(r"<target(?:\s+[^>]*)?>([^<]*)</target>", output_content)
        empty_targets = [t for t in target_matches if not t.strip()]
        assert len(target_matches) >= 3, (
            f"Expected at least 3 <target> elements (one per trans-unit), got {len(target_matches)}. "
            f"Output: {output_content[:500]}"
        )
        assert not empty_targets, (
            f"Found {len(empty_targets)} empty <target> elements (E2E-04 symptom). "
            f"Empty targets: {empty_targets}. "
            f"Full output: {output_content}"
        )
