"""``orf apply-xliff --force``: warn-and-proceed on a cross-format backfill.

Rebuilt after e2e-test-suite#102 (11 e2e files existed only on one machine and
were never committed, so CI never ran them).

What the filename implies, and what is actually true
----------------------------------------------------
``--force`` reads like "ignore errors". It does not: ORF's XLIFF channel is
format-preserving, and there are three sequential guards that each reject a
skeleton whose container does not match ``--format``:

1. the skeleton **extension** check (``src/orf/commands/apply_xliff.py:204-217``),
2. the skeleton **ZIP content** check, which probes ``word/document.xml`` vs
   ``ppt/presentation.xml`` etc. (``:236-253``),
3. the **final converter gate** ``converter.validate_input`` (``:336``).

Guards 1 and 2 raise ``click.BadParameter`` (exit 2) without ``--force`` and
downgrade to a ``FORCE MODE`` warning with it. Guard 3 is the one ORF#86 fixed:
it used to re-reject *after* the force warnings had already been printed, so
``--force`` exited 1 with "Input file ... is not valid for pptx format" — a
contract that said "warn + proceed" in one place and "hard fail" in another.
``git blame`` puts the current ``if not force and not converter.validate_input(...)``
on commit 3ee61a9, with no later commit touching the file, and the tests below
confirm the behaviour at runtime rather than trusting that history.

Two contract details this file pins because they are easy to get wrong:

* the warning goes to **stderr** only. ``--json`` puts the envelope on stdout
  and the converter's own ``warnings`` array on stdout, and neither carries the
  FORCE MODE text — a test that asserts on the JSON payload alone would pass
  with the warning silently dropped.
* without ``--force`` the same invocation exits **2** and produces no file.

Hermetic: no API keys, no network, no LLM, no pandoc, no OPP. The fixtures are
a two-entry DOCX zip and a one-trans-unit XLIFF, both built by the helpers below.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.requires_orf,
]

#: ORF's own console handler prefixes warnings with this (src/orf/logging).
_WARNING_PREFIX = "[WARNING]"

#: The two literals ORF emits, one per guard. Matched on the stable head only
#: so a wording tweak in the trailing advice does not fail the test.
_FORCE_MODE_MARKER = "FORCE MODE:"


# ─────────────────────────────────────────────────────────────────────
# Fixture builders
# ─────────────────────────────────────────────────────────────────────


def _write_docx_skeleton(path: Path) -> Path:
    """A minimal but *real* DOCX zip: ``word/document.xml`` + ``[Content_Types].xml``.

    Real, not the 4-byte ``PK\\x03\\x04`` stub: with a stub the guards warn and
    then the converter fails to load the skeleton, so the test would be
    asserting on a run that ends in exit 1 rather than on warn-and-proceed.
    """
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        "<w:p><w:r><w:t>Hello World</w:t></w:r></w:p>"
        "</w:body>"
        "</w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("[Content_Types].xml", "<Types/>")
    return path


def _write_xliff(path: Path) -> Path:
    """XLIFF 1.2 with a single translated trans-unit."""
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">\n'
        '  <file original="input.docx" source-language="en" target-language="zh"\n'
        '        datatype="plaintext">\n'
        "    <body>\n"
        '      <trans-unit id="p_1" resname="para_index_0">\n'
        "        <source>Hello World</source>\n"
        '        <target state="translated">\u4f60\u597d\u4e16\u754c</target>\n'
        "      </trans-unit>\n"
        "    </body>\n"
        "  </file>\n"
        "</xliff>\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def force_case(tmp_path: Path) -> dict[str, Path]:
    """A DOCX-named skeleton plus an XLIFF, ready for a ``--format pptx`` backfill."""
    docx = _write_docx_skeleton(tmp_path / "input.docx")
    xliff = _write_xliff(tmp_path / "translation.xlf")
    return {"skeleton": docx, "xliff": xliff, "workdir": tmp_path / "work"}


def _run_apply_xliff(
    workdir: Path,
    skeleton: Path,
    xliff: Path,
    output: Path,
    target_format: str,
    force: bool,
    extra: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke the shipped ``orf`` CLI exactly as ``Omni_Re_Formatter``'s own
    tests do (``python -m orf.cli apply-xliff``).

    Two deliberate choices:

    * ``cwd=workdir`` — ORF's logging module creates ``logs/`` relative to the
      process cwd at import time, so this keeps the repo tree clean.
    * a per-invocation ``OMNI_CACHE_DIR`` — ORF checks its conversion cache
      *before* any of the three force guards, and the cache key does not
      include ``--force``. A warm shared cache would short-circuit the run and
      suppress the FORCE MODE line, making these assertions pass or fail for
      reasons unrelated to ``--force``.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["OMNI_CACHE_DIR"] = str(workdir / "cache")

    cmd = [
        sys.executable,
        "-m",
        "orf.cli",
        "apply-xliff",
        str(skeleton),
        "--xliff",
        str(xliff),
        "--output",
        str(output),
        "--format",
        target_format,
    ]
    if force:
        cmd.append("--force")
    cmd += extra or []

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=180,
        cwd=str(workdir),
        env=env,
    )


# ─────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────


class TestForceWarnsAndProceeds:
    """``--force`` downgrades a format-mismatch rejection to a warning."""

    def test_extension_mismatch_completes_with_warning(self, force_case: dict[str, Path]) -> None:
        """A ``.docx`` skeleton with ``--format pptx --force`` exits 0 and warns."""
        workdir = force_case["workdir"]
        output = workdir / "forced.pptx"

        result = _run_apply_xliff(
            workdir,
            force_case["skeleton"],
            force_case["xliff"],
            output,
            target_format="pptx",
            force=True,
        )

        combined = result.stdout + result.stderr
        assert result.returncode == 0, (
            f"--force did not complete the conversion (rc={result.returncode}). "
            f"ORF#86 fixed exactly this: the final converter gate used to re-reject "
            f"with exit 1 after the force warnings. Output:\n{combined}"
        )
        assert f"{_WARNING_PREFIX} {_FORCE_MODE_MARKER}" in result.stderr, (
            f"expected a FORCE MODE warning on stderr, got:\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        assert output.is_file(), f"--force exited 0 but wrote no output at {output}"
        assert zipfile.is_zipfile(output), f"{output} is not a valid zip container"

    def test_zip_content_mismatch_completes_with_warning(
        self, tmp_path: Path, force_case: dict
    ) -> None:
        """A ``.zip`` skeleton whose *contents* are DOCX also warns instead of failing.

        This is guard 2, reached only when the suffix is exactly ``.zip``: the
        extension check passes and the format probe on the zip entries is what
        catches the mismatch. A different warning from guard 1, so it is worth
        its own case.
        """
        zipped = tmp_path / "input.skeleton.zip"
        zipped.write_bytes(force_case["skeleton"].read_bytes())

        workdir = force_case["workdir"]
        output = workdir / "forced_from_zip.pptx"
        result = _run_apply_xliff(
            workdir,
            zipped,
            force_case["xliff"],
            output,
            target_format="pptx",
            force=True,
        )

        combined = result.stdout + result.stderr
        assert result.returncode == 0, (
            f"--force did not complete the zip-content mismatch (rc={result.returncode}):\n"
            f"{combined}"
        )
        assert f"{_WARNING_PREFIX} {_FORCE_MODE_MARKER}" in result.stderr, (
            f"expected a FORCE MODE warning on stderr, got:\n{combined}"
        )
        assert "Skeleton ZIP contains" in result.stderr, (
            f"expected the ZIP-content guard's warning wording, got:\n{combined}"
        )
        assert output.is_file(), f"--force exited 0 but wrote no output at {output}"

    def test_matching_format_needs_no_force(self, force_case: dict[str, Path]) -> None:
        """The control case: ``--format docx`` on a ``.docx`` warns about nothing."""
        workdir = force_case["workdir"]
        output = workdir / "matched.docx"

        result = _run_apply_xliff(
            workdir,
            force_case["skeleton"],
            force_case["xliff"],
            output,
            target_format="docx",
            force=False,
        )

        combined = result.stdout + result.stderr
        assert result.returncode == 0, f"matched-format backfill failed:\n{combined}"
        assert _FORCE_MODE_MARKER not in combined, (
            f"a format-preserving backfill emitted a FORCE MODE warning:\n{combined}"
        )
        assert output.is_file(), f"no output at {output}"
        assert zipfile.is_zipfile(output), f"{output} is not a valid DOCX zip"


class TestWithoutForceHardFails:
    """The same inputs without ``--force`` are rejected, loudly and early."""

    def test_extension_mismatch_exits_two_without_force(self, force_case: dict[str, Path]) -> None:
        """No ``--force`` on a mismatched extension: exit 2, no output, no warning."""
        workdir = force_case["workdir"]
        output = workdir / "noforce.pptx"

        result = _run_apply_xliff(
            workdir,
            force_case["skeleton"],
            force_case["xliff"],
            output,
            target_format="pptx",
            force=False,
        )

        combined = result.stdout + result.stderr
        assert result.returncode == 2, (
            f"expected click's UsageError exit code 2, got {result.returncode}:\n{combined}"
        )
        assert "Invalid value" in result.stderr, (
            f"expected a click BadParameter rejection on stderr:\n{combined}"
        )
        assert "does not match --format" in result.stderr, (
            f"rejection does not name the format mismatch:\n{combined}"
        )
        assert _FORCE_MODE_MARKER not in combined, (
            f"the rejected run must not also print a FORCE MODE warning:\n{combined}"
        )
        assert not output.exists(), f"rejected run still wrote {output}"

    def test_zip_content_mismatch_exits_two_without_force(
        self, tmp_path: Path, force_case: dict
    ) -> None:
        """No ``--force`` on a ``.zip`` whose contents are DOCX: exit 2 as well."""
        zipped = tmp_path / "input.skeleton.zip"
        zipped.write_bytes(force_case["skeleton"].read_bytes())

        workdir = force_case["workdir"]
        output = workdir / "noforce_from_zip.pptx"
        result = _run_apply_xliff(
            workdir,
            zipped,
            force_case["xliff"],
            output,
            target_format="pptx",
            force=False,
        )

        combined = result.stdout + result.stderr
        assert result.returncode == 2, f"expected exit 2, got {result.returncode}:\n{combined}"
        assert "Skeleton ZIP contains" in result.stderr, (
            f"expected the ZIP-content guard's rejection wording:\n{combined}"
        )
        assert not output.exists(), f"rejected run still wrote {output}"


class TestForceWarningPlumbing:
    """Where the warning is observable — and where it is not."""

    def test_warning_is_on_stderr_not_stdout(self, force_case: dict[str, Path]) -> None:
        """The FORCE MODE line is on stderr; stdout carries only the result line.

        Worth pinning because ORF's console handler is bound to stderr while
        the success message is a plain ``print`` to stdout, so an agent that
        parses stdout sees a clean run and misses the warning entirely.
        """
        workdir = force_case["workdir"]
        output = workdir / "forced_plumbing.pptx"

        result = _run_apply_xliff(
            workdir,
            force_case["skeleton"],
            force_case["xliff"],
            output,
            target_format="pptx",
            force=True,
        )

        assert result.returncode == 0, f"forced run failed: {result.stderr[-800:]}"
        assert _FORCE_MODE_MARKER in result.stderr, (
            f"FORCE MODE missing from stderr:\n{result.stderr}"
        )
        assert _FORCE_MODE_MARKER not in result.stdout, (
            f"FORCE MODE unexpectedly on stdout:\n{result.stdout}"
        )

    def test_json_envelope_reports_success_but_not_the_warning(
        self, force_case: dict[str, Path]
    ) -> None:
        """``--json`` + ``--force``: envelope on stdout, warning still on stderr.

        The envelope's ``warnings`` array mirrors the converter's own warnings
        and never contains the FORCE MODE text — ORF#86's contract is a console
        warning, not a machine-readable one. This test documents that gap so a
        future agent reading the JSON does not conclude the force was silent.
        """
        workdir = force_case["workdir"]
        output = workdir / "forced_json.pptx"

        result = _run_apply_xliff(
            workdir,
            force_case["skeleton"],
            force_case["xliff"],
            output,
            target_format="pptx",
            force=True,
            extra=["--json"],
        )

        assert result.returncode == 0, f"forced --json run failed: {result.stderr[-800:]}"
        envelope = json.loads(result.stdout)
        assert envelope["success"] is True, f"envelope reports failure: {envelope}"
        assert envelope["output_path"] == str(output), (
            f"envelope output_path {envelope.get('output_path')!r} != {output}"
        )
        assert _FORCE_MODE_MARKER in result.stderr, (
            "the FORCE MODE warning vanished under --json:\n" + result.stderr
        )
        assert _FORCE_MODE_MARKER not in result.stdout, (
            "FORCE MODE text must not leak into the JSON payload:\n" + result.stdout
        )
        assert all(
            _FORCE_MODE_MARKER not in item.get("message", "")
            for item in envelope.get("warnings", [])
        ), f"envelope warnings unexpectedly carry the FORCE MODE text: {envelope.get('warnings')}"

    def test_force_rejects_unknown_format_option_names(self, force_case: dict[str, Path]) -> None:
        """``apply-xliff`` has no ``--target-format`` and no ``--dry-run``.

        ``apply-md`` uses ``--target-format``; ``apply-xliff`` uses ``--format``.
        That inconsistency is real and easy to get wrong from memory, and the
        failure mode is a silent-looking "no such option" rather than a wrong
        conversion, so it earns an assertion.
        """
        workdir = force_case["workdir"]
        output = workdir / "wrong_flag.pptx"

        for bad_flag in ("--target-format", "--dry-run"):
            result = _run_apply_xliff(
                workdir,
                force_case["skeleton"],
                force_case["xliff"],
                output,
                target_format="pptx",
                force=True,
                extra=[bad_flag, "pptx"] if bad_flag == "--target-format" else [bad_flag],
            )
            assert result.returncode == 2, (
                f"{bad_flag} should be rejected with exit 2, got "
                f"{result.returncode}: {result.stdout + result.stderr}"
            )
            assert "No such option" in result.stderr, (
                f"{bad_flag} rejection does not say 'No such option':\n{result.stderr}"
            )
