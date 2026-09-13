"""Gap X-03 — mutation transparency.

Mutating tools must report the files they actually wrote:

    {success: ..., outputs: [{path, sha256, bytes}], sidecars: [{path, sha256, bytes}]}

where every returned ``sha256``/``bytes`` matches the bytes on disk.  A tool
that reports a mutation but cannot prove it (the file is gone) is a
misleading success — these tests fail on a stale or absent output.

Coverage of this file: ORF ``apply_md`` and suite ``omni_mcp.translate_file``.
The remaining mutating tools (OPP extract_document/save_skeleton, OL
translate_file/translate_md_text, ORF apply_xliff/batch_convert) are recorded
as a follow-up in ``.omo/plans/agent-oriented-gap-register.md`` §4.3 (X-03).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

# ORF MCP is fail-closed: without an allowlist the PathValidator refuses every
# path. pytest's tmp_path lives under /tmp.
os.environ.setdefault("ORF_MCP_ALLOWED_DIRS", "/tmp")
os.environ.setdefault("MCP_ALLOWED_DIRECTORIES", "/tmp")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# ORF apply_md — the hermetic mutating tool (MD → HTML needs no pandoc)
# ---------------------------------------------------------------------------


class TestOrfApplyMdManifest:
    """``orf.mcp.server.apply_md`` reports the file it wrote."""

    def test_apply_md_reports_written_file_with_matching_hash(self, tmp_path):
        from orf.mcp.common import reset_config_and_validator

        reset_config_and_validator()

        from orf.mcp.server import apply_md

        md = tmp_path / "doc.md"
        md.write_text("# Title\n\nBody text.\n", encoding="utf-8")
        out = tmp_path / "doc.html"

        parsed = json.loads(
            apply_md(input_md=str(md), target_format="html", output_path=str(out))
        )

        assert parsed["success"] is True
        assert out.is_file(), "apply_md reported success but wrote no output"
        outputs = parsed["outputs"]
        assert isinstance(outputs, list) and len(outputs) == 1
        entry = outputs[0]
        assert entry["path"] == str(out)
        assert entry["sha256"] == _sha256(out)
        assert entry["bytes"] == out.stat().st_size
        assert isinstance(parsed["sidecars"], list)

    def test_apply_md_rejects_a_claimed_but_missing_output(self, tmp_path, monkeypatch):
        """Adversarial: a success envelope naming a file that was never written
        must not be presented as a verified mutation."""
        from orf.mcp.common import reset_config_and_validator

        reset_config_and_validator()

        import orf.mcp.server as server
        from orf.mcp.server import apply_md

        md = tmp_path / "doc.md"
        md.write_text("# Title\n", encoding="utf-8")
        phantom = tmp_path / "never-written.html"

        monkeypatch.setattr(
            server,
            "_run_cli_command",
            lambda args: {
                "success": True,
                "output_path": str(phantom),
                "errors": [],
                "warnings": [],
                "metadata": {},
            },
        )

        parsed = json.loads(apply_md(input_md=str(md), target_format="html"))

        assert parsed["success"] is True
        assert parsed["outputs"][0]["sha256"] is None
        assert parsed["outputs"][0]["bytes"] == 0


class TestWrittenFilesHelper:
    """The shared hash helper reports outputs and real sidecars."""

    def test_written_files_hashes_output_and_sidecars(self, tmp_path):
        from orf.mcp.manifest import written_files

        out = tmp_path / "doc.html"
        out.write_bytes(b"<html></html>")
        (tmp_path / "images.json").write_text("{}", encoding="utf-8")
        (tmp_path / "images.zip").write_bytes(b"PK\x05\x06" + b"\x00" * 18)

        outputs, sidecars = written_files(str(out))

        assert outputs == [
            {"path": str(out), "sha256": _sha256(out), "bytes": out.stat().st_size}
        ]
        names = {Path(s["path"]).name for s in sidecars}
        assert names == {"images.json", "images.zip"}
        for sidecar in sidecars:
            p = Path(sidecar["path"])
            assert sidecar["sha256"] == _sha256(p)
            assert sidecar["bytes"] == p.stat().st_size


# ---------------------------------------------------------------------------
# omni_mcp.translate_file — the suite mutating orchestrator
# ---------------------------------------------------------------------------


class TestTranslateFileManifest:
    """``omni_mcp.orchestrator.translate_file`` reports its final artifact."""

    @staticmethod
    def _fake_cli(cmd, **kwargs):
        """Simulate the three sub-CLIs writing their documented outputs."""
        if "apply-md" in cmd:
            i = cmd.index("-o")
            Path(cmd[i + 1]).write_bytes(b"fake docx bytes")
            return {"success": True}
        if "translate-md" in cmd:
            i = cmd.index("-o")
            out_dir = Path(cmd[i + 1])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "src.md").write_text("# 你好\n", encoding="utf-8")
            return {"success": True}
        # OPP extract
        i = cmd.index("--output-dir")
        out_dir = Path(cmd[i + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "src.md").write_text("# Hello\n", encoding="utf-8")
        return {"success": True, "suggested_pipeline": "md_only"}

    def test_translate_file_reports_persisted_output_hash(self, tmp_path, monkeypatch):
        import omni_mcp.orchestrator as orch

        monkeypatch.setattr(orch, "_run_cli", self._fake_cli)

        src = tmp_path / "src.docx"
        src.write_bytes(b"PK\x03\x04")

        result = orch.translate_file(
            file_path=str(src),
            source_lang="en",
            target_lang="zh",
            output_format="docx",
        )

        assert result["success"] is True
        out = Path(result["content"]["output_path"])
        assert out.is_file(), "translate_file deleted its own output before returning"
        outputs = result["outputs"]
        assert outputs and outputs[0]["path"] == str(out)
        assert outputs[0]["sha256"] == _sha256(out)
        assert outputs[0]["bytes"] == out.stat().st_size
        assert result["outputs"][0]["sha256"] is not None
        assert isinstance(result["sidecars"], list)

    def test_translate_file_workspace_is_unique_per_call(self, tmp_path, monkeypatch):
        """Stale-state guard: two calls that start in the same wall-clock second
        must not share (and therefore cross-report) a workspace directory."""
        import omni_mcp.orchestrator as orch

        monkeypatch.setattr(orch, "_run_cli", self._fake_cli)
        monkeypatch.setattr(orch.time, "time", lambda: 1_700_000_000.0)

        src = tmp_path / "src.docx"
        src.write_bytes(b"PK\x03\x04")

        first = orch.translate_file(
            file_path=str(src), source_lang="en", target_lang="zh", output_format="docx"
        )
        second = orch.translate_file(
            file_path=str(src), source_lang="en", target_lang="zh", output_format="docx"
        )

        first_path = Path(first["content"]["output_path"])
        second_path = Path(second["content"]["output_path"])
        assert first_path != second_path
        assert first["outputs"][0]["sha256"] == _sha256(first_path)
        assert second["outputs"][0]["sha256"] == _sha256(second_path)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
