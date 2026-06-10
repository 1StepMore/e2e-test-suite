#!/usr/bin/env python3
"""Validate that all <w:drawing> rId references exist in <Relationships>.

Usage:
    python scripts/validate_docx_rids.py <path_to.docx>
"""

import sys
import zipfile
from lxml import etree

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def validate_docx(docx_path: str) -> int:
    """Check every drawing in the DOCX references a valid relationship.

    Returns: 0 if all OK, 1 if errors found.
    """
    errors = 0

    with zipfile.ZipFile(docx_path) as z:
        # 1. Load relationships
        rels_path = "word/_rels/document.xml.rels"
        if rels_path not in z.namelist():
            print(f"ERROR: {rels_path} not found in DOCX")
            return 1

        rels_data = z.read(rels_path)
        rels_root = etree.fromstring(rels_data)

        valid_rids = set()
        for rel in rels_root:
            rid = rel.get("Id")
            if rid:
                valid_rids.add(rid)

        print(f"Valid relationship IDs ({len(valid_rids)} total):")
        for rid in sorted(valid_rids):
            target = rels_root.find(f".//*[@Id='{rid}']")
            target_str = target.get("Target", "") if target is not None else "?"
            print(f"  {rid} -> {target_str}")

        # 2. Load document.xml and find all drawings
        doc_path = "word/document.xml"
        if doc_path not in z.namelist():
            print(f"ERROR: {doc_path} not found")
            return 1

        doc_xml = z.read(doc_path).decode("utf-8")
        doc_root = etree.fromstring(doc_xml.encode("utf-8"))

        # Find all <w:drawing> elements
        # They contain <wp:inline> or <wp:anchor> which reference rIds
        nsmap = {
            "w": W_NS,
            "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
            "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
            "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
            "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
        }

        drawings = doc_root.findall(".//w:drawing", nsmap)
        print(f"\nDrawings found: {len(drawings)}")

        for i, drawing in enumerate(drawings):
            # Find all rId references (in blipFill or shape)
            # <a:blip r:embed="rId16"> or <a:blip r:link="rId16">
            blips = drawing.findall(".//a:blip", nsmap)
            for blip in blips:
                embed = blip.get(f"{{{nsmap['r']}}}embed")
                link = blip.get(f"{{{nsmap['r']}}}link")
                for rid in [embed, link]:
                    if rid:
                        if rid not in valid_rids:
                            print(f"  ERROR: Drawing {i} references rId '{rid}' which is NOT in <Relationships>!")
                            errors += 1
                        else:
                            print(f"  OK: Drawing {i} -> {rid}")

        if errors == 0:
            print(f"\n✓ All {len(drawings)} drawings reference valid relationship IDs.")
        else:
            print(f"\n✗ Found {errors} invalid rId reference(s).")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate_docx_rids.py <path_to.docx>")
        sys.exit(1)

    sys.exit(validate_docx(sys.argv[1]))
