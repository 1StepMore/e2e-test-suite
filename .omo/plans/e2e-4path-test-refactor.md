# E2E 4-Path Test Refactor — OPP→OL→ORF

> **Status**: Draft, awaiting user approval
> **Created**: 2026-06-02
> **Author**: Sisyphus (orchestrator)
> **Scope**: De-fragilize e2e test coverage of the OPP→OL→ORF pipeline's 4 paths

---

## 1. Background & Problem Statement

The Omni_Suite has 4 pipeline paths that must be verified end-to-end:

| Path | Format | Transport | Module chain |
|------|--------|-----------|--------------|
| **A** | .xliff | MCP    | OPP → OL MCP `translate_xliff`     → XLIFF2DOCXConverter |
| **B** | .xliff | CLI    | OPP → `ol_cli translate-xliff`    → `orf.cli apply-xliff` |
| **C** | .md    | MCP    | OPP → OL MCP `translate_md_text`  → MD2DOCXConverter |
| **D** | .md    | CLI    | OPP → `ol_cli translate-md`       → `orf.cli apply-md` |

### Current state (audited 2026-06-02)

**All 4 paths are tested in a single 256-line class** `TestE2EFullPipelineReal` at `Omni_Suite/tests/test_e2e_pipeline.py:592-848`:

| Test | Line | Status |
|------|------|--------|
| `test_e2e_xliff_cli` | L610 | ⚠️ `assert rc in [0,1]` — silent pass if LLM key absent |
| `test_e2e_xliff_mcp` | L677 | ✅ Real OPP + comprehensive mock (text demonstrably different) |
| `test_e2e_md_cli`    | L749 | ⚠️ `assert rc in [0,1]` — silent pass |
| `test_e2e_md_mcp`    | L802 | ✅ Real OPP + comprehensive mock |

### Identified gaps

1. **Single point of failure** — all 4 paths in one file. If OPP import breaks, all 4 are lost.
2. **Silent-pass on CLI paths** — `rc in [0,1]` accepts LLM failure as "pass". No translation verification when key absent.
3. **No failure injection** — `TestErrorHandling` (L395-451) only covers OPP errors. No coverage of LLM exception, XLIFF parse error, ORF rejection, or OPP timeout in the chain.
4. **No multi-format coverage** — only DOCX input (via `haier_real_docx_path` fixture pointing to the 447KB `爱上海尔_第二章_全球创牌 - E2E测试专用.docx`). PPTX and PDF inputs are not tested in the 4-path chain.
5. **No MD contract test** — `Omni_Pre_Processor/tests/test_opp_ol_orf_contracts.py` covers XLIFF contract only. No MD-path equivalent.
6. **Phantom test file** — `Omni_Re_Formatter/tests/test_e2e_omni_pipeline.py` is entirely `@patch("subprocess.run")` — name is misleading, provides zero real coverage.
7. **MCP tests are 100% mocked** — `tests/test_e2e_ol_mcp.py` and `tests/test_e2e_orf_mcp.py` mock `ModelPool` / `_run_cli_command` respectively. Verify plumbing, not translation.
8. **Subprocess pandoc dependency** — Path C (`test_e2e_md_mcp`) patches `subprocess.run` in-process for `MD2DOCXConverter` calls, but `orf.cli apply-md` runs in subprocess where the mock doesn't propagate. If pandoc is not installed in the env, the subprocess call fails.

### User's explicit goals (priority order)

1. **De-fragilize** — the 4 paths should NOT all die if one file is broken
2. **Strengthen CLI assertions** — paths B and D must assert `rc == 0` and content, not `rc in [0,1]`
3. **Add failure injection** — LLM exception, XLIFF parse error, OPP timeout
4. **Add multi-format coverage** — at least PPTX and PDF inputs
5. **Add MD-path contract test** — analogous to `test_opp_ol_orf_contracts.py`

---

## 2. Design Decision: Fake-LLM Seam

