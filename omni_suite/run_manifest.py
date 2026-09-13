"""Run manifest for ``omni-suite pipeline`` checkpoint/resume (gap R-01).

The manifest records per-stage status next to the pipeline intermediates so a
run interrupted mid-stage (failure or Ctrl-C) can be resumed with
``--resume-from <stage>``. Stages are ``opp`` → ``ol`` → ``orf``; a manifest is
stored at ``<run-dir>/manifest.json`` and mirrors the actual artifacts on disk.

Resume semantics (``plan_resume``): only stages *before* the requested stage
are reusable, and only when their intermediate artifact actually exists. A
stale manifest with no artifacts never fakes a resume — the caller falls back
to a full run.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

STAGES: tuple[str, ...] = ("opp", "ol", "orf")

PENDING = "pending"
RUNNING = "running"
COMPLETE = "complete"
FAILED = "failed"
REUSED = "reused"
SKIPPED = "skipped"

RUN_PARTIAL = "partial"
RUN_COMPLETE = "complete"

MANIFEST_NAME = "manifest.json"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class StageState:
    """Mutable per-stage record; constructed fresh on every load."""

    status: str = PENDING
    detail: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> StageState:
        return cls(
            status=str(data.get("status", PENDING)),
            detail=str(data.get("detail", "")),
            updated_at=str(data.get("updated_at", "")),
        )

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "detail": self.detail,
            "updated_at": self.updated_at,
        }


@dataclass
class RunManifest:
    """Checkpoint state for one pipeline run."""

    run_id: str
    input_file: str
    temp_dir: str
    output: str
    source_lang: str = "en"
    target_lang: str = "zh"
    target_format: str = "docx"
    status: str = RUN_PARTIAL
    failed_stage: str | None = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    stages: dict[str, StageState] = field(
        default_factory=lambda: {s: StageState() for s in STAGES}
    )

    @classmethod
    def load(cls, path: Path) -> RunManifest:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        stages = {
            s: StageState.from_dict(raw.get("stages", {}).get(s, {}))
            for s in STAGES
        }
        return cls(
            run_id=str(raw.get("run_id", "")),
            input_file=str(raw.get("input_file", "")),
            temp_dir=str(raw.get("temp_dir", "")),
            output=str(raw.get("output", "")),
            source_lang=str(raw.get("source_lang", "en")),
            target_lang=str(raw.get("target_lang", "zh")),
            target_format=str(raw.get("target_format", "docx")),
            status=str(raw.get("status", RUN_PARTIAL)),
            failed_stage=raw.get("failed_stage"),
            created_at=str(raw.get("created_at", _now())),
            updated_at=str(raw.get("updated_at", _now())),
            stages=stages,
        )

    def save(self, path: Path) -> None:
        self.updated_at = _now()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def mark(self, stage: str, status: str, detail: str = "") -> None:
        self.stages[stage] = StageState(
            status=status, detail=detail, updated_at=_now()
        )
        if status == FAILED:
            self.failed_stage = stage
            self.status = RUN_PARTIAL
        elif status == COMPLETE and self.failed_stage is None:
            self.status = RUN_COMPLETE

    def completed_count(self) -> int:
        """Number of stages done (complete or reused on resume)."""
        return sum(
            1 for s in self.stages.values() if s.status in (COMPLETE, REUSED)
        )

    def resume_hint(self) -> str:
        """A runnable ``omni-suite pipeline`` command resuming from the failure."""
        if not self.failed_stage:
            return ""
        return " ".join(
            [
                "omni-suite",
                "pipeline",
                self.input_file,
                "--resume-from",
                self.failed_stage,
                "--run-id",
                self.run_id,
                "--output",
                self.output,
            ]
        )

    def summary(self) -> dict:
        return {
            "status": self.status,
            "completed": self.completed_count(),
            "resume_hint": self.resume_hint(),
            "run_id": self.run_id,
            "failed_stage": self.failed_stage,
        }

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "input_file": self.input_file,
            "temp_dir": self.temp_dir,
            "output": self.output,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "target_format": self.target_format,
            "status": self.status,
            "failed_stage": self.failed_stage,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "stages": {s: st.to_dict() for s, st in self.stages.items()},
        }


def plan_resume(
    resume_from: str | None, opp_dir: Path, ol_dir: Path
) -> list[str]:
    """Return the prior stages whose intermediates exist and may be reused.

    Empty list means "run everything": either no ``--resume-from`` was given,
    the stage is unknown, or a required intermediate artifact is missing. A
    missing artifact is authoritative even if a manifest claims the stage was
    complete — the manifest must never override reality on disk.
    """
    if resume_from not in STAGES:
        return []
    prior = list(STAGES[: STAGES.index(resume_from)])
    if not intermediates_present(prior, opp_dir, ol_dir):
        return []
    return prior


def intermediates_present(stages: list[str], opp_dir: Path, ol_dir: Path) -> bool:
    """True when every prior stage's intermediate artifact exists on disk."""
    for stage in stages:
        if stage == "opp" and not any(Path(opp_dir).glob("*.md")):
            return False
        if stage == "ol" and not any(Path(ol_dir).glob("*.md")):
            return False
    return True
