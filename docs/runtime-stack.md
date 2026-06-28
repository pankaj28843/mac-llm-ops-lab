# Runtime Stack

This page separates static validation from runtime side effects.

## What Exists Now

The repo currently has:

- a fake-backend FastAPI API service
- a static runtime topology in `mac_llm_ops_lab.runtime_stack`
- `compose.yaml` wiring for PostgreSQL, Phoenix, Open WebUI, and the API
- a minimal API `Dockerfile`
- tests that validate the Compose file with `docker compose config`
- one local E2E proof run of the Docker-built fake-backend API stack
- one `vllm-mlx` standalone smoke with a downloaded MLX model
- one model-backed project API smoke, where this repo's FastAPI app proxied to
  the native `vllm-mlx` server through the OpenAI-compatible backend adapter
- one PostgreSQL migration and sample insert/read proof for persistence metadata
- one code-backed model catalog/download gate for the approved small MLX model
- code-backed OpenTelemetry instrumentation for HTTP, scheduler, backend,
  streaming, and SQLAlchemy Unit of Work spans
- one Phoenix trace export proof for API success, streaming, backend error, and
  database transaction spans
- one real-backend Phoenix trace proof for `openai-compatible` `vllm-mlx`
  chat, streaming, and cancelled stream spans
- one Open WebUI workflow proof where the UI discovered `fake-local-model`,
  submitted chat, and rendered a fake-backend response through the Compose API
- one Open WebUI workflow proof where the UI discovered
  `mlx-community/Qwen3-0.6B-8bit`, submitted chat, and reached the native
  `vllm-mlx` backend through this repo's model-backed API

The Apple Silicon backend is intentionally native and gated. It is not a
Compose service yet. The API can be switched from the fake backend to a native
host OpenAI-compatible backend with `MAC_LLM_OPS_BACKEND_KIND=openai-compatible`. The
first candidate is `vllm-mlx`. Future native starts go through
`mac_llm_ops_lab.model_catalog`, which requires a cataloged model,
explicit `MAC_LLM_OPS_MODEL_DOWNLOAD_APPROVED=true`, ignored cache policy, and a
passing memory preflight. The backend slice still needs
fuller benchmark workload qualification before production performance claims.

## Safe Static Checks

These commands do not start containers, create volumes, use real secrets, or
download models:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
docker compose -f compose.yaml config --format json
```

## Working Local E2E Proof

The first working local app/API proof used ignored local runtime inputs and
artifacts:

```bash
mkdir -p secrets artifacts/runtime/2026-06-28T145945+0200-e2e
# secrets/postgres_password.txt contains the local placeholder used by compose.
docker compose up -d --build
```

The default host bindings intentionally use high local ports:

```text
API: http://localhost:28000
Open WebUI: http://localhost:23000
Phoenix: http://localhost:26006
PostgreSQL: localhost:25432
OTLP gRPC: localhost:24317
Phoenix Prometheus: http://localhost:29090
```

Container-internal URLs still use service-native ports, such as
`http://api:8000/v1` and `http://phoenix:6006/v1/traces`.

The saved evidence bundle is under:

```text
artifacts/runtime/2026-06-28T145945+0200-e2e/
```

The proof includes:

- Docker API image build with `uv sync --frozen --no-dev`
- Postgres container health via `pg_isready`
- API `GET /live`
- API `GET /ready`
- API `GET /v1/models`
- API non-streaming `POST /v1/chat/completions`
- API streaming `POST /v1/chat/completions`
- API `GET /metrics/snapshot`
- Phoenix HTTP `200 OK` on the mapped local UI port
- Open WebUI healthy container and root HTML on the mapped local UI port
- Open WebUI default embedding asset download into its Docker volume

Open WebUI root reachability is proven here only. Later browser workflow proof
for fake and native backends is recorded in the Open WebUI workflow sections
below.

## vllm-mlx Standalone Smoke

A native `vllm-mlx standalone smoke` also passed outside the project API
container:

```bash
uv tool install --python 3.12 vllm-mlx
HF_HOME="$PWD/model-cache/huggingface" \
  vllm-mlx download mlx-community/Qwen3-0.6B-8bit
HF_HOME="$PWD/model-cache/huggingface" \
  vllm-mlx serve mlx-community/Qwen3-0.6B-8bit \
  --served-model-name mlx-qwen3-0.6b-8bit \
  --host 127.0.0.1 \
  --port 28100 \
  --max-request-tokens 128 \
  --max-tokens 64 \
  --max-num-seqs 2 \
  --cache-memory-mb 512 \
  --continuous-batching \
  --stream-interval 1 \
  --enable-metrics
```

