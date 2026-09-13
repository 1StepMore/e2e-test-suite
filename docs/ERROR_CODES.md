# MCP Error Code Catalog

**Status:** Stable. Codes are part of the public MCP contract — adding new
codes is fine, but **do not rename or remove** existing ones. Clients may
switch on them.

**Source of truth:**
- OPP: `Omni_Pre_Processor/src/opp/mcp/_errors.py` (`_ERROR_CODE_MAP`, `RECOVERY_HINTS`)
- OL: `Omni_Localizer/src/ol_mcp/_errors.py` (`_ERROR_CODE_MAP`, `RECOVERY_HINTS`)
- ORF: `Omni_Re_Formatter/src/orf/mcp/_errors.py` (`SAFE_USER_MESSAGES`, `RECOVERY_HINTS`; envelopes built by `orf/mcp/common.py:error_response`)
- omni-mcp (suite): `omni_mcp/_errors.py` (`RECOVERY_HINTS`, `error_response`)
- Auth (OPP/OL/ORF): `*/mcp/auth.py` (`auth_failure_response()`)

The `RECOVERY_HINTS` registries are contract-tested by
`tests/contract/test_recovery_hints_contract.py` (R-09): every declared code
must map to a non-empty, static recovery hint.

---

## Response Shape

All four MCP servers (OPP, OL, ORF, omni-mcp) return errors in a uniform
shape, including a `recovery: {strategy, hint}` object:

```json
{
  "success": false,
  "error": {"code": "OPP_FILE_NOT_FOUND", "message": "A required file was not found."},
  "error_code": "OPP_FILE_NOT_FOUND",
  "message": "A required file was not found.",
  "recovery": {
    "strategy": "fix_input",
    "hint": "Verify the input path exists and is readable, then re-issue the call."
  }
}
```

`error.code` / `error_code` and `error.message` / `message` are duplicated for
backward compatibility (new clients should switch on the nested `error` object
or the flat `error_code`, both identical). ORF additionally carries an
`errors: [{code, message, recovery_strategy}]` list whose `recovery_strategy`
is the same strategy as `recovery.strategy`.

### Recovery envelope (R-09)

`recovery` is always present on an error envelope. It never interpolates the
exception message, a file path, or any caller-controlled data — the hint is a
static constant (prompt-injection safety). Unknown/dynamic codes fall back to
`{"strategy": "report_bug", "hint": "Unknown error code; inspect server logs..."}`.

| Strategy | Meaning |
|----------|---------|
| `retry` | Transient failure; retrying (optionally with smaller input / lower concurrency) may succeed. |
| `fix_input` | The caller must correct the request (missing field, bad path, unsupported format) and re-issue. |
| `use_allowed_path` | The path is outside the allowlist; choose or allowlist a permitted path. |
| `reduce_input` | The request exceeds a resource bound; split or shrink it. |
| `reissue_with_auth` | Auth token is missing/wrong; re-issue with the correct shared secret. |
| `fallback` | The requested path is unsupported; use an alternative (e.g. MD pipeline instead of XLIFF, `data_base64` instead of `file_path`). |
| `configure_environment` | Server-side environment/config is missing or invalid (CLI not installed, scenario library broken). |
| `report_bug` | Internal/unexpected failure; inspect logs and file a bug. Do not retry blindly. |
| `abort` | Not recoverable by retry (e.g. an unimplemented path); do not retry. |

---

## Shared Codes (all 3 modules)

| Code | Meaning | When it occurs | Caller action |
|------|---------|----------------|---------------|
| `AUTH_FAILED` | Shared-secret auth rejected the call. | `auth_token` missing or wrong AND `MCP_SHARED_SECRET` env var is set on the server. When the env var is unset, auth is disabled and this code never appears. | Re-issue the call with the correct `auth_token`. If the server is misconfigured, set `MCP_SHARED_SECRET` to a shared value across all callers. |

---

## OPP Codes

Source: `opp/mcp/_errors.py:_ERROR_CODE_MAP`

