"""Tests for scripts/validation/artifact_assertions.py (e2e-test-suite#44).

The assertion engine runs DETERMINISTIC checks on ACTUAL produced files —
the artifacts of the OPP → OL → ORF pipeline. Every text artifact runs the
always-on hard-security group (``_no_placeholder_leak`` P0,
``_no_secret_leak`` P0, ``_no_broken_reference`` P1,
``_no_external_error_text`` P0); module-specific structure assertions run
only when ``module`` matches (opp/ol/orf/all), and ``module="suite"`` runs
hard-security only.

Hermetic: no OPP/OL/ORF CLI, no LLM, no network. All fixtures are files in
``tmp_path``; the script is loaded from its file path with importlib (the
same convention as ``tests/validation/test_delivery_package.py`` — scripts/
is not a package).
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

SUITE_ROOT = Path(__file__).resolve().parent.parent.parent

_SCRIPT_PATH = SUITE_ROOT / "scripts" / "validation" / "artifact_assertions.py"

HARD_SECURITY_NAMES = {
    "_no_placeholder_leak",
    "_no_secret_leak",
    "_no_broken_reference",
    "_no_external_error_text",
}

# A clean artifact that must pass ALL hard-security assertions: a realistic
# markdown doc with a heading, list, table, and a plausible link target.
# No numbers 429/500/502/503 anywhere (the _EXT_ERROR regex flags them).
CLEAN_MD = """# Document Title

This is a plain paragraph with some content.

- item one
- item two

| col1 | col2 |
|------|------|
| a    | b    |

