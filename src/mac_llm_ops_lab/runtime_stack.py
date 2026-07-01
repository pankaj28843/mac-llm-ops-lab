RUNTIME_STACK_PLAN_SCHEMA_VERSION = "runtime-stack/v1"


def build_local_runtime_stack_plan() -> dict[str, object]:
    """Return the macOS-local runtime topology without causing side effects."""
    return {
        "schema_version": RUNTIME_STACK_PLAN_SCHEMA_VERSION,
        "platform": "macos-apple-silicon",
        "side_effects": {
            "starts_containers": False,
            "downloads_models": False,
            "requires_secrets": False,
        },
        "services": [
            _api_service(),
            _docs_service(),
            _postgres_service(),
            _phoenix_service(),
            _open_webui_service(),
            _apple_silicon_backend_service(),
        ],
    }


def _api_service() -> dict[str, object]:
    return {
        "name": "api",
        "runtime": "docker",
        "image": "mac-llm-ops-lab-api:local",
        "build_target": "api",
        "ports": {"api": 28000},
        "environment": {
            "MAC_LLM_OPS_BACKEND_KIND": "${MAC_LLM_OPS_BACKEND_KIND:-fake}",
            "MAC_LLM_OPS_OPENAI_BASE_URL": (
                "${MAC_LLM_OPS_OPENAI_BASE_URL:-http://host.docker.internal:28100/v1}"
            ),
            "MAC_LLM_OPS_OPENAI_TIMEOUT_SECONDS": (
                "${MAC_LLM_OPS_OPENAI_TIMEOUT_SECONDS:-30}"
            ),
            "MAC_LLM_OPS_MODEL_ALLOWLIST": "${MAC_LLM_OPS_MODEL_ALLOWLIST:-}",
            "MAC_LLM_OPS_OTEL_ENABLED": "${MAC_LLM_OPS_OTEL_ENABLED:-true}",
            "MAC_LLM_OPS_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": (
                "${MAC_LLM_OPS_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT:-"
                "http://phoenix:6006/v1/traces}"
            ),
            "MAC_LLM_OPS_PHOENIX_PROJECT_NAME": (
                "${MAC_LLM_OPS_PHOENIX_PROJECT_NAME:-mac-llm-ops-lab-local}"
            ),
        },
        "depends_on": {
            "phoenix": {"condition": "service_started"},
            "postgres": {"condition": "service_healthy"},
        },
    }


def _docs_service() -> dict[str, object]:
    return {
        "name": "docs",
        "runtime": "docker",
        "image": "mac-llm-ops-lab-docs:local",
        "build_target": "docs",
        "ports": {"docs": 28080, "container": 8000},
        "command": [
            "mkdocs",
            "serve",
            "--no-livereload",
            "-a",
            "0.0.0.0:8000",
        ],
        "depends_on": {},
    }


def _postgres_service() -> dict[str, object]:
    return {
        "name": "postgres",
        "runtime": "docker",
        "image": "postgres:16",
        "ports": {"postgres": 25432},
        "environment": {
            "POSTGRES_DB": "llm_serving",
            "POSTGRES_PASSWORD_FILE": "/run/secrets/postgres_password",
            "POSTGRES_USER": "llm_serving",
        },
        "secrets": {"postgres_password": "local-placeholder"},
        "healthcheck": [
            "pg_isready",
            "-U",
            "${POSTGRES_USER}",
            "-d",
            "${POSTGRES_DB}",
        ],
        "volumes": {"postgres-data": "/var/lib/postgresql/data"},
        "depends_on": {},
    }


def _phoenix_service() -> dict[str, object]:
    return {
        "name": "phoenix",
        "runtime": "docker",
        "image": "arizephoenix/phoenix:latest",
        "ports": {
            "ui": 26006,
            "otlp_grpc": 24317,
            "prometheus": 29090,
        },
        "environment": {
            "PHOENIX_SQL_DATABASE_URL": (
                "postgresql://llm_serving:local-placeholder@postgres:5432/llm_serving"
            ),
        },
        "depends_on": {
            "postgres": {"condition": "service_healthy"},
        },
    }


def _open_webui_service() -> dict[str, object]:
    return {
        "name": "open-webui",
        "runtime": "docker",
        "image": "ghcr.io/open-webui/open-webui:main",
        "ports": {"ui": 23000, "container": 8080},
        "environment": {
            "ENABLE_PERSISTENT_CONFIG": "False",
            "ENABLE_OLLAMA_API": "False",
            "OPENAI_API_BASE_URLS": "http://api:8000/v1",
            "OPENAI_API_KEYS": "local-dev-placeholder",
            "WEBUI_AUTH": "False",
        },
        "volumes": {"open-webui-data": "/app/backend/data"},
        "depends_on": {
            "api": {"condition": "service_started"},
        },
    }


def _apple_silicon_backend_service() -> dict[str, object]:
    return {
        "name": "apple-silicon-backend",
        "runtime": "direct-process",
        "enabled_by_default": True,
        "candidate": "vllm-mlx",
        "gate": {
            "requires_explicit_authorization": True,
            "requires_memory_preflight": True,
            "starts_containers": False,
            "downloads_models": False,
        },
        "cache_policy": {
            "model_cache": "model-cache/",
            "runtime_artifacts": "artifacts/runtime/",
        },
    }
