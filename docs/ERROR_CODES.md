# MCP Error Code Catalog

**Status:** Stable. Codes are part of the public MCP contract — adding new
codes is fine, but **do not rename or remove** existing ones. Clients may
switch on them.

**Source of truth:**
- OPP: `Omni_Pre_Processor/src/opp/mcp/_errors.py` (`_ERROR_CODE_MAP`)
- OL: `Omni_Localizer/src/ol_mcp/_errors.py` (`_ERROR_CODE_MAP`)
- ORF: inline in `Omni_Re_Formatter/src/orf/mcp/server.py` (no centralized map)
- Auth (all 3): `*/mcp/auth.py` (`auth_failure_response()`)

---

## Response Shape

All 3 MCP servers return errors in a uniform shape:

```json
{
  "success": false,
  "error_code": "OPP_FILE_NOT_FOUND",
  "message": "A required file was not found."
}
```

OPP and ORF also include a legacy `"error"` field (string, same as `message`)
for backward compat with existing test assertions. New clients should
switch on `error_code` only.

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

---

## How to Add a New Error Code

1. **Choose the right module prefix**: `OPP_`, `OL_`, or `ORF_`.
2. **Add to the map** (OPP/OL): edit `*/mcp/_errors.py:_ERROR_CODE_MAP`.
   For ORF, add the code string at the call site.
3. **Add a safe user message** (OPP/OL): edit `_safe_user_message()` in the
   same file. ORF call sites include the message inline.
4. **Update this document**: add a row to the relevant table above.
5. **Add a test**: extend `tests/security/test_*_mcp_*.py` to cover the
   new code.

Do not reuse a code across modules. Do not change a code's string value
after it ships — clients may switch on it.
