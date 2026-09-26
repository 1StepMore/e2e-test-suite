"""Multi-format coverage — 4 OPP→OL→ORF paths × PPTX/PDF inputs."""

import asyncio
import json
import os
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import pytest


pytestmark = [pytest.mark.e2e, pytest.mark.real_chain, pytest.mark.multiformat]


PATHS = ["xliff_mcp", "xliff_cli", "md_mcp", "md_cli"]


@pytest.fixture
def use_fake_llm(monkeypatch):
    monkeypatch.setenv("OMNI_TEST_FAKE_LLM", "1")
    monkeypatch.setenv("OMNI_TEST_FAKE_PANDOC", "1")
    return True


SUITE_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent
SRC_DIRS = [
    SUITE_ROOT / "Omni_Pre_Processor" / "src",
    SUITE_ROOT / "Omni_Localizer" / "src",
    SUITE_ROOT / "Omni_Re_Formatter" / "src",
]
OL_CONFIG_PATH = SUITE_ROOT / "Omni_Localizer" / "config" / "default.yaml"

TRANSLATION_MARKERS = ["[ZH]", "你好", "世界", "用户手册", "测试", "功能"]


@dataclass
class PathResult:
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    docx_path: Optional[Path] = None
    details: dict = field(default_factory=dict)


def _make_subprocess_env() -> dict:
    env = os.environ.copy()
    pp_parts = [str(TESTS_DIR)]
    pp_parts.extend(str(d) for d in SRC_DIRS if d.exists())
    if env.get("PYTHONPATH"):
        pp_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = ":".join(pp_parts)
    env.setdefault("OMNI_TEST_FAKE_LLM", "1")
    env.setdefault("OMNI_TEST_FAKE_PANDOC", "1")
    return env


def _run_opp(input_path: Path, output_dir: Path):
    from opp.pipeline import OPPPipeline

    output_dir.mkdir(parents=True, exist_ok=True)
    resource_dir = output_dir / "resources"
    resource_dir.mkdir(parents=True, exist_ok=True)
    pipeline = OPPPipeline(resource_storage_dir=resource_dir)
    result = pipeline.process_file(input_path)
    if result is None or getattr(result, "extraction_result", None) is None:
        raise RuntimeError(f"OPP extraction returned no result for {input_path}")
    return pipeline, result


def _run_xliff_mcp(input_path: Path, output_dir: Path) -> PathResult:
    try:
        pipeline, result = _run_opp(input_path, output_dir)
    except Exception as e:
        return PathResult(exit_code=1, stderr=f"OPP failed: {type(e).__name__}: {e}")

    xliff_path = output_dir / f"{input_path.stem}.xlf"
    pipeline.generate_xliff(result.extraction_result, xliff_path, "en", "zh")
    if not xliff_path.exists():
        return PathResult(exit_code=1, stderr=f"OPP did not produce XLIFF: {xliff_path}")

    skeleton_path = pipeline.save_skeleton(
        result.extraction_result, input_path.stem, output_dir
    )
    translated_xliff = output_dir / f"{input_path.stem}_translated.xlf"

    with patch("ol_mcp.translate_xliff.ModelPool") as MockPool:
        from tests.test_e2e_pipeline_fixtures import _FakeModelPool

        mock_instance = _FakeModelPool()
        MockPool.get_instance.return_value = mock_instance
        MockPool.return_value = mock_instance

        from ol_mcp.tools import translate_xliff, TranslateXliffInput

        params = TranslateXliffInput(
            input_path=str(xliff_path),
            output_path=str(translated_xliff),
            source_lang="en",
            target_lang="zh",
        )
        result_str = asyncio.run(translate_xliff(params))
        result_data = json.loads(result_str)

    if not result_data.get("success", False):
        warnings = result_data.get("warnings") or []
        return PathResult(
            exit_code=1,
            stderr=" | ".join(str(w) for w in warnings) or "OL MCP failed",
        )

    from orf.channels.xliff2docx import XLIFF2DOCXConverter

    converter = XLIFF2DOCXConverter()
    docx_output = output_dir / "result.docx"
    conv_result = converter.convert(
        input_skeleton=skeleton_path,
        xliff_path=translated_xliff,
        output_path=docx_output,
    )
    if not conv_result.success and not docx_output.exists():
        return PathResult(
            exit_code=1,
            stderr="; ".join(str(e) for e in (conv_result.errors or ["ORF failed"])),
        )
    return PathResult(exit_code=0, docx_path=docx_output)


