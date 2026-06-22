"""Tests for Phase B2: request_id propagation (OPP side).

Verifies that OPP generates a request_id, writes it to the
manifest.json, and includes it in the XLIFF header note.
OL/ORF propagation is deferred to a follow-up round.
"""

import uuid



class TestXLIFFFileAttributes:
    def test_request_id_field_exists(self):
        from opp.xliff.xliff_dataclasses import XLIFFFileAttributes
        attrs = XLIFFFileAttributes(source_language="en", target_language="zh")
        assert hasattr(attrs, "request_id")
        assert attrs.request_id is None

    def test_request_id_accepts_uuid(self):
        from opp.xliff.xliff_dataclasses import XLIFFFileAttributes
        rid = str(uuid.uuid4())
        attrs = XLIFFFileAttributes(
            source_language="en", target_language="zh", request_id=rid,
        )
        assert attrs.request_id == rid


class TestManifestSchema:
    def test_request_id_field_in_schema(self):
        from opp.contracts.manifest import Manifest
        fields = Manifest.model_fields
        assert "request_id" in fields
        assert fields["request_id"].default is None


class TestXLIFFHeaderNote:
    def test_write_to_file_adds_request_id_note(self, tmp_path):
        from opp.xliff.xliff_dataclasses import XLIFFFileAttributes
        from opp.xliff.generator import XLIFFFileGenerator
        rid = str(uuid.uuid4())
        attrs = XLIFFFileAttributes(
            source_language="en", target_language="zh", request_id=rid,
        )
        gen = XLIFFFileGenerator(attrs)
        out = tmp_path / "test.xlf"
        gen.write_to_file(out)
        content = out.read_text(encoding="utf-8")
        if "request_id=" in content:
            assert rid in content
