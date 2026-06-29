# Mac LLM Ops Lab

[![Publish Docs](https://github.com/pankaj28843/mac-llm-ops-lab/actions/workflows/pages.yml/badge.svg)](https://github.com/pankaj28843/mac-llm-ops-lab/actions/workflows/pages.yml)

Mac-first LLM serving lab for learning production serving patterns on Apple
Silicon. The project is built around a FastAPI OpenAI-compatible API, a
CPU-safe fake backend, a gated native `vllm-mlx` backend path, PostgreSQL
persistence, Phoenix/OpenTelemetry traces, Open WebUI, MkDocs, and saved
runtime evidence.

- Published docs: <https://pankaj28843.github.io/mac-llm-ops-lab/>
- GitHub repo: <https://github.com/pankaj28843/mac-llm-ops-lab>
- Docs CI/CD: `.github/workflows/pages.yml` (`Publish Docs`) builds `docs/`
  with `uv run mkdocs build --strict` and deploys the `site/` artifact through
  GitHub Pages.

This repository does not vendor purchased source exports, local model caches,
traces, secrets, database files, logs, or private benchmark payloads.

## Current Boundary

This is not full production certification. MacBook proof, fake-backend Docker
proof, Open WebUI proof, Phoenix tracing, MkDocs, release/no-leak checks, and
benchmark structure are complete for local learning. The test-double cluster
routing contract is code-backed, but real multi-node proof is still required
before any Mac Studio cluster claim. Mac Studio cluster capacity, failover, and
multi-user performance remain pending until real cluster evidence exists.

The native proofs are still not production UX or performance benchmarks. The
current Qwen3/Open WebUI operator path does prove a visible assistant answer:
`artifacts/runtime/2026-06-28T195945+0200-open-webui-visible-answer-no-think/`.

## Quick Start

```bash
uv sync
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

Runtime evidence uses `mac_llm_ops_lab.runtime_artifacts` to label git SHA,
command, host, backend, model, artifact directory, log path, runtime config, and
ports. Evidence manifests and bundle indexes stay under ignored
`artifacts/runtime/`.

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

The saved model-backed API evidence covers `/live`, `/ready`, `/v1/models`,
non-streaming chat, streaming chat, `/metrics/snapshot`, backend metrics, and
Phoenix spans:

- `artifacts/runtime/2026-06-28T153000+0200-model-backed-api-e2e/`
- `artifacts/runtime/2026-06-28T173605+0200-vllm-mlx-phoenix-real-backend/`
- `artifacts/runtime/2026-06-28T174936+0200-open-webui-native-backend/`

## Docs Map

- [Development](docs/development.md): setup, validation, native backend starts.
- [Operations](docs/operations.md): Docker, Open WebUI, and Phoenix runbook.
- [Design](docs/design.md): architecture, request, and evidence diagrams.
- [Evidence](docs/evidence.md): runtime proofs, persistence, telemetry, and benchmarks.
- [Mac Studio Cluster](docs/mac-studio-cluster.md): unsupported cluster claims.
- [Release Readiness](docs/release-readiness.md): public repo and no-leak gate.