| Code | Exception class | Meaning | When it occurs | Caller action |
|------|-----------------|---------|----------------|---------------|
| `OPP_FILE_NOT_FOUND` | `FileNotFoundError` | A required file was not found. | Input path doesn't exist, or a downstream tool opened a missing file. | Verify the path exists and is readable. Re-issue. |
| `OPP_PERMISSION_DENIED` | `PermissionError` | Permission denied for the requested operation. | Path exists but is not readable/writable by the server process, or filesystem permission check failed. | Check file/directory permissions. Re-issue after fixing. |
| `OPP_INVALID_INPUT` | `ValueError` | The request input was invalid. | Schema validation failed, or an extractor raised `ValueError` on bad input (e.g., corrupt DOCX). | Validate input against the tool's input schema. |
| `OPP_MISSING_KEY` | `KeyError` | A required key was missing from the input. | A required field was omitted from the input model. | Check the tool's input schema; all required fields must be present. |
| `OPP_TIMEOUT` | `TimeoutError` | The operation timed out. | Extraction took longer than the configured timeout. | Retry with a smaller input, or increase the server's timeout. |
| `OPP_NOT_IMPLEMENTED` | `NotImplementedError` | The requested feature is not yet implemented. | A code path was hit that is stubbed or pending. | File a feature request; do not retry. |
| `OPP_PATH_DENIED` | `PathValidationError` | Access to the requested path was denied. | Path is outside the allowlist, contains `..`, is a symlink to a disallowed target, or has a blocked extension. | Use a path within `OPP_MCP_ALLOWED_DIRS`. |
| `OPP_RESOURCE_EXHAUSTED` | `ResourceExhausted` | The operation exceeded resource limits. | Batch input exceeded `MAX_BATCH_FILES` or `MAX_BATCH_TEXTS`, or an image exceeded `MAX_IMAGE_BYTES`. | Split the batch into smaller chunks, or compress images. |
| `OPP_INTERNAL_ERROR` | (any other exception) | An internal error occurred. Catch-all for unmapped exception classes. | Unexpected server-side failure. | Check server logs for the full traceback. File a bug report. |

### OPP recovery hints (R-09)

Source: `opp/mcp/_errors.py:RECOVERY_HINTS`. `OPP_UNKNOWN_TOOL`, `AUTH_FAILED`,
and `RATE_LIMITED` are declared here too because the server's dispatch, auth,
and rate-limit paths emit them.

| Code | Strategy | Hint |
|------|----------|------|
| `AUTH_FAILED` | `reissue_with_auth` | Re-issue the call with the correct auth_token matching MCP_SHARED_SECRET. |
| `OPP_FILE_NOT_FOUND` | `fix_input` | Verify the input path exists and is readable, then re-issue the call. |
| `OPP_INTERNAL_ERROR` | `report_bug` | Do not retry blindly; check server logs for the traceback and file a bug report. |
| `OPP_INVALID_INPUT` | `fix_input` | Validate the request against the tool's input schema (format, required fields), then re-issue. |
| `OPP_MISSING_KEY` | `fix_input` | Add the missing required field from the tool's input schema, then re-issue. |
| `OPP_NOT_IMPLEMENTED` | `abort` | Do not retry; this code path is not implemented. File a feature request. |
| `OPP_PATH_DENIED` | `use_allowed_path` | Use a path inside OPP_MCP_ALLOWED_DIRS (no '..', no escaping symlinks), then re-issue. |
| `OPP_PERMISSION_DENIED` | `fix_input` | Check file and directory permissions for the server process, then re-issue. |
| `OPP_RESOURCE_EXHAUSTED` | `reduce_input` | Split the batch into smaller chunks or compress images, then re-issue. |
| `OPP_TIMEOUT` | `retry` | Retry with a smaller input, or raise OPP_MCP_TIMEOUT for large documents. |
| `OPP_UNKNOWN_TOOL` | `fix_input` | Call one of the advertised OPP tools; check the tool name spelling. |
| `RATE_LIMITED` | `retry` | Wait for the rate-limit window to reset, then retry with lower concurrency. |

---

## OL Codes

Source: `ol_mcp/_errors.py:_ERROR_CODE_MAP`

