"""Verify the tool names listed in CLAUDE.md match the live MCP registries.

This test parses the MCP Tool Quick Reference section in CLAUDE.md, extracts
all tool names per server, and confirms the set is exactly the set of tools
registered by the corresponding module's MCP server. The expected sets are
derived from the live registries (single source of truth), so the gate cannot
silently drift when a tool is added or removed:

  * OPP -> ``opp.mcp.server._TOOL_SCHEMAS``
  * OL  -> ``ol_mcp.tools.TOOL_REGISTRY``
  * ORF -> ``orf.mcp.server._TOOL_DISPATCH``
"""

import re
from pathlib import Path
from typing import Final

from opp.mcp.server import _TOOL_SCHEMAS
from ol_mcp.tools import TOOL_REGISTRY
from orf.mcp.server import _TOOL_DISPATCH

SUITE_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
CLAUDE_MD: Final[Path] = SUITE_ROOT / "CLAUDE.md"

# Expected tools derived from the live registries, used to validate both the
# parsing and completeness of the CLAUDE.md listing.
EXPECTED_TOOLS: Final[dict[str, set[str]]] = {
    "opp-mcp-server": {entry["name"] for entry in _TOOL_SCHEMAS},
    "ol-mcp": set(TOOL_REGISTRY),
    "orf-mcp-server": set(_TOOL_DISPATCH),
}

# Canonical source files per server (kept as documentation of where each
# registry originates; the registries above are imported from these modules).
_SOURCE_PATHS: Final[dict[str, Path]] = {
    "opp-mcp-server": SUITE_ROOT / "Omni_Pre_Processor" / "src" / "opp" / "mcp" / "server.py",
    "ol-mcp": SUITE_ROOT / "Omni_Localizer" / "src" / "ol_mcp" / "tools.py",
    "orf-mcp-server": SUITE_ROOT / "Omni_Re_Formatter" / "src" / "orf" / "mcp" / "server.py",
}


def _parse_claude_md_tool_sections(content: str) -> dict[str, set[str]]:
    """Parse CLAUDE.md MCP Tool Quick Reference into {server_name: {tool_names}}.

    Expects sections like::

        ### opp-mcp-server (9 tools)
        `extract_document`, `batch_extract`, ... `get_capabilities`

    Returns a dict keyed by server name with a set of tool names.
    """
    sections: dict[str, set[str]] = {}
    pattern = re.compile(r"^###\s+(?P<server>\S+)\s+\(\d+\s+tools\)", re.MULTILINE)
    for match in pattern.finditer(content):
        server = match.group("server")
        # Find the tool list on the next non-blank line
        rest = content[match.end():].strip()
        tool_line = rest.split("\n")[0].strip()
        tools = re.findall(r"`(\w+)`", tool_line)
        sections[server] = set(tools)
    return sections


class TestClaudeMdToolsExist:
    """Every tool named in CLAUDE.md must match the server's live registry."""

    def _assert_server_tools(self, server_name: str) -> None:
        content = CLAUDE_MD.read_text(encoding="utf-8")
        parsed = _parse_claude_md_tool_sections(content)
        assert server_name in parsed, (
            f"Server {server_name!r} not found in CLAUDE.md sections. "
            f"Found: {list(parsed)}"
        )
        tools_in_doc = parsed[server_name]

        source_path = _SOURCE_PATHS.get(server_name)
        assert source_path is not None, f"No source path registered for {server_name!r}"
        assert source_path.exists(), f"Source file not found: {source_path}"

        expected = EXPECTED_TOOLS[server_name]
        assert expected, f"Registry for {server_name!r} reported zero tools"

        # Every tool in the doc must exist in the live registry.
        unknown = tools_in_doc - expected
        assert not unknown, (
            f"CLAUDE.md lists tool(s) for {server_name!r} that are not registered: "
            f"{sorted(unknown)}. Registered tools: {sorted(expected)}"
        )

        # Every registered tool must be documented (no silent omissions).
        undocumented = expected - tools_in_doc
        assert not undocumented, (
            f"CLAUDE.md omits registered tool(s) for {server_name!r}: "
            f"{sorted(undocumented)}. Documented tools: {sorted(tools_in_doc)}"
        )

        # Count parity (redundant with set equality, but gives a clear message).
        assert len(tools_in_doc) == len(expected), (
            f"Tool count mismatch for {server_name!r}: CLAUDE.md lists "
            f"{len(tools_in_doc)} tools {sorted(tools_in_doc)} but expected "
            f"{len(expected)} tools {sorted(expected)}"
        )

    def test_opp_tools_exist(self) -> None:
        """OPP MCP tools in CLAUDE.md must match opp/mcp/server.py registry."""
        self._assert_server_tools("opp-mcp-server")

    def test_ol_tools_exist(self) -> None:
        """OL MCP tools in CLAUDE.md must match ol_mcp/tools.py registry."""
        self._assert_server_tools("ol-mcp")

    def test_orf_tools_exist(self) -> None:
        """ORF MCP tools in CLAUDE.md must match orf/mcp/server.py registry."""
        self._assert_server_tools("orf-mcp-server")

    def test_no_unknown_servers_in_claude_md(self) -> None:
        """CLAUDE.md must not list servers beyond the three expected ones."""
        content = CLAUDE_MD.read_text(encoding="utf-8")
        parsed = _parse_claude_md_tool_sections(content)
        expected_servers = set(EXPECTED_TOOLS)
        parsed_servers = set(parsed)
        unknown = parsed_servers - expected_servers
        assert not unknown, (
            f"CLAUDE.md lists unknown MCP server(s): {sorted(unknown)}"
        )
        missing = expected_servers - parsed_servers
        assert not missing, (
            f"CLAUDE.md is missing expected MCP server(s): {sorted(missing)}"
        )
