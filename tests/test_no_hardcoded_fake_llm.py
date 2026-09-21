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
import re
from pathlib import Path

import pytest

#: The hardcoded-assignment token the guard exists to catch.
FAKE_LLM_ASSIGNMENT = "OMNI_TEST_FAKE_LLM=1"

# A sentence that merely mentions the token continues with an English
# verb/connective ("... OMNI_TEST_FAKE_LLM=1 is active ..."); a shell command
# line continues with a command word ("OMNI_TEST_FAKE_LLM=1 opp ..."). Only
# the latter is an assignment the interpreter would honour.
_PROSE_CONTINUATIONS = frozenset(
    {
        "is", "was", "are", "were", "be", "been", "being",
        "will", "would", "shall", "should", "must", "may", "might",
        "can", "could", "has", "have", "had",
        "and", "or", "but", "not", "nor",
        "to", "for", "in", "on", "at", "by", "with", "from",
        "when", "while", "if", "because", "unless", "until",
        "set", "sets", "active", "already", "enabled", "disabled",
    }
)

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


def _is_hardcoded_assignment(s: str) -> bool:
    """Classify *s* as a hardcoded env assignment (True) vs. prose (False).

    A violation is the assignment standing alone: the whole string is the
    token (bar surrounding whitespace, a leading ``export``, a trailing
    ``;``), or the token opens a shell command line
    (``OMNI_TEST_FAKE_LLM=1 opp ...``). Explanatory prose that embeds the
    token inside a sentence (``OMNI_TEST_FAKE_LLM=1 is active ...``) is not
    an assignment: a sentence continues with a verb/connective, a shell
    line continues with a command word.
    """
    stripped = re.sub(r"^export\s+", "", s.strip()).rstrip(";").strip()
    if stripped == FAKE_LLM_ASSIGNMENT:
        return True
    if not stripped.startswith(FAKE_LLM_ASSIGNMENT):
        # Mentioned mid-sentence ("... with OMNI_TEST_FAKE_LLM=1 active, ...").
        return False
    rest = stripped[len(FAKE_LLM_ASSIGNMENT):].strip()
    if not rest:
        return True
    return rest.split()[0].lower() not in _PROSE_CONTINUATIONS


def _is_informational_text(s: str) -> bool:
    """Check if *s* is informational/help text, not a raw assignment."""
    return not _is_hardcoded_assignment(s)


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


def _violations_for_literal(tmp_path: Path, literal: str) -> list[dict]:
    module = tmp_path / "mod.py"
    module.write_text(f"VALUE = {literal!r}\n", encoding="utf-8")
    return _collect_violations(tmp_path)


def test_real_prose_messages_are_not_flagged(tmp_path: Path) -> None:
    """The shipped prose strings that embed the token are ignored (e2e#56e)."""
    prose = [
        # omni_mcp/validation/cli.py:498 — argparse help text
        "R-07 contract-only escape hatch: with OMNI_TEST_FAKE_LLM=1 active, "
        "re-admit a human-quality-family scenario ONLY when every step cites an "
        "AGENT-SURFACE anchor (anchor-less is ineligible); human-quality anchors "
        "and fake-echo artifacts stay invalid",
        # omni_mcp/validation/engine.py:293 — fallback-active verdict message
        "OMNI_TEST_FAKE_LLM=1 is active and this scenario is "
        "human-quality evidence — fake output is never admissible "
        "(family=human-quality, derivation=byname)",
        # omni_mcp/validation/engine.py:300 — fake-echo verdict message
        "OMNI_TEST_FAKE_LLM=1 is active and artifact "
        "'out/result.md' carries the `[<tgt>] ` fake-echo signature",
    ]
    for text in prose:
        assert _violations_for_literal(tmp_path, text) == [], text


def test_bare_assignment_literal_is_flagged(tmp_path: Path) -> None:
    """The historical failure mode — a bare literal — must stay flagged."""
    violations = _violations_for_literal(tmp_path, "OMNI_TEST_FAKE_LLM=1")
    assert len(violations) == 1
    assert violations[0]["file"].endswith("mod.py")


def test_shell_fragment_literal_is_flagged(tmp_path: Path) -> None:
    """An env-prefix command line is an honoured assignment — flagged."""
    violations = _violations_for_literal(
        tmp_path, "OMNI_TEST_FAKE_LLM=1 opp document.docx --target-format both"
    )
    assert len(violations) == 1
