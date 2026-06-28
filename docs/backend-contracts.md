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

## Benchmark Workload Policy

The machine-readable policy is exposed by
`mac_llm_ops_lab.backend_contracts.build_benchmark_workload_policy()`.
It is grounded in the book's benchmark process from chapter 9, the chapter 4
latency/throughput metric split, and the OpenTelemetry benchmark guidance to
warm up before measurement, repeat runs, and label the target platform. It also
keeps GenAI telemetry attributes available in Phoenix evidence.

Benchmark results must name one of these workloads before any interpretation:

| Workload | Role | Required shape |
| --- | --- | --- |
| `smoke_short` | Command-surface, parser, metrics, and trace smoke only. | Short prompt set, concurrency 1, token targets 4/16/64, no production claim. |
| `conversational_sharegpt` | Interactive chat baseline with realistic turn lengths. | ShareGPT-style prompt set, input token distribution, output token target 64/128/256, concurrency sweep 1/2/4, request-rate sweep, warmup, and repetitions. |
| `prefix_repetition_cache` | Cache and repeated-prefix behavior under controlled reuse. | Prefix Repetition prompt set, prefix/suffix/unique-prefix parameters, output token target 64/128, concurrency sweep 1/2/4, request-rate sweep, warmup, repetitions, and cache metrics. |

Production-eligible benchmark rows require `warmup` traffic before measurement
and at least three `repetitions`. The `smoke_short` row may keep
`validated:false`; `validated:false is smoke-only` and cannot support quality,
UX, latency, throughput, cost, or Mac Studio capacity claims.

Each benchmark artifact must carry enough metadata to make the result
reproducible and auditable:

- `git_sha`, command, backend name/version, model id, model revision,
  quantization, prompt set, input token distribution, output token target,
  concurrency, request rate, burstiness, warmup, repetition index, and
  validation state.
- Hardware and OS labels: host chip, unified memory, macOS version, and the
  local API/backend/Phoenix/OTLP ports. Local bindings must stay in the
  `20000-50000` range.
- Metrics: TTFT, end-to-end latency, TPOT or ITL, total TPS, output TPS,
  request throughput, prompt tokens, completion tokens, error rate, Metal memory
  active/peak/cache values, cache hit rate, tokens saved, and Phoenix GenAI spans.

MacBook measurements are local baselines for this development host and must
respect the capsule-local 24 GiB real-model memory ceiling.
Mac Studio cluster claims require Mac Studio runs with node count, chip, memory,
network, model, routing, and trace evidence. A MacBook benchmark can inform the
cluster plan, but it is not cluster capacity proof.

## Benchmark Artifact Manifest

Every fuller benchmark bundle must include
`benchmark-artifact-manifest.json`, generated or loaded through
`mac_llm_ops_lab.backend_contracts`. The manifest is separate from the
runtime evidence manifest because benchmark proof needs raw workload rows,
summarized benchmark JSON, and a publish-safety result in one place.

Required manifest fields:

- `raw_benchmark_path`: the raw `vllm-mlx bench-serve` JSON rows inside the
  same ignored `artifacts/runtime/<run>/` bundle.
- `summary_path`: the summarized JSON report, normally
  `backend-contract-report.json`, built from raw rows and backend metrics.
- `git_sha`, command, model id, model revision, host chip, host memory, macOS
  label, high local ports, and benchmark env values.
- `no_leak_scan`: a JSON publish-safety summary inside the same artifact bundle
  with `passed: true` and `findings_count: 0`.

Malformed bundles fail validation. The manifest rejects absolute paths,
parent-traversal paths, paths outside `artifact_dir`, non-JSON benchmark or
summary paths, empty command/git/model/revision labels, missing host chip or
memory labels, empty env maps, local ports outside `20000-50000`, and failed
or nonzero no-leak scans.

## Current MacBook Baseline

The current local baseline bundle is ignored runtime evidence under
`artifacts/runtime/2026-06-28T183228+0200-slice15-macbook-benchmark/`.
It ran `mlx-community/Qwen3-0.6B-8bit` directly against the native backend on
port `28100` with high-port project API/Phoenix/PostgreSQL/OTLP services still
on `28020`, `26006`, `25432`, and `24317`.

The bundle contains 12 benchmark rows across `conversational_sharegpt` and
`prefix_repetition_cache`, concurrency levels 1 and 2, max tokens 64, three
repetitions, warmup 1, runtime preflight estimate 4.7 GiB against the 24 GiB
capsule ceiling, backend metrics before/after, `backend-contract-report.json`,
`benchmark-artifact-manifest.json`, API trace proof through request id
`req-slice15-benchmark-chat`, and a zero-finding publish-safety summary.

The structural benchmark contract passed and a local MacBook baseline was
recorded, but `production_performance_claim_supported: false`. All benchmark
rows are `validated:false` under the 64-token cap, so this evidence is not a
quality benchmark, production performance claim, UX proof, or Mac Studio
capacity claim.

## Boundaries

This contract does not prove a fuller production benchmark. The one-row
`bench-serve` smoke proves command surface, parser shape, and basic backend
latency/throughput evidence only.

Current status: metrics and benchmark parsing are code-backed.
Open WebUI against the native backend is now runtime-proven under
`artifacts/runtime/2026-06-28T174936+0200-open-webui-native-backend/`; a
fuller production benchmark remains separate.
