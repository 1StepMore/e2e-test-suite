# doc_inventory.py: three copies, one cross-repo block

OPP, OL and ORF are **separate git repos**. Each ships its own
`scripts/doc_inventory.py` (no shared package is installable from all three),
so the cross-repo reference check exists in three copies. Everything outside
the delimited block is per-repo (`_PATH_ANCHORS`, claims, scope); the block
below is **byte-identical**:

```
# ── BEGIN SHARED CROSS-REPO RESOLUTION (e2e-test-suite#253) ──────────────────
...
# ── END SHARED CROSS-REPO RESOLUTION (e2e-test-suite#253) ────────────────────
```

`tests/test_doc_inventory_copy_parity.py` asserts the equality
(`test_doc_inventory_checked_copy_parity`); it skips only when fewer than two
module checkouts are present.

## Change rule

1. Edit the block in **every copy that is checked out**, byte for byte. Do not
   "improve" one copy locally — the parity test fails, by design.
2. Re-run each module's gate:
   `python scripts/doc_inventory.py --check` (exit 0 required).
3. Run the parity test from the suite root: `pytest tests/test_doc_inventory_copy_parity.py`.
4. Land the module patches and the suite test **together**; a lone module patch
   leaves the other copies behind.

## What the shared block decides

| Backticked token in `README.md` / `AGENTS.md` | Verdict |
|---|---|
| no prefix (`src/opp/x.py`, `docs/dev/y.md`) | must exist **in this repo**; missing ⇒ failure |
| `suite:` / `opp:` / `ol:` / `orf:` prefixed | resolved against a detected checkout; no checkout ⇒ counted as **skipped**, printed in the pass line |
| prefixed with another repo's checkout present but file missing | failure |

A repo counts as a detected checkout only when its marker tree exists
(`omni_mcp`/`omni_suite` for the suite, `src/opp`, `src/ol_md`, `src/orf` for
the modules), so a stray sibling directory cannot turn a skip into a false
failure. `DOC_CROSS_ROOT` (`os.pathsep`-separated) pins the roots to search.

Skipped is not verified: with no checkout the pass line says
`N cross-repo reference(s) NOT verified (suite: N) — no checkout for those
repos. Set DOC_CROSS_ROOT to verify them.`
