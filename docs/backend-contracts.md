# Backend Metrics And Benchmark Contracts

This project treats native `vllm-mlx` runtime proof as two separate signals:

- Prometheus-style runtime metrics from `/metrics`.
- Bounded benchmark rows from `vllm-mlx bench-serve`.

The parser in `mac_llm_ops_lab.backend_contracts` is intentionally small
and dependency-free. It turns raw runtime output into JSON-safe summaries that
can be saved under ignored `artifacts/runtime/` bundles.

## Metrics Contract

The minimum `vllm-mlx` metrics surface for slice 10 includes:

- `vllm_mlx_http_requests_total`
- `vllm_mlx_inference_requests_total`
- `vllm_mlx_prompt_tokens_total`
- `vllm_mlx_completion_tokens_total`
- `vllm_mlx_model_loaded`
- `vllm_mlx_engine_type`
- `vllm_mlx_scheduler_waiting_requests`
- `vllm_mlx_scheduler_running_requests`
- `vllm_mlx_metal_memory_bytes`
- `vllm_mlx_cache_type`
- `vllm_mlx_cache_hits`, `vllm_mlx_cache_misses`,
  `vllm_mlx_cache_hit_rate`, `vllm_mlx_cache_memory_bytes`, and
  `vllm_mlx_cache_tokens_saved`

Those fields cover request volume, inference success, token accounting,
scheduler state, Apple Silicon Metal memory, and cache/batching-related
signals. Missing required metrics make the metrics contract fail, but the raw
text should still be saved for investigation.

## Benchmark Contract

Use `vllm-mlx bench-serve` for bounded HTTP benchmarks against a running native
backend:

```bash
uv tool run vllm-mlx bench-serve \
  --url http://127.0.0.1:28100 \
  --model mlx-community/Qwen3-0.6B-8bit \
  --prompts short \
  --concurrency 1 \
  --max-tokens 4 \
  --repetitions 1 \
  --warmup 0 \
  --format json \
  --output artifacts/runtime/<run>/bench-smoke.json
```

A tiny smoke may legitimately report `validated:false` when generation is too
short for quality checks. Keep that field in the summary. Treat
`validated:false` as acceptable for command-surface and metrics smoke only, not
as a quality benchmark pass.

The benchmark summary records model id, prompt set, concurrency, token limit,
latency, throughput, Metal memory, cache hits/misses, and validation state.

## Boundaries

This contract does not prove a fuller production benchmark. The one-row
`bench-serve` smoke proves command surface, parser shape, and basic backend
latency/throughput evidence only.

Current status: metrics and benchmark parsing are code-backed.
Open WebUI against the native backend is now runtime-proven under
`artifacts/runtime/2026-06-28T174936+0200-open-webui-native-backend/`; a
fuller production benchmark remains separate.
