"""RED tests for scripts/doc_inventory.py (Task 2 TDD anchor).

These tests pin the CONTRACT the real implementation (Task 3) must satisfy:

- ``main(argv) -> int`` with two modes:
  * generate  — ``["--root", R]`` writes ``docs/dev/doc-inventory.md``
  * check     — ``["--check", "--root", R]`` verifies source-truth tool counts,
                claim-site parity (README.md / AGENTS.md), presence of a
                current inventory, absence of ``tests/test_bug_*.py`` files,
                and delegates to ``scripts/sync_version_docs.py``.
- ``--root DIR`` rebases every relative path onto DIR (lets fixtures build a
  temp repo tree). When ``scenarios/`` is absent, the scenario-count check is
  skipped (report-only, not a failure).
- Source-truth counting helpers are importable unit functions.

Coherence note (tests 3 vs 5): check REQUIRES the inventory file, so the
"consistent tree" must have been generated first. Tests 3, 4, 6 and 8 run
``generate`` before ``--check`` (the real workflow); test 5 checks a tree that
was never generated and must fail with a "missing inventory" marker. Tests 4,
6, 8 also generate first so check reaches the *specific* failure under test
instead of short-circuiting on the missing inventory.

All 8 tests are currently RED: the stub raises ``NotImplementedError``.
"""
from pathlib import Path

import pytest

import scripts.doc_inventory as di

# ---------------------------------------------------------------------------
# Fixtures — tmp repo trees built under tmp_path (rebased via --root)
# ---------------------------------------------------------------------------

# OPP source truth: a _TOOL_SCHEMAS block with 9 "name" entries (mirrors
# Omni_Pre_Processor/src/opp/mcp/server.py).
OPP_SERVER = """from mcp.server.fastmcp import types

_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {"name": "extract_document", "description": "..."},
    {"name": "batch_extract", "description": "..."},
    {"name": "detect_format_tool", "description": "..."},
    {"name": "generate_xliff", "description": "..."},
    {"name": "generate_markdown", "description": "..."},
    {"name": "save_skeleton", "description": "..."},
    {"name": "ping", "description": "..."},
    {"name": "validate_xliff", "description": "..."},
    {"name": "get_capabilities", "description": "..."},
]
"""

# OL source truth: 19 `from ol_mcp.X import ...` lines (one name each) plus
# 2 TOOL_REGISTRY[...] keys -> 19 + 2 = 21 (mirrors Omni_Localizer/src/ol_mcp/tools.py).
OL_TOOLS = """from ol_mcp.auth import check_auth
from ol_mcp.metrics import registry_metrics
from ol_mcp.tracing import trace_tool
from ol_mcp.rate_limiter import check_rate_limit
from ol_mcp.task_tracker import InMemoryTaskTracker
from ol_mcp.translate_md import translate_md_text
from ol_mcp.judge import judge_text
from ol_mcp.glossary import load_glossary
from ol_mcp.tm import search_tm
from ol_mcp.translate_file import translate_file
from ol_mcp.extract_terms import extract_terms
from ol_mcp.tm_add import add_tm_entries
from ol_mcp.shield_text import shield_md_text
from ol_mcp.generate_report import generate_report
from ol_mcp.inspect_config import inspect_config
from ol_mcp.disambiguate import disambiguate
from ol_mcp.batch_translate import batch_translate_texts
from ol_mcp.translate_xliff import translate_xliff
from ol_mcp.verify_terms import verify_terms

TOOL_REGISTRY["ping"] = (_ping, None, "Health check endpoint.")
TOOL_REGISTRY["get_capabilities"] = (_get_capabilities, None, "Return capabilities.")
"""

# ORF source truth: a _list_tools return with 7 types.Tool(name=...) entries
# (mirrors Omni_Re_Formatter/src/orf/mcp/server.py).
ORF_SERVER = """async def _list_tools() -> list[types.Tool]:
    return [
        types.Tool(name="apply_md", description="..."),
        types.Tool(name="apply_xliff", description="..."),
        types.Tool(name="batch_convert", description="..."),
        types.Tool(name="detect_format", description="..."),
        types.Tool(name="info", description="..."),
        types.Tool(name="ping", description="..."),
        types.Tool(name="get_capabilities", description="..."),
    ]
"""

