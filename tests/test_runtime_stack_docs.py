from pathlib import Path


def test_runtime_stack_docs_define_static_and_runtime_boundaries() -> None:
    docs_path = Path("docs/evidence.md")

    assert docs_path.exists()
    text = docs_path.read_text(encoding="utf-8")
    operations = Path("docs/operations.md").read_text(encoding="utf-8")
    development = Path("docs/development.md").read_text(encoding="utf-8")
    combined = " ".join([text, operations, development])

    for required in (
        "docker compose -f compose.yaml config --format json",
        "docker compose up -d --build",
        "http://localhost:28000",
        "http://localhost:26006",
        "http://localhost:23000",
        "artifacts/runtime/2026-06-28T145945+0200-e2e/",
        "/live",
        "/ready",
        "/v1/models",
        "PostgreSQL",
        "Phoenix",
        "Open WebUI",
        "vllm-mlx standalone smoke",
        "artifacts/runtime/2026-06-28T151600+0200-vllm-mlx/",
        "Model-backed project API",
        "artifacts/runtime/2026-06-28T153000+0200-model-backed-api-e2e/",
        "artifacts/runtime/2026-06-28T173605+0200-vllm-mlx-phoenix-real-backend/",
        "artifacts/runtime/2026-06-28T174936+0200-open-webui-native-backend/",
        "MAC_LLM_OPS_BACKEND_KIND=openai-compatible",
        "VLLM_MLX_PORT=28100",
        "API_PORT=28020",
        "127.0.0.1:23001",
        "host.docker.internal:28020/v1",
    ):
        assert required in combined

    assert "Do not run `docker compose up` yet" not in text
