"""Generate a ~50MB DOCX fixture for E1 production test.

Efficient approach: create a large image, embed it in a minimal DOCX.
Reaches 50MB in seconds instead of minutes.
"""

from __future__ import annotations

import struct
import sys
import zlib
import zipfile
from pathlib import Path

TARGET_SIZE_MB = 50


def generate(output_path: Path, target_mb: int = TARGET_SIZE_MB) -> None:
    """Generate a DOCX of approximately target_mb megabytes by embedding
    a large PNG image into a minimal valid DOCX structure.
    """
    image_size_bytes = (target_mb - 1) * 1024 * 1024
    png_data = _make_large_png(image_size_bytes)

    document_xml = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p>
      <w:r>
        <w:drawing>
          <wp:inline distT="0" distB="0" distL="0" distR="0"
                     xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">
            <wp:extent cx="914400" cy="914400"/>
            <wp:docPr id="1" name="LargeImage"/>
            <wp:cNvGraphicFramePr/>
            <a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
              <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
                <pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
                  <pic:nvPicPr>
                    <pic:cNvPr id="0" name="LargeImage"/>
                    <pic:cNvPicPr/>
                  </pic:nvPicPr>
                  <pic:blipFill>
                    <a:blip r:embed="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>
                    <a:stretch><a:fillRect/></a:stretch>
                  </pic:blipFill>
                </pic:pic>
              </a:graphicData>
            </a:graphic>
          </wp:drawing>
        </w:r>
    </w:p>
  </w:body>
</w:document>"""

    content_types = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

    rels = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/media/image1.png", png_data)

    actual_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Generated {output_path}: {actual_mb:.1f}MB")


def _make_large_png(target_bytes: int) -> bytes:
    """Create a valid PNG of approximately target_bytes size.

    Uses random pixel data that won't compress well, so the
    compressed PNG actually approaches the target size.
    """
    import os

    width = 1000
    row_size = width * 3 + 1
    height = max(1, target_bytes // row_size)
    raw_data = bytearray()
    for y in range(height):
        raw_data.append(0)
        raw_data.extend(os.urandom(width * 3))

    compressed = zlib.compress(bytes(raw_data), level=0)

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", compressed)
    png += chunk(b"IEND", b"")
    return png


if __name__ == "__main__":
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/omni_e1_fixture.docx")
    generate(output)
