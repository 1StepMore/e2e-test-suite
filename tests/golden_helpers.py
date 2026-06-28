"""Golden file capture and verification helpers for regression testing.

Two primary functions:

    capture_golden(path, golden_dir, name)
        Copy the actual output to the golden directory for future comparison.

    assert_golden_identical(actual, golden, mode="byte")
        Compare actual output against a stored golden file using SHA-256,
        paragraph count, or DOCX paragraph-level comparison.
"""

import hashlib
import shutil
from pathlib import Path


def capture_golden(
    actual_path: str | Path,
    golden_dir: str | Path,
    name: str,
) -> Path:
    """Copy actual output to the golden directory.

    Args:
        actual_path: Path to the actual output file produced by the test.
        golden_dir: Directory where golden (reference) files are stored.
        name: Base filename for the golden copy (e.g., "test_result.docx").

    Returns:
        Path to the newly created golden file.

    Raises:
        FileNotFoundError: If actual_path does not exist.
    """
    actual_path = Path(actual_path)
    golden_dir = Path(golden_dir)

    if not actual_path.exists():
        raise FileNotFoundError(f"Actual output file not found: {actual_path}")

    golden_dir.mkdir(parents=True, exist_ok=True)
    golden_path = golden_dir / name
    shutil.copy2(actual_path, golden_path)
    return golden_path


def _sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file's contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _paragraph_count(path: Path) -> int:
    """Count paragraphs in a text file (split by double newline)."""
    text = path.read_text(encoding="utf-8")
    return len(text.split("\n\n"))


def _docx_paragraph_texts(path: Path) -> list[str]:
    """Extract paragraph texts from a DOCX file via python-docx.

    Raises:
        ImportError: If python-docx is not installed.
    """
    try:
        from docx import Document
    except ImportError:
        raise ImportError(
            "python-docx is required for 'docx-paragraph' mode. "
            "Install it with: pip install python-docx"
        )

    doc = Document(str(path))
    return [p.text for p in doc.paragraphs]


def assert_golden_identical(
    actual: str | Path,
    golden: str | Path,
    mode: str = "byte",
) -> None:
    """Compare actual output against a stored golden reference file.

    Args:
        actual: Path to the actual output file produced during the test.
        golden: Path to the stored golden (reference) file.
        mode: Comparison strategy.
            ``"byte"`` (default):
                SHA-256 hash comparison — strict, bit-exact.
            ``"paragraph"``:
                Compare paragraph count (double-newline split). Lightweight
                structural check for text/MD files.
            ``"docx-paragraph"``:
                Extract paragraph text via python-docx and compare element-wise.
                Semantic check for DOCX output (ignores formatting-only diffs).

    Raises:
        FileNotFoundError: If either path does not exist.
        AssertionError: If the comparison fails.
        ValueError: If *mode* is unknown.
        ImportError: If python-docx is missing in ``"docx-paragraph"`` mode.
    """
    actual = Path(actual)
    golden = Path(golden)

    if not golden.exists():
        raise FileNotFoundError(
            f"Golden file not found: {golden}\n"
            f"  Run with --golden-capture to create golden files."
        )
    if not actual.exists():
        raise FileNotFoundError(f"Actual output file not found: {actual}")

    if mode == "byte":
        _assert_byte_identical(actual, golden)
    elif mode == "paragraph":
        _assert_paragraph_count_identical(actual, golden)
    elif mode == "docx-paragraph":
        _assert_docx_paragraph_identical(actual, golden)
    else:
        raise ValueError(
            f"Unknown comparison mode: {mode!r}. "
            f"Expected one of: 'byte', 'paragraph', 'docx-paragraph'."
        )


def _assert_byte_identical(actual: Path, golden: Path) -> None:
    """Assert two files are bit-identical via SHA-256."""
    actual_hash = _sha256(actual)
    golden_hash = _sha256(golden)
    assert actual_hash == golden_hash, (
        f"  actual SHA-256: {actual_hash}\n"
        f"  golden SHA-256: {golden_hash}"
    )


def _assert_paragraph_count_identical(actual: Path, golden: Path) -> None:
    """Assert two text files have the same number of paragraphs."""
    actual_count = _paragraph_count(actual)
    golden_count = _paragraph_count(golden)
    assert actual_count == golden_count, (
        f"Paragraph count mismatch:\n"
        f"  actual: {actual_count}\n"
        f"  golden: {golden_count}"
    )


def _assert_docx_paragraph_identical(actual: Path, golden: Path) -> None:
    """Assert two DOCX files have identical paragraph text content."""
    actual_paras = _docx_paragraph_texts(actual)
    golden_paras = _docx_paragraph_texts(golden)

    assert len(actual_paras) == len(golden_paras), (
        f"DOCX paragraph count mismatch:\n"
        f"  actual: {len(actual_paras)} paragraphs\n"
        f"  golden: {len(golden_paras)} paragraphs"
    )

    for i, (a_text, g_text) in enumerate(zip(actual_paras, golden_paras)):
        assert a_text == g_text, (
            f"Paragraph {i} text mismatch:\n"
            f"  actual:  {a_text!r}\n"
            f"  golden: {g_text!r}"
        )
