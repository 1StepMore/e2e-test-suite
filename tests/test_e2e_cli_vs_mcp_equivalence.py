"""CLI-vs-MCP equivalence: the same OPP input must extract the same substance.

Rebuilt after e2e-test-suite#102 (11 e2e files existed only on one machine and
were never committed, so CI never ran them).

The invariant under test is a *substance* invariant, not a byte invariant. The
CLI and the MCP tool are two different front-ends over the same
``OPPPipeline``; they legitimately differ in where they write (``--output-dir``
vs the tool's ``resource_dir``) and in whether they print a ``request_id``.
What must NOT differ is the extracted markdown body or the number of XLIFF
trans-units — those are what a translator downstream consumes.

Driven the way the rest of the suite drives it (``tests/test_e2e_opp_cli.py``:
``sys.executable -m opp``) and the way ``tests/test_e2e_opp_mcp.py`` drives the
MCP side (in-process tool call after ``_init_server``), so no transport or
event-loop scaffolding is invented here.

Hermetic: no API keys, no network, no LLM. OPP extraction is pure file I/O,
and :func:`_no_llm_configuration` strips the provider keys and the
``OMNI_TEST_FAKE_LLM`` seam for the whole module so every test here proves it.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.requires_opp,
]

_XLIFF_NS = "urn:oasis:names:tc:xliff:document:1.2"

#: Stripped for the whole module. The first two are the canonical OL provider
#: keys; the third is the suite's deterministic-fallback seam, which must not
#: be what makes an extraction succeed.
_LLM_ENV_VARS = ("AMD_API_KEY", "ZHIPU_API_KEY", "OMNI_TEST_FAKE_LLM")


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _trans_unit_ids(xliff_text: str) -> list[str]:
    """Return the ordered ``id`` attribute of every ``<trans-unit>``."""
    root = ET.fromstring(xliff_text)
    return [unit.get("id", "") for unit in root.iter(f"{{{_XLIFF_NS}}}trans-unit")]


def _trans_unit_count(xliff_text: str) -> int:
    return len(_trans_unit_ids(xliff_text))


def _run_opp_cli(docx_path: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
    """Extract via the shipped OPP CLI, exactly as ``tests/test_e2e_opp_cli.py`` does.

    ``cwd`` is the output dir because OPP creates a ``logs/`` directory
    relative to the process cwd at import time — pointing it at ``tmp_path``
    keeps the repo tree free of test residue.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "opp",
            "--target-format",
            "both",
            "--source-lang",
            "en",
            "--target-lang",
            "zh",
            "--output-dir",
            str(output_dir),
            str(docx_path),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=str(output_dir),
    )


def _call_opp_mcp_extract_document(docx_path: Path, resource_dir: Path) -> dict:
    """Call the real ``extract_document`` MCP tool in-process.

    Mirrors ``tests/test_e2e_opp_mcp.py``: ``_init_server`` plus the tool
    function imported from ``opp.mcp.server`` (a PEP 562 delegation to
    ``opp.mcp.tools.extract_document``), driven through ``asyncio.run`` because
    the tool is ``async``.
    """
    from opp.mcp.common import _init_server
    from opp.mcp.config import load_config
    from opp.mcp.server import extract_document

    resource_dir.mkdir(parents=True, exist_ok=True)
    config = replace(
        load_config(),
        resource_storage_dir=resource_dir,
    )
    _init_server(config)
    return asyncio.run(
        extract_document(
            file_path=str(docx_path),
            output_formats=["both"],
            source_lang="en",
            target_lang="zh",
            resource_dir=str(resource_dir),
        )
    )


@pytest.fixture(scope="module", autouse=True)
def _no_llm_configuration() -> None:
    """Remove every LLM key and the fake seam for the whole module.

    Without this the file would only be *probably* hermetic — it would inherit
    whatever the ambient environment happened to export. Restored on teardown
    by the suite's autouse ``_isolate_process_state`` fixture.
    """
    for name in _LLM_ENV_VARS:
        os.environ.pop(name, None)
    yield


