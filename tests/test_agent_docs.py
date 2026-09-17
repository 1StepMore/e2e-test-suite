"""W3.3: Content-scraping verification for AGENTS.md and SKILL.md."""
from pathlib import Path

SUITE_ROOT = Path(__file__).resolve().parent.parent

SKILL = SUITE_ROOT / ".opencode" / "skills" / "omni-suite" / "SKILL.md"
AGENTS = SUITE_ROOT / "AGENTS.md"


class TestAgentDocs:
    def test_agents_md_exists(self):
        assert AGENTS.exists(), f"AGENTS.md not found at {AGENTS}"
        content = AGENTS.read_text(encoding="utf-8")
        required = ["Quick Start", "Per-Module Cheat Sheet", "Common Tasks",
                     "Critical Notes", "Agent Tips"]
        for section in required:
            assert section in content, f"AGENTS.md missing: '{section}'"

    def test_skill_md_exists(self):
        assert SKILL.exists(), f"SKILL.md not found at {SKILL}"
        content = SKILL.read_text(encoding="utf-8")
        assert content.startswith("---\n"), "SKILL.md must start with YAML"
        assert "name: omni-suite" in content
        assert "description:" in content
        required = ["When to use", "The 3 stages",
                     "Output formats", "Critical constraints", "Example"]
        for section in required:
            assert section in content, f"SKILL.md missing: '{section}'"
