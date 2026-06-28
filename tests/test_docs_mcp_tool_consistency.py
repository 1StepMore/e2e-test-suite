"""Cross-reference MCP tool listings across all 3 documentation levels.

Levels verified:
  1. CLAUDE.md        — MCP Tool Quick Reference section
  2. suite AGENTS.md  — Per-Module Cheat Sheet + MCP Tool Reference + Agent Tips
  3. per-module        — Omni_Pre_Processor/AGENTS.md, Omni_Localizer/AGENTS.md,
                         Omni_Re_Formatter/AGENTS.md

All levels must agree on the canonical 7+8+6 tool lists.
"""

import re
from pathlib import Path
from typing import Callable, Final

SUITE_ROOT: Final[Path] = Path(__file__).resolve().parent.parent

# Canonical tool lists from the plan (the single source of truth)
CANONICAL: Final[dict[str, set[str]]] = {
    "opp-mcp-server": {
        "extract_document",
        "batch_extract",
        "detect_format_tool",
        "generate_markdown",
        "generate_xliff",
        "save_skeleton",
        "ping",
    },
    "ol-mcp": {
        "translate_md_text",
        "translate_xliff",
        "judge_text",
        "load_glossary",
        "get_relevant_terms",
        "search_tm",
        "batch_translate_texts",
        "ping",
    },
    "orf-mcp-server": {
        "apply_md",
        "apply_xliff",
        "batch_convert",
        "detect_format",
        "info",
        "ping",
    },
}

# Map docs to which servers they reference and the regex to extract tool names
_DOC_SPEC: list[tuple[str, str, set[str], str]] = [
    # (label, filepath_relative, servers_to_check, extraction_description)
    (
        "CLAUDE.md MCP Tool Quick Reference",
        "CLAUDE.md",
        {"opp-mcp-server", "ol-mcp", "orf-mcp-server"},
        "section with backtick tool names",
    ),
    (
        "suite AGENTS.md Per-Module Cheat Sheet",
        "AGENTS.md",
        {"opp-mcp-server", "ol-mcp", "orf-mcp-server"},
        "table at row with `MCP tools` column",
    ),
    (
        "suite AGENTS.md MCP Tool Reference (OPP table)",
        "AGENTS.md",
        {"opp-mcp-server"},
        "OPP MCP Server table",
    ),
    (
        "suite AGENTS.md MCP Tool Reference (OL table)",
        "AGENTS.md",
        {"ol-mcp"},
        "OL MCP Server table",
    ),
    (
        "suite AGENTS.md MCP Tool Reference (ORF table)",
        "AGENTS.md",
        {"orf-mcp-server"},
        "ORF MCP Server table",
    ),
    (
        "suite AGENTS.md Agent Tips (OPP)",
        "AGENTS.md",
        {"opp-mcp-server"},
        "agent tips bullet list",
    ),
    (
        "suite AGENTS.md Agent Tips (OL)",
        "AGENTS.md",
        {"ol-mcp"},
        "agent tips bullet list",
    ),
    (
        "suite AGENTS.md Agent Tips (ORF)",
        "AGENTS.md",
        {"orf-mcp-server"},
        "agent tips bullet list",
    ),
    (
        "OPP AGENTS.md",
        "Omni_Pre_Processor/AGENTS.md",
        {"opp-mcp-server"},
        "MCP tools table",
    ),
    (
        "OL AGENTS.md",
        "Omni_Localizer/AGENTS.md",
        {"ol-mcp"},
        "MCP tools table",
    ),
    (
        "ORF AGENTS.md",
        "Omni_Re_Formatter/AGENTS.md",
        {"orf-mcp-server"},
        "MCP tools table",
    ),
]


def _collect_tools_from_backtick_line(text: str) -> set[str]:
    """Extract tool names from a line like ``extract_document``, ``batch_extract``, ..."""
    return set(re.findall(r"`(\w+)`", text))


def _collect_tools_from_agent_tips(text: str, server_prefix: str) -> set[str]:
    """Extract tool names from an agent tips line like:
    ``OPP MCP provides 7 tools: `extract_document`, `batch_extract`, ...``
    """
    # Find the line containing the server prefix and "provides"
    for line in text.splitlines():
        if server_prefix in line and "provides" in line:
            return set(re.findall(r"`(\w+)`", line))
    return set()


