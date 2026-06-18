"""Regression test: no hardcoded API keys in tracked config files.

Closes the round-15 security audit finding that
``Omni_Localizer/config/local.yaml`` contained 6+ literal API
keys. The detector in ``ol_config.loader:_check_for_hardcoded_secrets``
catches them at config-load time, but we also want a CI-level
guard so a future commit can't reintroduce plaintext keys into
a tracked file.

Tracked files scanned:
- ``Omni_Localizer/config/default.yaml``
- ``Omni_Localizer/config/test_universal.yaml``
- ``.env.example`` (placeholders only)

``local.yaml`` is gitignored so it is not checked here. Run
``ol_config.loader`` on it at startup instead (it already does).
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

TRACKED_CONFIG_FILES = [
    REPO_ROOT / "Omni_Localizer" / "config" / "default.yaml",
    REPO_ROOT / "Omni_Localizer" / "config" / "test_universal.yaml",
    REPO_ROOT / ".env.example",
]

# Same 4 patterns as ol_config/loader.py:_check_for_hardcoded_secrets
SECRET_PATTERNS: dict[str, re.Pattern] = {
    "openai/anthropic/agnes (sk-...)": re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    "nvidia nim (nvapi-...)": re.compile(r"nvapi-[A-Za-z0-9_\-]{20,}"),
    "groq (gsk_...)": re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    "zhipu/MiniMax (hex.hex)": re.compile(r"^[a-f0-9]{16,}\.[A-Za-z0-9_\-]{12,}"),
}


def _scan_file(path: Path) -> list[tuple[str, int, str]]:
    """Return list of (pattern_name, line_number, matched_text) for a file."""
    if not path.exists():
        return []
    findings = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        # Skip comment-only lines
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        for name, pat in SECRET_PATTERNS.items():
            m = pat.search(line)
            if m:
                findings.append((name, i, m.group(0)[:20] + "..."))
    return findings


class TestNoHardcodedKeys:
    """Tracked config files must not contain literal API keys."""

    @pytest.mark.parametrize("path", TRACKED_CONFIG_FILES, ids=lambda p: p.name)
    def test_file_has_no_hardcoded_secrets(self, path):
        findings = _scan_file(path)
        if findings:
            details = "\n".join(
                f"  line {ln}: {name} matched {text!r}"
                for name, ln, text in findings
            )
            pytest.fail(
                f"Hardcoded secret(s) found in {path.relative_to(REPO_ROOT)}:\n{details}\n"
                f"Use ${{ENV_VAR}} references instead and put the real value in .env (gitignored)."
            )

    def test_patterns_cover_known_providers(self):
        """The test must cover the providers we actually use. If a new
        provider is added, add its pattern here too."""
        assert "sk-" in SECRET_PATTERNS["openai/anthropic/agnes (sk-...)"].pattern
        assert "nvapi-" in SECRET_PATTERNS["nvidia nim (nvapi-...)"].pattern
        assert "gsk_" in SECRET_PATTERNS["groq (gsk_...)"].pattern

    def test_env_example_has_placeholders(self):
        """``.env.example`` must be a template, not real keys. Verify
        placeholder text (e.g., ``<your-...-key>``) is present."""
        if not REPO_ROOT.joinpath(".env.example").exists():
            pytest.skip(".env.example not found")
        content = REPO_ROOT.joinpath(".env.example").read_text(encoding="utf-8")
        assert "<your-" in content, (
            ".env.example should contain placeholders like <your-zhipu-api-key>, "
            "not real API keys."
        )
