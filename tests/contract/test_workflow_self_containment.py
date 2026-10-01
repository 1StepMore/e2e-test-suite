"""The MCP matrix job must not inject path allowlists — e2e#112.

``scripts/mcp_matrix_verifier.py`` sets ``OPP_MCP_ALLOWED_DIRS``,
``OL_MCP_ALLOWED_DIRS`` and ``ORF_MCP_ALLOWED_DIRS`` itself, from
``--out-dir``. The ``mcp-matrix`` job used to inject four allowlist env
vars on top of that (a leftover from e2e#56c, when the verifier did not set
them and OL's fail-closed allowlist killed the MCP channel at startup).
PR #121 removed them.

This test exists because removing them is not self-enforcing. Editing this
workflow file does not trigger this workflow (it has ``paths:`` filters and
``.github/workflows/contract-tests.yml`` was not among them), so re-adding
the vars would produce a green run — the job would simply execute with the
vars it had just been given. A comment saying "do not re-add" is not a gate.

Worse, the injected ``MCP_ALLOWED_DIRECTORIES`` (the unified name) *outranks*
the per-module vars, so reinstating it would silently override the verifier's
own narrower ``--out-dir`` scoping. The matrix would keep reporting green
while no longer testing what it claims to test.

So: assert the invariant structurally. If a future change really does need
an allowlist injected here, this test fails and forces the author to delete
the assertion deliberately and explain why in the same commit — which is the
point.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "contract-tests.yml"

VERIFIER = "mcp_matrix_verifier.py"

#: Any env var that widens a module's filesystem allowlist. The unified name
#: and the three per-module names all count.
ALLOWLIST_ENV_RE = re.compile(r"(?:^|_)MCP_ALLOWED_(?:DIRECTORIES|DIRS)$")


def _steps_using_verifier() -> list[tuple[str, str, dict]]:
    """(job, step name, step) for every step that invokes the MCP verifier."""
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    found = []
    for job_name, job in (doc.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            if VERIFIER in str(step.get("run", "")):
                found.append((job_name, str(step.get("name", "<unnamed>")), step))
    return found


def test_workflow_defines_the_mcp_matrix_job():
    """Guard the guard: if the job is renamed, this file must be revisited."""
    steps = _steps_using_verifier()
    assert steps, (
        f"no step in {WORKFLOW.name} invokes {VERIFIER}. Either the job was "
        f"renamed or removed -- update this test to match, do not delete it."
    )


def test_mcp_matrix_job_injects_no_path_allowlist():
    """No step calling the verifier may widen a module allowlist via env."""
    offenders: list[str] = []
    for job_name, step_name, step in _steps_using_verifier():
        for key in (step.get("env") or {}):
            if ALLOWLIST_ENV_RE.search(key):
                offenders.append(f"{job_name} / {step_name} -> {key}")

    assert not offenders, (
        "the MCP matrix verifier sets its own allowlists from --out-dir, so "
        "injecting them here is redundant AND harmful: the unified "
        "MCP_ALLOWED_DIRECTORIES outranks the per-module vars, so it would "
        "override the verifier's own scoping and mask any future "
        "self-sufficiency regression (that is how e2e#109 shipped green).\n"
        f"offending env vars: {offenders}"
    )


def test_verifier_still_sets_its_own_allowlists():
    """The other half of the invariant: the verifier must stay self-sufficient.

    Guarding only the workflow side would let someone "fix" a red matrix by
    deleting the verifier's own env setup and letting the workflow supply it
    again. Both halves have to hold.
    """
    source = (REPO_ROOT / "scripts" / VERIFIER).read_text(encoding="utf-8")
    missing = [
        name
        for name in ("OPP_MCP_ALLOWED_DIRS", "OL_MCP_ALLOWED_DIRS", "ORF_MCP_ALLOWED_DIRS")
        if f'env["{name}"]' not in source
    ]
    assert not missing, (
        f"{VERIFIER} no longer sets {missing} itself. If the workflow is "
        f"meant to supply them instead, the matrix is no longer testing "
        f"verifier self-sufficiency -- do not make both changes at once."
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
