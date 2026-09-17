#!/usr/bin/env python3
"""L3 OMO loop wrapper for Omni Suite.

Per cycle:
  1. Run OPP→OL→ORF pipeline (scripts/run_pipeline.py)
  2. Check 5-6 cheap gates
  3. All GREEN? increment consecutive_green
  4. RED? diagnose + try safe fix whitelist + re-run
  5. Termination: consecutive_green ≥ 3 → converged
  6. Critical blocker: consecutive_fix_fail ≥ 5 → report

Safe fix whitelist:
  - Re-run with --no-cache
  - Clear OPP cache
  - Switch translation model (use next priority)
  - Adjust timeout (within ±30s)
  - Adjust max_xliff_concurrent (5-40)
  - Re-run with mock LLM (isolate real-LLM vs structural)
  - Restart subprocess

NOT in whitelist (require user):
  - Change model pool
  - Change gate definitions
  - Change temperature/judge config
  - Change schema/contracts
  - Skip cycle
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Paths
_SUITE_ROOT = Path(__file__).resolve().parents[1]
_VENV_PYTHON = _SUITE_ROOT / ".venv_ol" / "bin" / "python"
_RUN_PIPELINE = _SUITE_ROOT / "scripts" / "run_pipeline.py"
_OMNI_LOCALIZER_SRC = _SUITE_ROOT / "Omni_Localizer" / "src"
_OMNI_LOCALIZER_ENV = _SUITE_ROOT / "Omni_Localizer" / ".env"
_DEFAULT_CONFIG = _SUITE_ROOT / "Omni_Localizer" / "config" / "local.yaml"
_DEFAULT_FIXTURE = _SUITE_ROOT / "scenarios" / "_fixtures" / "haier_ch2_zh.docx"
_OMO_RUNS_DIR = _SUITE_ROOT / "test_artifacts" / "omo_runs"


@dataclass
class GateResult:
    """Result of a single gate check."""

    name: str
    passed: bool
    score: float
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "score": self.score,
            "details": self.details,
        }


@dataclass
class CycleArtifacts:
    """Files produced by a single pipeline run."""

    cycle_dir: Path
    source_docx: Path
    output_docx: Path | None
    opp_xlf: Path | None
    opp_manifest: Path | None
    opp_skeleton: Path | None
    opp_images: Path | None
    ol_xlf: Path | None
    exit_code: int
    duration_s: float
    stderr_tail: str = ""

    def to_dict(self) -> dict:
        return {
            "cycle_dir": str(self.cycle_dir),
            "output_docx": str(self.output_docx) if self.output_docx else None,
            "opp_xlf": str(self.opp_xlf) if self.opp_xlf else None,
            "ol_xlf": str(self.ol_xlf) if self.ol_xlf else None,
            "exit_code": self.exit_code,
            "duration_s": self.duration_s,
        }


def _build_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Build subprocess env with .env loaded and PYTHONPATH set."""
    env = os.environ.copy()
    if _OMNI_LOCALIZER_ENV.exists():
        for line in _OMNI_LOCALIZER_ENV.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                env.setdefault(k.strip(), v.strip())
    pp = env.get("PYTHONPATH", "")
    src = str(_OMNI_LOCALIZER_SRC)
    env["PYTHONPATH"] = f"{src}{os.pathsep}{pp}" if pp else src
    if extra:
        env.update(extra)
    return env


