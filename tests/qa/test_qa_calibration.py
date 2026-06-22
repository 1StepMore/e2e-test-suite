"""QA regression test (Phase D6).

Runs the multi-judge + calibration on a mock reference set to
verify the thresholds (Spearman ≥ 0.7, inter-judge agreement ≥ 60%)
are enforced correctly.

For the real reference set (20 docs with LLM translations),
see eval/reference/ — this test uses a synthetic mock set.
Runs in CI nightly, not on every commit (costs ~5min LLM time).
"""


from ol_lqa.calibration import calibrate
from ol_lqa.multi_judge import DIMENSIONS, JudgeScore, MultiJudgeResult, aggregate


def make_synthetic_reference_set(num_docs: int = 20) -> tuple[list[MultiJudgeResult], list[dict]]:
    """Generate a synthetic reference set where multi-judge strongly
    agrees with the reference LLM (Spearman ≈ 1.0, agreement = 1.0).

    Each document gets random scores 1-5, and all 3 judges give
    the same score per dimension. This simulates a well-calibrated
    multi-judge.
    """
    import random
    random.seed(42)
    judge_results = []
    reference_scores = []
    for _ in range(num_docs):
        scores = {dim: random.randint(1, 5) for dim in DIMENSIONS}
        judge_scores = [
            JudgeScore(judge_name=f"judge_{i}", scores=scores)
            for i in range(3)
        ]
        result = aggregate(judge_scores)
        judge_results.append(result)
        reference_scores.append(scores)
    return judge_results, reference_scores


def make_diverging_reference_set(num_docs: int = 20) -> tuple[list[MultiJudgeResult], list[dict]]:
    """Generate a reference set where multi-judge DISAGREES with
    reference LLM (anti-correlated). This should fail calibration.
    """
    import random
    random.seed(42)
    judge_results = []
    reference_scores = []
    for _ in range(num_docs):
        ref_scores = {dim: random.randint(1, 5) for dim in DIMENSIONS}
        inverted = {dim: 6 - ref_scores[dim] for dim in DIMENSIONS}
        judge_scores = [
            JudgeScore(judge_name=f"judge_{i}", scores=inverted)
            for i in range(3)
        ]
        result = aggregate(judge_scores)
        judge_results.append(result)
        reference_scores.append(ref_scores)
    return judge_results, reference_scores


class TestCalibrationThresholds:
    def test_synthetic_set_passes(self):
        judge_results, reference_scores = make_synthetic_reference_set(20)
        report = calibrate(judge_results, reference_scores)
        assert report.passed, f"Expected pass, got failures: {report.failures}"
        assert report.average_spearman >= 0.7
        assert report.average_inter_judge_agreement >= 0.6
        assert report.num_docs == 20

    def test_diverging_set_fails(self):
        judge_results, reference_scores = make_diverging_reference_set(20)
        report = calibrate(judge_results, reference_scores)
        assert not report.passed
        assert len(report.failures) > 0

    def test_minimum_20_docs_recommended(self):
        """The plan recommends 20 docs. Smaller sets are less reliable
        but still functional. This test just verifies the calibration
        works with fewer docs."""
        judge_results, reference_scores = make_synthetic_reference_set(5)
        report = calibrate(judge_results, reference_scores)
        assert report.passed
        assert report.num_docs == 5

    def test_calibration_report_serializable(self):
        judge_results, reference_scores = make_synthetic_reference_set(3)
        report = calibrate(judge_results, reference_scores)
        d = report.to_dict()
        assert "spearman_per_dimension" in d
        assert "thresholds" in d
        assert d["thresholds"]["spearman"] == 0.7
        assert d["thresholds"]["agreement"] == 0.6
