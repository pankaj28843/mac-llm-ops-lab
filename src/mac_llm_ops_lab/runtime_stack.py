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
            _postgres_service(),
            _phoenix_service(),
            _open_webui_service(),
            _apple_silicon_backend_service(),
        ],
    }


def _api_service() -> dict[str, object]:
    return {
        "name": "api",
        "runtime": "direct-process",
        "command": [
            "uv",
            "run",
            "uvicorn",
            "mac_llm_ops_lab.cli:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ],
        "ports": {"api": 8000},
        "depends_on": {
            "phoenix": {"condition": "service_started"},
            "postgres": {"condition": "service_healthy"},
        },
    }


def _postgres_service() -> dict[str, object]:
    return {
        "name": "postgres",
        "runtime": "docker",
        "image": "postgres:16",
        "ports": {"postgres": 5432},
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
            "ui": 6006,
            "otlp_grpc": 4317,
            "prometheus": 9090,
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
        "ports": {"ui": 3000, "container": 8080},
        "environment": {
            "ENABLE_PERSISTENT_CONFIG": "False",
            "OPENAI_API_BASE_URLS": "http://host.docker.internal:8000/v1",
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
        "enabled_by_default": False,
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
