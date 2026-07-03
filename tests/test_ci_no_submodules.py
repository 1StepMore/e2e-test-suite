"""Verify CI workflow files don't reference 'submodules: recursive'.

Also verifies they have 'fetch-depth: 1' on checkout steps.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

CI_FILES = [
    ROOT / ".github" / "workflows" / "contract-tests.yml",
    ROOT / ".github" / "workflows" / "e2e-tests.yml",
    ROOT / ".github" / "workflows" / "doctor.yml",
    ROOT / ".github" / "workflows" / "hardening-tests.yml",
    ROOT / ".github" / "workflows" / "fidelity.yml",
]


def test_no_submodules_recursive():
    """No CI workflow should have 'submodules: recursive'."""
    for path in CI_FILES:
        assert path.exists(), f"CI workflow not found: {path}"
        text = path.read_text(encoding="utf-8")
        assert "submodules: recursive" not in text, (
            f"{path.name} still contains 'submodules: recursive'"
        )


def test_fetch_depth_one_present():
    """All CI workflows should have 'fetch-depth: 1' on checkout steps."""
    for path in CI_FILES:
        assert path.exists(), f"CI workflow not found: {path}"
        text = path.read_text(encoding="utf-8")
        # Count occurrences
        count = text.count("fetch-depth: 1")
        assert count >= 1, (
            f"{path.name} missing 'fetch-depth: 1' on checkout (found {count})"
        )


def test_checkout_no_extra_args():
    """Checkout steps should not have stale 'submodules' references."""
    for path in CI_FILES:
        text = path.read_text(encoding="utf-8")
        # Ensure no line contains both checkout and submodules
        lines = text.splitlines()
        for i, line in enumerate(lines, 1):
            if "actions/checkout" in line:
                # Look at next lines in the with: block
                j = i  # 0-based index
                while j < len(lines) and lines[j].strip() == "":
                    j += 1
                # Check within the next few lines for submodules
                for k in range(j, min(j + 5, len(lines))):
                    if "submodules" in lines[k]:
                        pytest.fail(
                            f"{path.name}:{k+1} has 'submodules' near checkout"
                        )
