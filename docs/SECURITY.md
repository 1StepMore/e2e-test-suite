# Security Posture & User Action Items

> **Audience:** Omni_Suite maintainers and operators.
> **Last updated:** 2026-06-05 (T17 prep — C2 re-verified clean, see below)
> **Related:** `AUDIT_FINDINGS_VERIFIED.md` (full audit, CRITICAL items C1–C17)

This document covers the security items that **require user action** (C1, C2) and the items that were **fixed in code** during Phases 2–5 (C3–C6, C12). For the complete audit context, see `AUDIT_FINDINGS_VERIFIED.md`.

---

## 🔴 User Action Required

### C1. Rotate the API keys (assumed compromised)

The audit on 2026-06-04 found real `MINIMAX_API_KEY` and `BAIDU_API_KEY` values in `Omni_Localizer/.env` with file mode `chmod 777` (world-readable/writable). The same values were also committed to git history (see C2). **Treat both keys as compromised.**

**Action steps:**

1. **Rotate MiniMax key**
   - Go to https://api.minimaxi.com/ (or your MiniMax provider console)
   - Revoke the existing `MINIMAX_API_KEY`
   - Generate a new key
   - Copy the full string verbatim (no quotes, no spaces)

2. **Rotate Baidu Qianfan key**
   - Go to https://qianfan.baidubce.com/
   - Revoke the existing `BAIDU_API_KEY`
   - Generate a new key (the full `bce-v3/ALTpa...` string)
   - Copy verbatim

3. **Update `.env`** at `Omni_Localizer/.env`:
   ```env
   MINIMAX_API_KEY=eyJhbGciOi...your-new-minimax-key
   BAIDU_API_KEY=bce-v3/ALTpa...your-new-baidu-key
   ```
   Leave the `*_BASE_URL` lines as-is (they default to the correct endpoints).

4. **Lock the file down**:
   ```bash
   chmod 600 Omni_Localizer/.env
   ```
   Consider adding `install -m 600` to setup scripts so future `.env` files are born safe.

5. **Verify nothing broke**:
   ```bash
    cd <project-root>
   .venv_ol/bin/python -m ol_cli translate-md Omni_Localizer/tests/fixtures/sample.md \
       -c Omni_Localizer/config/local.yaml \
       -o /tmp/ol-rotate-smoke -s en -t zh
   ```
   Expected: `Using config: ol-local-real-llm (en -> zh)` then a `Translated: sample.md -> ...` line.

> **Why this is deferred (not auto-fixed):** Key rotation is destructive on the provider side. The Omni_Suite codebase cannot rotate keys for you — it has no credentials to the provider admin consoles, and rotating automatically would lock out any other workflows still using the old key. The fix is one human action in a browser.

---

### C2. Purge the leaked keys from git history (optional but recommended)

Commit `141123b657e2ca531b0a3761d0c38287da6ced95` (May 29 2026) added `Omni_Localizer/config/book_localization.yaml` whose header comments literally contained both API keys. Later commits (`da61b5f`, `9d62126`) only patched the **comments**; the historical diff is permanent in `.git/objects/`.

> **✅ VERIFIED CLEAN 2026-06-05 (T17 prep, before doing the filter-repo).** Exhaustive scan of **663 blobs in `Omni_Localizer/.git/objects/`** (every reachable + unreachable blob, including all dangling objects from `git fsck`) for the exact leaked key signatures from `GIT_HISTORY_PURGE_PLAN.md`:
> - `sk-cp-CAPjdmwYi7mVzEjlbnCpHfGAi2h07` → **0 matches**
> - `bce-v3/ALTAK-TxQXA9aqHZYbcg9FDXsNa/491ea5eaa48b124f595501b88736fb9db2a8c606` → **0 matches**
> - Broader patterns (`sk-cp-*`, `bce-v3/*`, `sk-ant-*`, generic `sk-*` ≥20 chars) → **0 matches**
> - The 3 specific blob SHAs from the plan (`3b15963d…`, `79c386c6…`, `707195f4…`) → **NOT in object DB at all**
> - Current `main:config/test_universal.yaml` → uses `${OPENAI_API_KEY}` placeholder, **clean**
>
> The plan's leak inventory describes a state that does not exist in this clone (neither local nor on `origin/main`, `origin/e2e-14-fix`, `origin/e2e-validated`). Either a prior cleanup already removed them, or the plan was based on an analysis of a different clone. **No filter-repo needed locally.**

