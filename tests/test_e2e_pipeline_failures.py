"""Failure injection tests — parametrized over all 4 OPP→OL→ORF paths.

Extends tests/test_e2e_pipeline.py::TestErrorHandling (OPP-only) to cover
failure modes across the full chain. Asserts each path fails GRACEFULLY
(non-zero exit + informative error message), not silent crash.
"""

import asyncio
import json
import os
import subprocess
import sys
import textwrap
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, patch

import pytest


pytestmark = [pytest.mark.e2e, pytest.mark.real_chain, pytest.mark.failure]


PATHS = ["xliff_mcp", "xliff_cli", "md_mcp", "md_cli"]


@pytest.fixture
def use_fake_llm(monkeypatch):
    """Set OMNI_TEST_FAKE_LLM=1 + OMNI_TEST_FAKE_PANDOC=1 for the test.

    Defined inline (rather than imported from test_e2e_pipeline_fixtures)
    because pytest only auto-discovers fixtures from conftest.py.
    """
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


@dataclass
class PathResult:
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    docx_path: Optional[Path] = None
    details: dict = field(default_factory=dict)


def _make_subprocess_env(extra: Optional[dict] = None) -> dict:
    env = os.environ.copy()
    pp_parts = [str(TESTS_DIR)]
    pp_parts.extend(str(d) for d in SRC_DIRS if d.exists())
    if env.get("PYTHONPATH"):
        pp_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = ":".join(pp_parts)
    if extra:
        env.update(extra)
    return env


# ---------------------------------------------------------------------------
# Failure-injection helpers
# ---------------------------------------------------------------------------

def _mcp_failure_message(result_data: dict, fallback: str) -> str:
    """Flatten an OL MCP error envelope into one diagnostic line.

    The shipped error payload carries ``error.code``/``error.message`` plus a
    recovery hint (ol_mcp/_errors.py); warnings are a separate channel. Reading
    only ``warnings`` collapsed every failure to the generic fallback string and
    destroyed the diagnostic the assertions below depend on.
    """
    error = result_data.get("error") or {}
    recovery = result_data.get("recovery") or {}
    parts = [
        str(error.get("code") or ""),
        str(error.get("message") or ""),
        str(recovery.get("hint") or ""),
        *(str(w) for w in (result_data.get("warnings") or [])),
    ]
    return " | ".join(p for p in parts if p) or fallback

def _make_raising_pool_class(exc: BaseException):
    """Return a _FakeModelPool subclass whose translate raises `exc`.

    Signature matches the real ModelPool: `context` is a 4th positional
    arg (MCP code calls `pool.translate(text, src, tgt, context)`).
    """
    from tests.test_e2e_pipeline_fixtures import _FakeModelPool

    class _RaisingModelPool(_FakeModelPool):
        async def translate(self, text, source_lang, target_lang, context=None, **kwargs):
            raise exc

    return _RaisingModelPool


