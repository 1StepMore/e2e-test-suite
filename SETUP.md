# Phase 1 Setup — Real LLM Integration Tests

> **Prerequisite:** Python >= 3.13. All Omni Suite components require Python 3.13+.
> Verify with `python3 --version` before proceeding.

> **Goal:** Wire your real MiniMax + Baidu Qianfan API keys so the nightly `pytest -m nightly` tests can hit real LLMs (instead of the fake LLM that runs in CI).
>
> **Time:** ~10 minutes.
>
> **What you do:** 3 steps. Copy-paste ready.
>
> **Prereq:** You have active API keys for:
> - **MiniMax** (provider: `minimax`) — https://api.minimaxi.com/
> - **Baidu Qianfan** (provider: `baidu`) — https://qianfan.baidubce.com/
>
> If you don't have these, get them first. Tests will be skipped (not failed) without them.
>
> **Venv prereq (one-time):** The suite ships with a single consolidated venv at `.venv_ol/` that contains all three components (OPP, OL, ORF) installed in editable mode. An older `.venv/` is still present on disk but **DEPRECATED** — see `.venv/DEPRECATED.md` for the deprecation notice. All commands below use `.venv_ol/bin/python`.
>
> If you ever need to rebuild the venv from scratch, run:
> ```bash
> cd "${OMNI_ROOT:-/mnt/d/贯维/Omni_Suite}"
> "${OMNI_ROOT:-/mnt/d/贯维/Omni_Suite}"/.venv_ol/bin/pip install -e Omni_Pre_Processor/ -e Omni_Localizer/ -e Omni_Re_Formatter/
> ```
> Do **not** add new dependencies to `.venv/` — they will not be visible to the test suite.

---

## Step 1 — Fill your API keys

Open: `Omni_Localizer/.env`

Replace these two lines:

```env
MINIMAX_API_KEY=
BAIDU_API_KEY=
```

With your real keys (keep the variable names, no quotes, no spaces around `=`):

```env
MINIMAX_API_KEY=eyJhbGciOi...paste-your-real-minimax-key-here
BAIDU_API_KEY=bce-v3/ALTpa...paste-your-real-baidu-key-here
```

Leave the `*_BASE_URL` lines as-is (they default to the correct endpoints).

**Resulting file should look like:**

```env
# ===== MiniMax (provider: "minimax") =====
MINIMAX_API_KEY=eyJhbGciOi...your-real-key
MINIMAX_BASE_URL=https://api.minimaxi.com/v1

# ===== Baidu Qianfan (provider: "baidu") =====
BAIDU_API_KEY=bce-v3/ALTpa...your-real-key
BAIDU_BASE_URL=https://qianfan.baidubce.com/v2
```

> **Safety:** `Omni_Localizer/.env` is git-ignored (line 59 of `Omni_Localizer/.gitignore` and line 8 of the root `.gitignore`). You will never accidentally commit it.

---

## Step 2 — Wire the 6 model entries into a NEW gitignored config file

**Why a new file?** `Omni_Localizer/config/default.yaml` is **tracked in git** (`git ls-files config/default.yaml` confirms it). We must NOT modify it — keep it as the public template. Instead, we create a new gitignored override at `Omni_Localizer/config/local.yaml` and pass it via `--config`.

> **Already done for you:**
> - `Omni_Localizer/.gitignore` line 66 now ignores `config/local.yaml`, `config/local.*.yaml`, `config/secret.yaml`, and `config/production.yaml`. So any local override you create will never be committed.
> - `Omni_Localizer/config/local.yaml` already exists with the real config (model names: `MiniMax-M3` + `ernie-4.5-turbo-32k`, project_id: `ol-local-real-llm`, `${VAR}` env refs).
> - `Omni_Localizer/config/default.yaml` has been **reverted to its tracked template** (openai/anthropic placeholders). Do not modify it.

### 2a. Verify the local.yaml is in place and gitignored

```bash
cd /mnt/d/贯维/Omni_Suite/Omni_Localizer
ls -la config/local.yaml                            # should exist
git check-ignore -v config/local.yaml               # should print .gitignore:66:config/local.yaml    config/local.yaml
git status --short config/                          # should print nothing (no M/D/?? for config/*)
```

If `git status` shows `M config/default.yaml`, that means someone modified the tracked file — re-revert with `git checkout -- config/default.yaml`. The real config is safe in `local.yaml`.

