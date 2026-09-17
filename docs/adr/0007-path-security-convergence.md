# ADR 0007 — Path-Security Validation: Converge the Three Copies Now, Defer the Shared Package

**Status**: Accepted (Phase 1 implemented 2026-09-17; Phase 2 deferred — see
"Implementation" below)

**Date**: 2026-09-17

## Context

Path security (traversal, symlink escape, system-directory blocking, extension
whitelist/blacklist, size, directory containment) is implemented in four validator
files across the three sub-repos, plus a fifth, partial copy in the suite layer —
`omni_mcp/orchestrator.py`, which starts the module CLIs directly and therefore
never reaches a sub-module `PathValidator`. They are not independent *policies* by
design — they are copies of one policy that have drifted apart. A security fix
applied to one copy does not propagate to the others.

### The files (verified 2026-09-17)

| Layer | File | Lines | Role |
|---|---|---|---|
| OPP shared core | `Omni_Pre_Processor/src/opp/utils/security.py` | 169 | Function API `validate_path(path_str, allowed_dirs, max_file_size_bytes=None, allow_missing=False) -> Path`; raises `PathValidationError`. Owns `SYSTEM_DIRS` / `BLOCKED_EXTENSIONS`. |
| OPP MCP wrapper | `Omni_Pre_Processor/src/opp/mcp/security.py` | 137 | `PathValidator.validate_path()` calls the shared core (`_shared_validate`, L104-109) for Phase 1, then applies the OPP extension whitelist (L124). **Already the target layering.** |
| OL standalone | `Omni_Localizer/src/ol_mcp/security.py` | 250 | Self-contained `PathValidator`; its own module header (L2-3) says it "Mirrors ``orf/mcp/security.py:PathValidator``". |
| ORF standalone | `Omni_Re_Formatter/src/orf/mcp/security.py` | 227 | Self-contained `PathValidator`. |
| Suite orchestrator | `omni_mcp/orchestrator.py` | 400+ | Not a `PathValidator` and never reaches one: it enforces its own copy of the *policy* (fail-CLOSED allowlist containment + `SYSTEM_DIRS` + `BLOCKED_EXTENSIONS`, L97-119, `_path_denial_message`). No extension whitelist, no size cap. |

OL and ORF are the real duplicates. OPP is already split into a shared core plus a
thin MCP wrapper that only adds its extension whitelist — that is the shape the
other two should adopt. The orchestrator copy exists because the suite drives the
CLIs instead of chaining MCP servers; it is the outermost entry point, so a gap
there silently defeats all three module validators.

### Verified policy drift

| Constant | OPP core | OL | ORF | Drift |
|---|---|---|---|---|
| `SYSTEM_DIRS` | 9 entries (`/etc`, `/usr`, `/var`, `/proc`, `/sys`, `/System`, `/Library`, `/C:/Windows`, `C:\Windows`) — `opp/utils/security.py:24-34` | **6** (missing `/proc`, `/sys`, `/C:/Windows`) — `ol_mcp/security.py:20-27` | **7** (missing `/proc`, `/sys`) — `orf/mcp/security.py:8-16` | ️ OL and ORF do **not** block `/proc` or `/sys`; OL also misses the forward-slash Windows form |
| `BLOCKED_EXTENSIONS` | 7 — `opp/utils/security.py:37-45` | 7 — `ol_mcp/security.py:30-38` | 7 — `orf/mcp/security.py:19-28` | identical today, but nothing keeps it that way |
| `ALLOWED_EXTENSIONS` | 16 (OPP) — `opp/mcp/security.py:62-66` | 7 — `ol_mcp/security.py:76` | 21 — `orf/mcp/security.py:66-70` | **Intentional** — each module advertises different formats |

The `ALLOWED_EXTENSIONS` split is legitimate (OPP ingests documents, OL ingests
glossaries/TMX/XLIFF/MD, ORF emits 16 output formats). The `SYSTEM_DIRS` /
`BLOCKED_EXTENSIONS` split is not: those are security boundaries that must be
identical everywhere. `/proc` in particular exposes `/proc/self/environ`.

A second, quieter divergence: the legacy class-level `validate()` in OPP
(`opp/mcp/security.py:157`) and ORF (`orf/mcp/security.py:254`) reads the **class
constant** `PathValidator.ALLOWED_EXTENSIONS`, while their `validate_path()` reads
the instance's env-overridden set. So `MCP_ALLOWED_EXTENSIONS` silently does not
apply on the legacy path. OL has no legacy `validate()`.

