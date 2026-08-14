"""omni_mcp.validation — validation framework engine (guide §2 schema, §3 phases).

Phase 1 (load) lives in :mod:`loader`; dispatch / grader / aggregator /
persistence arrive in later todos (6-8).  The package must stay importable
in-process by ``omni_mcp/server.py`` — clean function signatures only,
no argv parsing inside.
"""
