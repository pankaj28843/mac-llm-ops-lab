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