def _run_pipeline(
    input_path: Path,
    output_dir: Path,
    *,
    source_lang: str = "zh",
    target_lang: str = "en",
    config_path: Path | None = None,
    use_mock: bool = False,
    timeout: int = 1200,
) -> CycleArtifacts:
    """Run scripts/run_pipeline.py and capture artifacts + exit status."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cfg = config_path or _DEFAULT_CONFIG
    cmd = [
        str(_VENV_PYTHON),
        str(_RUN_PIPELINE),
        str(input_path),
        "-s", source_lang,
        "-t", target_lang,
        "-o", str(output_dir),
        "-c", str(cfg),
    ]
    if use_mock:
        cmd.append("--mock-llm")

    env = _build_env({"OMNI_TEST_FAKE_LLM": "1"} if use_mock else None)
    t0 = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return CycleArtifacts(
            cycle_dir=output_dir,
            source_docx=input_path,
            output_docx=None,
            opp_xlf=None,
            opp_manifest=None,
            opp_skeleton=None,
            opp_images=None,
            ol_xlf=None,
            exit_code=124,
            duration_s=time.monotonic() - t0,
            stderr_tail=f"TIMEOUT after {timeout}s",
        )
    duration = time.monotonic() - t0

    stem = input_path.stem
    opp_out = output_dir / "opp_out"
    ol_out = output_dir / "ol_out"
    orf_out = output_dir / "orf_out"

    return CycleArtifacts(
        cycle_dir=output_dir,
        source_docx=input_path,
        output_docx=orf_out / f"{stem}.docx",
        opp_xlf=opp_out / f"{stem}.xlf",
        opp_manifest=opp_out / f"{stem}_manifest.json",
        opp_skeleton=opp_out / f"{stem}.skeleton.zip",
        opp_images=opp_out / f"{stem}_images.json",
        ol_xlf=ol_out / f"{stem}.xlf",
        exit_code=result.returncode,
        duration_s=duration,
        stderr_tail=(result.stderr or "")[-2000:],
    )


# ── Gate implementations ─────────────────────────────────────────────────

def _gate_q1_functional(art: CycleArtifacts) -> GateResult:
    """Q1: pipeline exit 0 + output DOCX exists + python-docx can open."""
    if art.exit_code != 0:
        return GateResult("Q1_functional", False, 0.0, f"exit={art.exit_code}; stderr={art.stderr_tail[-200:]}")
    if not art.output_docx or not art.output_docx.exists():
        return GateResult("Q1_functional", False, 0.0, "output DOCX missing")
    try:
        from docx import Document
        doc = Document(str(art.output_docx))
        para_count = len(doc.paragraphs)
    except Exception as e:
        return GateResult("Q1_functional", False, 0.0, f"python-docx open failed: {e}")
    if para_count == 0:
        return GateResult("Q1_functional", False, 0.5, "DOCX has 0 paragraphs")
    return GateResult("Q1_functional", True, 1.0, f"exit 0, DOCX opens, {para_count} paragraphs")


def _gate_q4_image(art: CycleArtifacts, source_docx: Path) -> GateResult:
    """Q4: drawing count in output == source."""
    def _count_drawings(p: Path) -> int:
        try:
            with zipfile.ZipFile(p) as z:
                if "word/document.xml" not in z.namelist():
                    return 0
                return z.read("word/document.xml").decode("utf-8", errors="ignore").count("<w:drawing")
        except Exception:
            return 0

    if not art.output_docx or not art.output_docx.exists():
        return GateResult("Q4_image", False, 0.0, "output DOCX missing")
    src_count = _count_drawings(source_docx)
    out_count = _count_drawings(art.output_docx)
    if src_count == out_count and src_count > 0:
        return GateResult("Q4_image", True, 1.0, f"drawings: src={src_count} out={out_count} (match)")
    if src_count == 0:
        return GateResult("Q4_image", False, 0.0, "source has 0 drawings; cannot compare")
    return GateResult("Q4_image", False, 0.0, f"drawings: src={src_count} out={out_count} (mismatch)")


def _gate_q5_punctuation(art: CycleArtifacts, target_lang: str) -> GateResult:
    """Q5: 0 Chinese punctuation in English output (or 0 ASCII in Chinese output)."""
    if not art.output_docx or not art.output_docx.exists():
        return GateResult("Q5_punct", False, 0.0, "output DOCX missing")
    try:
        from docx import Document
        doc = Document(str(art.output_docx))
        text = "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        return GateResult("Q5_punct", False, 0.0, f"python-docx failed: {e}")

    if target_lang.startswith("en"):
        # 0 Chinese punctuation: U+201C/D (curly quotes), U+FF0C (full-width comma), U+3002 (full-width period)
        chinese_punct = re.findall(r"[\u201c\u201d\u2018\u2019\uff0c\u3002\uff1a\uff1b\uff01\uff1f]", text)
        if len(chinese_punct) == 0:
            return GateResult("Q5_punct", True, 1.0, "0 Chinese punctuation chars")
        return GateResult("Q5_punct", False, 0.0, f"{len(chinese_punct)} Chinese punct chars in English output")
    else:
        # Chinese output: 0 ASCII ,.;: should appear (they should be full-width)
        ascii_punct_in_body = re.findall(r"[,.;:](?=\s|$)", text)
        if len(ascii_punct_in_body) == 0:
            return GateResult("Q5_punct", True, 1.0, "0 ASCII punct in body text")
        return GateResult("Q5_punct", False, 0.0, f"{len(ascii_punct_in_body)} ASCII punct in body text")


def _gate_q6_roundtrip(art: CycleArtifacts, source_docx: Path) -> GateResult:
    """Q6: paragraph count within ±5% of source."""
    def _count_para(p: Path) -> int:
        try:
            from docx import Document
            return len(Document(str(p)).paragraphs)
        except Exception:
            return 0

    if not art.output_docx or not art.output_docx.exists():
        return GateResult("Q6_roundtrip", False, 0.0, "output DOCX missing")
    src_n = _count_para(source_docx)
    out_n = _count_para(art.output_docx)
    if src_n == 0:
        return GateResult("Q6_roundtrip", False, 0.0, "source has 0 paragraphs")
    ratio = out_n / src_n
    if 0.95 <= ratio <= 1.05:
        return GateResult("Q6_roundtrip", True, 1.0, f"src={src_n} out={out_n} ratio={ratio:.2%}")
    return GateResult("Q6_roundtrip", False, 0.0, f"src={src_n} out={out_n} ratio={ratio:.2%} (out of ±5%)")


def _gate_q3_glossary(art: CycleArtifacts, source_docx: Path) -> GateResult:
    """Q3: translation completeness — Chinese-char ratio in output < 5%.

    Replaces the old top-10-term check (which false-positived on brand
    names like 海尔→Haier that legitimately preserve the source chars).
    A real translation leaves only a few stray CJK chars (brand names,
    proper nouns) — we tolerate up to 5% CJK density.
    """
    if not art.output_docx or not art.output_docx.exists():
        return GateResult("Q3_glossary", False, 0.0, "output DOCX missing")
    try:
        from docx import Document
        out_doc = Document(str(art.output_docx))
        out_text = "\n".join(p.text for p in out_doc.paragraphs)
    except Exception as e:
        return GateResult("Q3_glossary", False, 0.0, f"python-docx failed: {e}")

    if not out_text.strip():
        return GateResult("Q3_glossary", False, 0.0, "output text empty")
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", out_text)
    ratio = len(chinese_chars) / len(out_text)
    if ratio < 0.05:
        return GateResult("Q3_glossary", True, 1.0, f"CJK ratio {ratio:.2%} (< 5%; brand names/proper nouns tolerated)")
    return GateResult("Q3_glossary", False, 0.0, f"CJK ratio {ratio:.2%} (≥ 5%; translation incomplete)")


def _gate_q2_lqa(art: CycleArtifacts, source_docx: Path, target_lang: str,
                 max_units: int = 50) -> GateResult:
    """Q2: LLM-judged translation quality. Avg score ≥ 4.0/5 over first N units.

    Uses OL's JudgeService on the first `max_units` (trans-unit id and
    source/target) from the translated XLIFF. Skips units whose <target>
    is whitespace-only (failed translation). Each judge call is one
    LLM round-trip; ~50 units ≈ 50s + ~50K tokens per cycle.
    """
    if not art.ol_xlf or not art.ol_xlf.exists():
        return GateResult("Q2_lqa", False, 0.0, "OL XLIFF missing")

    try:
        xlf_text = art.ol_xlf.read_text(encoding="utf-8")
    except Exception as e:
        return GateResult("Q2_lqa", False, 0.0, f"OL XLIFF read failed: {e}")

    pairs: list[tuple[str, str, str]] = []
    for m in re.finditer(r'<trans-unit[^>]*id="([^"]+)"[^>]*>.*?<source[^>]*>(.*?)</source>\s*<target[^>]*>(.*?)</target>', xlf_text, re.DOTALL):
        unit_id, source_raw, target_raw = m.group(1), m.group(2), m.group(3)
        source = re.sub(r"<[^>]+>", "", source_raw).strip()
        target = re.sub(r"<[^>]+>", "", target_raw).strip()
        if source and target and target != source:
            pairs.append((unit_id, source, target))
        if len(pairs) >= max_units:
            break

    if not pairs:
        return GateResult("Q2_lqa", False, 0.0, "no scorable unit pairs in OL XLIFF")

    try:
        from ol_lqa.judge import JudgeService
        from ol_pool.router import ModelPool
        from ol_config.loader import load_config
    except ImportError as e:
        return GateResult("Q2_lqa", False, 0.0, f"judge import failed: {e}")

    try:
        cfg, _ = load_config(str(_DEFAULT_CONFIG))
        pool = ModelPool.get_instance(str(_DEFAULT_CONFIG))
    except Exception as e:
        return GateResult("Q2_lqa", False, 0.0, f"judge pool init failed: {e}")

    try:
        # Pass threshold on the user-facing 0-5 scale.
        # (JudgeService.pass_threshold is on 0-1 post-_rescale scale, but
        # we display in /5 to match the user's "LQA ≥ 4.0/5" goal.)
        pass_threshold_5 = 4.0
        judge = JudgeService(pass_threshold=pass_threshold_5, model_pool=pool)
    except Exception as e:
        return GateResult("Q2_lqa", False, 0.0, f"JudgeService init failed: {e}")

    import asyncio, time
    async def _judge_all() -> list:
        tasks = [
            judge.judge(src, tgt, unit_id, source_lang="zh", target_lang=target_lang)
            for unit_id, src, tgt in pairs
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)

    t0 = time.monotonic()
    try:
        results = asyncio.run(_judge_all())
    except Exception as e:
        return GateResult("Q2_lqa", False, 0.0, f"judge gather failed: {e}")
    elapsed = time.monotonic() - t0

    scores_01: list[float] = []
    transport_errs = 0
    for r in results:
        if isinstance(r, Exception):
            transport_errs += 1
            continue
        try:
            if hasattr(r, "judge_overall_score"):
                scores_01.append(float(r.judge_overall_score))
            elif isinstance(r, dict) and "score" in r:
                scores_01.append(float(r["score"]))
        except Exception:
            transport_errs += 1

    if not scores_01:
        return GateResult("Q2_lqa", False, 0.0, f"all {transport_errs} judge calls failed; {elapsed:.1f}s")

    avg_10 = sum(scores_01) / len(scores_01)
    avg_5 = avg_10 / 2.0
    if avg_5 >= pass_threshold_5:
        return GateResult(
            "Q2_lqa", True, avg_5,
            f"avg LQA {avg_5:.2f}/5 (≥ {pass_threshold_5}); n={len(scores_01)}, transport_errs={transport_errs}, {elapsed:.1f}s",
        )
    return GateResult(
        "Q2_lqa", False, 0.0,
        f"avg LQA {avg_5:.2f}/5 (< {pass_threshold_5}); n={len(scores_01)}, transport_errs={transport_errs}, {elapsed:.1f}s",
    )


def _gate_q7_reproducibility(
    cur_art: CycleArtifacts,
    _prev_artifacts: dict | None,
    args,
) -> GateResult:
    """Q7: reproducibility between consecutive cycles.

    Compares the current cycle's DOCX against the previous cycle's DOCX
    using the already-available artifacts — no extra pipeline re-run needed.

    Two modes:
    - Mock LLM (--use-mock): content-level paragraph text overlap ≥ 95%
      (deterministic — should be near identical).
    - Real LLM (default): structural reproducibility — paragraph count and
      drawing count must be stable. Content naturally differs between runs due
      to LLM temperature, so structural fidelity is the meaningful signal.
    """
    if _prev_artifacts is None:
        return GateResult(
            "Q7_reproducibility", True, 1.0,
            "no previous cycle to compare; trivial pass (first cycle baseline)",
        )
    prev_docx = _prev_artifacts.get("output_docx")
    if not prev_docx or not Path(prev_docx).exists():
        return GateResult("Q7_reproducibility", False, 0.0, "previous output DOCX missing")
    if not cur_art.output_docx or not cur_art.output_docx.exists():
        return GateResult("Q7_reproducibility", False, 0.0, "current output DOCX missing")

    def _extract_paragraphs(p: Path) -> list[str]:
        try:
            from docx import Document
            return [para.text.strip() for para in Document(str(p)).paragraphs if para.text.strip()]
        except Exception:
            return []

    def _count_drawings(p: Path) -> int:
        try:
            from docx import Document
            body = Document(str(p)).element.body
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            return len(body.xpath(".//w:drawing", namespaces=ns))
        except Exception:
            return -1

    prev_paras = _extract_paragraphs(Path(prev_docx))
    cur_paras = _extract_paragraphs(cur_art.output_docx)
    if not prev_paras or not cur_paras:
        return GateResult("Q7_reproducibility", False, 0.0, "one or both outputs have 0 paragraphs")

    if args.use_mock:
        set_prev, set_cur = set(prev_paras), set(cur_paras)
        intersection = set_prev & set_cur
        overlap = len(intersection) / max(len(set_prev), len(set_cur))
        if overlap >= 0.95:
            return GateResult(
                "Q7_reproducibility", True, overlap,
                f"paragraph overlap {overlap:.2%} (≥ 95%); n_prev={len(prev_paras)}, n_cur={len(cur_paras)} (mock LLM)",
            )
        return GateResult(
            "Q7_reproducibility", False, 0.0,
            f"paragraph overlap {overlap:.2%} (< 95%); n_prev={len(prev_paras)}, n_cur={len(cur_paras)} (mock LLM)",
        )

    prev_drawings = _count_drawings(Path(prev_docx))
    cur_drawings = _count_drawings(cur_art.output_docx)
    issues: list[str] = []

    max_cnt = max(len(prev_paras), len(cur_paras))
    min_cnt = min(len(prev_paras), len(cur_paras))
    para_ratio = min_cnt / max_cnt if max_cnt > 0 else 0
    if para_ratio < 0.8:
        issues.append(f"paragraph count drift: {len(prev_paras)}→{len(cur_paras)}")
    if prev_drawings >= 0 and cur_drawings >= 0 and prev_drawings != cur_drawings:
        issues.append(f"drawing count: {prev_drawings}→{cur_drawings}")
    if cur_art.exit_code != 0:
        issues.append(f"pipeline exit={cur_art.exit_code}")

    if not issues:
        return GateResult(
            "Q7_reproducibility", True, 1.0,
            f"structural OK; {len(prev_paras)}/{len(cur_paras)} paras, {prev_drawings}/{cur_drawings} drawings (real LLM)",
        )
    return GateResult("Q7_reproducibility", False, 0.0, "; ".join(issues) + " (real LLM)")


def _gate_q8_code_health() -> GateResult:
    """Q8: collect-only pytest on OPP+OL+ORF+suite test directories.

    Soft gate: catches import errors, syntax errors, and collection
    failures (which would mean the test infra is broken). Pre-existing
    test failures are documented but not surfaced as gate failures
    here — Q8 is about test infrastructure health, not test pass rate.
    Catches import / syntax errors in ~5-10s per cycle.
    """
    import subprocess
    test_paths = [
        "Omni_Pre_Processor/tests",
        "Omni_Localizer/tests",
        "Omni_Re_Formatter/tests",
        "tests",
    ]
    env = _build_env()
    env["OMNI_TEST_FAKE_LLM"] = "1"
    env["OMNI_TEST_FAKE_PANDOC"] = "1"
    overall_ok = True
    details: list[str] = []
    for tp in test_paths:
        full = _SUITE_ROOT / tp
        if not full.exists():
            continue
        t0 = time.monotonic()
        try:
            result = subprocess.run(
                [str(_VENV_PYTHON), "-m", "pytest", str(full), "--collect-only", "-q", "--tb=no"],
                capture_output=True, text=True, env=env, timeout=60,
            )
            elapsed = time.monotonic() - t0
            ok = result.returncode == 0
            details.append(f"{tp}: {'OK' if ok else 'COLLECT-FAIL'} ({elapsed:.0f}s)")
            if not ok:
                overall_ok = False
        except subprocess.TimeoutExpired:
            details.append(f"{tp}: TIMEOUT")
            overall_ok = False

    if overall_ok:
        return GateResult("Q8_code_health", True, 1.0, "; ".join(details))
    return GateResult("Q8_code_health", False, 0.0, "; ".join(details))


def check_all_gates(art: CycleArtifacts, source_docx: Path, target_lang: str) -> list[GateResult]:
    """Run all cheap gates + Q2 LQA against a cycle's artifacts."""
    return [
        _gate_q1_functional(art),
        _gate_q2_lqa(art, source_docx, target_lang),
        _gate_q3_glossary(art, source_docx),
        _gate_q4_image(art, source_docx),
        _gate_q5_punctuation(art, target_lang),
        _gate_q6_roundtrip(art, source_docx),
    ]


