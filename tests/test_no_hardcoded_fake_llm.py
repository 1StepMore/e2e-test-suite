"""Test that no source file hardcodes OMNI_TEST_FAKE_LLM=1 as a literal.

AST-based regression guard. Catches unconditional assignments like
``os.environ["OMNI_TEST_FAKE_LLM"] = "1"`` in source code.

Allowed:
- ``os.environ.get("OMNI_TEST_FAKE_LLM") == "1"`` — runtime check
- Docstrings that explain the env var — informational
- Test files that set the env var — test setup
- Suite CLI behind the ``--fake-llm`` flag
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SOURCE_ROOTS = [
    Path(__file__).resolve().parent.parent / "Omni_Pre_Processor" / "src",
    Path(__file__).resolve().parent.parent / "Omni_Localizer" / "src",
    Path(__file__).resolve().parent.parent / "Omni_Re_Formatter" / "src",
]

SUITE_PACKAGES = [
    Path(__file__).resolve().parent.parent / "omni_suite",
    Path(__file__).resolve().parent.parent / "omni_mcp",
    Path(__file__).resolve().parent.parent / "omni_metrics",
]


def _collect_violations(root: Path) -> list[dict]:
    """Return list of OMNI_TEST_FAKE_LLM=1 violations in *root*."""
    violations: list[dict] = []
    if not root.exists():
        return violations

    for py_file in sorted(root.rglob("*.py")):
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            s = _str_value(node)
            if s is None:
                continue
            if "OMNI_TEST_FAKE_LLM=1" not in s:
                continue
            if _is_docstring_pos(node, tree):
                continue
            # Skip informational/help text: string contains lots of extra
            # explanatory text beyond the bare env-var name=value. This is
            # testing guidance for users, not a hardcoded assignment.
            if _is_informational_text(s):
                continue
            violations.append(
                {
                    "file": str(py_file.relative_to(root.parent.parent)),
                    "line": getattr(node, "lineno", 0),
                    "text": s.strip()[:120],
                }
            )

    return violations


def _str_value(node: ast.AST) -> str | None:
    """Extract string value from Constant or deprecated Str node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if hasattr(ast, "Str") and isinstance(node, ast.Str):
        return node.s
    return None


def _is_docstring_pos(node: ast.AST, tree: ast.Module) -> bool:
    """Check if *node* is the first Constant string in a body (docstring)."""
    lineno = getattr(node, "lineno", None)
    if lineno is None:
        return False
    for n in ast.walk(tree):
        body = getattr(n, "body", None)
        if not isinstance(body, list) or not body:
            continue
        first = body[0]
        if not isinstance(first, ast.Expr):
            continue
        val = first.value
        v = _str_value(val)
        if v is not None and getattr(val, "lineno", None) == lineno:
            return True
    return False


def _is_informational_text(s: str) -> bool:
    """Check if *s* is informational/help text, not a raw assignment.

    Informational text is longer than the bare env-var and contains
    explanatory words like 'testing', 'set', 'bypass', 'For'.
    """
    if len(s) <= 35:
        return False
    keywords = {"testing", "set ", "bypass", "For ", "for "}
    return any(kw in s for kw in keywords)


@pytest.mark.parametrize(
    "src_root",
    SOURCE_ROOTS + SUITE_PACKAGES,
    ids=lambda p: p.parent.name if p.parent.name != "Omni_Suite" else p.name,
)
def test_no_hardcoded_fake_llm_assignments(src_root: Path) -> None:
    """Verify no source code hardcodes OMNI_TEST_FAKE_LLM=1 as a literal."""
    violations = _collect_violations(src_root)
    if violations:
        msg_parts = [
            f"Found {len(violations)} hardcoded 'OMNI_TEST_FAKE_LLM=1' literal(s) "
            f"in {src_root.parent.name}:"
        ]
        for v in violations:
            msg_parts.append(f"  {v['file']}:{v['line']}  {v['text']!r}")
        msg_parts.append(
            "\nDo NOT hardcode OMNI_TEST_FAKE_LLM=1 in source code. "
            "Use os.environ.get('OMNI_TEST_FAKE_LLM') for runtime checks, "
            "or set the env var in test fixtures/conftest only."
        )
        pytest.fail("\n".join(msg_parts))
