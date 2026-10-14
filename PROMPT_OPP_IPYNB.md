Fix the OPP ipynb extraction bug (OPP_BackUp#1).

## Symptom (reproduced)
`opp <fixture>.ipynb --target-format md --output-dir /tmp/oppd -v` fails:
```
[INFO] OPP CLI v0.1.0
[INFO] Processing 1 input(s)
[INFO] [1/1] Processing: .../sample.ipynb
[ERROR] .../sample.ipynb: Extraction failed: outputs
[INFO] Completed: 0 succeeded, 1 failed
exit=1
```
The `Extraction failed: {str(e)}` comes from `opp/pipeline.py` (~line 349), and `str(e) == "outputs"`. The manifest `outputs` construction is in `opp/commands/extract.py` (~line 239). The extractor `opp/extractors/ipynb.py` returns a normal `ExtractionResult` (paragraphs/tables/images) — so the error is in the pipeline/manifest consumer path, not the extractor itself.

Reproduce command (from repo root): `opp Omni_Pre_Processor/tests/fixtures/ipynb/sample.ipynb --target-format md --output-dir /tmp/oppd -v`
(Dispatch adds `Omni_Pre_Processor/src` to sys.path; run via the suite venv: use `python -c` with proper PYTHONPATH if `opp` console script isn't on PATH.)

## Fix requirement
Make `opp <ipynb> --target-format md` succeed: produce the markdown output AND the manifest (with `outputs`), exit 0. Keep other formats working. Only touch OPP code under `Omni_Pre_Processor/src/opp` (valid target: `commands/extract.py`, `pipeline.py`, or the consumer path that raises the `outputs` error). Do NOT touch the ipynb extractor's public output shape unless clearly wrong.

## Investigate then fix
1. Reproduce and read the traceback to find where `outputs` is raised as an exception (e.g. `KeyError`, a dict guard, or a consumer that expects the extractor result to carry an `outputs` key).
2. Fix the root cause (not a band-aid).
3. Verify: re-run the reproduce command — must print `[INFO] Completed: 1 succeeded` / exit 0 and produce `sample.md` + `sample_manifest.json` (with `outputs`).

## Report
- Exact root cause line
- What you changed
- The verification command output (must show success + manifest with outputs)