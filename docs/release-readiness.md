# Release Readiness

This page is the public-repo handoff checklist. It keeps the repository honest
about what is complete, what is still pending, and what must never be
published.

## One Command

Run the local validation entrypoint:

```bash
make validate
```

`make validate` runs:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
docker compose -f compose.yaml config --format json
uv run mkdocs build --strict
uv run python scripts/validate-public-release.py --output artifacts/runtime/release-readiness/public-release-check.json
```

The public release scan writes `public-release-check/v1` JSON to:

```text
artifacts/runtime/release-readiness/public-release-check.json
```

That path is ignored by git and should be kept as local proof, not published as
source.

## Claim Checklist

| Claim | Evidence |
| --- | --- |
| Fake-backend API works in tests and Docker Compose. | `uv run pytest`; `docs/runtime-stack.md`; saved Docker E2E evidence. |
| PostgreSQL persistence is code-backed. | `tests/test_persistence_*`; `docs/persistence.md`; Alembic migration proof. |
| Phoenix/OpenTelemetry is prompt-safe by default. | `tests/test_observability.py`; `docs/observability.md`; Phoenix proof bundles. |
| Open WebUI reaches the API. | `tests/test_open_webui_integration.py`; `docs/open-webui.md`; browser evidence bundles. |
| `vllm-mlx` can run the approved small MLX model locally. | `docs/backends.md`; model catalog gate; runtime proof bundles. |
| MacBook benchmark baseline exists. | `docs/benchmarks.md`; `docs/backend-contracts.md`; local benchmark bundle. |
| Mac Studio cluster readiness is not claimed. | `docs/mac-studio-cluster.md`; real multi-node proof remains pending. |

## Do Not Publish

Do not publish or commit:

- `model-cache/`
- `artifacts/runtime/`
- `secrets/`
- `traces/`
- `data/`
- raw benchmark payloads
- database files
- local logs
- private EPUB exports from local ebook-management tools
- paths from Calibre Library
- local converted book trees outside this repository
- real provider keys, Hugging Face tokens, cookies, JWTs, or SSH keys

The public repo may mention the source URL and the reference repository, but it
must not vendor book text, purchased EPUB files, model weights, local traces, or
machine-local paths.

## external source Copyright Guard

Official source surface checked on 2026-06-28:

- [external source Terms of Service](https://github.com/pankaj28843/mac-llm-ops-lab/) says external source
  and its content providers retain ownership and copyright in site content and
  materials.
- [external source Membership Agreement](https://github.com/pankaj28843/mac-llm-ops-lab/)
  permits limited quoted portions with attribution, up to 250 words from a
  single text, and otherwise restricts publishing service content to third-party
  websites unless the agreement expressly allows it.
- [external source Rights and Permissions](https://github.com/pankaj28843/mac-llm-ops-lab/) directs
  reuse licensing through the Copyright Clearance Center or an explicit
  permission request.

For this public repo and GitHub Pages site, the rule is: links and short
paraphrase are allowed; no chapter text, no images, no screenshots, no tables,
no copied copyright notice, no converted book export, no purchased EPUB/PDF, and
no copied companion-repo code unless a future change records a reviewed license
basis.

## Current Honesty Boundary

This repo is production-style and evidence-driven, not production-certified.
MacBook proof, fake-backend Docker proof, Open WebUI proof, Phoenix tracing,
and benchmark structure are complete for local learning. Mac Studio cluster
capacity, failover, and multi-user performance remain pending until real
cluster evidence exists.
