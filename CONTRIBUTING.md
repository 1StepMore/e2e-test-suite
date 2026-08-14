# Contributing to Omni Suite

## PR Workflow

1. **Branch naming**: Use one of these prefixes:
   - `feat/` — new feature
   - `fix/` — bug fix
   - `docs/` — documentation only
   - `refactor/` — code restructuring
   - `test/` — adding or fixing tests
   - `chore/` — build, config, CI

   Examples: `feat/add-pptx-styles`, `fix/xliff-encoding-bug`, `docs/update-readme`

2. **Create a draft PR early** — even for work-in-progress. Mark it ready when
   tests pass and review is requested.

3. **Keep PRs focused**. One logical change per PR. Split large changes into
   stacked PRs when possible.

4. **Update AGENTS.md** if you add or change MCP tools, CLI commands, or
   pipeline behavior that agents need to know about.

5. **Update COMPATIBILITY.md** if version compatibility changes between
   modules.

## Test Expectations

All contributions must pass existing tests and add tests for new functionality.

### Running Tests

```bash
# Always set fake LLM unless testing with real API keys
export OMNI_TEST_FAKE_LLM=1

# Suite-level tests
source .venv_ol/bin/activate
pytest tests/ -q

# Module-level tests
pytest Omni_Pre_Processor/tests/ -q
pytest Omni_Localizer/tests/ -q
pytest Omni_Re_Formatter/tests/ -q

# Specific test categories
pytest tests/observability/ -q   # 38 observability tests
pytest tests/security/ -q        # 63 security tests
pytest tests/test_e2e_real_llm.py -v -k test_md_channel
```

The agent-agnostic validation framework is also part of the test surface:
`python scripts/validation/run_validation.py --list` / `--check`, tier-1
scenarios (`--scenario <name> --tier 1`, hermetic — no keys), and
`python scripts/validation/coverage_audit.py` (exit 0 = every live MCP
tool scenario-used). Full instructions: suite `AGENTS.md` → "How to validate".

### Test Requirements

- All new features need at least one test case.
- Bug fixes must include a regression test that failed before the fix.
- Tests should use `OMNI_TEST_FAKE_LLM=1` by default. Real LLM tests go in
  `test_e2e_real_llm.py` and are marked as nightly.
- Test file naming: `test_<module>_<feature>.py`
- MCP tool tests should cover both success and error paths (invalid paths,
  missing files, auth failures).

### Test Environment

| Variable | Purpose |
|----------|---------|
| `OMNI_TEST_FAKE_LLM=1` | Bypass real LLM calls (use for all routine testing) |
| `OMNI_TEST_FAKE_PANDOC=1` | Bypass pandoc calls for ORF tests |
| `OPP_ALLOWED_DIRECTORIES` | Set allowed paths for OPP MCP server |
| `OL_CONFIG_PATH` | Override OL config path |

## Coding Standards

### Python

- **Python 3.13** is the target runtime. All code must be compatible with 3.13.
- **Format**: Use `ruff format` (line length 100).
- **Lint**: Run `ruff check` before committing. The project uses `ruff` with
  the rules defined in each module's `pyproject.toml`.
- **Types**: All function signatures must have type annotations. Use `mypy`
  for static type checking where practical.
- **Imports**: Group imports as standard library, third-party, then local.
  Sort alphabetically within each group.
- **No copyright headers** in source files. License is project-level.

### Naming

| Category | Convention | Example |
|----------|-----------|---------|
| Modules | `snake_case` | `extractors`, `token_stream` |
| Classes | `PascalCase` | `OPPPipeline`, `MDRepairPipeline` |
| Functions | `snake_case` | `process_file`, `translate_md_text` |
| Variables | `snake_case` | `output_path`, `images_dir` |
| Constants | `UPPER_SNAKE` | `OMNI_TEST_FAKE_LLM` |
| Private | `_prefix` | `_safe_unlink`, `_config` |

### Documentation

- Public APIs need docstrings (Google style).
- Internal helpers can skip docstrings if the code is self-explanatory.
- README files stay in Chinese for the suite-level README. English is
  preferred for code comments and docstrings.
- AGENTS.md is the single source of truth for agent-facing documentation.
  Keep it in sync with actual tool surfaces.

## Commit Message Conventions

Follow conventional commits:

```
<type>(<scope>): <short description>

<body (optional)>
```

### Types

| Type | When to use |
|------|-------------|
| `feat` | New feature for a user or agent |
| `fix` | Bug fix |
| `docs` | Documentation only (README, AGENTS.md, etc.) |
| `refactor` | Code change that neither fixes nor adds |
| `test` | Adding or fixing tests |
| `chore` | Build, CI, config, dependencies |
| `perf` | Performance improvement |
| `security` | Security fix |

### Scope Examples

`opp`, `ol`, `orf`, `suite`, `mcp`, `cli`, `docs`

### Examples

```
fix(opp): handle empty paragraph in DOCX extraction

Skip paragraphs with no runs instead of raising IndexError.
Adds regression test test_empty_paragraph_skipped.
```

```
feat(ol): add glossary auto-load from project config

OL now checks for glossary.json in the config directory
and loads it automatically when translate-md is called.
```

```
docs(orf): update apply-md format table in README
```

```
chore: pin ruff to 0.9.x in CI
```

## Code Review

All PRs need at least one review before merging. Reviewers check:

- Tests pass and new functionality is tested.
- No regression in existing behavior.
- Type annotations are correct.
- Error paths are handled (not just the happy path).
- MCP tools return consistent JSON structures.
- No secrets or API keys committed.
- Documentation is updated if the change affects user or agent workflows.

## Getting Help

- Open an issue for bugs or feature requests.
- For MCP integration questions, see `AGENTS.md` or per-module `AGENTS.md`
  / `SKILL.md` files in each `Omni_*/` sub-repo.