### 2b. (Reference only — the YAML already in `local.yaml`)

For future maintainers, here's what should be in `local.yaml`:

```yaml
project_id: "ol-local-real-llm"
source_lang: "en"
target_lang: "zh"
glossary_path: null
llm_pool:
  translation:
    - provider: "minimax"
      model: "MiniMax-M3"
      priority: 1
      role: "translation"
      api_key: "${MINIMAX_API_KEY}"
      base_url: "${MINIMAX_BASE_URL}"
      timeout: 60.0
    - provider: "baidu"
      model: "ernie-4.5-turbo-32k"
      priority: 2
      role: "translation"
      api_key: "${BAIDU_API_KEY}"
      base_url: "${BAIDU_BASE_URL}"
      timeout: 60.0
  judging:
    - provider: "baidu"
      model: "ernie-4.5-turbo-32k"
      priority: 1
      role: "judging"
      api_key: "${BAIDU_API_KEY}"
      base_url: "${BAIDU_BASE_URL}"
      timeout: 60.0
    - provider: "minimax"
      model: "MiniMax-M3"
      priority: 2
      role: "judging"
      api_key: "${MINIMAX_API_KEY}"
      base_url: "${MINIMAX_BASE_URL}"
      timeout: 60.0
  restoration:
    - provider: "minimax"
      model: "MiniMax-M3"
      priority: 1
      role: "restoration"
      api_key: "${MINIMAX_API_KEY}"
      base_url: "${MINIMAX_BASE_URL}"
      timeout: 60.0
    - provider: "baidu"
      model: "ernie-4.5-turbo-32k"
      priority: 2
      role: "restoration"
      api_key: "${BAIDU_API_KEY}"
      base_url: "${BAIDU_BASE_URL}"
      timeout: 60.0
```

