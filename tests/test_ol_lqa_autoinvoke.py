"""Test OL LQA auto-invoke feature.

When enable_lqa=True in config, _translate_md_async wraps the translate
call in RetryManager + JudgeService for best-of-N retry. When enable_lqa=False
(default), the original single-translate-call behavior is preserved.

TODO: Extend coverage to _translate_xliff_async (per-unit retry) and
MCP tools (translate_md_text / translate_xliff).
"""

import asyncio
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# All LQA tests in this module use MagicMock/AsyncMock for both the LLM pool
# and the JudgeService seam, so they run in regular CI (no API keys needed).


def _write_config(tmp_path: Path, *, enable_lqa: bool, threshold: float = 7.0, max_retries: int = 2) -> Path:
    """Write a minimal ProjectConfig YAML file for testing."""
    config = textwrap.dedent(f"""\
        project_id: "test"
        source_lang: "en"
        target_lang: "zh"
        enable_lqa: {str(enable_lqa).lower()}
        lqa_threshold: {threshold}
        lqa_max_retries: {max_retries}
        max_md_concurrent: 1
        llm_pool:
          translation:
            - provider: "openai"
              model: "gpt-4o-mini"
              priority: 1
              role: "translation"
              api_key: "sk-test-key"
            - provider: "anthropic"
              model: "claude-3-haiku"
              priority: 2
              role: "translation"
              api_key: "sk-test-key"
          judging:
            - provider: "openai"
              model: "gpt-4o-mini"
              priority: 1
              role: "judging"
              api_key: "sk-test-key"
            - provider: "anthropic"
              model: "claude-3-haiku"
              priority: 2
              role: "judging"
              api_key: "sk-test-key"
          restoration:
            - provider: "openai"
              model: "gpt-4o-mini"
              priority: 1
              role: "restoration"
              api_key: "sk-test-key"
            - provider: "anthropic"
              model: "claude-3-haiku"
              priority: 2
              role: "restoration"
              api_key: "sk-test-key"
    """)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config, encoding="utf-8")
    return config_path


def _write_input_md(tmp_path: Path, content: str = "# Test\n\nHello world.") -> Path:
    """Write a simple markdown file for translation."""
    md_path = tmp_path / "input.md"
    md_path.write_text(content, encoding="utf-8")
    return md_path


def _mock_pool_with_translations(translations: list[str]) -> MagicMock:
    """Create a mock ModelPool whose .translate returns successive translations."""
    pool = MagicMock()
    pool.translate = AsyncMock(side_effect=translations)
    return pool


def _mock_judge_with_scores(scores: list[float]) -> MagicMock:
    """Create a mock JudgeService whose .judge returns successive scores."""
    from ol_core.dataclass import EvaluationResult

    def make_result(score: float) -> EvaluationResult:
        return EvaluationResult(
            unit_id="test_unit",
            judge_scores={
                "adequacy": score,
                "fluency": score,
                "terminology_consistency": score,
                "format_preservation": score,
            },
        )

    judge = MagicMock()
    judge.judge = AsyncMock(side_effect=[make_result(s) for s in scores])
    return judge


def _run_translate_md_async(
    *,
    config_path: Path,
    input_path: Path,
    output_dir: Path,
    pool: MagicMock,
    judge: MagicMock | None = None,
) -> str:
    """Run _translate_md_async with mocked pool (and optionally judge).

    NOTE: _translate_md_async uses _FakeModelPool when OMNI_TEST_FAKE_LLM=1
    (which is the default in CI), so we patch _FakeModelPool rather than
    the real ModelPool.
    """
    from ol_cli import _translate_md_async

    output_dir.mkdir(parents=True, exist_ok=True)

    if judge is not None:
        with patch("ol_pool.fake._FakeModelPool") as MockFP, \
             patch("ol_lqa.judge.JudgeService", return_value=judge):
            MockFP.return_value = pool
            return asyncio.run(_translate_md_async(
                input_path=input_path,
                output_path=output_dir,
                config_path=str(config_path),
                src_lang="en",
                tgt_lang="zh",
                add_frontmatter=False,
            ))
    else:
        with patch("ol_pool.fake._FakeModelPool") as MockFP:
            MockFP.return_value = pool
            return asyncio.run(_translate_md_async(
                input_path=input_path,
                output_path=output_dir,
                config_path=str(config_path),
                src_lang="en",
                tgt_lang="zh",
                add_frontmatter=False,
            ))