# ── Diagnosis & safe fix whitelist ───────────────────────────────────────

def diagnose(art: CycleArtifacts, gates: list[GateResult]) -> str:
    """Produce a human-readable diagnosis from artifacts + gate failures."""
    if art.exit_code == 124:
        return "TIMEOUT: pipeline exceeded 1200s. Likely cause: real LLM slow or hung. Suggested fix: try mock LLM to isolate."
    if art.exit_code != 0:
        tail = art.stderr_tail.splitlines()[-10:]
        return f"NON-ZERO EXIT (code={art.exit_code}). Last stderr lines:\n" + "\n".join("  " + l for l in tail)
    failed = [g for g in gates if not g.passed]
    if not failed:
        return "All checked gates GREEN; no diagnosis needed."
    lines = ["Gate failures:"]
    for g in failed:
        lines.append(f"  - {g.name}: {g.details}")
    return "\n".join(lines)


def try_safe_fix(diagnosis: str, cycle_dir: Path) -> dict | None:
    """Try one safe action from the whitelist. Returns fix info or None.

    Safe actions (in priority order):
      1. Clear OPP cache (~/.omni_cache/opp/) — old cached XLIFF might be bad
      2. Try again with --mock-llm — isolate real-LLM vs structural issues
      3. (no further automatic actions; require user)
    """
    opp_cache = Path.home() / ".omni_cache" / "opp"
    if opp_cache.exists():
        try:
            import shutil
            shutil.rmtree(opp_cache)
            return {"fix": "clear_opp_cache", "path": str(opp_cache)}
        except Exception as e:
            return {"fix": "clear_opp_cache", "error": str(e)}
    return None


