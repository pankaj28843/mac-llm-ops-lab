# Mac LLM Ops Lab

This repository is an independent Mac-first learning lab for production-style
LLM serving. It focuses on macOS, Apple Silicon, future Mac Studio clusters,
and local validation rather than copying third-party naming, source material,
or vendor-specific deployment shape.

## Learning Path

1. Read [Vision](vision.md) to understand why the project exists.
2. Read [Requirements](requirements.md) for current scope and non-goals.
3. Read [Design](design.md) for the architecture and boundary map.
4. Follow [Development](development.md) to run tests, linting, docs, and static
   Compose validation.
5. Follow [Operations](operations.md) to run the local Docker stack on high
   local ports.
6. Read [Mac Studio Cluster](mac-studio-cluster.md) before making any cluster
   claim.
7. Run [Release Readiness](release-readiness.md) before publishing or handing
   the repo to someone else.

## Clone And Run

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
docker compose -f compose.yaml config --format json
uv run mkdocs build --strict
docker compose -f compose.yaml up -d --build docs
```

The default local service ports are intentionally high: API
`http://localhost:28000`, Open WebUI `http://localhost:23000`, Phoenix
`http://localhost:26006`, PostgreSQL `localhost:25432`, OTLP gRPC
`localhost:24317`, Phoenix Prometheus `http://localhost:29090`, docs
`http://localhost:28080`, and native `vllm-mlx`
`http://127.0.0.1:28100`.
