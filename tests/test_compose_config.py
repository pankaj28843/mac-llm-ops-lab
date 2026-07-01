import json
import shutil
import subprocess
from pathlib import Path

import pytest


def test_compose_yaml_is_valid_and_keeps_real_backend_native_gated() -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker CLI is not installed")

    compose_path = Path("compose.yaml")
    assert compose_path.exists()

    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(compose_path),
            "config",
            "--format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout)
    services = config["services"]

    assert {"api", "docs", "postgres", "phoenix", "open-webui"} <= set(services)
    assert "apple-silicon-backend" not in services

    api = services["api"]
    assert api["build"]["target"] == "api"
    assert api["environment"]["MAC_LLM_OPS_BACKEND_KIND"] == "fake"
    assert api["environment"]["MAC_LLM_OPS_OPENAI_BASE_URL"] == (
        "http://host.docker.internal:28100/v1"
    )
    assert api["environment"]["MAC_LLM_OPS_OPENAI_TIMEOUT_SECONDS"] == "30"
    assert api["environment"]["MAC_LLM_OPS_OTEL_ENABLED"] == "true"
    assert api["environment"]["MAC_LLM_OPS_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] == (
        "http://phoenix:6006/v1/traces"
    )
    assert api["environment"]["MAC_LLM_OPS_PHOENIX_PROJECT_NAME"] == (
        "mac-llm-ops-lab-local"
    )

    docs = services["docs"]
    assert docs["build"]["target"] == "docs"
    assert docs["image"] == "mac-llm-ops-lab-docs:local"

    postgres = services["postgres"]
    assert postgres["image"] == "postgres:16"
    assert postgres["environment"]["POSTGRES_PASSWORD_FILE"] == (
        "/run/secrets/postgres_password"
    )
    assert any(
        secret["target"] == "postgres_password" for secret in postgres["secrets"]
    )

    phoenix = services["phoenix"]
    assert phoenix["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert phoenix["environment"]["PHOENIX_SQL_DATABASE_URL"].startswith(
        "postgresql://",
    )

    open_webui = services["open-webui"]
    assert open_webui["image"] == "ghcr.io/open-webui/open-webui:main"
    assert open_webui["environment"]["OPENAI_API_BASE_URLS"] == ("http://api:8000/v1")
    assert open_webui["environment"]["ENABLE_OLLAMA_API"] == "False"

    published_ports = {
        service: sorted(
            int(publisher["published"]) for publisher in service_config.get("ports", [])
        )
        for service, service_config in services.items()
    }
    assert published_ports["postgres"] == [25432]
    assert published_ports["phoenix"] == [24317, 26006, 29090]
    assert published_ports["api"] == [28000]
    assert published_ports["docs"] == [28080]
    assert published_ports["open-webui"] == [23000]
    assert all(
        20000 <= port <= 50000
        for service_ports in published_ports.values()
        for port in service_ports
    )


def test_local_secret_files_stay_out_of_git() -> None:
    gitignore_text = Path(".gitignore").read_text(encoding="utf-8")

    assert "secrets/" in {
        line.strip()
        for line in gitignore_text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def test_compose_host_ports_are_overridable_for_local_collisions() -> None:
    compose_text = Path("compose.yaml").read_text(encoding="utf-8")

    assert "${POSTGRES_HOST_PORT:-25432}:5432" in compose_text
    assert "${PHOENIX_HOST_PORT:-26006}:6006" in compose_text
    assert "${OTLP_GRPC_HOST_PORT:-24317}:4317" in compose_text
    assert "${PHOENIX_PROMETHEUS_HOST_PORT:-29090}:9090" in compose_text
    assert "${API_HOST_PORT:-28000}:8000" in compose_text
    assert "${DOCS_HOST_PORT:-28080}:8000" in compose_text
    assert "${OPEN_WEBUI_HOST_PORT:-23000}:8080" in compose_text
