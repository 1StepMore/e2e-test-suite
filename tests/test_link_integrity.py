"""CI-G10: Validate that all relative markdown links in AGENTS.md
(and other key docs) point to real files on disk.

Prior to this test, ``tests/test_agent_docs.py`` only checked section
presence in AGENTS.md / SKILL.md. It never parsed
``[text](path)`` markers and verified the target files exist.

This test catches:
  - typos in link targets (e.g. ``./Foo.md`` when the file is ``foo.md``)
  - dangling references after a file rename / move
  - submodule-relative links that need a clone step (this test
    runs AFTER ``scripts/clone_subrepos.sh`` in the workflow)

External links (http, https, mailto, #anchors) are skipped.
"""
from __future__ import annotations

import re
from pathlib import Path

SUITE_ROOT = Path(__file__).resolve().parent.parent

# Docs to validate. Add new top-level docs here as they grow.
DOCS_TO_CHECK = [
    SUITE_ROOT / "AGENTS.md",
    SUITE_ROOT / "README.md",
]

# Regex matching inline markdown links. Captures the target path.
# Excludes image syntax (![alt](path)) by only matching when not
# preceded by `!` — done with a negative lookbehind.
_LINK_RE = re.compile(
    r"(?<!\!)\[[^\]]*\]\(([^)]+)\)",
    re.MULTILINE,
)

# Schemes that mean "external / not a file"
_EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:", "//")


def _is_external(target: str) -> bool:
    target = target.strip()
    return any(target.startswith(p) for p in _EXTERNAL_PREFIXES)


def _is_anchor_only(target: str) -> bool:
    return target.strip().startswith("#")


class TestLinkIntegrity:
    """CI-G10: All relative markdown links resolve to existing files."""

    def test_agents_md_links_resolve(self):
        """Every relative link in AGENTS.md (and other key docs) points
        to an existing file.

        Failure mode: lists the broken links with their source file.
        """
        broken: list[tuple[Path, int, str, str]] = []
        checked = 0

        for doc in DOCS_TO_CHECK:
            if not doc.exists():
                # If the doc itself doesn't exist, that's a different
                # test's concern. Skip rather than fail here.
                continue
            text = doc.read_text(encoding="utf-8")
            for m in _LINK_RE.finditer(text):
                target = m.group(1).strip()
                # Strip optional title: [text](path "title")
                if " " in target and not target.startswith("."):
                    target = target.split(" ", 1)[0]
                # Strip #anchor
                if "#" in target:
                    target = target.split("#", 1)[0]
                    if not target:
                        continue
                if _is_external(target) or _is_anchor_only(target):
                    continue
                # Resolve relative to the doc's directory
                resolved = (doc.parent / target).resolve()
                checked += 1
                if not resolved.exists():
                    line_no = text[: m.start()].count("\n") + 1
                    broken.append((doc, line_no, target, str(resolved)))

        if broken:
            lines = [
                f"CI-G10: {len(broken)} broken link(s) out of {checked} checked:"
            ]
            for doc, line_no, target, resolved in broken:
                lines.append(
                    f"  {doc.relative_to(SUITE_ROOT)}:{line_no} "
                    f"[→ {target!r}] → {resolved}"
                )
            raise AssertionError("\n".join(lines))

        assert checked > 0, (
            "CI-G10: no relative links found in any checked doc — "
            "test may be too narrow or docs are empty"
        )
