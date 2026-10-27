"""Shared fixtures for the 4-path e2e pipeline tests.

Activated by:
  - OMNI_TEST_FAKE_LLM=1 (intercepted by ol_cli.py)
  - OMNI_TEST_FAKE_PANDOC=1 (intercepted by orf/cli.py)
"""

import subprocess
import zipfile
from pathlib import Path

import pytest


@pytest.fixture
def use_fake_llm(monkeypatch):
    """Marker fixture — sets OMNI_TEST_FAKE_LLM=1 and OMNI_TEST_FAKE_PANDOC=1.

    The OL CLI reads OMNI_TEST_FAKE_LLM=1 and short-circuits to _FakeModelPool.
    The ORF CLI reads OMNI_TEST_FAKE_PANDOC=1 and monkey-patches subprocess.run
    to _FakePandocRunner. Setting both yields a fully hermetic chain that
    needs no real API key or pandoc binary.
    """
    monkeypatch.setenv("OMNI_TEST_FAKE_LLM", "1")
    monkeypatch.setenv("OMNI_TEST_FAKE_PANDOC", "1")
    return True


class _FakeModelPool:
    """Drop-in for ol_pool.router.ModelPool.

    Maps EN→ZH deterministically for any input. Returns text that is
    demonstrably different from source. Accepts both the 3-arg MD call
    shape and the 4-arg XLIFF call shape (with `context=None`).
    """

    _TRANSLATE_MAP: dict = {
        "Hello": "你好",
        "World": "世界",
        "User Manual": "用户手册",
        "Test": "测试",
        "Chapter": "章节",
        "Section": "节",
        "Introduction": "介绍",
        "Feature": "功能",
        "Function": "功能",
        "Welcome": "欢迎",
    }

    async def translate(self, *args, **kwargs):
        # Accept any call shape: 3-arg (text, src, tgt), 4-arg
        # (text, src, tgt, context), or 5-arg (text, src, tgt, context, role).
        text = args[0] if args else kwargs.get("text", "")
        if text in self._TRANSLATE_MAP:
            return self._TRANSLATE_MAP[text]
        # Default: return a safe ZH marker that won't break XLIFF XML
        # (source may contain '&', '<', '>' chars that break <target>).
        return "[ZH]"


class _FakePandocRunner:
    """Drop-in for subprocess.run when OMNI_TEST_FAKE_PANDOC=1.

    Writes a format-appropriate stub container at the ``-o`` output path and
    returns a ``_CompletedProcessStub`` shaped like a real ``CompletedProcess``
    (so ``result.check_returncode()`` works — ORF's md2pptx pandoc fallback
    calls it, see ORF#71).

    ``check=True`` is honored like ``subprocess.run``: a nonzero ``returncode``
    raises ``subprocess.CalledProcessError`` instead of being swallowed.

    Accepts both ``(cmd, *args, **kwargs)`` and ``(args=cmd, **kwargs)`` call
    shapes.
    """

    def __init__(self, returncode: int = 0, stdout=b"", stderr=b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def __call__(self, cmd=None, *args, **kwargs):
        if cmd is None:
            try:
                cmd = kwargs.get("args") or kwargs.get("cmd")
            except Exception:
                cmd = None
        check = bool(kwargs.get("check", False))
        output_path = None
        if isinstance(cmd, (list, tuple)) and len(cmd) > 0:
            try:
                if "-o" in cmd:
                    output_path = cmd[cmd.index("-o") + 1]
            except (ValueError, IndexError):
                output_path = None
        # A failing real conversion produces no output file; mirror that.
        if output_path is not None and self.returncode == 0:
            _write_stub_output(output_path)
        result = _CompletedProcessStub(
            args=cmd, returncode=self.returncode, stdout=self.stdout, stderr=self.stderr
        )
        if check:
            result.check_returncode()
        return result


class _CompletedProcessStub:
    """Minimal CompletedProcess-shaped result for fake subprocess calls."""

    def __init__(self, args, returncode, stdout=b"", stderr=b""):
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def check_returncode(self) -> None:
        """Raise CalledProcessError on nonzero rc, exactly like subprocess."""
        if self.returncode:
            raise subprocess.CalledProcessError(
                self.returncode, self.args, output=self.stdout, stderr=self.stderr
            )
        return None


_DOCX_DOCUMENT_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:body><w:p><w:r><w:t>用户手册</w:t></w:r></w:p>'
    '<w:p><w:r><w:t>欢迎使用</w:t></w:r></w:p></w:body></w:document>'
)
_DOCX_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '</Types>'
)
_OFFICE_RELS_NS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
)
_RELS_OFFICE_DOC_SUFFIX = '</Relationships>'


