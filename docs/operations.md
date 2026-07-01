# Operations

## Local Docker Stack

The local stack runs PostgreSQL, Phoenix, Open WebUI, and the fake-backend API.
Create a local placeholder password file before starting Compose:

```bash
mkdir -p secrets artifacts/runtime
printf 'local-dev-password\n' > secrets/postgres_password.txt
docker compose up -d --build
```

The Makefile wraps the local runtime lifecycle:

```bash
make build
make up
make status
make down
```

`make up` starts Docker, native `vllm-mlx` with
`mlx-community/Qwen3-0.6B-8bit`, the model-backed API, Compose configured for
the OpenAI-compatible backend, and the project-managed non-Docker docs server.
`make down` stops project-managed host processes first,
including native `vllm-mlx` and model-backed API processes when present, stops
matching `vllm`/MLX containers, brings Compose down, clears repo-specific host
listeners, and leaves Docker Desktop running for other projects. The helpers
create the ignored local password file with a placeholder value when it is
missing.

The default local endpoints are:

- API: `http://localhost:28000`
- Open WebUI: `http://localhost:23000`
- Phoenix: `http://localhost:26006`
- PostgreSQL: `localhost:25432`
- OTLP gRPC: `localhost:24317`
- Phoenix Prometheus: `http://localhost:29090`

All host bindings stay in the `20000-50000` range. Container-internal URLs use
service-native ports, such as `http://api:8000/v1` and
`http://phoenix:6006/v1/traces`.

## Probes

```bash
curl -fsS http://localhost:28000/live
curl -fsS http://localhost:28000/ready
curl -fsS http://localhost:28000/v1/models \
  -H 'Authorization: Bearer local-dev-placeholder'
curl -fsS http://localhost:26006/ >/dev/null
```

## Open WebUI

Compose starts Open WebUI with environment-owned local configuration:

```text
OPENAI_API_BASE_URLS=http://api:8000/v1
OPENAI_API_KEYS=local-dev-placeholder
WEBUI_AUTH=False
ENABLE_PERSISTENT_CONFIG=False
ENABLE_OLLAMA_API=False
```

`OPENAI_API_KEYS` is a local placeholder because this repository's local API
does not enforce provider authentication yet. Do not commit real provider keys.
`ENABLE_PERSISTENT_CONFIG=False` keeps local restarts aligned with environment
variables. `ENABLE_OLLAMA_API=False` disables the default Ollama probe.

The relevant Open WebUI contract is protocol-oriented:

- `GET /v1/models` is the model discovery path.
- `POST /v1/chat/completions` is the chat path.
- Chat requests may include standard parameters such as `temperature`,
  `max_completion_tokens`, and streaming controls.

Docker-hosted Open WebUI must use a container-reachable URL. In Compose it uses
`http://api:8000/v1`; from a standalone Open WebUI container targeting a host
API process, use `host.docker.internal`. From the host browser, the default
Compose URL is `http://localhost:23000`.

The native-backend proof used a standalone container on
`http://127.0.0.1:23001` targeting this repo's host API through
`http://host.docker.internal:28020/v1` while the host API listened on
`http://127.0.0.1:28020/v1` and the native backend listened on
`127.0.0.1:28100`.

Current native Open WebUI runs must budget enough tokens for a visible final
answer:

```bash
VLLM_MLX_MAX_TOKENS=512 \
VLLM_MLX_MAX_REQUEST_TOKENS=1024 \
VLLM_MLX_REASONING_PARSER=qwen3 \
VLLM_MLX_DEFAULT_CHAT_TEMPLATE_KWARGS='{"enable_thinking": false}' \
scripts/run-vllm-mlx-backend.sh
```

`vllm-mlx` with Qwen3 reasoning parsing may stream answer text under
`delta.reasoning_content` when the normal `content` field is empty. The project
API maps that to non-empty `delta.content` chunks so Open WebUI receives visible
assistant text. The acceptance check is browser-visible: the answer must render
in Open WebUI and the direct backend/API response must show that
`finish_reason` is not `length`.

## Phoenix

Compose exports OpenTelemetry traces to:

```text
MAC_LLM_OPS_OTEL_ENABLED=true
MAC_LLM_OPS_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://phoenix:6006/v1/traces
MAC_LLM_OPS_PHOENIX_PROJECT_NAME=mac-llm-ops-lab-local
```

For a host-run API against the locally mapped Phoenix port:

```bash
MAC_LLM_OPS_OTEL_ENABLED=true \
MAC_LLM_OPS_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:26006/v1/traces \
MAC_LLM_OPS_PHOENIX_PROJECT_NAME=mac-llm-ops-lab-local \
uv run uvicorn mac_llm_ops_lab.cli:app --host 127.0.0.1 --port 28020
```

Default telemetry does not capture prompts, completions, request bodies, HTTP
headers, API keys, exception messages, local file paths, or model-cache paths.
Keep any exported traces under ignored local runtime artifacts and publish only
sanitized summaries.

## Safety

Never commit local secrets, model caches, runtime artifacts, database files,
logs, traces, or raw benchmark payloads. Keep those under ignored directories.