A third, more severe divergence is structural rather than textual: the suite
orchestrator (`omni_mcp/orchestrator.py`) had **no** `SYSTEM_DIRS` and **no**
`BLOCKED_EXTENSIONS` at all — it checked the allowlist and nothing else — so a
mis-scoped allowlist there bypassed both blacklists entirely, and being the
outermost entry point it did so in front of all three module validators (closed in
Step 3b below).

### Packaging facts that constrain the fix

- The three sub-repos are three separate distributions: `omni-pre-processor`
  (hatch wheel packages `src/opp`), `omni-localizer` (setuptools, `src` layout),
  `omni-re-formatter` (hatch wheel packages `src/orf`). They are regular
  directories with their own git repos, joined only by the root
  `[tool.uv.workspace].members`.
- **Neither OL nor ORF declares a dependency on OPP.** A shared package therefore
  requires a new dependency declaration in two `pyproject.toml` files (or a fourth
  workspace member), and *any* of those invalidates `uv.lock`.
- Relocking is not possible from this development environment: the workspace index
  configured in the lock (`https://pypi.tuna.tsinghua.edu.cn/simple`) returns
  **HTTP 403** for every path from WSL (`/simple/`, `/simple/ruff/`,
  `/simple/structlog/` all 403; `pypi.org` returns 200 but switching indexes would
  rewrite every registry URL in the lock). A hand-edited or stale lock would then
  break every CI job that runs `uv sync --locked`.

## Decision

**Two phases. Phase 1 lands now; Phase 2 is deferred until a lock regeneration is
possible.**

### Phase 1 — converge the shared security core and make drift impossible (no packaging change)

1. **Align the restrictive constants.** Add `/proc`, `/sys` and the
   `/C:/Windows` form to OL's `SYSTEM_DIRS`, and `/proc`, `/sys` to ORF's, so all
   three equal the OPP canonical set. Strictly additive (more restrictive), so no
   previously-rejected path becomes accepted.
2. **Fix the legacy `validate()` env-override bug** in OPP and ORF so the class
   method honours `MCP_ALLOWED_EXTENSIONS` exactly as `validate_path()` does.
3. **Add a parity invariant** — this is the part that actually stops the drift,
   and it follows the repo's existing "Invariant Convergence: Layer 1" convention
   (`.pre-commit-config.yaml:35-38`):
   - a canonical constants module (single source of truth for
     `SYSTEM_DIRS` / `BLOCKED_EXTENSIONS`), plus
   - a shared test-vector table (one YAML/JSON list of `(path, allowed_dirs,
     expected_verdict)` cases for the *shared* rules only), and
   - a checker that runs every vector against all four implementations and fails if
     any verdict differs, or if any copy's constants deviate from canonical.
   Wired into pre-commit + the `lint.yml` changed-file gate so a fix that lands in
   one copy cannot go green while the others stay stale.

### Phase 2 — extract `omni_security` (deferred, gated on relocking)

1. Create a fourth workspace member `omni-security` holding the shared core;
   add it to `[tool.uv.workspace].members` and to OL's and ORF's
   `dependencies`.
2. Rewrite the three `PathValidator`s as thin wrappers that pass their own
   `ALLOWED_EXTENSIONS` into the shared core — exactly the shape OPP already has.
3. Regenerate `uv.lock`, run all three sub-repo suites plus the parity invariant.
4. Retire the per-copy `SYSTEM_DIRS` / `BLOCKED_EXTENSIONS` and downgrade the
   parity checker to a regression test.

## Implementation — Phase 1 (landed 2026-09-17)

All three Phase 1 steps are implemented and gate-enforced. Verification evidence:
`docs/project-health-report-2026-09-17.md` §十一.

### Step 1 — constants aligned

| Copy | File | Change |
|---|---|---|
| OPP core | `Omni_Pre_Processor/src/opp/utils/security.py` | already canonical (9 `SYSTEM_DIRS`, 7 `BLOCKED_EXTENSIONS`) — unchanged |
| OL | `Omni_Localizer/src/ol_mcp/security.py` | `SYSTEM_DIRS` 6 → **9** (added `/proc`, `/sys`, `/C:/Windows`); the extension accessor also converged on one leading-dot convention |
| ORF | `Omni_Re_Formatter/src/orf/mcp/security.py` | `SYSTEM_DIRS` 7 → **9** (added `/proc`, `/sys`, `/C:/Windows`) |

Purely additive, i.e. strictly more restrictive: no path that used to be accepted
is accepted now, only some that used to slip through are blocked.

### Step 2 — legacy `validate()` env-override bug closed

OPP (`opp/mcp/security.py`) and ORF (`orf/mcp/security.py`) legacy `validate()`
now resolve the extension set through the same env-aware helper as
`validate_path()` (`resolve_allowed_extensions()`), so `MCP_ALLOWED_EXTENSIONS`
applies on both entry points. Regression coverage:
`TestLegacyValidateHonoursEnv` in the parity test.

