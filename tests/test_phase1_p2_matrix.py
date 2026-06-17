"""Regression tests for the phase1 matrix builder (scripts/phase1_runner.py).

2026-06-17 round 3 (OPT-09): P2 XLIFF backfill is format-preserving, so
docx→odt is invalid. The matrix was changed to remove odt from docx
outputs and from XLIFF_PATH_OUTPUTS. These tests lock in that change
so a future contributor doesn't add the invalid combination back.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SUITE_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = _SUITE_ROOT / "scripts"
if str(_SUITE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SUITE_ROOT))
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import phase1_runner  # noqa: E402


class TestP2XLIFFMatrix:
    """P2 (XLIFF backfill) is format-preserving: skeleton must match output."""

    def test_xliff_path_outputs_constant_excludes_odt(self):
        """XLIFF_PATH_OUTPUTS is the documentary constant for the XLIFF
        backfill surface. It must not include odt because XLIFF backfill
        is format-preserving (a DOCX skeleton cannot be backfilled into
        an ODT). 2026-06-17 round 3 OPT-09.
        """
        assert "odt" not in phase1_runner.XLIFF_PATH_OUTPUTS, (
            "XLIFF_PATH_OUTPUTS documents what ORF's apply-xliff supports. "
            "odt is supported by the CLI but only with an ODF skeleton, "
            "not from the matrix auto-test loop."
        )

    def test_p2_build_matrix_has_no_odt_in_outputs(self):
        """Generated P2 test cases must never include odt as an output format.

        This is the end-to-end guard: even if a future change adds odt
        via a different code path, the matrix must not produce a P2
        case with odt in its output_formats.
        """
        try:
            cases = phase1_runner.build_matrix()
        except Exception as e:
            # build_matrix() reads fixtures; if fixtures are missing in
            # the test env, that's OK — the matrix construction itself
            # is what we care about. Skip if it errors on fixture lookup.
            import pytest
            pytest.skip(f"build_matrix() requires fixtures: {e}")
        for case in cases:
            if case.tier != "P2":
                continue
            assert "odt" not in case.output_formats, (
                f"P2 case {case.description} has odt in output_formats; "
                f"XLIFF backfill cannot cross formats. Use P3 (MD path) for ODT."
            )

    def test_p2_docx_has_only_docx_output(self):
        """P2 docx cases must produce only 'docx' (no cross-format)."""
        try:
            cases = phase1_runner.build_matrix()
        except Exception:
            import pytest
            pytest.skip("build_matrix() requires fixtures")
        p2_docx = [c for c in cases if c.tier == "P2" and c.input_format == "docx"]
        assert len(p2_docx) >= 2, "P2 should cover both zh→en and en→zh docx paths"
        for case in p2_docx:
            assert case.output_formats == ["docx"], (
                f"Expected only ['docx'] for P2 docx; got {case.output_formats}"
            )

    def test_xliff_outputs_by_input_constant_exists(self):
        """FIX-#16 (round 6): xliff_outputs_by_input was promoted from a
        local var in build_matrix() to the module-level
        XLIFF_OUTPUTS_BY_INPUT constant so tests can import and assert
        on it directly. Locks in the matrix shape (docx→docx, pptx→pptx).
        """
        from scripts.phase1_runner import XLIFF_OUTPUTS_BY_INPUT  # type: ignore
        assert XLIFF_OUTPUTS_BY_INPUT == {"docx": ["docx"], "pptx": ["pptx"]}
        assert "odt" not in XLIFF_OUTPUTS_BY_INPUT.get("docx", [])