| Code | Exception class | Meaning | When it occurs | Caller action |
|------|-----------------|---------|----------------|---------------|
| `OL_FILE_NOT_FOUND` | `FileNotFoundError` | A required file was not found. | Glossary path, TMX path, or config path doesn't exist. | Verify the file exists. |
| `OL_PERMISSION_DENIED` | `PermissionError` | Permission denied for the requested operation. | File is not readable by the server process. | Check file permissions. |
| `OL_PATH_DENIED` | `PathDeniedError` | Path is not within the allowed directories. | Path falls outside the `MCP_ALLOWED_DIRECTORIES` allowlist (or the legacy `OL_MCP_ALLOWED_DIRS` / `OL_ALLOWED_DIRECTORIES`). | Set `MCP_ALLOWED_DIRECTORIES` to include the path. |
| `OL_INVALID_INPUT` | `ValueError` | The request input was invalid. | Schema validation failed, or LLM returned unparseable output. | Validate input; retry may succeed if LLM transient. |
| `OL_MISSING_KEY` | `KeyError` | A required key was missing from the input. | A required field was omitted from the input model. | Check the tool's input schema. |
| `OL_TIMEOUT` | `TimeoutError` | The operation timed out. | LLM call exceeded timeout. | Retry; consider increasing timeout for large batches. |
| `OL_NOT_IMPLEMENTED` | `NotImplementedError` | The requested feature is not yet implemented. | A code path was hit that is stubbed or pending. | File a feature request. |
| `OL_INTERNAL_ERROR` | (any other exception) | An internal error occurred. Catch-all for unmapped exception classes. | Unexpected server-side failure (e.g., LiteLLM router failure, repair pipeline crash). | Check server logs. Retry may succeed if transient. |

Note: OL does **not** emit `OL_RESOURCE_EXHAUSTED`. Path validation is
enforced by `ol_mcp/security.py`; path denials are reported with the stable
`OL_PATH_DENIED` code (`PathDeniedError`).

### OL recovery hints (R-09)

Source: `ol_mcp/_errors.py:RECOVERY_HINTS`. `OL_UNKNOWN_TOOL`, `AUTH_FAILED`,
and `RATE_LIMITED` are declared here too because the server's dispatch, auth,
and rate-limit paths emit them.

| Code | Strategy | Hint |
|------|----------|------|
| `AUTH_FAILED` | `reissue_with_auth` | Re-issue the call with the correct auth_token matching MCP_SHARED_SECRET. |
| `OL_FILE_NOT_FOUND` | `fix_input` | Verify the glossary, TMX, or config file path exists, then re-issue. |
| `OL_INTERNAL_ERROR` | `report_bug` | Check server logs for the traceback; retry once only if the failure looks transient. |
| `OL_INVALID_INPUT` | `fix_input` | Validate the request against the tool's input schema; retry only if the LLM output was transient. |
| `OL_MISSING_KEY` | `fix_input` | Add the missing required field from the tool's input schema, then re-issue. |
| `OL_NOT_IMPLEMENTED` | `abort` | Do not retry; this code path is not implemented. File a feature request. |
| `OL_PATH_DENIED` | `use_allowed_path` | Set MCP_ALLOWED_DIRECTORIES to include the path, or use a path already inside it, then re-issue. |
| `OL_PERMISSION_DENIED` | `fix_input` | Check file permissions for the server process, then re-issue. |
| `OL_TIMEOUT` | `retry` | Retry, or raise the model timeout for large batches. |
| `OL_UNKNOWN_TOOL` | `fix_input` | Call one of the advertised OL tools; check the tool name spelling. |
| `RATE_LIMITED` | `retry` | Wait for the rate-limit window to reset, then retry with lower concurrency. |

---

## ORF Codes

Source: inline in `orf/mcp/server.py` (no centralized map).

ORF does not use a `_ERROR_CODE_MAP`. Instead, error codes are emitted
inline at each call site. The codes below are the full set currently
in use.

| Code | Meaning | When it occurs | Caller action |
|------|---------|----------------|---------------|
| `AUTH_FAILED` | Shared-secret auth rejected the call. | Same as the shared code above. | Same as above. |
| `PATH_NOT_ALLOWED` | Path is outside the allowlist, contains `..`, is a symlink to a disallowed target, or has a blocked extension. | Path validation failed in `PathValidator.validate_path()`. | Use a path within `ORF_MCP_ALLOWED_DIRS`. |
| `FILE_PATH_NOT_ALLOWED` | An image's `file_path` was rejected during XLIFF backfill. | An `ImagePlacement` carried a `file_path` that is not under the working directory. ORF refuses arbitrary file paths to prevent path-injection via XLIFF. | Re-emit the XLIFF with image files under the same directory as the XLIFF, or remove `file_path` from the placement. |
| `CLI_ERROR` | The underlying ORF CLI subprocess failed. | `orf` CLI exited non-zero, or the subprocess could not be started. | Check the CLI's stderr (returned in the response's `error` field). Retry if the error is transient (e.g., missing dependency). |