def _write_cli_failure_wrapper(
    tmp_path: Path,
    ol_subcommand: str,
    ol_args: list,
    raise_spec: str,
) -> Path:
    """Write a wrapper that patches the OL CLI's async translate functions
    to raise, then invokes ol_cli.main_entry() with the given subcommand + args.

    We patch ``_translate_md_async`` / ``_translate_xliff_async`` in their
    OWNING modules (``cli.translate_md`` / ``cli.translate_xliff``) AFTER
    importing ol_cli, rather than patching ``_FakeModelPool.translate``.
    This is necessary for three reasons:

    1. The OL CLI's translate functions already catch exceptions from
       pool.translate() internally and fall back to source text — so
       patching the pool doesn't cause a non-zero exit. Patching the
       async functions themselves lets the exception propagate up to the
       CLI's outer ``except Exception`` handler, which calls
       ``raise typer.Exit(code=PIPELINE_ERROR)`` (exit code 1).

    2. Since the 2026-07 OL refactor (Omni_Localizer 12679b1) these
       functions live in ``cli/translate_md.py`` / ``cli/translate_xliff.py``
       and ol_cli only re-exports them. The typer commands resolve the
       names from their owning module's globals, so a patch on the
       ``ol_cli`` re-export attributes would never be consulted. The
       modules must be fetched via ``importlib.import_module``:
       ``cli/__init__.py`` star-imports the command functions, so the
       package attribute ``cli.translate_md`` is the FUNCTION, not the
       submodule — ``import cli.translate_md as m`` would bind the
       function and the patch would land on a dead attribute.

    3. ``--no-cache`` is passed because OL's content-addressed cache
       (~/.omni_cache, persistent across runs) short-circuits BEFORE
       ``_translate_md_async`` / ``_translate_xliff_async`` are called —
       a cache hit would return rc=0 and the injected failure would
       never fire.
    """
    wrapper = tmp_path / "_omni_failure_wrapper.py"
    suite_root_str = str(SUITE_ROOT)
    wrapper.write_text(textwrap.dedent(f"""\
        import sys
        from pathlib import Path as _P
        _SUITE_ROOT = {suite_root_str!r}
        if _SUITE_ROOT not in sys.path:
            sys.path.insert(0, _SUITE_ROOT)
        import importlib
        import unittest.mock

        _exc_name, _, _msg = {raise_spec!r}.partition(":")
        _exc_map = {{"RuntimeError": RuntimeError, "ValueError": ValueError, "TimeoutError": TimeoutError}}
        _exc_cls = _exc_map.get(_exc_name, RuntimeError)
        _exc = _exc_cls(_msg)

        sys.argv = {["ol_cli", ol_subcommand] + ol_args + ["--no-cache"]!r}
        import ol_cli
        _md_channel = importlib.import_module("cli.translate_md")
        _xliff_channel = importlib.import_module("cli.translate_xliff")
        _md_channel._translate_md_async = unittest.mock.AsyncMock(side_effect=_exc)
        _xliff_channel._translate_xliff_async = unittest.mock.AsyncMock(side_effect=_exc)

        ol_cli.main_entry()
    """))
    return wrapper


# MD path calls load_config() AFTER the fake-LLM seam, so the config
# must be resolvable from the subprocess CWD.
OL_CONFIG_PATH = SUITE_ROOT / "Omni_Localizer" / "config" / "default.yaml"


# ---------------------------------------------------------------------------
# Pandoc side-effect (MD2DOCXConverter mock — mirrors test_e2e_pipeline.py)
# ---------------------------------------------------------------------------

_DOCUMENT_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:body><w:p><w:r><w:t>Translated content</w:t></w:r></w:p></w:body></w:document>'
)
_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '</Types>'
)
_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    '</Relationships>'
)


def _create_minimal_docx(docx_path) -> None:
    docx_path = Path(docx_path)
    docx_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", _DOCUMENT_XML)
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _RELS)


def _pandoc_side_effect(*args, **kwargs):
    from unittest.mock import MagicMock
    cmd = args[0] if args else kwargs.get("args", [])
    if "-o" in cmd:
        output_path = Path(cmd[cmd.index("-o") + 1])
        _create_minimal_docx(output_path)
    result = MagicMock()
    result.returncode = 0
    result.stdout = ""
    result.stderr = ""
    return result


# ---------------------------------------------------------------------------
# OPP extraction (shared by all 4 paths)
# ---------------------------------------------------------------------------

def _run_opp(input_docx: Path, output_dir: Path):
    from opp.pipeline import OPPPipeline

    output_dir.mkdir(parents=True, exist_ok=True)
    resource_dir = output_dir / "resources"
    resource_dir.mkdir(parents=True, exist_ok=True)
    pipeline = OPPPipeline(resource_storage_dir=resource_dir)
    result = pipeline.process_file(input_docx)
    if result is None or getattr(result, "extraction_result", None) is None:
        raise RuntimeError("OPP extraction returned no result")
    return pipeline, result


# ---------------------------------------------------------------------------
# Path A: xliff_mcp — OPP -> OL MCP translate_xliff -> XLIFF2DOCXConverter
# ---------------------------------------------------------------------------

