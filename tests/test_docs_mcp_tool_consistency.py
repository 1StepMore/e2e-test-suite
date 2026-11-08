"""Cross-reference MCP tool listings across all 3 documentation levels.

The canonical tool sets are derived from the **live registries** (single source
of truth), not hardcoded, so this gate stays honest as tools are added/removed:

  * OPP -> ``opp.mcp.server._TOOL_SCHEMAS``
  * OL  -> ``ol_mcp.tools.TOOL_REGISTRY``
  * ORF -> ``orf.mcp.server._TOOL_DISPATCH``

Levels verified:
  1. CLAUDE.md                          — MCP Tool Quick Reference (exact sets)
  2. suite AGENTS.md                    — Per-Module Cheat Sheet (counts + examples)
     docs/agent-pipeline-guide.md       — `### Tool Lists` (exact sets)
  3. per-module AGENTS.md               — MCP tools section, two compliant
       styles (issue #242): enum-style (full tool table, exact sets) or
       pointer-style (declared count + reference to the authoritative doc,
       e.g. docs/API.md):
       Omni_Pre_Processor/AGENTS.md, Omni_Localizer/AGENTS.md,
       Omni_Re_Formatter/AGENTS.md
"""

import re
from collections.abc import Callable
from pathlib import Path
from typing import Final

import pytest
from ol_mcp.tools import TOOL_REGISTRY
from opp.mcp.server import _TOOL_SCHEMAS
from orf.mcp.server import _TOOL_DISPATCH

SUITE_ROOT: Final[Path] = Path(__file__).resolve().parent.parent

# Canonical tool lists derived from the live registries (single source of truth).
CANONICAL: Final[dict[str, set[str]]] = {
    "opp-mcp-server": {entry["name"] for entry in _TOOL_SCHEMAS},
    "ol-mcp": set(TOOL_REGISTRY),
    "orf-mcp-server": set(_TOOL_DISPATCH),
}

_GUIDE: Final[Path] = SUITE_ROOT / "docs" / "agent-pipeline-guide.md"

# Map the guide's short server labels to canonical server keys.
_GUIDE_SERVER_MAP: Final[dict[str, str]] = {
    "OPP MCP": "opp-mcp-server",
    "OL MCP": "ol-mcp",
    "ORF MCP": "orf-mcp-server",
}


def _collect_tools_from_backtick_line(text: str) -> set[str]:
    """Extract tool names from a line like ``extract_document``, ``batch_extract``, ..."""
    return set(re.findall(r"`(\w+)`", text))


def _claude_md_tools(content: str) -> dict[str, set[str]]:
    """Parse CLAUDE.md tool quick reference sections.

    Expects sections like::

        ### opp-mcp-server (9 tools)
        `extract_document`, `batch_extract`, ... `get_capabilities`
    """
    result: dict[str, set[str]] = {}
    pattern = re.compile(r"^###\s+(?P<server>\S+)\s+\(\d+\s+tools\)", re.MULTILINE)
    for match in pattern.finditer(content):
        server = match.group("server")
        rest = content[match.end():].strip()
        tool_line = rest.split("\n")[0].strip()
        result[server] = _collect_tools_from_backtick_line(tool_line)
    return result


def _suite_cheat_sheet_tools(content: str) -> dict[str, tuple[int, set[str]]]:
    """Parse suite AGENTS.md Per-Module Cheat Sheet table.

    Expects rows like::

        | **OPP** | ... | 9 tools (`extract_document`, `batch_extract`...) | ... |

    Returns ``{server: (expected_tool_count, example_tools)}``. The example list
    is abbreviated, so callers validate count + example prefix, not exact set.
    """
    result: dict[str, tuple[int, set[str]]] = {}
    server_map = {"OPP": "opp-mcp-server", "OL": "ol-mcp", "ORF": "orf-mcp-server"}
    count_pattern = re.compile(r"(\d+)\s+tools")
    for line in content.splitlines():
        if "| **" not in line:
            continue
        for abbr, server in server_map.items():
            if f"**{abbr}**" in line:
                count_match = count_pattern.search(line)
                count = int(count_match.group(1)) if count_match else 0
                tools = _collect_tools_from_backtick_line(line)
                result[server] = (count, tools)
    return result


