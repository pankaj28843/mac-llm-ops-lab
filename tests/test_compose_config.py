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

    assert {"api", "postgres", "phoenix", "open-webui"} <= set(services)
    assert "apple-silicon-backend" not in services

    api = services["api"]
    assert api["environment"]["MAC_LLM_OPS_BACKEND_KIND"] == "fake"
    assert api["environment"]["MAC_LLM_OPS_OPENAI_BASE_URL"] == (
        "http://host.docker.internal:8100/v1"
    )
    assert api["environment"]["MAC_LLM_OPS_OPENAI_TIMEOUT_SECONDS"] == "30"

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


def test_local_secret_files_stay_out_of_git() -> None:
    gitignore_text = Path(".gitignore").read_text(encoding="utf-8")

    assert "secrets/" in {
        line.strip()
        for line in gitignore_text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def test_compose_host_ports_are_overridable_for_local_collisions() -> None:
    compose_text = Path("compose.yaml").read_text(encoding="utf-8")

    assert "${POSTGRES_HOST_PORT:-5432}:5432" in compose_text
    assert "${PHOENIX_HOST_PORT:-6006}:6006" in compose_text
    assert "${OTLP_GRPC_HOST_PORT:-4317}:4317" in compose_text
    assert "${PHOENIX_PROMETHEUS_HOST_PORT:-9090}:9090" in compose_text
    assert "${API_HOST_PORT:-8000}:8000" in compose_text
    assert "${OPEN_WEBUI_HOST_PORT:-3000}:8080" in compose_text