@pytest.fixture(scope="module")
def opp_mcp_env(tmp_path_factory: pytest.TempPathFactory):
    """Bind the OPP MCP path validator to pytest's temp root; restore globals.

    Two things need care here:

    * ``opp.mcp.common`` holds module-level ``_config`` / ``_validator`` /
      ``_pipeline`` / ``_serializer`` singletons, so a test that calls
      ``_init_server`` would leave its config behind for the rest of the
      session. Snapshot and restore rather than leak.
    * OPP's config loader prefers the unified ``MCP_ALLOWED_DIRECTORIES`` over
      ``OPP_MCP_ALLOWED_DIRS``, so the unified name must be absent for the
      module-specific value to take effect (the same trap
      ``tests/security/test_ol_mcp_path_traversal.py`` documents for OL).
    """
    from opp.mcp import common as opp_mcp_common

    # pytest's session temp root: covers both module- and function-scoped
    # tmp_path values, and is strictly narrower than the /tmp default that
    # tests/conftest.py establishes.
    tmp_root = tmp_path_factory.getbasetemp().parent
    patcher = pytest.MonkeyPatch()
    patcher.delenv("MCP_ALLOWED_DIRECTORIES", raising=False)
    patcher.setenv("OPP_MCP_ALLOWED_DIRS", str(tmp_root))

    saved = {
        name: getattr(opp_mcp_common, name)
        for name in ("_config", "_validator", "_pipeline", "_serializer")
    }
    try:
        yield tmp_root
    finally:
        for name, value in saved.items():
            setattr(opp_mcp_common, name, value)
        patcher.undo()


# ─────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────


