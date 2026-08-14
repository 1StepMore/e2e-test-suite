"""omni_mcp.validation — validation framework engine (guide §2 schema, §3 phases).

Phase 1 (load) lives in :mod:`loader`, phase 2 (dispatch) in
:mod:`dispatch`, phase 3 (grade) in :mod:`grader`, and the orchestrator
(aggregate / trace / persist — phases 4-6) in :mod:`engine`.  The package
must stay importable in-process by ``omni_mcp/server.py`` — clean
function signatures only, no argv parsing inside.
"""
