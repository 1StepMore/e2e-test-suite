"""CI must install OPP's HTML-capable deps — e2e#148.

``contract-tests.yml`` installs OPP as ``-e ./Omni_Pre_Processor``, with no
extras. But OPP declares ``markdownify`` and ``readability-lxml`` in its
optional ``web`` extra, so a bare editable install has neither.

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
became "OPP does not support HTML skeletons" instead of "CI is missing two
packages". Reproduced exactly: with both imports blocked, the fixture's two
blocks collapse to the single glued paragraph ``htmlTestHello, world.``,
byte-identical to the CI log; with them present, the cell passes and the
skeleton zip carries one ``data-trans-unit-id`` anchor per block.

Editing this workflow file does not trigger ``contract-tests.yml`` for its own
edits unless the path filters match, and a green run would not have shown the
missing packages anyway — the job simply executes with whatever it installed.
So assert the invariant structurally: if a future change really does need OPP
installed without these, this test fails and forces the author to delete the
assertion deliberately and explain why in the same commit.

``docling`` is deliberately not required. It is the third member of the same
``web`` extra, it is heavy, and unlike these two it is genuinely optional:
OPP falls back to readability without it, which is the path that works.
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

#: Imports OPP's HTML extractor degrades without. Both live in the optional
#: ``web`` extra; ``pip install -e ./Omni_Pre_Processor`` installs neither.
REQUIRED_HTML_DEPS = ("markdownify", "readability-lxml")


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


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
