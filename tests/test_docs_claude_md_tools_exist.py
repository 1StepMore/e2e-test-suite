"""Verify tool names listed in CLAUDE.md actually exist in module source code.

This test parses the MCP Tool Quick Reference section in CLAUDE.md,
extracts all tool names per server, and confirms each one is registered
as a function in the corresponding module's MCP server implementation.
"""

import re
import ast
from pathlib import Path
from typing import Final

SUITE_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
CLAUDE_MD: Final[Path] = SUITE_ROOT / "CLAUDE.md"

# Expected tools (from plan), used to validate the parsing worked
EXPECTED_TOOLS: Final[dict[str, set[str]]] = {
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


def _parse_claude_md_tool_sections(content: str) -> dict[str, set[str]]:
    """Parse CLAUDE.md MCP Tool Quick Reference into {server_name: {tool_names}}.

    Expects sections like:
        ### opp-mcp-server (7 tools)
        `extract_document`, `batch_extract`, ...

    Returns a dict keyed by server name with a set of tool names.
    """
    sections: dict[str, set[str]] = {}
    # Match lines like: ### opp-mcp-server (7 tools)
    pattern = re.compile(r"^###\s+(?P<server>\S+)\s+\(\d+\s+tools\)", re.MULTILINE)
    for match in pattern.finditer(content):
        server = match.group("server")
        # Find the tool list on the next non-blank line
        rest = content[match.end():].strip()
        tool_line = rest.split("\n")[0].strip()
        # Tool names are inside backtick pairs, comma-separated
        tools = re.findall(r"`(\w+)`", tool_line)
        sections[server] = set(tools)
    return sections


def _get_function_names_in_file(filepath: Path) -> set[str]:
    """Return all top-level async/sync function names defined in a Python file."""
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(filepath))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
    return names


# ---------------------------------------------------------------------------
# Source file paths per server
# ---------------------------------------------------------------------------

_SOURCE_PATHS: Final[dict[str, Path]] = {
    "opp-mcp-server": SUITE_ROOT / "Omni_Pre_Processor" / "src" / "opp" / "mcp" / "server.py",
    "ol-mcp": SUITE_ROOT / "Omni_Localizer" / "src" / "ol_mcp" / "tools.py",
    "orf-mcp-server": SUITE_ROOT / "Omni_Re_Formatter" / "src" / "orf" / "mcp" / "server.py",
}


class TestClaudeMdToolsExist:
    """Every tool named in CLAUDE.md must exist as a function in the source."""

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

        funcs_in_source = _get_function_names_in_file(source_path)
        expected = EXPECTED_TOOLS[server_name]

        # Every tool in the doc must be in the source
        for tool in tools_in_doc:
            assert tool in expected, (
                f"Tool {tool!r} in CLAUDE.md for {server_name!r} is not in the "
                f"expected set. Expected tools: {sorted(expected)}"
            )
            assert tool in funcs_in_source, (
                f"Tool {tool!r} for {server_name!r} is listed in CLAUDE.md but "
                f"no matching function found in {source_path.name}. "
                f"Functions found: {sorted(funcs_in_source)}"
            )

        # Count parity
        assert len(tools_in_doc) == len(expected), (
            f"Tool count mismatch for {server_name!r}: CLAUDE.md lists "
            f"{len(tools_in_doc)} tools {sorted(tools_in_doc)} but expected "
            f"{len(expected)} tools {sorted(expected)}"
        )

    def test_opp_tools_exist(self) -> None:
        """OPP MCP tools in CLAUDE.md must exist in opp/mcp/server.py."""
        self._assert_server_tools("opp-mcp-server")

    def test_ol_tools_exist(self) -> None:
        """OL MCP tools in CLAUDE.md must exist in ol_mcp/tools.py."""
        self._assert_server_tools("ol-mcp")

    def test_orf_tools_exist(self) -> None:
        """ORF MCP tools in CLAUDE.md must exist in orf/mcp/server.py."""
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
