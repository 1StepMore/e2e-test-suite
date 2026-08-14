# Validation Director Loop — Omni Suite

The human-facing loop of the Omni Suite validation framework. The engine and
the scenario library are the machinery; this document is what a director does
with their output. If you are an agent reading this to validate, the six
per-agent adapters (`.opencode/skills/omni-validation/SKILL.md`,
`Omni_Localizer/src/.hermes/skills/omni-validation/SKILL.md`, the `CLAUDE.md`
and `.cursorrules` sections, and the "How to validate" sections of `AGENTS.md`)
each embed this loop in agent-specific form. The reference contract for every
mechanism named here is `docs/agent-tester-validation-guide.md`; the single
citable standards bar is `scenarios/STANDARDS.md`.

This file is a human loop, not an engine spec. It says nothing about how the
adapter executes a step; the adapters and the engine handle that. It describes
the 10-minute pass a director completes per run, and the flywheel that turns a
bug into a regression scenario that stays green forever.

## 1. The two-role model

The framework has exactly two roles (guide §1). The **validator agent**
executes scenarios, makes real calls against the shipped surface, collects
evidence, and drafts verdicts. The **director (human)** adjudicates those
verdicts, reads the artifacts, and signs off. The agent grades; the human
disposes. Anything the agent decides alone is a draft; anything the director
has not seen is not accepted.

| Role | Job |
|------|-----|
| validator agent | runs scenarios, records honest evidence, drafts verdicts, persists the run record |
| director (human) | reads verdicts, opens artifacts, triages blockers, records sign-off or returns findings |

Two states keep the loop honest (guide §1, §4):

- **GREEN** is the full chain: the call succeeded AND the artifact exists AND
  that artifact was shown to the director. A call that succeeded but whose
  artifact was never shown is not GREEN.
- **`unconfigured`** is a state, never a verdict of acceptance. A scenario
  that could not run because a prerequisite (for example a real LLM key) is
  missing reports `unconfigured` with its gating reason. It is never a silent
  skip and never a fake pass. A suite full of `unconfigured` rows is close to
  its pre-flight baseline: the honest RED state recorded before the
  environment was configured. Fix the environment and re-run; never paper
  over it.

## 2. Running a validation cycle

The cycle is: enumerate, run, lint, read, decide. All commands run from the
suite root with the suite venv active.

```bash
source .venv_ol/bin/activate
```

**Enumerate the library — no execution, no LLM:**

```bash
python scripts/validation/run_validation.py --list
```

**Run one hermetic scenario (tier 1 = no LLM keys needed):**

```bash
python scripts/validation/run_validation.py --scenario <name> --tier 1
```

`--scenario` is a case-insensitive substring match on the scenario **file
stem** (AutoInfo semantics). Real stems: `tool-`, `opp`, `orf-md`,
`orf-xliff`, `pipeline`, `regression`. The literal word `agent-surface` is NOT
a stem; running `--scenario agent-surface` matches nothing and exits 0 having
run zero scenarios. Use `--scenario tool- --tier 1` to select the 39
per-tool agent-surface scenarios.

Tiers (guide §1): 1 = hermetic, no keys; 2 = needs real LLM keys; 3 =
paid/external/network. A tier-2 scenario without keys reports `unconfigured`,
never a fake green.

**Contract-lint the library itself (falsifiable expects, no self-echo
PASS/FAIL, standard citations resolving to `scenarios/STANDARDS.md#<anchor>`):**

```bash
python scripts/validation/run_validation.py --check
```

Exit codes: 0 = no failures (`unconfigured`, `partial-pass`, `recovered`,
`passed` are not failures); 1 = any failed scenario, lint finding, or load
error.

**Read the latest run — `latest.txt` points at the newest run dir, the
director report turns it into decisions:**

```bash
cat validation-runs/latest.txt          # newest run dir, e.g. 20260814-200733
python scripts/validation/validation_report.py validation-runs/<ts>/scenarios.json
```

`validation_report.py` emits `report.md` + `report.json` in the same run
directory, rendering the two verdict families side by side (see §3). Read
`latest.txt` first to learn which `<ts>` to point the report at.

**Coverage audit — every live MCP tool must be exercised by a scenario:**

```bash
python scripts/validation/coverage_audit.py
```

This is the agent-satisfaction metric: `declared` (the LIVE module tool
registries, 39 tools at baseline) versus `scenario_used`. `missing` is a gap
an agent-user would hit blind and makes the audit exit 1; `phantom` coverage
never counts.

