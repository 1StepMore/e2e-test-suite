"""Call OPP, OL, ORF CLIs as subprocess to orchestrate a full translation pipeline.

The orchestrator runs each stage as a separate CLI subprocess, passing
``OMNI_TEST_FAKE_LLM=1`` by default for hermetic testing.  Results are
returned as standardized ``{success, content: {...}}`` or
``{success, error: {code, message}}`` dicts.

SECURITY
--------
This orchestrator calls OPP/OL/ORF **CLIs** as subprocesses (see
``_run_cli()``), bypassing the sub-module MCP path security provided by
OPP's and ORF's ``PathValidator``.  Any ``translate_file()`` invocation
therefore accepts arbitrary ``file_path`` values without path validation.
Only use this module in trusted environments.  A proper MCP-to-MCP bridge
(deferred to a later wave) would chain JSON-RPC calls through each sub-
module's MCP server, preserving PathValidator checks.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

logger = logging.getLogger("omni_mcp.orchestrator")


def _error(code: str, message: str) -> dict[str, object]:
    """Build a standardized error dict."""
    return {"success": False, "error": {"code": code, "message": message}}


def _success(content: dict[str, object]) -> dict[str, object]:
    """Build a standardized success dict."""
    return {"success": True, "content": content}


def _run_cli(
    cmd: list[str],
    env: dict[str, str] | None = None,
    timeout: int = 300,
) -> dict[str, object]:
    """Run a CLI command and return parsed JSON result.

    Always sets ``OMNI_TEST_FAKE_LLM=1`` unless the caller's *env*
    explicitly provides a different value.
    """
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    # FIXED: default is REAL (0); FAKE mode must be explicitly set in env
    merged_env.setdefault("OMNI_TEST_FAKE_LLM", os.environ.get("OMNI_TEST_FAKE_LLM", "0"))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=merged_env,
        )
    except FileNotFoundError:
        return _error("CLI_NOT_FOUND", f"Command not found: {cmd[0]}")
    except subprocess.TimeoutExpired:
        return _error("CLI_TIMEOUT", f"Command timed out after {timeout}s: {' '.join(cmd[:3])}")

    stdout = result.stdout.strip()
    if not stdout:
        stderr_snippet = (result.stderr or "")[:500]
        return _error(
            "CLI_EMPTY_OUTPUT",
            f"CLI returned empty stdout (exit {result.returncode}). stderr: {stderr_snippet}",
        )

    try:
        parsed = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return _error("CLI_PARSE_ERROR", f"Could not parse CLI output: {stdout[:500]}")

    return parsed


def _find_output_file(directory: Path, stem: str, extensions: list[str]) -> Path | None:
    """Search *directory* for a file matching *stem* + any of *extensions*.

    Checks both the directory root and common subdirectories (translated/,
    ol_output/).
    """
    search_dirs = [directory, directory / "translated", directory / "ol_output"]
    for d in search_dirs:
        if not d.exists():
            continue
        for ext in extensions:
            candidate = d / f"{stem}{ext}"
            if candidate.exists():
                return candidate
        # Fallback: glob for first matching extension
        for ext in extensions:
            matches = sorted(d.glob(f"*{ext}"))
            if matches:
                return matches[0]
    return None


def translate_file(
    file_path: str,
    source_lang: str,
    target_lang: str,
    output_format: str,
    pipeline: str | None = None,
    opp_path: str = "opp",
    ol_path: str = "ol",
    orf_path: str = "orf",
) -> dict[str, object]:
    """Orchestrate OPP→OL→ORF as subprocess calls.

    Parameters
    ----------
    file_path:
        Absolute path to the source document.
    source_lang / target_lang:
        ISO language codes (e.g. ``"en"``, ``"zh"``).
    output_format:
        Target output format (e.g. ``"docx"``, ``"html"``, ``"md"``).
    pipeline:
        Force pipeline type: ``"md"`` or ``"xliff"``.  ``None`` means
        auto-detect from OPP's ``suggested_pipeline`` field.
    opp_path / ol_path / orf_path:
        CLI commands for each module (default: ``"opp"``, ``"ol"``, ``"orf"``).

    Returns
    -------
    dict
        ``{success: True, content: {output_path, pipeline, ...}}`` on success.
        ``{success: False, error: {code, message}}`` on failure.
    """
    logger.warning(
        "SECURITY: omni_mcp bypasses sub-module MCP path security (PathValidator). "
        "Only use in trusted environments."
    )

    start = time.time()
    file_path = str(Path(file_path).resolve())

    if not Path(file_path).exists():
        return _error("FILE_NOT_FOUND", f"Source file does not exist: {file_path}")

    work_dir = Path(f"/tmp/omni_mcp_{int(start)}")
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        return _run_pipeline(
            file_path=file_path,
            source_lang=source_lang,
            target_lang=target_lang,
            output_format=output_format,
            pipeline=pipeline,
            work_dir=work_dir,
            opp_path=opp_path,
            ol_path=ol_path,
            orf_path=orf_path,
            start_time=start,
        )
    finally:
        shutil.rmtree(str(work_dir), ignore_errors=True)


def _run_pipeline(
    *,
    file_path: str,
    source_lang: str,
    target_lang: str,
    output_format: str,
    pipeline: str | None,
    work_dir: Path,
    opp_path: str,
    ol_path: str,
    orf_path: str,
    start_time: float,
) -> dict[str, object]:
    """Internal pipeline runner. Separated for readability."""

    stem = Path(file_path).stem
    opp_dir = work_dir / "opp"
    ol_dir = work_dir / "ol"
    opp_dir.mkdir(exist_ok=True)
    ol_dir.mkdir(exist_ok=True)

    # ── Step 1: OPP extract ───────────────────────────────────────────
    opp_cmd = [
        opp_path, file_path,
        "--target-format", "both",
        "--source-lang", source_lang,
        "--target-lang", target_lang,
        "--output-dir", str(opp_dir),
    ]
    opp_result = _run_cli(opp_cmd, timeout=120)
    if not opp_result.get("success"):
        err = opp_result.get("error", {})
        if isinstance(err, dict):
            return _error("OPP_FAILED", f"OPP extraction failed: {err.get('message', 'unknown')}")
        return _error("OPP_FAILED", f"OPP extraction failed: {err}")

    # Determine pipeline from OPP's suggested_pipeline or explicit arg
    if pipeline is None:
        suggested = opp_result.get("suggested_pipeline", "md_only")
        if suggested in ("both",):
            # Prefer MD path for simplicity; XLIFF path available if needed
            pipeline = "md"
        elif suggested == "xliff_only":
            pipeline = "xliff"
        else:
            pipeline = "md"

    # ── Step 2: OL translate ──────────────────────────────────────────
    if pipeline == "md":
        md_path = _find_output_file(opp_dir, stem, [".md"])
        if md_path is None:
            return _error("OPP_NO_MD", "OPP did not produce a .md output file")

        ol_cmd = [
            ol_path, "translate-md", str(md_path),
            "-s", source_lang,
            "-t", target_lang,
            "-o", str(ol_dir),
        ]
        ol_result = _run_cli(ol_cmd, timeout=300)
        if not ol_result.get("success"):
            err = ol_result.get("error", {})
            msg = err.get("message", "unknown") if isinstance(err, dict) else str(err)
            return _error("OL_FAILED", f"OL translation failed: {msg}")

        translated_md = _find_output_file(ol_dir, stem, [".md"])
        if translated_md is None:
            return _error("OL_NO_OUTPUT", "OL did not produce a translated .md file")

    elif pipeline == "xliff":
        xlf_path = _find_output_file(opp_dir, stem, [".xlf", ".xliff"])
        if xlf_path is None:
            return _error("OPP_NO_XLIFF", "OPP did not produce a .xlf output file")

        ol_cmd = [
            ol_path, "translate-xliff", str(xlf_path),
            "-s", source_lang,
            "-t", target_lang,
            "-o", str(ol_dir),
        ]
        ol_result = _run_cli(ol_cmd, timeout=300)
        if not ol_result.get("success"):
            err = ol_result.get("error", {})
            msg = err.get("message", "unknown") if isinstance(err, dict) else str(err)
            return _error("OL_FAILED", f"OL XLIFF translation failed: {msg}")

        translated_md = _find_output_file(ol_dir, stem, [".xlf", ".xliff"])
        if translated_md is None:
            return _error("OL_NO_OUTPUT", "OL did not produce a translated XLIFF file")
    else:
        return _error("INVALID_PIPELINE", f"Unknown pipeline type: {pipeline}")

    # ── Step 3: ORF backfill ──────────────────────────────────────────
    output_path = str(work_dir / f"output.{output_format}")

    if pipeline == "md":
        orf_cmd = [
            orf_path, "apply-md", str(translated_md),
            "--target-format", output_format,
            "-o", output_path,
        ]
    else:
        # XLIFF path: need original file + translated XLIFF
        orf_cmd = [
            orf_path, "apply-xliff", file_path,
            "--xliff", str(translated_md),
            "--output", output_path,
            "--format", output_format,
        ]

    orf_result = _run_cli(orf_cmd, timeout=120)
    if not orf_result.get("success"):
        err = orf_result.get("error", {})
        # Also check ORF's backward-compat errors list
        if not isinstance(err, dict):
            errors_list = orf_result.get("errors", [])
            if errors_list and isinstance(errors_list[0], dict):
                err = errors_list[0]
        msg = err.get("message", "unknown") if isinstance(err, dict) else str(err)
        return _error("ORF_FAILED", f"ORF backfill failed: {msg}")

    # Check output exists
    # ORF may place output at a slightly different path — check common locations
    actual_output = Path(output_path)
    if not actual_output.exists():
        # ORF sometimes uses the input stem
        alt = work_dir / f"{stem}.{output_format}"
        if alt.exists():
            actual_output = alt
        else:
            # Search work_dir for any file with the target extension
            matches = list(work_dir.glob(f"*.{output_format}"))
            if matches:
                actual_output = matches[0]
            else:
                return _error(
                    "OUTPUT_NOT_FOUND",
                    f"Output file not created at {output_path}",
                )

    duration_ms = int((time.time() - start_time) * 1000)

    return _success({
        "output_path": str(actual_output),
        "pipeline": pipeline,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "output_format": output_format,
        "duration_ms": duration_ms,
    })