# ── Reporting ────────────────────────────────────────────────────────────

def write_cycle_report(cycle_num: int, status: str, art: CycleArtifacts,
                       gates: list[GateResult], diagnosis: str,
                       fix: dict | None, summary_path: Path) -> None:
    """Write a 1-page Markdown report for a single cycle."""
    lines = [
        f"# OMO Cycle {cycle_num} — {status}",
        "",
        f"**Timestamp**: {datetime.now().isoformat()}",
        f"**Duration**: {art.duration_s:.1f}s",
        f"**Exit code**: {art.exit_code}",
        "",
        "## Gates",
        "",
        "| Gate | Status | Score | Details |",
        "|------|--------|-------|---------|",
    ]
    for g in gates:
        status_str = "✅ PASS" if g.passed else "❌ FAIL"
        lines.append(f"| {g.name} | {status_str} | {g.score:.2f} | {g.details} |")

    lines.extend([
        "",
        "## Artifacts",
        "",
        f"- Output DOCX: `{art.output_docx}`",
        f"- OP XLIFF: `{art.opp_xlf}`",
        f"- OL XLIFF: `{art.ol_xlf}`",
        "",
        "## Diagnosis",
        "",
        "```",
        diagnosis,
        "```",
        "",
        "## Fix Attempt",
        "",
        f"```json\n{json.dumps(fix, indent=2)}\n```" if fix else "_No fix attempted this cycle._",
        "",
    ])

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(lines), encoding="utf-8")


# ── Main loop ────────────────────────────────────────────────────────────

@dataclass
class LoopState:
    cycle: int = 0
    consecutive_green: int = 0
    consecutive_fix_fail: int = 0
    fix_log: list[dict] = field(default_factory=list)
    last_status: str = "init"
    history: list[dict] = field(default_factory=list)
    prev_artifacts: dict | None = None  # Q7 reproducibility baseline

    def to_dict(self) -> dict:
        prev = self.prev_artifacts
        if prev is not None and "output_docx" in prev:
            prev_for_json = {**prev, "output_docx": str(prev["output_docx"])}
        else:
            prev_for_json = prev
        return {
            "cycle": self.cycle,
            "consecutive_green": self.consecutive_green,
            "consecutive_fix_fail": self.consecutive_fix_fail,
            "fix_log": self.fix_log,
            "last_status": self.last_status,
            "history": self.history[-20:],
            "prev_artifacts": prev_for_json,
        }


# ── Tier 2-5: dispatch to existing infrastructure ────────────────────────
# 2026-06-17 round 7: omo_loop.py Tier 1 owns the gate-convergence loop.
# Tier 2-5 delegate to assets that already do the work.


def _run_tier_2(args) -> int:
    """Tier 2: invoke tests/e2e_runner.py for all 4 paths on --input."""
    import subprocess
    import sys

    suite_root = Path(__file__).resolve().parent.parent
    e2e_runner = suite_root / "tests" / "e2e_runner.py"
    cmd = [
        sys.executable, str(e2e_runner),
        "--input", str(args.input),
        "--source-lang", args.source_lang,
        "--target-lang", args.target_lang,
    ]
    print(f"Tier 2 → delegating to {e2e_runner.name} for all 4 paths")
    print(f"  cmd: {' '.join(cmd)}")
    rc = subprocess.run(cmd, env=os.environ.copy()).returncode
    return rc


