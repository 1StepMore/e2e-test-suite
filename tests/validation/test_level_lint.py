"""T-19 — every scenario declares an approved user level.

Wave-0 C-01 resolved "every level of user" to the two validation mission
families: ``agent-user`` and ``human-quality``.  T-19 makes that
declaration mandatory and lints it (``run_validation.py --check``): a
scenario that omits ``level:`` — or names a level outside the approved
set — is a finding, never a silent default.

These tests name the behavior before the lint rule exists (red first),
then lock it once the rule lands (green).
"""

import textwrap

from omni_mcp.validation.cli import lint_scenarios, main


def _write(tmp_path, name, level_line):
    """Write a minimal valid scenario, optionally carrying a ``level``

    *level_line* is the raw YAML header line (e.g. ``"level: agent-user"``)
    or an empty string when the scenario omits the field entirely.
    """
    p = tmp_path / name
    p.write_text(
        textwrap.dedent(
            f"""
            name: level-sample
            description: "level lint sample"
            tier: 1
            {level_line}
            steps:
              - name: "one"
                kind: cli
                command: "true"
                expect:
                  success: true
            """
        ),
        encoding="utf-8",
    )
    return p


def test_missing_level_is_a_lint_finding(tmp_path):
    """A scenario that omits ``level`` is not eligible for a silent
    default — the lint names the missing declaration (T-19)."""
    _write(tmp_path, "no-level.yaml", "")

    findings = lint_scenarios(tmp_path)

    assert any(f.rule == "level" for f in findings)


def test_unknown_level_is_a_lint_finding(tmp_path):
    """A level outside ``{agent-user, human-quality}`` is rejected —
    never coerced to a family the scenario did not declare."""
    _write(tmp_path, "bad-level.yaml", "level: developer")

    findings = lint_scenarios(tmp_path)

    assert any(f.rule == "level" for f in findings)


def test_approved_levels_are_clean(tmp_path):
    """Both approved levels pass the lint with no findings."""
    _write(tmp_path, "agent.yaml", "level: agent-user")
    _write(tmp_path, "human.yaml", "level: human-quality")

    assert lint_scenarios(tmp_path) == []


def test_main_check_missing_level_exits_one(tmp_path, capsys):
    """The ``--check`` CLI surface (not just the lint function) fails
    loudly on a missing level declaration."""
    _write(tmp_path, "no-level.yaml", "")

    rc = main(["--check", "--scenarios-dir", str(tmp_path)])

    out = capsys.readouterr().out
    assert rc == 1
    assert "level" in out


def test_main_check_unknown_level_exits_one(tmp_path, capsys):
    _write(tmp_path, "bad-level.yaml", "level: pipeline-operator")

    rc = main(["--check", "--scenarios-dir", str(tmp_path)])

    out = capsys.readouterr().out
    assert rc == 1
    assert "level" in out


def test_main_check_valid_level_exits_zero(tmp_path, capsys):
    _write(tmp_path, "agent.yaml", "level: agent-user")
    _write(tmp_path, "human.yaml", "level: human-quality")

    rc = main(["--check", "--scenarios-dir", str(tmp_path)])

    assert rc == 0