def _run_xliff_mcp(
    input_docx: Path,
    output_dir: Path,
    failure_pool=None,
) -> PathResult:
    try:
        pipeline, result = _run_opp(input_docx, output_dir)
    except Exception as e:
        return PathResult(
            exit_code=1,
            stderr=f"OPP extraction failed: {type(e).__name__}: {e}",
        )

    xliff_path = output_dir / f"{input_docx.stem}.xlf"
    pipeline.generate_xliff(result.extraction_result, xliff_path, "en", "zh")
    if not xliff_path.exists():
        return PathResult(exit_code=1, stderr=f"OPP did not produce XLIFF: {xliff_path}")

    skeleton_path = pipeline.save_skeleton(
        result.extraction_result, input_docx.stem, output_dir
    )
    translated_xliff = output_dir / f"{input_docx.stem}_translated.xlf"

    pool_cls = failure_pool or _make_raising_pool_class(RuntimeError())
    # Patch ModelPool in the module that performs the lookup
    # (ol_mcp/translate_xliff.py imports it from ol_pool.router and calls
    # ModelPool.get_instance). ol_mcp.tools only re-exports the tool wrapper
    # and never binds ModelPool, so patching it there raises AttributeError.
    with patch("ol_mcp.translate_xliff.ModelPool") as MockPool:
        mock_instance = pool_cls()
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
        stderr_msg = _mcp_failure_message(result_data, "OL MCP returned success=False")
        return PathResult(exit_code=1, stderr=stderr_msg, details={"json": result_data})

    from orf.channels.xliff2docx import XLIFF2DOCXConverter

    converter = XLIFF2DOCXConverter()
    docx_output = output_dir / "result.docx"
    conv_result = converter.convert(
        input_skeleton=skeleton_path,
        xliff_path=translated_xliff,
        output_path=docx_output,
    )
    if not conv_result.success:
        return PathResult(
            exit_code=1,
            stderr="; ".join(str(e) for e in (conv_result.errors or ["ORF convert failed"])),
            docx_path=docx_output if docx_output.exists() else None,
        )
    return PathResult(exit_code=0, docx_path=docx_output)


# ---------------------------------------------------------------------------
# Path B: xliff_cli — OPP -> ol_cli translate-xliff -> orf.cli apply-xliff
# ---------------------------------------------------------------------------

def _run_xliff_cli(
    input_docx: Path,
    output_dir: Path,
    tmp_path: Path,
    raise_spec: Optional[str] = None,
) -> PathResult:
    try:
        pipeline, result = _run_opp(input_docx, output_dir)
    except Exception as e:
        return PathResult(
            exit_code=1,
            stderr=f"OPP extraction failed: {type(e).__name__}: {e}",
        )

    xliff_path = output_dir / f"{input_docx.stem}.xlf"
    pipeline.generate_xliff(result.extraction_result, xliff_path, "en", "zh")
    if not xliff_path.exists():
        return PathResult(exit_code=1, stderr=f"OPP did not produce XLIFF: {xliff_path}")

    skeleton_dir = output_dir / "orf"
    skeleton_path = pipeline.save_skeleton(
        result.extraction_result, input_docx.stem, skeleton_dir
    )

    ol_out = output_dir / "ol"
    ol_out.mkdir(parents=True, exist_ok=True)

    extra_env = {"OMNI_TEST_FAKE_LLM": "1", "OMNI_TEST_FAKE_PANDOC": "1"}

    if raise_spec:
        wrapper = _write_cli_failure_wrapper(
            tmp_path,
            "translate-xliff",
            [str(xliff_path), "-o", str(ol_out), "-c", str(OL_CONFIG_PATH)],
            raise_spec,
        )
        cmd = [sys.executable, str(wrapper)]
    else:
        cmd = [
            sys.executable, "-m", "ol_cli", "translate-xliff",
            str(xliff_path), "-o", str(ol_out), "-c", str(OL_CONFIG_PATH),
        ]

    env = _make_subprocess_env(extra_env)
    ol_result = subprocess.run(cmd, capture_output=True, text=True, env=env)

    if ol_result.returncode != 0:
        return PathResult(
            exit_code=ol_result.returncode,
            stdout=ol_result.stdout,
            stderr=ol_result.stderr,
            details={"ol_result": ol_result},
        )

    translated_xliff = ol_out / f"{input_docx.stem}.xlf"
    if not translated_xliff.exists():
        return PathResult(
            exit_code=1,
            stderr=f"OL CLI did not produce translated XLIFF: {translated_xliff}",
        )

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

    return PathResult(
        exit_code=orf_result.returncode,
        stdout=orf_result.stdout,
        stderr=orf_result.stderr,
        docx_path=orf_out if orf_out.exists() else None,
    )


# ---------------------------------------------------------------------------
# Path C: md_mcp — OPP -> OL MCP translate_md_text -> MD2DOCXConverter
# ---------------------------------------------------------------------------

