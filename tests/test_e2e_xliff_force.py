"""``orf apply-xliff --force``: accepted, but inert — it is not a bypass.

Rebuilt after e2e-test-suite#102 (11 e2e files existed only on one machine and
were never committed, so CI never ran them); contract rewritten by
e2e-test-suite#64.

What the flag implies, and what is actually true
------------------------------------------------
``--force`` reads like "ignore errors". ORF's XLIFF channel is
format-preserving and there are three sequential guards that each reject a
skeleton whose container does not match ``--format``:

1. the skeleton **extension** check (``src/orf/commands/apply_xliff.py``),
2. the skeleton **ZIP content** check, which probes ``word/document.xml`` vs
   ``ppt/presentation.xml`` etc.,
3. the **final converter gate** ``converter.validate_input``.

Before #64, guards 1 and 2 raised ``click.BadParameter`` (exit 2) without
``--force`` and downgraded to a ``FORCE MODE`` warning with it. That downgrade
was a validation bypass, not a conversion: the backfill only ever rewrote the
declared content type, so a DOCX skeleton came out as a DOCX-shaped zip named
``cross.pptx`` / ``cross.epub``. python-pptx raised "not a PowerPoint file,
content type is ...wordprocessingml.document.main+xml"; an EPUB reader found no
``mimetype`` and no ``META-INF/container.xml``; python-docx happily opened the
``.epub`` one as a document. The CLI printed ``Created <path>`` and exited 0.

#64 removes the downgrade. All three guards now reject with or without
``--force``, and the flag is kept accepted so an existing caller gets the real
cross-format error instead of "No such option".

Three contract details this file pins:

* the rejection message is actionable: it names the detected source format,
  the requested ``--format``, says cross-format XLIFF backfill is not
  implemented, and names ``orf apply-md`` as the path that does work.
* a rejected cross-format request writes **no file** — and not merely "no file
  at the requested path": no file the target format's own library would accept
  is produced anywhere. Existence-plus-non-empty is what let the disguised
  artifact pass unnoticed.
* the same-format path with ``--force`` is untouched: exit 0, a real DOCX that
  python-docx opens.

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

#: The stable head of the cross-format rejection, one per guard. Matched on the
#: head only so a wording tweak in the trailing advice does not fail the test.
_NOT_IMPLEMENTED_MARKER = "Cross-format XLIFF backfill is not implemented"


# ─────────────────────────────────────────────────────────────────────
# Fixture builders
# ─────────────────────────────────────────────────────────────────────


_CONTENT_TYPES_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    "</Types>"
)

_PACKAGE_RELS_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/>'
    "</Relationships>"
)


def _write_docx_skeleton(path: Path) -> Path:
    """A minimal but *real* DOCX package: body part + content types + rels.

    Real, not the 4-byte ``PK\\x03\\x04`` stub: the content-level guard needs to
    actually detect DOCX so the rejection is attributable to the guard under
    test rather than to an unreadable input. It is also a valid OPC package
    (content types + ``_rels/.rels``), so a same-format backfill of it yields a
    DOCX python-docx can actually open -- which is what makes the
    format-validity assertions below meaningful instead of vacuous.
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
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES_XML)
        archive.writestr("_rels/.rels", _PACKAGE_RELS_XML)
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
        '        <target state="translated">你好世界</target>\n'
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
      before the skeleton guards, and the cache key does not include
      ``--force``. A warm shared cache would short-circuit the run, making
      these assertions pass or fail for reasons unrelated to the contract.
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