# Claim sites with claim lines matching the source truth above.
AGENTS_MD = """# Omni Suite AGENTS

### OPP MCP Server (9 tools)
### OL MCP Server (21 tools)
### ORF MCP Server (7 tools)
"""

README_MD = """# Omni Suite

### OPP MCP Server (9 tools)
### OL MCP Server (21 tools)
### ORF MCP Server (7 tools)
"""


@pytest.fixture
def consistent_tree(tmp_path: Path) -> Path:
    """A tmp repo tree whose README/AGENTS claims match the source truth.

    Contains the exact relative paths the real repo mirrors and a
    ``scripts/sync_version_docs.py`` no-op that exits 0. It has NO
    ``scenarios/`` dir (scenario-count check skipped) and NO inventory file —
    the check's inventory-requirement is exercised separately: tests run
    ``generate`` first to make a tree "consistent", and test 5 checks a tree
    that was never generated to pin the missing-inventory failure.
    """
    root = tmp_path
    (root / "README.md").write_text(README_MD, encoding="utf-8")
    (root / "AGENTS.md").write_text(AGENTS_MD, encoding="utf-8")

    opp = root / "Omni_Pre_Processor/src/opp/mcp"
    ol = root / "Omni_Localizer/src/ol_mcp"
    orf = root / "Omni_Re_Formatter/src/orf/mcp"
    for d in (opp, ol, orf, root / "scripts"):
        d.mkdir(parents=True, exist_ok=True)
    (opp / "server.py").write_text(OPP_SERVER, encoding="utf-8")
    (ol / "tools.py").write_text(OL_TOOLS, encoding="utf-8")
    (orf / "server.py").write_text(ORF_SERVER, encoding="utf-8")
    (root / "scripts/sync_version_docs.py").write_text(
        "if __name__ == '__main__':\n    raise SystemExit(0)\n",
        encoding="utf-8",
    )
    return root


def _generate(root: Path) -> None:
    """Run generate mode so the tree has a current inventory (the real
    generate-then-check workflow). Tests that probe a specific check failure
    call this first so check reaches that failure instead of stopping on the
    missing inventory."""
    rc = di.main(["--root", str(root)])
    assert rc == 0


# ---------------------------------------------------------------------------
# 1. Generate writes header + rows
# ---------------------------------------------------------------------------

def test_generate_writes_header_and_rows(tmp_path):
    """Generate with --root writes docs/dev/doc-inventory.md with a row per
    tracked doc, including nested dirs, and never lists itself."""
    root = tmp_path
    for rel in ("docs/a.md", "docs/dev/b.md", "docs/observability/c.md"):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {p.name}\n", encoding="utf-8")

    rc = di.main(["--root", str(root)])

    assert rc == 0
    out = root / "docs/dev/doc-inventory.md"
    assert out.exists(), "generate must write docs/dev/doc-inventory.md"
    text = out.read_text(encoding="utf-8")
    assert text.startswith(
        "<!-- AUTO-GENERATED by scripts/doc_inventory.py"
    ), "header must carry the AUTO-GENERATED marker"
    for rel in ("a.md", "b.md", "c.md"):
        assert rel in text, f"inventory must list {rel}"
    assert "doc-inventory.md" not in text, "inventory must not list itself"


# ---------------------------------------------------------------------------
# 2. Generate is idempotent
# ---------------------------------------------------------------------------

def test_generate_is_idempotent(tmp_path):
    """Two generate runs on the same tree produce byte-identical output."""
    root = tmp_path
    for rel in ("docs/a.md", "docs/dev/b.md"):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {p.name}\n", encoding="utf-8")

    assert di.main(["--root", str(root)]) == 0
    out = root / "docs/dev/doc-inventory.md"
    first = out.read_bytes()
    assert di.main(["--root", str(root)]) == 0
    assert out.read_bytes() == first, "regenerating must be byte-idempotent"


# ---------------------------------------------------------------------------
# 3. Check passes on a consistent tree
# ---------------------------------------------------------------------------

