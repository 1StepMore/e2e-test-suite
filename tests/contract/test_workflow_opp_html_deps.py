"""CI must install OPP's load-bearing HTML dep — e2e#148.

``contract-tests.yml`` installs OPP as ``-e ./Omni_Pre_Processor``, with no
extras. But ``markdownify`` lives in OPP's optional ``web`` extra, so a bare
editable install does not have it.

That is invisible in the common case, because OPP's HTML extractor does not
fail when the import is missing — it degrades. ``html_to_markdown()`` returns
the *raw HTML* instead of Markdown, the raw markup is then parsed as if it
were Markdown, and the resulting paragraph text still carries its tags. The
skeleton builder matches paragraph text against the DOM text of the original
document; markup-contaminated text matches nothing, ``matched == 0``, and
``_generate_skeleton_html`` returns ``None``. No paragraphs-with-anchors means
no ``skeleton.zip``, so OPP's ``extract_document`` returns no
``skeleton_path``, so the ``html -> html (xliff)`` matrix cell FAILs.

The symptom points away from the cause. It reads as a missing OPP capability —
the CLI channel passes locally while the MCP channel fails — which is how this
became "OPP does not support HTML skeletons" instead of "CI is missing a
package". Reproduced exactly: with the import blocked, the fixture's two
blocks collapse to the single glued paragraph ``htmlTestHello, world.``,
byte-identical to the CI log; with it present, the cell passes and the
skeleton zip carries one ``data-trans-unit-id`` anchor per block.

``markdownify`` is the whole fix. Its two siblings in the same extra are
excluded on purpose, and the second test pins that: ``readability-lxml``
degrades low-content HTML (see below), and ``docling`` is heavy and optional.

Editing this workflow file does not trigger ``contract-tests.yml`` for its own
edits unless the path filters match, and a green run would not have shown the
missing package either — the job simply executes with whatever it installed.
So assert the invariant structurally: if a future change really does need OPP
installed without ``markdownify``, this test fails and forces the author to
delete the assertion deliberately and explain why in the same commit.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "contract-tests.yml"

#: How OPP is installed in these workflows (editable, root-level clone).
OPP_EDITABLE = "-e ./Omni_Pre_Processor"

#: The load-bearing import. ``html_to_markdown()`` returns raw HTML without it,
#: the markup is then parsed as if it were Markdown, and the resulting
#: paragraphs carry their tags.
REQUIRED_HTML_DEPS = ("markdownify",)

#: Same optional ``web`` extra, deliberately not installed. readability-lxml
#: scores the document and returns an empty summary when it judges the content
#: too small — which blanks the PDF-via-HTML path entirely. docling is heavy
#: and genuinely optional. Both exclusions are measured, not stylistic.
FORBIDDEN_HTML_DEPS = ("readability-lxml", "docling")


def _opp_install_steps() -> list[tuple[str, str]]:
    """(job, install command) for every step that pip-installs OPP."""
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    found = []
    for job_name, job in (doc.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            for line in str(step.get("run", "")).splitlines():
                if "pip install" in line and OPP_EDITABLE in line:
                    found.append((job_name, line.strip()))
    return found


def test_workflow_installs_opp_at_all():
    """Guard the guard: if OPP moves or the install form changes, revisit this."""
    steps = _opp_install_steps()
    assert steps, (
        f"no step in {WORKFLOW.name} pip-installs {OPP_EDITABLE}. Either the "
        f"workflow was restructured or this test is stale -- update this test "
        f"to match, do not delete it."
    )


def test_opp_installs_carry_html_capable_deps():
    """Every OPP install must bring the deps its HTML extractor silently needs."""
    offenders = [
        f"{job}: {cmd}"
        for job, cmd in _opp_install_steps()
        if [dep for dep in REQUIRED_HTML_DEPS if not re.search(rf"\b{dep}\b", cmd)]
    ]
    assert not offenders, (
        "OPP's HTML extractor degrades silently without markdownify and "
        "readability-lxml: blocks collapse into one markup-contaminated "
        "paragraph, the skeleton text match finds nothing, no skeleton.zip is "
        "produced, and `extract_document` returns no `skeleton_path` — which "
        "surfaces as the html -> html (xliff) cell failing for reasons that "
        "look like a missing OPP capability (e2e#148). docling stays optional: "
        "OPP falls back to readability without it, and that path works.\n"
        f"installs missing the deps: {offenders}"
    )


def test_opp_installs_exclude_degrading_html_deps():
    """readability-lxml must stay out: it empties low-content HTML, not just PDF."""
    offenders = [
        f"{job}: {dep}"
        for job, cmd in _opp_install_steps()
        for dep in FORBIDDEN_HTML_DEPS
        if re.search(rf"\b{dep}\b", cmd)
    ]
    assert not offenders, (
        "readability-lxml returns an empty summary when it scores a document as "
        "too small to be readable content. OPP routes PDF through HTML, so the "
        "smallest fixtures come back with `paragraphs: []` and `content: ''` — "
        "measured: the pdf md subset goes 12 fail / 0 pass with it installed and "
        "0 fail / 12 pass without. Installing it to 'match the [web] extra' "
        "would reintroduce a silent-wrong-output path (OPP#97) that this matrix "
        "would then report as a capability gap. docling stays out as well: it is "
        "heavy and OPP falls back cleanly without it.\n"
        f"forbidden deps installed: {offenders}"
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