Note: ORF does not currently map generic Python exceptions (`FileNotFoundError`,
`PermissionError`, etc.) to stable codes — they bubble up as `CLI_ERROR` or
propagate as raw exception text. This is a known gap; see Phase B (observability)
for the planned fix.

### ORF recovery hints (R-09)

Source: `orf/mcp/_errors.py:RECOVERY_HINTS`. `error_response()` also mirrors the
strategy into `errors[0].recovery_strategy` for the existing error-list shape.

| Code | Strategy | Hint |
|------|----------|------|
| `AUTH_FAILED` | `reissue_with_auth` | Re-issue the call with the correct auth_token matching MCP_SHARED_SECRET. |
| `CLI_ERROR` | `retry` | Inspect the CLI stderr in the message; retry if transient (e.g. after installing a missing dependency). |
| `CLI_TIMEOUT` | `retry` | Retry with a smaller document, or raise ORF_MCP_TIMEOUT. |
| `EMPTY_OUTPUT` | `report_bug` | The CLI returned no output; check server logs and the CLI install, then file a bug if it persists. |
| `FILE_PATH_NOT_ALLOWED` | `fallback` | Re-emit the XLIFF with image files under the same directory as the XLIFF, or pass data_base64 instead of file_path. |
| `INLINE_CONTENT_WRITE_FAILED` | `report_bug` | Check disk space and write permissions for the temp directory, then file a bug if it persists. |
| `INLINE_REFERENCE_DOC_WRITE_FAILED` | `report_bug` | Check disk space and write permissions for the temp directory, then file a bug if it persists. |
| `JSON_PARSE_ERROR` | `report_bug` | The CLI emitted invalid JSON; check server logs and file a bug report. |
| `MISSING_INPUT` | `fix_input` | Provide either input_md (path) or content (inline markdown), then re-issue. |
| `MUTUALLY_EXCLUSIVE` | `fix_input` | Remove one of the mutually exclusive parameters, then re-issue. |
| `ORF_ERROR` | `report_bug` | Check server logs; the generic ORF error has no specific recovery. File a bug if it persists. |
| `ORF_INTERNAL_ERROR` | `report_bug` | Do not retry blindly; check server logs for the traceback and file a bug report. |
| `ORF_UNKNOWN_TOOL` | `fix_input` | Call one of the advertised ORF tools; check the tool name spelling. |
| `PATH_NOT_ALLOWED` | `use_allowed_path` | Use a path inside ORF_MCP_ALLOWED_DIRS, then re-issue. |
| `RATE_LIMITED` | `retry` | Wait for the rate-limit window to reset, then retry with lower concurrency. |

---

## omni-mcp Codes

Source: `omni_mcp/_errors.py:RECOVERY_HINTS`; envelopes are built by
`omni_mcp/_errors.py:error_response` (used by `omni_mcp/server.py` and
`omni_mcp/orchestrator.py`).

| Code | Meaning |
|------|---------|
| `AUTH_FAILED` | Shared-secret auth rejected the suite call. |
| `OMNI_PATH_DENIED` | Source path outside the suite allowlist (or no allowlist configured — fail CLOSED). |
| `FILE_NOT_FOUND` | Source document does not exist at the suite entry point. |
| `CLI_NOT_FOUND` | An OPP/OL/ORF CLI entry point could not be spawned. |
| `CLI_TIMEOUT` | A pipeline stage exceeded its configured timeout. |
| `CLI_EMPTY_OUTPUT` | A pipeline stage CLI returned no stdout. |
| `CLI_PARSE_ERROR` | A pipeline stage CLI emitted unparseable JSON. |
| `OPP_FAILED` | The OPP extraction stage failed. |
| `OPP_NO_MD` | OPP did not produce the expected Markdown output. |
| `OPP_NO_XLIFF` | OPP did not produce the expected XLIFF output. |
| `OL_FAILED` | The OL translation stage failed. |
| `OL_NO_OUTPUT` | OL did not produce the expected translated output. |
| `INVALID_PIPELINE` | Unknown pipeline type (not `md`/`xliff`). |
| `ORF_FAILED` | The ORF backfill stage failed. |
| `OUTPUT_NOT_FOUND` | Backfill reported success but the output file is absent. |
| `OMNI_INVALID_INPUT` | A tool argument failed validation. |
| `OMNI_VALIDATION_LOAD_ERROR` | The validation scenario library failed to load. |
| `OMNI_UNKNOWN_TOOL` | Unknown omni-mcp tool name. |
| `OMNI_INTERNAL_ERROR` | Unhandled exception in an omni-mcp tool. |

