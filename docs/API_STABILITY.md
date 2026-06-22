# Omni Suite — API Stability Policy

> **Audience**: developers and integrators of the Omni Suite who depend on
> OPP/OL/ORF CLI flags, MCP tools, or artifact formats. Also for maintainers
> who need to know what is and isn't safe to change.
>
> **Scope**: cross-module stability contract. This document supersedes
> per-module ad-hoc stability claims. If they conflict, this file wins.
>
> **Companion doc**: `docs/ARCHITECTURE.md` for the pipeline and module
> boundaries; `VERSION_COMPATIBILITY.md` for tested version combinations.

---

## 1. Commitment in one sentence

**We follow SemVer (https://semver.org/) per module, with a written
deprecation policy and a contract test suite that fails CI on any
backward-incompatible change to the public surface.**

Each of OPP, OL, ORF is its own SemVer stream. Compatibility across the
three is recorded in `VERSION_COMPATIBILITY.md` and verified by
`tests/integration/test_version_compat.py`.

---

## 2. Per-Module SemVer Commitment

| Module | Current version | Package name | Import name | Bumped by |
|--------|-----------------|--------------|-------------|-----------|
| OPP | 0.6.1 | `omni-pre-processor` (PyPI) | `opp` | `scripts/bumpversion.py` |
| OL | 0.4.4 | `omni-localizer` | `ol` | `scripts/bumpversion.py` |
| ORF | 0.4.3 | `omni-re-formatter` | `orf` | `scripts/bumpversion.py` |
| omni-suite | 0.2.0 | (root workspace) | `omni_suite` | manual, per release |

### 2.1 What bumps each level

| Bump | When | Examples |
|------|------|----------|
| **Patch** (`0.6.1` → `0.6.2`) | Backward-compatible bug fix or perf improvement that does not change a public interface. | `orf apply-md` no longer crashes on a missing `images` argument (was: NameError). |
| **Minor** (`0.6.x` → `0.7.0`) | New public API, new CLI flag, new MCP tool, new optional field in `manifest.json` (with a default), or deprecation notice on an existing API. | Add `orf apply-md --reference-doc` flag. Add `batch_translate_texts` MCP tool to OL. |
| **Major** (`0.x.y` → `1.0.0`) | Any backward-incompatible change to the public surface. | Remove a CLI flag. Rename an MCP tool. Change a required `manifest.json` field. Change a CLI exit code. |

### 2.2 Module maturity

- **OPP** is on its 0.6.x line. The CLI surface and the 7 MCP tools are
  stable enough to be treated as 1.0 candidates. We will bump to 1.0
  when we have completed Phase 4 observability work and have a clean
  security audit.
- **OL** is on 0.4.x. The text-in/text-out MCP tool set is stable; the
  file-based CLI is stable.
- **ORF** is on 0.4.x. The 6 MCP tools and the `apply-md`/`apply-xliff`
  CLIs are stable.

Until each module reaches 1.0, a minor bump **may** contain a
backward-incompatible change if it is justified in
`Omni_<Module>/CHANGELOG.md` and `VERSION_COMPATIBILITY.md` is updated
in the same release. This exception will be removed when each module
hits 1.0.

### 2.3 Coordinated release procedure

When releasing a new version combination:

1. `bash scripts/bumpversion.py {patch|minor|major}` updates the three
   `pyproject.toml` files atomically. The script refuses to bump if any
   module's working tree is dirty.
2. Update `VERSION_COMPATIBILITY.md` with a new row (or mark an existing
   row as the current baseline).
3. Run `pytest tests/integration/test_version_compat.py` — must pass for
   the new combination.
4. Run `pre-commit run --all-files` — `omni-contract-smoke` is a
   manual stage; run it explicitly (`pre-commit run
   omni-contract-smoke --all-files`) before tagging.
5. Tag and push the three sub-repo commits plus the parent `VERSION`
   bump in one logical release.

This procedure is the same as the one documented in
`.omo/plans/2026-06-22-production-readiness-plan.md` § 13.3.

---

## 3. Public vs Private API Surface

The rule is simple: **public surface is everything we promise not to
break under SemVer; private surface is everything else, including
implementation details even if they are importable today.**

### 3.1 Public surface (stable)

| Surface | Examples | Where it is defined |
|---------|----------|---------------------|
| **CLI commands & flags** | `opp --target-format=md <file>`, `ol translate-md <file> -s en -t zh -o <dir>`, `orf apply-md <file> --target-format docx -o <out>` | `Omni_<Module>/src/<pkg>/cli.py` (per subcommand) |
| **Exit codes** | `0` ok, non-zero error (see `docs/ERROR_CODES.md` for the full table) | Per-module `cli.py` |
| **MCP tool names** | `extract_document`, `translate_md_text`, `apply_md`, `apply_xliff`, etc. (7 + 8 + 6 = 21 tools) | `Omni_<Module>/src/<pkg>/mcp/server.py` `_TOOL_SCHEMAS` / `@server.list_tools()` |
| **MCP tool input schemas** | Required and optional parameters, types, defaults | Same location as above |
| **MCP tool output schemas** | Structured JSON payloads returned via `TextContent` | Same location |
| **Artifact filenames** | `document.md`, `document.xlf`, `document_manifest.json`, `document.skeleton.zip`, `images.json` | OPP `cli.py` writers |
| **`manifest.json` schema** | Required keys, types, `manifest_version` | OPP `cli.py:392-457` |
| **`skeleton.zip` key-files list** | For DOCX: `word/document.xml`, `word/styles.xml`, `word/numbering.xml`, `word/settings.xml`, `[Content_Types].xml`. For PPTX: all `ppt/*`. | OPP `cli.py` |
| **ORF output-format whitelist** | The 16 formats `apply-md` accepts | ORF `cli.py` / `security.py` |
| **Environment variables** | `OMNI_TEST_FAKE_LLM=1`, `OMNI_TEST_FAKE_PANDOC=1`, `OPP_MCP_ALLOWED_DIRS`, `OL_CONFIG_PATH`, `ORF_MCP_ALLOWED_DIRS`, `MCP_SHARED_SECRET` | Per-module `mcp/config.py` |
| **Package names & import names** | `pip install omni-pre-processor` (imports as `opp`), `pip install omni-localizer`, `pip install omni-re-formatter` | Per-module `pyproject.toml` |

### 3.2 Private surface (may change without notice)

| Surface | Why it's private |
|---------|------------------|
| Internal Python module structure (e.g. `opp.extractors._internal_helpers`) | Implementation detail; we reserve the right to refactor. |
| Logger names, log message format (until structlog migration lands in Phase 4) | Not yet part of the contract. |
| Internal CLI subcommands not in the public list above | Will be promoted to public if they are kept. |
| `manifest.json` fields under `extraction.warnings` content | Shape may grow; consumers must tolerate unknown keys (see § 5 contract). |
| `images.json` fields beyond the documented floating-image fields | Internal to OPP/ORF coordination. |
| Process-internal state (config singletons, validator instances) | Not a public API. |
| Test fixtures in `tests/fixtures/` and per-module test corpora | Not a public API. |
| Anything prefixed with `_` | Python convention; private by name. |

**Rule of thumb for integrators**: if it is not in the table above and not
documented in a per-module `README.md`, treat it as private. Open an issue
if you need it promoted to public.

---

## 4. Deprecation Policy

We use the standard **warn → 2 minor versions → remove** cycle.

### 4.1 The cycle

| Step | What happens | Timeline (relative to the deprecation notice) |
|------|--------------|-----------------------------------------------|
| 1. **Deprecate** | Mark the API as deprecated in code AND in docs. Emit a `DeprecationWarning` (CLI) or return a `deprecation` field in the MCP response. Add an entry to `Omni_<Module>/CHANGELOG.md` under a "Deprecated" heading. | T = 0 |
| 2. **Warn in minor #1** | The deprecated API still works. Every release notes the deprecation in `CHANGELOG.md` and `VERSION_COMPATIBILITY.md` (if the new combination includes the deprecation). | T = 0 to T = minor +1 |
| 3. **Warn in minor #2** | Same as above. By this point the deprecation has been visible in two released minor versions. | T = minor +1 to T = minor +2 |
| 4. **Remove** | The API is deleted in the next major version (or, pre-1.0, the next minor — see § 2.2). `CHANGELOG.md` notes the removal under "Breaking changes". | T ≥ minor +2 |

### 4.2 What "warn" looks like

- **CLI**: a one-line warning to stderr, prefixed with the module name
  and the deprecation target version, e.g.
  ```
  opp: WARNING: --legacy-format is deprecated and will be removed in opp 1.2.0. Use --target-format=md instead.
  ```
- **MCP tool**: the response payload includes a `deprecation` field
  alongside the normal return value:
  ```json
  {
    "success": true,
    "result": { ... },
    "deprecation": {
      "tool": "extract_document",
      "removal_version": "1.2.0",
      "replacement": "Use 'generate_markdown' for MD-only output."
    }
  }
  ```
- **Manifest / artifact fields**: a `deprecated` flag in
  `manifest.json` and a `CHANGELOG.md` note. Existing consumers that
  ignore unknown keys keep working.

### 4.3 Exceptions

Three cases skip the full cycle:

1. **Security**: an API that is a proven security hole can be removed in
   the next release with a same-day `CHANGELOG.md` security advisory. The
   fix is documented in `docs/SECURITY.md`.
2. **Bug fix that is not API-breaking for the documented happy path**:
   no deprecation needed; this is a patch bump. Example: fixing a crash
   on an edge case is not "removing" the API.
3. **Internal / private surface** (see § 3.2): can be removed or
   reshaped in any release, including patches. No deprecation warning
   is required.

### 4.4 Deprecations currently in effect

As of 2026-06-22: **none**. The first candidate is the
`OPP_ALLOWED_DIRECTORIES` env-var name from the legacy OPP MCP server
(the rewrite uses `OPP_MCP_ALLOWED_DIRS`). This is on the deprecation
track but has not been formally announced yet — see
`.omo/plans/2026-06-22-production-readiness-plan.md` § 7.4 for the
deferred P1-11 work item.

---

## 5. Contract Test Strategy

Contract tests are the executable form of this policy. They live in
`tests/contract/` (planned, Phase 4 P1-12) and `tests/integration/`.

### 5.1 The five contract surfaces

| # | Surface | What we freeze | Test file |
|---|---------|----------------|-----------|
| 1 | **CLI flags & help text** | `--help` output is byte-stable per module version. Adding a flag is a minor bump. Removing one is a major. | `tests/contract/test_cli_help_contract.py` |
| 2 | **MCP tool list & schemas** | `server.list_tools()` output is byte-stable. New tools are minor; renames/removals are major. | `tests/contract/test_mcp_schema_contract.py` |
| 3 | **MCP tool I/O** | For each tool, the structured response shape (keys, types, success/error envelope) is frozen. | `tests/contract/test_mcp_io_contract.py` |
| 4 | **Artifact format** | `manifest.json` schema (required keys, types), `skeleton.zip` key-files list, `images.json` floating-image keys. | `tests/contract/test_artifact_contract.py` |
| 5 | **Cross-version pipeline** | A pinned (opp, ol, orf) combination runs end-to-end on a minimal DOCX and produces a valid result. | `tests/integration/test_version_compat.py` |

### 5.2 What "byte-stable" means in practice

- **CLI**: `subprocess.run([module_cli, "--help"])` output is captured
  and compared to a checked-in fixture. Adding whitespace is a minor
  bump. The fixture is regenerated by an explicit
  `make update-cli-fixtures` target that the maintainer runs after
  reviewing the diff.
- **MCP tool list**: `await session.list_tools()` returns a list of
  `types.Tool` objects. We assert the list of names and each tool's
  `inputSchema` matches a checked-in JSON fixture. Order of tools is
  not part of the contract.
- **MCP tool I/O**: for each tool, we drive it with a "smoke" input
  and assert the success-path response has the expected keys. We do
  not assert exact byte content for translated output (translation is
  non-deterministic) — only the envelope shape.

### 5.3 Schema evolution rules

When evolving `manifest.json` (or any other JSON artifact):

| Change | Allowed at | Test impact |
|--------|------------|-------------|
| Add an **optional** key with a default | minor | Add a fixture covering the new key. |
| Add a new top-level section | minor | New fixture; old consumers keep working. |
| Add a new value to an `enum` field (e.g. a new source format) | minor | New fixture. |
| **Rename** a key | major | Migrate consumers; bump `manifest_version`. |
| **Remove** a key | major | Same. |
| **Change the type** of a key | major | Same. |
| Change a key from optional to required | major | Same. |

The `manifest_version` field is the contract for "what schema version
does this file obey?" It only bumps on a major. Old `manifest_version`
files keep being readable for at least one major cycle.

### 5.4 Cross-version contract test

`tests/integration/test_version_compat.py` is the integration counterpart
to the contract tests. It:

1. Reads the current pinned versions from each module's `pyproject.toml`.
2. Runs the full OPP → OL → ORF pipeline on a minimal generated DOCX.
3. Asserts the output exists, parses, and round-trips through
   `scripts/fidelity_checker.py compute_fidelity()` above the smoke
   threshold (text_score > 0.0 with `OMNI_TEST_FAKE_LLM=1`; the real
   threshold of 0.9 needs real LLM and is gated separately).
4. Reports pass/fail per (opp, ol, orf) combo — this is what populates
   the rows in `VERSION_COMPATIBILITY.md`.

The test is run on every PR. A failure on the current pinned combo
blocks merge; a failure on an older combo is a regression that
demotes that row from "✅ Tested" to "⚠️ Partial" in the compat
matrix.

### 5.5 Rollback / migration coupling

When a major version ships, the matching `docs/MIGRATION_<from>-<to>.md`
must be published in the same release. The migration guide must:

- List every removed/renamed API from § 3.1.
- Show a one-command or one-edit upgrade path for each.
- Reference the test fixtures that exercise the new path.
- Note the deprecation cycle from § 4 (i.e. when the deprecation was
  first announced, so consumers can correlate with their own
  upgrade timeline).

The Phase 1 (MCP rewrite) migration is already documented in
`.omo/plans/2026-06-22-production-readiness-plan.md` § 14.2 and
serves as the template for future migrations.

---

## 6. What this policy does NOT cover

To avoid scope creep:

- **Bug fixes** that change behavior on edge cases. These are patch
  bumps, not breaking changes, even if a consumer was depending on
  the old (buggy) behavior. We will document the fix in
  `CHANGELOG.md` so consumers can see what changed.
- **Performance changes**. We commit to the SLA in `docs/SLA.md`
  (planned, Phase 4) but not to a specific throughput number per
  release.
- **Dependency upgrades** in `pyproject.toml`. We follow `pip check`
  in CI to ensure the three modules co-install; minor dep updates
  are not API-breaking unless they drop a symbol we re-export.
- **Localization of CLI messages** (currently English-only). When we
  add translations, we will do it as an additive change.
- **The `src/Omni_*/` empty submodule paths** — these are a historical
  quirk, not API. See `docs/ARCHITECTURE.md` § 9.

---

## 7. References

- `VERSION_COMPATIBILITY.md` — current tested (opp, ol, orf) combinations
- `docs/ARCHITECTURE.md` — pipeline, module boundaries, artifact contracts
- `docs/ERROR_CODES.md` — CLI exit-code table (part of public API)
- `docs/SECURITY.md` — security audit & CVE policy (overrides § 4.3 #1 for security fixes)
- `scripts/bumpversion.py` — coordinated version bump
- `scripts/mcp_matrix_verifier.py` — real-MCP end-to-end matrix (used for CI gate)
- `tests/integration/test_version_compat.py` — cross-version integration test
- `.omo/plans/2026-06-22-production-readiness-plan.md` § 13 (version strategy) and § 14 (rollback/migration)
- Per-module:
  - `Omni_Pre_Processor/README.md` — OPP public CLI and 7 MCP tools
  - `Omni_Pre_Processor/CHANGELOG.md` — OPP release history
  - `Omni_Localizer/README.md` — OL public CLI and 8 MCP tools
  - `Omni_Localizer/CHANGELOG.md` — OL release history
  - `Omni_Re_Formatter/README.md` — ORF public CLI and 6 MCP tools
  - `Omni_Re_Formatter/CHANGELOG.md` — ORF release history
