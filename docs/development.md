# Development

## Setup

```bash
uv sync
make help
```

This installs runtime and dev dependencies, including MkDocs for the local
learning site. `make help` lists the validation and local runtime lifecycle
helpers.

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
docker compose -f compose.yaml up -d --build docs
```

## Local API Smoke

The fake-backend ASGI app is safe to import without Docker, PostgreSQL,
Phoenix, Open WebUI, model downloads, or traces:

```bash
uv run python -c "from mac_llm_ops_lab.cli import app; print(app.title)"
```

For native model-backed development, start the MLX backend on the host and the
API in Docker:

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
MAC_LLM_OPS_BACKEND_KIND=openai-compatible \
MAC_LLM_OPS_MODEL_ALLOWLIST=mlx-community/Qwen3-0.6B-8bit \
docker compose -f compose.yaml up -d --build api
```

Do not run real-model work without the model download gate.

## Model Download Gate

The first approved local model is:

```text
model_id: mlx-community/Qwen3-0.6B-8bit
backend_id: vllm-mlx
revision: 11de96878523501bcaa86104e3c186de07ff9068
license: apache-2.0
library: mlx
pipeline: text-generation
cache_root: model-cache/huggingface
estimated_runtime_total_gib: 4.7
```

The CPU-safe gate denies by default with `runtime_not_authorized`:

```bash
uv run python -m mac_llm_ops_lab.model_catalog mlx-community/Qwen3-0.6B-8bit
```

To approve a local run or download, set the approval flag and save the report
under ignored runtime artifacts:

```bash
MAC_LLM_OPS_MODEL_DOWNLOAD_APPROVED=true \
MODEL_DOWNLOAD_GATE_REPORT=artifacts/runtime/vllm-mlx-model-download-gate.json \
uv run python -m mac_llm_ops_lab.model_catalog mlx-community/Qwen3-0.6B-8bit
```

`scripts/run-vllm-mlx-backend.sh` invokes the same gate before `vllm-mlx serve`.
The script defaults `MAC_LLM_OPS_MODEL_DOWNLOAD_APPROVED=false`, so future
starts cannot silently download or run a cataloged model without an operator
decision.
