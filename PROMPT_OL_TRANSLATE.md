Fix OL translate_file: it should reject a NON-EXISTENT ORF input with the clean `ORF_INPUT_MISSING` error, but currently it succeeds.

## Symptom / repro
Scenario `scenarios/agent-surface/tool-ol-translate_file.yaml` step1:
- name: "translate_file with valid args returns the shipped clean ORF_INPUT_MISSING defect error"
- expect: `{'success': True, 'exit_code': 0, 'stdout_has': ['ORF_INPUT_MISSING', 'does not exist'], 'stdout_not_has': ['Traceback (most recent call last)']}`
- Actual: `{"success": true, "content": {"output_path": ..., "pipeline": "md", ...}}` — succeeds, no error.

So the test deliberately points translate_file at a non-existent ORF input and expects a clean `ORF_INPUT_MISSING` / "does not exist" error, but the OL code path returns success instead.

## Where to look
- `Omni_Localizer/src/ol_mcp/tools/translate_file.py` (or wherever `translate_file` / its ORF pre-check lives inside `Omni_Localizer/src`).
- Look for a pre-step that validates the ORF input path / skeleton exists and raises a typed `ORF_INPUT_MISSING` error. It either doesn't exist (missing guard) or its path-existence check is wrong (so a non-existent input passes).

## Requirement
Make translate_file return a clean `success:false` + `ORF_INPUT_MISSING` (message containing "does not exist") when the ORF input/skeleton it is told to use does not exist — WITHOUT a Python Traceback. Keep the happy path (real ORF input) working. Only touch OL code under `Omni_Localizer/src`. Do NOT change the real translate behaviour.

## Verify
After fixing, run the scenario and confirm it passes:
```
cd <e2e-test-suite> && export PYTHONPATH=Omni_Pre_Processor/src:Omni_Localizer/src:Omni_Re_Formatter/src .venv/bin/python scripts/validation/run_validation.py --scenario translate_file --scenarios-dir scenarios
```
(Or, if that's slow/needs MCP, directly invoke the translate_file function with a non-existent ORF path and assert it returns ORF_INPUT_MISSING, and with a real path that it still succeeds.)
Note: runs may touch external/tmp paths — if auto-rejected, tell me and I'll run the verification myself; still make the code fix and report the root cause + changed lines.
