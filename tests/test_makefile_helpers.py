import subprocess
from pathlib import Path


def _run_make(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["make", *args],
        capture_output=True,
        check=False,
        text=True,
    )


def test_makefile_help_lists_local_stack_helpers() -> None:
    result = _run_make("help")

    assert result.returncode == 0, result.stderr
    assert "Usage:" in result.stdout
    for target in ("help", "--help", "validate", "up", "down", "build", "status"):
        assert target in result.stdout


def test_makefile_default_target_is_help() -> None:
    result = _run_make()

    assert result.returncode == 0, result.stderr
    assert "Usage:" in result.stdout
    assert "make <target>" in result.stdout


def test_makefile_dash_dash_help_alias_targets_project_help() -> None:
    result = _run_make("--", "--help")

    assert result.returncode == 0, result.stderr
    assert "Usage:" in result.stdout
    assert "up" in result.stdout
    assert "status" in result.stdout


def test_makefile_local_stack_targets_use_compose_yaml() -> None:
    expected_commands = {
        "up": "docker compose -f compose.yaml up -d --build",
        "down": "docker compose -f compose.yaml down --remove-orphans",
        "build": "docker compose -f compose.yaml build",
        "status": "docker compose -f compose.yaml ps",
    }

    for target, expected_command in expected_commands.items():
        result = _run_make("-n", target)

        assert result.returncode == 0, result.stderr
        assert expected_command in result.stdout


def test_makefile_up_down_status_manage_docker_and_native_backend() -> None:
    expectations = {
        "up": (
            "scripts/local-runtime.sh start-docker",
            (
                "MAC_LLM_OPS_MODEL_DOWNLOAD_APPROVED=true "
                "MODEL_ID=mlx-community/Qwen3-0.6B-8bit "
                "scripts/local-runtime.sh start"
            ),
            (
                "MAC_LLM_OPS_BACKEND_KIND=openai-compatible "
                "MAC_LLM_OPS_MODEL_ALLOWLIST=mlx-community/Qwen3-0.6B-8bit "
                "docker compose -f compose.yaml up -d --build"
            ),
        ),
        "down": (
            "scripts/local-runtime.sh stop-managed",
            "scripts/local-runtime.sh stop-docker-vllm",
            "docker compose -f compose.yaml down --remove-orphans",
            "scripts/local-runtime.sh stop-ports",
        ),
        "build": (
            "scripts/local-runtime.sh start-docker",
            "docker compose -f compose.yaml build",
        ),
        "status": (
            "docker compose -f compose.yaml ps",
            "scripts/local-runtime.sh status",
        ),
    }

    for target, expected_commands in expectations.items():
        result = _run_make("-n", target)

        assert result.returncode == 0, result.stderr
        for expected_command in expected_commands:
            assert expected_command in result.stdout


def test_makefile_compose_targets_prepare_ignored_local_runtime_paths() -> None:
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "secrets/postgres_password.txt" in makefile
    assert "artifacts/runtime" in makefile

    for target in ("validate", "up", "down", "build", "status"):
        result = _run_make("-n", target)

        assert result.returncode == 0, result.stderr
        assert "mkdir -p secrets/ artifacts/runtime" in result.stdout
        assert "printf '%s\\n' \"local-dev-password\"" in result.stdout


def test_local_runtime_script_manages_project_host_processes() -> None:
    script = Path("scripts/local-runtime.sh")
    text = script.read_text(encoding="utf-8")

    assert script.stat().st_mode & 0o111
    for required in (
        "scripts/start-detached.py",
        "scripts/run-vllm-mlx-backend.sh",
        "MAC_LLM_OPS_START_TIMEOUT_SECONDS",
        "start-docker",
        "stop-managed",
        "stop-docker-vllm",
        "stop-ports",
        "docker desktop start",
        "docker ps",
        "lsof -ti",
        "pgrep -f",
        "vllm_mlx",
        "MAC_LLM_OPS_DOWN_KILL_PORTS",
    ):
        assert required in text

    assert 'start_service \\\n    "model-backed-api"' not in text
    assert "uv run mkdocs serve" not in text


def test_detached_launcher_starts_processes_in_new_sessions() -> None:
    launcher = Path("scripts/start-detached.py")
    text = launcher.read_text(encoding="utf-8")

    assert launcher.stat().st_mode & 0o111
    assert "subprocess.Popen" in text
    assert "stdin=subprocess.DEVNULL" in text
    assert "start_new_session=True" in text
    assert "pid_file.write_text" in text