The saved evidence bundle is under:

```text
artifacts/runtime/2026-06-28T151600+0200-vllm-mlx/
```

The proof includes install/import/version output for `vllm-mlx` 0.3.0 and MLX
0.31.2, MLX GPU device detection, ignored Hugging Face cache use under
`model-cache/`, a preflight under the 24 GiB local ceiling, model download,
`/v1/models`, non-streaming chat, streaming chat, and `/metrics`. The native
server was stopped after the smoke to free local memory.

## Model-Backed Project API Smoke

The project API now has an OpenAI-compatible backend adapter and an env-driven
backend switch. With the downloaded MLX model available under ignored
`model-cache/`, this native backend command starts the local model server:

```bash
MODEL_ID=mlx-community/Qwen3-0.6B-8bit \
VLLM_MLX_PORT=28100 \
scripts/run-vllm-mlx-backend.sh
```

In a second shell, start this repo's API against that backend:

```bash
MODEL_ID=mlx-community/Qwen3-0.6B-8bit \
MAC_LLM_OPS_BACKEND_KIND=openai-compatible \
MAC_LLM_OPS_OPENAI_BASE_URL=http://127.0.0.1:28100/v1 \
API_PORT=28020 \
scripts/run-model-backed-api.sh
```

The saved evidence bundle is under:

```text
artifacts/runtime/2026-06-28T153000+0200-model-backed-api-e2e/
```

The original proof used lower temporary ports; current runbook defaults use
`vllm-mlx` on `127.0.0.1:28100` and this repo's FastAPI app on
`127.0.0.1:28020`.
It includes project API `GET /live`, `GET /ready`, `GET /v1/models`,
non-streaming `POST /v1/chat/completions`, streaming
`POST /v1/chat/completions`, project API `GET /metrics/snapshot`, and the
backend `/metrics` head. The API adapter path is now code-backed and tested;
Open WebUI against the real backend is proven separately below, while fuller
benchmark proof remains a separate gate.

## Real-Backend Phoenix Trace Proof

The model-backed API has also been run with OpenTelemetry enabled against the
native `vllm-mlx` backend on high local ports:

```bash
VLLM_MLX_PORT=28100 scripts/run-vllm-mlx-backend.sh
MAC_LLM_OPS_BACKEND_KIND=openai-compatible \
MAC_LLM_OPS_OPENAI_BASE_URL=http://127.0.0.1:28100/v1 \
MAC_LLM_OPS_OTEL_ENABLED=true \
MAC_LLM_OPS_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:26006/v1/traces \
API_PORT=28020 \
scripts/run-model-backed-api.sh
```

The saved evidence bundle is under:

```text
artifacts/runtime/2026-06-28T173605+0200-vllm-mlx-phoenix-real-backend/
```

The proof includes real-backend non-streaming chat, streaming chat, an
intentionally interrupted stream, Phoenix/PostgreSQL span queries for
`openai-compatible` HTTP, scheduler, `gen_ai.chat`, `gen_ai.stream`, and
cancelled stream spans, plus a publish-safety scan over the trace/query proof
files.

## Model Download Gate

The first approved local model is `mlx-community/Qwen3-0.6B-8bit`, pinned in
the project catalog with Hugging Face model-card metadata, revision
`11de96878523501bcaa86104e3c186de07ff9068`, `apache-2.0` license, MLX tags,
and a 4.7 GiB local runtime estimate. Run the CPU-safe gate without starting
the model:

```bash
uv run python -m mac_llm_ops_lab.model_catalog mlx-community/Qwen3-0.6B-8bit
```

That command denies by default. To allow a local run:

```bash
MAC_LLM_OPS_MODEL_DOWNLOAD_APPROVED=true \
MODEL_DOWNLOAD_GATE_REPORT=artifacts/runtime/vllm-mlx-model-download-gate.json \
uv run python -m mac_llm_ops_lab.model_catalog mlx-community/Qwen3-0.6B-8bit
```

`scripts/run-vllm-mlx-backend.sh` invokes the same gate before `vllm-mlx serve`.
See `docs/model-catalog.md` for source evidence and cache policy.

## Open WebUI Workflow Proof

Open WebUI is configured as an OpenAI-compatible frontend for this repo's API.
The Compose profile uses:

```text
OPENAI_API_BASE_URLS=http://api:8000/v1
OPENAI_API_KEYS=local-dev-placeholder
WEBUI_AUTH=False
ENABLE_PERSISTENT_CONFIG=False
ENABLE_OLLAMA_API=False
```

