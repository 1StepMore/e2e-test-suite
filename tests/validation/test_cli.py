"""Tests for omni_mcp.validation.cli (plan todo 9: CLI entrypoint +
contract lint + tier filter).

The CLI is the engine's thin consumer: argparse flags on top of
``run_scenarios``, the contract lint (--check), the listing (--list), a
dry-run plan, scenario/tier filters, and the exit-code mapping (0 = no
failures; 1 = any ``failed`` scenario, lint finding, or load error).

Every test drives ``main(argv)`` in-process and points
``--scenarios-dir`` / ``--runs-dir`` into tmp dirs, so nothing touches
the real scenario library, the real validation-runs/ dir, or the
persisted suite state.
"""

import textwrap

import pytest

from omni_mcp.validation.cli import (
    lint_scenarios,
    main,
    parse_standard_anchors,
)

VALID = """
name: sample
description: "valid hermetic scenario"
tier: 1
requires_env: []
steps:
  - name: "one"
    kind: cli
    command: "true"
    expect:
      success: true
"""

STANDARDS = """
# Standards

## Family

### Tool contract conformance {#tool-contract}

Text.
"""


def _write(tmp_path, name, body):
    """Write a file under tmp_path, creating parent dirs."""
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# --list
# ---------------------------------------------------------------------------


def test_main_list_empty_library_exits_zero(tmp_path, capsys):
    """An empty library lists 0 scenarios and exits 0 (guide §7.1 outcome:
    the engine lists zero scenarios cleanly, with no error)."""
    rc = main(["--list", "--scenarios-dir", str(tmp_path)])

    out = capsys.readouterr().out
    assert rc == 0
    assert "Available Scenarios (0)" in out


def test_main_list_enumerates_name_tier_env_steps(tmp_path, capsys):
    _write(tmp_path, "alpha.yaml", VALID)
    _write(
        tmp_path,
        "beta.yaml",
        VALID.replace(
            'name: sample',
            'name: beta-keyed',
        ).replace(
            "requires_env: []",
            "requires_env: [LLM_API_KEY]",
        ).replace(
            "tier: 1",
            "tier: 2",
        ),
    )

    rc = main(["--list", "--scenarios-dir", str(tmp_path)])

    out = capsys.readouterr().out
    assert rc == 0
    assert "Available Scenarios (2)" in out
    assert "sample" in out and "tier=1" in out and "steps=1" in out
    assert "beta-keyed" in out and "tier=2" in out
    assert "LLM_API_KEY" in out  # requires_env enumerated


# ---------------------------------------------------------------------------
# --check: contract lint
# ---------------------------------------------------------------------------


def test_main_check_clean_exits_zero(tmp_path, capsys):
    _write(tmp_path, "good.yaml", VALID)
    _write(tmp_path, "STANDARDS.md", STANDARDS)

    rc = main(["--check", "--scenarios-dir", str(tmp_path)])

    assert rc == 0
    assert "clean" in capsys.readouterr().out.lower()


def test_main_check_self_echo_command_fails(tmp_path, capsys):
    _write(
        tmp_path,
        "self-echo.yaml",
        VALID.replace('command: "true"', 'command: "echo PASS && true"'),
    )

    rc = main(["--check", "--scenarios-dir", str(tmp_path)])

    out = capsys.readouterr().out
    assert rc == 1
    assert "self-echo.yaml" in out
    assert "step 1" in out
    assert "self-echo" in out


@pytest.mark.parametrize(
    "command",
    [
        'echo PASS',
        'echo FAIL',
        'echo "PASS"',
        "echo 'PASS'",
        'echo "FAIL"',
        "echo 'FAIL'",
    ],
)
def test_main_check_self_echo_forms_all_rejected(tmp_path, capsys, command):
    """The self-echo anti-pattern: bare, double-quoted, single-quoted."""
    _write(
        tmp_path,
        "echo.yaml",
        VALID.replace('command: "true"', f"command: {command!r}"),
    )

    rc = main(["--check", "--scenarios-dir", str(tmp_path)])

    assert rc == 1
    assert "self-echo" in capsys.readouterr().out


def test_main_check_unknown_standard_anchor_fails(tmp_path, capsys):
    """D12: a standard citation must resolve to a real STANDARDS.md anchor
    heading (### Name {#anchor-id}); unknown anchor -> finding naming file
    + step + anchor."""
    _write(
        tmp_path,
        "cite.yaml",
        VALID.replace(
            'command: "true"',
            'command: "true"\n    standard: STANDARDS.md#no-such-anchor',
        ),
    )
    _write(tmp_path, "STANDARDS.md", STANDARDS)

    rc = main(["--check", "--scenarios-dir", str(tmp_path)])

    out = capsys.readouterr().out
    assert rc == 1
    assert "cite.yaml" in out
    assert "step 1" in out
    assert "no-such-anchor" in out