def _write_zip(path: Path, entries) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in entries:
            zf.writestr(name, payload)


def _write_zip_with_mimetype(path: Path, mimetype: str, entries) -> None:
    """ODT/EPUB shape: `mimetype` must be the FIRST entry and ZIP_STORED."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", mimetype, compress_type=zipfile.ZIP_STORED)
        for name, payload in entries:
            zf.writestr(name, payload)


def _write_stub_docx(path) -> None:
    """Thin alias for :func:`_write_stub_output` (DOCX-shaped targets)."""
    _write_stub_output(path)


def _write_stub_output(path) -> None:
    """Write a format-appropriate stub container at `path`.

    Dispatches on the output suffix so a `.pptx`/`.odt`/`.epub`/… target never
    silently receives DOCX bytes (e2e#225). Unknown suffixes raise ValueError
    instead of writing a mislabeled file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()

    if suffix == ".docx":
        _write_zip(
            path,
            [
                ("word/document.xml", _DOCX_DOCUMENT_XML),
                ("[Content_Types].xml", _DOCX_CONTENT_TYPES),
                (
                    "_rels/.rels",
                    _OFFICE_RELS_NS
                    + '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                    + _RELS_OFFICE_DOC_SUFFIX,
                ),
            ],
        )
        return

    if suffix == ".pptx":
        pptx_content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
            '</Types>'
        )
        pptx_rels = (
            _OFFICE_RELS_NS
            + '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>'
            + _RELS_OFFICE_DOC_SUFFIX
        )
        presentation_xml = (
            '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
            "<p:sldIdLst/></p:presentation>"
        )
        _write_zip(
            path,
            [
                ("[Content_Types].xml", pptx_content_types),
                ("_rels/.rels", pptx_rels),
                ("ppt/presentation.xml", presentation_xml),
            ],
        )
        return

    if suffix == ".odt":
        _write_zip_with_mimetype(
            path,
            "application/vnd.oasis.opendocument.text",
            [
                (
                    "content.xml",
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<office:document-content '
                    'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0">'
                    "<office:body/></office:document-content>",
                ),
            ],
        )
        return

    if suffix == ".epub":
        _write_zip_with_mimetype(
            path,
            "application/epub+zip",
            [
                (
                    "META-INF/container.xml",
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<container version="1.0" '
                    'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                    '<rootfiles><rootfile full-path="OEBPS/content.xhtml" '
                    'media-type="application/xhtml+xml"/></rootfiles></container>',
                ),
                (
                    "OEBPS/content.xhtml",
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<html xmlns="http://www.w3.org/1999/xhtml"><body>'
                    "<p>用户手册</p></body></html>",
                ),
            ],
        )
        return

    if suffix == ".rtf":
        path.write_bytes(b"{\\rtf1\\ansi\\deff0 {\\pard \\u29992?\\u25143?\\par}}")
        return

    if suffix == ".icml":
        path.write_text(
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Document DOMVersion="18.0"><Story Self="story1">'
            "<ParagraphStyleRange><Content>用户手册</Content></ParagraphStyleRange>"
            "</Story></Document>",
            encoding="utf-8",
        )
        return

    if suffix == ".pdf":
        path.write_bytes(
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Count 0/Kids[]>>endobj\n"
            b"trailer<</Root 1 0 R>>\n"
            b"%%EOF\n"
        )
        return

    if suffix in (".html", ".htm"):
        path.write_text(
            "<!DOCTYPE html><html><body><p>用户手册</p></body></html>",
            encoding="utf-8",
        )
        return

    raise ValueError(
        f"OMNI_TEST_FAKE_PANDOC stub: unsupported output target {suffix or '<none>'} "
        f"for path {path} — refusing to write DOCX bytes under a foreign extension."
    )
