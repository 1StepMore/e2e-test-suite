"""Shared fixtures for the 4-path e2e pipeline tests.

Activated by:
  - OMNI_TEST_FAKE_LLM=1 (intercepted by ol_cli.py)
  - OMNI_TEST_FAKE_PANDOC=1 (intercepted by orf/cli.py)
"""

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

    Writes a minimal valid DOCX at the output path so downstream
    DOCX/ZIP validators pass. Accepts both `(cmd, *args, **kwargs)`
    and `(args=cmd, **kwargs)` call shapes.
    """

    def __call__(self, cmd, *args, **kwargs):
        if cmd is None:
            try:
                cmd = kwargs.get("args") or kwargs.get("cmd")
            except Exception:
                cmd = None
        output_path = None
        if isinstance(cmd, (list, tuple)) and len(cmd) > 0:
            try:
                if "-o" in cmd:
                    output_path = cmd[cmd.index("-o") + 1]
            except (ValueError, IndexError):
                output_path = None
        if output_path is not None:
            _write_stub_docx(output_path)
        return _CompletedProcessStub(args=cmd, returncode=0, stdout=b"", stderr=b"")


class _CompletedProcessStub:
    """Minimal CompletedProcess-shaped result for fake subprocess calls."""

    def __init__(self, args, returncode, stdout=b"", stderr=b""):
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _write_stub_docx(path) -> None:
    """Write a minimal DOCX (valid ZIP with word/document.xml) at `path`."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body><w:p><w:r><w:t>用户手册</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>欢迎使用</w:t></w:r></w:p></w:body></w:document>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