**Diff two runs — verdict changes + regression detection:**

```bash
python scripts/validation/validation_diff.py validation-runs/<older> validation-runs/<newer>
```

Any verdict change from passed-like to `failed` is a REGRESSION and makes the
diff exit 1. Trend tool on an established checkout, not a fresh clone;
`validation-runs/` is gitignored.

## 3. Reading the two-family report (D13)

The director report renders **two verdict families side by side**, one per
validation mission. Both headings always render, even when a family has zero
scenarios in the run (the report is honest about what was not exercised).

| Family | What it proves | Sources |
|--------|----------------|---------|
| **agent-user conformance** | every agent-facing surface works as an agent would use it: tool contract conformance, JSON parseability, error clarity, path security, exit codes | agent-surface scenarios (name prefix `tool-`) plus anything citing an AGENT-SURFACE standard anchor |
| **human-quality conformance** | the pipeline's output satisfies human end-users: LQA ≥ 4.0/5, paragraph ratio ±5%, CJK density < 5%, zero foreign punctuation, drawing count preserved, opens in python-docx | pipeline scenarios (name prefix `pipeline-`) plus anything citing a HUMAN-QUALITY standard anchor |

Read the report like this:

1. **The verdicts table** orients you: one row per scenario, what passed, what
   failed, what never ran.
2. **The executive summary** sizes the problem: totals for each family, plus
   how many regression scenarios failed.
3. **The regression failures** tell you whether a fixed bug came back. This is
   the signal that costs the most if missed; triage it first.
4. **The blockers** tell you what to do. Blockers are **findings only**: every
   failed scenario is a finding citing the standard it violated, with no fix
   suggestions, no "should change", no recommendations. The report is a
   witness, not a repairman. You route the finding yourself, which is what
   makes you understand it.
5. **The per-step trace** lets you verify: pick a step, find its `trace_id`,
   open its artifact.

Every step renders the six-field evidence line (D12):
`checked {surface} against {standard} → {actual}` — the five-part evidence
contract (surface / real call / expect / actual / artifact-to-show) plus the
`standard` citation.

`unconfigured` renders as a distinct status with its `missing_env` shown —
never GREEN, never RED-as-failure, never in blockers.

## 4. The 10-minute director checklist

The canonical checklist is ported verbatim from the reference guide §6.6,
then extended with the per-run **standards conformance** pass (D12) that
ticks each STANDARDS.md family explicitly.

### 4.1 The canonical 10-minute review (guide §6.6, verbatim)

Ten checks, roughly in the order that costs the least time first. If a check
passes, move on; if it fails, that is your work item. Nothing here asks you to
run tooling; you read, you confirm, you decide.

1. **Verdicts table scanned.** Any unexpected FAIL, or any PASS where you
 expected RISK? Read the table top to bottom once, fast.
2. **Regression failures empty.** If not, each one is a re-opened bug; triage
 them first, before any other finding.
3. **Blockers read and assigned.** Every blocker went back to the agent as a
 finding, with an owner. A blocker with no owner is a blocker that will
 recur.
4. **Artifacts spot-checked.** Opened the artifacts of one or two thin-looking
 steps and confirmed they are real, not stubs or local-only sinks, and that
 their content matches the `expect`.
5. **unconfigured rows explained.** For each one, the gate reason (missing env
 var, unreachable endpoint) confirmed against the current environment, and a
 re-run scheduled once configured.
6. **RISK rows inspected.** Every RISK verdict's artifacts reviewed before you
 consider sign-off, so no footnote reaches acceptance unseen.
7. **Totals cross-checked.** The executive summary's counts match the verdicts
 table, with nothing counted as a pass that was not one. Discrepancies here
 mean the report itself is unreliable.
8. **Trace skimmed.** Per-step trace scanned for absurd durations or missing
 `trace_id`s, either of which marks a step worth opening directly.
9. **Run record confirmed.** The run is persisted, and the pointer names it, or
 the archive copy exists. A run you cannot find later is a run you cannot
 cite.
10. **Loop closed.** Sign-off recorded, or the findings returned for rework.
 Nothing left pending.

Ten minutes, one pass, and the run is either accepted or back in the agent's
hands. That is the whole director loop: read, verify, dispose.

### 4.2 Standards conformance pass (D12 extension)

Per run, tick each STANDARDS.md family explicitly. A tick means: at least one
scenario in this run exercised the bar, the step's evidence line
(`checked {surface} against {standard} → {actual}`) matches the cited
threshold, and you confirmed it. A bar with no scenario in the run is a gap to
note, not a silent pass. The anchors below are the citable ids from
`scenarios/STANDARDS.md`.