class TestForceIsInert:
    """``--force`` no longer downgrades either skeleton guard to a warning."""

    def test_extension_mismatch_still_rejected_with_force(
        self, force_case: dict[str, Path]
    ) -> None:
        """A ``.docx`` skeleton with ``--format pptx --force`` exits 2, no output."""
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
        assert result.returncode == 2, (
            f"--force must not buy a cross-format artifact; rc={result.returncode}\n"
            f"{combined}"
        )
        assert "does not match --format 'pptx'" in result.stderr, (
            f"rejection does not name the format mismatch:\n{combined}"
        )
        assert _NOT_IMPLEMENTED_MARKER in result.stderr, (
            f"rejection must say cross-format is not implemented:\n{combined}"
        )
        assert "orf apply-md" in result.stderr, (
            f"rejection must point at the MD path:\n{combined}"
        )
        assert "FORCE MODE" not in combined, (
            f"the FORCE MODE downgrade path must be gone:\n{combined}"
        )
        assert not output.exists(), f"--force still wrote {output}"

    def test_zip_content_mismatch_still_rejected_with_force(
        self, tmp_path: Path, force_case: dict
    ) -> None:
        """A ``.zip`` skeleton whose *contents* are DOCX is rejected too.

        This is guard 2, reached only when the suffix is exactly ``.zip``: the
        extension check passes and the format probe on the zip entries is what
        catches the mismatch. A different message from guard 1, so it earns its
        own case.
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
        assert result.returncode == 2, (
            f"--force must not buy a cross-format artifact; rc={result.returncode}\n"
            f"{combined}"
        )
        assert "Skeleton ZIP contains 'DOCX' format content" in result.stderr, (
            f"expected the ZIP-content guard's rejection wording, got:\n{combined}"
        )
        assert not output.exists(), f"--force still wrote {output}"

    def test_extensionless_skeleton_rejected_with_force(
        self, tmp_path: Path, force_case: dict
    ) -> None:
        """An extensionless skeleton skips guards 1-2; guard 3 must not yield to --force."""
        skeleton = tmp_path / "skeleton"
        skeleton.write_bytes(force_case["skeleton"].read_bytes())

        workdir = force_case["workdir"]
        output = workdir / "forced_noext.pptx"
        result = _run_apply_xliff(
            workdir,
            skeleton,
            force_case["xliff"],
            output,
            target_format="pptx",
            force=True,
        )

        combined = result.stdout + result.stderr
        assert result.returncode != 0, (
            f"--force must not bypass the final converter gate; "
            f"rc={result.returncode}\n{combined}"
        )
        assert "is not valid for pptx format" in combined, (
            f"expected the final validate_input gate to fire:\n{combined}"
        )
        assert not output.exists(), f"--force still wrote {output}"

    def test_matching_format_needs_no_force(self, force_case: dict[str, Path]) -> None:
        """The control case: ``--format docx`` on a ``.docx`` is accepted with --force."""
        workdir = force_case["workdir"]
        output = workdir / "matched.docx"

        result = _run_apply_xliff(
            workdir,
            force_case["skeleton"],
            force_case["xliff"],
            output,
            target_format="docx",
            force=True,
        )

        combined = result.stdout + result.stderr
        assert result.returncode == 0, f"matched-format backfill failed:\n{combined}"
        assert _NOT_IMPLEMENTED_MARKER not in combined, (
            f"a format-preserving backfill was rejected as cross-format:\n{combined}"
        )
        assert output.is_file(), f"no output at {output}"
        assert zipfile.is_zipfile(output), f"{output} is not a valid DOCX zip"

        from docx import Document

        doc = Document(str(output))
        assert len(doc.paragraphs) >= 1, "control DOCX has no paragraphs"


class TestWithoutForceHardFails:
    """The unforced path is unchanged — this contract predates #64 and still holds."""

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
        assert "FORCE MODE" not in combined, (
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


class TestNoDisguisedArtifact:
    """A rejected cross-format request leaves nothing the target format accepts.

    Existence-plus-non-empty is the check that let the pre-#64 artifact pass:
    a DOCX-shaped zip named ``cross.pptx`` exists and is 38 KB, yet python-pptx
    rejects it. These tests therefore ask the *target format's own library*.
    """

    @pytest.mark.parametrize("target_format", ["pptx", "epub"])
    def test_no_artifact_the_target_library_accepts(
        self, force_case: dict[str, Path], target_format: str
    ) -> None:
        workdir = force_case["workdir"]
        output = workdir / f"forced.{target_format}"

        result = _run_apply_xliff(
            workdir,
            force_case["skeleton"],
            force_case["xliff"],
            output,
            target_format=target_format,
            force=True,
        )
        assert result.returncode != 0, (
            f"--force must not succeed for {target_format}: rc={result.returncode}\n"
            f"{result.stdout}{result.stderr}"
        )

        produced = [p for p in workdir.iterdir() if p.is_file() and p.suffix != ".xlf"]
        assert produced == [], f"rejected run produced files: {[p.name for p in produced]}"
        if target_format == "pptx":
            from pptx import Presentation

            for path in produced:
                Presentation(str(path))  # would raise on a disguised DOCX zip
        else:
            for path in produced:
                names = zipfile.ZipFile(path).namelist()
                assert "mimetype" in names and "META-INF/container.xml" in names


class TestInertFlagPlumbing:
    """Where the flag is observable — and where it is not."""

    def test_inert_notice_is_on_stderr_not_stdout(self, force_case: dict[str, Path]) -> None:
        """The "--force is accepted but inert" note is a console warning on stderr.

        Worth pinning because ORF's console handler is bound to stderr while
        the rejection itself is click's own stderr output: both land in the same
        stream, and an agent parsing stdout sees no trace of either.
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

        assert result.returncode != 0, f"forced run unexpectedly succeeded: {result.stdout}"
        assert f"{_WARNING_PREFIX} --force is accepted but inert" in result.stderr, (
            f"inert-flag notice missing from stderr:\n{result.stderr}"
        )
        assert "--force is accepted but inert" not in result.stdout, (
            f"inert-flag notice unexpectedly on stdout:\n{result.stdout}"
        )

    def test_json_envelope_reports_the_failure(self, force_case: dict[str, Path]) -> None:
        """``--json`` + ``--force``: the envelope must not claim success."""
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

        assert result.returncode != 0, f"--force unexpectedly succeeded: {result.stdout}"
        assert not output.exists(), f"--force wrote {output}"
        assert '"success": true' not in result.stdout, (
            f"a success envelope would tell an agent the conversion happened:\n"
            f"{result.stdout}"
        )

    def test_json_envelope_still_parses_on_same_format(self, force_case: dict[str, Path]) -> None:
        """The control under ``--json``: a real success envelope, parseable."""
        workdir = force_case["workdir"]
        output = workdir / "matched_json.docx"

        result = _run_apply_xliff(
            workdir,
            force_case["skeleton"],
            force_case["xliff"],
            output,
            target_format="docx",
            force=True,
            extra=["--json"],
        )

        assert result.returncode == 0, f"same-format run failed: {result.stderr[-800:]}"
        envelope = json.loads(result.stdout)
        assert envelope["success"] is True, f"envelope reports failure: {envelope}"
        assert envelope["output_path"] == str(output), (
            f"envelope output_path {envelope.get('output_path')!r} != {output}"
        )

    def test_apply_xliff_rejects_unknown_format_option_names(self, force_case: dict[str, Path]) -> None:
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