def _run_xliff_cli(input_path: Path, output_dir: Path) -> PathResult:
    try:
        pipeline, result = _run_opp(input_path, output_dir)
    except Exception as e:
        return PathResult(exit_code=1, stderr=f"OPP failed: {type(e).__name__}: {e}")

    xliff_path = output_dir / f"{input_path.stem}.xlf"
    pipeline.generate_xliff(result.extraction_result, xliff_path, "en", "zh")
    if not xliff_path.exists():
        return PathResult(exit_code=1, stderr=f"OPP did not produce XLIFF: {xliff_path}")

    skeleton_dir = output_dir / "orf"
    skeleton_dir.mkdir(parents=True, exist_ok=True)
    skeleton_path = pipeline.save_skeleton(
        result.extraction_result, input_path.stem, skeleton_dir
    )
    if skeleton_path is None or not skeleton_path.exists():
        return PathResult(exit_code=1, stderr="save_skeleton returned None or missing file")
    ol_out = output_dir / "ol"
    ol_out.mkdir(parents=True, exist_ok=True)
    env = _make_subprocess_env()

    ol_result = subprocess.run(
        [
            sys.executable, "-m", "ol_cli", "translate-xliff",
            str(xliff_path), "-o", str(ol_out), "-c", str(OL_CONFIG_PATH),
        ],
        capture_output=True, text=True, env=env,
    )
    if ol_result.returncode != 0:
        return PathResult(
            exit_code=ol_result.returncode,
            stdout=ol_result.stdout,
            stderr=ol_result.stderr,
        )

    translated_xliff = ol_out / f"{input_path.stem}.xlf"
    if not translated_xliff.exists():
        return PathResult(exit_code=1, stderr="OL CLI did not produce translated XLIFF")

    orf_out = output_dir / "orf" / "result.docx"
    orf_out.parent.mkdir(parents=True, exist_ok=True)
    orf_result = subprocess.run(
        [
            sys.executable, "-m", "orf.cli", "apply-xliff",
            str(skeleton_path), "--xliff", str(translated_xliff),
            "--output", str(orf_out), "--format", "docx",
        ],
        capture_output=True, text=True, env=env,
    )
    if orf_result.returncode != 0 and not orf_out.exists():
        return PathResult(
            exit_code=orf_result.returncode,
            stdout=orf_result.stdout,
            stderr=orf_result.stderr,
        )
    return PathResult(
        exit_code=orf_result.returncode,
        stdout=orf_result.stdout,
        stderr=orf_result.stderr,
        docx_path=orf_out if orf_out.exists() else None,
    )


def _run_md_mcp(input_path: Path, output_dir: Path) -> PathResult:
    try:
        pipeline, result = _run_opp(input_path, output_dir)
    except Exception as e:
        return PathResult(exit_code=1, stderr=f"OPP failed: {type(e).__name__}: {e}")

    md_path = output_dir / f"{input_path.stem}.md"
    pipeline.generate_markdown(result.extraction_result, md_path)
    if not md_path.exists():
        return PathResult(exit_code=1, stderr=f"OPP did not produce MD: {md_path}")

    with patch("ol_mcp.translate_md.ModelPool") as MockPool:
        from tests.test_e2e_pipeline_fixtures import _FakeModelPool

        mock_instance = _FakeModelPool()
        MockPool.get_instance.return_value = mock_instance
        MockPool.return_value = mock_instance

        from ol_mcp.tools import translate_md_text, TranslateInput

        original_md_content = md_path.read_text(encoding="utf-8")
        params = TranslateInput(
            content=original_md_content,
            source_lang="en",
            target_lang="zh",
        )
        result_str = asyncio.run(translate_md_text(params))
        result_data = json.loads(result_str)

    if not result_data.get("success", False):
        warnings = result_data.get("warnings") or []
        return PathResult(
            exit_code=1,
            stderr=" | ".join(str(w) for w in warnings) or "OL MCP failed",
        )

    translated_md = output_dir / f"{input_path.stem}_translated.md"
    translated_md.write_text(result_data.get("translated", ""), encoding="utf-8")

    with patch("subprocess.run") as mock_run:
        from tests.test_e2e_pipeline_fixtures import _FakePandocRunner

        mock_run.side_effect = _FakePandocRunner()
        from orf.channels.md2docx import MD2DOCXConverter

        converter = MD2DOCXConverter()
        docx_output = output_dir / "result.docx"
        conv_result = converter.convert(translated_md, docx_output)
    if not conv_result.success:
        return PathResult(
            exit_code=1,
            stderr="; ".join(str(e) for e in (conv_result.errors or ["ORF failed"])),
        )
    return PathResult(exit_code=0, docx_path=docx_output)