**If you have already rotated the keys (C1) AND the keys are no longer in any active config, the git history is purely archival.** You can choose to leave it alone. If you want to purge (now moot for the local clone, but the playbook is preserved in `GIT_HISTORY_PURGE_PLAN.md` for reference):

**Option A — `git filter-repo` (recommended):**

```bash
# One-time install
pip install git-filter-repo

# Remove the leaked file from ALL commits, across all branches
cd Omni_Localizer
git filter-repo --invert-paths --path config/book_localization.yaml

# Force-push (COORDINATE WITH ALL COLLABORATORS — they must re-clone)
git remote add origin <your-remote-url>  # if filter-repo stripped it
git push origin --force --all
git push origin --force --tags
```

**Option B — `git filter-branch` (legacy, slower, kept for reference):**

```bash
cd Omni_Localizer
git filter-branch --force --index-filter \
    "git rm --cached --ignore-unmatch config/book_localization.yaml" \
    --prune-empty --tag-name-filter cat -- --all
git push origin --force --all
```

> **⚠️ Destructive — coordinate before force-pushing.** After force-push, all clones (yours included) must be re-cloned or `git fetch origin && git reset --hard origin/main`'d. Any in-flight feature branches will need to be rebased.

**Post-purge verification:**

```bash
# Should print nothing
git log --all --full-history -- config/book_localization.yaml
git rev-list --all | while read rev; do
    git grep -l "MINIMAX_API_KEY=" $rev 2>/dev/null
done | head -5
```

> **Why this is deferred (not auto-fixed):** `git filter-repo` rewrites the entire local git history. Doing it in the Omni_Suite codebase (or any sub-repo) without coordinating with every collaborator will cause silent desyncs. The fix is a deliberate human action with communication.

---

## ✅ Code Fixes Landed in Phases 2–5 (T1–T15)

The following CRITICAL items were fixed in code during the T1–T15 work cycles. They are documented here for completeness; for the full audit context see `AUDIT_FINDINGS_VERIFIED.md` § "✅ Resolution Status".

### C3. OPP MCP `unlink()` on user-controlled paths → **FIXED**

**Before:** `Path(file_path).with_suffix(".md")` was later `unlink()`'d without re-validation. Attacker could swap a symlink to delete files outside the allowlist.

**Fix:** Every `unlink()` now calls `Path(...).resolve()` first and re-validates against `allowed_directories`. Intermediate outputs use `tempfile.NamedTemporaryFile` so they auto-clean on context exit without `unlink()`.

**Verified by:** `Omni_Pre_Processor/tests/mcp/test_security_attacks.py`

---

### C4. ORF MCP `ImagePlacement.file_path` arbitrary read → **FIXED**

**Before:** `Path(img_dict["file_path"]).read_bytes()` — no path validation. Attacker could read `/etc/passwd` and have it embedded as a base64 image.

**Fix:** All `img_dict["file_path"]` values now flow through `PathValidator.validate(...)` before read. The MCP request layer rejects `file_path` for images unless the path is inside an allowlisted directory.

**Verified by:** `Omni_Re_Formatter/tests/test_orf_security_attacks.py`

---

### C5. ORF MCP `apply_xliff` arbitrary file write → **FIXED**

**Before:** `output_path` (required, unvalidated) → CLI subprocess → file write. Attacker could overwrite `~/.ssh/authorized_keys`, `/etc/cron.d/*`, etc.

**Fix:** `output_path` now goes through `PathValidator.validate(output_path, base_dir=...)` before any subprocess is invoked. The subprocess's working directory is also pinned to the validated parent.

**Verified by:** `Omni_Re_Formatter/tests/test_orf_security_attacks.py`

---