class TestCliVsMcpEquivalence:
    """The CLI path and the MCP tool path must extract the same substance."""

    def test_markdown_content_matches(
        self, sample_docx_path: Path, tmp_path: Path, opp_mcp_env: Path
    ) -> None:
        """CLI ``opp --target-format both`` and MCP ``extract_document`` emit the same markdown."""
        cli_dir = tmp_path / "cli_out"
        cli = _run_opp_cli(sample_docx_path, cli_dir)
        assert cli.returncode == 0, f"OPP CLI failed: {cli.stderr}"

        cli_md = cli_dir / f"{sample_docx_path.stem}.md"
        assert cli_md.is_file(), f"CLI produced no markdown at {cli_md}"
        cli_md_text = cli_md.read_text(encoding="utf-8")
        assert cli_md_text.strip(), "CLI produced empty markdown"

        mcp_result = _call_opp_mcp_extract_document(sample_docx_path, tmp_path / "mcp_out")
        assert mcp_result["success"] is True, f"MCP extract failed: {mcp_result}"
        mcp_md_text = mcp_result["content"]["md_content"]
        assert mcp_md_text, "MCP extract returned empty markdown"

        assert mcp_md_text == cli_md_text, (
            f"CLI and MCP markdown diverged: CLI={len(cli_md_text)} chars, "
            f"MCP={len(mcp_md_text)} chars"
        )

    def test_trans_unit_count_matches(
        self, sample_docx_path: Path, tmp_path: Path, opp_mcp_env: Path
    ) -> None:
        """Both paths emit the same number of ``<trans-unit>`` elements."""
        cli_dir = tmp_path / "cli_out"
        cli = _run_opp_cli(sample_docx_path, cli_dir)
        assert cli.returncode == 0, f"OPP CLI failed: {cli.stderr}"

        cli_xlf = cli_dir / f"{sample_docx_path.stem}.xlf"
        assert cli_xlf.is_file(), f"CLI produced no XLIFF at {cli_xlf}"
        cli_xliff_text = cli_xlf.read_text(encoding="utf-8")

        mcp_result = _call_opp_mcp_extract_document(sample_docx_path, tmp_path / "mcp_out")
        assert mcp_result["success"] is True, f"MCP extract failed: {mcp_result}"
        mcp_xliff_text = mcp_result["content"]["xliff_content"]
        assert mcp_xliff_text, "MCP extract returned empty XLIFF"

        cli_count = _trans_unit_count(cli_xliff_text)
        mcp_count = _trans_unit_count(mcp_xliff_text)

        # The sample DOCX carries a 3x2 table, so "more than one trans-unit" is
        # a meaningful floor: an empty XLIFF would make the equality vacuous.
        assert cli_count > 1, (
            f"sample DOCX yielded only {cli_count} trans-unit(s); "
            "the comparison below would be vacuous"
        )
        assert cli_count == mcp_count, (
            f"trans-unit count diverged: CLI={cli_count}, MCP={mcp_count}. "
            f"CLI ids={_trans_unit_ids(cli_xliff_text)} "
            f"MCP ids={_trans_unit_ids(mcp_xliff_text)}"
        )

    def test_mcp_reported_unit_count_agrees_with_its_own_payload(
        self, sample_docx_path: Path, tmp_path: Path, opp_mcp_env: Path
    ) -> None:
        """``xliff_units_count`` matches the count inside the returned XLIFF text.

        This is the self-consistency half of the equivalence contract: if the
        two front-ends ever agreed only because both were wrong the same way,
        this check is what would catch it.
        """
        mcp_result = _call_opp_mcp_extract_document(sample_docx_path, tmp_path / "mcp_out")
        assert mcp_result["success"] is True, f"MCP extract failed: {mcp_result}"

        content = mcp_result["content"]
        actual = _trans_unit_count(content["xliff_content"])
        reported = content["xliff_units_count"]

        assert reported == actual, (
            f"MCP envelope reports xliff_units_count={reported} but the returned "
            f"XLIFF holds {actual} trans-units"
        )

    def test_cli_manifest_reports_the_same_counts(
        self, sample_docx_path: Path, tmp_path: Path, opp_mcp_env: Path
    ) -> None:
        """The CLI manifest's trans-unit count equals the XLIFF beside it."""
        cli_dir = tmp_path / "cli_out"
        cli = _run_opp_cli(sample_docx_path, cli_dir)
        assert cli.returncode == 0, f"OPP CLI failed: {cli.stderr}"

        manifest_path = cli_dir / f"{sample_docx_path.stem}_manifest.json"
        assert manifest_path.is_file(), f"CLI produced no manifest at {manifest_path}"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        xlf_path = cli_dir / f"{sample_docx_path.stem}.xlf"
        actual = _trans_unit_count(xlf_path.read_text(encoding="utf-8"))
        reported = manifest["extraction"]["outputs"]["xliff"]["trans_unit_count"]

        assert reported == actual, (
            f"manifest reports trans_unit_count={reported} but the XLIFF holds {actual}"
        )

    def test_module_runs_with_no_llm_configuration(
        self, sample_docx_path: Path, tmp_path: Path, opp_mcp_env: Path
    ) -> None:
        """Both front-ends extract with no provider key and no fake seam set.

        OPP extraction is not a translation step, so it must not need an LLM.
        This asserts the property that lets the whole file be a tier-1
        (hermetic) test, and fails loudly if a future change starts gating OPP
        extraction behind OL's provider-key check.
        """
        for name in _LLM_ENV_VARS:
            assert name not in os.environ, f"{name} leaked back into the environment"

        cli = _run_opp_cli(sample_docx_path, tmp_path / "cli_out")
        assert cli.returncode == 0, f"OPP CLI needs LLM configuration: {cli.stderr}"

        mcp_result = _call_opp_mcp_extract_document(sample_docx_path, tmp_path / "mcp_out")
        assert mcp_result["success"] is True, (
            f"OPP MCP extract needs LLM configuration: {mcp_result}"
        )