def test_main_check_known_standard_anchor_passes(tmp_path, capsys):
    _write(
        tmp_path,
        "cite.yaml",
        VALID.replace(
            'command: "true"',
            'command: "true"\n    standard: STANDARDS.md#tool-contract',
        ),
    )
    _write(tmp_path, "STANDARDS.md", STANDARDS)

    rc = main(["--check", "--scenarios-dir", str(tmp_path)])

    assert rc == 0


def test_main_check_malformed_citation_fails(tmp_path, capsys):
    """Citations must be STANDARDS.md#<anchor> — anything else is a
    finding (unknown/typo'd reference)."""
    _write(
        tmp_path,
        "cite.yaml",
        VALID.replace(
            'command: "true"',
            'command: "true"\n    standard: docs/other.md#exit-codes',
        ),
    )
    _write(tmp_path, "STANDARDS.md", STANDARDS)

    rc = main(["--check", "--scenarios-dir", str(tmp_path)])

    assert rc == 1
    assert "cite.yaml" in capsys.readouterr().out


def test_lint_scenarios_reports_unfalsifiable_step(tmp_path):
    """The lint re-confirms falsifiability: an empty expect block is a
    finding (the loader also rejects it at run time — belt and braces)."""
    _write(
        tmp_path,
        "empty-expect.yaml",
        VALID.replace("expect:\n      success: true", "expect: {}"),
    )

    findings = lint_scenarios(tmp_path)

    assert len(findings) == 1
    f = findings[0]
    assert f.rule == "falsifiable"
    assert "empty-expect.yaml" in f.file
    assert f.step == 1


def test_parse_standard_anchors_extracts_heading_anchors(tmp_path):
    path = _write(
        tmp_path,
        "STANDARDS.md",
        """
        ### Tool contract {#tool-contract}
        ### Exit codes {#exit-codes}
        Not a heading {#not-h2}
        ## Not h3 {#nope}
        ### No anchor heading
        """,
    )

    anchors = parse_standard_anchors(path)

    assert anchors == {"tool-contract", "exit-codes"}


# ---------------------------------------------------------------------------
# --dry-run
# ---------------------------------------------------------------------------