The saved evidence bundle is under:

```text
artifacts/runtime/2026-06-28T163030+0200-open-webui/
```

The proof includes rebuilt API image output, recreated healthy Open WebUI
container state, direct API probes for `/v1/models`, chat, streaming, and
metrics, headed-CDP browser evidence showing `fake-local-model`, redacted
network evidence for `POST /api/chat/completions` through Open WebUI, project
API logs showing Open WebUI's container calling `GET /v1/models` and
`POST /v1/chat/completions`, and a clean publish-safety scan over the saved
evidence.

Open WebUI is also proven against the native model-backed path. A separate
standalone container ran on `http://127.0.0.1:23001` with:

```text
OPENAI_API_BASE_URLS=http://host.docker.internal:28020/v1
OPENAI_API_KEYS=local-dev-placeholder
WEBUI_AUTH=False
ENABLE_PERSISTENT_CONFIG=False
ENABLE_OLLAMA_API=False
```

The saved native-backend evidence bundle is under:

```text
artifacts/runtime/2026-06-28T174936+0200-open-webui-native-backend/
```

That proof includes direct API checks against `http://127.0.0.1:28020/v1`,
native backend checks against `127.0.0.1:28100`, Open WebUI health/root HTML,
headed-CDP browser evidence showing `mlx-community/Qwen3-0.6B-8bit`, redacted
network evidence for `POST /api/chat/completions` through Open WebUI, project
API and backend logs showing `/v1/chat/completions`, API metrics showing token
generation, and Phoenix spans after the saved watermark for successful
`POST /v1/chat/completions`, `gen_ai.stream`, and `gen_ai.chat`.

Known caveats: Open WebUI background generation triggered one native
`/v1/chat/completions` 502 after the successful foreground chat, and the
64-token Qwen3 smoke rendered little visible final-answer text. Treat this as
connectivity and trace proof, not as a UX quality or performance benchmark.

## Still Not Complete

The local E2E proof is intentionally narrower than production readiness. These
claims are not complete yet:

- production secret management beyond the ignored local placeholder file
- production model-cache retention and cleanup policy beyond ignored
  `model-cache/`
- production runtime-artifact retention policy beyond ignored `artifacts/runtime/`
- fuller benchmark workload qualification for the real backend

`secrets/`, `model-cache/`, traces, logs, raw benchmarks, database files, and
runtime artifacts must stay out of git.

## OpenTelemetry And Phoenix

The API now has manual OpenTelemetry instrumentation. The static tests prove
bounded prompt-safe span attributes for request, scheduler, backend generation,
streaming error/token, and database transaction paths. The Compose API service
sets:

```text
MAC_LLM_OPS_OTEL_ENABLED=true
MAC_LLM_OPS_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://phoenix:6006/v1/traces
MAC_LLM_OPS_PHOENIX_PROJECT_NAME=mac-llm-ops-lab-local
```

For a host-run API against the locally mapped Phoenix UI port, use:

```bash
MAC_LLM_OPS_OTEL_ENABLED=true \
MAC_LLM_OPS_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:26006/v1/traces \
MAC_LLM_OPS_PHOENIX_PROJECT_NAME=mac-llm-ops-lab-local \
uv run uvicorn mac_llm_ops_lab.cli:app --host 127.0.0.1 --port 28020
```

Saved proof under `artifacts/runtime/2026-06-28T160713+0200-phoenix-otel/`
shows local Phoenix received prompt-safe HTTP, scheduler, backend, streaming
token/error, and database transaction spans. Real-backend proof under
`artifacts/runtime/2026-06-28T173605+0200-vllm-mlx-phoenix-real-backend/`
shows the `openai-compatible` `vllm-mlx` path emitting chat, stream, and
cancelled stream spans. See `docs/observability.md` for the prompt-safety
contract and the evidence requirements for future runs.

## Current Service Intent

PostgreSQL stores future model catalog, run metadata, benchmark, and node
inventory records.

Phoenix receives OpenTelemetry traces for HTTP, scheduling, backend calls,
streaming, database writes, and benchmark runs.

Open WebUI connects to the local OpenAI-compatible API. In Compose, it uses
`http://api:8000/v1`; when running Open WebUI outside Compose against a host
API process, use the appropriate host URL.

The API service is still safe to import and test without Docker, PostgreSQL,
Phoenix, Open WebUI, `vllm-mlx`, or model downloads.
