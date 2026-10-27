"""Contract tests for the OMNI_TEST_FAKE_PANDOC stub.

Locks two booked defects:

* ORF#71 — ``_CompletedProcessStub`` must be CompletedProcess-shaped, i.e. it
  must expose ``check_returncode()``. ORF's md2pptx pandoc fallback calls it
  on the ``subprocess.run`` result, so a stub without it raises
  ``AttributeError``.
* e2e#225 — the fake runner must write a container matching the requested
  output format instead of always writing DOCX bytes under whatever suffix
  follows ``-o`` (which made "file exists / is a zip" assertions pass falsely
  for .pptx/.epub/.odt/.icml/.rtf/.pdf targets).

Hermetic: no network, no pandoc binary, no md2pptx binary.
"""

import subprocess
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.test_e2e_pipeline_fixtures import (
    _CompletedProcessStub,
    _FakePandocRunner,
    _write_stub_output,
)

MD_SOURCE = """---
title: User Manual
source_lang: en
target_lang: zh
---

# 用户手册

欢迎使用
"""


def _run_to(tmp_path: Path, filename: str, **runner_kwargs):
    """Invoke the fake runner with a pandoc-shaped command; return written path."""
    out = tmp_path / filename
    runner = _FakePandocRunner(**runner_kwargs)
    result = runner(["pandoc", str(tmp_path / "in.md"), "-o", str(out)])
    return out, result


# ---------------------------------------------------------------------------
# #225: format-aware stub containers
# ---------------------------------------------------------------------------


def test_docx_target_writes_word_document_zip(tmp_path):
    out, result = _run_to(tmp_path, "out.docx")
    assert result.returncode == 0
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert "word/document.xml" in names
    assert "ppt/presentation.xml" not in names


def test_pptx_target_writes_presentation_zip_not_docx(tmp_path):
    out, _ = _run_to(tmp_path, "out.pptx")
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        content_types = zf.read("[Content_Types].xml").decode("utf-8")
        rels = zf.read("_rels/.rels").decode("utf-8")
        presentation = zf.read("ppt/presentation.xml").decode("utf-8")
    assert "ppt/presentation.xml" in names
    assert "word/document.xml" not in names
    assert "presentationml.presentation.main+xml" in content_types
    assert "ppt/presentation.xml" in rels
    assert "<p:sldIdLst/>" in presentation


def test_odt_mimetype_is_first_stored_entry(tmp_path):
    out, _ = _run_to(tmp_path, "out.odt")
    with zipfile.ZipFile(out) as zf:
        first = zf.infolist()[0]
        assert first.filename == "mimetype"
        assert first.compress_type == zipfile.ZIP_STORED
        assert zf.read("mimetype").decode("utf-8") == (
            "application/vnd.oasis.opendocument.text"
        )
        assert "content.xml" in zf.namelist()


def test_epub_mimetype_is_first_stored_entry(tmp_path):
    out, _ = _run_to(tmp_path, "out.epub")
    with zipfile.ZipFile(out) as zf:
        first = zf.infolist()[0]
        assert first.filename == "mimetype"
        assert first.compress_type == zipfile.ZIP_STORED
        assert zf.read("mimetype").decode("utf-8") == "application/epub+zip"
        names = zf.namelist()
    assert "META-INF/container.xml" in names
    assert "OEBPS/content.xhtml" in names


def test_rtf_target_has_rtf_header(tmp_path):
    out, _ = _run_to(tmp_path, "out.rtf")
    assert out.read_bytes().startswith(b"{\\rtf1\\ansi\\deff0")