def _run_tier_3(args) -> int:
    """Tier 3: invoke scripts/phase1_runner.py P1 (10 formats × 2 langs MD).

    phase1_runner's build_matrix() already iterates both directions,
    so a single invocation runs all 20 cases. Passing
    --source-lang/--target-lang would be silently ignored (round 10
    caught the round 7 dispatch over-specifying these args).
    """
    import subprocess
    import sys

    suite_root = Path(__file__).resolve().parent.parent
    phase1 = suite_root / "scripts" / "phase1_runner.py"
    cmd = [
        sys.executable, str(phase1),
        "--tier", "P1",
        "--run-id", f"tier3_{args.source_lang}_{args.target_lang}",
    ]
    print(f"Tier 3 → delegating to {phase1.name} P1 (10 formats × 2 langs MD)")
    print(f"  cmd: {' '.join(cmd)}")
    return subprocess.run(cmd, env=os.environ.copy()).returncode


def _run_tier_4(args) -> int:
    """Tier 4: invoke scripts/phase1_runner.py P2 (docx+pptx × 2 langs XLIFF)."""
    import subprocess
    import sys

    suite_root = Path(__file__).resolve().parent.parent
    phase1 = suite_root / "scripts" / "phase1_runner.py"
    cmd = [
        sys.executable, str(phase1),
        "--tier", "P2",
        "--run-id", f"tier4_{args.source_lang}_{args.target_lang}",
    ]
    print(f"Tier 4 → delegating to {phase1.name} P2 (XLIFF backfill matrix)")
    print(f"  cmd: {' '.join(cmd)}")
    return subprocess.run(cmd, env=os.environ.copy()).returncode


def _run_tier_5(args) -> int:
    """Tier 5: run module-only pytest tests for each module.

    2026-06-17 round 11 v2: switched from run_test.sh to pytest.
    run_test.sh --module is NOT actually module-only — it assumes
    OPP step ran first (the script prepares a doc + runs OPP
    before OL/ORF). The right tool for "3 modules verified
    independently" is the existing per-module pytest suites:
      - OPP: tests/test_e2e_opp_all_formats.py + test_e2e_opp_cli.py
      - OL:  tests/test_e2e_ol_cli.py + test_e2e_ol_mcp.py
      - ORF: tests/test_e2e_orf_cli.py + test_e2e_orf_mcp.py

    The per-module pytest suites were the original "老规矩"
    comprehensive runner before OMO. Tier 5 re-uses them.
    """
    import subprocess

    suite_root = Path(__file__).resolve().parent.parent
    venv_py = suite_root / ".venv_ol" / "bin" / "python"

    module_tests = {
        "opp": [
            "tests/test_e2e_opp_all_formats.py",
            "tests/test_e2e_opp_cli.py",
        ],
        "ol": [
            "tests/test_e2e_ol_cli.py",
            "tests/test_e2e_ol_mcp.py",
        ],
        "orf": [
            "tests/test_e2e_orf_cli.py",
            "tests/test_e2e_orf_mcp.py",
        ],
    }

    rc_total = 0
    for module, test_files in module_tests.items():
        print(f"\nTier 5 → module={module}")
        for tf in test_files:
            cmd = [
                str(venv_py), "-m", "pytest", tf, "-v", "--tb=short", "-q",
            ]
            print(f"  cmd: {' '.join(cmd)}")
            rc = subprocess.run(cmd, env=os.environ.copy()).returncode
            if rc != 0:
                rc_total = rc
                print(f"  ❌ {tf} failed rc={rc}")
            else:
                print(f"  ✅ {tf} OK")
    return rc_total


def _run_format_matrix(args) -> int:
    """Tier 7 (2026-06-21): run the format matrix verifier.

    Iterates input × output combinations end-to-end and reports
    pass/skip/fail per cell. Exits 0 if all non-skipped cells pass.
    """
    suite_root = _SUITE_ROOT
    script = suite_root / "scripts" / "format_matrix_verifier.py"
    if not script.exists():
        print(f"[Tier7] ERROR: {script} not found", file=sys.stderr, flush=True)
        return 1
    env = _build_env({"OMNI_TEST_FAKE_LLM": "1", "OMNI_TEST_FAKE_PANDOC": "1"})
    t0 = time.monotonic()
    result = subprocess.run(
        [sys.executable, str(script), "--suite-root", str(suite_root)],
        capture_output=True, text=True, env=env, cwd=str(suite_root), timeout=3600,
    )
    elapsed = time.monotonic() - t0
    print(f"[Tier7] exit={result.returncode} in {elapsed:.1f}s", flush=True)
    return result.returncode


def _run_tier8(args) -> int:
    """Tier 8 (2026-06-21): run the real corpus + fidelity + equivalence gate.

    Steps:
      1. Run format matrix with --corpus real --fidelity against test_corpus/
         (complex DOCX/PPTX/PDF/XLSX/HTML with tables, images, formatting)
      2. Run equivalence check between two CLI runs (deterministic with
         FAKE_LLM, so all cells should be equivalent; catches any
         nondeterminism in the pipeline)
      3. Attempt MCP matrix (currently blocked: fastmcp 3.x servers don't
         accept stdio in this env — see ACCEPTED_GAPS.md)

    Exits 0 only if the CLI real-corpus matrix passes (0 FAIL) AND the
    equivalence check reports no divergent cells. MCP step is reported
    but does not block the gate (it's a known gap).
    """
    suite_root = _SUITE_ROOT
    t0 = time.monotonic()
    out_a = suite_root / "test_artifacts" / "matrix_real_a"
    out_b = suite_root / "test_artifacts" / "matrix_real_b"

    env = _build_env({"OMNI_TEST_FAKE_LLM": "1", "OMNI_TEST_FAKE_PANDOC": "1"})

    # Step 1: Run CLI matrix with real corpus + fidelity (run A)
    print(f"[Tier8] Step 1: CLI matrix with real corpus (run A) → {out_a}")
    r1 = subprocess.run(
        [sys.executable, str(suite_root / "scripts" / "format_matrix_verifier.py"),
         "--suite-root", str(suite_root),
         "--out-dir", str(out_a),
         "--corpus", "real", "--fidelity",
         "--path-filter", "both", "--parallel", "8", "--timeout", "120"],
        capture_output=True, text=True, env=env, cwd=str(suite_root), timeout=3600,
    )
    a_pass = r1.returncode == 0
    print(f"[Tier8]   run A exit={r1.returncode}")

    # Step 2: Run again (run B) to test equivalence/determinism
    print(f"[Tier8] Step 2: CLI matrix with real corpus (run B) → {out_b}")
    r2 = subprocess.run(
        [sys.executable, str(suite_root / "scripts" / "format_matrix_verifier.py"),
         "--suite-root", str(suite_root),
         "--out-dir", str(out_b),
         "--corpus", "real", "--fidelity",
         "--path-filter", "both", "--parallel", "8", "--timeout", "120"],
        capture_output=True, text=True, env=env, cwd=str(suite_root), timeout=3600,
    )
    b_pass = r2.returncode == 0
    print(f"[Tier8]   run B exit={r2.returncode}")

    # Step 3: Equivalence check between A and B
    print("[Tier8] Step 3: equivalence check (run A vs B)")
    r3 = subprocess.run(
        [sys.executable, str(suite_root / "scripts" / "equivalence_checker.py"),
         "--a-dir", str(out_a), "--b-dir", str(out_b),
         "--a-label", "run_A", "--b-label", "run_B",
         "--json"],
        capture_output=True, text=True, env=env, cwd=str(suite_root), timeout=300,
    )
    equiv_pass = r3.returncode == 0
    if r3.stdout:
        try:
            import json as _json
            data = _json.loads(r3.stdout)
            print(f"[Tier8]   equivalent: {data.get('equivalent', 0)}/"
                  f"{data.get('total', 0)} | divergent: {data.get('divergent', 0)}")
        except _json.JSONDecodeError:
            pass
    print(f"[Tier8]   equivalence exit={r3.returncode}")

    # Step 4: MCP matrix via raw-stdio bridge (c6197f8). Should now PASS
    # because the bridge bypasses the FastMCP 3.4.2 stdio bug.
    print("[Tier8] Step 4: MCP matrix via raw-stdio bridge")
    r4 = subprocess.run(
        [sys.executable, str(suite_root / "scripts" / "mcp_matrix_verifier.py"),
         "--out-dir", str(suite_root / "test_artifacts" / "mcp_test"),
         "--path-filter", "md", "--subset", "docx"],
        capture_output=True, text=True, env=env, cwd=str(suite_root), timeout=300,
    )
    mcp_pass = r4.returncode == 0
    print(f"[Tier8]   MCP matrix exit={r4.returncode} (passed={mcp_pass})")

    elapsed = time.monotonic() - t0
    print(f"[Tier8] Total: {elapsed:.1f}s | "
          f"runA={'PASS' if a_pass else 'FAIL'} | "
          f"runB={'PASS' if b_pass else 'FAIL'} | "
          f"equivalence={'PASS' if equiv_pass else 'FAIL'} | "
          f"MCP={'PASS' if mcp_pass else 'FAIL'}")
    # Gate passes only if all 4 steps pass: CLI×2 + equivalence + MCP.
    return 0 if (a_pass and b_pass and equiv_pass and mcp_pass) else 1


