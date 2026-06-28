# Development

## Setup

```bash
uv sync
```

This installs runtime and dev dependencies, including MkDocs for the local
learning site.

## Validation

Run the CPU-safe checks before changing runtime behavior:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
docker compose -f compose.yaml config --format json
uv run mkdocs build --strict
```

Preview the docs on a high local port:

```bash
uv run mkdocs serve -a 127.0.0.1:28080
```

## Local API Smoke

The fake-backend ASGI app is safe to import without Docker, PostgreSQL,
Phoenix, Open WebUI, model downloads, or traces:

```bash
uv run python -c "from mac_llm_ops_lab.cli import app; print(app.title)"
```

For native model-backed development, start the backend and API on high ports:

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

Do not run real-model work without the model catalog approval and memory
preflight described in [Model Catalog](model-catalog.md).