[link](https://example.com)
"""


def _load_assertions():
    """Import scripts/validation/artifact_assertions.py from its file path."""
    spec = importlib.util.spec_from_file_location("artifact_assertions", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["artifact_assertions"] = mod
    spec.loader.exec_module(mod)
    return mod


aa = _load_assertions()


# ---------------------------------------------------------------------------
# AssertionResult contract
# ---------------------------------------------------------------------------


def test_assertion_result_is_frozen_dataclass():
    """AssertionResult is a frozen dataclass; mutating an attribute raises."""
    r = aa.AssertionResult(
        "_no_placeholder_leak", False, "e2e#44", "P0", "suite", "doc.md",
        "placeholders=_No data_",
    )
    assert r.name == "_no_placeholder_leak"
    assert r.passed is False
    assert r.severity == "P0"
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.passed = True  # type: ignore[misc]


def test_assertion_result_to_dict_shape():
    """to_dict() returns the exact 7-key asdict shape report/engine read."""
    r = aa.AssertionResult(
        "_no_placeholder_leak", False, "e2e#44", "P0", "suite", "doc.md", "clean"
    )
    d = r.to_dict()
    assert set(d) == {"name", "passed", "issue", "severity", "module", "artifact", "detail"}
    assert d == {
        "name": "_no_placeholder_leak",
        "passed": False,
        "issue": "e2e#44",
        "severity": "P0",
        "module": "suite",
        "artifact": "doc.md",
        "detail": "clean",
    }


# ---------------------------------------------------------------------------
# Hard-security group — parametrized pollution -> failing assertion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "content, assertion, severity",
    [
        # _no_placeholder_leak (P0)
        ("the value was _No data_", "_no_placeholder_leak", "P0"),
        ("config = {{var}}", "_no_placeholder_leak", "P0"),
        ("note: <finding 1>", "_no_placeholder_leak", "P0"),
        ("leftover [OL:PLACEHOLDER:0000] marker", "_no_placeholder_leak", "P0"),
        # _no_secret_leak (P0)
        ("key sk-abcdefghijklmnop1234", "_no_secret_leak", "P0"),
        ("token AIzaSyD1234567890abcdefghij", "_no_secret_leak", "P0"),
        ("aws AKIAIOSFODNN7EXAMPLE", "_no_secret_leak", "P0"),
        ("-----BEGIN PRIVATE KEY-----\nabc", "_no_secret_leak", "P0"),
        ("ghp_abcdefghijklmnopqrstuvwxyzABCDEFGH", "_no_secret_leak", "P0"),
        # _no_broken_reference (P1)
        ("[View Source]()", "_no_broken_reference", "P1"),
        ("![]( )", "_no_broken_reference", "P1"),
        # _no_external_error_text (P0)
        ("Traceback (most recent call last)\n", "_no_external_error_text", "P0"),
        ("litellm timeout", "_no_external_error_text", "P0"),
        ("line \x1b[31mred\x1b[0m", "_no_external_error_text", "P0"),
    ],
)
def test_hard_security_pollution_fails(tmp_path, content, assertion, severity):
    """Each polluted content fails its own hard-security assertion, with the
    documented severity, on module='suite' (hard-security only)."""
    (tmp_path / "doc.md").write_text(content, encoding="utf-8")
    results = aa.run_assertions(tmp_path, "suite")
    by_name = {r.name: r for r in results}
    assert set(by_name) == HARD_SECURITY_NAMES  # suite -> no structure checks
    failing = by_name[assertion]
    assert failing.passed is False
    assert failing.severity == severity
    assert failing.artifact == "doc.md"


def test_clean_artifact_all_hard_security_pass(tmp_path):
    """A plain, clean markdown artifact passes all four hard-security
    assertions (module suite)."""
    (tmp_path / "doc.md").write_text(CLEAN_MD, encoding="utf-8")
    results = aa.run_assertions(tmp_path, "suite")
    assert {r.name for r in results} == HARD_SECURITY_NAMES
    assert all(r.passed for r in results)


def test_run_assertions_missing_dir_returns_empty(tmp_path):
    """A nonexistent artifacts dir yields zero results, never an error."""
    assert aa.run_assertions(tmp_path / "nope") == []


def test_run_assertions_sorted_by_artifact_then_name(tmp_path):
    """Results come back sorted by (artifact, name) — deterministic order."""
    (tmp_path / "b.txt").write_text("clean", encoding="utf-8")
    (tmp_path / "a.txt").write_text("clean", encoding="utf-8")
    results = aa.run_assertions(tmp_path, "suite")
    keys = [(r.artifact, r.name) for r in results]
    assert keys == sorted(keys)
    # each of the 4 hard-security assertions ran on both files; a.txt first
    assert [r.artifact for r in results][:4] == ["a.txt"] * 4
    assert [r.artifact for r in results][4:] == ["b.txt"] * 4


# ---------------------------------------------------------------------------
# module='suite' — hard-security only, no structure assertions
# ---------------------------------------------------------------------------


def test_module_suite_runs_only_hard_security(tmp_path):
    """Under 'suite' a structurally broken .csv gets NO _csv_structure check —
    only the four hard-security assertions run, all passing."""
    (tmp_path / "data.csv").write_text("only,header,row\n", encoding="utf-8")
    (tmp_path / "doc.md").write_text("_No data_", encoding="utf-8")
    results = aa.run_assertions(tmp_path, "suite")
    names = {r.name for r in results}
    assert names == HARD_SECURITY_NAMES
    assert "csv_structure" not in names
    placeholder = next(
        r for r in results
        if r.name == "_no_placeholder_leak" and r.artifact == "doc.md"
    )
    assert placeholder.passed is False


def test_module_suite_skips_structure_that_opp_would_flag(tmp_path):
    """The same single-row .csv PASSES under suite (no csv check) but the
    structure assertion exists and fires under module='opp'."""
    (tmp_path / "data.csv").write_text("only,header\n", encoding="utf-8")
    suite_names = {r.name for r in aa.run_assertions(tmp_path, "suite")}
    assert suite_names == HARD_SECURITY_NAMES
    opp = [r for r in aa.run_assertions(tmp_path, "opp") if r.name == "_csv_structure"]
    assert len(opp) == 1
    assert opp[0].passed is False


# ---------------------------------------------------------------------------
# opp — extraction structure assertions
# ---------------------------------------------------------------------------


def test_module_opp_md_nonempty(tmp_path):
    """_md_nonempty: a blank .md fails; a content .md passes."""
    (tmp_path / "empty.md").write_text("", encoding="utf-8")
    (tmp_path / "content.md").write_text("# Hi\n", encoding="utf-8")
    results = aa.run_assertions(tmp_path, "opp")
    by_artifact = {r.artifact: r for r in results if r.name == "_md_nonempty"}
    assert not by_artifact["empty.md"].passed
    assert by_artifact["content.md"].passed


def test_module_opp_manifest_json_parseable(tmp_path):
    """_manifest_json_parseable: a *_manifest.json missing required keys
    fails; a complete manifest passes."""
    ok = tmp_path / "doc_manifest.json"
    ok.write_text(
        json.dumps({
            "source": {"file_path": "doc.docx", "format": "docx"},
            "extraction": {"outputs": ["doc.md"]},
        }),
        encoding="utf-8",
    )
    bad = tmp_path / "bad_manifest.json"
    bad.write_text('{"source": {}}', encoding="utf-8")
    results = aa.run_assertions(tmp_path, "opp")
    by_artifact = {r.artifact: r for r in results if r.name == "_manifest_json_parseable"}
    assert by_artifact["doc_manifest.json"].passed
    assert not by_artifact["bad_manifest.json"].passed


def test_module_opp_csv_structure(tmp_path):
    """_csv_structure: >= 2 rows with consistent column counts pass; a
    single row (or ragged rows) fails."""
    (tmp_path / "good.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (tmp_path / "bad.csv").write_text("only,header\n", encoding="utf-8")
    results = aa.run_assertions(tmp_path, "opp")
    by_artifact = {r.artifact: r for r in results if r.name == "_csv_structure"}
    assert by_artifact["good.csv"].passed
    assert not by_artifact["bad.csv"].passed


def test_module_opp_html_no_tag_leak(tmp_path):
    """_html_no_tag_leak (OPP#36): a raw <html>/<body> tag in an .md fails."""
    (tmp_path / "doc.md").write_text("<html><body>leaked</body></html>", encoding="utf-8")
    results = aa.run_assertions(tmp_path, "opp")
    leaked = [r for r in results if r.name == "_html_no_tag_leak"]
    assert len(leaked) == 1
    assert leaked[0].passed is False
    assert leaked[0].issue == "OPP#36"
    assert leaked[0].severity == "P1"


# ---------------------------------------------------------------------------
# ol — translation structure assertions
# ---------------------------------------------------------------------------


def test_module_ol_target_complete_xlf_empty_target_fails(tmp_path):
    """_target_complete: an .xlf whose <trans-unit> has an empty <target>
    fails; a unit with a non-empty target passes."""
    empty = """<xliff version="1.2">
  <file>
    <body>
      <trans-unit id="1">
        <source>Hello</source>
        <target></target>
      </trans-unit>
    </body>
  </file>
</xliff>
"""
    (tmp_path / "empty.xlf").write_text(empty, encoding="utf-8")
    filled = """<xliff version="1.2">
  <file>
    <body>
      <trans-unit id="1">
        <source>Hello</source>
        <target>你好</target>
      </trans-unit>
    </body>
  </file>
</xliff>
"""
    (tmp_path / "filled.xlf").write_text(filled, encoding="utf-8")
    results = aa.run_assertions(tmp_path, "ol")
    by_artifact = {r.artifact: r for r in results if r.name == "_target_complete"}
    assert not by_artifact["empty.xlf"].passed
    assert by_artifact["filled.xlf"].passed


def test_module_ol_no_source_echo_self_translation_fails(tmp_path):
    """_no_source_echo: an .md whose frontmatter declares source_lang ==
    target_lang (self-translation) fails."""
    (tmp_path / "doc.md").write_text(
        "---\nsource_lang: en\ntarget_lang: en\n---\n# Translated\n",
        encoding="utf-8",
    )
    results = aa.run_assertions(tmp_path, "ol")
    echo = [r for r in results if r.name == "_no_source_echo"]
    assert len(echo) == 1
    assert echo[0].passed is False
    assert "self-translation" in echo[0].detail


def test_module_ol_shield_roundtrip(tmp_path):
    """_shield_roundtrip: a leftover [OL:TYPE:NNNN] marker in an .md output
    fails (stricter than the P0 placeholder leak)."""
    (tmp_path / "doc.md").write_text("unresolved [OL:CODE:0000] marker", encoding="utf-8")
    results = aa.run_assertions(tmp_path, "ol")
    shield = [r for r in results if r.name == "_shield_roundtrip"]
    assert len(shield) == 1
    assert shield[0].passed is False
    assert shield[0].issue == "E2E-77/78"


# ---------------------------------------------------------------------------
# orf — backfill structure assertions
# ---------------------------------------------------------------------------


def test_module_orf_srt_timecodes(tmp_path):
    """_srt_timecodes: a cue with a valid HH:MM:SS,mmm --> HH:MM:SS,mmm
    timecode passes; a cue WITH an arrow but malformed timecode fails."""
    (tmp_path / "subs.srt").write_text(
        "1\n00:00:01,000 --> 00:00:04,000\nHello\n", encoding="utf-8"
    )
    (tmp_path / "bad.srt").write_text(
        "1\n00:00:01 --> 00:00:04\nHello\n", encoding="utf-8"
    )
    results = aa.run_assertions(tmp_path, "orf")
    by_artifact = {r.artifact: r for r in results if r.name == "_srt_timecodes"}
    assert by_artifact["subs.srt"].passed
    assert not by_artifact["bad.srt"].passed


def test_module_orf_srt_no_timecode_cues_passes(tmp_path):
    """An SRT passthrough with no --> arrows at all is NOT a failure (a
    non-empty passthrough per STANDARDS.md#srt-structure)."""
    (tmp_path / "plain.srt").write_text("Just some text, no timing blocks\n", encoding="utf-8")
    results = aa.run_assertions(tmp_path, "orf")
    srt = [r for r in results if r.name == "_srt_timecodes"]
    assert len(srt) == 1
    assert srt[0].passed is True


def test_module_orf_json_parseable(tmp_path):
    """_json_parseable: valid JSON passes, malformed JSON fails."""
    (tmp_path / "ok.json").write_text('{"a": 1}', encoding="utf-8")
    (tmp_path / "bad.json").write_text('{"a": ', encoding="utf-8")
    results = aa.run_assertions(tmp_path, "orf")
    by_artifact = {r.artifact: r for r in results if r.name == "_json_parseable"}
    assert by_artifact["ok.json"].passed
    assert not by_artifact["bad.json"].passed


def test_module_orf_xml_parseable(tmp_path):
    """_xml_parseable: well-formed XML passes, mismatched tags fail."""
    (tmp_path / "ok.xml").write_text("<root><item>1</item></root>", encoding="utf-8")
    (tmp_path / "bad.xml").write_text("<root><item></root>", encoding="utf-8")
    results = aa.run_assertions(tmp_path, "orf")
    by_artifact = {r.artifact: r for r in results if r.name == "_xml_parseable"}
    assert by_artifact["ok.xml"].passed
    assert not by_artifact["bad.xml"].passed


def test_module_orf_html_has_structure(tmp_path):
    """_html_has_structure: an html with <html>+<body> passes; a bare
    fragment without structure fails."""
    (tmp_path / "ok.html").write_text(
        "<!DOCTYPE html><html><body><p>hi</p></body></html>", encoding="utf-8"
    )
    (tmp_path / "bad.html").write_text("<p>hi</p>", encoding="utf-8")
    results = aa.run_assertions(tmp_path, "orf")
    by_artifact = {r.artifact: r for r in results if r.name == "_html_has_structure"}
    assert by_artifact["ok.html"].passed
    assert not by_artifact["bad.html"].passed


def test_module_orf_docx_pptx_zip_ok(tmp_path):
    """_docx_pptx_zip_ok: a real minimal docx (zipfile) passes; a corrupt
    (non-zip) docx fails."""
    good = tmp_path / "good.docx"
    with zipfile.ZipFile(good, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<w:document/>")
    bad = tmp_path / "bad.docx"
    bad.write_bytes(b"this is not a zip file at all")
    results = aa.run_assertions(tmp_path, "orf")
    by_artifact = {r.artifact: r for r in results if r.name == "_docx_pptx_zip_ok"}
    assert by_artifact["good.docx"].passed
    assert not by_artifact["bad.docx"].passed


# ---------------------------------------------------------------------------
# module='all' — every group whose extension/frontmatter matches
# ---------------------------------------------------------------------------


def test_module_all_json_gets_opp_and_orf_checks(tmp_path):
    """Under 'all' a .json gets the opp manifest/json check AND the orf json
    check plus the 4 hard-security assertions = 6 total."""
    (tmp_path / "data.json").write_text('{"a": 1}', encoding="utf-8")
    results = aa.run_assertions(tmp_path, "all")
    names = {r.name for r in results}
    assert len(results) == 6
    assert {"_manifest_json_parseable", "_json_parseable"} <= names
    assert all(r.passed for r in results)


def test_module_all_md_gets_opp_and_ol_checks(tmp_path):
    """Under 'all' a translated .md gets opp md checks + ol checks + 4
    hard-security = 9 total, all passing."""
    (tmp_path / "doc.md").write_text(
        "---\nsource_lang: en\ntarget_lang: zh\n---\n# Title\n", encoding="utf-8"
    )
    results = aa.run_assertions(tmp_path, "all")
    names = {r.name for r in results}
    assert len(results) == 9
    assert {
        "_md_nonempty", "_html_no_tag_leak",
        "_target_complete", "_no_source_echo", "_shield_roundtrip",
    } <= names
    assert all(r.passed for r in results)
