"""Call OPP, OL, ORF CLIs as subprocess to orchestrate a full translation pipeline.

The orchestrator runs each stage as a separate CLI subprocess, passing
``OMNI_TEST_FAKE_LLM=1`` by default for hermetic testing.  Results are
returned as standardized ``{success, content: {...}}`` or
``{success, error: {code, message}}`` dicts.

SECURITY
--------
This orchestrator calls OPP/OL/ORF **CLIs** as subprocesses (see
``_run_cli()``) instead of chaining their MCP servers, so the sub-modules'
``PathValidator`` objects never see the request.  Because it is the outermost
entry point, it enforces the shared path policy before any subprocess starts
(``_path_denial_message()``): a fail-CLOSED directory allowlist plus the
canonical ``SYSTEM_DIRS`` / ``BLOCKED_EXTENSIONS`` blacklists.  The policy now
comes from the single-source ``omni_security`` package (ADR 0007) instead of a
fourth in-tree copy — ``omni_mcp`` must not import the sub-repos, and
``tests/security/test_path_policy_parity.py`` asserts the constants here are the
*same objects* the package exports.

What this layer deliberately does **not** replicate from the module validators:
the per-module allowed-extension whitelist (OPP/OL/ORF legitimately differ and
the orchestrator accepts any format a module can ingest), the max-file-size cap,
and the explicit symlink re-check.  A symlink whose target escapes the allowlist
is still denied, because the path is resolved before the containment test.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from omni_mcp._errors import error_response as _build_error_response
from omni_mcp._manifest import written_files
from omni_security import (
    BLOCKED_EXTENSIONS,
    SYSTEM_DIRS as SYSTEM_DIRS,
    system_dir_denial,
)
from omni_security import (
    parse_allowed_dirs as _parse_allowed_dirs,
)

logger = logging.getLogger("omni_mcp.orchestrator")

ProgressEvent = dict[str, object]
ProgressCallback = Callable[[ProgressEvent], None]

TOTAL_STAGES = 3

#: Expected wall-clock duration per stage.  These are hermetic
#: (``OMNI_TEST_FAKE_LLM``) figures; with a real LLM provider the OL stage
#: dominates and can run for minutes on a large document.
STAGE_EXPECTED_SECONDS: dict[str, int] = {"opp": 5, "ol": 30, "orf": 10}


def _emit_progress(
    callback: ProgressCallback | None,
    stage: str,
    index: int,
    message: str,
) -> None:
    """Emit one stage progress event. A failing reporter never aborts the run."""
    if callback is None:
        return
    try:
        callback(
            {
                "stage": stage,
                "index": index,
                "total": TOTAL_STAGES,
                "message": message,
            }
        )
    except Exception:  # noqa: BLE001 - progress is best-effort side channel
        logger.debug("progress callback raised for stage %s", stage, exc_info=True)

#: Allowlist env vars, in resolution order. The unified cross-module name
#: comes first, then the suite-specific name, then each sub-module's own
#: name (the orchestrator drives all three CLIs, so honoring any of their
#: allowlists is consistent with their fail-closed policies).
_ALLOWLIST_ENV_VARS = (
    "MCP_ALLOWED_DIRECTORIES",
    "OMNI_MCP_ALLOWED_DIRS",
    "OPP_MCP_ALLOWED_DIRS",
    "OL_MCP_ALLOWED_DIRS",
    "ORF_MCP_ALLOWED_DIRS",
)

#: Error code for a path outside the omni-mcp allowlist. Mirrors the
#: *_PATH_DENIED codes the sub-modules use so agents can switch on one shape.
OMNI_PATH_DENIED = "OMNI_PATH_DENIED"


def _allowed_directories() -> list[Path]:
    """Resolve the explicit directory allowlist from the environment.

    Returns an empty list when no allowlist is configured (callers must
    fail CLOSED in that case — never fall back to cwd).
    """
    raw = ""
    for var in _ALLOWLIST_ENV_VARS:
        raw = os.environ.get(var, "")
        if raw.strip():
            break
    if not raw.strip():
        return []
    return [
        Path(part).expanduser().resolve() for part in _split_allowlist(raw)
    ]


def _split_allowlist(raw: str) -> list[str]:
    """已废弃的字符串视图：委托给 canonical ``omni_security.parse_allowed_dirs``。

    本函数不再是路径策略的一份拷贝 —— 切分算法（``os.pathsep`` + 逗号、去空白、
    丢空段，Windows 盘符不被切开）只存在于 ``omni_security``。保留这个薄适配层
    仅为兼容既有调用方与测试（它们期望 ``list[str]``）；``Path`` 转换由 canonical
    解析器完成。

    Args:
        raw: 环境变量原始值。

    Returns:
        去掉空白后的非空分段列表（``str`` 形式，未做 ``Path`` 解析）。
    """
    return [str(path) for path in _parse_allowed_dirs(raw)]


def _path_denial_message(file_path: str) -> str | None:
    """Return a denial message for *file_path* or None if it is allowed.

    Checks, in order — the fail-CLOSED allowlist precondition first (it is a
    precondition, not a property of the path), then the two canonical blacklists
    imported from ``omni_security``, then the allowlist containment test:

    1. at least one allowlist env var must be set, else every path is denied
       (never fall back to cwd);
    2. the resolved path must not be inside a :data:`SYSTEM_DIRS` entry;
    3. its extension must not be in :data:`BLOCKED_EXTENSIONS`;
    4. it must resolve inside one of the allowlisted directories.

    Resolution happens first, so a symlink whose target leaves the allowlist is
    denied by check 4.  No existence check here — ``translate_file()`` reports
    a missing source as ``FILE_NOT_FOUND`` after this gate.

    Args:
        file_path: 待判定路径（调用方通常已 ``resolve()``）。

    Returns:
        拒绝原因（人类可读，含被拒的具体目录/扩展名），放行时返回 None。
    """
    allowed = _allowed_directories()
    if not allowed:
        return (
            "MCP_ALLOWED_DIRECTORIES (or OMNI_MCP_ALLOWED_DIRS) must be set "
            "(fail-CLOSED security policy). Export it as a comma- or "
            f"'{os.pathsep}'-separated list of allowed directories."
        )
    try:
        resolved = Path(file_path).resolve()
    except (ValueError, OSError) as e:
        return f"Cannot resolve path: {e}"
    system_dir = system_dir_denial(resolved)
    if system_dir is not None:
        return f"Access to system directory not allowed: {system_dir}"
    suffix = resolved.suffix.lower()
    if suffix in BLOCKED_EXTENSIONS:
        return f"File extension '{suffix}' is blocked"
    for d in allowed:
        try:
            resolved.relative_to(d)
            return None
        except ValueError:
            continue
    return (
        "Path is not within the allowed directories: "
        + ", ".join(str(d) for d in allowed)
    )


def _check_shared_secret(provided: str | None) -> bool:
    """Shared-secret auth mirroring the sub-modules (disabled when unset)."""
    expected = os.environ.get("MCP_SHARED_SECRET")
    if not expected:
        return True
    return provided == expected


def _error(code: str, message: str) -> dict[str, object]:
    """Build a standardized error dict (with a recovery hint)."""
    return _build_error_response(code, message)


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
    shared_secret: str | None = None,
    progress_callback: ProgressCallback | None = None,
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
    shared_secret:
        MCP shared secret. Required only when ``MCP_SHARED_SECRET`` is set.
    progress_callback:
        Optional synchronous reporter invoked once per stage with
        ``{stage, index, total, message}``.  Called from whatever thread runs
        this function, so an async caller that offloads to an executor can
        bridge it to MCP progress notifications.

    Expected duration (hermetic, ``OMNI_TEST_FAKE_LLM=1``): roughly 10-60s
    total (OPP ~5s, OL ~30s, ORF ~10s).  With a real LLM provider the OL
    stage dominates and can take minutes for a large document; callers should
    surface progress rather than block on the result.

    Returns
    -------
    dict
        ``{success: True, content: {output_path, pipeline, ...}}`` on success.
        ``{success: False, error: {code, message}}`` on failure.
        ``AUTH_FAILED`` when ``MCP_SHARED_SECRET`` is configured and the
        provided secret does not match.  ``OMNI_PATH_DENIED`` when the
        source path is inside a system directory, carries a blocked
        executable extension, is outside the configured allowlist, or no
        allowlist is configured (fail CLOSED — the path never reaches the
        sub-CLIs in any of those cases).
    """
    if not _check_shared_secret(shared_secret):
        return _error(
            "AUTH_FAILED",
            "Authentication failed: shared_secret is missing or incorrect.",
        )
    logger.warning(
        "SECURITY: omni_mcp enforces its own copy of the shared path policy "
        "(fail-CLOSED allowlist + SYSTEM_DIRS + BLOCKED_EXTENSIONS) instead of "
        "chaining the sub-modules' PathValidator; the per-module extension "
        "whitelist and the file-size cap are not applied at this layer."
    )

    start = time.time()
    file_path = str(Path(file_path).resolve())

    denial = _path_denial_message(file_path)
    if denial is not None:
        return _error(OMNI_PATH_DENIED, denial)

    if not Path(file_path).exists():
        return _error("FILE_NOT_FOUND", f"Source file does not exist: {file_path}")

    work_dir = Path(tempfile.mkdtemp(prefix="omni_mcp_"))

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
            progress_callback=progress_callback,
        )
    finally:
        for intermediate_name in ("opp", "ol"):
            shutil.rmtree(str(work_dir / intermediate_name), ignore_errors=True)


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
    progress_callback: ProgressCallback | None = None,
) -> dict[str, object]:
    """Internal pipeline runner. Separated for readability."""

    stem = Path(file_path).stem
    opp_dir = work_dir / "opp"
    ol_dir = work_dir / "ol"
    opp_dir.mkdir(exist_ok=True)
    ol_dir.mkdir(exist_ok=True)

    # ── Step 1: OPP extract ───────────────────────────────────────────
    _emit_progress(progress_callback, "opp", 1, "OPP extraction")
    opp_cmd = [
        opp_path, file_path,
        "--target-format", "both",
        "--source-lang", source_lang,
        "--target-lang", target_lang,
        "--output-dir", str(opp_dir),
        "--json",
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
    _emit_progress(progress_callback, "ol", 2, "OL translation")
    if pipeline == "md":
        md_path = _find_output_file(opp_dir, stem, [".md"])
        if md_path is None:
            return _error("OPP_NO_MD", "OPP did not produce a .md output file")

        ol_cmd = [
            ol_path, "translate-md", str(md_path),
            "-s", source_lang,
            "-t", target_lang,
            "-o", str(ol_dir),
            "--json",
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
            "--json",
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
    _emit_progress(progress_callback, "orf", 3, "ORF backfill")
    output_path = str(work_dir / f"output.{output_format}")

    if pipeline == "md":
        orf_cmd = [
            orf_path, "apply-md", str(translated_md),
            "--target-format", output_format,
            "-o", output_path,
            "--json",
        ]
    else:
        # XLIFF path: need original file + translated XLIFF
        orf_cmd = [
            orf_path, "apply-xliff", file_path,
            "--xliff", str(translated_md),
            "--output", output_path,
            "--format", output_format,
            "--json",
        ]

    orf_result = _run_cli(orf_cmd, timeout=120)
    if not orf_result.get("success"):
        err = orf_result.get("error", {})
        # Also check ORF's backward-compat errors list
        if not isinstance(err, dict):
            errors_list = orf_result.get("errors", [])
            if isinstance(errors_list, list) and errors_list and isinstance(errors_list[0], dict):
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

    response = _success({
        "output_path": str(actual_output),
        "pipeline": pipeline,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "output_format": output_format,
        "duration_ms": duration_ms,
    })
    response["outputs"], response["sidecars"] = written_files(str(actual_output))
    return response
