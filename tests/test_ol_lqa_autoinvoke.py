"""Test OL LQA auto-invoke feature.

When enable_lqa=True in config, _translate_md_async wraps the translate
call in RetryManager + JudgeService for best-of-N retry. When enable_lqa=False
(default), the original single-translate-call behavior is preserved.

TODO: Extend coverage to _translate_xliff_async (per-unit retry) and
MCP tools (translate_md_text / translate_xliff).
"""

import asyncio
import os
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# All LQA tests in this module use MagicMock/AsyncMock for both the LLM pool
# and the JudgeService seam, so they run in regular CI (no API keys needed).

# ``# Test\n\nHello world.`` is split into two translatable units by the MD
# extractor: heading ``md_1`` ("Test") and paragraph ``md_2``
# ("Hello world."). ``pool.translate`` is called once per unit per attempt,
# never once per document.
UNITS = 2

_SOURCE_COPY_RETRY_MARKERS = (
    "SOURCE_COPY",
    "retranslation request",
    "上一次输出与源文完全相同",
)


@pytest.fixture(autouse=True)
def _require_fake_llm_seam() -> None:
    """Fail loudly when the FAKE_LLM seam is not active for this module."""
    if os.environ.get("OMNI_TEST_FAKE_LLM") != "1":
        pytest.fail(
            "本地跑本文件必须 OMNI_TEST_FAKE_LLM=1，否则会走真实 ModelPool "
            "并报与本测试无关的 `Router() takes no arguments`"
        )


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
    """Create a mock ModelPool whose .translate returns successive translations.

    Once the list is exhausted the last translation is repeated, so per-unit
    translation (2 units by default) can never raise ``StopAsyncIteration``
    and silently fall back to the source text.
    """
    if not translations:
        raise ValueError("translations must not be empty")
    pool = MagicMock()
    calls = {"index": 0}

    async def _translate(*_args, **_kwargs) -> str:
        index = min(calls["index"], len(translations) - 1)
        calls["index"] += 1
        return translations[index]

    pool.translate = AsyncMock(side_effect=_translate)
    return pool


def _mock_judge_with_scores(scores: list[float]) -> MagicMock:
    """Create a mock JudgeService whose .judge returns successive scores.

    Like the translation fixture, the last score repeats instead of raising
    ``StopAsyncIteration`` when the list is exhausted.
    """
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

    if not scores:
        raise ValueError("scores must not be empty")
    results = [make_result(s) for s in scores]
    calls = {"index": 0}

    async def _judge(*_args, **_kwargs) -> EvaluationResult:
        index = min(calls["index"], len(results) - 1)
        calls["index"] += 1
        return results[index]

    judge = MagicMock()
    judge.judge = AsyncMock(side_effect=_judge)
    return judge