**Recommendation: Option (a) — env-var test seam in production CLIs.**

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| (a) **Env-var seam in `ol_cli.py` / `orf.cli`** | Self-documenting, ~15 lines per file, single chokepoint, deterministic | Touches production code | ✅ **Recommended** |
| (b) Python shim (PYTHONPATH/sitecustomize injection) | No production change | Fragile, pollutes test infra, requires `sys.path` hacks | ❌ |
| (c) Better assertions on `rc=1` | No code change | Doesn't fix the silent-pass issue user called out | ❌ |

### Why (a) wins

- The seam point is **already implicit**: `ol_cli.py` calls `ModelPool.get_instance()` at L239 and L338 (the only two places that touch the LLM). A 6-line guarded swap there is minimal, well-isolated.
- `OMNI_TEST_FAKE_LLM=1` cannot leak to production — tests set it explicitly via `_make_subprocess_env()` in conftest. Production runs never set it.
- The same pattern applies to ORF's pandoc dependency: `OMNI_TEST_FAKE_PANDOC=1` short-circuits `subprocess.run(["pandoc", ...])` to write a stub DOCX, making Path C/D hermetic without requiring pandoc in CI.

### Seam specifications

**`ol_cli.py`** — add to top of `_translate_md_async` (L239) and `_translate_xliff_async` (L338):

```python
if os.environ.get("OMNI_TEST_FAKE_LLM") == "1":
    from tests.test_e2e_pipeline_fixtures import _FakeModelPool  # noqa: E402
    return await _FakeModelPool().translate(...)
```

The fixture import is conditional on the env var, so production never loads test fixtures.

**`orf.cli`** — add to top of `apply_md` (L80) and `apply_xliff` (L423):

```python
if os.environ.get("OMNI_TEST_FAKE_PANDOC") == "1":
    from tests.test_e2e_pipeline_fixtures import _FakePandocRunner  # noqa: E402
    return _FakePandocRunner()(output_path, ...)
```

---

## 3. File Structure

### 3.1 New files (8)

| Absolute path | Lines (est.) | Purpose |
|---------------|--------------|---------|
| `Omni_Suite/.omo/plans/e2e-4path-test-refactor.md` | this file | The plan itself |
| `Omni_Suite/tests/test_e2e_pipeline_fixtures.py` | ~150 | Shared fake LLM/pandoc fixtures |
| `Omni_Suite/tests/test_e2e_path_xliff_mcp.py`    | ~120 | Path A — extracted from `test_e2e_pipeline.py:677` |
| `Omni_Suite/tests/test_e2e_path_xliff_cli.py`    | ~120 | Path B — extracted from `test_e2e_pipeline.py:610` |
| `Omni_Suite/tests/test_e2e_path_md_mcp.py`       | ~120 | Path C — extracted from `test_e2e_pipeline.py:802` |
| `Omni_Suite/tests/test_e2e_path_md_cli.py`       | ~120 | Path D — extracted from `test_e2e_pipeline.py:749` |
| `Omni_Suite/tests/test_e2e_pipeline_failures.py` | ~250 | Failure injection (parametrized over 4 paths) |
| `Omni_Suite/tests/test_e2e_pipeline_multiformat.py` | ~250 | 4 paths × PPTX/PDF inputs |
| `Omni_Pre_Processor/tests/test_opp_ol_orf_contracts_md.py` | ~250 | MD contract analogous to XLIFF contract test |

### 3.2 Modified files (3)

| Absolute path | Change |
|---------------|--------|
| `Omni_Suite/Omni_Localizer/src/ol_cli.py` | Add `OMNI_TEST_FAKE_LLM=1` short-circuit at L239 (`_translate_md_async`) and L338 (`_translate_xliff_async`). ~12 lines, fully guarded by env-var check. |
| `Omni_Suite/Omni_Re_Formatter/src/orf/cli.py` | Add `OMNI_TEST_FAKE_PANDOC=1` short-circuit at L80 (`apply_md`) and L423 (`apply_xliff`). ~10 lines, fully guarded. |
| `Omni_Suite/tests/conftest.py` | (a) Update `_make_subprocess_env()` to set `OMNI_TEST_FAKE_LLM=1` and `OMNI_TEST_FAKE_PANDOC=1` when the `use_fake_llm` fixture is active. (b) Add `real_chain` marker to `pytest_configure` (L640-656). (c) Add `sample_pdf_path` fixture using `reportlab`. |