### C6. OPP MCP resource validation only checked `allowed_directories[0]` → **FIXED**

**Before:** `resource_path.resolve().relative_to(_config.allowed_directories[0])` — directories 1..N were silently ignored.

**Fix:** Iterates **all** `allowed_directories` and accepts the path if it is relative to **any** of them. Uses `Path.is_relative_to()` for the check.

**Verified by:** `Omni_Pre_Processor/tests/mcp/test_security_attacks.py`

---

### C12. MCP servers leaked full tracebacks → **FIXED**

**Before:** Six near-identical copies of `return {"success": False, "error": f"...{str(e)}"}` in `ol_mcp/tools.py` alone, plus similar blocks in `opp_mcp/server.py` and `orf_mcp/server.py`. Clients received file paths, internal logic, and system info in error messages.

**Fix:** A single `@mcp_error_boundary` decorator at the tool boundary. The decorator:

- Logs the full traceback server-side (with `logger.exception(...)`)
- Returns an opaque error code + generic message to the client
- Generates a short correlation id (`corr_xxxx`) so server logs can be looked up by the client error code

The decorator lives at:
- `Omni_Pre_Processor/src/opp_mcp/_errors.py`
- `Omni_Re_Formatter/src/orf_mcp/_errors.py` (added during T10; see also the `mcp_error_boundary` import in `ol_mcp/tools.py`)

**Verified by:** `Omni_Pre_Processor/tests/mcp/test_*.py` and the per-tool tests in the three sub-repos.

---

## 📋 Recommended Pre-Commit / CI Hardening

To prevent future secret leaks, install **one** of the following as a pre-commit hook:

### Option A — `gitleaks` (preferred, faster)

```bash
# One-time install
brew install gitleaks          # macOS
# or
go install github.com/gitleaks/gitleaks/v8@latest

# .pre-commit-config.yaml (add to repo root)
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks
```

### Option B — `detect-secrets` (Python-native, more configurable)

```bash
# One-time install
pip install detect-secrets

# Initialize a baseline (one-time)
cd <project-root>
detect-secrets scan > .secrets.baseline

# .pre-commit-config.yaml
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
```

### What to scan for

Both tools flag any line matching patterns like:
- `*_API_KEY=...`
- `*_SECRET=...`
- `*_TOKEN=...`
- `-----BEGIN [A-Z ]*PRIVATE KEY-----`
- AWS access keys (`AKIA[0-9A-Z]{16}`)
- Generic high-entropy strings in known config files

The existing `.gitignore` files already cover `*.env`, `config/local*.yaml`, `config/secret.yaml`, and `config/production.yaml`, so secrets in those files won't be committed — but the pre-commit hook is a safety net for **new** patterns the gitignore didn't anticipate.

---

## 📌 Accepted Risk: C7 (no auth on stdio MCP)

The three MCP servers (`ol_mcp`, `opp_mcp`, `orf_mcp`) currently expose no authentication. This is **acceptable for stdio transport** (trust = the OS user that spawned the process). It would be **catastrophic if any MCP server were ever exposed over HTTP or SSE without auth** — anyone reachable on the network could call the tools and read/write files on the host.

**If you ever add an HTTP/SSE transport:**

1. Require an `Authorization: Bearer <token>` header on every request
2. Verify the token against a secrets manager (not a file)
3. Add per-client rate limits
4. Add a structured audit log of every tool call (timestamp, caller PID/UID, tool name, args hash, result code)
5. Update `AUDIT_FINDINGS_VERIFIED.md` to mark C7 as "fixed"

Until then, the recommendation is: **stdio only, never bind to a network socket**.

---

## See also

- `AUDIT_FINDINGS_VERIFIED.md` — full audit, 17 CRITICAL items, 22 HIGH, 35 MEDIUM/LOW
- `GIT_HISTORY_PURGE_PLAN.md` — pre-written playbook for the C2 purge (do not run without coordination)
- `docs/T14_LIMITATION.md` — the T14 partial-state limitation (hermetic CI seam gap)
- `SETUP.md` — Phase 1 setup guide (where the `.env` and `local.yaml` go)