def test_main_dry_run_prints_plan_exits_zero_even_if_run_would_fail(
    tmp_path, capsys
):
    """Dry-run loads + validates + prints the plan; nothing dispatches, so
    a command that WOULD fail in a real run still exits 0."""
    _write(
        tmp_path,
        "doomed.yaml",
        VALID.replace('command: "true"', 'command: "false"'),
    )

    rc = main(
        ["--dry-run", "--scenarios-dir", str(tmp_path), "--runs-dir", str(tmp_path / "runs")]
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert "sample" in out  # the scenario name appears in the plan
    assert "steps=1" in out or "1 step" in out
    assert "dry" in out.lower()
    assert not (tmp_path / "runs").exists()  # no run record persisted


def test_main_dry_run_respects_filters(tmp_path, capsys):
    _write(tmp_path, "alpha.yaml", VALID)
    _write(
        tmp_path,
        "beta.yaml",
        VALID.replace('name: sample', 'name: beta').replace('tier: 1', 'tier: 2'),
    )

    rc = main(
        ["--dry-run", "--scenario", "ALPHA", "--tier", "1", "--scenarios-dir", str(tmp_path)]
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert "sample" in out
    assert "beta" not in out


# ---------------------------------------------------------------------------
# --scenario (filename substring) and --tier filters
# ---------------------------------------------------------------------------


def test_main_scenario_filter_substring_case_insensitive(tmp_path, capsys):
    _write(tmp_path, "alpha-docx.yaml", VALID)
    _write(tmp_path, "beta-docx.yaml", VALID.replace("sample", "beta-docx"))

    rc = main(
        ["--scenario", "ALPHA", "--scenarios-dir", str(tmp_path), "--runs-dir", str(tmp_path / "runs")]
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert "sample" in out  # scenario name of alpha-docx.yaml
    assert "beta-docx" not in out


def test_main_scenario_filter_no_match_warns_exits_zero(tmp_path, capsys):
    _write(tmp_path, "alpha.yaml", VALID)

    rc = main(["--scenario", "zzz", "--scenarios-dir", str(tmp_path)])

    out = capsys.readouterr().out
    assert rc == 0
    assert "WARNING" in out.upper()


def test_main_tier_filter_selects_matching_tier(tmp_path, capsys):
    _write(tmp_path, "hermetic.yaml", VALID)
    _write(
        tmp_path,
        "keyed.yaml",
        VALID.replace("sample", "keyed").replace("tier: 1", "tier: 2"),
    )

    rc = main(["--tier", "2", "--scenarios-dir", str(tmp_path), "--runs-dir", str(tmp_path / "runs")])

    out = capsys.readouterr().out
    assert rc == 0
    assert "keyed" in out
    assert "sample" not in out


def test_main_tier_and_scenario_filters_intersect(tmp_path, capsys):
    _write(tmp_path, "alpha-t1.yaml", VALID)
    _write(tmp_path, "alpha-t2.yaml", VALID.replace("sample", "alpha-t2").replace("tier: 1", "tier: 2"))
    _write(tmp_path, "beta-t2.yaml", VALID.replace("sample", "beta-t2").replace("tier: 1", "tier: 2"))

    rc = main(
        ["--tier", "2", "--scenario", "alpha", "--scenarios-dir", str(tmp_path),
         "--runs-dir", str(tmp_path / "runs")]
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert "alpha-t2" in out
    assert "alpha-t1" not in out
    assert "beta-t2" not in out


# ---------------------------------------------------------------------------
# Run mode: verdicts + exit-code mapping
# ---------------------------------------------------------------------------


def test_main_run_passed_exits_zero(tmp_path, capsys):
    _write(tmp_path, "ok.yaml", VALID)

    rc = main(["--scenarios-dir", str(tmp_path), "--runs-dir", str(tmp_path / "runs")])

    out = capsys.readouterr().out
    assert rc == 0
    assert "passed" in out  # verdict table row
    assert (tmp_path / "runs" / "latest.txt").exists()  # run persisted


def test_main_run_failed_exits_one(tmp_path, capsys):
    _write(
        tmp_path,
        "fail.yaml",
        VALID.replace('command: "true"', 'command: "false"'),
    )

    rc = main(["--scenarios-dir", str(tmp_path), "--runs-dir", str(tmp_path / "runs")])

    out = capsys.readouterr().out
    assert rc == 1
    assert "failed" in out


def test_main_run_unconfigured_exits_zero(tmp_path, capsys):
    """unconfigured is NOT a failure (guide §4.2): missing requires_env
    vars record the reason, never fail the run."""
    _write(
        tmp_path,
        "gated.yaml",
        VALID.replace("requires_env: []", "requires_env: [DEFINITELY_MISSING_VAR]"),
    )

    rc = main(["--scenarios-dir", str(tmp_path), "--runs-dir", str(tmp_path / "runs")])

    out = capsys.readouterr().out
    assert rc == 0
    assert "unconfigured" in out


def test_main_verbose_shows_per_step_detail(tmp_path, capsys):
    _write(tmp_path, "ok.yaml", VALID)

    rc = main(
        ["--verbose", "--scenarios-dir", str(tmp_path), "--runs-dir", str(tmp_path / "runs")]
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert "step 1" in out
    assert "cli: true" in out


def test_main_run_persists_run_record(tmp_path, capsys):
    _write(tmp_path, "ok.yaml", VALID)

    main(["--scenarios-dir", str(tmp_path), "--runs-dir", str(tmp_path / "runs")])

    runs = tmp_path / "runs"
    latest = (runs / "latest.txt").read_text(encoding="utf-8").strip()
    run_dir = runs / latest
    assert run_dir.is_dir()
    assert (run_dir / "scenarios.json").is_file()
    assert "sample" in (run_dir / "scenarios.json").read_text(encoding="utf-8")


def test_main_load_error_exits_one(tmp_path, capsys):
    """A malformed scenario is a load error: loud, exit 1 (never counted
    as coverage, never silently skipped)."""
    _write(tmp_path, "broken.yaml", "name: [unclosed, yaml")

    rc = main(["--scenarios-dir", str(tmp_path)])

    assert rc == 1
    assert "broken.yaml" in capsys.readouterr().err


def test_main_help_exits_zero(capsys):
    rc = main(["--help"])

    out = capsys.readouterr().out
    assert rc == 0
    for flag in ("--list", "--scenario", "--dry-run", "--verbose", "--check", "--tier"):
        assert flag in out