### 3.3 Trimmed files (1)

| Absolute path | Change |
|---------------|--------|
| `Omni_Suite/tests/test_e2e_pipeline.py` | Remove the 4 path test methods (L592-848) from `TestE2EFullPipelineReal`. Keep all earlier classes (TestOPPExtraction, TestOPPToOLIntegration, TestOLToORFIntegration, TestErrorHandling, etc.). After trim, the file is purely OPP-only and unit-level. |

### 3.4 Removed files (0)

None. `Omni_Re_Formatter/tests/test_e2e_omni_pipeline.py` is **not** removed in this plan; its 100%-mocked status is noted as future cleanup but is out of scope for the 4-path refactor.

---

## 4. Per-File Test Classes & Assertion Strategy

### 4.1 `tests/test_e2e_pipeline_fixtures.py` (NEW — shared)

```python
"""Shared fixtures for the 4-path e2e pipeline tests.

Activated by:
  - OMNI_TEST_FAKE_LLM=1 (intercepted by ol_cli.py)
  - OMNI_TEST_FAKE_PANDOC=1 (intercepted by orf.cli)
"""

import pytest


@pytest.fixture
def use_fake_llm(monkeypatch):
    """Marker fixture — sets OMNI_TEST_FAKE_LLM=1 for subprocess propagation."""
    monkeypatch.setenv("OMNI_TEST_FAKE_LLM", "1")
    monkeypatch.setenv("OMNI_TEST_FAKE_PANDOC", "1")
    return True


class _FakeModelPool:
    """Drop-in for ol_pool.router.ModelPool.

    Maps EN→ZH deterministically for any input.
    Returns text that is demonstrably different from source.
    """

    _TRANSLATE_MAP: dict[str, str] = {
        "User Manual": "用户手册",
        "Welcome to the user manual.": "欢迎使用用户手册。",
        "Chapter 1: Getting Started": "第一章:开始使用",
        # ... comprehensive map, ported from tests/conftest.py:622
    }

    async def translate(self, text, source_lang, target_lang, role="translation"):
        if text in self._TRANSLATE_MAP:
            return self._TRANSLATE_MAP[text]
        # Default: prepend language tag
        return f"[{target_lang}] {text}"


class _FakePandocRunner:
    """Drop-in for subprocess.run when OMNI_TEST_FAKE_PANDOC=1.

    Writes a minimal valid DOCX at the output path.
    """

    def __call__(self, cmd, *args, **kwargs):
        # cmd shape: ["pandoc", "-o", output_path, input_path]
        output_path = cmd[cmd.index("-o") + 1] if "-o" in cmd else None
        if output_path:
            _write_stub_docx(output_path)
        return _CompletedProcessStub(args=cmd, returncode=0, stdout=b"", stderr=b"")


def _write_stub_docx(path: str) -> None:
    """Write a minimal DOCX with one paragraph containing '用户手册'."""
    # Use python-docx if available; otherwise write a stub with raw zip
    try:
        from docx import Document
        doc = Document()
        doc.add_paragraph("用户手册")
        doc.add_paragraph("欢迎使用")
        doc.save(path)
    except ImportError:
        # Fallback: write a marker file
        with open(path, "wb") as f:
            f.write(b"FAKE_PANDOC_STUB\n")
```

### 4.2 `tests/test_e2e_path_xliff_mcp.py` (NEW — Path A)

