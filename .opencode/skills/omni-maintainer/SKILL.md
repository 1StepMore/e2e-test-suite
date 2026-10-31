---
name: omni-maintainer
description: Maintain the Omni Suite ACROSS its three sub-repos (OPP/OL/ORF) — process cross-repo issues and PRs, run the full OPP→OL→ORF chain end to end, land per-repo PRs with honest evidence, and package deliveries. Use when the task spans repos or asks "处理 issue/PR"、"跑全链路/跨仓验证"、"出交付包"、"这个缺陷属于哪个仓"。
---

# Omni Suite — Maintainer (cross-repo orchestration)

The operating knowledge for maintaining the suite as a whole: the three
sub-repos are independent repos with their own CI, versions and policies;
this skill is how work moves across them without breaking the boundary.

## 1. Boundary first (read before anything else)

- This repo owns `Omni_Pre_Processor/`, `Omni_Localizer/`,
  `Omni_Re_Formatter/` (each has its own `.git/`). It does NOT own the
  sibling product repos (`AutoInfo`, `AutoMedia`) — a mention of them in
  this tree is a reference, never scope.
- A defect observed in another repo's surface is **filed as an issue in
  THIS repo** naming the owning repo + evidence (file:line, command,
  output) — never "fixed in passing" from here.
- Issues here may carry cross-repo references (e.g. "see AutoInfo's
  pattern") — those are inspiration, not acceptance criteria. The
  issue's own 验收 list is the contract.

## 2. Full-chain verification (OPP → OL → ORF)

Smoke/contract runs only (deterministic, zero cost):

```bash
export OMNI_TEST_FAKE_LLM=1
omni-suite pipeline <file> --dry-run      # print the 3 stages, no execution
omni-suite pipeline <file> --gates-only   # OPP + OL 8 gates + warnings, no ORF
```

Rules that make the difference between evidence and theater:

- FAKE_LLM output is **never** human-quality evidence — a fallback-active
  human-quality run reports `invalid` (see `scenarios/STANDARDS.md`).
- The nightly gap matrix runs BOTH channels (CLI + MCP) over the full
  format matrix: `python scripts/nightly_gap.py` (see `docs/NIGHTLY.md`
  for the two-verdict reading — `gap_units` decides, the regression guard
  does not). Verifier details: `scripts/format_matrix_verifier.py` (CLI
  channel) and `scripts/mcp_matrix_verifier.py` (MCP channel); both are
  direct-executable entry scripts as well as `scripts.*` package modules.
- Tier semantics: 1 = hermetic (no keys), 2 = real LLM keys, 3 = paid /
  network. `unconfigured` is a distinct status — never a pass.

## 3. Landing cross-repo changes

- One logical change = one branch + one PR **in the repo that owns the
  files** (sub-repos have their own remotes, CI, and merge conventions —
  merge commits there; suite PRs merge via the GitHub UI too).
- Every suite commit needs a DCO sign-off (`git commit -s`); the repo
  also requires the PR branch to be up to date with main before merge.
- Run the owning repo's own gates before pushing (pre-commit / lint /
  unit suite), and let its CI finish before merging — a red CI on main
  blocks every other PR.
- After merge: sync the local checkout (`git pull` in each sub-repo)
  before building anything that depends on the merged state.

## 4. Evidence & records (non-negotiable)

- Citable bar: `scenarios/STANDARDS.md`. Judge verdicts against its
  anchors; never invent thresholds.
- Every validation cycle leaves: run record (`validation-runs/`),
  LOOP-LOG event row (`docs/dev/validation-loop-log.md`), and — when
  delivering — the package under `04-Output/artifacts/deliverables/`
  (`python scripts/validation/make_delivery_package.py`).
- Throwaway drivers and evidence files go to
  `99-Tools/validation-scratch/omni-suite/` (workspace level), never /tmp
  for anything you want to cite later.
- Lint/claim verification must be reproducible: tool version + full
  command + raw output; "pre-existing N errors" must list rule codes and
  lines and confirm they sit on untouched lines.

## 5. Where the detail lives (do not memorize, point)

| Need | Source of truth |
|------|-----------------|
| Repo boundary & invariants | `AGENTS.md` (root) |
| MCP tool inventory / namespacing | `docs/agent-pipeline-guide.md` |
| Nightly matrix + gap math | `docs/NIGHTLY.md` |
| Validation loop governance | `docs/dev/validation-director-loop.md` + `docs/dev/validation-loop-log.md` |
| Known gaps & their history | `ACCEPTED_GAPS.md` |
| Handoff contract | `CONTRACT.md` |
