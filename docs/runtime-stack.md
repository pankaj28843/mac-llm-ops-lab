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

The Apple Silicon backend is intentionally native and gated. It is not a
Compose service yet. The API can be switched from the fake backend to a native
host OpenAI-compatible backend with `MAC_LLM_OPS_BACKEND_KIND=openai-compatible`. The
first candidate is `vllm-mlx`, but it still needs cancellation, Phoenix trace,
and benchmark gates before the backend slice is complete.

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
PHOENIX_HOST_PORT=16006 docker compose up -d --build
```

`PHOENIX_HOST_PORT=16006` was needed on this MacBook because another local
Docker project already owned `localhost:6006`. Without that collision, the
default Phoenix URL remains `http://localhost:6006`.

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
- Phoenix HTTP `200 OK` on `http://localhost:16006/`
- Open WebUI healthy container and root HTML on `http://localhost:3000/`
- Open WebUI default embedding asset download into its Docker volume

Open WebUI root reachability is proven; its backend API probes returned `401`
for unauthenticated direct curl calls. A browser workflow or authenticated API
contract is still needed before claiming Open WebUI chat workflow integration.

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
  --port 8100 \
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
MODEL_ID=mlx-community/Qwen3-0.6B-8bit scripts/run-vllm-mlx-backend.sh
```

In a second shell, start this repo's API against that backend:

```bash
MODEL_ID=mlx-community/Qwen3-0.6B-8bit \
MAC_LLM_OPS_BACKEND_KIND=openai-compatible \
MAC_LLM_OPS_OPENAI_BASE_URL=http://127.0.0.1:8100/v1 \
API_PORT=8020 \
scripts/run-model-backed-api.sh
```

The saved evidence bundle is under:

```text
artifacts/runtime/2026-06-28T153000+0200-model-backed-api-e2e/
```

The proof used `vllm-mlx` on `127.0.0.1:8100` and this repo's FastAPI app on
`127.0.0.1:8020` because local ports `8000` and `8010` were already occupied.
It includes project API `GET /live`, `GET /ready`, `GET /v1/models`,
non-streaming `POST /v1/chat/completions`, streaming
`POST /v1/chat/completions`, project API `GET /metrics/snapshot`, and the
backend `/metrics` head. The API adapter path is now code-backed and tested;
Open WebUI workflow, Phoenix trace export, cancellation, and benchmark proof
remain separate gates.

## Still Not Complete

The local E2E proof is intentionally narrower than production readiness. These
claims are not complete yet:

- production secret management beyond the ignored local placeholder file
- PostgreSQL migration and sample persistence proof
- Phoenix OpenTelemetry trace export proof
- Open WebUI model listing and chat smoke proof through its UI/API workflow
- model-cache policy under ignored `model-cache/`
- runtime artifacts under ignored `artifacts/runtime/`
- cancellation, benchmark, and Phoenix trace proof for the real backend

`secrets/`, `model-cache/`, traces, logs, raw benchmarks, database files, and
runtime artifacts must stay out of git.

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