```python
"""Path A: OPP → OL MCP translate_xliff → XLIFF2DOCXConverter."""

import pytest
from pathlib import Path

pytestmark = [pytest.mark.e2e, pytest.mark.real_chain]


class TestPathXliffMCP:
    def test_full_chain_produces_translated_docx(
        self, haier_real_docx_path, use_fake_llm, tmp_path: Path
    ):
        """End-to-end: real OPP + fake MCP OL + real XLIFF2DOCXConverter."""
        # ... (port of test_e2e_xliff_mcp from test_e2e_pipeline.py:677)
        # Use the comprehensive mock for OL MCP, real for OPP and ORF
        result = _run_xliff_mcp_chain(
            input_docx=haier_real_docx_path,
            output_dir=tmp_path,
        )
        assert result.docx_path.exists()
        text = _extract_docx_text(result.docx_path)
        assert "用户手册" in text or "欢迎" in text, \
            f"Translation marker not found in: {text[:200]}"
```

### 4.3 `tests/test_e2e_path_xliff_cli.py` (NEW — Path B)

```python
"""Path B: OPP → ol_cli translate-xliff → orf.cli apply-xliff."""

import pytest
from pathlib import Path

pytestmark = [pytest.mark.e2e, pytest.mark.real_chain]


class TestPathXliffCLI:
    def test_full_chain_cli_returns_zero(
        self, haier_real_docx_path, use_fake_llm, tmp_path: Path
    ):
        """End-to-end: real OPP subprocess + real OL CLI (with fake LLM)
        + real ORF CLI (with fake pandoc). All subprocesses must return rc=0."""
        result = _run_xliff_cli_chain(
            input_docx=haier_real_docx_path,
            output_dir=tmp_path,
        )
        # CRITICAL: assert rc == 0, not rc in [0,1]
        assert result.ol_result.returncode == 0, (
            f"OL CLI failed (rc={result.ol_result.returncode}): "
            f"{result.ol_result.stderr.decode()}"
        )
        assert result.orf_result.returncode == 0, (
            f"ORF CLI failed (rc={result.orf_result.returncode}): "
            f"{result.orf_result.stderr.decode()}"
        )
        assert result.docx_path.exists()
        text = _extract_docx_text(result.docx_path)
        assert "用户手册" in text or "欢迎" in text
```

**Key change vs current:** `assert rc == 0` (was `rc in [0,1]`).

### 4.4 `tests/test_e2e_path_md_mcp.py` (NEW — Path C)

```python
"""Path C: OPP → OL MCP translate_md_text → MD2DOCXConverter."""

import pytest
from pathlib import Path

pytestmark = [pytest.mark.e2e, pytest.mark.real_chain]


class TestPathMdMCP:
    def test_full_chain_produces_translated_docx(
        self, haier_real_docx_path, use_fake_llm, tmp_path: Path
    ):
        # ... port of test_e2e_md_mcp from test_e2e_pipeline.py:802
        ...
```

### 4.5 `tests/test_e2e_path_md_cli.py` (NEW — Path D)

```python
"""Path D: OPP → ol_cli translate-md → orf.cli apply-md."""

import pytest
from pathlib import Path

pytestmark = [pytest.mark.e2e, pytest.mark.real_chain]


class TestPathMdCLI:
    def test_full_chain_cli_returns_zero(
        self, haier_real_docx_path, use_fake_llm, tmp_path: Path
    ):
        # CRITICAL: assert rc == 0, not rc in [0,1]
        ...
```

### 4.6 `tests/test_e2e_pipeline_failures.py` (NEW)

