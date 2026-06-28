# Mac LLM Ops Lab

Mac-first LLM serving lab for learning production serving patterns on Apple
Silicon. The first implementation target is a FastAPI service with fake-backend
tests, then observable local backend adapters and Mac Studio cluster proof.

This repository does not vendor the book export, local model caches, traces, or
private benchmark payloads.

## Development

The CPU-safe fake-backend ASGI target is:

```text
mac_llm_ops_lab.cli:app
```

It builds the FastAPI app with `FakeBatchedBackend`. Importing this target does
not download models, start Docker, connect to PostgreSQL, emit Phoenix traces,
or require Open WebUI or Mac Studio cluster services.

Future real-model runtime checks must pass the CPU-safe preflight guard in
`mac_llm_ops_lab.runtime_guard` first. The guard requires explicit
authorization and skips plans whose estimated model weights, KV cache, runtime
overhead, and service overhead exceed the configured memory ceiling. It can also
build a JSON-safe preflight report for future runtime evidence before any risky
command runs. Runtime guard tests also enforce the `.gitignore` policy for
local model caches, traces, raw benchmarks, logs, database files, and artifacts.
Future runtime runs can use `mac_llm_ops_lab.runtime_artifacts` to build a
JSON-safe evidence manifest with git SHA, command, host, backend, model,
artifact directory, and log path labels. Manifest paths must stay under
`artifacts/runtime/`, logs must stay inside the artifact directory, and required
runtime labels must be non-empty.

For direct Python use:

```bash
uv run python -c "from mac_llm_ops_lab.cli import app; print(app.title)"
```

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
