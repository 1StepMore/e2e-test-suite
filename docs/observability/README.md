# Observability

> **Status**: metrics surface shipped (Phase 4.5); structured logging
> still in flight (`bg_86b8db38`).

## Artifacts

- `METRICS.md` — module-prefixed counters and histograms for the
  three MCP servers (this file)
- `SCRAPE_CONFIG.yml` — example Prometheus scrape config
- `STRUCTURED_LOGGING.md` — `structlog` configuration (scaffold;
  lands with `bg_86b8db38`)

## METRICS.md

Each module emits its own Prometheus textfile under
`OMNI_METRICS_DIR` (default `/tmp/omni-metrics/`):

| File | Module | Owner |
|------|--------|-------|
| `opp.prom` | Omni Pre-Processor | `opp.mcp.metrics` |
| `ol.prom`  | Omni Localizer     | `ol_mcp.metrics` |
| `orf.prom` | Omni Re-Formatter  | `orf.mcp.metrics` |

`write_to_textfile()` is called on every recorded request and uses
atomic `.tmp → final` rename, so concurrent scrapes always see a
complete file.

### Metric Names

All per-module metrics are prefixed with the module name and follow
the Prometheus naming convention (`_total` suffix on counters,
`_seconds` suffix on duration histograms).

#### OPP (`opp.prom`)

| Metric | Type | Labels | Notes |
|--------|------|--------|-------|
| `opp_requests_total` | counter | `tool_name`, `status` | One per MCP tool call. |
| `opp_request_duration_seconds` | histogram | `tool_name` | Buckets: 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10. |
| `opp_extractions_total` | counter | `format`, `status` | One per extraction (source format). |

`status` values: `success`, `error`, `rate_limited`, `auth_failed`.
`format` values: source document extension (e.g. `docx`, `pdf`,
`json`, `epub`); `unknown` if the path has no recognized extension.

#### OL (`ol.prom`)

| Metric | Type | Labels | Notes |
|--------|------|--------|-------|
| `ol_requests_total` | counter | `tool_name`, `status` | One per MCP tool call. |
| `ol_request_duration_seconds` | histogram | `tool_name` | Same buckets as OPP. |
| `ol_translations_total` | counter | `source_lang`, `target_lang`, `mode` | `mode` is `md` or `xliff`. Success-only (failures don't inflate the translation count). |

#### ORF (`orf.prom`)

| Metric | Type | Labels | Notes |
|--------|------|--------|-------|
| `orf_requests_total` | counter | `tool_name`, `status` | One per MCP tool call. |
| `orf_request_duration_seconds` | histogram | `tool_name` | Same buckets as OPP. |
| `orf_backfills_total` | counter | `target_format`, `status` | One per `apply_md` / `apply_xliff` / `batch_convert` call. |

`target_format` is normalised to lowercase (e.g. `docx`, `epub`, `html`).

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OMNI_METRICS_DIR` | `/tmp/omni-metrics` | Directory for `.prom` textfiles. |
| `OMNI_RATE_LIMIT_RPM` | `60` | Token-bucket RPM (set to `0` to disable). |
| `OMNI_RATE_LIMIT_BURST` | `10` | Token-bucket burst size. |
| `MCP_SHARED_SECRET` | (unset) | When set, every tool call must include the matching `auth_token` (or `shared_secret` for OL). |

### Why file-based (not HTTP)?

The MCP servers use **stdio** transport. Anything written to stdout
breaks the JSON-RPC stream. A separate metrics port (HTTP) would
require a parallel process or a forked socket inside the MCP server,
both of which add operational complexity. The textfile approach:

- never touches the stdio stream
- works with the existing `mcp.server.stdio.stdio_server()` pattern
- is atomic (`write_to_textfile` renames `.tmp` → final)
- is zero-cost when `OMNI_METRICS_DIR` is set to a tmpfs

### Wired From

- OPP: `Omni_Pre_Processor/src/opp/mcp/server.py` (`_handle_call_tool`)
- OL: `Omni_Localizer/src/ol_mcp/tools.py` (`_call_tool`)
- ORF: `Omni_Re_Formatter/src/orf/mcp/server.py` (`_call_tool`)

## SCRAPE_CONFIG.yml

```yaml
scrape_configs:
  - job_name: omni_opp
    static_configs:
      - targets: ['127.0.0.1:8766']  # OPP MCP server (when started in HTTP mode)

  - job_name: omni_ol
    static_configs:
      - targets: ['127.0.0.1:8767']  # OL MCP server (HTTP mode)

  - job_name: omni_orf
    static_configs:
      - targets: ['127.0.0.1:8765']  # ORF MCP server (HTTP mode)

  - job_name: omni_textfiles
    file_sd_configs:
      - files:
          - /tmp/omni-metrics/*.prom
```

For now, the production deployment scrapes the textfiles (last
job). The HTTP scrape configs are placeholders for when the
Prometheus exporter port is added.

### Validate offline with `promtool`

```bash
promtool check metrics /tmp/omni-metrics/opp.prom
promtool check metrics /tmp/omni-metrics/ol.prom
promtool check metrics /tmp/omni-metrics/orf.prom
```

## How to verify

```bash
# Run the metrics tests
make test-metrics

# Inspect a sample emitted metric line
cat /tmp/omni-metrics/opp.prom | head -10
cat /tmp/omni-metrics/ol.prom  | head -10
cat /tmp/omni-metrics/orf.prom | head -10
```