**Why this shape:**
- Schema requires **≥ 2 models per role** (`LLMPoolConfig.check_min_models_per_role` in `Omni_Localizer/src/ol_config/schema.py:48-57`).
- `api_key` and `base_url` use `${VAR}` syntax — the loader (`Omni_Localizer/src/ol_config/loader.py:14-21`) auto-resolves from `.env` at config load time, and the schema validator (`schema.py:17-23`) fails fast if the env var is missing.
- `timeout: 60.0` matches the schema default.
- `project_id` is `ol-local-real-llm` (NOT the template's `ol-phase0-test`) so logs distinguish your real-LLM runs from CI's fake runs.

> **Backup models:** If `priority 1` fails, litellm falls back to `priority 2` automatically (`router.py:51-57`, `num_retries=2`).

---

## Step 3 — Verify the real LLM works

Run these commands from the repo root. The CLI auto-loads `.env` via `_load_env_for_cli()` (`Omni_Localizer/src/ol_cli.py:321`), so you do NOT need to `source` anything.

> **Note:** Both `translate-md` and `translate-xliff` require:
> - `--output-dir` (or `-o`) — the CLI exits with code 1 if missing.
> - `--config` (or `-c`) — points to your gitignored `local.yaml` (NOT the tracked `default.yaml`).

### 3a. Quick smoke test (CLI, MD path)

```bash
cd /mnt/d/贯维/Omni_Suite
.venv_ol/bin/python -m ol_cli translate-md \
    Omni_Localizer/tests/fixtures/sample.md \
    -c Omni_Localizer/config/local.yaml \
    -o /tmp/ol-smoke \
    -s en -t zh
```

Expected output (last line):

```
Translated: sample.md -> /tmp/ol-smoke/sample.md (en -> zh)
```

Should finish in **< 30 seconds** (real network round-trip to MiniMax/Baidu). You should also see `Using config: ol-local-real-llm (en -> zh)` printed before the translate line (proof the local.yaml was loaded, not the tracked default).

### 3b. Quick smoke test (CLI, XLIFF path)

```bash
cd /mnt/d/贯维/Omni_Suite
.venv_ol/bin/python -m ol_cli translate-xliff \
    Omni_Localizer/tests/fixtures/sample-xliff12.xlf \
    -c Omni_Localizer/config/local.yaml \
    -o /tmp/ol-smoke \
    -s en -t zh
```

Expected output (last line):

```
Translated: sample-xliff12.xlf -> /tmp/ol-smoke/sample-xliff12.xlf (en -> zh)
```

Same ~30s target.

### 3c. If you have the Haier DOCX converted to XLIFF (24-image stress test)

The full Haier DOCX (24 images, 9 paragraphs) is the committed fixture `scenarios/_fixtures/haier_ch2_zh.docx`. To convert it to XLIFF first:

```bash
# (Optional) Convert DOCX → XLIFF via OPP
cd /mnt/d/贯维/Omni_Suite
.venv_ol/bin/python -m opp_cli extract "scenarios/_fixtures/haier_ch2_zh.docx" \
    -o /tmp/ol-haier-xliff
```

Then translate the XLIFF:

```bash
.venv_ol/bin/python -m ol_cli translate-xliff \
    /tmp/ol-haier-xliff/*.xlf \
    -c Omni_Localizer/config/local.yaml \
    -o /tmp/ol-smoke-haier \
    -s en -t zh
```

Expected: translated XLIFF with all 9 paragraphs + 24 image placeholders preserved. This is the smoke test the new nightly suite exercises end-to-end (`tests/test_e2e_real_llm.py`).

---

## Common errors & fixes

| Symptom | Cause | Fix |
|---|---|---|
| `Environment variable 'MINIMAX_API_KEY' not set` | `.env` not loaded | Check Step 1 — make sure the line has no leading space, no quote, the `=` is direct. |
| `AuthenticationError: Invalid API key` (401/403) | Key typo / wrong project | Re-paste key from provider console. For Baidu, copy the full `bce-v3/ALTpa...` string verbatim. |
| `Model not found` (404 from MiniMax) | Wrong model name | `MiniMax-M3` is the current default; if MiniMax rotated, check https://api.minimaxi.com/ for the current text model id. |
| `RateLimitError` (429) | Hit free-tier cap | Wait 60s and re-run, or upgrade tier. |
| Test `SKIPPIPPED: no MINIMAX/BAIDU key` | `.env` not visible to pytest | Confirm the file is at `Omni_Localizer/.env` (suite root, not test cwd). The `use_real_llm` fixture (`tests/test_e2e_real_llm.py:48-63`) reads it from there via `Path(__file__).resolve().parents[1] / "Omni_Localizer" / ".env"`. |
| `Error: --output-dir is required` | CLI requires `-o` flag | Add `-o /tmp/ol-smoke` (or any writable dir) to every `translate-md` / `translate-xliff` command. |
| CLI is using `openai`/`anthropic` even though I set up `local.yaml` | Forgot `--config` flag, so it fell back to tracked `default.yaml` | Add `-c Omni_Localizer/config/local.yaml` to every command. Check the line `Using config: ol-local-real-llm` appears in the output. |

---

## Confirmation checklist (tick all before saying "done")

- [ ] `Omni_Localizer/.env` has real `MINIMAX_API_KEY` and `BAIDU_API_KEY` values (no quotes, no spaces).
- [ ] `Omni_Localizer/config/local.yaml` exists with 6 model entries (2 per role, MiniMax + Baidu, `${VAR}` env refs).
- [ ] `Omni_Localizer/.gitignore` line 66+ ignores `config/local.yaml` (verified with `git check-ignore -v config/local.yaml`).
- [ ] `Omni_Localizer/config/default.yaml` is UNCHANGED (still the tracked template, no real config in it). Run `git diff Omni_Localizer/config/default.yaml` — should be empty.
- [ ] Step 3a prints `Using config: ol-local-real-llm ...` then `Translated: sample.md -> ...`.
- [ ] Step 3b prints `Translated: sample-xliff12.xlf -> ...`.
- [ ] `git status` in `Omni_Localizer/` shows `local.yaml` **NOT** in the untracked list, and `.env` **NOT** in the modified list.
- [ ] You can read this checklist out loud to me and say "Phase 1 done".

---

## What's next (you don't do this; I do)

After Phase 1, I run Phases 2-7 (~7-8 hours):
- **Phase 2-3:** OPP floating-image fix + ORF `wp:anchor` injection (24/24 strict visual positioning).
- **Phase 4:** OL LQA auto-invoke in main pipeline (opt-in via `enable_lqa: bool`).
- **Phase 5:** MD path "DOCX + images separate" mode (opt-in).
- **Phase 6:** The 3 nightly real-LLM tests in `tests/test_e2e_real_llm.py`.
- **Phase 7:** Full CI green + nightly locally green verification.

Trigger: tell me "Phase 1 done" and paste the Step 3a output, and I start.
