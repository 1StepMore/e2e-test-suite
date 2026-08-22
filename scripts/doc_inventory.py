"""Task 2 stub for the doc inventory generator/checker (RED state).

Every mode and helper raises ``NotImplementedError``. Task 3 replaces this
stub with a real implementation that satisfies the contracts pinned in
``tests/test_doc_inventory.py`` (which is the only consumer of this module).
"""


def count_tool_schemas(path):
    """Count ``"name": ...`` entries in a ``_TOOL_SCHEMAS`` block."""
    raise NotImplementedError


def count_tool_registry(path):
    """Count ``from ol_mcp.X import ...`` lines plus ``TOOL_REGISTRY[...]`` keys."""
    raise NotImplementedError


def count_listed_tools(path):
    """Count ``types.Tool(name=...)`` entries in an ORF ``_list_tools`` return."""
    raise NotImplementedError


def main(argv=None):
    """CLI entry point.

    ``main(["--root", R])``      -> generate mode (writes docs/dev/doc-inventory.md)
    ``main(["--check", "--root", R])`` -> check mode (verifies inventory consistency)
    """
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
