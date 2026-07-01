COMPOSE_FILE ?= compose.yaml
COMPOSE ?= docker compose -f $(COMPOSE_FILE)
LOCAL_RUNTIME ?= scripts/local-runtime.sh
LOCAL_POSTGRES_PASSWORD ?= local-dev-password
MODEL_ID ?= mlx-community/Qwen3-0.6B-8bit
POSTGRES_PASSWORD_FILE ?= secrets/postgres_password.txt
PUBLIC_RELEASE_REPORT ?= artifacts/runtime/release-readiness/public-release-check.json

.DEFAULT_GOAL := help

.PHONY: help --help validate up down build status ensure-local-runtime-dirs

help: ## Show available Makefile targets.
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make <target>\n\nTargets:\n"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "  %-26s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

--help: help ## Alias for project help; invoke with `make -- --help`.

validate: ensure-local-runtime-dirs ## Run tests, linting, docs, Compose config, and release checks.
	uv run pytest
	uv run ruff check .
	uv run ruff format --check .
	$(COMPOSE) config --format json | python3 -m json.tool >/dev/null
	uv run mkdocs build --strict
	uv run python scripts/validate-public-release.py --output $(PUBLIC_RELEASE_REPORT)

up: ensure-local-runtime-dirs ## Start Docker plus project-managed host services.
	$(LOCAL_RUNTIME) start-docker
	MAC_LLM_OPS_MODEL_DOWNLOAD_APPROVED=true MODEL_ID=$(MODEL_ID) $(LOCAL_RUNTIME) start
	MAC_LLM_OPS_BACKEND_KIND=openai-compatible MAC_LLM_OPS_MODEL_ALLOWLIST=$(MODEL_ID) $(COMPOSE) up -d --build

down: ensure-local-runtime-dirs ## Stop project-managed host services and Docker stack.
	$(LOCAL_RUNTIME) stop-managed
	$(LOCAL_RUNTIME) stop-docker-vllm
	-$(COMPOSE) down --remove-orphans
	$(LOCAL_RUNTIME) stop-ports

build: ensure-local-runtime-dirs ## Build the local Docker images.
	$(LOCAL_RUNTIME) start-docker
	$(COMPOSE) build

status: ensure-local-runtime-dirs ## Show Docker and project-managed host service status.
	-$(COMPOSE) ps
	$(LOCAL_RUNTIME) status

ensure-local-runtime-dirs:
	@mkdir -p $(dir $(POSTGRES_PASSWORD_FILE)) artifacts/runtime
	@if [ ! -f "$(POSTGRES_PASSWORD_FILE)" ]; then \
		printf '%s\n' "$(LOCAL_POSTGRES_PASSWORD)" > "$(POSTGRES_PASSWORD_FILE)"; \
		echo "created $(POSTGRES_PASSWORD_FILE)"; \
	fi
