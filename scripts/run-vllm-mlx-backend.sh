#!/usr/bin/env bash
set -euo pipefail

MODEL_ID="${MODEL_ID:-mlx-community/Qwen3-0.6B-8bit}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-$MODEL_ID}"
HOST="${VLLM_MLX_HOST:-127.0.0.1}"
PORT="${VLLM_MLX_PORT:-28100}"
HF_HOME="${HF_HOME:-$PWD/model-cache/huggingface}"
MAC_LLM_OPS_MODEL_DOWNLOAD_APPROVED="${MAC_LLM_OPS_MODEL_DOWNLOAD_APPROVED:-false}"
MODEL_DOWNLOAD_GATE_REPORT="${MODEL_DOWNLOAD_GATE_REPORT:-artifacts/runtime/vllm-mlx-model-download-gate.json}"
REASONING_PARSER="${VLLM_MLX_REASONING_PARSER-}"
DEFAULT_CHAT_TEMPLATE_KWARGS="${VLLM_MLX_DEFAULT_CHAT_TEMPLATE_KWARGS-}"

if [[ -z "${VLLM_MLX_REASONING_PARSER+x}" ]]; then
  REASONING_PARSER="qwen3"
fi

if [[ -z "${VLLM_MLX_DEFAULT_CHAT_TEMPLATE_KWARGS+x}" ]]; then
  DEFAULT_CHAT_TEMPLATE_KWARGS='{"enable_thinking": false}'
fi

export HF_HOME
export MAC_LLM_OPS_MODEL_DOWNLOAD_APPROVED

uv run python -m mac_llm_ops_lab.model_catalog "$MODEL_ID" \
  --report-path "$MODEL_DOWNLOAD_GATE_REPORT"

args=(
  "$MODEL_ID"
  --served-model-name "$SERVED_MODEL_NAME" \
  --host "$HOST" \
  --port "$PORT" \
  --max-tokens "${VLLM_MLX_MAX_TOKENS:-512}" \
  --max-request-tokens "${VLLM_MLX_MAX_REQUEST_TOKENS:-1024}" \
  --cache-memory-mb "${VLLM_MLX_CACHE_MEMORY_MB:-512}" \
  --enable-metrics
)

if [[ -n "$REASONING_PARSER" ]]; then
  args+=(--reasoning-parser "$REASONING_PARSER")
fi

if [[ -n "$DEFAULT_CHAT_TEMPLATE_KWARGS" ]]; then
  args+=(--default-chat-template-kwargs "$DEFAULT_CHAT_TEMPLATE_KWARGS")
fi

uv tool run vllm-mlx serve "${args[@]}"
