# Mac LLM Ops Lab

Mac-first LLM serving lab for learning production serving patterns on Apple
Silicon. The first implementation target is a FastAPI service with fake-backend
tests, then observable local backend adapters and Mac Studio cluster proof.

This repository does not vendor the book export, local model caches, traces, or
private benchmark payloads.

## Development

The CPU-safe fake-backend ASGI target is:

```text
mac_llm_ops_lab.cli:app
```

It builds the FastAPI app with `FakeBatchedBackend`. Importing this target does
not download models, start Docker, connect to PostgreSQL, emit Phoenix traces,
or require Open WebUI or Mac Studio cluster services.

Future real-model runtime checks must pass the CPU-safe preflight guard in
`mac_llm_ops_lab.runtime_guard` first. The guard requires explicit
authorization and skips plans whose estimated model weights, KV cache, runtime
overhead, and service overhead exceed the configured memory ceiling. It can also
build a JSON-safe preflight report for future runtime evidence before any risky
command runs. Runtime guard tests also enforce the `.gitignore` policy for
local model caches, traces, raw benchmarks, logs, database files, and artifacts.
Future runtime runs can use `mac_llm_ops_lab.runtime_artifacts` to build a
JSON-safe evidence manifest with git SHA, command, host, backend, model,
artifact directory, and log path labels. Manifest paths must stay under
`artifacts/runtime/`, logs must stay inside the artifact directory, and required
runtime labels must be non-empty.
Execution records combine the preflight report and evidence manifest, exposing
the final execute/skip state while checking schema versions, boolean decision
shape, reason codes, manifest labels and paths, and backend/model consistency.
They can be persisted as sorted JSON under the validated artifact directory for
future runtime evidence bundles, then loaded back with the same validation
before downstream proof consumes them.
Evidence bundles can be indexed deterministically so logs, execution records,
request samples, metrics, traces, and benchmark files remain under the same
validated artifact directory. The bundle index can also be persisted as sorted
JSON beside the execution record.

`mac_llm_ops_lab.runtime_stack.build_local_runtime_stack_plan()` exposes a
macOS-local topology for API, PostgreSQL, Phoenix, Open WebUI, and a gated
native Apple Silicon backend path. The Docker-built fake-backend API stack has
now been run locally with Compose and probed through `/live`, `/ready`,
`/v1/models`, non-streaming chat, streaming chat, and `/metrics/snapshot`.
Phoenix and Open WebUI are exposed on high local ports by default to avoid
collisions with common developer services.
Evidence is saved under the ignored
`artifacts/runtime/2026-06-28T145945+0200-e2e/` bundle.

This is not yet full production proof: fuller benchmark qualification, MkDocs,
cluster routing, and release/no-leak checks are still pending.
PostgreSQL persistence now has
SQLAlchemy/Alembic code and a local migration plus sample insert/read proof
under ignored `artifacts/runtime/2026-06-28T154545+0200-postgres-persistence/`.
OpenTelemetry instrumentation is now code-backed for HTTP request spans,
scheduler dispatch, backend generation, streaming errors/tokens, and
SQLAlchemy Unit of Work transaction spans. Telemetry remains disabled by
default for imports and tests, while Compose enables API export to Phoenix via
`MAC_LLM_OPS_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://phoenix:6006/v1/traces`.
Phoenix receipt evidence is saved under ignored
`artifacts/runtime/2026-06-28T160713+0200-phoenix-otel/`; see
`docs/observability.md`.
Real-backend Phoenix evidence for the `openai-compatible` `vllm-mlx` path is
saved under ignored
`artifacts/runtime/2026-06-28T173605+0200-vllm-mlx-phoenix-real-backend/`.
A standalone `vllm-mlx` smoke did pass with
`mlx-community/Qwen3-0.6B-8bit`, including model download,
`/v1/models`, chat, streaming, and `/metrics`; evidence is saved under ignored
`artifacts/runtime/2026-06-28T151600+0200-vllm-mlx/`.
Future model downloads and native backend starts are gated by
`mac_llm_ops_lab.model_catalog` and require
`MAC_LLM_OPS_MODEL_DOWNLOAD_APPROVED=true` plus a passing 24 GiB memory preflight and
ignored cache policy. See `docs/model-catalog.md`.

The project API can now proxy to that native OpenAI-compatible backend:

```bash
MODEL_ID=mlx-community/Qwen3-0.6B-8bit \
VLLM_MLX_PORT=28100 \
scripts/run-vllm-mlx-backend.sh
```

```bash
MODEL_ID=mlx-community/Qwen3-0.6B-8bit \
MAC_LLM_OPS_BACKEND_KIND=openai-compatible \
MAC_LLM_OPS_OPENAI_BASE_URL=http://127.0.0.1:28100/v1 \
API_PORT=28020 \
scripts/run-model-backed-api.sh
```

That model-backed app/API path was probed through this repo's `/live`,
`/ready`, `/v1/models`, non-streaming chat, streaming chat, and
`/metrics/snapshot`; evidence is saved under ignored
`artifacts/runtime/2026-06-28T153000+0200-model-backed-api-e2e/`. Local secret
files belong under ignored `secrets/` paths and must not be committed.

Open WebUI workflow integration is now code-backed and runtime-proven against
the Docker Compose fake-backend stack. The API accepts Open WebUI-style
generation parameters, returns discoverable model records and non-streaming
usage, and forwards generation options to native OpenAI-compatible backends.
Open WebUI was recreated with `ENABLE_OLLAMA_API=False`, showed
`fake-local-model`, submitted a browser chat, and rendered the fake-backend
response. Evidence is saved under ignored
`artifacts/runtime/2026-06-28T163030+0200-open-webui/`.
Open WebUI is also runtime-proven against the native `vllm-mlx` model-backed
API path: a separate container on `127.0.0.1:23001` targeted
`http://host.docker.internal:28020/v1`, discovered
`mlx-community/Qwen3-0.6B-8bit`, submitted chat, and produced project API,
backend, metrics, and Phoenix evidence. That evidence is saved under ignored
`artifacts/runtime/2026-06-28T174936+0200-open-webui-native-backend/`.
The native proof includes caveats for one Open WebUI background-generation 502
and the 64-token Qwen3 smoke's limited visible answer text; it is connectivity
and trace proof, not a production UX/performance benchmark.

See `docs/runtime-stack.md` for the static-vs-runtime boundary before running
any Docker services.
See `docs/persistence.md` for the SQLAlchemy/Alembic persistence boundary and
local PostgreSQL migration proof.
See `docs/observability.md` for the OpenTelemetry/Phoenix configuration,
prompt-safety contract, and runtime proof gate.
See `docs/open-webui.md` for Open WebUI connection settings and workflow proof
requirements.
See `docs/model-catalog.md` for MLX model source evidence, local approval, and
cache policy.

For direct Python use:

```bash
uv run python -c "from mac_llm_ops_lab.cli import app; print(app.title)"
```

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
