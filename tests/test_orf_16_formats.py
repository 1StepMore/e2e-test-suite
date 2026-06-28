"""Verify ORF supports all 16 documented output formats.

The 16 formats are the ``apply-md`` and ``convert-batch`` target formats:
DOCX, ODT, EPUB, HTML, RTF, PDF, PPTX, ICML, SRT, CSV, XLSX, JSON,
XML, IPYNB, EML, MSG.

This test reads the format list directly from the ORF source code
(``click.Choice`` in ``apply_md.py`` and ``convert_batch.py``) to
ensure no format is accidentally removed or renamed.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ORF_COMMANDS_DIR = ROOT / "Omni_Re_Formatter" / "src" / "orf" / "commands"

# The canonical 16 formats (in lower case, as they appear in click.Choice)
EXPECTED_16_FORMATS = frozenset({
    "docx", "odt", "epub", "html", "rtf", "pdf", "pptx",
    "icml", "srt", "csv", "xlsx", "json", "xml", "ipynb",
    "eml", "msg",
})


def _extract_click_choices(file_path: Path) -> set[str]:
    """Parse a Python file and extract format strings from ``click.Choice([...])``."""
    if not file_path.exists():
        return set()

    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))

    formats: set[str] = set()

    for node in ast.walk(tree):
        # Match: click.Choice([ "docx", "odt", ...])
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "Choice"):
            continue
        if not node.args:
            continue
        list_node = node.args[0]
        if not isinstance(list_node, ast.List):
            continue

        for elt in list_node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                fmt = elt.value.lower()
                if fmt != "auto":  # skip "auto" which is only in apply-md
                    formats.add(fmt)

    return formats


def test_apply_md_has_16_formats():
    """apply-md click.Choice must list all 16 formats (plus 'auto')."""
    apply_md = ORF_COMMANDS_DIR / "apply_md.py"
    formats = _extract_click_choices(apply_md)
    missing = EXPECTED_16_FORMATS - formats
    assert not missing, (
        f"apply_md.py is missing formats: {sorted(missing)}"
    )
    # Check there are no extras beyond the expected 16
    # (apply-md also has "auto" which is intentionally excluded above)
    extra = formats - EXPECTED_16_FORMATS
    assert not extra, (
        f"apply_md.py has unexpected extra formats: {sorted(extra)}"
    )


def test_convert_batch_has_16_formats():
    """convert-batch click.Choice must list all 16 formats (no 'auto')."""
    convert_batch = ORF_COMMANDS_DIR / "convert_batch.py"
    formats = _extract_click_choices(convert_batch)
    missing = EXPECTED_16_FORMATS - formats
    assert not missing, (
        f"convert_batch.py is missing formats: {sorted(missing)}"
    )
    extra = formats - EXPECTED_16_FORMATS
    assert not extra, (
        f"convert_batch.py has unexpected extra formats: {sorted(extra)}"
    )


def test_16_formats_match_expected_list():
    """Verify the expected 16 formats list has exactly 16 items."""
    assert len(EXPECTED_16_FORMATS) == 16, (
        f"Expected exactly 16 formats, got {len(EXPECTED_16_FORMATS)}"
    )