def _guide_tool_lists(content: str) -> dict[str, set[str]]:
    """Parse the `### Tool Lists` section of docs/agent-pipeline-guide.md.

    Blocks look like::

        **OPP MCP (9 tools):**
        `extract_document`, `batch_extract`, ... ``get_capabilities``

    A block's tool names may wrap across multiple lines; the block ends at the
    next line that starts a ``**...**`` block (e.g. `**Omni MCP:**`).
    """
    result: dict[str, set[str]] = {}
    section = re.search(r"^### Tool Lists\s*$", content, re.MULTILINE)
    if not section:
        return result
    rest = content[section.end():]
    stop = re.search(r"^#{2,3}\s+\S", rest, re.MULTILINE)
    body = rest[: stop.start()] if stop else rest

    header_re = re.compile(
        r"^\*\*(?P<label>[A-Za-z ]+?)\s*\(\d+ tools\):\*\*", re.MULTILINE
    )
    matches = list(header_re.finditer(body))
    for i, match in enumerate(matches):
        server = _GUIDE_SERVER_MAP.get(match.group("label").strip())
        if server is None:
            continue
        start = match.end()
        next_block = re.search(r"^\*\*", body[start:], re.MULTILINE)
        end = start + next_block.start() if next_block else len(body)
        result[server] = _collect_tools_from_backtick_line(body[start:end])
    return result


def _guide_server_overview_counts(content: str) -> dict[str, int]:
    """Parse the Server Overview count table of docs/agent-pipeline-guide.md."""
    counts: dict[str, int] = {}
    row_re = re.compile(r"^\|\s*(?P<label>[A-Za-z ]+?)\s*\|\s*(?P<count>\d+)\s*\|")
    for line in content.splitlines():
        match = row_re.match(line)
        if not match:
            continue
        server = _GUIDE_SERVER_MAP.get(match.group("label").strip())
        if server is not None:
            counts[server] = int(match.group("count"))
    return counts


_MODULE_SECTION_HEADER: Final[re.Pattern[str]] = re.compile(
    r"^## MCP tools \((?P<count>\d+) total\)", re.MULTILINE
)
# A tool name is a lowercase snake_case identifier. Anything else (`…`, `-`,
# the `Tool`/`Purpose` header cells, backticked paths like `docs/API.md`) is
# documentation debris and must never reach the registry comparison — issue
# #242: a literal `…` cell was once parsed as a tool name and flagged as an
# "extra tool".
_TOOL_IDENTIFIER: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]*$")
# Backticked or markdown-linked .md references, e.g. [`docs/API.md`](docs/API.md).
_MD_REFERENCE: Final[re.Pattern[str]] = re.compile(r"(?:`|\]\()([^\s`)\]]+\.md)")


def _module_tools_section(content: str) -> tuple[int, str] | None:
    """Return ``(declared_count, body)`` of the ``## MCP tools (N total)`` section.

    The body extends to the next markdown heading. ``None`` when the section
    is absent.
    """
    match = _MODULE_SECTION_HEADER.search(content)
    if not match:
        return None
    rest = content[match.end():]
    stop = re.search(r"^#{1,6}\s", rest, re.MULTILINE)
    body = rest[: stop.start()] if stop else rest
    return int(match.group("count")), body


def _enum_table_tools(body: str) -> set[str]:
    """Tool names from enum-style table rows (first column) in the section body.

    Only lowercase snake_case identifiers count: ``…``, ``-``, the ``Tool`` /
    ``Purpose`` header cells and backticked paths are documentation debris
    and are ignored (#242).
    """
    tools: set[str] = set()
    for line in body.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = line.split("|")
        if len(cells) < 3:
            continue
        name = cells[1].strip().strip("`").strip()
        if _TOOL_IDENTIFIER.match(name):
            tools.add(name)
    return tools


def _pointer_doc_refs(body: str) -> list[str]:
    """Authoritative docs referenced by a pointer-style section (e.g. ``docs/API.md``)."""
    refs: list[str] = []
    for raw in _MD_REFERENCE.findall(body):
        ref = raw.split("#", 1)[0]
        if ref and "://" not in ref and ref not in refs:
            refs.append(ref)
    return refs