def _run_md_mcp(
    input_docx: Path,
    output_dir: Path,
    failure_pool=None,
) -> PathResult:
    try:
        pipeline, result = _run_opp(input_docx, output_dir)
    except Exception as e:
        return PathResult(
            exit_code=1,
            stderr=f"OPP extraction failed: {type(e).__name__}: {e}",
        )

    md_path = output_dir / f"{input_docx.stem}.md"
    pipeline.generate_markdown(result.extraction_result, md_path)
    if not md_path.exists():
        return PathResult(exit_code=1, stderr=f"OPP did not produce MD: {md_path}")

    pool_cls = failure_pool or _make_raising_pool_class(RuntimeError())
    # See the xliff helper above: ModelPool is looked up in the module that
    # owns the translate function, not in ol_mcp.tools.
    with patch("ol_mcp.translate_md.ModelPool") as MockPool:
        mock_instance = pool_cls()
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
        stderr_msg = _mcp_failure_message(result_data, "OL MCP returned success=False")
        return PathResult(exit_code=1, stderr=stderr_msg, details={"json": result_data})

    translated_md = output_dir / f"{input_docx.stem}_translated.md"
    translated_md.write_text(result_data.get("translated", ""), encoding="utf-8")

    with patch("subprocess.run", side_effect=_pandoc_side_effect):
        from orf.channels.md2docx import MD2DOCXConverter

        converter = MD2DOCXConverter()
        docx_output = output_dir / "result.docx"
        conv_result = converter.convert(translated_md, docx_output)
    if not conv_result.success:
        return PathResult(
            exit_code=1,
            stderr="; ".join(str(e) for e in (conv_result.errors or ["ORF convert failed"])),
            docx_path=docx_output if docx_output.exists() else None,
        )
    return PathResult(exit_code=0, docx_path=docx_output)


# ---------------------------------------------------------------------------
# Path D: md_cli — OPP -> ol_cli translate-md -> orf.cli apply-md
# ---------------------------------------------------------------------------

def _run_md_cli(
    input_docx: Path,
    output_dir: Path,
    tmp_path: Path,
    raise_spec: Optional[str] = None,
) -> PathResult:
    try:
        pipeline, result = _run_opp(input_docx, output_dir)
    except Exception as e:
        return PathResult(
            exit_code=1,
            stderr=f"OPP extraction failed: {type(e).__name__}: {e}",
        )

    md_path = output_dir / f"{input_docx.stem}.md"
    pipeline.generate_markdown(result.extraction_result, md_path)
    if not md_path.exists():
        return PathResult(exit_code=1, stderr=f"OPP did not produce MD: {md_path}")

    ol_out = output_dir / "ol"
    ol_out.mkdir(parents=True, exist_ok=True)

    extra_env = {"OMNI_TEST_FAKE_LLM": "1", "OMNI_TEST_FAKE_PANDOC": "1"}

    if raise_spec:
        wrapper = _write_cli_failure_wrapper(
            tmp_path,
            "translate-md",
            [str(md_path), "-o", str(ol_out), "-c", str(OL_CONFIG_PATH)],
            raise_spec,
        )
        cmd = [sys.executable, str(wrapper)]
    else:
        cmd = [
            sys.executable, "-m", "ol_cli", "translate-md",
            str(md_path), "-o", str(ol_out), "-c", str(OL_CONFIG_PATH),
        ]

    env = _make_subprocess_env(extra_env)
    ol_result = subprocess.run(cmd, capture_output=True, text=True, env=env)

    if ol_result.returncode != 0:
        return PathResult(
            exit_code=ol_result.returncode,
            stdout=ol_result.stdout,
            stderr=ol_result.stderr,
            details={"ol_result": ol_result},
        )

    translated_md = ol_out / f"{input_docx.stem}.md"
    if not translated_md.exists():
        return PathResult(
            exit_code=1,
            stderr=f"OL CLI did not produce translated MD: {translated_md}",
        )

    orf_out = output_dir / "orf" / "result.docx"
    orf_out.parent.mkdir(parents=True, exist_ok=True)
    orf_result = subprocess.run(
        [
            sys.executable, "-m", "orf.cli", "apply-md",
            str(translated_md),
            "--target-format", "docx",
            "--output", str(orf_out),
        ],
        capture_output=True, text=True, env=env,
    )

    return PathResult(
        exit_code=orf_result.returncode,
        stdout=orf_result.stdout,
        stderr=orf_result.stderr,
        docx_path=orf_out if orf_out.exists() else None,
    )


# ---------------------------------------------------------------------------
# Path dispatcher
# ---------------------------------------------------------------------------