def _run_verify_all(
    args,
    verifiers: list[tuple[str, Path, list[str]]] | None = None,
    out_dir: Path | None = None,
) -> int:
    """Tier 6 (2026-06-21): aggregate the 3 verifiers into a single matrix.

    Runs:
      - scripts/check_readiness.py --readiness  (60 V1–V11 checks)
      - scripts/verify_usability.py             (CLI + MCP usability matrix)
      - scripts/verify_mcp.py                   (MCP smoke tests)

    Exits 0 only if all three return 0. Writes a markdown matrix to
    test_artifacts/omo_runs/verify_all_<timestamp>.md so downstream tools
    and the convergence report can consume it.

    Args:
        args: CLI args (unused; reserved for future per-call overrides).
        verifiers: Optional override of the verifier list. Each entry is
            (name, script_path, extra_args). Used by tests to inject
            fake/missing verifiers without touching the real scripts.
        out_dir: Optional override of the report output directory.
    """
    try:
        return _run_verify_all_inner(args, verifiers, out_dir)
    except Exception as e:
        print(f"[Tier6] FATAL: unhandled exception: {type(e).__name__}: {e}",
              file=sys.stderr, flush=True)
        return 1


def _write_verify_report(report: Path, stamp: str, rows: list, failed: list) -> None:
    lines = [
        f"# Verify-All Report — {stamp}",
        "",
        "| Verifier | Exit | Status |",
        "|----------|------|--------|",
    ]
    for name, rc, status in rows:
        lines.append(f"| {name} | {rc} | {status} |")
    lines.append("")
    lines.append(f"Result: {len(rows) - len(failed)}/{len(rows)} passed.")
    report.write_text("\n".join(lines), encoding="utf-8")


def _run_verify_all_inner(
    args,
    verifiers,
    out_dir,
) -> int:
    suite_root = Path(__file__).resolve().parent.parent
    if verifiers is None:
        verifiers = [
            ("check_readiness", suite_root / "scripts" / "check_readiness.py", ["--readiness"]),
            ("verify_usability", suite_root / "scripts" / "verify_usability.py", []),
            ("verify_mcp", suite_root / "scripts" / "verify_mcp.py", []),
        ]
    if out_dir is None:
        out_dir = _OMO_RUNS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report = out_dir / f"verify_all_{stamp}.md"

    env = _build_env({"OMNI_TEST_FAKE_LLM": "1", "OMNI_TEST_FAKE_PANDOC": "1"})
    rows: list[tuple[str, int, str]] = []
    failed: list[str] = []

    print(f"[Tier6] Starting at {stamp}", flush=True)
    print(f"[Tier6] Report will be written to: {report}", flush=True)

    for name, script, extra in verifiers:
        cmd = [sys.executable, str(script), *extra]
        t0 = time.monotonic()
        # Write verifier output to a log file. capture_output=True can
        # deadlock on pytest runs that exceed the pipe buffer (~64KB).
        log_path = out_dir / f"verify_{name}_{stamp}.log"
        print(f"[Tier6] Running {name}... (log: {log_path.name})", flush=True)
        rc = -1
        try:
            with open(log_path, "w") as logf:
                result = subprocess.run(
                    cmd, stdout=logf, stderr=subprocess.STDOUT,
                    env=env, cwd=str(suite_root), timeout=600,
                )
            rc = result.returncode
        except subprocess.TimeoutExpired:
            rc = 124
        except Exception as e:
            print(f"[Tier6] ERROR running {name}: {type(e).__name__}: {e}",
                  file=sys.stderr, flush=True)
            rc = 125
        elapsed = time.monotonic() - t0
        status = "PASS" if rc == 0 else f"FAIL(rc={rc})"
        rows.append((name, rc, f"{status} in {elapsed:.1f}s"))
        if rc != 0:
            failed.append(name)
        print(f"[Tier6] {name} -> rc={rc} in {elapsed:.1f}s", flush=True)
        _write_verify_report(report, stamp, rows, failed)

    rc = 0 if not failed else 1
    print(f"[Tier6] DONE. Result: {len(rows) - len(failed)}/{len(rows)} passed. "
          f"Report: {report}", flush=True)
    return rc


