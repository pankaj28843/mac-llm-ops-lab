# Mac Studio Cluster

Mac Studio cluster support is the next platform goal, not a completed claim.
This page defines what must exist before the repo can say it supports cluster
operation.

## Required Evidence

- Node count, chip generation, unified memory, macOS version, thermal or power
  mode, and Apple GPU availability for each node.
- Network topology, service discovery, routing policy, health checks, retry
  behavior, and rollback behavior.
- Same model id, model revision, quantization, and benchmark workload policy
  across nodes unless a test explicitly varies one factor.
- Per-node API/backend logs, Phoenix/OpenTelemetry spans, benchmark rows,
  backend metrics, Metal memory/cache metrics, and publish-safety scans.
- A routed-cluster endpoint proof that separates single-node latency,
  aggregate throughput, failover behavior, and Open WebUI UX behavior.

## Current Status

The MacBook Pro baseline proves this repo can run an approved small MLX model,
serve through the native backend and project API on high local ports, emit
Phoenix traces, and produce a structurally valid benchmark bundle. It does not
prove Mac Studio cluster capacity.

The current code-backed preparation lives in
`mac_llm_ops_lab.cluster`. It is intentionally side-effect-free so the
cluster logic can be tested on one MacBook before real Mac Studio hardware
exists.

## Code-Backed Contracts

`ClusterNode` is the fake-node and future inventory shape. A node records:

- node id and hostname
- API and backend base URLs
- backend id
- chip and unified memory
- served models
- queue depth
- readiness and health
- capabilities
- local service ports, which must stay in the `20000-50000` range

`route_to_model` is conservative. It only routes to registered nodes that are
both healthy and ready and that explicitly list the requested model. Among
eligible nodes, it selects `least_queue_depth`. If no registered node can serve
the model, it returns the local rollback decision with
`no_healthy_registered_node` and `fallback: true`.

`cluster-evidence-manifest/v1` is the future multi-node proof schema. A valid
manifest records git SHA, command, artifact directory, node inventory, route
decisions, and one evidence set per node. Each node evidence set must include:

- `api_log`
- `backend_log`
- `phoenix_spans`
- `metrics`

This manifest is not real multi-node proof by itself. It is the contract that
future real multi-node proof must satisfy before the project claims Mac Studio
cluster readiness.

## Node Evidence Capture

`mac-studio-node-evidence/v1` is the per-node capture shape for future Mac
Studio runs. Generate one `node-evidence.json` per Apple Silicon node, then
reference those node bundles from `cluster-evidence-manifest/v1`.

The command is intentionally explicit so the generated JSON can be reviewed and
reproduced:

```bash
python -m mac_llm_ops_lab.cluster node-evidence \
  --node-id macbook-pro-local \
  --hostname macbook-pro.local \
  --api-base-url http://127.0.0.1:28020/v1 \
  --backend-base-url http://127.0.0.1:28100/v1 \
  --backend-id vllm-mlx \
  --chip "Apple M3 Max" \
  --memory-gib 36 \
  --model-id mlx-community/Qwen3-0.6B-8bit \
  --model-revision 11de96878523501bcaa86104e3c186de07ff9068 \
  --macos-version 15.5 \
  --capability mlx \
  --capability openai-compatible \
  --capability streaming \
  --capability otel \
  --port api=28020 \
  --port backend=28100 \
  --port phoenix=26006 \
  --health-url api_ready=http://127.0.0.1:28020/ready \
  --health-url backend_models=http://127.0.0.1:28100/v1/models \
  --phoenix-url http://127.0.0.1:26006 \
  --git-sha "$(git rev-parse --short HEAD)" \
  --command scripts/run-model-backed-api.sh \
  --artifact-dir artifacts/runtime/example-node \
  --api-log artifacts/runtime/example-node/api.log \
  --backend-log artifacts/runtime/example-node/backend.log \
  --phoenix-spans artifacts/runtime/example-node/phoenix-spans.json \
  --metrics artifacts/runtime/example-node/metrics.json \
  --output artifacts/runtime/example-node/node-evidence.json
```

Every local binding in that report must use a high port in the `20000-50000`
range. The report rejects low ports such as `8000`, `6006`, `5432`, `4317`, or
`9090` for host-local bindings, rejects absolute or parent-traversal artifact
paths, and requires API logs, backend logs, Phoenix spans, metrics, command,
model revision, macOS version, and health URLs.

The generated report includes `requires_real_multi_node_proof: true`. A single
node report is useful setup evidence, but it does not complete real multi-node
proof. In short: node evidence capture does not complete real multi-node proof.
Cluster readiness still requires at least two Apple Silicon nodes with routing,
rollback, Phoenix/OpenTelemetry, benchmark, and publish-safety evidence.

## Planned Shape

The likely first cluster shape is a private Mac Studio LAN where each node runs
a native `vllm-mlx` backend and a local health endpoint, while a router exposes
one OpenAI-compatible API surface. PostgreSQL stores inventory and benchmark
metadata. Phoenix receives spans from the router and nodes.
