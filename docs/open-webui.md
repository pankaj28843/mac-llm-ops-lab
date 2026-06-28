# Open WebUI

Open WebUI is the local operator/user front end for this project. It connects
to the FastAPI service through the OpenAI-compatible API surface.

## Source Surface

Version/source-surface: local `docsearch` tenant `openwebui` from
`https://docs.openwebui.com`, fetched pages `OpenAI-Compatible / Open WebUI`,
`Environment Variable Configuration / Open WebUI`, and
`API Endpoints / Open WebUI`; local Open WebUI image version is `main`, so
runtime smoke evidence is required before claiming workflow compatibility.

The relevant Open WebUI contract is protocol-oriented:

- `GET /v1/models` is recommended for model discovery and UI model selection.
- `POST /v1/chat/completions` is required for chat.
- Chat requests can include standard OpenAI parameters such as `temperature`,
  `top_p`, `max_tokens`, `max_completion_tokens`, `stop`, `seed`, and
  `logit_bias`.
- Docker-hosted Open WebUI must use a container-reachable URL. In this Compose
  stack the API service URL is `http://api:8000/v1`; from a standalone Open
  WebUI container targeting a host process, use `host.docker.internal`. From
  the host browser, the default Compose URL is `http://localhost:23000`.
  A standalone native-backend proof can bind Open WebUI on
  `http://127.0.0.1:23001` while it targets
  `http://127.0.0.1:28020/v1` through
  `http://host.docker.internal:28020/v1` from inside the container.

## Compose Configuration

`compose.yaml` starts Open WebUI with environment-owned local configuration:

```text
OPENAI_API_BASE_URLS=http://api:8000/v1
OPENAI_API_KEYS=local-dev-placeholder
WEBUI_AUTH=False
ENABLE_PERSISTENT_CONFIG=False
ENABLE_OLLAMA_API=False
```

`OPENAI_API_KEYS` is a local placeholder because this repository's local API
does not enforce provider authentication yet. Do not commit real provider keys.
When a real backend requires a key, pass it through local shell environment or a
secret manager, not through tracked files.

`ENABLE_PERSISTENT_CONFIG=False` keeps local container restarts aligned with
the environment variables instead of stale values saved in Open WebUI's data
volume. UI edits made in that mode are not the durable source of truth.

`WEBUI_AUTH=False` is only for this local single-user lab smoke. Production or
shared Mac Studio deployments need authentication, secret management, and a
separate operator access policy before exposing Open WebUI beyond localhost or
a private admin network.

`ENABLE_OLLAMA_API=False` disables Open WebUI's default Ollama probe. This
profile intentionally uses only this repository's OpenAI-compatible API, so
missing `host.docker.internal:11434` logs are not useful signal.

## API Compatibility

This project's API must stay compatible with the Open WebUI path:

```bash
curl http://localhost:28000/v1/models \
  -H 'Authorization: Bearer local-dev-placeholder'
```

```bash
curl http://localhost:28000/v1/chat/completions \
  -H 'Authorization: Bearer local-dev-placeholder' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "fake-local-model",
    "messages": [{"role": "user", "content": "hello webui"}],
    "temperature": 0.2,
    "max_completion_tokens": 32,
    "stream": false
  }'
```

The API accepts the placeholder bearer token without treating it as a secret,
returns OpenAI-style model records, returns non-streaming `usage`, and forwards
standard generation parameters to an OpenAI-compatible native backend such as
`vllm-mlx`.

## Runtime Proof

Open WebUI workflow integration is complete for the Docker Compose fake-backend
stack. The saved fake-backend evidence bundle is:

```text
artifacts/runtime/2026-06-28T163030+0200-open-webui/
```

That bundle shows:

- Open WebUI container is healthy and reachable at `http://localhost:23000`.
- Open WebUI sees the API model through `/v1/models`.
- A chat request submitted through Open WebUI reaches
  `/v1/chat/completions`.
- The browser renders the fake-backend response for `fake-local-model`.
- The saved evidence is publish-safe: no real API keys, cookies, JWTs, prompts
  that should stay private, local home paths, model cache contents, or database
  files.

Open WebUI workflow integration is also runtime-proven against the native
`vllm-mlx` backend through this repo's model-backed API. The saved native
evidence bundle is:

```text
artifacts/runtime/2026-06-28T174936+0200-open-webui-native-backend/
```

That proof used a separate high-port container so the Compose fake-backend UI
on `23000` stayed untouched:

```bash
docker run -d \
  --name mac-llm-ops-open-webui-native-174936 \
  -p 127.0.0.1:23001:8080 \
  -e ENABLE_PERSISTENT_CONFIG=False \
  -e ENABLE_OLLAMA_API=False \
  -e OPENAI_API_BASE_URLS=http://host.docker.internal:28020/v1 \
  -e OPENAI_API_KEYS=local-dev-placeholder \
  -e WEBUI_AUTH=False \
  ghcr.io/open-webui/open-webui:main
```

The native proof shows:

- Open WebUI was healthy and reachable at `http://127.0.0.1:23001`.
- Open WebUI discovered `mlx-community/Qwen3-0.6B-8bit`.
- Headed CDP submitted a chat through Open WebUI, and redacted network
  evidence shows `POST /api/chat/completions` returned 200 for that model.
- This repo's API on `http://127.0.0.1:28020/v1` and the native backend on
  `127.0.0.1:28100` both logged successful chat requests.
- API metrics showed `/v1/models` and `/v1/chat/completions` counts increased,
  and `tokens_generated_total` reached 151 for the native model.
- Phoenix spans after the saved watermark include `POST /v1/chat/completions`
  200, `gen_ai.stream`, `gen_ai.chat`, scheduler dispatch, and model/token
  attributes for `mlx-community/Qwen3-0.6B-8bit`.

Known caveats from the proof:

- Open WebUI background generation triggered one `/v1/chat/completions` 502
  after the successful foreground chat. The error is captured in metrics and
  Phoenix as `backend_generation_failed`.
- The tiny Qwen3 run is capped at 64 output tokens, so Open WebUI rendered a
  completed reasoning block with little visible final-answer text. Do not use
  this smoke as a UX quality or performance benchmark.