def _run_bug_fix(args) -> int:
    """MVA Tier 7 (2026-06-21): read active-bugs.json, dispatch each open
    bug to a sub-agent for TDD fix, update statuses.

    The bug-fix dispatch spawns a sub-agent (via the orchestrator's task
    system) per open bug. The sub-agent follows the TDD protocol:
    1. Read the bug description in active-bugs.json
    2. Write a failing test that reproduces it
    3. Confirm RED
    4. Write the smallest production fix
    5. Confirm GREEN
    6. Report FIXED or ESCALATED

    The orchestrator updates active-bugs.json based on the sub-agent's
    report. This function does NOT run the verify_all aggregator — call
    --mode convergence-watch for the full loop.

    Returns 0 if at least one bug was fixed, 1 if no open bugs or all
    dispatches failed.
    """
    suite_root = _SUITE_ROOT
    bug_file = suite_root / ".omo" / "plans" / "active-bugs.json"

    if not bug_file.exists():
        print(f"ERROR: bug file not found: {bug_file}", file=sys.stderr)
        return 1

    data = json.loads(bug_file.read_text(encoding="utf-8"))
    open_bugs = [b for b in data.get("bugs", []) if b.get("status") == "open"]

    if not open_bugs:
        total = len(data.get("bugs", []))
        print(f"No open bugs (all {total} are fixed/escalated/wontfix). System is converged.")
        return 0

    print(f"=== bug-fix: {len(open_bugs)} open bug(s) ===")
    for bug in open_bugs:
        print(f"\n--- Dispatching {bug['id']}: {bug.get('symptom', '')[:80]}... ---")
        prompt = (
            f"You are a TDD fix agent for the Omni Suite project at "
            f"{suite_root}.\n\n"
            f"## Bug: {bug['id']}\n"
            f"## File: {bug.get('file', '?')}\n"
            f"## Symptom: {bug.get('symptom', '?')}\n"
            f"## Verify test: {bug.get('verify_test', '?')}\n\n"
            f"## Your task (strict TDD):\n"
            f"1. Read the affected file(s) and the existing test referenced by verify_test\n"
            f"2. If the verify_test does not exist yet, write it now (FAILING).\n"
            f"3. Run the test. Confirm it FAILS for the right reason (not import error, not syntax).\n"
            f"4. Write the SMALLEST production code change that flips the test RED->GREEN.\n"
            f"5. Run the test again. Confirm it PASSES.\n"
            f"6. Run the relevant module's full test suite to confirm no regression.\n"
            f"7. Report back: print exactly 'FIXED' on the last line if the fix worked, "
            f"or 'ESCALATED: <one-line reason>' if you cannot fix it in 3 attempts.\n\n"
            f"## Hard rules:\n"
            f"- NEVER add comments unless absolutely necessary.\n"
            f"- NEVER use type-error suppression.\n"
            f"- NEVER delete a failing test to 'pass'.\n"
            f"- NEVER commit anything.\n"
            f"- Do NOT modify active-bugs.json (the orchestrator does that).\n"
        )
        # The script has no sub-agent system, so it writes a dispatch
        # prompt per bug. The orchestrator picks these up and runs the
        # task() call, then updates active-bugs.json with the result.
        dispatch_file = _OMO_RUNS_DIR / f"dispatch_{bug['id']}.txt"
        dispatch_file.parent.mkdir(parents=True, exist_ok=True)
        dispatch_file.write_text(prompt, encoding="utf-8")
        print(f"  Prompt written to: {dispatch_file}")
        print("  (Orchestrator must run the dispatch and update active-bugs.json)")

    print(f"\n{len(open_bugs)} dispatch prompt(s) written.")
    print("Run the orchestrator (Sisyphus) to execute them.")
    return 0


