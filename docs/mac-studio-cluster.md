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

## Planned Shape

The likely first cluster shape is a private Mac Studio LAN where each node runs
a native `vllm-mlx` backend and a local health endpoint, while a router exposes
one OpenAI-compatible API surface. PostgreSQL stores inventory and benchmark
metadata. Phoenix receives spans from the router and nodes.
