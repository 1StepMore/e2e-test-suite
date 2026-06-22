"""Fidelity scoring runner — invoked by `make fidelity`.

Computes BLEU, char_jaccard, and char_cosine on the existing
Alice ch1 translation against the Bilinguis public-domain reference,
asserts char_cosine >= 0.9, and updates the result JSON.

No LLM calls — only the existing candidate file and reference are used.
The candidate must be produced ahead of time (manually or via `make fidelity-nightly`).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIDELITY_DIR = Path(__file__).resolve().parent
RESULTS_FILE = FIDELITY_DIR / "results" / "alice_ch1_fidelity.json"
CANDIDATE = REPO_ROOT / "test_artifacts" / "ol" / "alice_ch1_zhipu_real.md"
REFERENCE = FIDELITY_DIR / "reference" / "alice_ch1_zh_bilinguis.txt"
CHAR_COSINE_THRESHOLD = 0.9


def main() -> int:
    sys.path.insert(0, str(FIDELITY_DIR))
    from fidelity_scorer import FidelityScorer, strip_md_noise

    if not CANDIDATE.exists():
        print(f"FAIL: candidate not found: {CANDIDATE}")
        print("  Run `make fidelity-nightly` to generate it, or place a translation manually.")
        return 1

    if not REFERENCE.exists():
        print(f"FAIL: reference not found: {REFERENCE}")
        return 1

    candidate = strip_md_noise(CANDIDATE.read_text(encoding="utf-8"))
    reference = strip_md_noise(REFERENCE.read_text(encoding="utf-8"))

    bleu = FidelityScorer.bleu_vs_reference(candidate, reference)
    jaccard = FidelityScorer.char_jaccard(candidate, reference)
    cosine = FidelityScorer.char_cosine(candidate, reference)

    result = {
        "corpus": "Alice in Wonderland chapter 1",
        "candidate_source": CANDIDATE.name,
        "reference_source": REFERENCE.name,
        "candidate_chars": len(candidate),
        "reference_chars": len(reference),
        "metrics": {
            "bleu": round(bleu, 4),
            "char_jaccard": round(jaccard, 4),
            "char_cosine": round(cosine, 4),
        },
        "thresholds": {
            "char_cosine_production": CHAR_COSINE_THRESHOLD,
            "bleu_informational_only": "BLEU=0 expected for modern vs 1922 Chinese (no shared n-grams)",
        },
        "verdict": {
            "char_cosine_passes": cosine >= CHAR_COSINE_THRESHOLD,
            "jaccard_acceptable": jaccard >= 0.5,
        },
    }

    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print("=== FIDELITY SCORING (Alice ch1) ===")
    print(f"  Candidate: {CANDIDATE.name} ({len(candidate)} chars)")
    print(f"  Reference: {REFERENCE.name} ({len(reference)} chars)")
    print()
    print(f"  BLEU:          {bleu:.4f}  (informational; 0 expected for cross-era Chinese)")
    print(f"  Char Jaccard:  {jaccard:.4f}  (>=0.5 acceptable)")
    print(f"  Char Cosine:   {cosine:.4f}  (>=0.9 production threshold)")
    print()
    if cosine >= CHAR_COSINE_THRESHOLD:
        print(f"  PASS — char_cosine {cosine:.4f} >= {CHAR_COSINE_THRESHOLD}")
        return 0
    else:
        print(f"  FAIL — char_cosine {cosine:.4f} < {CHAR_COSINE_THRESHOLD}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