### Step 3 — parity invariant (canonical location deviates from this ADR, on purpose)

Implemented as **one** test module rather than a canonical module + a YAML/JSON
vector table:

- `tests/security/test_path_policy_parity.py` — holds `CANONICAL_SYSTEM_DIRS`,
  `CANONICAL_BLOCKED_EXTENSIONS` (the frozen source of truth), `SHARED_VECTORS`
  (the shared behavioural vector table), a `_Copy` adapter that normalises the two
  different failure APIs (OPP raises `PathValidationError`; OL/ORF return
  `ValidationResult(success=False)`), and the three checkers: canonical constants,
  shared-vector verdicts, env override / legacy `validate()` / allowlist parsing.

**Why the deviation**: a canonical *runtime* module would have to live in the
suite (`omni_mcp/…`) and be imported by three sub-repos that do not declare a
dependency on it — the same undeclared-dependency objection that rules out
Alternative 3, and the same `uv.lock` constraint that defers Phase 2. Keeping the
frozen values inside the gate gives the required property ("a fix landing in one
copy cannot go green while the others stay stale") without adding any runtime
import edge. The vector table is Python rather than YAML for the same reason: it
needs no new loader.

Wiring (both halves, per this ADR):

- local: pre-commit hook `omni-path-policy-parity`
  (`.pre-commit-config.yaml`), scoped to the policy surface.
- CI: `lint.yml` step *"Blocking: path-security parity (every copy, one policy)"*
  (ADR 0007 Phase 1 step 3), changed-file scoped like every other gate in that
  job. The step was named "three copies" until the suite orchestrator was folded
  into the same invariant (below).

### Step 3b — the suite orchestrator aligned to the same policy (2026-09-17)

`omni_mcp/orchestrator.py` was the fourth copy of the policy and the weakest one:
it enforced only the fail-CLOSED allowlist containment check, so **neither**
`SYSTEM_DIRS` nor `BLOCKED_EXTENSIONS` blocked anything on the outermost entry
point — an allowlist configured at a directory root would happily hand
`/etc/passwd` (or any `.exe`) to the OPP/OL/ORF subprocesses. Since the
orchestrator never calls a sub-module `PathValidator`, the three module copies
could not compensate.

Fixed without adding a runtime import edge (`omni_mcp` must not import the
sub-repos — see "Why the deviation" above):

- `SYSTEM_DIRS` / `BLOCKED_EXTENSIONS` added to `omni_mcp/orchestrator.py` as a
  local copy of the canonical values (same constraint as OL/ORF);
- `_system_dir_denial()` replicates the modules' algorithm exactly — `Path.parts`
  prefix comparison, no "improvement";
- `_path_denial_message()` now checks, in order: allowlist precondition (fail
  CLOSED) → system directory → blocked extension → allowlist containment;
- the module docstring's "accepts arbitrary `file_path` values without path
  validation" claim was stale and is replaced with what the code actually does,
  including the three things it deliberately does *not* replicate (per-module
  extension whitelist, size cap, explicit symlink re-check).

Gate extension: the same module now asserts the orchestrator's constants equal
canonical, runs `ORCHESTRATOR_POLICY_VECTORS` (the shared vector table minus the
existence vector — the orchestrator reports a missing source as `FILE_NOT_FOUND`
after the policy gate, and collapsing that into `OMNI_PATH_DENIED` would be a
behaviour regression), adds a platform-conditional system-directory vector, and
includes the orchestrator's allowlist parser in `TestAllowlistParsingParity`.
Contract `tests/security/test_omni_mcp_path_denied.py` (5 cases) is unchanged and
still green.

### Same-family defects found and fixed while implementing Phase 1

The audit for step 3 exposed four more instances of the same root cause — POSIX
literals / single-separator assumptions applied to a platform-dependent path
problem. They are fixed here because leaving them would have made the new gate
misleading (a "one policy" claim on top of five divergent allowlist parsers).

| # | Defect | Sites | Fix |
|---|---|---|---|
| D-3 | allowlist split on `":"` in the suite orchestrator | `omni_mcp/orchestrator.py` `_split_allowlist` | split on `os.pathsep` + comma |
| D-4 | allowlist parser **preferred `":"`** on every platform | `opp/mcp/config.py`, `orf/mcp/config.py` (`_parse_allowed_dirs`), `ol_mcp/security.py` (new module-level `_parse_allowed_dirs`) | split on `os.pathsep` + comma; the three parsers are now pinned by `TestAllowlistParsingParity`. On Windows the documented `C:\docs;C:\out` form had been **silently and totally broken** (drive-letter colon split each path) |
| D-5 | `--resource-dir` guard used `Path("/tmp")` and comma-only parsing | `opp/cli.py` | `tempfile.gettempdir()` + reuse the MCP parser, so the CLI entry point is not a fourth divergent parser |
| D-6 | shutdown-cleanup root guard compared `str(resolved) == "/"` | `opp/mcp/common.py` `_cleanup_resource_dir` | compare against `Path.anchor` (POSIX `/`, Windows `D:\`); also moved the counting `rglob` inside the `try`, since any `OSError` there escaped the shutdown hook |

### Residual differences (documented, not hidden)

- `Omni_Localizer/src/cli/load_glossary.py` is a **fourth** allowlist parse (comma
  only) on the OL *CLI* surface, and it fails **open** (`cwd` + `/tmp` fallback).
  It is outside the MCP policy surface this ADR converges and is not covered by the
  parity gate; it should be folded into the same helper when that surface is next
  touched.
- The algorithm itself is still duplicated four times (the three validators plus
  the orchestrator's partial copy) — that is Phase 2.

## Rationale

- Phase 1 removes the *security* half of the problem today, at low risk, without
  touching dependency topology. The two constants that must not drift become
  gate-enforced rather than convention-enforced.
- Phase 1 is also the prerequisite for Phase 2: once the vectors exist, the thin
  wrappers of Phase 2 can be verified against the same table.
- Deferring Phase 2 costs little *because* Phase 1's invariant catches drift in
  the meantime — the failure mode becomes a red gate instead of a silent gap.

## Alternatives Considered

1. **Full shared package now (Phase 2 only).** Blocked: it invalidates `uv.lock`
   and this environment cannot relock (403 from the workspace index), so the repo
   would ship a broken `uv sync --locked` for every CI job. It also changes the
   dependency graph of two independently released sub-repos in one step.
2. **Do nothing / defer entirely (the ADR-0001 pattern).** Rejected: unlike the
   CLI-framework split, this one is a security boundary. `/proc` and `/sys` are
   verifiably unblocked in OL and ORF today — that is a live divergence, not a
   cosmetic one.
3. **Have OL and ORF import `opp.utils.security` without declaring a dependency.**
   Rejected: works only inside this workspace (where OPP happens to be installed);
   an independent `pip install omni-localizer` would break at import time. It
   trades a documented duplication for an undeclared dependency.
4. **Vendor the core into each repo and compare files byte-for-byte.** Rejected as
   the sole mechanism: textual comparison is brittle against formatting churn and
   still allows semantically different code that formats identically. Behavioural
   vectors (Phase 1 step 3) are the real invariant; the constants check is a cheap
   complement.

## Consequences

**Positive**

- The security-relevant constants become identical across all four copies and
  are gate-enforced, so a partial fix now fails CI instead of shipping.
- The legacy `validate()` env-override bug is closed in two modules, and the
  suite orchestrator no longer waves system directories / executables through.
- Phase 2 becomes a mechanical refactor with a ready-made verification table.

**Negative / residual**

- Duplication of the *algorithm* remains until Phase 2; four places still have to
  be edited in lockstep (the invariant only detects drift, it does not prevent it).
- The parity checker adds a new gate that must be maintained and kept in sync with
  the canonical constant list.
- Phase 2 stays blocked until the lock can be regenerated against the workspace
  index; that dependency is environmental, not technical.

## Future Plan (NOT in scope of Phase 1)

1. Relock against a reachable index (CI side or a configured mirror) and confirm
   `uv sync --locked` stays green.
2. Extract `omni-security` as a workspace member; declare it in OL and ORF.
3. Convert the three validators to thin wrappers; delete the duplicated
   `SYSTEM_DIRS` / `BLOCKED_EXTENSIONS`.
4. Re-run the parity vectors as a regression test; then narrow the checker to the
   per-module extension whitelists only.

## Related

- `docs/project-health-report-2026-09-17.md` §五 risk #2 (trigger for this ADR)
- ADR 0002 — Three Independent Modules, Not a Monolith (why there is no shared library today)
- ADR 0001 — CLI Framework: Defer Unification (the deferral precedent)
- `docs/SECURITY.md` (PathValidator is part of the documented security model)
- `.pre-commit-config.yaml:35-38` (Invariant Convergence convention this ADR follows)
- `docs/dev/validation-director-loop.md` + `scenarios/STANDARDS.md` (where the parity vector table should be registered)

---

*Authored 2026-09-17 from a verified audit of the four files; every constant and
line reference above was read from the working tree, not quoted from docs.*