def _run_path(
    path: str,
    input_docx: Path,
    output_dir: Path,
    tmp_path: Path,
    failure_pool=None,
    raise_spec: Optional[str] = None,
) -> PathResult:
    if path == "xliff_mcp":
        return _run_xliff_mcp(input_docx, output_dir, failure_pool=failure_pool)
    if path == "xliff_cli":
        return _run_xliff_cli(input_docx, output_dir, tmp_path, raise_spec=raise_spec)
    if path == "md_mcp":
        return _run_md_mcp(input_docx, output_dir, failure_pool=failure_pool)
    if path == "md_cli":
        return _run_md_cli(input_docx, output_dir, tmp_path, raise_spec=raise_spec)
    raise ValueError(f"Unknown path: {path}")


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TestPathFailures:

    @pytest.mark.parametrize("path", PATHS)
    def test_ol_llm_exception_handled_gracefully(
        self, path, haier_real_docx_path, use_fake_llm, tmp_path, monkeypatch
    ):
        """LLM raises mid-translation: path must fail with rc != 0 AND
        stderr mentioning LLM/translation (informative, not silent crash)."""
        from tests.test_e2e_pipeline_fixtures import _FakeModelPool

        exc = RuntimeError("LLM down (test)")
        monkeypatch.setattr(
            _FakeModelPool, "translate", AsyncMock(side_effect=exc)
        )

        failure_pool = _make_raising_pool_class(exc)
        result = _run_path(
            path,
            haier_real_docx_path,
            tmp_path / path,
            tmp_path,
            failure_pool=failure_pool,
            raise_spec="RuntimeError:LLM down (test)",
        )

        assert result.exit_code != 0, (
            f"Path {path}: expected rc != 0, got rc={result.exit_code}; "
            f"stderr={result.stderr[:300]!r}"
        )
        stderr = result.stderr or ""
        assert "LLM" in stderr or "translation" in stderr.lower(), (
            f"Path {path}: expected informative error mentioning LLM/translation, "
            f"got stderr={stderr[:300]!r}"
        )

    @pytest.mark.parametrize("path", ["xliff_mcp", "xliff_cli"])
    def test_orf_xliff_parse_error_handled_gracefully(
        self, path, haier_real_docx_path, use_fake_llm, tmp_path, monkeypatch
    ):
        """Malformed XLIFF in ORF path: must fail with rc != 0 AND
        stderr mentioning XLIFF/malformed/parse."""
        from tests.test_e2e_pipeline_fixtures import _FakeModelPool

        exc = ValueError("malformed XLIFF (test)")
        monkeypatch.setattr(
            _FakeModelPool, "translate", AsyncMock(side_effect=exc)
        )

        failure_pool = _make_raising_pool_class(exc)
        result = _run_path(
            path,
            haier_real_docx_path,
            tmp_path / path,
            tmp_path,
            failure_pool=failure_pool,
            raise_spec="ValueError:malformed XLIFF (test)",
        )

        assert result.exit_code != 0, (
            f"Path {path}: expected rc != 0, got rc={result.exit_code}; "
            f"stderr={result.stderr[:300]!r}"
        )
        stderr = result.stderr or ""
        assert (
            "XLIFF" in stderr
            or "malformed" in stderr.lower()
            or "parse" in stderr.lower()
        ), (
            f"Path {path}: expected informative error mentioning XLIFF/malformed/parse, "
            f"got stderr={stderr[:300]!r}"
        )

    @pytest.mark.parametrize("path", PATHS)
    def test_opp_timeout_handled_gracefully(
        self, path, haier_real_docx_path, use_fake_llm, tmp_path, monkeypatch
    ):
        """OPP times out: path must fail with rc != 0 AND
        stderr mentioning OPP/timeout."""
        from opp.pipeline import OPPPipeline

        def slow_process_file(self, *args, **kwargs):
            time.sleep(0.05)
            raise TimeoutError("OPP timed out (test)")

        monkeypatch.setattr(OPPPipeline, "process_file", slow_process_file)

        result = _run_path(
            path,
            haier_real_docx_path,
            tmp_path / path,
            tmp_path,
        )

        assert result.exit_code != 0, (
            f"Path {path}: expected rc != 0, got rc={result.exit_code}; "
            f"stderr={result.stderr[:300]!r}"
        )
        stderr = result.stderr or ""
        assert "OPP" in stderr or "timeout" in stderr.lower(), (
            f"Path {path}: expected informative error mentioning OPP/timeout, "
            f"got stderr={stderr[:300]!r}"
        )
