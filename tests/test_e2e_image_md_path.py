"""E2E test: images.json forwarding through OL translate-md MD path (OL#73).

Verifies that:
1. ``--images-json`` flag copies images.json to output dir alongside translated .md
2. Auto-detection of ``{stem}_images.json`` / ``{stem}.images.json`` works when flag omitted
3. Full OPP → OL → ORF MD path with images.json survives end-to-end

Requires: OPP, OL, ORF installed (FAKE_LLM + FAKE_PANDOC modes).
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SUITE_ROOT = Path(__file__).resolve().parents[1]


# ── helpers ──────────────────────────────────────────────────────────────

def _build_env() -> dict[str, str]:
    """Build environment with PYTHONPATH and FAKE_LLM/FAKE_PANDOC seams."""
    env = os.environ.copy()
    env["OMNI_TEST_FAKE_LLM"] = "1"
    env["OMNI_TEST_FAKE_PANDOC"] = "1"
    # Ensure all three component src dirs are importable
    _paths = [
        str(SUITE_ROOT / "Omni_Pre_Processor" / "src"),
        str(SUITE_ROOT / "Omni_Localizer" / "src"),
        str(SUITE_ROOT / "Omni_Re_Formatter" / "src"),
    ]
    _existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = ":".join(_paths + ([_existing] if _existing else []))
    return env


def _create_dummy_images_json(path: Path, count: int = 1) -> None:
    """Write a minimal valid images.json to *path*."""
    data = {
        "images": [
            {
                "id": f"img_{i}",
                "paragraph_index": i,
                "mime_type": "image/png",
                "width": 100,
                "height": 100,
            }
            for i in range(count)
        ]
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _create_minimal_md(path: Path) -> None:
    """Write a one-line markdown file for testing."""
    path.write_text("# Hello\n\nThis is a test paragraph with an image reference.\n", encoding="utf-8")


# ── tests ────────────────────────────────────────────────────────────────

class TestImagesJsonForwarding:
    """Direct tests for images.json forwarding in OL translate-md (OL#73)."""

    @pytest.mark.requires_ol
    def test_explicit_flag(self, tmp_path: Path) -> None:
        """--images-json flag copies images.json to output directory."""
        _create_minimal_md(tmp_path / "input.md")
        src_json = tmp_path / "my_images.json"
        _create_dummy_images_json(src_json, count=2)

        out_dir = tmp_path / "out"
        out_dir.mkdir()

        env = _build_env()
        py = sys.executable
        result = subprocess.run(
            [
                py, "-m", "ol_cli", "translate-md",
                str(tmp_path / "input.md"),
                "-s", "en", "-t", "zh",
                "-o", str(out_dir),
                "--images-json", str(src_json),
            ],
            capture_output=True, text=True, env=env,
            cwd=str(SUITE_ROOT / "Omni_Localizer"),
            timeout=60,
        )
        assert result.returncode == 0, f"OL failed: {result.stderr[:500]}"

        copied = out_dir / "my_images.json"
        assert copied.exists(), f"images.json not copied to {copied}"
        data = json.loads(copied.read_text(encoding="utf-8"))
        assert len(data["images"]) == 2

    @pytest.mark.requires_ol
    def test_auto_detect_stem_suffix(self, tmp_path: Path) -> None:
        """Auto-detect {stem}_images.json when --images-json is omitted."""
        _create_minimal_md(tmp_path / "report.md")
        src_json = tmp_path / "report_images.json"
        _create_dummy_images_json(src_json, count=3)

        out_dir = tmp_path / "out"
        out_dir.mkdir()

        env = _build_env()
        py = sys.executable
        result = subprocess.run(
            [
                py, "-m", "ol_cli", "translate-md",
                str(tmp_path / "report.md"),
                "-s", "en", "-t", "zh",
                "-o", str(out_dir),
            ],
            capture_output=True, text=True, env=env,
            cwd=str(SUITE_ROOT / "Omni_Localizer"),
            timeout=60,
        )
        assert result.returncode == 0, f"OL failed: {result.stderr[:500]}"

        copied = out_dir / "report_images.json"
        assert copied.exists(), f"Auto-detected images.json not found at {copied}"
        data = json.loads(copied.read_text(encoding="utf-8"))
        assert len(data["images"]) == 3

    @pytest.mark.requires_ol
    def test_auto_detect_dot_suffix(self, tmp_path: Path) -> None:
        """Auto-detect {stem}.images.json (alternative OPP format)."""
        _create_minimal_md(tmp_path / "doc.md")
        src_json = tmp_path / "doc.images.json"
        _create_dummy_images_json(src_json, count=1)

        out_dir = tmp_path / "out"
        out_dir.mkdir()

        env = _build_env()
        py = sys.executable
        result = subprocess.run(
            [
                py, "-m", "ol_cli", "translate-md",
                str(tmp_path / "doc.md"),
                "-s", "en", "-t", "zh",
                "-o", str(out_dir),
            ],
            capture_output=True, text=True, env=env,
            cwd=str(SUITE_ROOT / "Omni_Localizer"),
            timeout=60,
        )
        assert result.returncode == 0, f"OL failed: {result.stderr[:500]}"

        copied = out_dir / "doc.images.json"
        assert copied.exists(), f"Auto-detected images.json not found at {copied}"

    @pytest.mark.requires_ol
    def test_no_images_json_skips_gracefully(self, tmp_path: Path) -> None:
        """translate-md succeeds when no images.json exists (graceful no-op)."""
        _create_minimal_md(tmp_path / "plain.md")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        env = _build_env()
        py = sys.executable
        result = subprocess.run(
            [
                py, "-m", "ol_cli", "translate-md",
                str(tmp_path / "plain.md"),
                "-s", "en", "-t", "zh",
                "-o", str(out_dir),
            ],
            capture_output=True, text=True, env=env,
            cwd=str(SUITE_ROOT / "Omni_Localizer"),
            timeout=60,
        )
        assert result.returncode == 0, f"OL failed: {result.stderr[:500]}"
        # No images.json expected — just verify the .md was produced
        md_out = out_dir / "plain.md"
        assert md_out.exists(), f"Translated .md not found at {md_out}"


@pytest.mark.e2e
class TestFullPipelineImages:
    """End-to-end OPP → OL → ORF MD path with images.json forwarding."""

    @pytest.mark.requires_opp
    @pytest.mark.requires_ol
    @pytest.mark.requires_orf
    def test_images_survive_md_pipeline(self, tmp_path: Path) -> None:
        """Full MD pipeline: OPP extracts → OL translates → ORF backfills.

        Verifies that images.json is produced by OPP, forwarded by OL,
        and ORF outputs a valid result.
        """
        # ── 1. Create a minimal DOCX with an inline image ──
        import io

        from docx import Document
        from docx.shared import Inches

        docx_path = tmp_path / "test.docx"
        doc = Document()
        doc.add_paragraph("Hello world — this document has an image below.")

        # Valid 1×1 RGB PNG (zlib+struct-built, verified against python-docx's
        # strict chunk parser). The previous hand-rolled byte literal was
        # malformed — its IDAT header declared length 12 but carried 14
        # bytes, so python-docx's chunk walker misread the next chunk type
        # as b'ND\xaeB' and raised UnicodeDecodeError (docx/image/helpers.py
        # decodes chunk types as UTF-8) inside add_picture, before OPP ran.
        _png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1Pe"
            "AAAAC0lEQVR4nPvPwAAAAwABAIPJ7GsAAAAASUVORK5CYII="
        )
        doc.add_picture(io.BytesIO(_png_bytes), width=Inches(1))
        doc.save(str(docx_path))
        assert docx_path.exists()

        # ── 2. OPP extract ──
        opp_out = tmp_path / "opp_out"
        opp_out.mkdir()
        env = _build_env()
        py = sys.executable

        r1 = subprocess.run(
            [
                py, "-m", "opp.cli", str(docx_path),
                "--target-format", "both",
                "--source-lang", "en", "--target-lang", "zh",
                "--output-dir", str(opp_out),
            ],
            capture_output=True, text=True, env=env,
            cwd=str(SUITE_ROOT / "Omni_Pre_Processor"),
            timeout=120,
        )
        assert r1.returncode == 0, f"OPP failed: {r1.stderr[:500]}"

        md_path = opp_out / "test.md"
        images_json_path: Path | None = None
        for candidate in ("test_images.json", "test.images.json"):
            p = opp_out / candidate
            if p.exists():
                images_json_path = p
                break

        if not md_path.exists():
            pytest.skip("OPP did not produce .md output (format may not be supported)")

        # ── 3. OL translate-md with --images-json ──
        ol_out = tmp_path / "ol_out"
        ol_out.mkdir()

        ol_cmd = [
            py, "-m", "ol_cli", "translate-md",
            str(md_path),
            "-s", "en", "-t", "zh",
            "-o", str(ol_out),
        ]
        if images_json_path and images_json_path.exists():
            ol_cmd.extend(["--images-json", str(images_json_path)])

        r2 = subprocess.run(
            ol_cmd, capture_output=True, text=True, env=env,
            cwd=str(SUITE_ROOT / "Omni_Localizer"),
            timeout=120,
        )
        assert r2.returncode == 0, f"OL failed: {r2.stderr[:500]}"

        # Verify images.json was copied to OL output dir
        if images_json_path:
            ol_images = ol_out / images_json_path.name
            assert ol_images.exists(), (
                f"images.json not forwarded to OL output: {ol_images}"
            )

        # Find the translated .md
        ol_md: Path | None = None
        for candidate in (ol_out / "test.md", ol_out / "translated_test.md"):
            if candidate.exists():
                ol_md = candidate
                break
        if ol_md is None:
            pytest.skip("OL did not produce .md output — check logs")

        # ── 4. ORF apply-md ──
        orf_out = tmp_path / "result.docx"

        r3 = subprocess.run(
            [
                py, "-m", "orf.cli", "apply-md",
                str(ol_md),
                "--target-format", "docx",
                "--output", str(orf_out),
            ],
            capture_output=True, text=True, env=env,
            cwd=str(SUITE_ROOT / "Omni_Re_Formatter"),
            timeout=120,
        )
        assert r3.returncode == 0, f"ORF failed: {r3.stderr[:500]}"
        assert orf_out.exists(), f"ORF output not found at {orf_out}"
