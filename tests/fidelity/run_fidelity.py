"""Fidelity scoring runner — invoked by `make fidelity`.

Computes BLEU, char_jaccard, and char_cosine on the existing
Alice ch1 translation against the Bilinguis public-domain reference,
asserts char_cosine >= 0.9, and updates the result JSON.

No LLM calls — only the existing candidate file and reference are used.
The candidate must be produced ahead of time (manually or via `make fidelity-nightly`).

suite#279: when a fresh regen meta sidecar is present (and its candidate
sha256 matches the candidate being scored), the result carries
`sample_coverage`. An undersampled regen (provider throttle/auth kept part
of the corpus untranslated) is reported as verdict status `unconfigured` —
an explicit environment gap, never a fake green pass and never a quality red.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIDELITY_DIR = Path(__file__).resolve().parent
RESULTS_FILE = FIDELITY_DIR / "results" / "alice_ch1_fidelity.json"
META_FILE = FIDELITY_DIR / "results" / "alice_ch1_regen_meta.json"
CANDIDATE = REPO_ROOT / "test_artifacts" / "ol" / "alice_ch1_zhipu_real.md"
REFERENCE = FIDELITY_DIR / "reference" / "alice_ch1_zh_bilinguis.txt"
CHAR_COSINE_THRESHOLD = 0.9


def load_sample_coverage() -> dict | None:
    """Fresh-regen coverage from the regen meta sidecar (suite#279).

    The meta is trusted only when its candidate_sha256 matches the candidate
    actually being scored — a stale or unrelated meta must not soften the
    verdict of a different candidate.
    """
    if not META_FILE.exists() or not CANDIDATE.exists():
        return None
    try:
        meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(meta, dict):
        return None
    expected = meta.get("candidate_sha256")
    if not expected or hashlib.sha256(CANDIDATE.read_bytes()).hexdigest() != expected:
        print("  NOTE: regen meta ignored (candidate sha256 mismatch — stale meta)")
        return None
    total, translated = meta.get("total_paragraphs"), meta.get("translated")
    if not isinstance(total, int) or not isinstance(translated, int) or total <= 0:
        return None
    return {
        "translated": translated,
        "total": total,
        "undersampled": translated < total,
    }


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

    coverage = load_sample_coverage()

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
    if coverage is not None:
        result["sample_coverage"] = coverage

    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print("=== FIDELITY SCORING (Alice ch1) ===")
    print(f"  Candidate: {CANDIDATE.name} ({len(candidate)} chars)")
    print(f"  Reference: {REFERENCE.name} ({len(reference)} chars)")
    print()
    if coverage is not None:
        print(f"  Sample:        {coverage['translated']}/{coverage['total']} paragraphs"
              + ("  (UNDERSAMPLED)" if coverage["undersampled"] else "  (full)"))
    print(f"  BLEU:          {bleu:.4f}  (informational; 0 expected for cross-era Chinese)")
    print(f"  Char Jaccard:  {jaccard:.4f}  (>=0.5 acceptable)")
    print(f"  Char Cosine:   {cosine:.4f}  (>=0.9 production threshold)")
    print()
    if coverage is not None and coverage["undersampled"]:
        # Environment gap, not a quality verdict: the regen could not produce
        # a full corpus (throttle/auth), so scoring a partial candidate says
        # nothing about translation quality. Report unconfigured explicitly —
        # never a silent pass, never a fake-quality red (suite#279).
        result["verdict"]["sampling"] = "insufficient"
        result["verdict"]["status"] = "unconfigured"
        RESULTS_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(
            f"  UNCONFIGURED — sampling insufficient: only "
            f"{coverage['translated']}/{coverage['total']} paragraphs were "
            "translated (provider throttle/auth). This is an environment gap, "
            "not a quality verdict; char_cosine on a partial corpus is "
            "informational only."
        )
        return 0
    if cosine >= CHAR_COSINE_THRESHOLD:
        print(f"  PASS — char_cosine {cosine:.4f} >= {CHAR_COSINE_THRESHOLD}")
        return 0
    else:
        print(f"  FAIL — char_cosine {cosine:.4f} < {CHAR_COSINE_THRESHOLD}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