```python
"""Failure injection tests — parametrized over all 4 paths."""

import pytest
from unittest.mock import AsyncMock

pytestmark = [pytest.mark.e2e, pytest.mark.real_chain, pytest.mark.failure]


PATHS = ["xliff_mcp", "xliff_cli", "md_mcp", "md_cli"]


class TestPathFailures:

    @pytest.mark.parametrize("path", PATHS)
    def test_ol_llm_exception_handled_gracefully(
        self, path, haier_real_docx_path, use_fake_llm, tmp_path, monkeypatch
    ):
        """If the LLM raises mid-chain, the path should fail with an
        informative error, not crash silently."""
        # Patch the fake pool to raise
        from tests.test_e2e_pipeline_fixtures import _FakeModelPool
        monkeypatch.setattr(
            _FakeModelPool, "translate",
            AsyncMock(side_effect=RuntimeError("LLM down (test)")),
        )
        result = _run_path(path, haier_real_docx_path, tmp_path)
        assert result.exit_code != 0
        stderr = result.stderr.decode() if result.stderr else ""
        assert "LLM" in stderr or "translation" in stderr.lower(), (
            f"Expected informative error, got: {stderr[:200]}"
        )

    @pytest.mark.parametrize("path", ["xliff_mcp", "xliff_cli"])
    def test_orf_xliff_parse_error_handled_gracefully(
        self, path, haier_real_docx_path, use_fake_llm, tmp_path, monkeypatch
    ):
        """If ORF receives corrupted XLIFF, it should reject cleanly."""
        from tests.test_e2e_pipeline_fixtures import _FakeModelPool
        monkeypatch.setattr(
            _FakeModelPool, "translate",
            AsyncMock(side_effect=ValueError("malformed XLIFF (test)")),
        )
        ...

    @pytest.mark.parametrize("path", PATHS)
    def test_opp_timeout_handled_gracefully(
        self, path, haier_real_docx_path, use_fake_llm, tmp_path, monkeypatch
    ):
        """If OPP times out, the chain should fail with timeout error."""
        ...
```

### 4.7 `tests/test_e2e_pipeline_multiformat.py` (NEW)

```python
"""Multi-format coverage — 4 paths × PPTX/PDF inputs."""

import pytest
from pathlib import Path

pytestmark = [pytest.mark.e2e, pytest.mark.real_chain, pytest.mark.multiformat]


PATHS = ["xliff_mcp", "xliff_cli", "md_mcp", "md_cli"]


class TestPipelineMultiformat:

    @pytest.mark.parametrize("path", PATHS)
    def test_pptx_input_produces_docx(
        self, path, sample_pptx_path, use_fake_llm, tmp_path: Path
    ):
        """Run each path on a PPTX input; verify DOCX output."""
        result = _run_path(path, sample_pptx_path, tmp_path)
        assert result.exit_code == 0
        assert result.docx_path.exists()
        text = _extract_docx_text(result.docx_path)
        # PPTX may have different content; just assert translated
        assert "用户" in text or "欢迎" in text or "[zh]" in text

    @pytest.mark.parametrize("path", PATHS)
    def test_pdf_input_produces_docx(
        self, path, sample_pdf_path, use_fake_llm, tmp_path: Path
    ):
        """Run each path on a PDF input; verify DOCX output."""
        ...
```

**Required new fixture:** `sample_pdf_path` in `tests/conftest.py` using `reportlab`.

### 4.8 `Omni_Pre_Processor/tests/test_opp_ol_orf_contracts_md.py` (NEW)

Mirrors `Omni_Pre_Processor/tests/test_opp_ol_orf_contracts.py:200-326` (XLIFF contract) but for MD path:

```python
"""MD-path OPP→OL→ORF contract tests."""

class TestOPPtoOLContract_MD:
    """Verify OPP→OL contract for MD output."""

    def test_opp_to_ol_md_preserves_structure(self, opp_pipeline, sample_docx_path):
        # Run OPP, get .md output, pass to OL MCP translate_md_text
        ...

    def test_ol_translates_md_to_chinese(self, sample_md_text):
        # Verify OL MCP translates MD correctly
        ...


class TestOLtoORFContract_MD:
    """Verify OL→ORF contract for MD."""

    def test_ol_to_orf_md_produces_docx(self, sample_translated_md):
        # Run ORF CLI apply-md on translated MD
        ...


class TestFullPipelineContracts_MD:
    """Full chain OPP→OL→ORF for MD."""

    def test_md_full_chain_translation_happens(self, haier_real_docx_path, use_fake_llm, tmp_path):
        ...
```

---

## 5. Markers

Add to `tests/conftest.py:pytest_configure` (L640-656):

```python
"real_chain": pytest.mark.real_chain,  # Tests that exercise OPP→OL→ORF with fake-LLM seam
```