**AGENT-SURFACE family** (mission axis 1 — agent-user conformance):

- [ ] Tool contract conformance — `standard: STANDARDS.md#tool-contract`
  (schema-shaped params accepted, structured result with expected keys).
- [ ] JSON parseability — `standard: STANDARDS.md#json-parseable`
  (every tool result and CLI JSON output parses as valid JSON).
- [ ] Error clarity — `standard: STANDARDS.md#error-clarity`
  (clear parseable error naming tool + offending parameter; no stack-trace
  soup).
- [ ] Path security — `standard: STANDARDS.md#path-security`
  (out-of-allowlist paths denied; OPP fail-closed).
- [ ] Exit codes — `standard: STANDARDS.md#exit-codes`
  (0 on success, nonzero with reason on stderr on failure; includes the T2
  PDF→XLIFF guard contract).

**HUMAN-QUALITY family** (mission axis 2 — human-result quality):

- [ ] LQA threshold — `standard: STANDARDS.md#lqa-threshold`
  (average LLM-judged score ≥ 4.0/5).
- [ ] Paragraph ratio — `standard: STANDARDS.md#para-ratio`
  (out_n / src_n in [0.95, 1.05]).
- [ ] CJK density — `standard: STANDARDS.md#cjk-density`
  (CJK character ratio < 5% in the target-language output).
- [ ] Punctuation hygiene — `standard: STANDARDS.md#punct-hygiene`
  (zero foreign-language punctuation per target language).
- [ ] Drawing count — `standard: STANDARDS.md#drawing-count`
  (output drawing count equals source, both > 0).
- [ ] Opens in python-docx — `standard: STANDARDS.md#opens-docx`
  (output DOCX opens with ≥ 1 paragraph).

## 5. Bug → regression-scenario flywheel

Every bug fixed MUST be locked by a regression scenario that stays green
forever. The flywheel has four steps.

1. **Report the bug.** `.github/ISSUE_TEMPLATE/bug_report.md` carries a
   mandatory regression-scenario field in its Fix status checklist:
   `- [ ] **Regression scenario:** will you add a
   \`scenarios/regression/<bug>.yaml\` locking this fix? (required for merge)`.
   A bug without that checkbox ticked is not merged.
2. **Prove it RED.** Write `scenarios/regression/<bug>.yaml` with
   `regression: true` and `regression_issue: "<bug reference>"`, one or more
   steps whose `expect` asserts the CORRECT behavior. First run is expected
   RED: the bug is live. Record that RED as the baseline before any fix.
3. **Fix via the normal fix cycle.** The failing scenario is the defect proof;
   the product fix is made in the owning module. The scenario is the contract
   the fix must turn GREEN.
4. **Stay GREEN forever.** Re-run the scenario after the fix. A GREEN
   regression scenario pins the fix; a future RED on it means the bug came
   back, and the report flags it as a regression failure with the issue
   reference attached.

**The T2 seed — the framework's first flywheel catch.** The seed scenario
`scenarios/regression/t2-pdf-xliff-guard.yaml` pins the OPP PDF→XLIFF guard
(D5): `opp sample.pdf --target-format xlf --source-lang en --target-lang zh`
must exit 1 with `XLIFF not supported for PDF format` on stderr
(`opp/pipeline.py:131`, cited as `standard: STANDARDS.md#exit-codes`). It was
committed RED: on the live CLI path the guard was dead (the PDF2HTML
extractor relabeled `format_type` to `"html"`, and the A6 cache could replay a
pre-guard `.xlf`), even though the unit test passed — unit GREEN /
integration RED, exactly the drift class the flywheel exists to catch. The
subsequent fix cycle (three-layer: format-relabel restored, failure reason
printed to stderr, guard fired before the cache check) turned the scenario
GREEN. That cycle is the template every future bug follows: report, prove RED,
fix, pin GREEN.

---

**References.** Guide: `docs/agent-tester-validation-guide.md` (§1 two-role
model, §4 honesty rules, §5 coverage/regression, §6 director loop).
Standards: `scenarios/STANDARDS.md` (the two families and every citable
anchor). Engine: `omni_mcp/validation/` + `scripts/validation/`. Bug intake:
`.github/ISSUE_TEMPLATE/bug_report.md`. Per-agent adapters list the same loop
in agent-specific form.