class TestDocsMcpToolConsistency:
    """Cross-reference MCP tool names across all 3 documentation levels."""

    def _assert_exact(
        self, label: str, server: str, doc_tools: set[str]
    ) -> None:
        canonical_tools = CANONICAL[server]
        extra = doc_tools - canonical_tools
        missing = canonical_tools - doc_tools
        assert not extra, (
            f"[{label}] {server!r} lists extra tools: {sorted(extra)}"
        )
        assert not missing, (
            f"[{label}] {server!r} missing tools: {sorted(missing)}"
        )
        assert len(doc_tools) == len(canonical_tools), (
            f"[{label}] {server!r} tool count mismatch: "
            f"doc has {len(doc_tools)}, canonical has {len(canonical_tools)}"
        )

    def _check_level(
        self,
        label: str,
        filepath: Path,
        servers: set[str],
        extract_fn: Callable[[str], dict[str, set[str]]],
    ) -> None:
        assert filepath.exists(), f"File not found: {filepath}"
        content = filepath.read_text(encoding="utf-8")
        extracted = extract_fn(content)
        for server in servers:
            assert server in extracted, (
                f"[{label}] Server {server!r} not found. "
                f"Found: {sorted(extracted)}"
            )
            self._assert_exact(label, server, extracted[server])

    # --- Level 1: CLAUDE.md ---

    def test_claude_md_quick_reference(self) -> None:
        """CLAUDE.md MCP Tool Quick Reference matches canonical.

        O-7 (2026-11-08): CLAUDE.md may be a thin pointer to AGENTS.md. When it
        carries no server sections it must point at AGENTS.md; claim-site truth
        for tool counts is then enforced by scripts/doc_inventory.py --check.
        """
        path = SUITE_ROOT / "CLAUDE.md"
        content = path.read_text(encoding="utf-8")
        if not _claude_md_tools(content):
            assert "AGENTS.md" in content, (
                "CLAUDE.md carries no MCP quick reference and does not point at "
                "AGENTS.md — neither claim model is satisfied"
            )
            return
        self._check_level(
            "CLAUDE.md",
            path,
            {"opp-mcp-server", "ol-mcp", "orf-mcp-server"},
            _claude_md_tools,
        )

    # --- Level 2: suite AGENTS.md Per-Module Cheat Sheet ---

    def test_suite_agents_cheat_sheet(self) -> None:
        """Suite AGENTS.md Per-Module Cheat Sheet matches canonical count + examples.

        The cheat sheet abbreviates tool lists (e.g. ``9 tools (`extract_document`,
        `batch_extract`…)``), so we verify the tool count and that the shown
        examples are actual canonical tools rather than checking exact set equality.
        """
        filepath = SUITE_ROOT / "AGENTS.md"
        assert filepath.exists()
        content = filepath.read_text(encoding="utf-8")
        extracted = _suite_cheat_sheet_tools(content)

        expected_examples = {
            "opp-mcp-server": {"extract_document", "batch_extract"},
            "ol-mcp": {"translate_md_text", "judge_text"},
            "orf-mcp-server": {"apply_md", "apply_xliff"},
        }

        for server, canonical_tools in CANONICAL.items():
            assert server in extracted, (
                f"Server {server!r} not found in cheat sheet. Found: {sorted(extracted)}"
            )
            doc_count, doc_examples = extracted[server]
            assert doc_count == len(canonical_tools), (
                f"[Cheat Sheet] {server!r} tool count: {doc_count}, "
                f"expected {len(canonical_tools)}"
            )
            assert doc_examples == expected_examples[server], (
                f"[Cheat Sheet] {server!r} example tools: {sorted(doc_examples)}, "
                f"expected {sorted(expected_examples[server])}"
            )
            assert doc_examples <= canonical_tools, (
                f"[Cheat Sheet] {server!r} example tools {sorted(doc_examples)} are "
                f"not all canonical tools: {sorted(canonical_tools)}"
            )

    # --- Level 2: docs/agent-pipeline-guide.md Tool Lists ---

    def test_guide_server_overview_counts(self) -> None:
        """Guide Server Overview tool counts match the live registries."""
        assert _GUIDE.exists(), f"File not found: {_GUIDE}"
        counts = _guide_server_overview_counts(_GUIDE.read_text(encoding="utf-8"))
        for server, canonical_tools in CANONICAL.items():
            assert server in counts, (
                f"[Guide Overview] Server {server!r} not found. Found: {sorted(counts)}"
            )
            assert counts[server] == len(canonical_tools), (
                f"[Guide Overview] {server!r} count: {counts[server]}, "
                f"expected {len(canonical_tools)}"
            )

    def test_guide_opp_tools(self) -> None:
        """Guide Tool Lists OPP block matches canonical."""
        assert _GUIDE.exists(), f"File not found: {_GUIDE}"
        tools = _guide_tool_lists(_GUIDE.read_text(encoding="utf-8"))
        assert "opp-mcp-server" in tools, f"OPP block not found. Found: {sorted(tools)}"
        assert tools["opp-mcp-server"] == CANONICAL["opp-mcp-server"], (
            f"OPP tools from guide: {sorted(tools['opp-mcp-server'])}\n"
            f"Expected: {sorted(CANONICAL['opp-mcp-server'])}"
        )

    def test_guide_ol_tools(self) -> None:
        """Guide Tool Lists OL block matches canonical."""
        assert _GUIDE.exists(), f"File not found: {_GUIDE}"
        tools = _guide_tool_lists(_GUIDE.read_text(encoding="utf-8"))
        assert "ol-mcp" in tools, f"OL block not found. Found: {sorted(tools)}"
        assert tools["ol-mcp"] == CANONICAL["ol-mcp"], (
            f"OL tools from guide: {sorted(tools['ol-mcp'])}\n"
            f"Expected: {sorted(CANONICAL['ol-mcp'])}"
        )

    def test_guide_orf_tools(self) -> None:
        """Guide Tool Lists ORF block matches canonical."""
        assert _GUIDE.exists(), f"File not found: {_GUIDE}"
        tools = _guide_tool_lists(_GUIDE.read_text(encoding="utf-8"))
        assert "orf-mcp-server" in tools, f"ORF block not found. Found: {sorted(tools)}"
        assert tools["orf-mcp-server"] == CANONICAL["orf-mcp-server"], (
            f"ORF tools from guide: {sorted(tools['orf-mcp-server'])}\n"
            f"Expected: {sorted(CANONICAL['orf-mcp-server'])}"
        )

    # --- Level 3: Per-module AGENTS.md ---

    def _assert_module_agents_doc(
        self, label: str, server: str, module_root: Path
    ) -> None:
        """Per-module AGENTS.md accepts two compliant styles (issue #242).

        * enum-style — a full tool table: the declared section count must
          match the number of listed rows and every name is compared against
          the live registry (exact sets, unchanged strictness);
        * pointer-style — a declared count plus a pointer to the
          authoritative per-tool doc (e.g. ``docs/API.md``): the declared
          count must equal the live registry size and every referenced file
          must exist. Individual tool names are not required.

        A section that neither enumerates tools nor points anywhere fails
        loudly, so the gate can never loosen into "mentions tools somewhere".
        """
        filepath = module_root / "AGENTS.md"
        assert filepath.exists(), f"File not found: {filepath}"
        section = _module_tools_section(filepath.read_text(encoding="utf-8"))
        assert section is not None, (
            f"[{label}] no '## MCP tools (N total)' section in {filepath}"
        )
        declared, body = section
        canonical = CANONICAL[server]

        table_tools = _enum_table_tools(body)
        if table_tools:
            assert declared == len(table_tools), (
                f"[{label}] {server!r} declared tool count: {declared}, "
                f"but the enum-style table lists {len(table_tools)}"
            )
            self._assert_exact(label, server, table_tools)
            return

        # Pointer-style: the declared count must match the live registry ...
        assert declared == len(canonical), (
            f"[{label}] {server!r} pointer-style declared tool count: "
            f"{declared}, expected {len(canonical)}"
        )
        # ... and the referenced authoritative doc must exist.
        refs = _pointer_doc_refs(body)
        assert refs, (
            f"[{label}] {server!r} MCP tools section neither lists tools nor "
            f"references an authoritative doc (e.g. docs/API.md)"
        )
        for ref in refs:
            assert (module_root / ref).exists(), (
                f"[{label}] {server!r} pointer-style reference not found: "
                f"{module_root / ref}"
            )

    def test_opp_agents_md(self) -> None:
        """OPP AGENTS.md MCP tools section matches canonical (either style)."""
        self._assert_module_agents_doc(
            "OPP AGENTS.md", "opp-mcp-server", SUITE_ROOT / "Omni_Pre_Processor"
        )

    def test_ol_agents_md(self) -> None:
        """OL AGENTS.md MCP tools section matches canonical (either style)."""
        self._assert_module_agents_doc(
            "OL AGENTS.md", "ol-mcp", SUITE_ROOT / "Omni_Localizer"
        )

    def test_orf_agents_md(self) -> None:
        """ORF AGENTS.md MCP tools section matches canonical (either style)."""
        self._assert_module_agents_doc(
            "ORF AGENTS.md", "orf-mcp-server", SUITE_ROOT / "Omni_Re_Formatter"
        )

    # --- Issue #242: dual-style samples (positive + negative) ---

    def _ol_enum_style_doc(self) -> str:
        tools = sorted(CANONICAL["ol-mcp"])
        rows = "\n".join(f"| `{tool}` | purpose of {tool} |" for tool in tools)
        return (
            f"## MCP tools ({len(tools)} total)\n"
            "\n| Tool | Purpose |\n|------|---------|\n"
            f"{rows}\n"
        )

    def _ol_pointer_style_doc(self, declared: int) -> str:
        return (
            f"## MCP tools ({declared} total)\n"
            "\nThe Agent-facing surface. The authoritative per-tool parameter\n"
            "reference is [docs/API.md](docs/API.md).\n"
        )

    def test_enum_style_positive_sample(self, tmp_path: Path) -> None:
        """Enum-style: a full tool table passes the exact-set check."""
        (tmp_path / "AGENTS.md").write_text(
            self._ol_enum_style_doc(), encoding="utf-8"
        )
        self._assert_module_agents_doc("sample", "ol-mcp", tmp_path)

    def test_enum_style_negative_sample_misspelled_tool(self, tmp_path: Path) -> None:
        """A misspelled tool name in an enum-style table must fail (#242)."""
        table = self._ol_enum_style_doc().replace("`judge_text`", "`judge_textt`")
        (tmp_path / "AGENTS.md").write_text(table, encoding="utf-8")
        with pytest.raises(AssertionError, match="extra tools"):
            self._assert_module_agents_doc("sample", "ol-mcp", tmp_path)

    def test_pointer_style_positive_sample(self, tmp_path: Path) -> None:
        """Pointer-style: declared count + existing authoritative doc passes."""
        (tmp_path / "AGENTS.md").write_text(
            self._ol_pointer_style_doc(len(CANONICAL["ol-mcp"])), encoding="utf-8"
        )
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "API.md").write_text("# OL API\n", encoding="utf-8")
        self._assert_module_agents_doc("sample", "ol-mcp", tmp_path)

    def test_pointer_style_negative_sample_wrong_count(self, tmp_path: Path) -> None:
        """A wrong declared count in a pointer-style section must fail (#242)."""
        wrong = len(CANONICAL["ol-mcp"]) + 1
        (tmp_path / "AGENTS.md").write_text(
            self._ol_pointer_style_doc(wrong), encoding="utf-8"
        )
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "API.md").write_text("# OL API\n", encoding="utf-8")
        with pytest.raises(AssertionError, match="pointer-style declared tool count"):
            self._assert_module_agents_doc("sample", "ol-mcp", tmp_path)

    def test_pointer_style_negative_sample_missing_doc(self, tmp_path: Path) -> None:
        """A pointer to a non-existent authoritative doc must fail (#242)."""
        doc = self._ol_pointer_style_doc(len(CANONICAL["ol-mcp"])).replace(
            "docs/API.md", "docs/MISSING.md"
        )
        (tmp_path / "AGENTS.md").write_text(doc, encoding="utf-8")
        with pytest.raises(AssertionError, match="pointer-style reference not found"):
            self._assert_module_agents_doc("sample", "ol-mcp", tmp_path)

    def test_non_identifier_cells_never_become_tool_names(self) -> None:
        """`…`, `-` and backticked paths are debris, never tool names (#242)."""
        body = (
            "| Tool | Purpose |\n"
            "|------|---------|\n"
            "| `translate_md_text` | real tool |\n"
            "| `…` | ellipsis debris |\n"
            "| - | dash debris |\n"
            "| `docs/API.md` | a path, not a tool |\n"
        )
        assert _enum_table_tools(body) == {"translate_md_text"}
