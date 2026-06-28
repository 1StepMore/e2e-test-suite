#!/usr/bin/env python3
"""Audit bare ``except Exception`` blocks across all 3 module src/ directories.

Scans every ``.py`` file and classifies each ``except Exception`` / bare
``except:`` handler into one of four safe categories:

    (a) Specifies an exact exception type (other than ``Exception``)
    (b) Has a ``logger.*`` call or ``print(…, exc_info=…)`` in the body
    (c) Has an inline ``# expected`` comment on the same line
    (d) Re-raises (a bare ``raise`` in the body)

Any handler that matches none of (a)–(d) is **flagged as a violation**.

Exit codes
    * 0 — no violations found
    * 1 — violations found (printed to stderr)
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Directories to scan
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

    # logger.<method>(...)  or  logging.<method>(...)
    if isinstance(func, ast.Attribute) and func.attr in LOG_METHODS:
        return True

    # print(..., exc_info=...)
    if isinstance(func, ast.Name) and func.id == "print":
        for kw in call.keywords:
            if kw.arg == "exc_info":
                return True
    return False


def _has_logging(handler: ast.ExceptHandler) -> bool:
    """Return True if the handler body contains a logger call."""
    return any(_is_logger_call(stmt) for stmt in handler.body)


def _has_raise(handler: ast.ExceptHandler) -> bool:
    """Return True if the handler body contains a bare ``raise``."""
    for stmt in handler.body:
        if isinstance(stmt, ast.Raise) and stmt.exc is None:
            return True
    return False


def _has_expected_comment(handler: ast.ExceptHandler) -> bool:
    """Return True if the ``except`` line has a ``# expected`` comment."""
    if not handler.lineno:
        return False
    return False  # We rely on the caller to pass source lines


def classify_handler(
    handler: ast.ExceptHandler, source_lines: list[str]
) -> tuple[str, list[str]]:
    """Classify an exception handler.

    Returns ``(category, reasons)`` where *category* is one of:
        ``"safe"``, ``"violation"``
    """
    reasons: list[str] = []

    type_node = handler.type

    # Bare ``except:`` (no type specified)
    if type_node is None:
        # Check inline comment
        if handler.lineno is not None and handler.lineno <= len(source_lines):
            line = source_lines[handler.lineno - 1]
            if "# expected" in line:
                return "safe", ["bare except with # expected comment"]
        if _has_logging(handler):
            return "safe", ["bare except with logging"]
        if _has_raise(handler):
            return "safe", ["bare except with re-raise"]
        return "violation", ["bare except: — no logging, no re-raise, no # expected"]

    # ``except Exception:``
    if isinstance(type_node, ast.Name) and type_node.id == "Exception":
        if handler.lineno is not None and handler.lineno <= len(source_lines):
            line = source_lines[handler.lineno - 1]
            if "# expected" in line:
                return "safe", ["except Exception with # expected comment"]
        if _has_logging(handler):
            return "safe", ["except Exception with logging"]
        if _has_raise(handler):
            return "safe", ["except Exception with re-raise"]
        return "violation", ["except Exception — no logging, no re-raise, no # expected"]

    # If it's a more specific type like ValueError, KeyError etc — always safe
    if isinstance(type_node, ast.Name):
        return "safe", [f"except {type_node.id}"]
    if isinstance(type_node, ast.Tuple):
        names = [e.id if isinstance(e, ast.Name) else ast.dump(e) for e in type_node.elts]
        return "safe", [f"except ({', '.join(names)})"]
    if isinstance(type_node, ast.Attribute):
        return "safe", [f"except {type_node.attr}"]
    return "safe", [f"except {ast.dump(type_node)}"]


def audit_file(file_path: Path) -> list[dict]:
    """Audit a single Python file for bare exception handlers."""
    violations: list[dict] = []
    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
        source_lines = source.splitlines()
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        print(f"  [SKIP] Syntax error in {file_path}", file=sys.stderr)
        return []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue

        category, reasons = classify_handler(node, source_lines)
        if category == "violation":
            violations.append(
                {
                    "file": str(file_path),
                    "line": node.lineno,
                    "type": "bare except:" if node.type is None else "except Exception",
                    "reasons": reasons,
                }
            )
    return violations


def main() -> int:
    total_violations: list[dict] = []
    total_handlers = 0
    total_safe = 0

    for src_root in SRC_ROOTS:
        if not src_root.exists():
            print(f"  [SKIP] Directory not found: {src_root}", file=sys.stderr)
            continue
        py_files = sorted(src_root.rglob("*.py"))
        for py_file in py_files:
            # Count all except handlers in this file
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                source_lines = source.splitlines()
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.ExceptHandler):
                    continue
                total_handlers += 1
                category, _ = classify_handler(node, source_lines)
                if category == "safe":
                    total_safe += 1

            violations = audit_file(py_file)
            total_violations.extend(violations)

    if total_violations:
        print(
            f"Found {len(total_violations)} violation(s) out of "
            f"{total_handlers} total handlers ({total_safe} safe):",
            file=sys.stderr,
        )
        for v in total_violations:
            print(
                f"  {v['file']}:{v['line']}  {v['type']}  — {'; '.join(v['reasons'])}",
                file=sys.stderr,
            )
        return 1

    print(
        f"OK — {total_handlers} exception handlers checked, "
        f"{total_safe} safe, 0 violations.",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
