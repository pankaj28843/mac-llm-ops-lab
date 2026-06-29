# Evidence

Evidence is the boundary between "the code says this should work" and "the lab
has a saved proof." Runtime artifacts stay under ignored `artifacts/runtime/`;
docs summarize only publish-safe conclusions.

## Current Proof Index

| Proof | Bundle |
| --- | --- |
| Docker fake-backend API stack with PostgreSQL, Phoenix, and Open WebUI | `artifacts/runtime/2026-06-28T145945+0200-e2e/` |
| Native `vllm-mlx standalone smoke` | `artifacts/runtime/2026-06-28T151600+0200-vllm-mlx/` |
| Model-backed project API against native backend | `artifacts/runtime/2026-06-28T153000+0200-model-backed-api-e2e/` |
| PostgreSQL persistence migration and sample Unit of Work | `artifacts/runtime/2026-06-28T154545+0200-postgres-persistence/` |
| Phoenix/OpenTelemetry fake-backend proof | `artifacts/runtime/2026-06-28T160713+0200-phoenix-otel/` |
| Open WebUI fake-backend proof | `artifacts/runtime/2026-06-28T163030+0200-open-webui/` |
| Real-backend Phoenix trace proof | `artifacts/runtime/2026-06-28T173605+0200-vllm-mlx-phoenix-real-backend/` |
| Open WebUI native-backend proof | `artifacts/runtime/2026-06-28T174936+0200-open-webui-native-backend/` |
| MacBook benchmark baseline | `artifacts/runtime/2026-06-28T183228+0200-slice15-macbook-benchmark/` |
| Open WebUI visible-answer regression proof | `artifacts/runtime/2026-06-28T195945+0200-open-webui-visible-answer-no-think/` |

## Runtime Boundary

Static validation does not start containers, create volumes, use real secrets,
or download models:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
docker compose -f compose.yaml config --format json
uv run mkdocs build --strict
```

The first working local app/API proof used:

```bash
mkdir -p secrets artifacts/runtime
printf 'local-dev-password\n' > secrets/postgres_password.txt
docker compose up -d --build
```

The proof included `GET /live`, `GET /ready`, `GET /v1/models`, non-streaming
and streaming `POST /v1/chat/completions`, `GET /metrics/snapshot`,
PostgreSQL health, Phoenix reachability, and Open WebUI reachability.

## Backend Metrics

The parser in `mac_llm_ops_lab.backend_contracts` turns raw `vllm-mlx` output
into JSON-safe summaries. Required metrics include:

- `vllm_mlx_http_requests_total`
- `vllm_mlx_inference_requests_total`
- `vllm_mlx_prompt_tokens_total`
- `vllm_mlx_completion_tokens_total`
- `vllm_mlx_model_loaded`
- `vllm_mlx_engine_type`
- `vllm_mlx_scheduler_waiting_requests`
- `vllm_mlx_scheduler_running_requests`
- `vllm_mlx_metal_memory_bytes`
- `vllm_mlx_cache_hit_rate`

Use `vllm-mlx bench-serve` for bounded HTTP benchmarks against a running
native backend:

```bash
uv tool run vllm-mlx bench-serve \
  --url http://127.0.0.1:28100 \
  --model mlx-community/Qwen3-0.6B-8bit \
  --prompts short \
  --concurrency 1 \
  --max-tokens 4 \
  --repetitions 1 \
  --warmup 0 \
  --format json \
  --output artifacts/runtime/<run>/bench-smoke.json
```

A tiny smoke may report `validated:false`. That is acceptable for command
surface and metrics smoke only; `validated:false is smoke-only` and cannot
support quality, UX, latency, throughput, cost, or Mac Studio capacity claims.

## Benchmark Workload Policy

The machine-readable policy is exposed by
`mac_llm_ops_lab.backend_contracts.build_benchmark_workload_policy()`.
It requires latency/throughput separation, warmup before measurement, repeated
runs, target-platform labels, and Phoenix GenAI spans.

Supported workload names:

- `smoke_short`
- `conversational_sharegpt`
- `prefix_repetition_cache`

Every benchmark artifact needs model id, model revision, quantization, backend,
command, git SHA, prompt set, input token distribution, output token target,
concurrency, request rate, warmup, repetitions, TTFT, TPOT or ITL, request
throughput, Metal memory, cache metrics, error rate, and validation state.

Fuller bundles need a `benchmark-artifact-manifest.json` with
`raw_benchmark_path`, `summary_path`, and `no_leak_scan`. The manifest rejects
absolute paths, parent traversal, local ports outside `20000-50000`, and failed
publish-safety scans.

The current MacBook baseline produced structurally valid evidence, but
`production_performance_claim_supported: false`. It is not a quality benchmark,
production performance claim, UX proof, or Mac Studio capacity claim.

## Observability

This project uses manual OpenTelemetry spans around HTTP, scheduling, backend
generation/streaming, cancellation, and SQLAlchemy Unit of Work transactions.
Importing the ASGI target does not configure a global tracer provider and does
not require Phoenix unless telemetry is explicitly enabled.

Prompt safety is deliberate. Default telemetry does not capture prompts,
completions, request bodies, HTTP headers, API keys, exception messages, local
file paths, or model-cache paths. The app records bounded labels and counters:

- `gen_ai.usage.input_tokens`
- `gen_ai.usage.output_tokens`
- `mac_llm_ops.stream.cancelled`
- `gen_ai.response.finish_reasons=("cancelled",)`
- `db.transaction.outcome`

The Phoenix proof shows prompt-safe HTTP, scheduler, backend, streaming token
and error, and `db.transaction` spans. The real-backend proof shows the
`openai-compatible` `vllm-mlx` path emitting chat, stream, and cancelled stream
spans for `mlx-community/Qwen3-0.6B-8bit`.

## Persistence

PostgreSQL stores model catalog records, Mac node inventory, inference run
metadata, benchmark summaries, and runtime artifact pointers. The application
uses plain domain dataclasses plus Repository and Unit of Work ports. FastAPI
request handlers do not import SQLAlchemy or Alembic adapters.

Run migrations against the local Compose PostgreSQL service with:

```bash
POSTGRES_PASSWORD_VALUE="$(tr -d '\n' < secrets/postgres_password.txt)"
DATABASE_URL="postgresql+asyncpg://llm_serving:${POSTGRES_PASSWORD_VALUE}@127.0.0.1:${POSTGRES_HOST_PORT:-5432}/llm_serving" \
  uv run alembic upgrade head
```

The Alembic version table is `mac_llm_ops_alembic_version`. The first
persistence proof created the schema, confirmed `model_catalog`,
`node_inventory`, `inference_runs`, `benchmark_results`, and
`artifact_pointers`, then performed a sample insert/read through
`SQLAlchemyUnitOfWork`.

## MacBook To Mac Studio Boundary

Measured on this MacBook Pro means local development baseline only. Do not
extrapolate those results into Mac Studio cluster throughput, cluster latency,
capacity planning, failover behavior, queue depth targets, or Open WebUI
multi-user UX claims.

Mac Studio cluster claims require Mac Studio runs with node count, chip
generation, unified memory, network topology, routing policy, same model
revision, same benchmark workload policy, per-node spans, routed-cluster spans,
backend metrics, benchmark rows, and publish-safe artifacts.

Until that evidence exists, supported claims are limited to: this MacBook can
run the approved small MLX model, serve through the native backend and project
API on high local ports, emit telemetry, and produce a structurally valid local
benchmark bundle with caveats.
