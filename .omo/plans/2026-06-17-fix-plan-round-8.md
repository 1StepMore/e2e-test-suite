# Fix Plan — Round 8 (2026-06-17) — API Key Security (#24)

## Background

**Issue #24** (deferred from rounds 5-7): real API keys are hardcoded
in `Omni_Localizer/config/default.yaml`, which is **tracked in git**.

Hardcoded literals in the tracked template (current state):

| Provider | Model | Value (truncated) |
|---|---|---|
| Zhipu (BigModel) | glm-4-flash | `REDACTED_ZHIPU_KEY` |
| Agnes | agnes-2.0-flash | `${AGNES_API_KEY}` |
| NVIDIA NIM | deepseek-v4-flash | `REDACTED_NVIDIA_NIM_KEY...` |
| NVIDIA NIM | kimi-k2.6 | (same as above) |

These appear in **9 `api_key` fields** across `translation`,
`judging`, and `restoration` roles.

The `Omni_Localizer/.gitignore` *explicitly* forbids this:
```
# `default.yaml` is tracked as a TEMPLATE — never put real keys/endpoints in it.
# Use `local.yaml` and pass `--config Omni_Localizer/config/local.yaml` to CLI.
```
…yet `default.yaml` violates its own policy.

**Severity: HIGH.** Free-tier keys → no billable risk, so we skip
rotation per user instruction. But the violation pattern + lack of
loader-time guard means the next person adding a model entry can
re-introduce hardcoded literals.

## Scope (Round 8)

### Step 1 — SKIPPED per user instruction

Skip API key rotation. All 3 providers are free-tier; no financial
exposure. The leaked keys remain valid but harmless.

### Step 2 — Replace literals in default.yaml with `${ENV_VAR}` refs

| Old literal (truncated) | New ref | Env var to add to .env.example |
|---|---|---|
| `ca5c1f6cb3d1...` (Zhipu) | `${ZHIPU_API_KEY}` | `ZHIPU_API_KEY` |
| `sk-7StQr3Gn...` (Agnes) | `${AGNES_API_KEY}` | `AGNES_API_KEY` |
| `nvapi-C_7ORG...` (NVIDIA NIM) | `${NVIDIA_NIM_API_KEY}` | `NVIDIA_NIM_API_KEY` |

Use the existing `${OPENCODE_GO_KEY}` pattern (line 51) as template.

### Step 3 — Loader-time hardcoded-key detection

Add `_check_for_hardcoded_secrets(data: dict) -> list[str]` in
`src/ol_config/loader.py` that scans the parsed YAML tree for
`api_key` fields matching known literal patterns:

```
- sk-[A-Za-z0-9_-]{20,}       (OpenAI/Anthropic)
- nvapi-[A-Za-z0-9_-]{20,}    (NVIDIA NIM)
- ^[a-f0-9]{16,}\.[A-Za-z0-9]{12,}  (Zhipu MiniMax style)
- ^gsk_[A-Za-z0-9]{20,}       (Groq, future-proofing)
```

Plus a **whitelist exclusion** for any string starting with `${` and
ending with `}` (env var interpolation). Loader raises
`SecurityError("Hardcoded API key detected in config: <model>")` if
any literal matches.

Call site: `load_config()` runs the check after `yaml.safe_load()` and
**before** `ProjectConfig(**data)`.

### Step 4 — Pre-commit / gitleaks coverage

`.pre-commit-config.yaml` already has `gitleaks v8.18.0` (line 4-9).
Verify default rules catch our 3 patterns; if not, add a custom
`gitleaks:custom` rule in `.gitleaks.toml` (new file) to catch
`ca5c1f6c...` Zhipu pattern.

Test: add a fake "leaked" key in a temp file, run `gitleaks detect`,
assert it catches it.

### Step 5 — Git history scrub via `git filter-repo`

`git filter-repo` is available at `/home/renanzai/.local/bin/git-filter-repo`.

```bash
# Replace the 3 hardcoded literals with "<REDACTED-API-KEY>" across
# every commit in default.yaml's history. Rewrite + force-push.
cd Omni_Localizer
git filter-repo --replace-text <(printf '%s\n' \
  '<REDACTED-ZHIPU-API-KEY>' \
  '<REDACTED-AGNES-API-KEY>' \
  '<REDACTED-NVIDIA-API-KEY>' \
) --force
```

Note: `--force` will rewrite + force-push on next push. Requires
coordinating with any other Omni_Localizer collaborators (none
expected — it's the user's own fork per `.gitmodules`).

## Round 8 Execution Plan

1. **Plan file (this file)** — done.
2. **Commit** — round 8 plan.
3. **Step 2: Edit `config/default.yaml`** — replace literals with
   `${ENV_VAR}` refs. 9 fields × ~3 lines each.
4. **Step 3: Edit `src/ol_config/loader.py`** — add
   `_check_for_hardcoded_secrets()` + invoke from `load_config()`.
5. **Add `tests/test_loader_security.py`** — 4-5 tests covering
   the detection patterns (sk-, nvapi-, MiniMax hex, env-var
   exclusion, multi-key).
6. **Step 4: Add `.gitleaks.toml`** if needed for Zhipu pattern.
7. **Step 5: Run `git filter-repo --replace-text`** on the
   Omni_Localizer submodule to scrub history.
8. **Force-push** Omni_Localizer remote (the user's own fork).
9. **Verify**:
   - `git log --all -p -- Omni_Localizer/config/default.yaml | grep
     ca5c1f6c` → no matches
   - OMO loop tier 1 still converges
10. **Commit round 8** as multiple commits (one per step).
11. **Update plan** with results.

## Verification Targets

- `config/default.yaml` has 0 hardcoded literals (only `${...}` refs).
- `_check_for_hardcoded_secrets()` blocks any future re-introduction.
- `gitleaks` config covers all 3 patterns (default or custom rule).
- `git filter-repo` rewrites history → `git log -p` shows no
  hardcoded keys in any historical commit.
- All 46 existing tests pass + new loader security tests pass.
- OMO Tier 1 still converges (regression).

## Risk

- **Loader step 3**: false positive if a user pastes a literal that
  happens to look like an API key (e.g., a 32-char hash in a base URL).
  Mitigation: only scan `api_key` fields, not all strings.
- **gitleaks step 4**: default rules might miss Zhipu pattern.
  Mitigation: add custom rule (`.gitleaks.toml`) before declaring
  step 4 done.
- **filter-repo step 5**: irreversible once pushed. Mitigation: run
  in dry-run mode first (`--dry-run` flag exists in `git filter-repo`
  in newer versions); verify output before pushing.

## What This Round is NOT

- Not rotating API keys (user said no need; free tier).
- Not modifying `local.yaml` (already gitignored + per .gitignore
  policy that's the correct way).
- Not adding new logging, metrics, or features.
- Not changing any translation behavior.

Pure security hardening.