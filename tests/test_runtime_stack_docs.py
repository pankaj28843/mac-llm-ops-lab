from pathlib import Path


def test_runtime_stack_docs_define_static_and_runtime_boundaries() -> None:
    docs_path = Path("docs/runtime-stack.md")

    assert docs_path.exists()
    text = docs_path.read_text(encoding="utf-8")

    for required in (
        "docker compose config",
        "PHOENIX_HOST_PORT=16006 docker compose up -d --build",
        "artifacts/runtime/2026-06-28T145945+0200-e2e/",
        "/live",
        "/ready",
        "/v1/models",
        "PostgreSQL",
        "Phoenix",
        "Open WebUI",
        "vllm-mlx standalone smoke",
        "artifacts/runtime/2026-06-28T151600+0200-vllm-mlx/",
        "Model-Backed Project API Smoke",
        "artifacts/runtime/2026-06-28T153000+0200-model-backed-api-e2e/",
        "MAC_LLM_OPS_BACKEND_KIND=openai-compatible",
        "Apple Silicon backend",
        "not complete",
    ):
        assert required in text

    assert "Do not run `docker compose up` yet" not in text
