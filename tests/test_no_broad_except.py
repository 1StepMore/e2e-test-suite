"""Test that no bare ``except Exception`` or ``except:`` blocks exist
without logging, re-raise, or ``# expected`` annotation.

Uses Python AST (not grep) for reliable structural detection.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

SRC_ROOTS = [
    Path(__file__).resolve().parent.parent / "Omni_Pre_Processor" / "src",
    Path(__file__).resolve().parent.parent / "Omni_Localizer" / "src",
    Path(__file__).resolve().parent.parent / "Omni_Re_Formatter" / "src",
]


LOG_METHODS = frozenset({
    "exception", "error", "warning", "info", "debug", "critical", "log",
})


def _is_logger_call(node: ast.AST) -> bool:
    """Check if *node* is a call to a logger method or ``print(…, exc_info=…)``."""
    if not isinstance(node, ast.Expr):
        return False
    call = node.value
    if not isinstance(call, ast.Call):
        return False
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr in LOG_METHODS:
        return True
    if isinstance(func, ast.Name) and func.id == "print":
        for kw in call.keywords:
            if kw.arg == "exc_info":
                return True
    return False


def _has_logging(handler: ast.ExceptHandler) -> bool:
    return any(_is_logger_call(stmt) for stmt in handler.body)


def _has_raise(handler: ast.ExceptHandler) -> bool:
    for stmt in handler.body:
        if isinstance(stmt, ast.Raise) and stmt.exc is None:
            return True
    return False


def _has_expected_comment(handler: ast.ExceptHandler, source_lines: list[str]) -> bool:
    if handler.lineno is None or handler.lineno > len(source_lines):
        return False
    return "# expected" in source_lines[handler.lineno - 1]


def _is_broad_except_violation(
    handler: ast.ExceptHandler,
    source_lines: list[str],
) -> bool:
    """Return True if *handler* is a broad exception without safe guards."""
    # Bare ``except:``
    if handler.type is None:
        if _has_expected_comment(handler, source_lines):
            return False
        if _has_logging(handler):
            return False
        if _has_raise(handler):
            return False
        return True

    # ``except Exception:`` or ``except Exception as e:``
    if isinstance(handler.type, ast.Name) and handler.type.id == "Exception":
        if _has_expected_comment(handler, source_lines):
            return False
        if _has_logging(handler):
            return False
        if _has_raise(handler):
            return False
        return True

    return False


def _collect_violations(src_root: Path) -> list[dict]:
    """Collect all broad-except violations in *src_root*."""
    violations: list[dict] = []
    if not src_root.exists():
        return violations

    for py_file in sorted(src_root.rglob("*.py")):
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            source_lines = source.splitlines()
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if _is_broad_except_violation(node, source_lines):
                type_str = "except:" if node.type is None else "except Exception"
                violations.append(
                    {
                        "file": str(py_file.relative_to(src_root.parent)),
                        "line": node.lineno,
                        "type": type_str,
                    }
                )
    return violations


@pytest.mark.parametrize("src_root", SRC_ROOTS, ids=lambda p: p.parent.name)
def test_no_broad_except_without_safeguards(src_root: Path) -> None:
    """Verify no bare except blocks exist without logging/raise/expected."""
    violations = _collect_violations(src_root)
    if violations:
        msg_parts = [
            f"Found {len(violations)} broad-except violation(s) without logging, "
            f"re-raise, or # expected comment in {src_root.parent.name}:"
        ]
        for v in violations:
            msg_parts.append(f"  {v['file']}:{v['line']}  {v['type']}")
        msg_parts.append(
            "\nEach must either:"
            "\n  - log the exception (logger.* / print(..., exc_info=...))"
            "\n  - re-raise (bare `raise`)"
            "\n  - have an inline `# expected` comment"
        )
        pytest.fail("\n".join(msg_parts))
