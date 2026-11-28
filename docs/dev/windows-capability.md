# Windows capability matrix — what runs natively, what needs WSL

e2e-test-suite#447. The repo's Windows note (`AGENTS.md` → "Windows hosts") says
execution-backed validation evidence requires WSL. This page answers the other
half: **what you can do on native Windows (PowerShell / Git Bash), and how to
verify each item on your machine right now.**

Interpreter note: `.venv_ol/` is a Linux venv (WSL). The native-Windows venv is
`.venv_win/` — built by `scripts/setup_dev.ps1` (suite repo script). Every
command below routes through `.venv_win/Scripts/`.

Last full verification pass: **2026-11-28** on Windows 10.0.26300 x64 (this
matrix is re-verified whenever a row changes; a stale row should be corrected,
not copied forward).

## Matrix

| Capability | Native Windows | How to verify (paste as-is in Git Bash) | Evidence |
|---|---|---|---|
| Install (`​.venv_win`) | ✅ | `powershell -ExecutionPolicy Bypass -File scripts/setup_dev.ps1 -CheckOnly` | suite#320 fixed the `omni-security` workspace-member resolution that broke first-run installs (closed 2026-11-14); `.venv_win` exists on the verify machine |
| `omni-suite` CLI | ✅ | `./.venv_win/Scripts/omni-suite.exe --version` | printed `0.5.0` on 2026-11-28 |
| Suite pipeline, real chain (OPP→OL→ORF) | ✅ | provider key **or** endpoint triple: `LLM_BASE_URL=http://127.0.0.1:8899/v1 LLM_API_KEY=… LLM_MODEL=… ./.venv_win/Scripts/omni-suite.exe pipeline <docx> --target-format html --output out.html` | #448 E2E (`tests/test_e2e_pipeline_custom_endpoint.py`) drives the real chain over a localhost OpenAI-compatible endpoint — no provider key, no FAKE_LLM |
| Suite pipeline, plumbing only | ✅ | `OMNI_TEST_FAKE_LLM=1 ./.venv_win/Scripts/omni-suite.exe pipeline <docx> --fake-llm --target-format html --output out.html` | FAKE_LLM CI-mode is the documented plumbing path; **never** human-quality evidence (STANDARDS.md#fallbacks-never-evidence) |
| Per-module CLI smoke (opp / ol / orf) | ✅ | `OMNI_TEST_FAKE_LLM=1 ./.venv_win/Scripts/orf.exe apply-md <md> --target-format html -o out.html` (same shape for `opp` / `ol`) | all three consoles exercised in the #448 E2E run, 2026-11-28 |
| Per-module tests — OL | ✅ | `./.venv_win/Scripts/python.exe -m pytest Omni_Localizer/tests/ -q` | 1951 passed / 46 skipped / 0 failed on 2026-11-28 (Windows-native suite made green by OL#197/#201) |
| Per-module tests — OPP / ORF | ⚠️ partial | same command against `Omni_Pre_Processor/tests/` / `Omni_Re_Formatter/tests/` | Windows-native reds are tracked per repo: OPP#136, ORF#94 (ORF#106 documents the first-run red count); judge each red against those ledgers, not "known noise" |
| Suite test battery | ✅ | `./.venv_win/Scripts/python.exe -m pytest tests/ -q -m "not nightly"` | suite#349 closed the 24-red Windows-native cluster (2026-11-27); re-verified on 2026-11-28 — see the dated result below |
| pre-commit | ✅ (with caveat) | `pre-commit run --all-files` | the two `.venv_ol`-specific hooks print classified `SKIP[...]` lines instead of silently passing; mixed-staging caveat in the root `AGENTS.md` applies |
| Doc truth | ✅ | `bash scripts/pre_commit_python.sh scripts/doc_inventory.py --check` | CI-blocking gate; runs natively via the `.venv_win` router script |
| Nightly-matrix criterion **readback** | ✅ | `./.venv_win/Scripts/python.exe scripts/nightly_gap.py --skip-run` (cache restored from `99-Tools/validation-scratch/`) | #394 made the verifier platform-aware; the matrix itself is still produced in WSL |
| **Execution-backed validation evidence** | ❌ WSL required | `wsl -e bash -lc "cd /mnt/d/贯维/Omni_Suite && MCP_ALLOWED_DIRECTORIES=/tmp OMNI_TEST_FAKE_LLM=1 ./.venv_ol/bin/python scripts/validation/run_validation.py --scenario <name> --tier 1"` | `omni_mcp/validation/dispatch.py` pins `VENV_BIN` to `.venv_ol`; native parity measured 0/41 (validation-loop-log, 2026-09-17) |
| MCP servers (opp-mcp / ol-mcp / orf-mcp / omni-mcp) | ⚠️ unverified | `MCP_ALLOWED_DIRECTORIES=/tmp ./.venv_win/Scripts/python.exe -m omni_mcp.server` then handshake from your client | no native-Windows ledger row exists yet — if you verify it, update this row with the date (do not assume) |

Dated suite-battery evidence: the battery result for 2026-11-28 is recorded in
the LOOP-LOG for that date and reproducible with the command above; the matrix
intentionally stores no rot-prone pass/fail counts beyond the dated rows.

## Rules of thumb

1. Anything that only **reads Python + `.venv_win`** runs natively: CLIs, unit
   tests, doc truth, pre-commit, `omni-suite` orchestration.
2. Anything that **must cite validation evidence** for a scenario run goes
   through `.venv_ol` in WSL — no exceptions, because the dispatcher and the
   E2E parity harness are pinned there.
3. A red test on native Windows is **not** automatically "the known 63" — check
   the per-repo ledger (OPP#136 / ORF#94 / OL#202) before treating it as known.