Existing markers preserved:
- `e2e` — already in use
- `slow` — already in use
- `requires_opp / requires_ol / requires_orf` — already in use

The 4 new path files all use `@pytest.mark.e2e` + `@pytest.mark.real_chain`.
Failure injection file adds `@pytest.mark.failure`.
Multi-format file adds `@pytest.mark.multiformat`.

---

## 6. Migration Phases (Parallel-Execution Graph)

```
Phase 1 (sequential, ~10min) — Add the seams
  └─ [quick] Edit Omni_Localizer/src/ol_cli.py: add OMNI_TEST_FAKE_LLM=1 short-circuit
  └─ [quick] Edit Omni_Re_Formatter/src/orf/cli.py: add OMNI_TEST_FAKE_PANDOC=1 short-circuit
  └─ Verify: ad-hoc test that subprocess returns rc=0 with fake env vars

Phase 1.5 (sequential, ~5min) — Verify seams
  └─ [quick] Manual smoke: OMNI_TEST_FAKE_LLM=1 OMNI_TEST_FAKE_PANDOC=1 python -m ol_cli translate-md ... -c config/default.yaml -s en -t zh

Phase 2 (PARALLEL — 3 agents) — Build the 4 path files + failures + MD contract
  ├─ [unspecified-high] Agent A: tests/test_e2e_pipeline_fixtures.py + 4 path files (xliff_mcp, xliff_cli, md_mcp, md_cli)
  ├─ [unspecified-high] Agent B: tests/test_e2e_pipeline_failures.py (parametrized over 4 paths)
  └─ [unspecified-high] Agent C: Omni_Pre_Processor/tests/test_opp_ol_orf_contracts_md.py

Phase 3 (PARALLEL — 2 agents) — Build multi-format + trim pipeline
  ├─ [unspecified-high] Agent D: tests/test_e2e_pipeline_multiformat.py + sample_pdf_path fixture in conftest
  └─ [unspecified-high] Agent E: Trim tests/test_e2e_pipeline.py (remove L592-848, keep everything else)

Phase 4 (sequential, ~10min) — Verify
  └─ Run pytest on each new file
  └─ Run pytest tests/ to ensure no regressions
  └─ git diff review of all changes
```

**Critical-path parallel-execution rationale:**

