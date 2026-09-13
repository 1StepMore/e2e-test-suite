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
  3. per-module AGENTS.md               — MCP tools tables (exact sets):
       Omni_Pre_Processor/AGENTS.md, Omni_Localizer/AGENTS.md,
       Omni_Re_Formatter/AGENTS.md
"""

import re
from pathlib import Path
from typing import Callable, Final

from opp.mcp.server import _TOOL_SCHEMAS
from ol_mcp.tools import TOOL_REGISTRY
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


def _per_module_table_tools(content: str) -> set[str]:
    """Extract tool names from a per-module AGENTS.md MCP tools table.

    Looks for a section header like "## MCP tools (9 total)" and parses the
    first column of the table below it.
    """
    section_pattern = re.compile(r"^## MCP tools \(\d+ total\)", re.MULTILINE)
    match = section_pattern.search(content)
    if not match:
        return set()
    rest = content[match.end():].strip()
    _NON_TOOLS = {"Tool", "Purpose"}
    tools: set[str] = set()
    for line in rest.splitlines()[:25]:
        if not line.startswith("|"):
            if line.startswith("##") or line.startswith("---"):
                break
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) >= 2:
            first_col = cells[1].strip()
            tool_name = first_col.strip("`")
            if tool_name and tool_name not in _NON_TOOLS and not tool_name.startswith("-"):
                tools.add(tool_name)
    return tools


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
        """CLAUDE.md MCP Tool Quick Reference matches canonical."""
        self._check_level(
            "CLAUDE.md",
            SUITE_ROOT / "CLAUDE.md",
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

    def test_opp_agents_md(self) -> None:
        """OPP AGENTS.md MCP tools table matches canonical."""
        content = (SUITE_ROOT / "Omni_Pre_Processor" / "AGENTS.md").read_text(encoding="utf-8")
        self._assert_exact("OPP AGENTS.md", "opp-mcp-server", _per_module_table_tools(content))

    def test_ol_agents_md(self) -> None:
        """OL AGENTS.md MCP tools table matches canonical."""
        content = (SUITE_ROOT / "Omni_Localizer" / "AGENTS.md").read_text(encoding="utf-8")
        self._assert_exact("OL AGENTS.md", "ol-mcp", _per_module_table_tools(content))

    def test_orf_agents_md(self) -> None:
        """ORF AGENTS.md MCP tools table matches canonical."""
        content = (SUITE_ROOT / "Omni_Re_Formatter" / "AGENTS.md").read_text(encoding="utf-8")
        self._assert_exact("ORF AGENTS.md", "orf-mcp-server", _per_module_table_tools(content))
