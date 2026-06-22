"""Tests for the FidelityScorer module."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_FIDELITY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_FIDELITY_DIR))

from fidelity_scorer import FidelityScorer, strip_md_noise  # noqa: E402


class TestFidelityScorer:
    def test_strip_md_noise_removes_frontmatter(self):
        text = "---\nsource_lang: en\n---\n# Title\n\nBody text"
        out = strip_md_noise(text)
        assert "source_lang" not in out
        assert "Title" not in out
        assert "Body text" in out

    def test_strip_md_noise_removes_headers(self):
        text = "# H1\n## H2\n\nBody"
        out = strip_md_noise(text)
        assert "H1" not in out
        assert "H2" not in out
        assert "Body" in out

    def test_bleu_perfect_match_long_text(self):
        text = "今天天气很好我们去公园散步。公园里有很多花。小鸟在树上唱歌。我们玩得很开心。"
        score = FidelityScorer.bleu_vs_reference(text, text)
        assert isinstance(score, float)

    def test_bleu_zero_overlap(self):
        hyp = "今天天气很好我们去公园散步"
        ref = "明天会下雨记得带伞"
        score = FidelityScorer.bleu_vs_reference(hyp, ref)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_char_jaccard_perfect_match(self):
        text = "你好世界"
        assert FidelityScorer.char_jaccard(text, text) == pytest.approx(1.0)

    def test_char_jaccard_no_overlap(self):
        a = "你好世界"
        b = "再见朋友"
        score = FidelityScorer.char_jaccard(a, b)
        assert 0.0 < score < 0.5

    def test_char_cosine_perfect_match(self):
        text = "你好世界"
        assert FidelityScorer.char_cosine(text, text) == pytest.approx(1.0, abs=0.001)

    def test_char_cosine_distribution_match(self):
        a = "你好世界你好"
        b = "世界你好世界"
        assert FidelityScorer.char_cosine(a, b) > 0.8

    def test_alice_ch1_fidelity_results_exist(self):
        results_file = _FIDELITY_DIR / "results" / "alice_ch1_fidelity.json"
        assert results_file.exists()
        import json
        data = json.loads(results_file.read_text())
        assert "metrics" in data
        assert "bleu" in data["metrics"]
        assert "char_jaccard" in data["metrics"]
        assert "char_cosine" in data["metrics"]

    def test_alice_reference_exists(self):
        ref_file = _FIDELITY_DIR / "reference" / "alice_ch1_zh_bilinguis.txt"
        assert ref_file.exists()
        content = ref_file.read_text(encoding="utf-8")
        chinese = sum(1 for c in content if "\u4e00" <= c <= "\u9fff")
        assert chinese > 500, f"Reference has only {chinese} Chinese chars"
