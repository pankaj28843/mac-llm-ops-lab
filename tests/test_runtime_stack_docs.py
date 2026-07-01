from pathlib import Path


def test_runtime_stack_docs_define_static_and_runtime_boundaries() -> None:
    text = Path("README.md").read_text(encoding="utf-8")
    operations = Path("docs/operations.md").read_text(encoding="utf-8")
    development = Path("docs/development.md").read_text(encoding="utf-8")
    combined = " ".join([text, operations, development])

    for required in (
        "docker compose -f compose.yaml config --format json",
        "docker compose up -d --build",
        "http://localhost:28000",
        "http://localhost:26006",
        "http://localhost:23000",
        "/live",
        "/ready",
        "/v1/models",
        "PostgreSQL",
        "Phoenix",
        "Open WebUI",
        "Native Backend Smoke",
        "MAC_LLM_OPS_BACKEND_KIND=openai-compatible",
        "VLLM_MLX_PORT=28100",
        "docker compose -f compose.yaml up -d --build api",
        "host.docker.internal:28100/v1",
    ):
        assert required in combined

    assert "artifacts/runtime/2026-" not in combined
    assert "Do not run `docker compose up` yet" not in combined
