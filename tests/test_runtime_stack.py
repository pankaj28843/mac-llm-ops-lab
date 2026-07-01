import json

from mac_llm_ops_lab.runtime_stack import (
    RUNTIME_STACK_PLAN_SCHEMA_VERSION,
    build_local_runtime_stack_plan,
)


def test_local_runtime_stack_plan_declares_real_services_without_side_effects() -> None:
    plan = build_local_runtime_stack_plan()

    assert plan["schema_version"] == RUNTIME_STACK_PLAN_SCHEMA_VERSION
    assert plan["platform"] == "macos-apple-silicon"
    assert plan["side_effects"] == {
        "starts_containers": False,
        "downloads_models": False,
        "requires_secrets": False,
    }
    assert json.loads(json.dumps(plan, sort_keys=True)) == plan

    services = {service["name"]: service for service in plan["services"]}
    assert set(services) == {
        "api",
        "docs",
        "postgres",
        "phoenix",
        "open-webui",
        "apple-silicon-backend",
    }

    postgres = services["postgres"]
    assert postgres["runtime"] == "docker"
    assert postgres["image"].startswith("postgres:")
    assert postgres["ports"] == {"postgres": 25432}
    assert "POSTGRES_PASSWORD_FILE" in postgres["environment"]
    assert "POSTGRES_PASSWORD" not in postgres["environment"]
    assert "pg_isready" in postgres["healthcheck"]
    assert postgres["volumes"] == {
        "postgres-data": "/var/lib/postgresql/data",
    }

    phoenix = services["phoenix"]
    assert phoenix["runtime"] == "docker"
    assert phoenix["image"] == "arizephoenix/phoenix:latest"
    assert phoenix["depends_on"] == {
        "postgres": {"condition": "service_healthy"},
    }
    assert phoenix["ports"] == {
        "ui": 26006,
        "otlp_grpc": 24317,
        "prometheus": 29090,
    }
    assert phoenix["environment"]["PHOENIX_SQL_DATABASE_URL"].startswith(
        "postgresql://",
    )

    open_webui = services["open-webui"]
    assert open_webui["runtime"] == "docker"
    assert open_webui["image"] == "ghcr.io/open-webui/open-webui:main"
    assert open_webui["ports"] == {"ui": 23000, "container": 8080}
    assert open_webui["environment"] == {
        "ENABLE_PERSISTENT_CONFIG": "False",
        "ENABLE_OLLAMA_API": "False",
        "OPENAI_API_BASE_URLS": "http://api:8000/v1",
        "OPENAI_API_KEYS": "local-dev-placeholder",
        "WEBUI_AUTH": "False",
    }
    assert open_webui["volumes"] == {"open-webui-data": "/app/backend/data"}

    api = services["api"]
    assert api["runtime"] == "docker"
    assert api["image"] == "mac-llm-ops-lab-api:local"
    assert api["build_target"] == "api"
    assert api["ports"] == {"api": 28000}
    assert api["environment"] == {
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
            "${MAC_LLM_OPS_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT:-http://phoenix:6006/v1/traces}"
        ),
        "MAC_LLM_OPS_PHOENIX_PROJECT_NAME": (
            "${MAC_LLM_OPS_PHOENIX_PROJECT_NAME:-mac-llm-ops-lab-local}"
        ),
    }
    assert api["depends_on"] == {
        "phoenix": {"condition": "service_started"},
        "postgres": {"condition": "service_healthy"},
    }

    docs = services["docs"]
    assert docs["runtime"] == "docker"
    assert docs["image"] == "mac-llm-ops-lab-docs:local"
    assert docs["build_target"] == "docs"
    assert docs["ports"] == {"docs": 28080, "container": 8000}
    assert docs["command"] == [
        "mkdocs",
        "serve",
        "--no-livereload",
        "-a",
        "0.0.0.0:8000",
    ]
    assert docs["depends_on"] == {}

    backend = services["apple-silicon-backend"]
    assert backend["runtime"] == "direct-process"
    assert backend["enabled_by_default"] is True
    assert backend["candidate"] == "vllm-mlx"
    assert backend["gate"] == {
        "requires_explicit_authorization": True,
        "requires_memory_preflight": True,
        "starts_containers": False,
        "downloads_models": False,
    }
    assert backend["cache_policy"] == {
        "model_cache": "model-cache/",
        "runtime_artifacts": "artifacts/runtime/",
    }