def _assert_no_source_copy_retry(pool: MagicMock) -> None:
    """Assert no translate call carried OL#189's source-copy retry instruction."""
    for call in pool.translate.call_args_list:
        instruction = call.kwargs.get("extra_instruction") or ""
        assert not any(
            marker in instruction for marker in _SOURCE_COPY_RETRY_MARKERS
        ), (
            "pool.translate received a SOURCE_COPY retry instruction; the "
            f"fixture is manufacturing a source-copy retry: {instruction!r}"
        )
        assert instruction == "", (
            "pool.translate received an unexpected extra_instruction: "
            f"{instruction!r}"
        )


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
        """When enable_lqa=False (default), pool.translate is called once per
        unit and the result is used directly without retry."""
        config_path = _write_config(tmp_path, enable_lqa=False)
        md_path = _write_input_md(tmp_path)
        pool = _mock_pool_with_translations(["测试", "你好世界。"])

        result = _run_translate_md_async(
            config_path=config_path,
            input_path=md_path,
            output_dir=tmp_path / "out",
            pool=pool,
        )

        # 2 units × 1 attempt = 2 translate calls
        assert pool.translate.call_count == UNITS, (
            f"Expected {UNITS} translate calls (one per unit, no LQA retry), "
            f"got {pool.translate.call_count}"
        )
        assert "你好世界" in Path(result).read_text(encoding="utf-8")
        _assert_no_source_copy_retry(pool)

    def test_lqa_enabled_passes_first_attempt_no_retry(self, tmp_path: Path):
        """When enable_lqa=True and first judge score >= threshold, no retry."""
        config_path = _write_config(tmp_path, enable_lqa=True, threshold=7.0, max_retries=2)
        md_path = _write_input_md(tmp_path)
        pool = _mock_pool_with_translations(["测试", "你好。"])
        judge = _mock_judge_with_scores([8.0, 8.0])  # Above threshold

        _run_translate_md_async(
            config_path=config_path,
            input_path=md_path,
            output_dir=tmp_path / "out",
            pool=pool,
            judge=judge,
        )

        # 2 units × 1 attempt = 2 translate calls, each judged once
        assert pool.translate.call_count == UNITS, (
            f"Expected {UNITS} translate calls (first attempt passed), "
            f"got {pool.translate.call_count}"
        )
        assert judge.judge.call_count == UNITS
        _assert_no_source_copy_retry(pool)

    def test_lqa_enabled_retries_when_score_below_threshold(self, tmp_path: Path):
        """When enable_lqa=True and first judge score < threshold, retry happens."""
        config_path = _write_config(
            tmp_path, enable_lqa=True, threshold=7.0, max_retries=2
        )
        md_path = _write_input_md(tmp_path)
        pool = _mock_pool_with_translations([
            "单元1尝试1",  # md_1 attempt 1 (bad)
            "单元1尝试2",  # md_1 attempt 2 (still bad)
            "单元1尝试3",  # md_1 attempt 3 (best, also bad)
            "单元2尝试1",  # md_2 attempt 1 (bad)
            "单元2尝试2",  # md_2 attempt 2 (still bad)
            "单元2尝试3",  # md_2 attempt 3 (best, also bad)
        ])
        judge = _mock_judge_with_scores([5.0, 5.5, 6.0, 5.0, 5.5, 6.5])

        result = _run_translate_md_async(
            config_path=config_path,
            input_path=md_path,
            output_dir=tmp_path / "out",
            pool=pool,
            judge=judge,
        )

        # 2 units × (1 initial + 2 retries) = 6
        assert pool.translate.call_count == UNITS * 3, (
            f"Expected {UNITS * 3} translate calls (initial + 2 retries per "
            f"unit), got {pool.translate.call_count}"
        )
        assert judge.judge.call_count == UNITS * 3
        # Each unit's best translation (attempt 3, highest score) is in output.
        output = Path(result).read_text(encoding="utf-8")
        assert "单元1尝试3" in output
        assert "单元2尝试3" in output
        _assert_no_source_copy_retry(pool)

    def test_lqa_enabled_returns_best_of_n(self, tmp_path: Path):
        """When the 2nd attempt scores above threshold, retry returns immediately."""
        config_path = _write_config(
            tmp_path, enable_lqa=True, threshold=7.0, max_retries=3
        )
        md_path = _write_input_md(tmp_path)
        pool = _mock_pool_with_translations([
            "单元1尝试1",  # md_1 attempt 1 (bad)
            "单元1尝试2",  # md_1 attempt 2 (passes)
            "单元2尝试1",  # md_2 attempt 1 (bad)
            "单元2尝试2",  # md_2 attempt 2 (passes)
        ])
        judge = _mock_judge_with_scores([4.0, 9.0, 4.0, 9.0])

        result = _run_translate_md_async(
            config_path=config_path,
            input_path=md_path,
            output_dir=tmp_path / "out",
            pool=pool,
            judge=judge,
        )

        # 2 units × 2 attempts (fail then pass) = 4
        assert pool.translate.call_count == UNITS * 2
        assert judge.judge.call_count == UNITS * 2
        output = Path(result).read_text(encoding="utf-8")
        assert "单元1尝试2" in output
        assert "单元2尝试2" in output
        _assert_no_source_copy_retry(pool)

    def test_lqa_enabled_all_attempts_fail_uses_best_of_n(self, tmp_path: Path):
        """When all attempts fail, the best-scored translation is used (best-of-N)."""
        config_path = _write_config(
            tmp_path, enable_lqa=True, threshold=7.0, max_retries=3
        )
        md_path = _write_input_md(tmp_path)
        pool = _mock_pool_with_translations([
            "单元1尝试1",
            "单元1尝试2",
            "单元1尝试3",
            "单元1尝试4",
            "单元2尝试1",
            "单元2尝试2",
            "单元2尝试3",
            "单元2尝试4",
        ])
        judge = _mock_judge_with_scores([4.0, 6.5, 5.0, 6.0, 4.0, 6.5, 5.0, 6.0])

        result = _run_translate_md_async(
            config_path=config_path,
            input_path=md_path,
            output_dir=tmp_path / "out",
            pool=pool,
            judge=judge,
        )

        # 2 units × (1 initial + 3 retries) = 8
        assert pool.translate.call_count == UNITS * 4
        assert judge.judge.call_count == UNITS * 4
        # Each unit's best-scored attempt is attempt 2.
        output = Path(result).read_text(encoding="utf-8")
        assert "单元1尝试2" in output
        assert "单元2尝试2" in output
        _assert_no_source_copy_retry(pool)

    def test_lqa_max_retries_zero_equivalent_to_disabled(self, tmp_path: Path):
        """When max_retries=0, only 1 attempt is made (initial)."""
        config_path = _write_config(
            tmp_path, enable_lqa=True, threshold=7.0, max_retries=0
        )
        md_path = _write_input_md(tmp_path)
        pool = _mock_pool_with_translations([
            "单元1仅一次",
            "单元2仅一次",
        ])
        judge = _mock_judge_with_scores([5.0, 5.0])  # Below threshold but no retry

        _run_translate_md_async(
            config_path=config_path,
            input_path=md_path,
            output_dir=tmp_path / "out",
            pool=pool,
            judge=judge,
        )

        # 2 units × 1 attempt (max_retries=0 = no retry) = 2
        assert pool.translate.call_count == UNITS * 1, (
            f"Expected {UNITS * 1} translate calls (max_retries=0 = no retry), "
            f"got {pool.translate.call_count}"
        )
        assert judge.judge.call_count == UNITS * 1
        _assert_no_source_copy_retry(pool)

    def test_lqa_enabled_with_all_good_scores_no_retry(self, tmp_path: Path):
        """When enable_lqa=True and all scores are high, retry never happens."""
        config_path = _write_config(
            tmp_path, enable_lqa=True, threshold=7.0, max_retries=5
        )
        md_path = _write_input_md(tmp_path)
        pool = _mock_pool_with_translations([
            "单元1一次",
            "单元2一次",
        ])
        judge = _mock_judge_with_scores([9.0, 9.0])  # High score, no retry needed

        _run_translate_md_async(
            config_path=config_path,
            input_path=md_path,
            output_dir=tmp_path / "out",
            pool=pool,
            judge=judge,
        )

        # 2 units × 1 attempt (all scores pass) = 2
        assert pool.translate.call_count == UNITS
        assert judge.judge.call_count == UNITS
        _assert_no_source_copy_retry(pool)
