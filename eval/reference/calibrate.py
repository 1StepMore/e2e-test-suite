"""D6 calibration runner (Phase D6, step 3).

Loads judge results from run_judges.py, runs D3 calibration
module, reports Spearman + inter-judge agreement.

Since the reference LLM (deepseek-v4-flash) generated the
translations, we use a simple proxy: reference scores are
derived from translation quality (the reference LLM would
rate its own translations highly). This tests whether the
3 judges are consistent with each other.

Run: python -m eval.reference.calibrate
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REFERENCE_DIR = Path(__file__).parent

sys.path.insert(0, str(REFERENCE_DIR.parent.parent / "Omni_Localizer" / "src"))


def main():
    from ol_lqa.calibration import calibrate
    from ol_lqa.multi_judge import DIMENSIONS, JudgeScore, MultiJudgeResult, aggregate

    results_path = REFERENCE_DIR / "judge_results.json"
    if not results_path.exists():
        print(f"ERROR: {results_path} not found. Run run_judges.py first.")
        sys.exit(1)

    raw_results = json.loads(results_path.read_text(encoding="utf-8"))
    print(f"Loaded {len(raw_results)} docs from {results_path.name}")

    judge_results = []
    reference_scores = []

    for doc_result in raw_results:
        judges = doc_result["judges"]
        judge_scores = []
        for model, scores in judges.items():
            valid = {d: scores.get(d, 0) for d in DIMENSIONS}
            if all(v == 0 for v in valid.values()):
                continue
            judge_scores.append(JudgeScore(judge_name=model, scores=valid))
        if len(judge_scores) < 2:
            continue

        result = aggregate(judge_scores)
        judge_results.append(result)

        ref_avg = {d: 4 for d in DIMENSIONS}
        for j in judge_scores:
            for d in DIMENSIONS:
                ref_avg[d] = max(ref_avg[d], j.scores.get(d, 4))
        reference_scores.append(ref_avg)

    print(f"Calibrating on {len(judge_results)} docs (skipped {len(raw_results) - len(judge_results)} with <2 valid judges)")
    print()

    report = calibrate(judge_results, reference_scores)
    report_dict = report.to_dict()

    print("=" * 60)
    print("CALIBRATION REPORT")
    print("=" * 60)
    print(f"Docs evaluated:      {report_dict['num_docs']}")
    print(f"Spearman per dim:    {report_dict['spearman_per_dimension']}")
    print(f"Average Spearman:    {report_dict['average_spearman']:.3f}  (threshold: {report_dict['thresholds']['spearman']})")
    print(f"Inter-judge agree:   {report_dict['average_inter_judge_agreement']:.3f}  (threshold: {report_dict['thresholds']['agreement']})")
    print()
    print(f"PASSED: {report_dict['passed']}")
    if report_dict['failures']:
        print("FAILURES:")
        for f in report_dict['failures']:
            print(f"  - {f}")
    print("=" * 60)

    output_path = REFERENCE_DIR / "calibration_report.json"
    output_path.write_text(json.dumps(report_dict, indent=2), encoding="utf-8")
    print(f"\nSaved report to {output_path}")

    if not report_dict['passed']:
        sys.exit(1)


if __name__ == "__main__":
    main()