class TestOLLQAAutoInvoke:
    def test_lqa_disabled_by_default_single_translate_call(self, tmp_path: Path):
        """When enable_lqa=False (default), pool.translate is called exactly once
        and the result is used directly without retry."""
        config_path = _write_config(tmp_path, enable_lqa=False)
        md_path = _write_input_md(tmp_path)
        pool = _mock_pool_with_translations(["# Test\n\n你好世界。"])

        result = _run_translate_md_async(
            config_path=config_path,
            input_path=md_path,
            output_dir=tmp_path / "out",
            pool=pool,
        )

        assert pool.translate.call_count == 1, (
            f"Expected 1 translate call (no LQA retry), got {pool.translate.call_count}"
        )
        assert "你好世界" in Path(result).read_text(encoding="utf-8")

    def test_lqa_enabled_passes_first_attempt_no_retry(self, tmp_path: Path):
        """When enable_lqa=True and first judge score >= threshold, no retry."""
        config_path = _write_config(tmp_path, enable_lqa=True, threshold=7.0, max_retries=2)
        md_path = _write_input_md(tmp_path)
        pool = _mock_pool_with_translations([
            "# Test\n\n你好。",  # First (and only) translation
        ])
        judge = _mock_judge_with_scores([8.0])  # Above threshold

        result = _run_translate_md_async(
            config_path=config_path,
            input_path=md_path,
            output_dir=tmp_path / "out",
            pool=pool,
            judge=judge,
        )

        assert pool.translate.call_count == 1, (
            f"Expected 1 translate call (first attempt passed), got {pool.translate.call_count}"
        )
        assert judge.judge.call_count == 1

    def test_lqa_enabled_retries_when_score_below_threshold(self, tmp_path: Path):
        """When enable_lqa=True and first judge score < threshold, retry happens."""
        config_path = _write_config(
            tmp_path, enable_lqa=True, threshold=7.0, max_retries=2
        )
        md_path = _write_input_md(tmp_path)
        pool = _mock_pool_with_translations([
            "# Test\n\nattempt1",  # First attempt (bad)
            "# Test\n\nattempt2",  # Second attempt (still bad)
            "# Test\n\nattempt3",  # Third attempt (best, also bad)
        ])
        judge = _mock_judge_with_scores([5.0, 6.0, 6.5])  # All below 7.0

        result = _run_translate_md_async(
            config_path=config_path,
            input_path=md_path,
            output_dir=tmp_path / "out",
            pool=pool,
            judge=judge,
        )

        assert pool.translate.call_count == 3, (
            f"Expected 3 translate calls (initial + 2 retries), got {pool.translate.call_count}"
        )
        assert judge.judge.call_count == 3
        # Best translation (attempt3 with score 6.5) should be in output
        assert "attempt3" in Path(result).read_text(encoding="utf-8")

    def test_lqa_enabled_returns_best_of_n(self, tmp_path: Path):
        """When the 2nd retry scores above threshold, retry returns immediately."""
        config_path = _write_config(
            tmp_path, enable_lqa=True, threshold=7.0, max_retries=3
        )
        md_path = _write_input_md(tmp_path)
        pool = _mock_pool_with_translations([
            "# Test\n\nattempt1",
            "# Test\n\nattempt2",
        ])
        judge = _mock_judge_with_scores([4.0, 9.0])

        result = _run_translate_md_async(
            config_path=config_path,
            input_path=md_path,
            output_dir=tmp_path / "out",
            pool=pool,
            judge=judge,
        )

        assert pool.translate.call_count == 2
        assert "attempt2" in Path(result).read_text(encoding="utf-8")

    def test_lqa_enabled_all_attempts_fail_uses_best_of_n(self, tmp_path: Path):
        """When all attempts fail, the best-scored translation is used (best-of-N)."""
        config_path = _write_config(
            tmp_path, enable_lqa=True, threshold=7.0, max_retries=3
        )
        md_path = _write_input_md(tmp_path)
        pool = _mock_pool_with_translations([
            "# Test\n\nattempt1",
            "# Test\n\nattempt2",
            "# Test\n\nattempt3",
            "# Test\n\nattempt4",
        ])
        judge = _mock_judge_with_scores([4.0, 6.5, 5.0, 6.0])

        result = _run_translate_md_async(
            config_path=config_path,
            input_path=md_path,
            output_dir=tmp_path / "out",
            pool=pool,
            judge=judge,
        )

        assert pool.translate.call_count == 4
        assert "attempt2" in Path(result).read_text(encoding="utf-8")

    def test_lqa_max_retries_zero_equivalent_to_disabled(self, tmp_path: Path):
        """When max_retries=0, only 1 attempt is made (initial)."""
        config_path = _write_config(
            tmp_path, enable_lqa=True, threshold=7.0, max_retries=0
        )
        md_path = _write_input_md(tmp_path)
        pool = _mock_pool_with_translations([
            "# Test\n\nonly_attempt",
        ])
        judge = _mock_judge_with_scores([5.0])  # Below threshold but no retry

        result = _run_translate_md_async(
            config_path=config_path,
            input_path=md_path,
            output_dir=tmp_path / "out",
            pool=pool,
            judge=judge,
        )

        assert pool.translate.call_count == 1, (
            f"Expected 1 translate call (max_retries=0 = no retry), got {pool.translate.call_count}"
        )

    def test_lqa_enabled_with_all_good_scores_no_retry(self, tmp_path: Path):
        """When enable_lqa=True and all scores are high, retry never happens."""
        config_path = _write_config(
            tmp_path, enable_lqa=True, threshold=7.0, max_retries=5
        )
        md_path = _write_input_md(tmp_path)
        pool = _mock_pool_with_translations([
            "# Test\n\nonly_attempt",
        ])
        judge = _mock_judge_with_scores([9.0])  # High score, no retry needed

        result = _run_translate_md_async(
            config_path=config_path,
            input_path=md_path,
            output_dir=tmp_path / "out",
            pool=pool,
            judge=judge,
        )

        assert pool.translate.call_count == 1
        assert judge.judge.call_count == 1