def _run_md_cli(input_path: Path, output_dir: Path) -> PathResult:
    try:
        pipeline, result = _run_opp(input_path, output_dir)
    except Exception as e:
        return PathResult(exit_code=1, stderr=f"OPP failed: {type(e).__name__}: {e}")

    md_path = output_dir / f"{input_path.stem}.md"
    pipeline.generate_markdown(result.extraction_result, md_path)
    if not md_path.exists():
        return PathResult(exit_code=1, stderr=f"OPP did not produce MD: {md_path}")

    ol_out = output_dir / "ol"
    ol_out.mkdir(parents=True, exist_ok=True)
    env = _make_subprocess_env()

    ol_result = subprocess.run(
        [
            sys.executable, "-m", "ol_cli", "translate-md",
            str(md_path), "-o", str(ol_out), "-c", str(OL_CONFIG_PATH),
        ],
        capture_output=True, text=True, env=env,
    )
    if ol_result.returncode != 0:
        return PathResult(
            exit_code=ol_result.returncode,
            stdout=ol_result.stdout,
            stderr=ol_result.stderr,
        )

    translated_md = ol_out / f"{input_path.stem}.md"
    if not translated_md.exists():
        return PathResult(exit_code=1, stderr="OL CLI did not produce translated MD")

    orf_out = output_dir / "orf" / "result.docx"
    orf_out.parent.mkdir(parents=True, exist_ok=True)
    orf_result = subprocess.run(
        [
            sys.executable, "-m", "orf.cli", "apply-md",
            str(translated_md), "--target-format", "docx", "--output", str(orf_out),
        ],
        capture_output=True, text=True, env=env,
    )
    return PathResult(
        exit_code=orf_result.returncode,
        stdout=orf_result.stdout,
        stderr=orf_result.stderr,
        docx_path=orf_out if orf_out.exists() else None,
    )


def _run_path(path: str, input_path: Path, output_dir: Path) -> PathResult:
    if path == "xliff_mcp":
        return _run_xliff_mcp(input_path, output_dir)
    if path == "xliff_cli":
        return _run_xliff_cli(input_path, output_dir)
    if path == "md_mcp":
        return _run_md_mcp(input_path, output_dir)
    if path == "md_cli":
        return _run_md_cli(input_path, output_dir)
    raise ValueError(f"Unknown path: {path}")


def _assert_docx_translated(result: PathResult, label: str) -> None:
    assert result.exit_code == 0, (
        f"{label}: rc={result.exit_code}; stderr={result.stderr[:500]!r}"
    )
    assert result.docx_path is not None and result.docx_path.exists(), (
        f"{label}: DOCX not produced at {result.docx_path}"
    )
    with zipfile.ZipFile(result.docx_path) as zf:
        assert "word/document.xml" in zf.namelist(), f"{label}: missing word/document.xml"
        doc_xml = zf.read("word/document.xml").decode("utf-8")
    assert any(m in doc_xml for m in TRANSLATION_MARKERS), (
        f"{label}: no translation marker in DOCX: {doc_xml[:500]}"
    )


class TestPipelineMultiformat:

    @pytest.mark.parametrize("path", ["xliff_mcp", "xliff_cli"])
    @pytest.mark.skip(reason="XLIFF skeleton preserves input format; DOCX output requires DOCX input")
    def test_xliff_on_pptx_input(
        self, path, sample_pptx_path, use_fake_llm, tmp_path: Path
    ):
        result = _run_path(path, sample_pptx_path, tmp_path / f"pptx_{path}")
        _assert_docx_translated(result, f"PPTX/{path}")

    @pytest.mark.parametrize("path", ["xliff_mcp", "xliff_cli"])
    @pytest.mark.skip(reason="XLIFF skeleton preserves input format; DOCX output requires DOCX input")
    def test_xliff_on_pdf_input(
        self, path, sample_pdf_path, use_fake_llm, tmp_path: Path
    ):
        result = _run_path(path, sample_pdf_path, tmp_path / f"pdf_{path}")
        _assert_docx_translated(result, f"PDF/{path}")

    @pytest.mark.parametrize("path", ["md_mcp", "md_cli"])
    def test_md_on_pptx_input(
        self, path, sample_pptx_path, use_fake_llm, tmp_path: Path
    ):
        result = _run_path(path, sample_pptx_path, tmp_path / f"pptx_{path}")
        _assert_docx_translated(result, f"PPTX/{path}")

    @pytest.mark.parametrize("path", ["md_mcp", "md_cli"])
    def test_md_on_pdf_input(
        self, path, sample_pdf_path, use_fake_llm, tmp_path: Path
    ):
        result = _run_path(path, sample_pdf_path, tmp_path / f"pdf_{path}")
        _assert_docx_translated(result, f"PDF/{path}")
