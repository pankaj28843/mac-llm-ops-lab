# Design

## Architecture

The project keeps delivery, policy, backend execution, persistence, and
observability separated.

- FastAPI owns the HTTP/OpenAI-compatible surface.
- Application code owns request shaping, backend selection, streaming behavior,
  metrics, and errors.
- Backend adapters hide execution details behind a small generation interface.
- Persistence uses repository and unit-of-work ports, with SQLAlchemy as an
  adapter.
- Observability is app-local and explicit: importing the ASGI app does not start
  exporters, connect to Phoenix, or download models.
- Runtime artifacts are structured evidence bundles, not source files.

<div class="mermaid">
flowchart LR
  Browser["Open WebUI or curl"] --> API["FastAPI OpenAI-compatible API"]
  API --> Policy["runtime guards and model catalog"]
  API --> Fake["fake backend"]
  API --> Adapter["OpenAI-compatible adapter"]
  Adapter --> Native["native vllm-mlx on Apple Silicon"]
  API --> DB["PostgreSQL metadata"]
  API --> OTel["OpenTelemetry spans"]
  OTel --> Phoenix["Phoenix"]
  API --> Evidence["artifacts/runtime evidence"]
</div>

## Request Flow

<div class="mermaid">
sequenceDiagram
  participant Client as Client
  participant API as FastAPI
  participant Backend as Backend adapter
  participant Store as PostgreSQL
  participant Trace as Phoenix
  Client->>API: /v1/chat/completions
  API->>Trace: prompt-safe HTTP span
  API->>Backend: generate or stream
  Backend-->>API: tokens and metrics
  API->>Store: metadata through Unit of Work
  API-->>Client: OpenAI-compatible response
</div>

## Backend Boundary

The fake backend is the default for tests and Compose. The native backend is a
host process reached through the OpenAI-compatible adapter. That keeps Apple
GPU execution outside the API container while the Docker stack still provides
PostgreSQL, Phoenix, Open WebUI, and the API service.

## Evidence Boundary

Code changes need tests. Runtime claims need saved evidence. Performance claims
need benchmark workload policy, raw rows, summaries, backend metrics, Phoenix
spans, and publish-safety scans. A MacBook baseline can guide the plan, but it
cannot prove Mac Studio cluster behavior.

<div class="mermaid">
flowchart TB
  Change["code or runtime change"] --> Tests["pytest and ruff"]
  Change --> Runtime["local runtime proof"]
  Runtime --> Bundle["ignored artifacts/runtime bundle"]
  Bundle --> Scan["public-release scan"]
  Tests --> Claim["supported docs claim"]
  Scan --> Claim
  Claim --> Boundary["explicit unsupported claims"]
</div>

## Reference Boundary

External examples, articles, repositories, and other source material are
reference-only background. This project owns its names, code, docs, tests,
evidence format, and macOS/Apple Silicon operating boundaries.
