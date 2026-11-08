"""Regression tests for the canonical scenario-file rule (issue #266).

The dot-directory filter must inspect only the path *below* the scenarios
root.  A dot component in the root's ancestors (``/tmp/.probe/scenarios``)
is not a hidden scenario directory; treating it as one hid every scenario
in that library.
"""

from pathlib import Path

from scripts.validation.scenario_discovery import iter_scenario_yamls

VALID_SCENARIO = """
name: sample
description: "valid scenario"
steps:
  - name: "one"
    kind: cli
    command: "true"
    expect:
      success: true
"""


def _write(root: Path, rel: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(VALID_SCENARIO, encoding="utf-8")
    return path


def test_dot_ancestor_does_not_hide_scenarios(tmp_path):
    root = tmp_path / ".probe" / "scenarios"
    expected = _write(root, "normal.yaml")

    assert iter_scenario_yamls(root) == [expected]


def test_dot_root_itself_does_not_hide_scenarios(tmp_path):
    root = tmp_path / ".scenarios"
    expected = _write(root, "normal.yaml")

    assert iter_scenario_yamls(root) == [expected]


def test_hidden_child_directory_is_still_excluded(tmp_path):
    root = tmp_path / "scenarios"
    expected = _write(root, "normal.yaml")
    _write(root, ".hidden/bad.yaml")

    assert iter_scenario_yamls(root) == [expected]
