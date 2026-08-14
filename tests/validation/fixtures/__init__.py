"""Synthetic fixture generators for the validation scenario library.

Canonical, committed reference for the fixture shapes used by
``scenarios/``. Ported from ``tests/test_cross_format_e2e.py:142-334``
(``_create_synthetic_html/csv/json/xml/xlsx/md``), plus DOCX / PPTX / EPUB
generators sourced from the suite's format test helpers
(``tests/test_e2e_pipeline.py:573``, ``tests/test_e2e_images.py:563``,
``tests/test_e2e_opp_all_formats.py:603``).

NOT ported: ``_create_synthetic_pdf`` — the PDF case is served by the
committed static PDFs at ``scenarios/_fixtures/normal.pdf`` +
``multipage.pdf`` (reportlab is intentionally NOT a dependency).

Every generator takes a destination directory (``tmp_path``-style,
``pathlib.Path``) and returns the written file path, matching the original
test-helper signatures. All generators are deterministic (no randomness,
no timestamps) so pre-generated fixtures are reproducible.
"""
