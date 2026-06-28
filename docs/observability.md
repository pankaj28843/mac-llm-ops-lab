# Observability

This project uses manual OpenTelemetry spans around the API request path,
scheduling boundary, backend generation/streaming calls, and SQLAlchemy Unit of
Work transactions. The implementation is app-local: importing the ASGI target
does not configure a global tracer provider and does not require Phoenix or any
exporter unless telemetry is explicitly enabled.

## Source Surface

- Local `docsearch` tenant `opentelemetry-specs` from `https://opentelemetry.io`
  confirms OTLP/HTTP signal-specific trace endpoints are used as-is, while the
  generic OTLP endpoint appends `/v1/traces`.
- Local `docsearch` tenant `otel-semconv` from `https://opentelemetry.io`
  confirms HTTP server spans should use low-cardinality routes such as
  `http.route`, and GenAI message content fields are opt-in.
- Local `docsearch` tenant `phoenix` from `https://arize.com` confirms Phoenix
  has a separate application endpoint and OpenTelemetry tracing endpoint.
- Local dependency version: OpenTelemetry Python packages resolved to `1.43.0`.

## Configuration

Telemetry is disabled by default:

```bash
MAC_LLM_OPS_OTEL_ENABLED=false
```

Enable Phoenix export for a host-run API:

```bash
MAC_LLM_OPS_OTEL_ENABLED=true \
MAC_LLM_OPS_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:16006/v1/traces \
MAC_LLM_OPS_PHOENIX_PROJECT_NAME=mac-llm-ops-lab-local \
uv run uvicorn mac_llm_ops_lab.cli:app --host 127.0.0.1 --port 8020
```

In Compose, the API defaults to:

```text
MAC_LLM_OPS_OTEL_ENABLED=true
MAC_LLM_OPS_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://phoenix:6006/v1/traces
MAC_LLM_OPS_PHOENIX_PROJECT_NAME=mac-llm-ops-lab-local
```

Use `MAC_LLM_OPS_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` for the exact OTLP/HTTP traces
URL. `MAC_LLM_OPS_PHOENIX_COLLECTOR_ENDPOINT` or `PHOENIX_COLLECTOR_ENDPOINT` is also
accepted as a fallback for local Phoenix compatibility.

## Data Safety

Default telemetry does not capture prompts, completions, request bodies, HTTP
headers, API keys, exception messages, local file paths, or model-cache paths.
The app records bounded labels and counters instead:

- `http.request.method`, `http.route`, `http.response.status_code`
- `mac_llm_ops.request.id`, `mac_llm_ops.backend.kind`, `mac_llm_ops.model.id`
- `mac_llm_ops.queue.wait_ms`
- `gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.request.model`
- `gen_ai.response.model`, `gen_ai.usage.input_tokens`,
  `gen_ai.usage.output_tokens`
- `mac_llm_ops.stream.cancelled` and `gen_ai.response.finish_reasons=("cancelled",)`
  for client-cancelled streaming responses
- `error.type` for low-cardinality failure classes
- `db.system.name`, `db.operation.name`, `db.transaction.outcome`

`MAC_LLM_OPS_OTEL_CAPTURE_CONTENT` defaults to `false` and is reserved for future
explicit, local-only debugging. It is not used by the current instrumentation.

## Local Proof

Automated contract:

```bash
uv run pytest tests/test_observability.py
```

Runtime proof must save a publish-safe artifact bundle under
`artifacts/runtime/<timestamp>-phoenix-otel/` with:

- API request samples for success, streaming, and error paths
- a Phoenix trace export or query artifact showing HTTP, scheduler, backend,
  token, stream/error/cancellation, and database spans where exercised
- a text check proving raw prompts, completions, secrets, and machine-local
  paths are absent from saved trace artifacts

Current saved proof exists under
`artifacts/runtime/2026-06-28T160713+0200-phoenix-otel/`. That bundle shows
Phoenix trace receipt for HTTP, scheduler, backend generation, streaming token
and error, and `db.transaction` spans, plus a publish-safety grep over saved
trace artifacts.