def test_check_clean_exit_0(consistent_tree, capsys):
    """A consistent tree that has been generated (so its inventory exists) and
    has no scenarios/ dir (scenario-count skipped) is a clean check: exit 0
    and stdout says 'check passed'."""
    _generate(consistent_tree)
    rc = di.main(["--check", "--root", str(consistent_tree)])
    captured = capsys.readouterr()
    assert rc == 0, "a consistent tree must pass the check"
    assert "check passed" in captured.out, (
        f"stdout must announce the pass, got: {captured.out!r}"
    )


# ---------------------------------------------------------------------------
# 4. Check fails on a wrong claimed tool count
# ---------------------------------------------------------------------------

def test_check_wrong_tool_count_exit_1(consistent_tree, capsys):
    """AGENTS.md claiming 'OPP MCP Server (3 tools)' against a 9-schema source
    is exit 1 and the failure text names the offending site."""
    (consistent_tree / "AGENTS.md").write_text(
        AGENTS_MD.replace("OPP MCP Server (9 tools)", "OPP MCP Server (3 tools)"),
        encoding="utf-8",
    )
    _generate(consistent_tree)
    rc = di.main(["--check", "--root", str(consistent_tree)])
    captured = capsys.readouterr()
    assert rc == 1, "a wrong claimed tool count must fail the check"
    combined = captured.out + captured.err
    assert "OPP" in combined or "3 tools" in combined, (
        f"failure text must name the offending claim site, got: {combined!r}"
    )


# ---------------------------------------------------------------------------
# 5. Check fails when the inventory file is missing
# ---------------------------------------------------------------------------

def test_check_missing_inventory_exit_1(consistent_tree, capsys):
    """A tree with no docs/dev/doc-inventory.md (generate never ran) is exit 1
    and the failure text tells the user to regenerate."""
    rc = di.main(["--check", "--root", str(consistent_tree)])
    captured = capsys.readouterr()
    assert rc == 1, "a missing inventory file must fail the check"
    combined = captured.out + captured.err
    assert "missing" in combined and "python3 scripts/doc_inventory.py" in combined, (
        f"failure text must say the inventory is missing and how to regenerate, got: {combined!r}"
    )


# ---------------------------------------------------------------------------
# 6. Check fails on a stray tests/test_bug_*.py file
# ---------------------------------------------------------------------------

def test_check_stray_test_bug_file_exit_1(consistent_tree, capsys):
    """A tests/test_bug_x.py in the tree is exit 1 (policy: no bug-repro files
    may live in the shipped tree)."""
    (consistent_tree / "tests").mkdir(parents=True, exist_ok=True)
    (consistent_tree / "tests/test_bug_x.py").write_text(
        "def test_x():\n    assert True\n", encoding="utf-8"
    )
    _generate(consistent_tree)
    rc = di.main(["--check", "--root", str(consistent_tree)])
    captured = capsys.readouterr()
    assert rc == 1, "a stray tests/test_bug_*.py file must fail the check"
    combined = captured.out + captured.err
    assert "test_bug_x.py" in combined, (
        f"failure text must name the offending file, got: {combined!r}"
    )


# ---------------------------------------------------------------------------
# 7. Source-truth counting helpers (unit)
# ---------------------------------------------------------------------------

def test_source_truth_counters(tmp_path):
    """count_tool_schemas -> 9 for a 9-entry _TOOL_SCHEMAS block,
    count_tool_registry -> 21 for 19 import lines + 2 registry keys,
    count_listed_tools -> 7 for a 7-entry _list_tools return."""
    opp = tmp_path / "server.py"
    opp.write_text(OPP_SERVER, encoding="utf-8")
    ol = tmp_path / "tools.py"
    ol.write_text(OL_TOOLS, encoding="utf-8")
    orf = tmp_path / "orf_server.py"
    orf.write_text(ORF_SERVER, encoding="utf-8")

    assert di.count_tool_schemas(opp) == 9
    assert di.count_tool_registry(ol) == 21
    assert di.count_listed_tools(orf) == 7


# ---------------------------------------------------------------------------
# 8. Check delegates to scripts/sync_version_docs.py
# ---------------------------------------------------------------------------