def _claude_md_tools(content: str) -> dict[str, set[str]]:
    """Parse CLAUDE.md tool quick reference sections."""
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

    Expects rows like:
        | **OPP** | ... | 7 tools (`extract_document`, `batch_extract`...) | ... |

    Returns a dict mapping server name -> (expected_tool_count, set_of_example_tools).
    The example list is often abbreviated (first 2 tools + ellipsis), so the
    validation checks count + example prefix, not exact set match.
    """
    result: dict[str, tuple[int, set[str]]] = {}
    server_map = {"OPP": "opp-mcp-server", "OL": "ol-mcp", "ORF": "orf-mcp-server"}
    count_pattern = re.compile(r"(\d+)\s+tools")
    for line in content.splitlines():
        if "| **" not in line:
            continue
        for abbr, server in server_map.items():
            if f"**{abbr}**" in line:
                # Extract tool count
                count_match = count_pattern.search(line)
                count = int(count_match.group(1)) if count_match else 0
                tools = _collect_tools_from_backtick_line(line)
                result[server] = (count, tools)
    return result


def _suite_mcp_table_tools(content: str, section_title: str) -> set[str]:
    """Extract tool names from an MCP Tool Reference table.

    Finds the section by title (e.g. "OPP MCP Server (7 tools)"),
    then parses tool names from the first column of the table rows.
    """
    # Find the section start
    section_pattern = re.compile(
        rf"^###\s+{re.escape(section_title)}\s*$", re.MULTILINE
    )
    match = section_pattern.search(content)
    if not match:
        return set()
    rest = content[match.end():].strip()
    _NON_TOOL_NAMES = {"Tool", "Description", "Key", "Parameters",
                       "Purpose", "The", "check", "endpoint", "magic",
                       "bytes", "detection", "interface"}
    tools: set[str] = set()
    for line in rest.splitlines()[:30]:
        if not line.startswith("|"):
            if line.startswith("##") or line.startswith("---"):
                break
            continue
        # Only extract first column (between the first two pipes)
        cells = line.split("|")
        if len(cells) >= 2:
            first_cell = cells[1].strip()
            tool = first_cell.strip("`")
            if tool and tool not in _NON_TOOL_NAMES and not tool.startswith("-"):
                tools.add(tool)
    return tools


def _per_module_table_tools(content: str) -> set[str]:
    """Extract tool names from a per-module AGENTS.md MCP tools table.

    Looks for a section header like "## MCP tools (7 total)" and parses
    the first column of the table below it.
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

        # If extract returns a dict, iterate; if a set, it applies to all servers
        if isinstance(extracted, dict):
            for server in servers:
                assert server in extracted, (
                    f"[{label}] Server {server!r} not found. "
                    f"Found: {sorted(extracted)}"
                )
                doc_tools = extracted[server]
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
        elif isinstance(extracted, set):
            for server in servers:
                canonical_tools = CANONICAL[server]
                extra = extracted - canonical_tools
                missing = canonical_tools - extracted
                assert not extra, (
                    f"[{label}] Extra tools: {sorted(extra)}"
                )
                assert not missing, (
                    f"[{label}] Missing tools: {sorted(missing)}"
                )
                assert len(extracted) == len(canonical_tools), (
                    f"[{label}] Tool count mismatch: "
                    f"doc has {len(extracted)}, canonical has {len(canonical_tools)}"
                )

    # --- Level 1: CLAUDE.md ---

    def test_claude_md_quick_reference(self) -> None:
        """CLAUDE.md MCP Tool Quick Reference matches canonical."""
        self._check_level(
            "CLAUDE.md",
            SUITE_ROOT / "CLAUDE.md",
            {"opp-mcp-server", "ol-mcp", "orf-mcp-server"},
            _claude_md_tools,
        )

    # --- Level 2: Suite AGENTS.md (3 locations) ---

    def test_suite_agents_cheat_sheet(self) -> None:
        """Suite AGENTS.md Per-Module Cheat Sheet matches canonical count + examples.

        The cheat sheet abbreviates tool lists (e.g. ``7 tools (`extract_document`,
        `batch_extract`…)``), so we verify the tool count and that the shown
        examples are actual canonical tools rather than checking exact set equality.
        """
        filepath = SUITE_ROOT / "AGENTS.md"
        assert filepath.exists()
        content = filepath.read_text(encoding="utf-8")
        extracted = _suite_cheat_sheet_tools(content)

        server_expected_tool_count = {
            "opp-mcp-server": (7, {"extract_document", "batch_extract"}),
            "ol-mcp": (8, {"translate_md_text", "judge_text"}),
            "orf-mcp-server": (6, {"apply_md", "apply_xliff"}),
        }

        for server, (expected_count, expected_examples) in server_expected_tool_count.items():
            assert server in extracted, (
                f"Server {server!r} not found in cheat sheet. Found: {sorted(extracted)}"
            )
            doc_count, doc_examples = extracted[server]
            assert doc_count == expected_count, (
                f"[Cheat Sheet] {server!r} tool count: {doc_count}, expected {expected_count}"
            )
            assert doc_examples == expected_examples, (
                f"[Cheat Sheet] {server!r} example tools: {sorted(doc_examples)}, "
                f"expected {sorted(expected_examples)}"
            )
            # Also verify examples are subset of canonical
            assert doc_examples <= CANONICAL[server], (
                f"[Cheat Sheet] {server!r} example tools {sorted(doc_examples)} are "
                f"not all canonical tools: {sorted(CANONICAL[server])}"
            )

    def test_suite_agents_opp_table(self) -> None:
        """Suite AGENTS.md OPP MCP Tool Reference table matches canonical."""
        content = (SUITE_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        tools = _suite_mcp_table_tools(content, "OPP MCP Server (7 tools)")
        assert tools == CANONICAL["opp-mcp-server"], (
            f"OPP tools from suite AGENTS.md table: {sorted(tools)}\n"
            f"Expected: {sorted(CANONICAL['opp-mcp-server'])}"
        )

    def test_suite_agents_ol_table(self) -> None:
        """Suite AGENTS.md OL MCP Tool Reference table matches canonical."""
        content = (SUITE_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        tools = _suite_mcp_table_tools(content, "OL MCP Server (8 tools)")
        assert tools == CANONICAL["ol-mcp"], (
            f"OL tools from suite AGENTS.md table: {sorted(tools)}\n"
            f"Expected: {sorted(CANONICAL['ol-mcp'])}"
        )

    def test_suite_agents_orf_table(self) -> None:
        """Suite AGENTS.md ORF MCP Tool Reference table matches canonical."""
        content = (SUITE_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        tools = _suite_mcp_table_tools(content, "ORF MCP Server (6 tools)")
        assert tools == CANONICAL["orf-mcp-server"], (
            f"ORF tools from suite AGENTS.md table: {sorted(tools)}\n"
            f"Expected: {sorted(CANONICAL['orf-mcp-server'])}"
        )

    def test_suite_agents_opp_tips(self) -> None:
        """Suite AGENTS.md Agent Tips OPP line matches canonical."""
        content = (SUITE_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        tools = _collect_tools_from_agent_tips(content, "OPP MCP provides")
        assert tools == CANONICAL["opp-mcp-server"], (
            f"OPP tools from Agent Tips: {sorted(tools)}\n"
            f"Expected: {sorted(CANONICAL['opp-mcp-server'])}"
        )

    def test_suite_agents_ol_tips(self) -> None:
        """Suite AGENTS.md Agent Tips OL line matches canonical."""
        content = (SUITE_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        tools = _collect_tools_from_agent_tips(content, "OL MCP provides")
        assert tools == CANONICAL["ol-mcp"], (
            f"OL tools from Agent Tips: {sorted(tools)}\n"
            f"Expected: {sorted(CANONICAL['ol-mcp'])}"
        )

    def test_suite_agents_orf_tips(self) -> None:
        """Suite AGENTS.md Agent Tips ORF line matches canonical."""
        content = (SUITE_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        tools = _collect_tools_from_agent_tips(content, "ORF MCP provides")
        assert tools == CANONICAL["orf-mcp-server"], (
            f"ORF tools from Agent Tips: {sorted(tools)}\n"
            f"Expected: {sorted(CANONICAL['orf-mcp-server'])}"
        )

    # --- Level 3: Per-module AGENTS.md ---

    def test_opp_agents_md(self) -> None:
        """OPP AGENTS.md MCP tools table matches canonical."""
        content = (SUITE_ROOT / "Omni_Pre_Processor" / "AGENTS.md").read_text(encoding="utf-8")
        tools = _per_module_table_tools(content)
        assert tools == CANONICAL["opp-mcp-server"], (
            f"OPP AGENTS.md tools: {sorted(tools)}\n"
            f"Expected: {sorted(CANONICAL['opp-mcp-server'])}"
        )

    def test_ol_agents_md(self) -> None:
        """OL AGENTS.md MCP tools table matches canonical."""
        content = (SUITE_ROOT / "Omni_Localizer" / "AGENTS.md").read_text(encoding="utf-8")
        tools = _per_module_table_tools(content)
        assert tools == CANONICAL["ol-mcp"], (
            f"OL AGENTS.md tools: {sorted(tools)}\n"
            f"Expected: {sorted(CANONICAL['ol-mcp'])}"
        )

    def test_orf_agents_md(self) -> None:
        """ORF AGENTS.md MCP tools table matches canonical."""
        content = (SUITE_ROOT / "Omni_Re_Formatter" / "AGENTS.md").read_text(encoding="utf-8")
        tools = _per_module_table_tools(content)
        assert tools == CANONICAL["orf-mcp-server"], (
            f"ORF AGENTS.md tools: {sorted(tools)}\n"
            f"Expected: {sorted(CANONICAL['orf-mcp-server'])}"
        )