### omni-mcp recovery hints (R-09)

Source: `omni_mcp/_errors.py:RECOVERY_HINTS`.

| Code | Strategy | Hint |
|------|----------|------|
| `AUTH_FAILED` | `reissue_with_auth` | Re-issue the call with the shared_secret matching the server's MCP_SHARED_SECRET environment variable. |
| `CLI_EMPTY_OUTPUT` | `report_bug` | A pipeline stage CLI returned empty output; check server logs and file a bug report. |
| `CLI_NOT_FOUND` | `configure_environment` | Install the OPP/OL/ORF packages (or fix PATH) so the CLI entry point resolves, then re-issue. |
| `CLI_PARSE_ERROR` | `report_bug` | A pipeline stage CLI emitted unparseable output; check server logs and file a bug report. |
| `CLI_TIMEOUT` | `retry` | Retry, or raise the stage timeout for a large document. |
| `FILE_NOT_FOUND` | `fix_input` | Verify the source document path exists at the suite entry point, then re-issue. |
| `INVALID_PIPELINE` | `fix_input` | Pass pipeline='md' or pipeline='xliff' (or omit it), then re-issue. |
| `OL_FAILED` | `retry` | Read the OL error in the message; retry once (LLM failures are often transient), else fix the input. |
| `OL_NO_OUTPUT` | `report_bug` | OL produced no translated output; check server logs and file a bug report. |
| `OMNI_INTERNAL_ERROR` | `report_bug` | Do not retry blindly; check server logs for the traceback and file a bug report. |
| `OMNI_INVALID_INPUT` | `fix_input` | Validate the arguments against the tool's inputSchema, then re-issue. |
| `OMNI_PATH_DENIED` | `use_allowed_path` | Set MCP_ALLOWED_DIRECTORIES (or OMNI_MCP_ALLOWED_DIRS) to include the path, or use a path already inside it, then re-issue. |
| `OMNI_UNKNOWN_TOOL` | `fix_input` | Call one of the advertised omni-mcp tools; check the tool name spelling. |
| `OMNI_VALIDATION_LOAD_ERROR` | `configure_environment` | Fix the scenario library (missing or invalid scenario files), then re-issue. |
| `OPP_FAILED` | `fix_input` | Read the OPP error in the message; fix the input document or extraction settings, then retry. |
| `OPP_NO_MD` | `fix_input` | OPP produced no Markdown; verify the input format supports the MD path, then retry. |
| `OPP_NO_XLIFF` | `fallback` | OPP cannot produce XLIFF for this input (e.g. PDF); switch to the MD pipeline. |
| `ORF_FAILED` | `retry` | Read the ORF error in the message; retry once, else fix the input or output format. |
| `OUTPUT_NOT_FOUND` | `report_bug` | The backfill reported success but no output file exists; check server logs and file a bug report. |

---

## How to Add a New Error Code

1. **Choose the right module prefix**: `OPP_`, `OL_`, `ORF_`, or `OMNI_`
   (suite-level codes use `OMNI_`).
2. **Add to the map** (OPP/OL): edit `*/mcp/_errors.py:_ERROR_CODE_MAP`.
   For ORF, add the code string in `orf/mcp/_errors.py`. For omni-mcp, add it
   to `omni_mcp/_errors.py`.
3. **Add a safe user message** (OPP/OL): edit `_safe_user_message()` in the
   same file. ORF stores messages in `SAFE_USER_MESSAGES`; omni-mcp includes
   the message inline.
4. **Add a recovery hint**: add the code to the module's `RECOVERY_HINTS` map
   (strategy + static hint). Add the code to the module's
   `DECLARED_ERROR_CODES` (ORF/omni derive it from the map/registry).
5. **Update this document**: add a row to the relevant tables above.
6. **Add a test**: extend `tests/security/test_*_mcp_*.py` to cover the new
   code. The R-09 contract test (`tests/contract/test_recovery_hints_contract.py`)
   fails automatically if the new code lacks a recovery hint.

Do not reuse a code across modules. Do not change a code's string value
after it ships — clients may switch on it.