def test_check_version_sync_delegation(consistent_tree, capsys):
    """When scripts/sync_version_docs.py exits 1, --check must return 1."""
    _generate(consistent_tree)
    (consistent_tree / "scripts/sync_version_docs.py").write_text(
        "if __name__ == '__main__':\n    raise SystemExit(1)\n",
        encoding="utf-8",
    )
    rc = di.main(["--check", "--root", str(consistent_tree)])
    captured = capsys.readouterr()
    assert rc == 1, "a failing sync_version_docs.py must fail the check"
    combined = captured.out + captured.err
    assert "sync_version_docs.py" in combined, (
        f"failure text must name the failing sub-script, got: {combined!r}"
    )


# ---------------------------------------------------------------------------
# 9. Gate A — archive discipline (check_archive)
# ---------------------------------------------------------------------------

def test_check_archive_marker_missing_exit_1(tmp_path, capsys):
    """An archived doc without the first-line 'Status: ARCHIVED' marker is
    exit 1 naming the offending file."""
    root = tmp_path
    (root / "docs/archive").mkdir(parents=True, exist_ok=True)
    (root / "docs/archive/old_plan.md").write_text(
        "# Old Plan\n\nSuperseded content.\n", encoding="utf-8"
    )
    _generate(root)
    rc = di.main(["--check", "--root", str(root)])
    captured = capsys.readouterr()
    assert rc == 1, "an archived doc without its marker must fail the check"
    combined = captured.out + captured.err
    assert "old_plan.md" in combined and "ARCHIVED" in combined, (
        f"failure text must name the file and the marker requirement, got: {combined!r}"
    )


def test_check_archive_marker_present_exit_0(tmp_path):
    """An archived doc WITH the first-line 'Status: ARCHIVED' marker passes."""
    root = tmp_path
    (root / "docs/archive").mkdir(parents=True, exist_ok=True)
    (root / "docs/archive/old_plan.md").write_text(
        "> **Status: ARCHIVED (2026-08-23). Reason: superseded. "
        "Superseded by: scripts/validation/run_validation.py.**\n\n"
        "# Old Plan\n\nSuperseded content.\n",
        encoding="utf-8",
    )
    _generate(root)
    assert di.main(["--check", "--root", str(root)]) == 0


def test_check_archive_marker_in_maintained_path_exit_1(tmp_path, capsys):
    """An ARCHIVED marker in a maintained (non-archive) doc fails the check."""
    root = tmp_path
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/still_active.md").write_text(
        "> **Status: ARCHIVED (2026-08-23).**\n\n# Still active\n", encoding="utf-8"
    )
    _generate(root)
    rc = di.main(["--check", "--root", str(root)])
    captured = capsys.readouterr()
    assert rc == 1, "an ARCHIVED marker outside docs/archive/ must fail"
    combined = captured.out + captured.err
    assert "still_active.md" in combined, (
        f"failure text must name the misplaced file, got: {combined!r}"
    )


# ---------------------------------------------------------------------------
# 10. Gate B — referential integrity (check_referential)
# ---------------------------------------------------------------------------

def test_check_broken_link_exit_1(tmp_path, capsys):
    """A broken relative Markdown link in a scoped instruction doc is exit 1."""
    root = tmp_path
    (root / "README.md").write_text(
        "# Omni Suite\n\nSee [missing doc](docs/does-not-exist.md).\n",
        encoding="utf-8",
    )
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts/sync_version_docs.py").write_text(
        "if __name__ == '__main__':\n    raise SystemExit(0)\n",
        encoding="utf-8",
    )
    _generate(root)
    rc = di.main(["--check", "--root", str(root)])
    captured = capsys.readouterr()
    assert rc == 1, "a broken link must fail the check"
    combined = captured.out + captured.err
    assert "does-not-exist.md" in combined, (
        f"failure text must name the broken target, got: {combined!r}"
    )


def test_check_dead_path_token_exit_1(tmp_path, capsys):
    """A backticked path-shaped token that resolves nowhere is exit 1."""
    root = tmp_path
    (root / "README.md").write_text(
        "# Omni Suite\n\nSource lives in `src/opp/mcp/server.py`.\n",
        encoding="utf-8",
    )
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts/sync_version_docs.py").write_text(
        "if __name__ == '__main__':\n    raise SystemExit(0)\n",
        encoding="utf-8",
    )
    _generate(root)
    rc = di.main(["--check", "--root", str(root)])
    captured = capsys.readouterr()
    assert rc == 1, "a dead path token must fail the check"
    combined = captured.out + captured.err
    assert "src/opp/mcp/server.py" in combined, (
        f"failure text must name the dead path token, got: {combined!r}"
    )


