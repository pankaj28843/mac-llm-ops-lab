# Backends

## Fake Backend

The fake backend is deterministic, CPU-safe, and the default for tests and
Docker Compose. It proves the API contract, streaming behavior, metrics, and
Open WebUI compatibility without downloading a model.

## Native Apple Silicon Backend

The native backend path uses `vllm-mlx` outside Docker and the project API's
OpenAI-compatible adapter. The first approved local model is
`mlx-community/Qwen3-0.6B-8bit`.

```bash
MODEL_ID=mlx-community/Qwen3-0.6B-8bit \
VLLM_MLX_PORT=28100 \
VLLM_MLX_MAX_TOKENS=512 \
VLLM_MLX_MAX_REQUEST_TOKENS=1024 \
VLLM_MLX_REASONING_PARSER=qwen3 \
VLLM_MLX_DEFAULT_CHAT_TEMPLATE_KWARGS='{"enable_thinking": false}' \
scripts/run-vllm-mlx-backend.sh
```

```bash
MODEL_ID=mlx-community/Qwen3-0.6B-8bit \
MAC_LLM_OPS_BACKEND_KIND=openai-compatible \
MAC_LLM_OPS_OPENAI_BASE_URL=http://127.0.0.1:28100/v1 \
API_PORT=28020 \
scripts/run-model-backed-api.sh
```

The backend start path is gated by the model catalog, explicit local approval,
ignored cache policy, and memory preflight. The API container can point at a
host backend through `host.docker.internal` when needed.

## Why The Boundary Exists

Apple GPU access is host-native today, while PostgreSQL, Phoenix, Open WebUI,
and the fake-backend API can run cleanly in Docker. Keeping the backend as an
adapter lets the service teach production boundaries without pretending Docker
is the right place for every Apple Silicon workload.