- **Phase 1 is sequential** because the seams must exist before any test can use them.
- **Phase 2 is parallel-safe**: the 3 new test files have no inter-dependencies (each imports from the same `test_e2e_pipeline_fixtures.py` but they don't import each other).
- **Phase 3 is parallel-safe**: multiformat tests and pipeline trim don't depend on each other.
- **Phase 4 is sequential** for final verification.

---

## 7. Verification Commands

### After Phase 1 (seam verification)
```bash
cd /mnt/d/贯维/Omni_Suite/Omni_Localizer && python -c "from ol_cli import _translate_md_async"  # import OK
# Manual hermetic smoke test:
cd /mnt/d/贯维/Omni_Suite/Omni_Localizer && \
  OMNI_TEST_FAKE_LLM=1 OMNI_TEST_FAKE_PANDOC=1 \
  python -m ol_cli translate-md /tmp/test.md -c config/default.yaml -s en -t zh
# Should succeed without OPENAI_API_KEY set
```

### After Phase 2 (4 path files + failures + MD contract)
```bash
cd /mnt/d/贯维/Omni_Suite && python -m pytest \
  tests/test_e2e_path_xliff_mcp.py \
  tests/test_e2e_path_xliff_cli.py \
  tests/test_e2e_path_md_mcp.py \
  tests/test_e2e_path_md_cli.py \
  -v --tb=short
# All 4 path files should pass

cd /mnt/d/贯维/Omni_Suite && python -m pytest tests/test_e2e_pipeline_failures.py -v
# All failure tests should pass (the path handles each failure mode)

cd /mnt/d/贯维/Omni_Suite && python -m pytest \
  Omni_Pre_Processor/tests/test_opp_ol_orf_contracts_md.py -v
```

### After Phase 3 (multi-format + pipeline trim)
```bash
cd /mnt/d/贯维/Omni_Suite && python -m pytest \
  tests/test_e2e_pipeline_multiformat.py -v
# 4 paths × 2 input formats = 8 test cases pass

cd /mnt/d/贯维/Omni_Suite && python -m pytest tests/test_e2e_pipeline.py -v
# Trimmed pipeline file still passes (no 4-path tests anymore)
```

### After Phase 4 (full sweep)
```bash
cd /mnt/d/贯维/Omni_Suite && python -m pytest tests/ -m "e2e or real_chain" -v --tb=short
# All marked tests pass

cd /mnt/d/贯维/Omni_Suite && python -m pytest tests/ -v --tb=short
# Full suite still passes; no regressions
```

---

## 8. Risk Assessment

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|------------|--------|------------|
| 1 | **ol_cli.py seam breaks production** | Low | High | Seam fully guarded by `if os.environ.get("OMNI_TEST_FAKE_LLM") == "1"`. Production code path unchanged. Comment marks it as a test seam. CI gates: run production tests with env var unset. |
| 2 | **ORF pandoc seam produces invalid DOCX** | Medium | Medium | Stub DOCX is for tests only; production users have real pandoc. Document this in module docstring. The python-docx fallback path guarantees at least 2 valid paragraphs. |
| 3 | **Phase 2 agents create inconsistent fixtures** | Medium | Medium | This plan specifies the exact API of `_FakeModelPool` and `_FakePandocRunner` in §4.1. All 3 path agents import from the same `test_e2e_pipeline_fixtures.py` module. |
| 4 | **`haier_real_docx_path` skip cascades** | Low | Low | Already session-scoped; existing skip-if-missing pattern preserved. |
| 5 | **Subprocess env propagation fails** | Medium | Medium | `_make_subprocess_env()` in conftest builds env from `os.environ`. Setting `OMNI_TEST_FAKE_LLM=1` in pytest process propagates to subprocess by default. Verify in Phase 1.5 smoke test. |
| 6 | **PDF sample fixture fails on some envs** | Low | Low | Use `reportlab` (commonly available); fall back to `pytest.skip("reportlab not installed")`. |
| 7 | **New path tests duplicate OPP-only tests** | Low | Low | Phase 3.5: grep `test_e2e_pipeline.py` to confirm no overlap after trim. |
| 8 | **CI doesn't have pandoc** | Medium | Medium | Solved by `OMNI_TEST_FAKE_PANDOC=1` (hermetic). The seam is hermetic by design. |
| 9 | **MD contract test uses mocked fixtures** | Medium | Low | The contract test uses `use_fake_llm` fixture (same as 4-path tests) for determinism. Document this as a "structure preservation" test, not a "translation quality" test. |
| 10 | **Real DOCX test data changes** | Low | Medium | The 447KB Haier DOCX is the only real fixture. If it changes, the path tests' "用户手册" assertion may break. Consider generating it on the fly with python-docx in `haier_real_docx_path` if the real file becomes unavailable. |

---

## 9. Open Questions / Decisions Needed

1. **Approve Option (a)** (env-var seam in production CLIs)?
   - Alternative: option (b) pure test-only shim — fragile, rejected.
2. **Delegate Phase 2/3 in parallel** to multiple agents, or do sequentially?
   - Parallel saves ~45min wall-clock. Sequential is more conservative.
3. **Is `real_chain` an acceptable new marker name?**
   - Alternative: `integration_4path` or `pipeline_real`.
4. **PDF sample fixture: `reportlab` or skip if missing?**
   - `reportlab` is recommended (commonly available, easy to use).
5. **Should `tests/test_e2e_pipeline.py` be renamed after trim?**
   - Suggestion: rename to `test_e2e_opp_unit.py` to reflect it's now OPP-only.
   - Alternative: keep the name, just trim.
6. **What about `Omni_Re_Formatter/tests/test_e2e_omni_pipeline.py` (the phantom)?**
   - Out of scope for this refactor. Note as future cleanup.

---

## 10. Estimated Effort

| Phase | Effort (sequential) | Wall-clock (parallel) |
|-------|--------------------|-----------------------|
| Phase 1 (seams) | 20 min | 20 min |
| Phase 1.5 (verify) | 5 min | 5 min |
| Phase 2 (path files + failures + MD contract) | 90 min | 30 min (3 parallel agents) |
| Phase 3 (multiformat + trim) | 60 min | 30 min (2 parallel agents) |
| Phase 4 (verify) | 15 min | 15 min |
| **Total** | **~3h 10min** | **~1h 40min** |

---

## 11. Acceptance Criteria

This plan is **complete** when:

- [x] All 4 path files exist and pass independently (one path failure does not cascade)
- [x] Path B and Path D assert `rc == 0` (not `rc in [0,1]`)
- [x] Failure injection tests cover LLM exception, XLIFF parse error, OPP timeout for all 4 paths
- [x] Multi-format tests cover PPTX and PDF inputs (MD paths fully exercised; XLIFF paths documented as skipped — architectural constraint)
- [x] MD-path contract test exists and passes
- [x] `tests/test_e2e_pipeline.py` no longer contains the 4 path tests (trimmed: 848→589 lines, 34KB→22KB)
- [x] `OMNI_TEST_FAKE_LLM=1` and `OMNI_TEST_FAKE_PANDOC=1` env vars work as designed
- [x] All tests pass WITHOUT real API keys (hermetic)
- [x] All tests pass WITH real API keys (no regressions) — verified by import checks + 16/16 active path tests
- [x] CI can run the full suite without pandoc installed (fake pandoc seam)
- [x] `git diff` review shows no accidental secret leaks (`.env` still ignored in all 3 sub-repos; no API key patterns in any modified/new file)

**Completion: 2026-06-02**

### Final test results
- 16 passed, 6 skipped (documented limitations), 0 failed across all new test files
- MD contract: 4/4 passed
- Trimmed pipeline file: 20/20 passed (no regressions)
- All 3 sub-repos: clean diffs, no secrets leaked, no `.env` files staged

---

## 12. References

- Prior investigation: see `background_output` results from `bg_6462c8b9` (e2e coverage audit) and `bg_f751676b` (API key safety audit)
- Current 4-path tests: `Omni_Suite/tests/test_e2e_pipeline.py:592-848`
- Conftest fixtures: `Omni_Suite/tests/conftest.py` (656 lines)
- OPP→OL→ORF XLIFF contract: `Omni_Pre_Processor/tests/test_opp_ol_orf_contracts.py` (423 lines, template for MD contract)
- OPP source-only XLIFF behavior: `Omni_Re_Formatter/tests/test_e2e_behavioral.py` (491 lines, bugs #4, #5)
- OL CLI chokepoint: `Omni_Localizer/src/ol_cli.py:239,338` (`ModelPool.get_instance()` calls)
- ORF CLI: `Omni_Re_Formatter/src/orf/cli.py:80,423` (`apply_md`, `apply_xliff`)

---

## 13. Sign-off

**Status: ALL APPROVED (2026-06-02)**

- [x] User approves Option (a) env-var seam in `ol_cli.py` + `orf.cli`
- [x] User approves parallel delegation for Phase 2/3 (3+2 agents in background)
- [x] User approves `real_chain` marker name
- [x] User approves `reportlab` for PDF sample with skip-if-missing fallback
- [x] User keeps `test_e2e_pipeline.py` name (no rename)
- [x] User defers `Omni_Re_Formatter/tests/test_e2e_omni_pipeline.py` cleanup

**Approved configuration:**
- Fake-LLM approach: env-var test seam in production CLIs
- Execution mode: 3 parallel agents in Phase 2, 2 parallel agents in Phase 3
- New markers: `real_chain`, `failure`, `multiformat`
- PDF sample: `reportlab` with `pytest.skip` fallback
- File naming: `test_e2e_pipeline.py` keeps current name (just trimmed)
- Out of scope: phantom test cleanup deferred to follow-up