def test_icml_target_has_xml_declaration_and_document_root(tmp_path):
    out, _ = _run_to(tmp_path, "out.icml")
    text = out.read_text(encoding="utf-8")
    assert text.startswith('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
    assert "<Document " in text


def test_pdf_target_has_pdf_magic_and_eof(tmp_path):
    out, _ = _run_to(tmp_path, "out.pdf")
    data = out.read_bytes()
    assert data.startswith(b"%PDF-1.4")
    assert data.rstrip().endswith(b"%%EOF")


def test_html_target_has_doctype_and_body(tmp_path):
    out, _ = _run_to(tmp_path, "out.html")
    text = out.read_text(encoding="utf-8")
    assert text.startswith("<!DOCTYPE html><html><body>")
    assert text.endswith("</body></html>")


def test_unknown_suffix_raises_value_error_naming_target(tmp_path):
    out = tmp_path / "out.xyz"
    with pytest.raises(ValueError, match=r"\.xyz"):
        _write_stub_output(out)
    assert not out.exists(), "must not leave a mislabeled file behind"


def test_fake_runner_unknown_suffix_raises(tmp_path):
    with pytest.raises(ValueError, match=r"\.xyz"):
        _FakePandocRunner()(["pandoc", "in.md", "-o", str(tmp_path / "out.xyz")])


# ---------------------------------------------------------------------------
# #71: CompletedProcess shape + check=True semantics
# ---------------------------------------------------------------------------


def test_check_returncode_zero_returns_none():
    assert _CompletedProcessStub(args=["pandoc"], returncode=0).check_returncode() is None


def test_check_returncode_nonzero_raises_called_process_error():
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        _CompletedProcessStub(
            args=["pandoc", "-o", "x.pptx"],
            returncode=1,
            stdout=b"",
            stderr=b"boom",
        ).check_returncode()
    assert excinfo.value.returncode == 1
    assert excinfo.value.cmd == ["pandoc", "-o", "x.pptx"]
    assert excinfo.value.stderr == b"boom"


def test_fake_runner_honors_check_true_on_nonzero_rc(tmp_path):
    runner = _FakePandocRunner(returncode=1, stderr=b"boom")
    with pytest.raises(subprocess.CalledProcessError):
        runner(["pandoc", "in.md", "-o", str(tmp_path / "out.pptx")], check=True)


def test_fake_runner_honors_check_true_on_zero_rc(tmp_path):
    runner = _FakePandocRunner()
    result = runner(["pandoc", "in.md", "-o", str(tmp_path / "out.pptx")], check=True)
    assert result.returncode == 0
    assert (tmp_path / "out.pptx").exists()


def test_fake_runner_accepts_args_keyword_shape(tmp_path):
    out = tmp_path / "out.docx"
    result = _FakePandocRunner()(args=["pandoc", "in.md", "-o", str(out)])
    assert result.returncode == 0
    assert out.exists()
    with zipfile.ZipFile(out) as zf:
        assert "word/document.xml" in zf.namelist()


# ---------------------------------------------------------------------------
# #71 end-to-end regression: md2pptx -> pandoc fallback path
# ---------------------------------------------------------------------------


def test_md2pptx_pandoc_fallback_writes_pptx_without_attribute_error(tmp_path):
    """Pre-fix stub raises AttributeError on result.check_returncode()."""
    md_path = tmp_path / "doc.md"
    md_path.write_text(MD_SOURCE, encoding="utf-8")
    out_pptx = tmp_path / "doc.pptx"

    from orf.channels.md2pptx import MD2PPTXConverter

    def _which(name):
        # md2pptx absent, pandoc present -> pandoc fallback branch
        return None if name == "md2pptx" else f"/usr/bin/{name}"

    with patch("subprocess.run", side_effect=_FakePandocRunner()):
        with patch("orf.channels.md2pptx.shutil.which", side_effect=_which):
            result = MD2PPTXConverter().convert(md_path, out_pptx)

    assert result.success, f"md2pptx pandoc fallback failed: {result.errors}"
    assert out_pptx.exists()
    with zipfile.ZipFile(out_pptx) as zf:
        names = zf.namelist()
    assert "ppt/presentation.xml" in names
    assert "word/document.xml" not in names
