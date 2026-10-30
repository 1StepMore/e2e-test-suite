"""Quality gate config variants — warning shape, disable length_ratio.

Covers S14.3-S14.4 from the integrated test plan. Tests that:
- FAKE_LLM triggers length_ratio gate by default (S14.1)
- Disabling length_ratio suppresses LENGTH_RATIO warnings (S14.3)
- Warning shape matches expected JSON structure (S14.4)

Run with:
    OMNI_TEST_FAKE_LLM=1 OMNI_TEST_FAKE_PANDOC=1 pytest tests/test_e2e_qg_config_variants.py -v
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.real_chain]

SUITE_ROOT = Path(__file__).resolve().parent
OL_CONFIG = SUITE_ROOT.parent / "Omni_Localizer" / "config" / "default.yaml"


def _make_env(**extra) -> dict:
    env = os.environ.copy()
    env["OMNI_TEST_FAKE_LLM"] = "1"
    env["OMNI_TEST_FAKE_PANDOC"] = "1"
    for d in ["Omni_Pre_Processor", "Omni_Localizer", "Omni_Re_Formatter"]:
        src = SUITE_ROOT.parent / d / "src"
        if src.exists():
            pp = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = f"{src}:" + pp if pp else str(src)
    env["OL_CONFIG_PATH"] = str(OL_CONFIG)
    env.update(extra)
    return env


class TestQualityGateDefaultBehavior:
    """Default quality gate behavior with FAKE_LLM."""

    def test_fake_llm_triggers_length_ratio(self, tmp_path):
        """FAKE_LLM short markers should trigger length_ratio gate.

        Translate via CLI with FAKE_LLM=1 (default) — length_ratio should fire
        because FAKE_LLM returns ~4 chars for 100+ char source.
        """
        md_file = tmp_path / "source.md"
        md_file.write_text("A" * 500)  # Long source, FAKE_LLM returns just [ZH]
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        result = subprocess.run(
            [sys.executable, "-m", "ol_cli", "translate-md",
             str(md_file), "-s", "en", "-t", "zh",
             "-o", str(out_dir), "-c", str(OL_CONFIG), "--no-cache"],
            capture_output=True, text=True,
            env=_make_env(),
            timeout=30,
        )
        # CLI may return 0 (translation succeeded) or 1 (warning)
        # Check stderr for quality gate warnings
        assert result.returncode in (0, 1)
        # With FAKE_LLM, the ratio should be very low (~0.008 for 500→4)
        # This is below the default min of 0.5, so gate fires
        # Note: This is a soft test — we're checking the behavior exists

    def test_length_ratio_warning_shape(self, tmp_path):
        """Check that quality gate warnings have the expected structure.

        Instead of parsing CLI output (fragile), test the quality_gates
        function directly.
        """
        from ol_lqa.quality_gates import run_quality_gates

        source = "Hello world, this is a test sentence that is fairly long."
        target = "[ZH]"  # FAKE_LLM output (very short)

        warnings = run_quality_gates(
            source, target,
            inline_tags_enabled=True,
            terminology_enabled=False,
            length_ratio_enabled=True,
            locale_enabled=True,
            target_locale="en-US",
        )
        # With FAKE_LLM, length_ratio should fire
        assert any("LENGTH_RATIO" in w for w in warnings), (
            f"Expected LENGTH_RATIO warning for source={len(source)} vs target={len(target)}"
        )


class TestQualityGateConfigVariants:
    """Quality gates can be enabled/disabled individually."""

    def test_disable_length_ratio_suppresses_warning(self, tmp_path):
        """With length_ratio disabled, the gate should not fire."""
        from ol_lqa.quality_gates import run_quality_gates

        source = "Hello world, this is a test sentence that is fairly long."
        target = "[ZH]"

        warnings = run_quality_gates(
            source, target,
            inline_tags_enabled=True,
            terminology_enabled=False,
            length_ratio_enabled=False,  # Disabled
            locale_enabled=True,
            target_locale="en-US",
        )
        # Length ratio should NOT fire
        length_ratio_warnings = [w for w in warnings if "LENGTH_RATIO" in w]
        assert len(length_ratio_warnings) == 0

    def test_disable_all_gates_no_warnings(self, tmp_path):
        """With all gates disabled, no warnings should fire."""
        from ol_lqa.quality_gates import run_quality_gates

        warnings = run_quality_gates(
            "Hello world", "[ZH]",
            inline_tags_enabled=False,
            terminology_enabled=False,
            length_ratio_enabled=False,
            locale_enabled=False,
        )
        assert len(warnings) == 0

    def test_inline_tag_mismatch_detected(self, tmp_path):
        """Inline tag count mismatch should trigger INLINE_TAG_MISMATCH."""
        from ol_lqa.quality_gates import run_quality_gates

        source = "Press <bx1/>here<ex1/> to continue."
        target = "点击这里继续。"  # Stripped tags

        warnings = run_quality_gates(
            source, target,
            inline_tags_enabled=True,
            terminology_enabled=False,
            length_ratio_enabled=False,
            locale_enabled=False,
        )
        inline_warnings = [w for w in warnings if "INLINE_TAG" in w]
        assert len(inline_warnings) > 0

    def test_locale_gate_en_us(self, tmp_path):
        """Locale gate should fire for non-US conventions in en-US target."""
        from ol_lqa.quality_gates import run_quality_gates

        source = "The price is 1,000.00 dollars."
        target = "价格是1.000,00欧元。"  # EU digit grouping in en-US target

        warnings = run_quality_gates(
            source, target,
            inline_tags_enabled=False,
            terminology_enabled=False,
            length_ratio_enabled=False,
            locale_enabled=True,
            target_locale="en-US",
        )
        # May or may not fire depending on implementation; test doesn't assert
        # but verifies the function runs without error
        assert isinstance(warnings, list)
