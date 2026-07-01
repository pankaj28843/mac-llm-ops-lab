# Mac LLM Ops Lab

[![Publish Docs](https://github.com/pankaj28843/mac-llm-ops-lab/actions/workflows/pages.yml/badge.svg)](https://github.com/pankaj28843/mac-llm-ops-lab/actions/workflows/pages.yml)

Mac-first LLM serving lab for learning production serving patterns on Apple
Silicon. The project is built around a FastAPI OpenAI-compatible API, a
CPU-safe fake backend, a gated native `vllm-mlx` backend path, PostgreSQL
persistence, Phoenix/OpenTelemetry traces, Open WebUI, MkDocs, and saved
local validation.

- Published docs: <https://pankaj28843.github.io/mac-llm-ops-lab/>
- GitHub repo: <https://github.com/pankaj28843/mac-llm-ops-lab>
- Docs CI/CD: `.github/workflows/pages.yml` (`Publish Docs`) builds `docs/`
  with `uv run mkdocs build --strict` and deploys the `site/` artifact through
  GitHub Pages.

This repository does not vendor purchased source exports, local model caches,
traces, secrets, database files, logs, or private benchmark payloads.

## Current Boundary

This is not full production certification. The fake-backend API, local Docker
stack, Open WebUI path, Phoenix tracing, MkDocs site, release/no-leak checks,
and benchmark structure are complete for local learning. The test-double
cluster routing contract is code-backed, but real multi-node proof is still
required before any Mac Studio cluster claim. Mac Studio cluster capacity,
failover, and multi-user performance remain pending until real cluster
validation exists.

## Quick Start

```bash
uv sync
make help
make validate
uv run mkdocs serve -a 127.0.0.1:28080
```

`make validate` runs the local proof contract:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
docker compose -f compose.yaml config --format json
uv run mkdocs build --strict
uv run python scripts/validate-public-release.py --output artifacts/runtime/release-readiness/public-release-check.json
```

The CPU-safe ASGI target is:

```text
mac_llm_ops_lab.cli:app
```

Importing it builds the FastAPI app with `FakeBatchedBackend`; it does not
download models, start Docker, connect to PostgreSQL, emit Phoenix traces, or
require Open WebUI.

Use the local stack helpers for runtime lifecycle work:

```bash
make build
make up
make status
make down
```

`make up` starts Docker, native `vllm-mlx` with
`mlx-community/Qwen3-0.6B-8bit`, the model-backed API, the Compose stack
configured for the OpenAI-compatible backend, and the project-managed
non-Docker docs server. `make down` is the memory-release path: it stops
project-managed host processes, unloads native `vllm-mlx`/model-backed API
processes when present, stops matching `vllm`/MLX containers, brings Compose
down, and cleans up repo-specific host listeners. Docker Desktop is left
running because other projects may have containers or use its VM.

## Local Runtime Shape

Default local bindings intentionally use high ports:

| Component | URL or Port |
| --- | --- |
| API | `http://localhost:28000` |
| Open WebUI | `http://localhost:23000` |
| Phoenix | `http://localhost:26006` |
| PostgreSQL | `localhost:25432` |
| OTLP gRPC | `localhost:24317` |
| Phoenix Prometheus | `http://localhost:29090` |
| Native `vllm-mlx` | `http://127.0.0.1:28100` |
| Native model-backed API | `http://127.0.0.1:28020` |

Future real-model runtime checks must pass the CPU-safe preflight guard in
`mac_llm_ops_lab.runtime_guard` first. Model downloads and native backend
starts are gated by `mac_llm_ops_lab.model_catalog`,
`MAC_LLM_OPS_MODEL_DOWNLOAD_APPROVED=true`, a passing 24 GiB memory preflight, and the
ignored cache policy.

## Native Backend Smoke

Start the approved small MLX model with enough Qwen3 budget for a visible Open
WebUI answer:

```bash
MODEL_ID=mlx-community/Qwen3-0.6B-8bit \
VLLM_MLX_PORT=28100 \
VLLM_MLX_MAX_TOKENS=512 \
VLLM_MLX_MAX_REQUEST_TOKENS=1024 \
VLLM_MLX_REASONING_PARSER=qwen3 \
VLLM_MLX_DEFAULT_CHAT_TEMPLATE_KWARGS='{"enable_thinking": false}' \
scripts/run-vllm-mlx-backend.sh
```

Then run this repo's model-backed API:

```bash
MODEL_ID=mlx-community/Qwen3-0.6B-8bit \
MAC_LLM_OPS_BACKEND_KIND=openai-compatible \
MAC_LLM_OPS_OPENAI_BASE_URL=http://127.0.0.1:28100/v1 \
API_PORT=28020 \
scripts/run-model-backed-api.sh
```

Use `/live`, `/ready`, `/v1/models`, `/v1/chat/completions`, streaming chat,
`/metrics/snapshot`, backend metrics, and Phoenix spans to validate a local
run.

## Docs Map

- [Development](docs/development.md): setup, validation, native backend starts.
- [Operations](docs/operations.md): Docker, Open WebUI, and Phoenix runbook.
- [Design](docs/design.md): architecture, request, and validation diagrams.
- [Mac Studio Cluster](docs/mac-studio-cluster.md): unsupported cluster claims.
- [Release Readiness](docs/release-readiness.md): public repo and no-leak gate.
