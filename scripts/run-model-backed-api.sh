#!/usr/bin/env bash
set -euo pipefail

MODEL_ID="${MODEL_ID:-mlx-community/Qwen3-0.6B-8bit}"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8020}"

export MAC_LLM_OPS_BACKEND_KIND="${MAC_LLM_OPS_BACKEND_KIND:-openai-compatible}"
export MAC_LLM_OPS_OPENAI_BASE_URL="${MAC_LLM_OPS_OPENAI_BASE_URL:-http://127.0.0.1:8100/v1}"
export MAC_LLM_OPS_MODEL_ALLOWLIST="${MAC_LLM_OPS_MODEL_ALLOWLIST:-$MODEL_ID}"

uv run uvicorn mac_llm_ops_lab.cli:app --host "$API_HOST" --port "$API_PORT"