def _run_convergence_watch(args) -> int:
    """MVA Tier 8 (2026-06-21): outer loop that runs the configured gates
    (Tier 6 verifier health + Tier 7 format matrix + Tier 8 real corpus /
    fidelity / equivalence) and dispatches
    bug-fix on RED until consecutive-green >= threshold or
    max-fix-fail >= threshold.

    This is the canonical "fully autonomous" entry point:
        python scripts/omo_loop.py --mode convergence-watch

    Default --gate is "both" (Tier 6 + Tier 7 + Tier 8). Use --gate tier6,
    --gate tier7 or --gate tier8 to run a single gate.

    The loop:
    - Cycle 1..N:
      - Run each configured gate
      - If ALL GREEN: increment consecutive_green
      - If any RED: dispatch --mode bug-fix, increment consecutive_fix_fail
      - Exit on consecutive_green >= --consecutive-green (success)
      - Exit on consecutive_fix_fail >= --max-fix-fail (blocked)
    """
    max_cycles = args.max_cycles
    consecutive_green = 0
    consecutive_fix_fail = 0

    gate = getattr(args, "gate", "both")
    gates = (
        ["tier6", "tier7", "tier8"] if gate == "both" else [gate]
    )
    gate_fns = {
        "tier6": ("verifier health (Tier 6)", _run_verify_all),
        "tier7": ("format matrix (Tier 7)", _run_format_matrix),
        "tier8": ("real corpus + fidelity + equivalence (Tier 8)", _run_tier8),
    }

    print(f"=== convergence-watch: max_cycles={max_cycles}, "
          f"consecutive_green_target={args.consecutive_green}, "
          f"max_fix_fail={args.max_fix_fail}, "
          f"gates={','.join(gates)} ===")

    for cycle in range(1, max_cycles + 1):
        print(f"\n{'='*60}\n  CYCLE {cycle}\n{'='*60}")

        all_green = True
        for g in gates:
            label, fn = gate_fns[g]
            print(f"  [gate {g}] running {label}...")
            rc = fn(args)
            if rc != 0:
                all_green = False
                print(f"  [gate {g}] RED (rc={rc})")
            else:
                print(f"  [gate {g}] GREEN")

        if all_green:
            consecutive_green += 1
            consecutive_fix_fail = 0
            print(f"  ALL GATES GREEN ({consecutive_green} consecutive)")
            if consecutive_green >= args.consecutive_green:
                print(f"\n*** CONVERGED: {consecutive_green} consecutive GREEN runs ***")
                return 0
        else:
            consecutive_green = 0
            consecutive_fix_fail += 1
            print(f"  RED (fix-fail #{consecutive_fix_fail})")
            if consecutive_fix_fail >= args.max_fix_fail:
                print(f"\n*** BLOCKED: {consecutive_fix_fail} consecutive fix-fails ***")
                return 1
            print("  Dispatching --mode bug-fix...")
            _run_bug_fix(args)
            print("  (After orchestrator applies fixes, re-run this loop)")

    print(f"\n*** MAX CYCLES REACHED ({max_cycles}) ***")
    return 1 if consecutive_green < args.consecutive_green else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="L3 OMO loop")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3, 4, 5, 6, 7], default=1,
        help="Tier 1: single-doc full pipeline (default). "
             "Tier 2: all 4 paths via e2e_runner.py. "
             "Tier 3: format matrix (P1) via phase1_runner.py. "
             "Tier 4: XLIFF backfill (P2) via phase1_runner.py. "
             "Tier 5: module-only runs via run_test.sh. "
             "Tier 6: verify-all (readiness + usability + mcp).")
    parser.add_argument("--mode", choices=["tier", "bug-fix", "convergence-watch"],
        default="tier", help="Execution mode. 'tier' runs a single tier (1-6). "
             "'bug-fix' dispatches all open bugs. 'convergence-watch' runs the autonomous loop.")
    parser.add_argument("--max-cycles", type=int, default=10, help="Stop after N cycles (default 10)")
    parser.add_argument("--consecutive-green", type=int, default=3, help="Consecutive GREEN runs to declare converged (default 3)")
    parser.add_argument("--max-fix-fail", type=int, default=5, help="Consecutive fix-fails to declare critical blocker (default 5)")
    parser.add_argument("--source-lang", default="zh")
    parser.add_argument("--target-lang", default="en")
    parser.add_argument("--input", type=Path, default=_DEFAULT_FIXTURE)
    parser.add_argument("--config", type=Path, default=_DEFAULT_CONFIG)
    parser.add_argument("--use-mock", action="store_true", help="Use mock LLM (for testing without API spend)")
    parser.add_argument("--gate", choices=["tier6", "tier7", "tier8", "both"], default="both",
        help="Which gate(s) convergence-watch uses to detect 'system is green'. "
             "'tier6' = verifier health; 'tier7' = format matrix; 'tier8' = real "
             "corpus + fidelity + equivalence; 'both' (default) = all three.")
    args = parser.parse_args()

    if args.mode == "bug-fix":
        return _run_bug_fix(args)
    if args.mode == "convergence-watch":
        return _run_convergence_watch(args)

    # 2026-06-17 round 7: dispatch tier 2-5 to existing comprehensive infra.
    if args.tier == 2:
        return _run_tier_2(args)
    if args.tier == 3:
        return _run_tier_3(args)
    if args.tier == 4:
        return _run_tier_4(args)
    if args.tier == 5:
        return _run_tier_5(args)
    if args.tier == 6:
        return _run_verify_all(args)
    if args.tier == 7:
        return _run_format_matrix(args)
    if args.tier == 8:
        return _run_tier8(args)

    if not args.input.exists():
        print(f"ERROR: input not found: {args.input}", file=sys.stderr)
        return 1

    state = LoopState()
    print(f"OMO loop started: {args.input.name}, {args.source_lang}->{args.target_lang}")
    print(f"Mock LLM: {args.use_mock}, max_cycles={args.max_cycles}, consecutive_green={args.consecutive_green}")

    while state.cycle < args.max_cycles:
        state.cycle += 1
        cycle_dir = _OMO_RUNS_DIR / f"cycle_{state.cycle:03d}"
        cycle_dir.mkdir(parents=True, exist_ok=True)
        report_path = cycle_dir / "report.md"

        print(f"\n{'='*60}\n  CYCLE {state.cycle}  ({'mock' if args.use_mock else 'real'} LLM)\n{'='*60}")

        art = _run_pipeline(
            args.input, cycle_dir,
            source_lang=args.source_lang, target_lang=args.target_lang,
            config_path=args.config, use_mock=args.use_mock,
        )
        print(f"  pipeline exit={art.exit_code}, duration={art.duration_s:.1f}s")

        gates = check_all_gates(art, args.input, args.target_lang)
        # Q7 has no baseline on cycle 1, so it returns a trivial pass and
        # only becomes a real reproducibility check from cycle 2 onward.
        q7 = _gate_q7_reproducibility(
            art, state.prev_artifacts, args,
        )
        gates.append(q7)
        q8 = _gate_q8_code_health()
        gates.append(q8)
        all_green = all(g.passed for g in gates)
        diagnosis = diagnose(art, gates)
        fix: dict | None = None

        if all_green:
            state.consecutive_green += 1
            state.consecutive_fix_fail = 0
            state.last_status = "GREEN"
            print(f"  ALL GATES GREEN ({state.consecutive_green} consecutive)")
        else:
            print("  GATES FAILED:")
            for g in gates:
                if not g.passed:
                    print(f"    ❌ {g.name}: {g.details}")
            print(f"  Diagnosis:\n{diagnosis}")
            state.consecutive_green = 0
            fix = try_safe_fix(diagnosis, cycle_dir)
            if fix:
                print(f"  Fix attempted: {fix}")
                state.fix_log.append(fix)
                # Re-run after fix
                art2 = _run_pipeline(
                    args.input, cycle_dir,
                    source_lang=args.source_lang, target_lang=args.target_lang,
                    config_path=args.config, use_mock=args.use_mock,
                )
                gates2 = check_all_gates(art2, args.input, args.target_lang)
                if all(g.passed for g in gates2):
                    state.consecutive_green = 1
                    state.consecutive_fix_fail = 0
                    state.last_status = "FIXED"
                    print("  FIX WORKED — gates now GREEN")
                    art = art2
                    gates = gates2
                else:
                    state.consecutive_fix_fail += 1
                    state.last_status = "STILL_RED"
                    print(f"  FIX FAILED ({state.consecutive_fix_fail} consecutive fix-fails)")
            else:
                state.consecutive_fix_fail += 1
                state.last_status = "RED_NO_FIX"
                print(f"  No fix available ({state.consecutive_fix_fail} consecutive)")

        # Write report
        write_cycle_report(state.cycle, state.last_status, art, gates, diagnosis, fix, report_path)

        state.prev_artifacts = art.to_dict()

        # History
        state.history.append({
            "cycle": state.cycle,
            "status": state.last_status,
            "exit_code": art.exit_code,
            "duration_s": art.duration_s,
            "gates_passed": sum(1 for g in gates if g.passed),
            "gates_total": len(gates),
        })

        # Termination
        if state.consecutive_green >= args.consecutive_green:
            print(f"\n*** CONVERGED: {state.consecutive_green} consecutive GREEN runs ***")
            break
        if state.consecutive_fix_fail >= args.max_fix_fail:
            print(f"\n*** CRITICAL BLOCKER: {state.consecutive_fix_fail} consecutive fix-fails ***")
            print(f"  Please review test_artifacts/omo_runs/cycle_{state.cycle:03d}/report.md")
            break

    # Final state
    state_path = _OMO_RUNS_DIR / "state.json"
    state_path.write_text(json.dumps(state.to_dict(), indent=2, ensure_ascii=False))
    print(f"\nFinal state: {state.to_dict()}")
    print(f"Reports at: {_OMO_RUNS_DIR}")
    return 0 if state.consecutive_green >= args.consecutive_green else 1


if __name__ == "__main__":
    sys.exit(main())