def test_check_resolvable_path_token_exit_0(tmp_path):
    """A path-shaped token that resolves (repo-root or module-root) passes."""
    root = tmp_path
    (root / "README.md").write_text(
        "# Omni Suite\n\nSource lives in `src/opp/mcp/server.py`.\n",
        encoding="utf-8",
    )
    mcp = root / "Omni_Pre_Processor/src/opp/mcp"
    mcp.mkdir(parents=True, exist_ok=True)
    (mcp / "server.py").write_text(OPP_SERVER, encoding="utf-8")
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts/sync_version_docs.py").write_text(
        "if __name__ == '__main__':\n    raise SystemExit(0)\n",
        encoding="utf-8",
    )
    _generate(root)
    assert di.main(["--check", "--root", str(root)]) == 0


# ---------------------------------------------------------------------------
# 11. Gate C — skill line-count claims (check_line_claims)
# ---------------------------------------------------------------------------

def test_check_line_claim_drift_exit_1(tmp_path, capsys):
    """omni-docmap SKILL.md line-count claims outside ±15% fail the check."""
    root = tmp_path
    skill = root / ".opencode/skills/omni-docmap"
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(
        "# Docmap\n\n| File | Lines |\n|------|-------|\n"
        "| `AGENTS.md` | ~50 |\n",
        encoding="utf-8",
    )
    (root / "AGENTS.md").write_text(
        "\n".join(f"# line {i}" for i in range(200)), encoding="utf-8"
    )
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts/sync_version_docs.py").write_text(
        "if __name__ == '__main__':\n    raise SystemExit(0)\n",
        encoding="utf-8",
    )
    _generate(root)
    rc = di.main(["--check", "--root", str(root)])
    captured = capsys.readouterr()
    assert rc == 1, "a drifted line-count claim must fail the check"
    combined = captured.out + captured.err
    assert "AGENTS.md" in combined and "~50" in combined, (
        f"failure text must name the claim and file, got: {combined!r}"
    )


def test_check_line_claim_in_band_exit_0(tmp_path):
    """Line-count claims within ±15% of the actual pass the check."""
    root = tmp_path
    skill = root / ".opencode/skills/omni-docmap"
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(
        "# Docmap\n\n| File | Lines |\n|------|-------|\n"
        "| `AGENTS.md` | ~200 |\n",
        encoding="utf-8",
    )
    (root / "AGENTS.md").write_text(
        "\n".join(f"# line {i}" for i in range(200)), encoding="utf-8"
    )
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts/sync_version_docs.py").write_text(
        "if __name__ == '__main__':\n    raise SystemExit(0)\n",
        encoding="utf-8",
    )
    _generate(root)
    assert di.main(["--check", "--root", str(root)]) == 0


# ---------------------------------------------------------------------------
# 12. Archive categorization (generator)
# ---------------------------------------------------------------------------

def test_archive_categorization(tmp_path):
    """An archived *_VALIDATION_MASTER_PLAN.md categorizes as 'archive', not
    'validation-plans' (archive segment wins over filename overrides)."""
    root = tmp_path
    (root / "docs/archive").mkdir(parents=True, exist_ok=True)
    (root / "docs/archive/OL_VALIDATION_MASTER_PLAN.md").write_text(
        "> **Status: ARCHIVED (2026-08-23).**\n\n# OL Plan\n", encoding="utf-8"
    )
    _generate(root)
    text = (root / "docs/dev/doc-inventory.md").read_text(encoding="utf-8")
    assert "archive/OL_VALIDATION_MASTER_PLAN.md" in text
    assert "| archive |" in text, (
        f"archived master plan must categorize as 'archive', inventory: {text!r}"
    )
    assert "validation-plans" not in text.split("OL_VALIDATION_MASTER_PLAN.md")[0].split("|")[-1]
