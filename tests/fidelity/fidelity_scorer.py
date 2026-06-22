"""Fidelity scoring for en→zh translation quality.

Provides two metrics with clear, non-deceptive semantics:
- BLEU via sacrebleu.corpus_bleu() (both inputs must be the same language)
- Semantic cosine via sentence-transformers (cross-lingual)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


def strip_md_noise(text: str) -> str:
    """Remove YAML frontmatter and markdown headers, keep prose."""
    parts = text.split("---", 2)
    body = parts[2] if len(parts) >= 3 and parts[0].strip() == "" else text
    return re.sub(r"^#+\s.*$", "", body, flags=re.MULTILINE).strip()


class FidelityScorer:
    @staticmethod
    def bleu_vs_reference(hypothesis: str, reference: str) -> float:
        """Corpus-level BLEU. Both must be the same language. Returns 0-1.

        Wraps sacrebleu.corpus_bleu() so the caller doesn't have to remember
        the hypothesis vs reference argument order.
        """
        import sacrebleu

        bleu = sacrebleu.corpus_bleu([hypothesis], [[reference]])
        return bleu.score / 100.0

    @staticmethod
    def semantic_cosine(source: str, target: str, model: "SentenceTransformer") -> float:
        """Cross-lingual cosine similarity via sentence-transformers. Returns 0-1.

        `source` and `target` should be in different languages (e.g. en/zh).
        `model` must be a pre-loaded SentenceTransformer with normalize_embeddings=True.
        """
        emb_src = model.encode([source], normalize_embeddings=True, show_progress_bar=False)
        emb_tgt = model.encode([target], normalize_embeddings=True, show_progress_bar=False)
        return float((emb_src * emb_tgt).sum())

    @staticmethod
    def score_file_pair(
        candidate_path: Path,
        reference_path: Path,
        model: "SentenceTransformer | None" = None,
    ) -> dict[str, float]:
        """Score a candidate translation against a reference. Both files are stripped
        of YAML frontmatter and markdown headers before scoring."""
        candidate = strip_md_noise(candidate_path.read_text(encoding="utf-8"))
        reference = strip_md_noise(reference_path.read_text(encoding="utf-8"))

        result: dict[str, float] = {
            "bleu": FidelityScorer.bleu_vs_reference(candidate, reference),
            "candidate_chars": len(candidate),
            "reference_chars": len(reference),
        }

        if model is not None:
            result["semantic_cosine"] = FidelityScorer.semantic_cosine(
                reference, candidate, model
            )

        return result


    @staticmethod
    def char_jaccard(a: str, b: str) -> float:
        """Character-level Jaccard similarity."""
        chars_a = set(c for c in a if c.strip())
        chars_b = set(c for c in b if c.strip())
        if not chars_a or not chars_b:
            return 0.0
        return len(chars_a & chars_b) / len(chars_a | chars_b)

    @staticmethod
    def char_cosine(a: str, b: str) -> float:
        """Character-level cosine similarity (bag-of-chars)."""
        from collections import Counter
        import math
        ca = Counter(c for c in a if c.strip())
        cb = Counter(c for c in b if c.strip())
        if not ca or not cb:
            return 0.0
        dot = sum(ca[k] * cb.get(k, 0) for k in ca)
        na = math.sqrt(sum(v * v for v in ca.values()))
        nb = math.sqrt(sum(v * v for v in cb.values()))
        return dot / (na * nb) if na and nb else 0.0
